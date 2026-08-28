import json
from pathlib import Path

import pytest

from meatcell.experiment_matrix import build_manifest, validate_manifest
from tools.summarize_hybrid_comparison import summarize


def _manifest(stacks=("S0", "S1", "S2", "S3", "S4")):
    return build_manifest(
        experiment_id="paired_test",
        flows=("a", "b"),
        stacks=stacks,
        seed=4801,
        perturbation="pose_disturbance",
        belt_speed_mps=0.16,
        start_y_m=0.02,
        start_yaw_deg=35.0,
        model_hashes={"yolo26": "yolo-hash", "grasp_affordance": "grasp-hash", "contact_skill": None},
    )


def test_manifest_has_unique_paired_cases_and_marks_s4_not_run() -> None:
    manifest = _manifest()
    validate_manifest(manifest)

    assert len(manifest["cases"]) == 10
    assert len({case["case_id"] for case in manifest["cases"]}) == 10
    s4 = [case for case in manifest["cases"] if case["stack_id"] == "S4"]
    assert all(case["status"] == "not_run" and not case["required_for_gate"] for case in s4)


def test_manifest_rejects_a_stack_configuration_mismatch() -> None:
    manifest = _manifest(("S0",))
    manifest["cases"][0]["grasp_selector"] = "learned"

    with pytest.raises(ValueError, match="grasp selector"):
        validate_manifest(manifest)


def test_summary_fails_closed_when_required_evidence_is_missing(tmp_path: Path) -> None:
    manifest = _manifest(("S0", "S4"))
    (tmp_path / "experiment_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = summarize(tmp_path)

    assert result["passed"] is False
    assert result["required_case_count"] == 2
    assert len(result["missing_required_cases"]) == 2
    s4_results = [value for name, value in result["results"].items() if "_s4_" in name]
    assert all(value["status"] == "not_run" for value in s4_results)


def test_summary_reports_reduced_simulator_failure_without_crashing(tmp_path: Path) -> None:
    manifest = _manifest(("S0",))
    case = manifest["cases"][0]
    (tmp_path / "experiment_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    case_root = tmp_path / case["result_directory"]
    case_root.mkdir()
    (case_root / "scene2_integrated_metrics.json").write_text(
        json.dumps({"passed": False, "error": "lift IK unreachable"}),
        encoding="utf-8",
    )

    result = summarize(tmp_path)

    assert result["passed"] is False
    assert result["results"][case["case_id"]]["status"] == "failed"
    assert result["results"][case["case_id"]]["error"] == "lift IK unreachable"
