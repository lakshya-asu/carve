"""Validate and summarize paired S0 through S4 full-cell evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from meatcell.experiment_matrix import validate_manifest, write_json


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _artifact(path_value: Any) -> dict[str, Any]:
    path = Path(str(path_value))
    return {"path": str(path), "exists": path.is_file(), "bytes": path.stat().st_size if path.is_file() else 0}


def _extract(payload: Mapping[str, Any], case: Mapping[str, Any], model_hashes: Mapping[str, Any]) -> dict[str, Any]:
    test_settings = payload["test_settings"]
    affordance = payload["grasp"]["affordance"]
    reactive = payload["reactive_interception"]
    measurement = payload["delivery"].get("measurement") or {}
    artifacts = {
        "rgb": _artifact(payload["artifacts"]["rgb"]),
        "depth": _artifact(payload["artifacts"]["depth_npy"]),
        "segmentation": _artifact(payload["artifacts"]["segmentation"]),
        "trajectory": _artifact(payload["artifacts"]["trajectory"]),
        "trace": _artifact(payload["artifacts"]["trace"]),
        "video": _artifact(payload["recording"]["path"]),
        "usd": _artifact(payload["stage"]["path"]),
    }
    config_matches = bool(
        payload["solution"] == case["flow"]
        and int(payload["seed"]) == int(case["seed"])
        and test_settings["grasp_selector"] == case["grasp_selector"]
        and test_settings["interception_controller"] == case["interception_controller"]
        and test_settings["interception_perturbation"] == case["interception_perturbation"]
    )
    model_matches = bool(payload["perception"]["checkpoint_sha256"] == model_hashes.get("yolo26"))
    learned_active = case["grasp_selector"] == "learned"
    if learned_active:
        model_matches = bool(
            model_matches
            and affordance["mode"] == "learned"
            and not affordance["fallback_used"]
            and affordance["model_sha256"] == model_hashes.get("grasp_affordance")
        )
    safety_passed = bool(
        len(payload["grasp"]["unexpected_contact_pairs"]) == 0
        and int(payload["motion"]["joint_limit_violations"]) == 0
        and int(payload["motion"]["velocity_limit_violations"]) == 0
        and int(payload["motion"]["acceleration_limit_violations"]) == 0
    )
    artifact_passed = all(item["exists"] and item["bytes"] > 0 for item in artifacts.values())
    reactive_exercised = bool(
        case["interception_controller"] != "reactive"
        or case["interception_perturbation"] == "none"
        or len(reactive["updates"]) > 0
    )
    gate_passed = bool(payload["passed"] and config_matches and model_matches and safety_passed and artifact_passed and reactive_exercised)
    return {
        "gate_passed": gate_passed,
        "simulator_passed": bool(payload["passed"]),
        "config_matches": config_matches,
        "model_hashes_match": model_matches,
        "safety_passed": safety_passed,
        "artifacts_passed": artifact_passed,
        "reactive_exercised": reactive_exercised,
        "delivered": bool(payload["delivery"]["delivered"]),
        "grasp_confirmed": bool(payload["grasp"]["bilateral_contact"]),
        "retained_lift": float(payload["grasp"]["lift_distance_m"]) >= 0.10,
        "slip_detected": bool(payload["slip_detected"]),
        "intercept_position_error_m": float(payload["interception"]["grasp_position_error_m"]),
        "intercept_timing_error_s": float(payload["interception"]["timing_error_s"]),
        "delivery_position_error_m": measurement.get("position_error_m"),
        "delivery_yaw_error_rad": measurement.get("angle_error_rad"),
        "cycle_time_s": float(payload["recording"]["duration_s"]),
        "applied_updates": int(reactive["applied_update_count"]),
        "rejected_updates": int(reactive["rejected_update_count"]),
        "minimum_precontact_clearance_m": float(payload["motion"]["minimum_precontact_pad_clearance_m"]),
        "artifacts": artifacts,
    }


def summarize(root: Path) -> dict[str, Any]:
    manifest_path = root / "experiment_manifest.json"
    manifest = _read(manifest_path)
    validate_manifest(manifest)
    results: dict[str, Any] = {}
    missing_required: list[str] = []
    for case in manifest["cases"]:
        identifier = case["case_id"]
        metrics_path = root / case["result_directory"] / "scene2_integrated_metrics.json"
        if not metrics_path.exists():
            status = "not_run" if not case["required_for_gate"] else "blocked"
            results[identifier] = {"status": status, "gate_passed": False, "metrics": str(metrics_path)}
            if case["required_for_gate"]:
                missing_required.append(identifier)
            continue
        payload = _read(metrics_path)
        if not payload.get("passed", False) and "test_settings" not in payload:
            results[identifier] = {
                "status": "failed",
                "gate_passed": False,
                "simulator_passed": False,
                "metrics": str(metrics_path),
                "error": payload.get("error", "incomplete failure evidence"),
            }
            continue
        extracted = _extract(payload, case, manifest["model_hashes"])
        results[identifier] = {"status": "passed" if extracted["gate_passed"] else "failed", "metrics": str(metrics_path), **extracted}

    comparisons: dict[str, Any] = {}
    grouped: dict[tuple[str, int], dict[str, Any]] = {}
    for case in manifest["cases"]:
        result = results[case["case_id"]]
        if result["status"] != "passed":
            continue
        grouped.setdefault((case["flow"], int(case["seed"])), {})[case["stack_id"]] = result
    for (flow, seed), stacks in grouped.items():
        baseline = stacks.get("S0")
        if baseline is None:
            continue
        for stack_id, candidate in stacks.items():
            if stack_id == "S0":
                continue
            comparisons[f"{flow}_seed{seed}_{stack_id.lower()}_vs_s0"] = {
                "delivery_success_delta": int(candidate["delivered"]) - int(baseline["delivered"]),
                "intercept_position_improvement_m": baseline["intercept_position_error_m"] - candidate["intercept_position_error_m"],
                "intercept_timing_improvement_s": baseline["intercept_timing_error_s"] - candidate["intercept_timing_error_s"],
                "cycle_time_delta_s": candidate["cycle_time_s"] - baseline["cycle_time_s"],
            }
    required = [case["case_id"] for case in manifest["cases"] if case["required_for_gate"]]
    gate_passed = bool(not missing_required and required and all(results[name]["gate_passed"] for name in required))
    return {
        "schema_version": 1,
        "experiment_id": manifest["experiment_id"],
        "passed": gate_passed,
        "required_case_count": len(required),
        "missing_required_cases": missing_required,
        "results": results,
        "comparisons": comparisons,
        "claim_boundary": manifest["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    summary = summarize(root)
    write_json(root / "comparison_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
