"""The blade pushes back on the leg, and the hold-down belt is what holds it still.

These pin the mechanics: the top belt floats at its clearance until a leg lifts
it, presses that leg with at least its set force, carries it at belt speed
rather than braking it, and does not disturb the arm's control indices. How
much the hold-down reduces a cut's error is a measurement, not a test; see
scripts/measure_hold_down.py.
"""

import math

import mujoco
import pytest

from meat_cell_sim.cell import Cell
from meat_cell_sim.holddown import HOLD_DOWN_DRIVE, HOLD_DOWN_PRESS, HoldDownConfig
from meat_cell_sim.product import PRODUCT_BODY, LegConfig
from meat_cell_sim.saw import CutOutcome, SawConfig
from meat_cell_sim.scene import CellConfig

BELT_SPEED_MPS = 0.30
START_BEFORE_BLADE_M = 0.80


@pytest.fixture(scope="module")
def held_cell():
    config = CellConfig(belt_speed_mps=BELT_SPEED_MPS, leg=LegConfig(), saw=SawConfig(), hold_down=HoldDownConfig())
    with Cell(config) as cell:
        yield cell


def _place_across(cell: Cell) -> None:
    assert cell.saw is not None and cell.config.leg is not None
    cell.reset()
    cell.place_product(
        cell.saw.config.x_m - START_BEFORE_BLADE_M,
        cell.saw.blade_y_m + cell.config.leg.hock_offset_m,
        -math.pi / 2,
    )


def _ride_until_under_the_top_belt(cell: Cell) -> None:
    assert cell.config.hold_down is not None
    target_x = cell.config.hold_down.x_centre_m - 0.25
    deadline = cell.time_s + 4.0
    while cell.product_x_m < target_x and cell.time_s < deadline:
        cell.step(seconds=0.02)
    assert cell.product_x_m >= target_x, "the leg never reached the top belt"


def test_the_top_belt_rests_at_its_clearance_with_nothing_under_it(held_cell) -> None:
    assert held_cell.hold_down is not None
    held_cell.reset()
    held_cell.place_product(-1.2, 0.50, 0.0)
    held_cell.step(seconds=0.5)
    assert held_cell.hold_down.lift_m(held_cell.data) < 0.002


def test_a_leg_lifts_the_top_belt_and_is_pressed_with_at_least_the_set_force(held_cell) -> None:
    assert held_cell.hold_down is not None and held_cell.config.hold_down is not None
    _place_across(held_cell)
    _ride_until_under_the_top_belt(held_cell)
    ham = mujoco.mj_name2id(held_cell.model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
    assert held_cell.hold_down.lift_m(held_cell.data) > 0.03, "the ham did not lift the top belt"
    force = held_cell.hold_down.force_on_body_n(held_cell.model, held_cell.data, ham)
    assert force > held_cell.config.hold_down.press_force_n, f"pressing with only {force:.0f} N"


def test_a_pressed_leg_still_travels_at_belt_speed(held_cell) -> None:
    _place_across(held_cell)
    _ride_until_under_the_top_belt(held_cell)
    start_x, start_t = held_cell.product_x_m, held_cell.time_s
    held_cell.step(seconds=0.3)
    speed = (held_cell.product_x_m - start_x) / (held_cell.time_s - start_t)
    assert speed == pytest.approx(BELT_SPEED_MPS, rel=0.10), f"the top belt drags the leg to {speed:.3f} m/s"


def test_the_hold_down_actuators_come_after_the_arm_and_gripper(held_cell) -> None:
    """The arm's controls are addressed by index; new actuators must not shift them."""
    model = held_cell.model
    assert mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, HOLD_DOWN_DRIVE) == model.nu - 2
    assert mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, HOLD_DOWN_PRESS) == model.nu - 1
    assert mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "g_grip") == 7


def test_an_unheld_leg_moves_under_the_blade_and_the_cut_reports_it() -> None:
    """Without a hold-down, the blade's push shows up in the cut result."""
    config = CellConfig(belt_speed_mps=BELT_SPEED_MPS, leg=LegConfig(), saw=SawConfig(feed_resistance_n=60.0))
    with Cell(config) as cell:
        _place_across(cell)
        deadline = cell.time_s + 6.0
        while cell.cut_result is None and cell.time_s < deadline:
            cell.step(seconds=0.02)
        result = cell.cut_result
    assert result is not None and result.outcome in (CutOutcome.CUT, CutOutcome.STALLED)
    assert result.slip_m > 0.001 or abs(math.degrees(result.yaw_drift_rad)) > 0.2
