"""The shank grasp is the first library skill running on the simulated cell.

The strongest pair, the UR20 with the 1800 N jaw, must take a leg lying square
on a stopped belt and prove the grip. A leg placed beyond the arm's reach must
end in a declared failure, not an exception. How every arm and gripper pair
does is a measurement, in scripts/measure_shank_grasp.py.
"""

import math

import numpy as np
import pytest

from meat_cell_sim.arms import ArmModel
from meat_cell_sim.cell import Cell
from meat_cell_sim.gripper import GripperModel
from meat_cell_sim.product import LegConfig
from meat_cell_sim.scene import CellConfig
from meat_cell_sim.skills import AcquireShank, SelectShankGrasp, ShankGrasp
from skill_library import SUCCESS, run_skill


@pytest.fixture(scope="module")
def ur20_jaw_cell():
    config = CellConfig(belt_speed_mps=0.0, leg=LegConfig(), arm=ArmModel.UR20, gripper=GripperModel.JAW_GEH6180)
    with Cell(config) as cell:
        yield cell


def test_the_ur20_with_the_jaw_grips_a_square_leg_and_lifts_its_shank(ur20_jaw_cell) -> None:
    cell = ur20_jaw_cell
    cell.reset()
    cell.place_product(0.30, 0.55, -math.pi / 2, settle_s=0.3)
    selected = run_skill(SelectShankGrasp(), cell, {})
    assert selected.outcome == SUCCESS
    acquired = run_skill(AcquireShank(), cell, selected.outputs)
    assert acquired.outcome == SUCCESS, f"{acquired.outcome}: {dict(acquired.evidence)}"
    assert acquired.evidence["tool_rise_m"] > 0.0005
    assert abs(acquired.evidence["part_minus_tool_m"]) <= 0.001


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
