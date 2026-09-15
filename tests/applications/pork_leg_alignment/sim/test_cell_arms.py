"""Every arm the cell can be built with has to stand in it, hold still, and reach the belt.

The UR5e is covered by the older scene and cell tests. These cover the two 20 kg
arms Neil's SCARA against six-axis question is decided on, mounted behind the
far rail.
"""

import math

import mujoco
import numpy as np
import pytest

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.scene import CellConfig
from robotics.hardware.arms import ArmModel
from robotics.hardware.ik import UnreachableError, solve_ik

BELT_TOP_Z_M = 0.90
FAR_RAIL_OUTER_Y_M = 0.873
GRASP_HEIGHT_ABOVE_BELT_M = 0.05  # about a shank's centreline


@pytest.fixture(scope="module", params=[ArmModel.UR20, ArmModel.SR20IA], ids=lambda arm: arm.value)
def arm_cell(request):
    with Cell(CellConfig(belt_speed_mps=0.0, arm=request.param)) as cell:
        yield cell


def test_the_arm_holds_its_home_pose_in_the_cell(arm_cell) -> None:
    arm_cell.reset()
    arm_cell.step(seconds=1.0)
    observation, _ = arm_cell.observe()
    assert observation.joint_pos_rad.shape == (arm_cell.arm.dof,)
    assert observation.joint_pos_rad == pytest.approx(arm_cell.arm.home_qpos, abs=0.02)


def test_the_arm_stands_behind_the_far_rail(arm_cell) -> None:
    site = mujoco.mj_name2id(arm_cell.model, mujoco.mjtObj.mjOBJ_SITE, "arm_mount")
    arm_cell.reset()
    assert float(arm_cell.data.site_xpos[site][1]) > FAR_RAIL_OUTER_Y_M


def test_the_tool_reaches_shank_height_over_the_middle_of_the_belt(arm_cell) -> None:
    """The whole alignment zone must be reachable; the belt's far corners may not be."""
    arm_cell.reset()
    misses = []
    for x in np.arange(-0.2, 0.61, 0.2):
        for y in (0.35, 0.50, 0.65):
            target = np.array([x, y, BELT_TOP_Z_M + GRASP_HEIGHT_ABOVE_BELT_M])
            try:
                solve_ik(arm_cell.model, arm_cell.data, target, -math.pi / 2, arm=arm_cell.arm)
            except UnreachableError as error:
                misses.append((round(float(x), 2), y, str(error)))
    assert not misses, f"{arm_cell.arm.model.value} cannot reach: {misses}"
