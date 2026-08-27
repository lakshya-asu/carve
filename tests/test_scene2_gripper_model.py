import pytest

from isaac_sim.scene2_builder import (
    GRIPPER_COMPLIANCE_M_PER_N,
    GRIPPER_FINGER_OPEN_Y_M,
    GRIPPER_GRASP_CENTER_FLANGE_M,
    GRIPPER_NORMAL_FORCE_SETPOINT_N,
    GRIPPER_OPEN_INNER_GAP_M,
    GRIPPER_PAD_HEIGHT_M,
    GRIPPER_PAD_INWARD_OFFSET_M,
    GRIPPER_PAD_LENGTH_M,
    GRIPPER_PAD_THICKNESS_M,
    gripper_open_inner_gap_m,
    gripper_target_travel_m,
)


def test_nominal_target_adds_configured_compliance_after_contact() -> None:
    width_m = 0.14
    contact_travel = (GRIPPER_OPEN_INNER_GAP_M - width_m) / 2.0
    expected_deflection = GRIPPER_NORMAL_FORCE_SETPOINT_N * GRIPPER_COMPLIANCE_M_PER_N
    assert gripper_target_travel_m(width_m) == pytest.approx(contact_travel + expected_deflection)


def test_pad_geometry_produces_the_declared_opening() -> None:
    expected = 2.0 * (
        GRIPPER_FINGER_OPEN_Y_M
        - GRIPPER_PAD_INWARD_OFFSET_M
        - GRIPPER_PAD_THICKNESS_M / 2.0
    )
    assert gripper_open_inner_gap_m() == pytest.approx(expected)
    assert gripper_open_inner_gap_m() == pytest.approx(GRIPPER_OPEN_INNER_GAP_M)


def test_contact_pads_are_compact_and_cover_the_nominal_pork_cross_section() -> None:
    assert 0.13 <= GRIPPER_PAD_LENGTH_M <= 0.15
    assert 0.09 <= GRIPPER_PAD_HEIGHT_M <= 0.11


def test_gripper_is_sized_for_nominal_recipes_without_excessive_overhang() -> None:
    assert 0.20 < GRIPPER_OPEN_INNER_GAP_M <= 0.23
    assert GRIPPER_GRASP_CENTER_FLANGE_M[0] <= 0.36


@pytest.mark.parametrize("width_m", [0.0, -0.1, GRIPPER_OPEN_INNER_GAP_M, 0.4])
def test_invalid_product_width_is_rejected(width_m: float) -> None:
    with pytest.raises(ValueError, match="Product width"):
        gripper_target_travel_m(width_m)
