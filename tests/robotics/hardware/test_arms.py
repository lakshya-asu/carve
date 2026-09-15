"""The built arms must match the numbers they were built from.

A DH table typed into a body chain with one sign or one frame wrong still
compiles and still moves; it just puts the tool somewhere else. These check the
UR20's forward kinematics against the DH product at random configurations, and
the SCARA's reach, stroke and tool direction against its datasheet.
"""

import math

import mujoco
import numpy as np
import pytest

from robotics.hardware.arms import (
    SR20IA_ARM_LENGTHS_M,
    SR20IA_J3_STROKE_M,
    SR20IA_SPEC,
    UR20_DH,
    UR20_LINKS,
    UR20_SPEC,
    ArmModel,
    build_arm,
    dh_transform,
)


def _compiled(model: ArmModel) -> tuple[mujoco.MjModel, mujoco.MjData]:
    compiled = build_arm(model).compile()
    return compiled, mujoco.MjData(compiled)


def _site_pose(model: mujoco.MjModel, data: mujoco.MjData, name: str) -> tuple[np.ndarray, np.ndarray]:
    site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)
    return data.site_xpos[site].copy(), data.site_xmat[site].reshape(3, 3).copy()


def test_ur20_forward_kinematics_equal_the_published_dh_product() -> None:
    model, data = _compiled(ArmModel.UR20)
    rng = np.random.default_rng(20260914)
    for _ in range(25):
        q = rng.uniform(-math.pi, math.pi, size=6)
        data.qpos[:6] = q
        mujoco.mj_kinematics(model, data)
        position, rotation = _site_pose(model, data, UR20_SPEC.attachment_site)
        expected = np.eye(4)
        for theta, (a, d, alpha) in zip(q, UR20_DH, strict=True):
            expected = expected @ dh_transform(float(theta), a, d, alpha)
        assert position == pytest.approx(expected[:3, 3], abs=1e-9)
        assert rotation == pytest.approx(expected[:3, :3], abs=1e-9)


def test_ur20_carries_the_published_link_masses() -> None:
    model, _ = _compiled(ArmModel.UR20)
    masses = [
        float(model.body_mass[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"link{i}")]) for i in range(1, 7)
    ]
    assert masses == pytest.approx([link[0] for link in UR20_LINKS])
    assert sum(masses) == pytest.approx(60.88, abs=0.01)


def test_ur20_stretched_out_reaches_about_its_rated_reach() -> None:
    """Rated reach is shoulder to flange; the DH lengths alone give 0.862 + 0.7287 plus the wrist offsets."""
    model, data = _compiled(ArmModel.UR20)
    data.qpos[:6] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    mujoco.mj_kinematics(model, data)
    position, _ = _site_pose(model, data, UR20_SPEC.attachment_site)
    shoulder = np.array([0.0, 0.0, UR20_DH[0][1]])
    assert float(np.linalg.norm(position - shoulder)) == pytest.approx(UR20_SPEC.reach_m, abs=0.12)


def test_scara_stretched_out_reaches_its_two_arm_lengths() -> None:
    model, data = _compiled(ArmModel.SR20IA)
    data.qpos[:4] = [0.0, 0.0, 0.0, 0.0]
    mujoco.mj_kinematics(model, data)
    position, _ = _site_pose(model, data, SR20IA_SPEC.attachment_site)
    assert float(np.hypot(position[0], position[1])) == pytest.approx(sum(SR20IA_ARM_LENGTHS_M), abs=1e-9)
    assert sum(SR20IA_ARM_LENGTHS_M) == pytest.approx(SR20IA_SPEC.reach_m)


def test_scara_quill_lowers_the_tool_by_its_stroke_and_never_tilts_it() -> None:
    model, data = _compiled(ArmModel.SR20IA)
    rng = np.random.default_rng(7)
    data.qpos[:4] = [0.3, -0.8, 0.0, 1.1]
    mujoco.mj_kinematics(model, data)
    top, _ = _site_pose(model, data, SR20IA_SPEC.attachment_site)
    data.qpos[2] = SR20IA_J3_STROKE_M
    mujoco.mj_kinematics(model, data)
    bottom, _ = _site_pose(model, data, SR20IA_SPEC.attachment_site)
    assert top[2] - bottom[2] == pytest.approx(SR20IA_J3_STROKE_M, abs=1e-9)
    for _ in range(20):
        data.qpos[:4] = [rng.uniform(-2.5, 2.5), rng.uniform(-2.5, 2.5), rng.uniform(0, 0.3), rng.uniform(-6, 6)]
        mujoco.mj_kinematics(model, data)
        _, rotation = _site_pose(model, data, SR20IA_SPEC.attachment_site)
        assert rotation[:, 2] == pytest.approx([0.0, 0.0, -1.0], abs=1e-9), "a SCARA tool axis must point straight down"


@pytest.mark.parametrize("arm", [ArmModel.UR20, ArmModel.SR20IA])
def test_every_joint_has_a_servo_and_holds_its_home_pose(arm: ArmModel) -> None:
    from robotics.hardware.arms import ARM_SPECS

    spec = ARM_SPECS[arm]
    model, data = _compiled(arm)
    assert model.nu == spec.dof
    data.qpos[: spec.dof] = spec.home_qpos
    data.ctrl[: spec.dof] = spec.home_qpos
    for _ in range(int(1.0 / model.opt.timestep)):
        mujoco.mj_step(model, data)
    assert data.qpos[: spec.dof] == pytest.approx(spec.home_qpos, abs=0.01), "the arm sagged away from home"
