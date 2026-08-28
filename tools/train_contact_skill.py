"""Fit a small ridge behavior-cloning model for Route E shadow proposals."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from meatcell.contact_skill import FEATURE_ORDER


PHASE_SPECS = {
    "close": (0.30, 0.40, "s", ["intercept"]),
    "stabilize": (0.35, 0.55, "s", ["verify_grasp"]),
    "slip_correction": (0.0, 0.002, "m", ["settle", "reobserve_buffer"]),
    "reorientation": (0.90, 1.10, "scale", ["transfer_direct", "feed_buffer"]),
    "release": (0.60, 0.70, "s", ["align_direct", "feed_buffer"]),
}


def _features(row: dict) -> list[float]:
    values = row["features"]
    return [
        1.0,
        float(values["solution_b"]),
        float(values["abs_yaw_rad"]),
        float(values["product_width_m"]),
        float(values["contact_force_imbalance"]),
        float(values["slip_flag"]),
    ]


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    augmented = [row[:] + [value] for row, value in zip(matrix, vector, strict=True)]
    size = len(vector)
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        if abs(divisor) < 1e-12:
            raise RuntimeError("Contact-skill normal matrix is singular")
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(augmented[row], augmented[column], strict=True)
            ]
    return [augmented[index][-1] for index in range(size)]


def _fit(rows: list[dict], ridge: float) -> list[float]:
    size = len(FEATURE_ORDER)
    matrix = [[0.0] * size for _ in range(size)]
    vector = [0.0] * size
    for row in rows:
        features = _features(row)
        target = float(row["target"])
        for left in range(size):
            vector[left] += features[left] * target
            for right in range(size):
                matrix[left][right] += features[left] * features[right]
    for index in range(1, size):
        matrix[index][index] += ridge
    matrix[0][0] += ridge * 1e-3
    return _solve(matrix, vector)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset")
    parser.add_argument("--output", required=True)
    parser.add_argument("--ridge", type=float, default=0.01)
    args = parser.parse_args()
    dataset = Path(args.dataset).resolve()
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    phases = {}
    for phase, (minimum, maximum, unit, states) in PHASE_SPECS.items():
        fit_rows = [row for row in rows if row["phase"] == phase and row["split"] == "fit"]
        held_out = [row for row in rows if row["phase"] == phase and row["split"] == "held_out"]
        if not fit_rows or not held_out:
            raise RuntimeError(f"Phase {phase} is missing fit or held-out rows")
        weights = _fit(fit_rows, args.ridge)
        errors = [abs(sum(w * x for w, x in zip(weights, _features(row), strict=True)) - float(row["target"])) for row in held_out]
        mae = sum(errors) / len(errors)
        phases[phase] = {
            "weights": weights,
            "minimum": minimum,
            "maximum": maximum,
            "unit": unit,
            "held_out_mae": mae,
            "held_out_max_error": max(errors),
            "allowed_states": states,
            "fit_rows": len(fit_rows),
            "held_out_rows": len(held_out),
        }
    payload = {
        "schema_version": 1,
        "model_family": "ridge_behavior_clone_shadow_v1",
        "execution_policy": "shadow_only",
        "feature_order": list(FEATURE_ORDER),
        "dataset": str(dataset),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "ridge": args.ridge,
        "phases": phases,
        "physical_data_blocker": "No representative real force, tactile, slip, tissue-damage, or recovery data.",
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "passed": all(math.isfinite(spec["held_out_mae"]) and spec["held_out_mae"] <= 0.05 for spec in phases.values()),
        "model": str(output),
        "model_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "phases": phases,
    }
    output.with_name("training_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
