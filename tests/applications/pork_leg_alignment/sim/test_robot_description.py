"""The URDF chains MoveIt uses describe the same arms the simulator moves."""

import math
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
import pytest

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.robot_description import arm_chain, forward_kinematics, to_urdf
from applications.pork_leg_alignment.sim.scene import CellConfig
from robotics.hardware.arms import ARM_SPECS, ArmModel
from robotics.hardware.grippers import TCP_SITE, GripperModel


@pytest.mark.parametrize("arm", [ArmModel.UR20, ArmModel.SR20IA])
def test_chain_forward_kinematics_matches_the_simulated_tool_centre_point(arm: ArmModel) -> None:
    spec = ARM_SPECS[arm]
    chain = arm_chain(arm)
    moving = {j.name: j for j in chain if j.kind != "fixed"}
    rng = np.random.default_rng(0)
    with Cell(CellConfig(arm=arm, gripper=GripperModel.JAW_GEH6180), {}) as cell:
        model, data = cell.model, cell.data
        tcp = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, TCP_SITE)
        for _ in range(5):
            positions = {}
            for name in spec.joints:
                joint = moving[name]
                value = float(rng.uniform(max(joint.lower, -2.0), min(joint.upper, 2.0)))
                positions[name] = value
                data.qpos[
                    model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, spec.prefix + name)]
                ] = value
            mujoco.mj_kinematics(model, data)
            fk = forward_kinematics(chain, positions)
            assert np.allclose(fk[:3, 3], data.site_xpos[tcp], atol=1e-4)
            assert np.allclose(fk[:3, :3], data.site_xmat[tcp].reshape(3, 3), atol=1e-4)


def test_the_urdf_is_well_formed_and_names_the_arm_joints() -> None:
    urdf = ET.fromstring(to_urdf("sr20ia_cell", arm_chain(ArmModel.SR20IA)))
    moving = [j.get("name") for j in urdf.findall("joint") if j.get("type") != "fixed"]
    assert moving == list(ARM_SPECS[ArmModel.SR20IA].joints)
    links = {link.get("name") for link in urdf.findall("link")}
    assert {"world", "base_link", "tool0", "tcp"} <= links
    assert all(
        j.find("parent").get("link") in links and j.find("child").get("link") in links for j in urdf.findall("joint")
    )


def test_an_arm_without_a_description_is_refused() -> None:
    with pytest.raises(ValueError, match="vendor model"):
        arm_chain(ArmModel.UR5E)
    assert math.isfinite(forward_kinematics(arm_chain(ArmModel.UR20), {})[0, 3])
