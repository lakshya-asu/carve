"""Timed tool waypoints for a grasp: come down along the tool axis onto a moving point, then follow it."""

import math

import numpy as np
import pytest

from robotics.core.belt_state import BeltState
from robotics.core.grasp_action import GraspAction
from robotics.core.grasp_execution import grasp_waypoints
from robotics.core.intercept import ArmMotion, PickWindow, plan_intercept

BELT = BeltState(stamp_s=0.0, travel_m=0.0, speed_mps=0.3, acceleration_mps2=0.0)


def _action(tilt_deg: float = 0.0) -> GraspAction:
    return GraspAction(
        stamp_s=0.0,
        policy="test",
        grasp_point_belt_m=np.array([-0.1, 0.5, 0.95]),
        finger_axis_rad=math.pi / 2,
        tool_tilt_rad=math.radians(tilt_deg),
        opening_m=0.12,
        approach_height_m=0.15,
        close_s=0.6,
    )


def _plan(action: GraspAction):
    window = PickWindow(-0.2, 1.0, 0.2, 0.8)
    return plan_intercept(
        action.grasp_point_belt_m, BELT, np.array([0.3, 0.5, 1.2]), 0.0, window, ArmMotion(1.0, 3.0), action.close_s
    )


def test_waypoints_come_down_onto_the_moving_point_and_follow_it() -> None:
    action = _action()
    plan = _plan(action)
    above, meet, closed = grasp_waypoints(action, plan, descend_s=0.4)
    assert [w.phase for w in (above, meet, closed)] == ["above", "meet", "closed"]
    assert above.time_s == pytest.approx(plan.meet_time_s - 0.4)
    assert not above.close_jaws and meet.close_jaws and closed.close_jaws
    # 150 mm straight above where the point was 0.4 s earlier: 120 mm upstream at 0.3 m/s.
    assert np.allclose(above.position_m, plan.meet_world_m + np.array([-0.12, 0.0, 0.15]))
    assert closed.position_m[0] - meet.position_m[0] == pytest.approx(0.3 * 0.6)


def test_a_tilted_tool_comes_in_along_its_own_axis() -> None:
    action = _action(tilt_deg=30.0)
    above, meet, _ = grasp_waypoints(action, _plan(action))
    offset = above.position_m - meet.position_m + np.array([0.3 * 0.4, 0.0, 0.0])
    assert np.allclose(offset / np.linalg.norm(offset), -meet.rotation[:, 2])
