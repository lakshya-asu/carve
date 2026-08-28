import json
import math

import pytest

from meatcell.contact_skill import ContactSkillModel, ContactSkillObservation, FEATURE_ORDER


def _model(tmp_path):
    path = tmp_path / "model.json"
    path.write_text(
        json.dumps(
            {
                "feature_order": list(FEATURE_ORDER),
                "execution_policy": "shadow_only",
                "phases": {
                    "close": {
                        "weights": [0.35, 0, 0, 0, 0, 0],
                        "minimum": 0.30,
                        "maximum": 0.40,
                        "unit": "s",
                        "held_out_mae": 0.0,
                        "allowed_states": ["intercept"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return ContactSkillModel.load(path)


def _observation(**overrides):
    values = {
        "solution_b": False,
        "yaw_rad": 0.2,
        "product_width_m": 0.12,
        "contact_force_imbalance": 0.1,
        "slip_detected": False,
        "age_s": 0.02,
        "supervisor_state": "intercept",
        "plc_ready": True,
        "emergency_stop": False,
    }
    values.update(overrides)
    return ContactSkillObservation(**values)


def test_shadow_proposal_never_executes(tmp_path) -> None:
    proposal = _model(tmp_path).propose("close", _observation())

    assert proposal.accepted_by_shadow_gate is True
    assert proposal.executed is False
    assert proposal.value == pytest.approx(0.35)


@pytest.mark.parametrize(
    "override,reason",
    [
        ({"age_s": 0.2}, "stale"),
        ({"plc_ready": False}, "plc_blocked"),
        ({"emergency_stop": True}, "emergency_stop"),
        ({"supervisor_state": "idle"}, "state_blocked"),
    ],
)
def test_shadow_gate_fails_closed(tmp_path, override, reason) -> None:
    proposal = _model(tmp_path).propose("close", _observation(**override))

    assert proposal.accepted_by_shadow_gate is False
    assert proposal.fallback_reason == reason


def test_nonfinite_features_fail_closed(tmp_path) -> None:
    with pytest.raises(ValueError):
        _model(tmp_path).propose("close", _observation(yaw_rad=math.nan))
