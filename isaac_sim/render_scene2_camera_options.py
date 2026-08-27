"""Render candidate presentation-camera views for the Scene 2 FANUC cell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


CAMERA_OPTIONS = {
    "cell_story_clear": {
        "eye": (3.65, -2.20, 2.40),
        "target": (0.30, 0.00, 0.86),
        "focal_length_mm": 18.0,
        "purpose": "Show robot, conveyor, product, gripper, and cutter entrance without guard occlusion.",
    },
    "operator_three_quarter": {
        "eye": (3.45, -3.10, 2.55),
        "target": (0.10, -0.05, 0.92),
        "focal_length_mm": 24.0,
        "purpose": "Show the arm, belt approach, gripper, and cutter tray in one readable frame.",
    },
    "process_side": {
        "eye": (1.20, -3.55, 2.15),
        "target": (0.00, 0.05, 0.88),
        "focal_length_mm": 24.0,
        "purpose": "Make product travel from conveyor to downstream tray easy to follow.",
    },
    "robot_task_close": {
        "eye": (3.00, -2.15, 2.20),
        "target": (-0.12, -0.02, 0.98),
        "focal_length_mm": 24.0,
        "purpose": "Show arm posture, end effector, and compliant jaws clearly.",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="results/scene2_camera_options")
    return parser.parse_args()


def _inside_project(path: Path) -> bool:
    return path == PROJECT_ROOT or PROJECT_ROOT in path.parents


def _as_uint8(image: object) -> object:
    import numpy as np

    array = np.asarray(image)
    if array.dtype == np.uint8:
        return array
    multiplier = 255.0 if float(array.max(initial=0.0)) <= 1.0 else 1.0
    return np.clip(array * multiplier, 0, 255).astype(np.uint8)


def render_options(simulation_app: object, output_root: Path) -> dict[str, object]:
    import numpy as np
    import omni.usd
    from PIL import Image
    from isaacsim.core.api import World
    from isaacsim.core.prims import SingleArticulation
    from isaacsim.core.utils.types import ArticulationAction
    from isaacsim.core.utils.viewports import set_camera_view
    from isaacsim.sensors.camera import Camera

    from isaac_sim.scene2_builder import ARTICULATION_ROOT, Scene2Builder

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
    articulation = world.scene.add(SingleArticulation(ARTICULATION_ROOT, name="fanuc_camera_preview"))
    world.reset()
    controller = articulation.get_articulation_controller()
    robot_indices = np.arange(6, dtype=np.int32)
    preview_pose = np.array([-0.82, 0.92, 0.28, -0.12, -0.78, 0.18], dtype=np.float32)
    controller.apply_action(ArticulationAction(joint_positions=preview_pose, joint_indices=robot_indices))
    for step in range(180):
        world.step(render=(step % 4 == 0))

    camera = Camera(
        build["presentation_camera_path"],
        name="scene2_camera_options",
        resolution=(1280, 720),
        frequency=60,
    )
    camera.initialize()
    outputs = []
    for name, option in CAMERA_OPTIONS.items():
        camera.prim.GetAttribute("focalLength").Set(float(option["focal_length_mm"]))
        set_camera_view(
            eye=list(option["eye"]),
            target=list(option["target"]),
            camera_prim_path=build["presentation_camera_path"],
        )
        for _ in range(24):
            world.render()
        rgb = camera.get_rgb()
        if rgb is None:
            raise RuntimeError(f"Presentation camera did not publish view {name}")
        image = _as_uint8(rgb)
        path = output_root / f"{name}.png"
        Image.fromarray(image[..., :3]).save(path)
        outputs.append(
            {
                "name": name,
                "path": str(path),
                "eye": option["eye"],
                "target": option["target"],
                "focal_length_mm": option["focal_length_mm"],
                "purpose": option["purpose"],
                "file_bytes": path.stat().st_size,
            }
        )
    payload = {
        "passed": len(outputs) == len(CAMERA_OPTIONS) and all(item["file_bytes"] > 10000 for item in outputs),
        "robot": "FANUC M-10iD/12 official description reference",
        "reference_notice": build["reference_notice"],
        "views": outputs,
    }
    (output_root / "camera_options.json").write_text(
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
        payload = render_options(simulation_app, output_root)
    except Exception as exc:
        payload = {
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "camera_options_failure.json").write_text(
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
