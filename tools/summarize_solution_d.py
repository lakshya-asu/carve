"""Summarize paired predict-once and reactive full-cell Solution D evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PERTURBATIONS = ("belt_ramp", "encoder_bias", "latency_spike", "pose_disturbance")


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _run(payload: dict[str, Any]) -> dict[str, Any]:
    motion = payload["motion"]
    measurement = payload["delivery"]["measurement"] or {}
    reactive = payload["reactive_interception"]
    return {
        "passed": bool(payload["passed"]),
        "delivered": bool(payload["delivery"]["delivered"]),
        "grasp_confirmed": bool(payload["grasp"]["bilateral_contact"]),
        "retained_lift": float(payload["grasp"]["lift_distance_m"]) >= 0.10,
        "slip_detected": bool(payload["slip_detected"]),
        "intercept_position_error_m": float(payload["interception"]["grasp_position_error_m"]),
        "intercept_yaw_error_rad": float(payload["interception"]["grasp_yaw_error_rad"]),
        "intercept_timing_error_s": float(payload["interception"]["timing_error_s"]),
        "delivery_position_error_m": float(measurement["position_error_m"]) if measurement.get("position_error_m") is not None else None,
        "delivery_yaw_error_rad": float(measurement["angle_error_rad"]) if measurement.get("angle_error_rad") is not None else None,
        "cycle_time_s": float(payload["recording"]["duration_s"]),
        "applied_updates": int(reactive["applied_update_count"]),
        "rejected_updates": int(reactive["rejected_update_count"]),
        "identity_maintained": bool(reactive["identity_maintained"]),
        "update_reasons": [item["reason"]["value"] for item in reactive["updates"]],
        "collision_violations": len(payload["grasp"]["unexpected_contact_pairs"]),
        "joint_limit_violations": int(motion["joint_limit_violations"]),
        "velocity_limit_violations": int(motion["velocity_limit_violations"]),
        "acceleration_limit_violations": int(motion["acceleration_limit_violations"]),
        "minimum_precontact_clearance_m": float(motion["minimum_precontact_pad_clearance_m"]),
        "video": payload["recording"]["path"],
        "usd": payload["stage"]["path"],
        "rgb": payload["artifacts"]["rgb"],
        "depth": payload["artifacts"]["depth_npy"],
        "segmentation": payload["artifacts"]["segmentation"],
        "trajectory": payload["artifacts"]["trajectory"],
        "trace": payload["artifacts"]["trace"],
        "updates_jsonl": reactive["updates_jsonl"],
        "target_visualization": reactive["target_visualization"],
    }


def _bounded_replay(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    tolerances = {
        "intercept_position_error_m": 0.001,
        "intercept_yaw_error_rad": 0.0087266463,
        "delivery_position_error_m": 0.0003,
        "delivery_yaw_error_rad": 0.0034906585,
    }
    deltas = {
        name: abs(float(left[name]) - float(right[name]))
        if left.get(name) is not None and right.get(name) is not None
        else None
        for name in tolerances
    }
    return {
        "passed": bool(
            left["passed"]
            and right["passed"]
            and all(deltas[key] is not None and deltas[key] <= value for key, value in tolerances.items())
        ),
        "metric_absolute_deltas": deltas,
        "metric_tolerances": tolerances,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    runs: dict[str, dict[str, Any]] = {}
    comparisons: dict[str, dict[str, Any]] = {}
    improvements: list[float] = []
    for solution in ("a", "b"):
        for perturbation in PERTURBATIONS:
            baseline_name = f"{solution}_{perturbation}_baseline"
            reactive_name = f"{solution}_{perturbation}_reactive"
            baseline = _run(_read(root / baseline_name / "scene2_integrated_metrics.json"))
            reactive = _run(_read(root / reactive_name / "scene2_integrated_metrics.json"))
            runs[baseline_name] = baseline
            runs[reactive_name] = reactive
            improvement = baseline["intercept_position_error_m"] - reactive["intercept_position_error_m"]
            improvements.append(improvement)
            comparisons[f"{solution}_{perturbation}"] = {
                "baseline_passed": baseline["passed"],
                "reactive_passed": reactive["passed"],
                "intercept_position_improvement_m": improvement,
                "intercept_yaw_improvement_rad": baseline["intercept_yaw_error_rad"] - reactive["intercept_yaw_error_rad"],
                "cycle_time_delta_s": reactive["cycle_time_s"] - baseline["cycle_time_s"],
                "reactive_identity_maintained": reactive["identity_maintained"],
                "reactive_update_reasons": reactive["update_reasons"],
            }
    replay = {}
    for solution in ("a", "b"):
        original = runs[f"{solution}_pose_disturbance_reactive"]
        replay_name = f"{solution}_pose_disturbance_reactive_replay"
        replay_run = _run(_read(root / replay_name / "scene2_integrated_metrics.json"))
        runs[replay_name] = replay_run
        replay[solution] = _bounded_replay(original, replay_run)

    reactive_runs = [value for name, value in runs.items() if "reactive" in name]
    no_new_violations = all(
        run["collision_violations"] == 0
        and run["joint_limit_violations"] == 0
        and run["velocity_limit_violations"] == 0
        and run["acceleration_limit_violations"] == 0
        and run["minimum_precontact_clearance_m"] >= 0.005
        for run in reactive_runs
    )
    performance_passed = sum(value > 0.0 for value in improvements) >= 4 and sum(improvements) > 0.0
    latency_fail_closed = all(
        "stale" in comparisons[f"{solution}_latency_spike"]["reactive_update_reasons"]
        for solution in ("a", "b")
    )
    passed = bool(
        all(run["passed"] for run in reactive_runs)
        and all(run["identity_maintained"] for run in reactive_runs)
        and no_new_violations
        and performance_passed
        and latency_fail_closed
        and all(item["passed"] for item in replay.values())
    )
    summary = {
        "schema_version": 1,
        "route": "solution_d",
        "passed": passed,
        "runs": runs,
        "comparisons": comparisons,
        "bounded_replay": replay,
        "performance_gate": {
            "positive_pair_count": sum(value > 0.0 for value in improvements),
            "pair_count": len(improvements),
            "mean_intercept_position_improvement_m": sum(improvements) / len(improvements),
            "passed": performance_passed,
        },
        "latency_fail_closed": latency_fail_closed,
        "no_new_violations": no_new_violations,
        "claim_boundary": "Complete Isaac Sim Scene 2 evidence only. D remains below deterministic gates and is not hardware validation.",
    }
    output = root / "comparison_summary.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
