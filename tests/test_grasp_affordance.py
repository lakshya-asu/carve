import json
from pathlib import Path

from meatcell.contracts import (
    BoundingBox,
    GraspClass,
    ObjectObservation,
    ObservationSource,
    SimTime,
    Transform,
    Vector3,
    VisionGraspProposal,
)
from meatcell.grasp_affordance import FEATURE_NAMES, OUTCOME_NAMES, rank_grasp_candidates


def _observation() -> ObjectObservation:
    return ObjectObservation(
        "detection-1",
        SimTime(0),
        SimTime.from_seconds(0.03),
        "meat_reference",
        0.9,
        BoundingBox(20.0, 20.0, 100.0, 80.0),
        None,
        Transform.planar(0.0, 0.0, 0.88, 0.0),
        Vector3(1e-5, 1e-5, 1e-5),
        1e-4,
        1.0,
        0.9,
        ObservationSource.SEGMENTATION,
    )


def _proposal(index: int, local_x_m: float) -> VisionGraspProposal:
    return VisionGraspProposal(
        f"candidate-{index}",
        "track-1",
        "mask_pca_clearance_v2",
        GraspClass.LONGITUDINAL,
        60.0 + 10.0 * index,
        50.0,
        Transform.planar(local_x_m, 0.0, 0.88, 0.0),
        Transform.planar(local_x_m, 0.0, 0.07, 0.0),
        0.0,
        Vector3(0.0, 0.0, -1.0),
        0.12,
        0.03,
        0.04,
        0.8,
        0.85,
    )


def _write_model(path: Path, local_x_weight: float) -> None:
    heads = {}
    for outcome in OUTCOME_NAMES:
        weights = [0.0] * len(FEATURE_NAMES)
        if outcome in {"retained_lift_probability", "delivery_probability"}:
            weights[0] = local_x_weight
        heads[outcome] = {
            "bias": 0.9 if outcome not in {"slip_probability", "excessive_contact_probability"} else 0.05,
            "weights": weights,
        }
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "model_family": "carve_grasp_affordance_ridge_v1",
                "feature_names": list(FEATURE_NAMES),
                "outcome_names": list(OUTCOME_NAMES),
                "normalization": {"mean": [0.0] * len(FEATURE_NAMES), "scale": [0.1] * len(FEATURE_NAMES)},
                "heads": heads,
            }
        ),
        encoding="utf-8",
    )


def test_learned_ranker_selects_from_safe_proposals_deterministically(tmp_path: Path) -> None:
    model_path = tmp_path / "model.json"
    _write_model(model_path, -0.5)
    proposals = (_proposal(0, 0.0), _proposal(1, 0.03), _proposal(2, -0.04))
    first = rank_grasp_candidates(proposals=proposals, observation=_observation(), model_path=model_path)
    second = rank_grasp_candidates(proposals=proposals, observation=_observation(), model_path=model_path)
    assert first.mode == "learned"
    assert not first.fallback_used
    assert first.selected.proposal_id == "candidate-0"
    assert first.selected.grasp_point_u_px in {item.grasp_point_u_px for item in proposals}
    assert first.to_dict() == second.to_dict()
    assert {item.rank for item in first.candidates} == {0, 1, 2}


def test_corrupt_model_falls_back_to_geometric_first_candidate(tmp_path: Path) -> None:
    model_path = tmp_path / "model.json"
    model_path.write_text("not json", encoding="utf-8")
    proposals = (_proposal(0, 0.0), _proposal(1, 0.03), _proposal(2, -0.04))
    decision = rank_grasp_candidates(proposals=proposals, observation=_observation(), model_path=model_path)
    assert decision.mode == "geometric_fallback"
    assert decision.fallback_used
    assert decision.selected is proposals[0]
    assert "JSONDecodeError" in decision.fallback_reason


def test_low_score_margin_falls_back_without_promoting_another_target(tmp_path: Path) -> None:
    model_path = tmp_path / "model.json"
    _write_model(model_path, 0.0)
    proposals = (_proposal(0, 0.0), _proposal(1, 0.03), _proposal(2, -0.04))
    decision = rank_grasp_candidates(
        proposals=proposals,
        observation=_observation(),
        model_path=model_path,
        minimum_score_margin=0.01,
    )
    assert decision.fallback_used
    assert decision.fallback_reason == "learned_score_margin_below_threshold"
    assert decision.selected is proposals[0]
