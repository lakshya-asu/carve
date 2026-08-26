"""Headless Isaac startup, stage, physics, articulation, sensor, and perception gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(PROJECT_ROOT / "results" / "setup_validation.json"))
    parser.add_argument("--stage", default=str(PROJECT_ROOT / "results" / "isaac_cell_validation.usda"))
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {"schema_version": 1, "passed": False, "checks": {}}
    simulation_app = None
    adapter = None
    try:
        from isaacsim import SimulationApp

        simulation_app = SimulationApp(
            {
                "headless": args.headless,
                "renderer": "RaytracedLighting",
                "width": 640,
                "height": 480,
                "anti_aliasing": 0,
            }
        )
        from isaac_sim.adapter import IsaacSimulatorAdapter
        from isaac_sim.adapter_config import IsaacCellPaths
        from isaac_sim.perception_adapter import RenderedColorDepthSegmentationModel
        from meatcell.perception import PinholeCalibration
        from meatcell.ports import RobotCommand

        adapter = IsaacSimulatorAdapter(simulation_app, physics_hz=240, render_hz=60)
        adapter.create_cell("a")
        paths = IsaacCellPaths()
        prims = set(adapter.prim_paths())
        missing = sorted(set(paths.required_for_solution("a")) - prims)
        report["checks"]["stage_contents"] = {"passed": not missing, "missing": missing, "prim_count": len(prims)}

        before_signature = adapter.save_stage(args.stage)
        reload_signature = adapter.reload_stage(args.stage)
        report["checks"]["stage_save_reload"] = {
            "passed": before_signature == reload_signature,
            "before_sha256": before_signature,
            "reload_sha256": reload_signature,
            "stage": str(Path(args.stage).resolve()),
        }

        start_world_time = float(adapter.world.current_time)
        for _ in range(240):
            adapter.step_once()
        end_world_time = float(adapter.world.current_time)
        elapsed_world = end_world_time - start_world_time
        report["checks"]["fixed_step_clock"] = {
            "passed": abs(adapter.simulation_time.seconds - 1.0) < 1e-12 and abs(elapsed_world - 1.0) <= 1.0 / 240.0,
            "domain_steps": adapter.clock.step_index,
            "domain_time_s": adapter.simulation_time.seconds,
            "isaac_elapsed_s": elapsed_world,
            "physics_hz": 240,
        }

        names = adapter.joint_names
        current = adapter.read_robot_state()
        targets = list(current.positions)
        targets[names.index("x_axis")] = 0.05
        command = RobotCommand(
            adapter.simulation_time,
            names,
            tuple(targets),
            tuple(2.0 for _ in names),
            tuple(20.0 for _ in names),
        )
        adapter.command_robot(command)
        for _ in range(120):
            adapter.step_once()
        controlled = adapter.read_robot_state()
        x_position = controlled.positions[names.index("x_axis")]
        report["checks"]["articulation_controller"] = {
            "passed": controlled.controller_ok and abs(x_position - 0.05) < 0.01,
            "joint_names": names,
            "x_target_m": 0.05,
            "x_actual_m": x_position,
            "joint_limit_violations": controlled.joint_limit_violation_count,
        }

        media = PROJECT_ROOT / "results" / "validation_media"
        sample = adapter.capture_rgbd("overhead", str(media))
        rgb, depth, _ = adapter.camera_arrays("overhead")
        calibration = PinholeCalibration(
            camera_x_world_m=1.0,
            camera_y_world_m=0.0,
            camera_z_world_m=3.0,
            fx_px=18.0 / 20.955 * sample.width_px,
            fy_px=18.0 / 20.955 * sample.width_px,
            cx_px=sample.width_px / 2.0,
            cy_px=sample.height_px / 2.0,
            belt_surface_z_world_m=0.04,
            calibration_position_sigma_m=0.002,
            calibration_yaw_sigma_rad=0.004,
        )
        model = RenderedColorDepthSegmentationModel(
            seed=7,
            latency_sigma_s=0.0,
            timestamp_jitter_sigma_s=0.0,
            position_noise_sigma_m=0.0,
            yaw_noise_sigma_rad=0.0,
        )
        observations = model.infer(rgb, depth, adapter.simulation_time, calibration)
        report["checks"]["rgb_depth_sensor"] = {
            "passed": sample.valid_rgb_pixels > 0 and sample.valid_depth_pixels > 0,
            "width_px": sample.width_px,
            "height_px": sample.height_px,
            "rgb_sha256": sample.rgb_sha256,
            "depth_sha256": sample.depth_sha256,
            "rgb_path": sample.rgb_path,
            "depth_path": sample.depth_path,
            "valid_rgb_pixels": sample.valid_rgb_pixels,
            "valid_depth_pixels": sample.valid_depth_pixels,
        }
        report["checks"]["rendered_perception"] = {
            "passed": len(observations) > 0,
            "model": model.model_name,
            "ground_truth_used_as_primary": False,
            "observation_count": len(observations),
            "observations": [item.to_dict() for item in observations],
        }
        report["isaac_sim_version"] = "6.0.1"
        report["reference_asset_notice"] = (
            "Robot, gripper, workpiece, cutter, and buffer are abstract reference models. "
            "They are not OEM accurate or physically calibrated."
        )
        report["passed"] = all(bool(item["passed"]) for item in report["checks"].values())
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
    finally:
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True), flush=True)
        if adapter is not None:
            adapter.close()
        if simulation_app is not None:
            simulation_app.close()
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
