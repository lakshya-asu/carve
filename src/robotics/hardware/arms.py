"""The arms the cell can be built with, and what the rest of the cell needs to know about each.

Neil's question is SCARA against six-axis, so the arm has to be a choice in the
config rather than a fact in the code. Each arm is described once by an
`ArmSpec` (joint names, home pose, attachment site, ratings) and built once by a
function returning an `MjSpec` that the scene attaches to its mount. Nothing
else in the cell may name an arm's joints directly.

Three arms:

* UR5e, from MuJoCo Menagerie, kept because every earlier experiment ran on it.
* UR20, 20 kg six-axis, built from Universal Robots' published DH parameters,
  link masses, centres of mass and inertias.
* FANUC SR-20iA, 20 kg SCARA, built from its datasheet. The two arm lengths are
  not printed; 550 and 550 mm are derived from the work-envelope drawing.

Sources and every number's provenance: `library/hardware/arm-models-for-sim.md`.
Neither vendor publishes joint torque limits, so the built arms have none, and
a trajectory that is infeasible on the real arm will still run here. Payload
feasibility has to be checked against the published payload curve, not against
whether the simulation moved.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import mujoco
import numpy as np

logger = logging.getLogger(__name__)

# parents[3] is the repo root: this file is src/robotics/hardware/arms.py.
MENAGERIE = Path(__file__).resolve().parents[3] / "third_party" / "mujoco_menagerie"
UR5E_XML = MENAGERIE / "universal_robots_ur5e" / "ur5e.xml"
ARM_NOTE = "library/hardware/arm-models-for-sim.md"


class ArmModel(str, Enum):
    """Which arm the cell is built with."""

    UR5E = "ur5e"
    UR20 = "ur20"
    SR20IA = "sr20ia"


@dataclass(frozen=True)
class ArmSpec:
    """What the cell needs to know about an arm, independent of how it is built.

    Attributes:
        model: Which arm.
        prefix: Prefix every name gets when the arm is attached to the cell.
        joints: Joint names in chain order, without the prefix.
        actuators: One position actuator per joint, same order, without the prefix.
        home_qpos: Joint values of the resting pose, radians or metres.
        attachment_site: Site the gripper mounts on, without the prefix. Its +z
            points out of the flange.
        payload_kg: Rated payload.
        reach_m: Published maximum reach.
        max_joint_speed: Per joint, rad/s for revolute and m/s for prismatic.
        tool_tilts: Whether the tool axis can leave vertical. A SCARA's cannot.
    """

    model: ArmModel
    prefix: str
    joints: tuple[str, ...]
    actuators: tuple[str, ...]
    home_qpos: tuple[float, ...]
    attachment_site: str
    payload_kg: float
    reach_m: float
    max_joint_speed: tuple[float, ...]
    tool_tilts: bool

    @property
    def dof(self) -> int:
        """Number of arm joints."""
        return len(self.joints)

    @property
    def joint_names(self) -> tuple[str, ...]:
        """Joint names as they appear in the compiled cell."""
        return tuple(self.prefix + name for name in self.joints)

    @property
    def actuator_names(self) -> tuple[str, ...]:
        """Actuator names as they appear in the compiled cell."""
        return tuple(self.prefix + name for name in self.actuators)

    @property
    def site_name(self) -> str:
        """Attachment site name as it appears in the compiled cell."""
        return self.prefix + self.attachment_site


UR5E_SPEC = ArmSpec(
    model=ArmModel.UR5E,
    prefix="ur_",
    joints=(
        "shoulder_pan_joint",
        "shoulder_lift_joint",
        "elbow_joint",
        "wrist_1_joint",
        "wrist_2_joint",
        "wrist_3_joint",
    ),
    actuators=("shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3"),
    home_qpos=(-1.5708, -1.5708, 1.5708, -1.5708, -1.5708, 0.0),
    attachment_site="attachment_site",
    payload_kg=5.0,
    reach_m=0.850,
    # UR5e techsheet: 180 deg/s on every joint.
    max_joint_speed=(math.pi,) * 6,
    tool_tilts=True,
)

UR20_SPEC = ArmSpec(
    model=ArmModel.UR20,
    prefix="ur20_",
    joints=(
        "shoulder_pan_joint",
        "shoulder_lift_joint",
        "elbow_joint",
        "wrist_1_joint",
        "wrist_2_joint",
        "wrist_3_joint",
    ),
    actuators=("shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3"),
    home_qpos=(-1.5708, -1.5708, 1.5708, -1.5708, -1.5708, 0.0),
    attachment_site="attachment_site",
    payload_kg=20.0,
    reach_m=1.750,
    max_joint_speed=tuple(math.radians(v) for v in (120.0, 120.0, 150.0, 210.0, 210.0, 210.0)),
    tool_tilts=True,
)

SR20IA_SPEC = ArmSpec(
    model=ArmModel.SR20IA,
    prefix="sr_",
    joints=("j1", "j2", "j3", "j4"),
    actuators=("j1_servo", "j2_servo", "j3_servo", "j4_servo"),
    home_qpos=(0.0, math.radians(90.0), 0.0, 0.0),
    attachment_site="attachment_site",
    payload_kg=20.0,
    reach_m=1.100,
    max_joint_speed=(math.radians(440.0), math.radians(500.0), 2.8, math.radians(1700.0)),
    tool_tilts=False,
)

ARM_SPECS = {spec.model: spec for spec in (UR5E_SPEC, UR20_SPEC, SR20IA_SPEC)}

# UR20 standard DH parameters (a, d, alpha), from Universal Robots' "DH parameters
# for calculations of kinematics and dynamics" page, fetched 2026-09-14.
UR20_DH = (
    (0.0, 0.2363, math.pi / 2),
    (-0.8620, 0.0, 0.0),
    (-0.7287, 0.0, 0.0),
    (0.0, 0.2010, math.pi / 2),
    (0.0, 0.1593, -math.pi / 2),
    (0.0, 0.1543, 0.0),
)

# UR20 link mass (kg), centre of mass in the link's DH frame (m), and inertia as
# printed (row-major 3x3), same page. The page gives no unit or reference point
# for the inertia; kg m^2 about the centre of mass is the reading that matches
# the magnitudes (unverified).
UR20_LINKS = (
    (16.343, (0.0, -0.0610, 0.0062), (0.0887, -0.0001, -0.0001, -0.0001, 0.0763, 0.0072, -0.0001, 0.0072, 0.0842)),
    (29.632, (0.5226, 0.0, 0.2098), (0.1467, 0.0002, -0.0516, 0.0002, 4.6659, 0.0, -0.0516, 0.0, 4.6348)),
    (7.879, (0.3234, 0.0, 0.0604), (0.0261, -0.0001, -0.0290, -0.0001, 0.7576, 0.0, -0.0290, 0.0, 0.7533)),
    (3.054, (0.0, -0.0026, 0.0393), (0.0056, 0.0, 0.0, 0.0, 0.0054, 0.0004, 0.0, 0.0004, 0.0040)),
    (3.126, (0.0, 0.0024, 0.0379), (0.0059, 0.0, 0.0, 0.0, 0.0058, -0.0004, 0.0, -0.0004, 0.0043)),
    (0.846, (0.0, -0.0003, -0.0318), (0.0009, 0.0, 0.0, 0.0, 0.0009, 0.0, 0.0, 0.0, 0.0012)),
)
# Drawn radius of each UR20 link, metres. Visual and collision only; read off
# product photos, not a dimension UR publishes.
UR20_LINK_RADIUS_M = (0.090, 0.075, 0.060, 0.050, 0.050, 0.045)
# Position servo stiffness per joint, N m/rad. UR publishes no torque limits or
# servo gains; these are high enough that the arm tracks under its own weight
# with gravity compensation on, chosen in simulation.
UR20_KP = (200000.0, 200000.0, 120000.0, 30000.0, 30000.0, 20000.0)

# FANUC SR-20iA, from its datasheet unless marked.
SR20IA_ARM_LENGTHS_M = (0.550, 0.550)  # derived from the envelope drawing, unverified
SR20IA_J3_STROKE_M = 0.300
SR20IA_J12_RANGE_RAD = math.radians(145.0)
SR20IA_J4_RANGE_RAD = math.radians(720.0)
# Not published: arm plane height above the mount, quill length and link
# masses. Assumed, sized to the 64 kg mechanical weight.
SR20IA_ARM_PLANE_HEIGHT_M = 0.60
SR20IA_QUILL_LENGTH_M = 0.45
SR20IA_LINK_MASS_KG = (18.0, 10.0, 3.0, 1.0)
# J4 at 800 N m/rad let a jaw's uneven squeeze on a shank twist the tool a few
# degrees, so the pads closed skewed and the finger arms bore on the leg; 8000
# holds it (2026-09-15). Both values are assumptions, as the UR20's are.
SR20IA_KP = (30000.0, 20000.0, 40000.0, 8000.0)

ARM_RGBA = (0.82, 0.84, 0.86, 1.0)
JOINT_ARMATURE = 0.5  # rotor inertia is not published for either arm; keeps the servos stable

# Integral action on the joint position loop, applied by whatever steps the
# cell (`Cell.step`). MuJoCo's position actuator is a pure spring and damper, so
# under a leg's weight it settles a few millimetres low: on a commanded 5 mm
# lift the UR20 rose 1.6 mm and the SR-20iA 2.6 mm (2026-09-14). A real drive
# closes its position loop with an integrator and holds a rated payload at its
# repeatability (UR20 0.05 mm, SR-20iA 0.01 mm, both datasheets). The gain is
# the rate at which the command is corrected per unit of standing error, and
# the limit bounds the correction so a joint held against something cannot
# wind up. Both chosen in simulation against the check in
# plan/overnight-2026-09-14.md task 4b: at 10 /s the UR20 rose 5.08 mm and the
# SR-20iA 5.06 mm of a commanded 5 mm holding the default leg, steady within
# 0.04 mm over the next second; at 20 /s the UR20 hunted at 3 Hz, a millimetre
# either way at the tool; at 5 /s it was still creeping 0.3 s after the move
# (measured 2026-09-15).
SERVO_INTEGRAL_GAIN_PER_S = 10.0
SERVO_INTEGRAL_LIMIT = 0.05  # radians, or metres on a prismatic joint


def _rot_x(angle: float) -> np.ndarray:
    c, s = math.cos(angle), math.sin(angle)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def _quat_x(angle: float) -> list[float]:
    return [math.cos(angle / 2), math.sin(angle / 2), 0.0, 0.0]


def dh_transform(theta: float, a: float, d: float, alpha: float) -> np.ndarray:
    """Standard DH link transform Rz(theta) Tz(d) Tx(a) Rx(alpha), as a 4x4 matrix."""
    ct, st = math.cos(theta), math.sin(theta)
    ca, sa = math.cos(alpha), math.sin(alpha)
    return np.array(
        [
            [ct, -st * ca, st * sa, a * ct],
            [st, ct * ca, -ct * sa, a * st],
            [0.0, sa, ca, d],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )


def build_ur20() -> mujoco.MjSpec:
    """A UR20 as a MuJoCo spec, one body per DH frame.

    Each link body sits at its DH frame with the pose Tz(d) Tx(a) Rx(alpha)
    relative to the previous frame. The joint rotates about the previous frame's
    z axis, so its axis and anchor are that axis and origin expressed in the
    link's own frame. Forward kinematics then equal the DH product exactly, which
    `tests/test_arms.py` checks at random configurations.
    """
    spec = mujoco.MjSpec()
    spec.modelname = "ur20"
    spec.compiler.autolimits = True
    # MjSpec reads angles in degrees unless told otherwise; every limit here is
    # in radians, and without this a 2 pi range compiled to 0.11 rad.
    spec.compiler.degree = False
    parent = spec.worldbody.add_body(name="base")
    parent.add_geom(
        type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[0.10, 0.04, 0.0], pos=[0.0, 0.0, 0.04], rgba=list(ARM_RGBA)
    )
    for index, ((a, d, alpha), (mass, com, inertia), radius, kp) in enumerate(
        zip(UR20_DH, UR20_LINKS, UR20_LINK_RADIUS_M, UR20_KP, strict=True)
    ):
        rotation = _rot_x(alpha)
        body = parent.add_body(name=f"link{index + 1}", pos=[a, 0.0, d], quat=_quat_x(alpha))
        anchor = -rotation.T @ np.array([a, 0.0, d])
        axis = rotation.T @ np.array([0.0, 0.0, 1.0])
        body.add_joint(
            name=UR20_SPEC.joints[index],
            type=mujoco.mjtJoint.mjJNT_HINGE,
            pos=anchor.tolist(),
            axis=axis.tolist(),
            range=[-2 * math.pi, 2 * math.pi],
            armature=JOINT_ARMATURE,
        )
        body.explicitinertial = True
        body.mass = mass
        body.ipos = list(com)
        m = inertia
        body.fullinertia = [m[0], m[4], m[8], m[1], m[2], m[5]]
        body.gravcomp = 1.0
        # The first link's anchor is the base origin, so a capsule from there
        # would sink into the base casing and the pedestal and jam the joint.
        if index > 0 and float(np.linalg.norm(anchor)) > 1e-6:
            body.add_geom(
                type=mujoco.mjtGeom.mjGEOM_CAPSULE,
                fromto=[*anchor.tolist(), 0.0, 0.0, 0.0],
                size=[radius, 0.0, 0.0],
                density=0.0,
                rgba=list(ARM_RGBA),
            )
        body.add_geom(type=mujoco.mjtGeom.mjGEOM_SPHERE, size=[radius, 0.0, 0.0], density=0.0, rgba=list(ARM_RGBA))
        actuator = spec.add_actuator(
            name=UR20_SPEC.actuators[index], target=UR20_SPEC.joints[index], trntype=mujoco.mjtTrn.mjTRN_JOINT
        )
        actuator.set_to_position(kp=kp, dampratio=1.0)
        parent = body
    parent.add_site(name=UR20_SPEC.attachment_site, size=[0.01, 0.0, 0.0])
    return spec


def build_sr20ia() -> mujoco.MjSpec:
    """A FANUC SR-20iA as a MuJoCo spec: two horizontal arms, a quill, a wrist.

    J1 and J2 turn about vertical axes, J3 slides the quill down, J4 turns the
    tool about vertical. The attachment site points its +z straight down, which
    is the only direction a SCARA's tool can point.
    """
    spec = mujoco.MjSpec()
    spec.modelname = "sr20ia"
    spec.compiler.autolimits = True
    spec.compiler.degree = False
    l1, l2 = SR20IA_ARM_LENGTHS_M
    base = spec.worldbody.add_body(name="base")
    base.add_geom(
        type=mujoco.mjtGeom.mjGEOM_CYLINDER,
        size=[0.12, SR20IA_ARM_PLANE_HEIGHT_M / 2, 0.0],
        pos=[0.0, 0.0, SR20IA_ARM_PLANE_HEIGHT_M / 2],
        rgba=list(ARM_RGBA),
    )
    joints = SR20IA_SPEC.joints
    arm1 = base.add_body(name="arm1", pos=[0.0, 0.0, SR20IA_ARM_PLANE_HEIGHT_M])
    arm1.add_joint(
        name=joints[0],
        type=mujoco.mjtJoint.mjJNT_HINGE,
        axis=[0, 0, 1],
        range=[-SR20IA_J12_RANGE_RAD, SR20IA_J12_RANGE_RAD],
        armature=JOINT_ARMATURE,
    )
    # Raised clear of the column top: a capsule sitting 20 mm into the column made
    # a contact that jammed J1 and J2 against their servos.
    arm1.add_geom(
        type=mujoco.mjtGeom.mjGEOM_CAPSULE, fromto=[0, 0, 0.09, l1, 0, 0.09], size=[0.07, 0, 0], rgba=list(ARM_RGBA)
    )
    arm2 = arm1.add_body(name="arm2", pos=[l1, 0.0, 0.0])
    arm2.add_joint(
        name=joints[1],
        type=mujoco.mjtJoint.mjJNT_HINGE,
        axis=[0, 0, 1],
        range=[-SR20IA_J12_RANGE_RAD, SR20IA_J12_RANGE_RAD],
        armature=JOINT_ARMATURE,
    )
    arm2.add_geom(
        type=mujoco.mjtGeom.mjGEOM_CAPSULE, fromto=[0, 0, -0.05, l2, 0, -0.05], size=[0.06, 0, 0], rgba=list(ARM_RGBA)
    )
    quill = arm2.add_body(name="quill", pos=[l2, 0.0, 0.0])
    quill.add_joint(
        name=joints[2],
        type=mujoco.mjtJoint.mjJNT_SLIDE,
        axis=[0, 0, -1],
        range=[0.0, SR20IA_J3_STROKE_M],
        armature=JOINT_ARMATURE,
    )
    quill.add_geom(
        type=mujoco.mjtGeom.mjGEOM_CYLINDER,
        size=[0.025, SR20IA_QUILL_LENGTH_M / 2, 0.0],
        pos=[0.0, 0.0, -SR20IA_QUILL_LENGTH_M / 2 + 0.1],
        rgba=list(ARM_RGBA),
    )
    wrist = quill.add_body(name="wrist", pos=[0.0, 0.0, -SR20IA_QUILL_LENGTH_M + 0.1])
    wrist.add_joint(
        name=joints[3],
        type=mujoco.mjtJoint.mjJNT_HINGE,
        axis=[0, 0, 1],
        range=[-SR20IA_J4_RANGE_RAD, SR20IA_J4_RANGE_RAD],
        armature=JOINT_ARMATURE,
    )
    wrist.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[0.05, 0.015, 0.0], rgba=list(ARM_RGBA))
    wrist.add_site(name=SR20IA_SPEC.attachment_site, quat=[0.0, 1.0, 0.0, 0.0], size=[0.01, 0.0, 0.0])

    for body, mass in zip((arm1, arm2, quill, wrist), SR20IA_LINK_MASS_KG, strict=True):
        body.gravcomp = 1.0
        for geom in body.geoms:
            geom.density = 0.0
        body.explicitinertial = True
        body.mass = mass
        body.inertia = [0.05 * mass, 0.05 * mass, 0.05 * mass]

    for joint, actuator, kp in zip(joints, SR20IA_SPEC.actuators, SR20IA_KP, strict=True):
        servo = spec.add_actuator(name=actuator, target=joint, trntype=mujoco.mjtTrn.mjTRN_JOINT)
        servo.set_to_position(kp=kp, dampratio=1.0)
    return spec


def build_arm(model: ArmModel) -> mujoco.MjSpec:
    """The spec for one arm, ready to attach at the cell's mount site.

    Raises:
        FileNotFoundError: If the UR5e is requested and the Menagerie checkout is missing.
    """
    if model is ArmModel.UR5E:
        if not UR5E_XML.exists():
            raise FileNotFoundError(
                f"UR5e model not found at {UR5E_XML}. Fetch it with:\n"
                "  git clone --depth 1 --filter=blob:none --sparse "
                "https://github.com/google-deepmind/mujoco_menagerie.git third_party/mujoco_menagerie\n"
                "  cd third_party/mujoco_menagerie && git sparse-checkout set universal_robots_ur5e"
            )
        return mujoco.MjSpec.from_file(str(UR5E_XML))
    if model is ArmModel.UR20:
        return build_ur20()
    return build_sr20ia()
