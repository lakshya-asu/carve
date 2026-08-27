"""Record a continuous, contact-driven FANUC pickup with no workpiece teleport."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CAMERA = {
    "eye": (1.45, 1.65, 1.65),
    "target": (0.35, 0.08, 0.98),
    "focal_length_mm": 28.0,
    "role": "fixed virtual demonstration camera inside the guard envelope",
}
BELT_SURFACE_Z_M = 0.8075
MIN_PAD_CLEARANCE_M = 0.005


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="results/scene2_real_pickup")
    parser.add_argument("--fps", type=int, default=12)
    return parser.parse_args()


def _inside_project(path: Path) -> bool:
    return path == PROJECT_ROOT or PROJECT_ROOT in path.parents


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _as_uint8(image: object) -> object:
    import numpy as np

    array = np.asarray(image)
    if array.dtype == np.uint8:
        return array
    multiplier = 255.0 if float(array.max(initial=0.0)) <= 1.0 else 1.0
    return np.clip(array * multiplier, 0, 255).astype(np.uint8)


def _tool_orientation(yaw_rad: float) -> object:
    """Return wxyz quaternion with tool X down and tool Z along product length."""
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


def record_demo(simulation_app: object, output_root: Path, fps: int) -> dict[str, object]:
    import numpy as np
    import omni.usd
    from PIL import Image
    from pxr import PhysicsSchemaTools, Usd, UsdGeom, UsdPhysics
    from isaacsim.core.api import World
    from isaacsim.core.prims import SingleArticulation, SingleRigidPrim
    from isaacsim.core.utils.extensions import enable_extension
    from isaacsim.core.utils.types import ArticulationAction
    from isaacsim.core.utils.viewports import set_camera_view
    from isaacsim.robot_motion.motion_generation import LulaKinematicsSolver
    from isaacsim.sensors.camera import Camera

    from isaac_sim.scene2_builder import (
        ARTICULATION_ROOT,
        GRIPPER_DRIVE_STIFFNESS_N_PER_M,
        GRIPPER_GRASP_CENTER_FLANGE_M,
        GRIPPER_NORMAL_FORCE_LIMIT_N,
        Scene2Builder,
        gripper_target_travel_m,
    )
    from isaac_sim.stage_builder import product_width_scale_at_grasp
    from isaac_sim.video_recorder import RawVideoRecorder

    if fps <= 0 or 240 % fps != 0:
        raise ValueError("Frame rate must be a positive divisor of 240")
    output_root.mkdir(parents=True, exist_ok=True)
    World.clear_instance()
    omni.usd.get_context().new_stage()
    world = World(
        physics_dt=1.0 / 240.0,
        rendering_dt=1.0 / 60.0,
        stage_units_in_meters=1.0,
        physics_prim_path="/World/PhysicsScene",
        backend="numpy",
        device="cpu",
    )
    stage = omni.usd.get_context().get_stage()
    build = Scene2Builder().build(stage)
    articulation = world.scene.add(SingleArticulation(ARTICULATION_ROOT, name="fanuc_real_pickup"))
    product_path = build["product_paths"][2]
    product_prim = stage.GetPrimAtPath(product_path)
    product = world.scene.add(SingleRigidPrim(product_path, name="continuous_pickup_product"))

    enable_extension("isaacsim.sensors.experimental.physics")
    simulation_app.update()
    from isaacsim.sensors.experimental.physics import Contact, ContactSensor

    contact_sensors = []
    for index, finger_path in enumerate(build["gripper_finger_paths"]):
        sensor_path = f"{finger_path}/real_pickup_contact_sensor_{index}"
        Contact.create(sensor_path, min_threshold=0.0, max_threshold=100000.0, radius=-1.0)
        contact_sensors.append(ContactSensor(sensor_path))

    world.reset()
    kinematic_attr = UsdPhysics.RigidBodyAPI(product_prim).CreateKinematicEnabledAttr(True)
    kinematic_attr.Set(True)
    controller = articulation.get_articulation_controller()
    dof_names = tuple(str(name) for name in articulation.dof_names)
    expected = ("J1", "J2", "J3", "J4", "J5", "J6", "finger_left", "finger_right")
    if dof_names != expected:
        raise RuntimeError(f"Unexpected FANUC DOF order: {dof_names}")
    lower = np.asarray(articulation.dof_properties["lower"], dtype=float)
    upper = np.asarray(articulation.dof_properties["upper"], dtype=float)
    robot_indices = np.arange(6, dtype=np.int32)
    finger_indices = np.asarray((6, 7), dtype=np.int32)
    overview = np.asarray((0.0, 1.2, 0.4, 0.0, -0.77, 0.0), dtype=float)
    initial_command = np.concatenate((overview, np.zeros(2, dtype=float)))
    controller.apply_action(ArticulationAction(joint_positions=initial_command.astype(np.float32)))
    for step in range(240):
        world.step(render=(step % 4 == 0))

    product_position, product_orientation = product.get_world_pose()
    product_position = np.asarray(product_position, dtype=float)
    if product_position[2] < BELT_SURFACE_Z_M:
        raise RuntimeError("Workpiece fell below the conveyor before recording")

    yaw_rad = math.radians(9.0)
    tool_orientation = _tool_orientation(yaw_rad)
    solver = LulaKinematicsSolver(
        str(PROJECT_ROOT / "configs" / "fanuc_m10id12_lula.yaml"),
        str(PROJECT_ROOT / "assets" / "robots" / "fanuc_m10id12" / "fanuc_m10id12.urdf"),
    )
    solver.set_robot_base_pose(
        np.asarray((0.35, -1.25, 0.59), dtype=float),
        np.asarray((2.0**-0.5, 0.0, 0.0, 2.0**-0.5), dtype=float),
    )

    grasp_tcp = np.asarray((product_position[0], product_position[1], product_position[2] + 0.070))
    tool_down_axis = np.asarray((0.0, 0.0, -1.0))
    flange_offset = tool_down_axis * GRIPPER_GRASP_CENTER_FLANGE_M[0]

    def solve_tcp(label: str, tcp_position: object, warm_start: object) -> np.ndarray:
        flange_target = np.asarray(tcp_position, dtype=float) - flange_offset
        joints, success = solver.compute_inverse_kinematics(
            "ee_link",
            flange_target,
            tool_orientation,
            warm_start=np.asarray(warm_start, dtype=float),
            position_tolerance=0.002,
            orientation_tolerance=0.025,
        )
        if not success:
            raise RuntimeError(f"Lula IK failed for {label}: {flange_target.tolist()}")
        joints = np.asarray(joints, dtype=float)
        if np.any(joints <= lower[:6]) or np.any(joints >= upper[:6]):
            raise RuntimeError(f"IK pose {label} exceeds an imported joint limit")
        return joints

    pregrasp = solve_tcp("pregrasp", grasp_tcp + np.asarray((0.0, 0.0, 0.16)), overview)
    grasp = solve_tcp("grasp", grasp_tcp, pregrasp)
    lift_tcp = grasp_tcp + np.asarray((0.0, 0.0, 0.16))
    lift = solve_tcp("lift", lift_tcp, grasp)
    transfer_tcp = lift_tcp + np.asarray((0.20, 0.0, 0.0))
    transfer = solve_tcp("transfer", transfer_tcp, lift)
    release_tcp = transfer_tcp - np.asarray((0.0, 0.0, 0.16))
    release_pose = solve_tcp("release", release_tcp, transfer)

    record_start_command = np.concatenate((pregrasp, np.zeros(2, dtype=float)))
    articulation.set_joint_positions(record_start_command.astype(np.float32))
    articulation.set_joint_velocities(np.zeros(8, dtype=np.float32))
    controller.apply_action(ArticulationAction(joint_positions=record_start_command.astype(np.float32)))
    for step in range(120):
        world.step(render=(step % 4 == 0))

    set_camera_view(
        eye=list(CAMERA["eye"]),
        target=list(CAMERA["target"]),
        camera_prim_path=build["presentation_camera_path"],
    )
    camera_prim = stage.GetPrimAtPath(build["presentation_camera_path"])
    camera_prim.GetAttribute("focalLength").Set(CAMERA["focal_length_mm"])
    camera = Camera(
        build["presentation_camera_path"],
        name="scene2_real_pickup_camera",
        resolution=(1280, 720),
        frequency=60,
    )
    camera.initialize()
    for _ in range(24):
        world.render()

    video_path = output_root / "scene2_real_pickup.mp4"
    poster_path = output_root / "scene2_real_pickup_poster.png"
    recorder = RawVideoRecorder(video_path, fps=fps, width=1280, height=720, source="rendered_fixed_camera_rgb")
    interval = 240 // fps
    previous_command = record_start_command.copy()
    previous_velocity = np.zeros(8, dtype=float)
    max_velocity = np.zeros(8, dtype=float)
    max_acceleration = np.zeros(8, dtype=float)
    command_count = 0
    physics_steps = 0
    joint_limit_violations = 0
    sequence: list[dict[str, object]] = []
    contact_pairs: list[set[tuple[str, str]]] = [set(), set()]
    peak_contact_forces = np.zeros(2, dtype=float)
    product_positions: list[list[float]] = []
    relative_offsets: list[list[float]] = []
    closure_started = False
    grasp_confirmed = False
    minimum_pad_z = float("inf")
    minimum_approach_pad_clearance = float("inf")
    pad_paths = [
        str(child.GetPath())
        for finger_path in build["gripper_finger_paths"]
        for child in stage.TraverseAll()
        if str(child.GetPath()).startswith(finger_path + "/SoftPad")
        and child.IsA(UsdGeom.Boundable)
    ]
    if not pad_paths:
        raise RuntimeError("No gripper pad geometry was found for clearance validation")

    def tcp_world_position() -> np.ndarray:
        cache = UsdGeom.XformCache(Usd.TimeCode.Default())
        matrix = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(f"{build['gripper_finger_paths'][0].rsplit('/', 1)[0]}/CompliantGripperReference/grasp_tcp"))
        return np.asarray(tuple(matrix.ExtractTranslation()), dtype=float)

    def pad_min_z() -> float:
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
        return min(
            float(cache.ComputeWorldBound(stage.GetPrimAtPath(path)).ComputeAlignedRange().GetMin()[2])
            for path in pad_paths
        )

    def capture_frame() -> None:
        image = camera.get_rgb()
        if image is None:
            raise RuntimeError("Presentation camera stopped publishing while recording")
        rgb = _as_uint8(image)[..., :3]
        recorder.write_frame(rgb.tobytes(), int(round(float(world.current_time) * 1_000_000_000)))

    def apply_and_step(command: object, step_index: int) -> None:
        nonlocal previous_command, previous_velocity, command_count, physics_steps
        nonlocal joint_limit_violations, minimum_pad_z, minimum_approach_pad_clearance
        command_array = np.asarray(command, dtype=float)
        velocity = (command_array - previous_command) * 240.0
        acceleration = (velocity - previous_velocity) * 240.0
        max_velocity[:] = np.maximum(max_velocity, np.abs(velocity))
        max_acceleration[:] = np.maximum(max_acceleration, np.abs(acceleration))
        if np.any(command_array < lower - 1e-6) or np.any(command_array > upper + 1e-6):
            joint_limit_violations += 1
        controller.apply_action(ArticulationAction(joint_positions=command_array.astype(np.float32)))
        should_capture = step_index % interval == 0
        world.step(render=(step_index % 4 == 0 or should_capture))
        command_count += 1
        physics_steps += 1
        previous_command = command_array
        previous_velocity = velocity
        current_product_position, _ = product.get_world_pose()
        product_positions.append(np.asarray(current_product_position, dtype=float).tolist())
        current_pad_z = pad_min_z()
        minimum_pad_z = min(minimum_pad_z, current_pad_z)
        if not closure_started:
            minimum_approach_pad_clearance = min(
                minimum_approach_pad_clearance, current_pad_z - BELT_SURFACE_Z_M
            )
        if grasp_confirmed:
            relative_offsets.append(
                (np.asarray(current_product_position, dtype=float) - tcp_world_position()).tolist()
            )
        for sensor_index, sensor in enumerate(contact_sensors):
            for contact in sensor.get_raw_data():
                body0 = str(PhysicsSchemaTools.intToSdfPath(int(contact["body0"])))
                body1 = str(PhysicsSchemaTools.intToSdfPath(int(contact["body1"])))
                contact_pairs[sensor_index].add((body0, body1))
                if product_path not in (body0, body1):
                    continue
                impulse = contact["impulse"]
                dt = max(float(contact.get("dt", 1.0 / 240.0)), 1e-9)
                force = math.sqrt(
                    float(impulse["x"]) ** 2
                    + float(impulse["y"]) ** 2
                    + float(impulse["z"]) ** 2
                ) / dt
                peak_contact_forces[sensor_index] = max(peak_contact_forces[sensor_index], force)
        if should_capture:
            capture_frame()

    def hold(label: str, duration_s: float) -> None:
        sequence.append({"label": label, "duration_s": duration_s})
        for step in range(1, int(round(duration_s * 240.0)) + 1):
            apply_and_step(previous_command.copy(), step)

    def move(label: str, indices: object, target: object, duration_s: float) -> None:
        sequence.append({"label": label, "duration_s": duration_s})
        selected = np.asarray(indices, dtype=int)
        start = previous_command[selected].copy()
        target_array = np.asarray(target, dtype=float)
        steps = int(round(duration_s * 240.0))
        for step in range(1, steps + 1):
            phase = step / steps
            blend = 0.5 - 0.5 * math.cos(math.pi * phase)
            command = previous_command.copy()
            command[selected] = start + (target_array - start) * blend
            apply_and_step(command, step)

    recording = None
    try:
        hold("show visible workpiece and open-jaw pregrasp clearance", 1.2)
        move("vertical approach", robot_indices, grasp, 1.5)
        hold("open jaws around visible workpiece", 0.4)
        closure_started = True
        product_width_m = 0.14 * product_width_scale_at_grasp("elongated_rounded_prism", 0.82)
        target_travel_m = gripper_target_travel_m(product_width_m)
        close_target = np.asarray((-target_travel_m, target_travel_m), dtype=float)
        move("force-limited bilateral closure", finger_indices, close_target, 1.0)
        bilateral_contact = all(any(product_path in pair for pair in pairs) for pairs in contact_pairs)
        if not bilateral_contact:
            raise RuntimeError("Bilateral workpiece contact was not established")
        kinematic_attr.Set(False)
        grasp_confirmed = True
        hold("contact-confirmed hold", 0.6)
        pickup_start, _ = product.get_world_pose()
        move("physics lift", robot_indices, lift, 1.8)
        pickup_end, _ = product.get_world_pose()
        lift_distance_m = float(np.asarray(pickup_end)[2] - np.asarray(pickup_start)[2])
        hold("show retained workpiece", 0.8)
        poster_image = camera.get_rgb()
        if poster_image is None:
            raise RuntimeError("Camera did not publish the pickup poster frame")
        Image.fromarray(_as_uint8(poster_image)[..., :3]).save(poster_path)
        move("bounded transport", robot_indices, transfer, 1.5)
        move("lower to release height", robot_indices, release_pose, 1.4)
        release_start, _ = product.get_world_pose()
        grasp_confirmed = False
        move("visible jaw opening", finger_indices, (0.0, 0.0), 0.8)
        hold("visible physical release", 1.0)
        release_end, _ = product.get_world_pose()
        release_displacement_m = float(np.linalg.norm(np.asarray(release_end) - np.asarray(release_start)))
        move("retract", robot_indices, transfer, 1.2)
        hold("finish", 0.6)
        recording = recorder.close()
    except Exception:
        try:
            recorder.close()
        except Exception:
            pass
        raise

    product_steps = np.asarray(product_positions, dtype=float)
    maximum_product_step_m = float(np.max(np.linalg.norm(np.diff(product_steps, axis=0), axis=1)))
    relative_array = np.asarray(relative_offsets, dtype=float)
    relative_drift_m = float(
        np.max(np.linalg.norm(relative_array - relative_array[0], axis=1))
    ) if len(relative_array) else float("inf")
    bilateral_contact = all(any(product_path in pair for pair in pairs) for pairs in contact_pairs)
    unexpected_contact_pairs = sorted(
        {
            pair
            for pairs in contact_pairs
            for pair in pairs
            if product_path not in pair
        }
    )
    passed = bool(
        recording.frame_count > 0
        and recording.file_bytes > 100000
        and joint_limit_violations == 0
        and bilateral_contact
        and all(force > 0.1 for force in peak_contact_forces)
        and lift_distance_m >= 0.10
        and relative_drift_m <= 0.020
        and release_displacement_m >= 0.020
        and maximum_product_step_m <= 0.020
        and minimum_approach_pad_clearance >= MIN_PAD_CLEARANCE_M
        and not unexpected_contact_pairs
    )
    payload = {
        "passed": passed,
        "demo_kind": "continuous stationary-belt physics pickup, transport, and release",
        "moving_conveyor_interception": False,
        "moving_conveyor_note": "This gate proves real pickup continuity. Moving interception remains the next integration gate.",
        "robot": "FANUC M-10iD/12 official description reference",
        "reference_notice": build["reference_notice"],
        "product_path": product_path,
        "product_visible_before_approach": True,
        "teleport_calls_after_record_start": 0,
        "workpiece_fixture": "Kinematic on the stationary belt until bilateral contact, then dynamic for lift and release.",
        "camera": CAMERA,
        "sequence": sequence,
        "ik": {
            "solver": "Isaac Sim LulaKinematicsSolver",
            "pregrasp_rad": pregrasp.tolist(),
            "grasp_rad": grasp.tolist(),
            "lift_rad": lift.tolist(),
            "transfer_rad": transfer.tolist(),
            "release_rad": release_pose.tolist(),
        },
        "grasp_validation": {
            "bilateral_contact": bilateral_contact,
            "peak_contact_force_n": peak_contact_forces.tolist(),
            "contact_pairs": [sorted(list(pairs)) for pairs in contact_pairs],
            "unexpected_contact_pairs": unexpected_contact_pairs,
            "lift_distance_m": lift_distance_m,
            "maximum_relative_drift_m": relative_drift_m,
            "release_displacement_m": release_displacement_m,
        },
        "clearance_validation": {
            "belt_surface_z_m": BELT_SURFACE_Z_M,
            "minimum_pad_z_m": minimum_pad_z,
            "minimum_approach_pad_clearance_m": minimum_approach_pad_clearance,
            "required_clearance_m": MIN_PAD_CLEARANCE_M,
        },
        "continuity_validation": {
            "sample_count": len(product_positions),
            "maximum_product_step_m": maximum_product_step_m,
            "maximum_allowed_step_m": 0.020,
        },
        "joint_limit_violations": joint_limit_violations,
        "max_command_velocity": dict(zip(expected, max_velocity.tolist(), strict=True)),
        "max_command_acceleration": dict(zip(expected, max_acceleration.tolist(), strict=True)),
        "physics_dt_seconds": 1.0 / 240.0,
        "physics_steps": physics_steps,
        "articulation_command_count": command_count,
        "recording": recording.to_dict(),
        "recording_sha256": _sha256(video_path),
        "poster_path": str(poster_path),
        "poster_sha256": _sha256(poster_path),
    }
    (output_root / "scene2_real_pickup_metrics.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def main() -> int:
    args = parse_args()
    output_root = (PROJECT_ROOT / args.output_root).resolve()
    if Path(args.output_root).is_absolute() or not _inside_project(output_root):
        raise ValueError("Output root must be project-relative and inside the project")
    simulation_app = None
    payload: dict[str, object] = {"passed": False}
    try:
        from isaacsim import SimulationApp

        simulation_app = SimulationApp(
            {
                "headless": True,
                "renderer": "RaytracedLighting",
                "width": 1280,
                "height": 720,
                "anti_aliasing": 0,
            }
        )
        payload = record_demo(simulation_app, output_root, args.fps)
    except Exception as exc:
        payload = {
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "scene2_real_pickup_metrics.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
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
