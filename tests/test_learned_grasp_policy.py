"""Learned grasp policy: its input vector, and that it only moves the deterministic grasp."""

import math
from pathlib import Path

import numpy as np
import pytest

from meat_cell_sim.belt_state import BeltState
from meat_cell_sim.grasp_action import LegPerception
from meat_cell_sim.grasp_policy import ShankGraspRule
from meat_cell_sim.learned_grasp_policy import FEATURES, TILT_CLASSES_RAD, LearnedGraspPolicy, grasp_features


def _leg() -> LegPerception:
    """A 740 mm leg along +x with its ham at belt x = -3.4 m."""
    stations = np.linspace(0.0, 0.74, 40)
    return LegPerception(
        stamp_s=1.0,
        belt_travel_m=3.0,
        belt_surface_z_m=0.90,
        centre_of_gravity_belt_m=np.array([-3.2, 0.45, 0.97]),
        outline_centre_belt_m=np.array([-3.16, 0.45]),
        axis_rad=0.0,
        length_m=0.74,
        volume_m3=0.011,
        stations_m=stations,
        centreline_belt_m=np.column_stack([-3.4 + stations, np.full(40, 0.45)]),
        widths_m=np.interp(stations, [0.0, 0.3, 0.45, 0.74], [0.24, 0.24, 0.10, 0.06]),
        top_heights_m=np.interp(stations, [0.0, 0.3, 0.45, 0.74], [0.18, 0.18, 0.09, 0.06]),
        method="test",
    )


def _weights(tmp_path: Path, last_bias: np.ndarray) -> Path:
    rng = np.random.default_rng(0)
    path = tmp_path / "policy.npz"
    np.savez(
        path,
        w0=rng.normal(size=(16, FEATURES)).astype(np.float32),
        b0=np.zeros(16, np.float32),
        w1=np.zeros((3 + len(TILT_CLASSES_RAD), 16), np.float32),
        b1=last_bias.astype(np.float32),
    )
    return path


def test_the_input_is_the_profile_and_the_leg_and_belt_scalars() -> None:
    features = grasp_features(_leg(), BeltState(0.0, 3.0, 0.3, -0.1))
    assert features.shape == (FEATURES,) and np.all(np.isfinite(features))
    assert features[-2:] == pytest.approx([0.3, -0.1])


def test_a_zero_offset_is_the_deterministic_grasp(tmp_path: Path) -> None:
    policy = LearnedGraspPolicy(_weights(tmp_path, np.array([0.0, 0.0, 0.0, 5.0, 0.0, 0.0])))
    learned, rule = policy.decide(_leg()), ShankGraspRule().decide(_leg())
    assert np.allclose(learned.grasp_point_belt_m, rule.grasp_point_belt_m)
    assert learned.finger_axis_rad == pytest.approx(rule.finger_axis_rad)
    assert learned.tool_tilt_rad == 0.0 and learned.opening_m == pytest.approx(rule.opening_m, abs=0.01)


def test_offsets_move_the_grasp_along_the_leg_and_tilt_only_where_allowed(tmp_path: Path) -> None:
    weights = _weights(tmp_path, np.array([-0.05, 0.01, math.radians(10.0), 0.0, 0.0, 5.0]))
    rule = ShankGraspRule().decide(_leg())
    learned = LearnedGraspPolicy(weights).decide(_leg())
    assert learned.grasp_point_belt_m[:2] - rule.grasp_point_belt_m[:2] == pytest.approx([-0.05, 0.01], abs=1e-6)
    assert learned.tool_tilt_rad == pytest.approx(math.radians(30.0))
    assert LearnedGraspPolicy(weights, can_tilt=False).decide(_leg()).tool_tilt_rad == 0.0
