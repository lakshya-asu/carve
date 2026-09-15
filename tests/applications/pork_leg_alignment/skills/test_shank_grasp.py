"""The shank grasp is the first library skill running on the simulated cell.

Both 20 kg arms with the 1800 N jaw must take a leg lying square on a stopped
belt, prove the grip, and lift the tool the commanded 5 mm under the leg's
weight: before the servos gained integral action the UR20 rose 1.6 mm and the
SR-20iA 2.6 mm (2026-09-14), an error that would land in every cut offset. A
leg placed beyond the arm's reach must end in a declared failure, not an
exception. How every arm and gripper pair does is a measurement, in
scripts/measure/shank_grasp.py.
"""

import math

import numpy as np
import pytest

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import LegConfig
from applications.pork_leg_alignment.sim.scene import CellConfig
from applications.pork_leg_alignment.skills import (
    AcquireShank,
    EstimateLegFromGroundTruth,
    SelectShankGrasp,
    ShankGrasp,
)
from applications.pork_leg_alignment.skills.shank_grasp import LIFT_CHECK_M
from robotics.core.skill_library import SUCCESS, run_skill
from robotics.hardware.arms import ArmModel
from robotics.hardware.grippers import GripperModel

# plan/overnight-2026-09-14.md task 4b: the 5 mm lift within 0.5 mm on both arms.
LIFT_TOLERANCE_M = 0.0005


@pytest.fixture(scope="module")
def ur20_jaw_cell():
    config = CellConfig(belt_speed_mps=0.0, leg=LegConfig(), arm=ArmModel.UR20, gripper=GripperModel.JAW_GEH6180)
    with Cell(config) as cell:
        yield cell


@pytest.fixture(scope="module")
def sr20ia_jaw_cell():
    config = CellConfig(belt_speed_mps=0.0, leg=LegConfig(), arm=ArmModel.SR20IA, gripper=GripperModel.JAW_GEH6180)
    with Cell(config) as cell:
        yield cell


def _grip_and_lift(cell: Cell) -> None:
    cell.reset()
    cell.place_product(0.30, 0.55, -math.pi / 2, settle_s=0.3)
    estimated = run_skill(EstimateLegFromGroundTruth(), cell, {})
    selected = run_skill(SelectShankGrasp(), cell, estimated.outputs)
    assert selected.outcome == SUCCESS
    acquired = run_skill(AcquireShank(), cell, selected.outputs)
    assert acquired.outcome == SUCCESS, f"{acquired.outcome}: {dict(acquired.evidence)}"
    assert acquired.evidence["tool_rise_m"] == pytest.approx(LIFT_CHECK_M, abs=LIFT_TOLERANCE_M)
    assert abs(acquired.evidence["part_minus_tool_m"]) <= 0.001


def test_the_ur20_with_the_jaw_grips_a_square_leg_and_lifts_its_shank_the_commanded_5_mm(ur20_jaw_cell) -> None:
    _grip_and_lift(ur20_jaw_cell)


def test_the_sr20ia_with_the_jaw_grips_a_square_leg_and_lifts_its_shank_the_commanded_5_mm(sr20ia_jaw_cell) -> None:
    _grip_and_lift(sr20ia_jaw_cell)


def test_an_unloaded_arm_holds_home_without_drifting(ur20_jaw_cell) -> None:
    """The integral term must not walk an arm that is already where it was told to be."""
    cell = ur20_jaw_cell
    cell.reset()
    cell.step(seconds=1.0)
    assert np.max(np.abs(cell.arm_qpos - np.array(cell.arm.home_qpos))) < 0.02


def test_a_grasp_out_of_reach_ends_in_a_declared_failure(ur20_jaw_cell) -> None:
    """3 m along the belt is past the UR20's 1.75 m reach from its mount."""
    cell = ur20_jaw_cell
    cell.reset()
    cell.place_product(0.30, 0.55, -math.pi / 2, settle_s=0.1)
    grasp = ShankGrasp(
        position_m=np.array([3.0, 0.50, 0.95]),
        yaw_rad=0.0,
        shank_width_m=0.09,
        widest_under_pads_m=0.10,
        fraction=0.66,
    )
    acquired = run_skill(AcquireShank(), cell, {"shank_grasp": grasp})
    assert acquired.outcome == "unreachable"
