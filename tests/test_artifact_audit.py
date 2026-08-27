import json

import pytest

from tools.audit_artifacts import AuditFailure, distribution, read_trace
from tools.audit_scene2_integrated import IntegratedAuditFailure, STAGE_TOKENS, audit_integrated_metrics
from isaac_sim.cell_runner import _failure_mode


def test_distribution_reports_interpolated_percentiles() -> None:
    result = distribution([1.0, 2.0, 3.0, 4.0])
    assert result == {"count": 4, "min": 1.0, "p50": 2.5, "p95": 3.8499999999999996, "max": 4.0}


def test_trace_reader_requires_monotonic_complete_jsonl(tmp_path) -> None:
    path = tmp_path / "trace.jsonl"
    records = [
        {"record_type": "run_metadata", "schema_version": 1, "payload": {}},
        {"record_type": "event", "schema_version": 1, "timestamp_ns": 2, "payload": {}},
        {"record_type": "terminal_result", "schema_version": 1, "timestamp_ns": 3, "payload": {}},
    ]
    path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
    assert len(read_trace(path)) == 3

    records[2]["timestamp_ns"] = 1
    path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
    with pytest.raises(AuditFailure, match="timestamps move backward"):
        read_trace(path)


def test_hardening_schedule_adds_integrated_safety_scenarios() -> None:
    assert [_failure_mode("a", index, "hardening") for index in range(6)] == [
        "nominal",
        "nominal",
        "failed_grasp",
        "cutter_unavailable",
        "emergency_stop",
        "stale_observation",
    ]
    assert _failure_mode("b", 3, "hardening") == "buffer_timeout"


def test_scene2_integrated_audit_fails_closed_before_artifact_checks(tmp_path) -> None:
    path = tmp_path / "scene2_integrated_metrics.json"
    path.write_text(json.dumps({"solution": "a", "passed": False}), encoding="utf-8")
    with pytest.raises(IntegratedAuditFailure, match="did not pass"):
        audit_integrated_metrics(path, "a")


def test_scene2_integrated_stage_gate_covers_robot_sensors_io_and_gripper() -> None:
    joined = "\n".join(STAGE_TOKENS)
    for required in ("FANUC_M10iD12", "OverheadCamera", "BufferCamera", "PLC", "finger_left"):
        assert required in joined


def test_scene2_integrated_artifact_audit_requires_stage_reload(tmp_path) -> None:
    path = tmp_path / "scene2_integrated_metrics.json"
    path.write_text(
        json.dumps({"solution": "a", "passed": True, "stage": {"reload_passed": False}}),
        encoding="utf-8",
    )
    with pytest.raises((IntegratedAuditFailure, KeyError)):
        audit_integrated_metrics(path, "a")
