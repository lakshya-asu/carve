"""Belt state from the encoder: speed, acceleration, and a prediction that stops when the belt does."""

import numpy as np
import pytest

from robotics.core.belt_state import BeltState, BeltStateEstimator

COUNT_M = 1e-4  # a 0.1 mm encoder count
RATE_HZ = 500.0


def _feed(estimator: BeltStateEstimator, travel_of_t, seconds: float) -> BeltState:
    state = None
    for k in range(int(seconds * RATE_HZ)):
        t = k / RATE_HZ
        state = estimator.update(t, np.floor(travel_of_t(t) / COUNT_M) * COUNT_M)
    assert state is not None
    return state


def test_a_steady_belt_reads_its_speed_and_no_acceleration() -> None:
    state = _feed(BeltStateEstimator(), lambda t: 0.30 * t, seconds=1.0)
    assert state.speed_mps == pytest.approx(0.30, abs=0.003)
    assert abs(state.acceleration_mps2) < 0.1


def test_a_speeding_belt_is_predicted_with_its_acceleration() -> None:
    speed, accel = 0.25, 0.5
    state = _feed(BeltStateEstimator(), lambda t: speed * t + 0.5 * accel * t**2, seconds=1.0)
    assert state.acceleration_mps2 == pytest.approx(accel, abs=0.1)
    ahead_s = state.stamp_s + 0.5
    truth_m = speed * ahead_s + 0.5 * accel * ahead_s**2
    # At constant speed the prediction is a dt^2 / 2 = 62 mm short; with the acceleration, a few mm at most.
    assert abs(state.travel_at(ahead_s) - truth_m) < 0.005
    assert truth_m - state.without_acceleration().travel_at(ahead_s) > 0.05


def test_a_braking_belt_is_predicted_to_stop_not_to_run_backwards() -> None:
    state = BeltState(stamp_s=0.0, travel_m=1.0, speed_mps=0.3, acceleration_mps2=-1.5)
    stopped_m = 1.0 + 0.3**2 / (2 * 1.5)
    assert state.travel_at(2.0) == pytest.approx(stopped_m)
    assert state.speed_at(2.0) == 0.0


def test_readings_must_move_forward_in_time() -> None:
    estimator = BeltStateEstimator(min_readings=3)
    assert estimator.update(0.0, 0.0) is None
    with pytest.raises(ValueError, match="increase"):
        estimator.update(0.0, 0.001)
