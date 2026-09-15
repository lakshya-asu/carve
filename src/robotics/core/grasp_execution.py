"""The timed tool poses one arm has to hit to carry out a grasp action, before any IK.

Given a `GraspAction` and an `InterceptPlan`, the tool comes down onto the grasp point along its own
axis, meets it at the planned time matched to the belt, and follows it while the jaws close. These
waypoints are the same for every arm; each executor solves IK for them (MoveIt's `/compute_ik` in
ROS 2, or `robotics.hardware.ik.solve_ik_rotation` in the simulator) and sends the joint trajectory, so this is the
last robot-agnostic step. Numpy only, so it runs inside a ROS 2 node.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from robotics.core.grasp_action import GraspAction, tool_rotation
from robotics.core.intercept import InterceptPlan


@dataclass(frozen=True)
class ToolWaypoint:
    """One tool pose at one time.

    Attributes:
        time_s: When the tool must be here, same clock as the plan.
        position_m: (3,) tool centre point, world frame.
        rotation: (3, 3) world-from-tool rotation.
        phase: "above", "meet" or "closed", for logs and feedback.
        close_jaws: Whether the jaws are commanded closed from this waypoint on.
    """

    time_s: float
    position_m: np.ndarray
    rotation: np.ndarray
    phase: str
    close_jaws: bool


def grasp_waypoints(action: GraspAction, plan: InterceptPlan, descend_s: float = 0.4) -> list[ToolWaypoint]:
    """Above the grasp point, at it, and following it until the jaws have closed.

    The "above" waypoint is where the grasp point will be `descend_s` before the meeting, raised by
    the approach height along the tool axis, so the tool descends onto a point that is moving with
    the belt rather than onto where it was.

    Raises:
        ValueError: If `descend_s` is not positive.
    """
    if descend_s <= 0.0:
        raise ValueError(f"descent time must be positive, got {descend_s}")
    rotation = tool_rotation(action.finger_axis_rad, action.tool_tilt_rad)
    up_the_tool = -rotation[:, 2]
    belt_step = np.array([plan.belt_speed_at_meet_mps * descend_s, 0.0, 0.0])
    above = plan.meet_world_m - belt_step + action.approach_height_m * up_the_tool
    return [
        ToolWaypoint(plan.meet_time_s - descend_s, above, rotation, "above", close_jaws=False),
        ToolWaypoint(plan.meet_time_s, plan.meet_world_m, rotation, "meet", close_jaws=True),
        ToolWaypoint(plan.closed_time_s, plan.closed_world_m, rotation, "closed", close_jaws=True),
    ]
