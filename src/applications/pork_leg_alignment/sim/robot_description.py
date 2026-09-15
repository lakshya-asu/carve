"""Each arm as a kinematic chain, written from the same numbers as its MuJoCo model, and exported as URDF.

MoveIt plans and solves IK on a URDF. If that URDF and the simulator's arm differ by a frame
convention or a link offset, every IK answer lands somewhere the simulated arm is not. So the chain
here is built from the constants `arms.py` builds the MuJoCo arms from (the UR20 DH table, the
SR-20iA dimensions), the cell's arm mounts (`scene.DEFAULT_MOUNTS`) and the jaw gripper's tool
centre point, and `tests/test_robot_description.py` checks its forward kinematics against MuJoCo's
tool site at random joint positions.

Frames: `world` is the cell's world; `base_link` is the arm's mount; `tcp` is the jaw gripper's tool
centre point, the point midway between the pads, with z pointing out of the gripper.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from applications.pork_leg_alignment.sim.scene import DEFAULT_MOUNTS, ArmMount
from robotics.hardware.arms import (
    SR20IA_ARM_LENGTHS_M,
    SR20IA_ARM_PLANE_HEIGHT_M,
    SR20IA_J3_STROKE_M,
    SR20IA_J4_RANGE_RAD,
    SR20IA_J12_RANGE_RAD,
    SR20IA_QUILL_LENGTH_M,
    SR20IA_SPEC,
    UR20_DH,
    UR20_SPEC,
    ArmModel,
)

# Jaw gripper tool centre point along the gripper's z axis, from `assets/jaw_gripper.xml` (site tcp).
JAW_TCP_OFFSET_M = 0.234
# The SR-20iA wrist sits this far below the quill body's origin (`arms.build_sr20ia`).
SR20IA_WRIST_DROP_M = SR20IA_QUILL_LENGTH_M - 0.1


@dataclass(frozen=True)
class ChainJoint:
    """One URDF joint.

    Attributes:
        name: Joint name; for moving joints, the arm's joint name without the simulator's prefix.
        kind: "fixed", "revolute" or "prismatic".
        parent: Parent link.
        child: Child link.
        xyz: Origin translation in the parent link, metres.
        rpy: Origin rotation in the parent link, roll-pitch-yaw radians (URDF convention).
        axis: Motion axis in the child link.
        lower: Lower limit, rad or m.
        upper: Upper limit, rad or m.
        velocity: Speed limit, rad/s or m/s.
    """

    name: str
    kind: str
    parent: str
    child: str
    xyz: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rpy: tuple[float, float, float] = (0.0, 0.0, 0.0)
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0)
    lower: float = 0.0
    upper: float = 0.0
    velocity: float = 0.0


def _rpy_matrix(rpy: tuple[float, float, float]) -> np.ndarray:
    roll, pitch, yaw = rpy
    cr, sr, cp, sp, cy, sy = (
        math.cos(roll),
        math.sin(roll),
        math.cos(pitch),
        math.sin(pitch),
        math.cos(yaw),
        math.sin(yaw),
    )
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return np.asarray(rz @ ry @ rx)


def _mount_joint(mount: ArmMount) -> ChainJoint:
    return ChainJoint(
        "world_to_base", "fixed", "world", "base_link", (mount.x_m, mount.y_m, mount.z_m), (0.0, 0.0, mount.yaw_rad)
    )


def arm_chain(arm: ArmModel, mount: ArmMount | None = None) -> list[ChainJoint]:
    """The arm from the world to its gripper's tool centre point, as URDF joints in order.

    Raises:
        ValueError: For an arm without a description here (the UR5e uses Menagerie's model).
    """
    mount = mount or DEFAULT_MOUNTS[arm]
    chain = [_mount_joint(mount)]
    if arm is ArmModel.UR20:
        parent = "base_link"
        for index, (a, d, alpha) in enumerate(UR20_DH):
            joint = UR20_SPEC.joints[index]
            rotor, link = f"{joint}_rotor", f"link{index + 1}"
            chain.append(
                ChainJoint(
                    joint,
                    "revolute",
                    parent,
                    rotor,
                    lower=-2 * math.pi,
                    upper=2 * math.pi,
                    velocity=UR20_SPEC.max_joint_speed[index],
                )
            )
            # Standard DH: turn about the previous z, then Tz(d) Tx(a) Rx(alpha) into the link frame.
            chain.append(ChainJoint(f"{link}_dh", "fixed", rotor, link, (a, 0.0, d), (alpha, 0.0, 0.0)))
            parent = link
        chain.append(ChainJoint("flange_to_tool0", "fixed", parent, "tool0"))
    elif arm is ArmModel.SR20IA:
        l1, l2 = SR20IA_ARM_LENGTHS_M
        j1, j2, j3, j4 = SR20IA_SPEC.joints
        speeds = SR20IA_SPEC.max_joint_speed
        chain += [
            ChainJoint("arm_plane", "fixed", "base_link", "arm_plane", (0.0, 0.0, SR20IA_ARM_PLANE_HEIGHT_M)),
            ChainJoint(
                j1,
                "revolute",
                "arm_plane",
                "arm1",
                lower=-SR20IA_J12_RANGE_RAD,
                upper=SR20IA_J12_RANGE_RAD,
                velocity=speeds[0],
            ),
            ChainJoint("arm1_end", "fixed", "arm1", "arm1_end", (l1, 0.0, 0.0)),
            ChainJoint(
                j2,
                "revolute",
                "arm1_end",
                "arm2",
                lower=-SR20IA_J12_RANGE_RAD,
                upper=SR20IA_J12_RANGE_RAD,
                velocity=speeds[1],
            ),
            ChainJoint("arm2_end", "fixed", "arm2", "arm2_end", (l2, 0.0, 0.0)),
            ChainJoint(
                j3,
                "prismatic",
                "arm2_end",
                "quill",
                axis=(0.0, 0.0, -1.0),
                lower=0.0,
                upper=SR20IA_J3_STROKE_M,
                velocity=speeds[2],
            ),
            ChainJoint("wrist_mount", "fixed", "quill", "wrist_mount", (0.0, 0.0, -SR20IA_WRIST_DROP_M)),
            ChainJoint(
                j4,
                "revolute",
                "wrist_mount",
                "wrist",
                lower=-SR20IA_J4_RANGE_RAD,
                upper=SR20IA_J4_RANGE_RAD,
                velocity=speeds[3],
            ),
            # The attachment site is turned half a turn about x, so its z points at the belt.
            ChainJoint("wrist_to_tool0", "fixed", "wrist", "tool0", rpy=(math.pi, 0.0, 0.0)),
        ]
    else:
        raise ValueError(f"no description for {arm.value}; it uses a vendor model")
    chain.append(ChainJoint("tool0_to_tcp", "fixed", "tool0", "tcp", (0.0, 0.0, JAW_TCP_OFFSET_M)))
    return chain


def forward_kinematics(chain: list[ChainJoint], positions: dict[str, float]) -> np.ndarray:
    """World-from-tcp transform (4, 4) at the given joint positions, by walking the chain."""
    transform = np.eye(4)
    for joint in chain:
        origin = np.eye(4)
        origin[:3, :3] = _rpy_matrix(joint.rpy)
        origin[:3, 3] = joint.xyz
        motion = np.eye(4)
        value = positions.get(joint.name, 0.0)
        axis = np.asarray(joint.axis, dtype=float)
        if joint.kind == "revolute":
            k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
            motion[:3, :3] = np.eye(3) + math.sin(value) * k + (1 - math.cos(value)) * (k @ k)
        elif joint.kind == "prismatic":
            motion[:3, 3] = value * axis
        transform = transform @ origin @ motion
    return transform


def to_urdf(name: str, chain: list[ChainJoint]) -> str:
    """URDF text for the chain. Links carry no geometry: this description is for kinematics and IK."""
    links = ["world"] + [joint.child for joint in chain]
    lines = [
        '<?xml version="1.0"?>',
        f'<robot name="{name}">',
        "  <!-- Generated by applications.pork_leg_alignment.sim.robot_description; do not edit by hand. -->",
    ]
    lines += [f'  <link name="{link}"/>' for link in links]
    for joint in chain:
        lines.append(f'  <joint name="{joint.name}" type="{joint.kind}">')
        lines.append(f'    <parent link="{joint.parent}"/>')
        lines.append(f'    <child link="{joint.child}"/>')
        lines.append(
            f'    <origin xyz="{" ".join(f"{v:.6f}" for v in joint.xyz)}" rpy="{" ".join(f"{v:.6f}" for v in joint.rpy)}"/>'
        )
        if joint.kind != "fixed":
            lines.append(f'    <axis xyz="{" ".join(f"{v:g}" for v in joint.axis)}"/>')
            lines.append(
                f'    <limit lower="{joint.lower:.6f}" upper="{joint.upper:.6f}" velocity="{joint.velocity:.4f}" effort="1000"/>'
            )
        lines.append("  </joint>")
    lines.append("</robot>")
    return "\n".join(lines) + "\n"
