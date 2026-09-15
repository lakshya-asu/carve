"""The saw that takes the trotter off, and where on the leg its cut lands.

The station exists for this cut. Operators orient each leg so its trotter hangs
off the open side of the belt; downstream, a blade standing just outside that
edge takes the foot off as the leg rides past. Alignment is therefore not "leg
roughly across the belt": it is the hock joint sitting on the blade plane, with
the leg square to the blade, at the moment the leg reaches it, and staying
there while the blade goes through.

Layout, as described by Lakshya on 2026-09-14 and pending measurement: a
circular blade (the only foot saw in the customer's footage is a handheld
circular saw) standing vertical, its plane parallel to belt travel, a small
clearance outside the open edge. The leg keeps moving; nothing stops it at the
saw. Every dimension is a parameter in `SawConfig`.

MuJoCo cannot cut a mesh, so the cut is a process with two events. It starts
when the blade's surface meets the leg's surface, found with `mj_geomDistance`.
While the blade is in the leg it pushes back on it with a feed resistance, which
is what makes a hold-down necessary (`holddown.py`). It ends when the leg has
travelled its own width past the blade's leading edge. Then the trotter weld is
switched off, the one-piece skin is swapped for the ham and trotter, and the
trotter falls.

Where the blade plane crosses the leg is scored at both events, so a leg that
turns or slides under the blade's push shows up as a cut that moved while it
was being made.

The contact distance is measured against every collision section of the leg
(`LEG_COLLISION_GEOMS`), whose short convex hulls follow the drawn outline, so
the blade meets the leg where the leg's surface is.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum

import mujoco
import numpy as np

from meat_cell_sim.product import (
    HOCK_FRACTION,
    LEG_COLLISION_GEOMS,
    LEG_SKIN_GEOM,
    PRODUCT_BODY,
    TROTTER_WELD,
    LegConfig,
    leg_centreline,
    leg_half_width_m,
)

logger = logging.getLogger(__name__)

SAW_BODY = "saw_blade"
SAW_DISC_GEOM = "saw_disc"
BELT_BODY = "belt"
BELT_GEOM = "belt_surface"
BELT_JOINT = "belt_x"
PRODUCT_JOINT = "slab_free"
BELT_TOP_Z_M = 0.90
BLADE_THICKNESS_M = 0.003
CENTRELINE_SAMPLES = 721  # one sample per millimetre on a 722 mm leg
# Distances beyond this are not resolved; only contact matters.
CONTACT_SEARCH_M = 0.01
# Skip the distance query while every point of the leg is this far upstream of
# the blade. It runs every step, and two hull queries per step add up.
NEAR_BLADE_M = 0.20


@dataclass(frozen=True)
class SawConfig:
    """Where the blade stands, how big it is, and how hard it pushes. All unmeasured.

    Attributes:
        x_m: Blade centre along the belt, world frame.
        edge_clearance_m: Distance from the belt's open edge out to the blade
            plane.
        blade_diameter_m: 250 to 300 mm matches the handheld saw in the
            customer's footage, estimated against the operator's hand.
        blade_centre_height_m: Blade centre above the belt surface. The default
            puts the widest part of the blade at the height of the default
            leg's hock centreline.
        blade_speed_rpm: Drives the drawing only.
        feed_resistance_n: Force the blade applies against the leg's travel
            while it is cutting. No published figure for a circular saw in a
            bone-in pork shank was found; the default is a placeholder to sweep.
        vertical_force_n: Vertical force from the blade on the leg while cutting,
            positive up. A blade whose teeth rise through the cut lifts the
            piece; one whose teeth fall presses it down. Zero until the blade's
            rotation direction and a force figure are known.
        cut_timeout_s: A cut still in progress after this long is recorded as
            stalled.
    """

    x_m: float = 1.10
    edge_clearance_m: float = 0.03
    blade_diameter_m: float = 0.30
    blade_centre_height_m: float = 0.045
    blade_speed_rpm: float = 1800.0
    feed_resistance_n: float = 60.0
    vertical_force_n: float = 0.0
    cut_timeout_s: float = 2.0

    def __post_init__(self) -> None:
        if self.edge_clearance_m < BLADE_THICKNESS_M:
            raise ValueError(f"the blade would touch the belt: clearance {self.edge_clearance_m} m")
        if self.blade_diameter_m <= 0:
            raise ValueError(f"blade diameter must be positive, got {self.blade_diameter_m}")
        if self.feed_resistance_n < 0:
            raise ValueError(f"feed resistance must be non-negative, got {self.feed_resistance_n}")


class CutOutcome(str, Enum):
    """What happened when a leg went past the saw."""

    CUT = "cut"
    GRAZED = "grazed"  # the blade touched the leg but its plane never crossed the centreline
    STALLED = "stalled"  # the blade entered the leg and never came out
    TROTTER_NOT_OVER_BLADE = "trotter_not_over_blade"


@dataclass(frozen=True)
class CutResult:
    """One leg's pass through the saw.

    Attributes:
        outcome: How the pass ended.
        time_s: When the blade first touched the leg, or when the leg cleared
            the blade untouched.
        through_s: When the blade came out the other side. NaN unless cut.
        offset_from_hock_m: Along the leg, from the hock joint to where the blade
            plane crossed the centreline at first contact. Positive is toward the
            trotter tip, which leaves foot on the ham; negative is into the
            shank. NaN if the blade never crossed the leg.
        offset_at_exit_m: The same, when the blade came out. Differs from the
            entry offset only if the leg moved under the blade's push.
        angle_rad: Between the leg's long axis and the blade normal at first
            contact, pointing out over the edge. Zero is a square cut; positive
            means the trotter tip leans downstream. NaN if never crossed.
        yaw_drift_rad: How far the leg turned while the blade was in it.
        slip_m: How far the leg slid relative to the belt surface while the
            blade was in it, in the belt plane.
    """

    outcome: CutOutcome
    time_s: float
    through_s: float = math.nan
    offset_from_hock_m: float = math.nan
    offset_at_exit_m: float = math.nan
    angle_rad: float = math.nan
    yaw_drift_rad: float = math.nan
    slip_m: float = math.nan


def blade_plane_y_m(spec_or_model: mujoco.MjSpec | mujoco.MjModel, config: SawConfig) -> float:
    """World y of the blade plane: the belt's open edge minus the clearance."""
    if isinstance(spec_or_model, mujoco.MjSpec):
        belt_y = float(spec_or_model.body(BELT_BODY).pos[1])
        half_width = float(spec_or_model.geom(BELT_GEOM).size[1])
    else:
        model = spec_or_model
        belt_y = float(model.body_pos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, BELT_BODY)][1])
        half_width = float(model.geom_size[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, BELT_GEOM)][1])
    return belt_y - half_width - config.edge_clearance_m


def add_saw(spec: mujoco.MjSpec, config: SawConfig) -> None:
    """Add the blade to the cell: a mocap body so it can spin without an actuator.

    An actuator would shift every control index after the belt, and the arm's
    controls are addressed by index. The blade has no collision response; the
    cut is found by measuring the distance from its surface to the leg's.
    """
    radius = config.blade_diameter_m / 2
    centre = [config.x_m, blade_plane_y_m(spec, config), BELT_TOP_Z_M + config.blade_centre_height_m]
    blade = spec.worldbody.add_body(name=SAW_BODY, pos=centre, mocap=True)
    # A cylinder's axis is its local z; turn it onto world y so the disc stands
    # in the x-z plane, parallel to belt travel.
    axis_to_y = [math.cos(-math.pi / 4), math.sin(-math.pi / 4), 0.0, 0.0]
    visual = {"contype": 0, "conaffinity": 0, "group": 2, "density": 0.0}
    blade.add_geom(
        name=SAW_DISC_GEOM,
        type=mujoco.mjtGeom.mjGEOM_CYLINDER,
        size=[radius, BLADE_THICKNESS_M / 2, 0.0],
        quat=axis_to_y,
        rgba=[0.80, 0.82, 0.85, 1.0],
        **visual,
    )
    # Two dark bars across the disc, so its rotation is visible on video.
    for angle in (0.0, math.pi / 2):
        blade.add_geom(
            type=mujoco.mjtGeom.mjGEOM_BOX,
            size=[0.9 * radius, BLADE_THICKNESS_M, 0.008],
            quat=[math.cos(angle / 2), 0.0, math.sin(angle / 2), 0.0],
            rgba=[0.25, 0.27, 0.30, 1.0],
            **visual,
        )
    blade.add_geom(
        name="saw_arbor",
        type=mujoco.mjtGeom.mjGEOM_CYLINDER,
        size=[0.035, 0.04, 0.0],
        quat=axis_to_y,
        pos=[0.0, -0.04, 0.0],
        rgba=[0.35, 0.37, 0.40, 1.0],
        **visual,
    )
    spec.worldbody.add_geom(
        name="saw_post",
        type=mujoco.mjtGeom.mjGEOM_BOX,
        size=[0.04, 0.04, (centre[2] - radius) / 2],
        pos=[centre[0], centre[1] - 0.08, (centre[2] - radius) / 2],
        rgba=[0.72, 0.74, 0.76, 1.0],
        **visual,
    )


def _name_id(model: mujoco.MjModel, kind: mujoco.mjtObj, name: str) -> int:
    index = mujoco.mj_name2id(model, kind, name)
    if index < 0:
        raise ValueError(f"the model has no {name!r}; build the cell with a leg and a saw")
    return int(index)


def _yaw_rad(rotation: np.ndarray) -> float:
    return math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))


@dataclass
class _CutInProgress:
    started_s: float
    offset_m: float
    angle_rad: float
    yaw_rad: float
    slip_xy_m: np.ndarray


class Saw:
    """Spins the blade, detects contact, pushes back while cutting, and scores the cut.

    Holds one result per leg pass; `rearm` clears it when a new leg is placed.
    """

    def __init__(self, model: mujoco.MjModel, config: SawConfig, leg: LegConfig) -> None:
        """Bind to a compiled cell that has a blade and a leg with a trotter weld.

        Raises:
            ValueError: If the model lacks the blade, the trotter weld or the leg's parts.
        """
        self.config = config
        self.leg = leg
        self._mocap = int(model.body_mocapid[_name_id(model, mujoco.mjtObj.mjOBJ_BODY, SAW_BODY)])
        self._leg_body = _name_id(model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
        self._weld = _name_id(model, mujoco.mjtObj.mjOBJ_EQUALITY, TROTTER_WELD)
        self._disc = _name_id(model, mujoco.mjtObj.mjOBJ_GEOM, SAW_DISC_GEOM)
        self._skin = _name_id(model, mujoco.mjtObj.mjOBJ_GEOM, LEG_SKIN_GEOM)
        self._parts = tuple(_name_id(model, mujoco.mjtObj.mjOBJ_GEOM, name) for name in LEG_COLLISION_GEOMS)
        self._belt_dof = int(model.jnt_dofadr[_name_id(model, mujoco.mjtObj.mjOBJ_JOINT, BELT_JOINT)])
        self._leg_dof = int(model.jnt_dofadr[_name_id(model, mujoco.mjtObj.mjOBJ_JOINT, PRODUCT_JOINT)])
        self._timestep_s = float(model.opt.timestep)
        self.blade_y_m = blade_plane_y_m(model, config)
        self._radius_m = config.blade_diameter_m / 2
        self._fractions = np.linspace(0.0, 1.0, CENTRELINE_SAMPLES)
        centreline = leg_centreline(leg, self._fractions)
        self._centreline_xy = centreline[:, :2]
        self._centreline_z = centreline[:, 2]
        self._half_width_m = leg_half_width_m(leg, self._fractions)
        self._hock_x_m = float(leg_centreline(leg, np.array([HOCK_FRACTION]))[0, 0])
        self._cut: _CutInProgress | None = None
        self.result: CutResult | None = None

    @property
    def cutting(self) -> bool:
        """The blade is in the leg right now."""
        return self._cut is not None

    def rearm(self, model: mujoco.MjModel, data: mujoco.MjData) -> None:
        """Weld the trotter back on, draw the leg whole, forget the last pass."""
        data.eq_active[self._weld] = 1
        data.xfrc_applied[self._leg_body] = 0.0
        self._show_whole(model, whole=True)
        self._cut = None
        self.result = None

    def _show_whole(self, model: mujoco.MjModel, whole: bool) -> None:
        model.geom_rgba[self._skin, 3] = 1.0 if whole else 0.0
        for part in self._parts:
            model.geom_rgba[part, 3] = 0.0 if whole else 1.0

    def blade_gap_m(self, model: mujoco.MjModel, data: mujoco.MjData) -> float:
        """Smallest distance from the blade's surface to the leg's, capped at `CONTACT_SEARCH_M`."""
        return min(
            float(mujoco.mj_geomDistance(model, data, self._disc, part, CONTACT_SEARCH_M, None)) for part in self._parts
        )

    def _crossing(self, data: mujoco.MjData) -> tuple[int, float, np.ndarray] | None:
        """Where the blade plane crosses the leg's centreline: sample index, blend, world xy."""
        rotation = data.xmat[self._leg_body].reshape(3, 3)
        world_xy = data.xpos[self._leg_body][:2] + self._centreline_xy @ rotation[:2, :2].T
        outboard = world_xy[:, 1] - self.blade_y_m
        crossings = np.flatnonzero(np.sign(outboard[:-1]) != np.sign(outboard[1:]))
        if crossings.size == 0:
            return None
        # The crossing nearest the tip is the one on the part hanging over the edge.
        i = int(crossings[-1])
        t = float(outboard[i] / (outboard[i] - outboard[i + 1]))
        return i, t, world_xy[i] + t * (world_xy[i + 1] - world_xy[i])

    def _offset_m(self, i: int, t: float) -> float:
        body_x = self._centreline_xy[i, 0] + t * (self._centreline_xy[i + 1, 0] - self._centreline_xy[i, 0])
        return float(body_x - self._hock_x_m)

    def update(self, model: mujoco.MjModel, data: mujoco.MjData) -> CutResult | None:
        """Advance one step: spin the blade, start, push through, or finish a cut.

        Returns:
            The result on the step the pass is decided, otherwise None.
        """
        angle = 2.0 * math.pi * self.config.blade_speed_rpm / 60.0 * float(data.time)
        data.mocap_quat[self._mocap] = [math.cos(angle / 2), 0.0, math.sin(angle / 2), 0.0]
        if self.result is not None:
            return None
        if self._cut is not None:
            return self._continue_cut(model, data)

        rotation = data.xmat[self._leg_body].reshape(3, 3)
        world_x = data.xpos[self._leg_body][0] + self._centreline_xy @ rotation[0, :2]
        leading_edge_x = self.config.x_m - self._radius_m
        if float(world_x.max()) < leading_edge_x - NEAR_BLADE_M:
            return None
        if self.blade_gap_m(model, data) > 0.0:
            if float(world_x.min()) > self.config.x_m + self._radius_m + NEAR_BLADE_M:
                self.result = CutResult(CutOutcome.TROTTER_NOT_OVER_BLADE, float(data.time))
                logger.info("leg cleared the saw at %.2f s without touching the blade", data.time)
            return self.result

        crossing = self._crossing(data)
        if crossing is None:
            self.result = CutResult(CutOutcome.GRAZED, float(data.time))
            logger.info("blade grazed the leg at %.2f s without crossing it", data.time)
            return self.result
        i, t, _ = crossing
        axis = rotation[:2, 0]
        self._cut = _CutInProgress(
            started_s=float(data.time),
            offset_m=self._offset_m(i, t),
            angle_rad=math.atan2(float(axis[0]), float(-axis[1])),
            yaw_rad=_yaw_rad(rotation),
            slip_xy_m=np.zeros(2),
        )
        logger.info(
            "blade entered the leg at %.2f s: %+.1f mm from the hock, %+.1f deg off square",
            data.time,
            1000 * self._cut.offset_m,
            math.degrees(self._cut.angle_rad),
        )
        return self._continue_cut(model, data)

    def _continue_cut(self, model: mujoco.MjModel, data: mujoco.MjData) -> CutResult | None:
        cut = self._cut
        assert cut is not None
        leg_velocity = data.qvel[self._leg_dof : self._leg_dof + 2]
        belt_velocity = np.array([data.qvel[self._belt_dof], 0.0])
        cut.slip_xy_m += (leg_velocity - belt_velocity) * self._timestep_s
        rotation = data.xmat[self._leg_body].reshape(3, 3)
        crossing = self._crossing(data)

        through = crossing is None
        if crossing is not None:
            i, _, point_xy = crossing
            cos_square = max(abs(math.cos(_yaw_rad(rotation) + math.pi / 2)), 0.3)
            width_m = float(self._half_width_m[i]) / cos_square
            through = float(point_xy[0]) >= self.config.x_m - self._radius_m + width_m

        if not through and float(data.time) - cut.started_s < self.config.cut_timeout_s:
            assert crossing is not None
            i, _, point_xy = crossing
            point = np.array([point_xy[0], point_xy[1], BELT_TOP_Z_M + self._centreline_z[i]])
            force = np.array([-self.config.feed_resistance_n, 0.0, self.config.vertical_force_n])
            data.xfrc_applied[self._leg_body, :3] = force
            data.xfrc_applied[self._leg_body, 3:] = np.cross(point - data.xipos[self._leg_body], force)
            return None

        data.xfrc_applied[self._leg_body] = 0.0
        yaw_drift = math.remainder(_yaw_rad(rotation) - cut.yaw_rad, 2.0 * math.pi)
        slip = float(np.linalg.norm(cut.slip_xy_m))
        self._cut = None
        if not through:
            self.result = CutResult(
                CutOutcome.STALLED,
                cut.started_s,
                offset_from_hock_m=cut.offset_m,
                angle_rad=cut.angle_rad,
                yaw_drift_rad=yaw_drift,
                slip_m=slip,
            )
            logger.info("cut stalled: blade still in the leg %.1f s after entering", self.config.cut_timeout_s)
            return self.result

        data.eq_active[self._weld] = 0
        self._show_whole(model, whole=False)
        self.result = CutResult(
            outcome=CutOutcome.CUT,
            time_s=cut.started_s,
            through_s=float(data.time),
            offset_from_hock_m=cut.offset_m,
            offset_at_exit_m=self._offset_m(*crossing[:2]) if crossing is not None else math.nan,
            angle_rad=cut.angle_rad,
            yaw_drift_rad=yaw_drift,
            slip_m=slip,
        )
        logger.info(
            "cut through at %.2f s: exit %+.1f mm from the hock, leg turned %+.2f deg and slid %.1f mm",
            data.time,
            1000 * self.result.offset_at_exit_m,
            math.degrees(yaw_drift),
            1000 * slip,
        )
        return self.result
