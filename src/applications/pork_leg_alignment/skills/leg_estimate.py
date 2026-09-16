"""Where the leg is, as the skills see it: one description, two sources.

The grasp and alignment skills plan on a `LegEstimate`: the leg's centreline
and width profile from ham end to trotter tip, its heading, and its centre of
gravity, all in the world frame at a known encoder reading. Nothing in the
estimate says where it came from except its `source` string, so the same
skills run from the simulator's ground truth (to isolate the manipulation) or
from the camera pipeline (to test the whole system), and the runner records
which. Scoring against the saw always uses ground truth; planning never does
unless the task graph wires the ground-truth estimator in.

`EstimateLegFromGroundTruth` reads the simulator. `EstimateLegFromCamera`
takes a `LegPerception` from `perception/perceive_leg.py`, which is what the
ROS 2 perception node publishes, plus an optional centre-of-gravity estimate
from the learned corrector. The camera's centreline is the middle of each
cross section on the belt; its height is taken as half the seen top, which is
where the tool point wants to be for a jaw closing across the leg.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from applications.pork_leg_alignment.grasping.leg_perception import LegPerception
from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import leg_centreline, leg_half_width_m
from robotics.core.skill_library import SUCCESS, Check, CheckResult, Contract, Port

logger = logging.getLogger(__name__)

BELT_TOP_Z_M = 0.90
GROUND_TRUTH_STATIONS = 41
# Neighbouring stations either side used for the local direction of the centreline.
DIRECTION_HALF_SPAN = 2


@dataclass(frozen=True)
class LegEstimate:
    """The leg's shape and pose, world frame, at one encoder reading.

    Attributes:
        centreline_m: (K, 3) points from the ham end (row 0) to the trotter
            tip (row K-1), where the leg was when the encoder read `belt_travel_m`.
        widths_m: (K,) width across the leg at each point.
        heading_rad: Yaw of the long axis, ham toward trotter, about world z.
        centre_of_gravity_m: (3,) at `belt_travel_m`.
        belt_travel_m: Encoder reading the positions are valid at; the leg has
            moved along the belt by the travel since.
        source: Where it came from, for the record.
    """

    centreline_m: np.ndarray
    widths_m: np.ndarray
    heading_rad: float
    centre_of_gravity_m: np.ndarray
    belt_travel_m: float
    source: str

    def __post_init__(self) -> None:
        if self.centreline_m.ndim != 2 or self.centreline_m.shape[1] != 3 or self.centreline_m.shape[0] < 3:
            raise ValueError(f"centreline must be (K >= 3, 3), got {self.centreline_m.shape}")
        if self.widths_m.shape != (self.centreline_m.shape[0],):
            raise ValueError("one width per centreline point")

    @property
    def arc_m(self) -> np.ndarray:
        """Distance along the centreline to each point, (K,), from the ham end, measured on the belt plane.

        Measured in the plane so a fraction of the length means the same as it
        does for the leg model, whose profile is a function of distance along
        the leg, not along its rising and falling centreline: with the height
        included the hock landed 3 mm short (2026-09-15).
        """
        steps = np.linalg.norm(np.diff(self.centreline_m[:, :2], axis=0), axis=1)
        return np.concatenate([[0.0], np.cumsum(steps)])

    @property
    def length_m(self) -> float:
        """Centreline length, ham end to trotter tip."""
        return float(self.arc_m[-1])

    def point_at(self, fraction: float) -> np.ndarray:
        """Centreline point `fraction` of the way from the ham end, (3,), interpolated."""
        arc = self.arc_m
        target = fraction * arc[-1]
        return np.array([np.interp(target, arc, self.centreline_m[:, i]) for i in range(3)])

    def width_at(self, fraction: float) -> float:
        """Width across the leg at `fraction`, interpolated."""
        arc = self.arc_m
        return float(np.interp(fraction * arc[-1], arc, self.widths_m))

    def widest_between(self, start_fraction: float, end_fraction: float) -> float:
        """Widest the leg gets between two fractions of its length."""
        arc = self.arc_m
        low, high = sorted((start_fraction, end_fraction))
        samples = np.linspace(low * arc[-1], high * arc[-1], 41)
        return float(np.interp(samples, arc, self.widths_m).max())

    def direction_at(self, fraction: float) -> float:
        """Yaw of the centreline around `fraction`, ham toward trotter, fitted over neighbouring points."""
        arc = self.arc_m
        k = int(np.argmin(np.abs(arc - fraction * arc[-1])))
        lo, hi = max(k - DIRECTION_HALF_SPAN, 0), min(k + DIRECTION_HALF_SPAN, arc.size - 1)
        delta = self.centreline_m[hi, :2] - self.centreline_m[lo, :2]
        if float(np.linalg.norm(delta)) < 1e-9:
            return self.heading_rad
        return math.atan2(float(delta[1]), float(delta[0]))


def estimate_from_ground_truth(cell: Cell) -> LegEstimate:
    """The simulator's own leg: true centreline, widths, heading and centre of mass, now."""
    leg = cell.config.leg
    if leg is None:
        raise ValueError("the cell has no leg")
    truth = cell.ground_truth()
    if truth.centre_of_mass_m is None:
        raise ValueError("ground truth carries no centre of mass")
    body = cell.model.body("slab").id
    position = np.asarray(cell.data.xpos[body], dtype=float)
    rotation = cell.data.xmat[body].reshape(3, 3)
    fractions = np.linspace(0.0, 1.0, GROUND_TRUTH_STATIONS)
    centreline = position + leg_centreline(leg, fractions) @ rotation.T
    return LegEstimate(
        centreline_m=np.asarray(centreline, dtype=float),
        widths_m=2.0 * np.asarray(leg_half_width_m(leg, fractions), dtype=float),
        heading_rad=math.atan2(float(rotation[1, 0]), float(rotation[0, 0])),
        centre_of_gravity_m=np.asarray(truth.centre_of_mass_m, dtype=float),
        belt_travel_m=cell.belt_travel_m,
        source="ground_truth",
    )


def estimate_from_perception(leg: LegPerception, centre_of_gravity_m: np.ndarray | None = None) -> LegEstimate:
    """The camera's leg, in world coordinates at the perception's encoder reading.

    Args:
        leg: What the perception pipeline saw.
        centre_of_gravity_m: (3,) world at `leg.belt_travel_m`, from a better
            estimator than the perception's own; the perception's column
            centroid is used when None.
    """
    shift = np.array([leg.belt_travel_m, 0.0])
    xy = leg.centreline_belt_m + shift
    z = leg.belt_surface_z_m + 0.5 * leg.top_heights_m
    centreline = np.column_stack([xy, z])
    centre = (
        np.asarray(centre_of_gravity_m, dtype=float)
        if centre_of_gravity_m is not None
        else leg.centre_of_gravity_belt_m + np.array([leg.belt_travel_m, 0.0, 0.0])
    )
    return LegEstimate(
        centreline_m=np.asarray(centreline, dtype=float),
        widths_m=np.asarray(leg.widths_m, dtype=float),
        heading_rad=leg.axis_rad,
        centre_of_gravity_m=centre,
        belt_travel_m=leg.belt_travel_m,
        source=f"camera ({leg.method})",
    )


def product_on_belt(cell: Any, _args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    """The product body's origin rests within 20 mm of the belt surface. Shared by every ground-truth estimator."""
    body = cell.model.body("slab").id
    height = float(cell.data.xpos[body][2]) - BELT_TOP_Z_M
    return CheckResult(abs(height) < 0.02, height, "product origin within 20 mm of the belt surface")


class EstimateLegFromGroundTruth:
    """Read the leg from the simulator. For isolating manipulation; never for a real cell."""

    name = "estimate_leg_from_ground_truth"
    contract = Contract(
        inputs=(),
        preconditions=(
            Check("leg_on_belt_m", "the leg rests on the belt, origin within 20 mm of its surface", product_on_belt),
        ),
        outputs=(Port("leg_estimate", LegEstimate, "true centreline, widths, heading and centre of mass"),),
        success=(),
        failures=(),
    )

    def execute(self, world: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:  # noqa: ANN401
        """Sample the true leg."""
        estimate = estimate_from_ground_truth(world)
        return SUCCESS, {"leg_estimate": estimate}, {"length_m": estimate.length_m}


class EstimateLegFromCamera:
    """Turn the perception node's leg into the estimate the skills plan on."""

    name = "estimate_leg_from_camera"
    contract = Contract(
        inputs=(Port("leg_perception", LegPerception, "the perceived leg, belt coordinates"),),
        preconditions=(),
        outputs=(Port("leg_estimate", LegEstimate, "perceived centreline, widths, heading and centre of gravity"),),
        success=(),
        failures=(),
    )

    def execute(self, world: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:  # noqa: ANN401
        """Convert, using `centre_of_gravity_m` from the arguments when a better estimator supplied one."""
        estimate = estimate_from_perception(args["leg_perception"], args.get("centre_of_gravity_m"))
        return SUCCESS, {"leg_estimate": estimate}, {"length_m": estimate.length_m}
