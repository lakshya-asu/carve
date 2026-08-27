"""Record a clear presentation-camera demo of the Scene 2 FANUC articulation."""

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


PRESENTATION_CAMERA = {
    "eye": (3.65, -2.20, 2.40),
    "target": (0.30, 0.00, 0.86),
    "focal_length_mm": 18.0,
    "role": "virtual demonstration camera inside the guard envelope",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="results/scene2_presentation_demo")
    parser.add_argument("--fps", type=int, default=12)
    return parser.parse_args()


def _inside_project(path: Path) -> bool:
    return path == PROJECT_ROOT or PROJECT_ROOT in path.parents


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _as_uint8(image: object) -> object:
    import numpy as np

    array = np.asarray(image)
    if array.dtype == np.uint8:
        return array
    multiplier = 255.0 if float(array.max(initial=0.0)) <= 1.0 else 1.0
    return np.clip(array * multiplier, 0, 255).astype(np.uint8)


def record_demo(simulation_app: object, output_root: Path, fps: int) -> dict[str, object]:
    import numpy as np
    import omni.usd
    from PIL import Image
    from pxr import Gf, PhysicsSchemaTools, PhysxSchema, UsdGeom, UsdPhysics
    from isaacsim.core.api import World
    from isaacsim.core.prims import SingleArticulation, SingleRigidPrim
    from isaacsim.core.utils.extensions import enable_extension
    from isaacsim.core.utils.types import ArticulationAction
    from isaacsim.core.utils.viewports import set_camera_view
    from isaacsim.sensors.camera import Camera

    from isaac_sim.scene2_builder import (
        ARTICULATION_ROOT,
        FLANGE_PATH,
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
    articulation = world.scene.add(SingleArticulation(ARTICULATION_ROOT, name="fanuc_presentation_demo"))
    test_product = world.scene.add(
        SingleRigidPrim(build["product_paths"][0], name="fanuc_presentation_grasp_product")
    )
    enable_extension("isaacsim.sensors.experimental.physics")
    simulation_app.update()
    from isaacsim.sensors.experimental.physics import Contact, ContactSensor

    contact_sensors = []
    for finger_path in build["gripper_finger_paths"]:
        sensor_path = f"{finger_path}/presentation_contact_sensor"
        Contact.create(sensor_path, min_threshold=0.0, max_threshold=100000.0, radius=-1.0)
        contact_sensors.append(ContactSensor(sensor_path))
    world.reset()
    controller = articulation.get_articulation_controller()
    dof_names = tuple(str(name) for name in articulation.dof_names)
    expected = ("J1", "J2", "J3", "J4", "J5", "J6", "finger_left", "finger_right")
    if dof_names != expected:
        raise RuntimeError(f"Unexpected FANUC DOF order: {dof_names}")

    robot_indices = np.arange(6, dtype=np.int32)
    finger_indices = np.array([6, 7], dtype=np.int32)
    lower = np.asarray(articulation.dof_properties["lower"], dtype=float)
    upper = np.asarray(articulation.dof_properties["upper"], dtype=float)
    robot_poses = {
        "overview": np.array([0.00, 1.20, 0.40, 0.00, -0.77, 0.00], dtype=np.float32),
        "belt_approach": np.array([0.25, 1.10, 0.35, 0.12, -0.75, -0.18], dtype=np.float32),
        "transfer": np.array([-0.65, 1.00, 0.30, -0.16, -0.82, 0.25], dtype=np.float32),
        "gripper_inspection": np.array([-1.40, 0.40, 0.20, 0.00, -0.40, 0.00], dtype=np.float32),
    }
    for name, pose in robot_poses.items():
        if np.any(pose <= lower[robot_indices]) or np.any(pose >= upper[robot_indices]):
            raise RuntimeError(f"Presentation pose {name} exceeds an imported joint limit")

    controller.apply_action(
        ArticulationAction(joint_positions=robot_poses["overview"], joint_indices=robot_indices)
    )
    for step in range(180):
        world.step(render=(step % 4 == 0))

    set_camera_view(
        eye=list(PRESENTATION_CAMERA["eye"]),
        target=list(PRESENTATION_CAMERA["target"]),
        camera_prim_path=build["presentation_camera_path"],
    )
    camera_prim = stage.GetPrimAtPath(build["presentation_camera_path"])
    camera_prim.GetAttribute("focalLength").Set(PRESENTATION_CAMERA["focal_length_mm"])
    camera = Camera(
        build["presentation_camera_path"],
        name="scene2_presentation_demo_camera",
        resolution=(1280, 720),
        frequency=60,
    )
    camera.initialize()
    for _ in range(24):
        world.render()

    poster = output_root / "scene2_fanuc_demo_poster.png"
    open_jaws_image_path = output_root / "scene2_gripper_open.png"
    aligned_cut_image_path = output_root / "scene2_gripper_aligned.png"

    recorder = RawVideoRecorder(
        output_root / "scene2_fanuc_demo.mp4",
        fps=fps,
        width=1280,
        height=720,
        source="rendered_presentation_rgb",
    )
    interval = 240 // fps
    physics_steps = 0
    command_count = 0
    max_velocity = np.zeros(8, dtype=float)
    max_acceleration = np.zeros(8, dtype=float)
    previous_command = np.concatenate((robot_poses["overview"].astype(float), np.zeros(2, dtype=float)))
    previous_velocity = np.zeros(8, dtype=float)
    limit_violations = 0
    sequence = []
    monitor_grasp_contacts = False
    peak_contact_forces = np.zeros(2, dtype=float)
    product_path = build["product_paths"][0]
    contact_pairs: list[set[tuple[str, str]]] = [set(), set()]

    def capture_frame() -> None:
        image = camera.get_rgb()
        if image is None:
            raise RuntimeError("Presentation camera stopped publishing while recording")
        rgb = _as_uint8(image)[..., :3]
        recorder.write_frame(rgb.tobytes(), int(round(float(world.current_time) * 1_000_000_000)))

    def apply_and_step(command: object, step_index: int) -> None:
        nonlocal physics_steps, command_count, previous_command, previous_velocity, limit_violations
        command_array = np.asarray(command, dtype=float)
        velocity = (command_array - previous_command) * 240.0
        acceleration = (velocity - previous_velocity) * 240.0
        max_velocity[:] = np.maximum(max_velocity, np.abs(velocity))
        max_acceleration[:] = np.maximum(max_acceleration, np.abs(acceleration))
        if np.any(command_array < lower - 1e-6) or np.any(command_array > upper + 1e-6):
            limit_violations += 1
        controller.apply_action(ArticulationAction(joint_positions=command_array.astype(np.float32)))
        should_capture = step_index % interval == 0
        world.step(render=(step_index % 4 == 0 or should_capture))
        physics_steps += 1
        command_count += 1
        previous_command = command_array
        previous_velocity = velocity
        if monitor_grasp_contacts:
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
                    peak_contact_forces[sensor_index] = max(
                        peak_contact_forces[sensor_index], force
                    )
        if should_capture:
            capture_frame()

    def hold(label: str, duration_s: float) -> None:
        sequence.append({"label": label, "duration_s": duration_s})
        command = previous_command.copy()
        for step in range(1, int(round(duration_s * 240.0)) + 1):
            apply_and_step(command, step)

    def move_joints(label: str, indices: object, target: object, duration_s: float) -> None:
        sequence.append({"label": label, "duration_s": duration_s})
        start_all = previous_command.copy()
        start = start_all[np.asarray(indices, dtype=int)]
        target_array = np.asarray(target, dtype=float)
        steps = int(round(duration_s * 240.0))
        for step in range(1, steps + 1):
            phase = step / steps
            blend = 0.5 - 0.5 * math.cos(math.pi * phase)
            command = previous_command.copy()
            command[np.asarray(indices, dtype=int)] = start + (target_array - start) * blend
            apply_and_step(command, step)

    try:
        hold("establish cell", 1.0)
        move_joints("move toward belt", robot_indices, robot_poses["belt_approach"], 2.0)
        hold("show belt approach", 0.75)
        move_joints("transfer across cell", robot_indices, robot_poses["transfer"], 2.0)
        move_joints("present compliant gripper", robot_indices, robot_poses["gripper_inspection"], 2.0)
        hold("show open guided jaws", 0.75)

        product_prim = stage.GetPrimAtPath(product_path)
        rigid_api = PhysxSchema.PhysxRigidBodyAPI.Apply(product_prim)
        rigid_api.CreateDisableGravityAttr(True).Set(True)
        kinematic_attr = UsdPhysics.RigidBodyAPI(product_prim).CreateKinematicEnabledAttr(True)
        flange_matrix = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(FLANGE_PATH))
        demo_product_center_flange_m = (
            GRIPPER_GRASP_CENTER_FLANGE_M[0] + 0.12,
            GRIPPER_GRASP_CENTER_FLANGE_M[1],
            GRIPPER_GRASP_CENTER_FLANGE_M[2],
        )
        grasp_position = np.asarray(
            tuple(flange_matrix.Transform(Gf.Vec3d(*demo_product_center_flange_m))),
            dtype=np.float32,
        )
        flange_quat = Gf.Transform(flange_matrix).GetRotation().GetQuat()
        grasp_orientation = np.asarray(
            (flange_quat.GetReal(), *tuple(flange_quat.GetImaginary())),
            dtype=np.float32,
        )
        closeup_eye_local = Gf.Vec3d(
            demo_product_center_flange_m[0] + 1.35,
            demo_product_center_flange_m[1] - 0.85,
            demo_product_center_flange_m[2] + 0.95,
        )
        closeup_eye = flange_matrix.Transform(closeup_eye_local)
        camera_prim.GetAttribute("focalLength").Set(24.0)
        set_camera_view(
            eye=list(tuple(closeup_eye)),
            target=list(tuple(grasp_position)),
            camera_prim_path=build["presentation_camera_path"],
        )
        for _ in range(24):
            world.render()
        open_jaws_image = camera.get_rgb()
        if open_jaws_image is None:
            raise RuntimeError("Presentation camera did not publish the open-jaw frame")
        Image.fromarray(_as_uint8(open_jaws_image)[..., :3]).save(open_jaws_image_path)
        test_product.set_world_pose(grasp_position, grasp_orientation)
        sequence.append({"label": "place reference cut at grasp test pose", "duration_s": 0.0})
        hold("show aligned reference cut", 0.75)
        aligned_cut_image = camera.get_rgb()
        if aligned_cut_image is None:
            raise RuntimeError("Presentation camera did not publish the aligned-cut frame")
        Image.fromarray(_as_uint8(aligned_cut_image)[..., :3]).save(aligned_cut_image_path)

        product_width_m = 0.14 * product_width_scale_at_grasp("elongated_rounded_prism", 0.82)
        target_travel_m = gripper_target_travel_m(product_width_m)
        close_target = np.asarray((-target_travel_m, target_travel_m), dtype=float)
        monitor_grasp_contacts = True
        move_joints("close force-limited compliant jaws", finger_indices, close_target, 1.25)
        measured_closed = np.asarray(articulation.get_joint_positions(), dtype=float)[finger_indices]
        elastic_deflection = np.abs(close_target - measured_closed)
        force_proxy = np.minimum(
            elastic_deflection * GRIPPER_DRIVE_STIFFNESS_N_PER_M,
            GRIPPER_NORMAL_FORCE_LIMIT_N,
        )
        kinematic_attr.Set(False)
        rigid_api.GetDisableGravityAttr().Set(False)
        test_product.set_linear_velocity(np.zeros(3, dtype=np.float32))
        test_product.set_angular_velocity(np.zeros(3, dtype=np.float32))
        hold_start, _ = test_product.get_world_pose()
        hold("gravity hold with bilateral contact", 1.50)
        hold_end, _ = test_product.get_world_pose()
        hold_slip_m = float(np.linalg.norm(np.asarray(hold_end) - np.asarray(hold_start)))

        poster_image = camera.get_rgb()
        if poster_image is None:
            raise RuntimeError("Presentation camera did not publish the grasp poster frame")
        Image.fromarray(_as_uint8(poster_image)[..., :3]).save(poster)

        release_start, _ = test_product.get_world_pose()
        move_joints("open compliant jaws", finger_indices, (0.0, 0.0), 1.0)
        hold("show physical release", 0.75)
        release_end, _ = test_product.get_world_pose()
        release_displacement_m = float(
            np.linalg.norm(np.asarray(release_end) - np.asarray(release_start))
        )
        monitor_grasp_contacts = False
        camera_prim.GetAttribute("focalLength").Set(PRESENTATION_CAMERA["focal_length_mm"])
        set_camera_view(
            eye=list(PRESENTATION_CAMERA["eye"]),
            target=list(PRESENTATION_CAMERA["target"]),
            camera_prim_path=build["presentation_camera_path"],
        )
        for _ in range(24):
            world.render()
        move_joints("return to overview", robot_indices, robot_poses["overview"], 2.0)
        hold("finish", 1.0)
        recording = recorder.close()
    except Exception:
        try:
            recorder.close()
        except Exception:
            pass
        raise

    bilateral_contact = all(
        any(product_path in pair for pair in pairs)
        for pairs in contact_pairs
    )
    unexpected_contact_pairs = sorted(
        {
            pair
            for pairs in contact_pairs
            for pair in pairs
            if product_path not in pair
        }
    )
    grasp_gate_passed = bool(
        bilateral_contact
        and np.all(elastic_deflection >= 0.001)
        and np.all(elastic_deflection <= 0.015)
        and np.all(force_proxy >= 30.0)
        and np.all(force_proxy <= GRIPPER_NORMAL_FORCE_LIMIT_N + 1e-6)
        and hold_slip_m <= 0.005
        and release_displacement_m >= 0.020
        and not unexpected_contact_pairs
    )
    payload = {
        "passed": bool(
            recording.frame_count > 0
            and recording.file_bytes > 100000
            and limit_violations == 0
            and grasp_gate_passed
        ),
        "demo_kind": "standard arm articulation and contact-confirmed compliant grasp presentation",
        "end_to_end_delivery": False,
        "end_to_end_note": "This proves the Scene 2 gripper contact, gravity hold, and release. Full YOLO-to-FANUC pickup and delivery remains T016.",
        "robot": "FANUC M-10iD/12 official description reference",
        "reference_notice": build["reference_notice"],
        "camera": PRESENTATION_CAMERA,
        "sequence": sequence,
        "physics_dt_seconds": 1.0 / 240.0,
        "physics_steps": physics_steps,
        "articulation_command_count": command_count,
        "joint_limit_violations": limit_violations,
        "grasp_validation": {
            "passed": grasp_gate_passed,
            "product_path": product_path,
            "product_width_m": product_width_m,
            "demo_product_center_flange_m": list(demo_product_center_flange_m),
            "close_target_m": close_target.tolist(),
            "measured_closed_m": measured_closed.tolist(),
            "elastic_deflection_m": elastic_deflection.tolist(),
            "force_proxy_n": force_proxy.tolist(),
            "force_limit_n": GRIPPER_NORMAL_FORCE_LIMIT_N,
            "bilateral_contact": bilateral_contact,
            "peak_contact_force_n": peak_contact_forces.tolist(),
            "contact_pairs": [sorted(list(pairs)) for pairs in contact_pairs],
            "unexpected_contact_pairs": unexpected_contact_pairs,
            "gravity_hold_slip_m": hold_slip_m,
            "release_displacement_m": release_displacement_m,
            "assumption": "Rigid product and linear series-compliance reference. No tissue deformation or pressure validation.",
        },
        "max_joint_velocity": {name: float(value) for name, value in zip(expected, max_velocity, strict=True)},
        "max_joint_acceleration": {name: float(value) for name, value in zip(expected, max_acceleration, strict=True)},
        "recording": recording.to_dict(),
        "recording_sha256": _file_sha256(Path(recording.path)),
        "poster_path": str(poster),
        "poster_sha256": _file_sha256(poster),
        "open_jaws_image_path": str(open_jaws_image_path),
        "open_jaws_image_sha256": _file_sha256(open_jaws_image_path),
        "aligned_cut_image_path": str(aligned_cut_image_path),
        "aligned_cut_image_sha256": _file_sha256(aligned_cut_image_path),
    }
    (output_root / "scene2_presentation_metrics.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
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
        (output_root / "scene2_presentation_failure.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
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
