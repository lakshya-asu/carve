"""Where the loin is, as the skills see it: the leg's estimate plus which side the bone lies on.

Three of the four parts of a `LegEstimate` fit a loin as they are: a piece
lying on the belt has a centreline, a width at each point along it and a
centre of gravity (Section 14.2 of the plan). The heading does not carry its
meaning across. On a leg the axis is signed by the centre of gravity sitting
toward the thin end; whether a loin's outline is uneven enough end to end for
that rule is unverified, so no skill may lean on which end of a loin is row 0.

The heading rule for a loin, stated once here: `heading_rad` is the yaw of
the long axis from row 0 to row K-1 of the centreline, and its sign is a
convention of the source, not a fact about the piece. From ground truth it is
the body's +x axis (blade end to sirloin end); a camera would sign it however
its centreline binning happens to run. What carries the pose's meaning is
`bone_side`: which side of that axis the bone edge lies on, an asymmetry
across the piece that a height profile across each section can read (the
bone edge stands higher, `sim/loin.py`). The infeed target is chosen from
`bone_side` (`skills/loin_infeed.py`), so flipping the axis's sign flips
`bone_side` with it and the target the skills plan on is the same either way.

Assumption, named: that the bone edge is the taller edge and that a camera
can read it from the height profile. Neither is measured on a real loin.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.skills.leg_estimate import (
    GROUND_TRUTH_STATIONS,
    LegEstimate,
    product_on_belt,
)
from robotics.core.skill_library import SUCCESS, Check, Contract, Port

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoinEstimate(LegEstimate):
    """A loin's shape and pose, world frame, at one encoder reading: the leg's estimate plus the bone side.

    Attributes:
        bone_side: +1 when the bone edge lies on the left of the heading
            (toward +y in the frame whose x is the heading), -1 on the right.
            See the module docstring for why this, and not the heading's
            sign, is what the pose means.
    """

    bone_side: float

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.bone_side not in (1.0, -1.0):
            raise ValueError(f"bone side is +1 or -1, got {self.bone_side}")

    def left_normal(self) -> np.ndarray:
        """Unit vector to the left of the heading in the belt plane, (3,)."""
        return np.array([-math.sin(self.heading_rad), math.cos(self.heading_rad), 0.0])


def estimate_loin_from_ground_truth(cell: Cell) -> LoinEstimate:
    """The simulator's own loin: true centreline, widths, heading, centre of mass and bone side, now."""
    loin = cell.config.loin
    if loin is None:
        raise ValueError("the cell has no loin")
    truth = cell.ground_truth()
    if truth.centre_of_mass_m is None:
        raise ValueError("ground truth carries no centre of mass")
    body = cell.model.body("slab").id
    rotation = cell.data.xmat[body].reshape(3, 3)
    fractions = np.linspace(0.0, 1.0, GROUND_TRUTH_STATIONS)
    return LoinEstimate(
        centreline_m=cell.product_centreline_world(fractions),
        widths_m=2.0 * np.asarray(loin.half_width_m(fractions), dtype=float),
        heading_rad=math.atan2(float(rotation[1, 0]), float(rotation[0, 0])),
        centre_of_gravity_m=np.asarray(truth.centre_of_mass_m, dtype=float),
        belt_travel_m=cell.belt_travel_m,
        source="ground_truth",
        # The body's +y side is the left of its +x axis, which is the heading here.
        bone_side=loin.bone_side,
    )


class EstimateLoinFromGroundTruth:
    """Read the loin from the simulator. For isolating manipulation; never for a real cell."""

    name = "estimate_loin_from_ground_truth"
    contract = Contract(
        inputs=(),
        preconditions=(
            Check("loin_on_belt_m", "the loin rests on the belt, origin within 20 mm of its surface", product_on_belt),
        ),
        outputs=(Port("leg_estimate", LoinEstimate, "true centreline, widths, heading, centre of mass and bone side"),),
        success=(),
        failures=(),
    )

    def execute(self, world: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:  # noqa: ANN401
        """Sample the true loin. The output keeps the leg's port name so the grasp and turn skills read it unchanged."""
        estimate = estimate_loin_from_ground_truth(world)
        return SUCCESS, {"leg_estimate": estimate}, {"length_m": estimate.length_m, "bone_side": estimate.bone_side}
