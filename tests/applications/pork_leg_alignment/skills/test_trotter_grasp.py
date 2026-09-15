"""The three-finger gripper takes the trotter end-on, and only where it can.

Chosen by Lakshya on 2026-09-14. On the UR20, a leg whose trotter hangs past the
open edge must be gripped and lifted. A leg whose trotter lies on the belt must
be refused before the arm moves, because the lower fingers would strike the
belt. A SCARA must be refused because it cannot point its tool along the leg.
"""

import math

import numpy as np
import pytest

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import LegConfig
from applications.pork_leg_alignment.sim.scene import CellConfig
from applications.pork_leg_alignment.skills import AcquireTrotterEnd, SelectTrotterEndGrasp
from robotics.core.skill_library import PRECONDITION_FAILED, SUCCESS, run_skill
from robotics.hardware.arms import ArmModel
from robotics.hardware.grippers import GripperModel
from robotics.hardware.ik import tool_rotation_for_approach

BLADE_PLANE_Y_M = 0.12  # the saw's default: 30 mm outside the open edge at y = 0.15


def _grip(cell: Cell, leg_y_m: float):
    cell.reset()
    cell.place_product(0.30, leg_y_m, -math.pi / 2, settle_s=0.3)
    selected = run_skill(SelectTrotterEndGrasp(), cell, {})
    assert selected.outcome == SUCCESS
    return run_skill(AcquireTrotterEnd(), cell, selected.outputs)


@pytest.fixture(scope="module")
def ur20_three_finger():
    config = CellConfig(belt_speed_mps=0.0, leg=LegConfig(), arm=ArmModel.UR20, gripper=GripperModel.THREE_FINGER_3FG25)
    with Cell(config) as cell:
        yield cell


def test_the_ur20_grips_an_overhanging_trotter_end_on_and_lifts_it(ur20_three_finger) -> None:
    cell = ur20_three_finger
    assert cell.config.leg is not None
    result = _grip(cell, BLADE_PLANE_Y_M + cell.config.leg.hock_offset_m)
    assert result.outcome == SUCCESS, f"{result.outcome}: {dict(result.evidence)}"
    assert result.evidence["tool_rise_m"] > 0.0005
    assert abs(result.evidence["part_minus_tool_m"]) <= 0.001


def test_a_trotter_lying_on_the_belt_is_refused_before_the_arm_moves(ur20_three_finger) -> None:
    # y = 0.62 puts the ham butt at 0.82, clear of the far rail at 0.857, and the
    # trotter grasp point at 0.165, just over the belt's open edge at 0.15.
    cell = ur20_three_finger
    result = _grip(cell, 0.62)
    assert result.outcome == PRECONDITION_FAILED
    assert result.evidence["trotter_overhang_m"] < cell.gripper_geometry.max_opening_m / 2


def test_a_scara_is_refused_because_its_tool_cannot_tilt() -> None:
    config = CellConfig(
        belt_speed_mps=0.0, leg=LegConfig(), arm=ArmModel.SR20IA, gripper=GripperModel.THREE_FINGER_3FG25
    )
    with Cell(config) as cell:
        assert cell.config.leg is not None
        result = _grip(cell, BLADE_PLANE_Y_M + cell.config.leg.hock_offset_m)
    assert result.outcome == PRECONDITION_FAILED
    assert result.evidence["arm_tilts_tool"] == 0.0


def test_the_approach_rotation_points_the_tool_along_the_leg_with_its_first_finger_up() -> None:
    rotation = tool_rotation_for_approach(np.array([0.0, 1.0, 0.0]))
    assert rotation[:, 2] == pytest.approx([0.0, 1.0, 0.0])
    assert rotation[:, 1] == pytest.approx([0.0, 0.0, 1.0])
    assert np.linalg.det(rotation) == pytest.approx(1.0)
