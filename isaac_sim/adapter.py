"""Isaac Sim implementation of the simulator ports.

Construct this class only after creating `isaacsim.SimulationApp`.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from meatcell.clock import FixedStepClock
from meatcell.contracts import CutterMode, CutterState, Quaternion, SimTime, Transform, Vector3
from meatcell.ports import CameraSample, ContactSample, RobotCommand, RobotState
from meatcell.product_profiles import ProductProfile, load_product_catalog

from .adapter_config import IsaacCellPaths
from .stage_builder import IsaacStageBuilder
from .video_recorder import RawVideoRecorder, VideoRecording


class IsaacSimulatorAdapter:
    def __init__(
        self,
        simulation_app: Any,
        *,
        physics_hz: int = 240,
        render_hz: int = 60,
        product_profile: ProductProfile | None = None,
        enable_instance_segmentation: bool = False,
    ) -> None:
        if physics_hz <= 0 or render_hz <= 0 or physics_hz % render_hz != 0:
            raise ValueError("Physics and render rates must be positive with render rate dividing physics rate")
        self.simulation_app = simulation_app
        self.physics_hz = physics_hz
        self.render_hz = render_hz
        self.product_profile = product_profile or load_product_catalog().get("beef_center_cut_tenderloin")
        self.enable_instance_segmentation = enable_instance_segmentation
        self.paths = IsaacCellPaths()
        self.builder = IsaacStageBuilder(self.paths, self.product_profile)
        self.clock = FixedStepClock(physics_hz)
        self.world: Any = None
        self.stage: Any = None
        self.robot: Any = None
        self.controller: Any = None
        self.cameras: dict[str, Any] = {}
        self.contact_sensors: dict[str, Any] = {}
        self.finger_contact_view: Any = None
        self.products: dict[str, Any] = {}
        self.product_paths: dict[str, str] = {}
        self.solution = "a"
        self._attached_product: str | None = None
        self._grasp_joint_path = f"{self.paths.robot}/Joints/active_grasp"
        self._belt_speed_mps = 2.24
        self._cutter_mode = CutterMode.READY
        self._recipe_id = self.product_profile.recipe_id
        self._permissive_sequence = 1
        self._fault_active = False
        self._emergency_stop = False
        self._result_ack = False
        self._last_command_positions: tuple[float, ...] | None = None
        self._last_command_velocities: tuple[float, ...] | None = None
        self._joint_limit_violations = 0
        self._world_step_offset = 0
        self._recent_product_contacts: dict[tuple[str, str], SimTime] = {}
        self._video_recorder: RawVideoRecorder | None = None
        self._video_step_interval: int | None = None
        self._closed = False

    @property
    def simulation_time(self) -> SimTime:
        return self.clock.now

    @property
    def conveyor_speed_mps(self) -> float:
        return self._belt_speed_mps

    @property
    def fault_active(self) -> bool:
        return self._fault_active

    @property
    def emergency_stop_active(self) -> bool:
        return self._emergency_stop

    @property
    def result_acknowledged(self) -> bool:
        return self._result_ack

    @property
    def product_center_z_m(self) -> float:
        return 0.04 + self.product_profile.geometry.height_m.nominal / 2.0 + 0.002

    def create_cell(self, solution: str) -> None:
        import omni.usd
        from isaacsim.core.api import World
        from isaacsim.core.utils.extensions import enable_extension
        from isaacsim.core.prims import RigidPrim, SingleArticulation, SingleRigidPrim
        from isaacsim.sensors.camera import Camera

        enable_extension("isaacsim.sensors.experimental.physics")
        self.simulation_app.update()

        World.clear_instance()
        omni.usd.get_context().new_stage()
        self.world = World(
            physics_dt=1.0 / self.physics_hz,
            rendering_dt=1.0 / self.render_hz,
            stage_units_in_meters=1.0,
            physics_prim_path=self.paths.physics_scene,
            backend="numpy",
            device="cpu",
        )
        self.stage = omni.usd.get_context().get_stage()
        self.solution = solution
        self._recipe_id = self.product_profile.recipe_id
        build = self.builder.build(self.stage, solution)
        from isaacsim.sensors.experimental.physics import Contact, ContactSensor

        for name, body_path in (("left", self.paths.finger_left), ("right", self.paths.finger_right)):
            sensor_path = f"{body_path}/contact_sensor"
            Contact.create(sensor_path, min_threshold=0.0, max_threshold=100000.0, radius=-1.0)
            self.contact_sensors[name] = ContactSensor(sensor_path)
        self.robot = self.world.scene.add(SingleArticulation(self.paths.robot, name="generic_cartesian_robot"))
        self.finger_contact_view = self.world.scene.add(
            RigidPrim(
                [self.paths.finger_left, self.paths.finger_right],
                name="finger_product_contact_view",
                reset_xform_properties=False,
                track_contact_forces=True,
                contact_filter_prim_paths_expr=[
                    [f"{self.paths.products}/MeatReference_000"],
                    [f"{self.paths.products}/MeatReference_000"],
                ],
                max_contact_count=64,
            )
        )
        for index, path in enumerate(build["product_paths"]):
            product_id = f"product-{index:03d}"
            wrapper = self.world.scene.add(SingleRigidPrim(path, name=f"meat_reference_{index:03d}"))
            self.products[product_id] = wrapper
            self.product_paths[product_id] = path
        self.world.reset()
        self.controller = self.robot.get_articulation_controller()
        overhead = Camera(self.paths.overhead_camera, name="overhead_camera", resolution=(640, 480), frequency=self.render_hz)
        wrist = Camera(self.paths.wrist_camera, name="wrist_camera", resolution=(400, 300), frequency=self.render_hz)
        for name, camera in (("overhead", overhead), ("wrist", wrist)):
            camera.initialize()
            camera.add_distance_to_image_plane_to_frame()
            if self.enable_instance_segmentation and name == "overhead":
                camera.add_instance_segmentation_to_frame(init_params={"colorize": False})
            self.cameras[name] = camera
        for _ in range(12):
            self.world.render()
        for product in self.products.values():
            product.set_linear_velocity((self._belt_speed_mps, 0.0, 0.0))
        self.clock.reset()
        self._world_step_offset = int(self.world.current_time_step_index)

    def step_once(self) -> SimTime:
        if self.world is None:
            raise RuntimeError("Cell is not created")
        for product_id, product in self.products.items():
            if product_id != self._attached_product:
                pose = self.get_product_pose(product_id)
                velocity = product.get_linear_velocity()
                on_conveyor = abs(pose.translation.y_m) <= 0.40 and pose.translation.x_m < 2.30
                if velocity is not None and on_conveyor:
                    product.set_linear_velocity((self._belt_speed_mps, float(velocity[1]), float(velocity[2])))
        self.world.step(render=False, update_fabric=True)
        now = self.clock.step()
        actual_step = self.world.current_time_step_index - self._world_step_offset
        if abs(actual_step - self.clock.step_index) > 1:
            raise RuntimeError(f"Isaac fixed-step index diverged: Isaac={actual_step}, domain={self.clock.step_index}")
        if self._video_recorder is not None and self._video_step_interval is not None:
            if self.clock.step_index % self._video_step_interval == 0:
                self._record_overhead_frame()
        return now

    def start_video_recording(self, output_path: str, *, fps: int = 12) -> None:
        """Record the actual rendered overhead RGB stream at simulator time."""

        if self._video_recorder is not None:
            raise RuntimeError("A video recording is already active")
        if fps <= 0 or self.physics_hz % fps != 0:
            raise ValueError("Recording FPS must divide the fixed physics rate")
        self._video_recorder = RawVideoRecorder(Path(output_path), fps=fps, width=640, height=480)
        self._video_step_interval = self.physics_hz // fps
        self.world.render()
        self._record_overhead_frame()

    def _record_overhead_frame(self) -> None:
        import numpy as np

        if self._video_recorder is None:
            return
        self.world.render()
        image = self.cameras["overhead"].get_rgb()
        if image is None:
            raise RuntimeError("The overhead camera did not publish a frame for video recording")
        rgb8 = np.asarray(image)
        if rgb8.dtype != np.uint8:
            rgb8 = np.clip(rgb8 * (255.0 if rgb8.max(initial=0.0) <= 1.0 else 1.0), 0, 255).astype(np.uint8)
        rgb24 = np.ascontiguousarray(rgb8[..., :3])
        self._video_recorder.write_frame(rgb24.tobytes(), self.simulation_time.nanoseconds)

    def stop_video_recording(self) -> VideoRecording | None:
        recorder = self._video_recorder
        self._video_recorder = None
        self._video_step_interval = None
        return recorder.close() if recorder is not None else None

    def save_stage(self, path: str) -> str:
        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        self.stage.GetRootLayer().Export(str(target))
        return self.builder.signature(self.stage)

    def reload_stage(self, path: str) -> str:
        from pxr import Usd

        loaded = Usd.Stage.Open(str(Path(path).resolve()))
        if loaded is None:
            raise RuntimeError(f"Could not reload USD stage: {path}")
        return self.builder.signature(loaded)

    def prim_paths(self) -> tuple[str, ...]:
        return tuple(sorted(prim.GetPath().pathString for prim in self.stage.Traverse()))

    def _dynamic_product(self, product_id: str, path: str) -> Any:
        from isaacsim.core.prims import SingleRigidPrim

        wrapper = SingleRigidPrim(path, name=f"dynamic_{product_id}")
        wrapper.initialize()
        return wrapper

    def create_product(self, product_id: str, pose_world: Transform, mass_kg: float) -> None:
        if product_id in self.products or mass_kg <= 0.0:
            raise ValueError("Product requires unique ID and positive mass")
        safe_name = "".join(character if character.isalnum() or character == "_" else "_" for character in product_id)
        path = f"{self.paths.products}/{safe_name}"
        self.builder._build_product(
            self.stage,
            len(self.products),
            (
                pose_world.translation.x_m,
                pose_world.translation.y_m,
                pose_world.translation.z_m,
            ),
            path_override=path,
        )
        wrapper = self._dynamic_product(product_id, path)
        self.products[product_id] = wrapper
        self.product_paths[product_id] = path

    def remove_product(self, product_id: str) -> None:
        self.stage.RemovePrim(self.product_paths.pop(product_id))
        self.products.pop(product_id)

    def get_product_pose(self, product_id: str) -> Transform:
        position, orientation = self.products[product_id].get_world_pose()
        return Transform(
            Vector3(float(position[0]), float(position[1]), float(position[2])),
            Quaternion(float(orientation[0]), float(orientation[1]), float(orientation[2]), float(orientation[3])),
        )

    def set_product_pose(self, product_id: str, pose_world: Transform) -> None:
        import numpy as np

        pose = pose_world
        self.products[product_id].set_world_pose(
            position=np.array([pose.translation.x_m, pose.translation.y_m, pose.translation.z_m]),
            orientation=np.array([pose.rotation.w, pose.rotation.x, pose.rotation.y, pose.rotation.z]),
        )
        self.products[product_id].set_linear_velocity((self._belt_speed_mps, 0.0, 0.0))

    def set_product_velocity(self, product_id: str, velocity_mps: tuple[float, float, float]) -> None:
        self.products[product_id].set_linear_velocity(velocity_mps)

    def get_product_velocity(self, product_id: str) -> tuple[float, float, float]:
        velocity = self.products[product_id].get_linear_velocity()
        return tuple(float(item) for item in velocity)

    def camera_arrays(self, camera_id: str) -> tuple[Any, Any, dict[str, Any]]:
        try:
            camera = self.cameras[camera_id]
        except KeyError as exc:
            raise KeyError(f"Unknown camera: {camera_id}") from exc
        for _ in range(3):
            self.world.render()
        rgb = camera.get_rgb()
        depth = camera.get_depth()
        frame = camera.get_current_frame(clone=True)
        if rgb is None or depth is None:
            raise RuntimeError(f"Camera {camera_id} did not publish RGB and depth after warmup")
        return rgb, depth, frame

    def capture_rgbd(self, camera_id: str, output_directory: str | None = None) -> CameraSample:
        import numpy as np
        from PIL import Image

        rgb, depth, _ = self.camera_arrays(camera_id)
        rgb8 = np.asarray(rgb)
        if rgb8.dtype != np.uint8:
            rgb8 = np.clip(rgb8 * (255.0 if rgb8.max(initial=0.0) <= 1.0 else 1.0), 0, 255).astype(np.uint8)
        depth32 = np.asarray(depth, dtype=np.float32)
        rgb_hash = hashlib.sha256(rgb8.tobytes()).hexdigest()
        depth_hash = hashlib.sha256(depth32.tobytes()).hexdigest()
        rgb_path = None
        depth_path = None
        if output_directory:
            output = Path(output_directory)
            output.mkdir(parents=True, exist_ok=True)
            stem = f"{camera_id}_{self.simulation_time.nanoseconds:012d}"
            rgb_target = output / f"{stem}_rgb.png"
            depth_target = output / f"{stem}_depth.npy"
            Image.fromarray(rgb8).save(rgb_target)
            np.save(depth_target, depth32)
            finite = np.where(np.isfinite(depth32), depth32, 0.0)
            maximum = float(finite.max(initial=0.0))
            preview = np.clip(finite / maximum * 255.0 if maximum else finite, 0, 255).astype(np.uint8)
            Image.fromarray(preview).save(output / f"{stem}_depth_preview.png")
            rgb_path = str(rgb_target.resolve())
            depth_path = str(depth_target.resolve())
        return CameraSample(
            camera_id,
            self.simulation_time,
            int(rgb8.shape[1]),
            int(rgb8.shape[0]),
            rgb_hash,
            depth_hash,
            rgb_path,
            depth_path,
            int(np.count_nonzero(np.any(rgb8 != 0, axis=-1))),
            int(np.count_nonzero(np.isfinite(depth32) & (depth32 > 0.0))),
        )

    @property
    def joint_names(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.robot.dof_names)

    def command_robot(self, command: RobotCommand) -> None:
        import numpy as np
        from isaacsim.core.utils.types import ArticulationAction

        names = self.joint_names
        current = tuple(float(item) for item in self.robot.get_joint_positions())
        targets = list(current)
        for name, target, velocity_limit, acceleration_limit in zip(
            command.joint_names,
            command.position_targets,
            command.velocity_limits,
            command.acceleration_limits,
            strict=True,
        ):
            if name not in names:
                raise ValueError(f"Unknown articulation joint: {name}")
            index = names.index(name)
            if velocity_limit <= 0.0 or acceleration_limit <= 0.0:
                raise ValueError("Robot velocity and acceleration limits must be positive")
            targets[index] = target
        if self._last_command_positions is not None:
            dt = 1.0 / self.physics_hz
            velocities = tuple((target - previous) / dt for target, previous in zip(targets, self._last_command_positions, strict=True))
            command_velocity = {name: limit for name, limit in zip(command.joint_names, command.velocity_limits, strict=True)}
            for index, name in enumerate(names):
                if name in command_velocity and abs(velocities[index]) > command_velocity[name] * 1.02:
                    raise ValueError(f"Command exceeds velocity limit for {name}")
            if self._last_command_velocities is not None:
                accelerations = tuple((velocity - previous) / dt for velocity, previous in zip(velocities, self._last_command_velocities, strict=True))
                command_accel = {name: limit for name, limit in zip(command.joint_names, command.acceleration_limits, strict=True)}
                for index, name in enumerate(names):
                    if name in command_accel and abs(accelerations[index]) > command_accel[name] * 1.02:
                        raise ValueError(f"Command exceeds acceleration limit for {name}")
            self._last_command_velocities = velocities
        self._last_command_positions = tuple(targets)
        lower = self.robot.dof_properties["lower"]
        upper = self.robot.dof_properties["upper"]
        if any(target < float(low) - 1e-6 or target > float(high) + 1e-6 for target, low, high in zip(targets, lower, upper, strict=True)):
            self._joint_limit_violations += 1
            raise ValueError("Command violates articulation joint limits")
        action = ArticulationAction(joint_positions=np.asarray(targets, dtype=np.float32))
        self.controller.apply_action(action)

    def reset_command_history(self) -> None:
        """Begin a new preflight-validated trajectory from measured state."""

        self._last_command_positions = None
        self._last_command_velocities = None

    def _tcp_from_positions(self, positions: tuple[float, ...]) -> Transform:
        names = self.joint_names
        values = {name: positions[index] for index, name in enumerate(names)}
        return Transform.planar(
            0.35 + values.get("x_axis", 0.0),
            values.get("y_axis", 0.0),
            1.10 + values.get("z_axis", 0.0) - 0.75,
            values.get("wrist_yaw", 0.0),
        )

    def read_robot_state(self) -> RobotState:
        import numpy as np

        positions = tuple(float(item) for item in self.robot.get_joint_positions())
        velocities_raw = self.robot.get_joint_velocities()
        efforts_raw = self.robot.get_measured_joint_efforts()
        velocities = tuple(float(item) for item in velocities_raw) if velocities_raw is not None else (0.0,) * len(positions)
        efforts = tuple(float(item) for item in efforts_raw) if efforts_raw is not None else (0.0,) * len(positions)
        controller_ok = all(np.isfinite(item) for item in (*positions, *velocities, *efforts))
        return RobotState(
            self.simulation_time,
            self.joint_names,
            positions,
            velocities,
            efforts,
            self._tcp_from_positions(positions),
            controller_ok,
            self._joint_limit_violations,
        )

    def get_finger_world_poses(self) -> tuple[Transform, Transform]:
        positions, orientations = self.finger_contact_view.get_world_poses()
        result = []
        for position, orientation in zip(positions, orientations, strict=True):
            result.append(
                Transform(
                    Vector3(float(position[0]), float(position[1]), float(position[2])),
                    Quaternion(
                        float(orientation[0]),
                        float(orientation[1]),
                        float(orientation[2]),
                        float(orientation[3]),
                    ),
                )
            )
        return tuple(result)  # type: ignore[return-value]

    def set_gripper_closed(self, closed: bool) -> None:
        state = self.read_robot_state()
        positions = list(state.positions)
        names = state.joint_names
        product_half_width_m = self.product_profile.geometry.width_m.nominal / 2.0
        closed_travel_m = max(0.0, 0.0875 - product_half_width_m + 0.008)
        for joint_name, target in (
            ("finger_left", -closed_travel_m if closed else 0.0),
            ("finger_right", closed_travel_m if closed else 0.0),
        ):
            if joint_name in names:
                positions[names.index(joint_name)] = target
        command = RobotCommand(
            self.simulation_time,
            names,
            tuple(positions),
            tuple(3.0 for _ in names),
            tuple(20.0 for _ in names),
        )
        self._last_command_positions = None
        self._last_command_velocities = None
        self.command_robot(command)

    def read_contacts(self) -> tuple[ContactSample, ...]:
        import numpy as np
        from pxr import PhysicsSchemaTools

        results = []
        for finger_name, sensor in self.contact_sensors.items():
            finger_path = self.paths.finger_left if finger_name == "left" else self.paths.finger_right
            raw = sensor.get_raw_data()
            for contact in raw:
                body0 = str(PhysicsSchemaTools.intToSdfPath(int(contact["body0"])))
                body1 = str(PhysicsSchemaTools.intToSdfPath(int(contact["body1"])))
                impulse = contact["impulse"]
                dt = max(float(contact.get("dt", 1.0 / self.physics_hz)), 1e-9)
                force_n = math.sqrt(float(impulse["x"]) ** 2 + float(impulse["y"]) ** 2 + float(impulse["z"]) ** 2) / dt
                intentional = self.paths.products in body0 or self.paths.products in body1
                results.append(ContactSample(self.simulation_time, body0, body1, force_n, 1, intentional))
                if intentional:
                    product_path = body0 if self.paths.products in body0 else body1
                    self._recent_product_contacts[(finger_path, product_path)] = self.simulation_time
        if self.finger_contact_view is not None and self.finger_contact_view.is_physics_handle_valid():
            matrix = np.asarray(self.finger_contact_view.get_contact_force_matrix(dt=1.0 / self.physics_hz))
            if matrix.ndim == 2:
                matrix = matrix[:, np.newaxis, :]
            target_product = min(
                self.products,
                key=lambda product_id: abs(
                    self.get_product_pose(product_id).translation.x_m
                    - self.read_robot_state().tcp_pose_world.translation.x_m
                ),
            )
            product_path = self.product_paths[target_product]
            for finger_index, finger_path in enumerate((self.paths.finger_left, self.paths.finger_right)):
                if finger_index >= matrix.shape[0]:
                    continue
                force_n = float(np.linalg.norm(matrix[finger_index]))
                if force_n > 0.05:
                    sample = ContactSample(
                        self.simulation_time,
                        finger_path,
                        product_path,
                        force_n,
                        1,
                        True,
                    )
                    results.append(sample)
                    self._recent_product_contacts[(finger_path, product_path)] = self.simulation_time
        return tuple(results)

    def attach_grasp(self, product_id: str) -> bool:
        from pxr import Gf, Sdf, UsdPhysics

        from meatcell.frames import compose, inverse

        product_path = self.product_paths[product_id]
        self.read_contacts()
        freshness_ns = SimTime.from_seconds(0.15).nanoseconds
        contacting_fingers = {
            finger
            for finger in (self.paths.finger_left, self.paths.finger_right)
            if (finger, product_path) in self._recent_product_contacts
            and self.simulation_time.nanoseconds - self._recent_product_contacts[(finger, product_path)].nanoseconds <= freshness_ns
        }
        if len(contacting_fingers) < 2:
            return False
        tcp = self.read_robot_state().tcp_pose_world
        product = self.get_product_pose(product_id)
        world_from_wrist = Transform(
            Vector3(
                tcp.translation.x_m,
                tcp.translation.y_m,
                tcp.translation.z_m + 0.75,
            ),
            tcp.rotation,
        )
        wrist_from_product = compose(inverse(world_from_wrist), product)
        joint = UsdPhysics.FixedJoint.Define(self.stage, self._grasp_joint_path)
        joint.CreateBody0Rel().SetTargets([Sdf.Path(f"{self.paths.robot}/wrist")])
        joint.CreateBody1Rel().SetTargets([Sdf.Path(product_path)])
        joint.CreateLocalPos0Attr(
            Gf.Vec3f(
                wrist_from_product.translation.x_m,
                wrist_from_product.translation.y_m,
                wrist_from_product.translation.z_m,
            )
        )
        joint.CreateLocalRot0Attr(
            Gf.Quatf(
                wrist_from_product.rotation.w,
                Gf.Vec3f(
                    wrist_from_product.rotation.x,
                    wrist_from_product.rotation.y,
                    wrist_from_product.rotation.z,
                ),
            )
        )
        joint.CreateLocalPos1Attr(Gf.Vec3f(0.0, 0.0, 0.0))
        joint.CreateLocalRot1Attr(Gf.Quatf(1.0, Gf.Vec3f(0.0, 0.0, 0.0)))
        self._attached_product = product_id
        return True

    def release_grasp(self) -> None:
        if self.stage.GetPrimAtPath(self._grasp_joint_path).IsValid():
            self.stage.RemovePrim(self._grasp_joint_path)
        self._attached_product = None

    def set_plc_inputs(
        self,
        *,
        conveyor_speed_mps: float | None = None,
        cutter_mode: CutterMode | None = None,
        recipe_id: str | None = None,
        permissive_sequence: int | None = None,
        fault_active: bool | None = None,
        emergency_stop: bool | None = None,
        result_acknowledged: bool | None = None,
    ) -> None:
        prim = self.stage.GetPrimAtPath(self.paths.plc)
        if conveyor_speed_mps is not None:
            self._belt_speed_mps = conveyor_speed_mps
            prim.GetAttribute("meatcell:conveyorSpeedMps").Set(conveyor_speed_mps)
        if cutter_mode is not None:
            self._cutter_mode = cutter_mode
            prim.GetAttribute("meatcell:cutterReady").Set(cutter_mode is CutterMode.READY)
        if recipe_id is not None:
            self._recipe_id = recipe_id
            prim.GetAttribute("meatcell:recipeId").Set(recipe_id)
        if permissive_sequence is not None:
            self._permissive_sequence = permissive_sequence
            prim.GetAttribute("meatcell:permissiveSequence").Set(permissive_sequence)
        if fault_active is not None:
            self._fault_active = fault_active
            prim.GetAttribute("meatcell:faultActive").Set(fault_active)
        if emergency_stop is not None:
            self._emergency_stop = emergency_stop
            prim.GetAttribute("meatcell:emergencyStop").Set(emergency_stop)
        if result_acknowledged is not None:
            self._result_ack = result_acknowledged
            prim.GetAttribute("meatcell:resultAcknowledged").Set(result_acknowledged)

    def read_cutter_state(self) -> CutterState:
        return CutterState(
            self.simulation_time,
            CutterMode.EMERGENCY_STOP if self._emergency_stop else CutterMode.FAULT if self._fault_active else self._cutter_mode,
            "cut_target_frame",
            0.4,
            (self.simulation_time.seconds * 2.0 * math.pi) % (2.0 * math.pi),
            self._recipe_id,
            self._permissive_sequence,
            "emergency_stop" if self._emergency_stop else "machine_fault" if self._fault_active else None,
        )

    def close(self) -> None:
        if self._closed:
            return
        if self._video_recorder is not None:
            try:
                self.stop_video_recording()
            except Exception:
                pass
        if self.world is not None:
            try:
                self.world.stop()
            except Exception:
                pass
        try:
            from isaacsim.core.api import World

            World.clear_instance()
        except Exception:
            pass
        self._closed = True
