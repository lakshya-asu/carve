import json
from pathlib import Path
import pytest

from meatcell.accuracy_benchmark import aggregate_cases, distribution, summarize_matrix


def test_distribution_reports_reproducible_percentiles() -> None:
    result = distribution([1.0, 2.0, 3.0, 4.0])
    assert result["count"] == 4
    assert result["mean"] == 2.5
    assert result["p50"] == 2.5
    assert result["p95"] == pytest.approx(3.85)


def test_stress_failure_does_not_weaken_core_gate() -> None:
    cases = [
        {"tier": "core", "solution": "a", "passed": True},
        {"tier": "core", "solution": "b", "passed": True},
        {"tier": "stress", "solution": "a", "passed": False},
    ]
    result = aggregate_cases(cases)
    assert result["core_gate_passed"] is True
    assert result["all_cases_passed"] is False
    assert result["stress"]["fail_count"] == 1


def test_replay_group_reports_exact_scalar_match() -> None:
    base = {
        "tier": "core", "solution": "a", "passed": True, "replay_group": "repeat",
        "delivery_position_error_m": 0.004,
    }
    result = aggregate_cases([{**base, "name": "first"}, {**base, "name": "second"}])
    assert result["deterministic_replay"]["repeat"]["both_passed"] is True
    assert result["deterministic_replay"]["repeat"]["exact_scalar_replay"] is True
    assert result["deterministic_replay"]["repeat"]["bounded_replay_passed"] is True


def test_summarize_matrix_reads_case_evidence(tmp_path: Path) -> None:
    case_root = tmp_path / "core_a"
    case_root.mkdir()
    config = {
        "name": "core_a", "tier": "core", "solution": "a", "seed": 1,
        "belt_speed_mps": 0.1, "start_y_m": 0.0, "start_yaw_deg": 0.0,
        "perception_latency_ms": 30.0, "position_noise_mm": 1.0, "yaw_noise_deg": 0.35,
    }
    metrics = {
        "passed": True,
        "perception": {"position_error_mean_m": 0.001, "yaw_error_mean_rad": 0.01, "confidence": 0.9, "track_speed_error_mps": 0.002, "oracle_samples": [{"position_error_m": 0.001}]},
        "tracking": {"position_error_mean_m": 0.002, "yaw_error_mean_rad": 0.02, "oracle_samples": [{"position_error_m": 0.002}]},
        "interception": {"grasp_position_error_m": 0.003, "grasp_yaw_error_rad": 0.03, "timing_error_s": 0.01},
        "delivery": {"delivered": True, "measurement": {"position_error_m": 0.004, "angle_error_rad": 0.04, "timing_error_s": 0.02, "speed_error_mps": 0.001}},
        "grasp": {"bilateral_contact": True, "point_inside_instance_mask": True, "proposal": {"confidence": 0.8}, "lift_distance_m": 0.1, "maximum_product_to_tcp_distance_m": 0.05},
        "motion": {"joint_limit_violations": 0, "velocity_limit_violations": 0, "acceleration_limit_violations": 0},
        "stage": {"reload_passed": True},
        "event_log_readback_passed": True,
        "recording": {"frame_count": 10, "file_bytes": 100},
        "artifacts": {"rgb": str(case_root / "rgb.png")},
        "test_settings": {"perception_latency_ms": 30.0, "position_noise_mm": 1.0, "yaw_noise_deg": 0.35},
    }
    (case_root / "rgb.png").write_bytes(b"evidence")
    (case_root / "case_config.json").write_text(json.dumps(config), encoding="utf-8")
    (case_root / "scene2_integrated_metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    (case_root / "process_exit_code.txt").write_text("0", encoding="utf-8")
    result = summarize_matrix(tmp_path)
    assert result["core_gate_passed"] is True
    assert result["cases"][0]["delivery_position_error_m"] == 0.004
    assert (tmp_path / "accuracy_cases.csv").is_file()
    assert "Simulation evidence only" in (tmp_path / "ACCURACY_REPORT.md").read_text(encoding="utf-8")
