"""Audit saved Isaac stages, rendered media, traces, and metric consistency."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMMON_STAGE_TOKENS = (
    'def PhysicsScene "PhysicsScene"',
    'def Xform "Conveyor"',
    'def Xform "RobotReference"',
    "PhysicsArticulationRootAPI",
    'def Xform "GripperReference"',
    'def Camera "OverheadCamera"',
    'def Camera "WristCamera"',
    'def Xform "cut_target_frame"',
    'def Xform "CutterFeedStationReference"',
    'def Xform "Guards"',
    'def Xform "RejectBin"',
    'def Xform "PLCReference"',
    'def Xform "MeatReference_000"',
    'def Xform "conveyor_frame"',
)


class AuditFailure(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditFailure(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percentile(values: Iterable[float], quantile: float) -> float | None:
    ordered = sorted(float(item) for item in values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    items = [float(item) for item in values]
    return {
        "count": len(items),
        "min": min(items) if items else None,
        "p50": _percentile(items, 0.50),
        "p95": _percentile(items, 0.95),
        "max": max(items) if items else None,
    }


def audit_stage(path: Path, solution: str, expected_recipe_id: str | None = None) -> dict[str, Any]:
    _require(path.is_file(), f"Saved stage is missing: {path}")
    text = path.read_text(encoding="utf-8")
    _require(text.startswith("#usda"), f"Saved stage is not text USDA: {path}")
    missing = [token for token in COMMON_STAGE_TOKENS if token not in text]
    if solution == "b" and 'def Xform "BufferReference"' not in text:
        missing.append('def Xform "BufferReference"')
    _require(not missing, f"Saved stage is missing required content: {missing}")
    _require("meatcell:referenceAssetNotice" in text, "Saved stage lacks the reference asset notice")
    if expected_recipe_id is not None:
        _require("meatcell:productRecipeId" in text, "Saved stage lacks the product recipe ID")
        _require("meatcell:physicalCalibrationComplete" in text, "Saved stage lacks product calibration status")
        _require(expected_recipe_id in text, "Saved stage recipe differs from metric evidence")
    _require("meatcell:emergencyStop" in text, "Saved stage lacks emergency stop I/O")
    _require("IsaacContactSensor" in text, "Saved stage lacks gripper contact sensors")
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "required_tokens": len(COMMON_STAGE_TOKENS) + (1 if solution == "b" else 0),
    }


def audit_media(directory: Path) -> dict[str, Any]:
    import numpy as np
    from PIL import Image

    rgb_files = sorted(directory.glob("*_rgb.png"))
    depth_files = sorted(directory.glob("*_depth.npy"))
    _require(rgb_files, f"No RGB render was saved in {directory}")
    _require(depth_files, f"No depth render was saved in {directory}")
    _require(len(rgb_files) == len(depth_files), f"RGB and depth counts differ in {directory}")
    rgb_hashes = []
    depth_hashes = []
    dimensions = set()
    valid_rgb_pixels = 0
    valid_depth_pixels = 0
    for rgb_path, depth_path in zip(rgb_files, depth_files, strict=True):
        rgb = np.asarray(Image.open(rgb_path).convert("RGB"))
        depth = np.load(depth_path, allow_pickle=False)
        _require(rgb.shape == (480, 640, 3), f"Unexpected RGB shape in {rgb_path}: {rgb.shape}")
        _require(depth.shape == (480, 640), f"Unexpected depth shape in {depth_path}: {depth.shape}")
        rgb_valid = int(np.count_nonzero(np.any(rgb != 0, axis=-1)))
        depth_valid = int(np.count_nonzero(np.isfinite(depth) & (depth > 0.0)))
        _require(rgb_valid >= 300_000, f"RGB render is mostly empty: {rgb_path}")
        _require(depth_valid >= 300_000, f"Depth render is mostly empty: {depth_path}")
        _require(int(rgb.max()) > int(rgb.min()), f"RGB render is constant: {rgb_path}")
        finite_depth = depth[np.isfinite(depth) & (depth > 0.0)]
        _require(float(np.ptp(finite_depth)) > 0.1, f"Depth render lacks scene range: {depth_path}")
        rgb_hashes.append(_sha256(rgb_path))
        depth_hashes.append(_sha256(depth_path))
        dimensions.add((int(rgb.shape[1]), int(rgb.shape[0])))
        valid_rgb_pixels += rgb_valid
        valid_depth_pixels += depth_valid
    return {
        "rgb_files": len(rgb_files),
        "depth_files": len(depth_files),
        "dimensions": sorted(dimensions),
        "rgb_sha256": rgb_hashes,
        "depth_sha256": depth_hashes,
        "valid_rgb_pixels": valid_rgb_pixels,
        "valid_depth_pixels": valid_depth_pixels,
    }


def read_trace(path: Path) -> list[dict[str, Any]]:
    _require(path.is_file(), f"Trace is missing: {path}")
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise AuditFailure(f"Invalid JSON in {path} line {line_number}: {exc}") from exc
    _require(records, f"Trace is empty: {path}")
    _require(records[0].get("record_type") == "run_metadata", f"Trace lacks leading metadata: {path}")
    _require(records[-1].get("record_type") == "terminal_result", f"Trace lacks terminal result: {path}")
    timestamps = [int(item["timestamp_ns"]) for item in records if "timestamp_ns" in item]
    _require(timestamps == sorted(timestamps), f"Trace timestamps move backward: {path}")
    return records


def _enum_value(value: Any) -> Any:
    return value.get("value") if isinstance(value, dict) else value


def audit_trace(path: Path, result: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    records = read_trace(path)
    types = Counter(item["record_type"] for item in records)
    required = {
        "run_metadata",
        "plc_state",
        "observation",
        "interception_decision",
        "final_robot_state",
        "replay_decision_input",
        "terminal_result",
    }
    _require(required <= set(types), f"Trace is missing required record types: {path}")
    metadata = records[0]["payload"]
    _require("isaacsim" in json.dumps(metadata), f"Trace lacks Isaac Sim dependency evidence: {path}")
    observations = [item["payload"] for item in records if item["record_type"] == "observation"]
    _require(len(observations) >= 2, f"Trace has fewer than two rendered observations: {path}")
    _require(
        all(_enum_value(item["source"]) == "segmentation" and item["instance_mask_rle"] for item in observations),
        f"Trace observation is not rendered segmentation with a mask: {path}",
    )
    terminal = records[-1]["payload"]
    _require(terminal == result, f"Trace terminal result differs from metrics: {path}")
    _require(bool(evidence["deterministic_replay_passed"]), f"Replay gate failed: {path}")
    _require(int(evidence["actual_controller_command_count"]) > 0, f"No articulation commands were executed: {path}")
    _require(result["collision_count"] == 0, f"Collision violation recorded: {path}")
    _require(result["joint_limit_violation_count"] == 0, f"Joint limit violation recorded: {path}")

    plc = [item["payload"] for item in records if item["record_type"] == "plc_state"]
    states = [item["payload"]["state"] for item in records if item["record_type"] == "cell_event"]
    reasons = [item["payload"]["reason"] for item in records if item["record_type"] == "cell_event"]
    mode = evidence["failure_mode"]
    terminal_path = _enum_value(result["terminal_path"])
    if terminal_path == "success":
        _require(types["delivery_product_pose"] == 1, f"Successful trace lacks delivery pose: {path}")
        _require(any(item["result_acknowledged"] for item in plc), f"Successful trace lacks PLC result acknowledgment: {path}")
        _require(all(state in states for state in ("verify_delivery", "retract", "idle")), f"Successful trace lacks delivery states: {path}")
        _require(int(evidence["intentional_contact_samples"]) > 0, f"Successful trace lacks contact evidence: {path}")
    if mode == "failed_grasp":
        _require(result["terminal_reason"] == "failed_grasp_contact_confirmation", f"Failed grasp reason mismatch: {path}")
        _require(terminal_path == "recovered" and "recover" in states and "idle" in states, f"Failed grasp did not recover: {path}")
        _require(any(item["fault_active"] for item in plc), f"Failed grasp did not assert PLC fault: {path}")
    elif mode == "cutter_unavailable":
        _require(result["terminal_reason"] == "cutter_unavailable_before_commit", f"Cutter block reason mismatch: {path}")
        _require(any(_enum_value(item["cutter"]["mode"]) == "blocked" for item in plc), f"Cutter block was not traced: {path}")
        _require(terminal_path == "reject", f"Cutter unavailable path did not reject: {path}")
    elif mode == "buffer_timeout":
        _require(result["terminal_reason"] == "buffer_timeout", f"Buffer timeout reason mismatch: {path}")
        _require(terminal_path == "recovered" and "recover" in states, f"Buffer timeout did not recover: {path}")
    elif mode == "emergency_stop":
        _require(result["terminal_reason"] == "plc_emergency_stop", f"Emergency stop reason mismatch: {path}")
        _require(terminal_path == "safe_stop" and "safe_stop" in states and "idle" in states, f"Emergency stop did not reach safe stop and reset: {path}")
        _require(any(item["emergency_stop_active"] for item in plc), f"Emergency stop PLC input was not traced: {path}")
        _require(types["safe_stop_robot_state"] == 2, f"Emergency stop hold states are missing: {path}")
        _require(float(evidence["safe_stop_hold_max_joint_delta"]) <= 0.005, f"Robot drifted during emergency stop hold: {path}")
    elif mode == "stale_observation":
        decisions = [item["payload"] for item in records if item["record_type"] == "interception_decision"]
        _require(any(_enum_value(item["reason"]) == "stale" for item in decisions), f"Stale observation was not rejected by the planner: {path}")
        _require(result["terminal_reason"] == "interception_stale" and terminal_path == "reject", f"Stale observation recovery mismatch: {path}")
    if result.get("slip_detected"):
        _require("buffer_slip_corrected" in reasons, f"Slip result lacks correction transition: {path}")
    latencies = [
        (item["delivery_time"]["nanoseconds"] - item["exposure_time"]["nanoseconds"]) / 1_000_000_000.0
        for item in observations
    ]
    return {
        "path": str(path.resolve()),
        "records": len(records),
        "record_types": dict(sorted(types.items())),
        "perception_latencies_s": latencies,
    }


def audit_metric_file(path: Path, expected_mode: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema_version = int(payload.get("schema_version", 1))
    solution = payload["solution"]
    _require(solution in {"a", "b"}, f"Invalid solution in {path}")
    _require(bool(payload["passed"]), f"Metric payload failed: {path}")
    _require(payload.get("scenario_profile", "baseline") == expected_mode, f"Scenario profile mismatch: {path}")
    _require(all(bool(item["passed"]) for item in payload["gates"].values()), f"One or more gates failed: {path}")
    product_recipe = payload.get("product_recipe")
    if schema_version >= 2:
        _require(isinstance(product_recipe, dict), f"Metric payload lacks product recipe evidence: {path}")
        _require(bool(product_recipe.get("recipe_id")), f"Metric product recipe ID is blank: {path}")
        _require(
            product_recipe.get("physical_calibration_complete") is False,
            f"Reference product must not claim physical calibration: {path}",
        )
    results = payload["cycle_results"]
    evidence = payload["cycle_evidence"]
    _require(len(results) == payload["cycles"] == len(evidence), f"Cycle counts are inconsistent: {path}")
    stage = audit_stage(
        Path(payload["stage"]),
        solution,
        product_recipe["recipe_id"] if schema_version >= 2 else None,
    )
    media = audit_media(path.parent / "media")
    traces = []
    latencies = []
    for result, item in zip(results, evidence, strict=True):
        trace = audit_trace(Path(item["trace"]), result, item)
        traces.append(trace)
        latencies.extend(trace["perception_latencies_s"])
    return {
        "path": str(path.resolve()),
        "solution": solution,
        "recipe_id": product_recipe["recipe_id"] if schema_version >= 2 else None,
        "seed": int(payload["seed"]),
        "cycles": int(payload["cycles"]),
        "stage": stage,
        "media": media,
        "traces": traces,
        "results": results,
        "evidence": evidence,
        "perception_latencies_s": latencies,
    }


def audit_root(root: Path, mode: str, expected_seeds: set[int] | None = None) -> dict[str, Any]:
    metric_paths = (
        [root / "isaac_a" / "metrics.json", root / "isaac_b" / "metrics.json"]
        if mode == "baseline"
        else sorted(root.rglob("metrics.json"))
    )
    metric_paths = [path for path in metric_paths if path.is_file()]
    _require(metric_paths, f"No metric files found under {root}")
    expected_profile = "baseline" if mode == "recipes" else mode
    batches = [audit_metric_file(path, expected_profile) for path in metric_paths]
    by_solution: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for batch in batches:
        by_solution[batch["solution"]].append(batch)
    _require(set(by_solution) == {"a", "b"}, "Artifact audit requires both Solution A and Solution B")
    if mode == "recipes":
        recipes: dict[str, set[str]] = defaultdict(set)
        for batch in batches:
            _require(batch["recipe_id"] is not None, "Recipe audit requires schema version 2 metrics")
            recipes[batch["recipe_id"]].add(batch["solution"])
        _require(
            all(solutions == {"a", "b"} for solutions in recipes.values()),
            "Every recipe must include both Solution A and Solution B evidence",
        )
    if expected_seeds is not None:
        for solution, items in by_solution.items():
            actual = {item["seed"] for item in items}
            _require(actual == expected_seeds, f"Seed matrix mismatch for Solution {solution.upper()}: {sorted(actual)}")
    all_results = [result for batch in batches for result in batch["results"]]
    all_evidence = [item for batch in batches for item in batch["evidence"]]
    stage_signatures = {
        solution: sorted({batch["stage"]["sha256"] for batch in items})
        for solution, items in by_solution.items()
    }
    if mode == "hardening":
        _require(all(len(items) == 1 for items in stage_signatures.values()), "Saved stage content changed across hardening seeds")
    if mode == "recipes":
        recipe_stage_signatures: dict[tuple[str, str], set[str]] = defaultdict(set)
        for batch in batches:
            recipe_stage_signatures[(batch["recipe_id"], batch["solution"])].add(batch["stage"]["sha256"])
        _require(
            all(len(items) == 1 for items in recipe_stage_signatures.values()),
            "Saved stage content changed within a recipe and solution",
        )
    scenario_counts = Counter(item["failure_mode"] for item in all_evidence)
    terminal_counts = Counter(_enum_value(item["terminal_path"]) for item in all_results)
    failure_counts = Counter(item["terminal_reason"] for item in all_results if _enum_value(item["terminal_path"]) != "success")
    success_results = [item for item in all_results if _enum_value(item["terminal_path"]) == "success"]
    latencies = [value for batch in batches for value in batch["perception_latencies_s"]]

    def solution_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
        results = [result for batch in items for result in batch["results"]]
        evidence = [item for batch in items for item in batch["evidence"]]
        successful = [result for result in results if _enum_value(result["terminal_path"]) == "success"]
        solution_latencies = [value for batch in items for value in batch["perception_latencies_s"]]
        return {
            "batches": len(items),
            "seeds": sorted(item["seed"] for item in items),
            "cycles": sum(item["cycles"] for item in items),
            "stage_sha256": stage_signatures[items[0]["solution"]],
            "rgb_files": sum(item["media"]["rgb_files"] for item in items),
            "depth_files": sum(item["media"]["depth_files"] for item in items),
            "scenario_counts": dict(sorted(Counter(item["failure_mode"] for item in evidence).items())),
            "terminal_path_counts": dict(
                sorted(Counter(_enum_value(item["terminal_path"]) for item in results).items())
            ),
            "failure_counts": dict(
                sorted(
                    Counter(
                        item["terminal_reason"]
                        for item in results
                        if _enum_value(item["terminal_path"]) != "success"
                    ).items()
                )
            ),
            "deterministic_replay_passes": sum(bool(item["deterministic_replay_passed"]) for item in evidence),
            "metrics_distributions": {
                "placement_position_error_m": distribution(item["placement_position_error_m"] for item in successful),
                "placement_angle_error_rad": distribution(item["placement_angle_error_rad"] for item in successful),
                "timing_error_s": distribution(item["timing_error_s"] for item in successful),
                "transfer_speed_error_mps": distribution(item["transfer_speed_error_mps"] for item in successful),
                "perception_latency_s": distribution(solution_latencies),
                "intercept_timing_error_s": distribution(
                    item["intercept_timing_error_s"]
                    for item in evidence
                    if item["intercept_timing_error_s"] is not None
                ),
                "safe_stop_hold_max_joint_delta": distribution(
                    item.get("safe_stop_hold_max_joint_delta")
                    for item in evidence
                    if item.get("safe_stop_hold_max_joint_delta") is not None
                ),
            },
        }

    summary = {
        "schema_version": 1,
        "passed": True,
        "mode": mode,
        "root": str(root.resolve()),
        "metric_files": len(metric_paths),
        "cycles": len(all_results),
        "solutions": {solution: solution_summary(items) for solution, items in sorted(by_solution.items())},
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "terminal_path_counts": dict(sorted(terminal_counts.items())),
        "failure_counts": dict(sorted(failure_counts.items())),
        "deterministic_replay_passes": sum(bool(item["deterministic_replay_passed"]) for item in all_evidence),
        "collision_count": sum(int(item["collision_count"]) for item in all_results),
        "joint_limit_violation_count": sum(int(item["joint_limit_violation_count"]) for item in all_results),
        "metrics_distributions": {
            "placement_position_error_m": distribution(item["placement_position_error_m"] for item in success_results),
            "placement_angle_error_rad": distribution(item["placement_angle_error_rad"] for item in success_results),
            "timing_error_s": distribution(item["timing_error_s"] for item in success_results),
            "transfer_speed_error_mps": distribution(item["transfer_speed_error_mps"] for item in success_results),
            "perception_latency_s": distribution(latencies),
            "intercept_timing_error_s": distribution(
                item["intercept_timing_error_s"]
                for item in all_evidence
                if item["intercept_timing_error_s"] is not None
            ),
            "safe_stop_hold_max_joint_delta": distribution(
                item.get("safe_stop_hold_max_joint_delta")
                for item in all_evidence
                if item.get("safe_stop_hold_max_joint_delta") is not None
            ),
        },
        "batches": [
            {
                "metrics": item["path"],
                "solution": item["solution"],
                "seed": item["seed"],
                "cycles": item["cycles"],
                "stage": item["stage"],
                "media": item["media"],
                "trace_count": len(item["traces"]),
            }
            for item in batches
        ],
    }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="results")
    parser.add_argument("--mode", choices=("baseline", "hardening", "recipes"), default="baseline")
    parser.add_argument("--expected-seeds", default="")
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = (PROJECT_ROOT / args.root).resolve()
    _require(PROJECT_ROOT in root.parents or root == PROJECT_ROOT, "Audit root must be inside the project")
    expected_seeds = {int(item) for item in args.expected_seeds.split(",") if item.strip()} or None
    try:
        summary = audit_root(root, args.mode, expected_seeds)
    except Exception as exc:
        summary = {
            "schema_version": 1,
            "passed": False,
            "mode": args.mode,
            "root": str(root),
            "error": f"{type(exc).__name__}: {exc}",
        }
    if args.output:
        output = (PROJECT_ROOT / args.output).resolve()
        _require(PROJECT_ROOT in output.parents, "Audit output must be inside the project")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
