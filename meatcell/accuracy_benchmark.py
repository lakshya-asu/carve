"""Aggregate simulation-only accuracy evidence from Scene 2 runs."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, Iterable


METRIC_FIELDS: dict[str, tuple[str, ...]] = {
    "perception_position_error_m": ("perception", "position_error_mean_m"),
    "perception_yaw_error_rad": ("perception", "yaw_error_mean_rad"),
    "tracking_position_error_m": ("tracking", "position_error_mean_m"),
    "tracking_yaw_error_rad": ("tracking", "yaw_error_mean_rad"),
    "track_speed_error_mps": ("perception", "track_speed_error_mps"),
    "intercept_position_error_m": ("interception", "grasp_position_error_m"),
    "intercept_yaw_error_rad": ("interception", "grasp_yaw_error_rad"),
    "intercept_timing_error_s": ("interception", "timing_error_s"),
    "delivery_position_error_m": ("delivery", "measurement", "position_error_m"),
    "delivery_angle_error_rad": ("delivery", "measurement", "angle_error_rad"),
    "delivery_timing_error_s": ("delivery", "measurement", "timing_error_s"),
    "delivery_speed_error_mps": ("delivery", "measurement", "speed_error_mps"),
    "detection_confidence": ("perception", "confidence"),
    "grasp_confidence": ("grasp", "proposal", "confidence"),
    "lift_distance_m": ("grasp", "lift_distance_m"),
    "maximum_retention_distance_m": ("grasp", "maximum_product_to_tcp_distance_m"),
}

# These are internal simulation regression thresholds. They are not physical
# process requirements and must be retuned against measured cell data.
ACCURACY_THRESHOLDS: dict[str, float] = {
    "perception_position_error_m": 0.012,
    "perception_yaw_error_rad": math.radians(2.0),
    "tracking_position_error_m": 0.012,
    "tracking_yaw_error_rad": math.radians(2.0),
    "intercept_position_error_m": 0.015,
    "intercept_yaw_error_rad": math.radians(3.0),
    "intercept_timing_error_s": 0.12,
    "delivery_position_error_m": 0.055,
    "delivery_angle_error_rad": math.radians(7.0),
}

REPLAY_TOLERANCES: dict[str, float] = {
    "perception_position_error_m": 0.00025,
    "perception_yaw_error_rad": math.radians(0.1),
    "tracking_position_error_m": 0.00025,
    "tracking_yaw_error_rad": math.radians(0.1),
    "track_speed_error_mps": 0.0001,
    "intercept_position_error_m": 0.0005,
    "intercept_yaw_error_rad": math.radians(0.1),
    "intercept_timing_error_s": 0.005,
    "delivery_position_error_m": 0.0002,
    "delivery_angle_error_rad": math.radians(0.2),
    "delivery_timing_error_s": 0.0001,
    "delivery_speed_error_mps": 0.0002,
    "detection_confidence": 0.01,
    "grasp_confidence": 0.001,
    "lift_distance_m": 0.001,
    "maximum_retention_distance_m": 0.0001,
}


def nested_value(document: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = document
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def percentile(values: Iterable[float], percent: float) -> float | None:
    ordered = sorted(float(value) for value in values if value is not None and math.isfinite(float(value)))
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percent / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not clean:
        return {"count": 0, "mean": None, "std": None, "min": None, "p50": None, "p90": None, "p95": None, "max": None}
    return {
        "count": len(clean),
        "mean": fmean(clean),
        "std": pstdev(clean),
        "min": min(clean),
        "p50": percentile(clean, 50.0),
        "p90": percentile(clean, 90.0),
        "p95": percentile(clean, 95.0),
        "max": max(clean),
    }


def extract_case(
    config: dict[str, Any],
    metrics: dict[str, Any] | None,
    process_exit_code: int,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    metrics = metrics or {}
    simulator_passed = bool(metrics.get("passed"))
    case: dict[str, Any] = {
        "name": config["name"],
        "tier": config["tier"],
        "solution": config["solution"],
        "seed": config["seed"],
        "belt_speed_mps": config["belt_speed_mps"],
        "start_y_m": config["start_y_m"],
        "start_yaw_deg": config["start_yaw_deg"],
        "perception_latency_ms": config["perception_latency_ms"],
        "position_noise_mm": config["position_noise_mm"],
        "yaw_noise_deg": config["yaw_noise_deg"],
        "replay_group": config.get("replay_group"),
        "process_exit_code": process_exit_code,
        "metrics_found": bool(metrics),
        "simulator_passed": simulator_passed,
        "process_exit_code_consistent": process_exit_code == (0 if simulator_passed else 1),
        "passed": simulator_passed,
        "error": metrics.get("error"),
        "terminal_reason": nested_value(metrics, ("terminal_result", "terminal_reason")),
    }
    for name, path in METRIC_FIELDS.items():
        case[name] = nested_value(metrics, path)
    motion = metrics.get("motion") or {}
    case["joint_limit_violations"] = motion.get("joint_limit_violations")
    case["velocity_limit_violations"] = motion.get("velocity_limit_violations")
    case["acceleration_limit_violations"] = motion.get("acceleration_limit_violations")
    case["bilateral_contact"] = nested_value(metrics, ("grasp", "bilateral_contact"))
    case["mask_interior_grasp"] = nested_value(metrics, ("grasp", "point_inside_instance_mask"))
    case["delivered"] = nested_value(metrics, ("delivery", "delivered"))
    case["video"] = nested_value(metrics, ("recording", "path"))
    case["overlay"] = nested_value(metrics, ("artifacts", "segmentation"))
    case["trace"] = nested_value(metrics, ("artifacts", "trace"))
    evidence_issues: list[str] = []
    for artifact_name, artifact_path in (metrics.get("artifacts") or {}).items():
        path = Path(str(artifact_path))
        if not path.is_absolute() and evidence_root is not None:
            path = evidence_root / path
        if not path.is_file() or path.stat().st_size == 0:
            evidence_issues.append(f"missing_or_empty_{artifact_name}")
    recording = metrics.get("recording") or {}
    if int(recording.get("frame_count") or 0) <= 0 or int(recording.get("file_bytes") or 0) <= 0:
        evidence_issues.append("empty_recording")
    if not bool(nested_value(metrics, ("stage", "reload_passed"))):
        evidence_issues.append("stage_reload_failed")
    if not bool(metrics.get("event_log_readback_passed")):
        evidence_issues.append("event_log_readback_failed")
    if not nested_value(metrics, ("perception", "oracle_samples")):
        evidence_issues.append("missing_perception_oracle_samples")
    if not nested_value(metrics, ("tracking", "oracle_samples")):
        evidence_issues.append("missing_tracking_oracle_samples")
    saved_settings = metrics.get("test_settings") or {}
    for setting in ("perception_latency_ms", "position_noise_mm", "yaw_noise_deg"):
        if saved_settings.get(setting) != config.get(setting):
            evidence_issues.append(f"settings_mismatch_{setting}")
    case["evidence_valid"] = not evidence_issues
    case["evidence_issues"] = ";".join(evidence_issues)
    accuracy_failures = [
        f"{name}>{limit}"
        for name, limit in ACCURACY_THRESHOLDS.items()
        if case.get(name) is None or float(case[name]) > limit
    ]
    functional_failures = []
    if not case.get("bilateral_contact"):
        functional_failures.append("bilateral_contact")
    if not case.get("mask_interior_grasp"):
        functional_failures.append("mask_interior_grasp")
    if not case.get("delivered"):
        functional_failures.append("delivered")
    for name in ("joint_limit_violations", "velocity_limit_violations", "acceleration_limit_violations"):
        if case.get(name) != 0:
            functional_failures.append(name)
    case["accuracy_gate_failures"] = ";".join(accuracy_failures)
    case["functional_gate_failures"] = ";".join(functional_failures)
    case["benchmark_passed"] = simulator_passed and not accuracy_failures and not functional_failures and not evidence_issues
    return case


def _group(cases: list[dict[str, Any]]) -> dict[str, Any]:
    def case_passed(case: dict[str, Any]) -> bool:
        return bool(case.get("benchmark_passed", case["passed"]))

    return {
        "case_count": len(cases),
        "pass_count": sum(case_passed(case) for case in cases),
        "fail_count": sum(not case_passed(case) for case in cases),
        "pass_rate": (sum(case_passed(case) for case in cases) / len(cases)) if cases else None,
        "metrics": {
            name: distribution(case.get(name) for case in cases)
            for name in METRIC_FIELDS
        },
    }


def aggregate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    core = [case for case in cases if case["tier"] == "core"]
    stress = [case for case in cases if case["tier"] == "stress"]
    solutions = {
        solution: _group([case for case in cases if case["solution"] == solution])
        for solution in sorted({str(case["solution"]) for case in cases})
    }
    core_solutions = {
        solution: _group([case for case in core if case["solution"] == solution])
        for solution in sorted({str(case["solution"]) for case in core})
    }
    stress_solutions = {
        solution: _group([case for case in stress if case["solution"] == solution])
        for solution in sorted({str(case["solution"]) for case in stress})
    }
    replay_results: dict[str, Any] = {}
    replay_names = sorted({str(case["replay_group"]) for case in cases if case.get("replay_group")})
    for replay_name in replay_names:
        members = [case for case in cases if case.get("replay_group") == replay_name]
        deltas: dict[str, float | None] = {}
        if len(members) == 2:
            for metric_name in METRIC_FIELDS:
                left = members[0].get(metric_name)
                right = members[1].get(metric_name)
                deltas[metric_name] = None if left is None or right is None else abs(float(left) - float(right))
        replay_results[replay_name] = {
            "case_names": [case["name"] for case in members],
            "member_count": len(members),
            "both_passed": len(members) == 2 and all(bool(case["passed"]) for case in members),
            "metric_absolute_deltas": deltas,
            "exact_scalar_replay": len(members) == 2 and bool(deltas) and all(value == 0.0 for value in deltas.values() if value is not None),
            "bounded_replay_passed": len(members) == 2 and bool(deltas) and all(
                value is None or value <= REPLAY_TOLERANCES[metric_name]
                for metric_name, value in deltas.items()
            ),
        }
    bounded_replay_passed = not replay_results or all(
        bool(result["both_passed"] and result["bounded_replay_passed"])
        for result in replay_results.values()
    )
    base_core_gate = bool(core) and all(bool(case.get("benchmark_passed", case["passed"])) for case in core)
    return {
        "schema_version": 1,
        "scope": "Isaac Sim reference-model accuracy and robustness benchmark",
        "claim_boundary": "Simulation evidence only. It is not real-world accuracy, food-safety validation, real-cell safety validation, OEM fidelity, or production readiness.",
        "oracle_policy": "Simulator ground truth is used only after each run for scoring. It is not an input to perception, tracking, planning, or robot control.",
        "thresholds": ACCURACY_THRESHOLDS,
        "threshold_note": "Internal simulation regression thresholds only. They are not measured production requirements.",
        "replay_tolerances": REPLAY_TOLERANCES,
        "core_gate_passed": base_core_gate and bounded_replay_passed,
        "all_cases_passed": bool(cases) and all(bool(case.get("benchmark_passed", case["passed"])) for case in cases),
        "overall": _group(cases),
        "core": _group(core),
        "stress": _group(stress),
        "by_solution": solutions,
        "core_by_solution": core_solutions,
        "stress_by_solution": stress_solutions,
        "deterministic_replay": replay_results,
        "cases": cases,
    }


def write_csv(path: Path, cases: list[dict[str, Any]]) -> None:
    fields = list(cases[0]) if cases else ["name", "tier", "solution", "passed"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(cases)


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Scene 2 accuracy benchmark",
        "",
        summary["claim_boundary"],
        "",
        f"Core gate: {'PASS' if summary['core_gate_passed'] else 'FAIL'}",
        f"Core cases: {summary['core']['pass_count']} passed, {summary['core']['fail_count']} failed",
        f"Stress cases: {summary['stress']['pass_count']} passed, {summary['stress']['fail_count']} failed",
        "",
        "| Case | Tier | Solution | Speed m/s | Y m | Yaw deg | Camera position mm | Track position mm | Intercept position mm | Delivery position mm | Result |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]

    def millimetres(value: Any) -> str:
        return "n/a" if value is None else f"{float(value) * 1000.0:.2f}"

    for case in summary["cases"]:
        lines.append(
            "| {name} | {tier} | {solution} | {speed:.2f} | {y:.3f} | {yaw:.1f} | {camera} | {track} | {intercept} | {delivery} | {result} |".format(
                name=case["name"], tier=case["tier"], solution=case["solution"].upper(),
                speed=case["belt_speed_mps"], y=case["start_y_m"], yaw=case["start_yaw_deg"],
                camera=millimetres(case.get("perception_position_error_m")),
                track=millimetres(case.get("tracking_position_error_m")),
                intercept=millimetres(case.get("intercept_position_error_m")),
                delivery=millimetres(case.get("delivery_position_error_m")),
                result="PASS" if case.get("benchmark_passed", case["passed"]) else "FAIL",
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_matrix(root: Path) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for config_path in sorted(root.glob("*/case_config.json")):
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        metrics_path = config_path.parent / "scene2_integrated_metrics.json"
        exit_path = config_path.parent / "process_exit_code.txt"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8-sig")) if metrics_path.is_file() else None
        exit_code = int(exit_path.read_text(encoding="utf-8-sig").strip()) if exit_path.is_file() else -1
        cases.append(extract_case(config, metrics, exit_code, config_path.parent))
    summary = aggregate_cases(cases)
    (root / "accuracy_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_csv(root / "accuracy_cases.csv", cases)
    write_markdown(root / "ACCURACY_REPORT.md", summary)
    return summary
