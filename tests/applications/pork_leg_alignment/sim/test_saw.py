"""The saw is what alignment is for, so the cut has to land where the leg puts it.

A leg arrives with its hock joint somewhere relative to the blade plane and at
some angle to it. The saw must report exactly that geometry as a cut offset and
a cut angle, separate the trotter when it cuts, and leave the trotter on when
the blade never reaches it. If the saw's arithmetic is wrong, every alignment
result scored against it is wrong with it.
"""

import math

import mujoco
import numpy as np
import pytest

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import TROTTER_BODY, LegConfig
from applications.pork_leg_alignment.sim.saw import CutOutcome, SawConfig
from applications.pork_leg_alignment.sim.scene import CellConfig

BELT_SPEED_MPS = 0.30
BELT_TOP_Z_M = 0.90
START_BEFORE_BLADE_M = 0.6


@pytest.fixture(scope="module")
def saw_cell():
    # No feed resistance: these tests pin the cut geometry, not how the leg
    # reacts to the blade's push. That is in test_hold_down.py.
    config = CellConfig(belt_speed_mps=BELT_SPEED_MPS, leg=LegConfig(), saw=SawConfig(feed_resistance_n=0.0))
    with Cell(config) as cell:
        yield cell


def _place_across(cell: Cell, inboard_m: float = 0.0, yaw_off_square_rad: float = 0.0) -> None:
    """Leg across the belt, trotter pointing out over the open edge, hock `inboard_m` inside the blade."""
    assert cell.saw is not None and cell.config.leg is not None
    cell.reset()
    cell.place_product(
        cell.saw.config.x_m - START_BEFORE_BLADE_M,
        cell.saw.blade_y_m + cell.config.leg.hock_offset_m + inboard_m,
        -math.pi / 2 + yaw_off_square_rad,
    )


def _run_until_decided(cell: Cell, timeout_s: float) -> None:
    deadline = cell.time_s + timeout_s
    while cell.cut_result is None and cell.time_s < deadline:
        cell.step(seconds=0.02)


def _trotter_z(cell: Cell) -> float:
    return float(cell.data.xpos[mujoco.mj_name2id(cell.model, mujoco.mjtObj.mjOBJ_BODY, TROTTER_BODY)][2])


def test_a_leg_with_its_hock_on_the_blade_is_cut_at_the_joint(saw_cell) -> None:
    _place_across(saw_cell)
    _run_until_decided(saw_cell, timeout_s=4.0)
    result = saw_cell.cut_result
    assert result is not None and result.outcome is CutOutcome.CUT
    assert abs(result.offset_from_hock_m) < 0.005, f"cut {1000 * result.offset_from_hock_m:+.1f} mm from the hock"
    assert abs(math.degrees(result.angle_rad)) < 1.0


def test_the_trotter_falls_away_once_cut(saw_cell) -> None:
    _place_across(saw_cell)
    _run_until_decided(saw_cell, timeout_s=4.0)
    assert saw_cell.cut_result is not None and saw_cell.cut_result.outcome is CutOutcome.CUT
    saw_cell.step(seconds=1.0)
    assert _trotter_z(saw_cell) < BELT_TOP_Z_M - 0.10, "the trotter is still at belt height after the cut"


def test_a_leg_too_far_onto_the_belt_is_cut_toward_the_tip(saw_cell) -> None:
    """The offset carries the sign that says which way the leg must move."""
    _place_across(saw_cell, inboard_m=0.040)
    _run_until_decided(saw_cell, timeout_s=4.0)
    result = saw_cell.cut_result
    assert result is not None and result.outcome is CutOutcome.CUT
    assert result.offset_from_hock_m == pytest.approx(0.040, abs=0.005)


def test_a_leg_turned_off_square_reports_the_cut_angle(saw_cell) -> None:
    _place_across(saw_cell, yaw_off_square_rad=math.radians(20.0))
    _run_until_decided(saw_cell, timeout_s=4.0)
    result = saw_cell.cut_result
    assert result is not None and result.outcome is CutOutcome.CUT
    assert math.degrees(result.angle_rad) == pytest.approx(20.0, abs=1.5)


def test_a_leg_lying_along_the_belt_keeps_its_trotter(saw_cell) -> None:
    assert saw_cell.saw is not None
    saw_cell.reset()
    saw_cell.place_product(saw_cell.saw.config.x_m - START_BEFORE_BLADE_M, 0.50, 0.0)
    _run_until_decided(saw_cell, timeout_s=4.0)
    result = saw_cell.cut_result
    assert result is not None and result.outcome is CutOutcome.TROTTER_NOT_OVER_BLADE
    assert math.isnan(result.offset_from_hock_m)
    assert _trotter_z(saw_cell) > BELT_TOP_Z_M - 0.02, "the trotter came off without a cut"


def test_the_weld_holds_the_trotter_on_while_the_leg_rides_the_belt(saw_cell) -> None:
    """Before the saw, the two bodies must travel as one leg."""
    _place_across(saw_cell)
    saw_cell.step(seconds=0.8)
    assert saw_cell.cut_result is None
    ham = mujoco.mj_name2id(saw_cell.model, mujoco.mjtObj.mjOBJ_BODY, "slab")
    trotter = mujoco.mj_name2id(saw_cell.model, mujoco.mjtObj.mjOBJ_BODY, TROTTER_BODY)
    gap = float(np.linalg.norm(saw_cell.data.xpos[ham] - saw_cell.data.xpos[trotter]))
    assert gap < 0.002, f"the trotter has drifted {1000 * gap:.1f} mm from the ham"


def test_nothing_is_cut_until_the_leg_surface_meets_the_blade(saw_cell) -> None:
    """The cut is the blade's surface meeting the leg's, not the leg reaching a line.

    With the belt stopped and the shank 5 mm short of the blade, the leg stays
    whole indefinitely. Start the belt and it is cut within the time 5 mm takes.
    """
    assert saw_cell.saw is not None and saw_cell.config.leg is not None
    saw = saw_cell.saw
    model, data = saw_cell.model, saw_cell.data
    disc = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "saw_disc")
    trotter = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "trotter_geom")
    x_m = saw.config.x_m - START_BEFORE_BLADE_M
    y_m = saw.blade_y_m + saw_cell.config.leg.hock_offset_m
    saw_cell.reset(belt_speed_mps=0.0)
    saw_cell.place_product(x_m, y_m, -math.pi / 2)
    # The leg moves along +x only, so the gap along x is the gap to close.
    far_gap = mujoco.mj_geomDistance(model, data, disc, trotter, 1.0, None)
    saw_cell.place_product(x_m + far_gap - 0.005, y_m, -math.pi / 2)
    gap = saw.blade_gap_m(model, data)
    assert 0.003 < gap < 0.007, f"setup: leg is {1000 * gap:.1f} mm from the blade"

    saw_cell.step(seconds=0.5)
    assert not saw.cutting and saw_cell.cut_result is None, "the leg was cut without touching the blade"

    saw_cell.data.ctrl[0] = BELT_SPEED_MPS
    deadline = saw_cell.time_s + 0.1
    while not saw.cutting and saw_cell.time_s < deadline:
        saw_cell.step()
    assert saw.cutting, "the blade did not enter within the time 5 mm of belt travel takes"
    _run_until_decided(saw_cell, timeout_s=1.0)
    result = saw_cell.cut_result
    assert result is not None and result.outcome is CutOutcome.CUT
    assert abs(result.offset_from_hock_m) < 0.005


def test_the_leg_is_drawn_whole_until_it_is_cut(saw_cell) -> None:
    """Ham and trotter meeting at the hock draw a seam that reads as an early cut."""
    from applications.pork_leg_alignment.sim.product import LEG_SKIN_GEOM, PRODUCT_GEOM, TROTTER_GEOM

    model = saw_cell.model
    alpha = {
        name: lambda name=name: float(model.geom_rgba[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name), 3])
        for name in (LEG_SKIN_GEOM, PRODUCT_GEOM, TROTTER_GEOM)
    }
    _place_across(saw_cell)
    assert (alpha[LEG_SKIN_GEOM](), alpha[PRODUCT_GEOM](), alpha[TROTTER_GEOM]()) == (1.0, 0.0, 0.0)
    _run_until_decided(saw_cell, timeout_s=4.0)
    assert saw_cell.cut_result is not None and saw_cell.cut_result.outcome is CutOutcome.CUT
    assert (alpha[LEG_SKIN_GEOM](), alpha[PRODUCT_GEOM](), alpha[TROTTER_GEOM]()) == (0.0, 1.0, 1.0)


def test_a_saw_without_a_leg_is_refused() -> None:
    with pytest.raises(ValueError, match="trotter"):
        CellConfig(saw=SawConfig())
