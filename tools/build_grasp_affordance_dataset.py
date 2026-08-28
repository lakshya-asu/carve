"""Build Solution C training rows from complete Scene 2 Isaac evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_artifact(metrics_path: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if PROJECT_ROOT not in path.parents:
        raise ValueError(f"Artifact is outside the project: {path}")
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Artifact is missing or empty for {metrics_path}: {path}")
    return path


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def validate_matched_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Require one executed row for every safe candidate in each reset group."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        group_id = str(row.get("trial_group_id", ""))
        if not group_id:
            raise ValueError("Every row requires a matched trial group ID")
        groups.setdefault(group_id, []).append(row)
    if len(groups) < 2:
        raise ValueError("Matched candidate data requires at least two reset groups")
    for group_id, group_rows in groups.items():
        indices = [int(row["candidate_index"]) for row in group_rows]
        if len(indices) != len(set(indices)):
            raise ValueError(f"Matched group {group_id} contains a duplicate candidate")
        if set(indices) != set(range(5)):
            raise ValueError(f"Matched group {group_id} must execute candidates 0 through 4")
        splits = {row["split"] for row in group_rows}
        if len(splits) != 1:
            raise ValueError(f"Matched group {group_id} crosses dataset splits")
        conditions = {json.dumps(row["trial_condition"], sort_keys=True) for row in group_rows}
        if len(conditions) != 1:
            raise ValueError(f"Matched group {group_id} changed conditions between candidates")
    return {
        "trial_group_count": len(groups),
        "candidate_indices": list(range(5)),
        "rows_per_group": 5,
    }


def build_row(metrics_path: Path, split: str) -> dict[str, Any]:
    payload = json.loads(metrics_path.read_text(encoding="utf-8-sig"))
    if payload.get("demo_kind") != "complete Scene 2 rendered YOLO26 to FANUC contact delivery":
        raise ValueError(f"Not complete Scene 2 evidence: {metrics_path}")
    if not str(payload.get("robot", "")).startswith("FANUC M-10iD/12"):
        raise ValueError(f"Missing FANUC execution evidence: {metrics_path}")
    proposal = payload["grasp"]["proposal"]
    settings = payload["test_settings"]
    candidate_index = settings.get("grasp_candidate_index")
    affordance = payload["grasp"]["affordance"]
    if candidate_index is None or affordance.get("mode") != "forced_geometry_candidate":
        raise ValueError(f"Not an executed matched-candidate trial: {metrics_path}")
    candidate_index = int(candidate_index)
    candidates = affordance.get("candidates", ())
    if len(candidates) != 5 or int(affordance.get("selected_rank", -1)) != candidate_index:
        raise ValueError(f"Candidate manifest is incomplete or inconsistent: {metrics_path}")
    if candidates[candidate_index]["proposal"]["proposal_id"] != proposal["proposal_id"]:
        raise ValueError(f"Executed proposal does not match the requested candidate: {metrics_path}")
    translation = proposal["grasp_in_product"]["translation"]
    features = {
        "local_x_abs_m": abs(float(translation["x_m"])),
        "local_y_abs_m": abs(float(translation["y_m"])),
        "boundary_clearance_m": float(proposal["boundary_clearance_m"]),
        "capture_margin_m": float(proposal["capture_margin_m"]),
        "estimated_width_m": float(proposal["estimated_width_m"]),
        "proposal_quality": float(proposal["quality"]),
        "proposal_confidence": float(proposal["confidence"]),
        "observation_confidence": float(payload["perception"]["confidence"]),
    }
    if tuple(features) != FEATURE_NAMES:
        raise ValueError("Dataset feature schema changed unexpectedly")

    grasp = payload["grasp"]
    lift_m = float(grasp.get("lift_distance_m") or 0.0)
    retention_m = float(grasp.get("maximum_product_to_tcp_distance_m") or 1.0)
    peak_forces = [float(value) for value in grasp.get("peak_contact_force_n", ())]
    maximum_force_n = max(peak_forces, default=0.0)
    delivery = payload["delivery"]
    measurement = delivery.get("measurement")
    if measurement:
        position_quality = _clamp(1.0 - float(measurement["position_error_m"]) / 0.055)
        yaw_quality = _clamp(1.0 - float(measurement["angle_error_rad"]) / 0.12217304763960307)
        delivery_quality = 0.5 * (position_quality + yaw_quality)
    else:
        delivery_quality = 0.0
    retained_quality = _clamp(lift_m / 0.10) * _clamp((0.13 - retention_m) / 0.06)
    outcomes = {
        "contact_probability": 1.0 if grasp.get("bilateral_contact") else 0.0,
        "retained_lift_probability": retained_quality,
        "slip_probability": 1.0 if payload.get("slip_detected") else 0.0,
        "excessive_contact_probability": 1.0 if maximum_force_n > 140.0 else 0.0,
        "delivery_probability": delivery_quality if delivery.get("delivered") else 0.0,
    }

    artifact_values = dict(payload["artifacts"])
    artifact_values["stage"] = payload["stage"]["path"]
    artifact_values["video"] = payload["recording"]["path"]
    required = ("rgb", "depth_npy", "segmentation", "trace", "trajectory", "stage", "video")
    artifact_paths = {name: _resolve_artifact(metrics_path, artifact_values[name]) for name in required}
    if not payload["stage"].get("reload_passed"):
        raise ValueError(f"Saved stage did not pass reload: {metrics_path}")
    motion = payload["motion"]
    if float(motion.get("maximum_physics_step_error_s", float("inf"))) > 1e-9:
        raise ValueError(f"Controller did not execute at measured 240 Hz: {metrics_path}")
    workpiece = payload.get("workpiece") or {}
    trial_condition = {
        "solution": payload["solution"],
        "seed": int(payload["seed"]),
        "scenario": payload["scenario"],
        "recipe_id": workpiece.get("recipe_id", "pork_boneless_loin"),
        "belt_speed_mps": float(payload["belt_speed_mps"]),
        "initial_pose": payload["initial_pose"],
        "perception_latency_ms": float(settings["perception_latency_ms"]),
        "position_noise_mm": float(settings["position_noise_mm"]),
        "yaw_noise_deg": float(settings["yaw_noise_deg"]),
        "interception_controller": settings["interception_controller"],
        "interception_perturbation": settings["interception_perturbation"],
    }
    trial_group_id = hashlib.sha256(
        json.dumps(trial_condition, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "schema_version": 1,
        "route": "solution_c",
        "source_kind": "complete_isaac_scene2_cycle",
        "split": split,
        "seed": int(payload["seed"]),
        "solution": payload["solution"],
        "scenario": payload["scenario"],
        "proposal_id": proposal["proposal_id"],
        "candidate_index": candidate_index,
        "trial_group_id": trial_group_id,
        "trial_condition": trial_condition,
        "features": features,
        "outcomes": outcomes,
        "raw_outcomes": {
            "bilateral_contact": bool(grasp.get("bilateral_contact")),
            "lift_distance_m": lift_m,
            "maximum_product_to_tcp_distance_m": retention_m,
            "slip_detected": bool(payload.get("slip_detected")),
            "maximum_contact_force_proxy_n": maximum_force_n,
            "excessive_contact_proxy_threshold_n": 140.0,
            "delivered": bool(delivery.get("delivered")),
            "delivery_measurement": measurement,
            "collision_violations": len(grasp.get("unexpected_contact_pairs", ())),
            "joint_limit_violations": int(motion["joint_limit_violations"]),
            "velocity_limit_violations": int(motion["velocity_limit_violations"]),
            "acceleration_limit_violations": int(motion["acceleration_limit_violations"]),
            "maximum_physics_step_error_s": float(motion["maximum_physics_step_error_s"]),
            "cycle_time_s": float(payload["recording"]["duration_s"]),
            "terminal_result": payload.get(
                "terminal_result",
                {
                    "terminal_path": "success" if delivery.get("delivered") else "recovered",
                    "reason": payload.get("terminal_reason", "historical_scene2_metrics"),
                    "state_sequence": payload.get("state_sequence", ()),
                },
            ),
        },
        "evidence": {
            "metrics": str(metrics_path.resolve()),
            "metrics_sha256": _sha256(metrics_path),
            "artifact_sha256": {name: _sha256(path) for name, path in artifact_paths.items()},
        },
        "claim_boundary": "Isaac Sim reference evidence only. Force and excessive-contact values are uncalibrated proxies.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output", default="results/solution_c/grasp_affordance_dataset.jsonl")
    parser.add_argument("--manifest", default="results/solution_c/grasp_affordance_split.json")
    parser.add_argument("--holdout-seed-min", type=int, default=4300)
    args = parser.parse_args()
    input_root = (PROJECT_ROOT / args.input_root).resolve()
    output = (PROJECT_ROOT / args.output).resolve()
    manifest_path = (PROJECT_ROOT / args.manifest).resolve()
    if PROJECT_ROOT not in input_root.parents or PROJECT_ROOT not in output.parents or PROJECT_ROOT not in manifest_path.parents:
        raise ValueError("Input and output paths must stay inside the project")
    metrics_files = sorted(input_root.rglob("scene2_integrated_metrics.json"))
    if not metrics_files:
        raise ValueError(f"No integrated metrics found under {input_root}")
    rows = [
        build_row(path, "held_out" if int(json.loads(path.read_text(encoding="utf-8-sig"))["seed"]) >= args.holdout_seed_min else "fit")
        for path in metrics_files
    ]
    matched = validate_matched_rows(rows)
    fit_seeds = sorted({row["seed"] for row in rows if row["split"] == "fit"})
    held_out_seeds = sorted({row["seed"] for row in rows if row["split"] == "held_out"})
    if not fit_seeds or not held_out_seeds or set(fit_seeds) & set(held_out_seeds):
        raise ValueError("Dataset requires disjoint nonempty fit and held-out seed sets")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "passed": True,
        "source_root": str(input_root),
        "dataset": str(output),
        "dataset_sha256": _sha256(output),
        "row_count": len(rows),
        "fit_rows": sum(row["split"] == "fit" for row in rows),
        "held_out_rows": sum(row["split"] == "held_out" for row in rows),
        "fit_seeds": fit_seeds,
        "held_out_seeds": held_out_seeds,
        **matched,
        "outcomes": [
            "bilateral contact",
            "retained lift",
            "slip",
            "excessive-contact proxy",
            "verified delivery",
        ],
        "claim_boundary": "All rows reference complete Isaac Scene 2 artifacts. This is not physical force or safety evidence.",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
