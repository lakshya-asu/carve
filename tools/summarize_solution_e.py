"""Summarize integrated Route E shadow and failure evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PHASES = {"close", "stabilize", "slip_correction", "reorientation", "release"}


def _read(root: Path, name: str) -> dict:
    return json.loads((root / name / "scene2_integrated_metrics.json").read_text(encoding="utf-8-sig"))


def _run(payload: dict) -> dict:
    skill = payload["contact_skill"]
    motion = payload["motion"]
    artifacts = payload["artifacts"]
    records = skill["records"]
    return {
        "passed": bool(payload["passed"]),
        "delivered": bool(payload["delivery"]["delivered"]),
        "grasp_confirmed": bool(payload["grasp"]["bilateral_contact"]),
        "retained_lift": float(payload["grasp"]["lift_distance_m"]) >= 0.10,
        "slip_detected": bool(payload["slip_detected"]),
        "delivery_position_error_m": payload["delivery"]["measurement"]["position_error_m"] if payload["delivery"]["measurement"] else None,
        "delivery_yaw_error_rad": payload["delivery"]["measurement"]["angle_error_rad"] if payload["delivery"]["measurement"] else None,
        "cycle_time_s": float(payload["recording"]["duration_s"]),
        "recovery_path": payload["terminal_result"]["terminal_path"]["value"],
        "collision_violations": len(payload["grasp"]["unexpected_contact_pairs"]),
        "joint_limit_violations": int(motion["joint_limit_violations"]),
        "velocity_limit_violations": int(motion["velocity_limit_violations"]),
        "acceleration_limit_violations": int(motion["acceleration_limit_violations"]),
        "shadow_gate_passed": bool(skill["shadow_gate_passed"]),
        "executed_action_count": int(skill["executed_action_count"]),
        "phases": sorted({item["phase"] for item in records}),
        "records": records,
        "model_sha256": skill["model_sha256"],
        "rgb": artifacts["rgb"],
        "depth": artifacts["depth_npy"],
        "visualization": artifacts["contact_skill_visualization"],
        "trajectory": artifacts["trajectory"],
        "trace": artifacts["trace"],
        "usd": payload["stage"]["path"],
        "video": payload["recording"]["path"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    names = ("a_shadow", "a_shadow_replay", "b_shadow", "b_slip_shadow", "a_emergency_shadow")
    runs = {name: _run(_read(root, name)) for name in names}
    original = {item["phase"]: float(item["proposal"]["value"]) for item in runs["a_shadow"]["records"]}
    replay = {item["phase"]: float(item["proposal"]["value"]) for item in runs["a_shadow_replay"]["records"]}
    replay_deltas = {phase: abs(original[phase] - replay[phase]) for phase in PHASES}
    bounded_replay_passed = all(value <= 0.01 for value in replay_deltas.values())
    emergency_rejected = any(
        item["proposal"]["fallback_reason"] == "emergency_stop"
        and item["proposal"]["executed"] is False
        for item in runs["a_emergency_shadow"]["records"]
    )
    nominal = (runs["a_shadow"], runs["a_shadow_replay"], runs["b_shadow"])
    no_violations = all(
        run["collision_violations"] == 0
        and run["joint_limit_violations"] == 0
        and run["velocity_limit_violations"] == 0
        and run["acceleration_limit_violations"] == 0
        for run in runs.values()
    )
    passed = bool(
        all(run["passed"] for run in runs.values())
        and all(set(run["phases"]) == PHASES for run in nominal)
        and all(run["executed_action_count"] == 0 for run in runs.values())
        and all(run["shadow_gate_passed"] for run in nominal)
        and runs["b_slip_shadow"]["slip_detected"]
        and emergency_rejected
        and bounded_replay_passed
        and no_violations
    )
    summary = {
        "schema_version": 1,
        "route": "solution_e",
        "passed": passed,
        "execution_policy": "shadow_only",
        "runs": runs,
        "bounded_replay": {
            "passed": bounded_replay_passed,
            "phase_absolute_deltas": replay_deltas,
            "tolerance": 0.01,
        },
        "emergency_stop_fail_closed": emergency_rejected,
        "no_new_violations": no_violations,
        "physical_data_blocker": "Representative real force, tactile, slip, tissue-damage, and recovery data is required before bounded learned execution or hardware-validity claims.",
        "claim_boundary": "Complete Isaac Sim Scene 2 shadow evidence only. Learned outputs were never executed.",
    }
    (root / "comparison_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
