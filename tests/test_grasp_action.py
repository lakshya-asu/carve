"""The arm-agnostic grasp action: its checks and the tool orientation every executor uses."""

import math

import numpy as np
import pytest

from meat_cell_sim.grasp_action import GraspAction, tool_rotation


def _action(**changes: object) -> GraspAction:
    fields = {
        "stamp_s": 1.0,
        "policy": "test",
        "grasp_point_belt_m": np.array([-0.2, 0.5, 0.95]),
        "finger_axis_rad": 0.3,
        "tool_tilt_rad": 0.0,
        "opening_m": 0.12,
        "approach_height_m": 0.15,
        "close_s": 0.6,
    }
    return GraspAction(**(fields | changes))  # type: ignore[arg-type]


def test_the_grasp_point_rides_with_the_belt() -> None:
    assert np.allclose(_action().world_point_m(0.35), [0.15, 0.5, 0.95])


def test_impossible_grasps_are_rejected_when_made() -> None:
    with pytest.raises(ValueError):
        _action(opening_m=0.0)
    with pytest.raises(ValueError):
        _action(tool_tilt_rad=math.radians(120.0))
    with pytest.raises(ValueError):
        _action(grasp_point_belt_m=np.array([0.0, np.nan, 0.9]))


def test_a_vertical_tool_points_down_with_the_jaws_along_the_finger_axis() -> None:
    rotation = tool_rotation(0.3, 0.0)
    assert np.allclose(rotation[:, 2], [0.0, 0.0, -1.0])
    assert np.allclose(rotation[:, 1], [math.cos(0.3), math.sin(0.3), 0.0])
    assert np.allclose(rotation.T @ rotation, np.eye(3)) and np.linalg.det(rotation) == pytest.approx(1.0)


def test_a_tilt_leans_the_tool_along_the_leg_and_keeps_the_jaw_line() -> None:
    rotation = tool_rotation(0.3, math.radians(30.0))
    assert rotation[:, 2] @ np.array([0.0, 0.0, -1.0]) == pytest.approx(math.cos(math.radians(30.0)))
    assert np.allclose(rotation[:, 1], tool_rotation(0.3, 0.0)[:, 1])
