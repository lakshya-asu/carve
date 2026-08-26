"""Command line entry point for the integrated Isaac cell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time
import traceback


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", choices=("a", "b"), required=True)
    parser.add_argument("--cycles", type=int, default=4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--scenario-profile", choices=("baseline", "hardening"), default="baseline")
    parser.add_argument(
        "--output-root",
        default="results",
        help="Project-relative result root. Absolute paths and paths outside the project are rejected.",
    )
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--vision-model", choices=("color", "yolo26"), default="color")
    parser.add_argument(
        "--recipe",
        default="beef_center_cut_tenderloin",
        help="Product recipe ID from configs/product_recipes.yaml.",
    )
    parser.add_argument("--yolo-weights", default="models/yolo26_meat_reference/weights/best.pt")
    parser.add_argument("--keep-open-seconds", type=float, default=0.0)
    parser.add_argument("--record-video", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--record-fps", type=int, default=12)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    simulation_app = None
    payload: dict[str, object] = {"passed": False, "solution": args.solution, "recipe_id": args.recipe}
    output_root = (PROJECT_ROOT / args.output_root).resolve()
    if Path(args.output_root).is_absolute() or PROJECT_ROOT not in output_root.parents:
        raise ValueError("Output root must be a project-relative path inside the project")
    if not re.fullmatch(r"[A-Za-z0-9_./\\-]+", args.output_root):
        raise ValueError("Output root contains unsupported characters")
    yolo_weights = (PROJECT_ROOT / args.yolo_weights).resolve()
    if Path(args.yolo_weights).is_absolute() or PROJECT_ROOT not in yolo_weights.parents:
        raise ValueError("YOLO weights must be a project-relative path inside the project")
    if args.keep_open_seconds < 0.0:
        raise ValueError("Keep-open time must be nonnegative")
    if args.record_fps <= 0 or 240 % args.record_fps != 0:
        raise ValueError("Record FPS must be positive and divide the 240 Hz physics rate")
    try:
        from meatcell.product_profiles import load_product_catalog

        product_profile = load_product_catalog().get(args.recipe)
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
        from isaac_sim.cell_runner import run_solution

        payload = run_solution(
            simulation_app,
            solution=args.solution,
            cycles=args.cycles,
            seed=args.seed,
            project_root=PROJECT_ROOT,
            output_root=output_root,
            scenario_profile=args.scenario_profile,
            vision_model_backend=args.vision_model,
            yolo_weights=yolo_weights,
            record_video=args.record_video,
            record_fps=args.record_fps,
            product_profile=product_profile,
        )
        if not args.headless and args.keep_open_seconds > 0.0:
            deadline = time.monotonic() + args.keep_open_seconds
            while simulation_app.is_running() and time.monotonic() < deadline:
                simulation_app.update()
                time.sleep(1.0 / 60.0)
    except Exception as exc:
        payload = {
            "passed": False,
            "solution": args.solution,
            "recipe_id": args.recipe,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        failure_path = output_root / f"isaac_{args.solution}" / "failure.json"
        failure_path.parent.mkdir(parents=True, exist_ok=True)
        failure_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
