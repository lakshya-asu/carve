"""Summarize paired geometric and learned Solution C full-cell runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _metrics(payload: dict[str, Any]) -> dict[str, Any]:
    measurement = payload["delivery"].get("measurement") or {}
    forces = [float(value) for value in payload["grasp"].get("peak_contact_force_n", ())]
    motion = payload["motion"]
    terminal = payload["terminal_result"]
    return {
        "passed": bool(payload["passed"]),
        "delivered": bool(payload["delivery"]["delivered"]),
        "grasp_confirmed": bool(payload["grasp"]["bilateral_contact"]),
        "retained_lift": float(payload["grasp"]["lift_distance_m"]) >= 0.10
        and float(payload["grasp"]["maximum_product_to_tcp_distance_m"]) <= 0.13,
        "lift_distance_m": float(payload["grasp"]["lift_distance_m"]),
        "slip_detected": bool(payload.get("slip_detected")),
        "excessive_contact_proxy": max(forces, default=0.0) > 140.0,
        "maximum_contact_force_proxy_n": max(forces, default=0.0),
        "interception_timing_error_s": payload["interception"]["timing_error_s"],
        "delivery_position_error_m": measurement.get("position_error_m"),
        "delivery_yaw_error_rad": measurement.get("angle_error_rad"),
        "cycle_time_s": float(payload["recording"]["duration_s"]),
        "recovery_terminal_path": terminal["terminal_path"]["value"],
        "collision_violations": len(payload["grasp"]["unexpected_contact_pairs"]),
        "joint_limit_violations": int(motion["joint_limit_violations"]),
        "velocity_limit_violations": int(motion["velocity_limit_violations"]),
        "acceleration_limit_violations": int(motion["acceleration_limit_violations"]),
        "event_log_readback_passed": bool(payload["event_log_readback_passed"]),
        "video": payload["recording"]["path"],
        "usd": payload["stage"]["path"],
        "rgb": payload["artifacts"]["rgb"],
        "depth": payload["artifacts"]["depth_npy"],
        "segmentation": payload["artifacts"]["segmentation"],
        "trajectory": payload["artifacts"]["trajectory"],
        "trace": payload["artifacts"]["trace"],
    }


def _within(left: float | None, right: float | None, tolerance: float) -> bool:
    return left is not None and right is not None and abs(float(left) - float(right)) <= tolerance


def _bounded_replay(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    tolerances = {
        "delivery_position_error_m": 0.0002,
        "delivery_yaw_error_rad": 0.0034906585,
        "interception_timing_error_s": 0.005,
        "lift_distance_m": 0.001,
    }
    deltas = {
        name: abs(float(left[name]) - float(right[name]))
        if left.get(name) is not None and right.get(name) is not None
        else None
        for name in tolerances
    }
    component_passes = {
        name: _within(left.get(name), right.get(name), tolerance)
        for name, tolerance in tolerances.items()
    }
    return {
        "passed": bool(left["passed"] and right["passed"] and all(component_passes.values())),
        "both_cycles_passed": bool(left["passed"] and right["passed"]),
        "metric_absolute_deltas": deltas,
        "metric_tolerances": tolerances,
        "metric_passes": component_passes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    names = ("baseline_a", "learned_a", "learned_a_replay", "baseline_b", "learned_b", "learned_b_replay")
    payloads = {name: _read(root / name / "scene2_integrated_metrics.json") for name in names}
    for name in ("learned_a", "learned_a_replay", "learned_b", "learned_b_replay"):
        affordance = payloads[name]["grasp"]["affordance"]
        if affordance["mode"] != "learned" or affordance["fallback_used"] or len(affordance["candidates"]) < 3:
            raise ValueError(f"{name} did not execute learned multi-candidate ranking")
    runs = {name: _metrics(payload) for name, payload in payloads.items()}
    replay = {}
    for solution in ("a", "b"):
        left = runs[f"learned_{solution}"]
        right = runs[f"learned_{solution}_replay"]
        replay[solution] = _bounded_replay(left, right)
    passed = all(run["passed"] for run in runs.values()) and all(item["passed"] for item in replay.values())
    summary = {
        "schema_version": 1,
        "route": "solution_c",
        "passed": passed,
        "comparison": "geometric mask_pca_clearance_v2 versus learned multi-outcome candidate ranking",
        "runs": runs,
        "bounded_replay": replay,
        "success_rate": sum(run["delivered"] for run in runs.values()) / len(runs),
        "claim_boundary": "Complete Isaac Sim Scene 2 evidence only. Contact-force values are uncalibrated proxies.",
    }
    output = root / "comparison_summary.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
