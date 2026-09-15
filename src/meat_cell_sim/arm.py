"""Put the tool where the plan says, and know when it cannot.

The grasp and placement steps need a tool pose, not joint angles. This module is
the translation, and the part that matters is not the solver but the honesty
about failure: an IK call that silently returns its best effort will happily
hand back a pose 40 mm from the one requested, and the arm will drive there.
`solve_ik` raises instead, and every caller is expected to treat that as an
episode outcome rather than something to retry blindly.

The tool is held pointing straight down, because the product lies flat on a belt
and the gripper approaches from above. That leaves position and one yaw, which
is exactly what `Pose2D` carries, so nothing in the pipeline has to invent a
full SE(3) pose it cannot measure.

Every function takes the arm's `ArmSpec`, defaulting to the UR5e, so the same
solver serves a six-axis arm and a four-axis SCARA. On a SCARA the tool can only
point down, so the orientation rows of the error that a six-axis arm uses to
hold the tool vertical are already zero there, and damped least squares simply
works in the four directions the SCARA has.
"""

from __future__ import annotations

import logging

import mujoco
import numpy as np

from meat_cell_sim.arms import UR5E_SPEC, ArmSpec

logger = logging.getLogger(__name__)

TCP_SITE = "g_tcp"
ARM_JOINTS = UR5E_SPEC.joint_names

# Damped least squares. The damping trades accuracy near a singularity for a
# bounded step; 1e-4 is small enough that a well-conditioned pose converges in a
# handful of iterations and large enough that a near-singular one does not throw
# the arm across the cell.
IK_DAMPING = 1e-4
IK_MAX_ITERATIONS = 200
IK_POSITION_TOLERANCE_M = 1e-5
IK_ORIENTATION_TOLERANCE_RAD = 1e-4
# Cap on one iteration's joint step, radians or metres. Without it the first
# step of a large move can leave the linearisation entirely and the solve
# oscillates.
IK_MAX_STEP_RAD = 0.2


class UnreachableError(Exception):
    """The requested tool pose has no joint solution the arm can hold."""


def tool_down_rotation(yaw_rad: float) -> np.ndarray:
    """Rotation with the tool z pointing at the belt and tool x along `yaw_rad`.

    Returns:
        (3, 3) world-from-tool rotation.
    """
    cos_yaw, sin_yaw = np.cos(yaw_rad), np.sin(yaw_rad)
    x_axis = np.array([cos_yaw, sin_yaw, 0.0])
    z_axis = np.array([0.0, 0.0, -1.0])
    y_axis = np.cross(z_axis, x_axis)
    return np.column_stack([x_axis, y_axis, z_axis])


def arm_qpos_indices(model: mujoco.MjModel, arm: ArmSpec = UR5E_SPEC) -> np.ndarray:
    """Indices into `qpos` of the arm joints, in chain order."""
    return np.array(
        [model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)] for name in arm.joint_names]
    )


def arm_dof_indices(model: mujoco.MjModel, arm: ArmSpec = UR5E_SPEC) -> np.ndarray:
    """Indices into `qvel` and the Jacobian columns of the arm joints."""
    return np.array(
        [model.jnt_dofadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)] for name in arm.joint_names]
    )


def tool_pose(model: mujoco.MjModel, data: mujoco.MjData) -> tuple[np.ndarray, np.ndarray]:
    """Current tool position and rotation in the world frame.

    Requires a forward pass to have run. Reading `site_xpos` after setting
    `qpos` but before `mj_forward` returns the previous pose, or zeros on a
    fresh `MjData`, and the resulting error looks like a calibration fault.
    """
    site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, TCP_SITE)
    return data.site_xpos[site].copy(), data.site_xmat[site].reshape(3, 3).copy()


def _orientation_error(current: np.ndarray, desired: np.ndarray) -> np.ndarray:
    """Rotation vector taking `current` to `desired`, in world coordinates."""
    current_quat = np.empty(4)
    desired_quat = np.empty(4)
    mujoco.mju_mat2Quat(current_quat, current.flatten())
    mujoco.mju_mat2Quat(desired_quat, desired.flatten())
    difference = np.empty(4)
    mujoco.mju_mulQuat(difference, desired_quat, np.array([current_quat[0], *(-current_quat[1:])]))
    rotation = np.empty(3)
    mujoco.mju_quat2Vel(rotation, difference, 1.0)
    return rotation


def solve_ik(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    position_m: np.ndarray,
    yaw_rad: float,
    seed_qpos: np.ndarray | None = None,
    arm: ArmSpec = UR5E_SPEC,
) -> np.ndarray:
    """Joint values putting the tool at `position_m`, pointing down, turned to `yaw_rad`.

    Solved on a scratch copy, so `data` is not disturbed.

    Args:
        model: The cell.
        data: Current state, used only for its joint values as a starting guess.
        position_m: Target tool position, world frame, metres.
        yaw_rad: Target tool heading about the world z axis.
        seed_qpos: Starting guess for the arm joints. Defaults to the current
            pose, which is what makes successive waypoints continuous.
        arm: Which arm the cell was built with.

    Returns:
        (n,) joint values, one per arm joint.

    Raises:
        UnreachableError: If the solver does not converge inside the joint
            limits. The caller must treat this as an outcome, not retry it.
    """
    return solve_ik_rotation(model, data, position_m, tool_down_rotation(yaw_rad), seed_qpos, arm)


def tool_rotation_for_approach(approach_world: np.ndarray, up_world: np.ndarray | None = None) -> np.ndarray:
    """Rotation with the tool z along `approach_world` and the tool y as close to `up_world` as it can be.

    For a tool that comes in sideways, such as a gripper pointed along a leg.
    The first finger of the three-finger gripper lies along tool y, so this
    turns it up and the other two below the part, symmetric about vertical.

    Raises:
        ValueError: If the approach is vertical, where "up" names no roll.

    Returns:
        (3, 3) world-from-tool rotation.
    """
    up = np.array([0.0, 0.0, 1.0]) if up_world is None else np.asarray(up_world, dtype=float)
    z_axis = np.asarray(approach_world, dtype=float) / np.linalg.norm(approach_world)
    y_axis = up - float(np.dot(up, z_axis)) * z_axis
    if float(np.linalg.norm(y_axis)) < 1e-6:
        raise ValueError("approach is parallel to up; use tool_down_rotation for a vertical tool")
    y_axis /= np.linalg.norm(y_axis)
    x_axis = np.cross(y_axis, z_axis)
    return np.column_stack([x_axis, y_axis, z_axis])


def solve_ik_rotation(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    position_m: np.ndarray,
    desired_rotation: np.ndarray,
    seed_qpos: np.ndarray | None = None,
    arm: ArmSpec = UR5E_SPEC,
) -> np.ndarray:
    """Joint values putting the tool at `position_m` with the world-from-tool rotation `desired_rotation`.

    Same solver and the same honesty about failure as `solve_ik`, for any tool
    orientation. A SCARA cannot reach an orientation that tilts its tool, and
    reports it as unreachable.

    Raises:
        UnreachableError: If the solver does not converge inside the joint limits.
    """
    qpos_index = arm_qpos_indices(model, arm)
    dof_index = arm_dof_indices(model, arm)
    scratch = mujoco.MjData(model)
    scratch.qpos[:] = data.qpos
    if seed_qpos is not None:
        scratch.qpos[qpos_index] = seed_qpos
    site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, TCP_SITE)
    jacobian_position = np.zeros((3, model.nv))
    jacobian_rotation = np.zeros((3, model.nv))
    lower, upper = _arm_joint_limits(model, arm)

    for _ in range(IK_MAX_ITERATIONS):
        mujoco.mj_kinematics(model, scratch)
        mujoco.mj_comPos(model, scratch)
        position_error = np.asarray(position_m, dtype=float) - scratch.site_xpos[site]
        rotation_error = _orientation_error(scratch.site_xmat[site].reshape(3, 3), desired_rotation)
        if (
            np.linalg.norm(position_error) < IK_POSITION_TOLERANCE_M
            and np.linalg.norm(rotation_error) < IK_ORIENTATION_TOLERANCE_RAD
        ):
            return np.asarray(scratch.qpos[qpos_index].copy(), dtype=float)
        mujoco.mj_jacSite(model, scratch, jacobian_position, jacobian_rotation, site)
        jacobian = np.vstack([jacobian_position[:, dof_index], jacobian_rotation[:, dof_index]])
        error = np.concatenate([position_error, rotation_error])
        step = jacobian.T @ np.linalg.solve(jacobian @ jacobian.T + IK_DAMPING * np.eye(6), error)
        largest = float(np.abs(step).max())
        if largest > IK_MAX_STEP_RAD:
            step *= IK_MAX_STEP_RAD / largest
        scratch.qpos[qpos_index] = np.clip(scratch.qpos[qpos_index] + step, lower, upper)

    raise UnreachableError(
        f"no joint solution for tool at {np.round(position_m, 4).tolist()} pointing "
        f"{np.round(desired_rotation[:, 2], 3).tolist()} after {IK_MAX_ITERATIONS} iterations; residual "
        f"{1000 * float(np.linalg.norm(position_error)):.2f} mm and "
        f"{np.degrees(float(np.linalg.norm(rotation_error))):.2f} deg"
    )


def _arm_joint_limits(model: mujoco.MjModel, arm: ArmSpec) -> tuple[np.ndarray, np.ndarray]:
    limits = []
    for name in arm.joint_names:
        joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if model.jnt_limited[joint]:
            limits.append(model.jnt_range[joint])
        else:
            limits.append([-np.pi * 2, np.pi * 2])
    bounds = np.array(limits)
    return bounds[:, 0], bounds[:, 1]
