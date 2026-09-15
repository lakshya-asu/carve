"""Intercept planning on a moving, speeding or stopped belt."""

import numpy as np
import pytest

from meat_cell_sim.belt_state import BeltState
from meat_cell_sim.intercept import ArmMotion, NoFeasibleInterceptError, PickWindow, plan_intercept

WINDOW = PickWindow(x_min_m=-0.2, x_max_m=0.6, y_min_m=0.2, y_max_m=0.8)
ARM = ArmMotion(max_speed_mps=1.0, max_acceleration_mps2=3.0, command_latency_s=0.02)
TOOL = np.array([0.3, 0.5, 1.2])
# A grasp point 0.4 m upstream of the tool at belt travel 0, at world z 0.95.
TARGET = np.array([-0.1, 0.5, 0.95])


def _belt(speed_mps: float = 0.3, accel_mps2: float = 0.0) -> BeltState:
    return BeltState(stamp_s=0.0, travel_m=0.0, speed_mps=speed_mps, acceleration_mps2=accel_mps2)


def test_the_plan_meets_the_leg_where_it_will_be() -> None:
    belt = _belt()
    plan = plan_intercept(TARGET, belt, TOOL, 0.0, WINDOW, ARM, close_s=0.6)
    assert WINDOW.x_min_m <= plan.meet_world_m[0] <= WINDOW.x_max_m
    assert plan.meet_world_m[0] == pytest.approx(TARGET[0] + belt.travel_at(plan.meet_time_s))
    distance = np.linalg.norm(plan.meet_world_m - TOOL)
    assert plan.meet_time_s == pytest.approx(0.02 + ARM.move_time_s(float(distance), 0.3), abs=1e-5)


def test_the_acceleration_changes_where_the_arm_must_go() -> None:
    speeding = _belt(accel_mps2=0.4)
    long_window = PickWindow(x_min_m=-0.2, x_max_m=1.5, y_min_m=0.2, y_max_m=0.8)
    plan = plan_intercept(TARGET, speeding, TOOL, 0.0, long_window, ARM, close_s=0.6)
    steady_plan = plan_intercept(TARGET, speeding.without_acceleration(), TOOL, 0.0, long_window, ARM, close_s=0.6)
    where_the_leg_is = TARGET[0] + speeding.travel_at(steady_plan.meet_time_s)
    # Planned at constant speed, the arm arrives where the leg is not.
    assert where_the_leg_is - steady_plan.meet_world_m[0] > 0.02
    assert plan.meet_world_m[0] == pytest.approx(TARGET[0] + speeding.travel_at(plan.meet_time_s))


def test_a_slow_arm_cannot_meet_a_leg_before_it_leaves() -> None:
    slow = ArmMotion(max_speed_mps=0.05, max_acceleration_mps2=0.1)
    # Either the meeting time never settles or the leg is gone before the jaws close; both are refusals.
    with pytest.raises(NoFeasibleInterceptError, match=r"outruns the arm|leaves the window"):
        plan_intercept(TARGET, _belt(), TOOL, 0.0, WINDOW, slow, close_s=0.6)


def test_a_stopped_belt_is_met_in_place_or_refused() -> None:
    stopped = _belt(speed_mps=0.0)
    plan = plan_intercept(TARGET, stopped, TOOL, 0.0, WINDOW, ARM, close_s=0.6)
    assert plan.meet_world_m[0] == pytest.approx(TARGET[0])
    upstream = np.array([-0.5, 0.5, 0.95])
    with pytest.raises(NoFeasibleInterceptError, match="will not carry"):
        plan_intercept(upstream, stopped, TOOL, 0.0, WINDOW, ARM, close_s=0.6)


def test_an_early_arm_waits_for_the_leg_to_enter_the_window() -> None:
    upstream = np.array([-0.9, 0.5, 0.95])
    plan = plan_intercept(upstream, _belt(), TOOL, 0.0, WINDOW, ARM, close_s=0.6)
    assert plan.meet_world_m[0] == pytest.approx(WINDOW.x_min_m, abs=1e-6)
    assert plan.meet_time_s == pytest.approx((WINDOW.x_min_m - upstream[0]) / 0.3, abs=1e-4)


def test_a_leg_outside_the_window_across_the_belt_is_refused() -> None:
    with pytest.raises(NoFeasibleInterceptError, match="outside the arm's window"):
        plan_intercept(np.array([0.0, 0.1, 0.95]), _belt(), TOOL, 0.0, WINDOW, ARM, close_s=0.6)
