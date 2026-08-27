"""Run the complete rendered-camera to FANUC delivery cycle in Scene 2.

The workpiece is coupled to the moving conveyor by a fixed-step kinematic
fixture until bilateral jaw contact. It is then a dynamic PhysX rigid body for
lift, transport, buffer handling, and cutter-tray release. No workpiece pose is
set after the grasp is confirmed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import traceback


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for candidate in (PROJECT_ROOT, PROJECT_ROOT / "third_party" / "python"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

PHYSICS_HZ = 240
BELT_SPEED_MPS = 0.10
BELT_SURFACE_Z_M = 0.8075
PRODUCT_CENTER_Z_M = 0.875
MIN_PAD_CLEARANCE_M = 0.005
FINAL_GRASP_CLEARANCE_PER_JAW_M = 0.012
FINAL_CLOSE_DURATION_S = 0.35
PRODUCT_SURFACE_TO_CENTER_M = 0.04
BUFFER_MAX_HOLD_S = 14.0
GRIPPER_OPEN_TARGET_M = (-0.002, 0.002)
CAMERA = {
    "eye": (2.35, 2.15, 2.05),
    "target": (0.40, -0.20, 0.96),
    "focal_length_mm": 30.0,
    "role": "fixed virtual evidence camera inside the simulated guard envelope",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solution", choices=("a", "b"), required=True)
    parser.add_argument("--seed", type=int, default=2601)
    parser.add_argument(
        "--scenario",
        choices=(
            "nominal",
            "failed_grasp",
            "cutter_unavailable",
            "buffer_timeout",
            "slip_correction",
            "emergency_stop",
            "stale_observation",
        ),
        default="nominal",
    )
    parser.add_argument("--output-root", default="results/scene2_integrated")
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument(
        "--yolo-weights",
        default="models/yolo26_meat_reference_buffer_v2/weights/best.pt",
    )
    return parser.parse_args()


def _inside_project(path: Path) -> bool:
    return path == PROJECT_ROOT or PROJECT_ROOT in path.parents


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_manifest(output_root: Path, event_path: Path, solution: str) -> dict[str, str]:
    artifacts = {
        "rgb": output_root / "overhead_rgb.png",
        "depth_png": output_root / "overhead_depth.png",
        "depth_npy": output_root / "overhead_depth_m.npy",
        "segmentation": output_root / "yolo26_segmentation.png",
        "trace": event_path,
    }
    missing = [str(path) for path in artifacts.values() if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise RuntimeError(f"Required integrated artifacts are missing or empty: {missing}")

    if solution == "b":
        buffer_artifacts = {
            "buffer_rgb": output_root / "buffer_rgb.png",
            "buffer_depth_npy": output_root / "buffer_depth_m.npy",
        }
        present = {name: path.is_file() and path.stat().st_size > 0 for name, path in buffer_artifacts.items()}
        if any(present.values()) and not all(present.values()):
            raise RuntimeError(f"Solution B buffer artifact set is incomplete: {present}")
        if all(present.values()):
            artifacts.update(buffer_artifacts)

    return {name: str(path) for name, path in artifacts.items()}


def _as_uint8(image: object) -> object:
    import numpy as np

    array = np.asarray(image)
    if array.dtype == np.uint8:
        return array
    multiplier = 255.0 if float(array.max(initial=0.0)) <= 1.0 else 1.0
    return np.clip(array * multiplier, 0, 255).astype(np.uint8)


def _tool_orientation(yaw_rad: float) -> object:
    import numpy as np

    half_yaw = yaw_rad / 2.0
    half_pitch = math.pi / 4.0
    return np.asarray(
        (
            math.cos(half_yaw) * math.cos(half_pitch),
            -math.sin(half_yaw) * math.sin(half_pitch),
            math.cos(half_yaw) * math.sin(half_pitch),
            math.sin(half_yaw) * math.cos(half_pitch),
        ),
        dtype=float,
    )


def _yaw_from_wxyz(quaternion: object) -> float:
    import numpy as np

    w, x, y, z = np.asarray(quaternion, dtype=float)
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _angle_error(value: float, target: float) -> float:
    return abs(math.atan2(math.sin(value - target), math.cos(value - target)))


def _mask_from_rle(value: str, shape: tuple[int, int]) -> object:
    import numpy as np

    values: list[int] = []
    for run in value.split(";"):
        bit, count = run.split(":", 1)
        values.extend([int(bit)] * int(count))
    return np.asarray(values, dtype=np.uint8).reshape(shape).astype(bool)


def run_integrated(simulation_app: object, args: argparse.Namespace, output_root: Path) -> dict[str, object]:
    import numpy as np
    import omni.usd
    from PIL import Image, ImageDraw
    from pxr import Gf, PhysicsSchemaTools, Sdf, Usd, UsdGeom, UsdPhysics
    from isaacsim.core.api import World
    from isaacsim.core.prims import SingleArticulation, SingleRigidPrim
    from isaacsim.core.utils.extensions import enable_extension
    from isaacsim.core.utils.types import ArticulationAction
    from isaacsim.core.utils.viewports import set_camera_view
    from isaacsim.robot_motion.motion_generation import LulaKinematicsSolver
    from isaacsim.sensors.camera import Camera

    from isaac_sim.scene2_builder import (
        ARTICULATION_ROOT,
        BUFFER_TARGET_CENTER_M,
        CUT_TARGET_CENTER_M,
        GRIPPER_ROOT,
        GRIPPER_GRASP_CENTER_FLANGE_M,
        Scene2Builder,
        gripper_target_travel_m,
    )
    from isaac_sim.stage_builder import product_width_scale_at_grasp
    from isaac_sim.video_recorder import RawVideoRecorder
    from isaac_sim.yolo_perception import YOLO26SegmentationModel
    from meatcell.contracts import (
        CellResult,
        CutterMode,
        CutterState,
        GraspCandidate,
        SimTime,
        TerminalPath,
        Transform,
    )
    from meatcell.eventlog import JsonlEventReader, JsonlEventWriter, RunMetadata, dependency_versions
    from meatcell.interception import InterceptionConfig, InterceptionPlanner
    from meatcell.perception import PinholeCalibration
    from meatcell.solutions import (
        BufferRuntime,
        DeliveryMeasurement,
        DeliveryTolerance,
        PLCState,
        SolutionAController,
        SolutionBController,
    )
    from meatcell.grasp import GraspModel, GraspModelConfig
    from meatcell.supervisor import CellState, CellSupervisor
    from meatcell.tracking import ObjectTracker, TrackerConfig

    if args.fps <= 0 or PHYSICS_HZ % args.fps != 0:
        raise ValueError("Frame rate must be a positive divisor of 240")
    if args.solution == "a" and args.scenario == "buffer_timeout":
        raise ValueError("buffer_timeout applies only to Solution B")
    output_root.mkdir(parents=True, exist_ok=True)
    weights_path = (PROJECT_ROOT / args.yolo_weights).resolve()
    if not _inside_project(weights_path) or not weights_path.is_file():
        raise FileNotFoundError(f"YOLO checkpoint not found inside the project: {weights_path}")

    rng = random.Random(args.seed)
    World.clear_instance()
    omni.usd.get_context().new_stage()
    world = World(
        physics_dt=1.0 / PHYSICS_HZ,
        rendering_dt=1.0 / 60.0,
        stage_units_in_meters=1.0,
        physics_prim_path="/World/PhysicsScene",
        backend="numpy",
        device="cpu",
    )
    stage = omni.usd.get_context().get_stage()
    build = Scene2Builder().build(stage)
    articulation = world.scene.add(SingleArticulation(ARTICULATION_ROOT, name="fanuc_integrated"))
    product_path = build["product_paths"][1]
    product_prim = stage.GetPrimAtPath(product_path)
    product = world.scene.add(SingleRigidPrim(product_path, name="integrated_product"))
    product_xform_ops = UsdGeom.Xformable(product_prim).GetOrderedXformOps()
    product_translate_op = next(op for op in product_xform_ops if op.GetOpType() == UsdGeom.XformOp.TypeTranslate)
    product_orientation_op = next(op for op in product_xform_ops if op.GetOpType() == UsdGeom.XformOp.TypeOrient)
    for path in build["product_paths"]:
        prim = stage.GetPrimAtPath(path)
        if path != product_path:
            UsdGeom.Imageable(prim).MakeInvisible()
            hidden_geometry = stage.GetPrimAtPath(f"{path}/Geometry")
            UsdPhysics.CollisionAPI(hidden_geometry).CreateCollisionEnabledAttr(False).Set(False)

    plc_prim = stage.GetPrimAtPath("/World/Cell/PLC")
    plc_prim.GetAttribute("meatcell:conveyorSpeedMps").Set(BELT_SPEED_MPS)
    stage.GetPrimAtPath("/World").GetAttribute("meatcell:conveyorSpeedMps").Set(BELT_SPEED_MPS)
    start_x = -0.18 + rng.uniform(-0.015, 0.015)
    start_y = rng.uniform(-0.075, 0.075)
    start_yaw = math.radians(rng.uniform(-8.0, 8.0))
    start_orientation = np.asarray(
        (math.cos(start_yaw / 2.0), 0.0, 0.0, math.sin(start_yaw / 2.0)),
        dtype=np.float32,
    )
    product_translate_op.Set(Gf.Vec3d(start_x, start_y, PRODUCT_CENTER_Z_M))
    product_orientation_op.Set(
        Gf.Quatd(math.cos(start_yaw / 2.0), Gf.Vec3d(0.0, 0.0, math.sin(start_yaw / 2.0)))
    )
    product.set_default_state(
        position=np.asarray((start_x, start_y, PRODUCT_CENTER_Z_M), dtype=np.float32),
        orientation=start_orientation,
    )
    stage_path = output_root / f"carve_scene2_{args.solution}.usda"

    enable_extension("isaacsim.sensors.experimental.physics")
    simulation_app.update()
    from isaacsim.sensors.experimental.physics import Contact, ContactSensor

    contact_sensors = []
    for index, finger_path in enumerate(build["gripper_finger_paths"]):
        sensor_path = f"{finger_path}/integrated_contact_sensor_{index}"
        Contact.create(sensor_path, min_threshold=0.0, max_threshold=100000.0, radius=-1.0)
        contact_sensors.append(ContactSensor(sensor_path))

    world.reset()
    for path in build["product_paths"]:
        UsdPhysics.RigidBodyAPI(stage.GetPrimAtPath(path)).CreateKinematicEnabledAttr(True).Set(True)
    kinematic_attr = UsdPhysics.RigidBodyAPI(product_prim).GetKinematicEnabledAttr()
    set_camera_view(
        eye=[-0.35, 0.0, 2.31],
        target=[-0.35, 0.0, BELT_SURFACE_Z_M],
        camera_prim_path=build["camera_path"],
    )
    buffer_view_proxy_path = "/OmniverseKit_Persp"
    set_camera_view(
        eye=[BUFFER_TARGET_CENTER_M[0], BUFFER_TARGET_CENTER_M[1], 1.76],
        target=[BUFFER_TARGET_CENTER_M[0], BUFFER_TARGET_CENTER_M[1], BUFFER_TARGET_CENTER_M[2]],
        camera_prim_path=buffer_view_proxy_path,
    )
    proxy_prim = stage.GetPrimAtPath(buffer_view_proxy_path)
    if not proxy_prim:
        raise RuntimeError("Isaac Sim did not create its calibrated viewport camera")
    proxy_transform = UsdGeom.Xformable(proxy_prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    buffer_xform = UsdGeom.Xformable(stage.GetPrimAtPath(build["buffer_camera_path"]))
    buffer_xform.ClearXformOpOrder()
    buffer_xform.AddTransformOp().Set(proxy_transform)
    set_camera_view(
        eye=list(CAMERA["eye"]),
        target=list(CAMERA["target"]),
        camera_prim_path=build["presentation_camera_path"],
    )
    stage.GetPrimAtPath(build["presentation_camera_path"]).GetAttribute("focalLength").Set(
        CAMERA["focal_length_mm"]
    )
    if not stage.GetRootLayer().Export(str(stage_path)):
        raise RuntimeError(f"USD stage export failed: {stage_path}")
    reloaded_stage = Usd.Stage.Open(str(stage_path))
    required_reload_paths = (
        "/World/Cell/Conveyor",
        ARTICULATION_ROOT,
        GRIPPER_ROOT,
        build["camera_path"],
        build["buffer_camera_path"],
        "/World/Cell/CutterStation",
        "/World/Cell/PLC",
        product_path,
    )
    stage_reload_passed = bool(
        reloaded_stage
        and all(reloaded_stage.GetPrimAtPath(path).IsValid() for path in required_reload_paths)
    )
    if not stage_reload_passed:
        raise RuntimeError("Saved USD did not reload with every required integrated-cell prim")
    controller = articulation.get_articulation_controller()
    dof_names = tuple(str(name) for name in articulation.dof_names)
    expected_dofs = ("J1", "J2", "J3", "J4", "J5", "J6", "finger_left", "finger_right")
    if dof_names != expected_dofs:
        raise RuntimeError(f"Unexpected FANUC DOF order: {dof_names}")
    lower = np.asarray(articulation.dof_properties["lower"], dtype=float)
    upper = np.asarray(articulation.dof_properties["upper"], dtype=float)
    robot_indices = np.arange(6, dtype=np.int32)
    finger_indices = np.asarray((6, 7), dtype=np.int32)
    joint_velocity_limits = np.asarray((2.0, 2.0, 2.0, 3.0, 3.0, 3.0, 0.25, 0.25), dtype=float)
    joint_acceleration_limits = np.asarray((8.0, 8.0, 8.0, 12.0, 12.0, 12.0, 1.5, 1.5), dtype=float)

    solver = LulaKinematicsSolver(
        str(PROJECT_ROOT / "configs" / "fanuc_m10id12_lula.yaml"),
        str(PROJECT_ROOT / "assets" / "robots" / "fanuc_m10id12" / "fanuc_m10id12.urdf"),
    )
    solver.set_robot_base_pose(
        np.asarray((0.35, -1.25, 0.59), dtype=float),
        np.asarray((2.0**-0.5, 0.0, 0.0, 2.0**-0.5), dtype=float),
    )
    tool_orientation = _tool_orientation(start_yaw)
    tool_down_axis = np.asarray((0.0, 0.0, -1.0), dtype=float)
    flange_offset = tool_down_axis * GRIPPER_GRASP_CENTER_FLANGE_M[0]
    overview = np.asarray((0.05, 1.00, 0.70, 0.0, -1.30, -1.45), dtype=float)

    def solve_tcp(label: str, tcp_position: object, warm_start: object, orientation: object | None = None) -> np.ndarray:
        flange_target = np.asarray(tcp_position, dtype=float) - flange_offset
        joints, success = solver.compute_inverse_kinematics(
            "ee_link",
            flange_target,
            tool_orientation if orientation is None else orientation,
            warm_start=np.asarray(warm_start, dtype=float),
            position_tolerance=0.002,
            orientation_tolerance=0.025,
        )
        joints = np.asarray(joints, dtype=float)
        if not success:
            raise RuntimeError(f"Lula IK failed for {label}: {flange_target.tolist()}")
        if np.any(joints <= lower[:6]) or np.any(joints >= upper[:6]):
            raise RuntimeError(f"IK pose {label} exceeds an imported joint limit")
        return joints

    ready_tcp = np.asarray((0.30, start_y, PRODUCT_CENTER_Z_M + 0.23), dtype=float)
    ready_joints = solve_tcp("ready", ready_tcp, overview)
    initial_command = np.concatenate((ready_joints, np.zeros(2, dtype=float)))
    articulation.set_joint_positions(initial_command.astype(np.float32))
    articulation.set_joint_velocities(np.zeros(8, dtype=np.float32))
    controller.apply_action(ArticulationAction(joint_positions=initial_command.astype(np.float32)))
    for step in range(120):
        world.step(render=(step % 4 == 0))

    presentation_camera = Camera(
        build["presentation_camera_path"],
        name="scene2_integrated_presentation",
        resolution=(1280, 720),
        frequency=60,
    )
    overhead_camera = Camera(
        build["camera_path"],
        name="scene2_integrated_overhead",
        resolution=(640, 480),
        frequency=60,
    )
    buffer_camera = Camera(
        build["buffer_camera_path"],
        name="scene2_integrated_buffer",
        resolution=(640, 480),
        frequency=60,
    )
    presentation_camera.initialize()
    overhead_camera.initialize()
    buffer_camera.initialize()
    presentation_camera.add_distance_to_image_plane_to_frame()
    overhead_camera.add_distance_to_image_plane_to_frame()
    buffer_camera.add_distance_to_image_plane_to_frame()
    for _ in range(32):
        world.render()

    video_path = output_root / f"scene2_solution_{args.solution}_{args.scenario}.mp4"
    recorder = RawVideoRecorder(video_path, fps=args.fps, width=1280, height=720, source="rendered_scene2_rgb_with_telemetry_overlay")
    previous_command = initial_command.copy()
    previous_velocity = np.zeros(8, dtype=float)
    previous_command_time_s = float(world.current_time)
    max_velocity = np.zeros(8, dtype=float)
    max_acceleration = np.zeros(8, dtype=float)
    command_count = 0
    physics_steps = 0
    next_capture_time_s = float(world.current_time)
    joint_limit_violations = 0
    velocity_limit_violations = 0
    acceleration_limit_violations = 0
    command_safety_limit_activations = 0
    state_label = "ACQUIRE"
    plc_label = "READY"
    overhead_inset = None
    track_label = "waiting for YOLO26"
    product_positions: list[list[float]] = []
    kinematic_product_positions: list[list[float]] = []
    contact_pairs: list[set[tuple[str, str]]] = [set(), set()]
    peak_contact_forces = np.zeros(2, dtype=float)
    last_product_contact_time_s = np.full(2, -math.inf, dtype=float)
    maximum_grasp_distance_m = 0.0
    minimum_precontact_pad_clearance_m = float("inf")
    grasp_confirmed = False
    conveyor_active = True
    trace: list[dict[str, object]] = []
    sequence: list[dict[str, object]] = []

    pad_paths = [
        str(child.GetPath())
        for finger_path in build["gripper_finger_paths"]
        for child in stage.TraverseAll()
        if str(child.GetPath()).startswith(finger_path + "/SoftPad") and child.IsA(UsdGeom.Boundable)
    ]
    if not pad_paths:
        raise RuntimeError("No gripper pad geometry was found")

    def sim_time() -> SimTime:
        return SimTime.from_seconds(float(world.current_time))

    def product_pose() -> tuple[np.ndarray, np.ndarray]:
        position, orientation = product.get_world_pose()
        return np.asarray(position, dtype=float), np.asarray(orientation, dtype=float)

    def pad_min_z() -> float:
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
        return min(
            float(cache.ComputeWorldBound(stage.GetPrimAtPath(path)).ComputeAlignedRange().GetMin()[2])
            for path in pad_paths
        )

    def world_bounds(path: str) -> dict[str, list[float]]:
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
        aligned_range = cache.ComputeWorldBound(stage.GetPrimAtPath(path)).ComputeAlignedRange()
        return {
            "minimum_m": [float(value) for value in aligned_range.GetMin()],
            "maximum_m": [float(value) for value in aligned_range.GetMax()],
        }

    def tcp_world_position() -> np.ndarray:
        measured_joints = np.asarray(articulation.get_joint_positions(), dtype=float)[:6]
        flange_position, _ = solver.compute_forward_kinematics(
            "ee_link",
            measured_joints,
        )
        return np.asarray(flange_position, dtype=float) + flange_offset

    def add_trace(kind: str, **data: object) -> None:
        trace.append({"time_s": float(world.current_time), "kind": kind, **data})

    def capture_frame() -> None:
        image = presentation_camera.get_rgb()
        if image is None:
            raise RuntimeError("Presentation camera stopped publishing")
        frame = Image.fromarray(_as_uint8(image)[..., :3])
        draw = ImageDraw.Draw(frame)
        draw.rectangle((0, 0, 1280, 58), fill=(8, 14, 19))
        draw.text((18, 10), f"CARVE | Solution {args.solution.upper()} | {args.scenario}", fill=(235, 246, 250))
        draw.text((18, 33), f"STATE {state_label}   PLC {plc_label}   {track_label}", fill=(107, 224, 204))
        if overhead_inset is not None:
            inset = Image.fromarray(overhead_inset).resize((256, 192))
            frame.paste(inset, (1008, 74))
            draw.rectangle((1006, 72, 1266, 268), outline=(107, 224, 204), width=2)
            draw.text((1016, 78), "YOLO26 RGBD", fill=(255, 255, 255))
        recorder.write_frame(np.asarray(frame, dtype=np.uint8).tobytes(), int(round(float(world.current_time) * 1_000_000_000)))

    def apply_and_step(command: object, *, capture: bool = True) -> None:
        nonlocal previous_command, previous_velocity, previous_command_time_s, command_count, physics_steps
        nonlocal joint_limit_violations, velocity_limit_violations, acceleration_limit_violations
        nonlocal command_safety_limit_activations
        nonlocal minimum_precontact_pad_clearance_m, next_capture_time_s
        nonlocal maximum_grasp_distance_m
        desired_command = np.asarray(command, dtype=float)
        command_time_s = float(world.current_time)
        command_dt_s = max(command_time_s - previous_command_time_s, 1.0 / PHYSICS_HZ)
        desired_velocity = (desired_command - previous_command) / command_dt_s
        lower_velocity = np.maximum(-joint_velocity_limits, previous_velocity - joint_acceleration_limits * command_dt_s)
        upper_velocity = np.minimum(joint_velocity_limits, previous_velocity + joint_acceleration_limits * command_dt_s)
        limited_velocity = np.clip(desired_velocity, lower_velocity, upper_velocity)
        command_array = previous_command + limited_velocity * command_dt_s
        command_array = np.clip(command_array, lower, upper)
        command_safety_limit_activations += int(not np.allclose(command_array, desired_command, atol=1e-9, rtol=0.0))
        joint_limit_violations += int(np.any(command_array < lower - 1e-6) or np.any(command_array > upper + 1e-6))
        controller.apply_action(ArticulationAction(joint_positions=command_array.astype(np.float32)))
        before_time_s = float(world.current_time)
        should_capture = capture and before_time_s + 1.0 / 60.0 >= next_capture_time_s
        world.step(render=(physics_steps % 4 == 0 or should_capture))
        dt_s = max(float(world.current_time) - before_time_s, 1.0 / PHYSICS_HZ)
        velocity = (command_array - previous_command) / command_dt_s
        acceleration = (velocity - previous_velocity) / command_dt_s
        max_velocity[:] = np.maximum(max_velocity, np.abs(velocity))
        max_acceleration[:] = np.maximum(max_acceleration, np.abs(acceleration))
        velocity_limit_violations += int(np.any(np.abs(velocity) > joint_velocity_limits * 1.001))
        acceleration_limit_violations += int(np.any(np.abs(acceleration) > joint_acceleration_limits * 1.001))
        if conveyor_active:
            position, orientation = product_pose()
            position[0] += BELT_SPEED_MPS * dt_s
            product.set_world_pose(position.astype(np.float32), orientation.astype(np.float32))
            product_translate_op.Set(Gf.Vec3d(*position.tolist()))
            kinematic_product_positions.append(position.tolist())
        command_count += 1
        physics_steps += 1
        previous_command = command_array
        previous_velocity = velocity
        previous_command_time_s = command_time_s
        position, _ = product_pose()
        product_positions.append(position.tolist())
        if not grasp_confirmed:
            minimum_precontact_pad_clearance_m = min(
                minimum_precontact_pad_clearance_m,
                pad_min_z() - BELT_SURFACE_Z_M,
            )
        for sensor_index, sensor in enumerate(contact_sensors):
            for contact in sensor.get_raw_data():
                body0 = str(PhysicsSchemaTools.intToSdfPath(int(contact["body0"])))
                body1 = str(PhysicsSchemaTools.intToSdfPath(int(contact["body1"])))
                contact_pairs[sensor_index].add((body0, body1))
                if product_path not in (body0, body1):
                    continue
                last_product_contact_time_s[sensor_index] = float(world.current_time)
                impulse = contact["impulse"]
                dt = max(float(contact.get("dt", 1.0 / PHYSICS_HZ)), 1e-9)
                force = math.sqrt(float(impulse["x"]) ** 2 + float(impulse["y"]) ** 2 + float(impulse["z"]) ** 2) / dt
                peak_contact_forces[sensor_index] = max(peak_contact_forces[sensor_index], force)
        if grasp_confirmed:
            maximum_grasp_distance_m = max(
                maximum_grasp_distance_m,
                float(np.linalg.norm(product_pose()[0] - tcp_world_position())),
            )
        if should_capture:
            capture_frame()
            while next_capture_time_s <= float(world.current_time):
                next_capture_time_s += 1.0 / args.fps

    def hold(label: str, duration_s: float) -> None:
        sequence.append({"label": label, "duration_s": duration_s})
        add_trace("motion", label=label, duration_s=duration_s)
        started_s = float(world.current_time)
        while float(world.current_time) - started_s < duration_s:
            apply_and_step(previous_command.copy())

    def move(label: str, indices: object, target: object, duration_s: float) -> None:
        sequence.append({"label": label, "duration_s": duration_s})
        add_trace("motion", label=label, duration_s=duration_s)
        selected = np.asarray(indices, dtype=int)
        start = previous_command[selected].copy()
        target_array = np.asarray(target, dtype=float)
        started_s = float(world.current_time)
        while True:
            phase = min(1.0, (float(world.current_time) - started_s) / duration_s)
            blend = 0.5 - 0.5 * math.cos(math.pi * phase)
            command = previous_command.copy()
            command[selected] = start + (target_array - start) * blend
            apply_and_step(command)
            if phase >= 1.0:
                break

    def move_cartesian(
        label: str,
        target_tcp: object,
        target_orientation: object,
        duration_s: float,
    ) -> object:
        """Follow a straight TCP path instead of a joint-space endpoint arc."""
        sequence.append({"label": label, "duration_s": duration_s})
        add_trace("motion", label=label, duration_s=duration_s, interpolation="cartesian_tcp")
        start_tcp = tcp_world_position()
        target = np.asarray(target_tcp, dtype=float)
        seed_joints = previous_command[:6].copy()
        started_s = float(world.current_time)
        while True:
            phase = min(1.0, (float(world.current_time) - started_s) / duration_s)
            blend = 0.5 - 0.5 * math.cos(math.pi * phase)
            requested_tcp = start_tcp + (target - start_tcp) * blend
            seed_joints = solve_tcp(label, requested_tcp, seed_joints, target_orientation)
            apply_and_step(np.concatenate((seed_joints, previous_command[6:])))
            if phase >= 1.0:
                break
        return seed_joints

    def grasp_retained(label: str, maximum_distance_m: float = 0.13, contact_age_s: float = 0.20) -> bool:
        distance_m = float(np.linalg.norm(product_pose()[0] - tcp_world_position()))
        contact_ages_s = (float(world.current_time) - last_product_contact_time_s).tolist()
        retained = distance_m <= maximum_distance_m and all(age <= contact_age_s for age in contact_ages_s)
        add_trace(
            "grasp_retention",
            label=label,
            retained=retained,
            product_to_tcp_distance_m=distance_m,
            maximum_allowed_distance_m=maximum_distance_m,
            bilateral_contact_age_s=contact_ages_s,
            maximum_allowed_contact_age_s=contact_age_s,
        )
        return retained

    def settle_robot_at_tcp(
        label: str,
        target_tcp: object,
        target_orientation: object,
        timeout_s: float = 2.0,
        tolerance_m: float = 0.012,
    ) -> None:
        target = np.asarray(target_tcp, dtype=float)
        started_s = sim_time().seconds
        error_m = float(np.linalg.norm(tcp_world_position() - target))
        while error_m > tolerance_m:
            if sim_time().seconds - started_s > timeout_s:
                measured = tcp_world_position()
                raise RuntimeError(
                    f"{label} did not converge within {timeout_s:.2f} s: "
                    f"error_m={error_m:.6f}, target={target.tolist()}, "
                    f"measured={measured.tolist()}, joints={np.asarray(articulation.get_joint_positions(), dtype=float)[:6].tolist()}, "
                    f"command={previous_command[:6].tolist()}"
                )
            measured = tcp_world_position()
            compensated_target = target + np.clip(target - measured, -0.06, 0.06)
            compensated_joints = solve_tcp(
                f"{label} feedback",
                compensated_target,
                previous_command[:6],
                target_orientation,
            )
            apply_and_step(np.concatenate((compensated_joints, previous_command[6:])))
            error_m = float(np.linalg.norm(tcp_world_position() - target))
        add_trace(
            "controller_convergence",
            label=label,
            target_tcp_position_m=target.tolist(),
            measured_tcp_position_m=tcp_world_position().tolist(),
            error_m=error_m,
            elapsed_s=sim_time().seconds - started_s,
        )

    def set_state(value: str) -> None:
        nonlocal state_label
        state_label = value.upper()
        add_trace("state", state=value)

    def plc_state(*, ready: bool, fault: bool = False, emergency: bool = False, acknowledged: bool = False) -> PLCState:
        nonlocal plc_label
        mode = CutterMode.EMERGENCY_STOP if emergency else CutterMode.FAULT if fault else CutterMode.READY if ready else CutterMode.BLOCKED
        plc_label = mode.value.upper()
        plc_prim.GetAttribute("meatcell:cutterReady").Set(ready)
        plc_prim.GetAttribute("meatcell:faultActive").Set(fault)
        plc_prim.GetAttribute("meatcell:emergencyStop").Set(emergency)
        for name, value_type, value in (
            ("resultAcknowledged", Sdf.ValueTypeNames.Bool, acknowledged),
            ("permissiveSequence", Sdf.ValueTypeNames.Int, 1),
            ("cutterPhaseRad", Sdf.ValueTypeNames.Double, 0.0),
        ):
            attribute = plc_prim.GetAttribute(f"meatcell:{name}")
            if not attribute:
                attribute = plc_prim.CreateAttribute(f"meatcell:{name}", value_type)
            attribute.Set(value)
        result = PLCState(
            sim_time(),
            BELT_SPEED_MPS if conveyor_active else 0.0,
            "pork_boneless_loin",
            CutterState(sim_time(), mode, "cut_target_frame", 0.0, 0.0, "pork_boneless_loin", 1, "injected" if fault else None),
            fault,
            emergency,
            acknowledged,
        )
        add_trace("plc", mode=mode.value, ready=ready, fault=fault, emergency_stop=emergency, acknowledged=acknowledged)
        return result

    camera_intrinsics = np.asarray(overhead_camera.get_intrinsics_matrix(), dtype=float)
    calibration = PinholeCalibration(
        -0.35,
        0.0,
        2.31,
        float(camera_intrinsics[0, 0]),
        float(camera_intrinsics[1, 1]),
        float(camera_intrinsics[0, 2]),
        float(camera_intrinsics[1, 2]),
        BELT_SURFACE_Z_M,
        0.002,
        math.radians(0.2),
    )
    buffer_intrinsics = np.asarray(buffer_camera.get_intrinsics_matrix(), dtype=float)
    buffer_calibration = PinholeCalibration(
        BUFFER_TARGET_CENTER_M[0],
        BUFFER_TARGET_CENTER_M[1],
        1.76,
        float(buffer_intrinsics[0, 0]),
        float(buffer_intrinsics[1, 1]),
        float(buffer_intrinsics[0, 2]),
        float(buffer_intrinsics[1, 2]),
        BUFFER_TARGET_CENTER_M[2] - 0.04,
        0.002,
        math.radians(0.2),
    )
    model = YOLO26SegmentationModel(
        weights_path=weights_path,
        seed=args.seed,
        confidence_threshold=0.05,
        latency_mean_s=0.030,
        latency_sigma_s=0.002,
        timestamp_jitter_sigma_s=0.0002,
        position_noise_sigma_m=0.001,
        yaw_noise_sigma_rad=math.radians(0.35),
        minimum_component_pixels=30,
        device="cpu",
        refine_color_mask=True,
        refinement_species="pork",
        surface_to_center_offset_m=PRODUCT_SURFACE_TO_CENTER_M,
    )
    tracker = ObjectTracker(TrackerConfig(confirmation_hits=2, association_distance_m=0.12, velocity_measurement_weight=0.0))

    def calibrated_scene2_observation(observation: object) -> object:
        """Keep the standard pinhole world pose after USD and PhysX synchronization."""
        return observation
    supervisor = CellSupervisor()
    episode_id = f"scene2-{args.solution}-{args.scenario}-{args.seed}"
    supervisor.start_episode(episode_id, sim_time())
    plc = plc_state(ready=args.scenario != "cutter_unavailable")

    config_hash = hashlib.sha256(
        json.dumps({"solution": args.solution, "seed": args.seed, "scenario": args.scenario, "belt_speed_mps": BELT_SPEED_MPS}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    event_path = output_root / "cycle_trace.jsonl"
    writer = JsonlEventWriter(
        event_path,
        RunMetadata(
            episode_id,
            config_hash,
            "scene2_fanuc_integrated",
            1,
            args.seed,
            args.solution,
            dependency_versions(("numpy", "torch", "ultralytics", "isaacsim")),
            sim_time(),
            build["reference_notice"],
        ),
    )
    writer.start()
    for event in supervisor.events:
        writer.append_event(event)
    event_cursor = len(supervisor.events)

    def flush_events() -> None:
        nonlocal event_cursor
        for event in supervisor.events[event_cursor:]:
            writer.append_event(event)
        event_cursor = len(supervisor.events)

    recording = None
    perceived = False
    tracked = False
    grasped = False
    delivered = False
    slip_detected = False
    buffer_sensor_oracle_position_error_m = None
    measurement = None
    terminal_reason = "partial"
    observation_count = 0
    perception_latencies: list[float] = []
    track = None
    planned_intercept_x = None
    planned_intercept_time_s = None
    actual_intercept_time_s = None
    lift_distance_m = 0.0
    relative_drift_m = float("inf")
    relative_offsets: list[list[float]] = []
    release_product_step_start = 0
    initial_product_teleports = 1

    try:
        hold("show moving workpiece and ready robot", 0.5)
        pending = []
        first_rgb = None
        first_depth = None
        first_observation = None
        for frame_index in range(4):
            for _ in range(4):
                world.render()
            rgb_value = overhead_camera.get_rgb()
            depth_value = overhead_camera.get_depth()
            if rgb_value is None or depth_value is None:
                raise RuntimeError("Overhead RGBD camera did not publish")
            rgb = _as_uint8(rgb_value)[..., :3]
            depth = np.asarray(depth_value, dtype=np.float32)
            if rgb.shape != (480, 640, 3) or depth.shape != (480, 640):
                raise RuntimeError(f"Unexpected overhead RGBD shape: {rgb.shape}, {depth.shape}")
            if not np.any(rgb) or not np.any(np.isfinite(depth) & (depth > 0.0)):
                raise RuntimeError("Overhead RGBD publication was empty")
            exposure_time = sim_time()
            oracle_position, oracle_orientation = product_pose()
            add_trace(
                "sensor_oracle",
                frame_index=frame_index,
                exposure_time_s=exposure_time.seconds,
                product_position_m=oracle_position.tolist(),
                product_yaw_rad=_yaw_from_wxyz(oracle_orientation),
                note="test oracle only; not supplied to perception, tracking, planning, or control",
            )
            Image.fromarray(rgb).save(output_root / f"overhead_rgb_frame_{frame_index}.png")
            observations = tuple(
                calibrated_scene2_observation(item)
                for item in model.infer(rgb, depth, exposure_time, calibration)
            )
            candidates = [
                item for item in observations
                if -0.60 < item.pose_belt.translation.x_m < 0.25
                and abs(item.pose_belt.translation.y_m) < 0.25
            ]
            if not candidates:
                Image.fromarray(rgb).save(output_root / f"failed_rgb_{frame_index}.png")
                raise RuntimeError("YOLO26 produced no conveyor workpiece detection")
            expected_position, _ = product_pose()
            chosen = min(candidates, key=lambda item: abs(item.pose_belt.translation.x_m - expected_position[0]) + abs(item.pose_belt.translation.y_m - expected_position[1]))
            pending.append(chosen)
            if first_rgb is None:
                first_rgb = rgb.copy()
                first_depth = depth.copy()
                first_observation = chosen
            while sim_time() < chosen.delivery_time:
                apply_and_step(previous_command.copy())
            writer.append("observation", chosen.delivery_time, chosen)
            observation_count += 1
            perception_latencies.append(chosen.delivery_time.seconds - chosen.exposure_time.seconds)
            track = tracker.update(chosen, current_time=sim_time(), encoder_speed_mps=BELT_SPEED_MPS)
            if frame_index == 0:
                supervisor.transition(CellState.TRACK, sim_time(), "rendered_yolo26_observation_acquired")
                flush_events()
            if track.lifecycle.value == "confirmed":
                break
            for _ in range(24):
                apply_and_step(previous_command.copy())
        perceived = observation_count > 0
        tracked = track is not None and track.lifecycle.value == "confirmed"
        if not tracked or first_rgb is None or first_depth is None or first_observation is None:
            raise RuntimeError("YOLO26 track was not confirmed")

        mask = _mask_from_rle(first_observation.instance_mask_rle or "", first_rgb.shape[:2])
        overlay = first_rgb.copy()
        overlay[mask] = (0.45 * overlay[mask] + 0.55 * np.asarray((36, 235, 183))).astype(np.uint8)
        overlay_image = Image.fromarray(overlay)
        draw_overlay = ImageDraw.Draw(overlay_image)
        box = first_observation.bbox
        draw_overlay.rectangle((box.x_min_px, box.y_min_px, box.x_max_px, box.y_max_px), outline=(255, 235, 92), width=3)
        overlay_image.save(output_root / "yolo26_segmentation.png")
        Image.fromarray(first_rgb).save(output_root / "overhead_rgb.png")
        finite_depth = first_depth[np.isfinite(first_depth) & (first_depth > 0.0)]
        np.save(output_root / "overhead_depth_m.npy", first_depth)
        depth_min = float(np.percentile(finite_depth, 1))
        depth_max = float(np.percentile(finite_depth, 99))
        depth_vis = np.clip((first_depth - depth_min) / max(depth_max - depth_min, 1e-6), 0.0, 1.0)
        depth_vis[~np.isfinite(first_depth)] = 0.0
        Image.fromarray((255.0 * (1.0 - depth_vis)).astype(np.uint8)).save(output_root / "overhead_depth.png")
        overhead_inset = np.asarray(overlay_image, dtype=np.uint8)
        track_label = f"{track.track_id}  vx={track.twist_belt.linear_mps.x_m:.3f} m/s"
        set_state("plan")
        supervisor.transition(CellState.PLAN, sim_time(), "confirmed_track_predicted")
        flush_events()

        if args.scenario == "stale_observation":
            for _ in range(48):
                apply_and_step(previous_command.copy())
        grasp = GraspCandidate("scene2-top-grasp", track.track_id, Transform.planar(0.0, 0.0, 0.07, 0.0), 0.88, 0.025, 0.040)
        planner = InterceptionPlanner(
            InterceptionConfig(
                pick_x_min_m=0.275,
                pick_x_max_m=0.335,
                candidate_step_m=0.010,
                workspace_y_abs_m=0.30,
                workspace_z_min_m=0.80,
                workspace_z_max_m=1.05,
                home_pose_world=Transform.planar(*ready_tcp, start_yaw),
                max_tcp_speed_mps=0.70,
                max_tcp_accel_mps2=1.50,
                grasp_close_s=FINAL_CLOSE_DURATION_S,
                command_latency_s=0.010,
                timing_reserve_s=0.10,
                commit_lead_s=0.10,
                max_observation_age_s=0.15,
                max_position_sigma_m=0.030,
                velocity_match_reserve_mps=0.10,
                minimum_boundary_clearance_m=0.010,
            )
        )
        decision = planner.plan(track=track, grasp=grasp, now=sim_time(), world_from_belt=Transform.identity())
        writer.append("interception_decision", sim_time(), decision)
        if not decision.accepted or decision.plan is None:
            supervisor.reject(sim_time(), f"interception_{decision.reason.value}")
            flush_events()
            set_state("recover")
            hold("safe hold after rejected plan", 0.5)
            supervisor.return_to_idle(sim_time(), "known_safe_after_rejected_plan")
            flush_events()
            terminal_reason = f"interception_{decision.reason.value}"
        else:
            plan = decision.plan
            planned_intercept_x = plan.interception_pose_world.translation.x_m
            planned_intercept_time_s = plan.intercept_at.seconds
            supervisor.transition(CellState.WAIT_COMMIT, sim_time(), "timed_interception_reserved")
            supervisor.transition(CellState.INTERCEPT, sim_time(), "fanuc_trajectory_committed")
            flush_events()
            set_state("intercept")
            intercept_tcp = np.asarray((planned_intercept_x, track.pose_belt.translation.y_m, PRODUCT_CENTER_Z_M + 0.07), dtype=float)
            if args.scenario == "failed_grasp":
                intercept_tcp[1] += 0.12
            grasp_joints = solve_tcp("moving_intercept", intercept_tcp, ready_joints)
            product_width_m = 0.14 * product_width_scale_at_grasp("elongated_rounded_prism", 0.82)
            target_travel = gripper_target_travel_m(product_width_m)
            preshape_travel = max(0.0, target_travel - FINAL_GRASP_CLEARANCE_PER_JAW_M)
            preshape_target = np.asarray((-preshape_travel, preshape_travel), dtype=float)
            approach_all = np.concatenate((grasp_joints, preshape_target))
            add_trace(
                "ik",
                label="moving_intercept",
                ready_joints_rad=ready_joints.tolist(),
                target_joints_rad=grasp_joints.tolist(),
                preshape_target_m=preshape_target.tolist(),
            )
            duration = max(1.0, plan.intercept_at.seconds - sim_time().seconds)
            move("timed approach with near-width jaw preshape", np.arange(8), approach_all, duration)
            add_trace(
                "measured_joints",
                label="after_intercept_approach",
                positions_rad=np.asarray(articulation.get_joint_positions(), dtype=float).tolist(),
                pad_clearance_m=pad_min_z() - BELT_SURFACE_Z_M,
                tcp_position_m=tcp_world_position().tolist(),
                product_position_m=product_pose()[0].tolist(),
            )
            actual_intercept_time_s = sim_time().seconds
            servo_started_s = sim_time().seconds
            servo_duration_s = 0.75
            last_servo_joints = grasp_joints.copy()
            while sim_time().seconds - servo_started_s < servo_duration_s:
                servo_target_tcp = intercept_tcp + np.asarray(
                    (BELT_SPEED_MPS * (sim_time().seconds - planned_intercept_time_s), 0.0, 0.0)
                )
                last_servo_joints = solve_tcp(
                    "matched-velocity Cartesian settle",
                    servo_target_tcp,
                    last_servo_joints,
                )
                apply_and_step(np.concatenate((last_servo_joints, preshape_target)))
            settled_target_tcp = intercept_tcp + np.asarray(
                (BELT_SPEED_MPS * (sim_time().seconds - planned_intercept_time_s), 0.0, 0.0)
            )
            add_trace(
                "servo",
                label="matched_velocity_cartesian_settle",
                target_tcp_position_m=settled_target_tcp.tolist(),
                measured_tcp_position_m=tcp_world_position().tolist(),
                product_position_m=product_pose()[0].tolist(),
            )
            closing_started_s = sim_time().seconds
            closing_end_tcp = intercept_tcp + np.asarray(
                (BELT_SPEED_MPS * (closing_started_s + FINAL_CLOSE_DURATION_S - planned_intercept_time_s), 0.0, 0.0)
            )
            closing_end_joints = solve_tcp("matched-velocity closure", closing_end_tcp, last_servo_joints)
            close_target = np.asarray((-target_travel, target_travel), dtype=float)
            close_all = np.concatenate((closing_end_joints, close_target))
            add_trace(
                "ik",
                label="matched_velocity_closure",
                target_tcp_position_m=closing_end_tcp.tolist(),
                target_joints_rad=closing_end_joints.tolist(),
                target_finger_travel_m=close_target.tolist(),
            )
            sequence.append({"label": "short matched-velocity force-limited closure", "duration_s": FINAL_CLOSE_DURATION_S})
            add_trace("motion", label="short matched-velocity force-limited closure", duration_s=FINAL_CLOSE_DURATION_S)
            finger_start = previous_command[finger_indices].copy()
            while True:
                elapsed_s = sim_time().seconds - closing_started_s
                phase = min(1.0, elapsed_s / FINAL_CLOSE_DURATION_S)
                blend = 0.5 - 0.5 * math.cos(math.pi * phase)
                servo_target_tcp = intercept_tcp + np.asarray(
                    (BELT_SPEED_MPS * (sim_time().seconds - planned_intercept_time_s), 0.0, 0.0)
                )
                closing_end_joints = solve_tcp(
                    "matched-velocity closure servo",
                    servo_target_tcp,
                    closing_end_joints,
                )
                finger_command = finger_start + (close_target - finger_start) * blend
                apply_and_step(np.concatenate((closing_end_joints, finger_command)))
                if phase >= 1.0:
                    break
            add_trace(
                "measured_joints",
                label="after_matched_closure",
                positions_rad=np.asarray(articulation.get_joint_positions(), dtype=float).tolist(),
                tcp_position_m=tcp_world_position().tolist(),
                product_position_m=product_pose()[0].tolist(),
            )
            bilateral_contact = all(any(product_path in pair for pair in pairs) for pairs in contact_pairs)
            supervisor.transition(CellState.VERIFY_GRASP, sim_time(), "bilateral_contact_checked")
            flush_events()
            if not bilateral_contact:
                set_state("recover")
                supervisor.recover(sim_time(), "failed_grasp_contact_confirmation")
                flush_events()
                move("open jaws after failed grasp", finger_indices, GRIPPER_OPEN_TARGET_M, 0.55)
                recovery_tcp = closing_end_tcp + np.asarray((0.0, 0.0, 0.12))
                recovery_joints = solve_tcp("failed-grasp retract", recovery_tcp, closing_end_joints)
                move_cartesian("safe vertical retract after failed grasp", recovery_tcp, tool_orientation, 1.2)
                supervisor.return_to_idle(sim_time(), "physical_recovery_complete")
                flush_events()
                terminal_reason = "failed_grasp_contact_confirmation"
            else:
                conveyor_active = False
                kinematic_attr.Set(False)
                grasp_confirmed = True
                grasped = True
                set_state("verify_grasp")
                hold("contact-confirmed dynamic hold", 0.45)
                pickup_start, _ = product_pose()
                lift_tcp = closing_end_tcp + np.asarray((0.0, 0.0, 0.18))
                lift_joints = solve_tcp("lift", lift_tcp, closing_end_joints)
                move_cartesian("collision-clear physics lift", lift_tcp, _tool_orientation(track.pose_belt.yaw_rad), 1.8)
                settle_robot_at_tcp("post-lift", lift_tcp, _tool_orientation(track.pose_belt.yaw_rad))
                pickup_end, _ = product_pose()
                lift_distance_m = float(pickup_end[2] - pickup_start[2])
                if not grasp_retained("after collision-clear lift"):
                    raise RuntimeError("Contact-confirmed grasp was lost during the vertical lift")

                if args.scenario == "emergency_stop":
                    plc = plc_state(ready=False, emergency=True)
                    set_state("safe_stop")
                    supervisor.safe_stop(sim_time(), "plc_emergency_stop")
                    flush_events()
                    hold("zero-motion emergency stop hold", 0.8)
                    move("controlled jaw opening after reset", finger_indices, GRIPPER_OPEN_TARGET_M, 0.7)
                    grasp_confirmed = False
                    supervisor.return_to_idle(sim_time(), "emergency_stop_reset_and_known_safe")
                    flush_events()
                    terminal_reason = "plc_emergency_stop"
                elif args.solution == "a":
                    tolerance = DeliveryTolerance(0.055, math.radians(7.0), 0.20, 0.10)
                    solution_controller = SolutionAController(supervisor, tolerance, max_hold_s=0.25)
                    if args.scenario == "cutter_unavailable":
                        plc = plc_state(ready=False)
                    ready = solution_controller.begin_direct_transfer(sim_time(), plc, predicted_ready_delay_s=0.5 if not plc.cutter.mode is CutterMode.READY else 0.0)
                    flush_events()
                    if not ready:
                        set_state("reject")
                        reject_tcp = np.asarray((1.05, -0.72, 1.08), dtype=float)
                        reject_joints = solve_tcp("reject", reject_tcp, lift_joints)
                        move("carry to reachable reject location", robot_indices, reject_joints, 1.8)
                        grasp_confirmed = False
                        move("release rejected workpiece", finger_indices, GRIPPER_OPEN_TARGET_M, 0.7)
                        hold("confirm reject release", 0.5)
                        supervisor.return_to_idle(sim_time(), "physical_reject_complete")
                        flush_events()
                        terminal_reason = "cutter_unavailable_before_commit"
                    else:
                        set_state("transfer_direct")
                        cut_yaw = 0.0
                        cut_orientation = _tool_orientation(cut_yaw)
                        cut_high_tcp = np.asarray((CUT_TARGET_CENTER_M[0], CUT_TARGET_CENTER_M[1], CUT_TARGET_CENTER_M[2] + 0.25), dtype=float)
                        cut_high = solve_tcp("cutter high", cut_high_tcp, lift_joints, cut_orientation)
                        cut_high = move_cartesian(
                            "collision-clear Cartesian transport to cutter entrance",
                            cut_high_tcp,
                            cut_orientation,
                            3.6,
                        )
                        settle_robot_at_tcp("cutter high", cut_high_tcp, cut_orientation)
                        if not grasp_retained("after Cartesian cutter transport"):
                            raise RuntimeError("Grasp was lost during the collision-clear cutter transport")
                        solution_controller.complete_direct_transfer(sim_time())
                        flush_events()
                        plc = plc_state(ready=True)
                        if not solution_controller.align_and_feed(sim_time(), plc):
                            raise RuntimeError("Cutter permissive rejected a ready direct feed")
                        flush_events()
                        set_state("align_direct")
                        cut_tcp = np.asarray((CUT_TARGET_CENTER_M[0], CUT_TARGET_CENTER_M[1], CUT_TARGET_CENTER_M[2] + 0.07), dtype=float)
                        cut_pose = solve_tcp("cut target", cut_tcp, cut_high, cut_orientation)
                        move_cartesian("align product to cut_target_frame", cut_tcp, cut_orientation, 1.6)
                        settle_robot_at_tcp("cut target", cut_tcp, cut_orientation)
                        if not grasp_retained("at cut_target_frame"):
                            raise RuntimeError("Grasp was lost before release at cut_target_frame")
                        planned_delivery_time = sim_time().seconds + 0.65 + 0.45
                        release_product_step_start = len(product_positions)
                        grasp_confirmed = False
                        move("release on stationary cutter-entry tray", finger_indices, GRIPPER_OPEN_TARGET_M, 0.65)
                        hold("verify stationary tray delivery", 0.45)
                        product_at_delivery, orientation_at_delivery = product_pose()
                        velocity_at_delivery = np.asarray(product.get_linear_velocity(), dtype=float)
                        measurement = DeliveryMeasurement(
                            float(np.linalg.norm(product_at_delivery[:2] - np.asarray(CUT_TARGET_CENTER_M[:2]))),
                            _angle_error(_yaw_from_wxyz(orientation_at_delivery), 0.0),
                            abs(sim_time().seconds - planned_delivery_time),
                            float(np.linalg.norm(velocity_at_delivery[:2])),
                        )
                        assessment = solution_controller.verify_delivery(sim_time(), measurement, auto_complete_retract=False)
                        flush_events()
                        delivered = assessment.success
                        plc_state(ready=True, acknowledged=delivered)
                        set_state("retract")
                        move("retract clear of cutter", robot_indices, cut_high, 1.25)
                        supervisor.return_to_idle(sim_time(), "physical_retract_complete")
                        flush_events()
                        terminal_reason = "delivery_verified" if delivered else "delivery_out_of_tolerance"
                else:
                    tolerance = DeliveryTolerance(0.055, math.radians(7.0), 0.25, 0.10)
                    grasp_model = GraspModel(GraspModelConfig(0.05, math.radians(25.0), 2, 1.25, 180000.0, 0.004, math.radians(2.0)))
                    buffer = BufferRuntime(1, BUFFER_MAX_HOLD_S)
                    solution_controller = SolutionBController(supervisor, tolerance, buffer, grasp_model)
                    if not solution_controller.begin_buffer_transfer(product_path, sim_time()):
                        raise RuntimeError("Solution B buffer rejected the nominal transfer")
                    flush_events()
                    set_state("transfer_buffer")
                    buffer_high_tcp = np.asarray((BUFFER_TARGET_CENTER_M[0], BUFFER_TARGET_CENTER_M[1], BUFFER_TARGET_CENTER_M[2] + 0.24), dtype=float)
                    buffer_high = solve_tcp("buffer high", buffer_high_tcp, lift_joints)
                    buffer_high = move_cartesian(
                        "collision-clear Cartesian carry to Solution B buffer",
                        buffer_high_tcp,
                        _tool_orientation(track.pose_belt.yaw_rad),
                        2.2,
                    )
                    settle_robot_at_tcp("buffer high", buffer_high_tcp, _tool_orientation(track.pose_belt.yaw_rad))
                    if not grasp_retained("after Cartesian buffer transport"):
                        raise RuntimeError("Grasp was lost during the collision-clear buffer transport")
                    buffer_tcp = np.asarray((BUFFER_TARGET_CENTER_M[0], BUFFER_TARGET_CENTER_M[1], BUFFER_TARGET_CENTER_M[2] + 0.07), dtype=float)
                    buffer_pose_joints = solve_tcp("buffer release", buffer_tcp, buffer_high)
                    move_cartesian(
                        "vertical descent into buffer",
                        buffer_tcp,
                        _tool_orientation(track.pose_belt.yaw_rad),
                        1.3,
                    )
                    settle_robot_at_tcp("buffer release", buffer_tcp, _tool_orientation(track.pose_belt.yaw_rad))
                    if not grasp_retained("before physical buffer release"):
                        raise RuntimeError("Grasp was lost before the buffer release")
                    solution_controller.release_to_buffer(product_path, sim_time())
                    flush_events()
                    grasp_confirmed = False
                    move("release into buffer", finger_indices, GRIPPER_OPEN_TARGET_M, 1.20)
                    hold("verify jaws clear after buffer release", 0.35)
                    released_fingers = np.asarray(articulation.get_joint_positions(), dtype=float)[6:]
                    (output_root / "buffer_release_debug.json").write_text(
                        json.dumps(
                            {
                                "measured_finger_positions_m": released_fingers.tolist(),
                                "commanded_finger_positions_m": previous_command[6:].tolist(),
                                "product_position_m": product_pose()[0].tolist(),
                                "tcp_position_m": tcp_world_position().tolist(),
                            },
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    if np.max(np.abs(released_fingers)) > 0.012:
                        raise RuntimeError(
                            "Buffer release did not reopen both compliant jaws: "
                            f"measured={released_fingers.tolist()}"
                        )
                    add_trace(
                        "measured_joints",
                        label="after_buffer_release",
                        positions=np.asarray(articulation.get_joint_positions(), dtype=float).tolist(),
                        product_position_m=product_pose()[0].tolist(),
                    )
                    move_cartesian(
                        "vertical retreat above buffer",
                        buffer_high_tcp,
                        _tool_orientation(track.pose_belt.yaw_rad),
                        1.1,
                    )
                    move_cartesian(
                        "Cartesian move to clear buffer inspection pose",
                        ready_tcp,
                        _tool_orientation(track.pose_belt.yaw_rad),
                        1.6,
                    )
                    solution_controller.begin_settle(sim_time())
                    flush_events()
                    set_state("settle")
                    if args.scenario == "slip_correction":
                        product.set_linear_velocity(np.asarray((0.0, 0.045, 0.0), dtype=np.float32))
                        product.set_angular_velocity(np.asarray((0.0, 0.0, 0.18), dtype=np.float32))
                    wait_s = BUFFER_MAX_HOLD_S + 0.25 if args.scenario == "buffer_timeout" else 0.65
                    hold("physical buffer settle", wait_s)
                    if args.scenario == "buffer_timeout":
                        current_position, current_orientation = product_pose()
                        observed_pose = Transform.planar(float(current_position[0]), float(current_position[1]), float(current_position[2]), _yaw_from_wxyz(current_orientation))
                        no_slip = grasp_model.estimate_slip(commanded_grasp_from_product=Transform.identity(), observed_grasp_from_product=Transform.identity())
                        solution_controller.reobserve_and_align(sim_time(), observed_pose, no_slip)
                        flush_events()
                        set_state("recover")
                        supervisor.return_to_idle(sim_time(), "buffer_timeout_known_safe")
                        flush_events()
                        terminal_reason = "buffer_timeout"
                    else:
                        # Route the active Fabric render product through the
                        # authored mounted buffer camera. This keeps the dynamic
                        # PhysX product transform current for both RGB and depth.
                        import omni.replicator.core as rep
                        from omni.kit.viewport.utility import get_active_viewport

                        active_viewport = get_active_viewport()
                        if active_viewport is None:
                            raise RuntimeError("No active viewport was available for buffer inspection")
                        fabric_buffer_camera_path = "/OmniverseKit_Persp"
                        active_viewport.camera_path = Sdf.Path(fabric_buffer_camera_path)
                        set_camera_view(
                            eye=[BUFFER_TARGET_CENTER_M[0], BUFFER_TARGET_CENTER_M[1], 1.76],
                            target=[BUFFER_TARGET_CENTER_M[0], BUFFER_TARGET_CENTER_M[1], BUFFER_TARGET_CENTER_M[2]],
                            camera_prim_path=fabric_buffer_camera_path,
                        )
                        fabric_camera_prim = stage.GetPrimAtPath(fabric_buffer_camera_path)
                        fabric_camera_prim.GetAttribute("focalLength").Set(18.0)
                        fabric_camera_prim.GetAttribute("horizontalAperture").Set(20.955)
                        fabric_camera_prim.GetAttribute("verticalAperture").Set(15.71625)
                        saved_viewport_resolution = active_viewport.resolution
                        active_viewport.resolution = (640, 480)
                        rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
                        depth_annotator = rep.AnnotatorRegistry.get_annotator("distance_to_image_plane")
                        render_product_path = active_viewport.render_product_path
                        rgb_annotator.attach([render_product_path])
                        depth_annotator.attach([render_product_path])
                        for _ in range(8):
                            simulation_app.update()
                        rgb_value = rgb_annotator.get_data()
                        depth_value = depth_annotator.get_data()
                        rgb_annotator.detach([render_product_path])
                        depth_annotator.detach([render_product_path])
                        active_viewport.resolution = saved_viewport_resolution
                        if rgb_value is None or depth_value is None:
                            raise RuntimeError("Buffer re-observation RGBD was missing")
                        buffer_rgb = _as_uint8(rgb_value)[..., :3]
                        buffer_depth = np.asarray(depth_value, dtype=np.float32)
                        Image.fromarray(buffer_rgb).save(output_root / "buffer_rgb.png")
                        np.save(output_root / "buffer_depth_m.npy", buffer_depth)
                        active_viewport.camera_path = Sdf.Path(build["presentation_camera_path"])
                        buffer_exposure_time = sim_time()
                        buffer_oracle_position, buffer_oracle_orientation = product_pose()
                        add_trace(
                            "sensor_oracle",
                            frame_index="buffer",
                            exposure_time_s=buffer_exposure_time.seconds,
                            product_position_m=buffer_oracle_position.tolist(),
                            product_yaw_rad=_yaw_from_wxyz(buffer_oracle_orientation),
                            note="test oracle only; not supplied to perception, tracking, planning, or control",
                        )
                        buffer_observations = tuple(
                            calibrated_scene2_observation(item)
                            for item in model.infer(
                                buffer_rgb,
                                buffer_depth,
                                buffer_exposure_time,
                                buffer_calibration,
                            )
                        )
                        (output_root / "buffer_perception_debug.json").write_text(
                            json.dumps(
                                {
                                    "authored_sensor_path": build["buffer_camera_path"],
                                    "capture_camera_path": fabric_buffer_camera_path,
                                    "capture_note": "Isaac's active Fabric camera is calibrated to the exact mounted buffer sensor pose and intrinsics for synchronized RGB and depth.",
                                    "capture_binding": "runtime render-product binding for the authored mounted sensor; no physics or ground-truth data enters perception",
                                    "camera_world_pose": [
                                        np.asarray(buffer_camera.get_world_pose()[0], dtype=float).tolist(),
                                        np.asarray(buffer_camera.get_world_pose()[1], dtype=float).tolist(),
                                    ],
                                    "oracle_position_m": buffer_oracle_position.tolist(),
                                    "oracle_yaw_rad": _yaw_from_wxyz(buffer_oracle_orientation),
                                    "observations": [
                                        {
                                            "confidence": item.confidence,
                                            "x_m": item.pose_belt.translation.x_m,
                                            "y_m": item.pose_belt.translation.y_m,
                                            "z_m": item.pose_belt.translation.z_m,
                                            "bbox": item.bbox.to_dict(),
                                        }
                                        for item in buffer_observations
                                    ],
                                },
                                indent=2,
                                sort_keys=True,
                            )
                            + "\n",
                            encoding="utf-8",
                        )
                        candidates = [item for item in buffer_observations if abs(item.pose_belt.translation.x_m - BUFFER_TARGET_CENTER_M[0]) < 0.25 and abs(item.pose_belt.translation.y_m - BUFFER_TARGET_CENTER_M[1]) < 0.25]
                        if not candidates:
                            raise RuntimeError("YOLO26 did not re-observe the workpiece in the Solution B buffer")
                        observed = max(candidates, key=lambda item: item.confidence)
                        buffer_sensor_oracle_position_error_m = float(
                            np.linalg.norm(
                                np.asarray(
                                    (
                                        observed.pose_belt.translation.x_m,
                                        observed.pose_belt.translation.y_m,
                                        observed.pose_belt.translation.z_m,
                                    ),
                                    dtype=float,
                                )
                                - buffer_oracle_position
                            )
                        )
                        add_trace(
                            "sensor_validation",
                            sensor_path=build["buffer_camera_path"],
                            oracle_position_error_m=buffer_sensor_oracle_position_error_m,
                            oracle_role="test gate only; not used by planning or control",
                        )
                        if buffer_sensor_oracle_position_error_m > 0.05:
                            raise RuntimeError(
                                "Mounted buffer RGBD perception exceeded its 50 mm simulation oracle gate: "
                                f"error_m={buffer_sensor_oracle_position_error_m:.6f}"
                            )
                        while sim_time() < observed.delivery_time:
                            apply_and_step(previous_command.copy())
                        writer.append("buffer_observation", observed.delivery_time, observed)
                        commanded = Transform.planar(*BUFFER_TARGET_CENTER_M, 0.0)
                        slip = grasp_model.estimate_slip(
                            commanded_grasp_from_product=commanded,
                            observed_grasp_from_product=observed.pose_belt,
                        )
                        slip_detected = slip.detected
                        if not solution_controller.reobserve_and_align(sim_time(), observed.pose_belt, slip):
                            raise RuntimeError("Solution B buffer re-observation timed out")
                        flush_events()
                        set_state("reobserve_buffer")
                        regrasp_orientation = _tool_orientation(observed.pose_belt.yaw_rad)
                        regrasp_tcp = np.asarray(
                            (
                                observed.pose_belt.translation.x_m,
                                observed.pose_belt.translation.y_m,
                                observed.pose_belt.translation.z_m + 0.07,
                            ),
                            dtype=float,
                        )
                        regrasp_high_tcp = regrasp_tcp + np.asarray((0.0, 0.0, 0.24), dtype=float)
                        regrasp_high_joints = solve_tcp(
                            "buffer regrasp clearance",
                            regrasp_high_tcp,
                            ready_joints,
                            regrasp_orientation,
                        )
                        regrasp_joints = solve_tcp(
                            "buffer regrasp",
                            regrasp_tcp,
                            regrasp_high_joints,
                            regrasp_orientation,
                        )
                        add_trace(
                            "ik",
                            label="buffer_regrasp_from_yolo_pose",
                            observed_product_pose=observed.pose_belt.to_dict(),
                            target_tcp_position_m=regrasp_tcp.tolist(),
                            target_joints_rad=regrasp_joints.tolist(),
                        )
                        move_cartesian(
                            "move above corrected buffer pose",
                            regrasp_high_tcp,
                            regrasp_orientation,
                            1.8,
                        )
                        move_cartesian(
                            "vertical descent to corrected buffer pose",
                            regrasp_tcp,
                            regrasp_orientation,
                            1.3,
                        )
                        approach_fingers = np.asarray(articulation.get_joint_positions(), dtype=float)[6:]
                        if np.max(np.abs(approach_fingers)) > 0.015:
                            raise RuntimeError(
                                "Buffer approach obstructed an open compliant jaw: "
                                f"measured={approach_fingers.tolist()}"
                            )
                        settle_robot_at_tcp("buffer regrasp approach", regrasp_tcp, regrasp_orientation)
                        add_trace(
                            "measured_joints",
                            label="after_buffer_regrasp_approach",
                            positions=np.asarray(articulation.get_joint_positions(), dtype=float).tolist(),
                            tcp_position_m=tcp_world_position().tolist(),
                            product_position_m=product_pose()[0].tolist(),
                        )
                        contact_pairs = [set(), set()]
                        peak_contact_forces[:] = 0.0
                        move("contact-confirmed buffer regrasp", finger_indices, close_target, 0.8)
                        add_trace(
                            "contact",
                            label="after_buffer_regrasp_closure",
                            positions=np.asarray(articulation.get_joint_positions(), dtype=float).tolist(),
                            tcp_position_m=tcp_world_position().tolist(),
                            product_position_m=product_pose()[0].tolist(),
                            product_bounds=world_bounds(product_path),
                            pad_bounds=[world_bounds(path) for path in pad_paths],
                            contact_pairs=[sorted(pairs) for pairs in contact_pairs],
                            peak_contact_force_n=peak_contact_forces.tolist(),
                        )
                        bilateral_regrasp = all(any(product_path in pair for pair in pairs) for pairs in contact_pairs)
                        if not bilateral_regrasp:
                            raise RuntimeError("Solution B buffer regrasp did not establish bilateral contact")
                        grasp_confirmed = True
                        buffer_lift_tcp = regrasp_tcp + np.asarray((0.0, 0.0, 0.18))
                        buffer_lift = solve_tcp("buffer lift", buffer_lift_tcp, regrasp_joints, regrasp_orientation)
                        buffer_lift = move_cartesian(
                            "vertical lift after buffer regrasp",
                            buffer_lift_tcp,
                            regrasp_orientation,
                            1.5,
                        )
                        settle_robot_at_tcp("buffer lift", buffer_lift_tcp, regrasp_orientation)
                        if not grasp_retained("after buffer regrasp lift"):
                            raise RuntimeError("Corrected buffer regrasp was lost during lift")
                        plc = plc_state(ready=args.scenario != "cutter_unavailable")
                        if not solution_controller.wait_and_feed(sim_time(), plc):
                            raise RuntimeError("Solution B cutter permissive rejected the feed")
                        flush_events()
                        set_state("feed_buffer")
                        cut_orientation = _tool_orientation(0.0)
                        cut_high_tcp = np.asarray((CUT_TARGET_CENTER_M[0], CUT_TARGET_CENTER_M[1], CUT_TARGET_CENTER_M[2] + 0.25), dtype=float)
                        cut_high = solve_tcp("buffer to cutter high", cut_high_tcp, buffer_lift, cut_orientation)
                        cut_high = move_cartesian(
                            "Cartesian transport of corrected product to cutter",
                            cut_high_tcp,
                            cut_orientation,
                            2.4,
                        )
                        settle_robot_at_tcp("buffer to cutter high", cut_high_tcp, cut_orientation)
                        if not grasp_retained("after corrected cutter transport"):
                            raise RuntimeError("Corrected product was lost during cutter transport")
                        cut_tcp = np.asarray((CUT_TARGET_CENTER_M[0], CUT_TARGET_CENTER_M[1], CUT_TARGET_CENTER_M[2] + 0.07), dtype=float)
                        cut_pose = solve_tcp("buffer cut target", cut_tcp, cut_high, cut_orientation)
                        move_cartesian("align corrected product to cut_target_frame", cut_tcp, cut_orientation, 1.6)
                        settle_robot_at_tcp("buffer cut target", cut_tcp, cut_orientation)
                        if not grasp_retained("corrected product at cut_target_frame"):
                            raise RuntimeError("Corrected grasp was lost before cutter release")
                        planned_delivery_time = sim_time().seconds + 0.65 + 0.45
                        release_product_step_start = len(product_positions)
                        grasp_confirmed = False
                        move("release corrected product on cutter tray", finger_indices, GRIPPER_OPEN_TARGET_M, 0.65)
                        hold("verify Solution B tray delivery", 0.45)
                        product_at_delivery, orientation_at_delivery = product_pose()
                        velocity_at_delivery = np.asarray(product.get_linear_velocity(), dtype=float)
                        measurement = DeliveryMeasurement(
                            float(np.linalg.norm(product_at_delivery[:2] - np.asarray(CUT_TARGET_CENTER_M[:2]))),
                            _angle_error(_yaw_from_wxyz(orientation_at_delivery), 0.0),
                            abs(sim_time().seconds - planned_delivery_time),
                            float(np.linalg.norm(velocity_at_delivery[:2])),
                        )
                        assessment = solution_controller.verify_delivery(sim_time(), measurement, auto_complete_retract=False)
                        flush_events()
                        delivered = assessment.success
                        plc_state(ready=True, acknowledged=delivered)
                        set_state("retract")
                        move("retract clear of cutter", robot_indices, cut_high, 1.25)
                        supervisor.return_to_idle(sim_time(), "physical_retract_complete")
                        flush_events()
                        terminal_reason = "delivery_verified" if delivered else "delivery_out_of_tolerance"

        hold("final evidence view", 0.65)
        recording = recorder.close()
    except Exception:
        try:
            recorder.close()
        except Exception:
            pass
        raise

    all_steps = np.asarray(product_positions, dtype=float)
    maximum_product_step_m = float(np.max(np.linalg.norm(np.diff(all_steps, axis=0), axis=1))) if len(all_steps) > 1 else 0.0
    kinematic_steps = np.asarray(kinematic_product_positions, dtype=float)
    maximum_conveyor_step_m = float(np.max(np.linalg.norm(np.diff(kinematic_steps, axis=0), axis=1))) if len(kinematic_steps) > 1 else 0.0
    bilateral_contact = all(any(product_path in pair for pair in pairs) for pairs in contact_pairs)
    unexpected_contact_pairs = sorted({pair for pairs in contact_pairs for pair in pairs if product_path not in pair})
    final_position, final_orientation = product_pose()
    expected_success = args.scenario in {"nominal", "slip_correction"}
    terminal_ok = delivered if expected_success else supervisor.state is CellState.IDLE and not delivered
    perception_gate = perceived and tracked and model.model_name.startswith("ultralytics_yolo26")
    delivery_gate = (
        measurement is not None
        and measurement.position_error_m <= 0.055
        and measurement.angle_error_rad <= math.radians(7.0)
        and measurement.speed_error_mps <= 0.10
    ) if expected_success else True
    passed = bool(
        terminal_ok
        and perception_gate
        and stage_reload_passed
        and recording.frame_count > 0
        and recording.file_bytes > 100000
        and joint_limit_violations == 0
        and velocity_limit_violations == 0
        and acceleration_limit_violations == 0
        and maximum_conveyor_step_m <= BELT_SPEED_MPS / 60.0 * 1.20
        and minimum_precontact_pad_clearance_m >= MIN_PAD_CLEARANCE_M
        and not unexpected_contact_pairs
        and delivery_gate
        and (args.scenario != "slip_correction" or slip_detected)
        and (
            not expected_success
            or grasped
            and bilateral_contact
            and lift_distance_m >= 0.10
            and maximum_grasp_distance_m <= 0.13
        )
    )
    result = CellResult(
        episode_id,
        args.solution,
        TerminalPath.SUCCESS if delivered else TerminalPath.RECOVERED,
        terminal_reason,
        SimTime(0),
        sim_time(),
        perceived,
        tracked,
        grasped,
        delivered,
        slip_detected,
        measurement.position_error_m if measurement else None,
        measurement.angle_error_rad if measurement else None,
        measurement.timing_error_s if measurement else None,
        measurement.speed_error_mps if measurement else None,
        len(unexpected_contact_pairs),
        joint_limit_violations,
    )
    writer.finish(result)
    replay_reader = JsonlEventReader(event_path)
    deterministic_log_readback = replay_reader.terminal_result == result and len(replay_reader.observations()) >= 2
    payload = {
        "passed": passed and deterministic_log_readback,
        "solution": args.solution,
        "scenario": args.scenario,
        "seed": args.seed,
        "demo_kind": "complete Scene 2 rendered YOLO26 to FANUC contact delivery",
        "reference_notice": build["reference_notice"],
        "robot": "FANUC M-10iD/12 official description reference",
        "gripper": "project compact compliant parallel-jaw reference",
        "workpiece_fixture": "Fixed-step kinematic conveyor coupling before bilateral contact, then dynamic PhysX rigid body. No pose writes after confirmed grasp.",
        "initial_product_pose_sets_before_recording": initial_product_teleports,
        "product_pose_sets_after_confirmed_grasp": 0,
        "physics_dt_s": 1.0 / PHYSICS_HZ,
        "belt_speed_mps": BELT_SPEED_MPS,
        "slip_detected": slip_detected,
        "buffer_sensor_oracle_position_error_m": buffer_sensor_oracle_position_error_m,
        "perception": {
            "model_name": model.model_name,
            "checkpoint": str(weights_path),
            "checkpoint_sha256": model.weights_sha256,
            "ultralytics_version": model.package_version,
            "observation_count": observation_count,
            "confidence": first_observation.confidence if first_observation else None,
            "track_id": track.track_id if track else None,
            "track_velocity_mps": track.twist_belt.linear_mps.x_m if track else None,
            "latency_s": perception_latencies,
            "rgb_nonempty": True,
            "depth_nonempty": True,
            "calibration": calibration.__dict__,
            "buffer_calibration": buffer_calibration.__dict__,
            "scene2_optical_axis_correction": "none; synchronized USD and PhysX transforms use the standard pinhole calibration",
        },
        "interception": {
            "planned_x_m": planned_intercept_x,
            "planned_time_s": planned_intercept_time_s,
            "actual_time_s": actual_intercept_time_s,
            "timing_error_s": abs(actual_intercept_time_s - planned_intercept_time_s) if actual_intercept_time_s is not None and planned_intercept_time_s is not None else None,
            "maximum_conveyor_step_m": maximum_conveyor_step_m,
        },
        "grasp": {
            "bilateral_contact": bilateral_contact,
            "peak_contact_force_n": peak_contact_forces.tolist(),
            "unexpected_contact_pairs": unexpected_contact_pairs,
            "lift_distance_m": lift_distance_m,
            "maximum_product_to_tcp_distance_m": maximum_grasp_distance_m,
            "retention_limit_m": 0.13,
        },
        "delivery": {
            "cut_target_center_m": list(CUT_TARGET_CENTER_M),
            "final_product_position_m": final_position.tolist(),
            "final_product_yaw_rad": _yaw_from_wxyz(final_orientation),
            "measurement": measurement.to_dict() if measurement else None,
            "delivered": delivered,
            "plc_result_acknowledged": delivered,
        },
        "motion": {
            "articulation_controller_commands": command_count,
            "simulator_step_calls": physics_steps,
            "joint_limit_violations": joint_limit_violations,
            "velocity_limit_violations": velocity_limit_violations,
            "acceleration_limit_violations": acceleration_limit_violations,
            "command_safety_limit_activations": command_safety_limit_activations,
            "max_command_velocity": dict(zip(expected_dofs, max_velocity.tolist(), strict=True)),
            "max_command_acceleration": dict(zip(expected_dofs, max_acceleration.tolist(), strict=True)),
            "minimum_precontact_pad_clearance_m": minimum_precontact_pad_clearance_m,
            "maximum_product_step_m": maximum_product_step_m,
        },
        "state_sequence": [item["state"] for item in trace if item["kind"] == "state"],
        "sequence": sequence,
        "trace_records": len(trace),
        "event_log_readback_passed": deterministic_log_readback,
        "stage": {
            "path": str(stage_path),
            "sha256": _sha256(stage_path),
            "reload_passed": stage_reload_passed,
            "required_reload_paths": list(required_reload_paths),
        },
        "recording": recording.__dict__,
        "recording_sha256": _sha256(video_path),
        "artifacts": _artifact_manifest(output_root, event_path, args.solution),
        "approximations": [
            "The belt coupling is a deterministic kinematic fixture, not a simulated belt-friction model.",
            "The product is rigid. Tissue deformation and surface moisture are not modeled.",
            "Gripper compliance is a finite-effort linear-drive proxy.",
            "The cutter, buffer, conveyor, and gripper are project reference geometry.",
            "This is simulation evidence, not physical, food-safety, real-cell safety, or production validation.",
        ],
    }
    (output_root / "scene2_integrated_metrics.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "cycle_trace_summary.json").write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    args = parse_args()
    output_root = (PROJECT_ROOT / args.output_root).resolve()
    if Path(args.output_root).is_absolute() or not _inside_project(output_root):
        raise ValueError("Output root must be project-relative")
    simulation_app = None
    payload: dict[str, object] = {"passed": False, "solution": args.solution, "scenario": args.scenario}
    try:
        from isaacsim import SimulationApp

        simulation_app = SimulationApp(
            {
                "headless": True,
                "renderer": "RaytracedLighting",
                "width": 1280,
                "height": 720,
                "anti_aliasing": 0,
                "extra_args": [
                    "--/rtx/post/motionblur/enabled=false",
                    "--/rtx/scenedb/maxHistoryTransformCount=32",
                ],
            }
        )
        payload = run_integrated(simulation_app, args, output_root)
    except Exception as exc:
        payload = {
            "passed": False,
            "solution": args.solution,
            "scenario": args.scenario,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "scene2_integrated_metrics.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    finally:
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        if simulation_app is not None:
            try:
                simulation_app.close()
            except SystemExit:
                pass
    return 0 if payload.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
