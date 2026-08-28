"""Fail closed when a Scene 2 integrated run lacks required Isaac evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGE_TOKENS = (
    'def PhysicsScene "PhysicsScene"',
    'def Xform "Conveyor"',
    'def Xform "FANUC_M10iD12"',
    'def Xform "CompliantGripperReference"',
    'def Camera "OverheadCamera"',
    'def Camera "BufferCamera"',
    'def Xform "CutterStation"',
    'def Xform "BufferStation"',
    'def "RejectBin"',
    'def Xform "Guards"',
    'def Xform "PLC"',
    'def Xform "Frames"',
    'def Xform "Workpieces"',
    'over "J1"',
    'def PhysicsPrismaticJoint "finger_left"',
    'def PhysicsPrismaticJoint "finger_right"',
)


class IntegratedAuditFailure(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise IntegratedAuditFailure(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_evidence_path(value: str, metrics_path: Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (metrics_path.parent / candidate).resolve()


def audit_integrated_metrics(metrics_path: Path, expected_solution: str | None = None) -> dict[str, Any]:
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    solution = str(payload.get("solution", ""))
    _require(solution in {"a", "b"}, "Metrics contain an invalid solution")
    if expected_solution is not None:
        _require(solution == expected_solution, f"Expected Solution {expected_solution.upper()}, got {solution.upper()}")
    _require(payload.get("passed") is True, "Integrated metrics did not pass")
    _require(payload.get("product_pose_sets_after_confirmed_grasp") == 0, "A workpiece pose was written after grasp")

    stage_path = _resolve_evidence_path(payload["stage"]["path"], metrics_path)
    _require(stage_path.is_file(), f"Saved USD is missing: {stage_path}")
    stage_text = stage_path.read_text(encoding="utf-8")
    missing_tokens = [token for token in STAGE_TOKENS if token not in stage_text]
    _require(not missing_tokens, f"Saved USD is missing required cell content: {missing_tokens}")
    _require(_sha256(stage_path) == payload["stage"]["sha256"], "Saved USD hash differs from metrics")
    _require(payload["stage"].get("reload_passed") is True, "Saved USD reload gate did not pass")

    recording_path = _resolve_evidence_path(payload["recording"]["path"], metrics_path)
    _require(recording_path.is_file(), f"Recording is missing: {recording_path}")
    _require(recording_path.stat().st_size == int(payload["recording"]["file_bytes"]), "Recording byte count differs")
    _require(_sha256(recording_path) == payload["recording_sha256"], "Recording hash differs from metrics")
    _require(int(payload["recording"]["frame_count"]) >= 100, "Recording has too few rendered frames")

    perception = payload["perception"]
    _require(str(perception["model_name"]).startswith("ultralytics_yolo26"), "Perception was not YOLO26")
    _require(int(perception["observation_count"]) >= 2, "Tracking lacks two observations")
    _require(perception["rgb_nonempty"] and perception["depth_nonempty"], "Rendered RGBD evidence is empty")
    _require(payload["event_log_readback_passed"] is True, "Deterministic event-log readback failed")
    _require(0.04 <= float(payload["belt_speed_mps"]) <= 0.30, "Belt speed is outside the validated range")
    _require(abs(float(payload["initial_pose"]["y_m"])) <= 0.09, "Initial lateral pose is outside the validated range")
    _require(abs(float(payload["initial_pose"]["yaw_deg"])) <= 85.0, "Initial yaw is outside the validated range")

    motion = payload["motion"]
    _require(int(motion["articulation_controller_commands"]) > 0, "No articulation-controller commands ran")
    _require(float(motion["maximum_physics_step_error_s"]) <= 1e-9, "Controller physics step differed from 1/240 second")
    for key in ("joint_limit_violations", "velocity_limit_violations", "acceleration_limit_violations"):
        _require(int(motion[key]) == 0, f"Motion gate failed: {key}")
    _require(int(motion["trajectory_samples"]) >= 100, "The robot trajectory has too few samples")
    _require(motion["trajectory_time_monotonic"] is True, "Robot trajectory time is not monotonic")
    _require(float(motion["trajectory_endpoint_error_rad"]) <= 1e-6, "Robot trajectory endpoint does not match the controller")
    _require(motion["moveit_runtime_executed"] is False, "Metrics incorrectly claim a live MoveIt runtime")

    trajectory_path = _resolve_evidence_path(payload["artifacts"]["trajectory"], metrics_path)
    _require(trajectory_path.is_file() and trajectory_path.stat().st_size > 0, "Robot trajectory evidence is missing")
    trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    _require(tuple(trajectory["joint_names"]) == ("J1", "J2", "J3", "J4", "J5", "J6"), "Trajectory joint order is invalid")
    samples = trajectory["samples"]
    _require(len(samples) == int(motion["trajectory_samples"]), "Trajectory sample count differs from metrics")
    times = [float(item["time_from_start_s"]) for item in samples]
    _require(all(right > left for left, right in zip(times, times[1:])), "Trajectory evidence time is not monotonic")
    _require(all(len(item["positions_rad"]) == 6 for item in samples), "Trajectory sample is incomplete")

    grasp = payload["grasp"]
    proposal = grasp["proposal"]
    _require(grasp["point_inside_instance_mask"] is True, "Selected grasp point is outside the instance mask")
    _require(float(proposal["confidence"]) >= 0.20, "Grasp classifier confidence is below the gate")
    _require(proposal["grasp_class"]["value"] in {"longitudinal", "diagonal_left", "diagonal_right", "transverse"}, "Grasp class is invalid")
    _require(grasp["bilateral_contact"] is True, "Bilateral physical contact was not confirmed")
    _require(float(grasp["lift_distance_m"]) >= 0.10, "Physical lift was too small")
    _require(float(grasp["maximum_product_to_tcp_distance_m"]) <= float(grasp["retention_limit_m"]), "Grasp retention failed")
    _require(grasp["unexpected_contact_pairs"] == [], "Unexpected gripper contact was recorded")

    delivery = payload["delivery"]
    measurement = delivery["measurement"]
    _require(delivery["delivered"] is True and delivery["plc_result_acknowledged"] is True, "Delivery was not acknowledged")
    _require(float(measurement["position_error_m"]) <= 0.055, "Delivery position error exceeded 55 mm")
    _require(float(measurement["angle_error_rad"]) <= math.radians(7.0), "Delivery angle error exceeded 7 degrees")
    _require(float(measurement["speed_error_mps"]) <= 0.10, "Delivery speed exceeded the stationary-tray limit")
    _require(float(payload["interception"]["timing_error_s"]) <= 0.12, "Interception timing error exceeded 120 ms")

    required_states = {"plan", "intercept", "verify_grasp", "retract"}
    required_states |= {"transfer_direct", "align_direct"} if solution == "a" else {"transfer_buffer", "settle", "reobserve_buffer", "feed_buffer"}
    _require(required_states <= set(payload["state_sequence"]), "The simulator state sequence is incomplete")
    if solution == "b":
        _require(payload["buffer_sensor_oracle_position_error_m"] is not None, "Buffer sensor oracle gate is missing")
        _require(float(payload["buffer_sensor_oracle_position_error_m"]) <= 0.05, "Buffer RGBD calibration gate failed")

    trace_path = _resolve_evidence_path(payload["artifacts"]["trace"], metrics_path)
    _require(trace_path.is_file() and trace_path.stat().st_size > 0, "Cycle trace is missing or empty")
    records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    _require(records[0]["record_type"] == "run_metadata", "Cycle trace lacks leading metadata")
    _require(records[-1]["record_type"] == "terminal_result", "Cycle trace lacks terminal result")

    return {
        "passed": True,
        "solution": solution,
        "scenario": payload["scenario"],
        "seed": payload["seed"],
        "stage_sha256": payload["stage"]["sha256"],
        "recording_sha256": payload["recording_sha256"],
        "recording_frames": payload["recording"]["frame_count"],
        "trace_records": len(records),
        "position_error_m": measurement["position_error_m"],
        "angle_error_rad": measurement["angle_error_rad"],
        "timing_error_s": measurement["timing_error_s"],
        "maximum_product_to_tcp_distance_m": grasp["maximum_product_to_tcp_distance_m"],
        "belt_speed_mps": payload["belt_speed_mps"],
        "initial_yaw_deg": payload["initial_pose"]["yaw_deg"],
        "grasp_class": proposal["grasp_class"]["value"],
        "grasp_classifier_confidence": proposal["confidence"],
        "trajectory_samples": motion["trajectory_samples"],
        "buffer_sensor_oracle_position_error_m": payload["buffer_sensor_oracle_position_error_m"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics")
    parser.add_argument("--solution", choices=("a", "b"))
    parser.add_argument("--output")
    args = parser.parse_args()
    metrics_path = (PROJECT_ROOT / args.metrics).resolve()
    _require(metrics_path == PROJECT_ROOT or PROJECT_ROOT in metrics_path.parents, "Metrics must be inside the project")
    try:
        result = audit_integrated_metrics(metrics_path, args.solution)
    except Exception as exc:
        result = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
    if args.output:
        output = (PROJECT_ROOT / args.output).resolve()
        _require(PROJECT_ROOT in output.parents, "Audit output must be inside the project")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
