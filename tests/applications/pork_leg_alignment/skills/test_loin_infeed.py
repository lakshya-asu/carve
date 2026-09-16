"""The leg's grasp and turn skills on a loin, with only the station and the target changed.

What is pinned: the centre-of-gravity station lands where the centreline passes nearest the
centre of gravity; the infeed target's datum point is the bone edge there and its heading is
the fixture's; the same `SelectShankGrasp`, `AcquireShank` and `RotateOnBelt` run on a loin
through `run_skill`, so the fit check's verdict on the derived loin is a measured number, not a
crash; and a loin narrow enough for the jaw goes through the whole chain to a scored alignment.
"""

import math

import numpy as np
import pytest

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.infeed_fixture import InfeedFixtureConfig, InfeedOutcome
from applications.pork_leg_alignment.sim.loin import LoinConfig
from applications.pork_leg_alignment.sim.scene import ArmMount, CellConfig
from applications.pork_leg_alignment.skills import (
    INFEED_TARGET,
    AcquireShank,
    EstimateLoinFromGroundTruth,
    LoinEstimate,
    RotateOnBelt,
    SelectShankGrasp,
    centre_of_gravity_station,
)
from applications.pork_leg_alignment.skills.loin_estimate import estimate_loin_from_ground_truth
from applications.pork_leg_alignment.skills.shank_grasp import OPEN_MARGIN_M
from robotics.core.skill_library import PRECONDITION_FAILED, SUCCESS, run_skill
from robotics.hardware.arms import ArmModel
from robotics.hardware.grippers import GripperModel

BELT_SPEED_MPS = 0.30
FIXTURE_X_M = 1.95
# The leg runner's square-set layout for the UR20.
UR20_MOUNT = ArmMount(x_m=0.0, y_m=1.10, z_m=0.90, yaw_rad=-math.pi / 2)


def _loin_cell(loin: LoinConfig, belt_speed_mps: float = BELT_SPEED_MPS) -> Cell:
    return Cell(
        CellConfig(
            belt_speed_mps=belt_speed_mps,
            belt_half_length_m=2.5,
            loin=loin,
            infeed_fixture=InfeedFixtureConfig(x_m=FIXTURE_X_M),
            arm=ArmModel.UR20,
            arm_mount=UR20_MOUNT,
            gripper=GripperModel.JAW_GEH6180,
        )
    )


def test_the_station_is_where_the_centreline_passes_nearest_the_centre_of_gravity() -> None:
    centreline = np.column_stack([np.linspace(0.0, 1.0, 11), np.zeros(11), np.zeros(11)])
    estimate = LoinEstimate(
        centreline_m=centreline,
        widths_m=np.full(11, 0.2),
        heading_rad=0.0,
        centre_of_gravity_m=np.array([0.43, 0.05, 0.0]),
        belt_travel_m=0.0,
        source="test",
        bone_side=1.0,
    )
    assert centre_of_gravity_station(estimate) == pytest.approx(0.43, abs=1e-9)


def test_the_datum_point_is_the_bone_edge_at_the_station_and_the_heading_faces_the_datum() -> None:
    with _loin_cell(LoinConfig(bone_on_left=True), belt_speed_mps=0.0) as cell:
        cell.reset()
        cell.place_product(0.30, 0.50, math.radians(30.0), settle_s=0.2)
        estimate = estimate_loin_from_ground_truth(cell)
        station = centre_of_gravity_station(estimate)
        point = INFEED_TARGET.datum_point(estimate)
        # Half the width to the left of the heading, at the station.
        expected = estimate.point_at(station) + 0.5 * estimate.width_at(station) * np.array(
            [-math.sin(estimate.heading_rad), math.cos(estimate.heading_rad), 0.0]
        )
        assert np.allclose(point, expected)
        assert cell.infeed_fixture is not None
        # The datum stands on the +y side and the bone on the left: heading 0 lays the bone toward it.
        assert cell.infeed_fixture.datum_side == 1.0
        assert INFEED_TARGET.heading_rad(cell, estimate) == 0.0
        assert INFEED_TARGET.datum_y_m(cell) == cell.infeed_fixture.config.datum_y_m
        # Inboard is -y here, so a point short of the datum reads positive.
        assert INFEED_TARGET.datum_offset_m(cell, cell.infeed_fixture.config.datum_y_m - 0.02) == pytest.approx(0.02)


def test_the_target_refuses_an_estimate_without_a_bone_side() -> None:
    from applications.pork_leg_alignment.skills import LegEstimate

    estimate = LegEstimate(
        centreline_m=np.zeros((3, 3)),
        widths_m=np.ones(3),
        heading_rad=0.0,
        centre_of_gravity_m=np.zeros(3),
        belt_travel_m=0.0,
        source="test",
    )
    with pytest.raises(TypeError, match="bone side"):
        INFEED_TARGET.datum_point(estimate)


def test_the_derived_loin_is_wider_than_the_jaw_leaves_room_for_and_the_fit_check_says_so() -> None:
    """The measured answer to Section 14.2's question, on the cutout-derived loin: refused before any motion."""
    with _loin_cell(LoinConfig(), belt_speed_mps=0.0) as cell:
        cell.reset()
        cell.place_product(0.30, 0.50, 0.0, settle_s=0.2)
        estimated = run_skill(EstimateLoinFromGroundTruth(), cell, {})
        selected = run_skill(SelectShankGrasp(station=centre_of_gravity_station), cell, estimated.outputs)
        assert selected.outcome == SUCCESS
        grasp = selected.outputs["shank_grasp"]
        assert grasp.widest_under_pads_m > cell.gripper_geometry.max_opening_m - 2 * OPEN_MARGIN_M
        acquired = run_skill(AcquireShank(), cell, selected.outputs)
        assert acquired.outcome == PRECONDITION_FAILED
        assert acquired.evidence["jaw_spare_m"] < 2 * OPEN_MARGIN_M


@pytest.mark.parametrize("bone_on_left", [True, False], ids=["bone_left", "bone_right"])
def test_a_loin_the_jaw_fits_is_gripped_turned_to_the_datum_and_scored_by_the_fixture(bone_on_left: bool) -> None:
    """The whole chain on a narrow loin: the same skills, the loin's station and target, the fixture's verdict."""
    narrow = LoinConfig(width_scale=0.60, bone_on_left=bone_on_left)
    with _loin_cell(narrow) as cell:
        cell.reset()
        assert cell.infeed_fixture is not None
        target_heading = cell.infeed_fixture.target_heading_rad
        cell.place_product(-0.30, 0.50, target_heading + math.radians(25.0), settle_s=0.3)
        estimated = run_skill(EstimateLoinFromGroundTruth(), cell, {})
        selected = run_skill(SelectShankGrasp(station=centre_of_gravity_station), cell, estimated.outputs)
        assert selected.outcome == SUCCESS
        acquired = run_skill(AcquireShank(), cell, selected.outputs)
        assert acquired.outcome == SUCCESS, f"{acquired.outcome}: {dict(acquired.evidence)}"
        planning = run_skill(EstimateLoinFromGroundTruth(), cell, {}).outputs["leg_estimate"]
        oriented = run_skill(
            RotateOnBelt(target=INFEED_TARGET),
            cell,
            {
                "leg_estimate": planning,
                "re_estimate": lambda: estimate_loin_from_ground_truth(cell),
                **selected.outputs,
                **acquired.outputs,
            },
        )
        assert oriented.outcome == SUCCESS, f"{oriented.outcome}: {dict(oriented.evidence)}"
        alignment = oriented.outputs["alignment"]
        assert abs(alignment.datum_offset_m) < 0.010
        assert abs(alignment.heading_error_rad) < math.radians(5.0)
        assert alignment.released_at_x_m < FIXTURE_X_M
        cell.open_gripper(cell.gripper_geometry.max_opening_m)
        deadline = cell.time_s + 15.0
        while cell.infeed_result is None and cell.time_s < deadline:
            cell.step(seconds=0.02)
        result = cell.infeed_result
        assert result is not None and result.outcome is InfeedOutcome.CROSSED
        assert abs(result.offset_m) < 0.010, f"bone edge {1000 * result.offset_m:+.1f} mm from the datum"
        assert abs(math.degrees(result.angle_rad)) < 5.0
        # The skill's own reading and the fixture's agree on the same point.
        assert result.offset_m == pytest.approx(alignment.datum_offset_m, abs=0.004)


def test_the_turn_refuses_a_cell_with_no_fixture_for_the_infeed_target() -> None:
    from applications.pork_leg_alignment.skills import ShankGrasp
    from applications.pork_leg_alignment.skills.shank_grasp import LiftProof

    with Cell(CellConfig(loin=LoinConfig(), arm=ArmModel.UR20, gripper=GripperModel.JAW_GEH6180)) as cell:
        cell.reset()
        cell.place_product(0.30, 0.50, 0.0, settle_s=0.1)
        estimate = estimate_loin_from_ground_truth(cell)
        grasp = ShankGrasp(np.array([0.3, 0.5, 0.95]), 0.0, 0.1, 0.1, 0.5)
        result = run_skill(
            RotateOnBelt(target=INFEED_TARGET),
            cell,
            {"leg_estimate": estimate, "shank_grasp": grasp, "lift_proof": LiftProof(0.95, 0.95)},
        )
        assert result.outcome == PRECONDITION_FAILED
        assert result.evidence["datum_present"] == 0.0
