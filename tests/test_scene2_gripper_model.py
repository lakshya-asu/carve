import pytest

from isaac_sim.scene2_builder import (
    GRIPPER_COMPLIANCE_M_PER_N,
    GRIPPER_NORMAL_FORCE_SETPOINT_N,
    GRIPPER_OPEN_INNER_GAP_M,
    gripper_target_travel_m,
)


def test_nominal_target_adds_configured_compliance_after_contact() -> None:
    width_m = 0.14
    contact_travel = (GRIPPER_OPEN_INNER_GAP_M - width_m) / 2.0
    expected_deflection = GRIPPER_NORMAL_FORCE_SETPOINT_N * GRIPPER_COMPLIANCE_M_PER_N
    assert gripper_target_travel_m(width_m) == pytest.approx(contact_travel + expected_deflection)


@pytest.mark.parametrize("width_m", [0.0, -0.1, GRIPPER_OPEN_INNER_GAP_M, 0.4])
def test_invalid_product_width_is_rejected(width_m: float) -> None:
    with pytest.raises(ValueError, match="Product width"):
        gripper_target_travel_m(width_m)
