"""The hold-down belt over the saw: the counterforce that lets the blade cut.

A spinning blade pushes back on whatever it cuts. A leg that is only resting on
a belt answers that push by sliding and turning, and a leg that turns while the
blade is in it gets a skewed cut, which is exactly the error the alignment
station exists to remove. Something has to hold the leg down while the blade
goes through.

Chosen by Lakshya on 2026-09-14: a hold-down belt. A short top belt runs over
the main belt at the saw, at the same speed, pressing down on whatever passes
under it. Nothing stops. A leg rides into a lead-in ramp, lifts the belt, and is
pressed onto the main belt by the belt's weight plus a set press force, the way
a sprung or pneumatically loaded top belt behaves.

Modelled as one body with two slide joints. Along x it is driven at belt speed
and rewound every step, the same trick that keeps the main belt endless
(`cell.py`). Along z it floats: a motor holds a constant downward force, so the
press force is the same for a thin leg and a thick one. The pressing surface is
rigid, so it bears on the tallest part of the leg, which is the ham. A real top
belt is compliant and wraps the product; that difference is not modelled.

Every dimension and force is an assumption until the line is measured.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import mujoco
import numpy as np

logger = logging.getLogger(__name__)

HOLD_DOWN_BODY = "hold_down"
HOLD_DOWN_X_JOINT = "hold_down_x"
HOLD_DOWN_Z_JOINT = "hold_down_z"
HOLD_DOWN_DRIVE = "hold_down_drive"
HOLD_DOWN_PRESS = "hold_down_press"
HOLD_DOWN_PLATE_GEOM = "hold_down_plate"
HOLD_DOWN_RAMP_GEOM = "hold_down_ramp"
BELT_BODY = "belt"
BELT_TOP_Z_M = 0.90
PLATE_HALF_THICKNESS_M = 0.010
# Damps the float so a leg entering the ramp lifts the belt without it
# bouncing. Chosen by eye in simulation, not measured.
FLOAT_DAMPING_NSPM = 300.0


@dataclass(frozen=True)
class HoldDownConfig:
    """Where the hold-down belt sits and how hard it presses. All assumed.

    Attributes:
        x_centre_m: Centre of the pressing section along the belt. Defaults to
            the default saw position so the leg is held through the whole cut.
        length_m: Length of the pressing section along the belt.
        y_inner_m: Edge of the belt nearest the open side. Kept inside the main
            belt edge so the top belt never reaches over the blade.
        y_outer_m: Edge nearest the far rail.
        rest_clearance_m: Gap between the top belt and the main belt with
            nothing under it. Above the height of a shank, below a ham.
        press_force_n: Downward force added to the belt's own weight.
        lift_range_m: How far the top belt can rise.
        lead_in_length_m: Length of the ramp at the upstream end.
        lead_in_angle_deg: Ramp angle up from the belt plane.
        plate_mass_kg: Moving mass of the top belt section.
    """

    x_centre_m: float = 1.10
    length_m: float = 0.70
    y_inner_m: float = 0.17
    y_outer_m: float = 0.80
    rest_clearance_m: float = 0.11
    press_force_n: float = 150.0
    lift_range_m: float = 0.25
    lead_in_length_m: float = 0.30
    lead_in_angle_deg: float = 25.0
    plate_mass_kg: float = 3.0

    def __post_init__(self) -> None:
        if self.y_outer_m <= self.y_inner_m:
            raise ValueError(f"outer edge {self.y_outer_m} must be beyond inner edge {self.y_inner_m}")
        if self.press_force_n < 0:
            raise ValueError(f"press force must be non-negative, got {self.press_force_n}")
        if not 0.0 < self.lead_in_angle_deg < 90.0:
            raise ValueError(f"lead-in angle must be between 0 and 90 degrees, got {self.lead_in_angle_deg}")


def add_hold_down(spec: mujoco.MjSpec, config: HoldDownConfig) -> None:
    """Add the hold-down belt and its two actuators to the cell.

    Call after the arm and gripper are attached: actuators are numbered in the
    order they are added, and the arm's controls are addressed by index.
    """
    half_y = (config.y_outer_m - config.y_inner_m) / 2
    body = spec.worldbody.add_body(
        name=HOLD_DOWN_BODY,
        pos=[
            config.x_centre_m,
            (config.y_inner_m + config.y_outer_m) / 2,
            BELT_TOP_Z_M + config.rest_clearance_m + PLATE_HALF_THICKNESS_M,
        ],
    )
    body.add_joint(
        name=HOLD_DOWN_X_JOINT, type=mujoco.mjtJoint.mjJNT_SLIDE, axis=[1, 0, 0], range=[-3, 3], armature=1.0
    )
    body.add_joint(
        name=HOLD_DOWN_Z_JOINT,
        type=mujoco.mjtJoint.mjJNT_SLIDE,
        axis=[0, 0, 1],
        range=[0.0, config.lift_range_m],
        damping=FLOAT_DAMPING_NSPM,
    )
    # Drawn see-through so the leg under it stays visible on video.
    solid = {"condim": 4, "friction": [0.8, 0.02, 0.001], "rgba": [0.20, 0.45, 0.62, 0.45]}
    body.add_geom(
        name=HOLD_DOWN_PLATE_GEOM,
        type=mujoco.mjtGeom.mjGEOM_BOX,
        size=[config.length_m / 2, half_y, PLATE_HALF_THICKNESS_M],
        mass=config.plate_mass_kg,
        **solid,
    )
    angle = math.radians(config.lead_in_angle_deg)
    half_ramp = config.lead_in_length_m / 2
    body.add_geom(
        name=HOLD_DOWN_RAMP_GEOM,
        type=mujoco.mjtGeom.mjGEOM_BOX,
        size=[half_ramp, half_y, PLATE_HALF_THICKNESS_M],
        # Rotating the box about y by the ramp angle lifts its upstream end.
        pos=[-config.length_m / 2 - half_ramp * math.cos(angle), 0.0, half_ramp * math.sin(angle)],
        quat=[math.cos(angle / 2), 0.0, math.sin(angle / 2), 0.0],
        mass=0.1 * config.plate_mass_kg,
        **solid,
    )
    exclude = spec.add_exclude()
    exclude.bodyname1 = HOLD_DOWN_BODY
    exclude.bodyname2 = BELT_BODY

    drive = spec.add_actuator(name=HOLD_DOWN_DRIVE, target=HOLD_DOWN_X_JOINT, trntype=mujoco.mjtTrn.mjTRN_JOINT)
    drive.set_to_velocity(kv=2000.0)
    drive.ctrlrange = [-1.0, 1.0]
    press = spec.add_actuator(name=HOLD_DOWN_PRESS, target=HOLD_DOWN_Z_JOINT, trntype=mujoco.mjtTrn.mjTRN_JOINT)
    press.set_to_motor()
    press.ctrlrange = [-max(config.press_force_n, 1.0), 0.0]


class HoldDown:
    """Runs the hold-down belt: drives it with the main belt and keeps it endless."""

    def __init__(self, model: mujoco.MjModel, config: HoldDownConfig) -> None:
        """Bind to a compiled cell that has a hold-down belt.

        Raises:
            ValueError: If the model has no hold-down belt.
        """
        self.config = config
        x_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, HOLD_DOWN_X_JOINT)
        if x_joint < 0:
            raise ValueError("the model has no hold-down belt")
        z_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, HOLD_DOWN_Z_JOINT)
        self._x_qadr = int(model.jnt_qposadr[x_joint])
        self._z_qadr = int(model.jnt_qposadr[z_joint])
        self._drive = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, HOLD_DOWN_DRIVE)
        self._press = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, HOLD_DOWN_PRESS)
        self._geoms = {
            mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, HOLD_DOWN_PLATE_GEOM),
            mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, HOLD_DOWN_RAMP_GEOM),
        }

    def start(self, data: mujoco.MjData, belt_speed_mps: float) -> None:
        """Run at belt speed and press with the configured force."""
        data.ctrl[self._drive] = belt_speed_mps
        data.ctrl[self._press] = -self.config.press_force_n
        data.qpos[self._x_qadr] = 0.0
        data.qpos[self._z_qadr] = 0.0

    def rewind(self, data: mujoco.MjData) -> None:
        """Return the drive joint to zero, keeping its velocity, as the main belt does."""
        data.qpos[self._x_qadr] = 0.0

    def lift_m(self, data: mujoco.MjData) -> float:
        """How far the top belt is lifted above its rest clearance."""
        return float(data.qpos[self._z_qadr])

    def force_on_body_n(self, model: mujoco.MjModel, data: mujoco.MjData, body: int) -> float:
        """Total normal force the top belt is pressing onto one body, newtons."""
        total = 0.0
        wrench = np.zeros(6)
        for i in range(data.ncon):
            contact = data.contact[i]
            geoms = (int(contact.geom1), int(contact.geom2))
            bodies = (int(model.geom_bodyid[geoms[0]]), int(model.geom_bodyid[geoms[1]]))
            if (geoms[0] in self._geoms and bodies[1] == body) or (geoms[1] in self._geoms and bodies[0] == body):
                mujoco.mj_contactForce(model, data, i, wrench)
                total += abs(float(wrench[0]))
        return total
