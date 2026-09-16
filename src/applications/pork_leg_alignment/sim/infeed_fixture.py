"""The loin puller's infeed fixture, and where a piece's pose stands when it reaches it.

The loin cell has no blade. The station exists to set each loin down so the
puller takes it in square, with its bone edge against the machine's guide, and
the fixture here is what scores that: a plane across the belt at the fixture's
x, where the piece's pose is read as its leading end crosses and again as its
trailing end leaves, plus a drawn guide along the datum line so the target is
visible on video. Nothing pushes back on the piece; there is no cut process
and no hold-down (Section 14.4 of the plan). The result has the shape of the
saw's `CutResult` so the runner's judge reads either.

What "aligned" means is a working assumption until the vendor or the plant
gives the numbers, and every part of it is named here. The piece lies along
belt travel, so the same guide the machine feeds along is the datum: a line
at `InfeedFixtureConfig.datum_y_m`, parallel to travel, on the far-rail side
of the belt (which side the real datum is on is unverified, Section 14.2).
The bone edge at the piece's centre of gravity must lie on that line, and the
piece's heading must point along the belt with the bone toward the datum:
heading 0 when the bone lies on the piece's left, pi when on its right
(`target_heading_rad`). The tolerance is the leg's assumed 10 mm and 5 degrees
and lives with the runner's judge, as the saw's does.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum

import mujoco
import numpy as np

from applications.pork_leg_alignment.sim.loin import LoinConfig
from applications.pork_leg_alignment.sim.product import PRODUCT_BODY

logger = logging.getLogger(__name__)

INFEED_GUIDE_GEOM = "infeed_guide"
INFEED_PLANE_GEOM = "infeed_plane"
BELT_BODY = "belt"
BELT_JOINT = "belt_x"
PRODUCT_JOINT = "slab_free"
BELT_TOP_Z_M = 0.90
CENTRELINE_SAMPLES = 721
# A piece whose origin has dropped this far below the belt surface has left it.
OFF_BELT_DROP_M = 0.10


@dataclass(frozen=True)
class InfeedFixtureConfig:
    """Where the fixture's reading plane and datum line stand. All assumed.

    Attributes:
        x_m: The reading plane across the belt, world x. The piece's pose is
            read as it crosses here.
        datum_y_m: The datum line the bone edge must lie on, world y, parallel
            to belt travel. The default stands 57 mm inside the far rail's
            inner face (0.857 m), on the arms' side of the belt; which side the
            loin puller's own guide is on is unverified.
        guide_length_m: How far the drawn guide runs downstream from the plane.
        guide_height_m: Height of the drawn guide above the belt.
    """

    x_m: float = 1.10
    datum_y_m: float = 0.80
    guide_length_m: float = 0.60
    guide_height_m: float = 0.12

    def __post_init__(self) -> None:
        if self.guide_length_m <= 0 or self.guide_height_m <= 0:
            raise ValueError(
                f"the guide needs a positive length and height, got {self.guide_length_m}, {self.guide_height_m}"
            )


def target_heading_rad(bone_side: float, datum_side: float) -> float:
    """The heading that lays the piece along the belt with its bone edge toward the datum.

    The working assumption for the infeed pose (module docstring). A heading
    is the yaw of the piece's long axis; the bone edge lies `bone_side` of it
    (+1 on the left, -1 on the right), so it faces +y at heading 0 when
    `bone_side` is +1, and faces +y at heading pi when `bone_side` is -1.

    Args:
        bone_side: +1 when the bone edge lies on the piece's left, -1 on its right.
        datum_side: +1 when the datum line lies on the +y side of the belt, -1 on the -y side.
    """
    return 0.0 if bone_side * datum_side > 0 else math.pi


class InfeedOutcome(str, Enum):
    """What happened when a piece rode to the fixture."""

    CROSSED = "crossed"
    OFF_BELT = "off_belt"  # the piece left the belt before reaching the plane


@dataclass(frozen=True)
class InfeedResult:
    """One piece's pass through the fixture's plane, in the shape of the saw's `CutResult`.

    Attributes:
        outcome: How the pass ended.
        time_s: When the leading end crossed the plane, or when the piece left the belt.
        through_s: When the trailing end left the plane. NaN unless crossed.
        offset_m: The bone edge's offset from the datum line at the centre of
            gravity, at entry: positive inboard, on the belt, short of the
            datum; negative past it. NaN unless crossed.
        offset_at_exit_m: The same at exit. Differs from entry only if the
            piece moved while crossing.
        angle_rad: Heading error at entry, the piece's heading minus the
            target heading for its bone side, wrapped. Zero is square to belt
            travel with the bone toward the datum. NaN unless crossed.
        yaw_drift_rad: How far the piece turned between entry and exit.
        slip_m: How far the piece slid relative to the belt surface between
            entry and exit, in the belt plane.
    """

    outcome: InfeedOutcome
    time_s: float
    through_s: float = math.nan
    offset_m: float = math.nan
    offset_at_exit_m: float = math.nan
    angle_rad: float = math.nan
    yaw_drift_rad: float = math.nan
    slip_m: float = math.nan


def add_infeed_fixture(spec: mujoco.MjSpec, config: InfeedFixtureConfig) -> None:
    """Draw the fixture: a guide plate along the datum and a translucent reading plane across the belt.

    Neither collides. The fixture scores the piece's pose; a guide that
    corrected it by contact would hide the very error the station exists to
    remove.
    """
    belt_y = float(spec.body(BELT_BODY).pos[1])
    belt_half_width = float(spec.geom("belt_surface").size[1])
    datum_side = 1.0 if config.datum_y_m > belt_y else -1.0
    visual = {"contype": 0, "conaffinity": 0, "group": 2, "density": 0.0}
    plate_half_thickness = 0.004
    spec.worldbody.add_geom(
        name=INFEED_GUIDE_GEOM,
        type=mujoco.mjtGeom.mjGEOM_BOX,
        size=[config.guide_length_m / 2, plate_half_thickness, config.guide_height_m / 2],
        # The plate's inner face is the datum: it stands just beyond the line, on the datum's side.
        pos=[
            config.x_m + config.guide_length_m / 2,
            config.datum_y_m + datum_side * plate_half_thickness,
            BELT_TOP_Z_M + config.guide_height_m / 2,
        ],
        rgba=[0.72, 0.74, 0.76, 1.0],
        **visual,
    )
    spec.worldbody.add_geom(
        name=INFEED_PLANE_GEOM,
        type=mujoco.mjtGeom.mjGEOM_BOX,
        size=[0.001, belt_half_width, config.guide_height_m / 2],
        pos=[config.x_m, belt_y, BELT_TOP_Z_M + config.guide_height_m / 2],
        rgba=[0.20, 0.45, 0.62, 0.25],
        **visual,
    )


def _name_id(model: mujoco.MjModel, kind: mujoco.mjtObj, name: str) -> int:
    index = mujoco.mj_name2id(model, kind, name)
    if index < 0:
        raise ValueError(f"the model has no {name!r}; build the cell with a loin and an infeed fixture")
    return int(index)


def _yaw_rad(rotation: np.ndarray) -> float:
    return math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))


@dataclass
class _Crossing:
    entered_s: float
    offset_m: float
    angle_rad: float
    yaw_rad: float
    slip_xy_m: np.ndarray


class InfeedFixture:
    """Reads the piece's pose as it crosses the fixture's plane and scores it against the datum.

    Holds one result per pass; `rearm` clears it when a new piece is placed.
    """

    def __init__(self, model: mujoco.MjModel, config: InfeedFixtureConfig, loin: LoinConfig) -> None:
        """Bind to a compiled cell that has a loin and the fixture's geoms.

        Raises:
            ValueError: If the model lacks the fixture or the product body.
        """
        self.config = config
        self.loin = loin
        _name_id(model, mujoco.mjtObj.mjOBJ_GEOM, INFEED_PLANE_GEOM)
        self._body = _name_id(model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
        self._belt_dof = int(model.jnt_dofadr[_name_id(model, mujoco.mjtObj.mjOBJ_JOINT, BELT_JOINT)])
        self._product_dof = int(model.jnt_dofadr[_name_id(model, mujoco.mjtObj.mjOBJ_JOINT, PRODUCT_JOINT)])
        self._timestep_s = float(model.opt.timestep)
        belt_y = float(model.body_pos[_name_id(model, mujoco.mjtObj.mjOBJ_BODY, BELT_BODY)][1])
        # +1 when the datum lies on the +y side of the belt. Inboard, toward the belt, is the other way.
        self.datum_side = 1.0 if config.datum_y_m > belt_y else -1.0
        self.target_heading_rad = target_heading_rad(loin.bone_side, self.datum_side)
        self._centreline_xy = loin.centreline_m(np.linspace(0.0, 1.0, CENTRELINE_SAMPLES))[:, :2]
        # The bone edge at the centre of gravity's section, body frame: the
        # point the skills put on the datum and the point scored here.
        cog_fraction = float(model.body_ipos[self._body][0]) / loin.length_m + 0.5
        self._bone_edge = loin.bone_edge_m(np.array([cog_fraction]))[0]
        self._crossing: _Crossing | None = None
        self.result: InfeedResult | None = None

    @property
    def crossing(self) -> bool:
        """The piece is on the plane right now."""
        return self._crossing is not None

    def rearm(self) -> None:
        """Forget the last pass."""
        self._crossing = None
        self.result = None

    def offset_m(self, bone_edge_y_m: float) -> float:
        """The bone edge's offset from the datum: positive inboard, on the belt; negative past the datum."""
        return -self.datum_side * (bone_edge_y_m - self.config.datum_y_m)

    def _pose(self, data: mujoco.MjData) -> tuple[np.ndarray, float, float]:
        """World x of every centreline sample, the heading, and the bone edge's offset now."""
        rotation = data.xmat[self._body].reshape(3, 3)
        position = data.xpos[self._body]
        world_x = position[0] + self._centreline_xy @ rotation[0, :2]
        edge = position + rotation @ self._bone_edge
        return world_x, _yaw_rad(rotation), self.offset_m(float(edge[1]))

    def update(self, model: mujoco.MjModel, data: mujoco.MjData) -> InfeedResult | None:
        """Advance one step: watch for the piece to reach the plane, then to leave it.

        Returns:
            The result on the step the pass is decided, otherwise None.
        """
        del model
        if self.result is not None:
            return None
        world_x, yaw, offset = self._pose(data)
        if self._crossing is None:
            if float(data.xpos[self._body][2]) < BELT_TOP_Z_M - OFF_BELT_DROP_M:
                self.result = InfeedResult(InfeedOutcome.OFF_BELT, float(data.time))
                logger.info("the piece left the belt at %.2f s before reaching the fixture", data.time)
                return self.result
            if float(world_x.max()) < self.config.x_m:
                return None
            self._crossing = _Crossing(
                entered_s=float(data.time),
                offset_m=offset,
                angle_rad=math.remainder(yaw - self.target_heading_rad, 2.0 * math.pi),
                yaw_rad=yaw,
                slip_xy_m=np.zeros(2),
            )
            logger.info(
                "piece reached the fixture at %.2f s: bone edge %+.1f mm from the datum, %+.1f deg off",
                data.time,
                1000 * offset,
                math.degrees(self._crossing.angle_rad),
            )
            return None

        crossing = self._crossing
        product_velocity = data.qvel[self._product_dof : self._product_dof + 2]
        belt_velocity = np.array([data.qvel[self._belt_dof], 0.0])
        crossing.slip_xy_m += (product_velocity - belt_velocity) * self._timestep_s
        if float(world_x.min()) < self.config.x_m:
            return None
        self._crossing = None
        self.result = InfeedResult(
            outcome=InfeedOutcome.CROSSED,
            time_s=crossing.entered_s,
            through_s=float(data.time),
            offset_m=crossing.offset_m,
            offset_at_exit_m=offset,
            angle_rad=crossing.angle_rad,
            yaw_drift_rad=math.remainder(yaw - crossing.yaw_rad, 2.0 * math.pi),
            slip_m=float(np.linalg.norm(crossing.slip_xy_m)),
        )
        logger.info(
            "piece cleared the fixture at %.2f s: exit %+.1f mm from the datum, turned %+.2f deg, slid %.1f mm",
            data.time,
            1000 * offset,
            math.degrees(self.result.yaw_drift_rad),
            1000 * self.result.slip_m,
        )
        return self.result
