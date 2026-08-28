from meatcell.grasp_affordance import GraspAffordanceModel
from tools.evaluate_grasp_affordance import evaluate


def _model() -> GraspAffordanceModel:
    names = (
        "local_x_abs_m",
        "local_y_abs_m",
        "boundary_clearance_m",
        "capture_margin_m",
        "estimated_width_m",
        "proposal_quality",
        "proposal_confidence",
        "observation_confidence",
    )
    outcomes = (
        "contact_probability",
        "retained_lift_probability",
        "slip_probability",
        "excessive_contact_probability",
        "delivery_probability",
    )
    heads = {
        name: {"bias": 0.0 if "probability" in name else 0.0, "weights": [0.0] * 8}
        for name in outcomes
    }
    heads["contact_probability"]["bias"] = 1.0
    heads["retained_lift_probability"]["weights"][0] = -1.0
    heads["delivery_probability"]["bias"] = 1.0
    return GraspAffordanceModel(
        {
            "schema_version": 1,
            "model_family": "carve_grasp_affordance_ridge_v1",
            "feature_names": list(names),
            "outcome_names": list(outcomes),
            "normalization": {"mean": [0.0] * 8, "scale": [1.0] * 8},
            "heads": heads,
        },
        "test-hash",
    )


def test_held_out_evaluation_compares_selection_to_baseline_and_oracle() -> None:
    rows = []
    for candidate_index in range(5):
        utility = 1.0 - 0.1 * candidate_index
        rows.append(
            {
                "split": "held_out",
                "trial_group_id": "held-1",
                "candidate_index": candidate_index,
                "features": {
                    "local_x_abs_m": 0.1 * candidate_index,
                    "local_y_abs_m": 0.0,
                    "boundary_clearance_m": 0.03,
                    "capture_margin_m": 0.04,
                    "estimated_width_m": 0.12,
                    "proposal_quality": 0.8,
                    "proposal_confidence": 0.9,
                    "observation_confidence": 0.9,
                },
                "outcomes": {
                    "contact_probability": 1.0,
                    "retained_lift_probability": utility,
                    "slip_probability": 0.0,
                    "excessive_contact_probability": 0.0,
                    "delivery_probability": 1.0,
                },
                "raw_outcomes": {
                    "collision_violations": 0,
                    "joint_limit_violations": 0,
                    "velocity_limit_violations": 0,
                    "acceleration_limit_violations": 0,
                },
            }
        )
    summary = evaluate(rows, _model())
    assert summary["passed"]
    assert summary["groups"][0]["selected_candidate_index"] == 0
    assert summary["groups"][0]["oracle_candidate_index"] == 0
    assert summary["mean_regret"] == 0.0
