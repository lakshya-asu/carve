"""Fit the small multi-outcome Solution C candidate-ranking model."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FEATURE_NAMES = (
    "local_x_abs_m",
    "local_y_abs_m",
    "boundary_clearance_m",
    "capture_margin_m",
    "estimated_width_m",
    "proposal_quality",
    "proposal_confidence",
    "observation_confidence",
)
OUTCOME_NAMES = (
    "contact_probability",
    "retained_lift_probability",
    "slip_probability",
    "excessive_contact_probability",
    "delivery_probability",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [value] for row, value in zip(matrix, vector, strict=True)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("Ridge system is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(augmented[row], augmented[column], strict=True)
            ]
    return [augmented[row][-1] for row in range(size)]


def _fit_head(features: list[list[float]], targets: list[float], regularization: float) -> tuple[float, list[float]]:
    columns = len(features[0]) + 1
    design = [[1.0] + row for row in features]
    normal = [[0.0 for _ in range(columns)] for _ in range(columns)]
    rhs = [0.0 for _ in range(columns)]
    for row, target in zip(design, targets, strict=True):
        for left in range(columns):
            rhs[left] += row[left] * target
            for right in range(columns):
                normal[left][right] += row[left] * row[right]
    for index in range(1, columns):
        normal[index][index] += regularization
    parameters = _solve(normal, rhs)
    return parameters[0], parameters[1:]


def _predict(row: list[float], bias: float, weights: list[float]) -> float:
    return max(0.0, min(1.0, bias + sum(value * weight for value, weight in zip(row, weights, strict=True))))


def _metrics(rows: list[dict[str, Any]], normalized: list[list[float]], heads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"row_count": len(rows), "heads": {}}
    for outcome in OUTCOME_NAMES:
        errors = []
        predictions = []
        for row, features in zip(rows, normalized, strict=True):
            prediction = _predict(features, heads[outcome]["bias"], heads[outcome]["weights"])
            target = float(row["outcomes"][outcome])
            predictions.append(prediction)
            errors.append((prediction - target) ** 2)
        result["heads"][outcome] = {
            "rmse": math.sqrt(sum(errors) / len(errors)),
            "prediction_min": min(predictions),
            "prediction_max": max(predictions),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="results/solution_c/grasp_affordance_dataset.jsonl")
    parser.add_argument("--model", default="models/grasp_affordance_v1/model.json")
    parser.add_argument("--summary", default="results/solution_c/training_summary.json")
    parser.add_argument("--regularization", type=float, default=2.0)
    args = parser.parse_args()
    dataset_path = (PROJECT_ROOT / args.dataset).resolve()
    model_path = (PROJECT_ROOT / args.model).resolve()
    summary_path = (PROJECT_ROOT / args.summary).resolve()
    if any(PROJECT_ROOT not in path.parents for path in (dataset_path, model_path, summary_path)):
        raise ValueError("Training paths must stay inside the project")
    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    fit_rows = [row for row in rows if row["split"] == "fit"]
    held_out_rows = [row for row in rows if row["split"] == "held_out"]
    if len(fit_rows) < len(FEATURE_NAMES) + 1 or not held_out_rows:
        raise ValueError("Training requires at least nine fit rows and one held-out row")
    if {row["seed"] for row in fit_rows} & {row["seed"] for row in held_out_rows}:
        raise ValueError("Fit and held-out seeds overlap")
    feature_columns = [[float(row["features"][name]) for name in FEATURE_NAMES] for row in fit_rows]
    means = [sum(row[index] for row in feature_columns) / len(feature_columns) for index in range(len(FEATURE_NAMES))]
    scales = []
    for index, mean in enumerate(means):
        variance = sum((row[index] - mean) ** 2 for row in feature_columns) / len(feature_columns)
        scales.append(max(math.sqrt(variance), 1e-6))

    def normalize(source_rows: list[dict[str, Any]]) -> list[list[float]]:
        return [
            [
                (float(row["features"][name]) - mean) / scale
                for name, mean, scale in zip(FEATURE_NAMES, means, scales, strict=True)
            ]
            for row in source_rows
        ]

    normalized_fit = normalize(fit_rows)
    heads: dict[str, dict[str, Any]] = {}
    for outcome in OUTCOME_NAMES:
        bias, weights = _fit_head(
            normalized_fit,
            [float(row["outcomes"][outcome]) for row in fit_rows],
            args.regularization,
        )
        heads[outcome] = {"bias": bias, "weights": weights}
    document = {
        "schema_version": 1,
        "model_family": "carve_grasp_affordance_ridge_v1",
        "feature_names": list(FEATURE_NAMES),
        "outcome_names": list(OUTCOME_NAMES),
        "normalization": {"mean": means, "scale": scales},
        "heads": heads,
        "training": {
            "method": "multi-output L2-regularized linear outcome regression",
            "regularization": args.regularization,
            "dataset": str(dataset_path),
            "dataset_sha256": _sha256(dataset_path),
            "fit_seeds": sorted({row["seed"] for row in fit_rows}),
            "held_out_seeds": sorted({row["seed"] for row in held_out_rows}),
            "data_source": "complete Isaac Sim Scene 2 cycles with rendered RGBD, articulation, PhysX contact, PLC, and delivery evidence",
            "claim_boundary": "Simulator outcome model only. Contact force and excessive-contact targets are uncalibrated proxies.",
        },
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "schema_version": 1,
        "passed": True,
        "model": str(model_path),
        "model_sha256": _sha256(model_path),
        "dataset_sha256": _sha256(dataset_path),
        "fit": _metrics(fit_rows, normalized_fit, heads),
        "held_out": _metrics(held_out_rows, normalize(held_out_rows), heads),
        "fit_seeds": document["training"]["fit_seeds"],
        "held_out_seeds": document["training"]["held_out_seeds"],
        "claim_boundary": document["training"]["claim_boundary"],
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
