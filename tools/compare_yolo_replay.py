"""Compare two Isaac vision datasets using explicit deterministic replay gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def dataset_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    if PROJECT_ROOT not in path.parents:
        raise ValueError("Replay dataset must be inside the project")
    return path


def main() -> int:
    import numpy as np
    from PIL import Image

    parser = argparse.ArgumentParser()
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--output")
    parser.add_argument("--rgb-mean-abs-max", type=float, default=1.5)
    parser.add_argument("--rgb-p99-abs-max", type=float, default=8.0)
    parser.add_argument("--depth-p99-abs-m", type=float, default=1e-5)
    parser.add_argument("--depth-outlier-fraction-max", type=float, default=1e-4)
    args = parser.parse_args()
    left = dataset_path(args.left)
    right = dataset_path(args.right)
    output = Path(args.output).resolve() if args.output else right / "replay_comparison.json"
    left_records = [json.loads(line) for line in (left / "frames.jsonl").read_text(encoding="utf-8").splitlines()]
    right_records = [json.loads(line) for line in (right / "frames.jsonl").read_text(encoding="utf-8").splitlines()]
    errors: list[str] = []
    rgb_differences = []
    depth_differences = []
    mask_mismatch_pixels = 0
    label_mismatches = 0
    exact_fields = (
        "frame_id",
        "scene_id",
        "scene_seed",
        "scene_frame_index",
        "split",
        "recipe_id",
        "zone",
        "negative",
        "configured_instance_count",
        "sim_time_ns",
        "configured_products",
    )
    if len(left_records) != len(right_records):
        errors.append("Frame counts differ")
    for index, (left_record, right_record) in enumerate(zip(left_records, right_records)):
        if any(left_record[field] != right_record[field] for field in exact_fields):
            errors.append(f"Exact manifest field mismatch at frame {index}")
        left_rgb = np.asarray(Image.open(left / left_record["files"]["image"]), dtype=np.int16)
        right_rgb = np.asarray(Image.open(right / right_record["files"]["image"]), dtype=np.int16)
        rgb_differences.append(np.abs(left_rgb - right_rgb).reshape(-1))
        left_mask = np.asarray(Image.open(left / left_record["files"]["mask"]))
        right_mask = np.asarray(Image.open(right / right_record["files"]["mask"]))
        mask_mismatch_pixels += int(np.count_nonzero(left_mask != right_mask))
        left_depth = np.load(left / left_record["files"]["depth"])["depth_m"]
        right_depth = np.load(right / right_record["files"]["depth"])["depth_m"]
        depth_differences.append(np.abs(left_depth - right_depth).reshape(-1))
        left_label = (left / left_record["files"]["label"]).read_text(encoding="utf-8")
        right_label = (right / right_record["files"]["label"]).read_text(encoding="utf-8")
        label_mismatches += int(left_label != right_label)
    rgb_all = np.concatenate(rgb_differences) if rgb_differences else np.zeros(1, dtype=np.int16)
    depth_all = np.concatenate(depth_differences) if depth_differences else np.zeros(1, dtype=np.float32)
    rgb_mean = float(rgb_all.mean())
    rgb_p99 = float(np.percentile(rgb_all, 99.0))
    depth_p99 = float(np.percentile(depth_all, 99.0))
    depth_outlier_fraction = float(np.mean(depth_all > 0.001))
    gates = {
        "frame_count_exact": len(left_records) == len(right_records),
        "manifest_and_sim_time_exact": not any("manifest" in error for error in errors),
        "mask_pixels_exact": mask_mismatch_pixels == 0,
        "yolo_labels_exact": label_mismatches == 0,
        "depth_p99_abs_within_tolerance": depth_p99 <= args.depth_p99_abs_m,
        "depth_outlier_fraction_within_tolerance": depth_outlier_fraction <= args.depth_outlier_fraction_max,
        "rgb_mean_abs_within_tolerance": rgb_mean <= args.rgb_mean_abs_max,
        "rgb_p99_abs_within_tolerance": rgb_p99 <= args.rgb_p99_abs_max,
    }
    payload = {
        "schema_version": 1,
        "passed": all(gates.values()) and not errors,
        "left": str(left),
        "right": str(right),
        "frames": min(len(left_records), len(right_records)),
        "gates": gates,
        "metrics": {
            "mask_mismatch_pixels": mask_mismatch_pixels,
            "label_mismatched_frames": label_mismatches,
            "depth_max_abs_m": float(depth_all.max()),
            "depth_p99_abs_m": depth_p99,
            "depth_fraction_over_1mm": depth_outlier_fraction,
            "rgb_mean_abs_8bit": rgb_mean,
            "rgb_p99_abs_8bit": rgb_p99,
        },
        "errors": errors,
        "note": "RTX RGB and depth edges are tolerance gated because process level rendering is not bit exact. Physics time, masks, and labels remain strict.",
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
