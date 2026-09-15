"""Closed-form inverse kinematics for the FANUC SR-20iA with the jaw gripper.

A SCARA's tool can only point straight down, so a tool pose has four free numbers (x, y, z and the
turn about vertical) and the arm has four joints: the answer is closed form, and a general IK solver
asked for a full six-number pose is the wrong tool (MoveIt's KDL plugin cannot satisfy it, and
pick_ik is not packaged for this machine). The ROS 2 `scara_ik_node` serves this through the same
`GetPositionIK` interface MoveIt uses, so the grasp executor does not care which arm it drives.

Geometry and frames as `robot_description.arm_chain(ArmModel.SR20IA)`; checked against MuJoCo in
`tests/test_scara_kinematics.py`. Numpy only.
"""

from __future__ import annotations

import math

import numpy as np

from applications.pork_leg_alignment.sim.robot_description import JAW_TCP_OFFSET_M, SR20IA_WRIST_DROP_M
from applications.pork_leg_alignment.sim.scene import ArmMount
from robotics.hardware.arms import (
    SR20IA_ARM_LENGTHS_M,
    SR20IA_ARM_PLANE_HEIGHT_M,
    SR20IA_J3_STROKE_M,
    SR20IA_J4_RANGE_RAD,
    SR20IA_J12_RANGE_RAD,
)

# A tool axis further than this from straight down is a tilt the arm cannot make.
VERTICAL_TOLERANCE_RAD = math.radians(0.5)


class ScaraUnreachableError(ValueError):
    """The tool pose has no joint solution on this arm; the message says why."""


def _wrap_near(angle: float, near: float, limit: float) -> float:
    """`angle` plus whole turns, as close to `near` as the joint's range allows."""
    best = None
    for turns in range(-3, 4):
        candidate = angle + 2 * math.pi * turns
        if -limit <= candidate <= limit and (best is None or abs(candidate - near) < abs(best - near)):
            best = candidate
    if best is None:
        raise ScaraUnreachableError(f"wrist angle {angle:.3f} rad has no turn inside +/-{limit:.3f} rad")
    return best


def scara_ik(
    tcp_world_m: np.ndarray,
    tool_rotation_world: np.ndarray,
    mount: ArmMount,
    seed: tuple[float, float, float, float] | None = None,
) -> tuple[float, float, float, float]:
    """Joint positions (j1, j2 in rad, j3 in m, j4 in rad) that put the tool centre point at a pose.

    Args:
        tcp_world_m: (3,) tool centre point, world frame.
        tool_rotation_world: (3, 3) world-from-tool rotation; tool z must point straight down.
        mount: Where the arm stands.
        seed: Current joints; the elbow and wrist turn closest to it are chosen.

    Raises:
        ScaraUnreachableError: If the tool is tilted, the point is out of reach, or a joint limit is exceeded.
    """
    down = np.array([0.0, 0.0, -1.0])
    if float(tool_rotation_world[:, 2] @ down) < math.cos(VERTICAL_TOLERANCE_RAD):
        raise ScaraUnreachableError("a SCARA's tool can only point straight down")
    seed = seed or (0.0, 0.0, 0.0, 0.0)
    cos_yaw, sin_yaw = math.cos(mount.yaw_rad), math.sin(mount.yaw_rad)
    # The flange (tool0) is the tool centre point lifted back up the tool axis.
    flange = tcp_world_m - JAW_TCP_OFFSET_M * tool_rotation_world[:, 2]
    dx, dy = flange[0] - mount.x_m, flange[1] - mount.y_m
    x, y = cos_yaw * dx + sin_yaw * dy, -sin_yaw * dx + cos_yaw * dy
    z = flange[2] - mount.z_m

    l1, l2 = SR20IA_ARM_LENGTHS_M
    reach = math.hypot(x, y)
    cos_j2 = (reach**2 - l1**2 - l2**2) / (2 * l1 * l2)
    if not -1.0 <= cos_j2 <= 1.0:
        raise ScaraUnreachableError(
            f"the point is {reach:.3f} m from the axis; the arm reaches {abs(l1 - l2):.3f} to {l1 + l2:.3f} m"
        )
    solutions = []
    for elbow in (1.0, -1.0):
        j2 = elbow * math.acos(cos_j2)
        j1 = math.atan2(y, x) - math.atan2(l2 * math.sin(j2), l1 + l2 * math.cos(j2))
        j1 = math.remainder(j1, 2 * math.pi)
        if abs(j1) <= SR20IA_J12_RANGE_RAD and abs(j2) <= SR20IA_J12_RANGE_RAD:
            solutions.append((j1, j2))
    if not solutions:
        raise ScaraUnreachableError("both elbow solutions exceed the J1 or J2 range")
    j1, j2 = min(solutions, key=lambda s: abs(s[0] - seed[0]) + abs(s[1] - seed[1]))

    j3 = SR20IA_ARM_PLANE_HEIGHT_M - SR20IA_WRIST_DROP_M - z
    if not 0.0 <= j3 <= SR20IA_J3_STROKE_M:
        raise ScaraUnreachableError(f"the quill would need {j3:.3f} m of its 0 to {SR20IA_J3_STROKE_M:.3f} m stroke")
    # tool0 is the wrist turned half a turn about x, so tool x is wrist x; the wrist's heading in
    # the world is the mount yaw plus J1, J2 and J4.
    tool_heading = math.atan2(tool_rotation_world[1, 0], tool_rotation_world[0, 0])
    j4 = _wrap_near(tool_heading - mount.yaw_rad - j1 - j2, seed[3], SR20IA_J4_RANGE_RAD)
    return j1, j2, j3, j4
