"""What a grasp policy hands on, the same for every arm and every product.

A policy, deterministic or learned, reads what its application perceives about one product and
returns a `GraspAction` (the interface is `grasp_policy.py`). The action does not mention a robot: it
is a point on the product in belt coordinates, the direction the jaws close along, how far the tool
leans, how wide to open and how long to close. The intercept planner turns it into a time and a
place, and each arm's executor (MoveIt through ROS 2, or the simulator's own IK) turns that into
motion, or refuses when the arm cannot do it, such as a SCARA asked to lean its tool. That split is
what lets one policy run on the UR20, the SR-20iA and whatever arm comes next.

Belt coordinates: x along the belt minus the belt's travel at the time of the reading, so a point
on a product that does not slip keeps its belt x; y and z are world y and z.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


def tool_rotation(finger_axis_rad: float, tool_tilt_rad: float) -> np.ndarray:
    """World-from-tool rotation (3, 3) for a grasp: tool z toward the grasp, jaws along tool y.

    The cell's grippers close along the tool's y axis (`robotics/hardware/grippers.py`), so tool y lies
    along the finger axis and tool x along the product. A tilt turns the tool about its y axis, leaning
    it along the product; with no tilt tool z points straight down, as `ik.tool_down_rotation` does.
    """
    finger = np.array([math.cos(finger_axis_rad), math.sin(finger_axis_rad), 0.0])
    down = np.array([0.0, 0.0, -1.0])
    along = np.cross(finger, down)
    vertical = np.column_stack([along, finger, down])
    cos_tilt, sin_tilt = math.cos(tool_tilt_rad), math.sin(tool_tilt_rad)
    about_y = np.array([[cos_tilt, 0.0, sin_tilt], [0.0, 1.0, 0.0], [-sin_tilt, 0.0, cos_tilt]])
    return np.asarray(vertical @ about_y)


@dataclass(frozen=True)
class GraspAction:
    """Where and how to take hold of the product, independent of the arm.

    Attributes:
        stamp_s: Exposure time of the perception it was decided from.
        policy: Which policy decided it, for the A/B record.
        grasp_point_belt_m: (3,) point midway between the jaws when closed, belt coordinates.
        finger_axis_rad: World yaw of the line the jaws close along.
        tool_tilt_rad: Lean of the tool from pointing straight down, about the finger axis.
            0 for a vertical tool; an arm whose tool cannot lean refuses anything else.
        opening_m: How wide to open before closing.
        approach_height_m: How far above the grasp point to come in from.
        close_s: How long the jaws take to close while the tool follows the belt.
    """

    stamp_s: float
    policy: str
    grasp_point_belt_m: np.ndarray
    finger_axis_rad: float
    tool_tilt_rad: float
    opening_m: float
    approach_height_m: float
    close_s: float

    def __post_init__(self) -> None:
        if self.grasp_point_belt_m.shape != (3,) or not np.all(np.isfinite(self.grasp_point_belt_m)):
            raise ValueError(f"grasp point must be a finite (3,) array, got {self.grasp_point_belt_m}")
        if not math.isfinite(self.finger_axis_rad) or not -math.pi / 2 <= self.tool_tilt_rad <= math.pi / 2:
            raise ValueError("finger axis must be finite and tool tilt within 90 degrees of vertical")
        if self.opening_m <= 0.0 or self.approach_height_m <= 0.0 or self.close_s <= 0.0:
            raise ValueError("opening, approach height and closing time must be positive")

    def world_point_m(self, belt_travel_m: float) -> np.ndarray:
        """The grasp point in the world once the belt has travelled `belt_travel_m`."""
        return np.array(
            [self.grasp_point_belt_m[0] + belt_travel_m, self.grasp_point_belt_m[1], self.grasp_point_belt_m[2]]
        )
