"""When and where the arm meets a leg riding the belt.

The library version of `snippets/conveyor_tracking.py`'s planner, extended for this cell: the
target is a point on the leg in the belt frame (it rides with the belt, so its belt coordinates do
not change), the belt's future travel comes from `BeltState` with its acceleration, the arm may meet
the leg anywhere in a rectangle on the belt, and a stopped belt is handled rather than divided by.

The arm's travel time is a rest-to-rest trapezoid over the straight-line distance plus the ramp to
match belt speed, the conservative stand-in the snippet uses. Each robot supplies its own limits;
the plan is the same for every arm, and turning the meeting point into joint motion is the
executor's job (MoveIt or the simulator's IK).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from meat_cell_sim.belt_state import BeltState

# The belt runs along world +x, so a point's world x is its belt x plus the belt's travel.
FIXED_POINT_ITERATIONS = 100
FIXED_POINT_TOLERANCE_S = 1e-6
WAIT_HORIZON_S = 30.0


class NoFeasibleInterceptError(ValueError):
    """The arm cannot meet the leg inside its window; the message says why."""


@dataclass(frozen=True)
class ArmMotion:
    """What the planner assumes about one arm's tool motion.

    Attributes:
        max_speed_mps: Tool speed the arm is allowed to use.
        max_acceleration_mps2: Tool acceleration the arm is allowed to use.
        command_latency_s: From a command being sent to the arm starting to move.
    """

    max_speed_mps: float
    max_acceleration_mps2: float
    command_latency_s: float = 0.0

    def __post_init__(self) -> None:
        if self.max_speed_mps <= 0.0 or self.max_acceleration_mps2 <= 0.0 or self.command_latency_s < 0.0:
            raise ValueError("need positive speed and acceleration limits and a non-negative latency")

    def move_time_s(self, distance_m: float, match_speed_mps: float) -> float:
        """Rest-to-rest trapezoid over `distance_m`, plus the ramp to `match_speed_mps`."""
        d, v, a = abs(distance_m), self.max_speed_mps, self.max_acceleration_mps2
        travel = 2.0 * math.sqrt(d / a) if d <= v**2 / a else d / v + v / a
        return travel + abs(match_speed_mps) / a


@dataclass(frozen=True)
class PickWindow:
    """Where on the belt this arm may meet a leg and close on it, world frame, metres."""

    x_min_m: float
    x_max_m: float
    y_min_m: float
    y_max_m: float


@dataclass(frozen=True)
class InterceptPlan:
    """A meeting the arm can make.

    Attributes:
        meet_time_s: When the tool reaches the grasp point, matched to the belt.
        meet_world_m: (3,) where the grasp point is at `meet_time_s`.
        closed_time_s: When the jaws have finished closing.
        closed_world_m: (3,) where the grasp point is at `closed_time_s`.
        belt_speed_at_meet_mps: The speed the tool has to match.
    """

    meet_time_s: float
    meet_world_m: np.ndarray
    closed_time_s: float
    closed_world_m: np.ndarray
    belt_speed_at_meet_mps: float


def _world_at(target_belt_m: np.ndarray, belt: BeltState, t_s: float) -> np.ndarray:
    return np.array([target_belt_m[0] + belt.travel_at(t_s), target_belt_m[1], target_belt_m[2]])


def _when_travel_reaches(travel_m: float, belt: BeltState, from_s: float) -> float:
    """Earliest time from `from_s` at which the belt has travelled `travel_m`; travel never decreases."""
    if belt.travel_at(from_s) >= travel_m:
        return from_s
    late = from_s + WAIT_HORIZON_S
    if belt.travel_at(late) < travel_m:
        raise NoFeasibleInterceptError("the belt will not carry the leg into the window")
    early = from_s
    for _ in range(60):
        middle = 0.5 * (early + late)
        early, late = (middle, late) if belt.travel_at(middle) < travel_m else (early, middle)
    return late


def plan_intercept(
    target_belt_m: np.ndarray,
    belt: BeltState,
    tool_world_m: np.ndarray,
    now_s: float,
    window: PickWindow,
    motion: ArmMotion,
    close_s: float,
) -> InterceptPlan:
    """Earliest meeting with a point on the leg, or say why there is none.

    Args:
        target_belt_m: (3,) the grasp point in belt coordinates: x along the belt minus travel, world y and z.
        belt: The belt state, with acceleration, used to predict travel.
        tool_world_m: (3,) where the tool is now.
        now_s: Planning time; the arm starts moving `command_latency_s` later.
        window: Where this arm may meet and close.
        motion: This arm's limits.
        close_s: Time for the jaws to close while the tool follows the belt.

    Raises:
        NoFeasibleInterceptError: If the leg is outside the window across the belt, the belt will not
            bring it in, the meet time does not settle, or the leg leaves before the jaws close.
    """
    if not window.y_min_m <= target_belt_m[1] <= window.y_max_m:
        raise NoFeasibleInterceptError(f"the grasp point at y = {target_belt_m[1]:.3f} m is outside the arm's window")
    start_s = now_s + motion.command_latency_s
    meet_s = start_s
    for _ in range(FIXED_POINT_ITERATIONS):
        distance_m = float(np.linalg.norm(_world_at(target_belt_m, belt, meet_s) - tool_world_m))
        following_s = start_s + motion.move_time_s(distance_m, belt.speed_at(meet_s))
        if abs(following_s - meet_s) < FIXED_POINT_TOLERANCE_S:
            meet_s = following_s
            break
        meet_s = following_s
    else:
        raise NoFeasibleInterceptError("the meeting time did not settle; the belt outruns the arm")
    # An arm that would arrive before the leg reaches the window waits at the window's entry.
    meet_s = _when_travel_reaches(window.x_min_m - target_belt_m[0], belt, meet_s)
    closed_s = meet_s + close_s
    meet_world, closed_world = _world_at(target_belt_m, belt, meet_s), _world_at(target_belt_m, belt, closed_s)
    if closed_world[0] > window.x_max_m:
        raise NoFeasibleInterceptError(
            f"the leg leaves the window at x = {window.x_max_m:.2f} m before the jaws close "
            f"(it would be at {closed_world[0]:.2f} m)"
        )
    return InterceptPlan(meet_s, meet_world, closed_s, closed_world, belt.speed_at(meet_s))
