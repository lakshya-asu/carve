"""Grasp policies: anything that turns a perceived leg into a grasp action, and the deterministic rule.

A policy reads a `LegPerception` and returns a `GraspAction` (`grasp_action.py`), and imports
nothing but numpy, so the same policy runs in the simulator and inside a ROS 2 node.
`ShankGraspRule` is the deterministic policy the learned one is A/B tested against: the shank at a
fixed fraction of the leg's length from the ham end, the jaws closing across the local centreline.
"""

from __future__ import annotations

import math
from typing import Protocol

import numpy as np

from meat_cell_sim.grasp_action import GraspAction, LegPerception

# Where the existing shank skill grips, as a fraction of the length from the ham butt
# (`skill_library/skills/grasp.py`, SHANK_GRASP_FRACTION).
SHANK_FRACTION = 0.66
# Each jaw opens at least 20 mm clear of the shank, as the skills' spare-opening precondition requires.
SPARE_OPENING_M = 0.040
# Cross sections either side of the grasp station used to fit the local centreline direction.
DIRECTION_HALF_SPAN = 3


class GraspRefusedError(ValueError):
    """The policy will not grasp this leg; the message says why."""


class GraspPolicy(Protocol):
    """Anything that decides a grasp from a perceived leg: the rule below, or a learned model."""

    name: str

    def decide(self, leg: LegPerception) -> GraspAction:
        """Return the grasp, or raise `GraspRefusedError`."""
        ...


class ShankGraspRule:
    """Grip the shank a fixed fraction of the way from the ham, jaws across the local centreline."""

    name = "shank-at-fraction"

    def __init__(
        self,
        fraction: float = SHANK_FRACTION,
        spare_opening_m: float = SPARE_OPENING_M,
        max_opening_m: float | None = None,
        tool_tilt_rad: float = 0.0,
        approach_height_m: float = 0.15,
        close_s: float = 0.6,
    ) -> None:
        """Configure the rule; `max_opening_m` is the gripper's widest opening, or None not to check."""
        if not 0.0 < fraction < 1.0:
            raise ValueError(f"fraction must be inside (0, 1), got {fraction}")
        self.fraction = fraction
        self.spare_opening_m = spare_opening_m
        self.max_opening_m = max_opening_m
        self.tool_tilt_rad = tool_tilt_rad
        self.approach_height_m = approach_height_m
        self.close_s = close_s

    def decide(self, leg: LegPerception) -> GraspAction:
        """The grasp for this leg.

        Raises:
            GraspRefusedError: If the shank at the grasp point is too wide for the gripper.
        """
        k = int(np.argmin(np.abs(leg.stations_m - self.fraction * leg.length_m)))
        span = slice(max(k - DIRECTION_HALF_SPAN, 0), min(k + DIRECTION_HALF_SPAN + 1, leg.stations_m.size))
        nearby = leg.centreline_belt_m[span]
        _, _, right = np.linalg.svd(nearby - nearby.mean(axis=0), full_matrices=False)
        local_axis = right[0]
        opening_m = float(leg.widths_m[k]) + self.spare_opening_m
        if self.max_opening_m is not None and opening_m > self.max_opening_m:
            raise GraspRefusedError(
                f"the shank is {1000 * leg.widths_m[k]:.0f} mm wide at the grasp point; with "
                f"{1000 * self.spare_opening_m:.0f} mm spare that needs {1000 * opening_m:.0f} mm, "
                f"the gripper opens {1000 * self.max_opening_m:.0f} mm"
            )
        # Seen from above, a shank's widest point is about half its width below its top.
        grasp_z_m = leg.belt_surface_z_m + float(leg.top_heights_m[k]) - 0.5 * float(leg.widths_m[k])
        return GraspAction(
            stamp_s=leg.stamp_s,
            policy=self.name,
            grasp_point_belt_m=np.array([*leg.centreline_belt_m[k], grasp_z_m]),
            finger_axis_rad=math.atan2(local_axis[1], local_axis[0]) + math.pi / 2,
            tool_tilt_rad=self.tool_tilt_rad,
            opening_m=opening_m,
            approach_height_m=self.approach_height_m,
            close_s=self.close_s,
        )
