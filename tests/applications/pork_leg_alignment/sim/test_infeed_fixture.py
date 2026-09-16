"""The infeed fixture is what the loin's alignment is scored against, so its reading must be the pose.

A loin reaches the fixture's plane with its bone edge somewhere relative to
the datum line and at some heading. The fixture must report exactly that as
an offset and a heading error, for either bone side, and must not touch the
piece. If its arithmetic is wrong, every loin result scored against it is
wrong with it, as the saw's tests say of the saw.
"""

import math

import numpy as np
import pytest

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.hold_down import HoldDownConfig
from applications.pork_leg_alignment.sim.infeed_fixture import (
    InfeedFixtureConfig,
    InfeedOutcome,
    target_heading_rad,
)
from applications.pork_leg_alignment.sim.loin import LoinConfig
from applications.pork_leg_alignment.sim.product import LegConfig
from applications.pork_leg_alignment.sim.saw import SawConfig
from applications.pork_leg_alignment.sim.scene import CellConfig

BELT_SPEED_MPS = 0.30
START_BEFORE_PLANE_M = 0.6


@pytest.fixture(scope="module", params=[False, True], ids=["bone_right", "bone_left"])
def fixture_cell(request):
    config = CellConfig(
        belt_speed_mps=BELT_SPEED_MPS, loin=LoinConfig(bone_on_left=request.param), infeed_fixture=InfeedFixtureConfig()
    )
    with Cell(config) as cell:
        yield cell


def _bone_edge_offset_body(cell: Cell) -> float:
    """Body-frame y of the bone edge at the centre of gravity: where to put the piece so it lies on the datum."""
    assert cell.infeed_fixture is not None and cell.config.loin is not None
    body = cell.model.body("slab").id
    fraction = float(cell.model.body_ipos[body][0]) / cell.config.loin.length_m + 0.5
    return float(cell.config.loin.bone_edge_m(np.array([fraction]))[0, 1])


def _place_along(cell: Cell, inboard_m: float = 0.0, off_square_rad: float = 0.0) -> None:
    """Loin along the belt at its target heading, bone edge `inboard_m` short of the datum, turned `off_square_rad`."""
    fixture = cell.infeed_fixture
    assert fixture is not None
    heading = fixture.target_heading_rad + off_square_rad
    # At the target heading the body's y axis points at the datum or away from it by the bone side.
    edge_y = _bone_edge_offset_body(cell) * math.cos(fixture.target_heading_rad)
    y = fixture.config.datum_y_m - edge_y - fixture.datum_side * inboard_m
    cell.reset()
    cell.place_product(fixture.config.x_m - START_BEFORE_PLANE_M, y, heading)


def _run_until_decided(cell: Cell, timeout_s: float) -> None:
    deadline = cell.time_s + timeout_s
    while cell.infeed_result is None and cell.time_s < deadline:
        cell.step(seconds=0.02)


def test_the_target_heading_lays_the_bone_edge_toward_the_datum() -> None:
    assert target_heading_rad(bone_side=1.0, datum_side=1.0) == 0.0
    assert target_heading_rad(bone_side=-1.0, datum_side=1.0) == math.pi
    assert target_heading_rad(bone_side=1.0, datum_side=-1.0) == math.pi
    assert target_heading_rad(bone_side=-1.0, datum_side=-1.0) == 0.0


def test_a_loin_on_the_datum_and_square_scores_zero(fixture_cell) -> None:
    _place_along(fixture_cell)
    _run_until_decided(fixture_cell, timeout_s=6.0)
    result = fixture_cell.infeed_result
    assert result is not None and result.outcome is InfeedOutcome.CROSSED
    assert abs(result.offset_m) < 0.003, f"bone edge {1000 * result.offset_m:+.1f} mm from the datum"
    assert abs(result.offset_at_exit_m - result.offset_m) < 0.003
    assert abs(math.degrees(result.angle_rad)) < 1.0
    assert abs(math.degrees(result.yaw_drift_rad)) < 1.0
    assert result.slip_m < 0.005
    assert fixture_cell.config.loin is not None
    crossing_s = result.through_s - result.time_s
    assert crossing_s == pytest.approx(fixture_cell.config.loin.length_m / BELT_SPEED_MPS, rel=0.05)


def test_a_loin_short_of_the_datum_reports_a_positive_inboard_offset(fixture_cell) -> None:
    _place_along(fixture_cell, inboard_m=0.040)
    _run_until_decided(fixture_cell, timeout_s=6.0)
    result = fixture_cell.infeed_result
    assert result is not None and result.outcome is InfeedOutcome.CROSSED
    assert result.offset_m == pytest.approx(0.040, abs=0.004)


def test_a_loin_turned_off_square_reports_the_heading_error(fixture_cell) -> None:
    # Placed 100 mm inboard: a piece turned 20 degrees with its bone edge on the
    # datum would swing its far corner into the rail and be shoved on placement.
    _place_along(fixture_cell, inboard_m=0.100, off_square_rad=math.radians(20.0))
    _run_until_decided(fixture_cell, timeout_s=6.0)
    result = fixture_cell.infeed_result
    assert result is not None and result.outcome is InfeedOutcome.CROSSED
    assert math.degrees(result.angle_rad) == pytest.approx(20.0, abs=1.5)


def test_a_loin_the_wrong_way_round_is_half_a_turn_off(fixture_cell) -> None:
    """Bone edge away from the datum: the heading is the other way, and the fixture says so."""
    _place_along(fixture_cell, off_square_rad=math.pi)
    _run_until_decided(fixture_cell, timeout_s=6.0)
    result = fixture_cell.infeed_result
    assert result is not None and result.outcome is InfeedOutcome.CROSSED
    assert abs(math.degrees(result.angle_rad)) == pytest.approx(180.0, abs=1.5)


def test_nothing_is_read_until_the_leading_end_reaches_the_plane(fixture_cell) -> None:
    _place_along(fixture_cell)
    assert fixture_cell.infeed_fixture is not None
    fixture_cell.step(seconds=0.3)
    assert not fixture_cell.infeed_fixture.crossing and fixture_cell.infeed_result is None


def test_the_fixture_does_not_touch_the_piece(fixture_cell) -> None:
    """A guide that corrected the pose by contact would hide the error the station exists to remove."""
    model = fixture_cell.model
    for name in ("infeed_guide", "infeed_plane"):
        geom = model.geom(name).id
        assert model.geom_contype[geom] == 0 and model.geom_conaffinity[geom] == 0


def test_the_release_deadline_is_the_fixture_plane_for_the_loin_and_the_ramp_for_the_leg(fixture_cell) -> None:
    assert fixture_cell.infeed_fixture is not None
    assert fixture_cell.release_before_x_m == fixture_cell.infeed_fixture.config.x_m
    leg_config = CellConfig(leg=LegConfig(), saw=SawConfig(x_m=1.5), hold_down=HoldDownConfig(x_centre_m=1.5))
    with Cell(leg_config) as leg_cell:
        assert leg_cell.hold_down is not None
        assert leg_cell.release_before_x_m == leg_cell.hold_down.config.entry_x_m
    with Cell(CellConfig()) as slab_cell:
        assert slab_cell.release_before_x_m is None


def test_the_cell_reads_either_product_centreline_in_the_world(fixture_cell) -> None:
    fixture_cell.reset()
    fixture_cell.place_product(0.20, 0.55, math.radians(30.0))
    fractions = np.array([0.0, 0.5, 1.0])
    points = fixture_cell.product_centreline_world(fractions)
    assert fixture_cell.config.loin is not None
    body = fixture_cell.model.body("slab").id
    expected = fixture_cell.data.xpos[body] + fixture_cell.config.loin.centreline_m(fractions) @ (
        fixture_cell.data.xmat[body].reshape(3, 3).T
    )
    assert np.allclose(points, expected)
    with Cell(CellConfig()) as slab_cell, pytest.raises(ValueError, match="slab"):
        slab_cell.product_centreline_world(fractions)


def test_a_fixture_without_a_loin_is_refused() -> None:
    with pytest.raises(ValueError, match="no loin"):
        CellConfig(infeed_fixture=InfeedFixtureConfig())
    with pytest.raises(ValueError, match="no loin"):
        CellConfig(leg=LegConfig(), infeed_fixture=InfeedFixtureConfig())
