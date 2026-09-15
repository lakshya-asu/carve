"""The two leg grippers must match their datasheets where it matters for a grasp.

Stroke decides whether a gripper fits round a shank at all; grip force times pad
friction decides whether it holds or turns a leg. Both are checked on the
gripper alone, closing on a free 90 mm cylinder with gravity off, so the numbers
belong to the gripper and not to an arm or a leg.
"""

import mujoco
import numpy as np
import pytest

from robotics.hardware.grippers import (
    GRIPPER_ASSETS,
    GRIPPER_SPECS,
    GripperModel,
    _finger_joint_addresses,
    measure_geometry,
)

CYLINDER_RADIUS_M = 0.045
PAD_FRICTION = 0.5  # both assets; an assumption for wet meat, see the asset comments

# Datasheet opening ranges, metres: Zimmer GEH6180IL 80 mm per jaw from a 20 mm
# rest gap (the rest gap is this model's choice); OnRobot 3FG25 18 to 155 mm.
OPENING_RANGE_M = {
    GripperModel.JAW_GEH6180: (0.020, 0.180),
    GripperModel.THREE_FINGER_3FG25: (0.018, 0.155),
}
# The cylinder's axis: across the jaws' long pads for the parallel jaw, along the
# tool axis for the centric three-finger gripper.
CYLINDER_QUAT = {
    GripperModel.JAW_GEH6180: [0.7071068, 0.0, 0.7071068, 0.0],
    GripperModel.THREE_FINGER_3FG25: [1.0, 0.0, 0.0, 0.0],
}
# Shank shape per gripper. The flat jaw pads close on a capsule, not a cylinder:
# MuJoCo's box-cylinder contact under a steady pull along the cylinder axis
# holds only 0.60 to 0.70 of mu times the grip force and then slides (measured
# 2026-09-14: 2.4 mm at 70 percent, 8.5 mm at 80 percent), while the same jaw on
# a capsule holds to 1.0 and slips at 1.1. That is a collision artefact, not the
# gripper, so the gripper is tested on the capsule. A capsule along the
# three-finger gripper's axis reaches into its body, so that one keeps the
# cylinder, on which it holds to 1.0.
SHANK_GEOM = {
    GripperModel.JAW_GEH6180: mujoco.mjtGeom.mjGEOM_CAPSULE,
    GripperModel.THREE_FINGER_3FG25: mujoco.mjtGeom.mjGEOM_CYLINDER,
}
LEG_GRIPPERS = [GripperModel.JAW_GEH6180, GripperModel.THREE_FINGER_3FG25]


def _gripper_on_a_cylinder(gripper: GripperModel) -> tuple[mujoco.MjModel, mujoco.MjData]:
    spec = mujoco.MjSpec()
    spec.compiler.degree = False
    spec.option.gravity = [0.0, 0.0, 0.0]
    # The cell's solver settings (cell.xml). MuJoCo's defaults, a pyramidal cone
    # and no no-slip pass, let a gripped part creep under a steady pull.
    spec.option.timestep = 0.002
    spec.option.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    spec.option.cone = mujoco.mjtCone.mjCONE_ELLIPTIC
    spec.option.noslip_iterations = 3
    mount = spec.worldbody.add_site(name="mount")
    spec.attach(mujoco.MjSpec.from_file(str(GRIPPER_ASSETS / GRIPPER_SPECS[gripper].asset)), prefix="g_", site=mount)
    tcp_z = float(spec.site("g_tcp").pos[2])
    cylinder = spec.worldbody.add_body(name="cylinder", pos=[0.0, 0.0, tcp_z], quat=CYLINDER_QUAT[gripper])
    cylinder.add_freejoint()
    cylinder.add_geom(
        name="cylinder_geom",
        type=SHANK_GEOM[gripper],
        size=[CYLINDER_RADIUS_M, 0.05, 0.0],
        mass=1.0,
        condim=4,
        friction=[PAD_FRICTION, 0.05, 0.001],
    )
    model = spec.compile()
    return model, mujoco.MjData(model)


def _close(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    """Start fully open, clear of the cylinder, then command closed and settle."""
    grip = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "g_grip")
    joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "g_finger_left_joint")
    high = float(model.jnt_range[joint][1])
    for address, ratio in _finger_joint_addresses(model):
        data.qpos[address] = ratio * high
    data.ctrl[grip] = high
    for _ in range(100):
        mujoco.mj_step(model, data)
    data.ctrl[grip] = 0.0
    for _ in range(int(0.6 / model.opt.timestep)):
        mujoco.mj_step(model, data)


def _normal_force_on_cylinder_n(model: mujoco.MjModel, data: mujoco.MjData) -> float:
    cylinder = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "cylinder_geom")
    wrench = np.zeros(6)
    total = 0.0
    for i in range(data.ncon):
        if cylinder in (data.contact[i].geom1, data.contact[i].geom2):
            mujoco.mj_contactForce(model, data, i, wrench)
            total += float(wrench[0])
    return total


@pytest.mark.parametrize("gripper", LEG_GRIPPERS, ids=lambda g: g.value)
def test_opening_range_matches_the_datasheet(gripper: GripperModel) -> None:
    model, _ = _gripper_on_a_cylinder(gripper)
    geometry = measure_geometry(model, GRIPPER_SPECS[gripper])
    low, high = OPENING_RANGE_M[gripper]
    assert geometry.rest_gap_m == pytest.approx(low, rel=0.05)
    assert geometry.max_opening_m == pytest.approx(high, rel=0.05)


@pytest.mark.parametrize("gripper", LEG_GRIPPERS, ids=lambda g: g.value)
def test_closing_on_a_shank_squeezes_with_the_rated_force(gripper: GripperModel) -> None:
    model, data = _gripper_on_a_cylinder(gripper)
    _close(model, data)
    squeeze = _normal_force_on_cylinder_n(model, data)
    assert squeeze == pytest.approx(GRIPPER_SPECS[gripper].rated_force_n, rel=0.15)


@pytest.mark.parametrize("gripper", LEG_GRIPPERS, ids=lambda g: g.value)
def test_the_grip_holds_a_pull_along_the_shank_up_to_its_friction_rating(gripper: GripperModel) -> None:
    """Pull-out force along the cylinder axis, ramped until it slips 2 mm."""
    model, data = _gripper_on_a_cylinder(gripper)
    _close(model, data)
    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cylinder")
    axis = data.xmat[body].reshape(3, 3)[:, 2].copy()
    start = data.xpos[body].copy()
    expected = PAD_FRICTION * GRIPPER_SPECS[gripper].rated_force_n
    ramp_s = 3.0
    slipped_at = None
    steps = int(ramp_s / model.opt.timestep)
    for k in range(steps):
        force = 2.0 * expected * k / steps
        data.xfrc_applied[body, :3] = force * axis
        mujoco.mj_step(model, data)
        if float(np.dot(data.xpos[body] - start, axis)) > 0.002:
            slipped_at = force
            break
    assert slipped_at is not None, "never slipped at twice the rated friction force"
    assert slipped_at >= 0.8 * expected, f"slipped at {slipped_at:.0f} N, rating gives {expected:.0f} N"
