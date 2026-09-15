"""What the jaws are actually doing, measured from the model rather than assumed.

Every number here is read out of the compiled model instead of copied from the
XML, because the three that matter are all easy to get wrong in a way that still
produces a grasp that looks plausible:

* The actuator commands **one finger's joint**. The opening between the pads is
  the rest gap plus twice that joint. Treating the command as a half-width
  commanded 116 mm of opening around a 90 mm product, and the jaws closed on
  nothing.
* The tool centre point is not the middle of the pad. On this gripper the pad
  reaches 18 mm past the TCP along the approach direction, so a grasp height set
  from the TCP alone drives the pad tips into the belt. That jams the fingers,
  which then stall part-open holding 80 N vertically, and the product is never
  gripped at all.
* The fingers slide along the tool's **y** axis while the tool's yaw names its
  **x** axis, so a gripper set square to the product closes along its length.

None of the three raise an error. All three end with the product on the belt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import mujoco
import numpy as np

logger = logging.getLogger(__name__)

GRIPPER_ASSETS = Path(__file__).parent / "assets"
GRIP_ACTUATOR = "g_grip"
GRIP_JOINT = "g_finger_left_joint"
PAD_GEOM = "g_finger_left_pad"
PAD_SITES = ("g_pad_left", "g_pad_right")
TCP_SITE = "g_tcp"


class GripperModel(str, Enum):
    """Which gripper the arm carries."""

    PINCH = "pinch"  # the original functional stand-in for a Robotiq 2F-140
    JAW_GEH6180 = "jaw_geh6180"
    THREE_FINGER_3FG25 = "three_finger_3fg25"


@dataclass(frozen=True)
class GripperSpec:
    """What the cell needs to know about a gripper. Ratings are the datasheets'.

    Attributes:
        model: Which gripper.
        asset: Model file in the assets directory.
        pad_sites: Pad face sites as named in the cell, the actuated finger first.
        rated_force_n: Total grip force over all fingers at the actuator limit.
        mass_kg: Gripper mass.
    """

    model: GripperModel
    asset: str
    pad_sites: tuple[str, ...]
    rated_force_n: float
    mass_kg: float


GRIPPER_SPECS = {
    GripperModel.PINCH: GripperSpec(GripperModel.PINCH, "gripper.xml", PAD_SITES, 140.0, 0.9),
    GripperModel.JAW_GEH6180: GripperSpec(GripperModel.JAW_GEH6180, "jaw_gripper.xml", PAD_SITES, 1800.0, 2.6),
    GripperModel.THREE_FINGER_3FG25: GripperSpec(
        GripperModel.THREE_FINGER_3FG25, "three_finger_gripper.xml", ("g_pad_left", "g_pad_2", "g_pad_3"), 450.0, 1.6
    ),
}


def _opening_m(model: mujoco.MjModel, data: mujoco.MjData, pad_sites: tuple[str, ...]) -> float:
    """Size of what the pads would close on.

    Two jaws: the distance between the pad faces. Three fingers closing on the
    tool axis: twice the mean distance of the pad faces from that axis, which is
    the diameter of the largest cylinder they would just touch.
    """
    pads = [data.site_xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)] for name in pad_sites]
    if len(pads) == 2:
        return float(np.linalg.norm(pads[0] - pads[1]))
    tcp = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, TCP_SITE)
    origin = data.site_xpos[tcp]
    axis = data.site_xmat[tcp].reshape(3, 3)[:, 2]
    radii = [float(np.linalg.norm((pad - origin) - np.dot(pad - origin, axis) * axis)) for pad in pads]
    return 2.0 * float(np.mean(radii))


@dataclass(frozen=True)
class GripperGeometry:
    """Jaw geometry measured from the compiled model.

    Attributes:
        rest_gap_m: Distance between the pad faces with the joint at zero.
        travel_per_joint_m: Opening gained per metre of joint travel. Two, for a
            symmetric pair, but measured rather than assumed.
        joint_range_m: Lower and upper joint limits.
        pad_reach_m: How far the pad tip extends past the TCP along the approach
            direction. A grasp height must clear the support surface by at least
            this much.
        pad_height_m: Length of the pad along the approach direction.
    """

    rest_gap_m: float
    travel_per_joint_m: float
    joint_range_m: tuple[float, float]
    pad_reach_m: float
    pad_height_m: float

    @property
    def max_opening_m(self) -> float:
        """Widest the jaws go."""
        return self.rest_gap_m + self.travel_per_joint_m * self.joint_range_m[1]

    def joint_for_opening(self, opening_m: float) -> float:
        """Joint command that puts the pads `opening_m` apart.

        Raises:
            ValueError: If the opening is outside the jaws' range. A silently
                clipped command is a grasp that closes on nothing or crushes.
        """
        joint = (opening_m - self.rest_gap_m) / self.travel_per_joint_m
        low, high = self.joint_range_m
        if not low - 1e-9 <= joint <= high + 1e-9:
            raise ValueError(
                f"opening {1000 * opening_m:.1f} mm needs joint {1000 * joint:.1f} mm, "
                f"outside [{1000 * low:.1f}, {1000 * high:.1f}]; jaws span "
                f"{1000 * self.rest_gap_m:.1f} to {1000 * self.max_opening_m:.1f} mm"
            )
        return float(np.clip(joint, low, high))

    def opening_for_joint(self, joint_m: float) -> float:
        """Pad separation at a given joint value."""
        return self.rest_gap_m + self.travel_per_joint_m * joint_m


def measure_geometry(
    model: mujoco.MjModel, gripper: GripperSpec = GRIPPER_SPECS[GripperModel.PINCH]
) -> GripperGeometry:
    """Read the jaw geometry out of the model by posing it.

    The pads are moved to two known joint values and the resulting opening is
    measured, which gives both the rest gap and the travel ratio without
    trusting any number written in the XML. Coupled fingers follow the actuated
    one through their equality constraints only when the solver runs, so every
    coupled finger joint is set explicitly here.
    """
    joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, GRIP_JOINT)
    low, high = (float(v) for v in model.jnt_range[joint])
    coupled = _finger_joint_addresses(model)
    scratch = mujoco.MjData(model)

    def opening_at(value: float) -> tuple[float, np.ndarray, np.ndarray]:
        for address, sign in coupled:
            scratch.qpos[address] = sign * value
        mujoco.mj_kinematics(model, scratch)
        pad = scratch.site_xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, gripper.pad_sites[0])].copy()
        tcp = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, TCP_SITE)
        return (
            _opening_m(model, scratch, gripper.pad_sites),
            pad,
            np.concatenate([scratch.site_xpos[tcp], scratch.site_xmat[tcp]]),
        )

    rest_gap, _, _ = opening_at(0.0)
    probe = min(high, 0.02)
    opened, pad, tcp_pose = opening_at(probe)
    travel_per_joint = (opened - rest_gap) / probe

    pad_geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, PAD_GEOM)
    pad_half_height = float(model.geom_size[pad_geom][2])
    # The approach direction is the tool's +z. Measured along that axis, so the
    # answer does not depend on which way the arm happens to point the tool.
    approach = tcp_pose[3:].reshape(3, 3)[:, 2]
    pad_reach = float(np.dot(pad - tcp_pose[:3], approach)) + pad_half_height

    geometry = GripperGeometry(
        rest_gap_m=rest_gap,
        travel_per_joint_m=travel_per_joint,
        joint_range_m=(low, high),
        pad_reach_m=pad_reach,
        pad_height_m=2 * pad_half_height,
    )
    logger.debug(
        "gripper: opening %.1f to %.1f mm, pad reaches %.1f mm past the TCP",
        1000 * geometry.rest_gap_m,
        1000 * geometry.max_opening_m,
        1000 * geometry.pad_reach_m,
    )
    return geometry


def grasp_height_m(
    geometry: GripperGeometry, support_z_m: float, product_thickness_m: float, clearance_m: float = 0.002
) -> float:
    """Tool height that puts the pads beside the product without touching the support.

    The pad tip is held `clearance_m` above the support surface. Anything lower
    jams the fingers against it, and jammed fingers stall part-open while the
    grasp reports a commanded width it never reached.

    Raises:
        ValueError: If the product is too thin for the pads to reach it at all
            without fouling the support.
    """
    tool_z = support_z_m + clearance_m + geometry.pad_reach_m
    lowest_contact = support_z_m + clearance_m
    if lowest_contact >= support_z_m + product_thickness_m:
        raise ValueError(
            f"a {1000 * product_thickness_m:.1f} mm product cannot be gripped with "
            f"{1000 * clearance_m:.1f} mm of pad clearance"
        )
    return tool_z


def command_opening(data: mujoco.MjData, model: mujoco.MjModel, geometry: GripperGeometry, opening_m: float) -> None:
    """Command the jaws to an opening, in metres between the pad faces."""
    actuator = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, GRIP_ACTUATOR)
    data.ctrl[actuator] = geometry.joint_for_opening(opening_m)


def measured_opening_m(
    data: mujoco.MjData, model: mujoco.MjModel, gripper: GripperSpec = GRIPPER_SPECS[GripperModel.PINCH]
) -> float:
    """Actual opening right now, which is not the commanded one when jammed."""
    return _opening_m(model, data, gripper.pad_sites)


def _finger_joint_addresses(model: mujoco.MjModel) -> list[tuple[int, float]]:
    """Address in `qpos` and ratio to the actuated joint of every coupled finger joint.

    Read from the joint equalities, so two jaws moving oppositely and three
    fingers moving together are both handled without naming either design. An
    equality reads joint1 = polycoef[0] + polycoef[1] * joint2, and the actuated
    joint may be either side of it: the jaw gripper names it as joint1.
    """
    actuated = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, GRIP_JOINT)
    addresses = [(int(model.jnt_qposadr[actuated]), 1.0)]
    for eq in range(model.neq):
        if model.eq_type[eq] != mujoco.mjtEq.mjEQ_JOINT:
            continue
        joint1, joint2 = int(model.eq_obj1id[eq]), int(model.eq_obj2id[eq])
        slope = float(model.eq_data[eq][1])
        if joint2 == actuated:
            addresses.append((int(model.jnt_qposadr[joint1]), slope))
        elif joint1 == actuated and slope != 0.0:
            addresses.append((int(model.jnt_qposadr[joint2]), 1.0 / slope))
    return addresses
