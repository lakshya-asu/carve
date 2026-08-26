"""Build, animate, render, save, and validate the Scene 2.0 FANUC cell."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import traceback


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--keep-open-seconds", type=float, default=0.0)
    parser.add_argument("--motion-cycles", type=int, default=1)
    parser.add_argument("--output-root", default="results/scene2")
    parser.add_argument("--ros2", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--ros2-self-test", action=argparse.BooleanOptionalAction, default=False)
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


def _run_ros2_gate(
    world: object,
    articulation: object,
    controller: object,
    camera: object,
    lower: object,
    upper: object,
) -> dict[str, object]:
    import numpy as np
    import rclpy
    from isaacsim.core.utils.types import ArticulationAction

    from isaac_sim.scene2_ros_bridge import Scene2RosBridge
    from isaac_sim.scene2_ros_probe import Scene2RosProbe

    bridge = Scene2RosBridge(
        articulation,
        camera,
        lower_limits=tuple(float(value) for value in lower),
        upper_limits=tuple(float(value) for value in upper),
    )
    probe = Scene2RosProbe()
    start = np.asarray(articulation.get_joint_positions(), dtype=float)
    offset = np.array([0.04, -0.035, 0.03, 0.025, -0.02, 0.03], dtype=float)
    target = np.minimum(np.maximum(start + offset, lower + 0.02), upper - 0.02)
    command_applied = False
    try:
        for step in range(720):
            sim_seconds = float(world.current_time)
            bridge.publish_clock(sim_seconds)
            if step % 4 == 0:
                bridge.publish_joint_state(sim_seconds)
            if step % 16 == 0:
                bridge.publish_camera(sim_seconds)
            if step == 72:
                probe.publish_invalid_partial_command(tuple(float(value) for value in target))
            if step >= 96 and step % 24 == 0 and not command_applied:
                probe.publish_command(tuple(float(value) for value in target))
            probe.spin_once()
            bridge.spin_once()
            command = bridge.consume_command()
            if command is not None:
                controller.apply_action(
                    ArticulationAction(joint_positions=np.asarray(command.positions, dtype=np.float32))
                )
                command_applied = True
            world.step(render=(step % 4 == 0))
        for _ in range(32):
            bridge.spin_once()
            probe.spin_once()
        measured = np.asarray(articulation.get_joint_positions(), dtype=float)
        error = np.abs(measured - target)
        snapshot = probe.snapshot
        passed = bool(
            command_applied
            and bridge.rejected_commands >= 1
            and snapshot.clocks > 0
            and snapshot.joint_states > 0
            and snapshot.rgb_images > 0
            and snapshot.depth_images > 0
            and snapshot.camera_info > 0
            and snapshot.last_rgb_bytes >= 640 * 480 * 3
            and snapshot.last_depth_bytes >= 640 * 480 * 4
            and float(error.max()) < 0.03
        )
        return {
            "passed": passed,
            "transport": "ROS 2 DDS using Isaac Sim bundled Humble libraries",
            "command_applied_by_articulation_controller": command_applied,
            "target_joint_positions_rad": target.tolist(),
            "measured_joint_positions_rad": measured.tolist(),
            "max_joint_error_rad": float(error.max()),
            "probe": {
                "clocks_received": snapshot.clocks,
                "joint_states_received": snapshot.joint_states,
                "rgb_images_received": snapshot.rgb_images,
                "depth_images_received": snapshot.depth_images,
                "camera_info_received": snapshot.camera_info,
                "last_rgb_bytes": snapshot.last_rgb_bytes,
                "last_depth_bytes": snapshot.last_depth_bytes,
                "commands_published": probe.commands_published,
            },
            "bridge": bridge.metrics(),
        }
    finally:
        probe.close()
        bridge.close()
        if rclpy.ok():
            rclpy.shutdown()


def run_scene(simulation_app: object, args: argparse.Namespace, output_root: Path) -> dict[str, object]:
    import numpy as np
    import omni.usd
    from PIL import Image
    from pxr import Usd
    from isaacsim.core.api import World
    from isaacsim.core.prims import SingleArticulation
    from isaacsim.core.utils.types import ArticulationAction
    from isaacsim.core.utils.viewports import set_camera_view
    from isaacsim.sensors.camera import Camera

    from isaac_sim.scene2_builder import ARTICULATION_ROOT, SCENE2_STAGE, Scene2Builder, stage_manifest

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
    articulation = world.scene.add(SingleArticulation(ARTICULATION_ROOT, name="fanuc_m10id12"))
    world.reset()
    controller = articulation.get_articulation_controller()
    dof_names = tuple(str(name) for name in articulation.dof_names)
    if dof_names != ("J1", "J2", "J3", "J4", "J5", "J6"):
        raise RuntimeError(f"Unexpected FANUC DOF order: {dof_names}")

    lower = np.asarray(articulation.dof_properties["lower"], dtype=float)
    upper = np.asarray(articulation.dof_properties["upper"], dtype=float)
    poses = (
        np.array([0.00, 1.20, 0.40, 0.00, -0.77, 0.00], dtype=np.float32),
        np.array([0.25, 1.10, 0.35, 0.12, -0.75, -0.18], dtype=np.float32),
        np.array([-0.65, 1.00, 0.30, -0.16, -0.82, 0.25], dtype=np.float32),
    )
    for pose in poses:
        if np.any(pose <= lower) or np.any(pose >= upper):
            raise RuntimeError("The demonstration pose exceeds an imported FANUC joint limit")

    physics_steps = 0
    max_velocity = np.zeros(6, dtype=float)
    max_acceleration = np.zeros(6, dtype=float)
    previous_command = np.asarray(articulation.get_joint_positions(), dtype=float)
    previous_velocity = np.zeros(6, dtype=float)
    limit_violations = 0
    motion_segments = 0
    controller.apply_action(ArticulationAction(joint_positions=poses[0]))
    for _ in range(120):
        world.step(render=False)
        physics_steps += 1
    previous_command = np.asarray(articulation.get_joint_positions(), dtype=float)
    previous_velocity = np.zeros(6, dtype=float)

    targets = list(poses[1:]) + [poses[0]]
    for _ in range(args.motion_cycles):
        for target in targets:
            start = np.asarray(articulation.get_joint_positions(), dtype=float)
            previous_command = start.copy()
            previous_velocity = np.zeros(6, dtype=float)
            segment_steps = 360
            for step in range(1, segment_steps + 1):
                phase = step / segment_steps
                blend = 0.5 - 0.5 * math.cos(math.pi * phase)
                command = start + (target - start) * blend
                velocity = (command - previous_command) * 240.0
                acceleration = (velocity - previous_velocity) * 240.0
                max_velocity = np.maximum(max_velocity, np.abs(velocity))
                max_acceleration = np.maximum(max_acceleration, np.abs(acceleration))
                if np.any(command < lower - 1e-6) or np.any(command > upper + 1e-6):
                    limit_violations += 1
                controller.apply_action(ArticulationAction(joint_positions=command.astype(np.float32)))
                world.step(render=(step % 4 == 0))
                physics_steps += 1
                previous_command = command
                previous_velocity = velocity
            motion_segments += 1

    ros2_metrics: dict[str, object] | None = None
    if args.ros2:
        overhead_camera = Camera(
            build["camera_path"],
            name="scene2_overhead_ros_camera",
            resolution=(640, 480),
            frequency=15,
        )
        overhead_camera.initialize()
        overhead_camera.add_distance_to_image_plane_to_frame()
        for _ in range(24):
            world.step(render=True)
            physics_steps += 1
        if args.ros2_self_test:
            ros2_metrics = _run_ros2_gate(
                world, articulation, controller, overhead_camera, lower, upper
            )
            physics_steps += 720
            if not ros2_metrics["passed"]:
                raise RuntimeError(f"Scene 2.0 ROS 2 gate failed: {ros2_metrics}")

    set_camera_view(
        eye=[3.05, -1.92, 2.55],
        target=[0.0, 0.0, 1.05],
        camera_prim_path=build["presentation_camera_path"],
    )
    camera = Camera(
        build["presentation_camera_path"],
        name="scene2_presentation_camera",
        resolution=(1280, 720),
        frequency=60,
    )
    camera.initialize()
    camera.add_distance_to_image_plane_to_frame()
    for _ in range(24):
        world.render()
    closeup_rgb = camera.get_rgb()
    if closeup_rgb is None:
        raise RuntimeError("The presentation camera did not publish the robot close-up")
    closeup_rgb8 = _as_uint8(closeup_rgb)
    closeup_path = output_root / "scene2_fanuc_robot_closeup.png"
    Image.fromarray(closeup_rgb8[..., :3]).save(closeup_path)

    set_camera_view(
        eye=[5.25, -6.4, 4.2],
        target=[0.25, 0.0, 0.9],
        camera_prim_path=build["presentation_camera_path"],
    )
    for _ in range(18):
        world.render()
    rgb = camera.get_rgb()
    depth = camera.get_depth()
    if rgb is None or depth is None:
        raise RuntimeError("The presentation camera did not publish RGB and depth")
    rgb8 = _as_uint8(rgb)
    depth32 = np.asarray(depth, dtype=np.float32)
    screenshot = output_root / "scene2_fanuc_cell.png"
    depth_path = output_root / "scene2_fanuc_cell_depth.npy"
    Image.fromarray(rgb8[..., :3]).save(screenshot)
    np.save(depth_path, depth32)

    stage_path = output_root / SCENE2_STAGE.name
    stage.GetRootLayer().Export(str(stage_path))
    before = stage_manifest(stage)
    loaded = Usd.Stage.Open(str(stage_path))
    if loaded is None:
        raise RuntimeError("The saved Scene 2.0 USD could not be reloaded")
    after = stage_manifest(loaded)
    if before != after:
        raise RuntimeError("The stage manifest changed after deterministic save and reload")
    finite_depth = np.isfinite(depth32) & (depth32 > 0.0)
    nonempty_rgb = int(np.count_nonzero(np.any(rgb8[..., :3] != 0, axis=-1)))
    nonempty_depth = int(np.count_nonzero(finite_depth))
    if nonempty_rgb < 10000 or nonempty_depth < 10000:
        raise RuntimeError("The rendered RGBD evidence is unexpectedly sparse")
    measured = np.asarray(articulation.get_joint_positions(), dtype=float)
    payload: dict[str, object] = {
        "passed": limit_violations == 0,
        "scene": "2.0",
        "robot": "FANUC M-10iD/12 official description reference",
        "reference_notice": build["reference_notice"],
        "stage_path": str(stage_path),
        "stage_sha256": _file_sha256(stage_path),
        "stage_manifest": before,
        "dof_names": dof_names,
        "imported_joint_limits_rad": {name: [float(lo), float(hi)] for name, lo, hi in zip(dof_names, lower, upper, strict=True)},
        "final_joint_positions_rad": {name: float(value) for name, value in zip(dof_names, measured, strict=True)},
        "controller_motion_segments": motion_segments,
        "physics_steps": physics_steps,
        "physics_dt_seconds": 1.0 / 240.0,
        "max_command_velocity_rad_s": {name: float(value) for name, value in zip(dof_names, max_velocity, strict=True)},
        "max_command_acceleration_rad_s2": {name: float(value) for name, value in zip(dof_names, max_acceleration, strict=True)},
        "joint_limit_violations": limit_violations,
        "rgb_path": str(screenshot),
        "rgb_sha256": _file_sha256(screenshot),
        "robot_closeup_path": str(closeup_path),
        "robot_closeup_sha256": _file_sha256(closeup_path),
        "rgb_nonempty_pixels": nonempty_rgb,
        "depth_path": str(depth_path),
        "depth_sha256": _file_sha256(depth_path),
        "depth_finite_positive_pixels": nonempty_depth,
        "save_reload_manifest_match": before == after,
        "ros2": ros2_metrics,
    }
    metrics_path = output_root / "scene2_validation.json"
    metrics_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not args.headless and args.keep_open_seconds > 0.0:
        set_camera_view(
            eye=[3.05, -1.92, 2.55],
            target=[0.0, 0.0, 1.05],
            camera_prim_path="/OmniverseKit_Persp",
        )
        deadline = time.monotonic() + args.keep_open_seconds
        while simulation_app.is_running() and time.monotonic() < deadline:
            simulation_app.update()
            time.sleep(1.0 / 60.0)
    return payload


def main() -> int:
    args = parse_args()
    output_root = (PROJECT_ROOT / args.output_root).resolve()
    if Path(args.output_root).is_absolute() or not _inside_project(output_root):
        raise ValueError("Output root must be project-relative and inside the project")
    if args.keep_open_seconds < 0.0 or args.motion_cycles < 1:
        raise ValueError("Keep-open time must be nonnegative and motion cycles must be positive")
    if args.ros2_self_test and not args.ros2:
        raise ValueError("The ROS 2 self-test requires --ros2")
    simulation_app = None
    payload: dict[str, object] = {"passed": False}
    try:
        from isaacsim import SimulationApp

        simulation_app = SimulationApp(
            {
                "headless": args.headless,
                "renderer": "RaytracedLighting",
                "width": 1280,
                "height": 720,
                "anti_aliasing": 0,
            }
        )
        payload = run_scene(simulation_app, args, output_root)
    except Exception as exc:
        payload = {
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "scene2_failure.json").write_text(
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
