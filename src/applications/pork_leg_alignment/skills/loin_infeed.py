"""The loin puller infeed: where the jaws close on a loin, and what "aligned" means at the fixture.

Two things change between the leg cell and this one, and both are here so
the grasp and turn skills stay as they are (Section 14.2 and 14.3 of the
plan).

The grasp station. The shank rule grips a leg at 0.70 of its length because
the shank is a rigid handle whose width the jaw clears. The library can
source no such handle on a loin, so the starting rule is the section nearest
the centre of gravity, jaws across the piece: it puts the pivot of the turn
under the jaws, so the turn moves no mass sideways. Whether the jaw holds a
loin there is what the runs measure, and the fit check in `AcquireShank`
refuses the grasp before any motion when the piece is wider than the jaw
leaves room for.

The alignment target. The piece must lie along belt travel with its bone
edge on the fixture's datum line (`sim/infeed_fixture.py`, whose
`target_heading_rad` states the assumption). The datum point is the bone
edge at the grasp station, so the point the skill puts on the datum is the
point the fixture scores.
"""

from __future__ import annotations

import numpy as np

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.infeed_fixture import target_heading_rad
from applications.pork_leg_alignment.skills.leg_estimate import LegEstimate
from applications.pork_leg_alignment.skills.loin_estimate import LoinEstimate, estimate_loin_from_ground_truth


def centre_of_gravity_station(estimate: LegEstimate) -> float:
    """The fraction of the length at which the centreline passes nearest the centre of gravity, in the belt plane.

    The centre of gravity is projected onto each centreline segment and the
    nearest projection taken, so the station is not limited to the estimate's
    sample points.
    """
    line = estimate.centreline_m[:, :2]
    target = estimate.centre_of_gravity_m[:2]
    starts, ends = line[:-1], line[1:]
    along = ends - starts
    lengths_sq = np.maximum(np.einsum("ij,ij->i", along, along), 1e-12)
    t = np.clip(np.einsum("ij,ij->i", target - starts, along) / lengths_sq, 0.0, 1.0)
    nearest = starts + t[:, None] * along
    segment = int(np.argmin(np.linalg.norm(nearest - target, axis=1)))
    arc = estimate.arc_m
    return float((arc[segment] + t[segment] * (arc[segment + 1] - arc[segment])) / arc[-1])


def _loin(estimate: LegEstimate) -> LoinEstimate:
    if not isinstance(estimate, LoinEstimate):
        raise TypeError(f"the infeed target needs the bone side, which a {type(estimate).__name__} does not carry")
    return estimate


class InfeedTarget:
    """The loin's alignment: the bone edge at the centre of gravity on the datum line, piece along the belt."""

    name = "infeed_fixture"

    def datum_point(self, estimate: LegEstimate) -> np.ndarray:
        """The bone-side edge of the piece at the grasp station, (3,)."""
        loin = _loin(estimate)
        station = centre_of_gravity_station(loin)
        return loin.point_at(station) + loin.bone_side * 0.5 * loin.width_at(station) * loin.left_normal()

    def heading_rad(self, cell: Cell, estimate: LegEstimate) -> float:
        """Along the belt, bone edge toward the fixture's datum: 0 or pi by the piece's bone side."""
        if cell.infeed_fixture is None:
            raise ValueError("the cell has no infeed fixture; there is no datum to face")
        return target_heading_rad(_loin(estimate).bone_side, cell.infeed_fixture.datum_side)

    def datum_y_m(self, cell: Cell) -> float | None:
        """The fixture's datum line, when the cell has one."""
        return cell.infeed_fixture.config.datum_y_m if cell.infeed_fixture is not None else None

    def datum_offset_m(self, cell: Cell, point_y_m: float) -> float:
        """The fixture's own signing: positive inboard, on the belt; negative past the datum."""
        if cell.infeed_fixture is None:
            raise ValueError("the cell has no infeed fixture; there is no datum to measure from")
        return cell.infeed_fixture.offset_m(point_y_m)

    def ground_truth(self, cell: Cell) -> LegEstimate:
        """The simulator's own loin."""
        return estimate_loin_from_ground_truth(cell)


INFEED_TARGET = InfeedTarget()
