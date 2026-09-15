"""Closed-form SR-20iA IK: its answers put the simulated tool where asked, and it refuses what the arm cannot do."""

import math

import mujoco
import numpy as np
import pytest

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.scara_kinematics import ScaraUnreachableError, scara_ik
from applications.pork_leg_alignment.sim.scene import DEFAULT_MOUNTS, CellConfig
from robotics.core.grasp_action import tool_rotation
from robotics.hardware.arms import ARM_SPECS, ArmModel
from robotics.hardware.grippers import TCP_SITE, GripperModel

MOUNT = DEFAULT_MOUNTS[ArmModel.SR20IA]
TARGETS = [((0.0, 0.45, 0.98), 0.3), ((-0.3, 0.6, 1.02), -1.2), ((0.25, 0.35, 0.95), 2.0)]


@pytest.mark.parametrize(("point", "finger_axis"), TARGETS)
def test_the_solution_puts_the_simulated_tool_on_the_target(point, finger_axis) -> None:
    spec = ARM_SPECS[ArmModel.SR20IA]
    target, rotation = np.array(point), tool_rotation(finger_axis, 0.0)
    joints = scara_ik(target, rotation, MOUNT)
    with Cell(CellConfig(arm=ArmModel.SR20IA, gripper=GripperModel.JAW_GEH6180), {}) as cell:
        model, data = cell.model, cell.data
        for name, value in zip(spec.joints, joints, strict=True):
            data.qpos[model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, spec.prefix + name)]] = (
                value
            )
        mujoco.mj_kinematics(model, data)
        tcp = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, TCP_SITE)
        assert np.allclose(data.site_xpos[tcp], target, atol=1e-6)
        assert np.allclose(data.site_xmat[tcp].reshape(3, 3), rotation, atol=1e-6)


def test_a_tilted_tool_and_an_out_of_reach_point_are_refused() -> None:
    with pytest.raises(ScaraUnreachableError, match="straight down"):
        scara_ik(np.array([0.0, 0.45, 0.98]), tool_rotation(0.3, math.radians(15.0)), MOUNT)
    with pytest.raises(ScaraUnreachableError, match="reaches"):
        scara_ik(np.array([2.0, 0.45, 0.98]), tool_rotation(0.3, 0.0), MOUNT)
    with pytest.raises(ScaraUnreachableError, match="stroke"):
        scara_ik(np.array([0.0, 0.45, 0.30]), tool_rotation(0.3, 0.0), MOUNT)


def test_the_elbow_closest_to_the_seed_is_chosen() -> None:
    target, rotation = np.array([0.0, 0.45, 0.98]), tool_rotation(0.3, 0.0)
    first = scara_ik(target, rotation, MOUNT)
    other = scara_ik(target, rotation, MOUNT, seed=(first[0], -first[1], 0.0, 0.0))
    assert math.copysign(1.0, other[1]) != math.copysign(1.0, first[1])
