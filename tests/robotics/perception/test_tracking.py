"""Tracker tests, written against the belt-frame model rather than the code.

The claim under test is that a carried product is a constant in belt
coordinates. These tests construct that situation exactly, then break it in the
specific ways the field breaks it: slip, a stale encoder, a wrapped heading.
"""

import math

import numpy as np
import pytest

from robotics.core.contracts import Frame, Observation, PieceEstimate, Pose2D
from robotics.perception.tracking import BeltTracker, finite_difference_velocity, prediction_error_m

BELT_SPEED_MPS = 0.30
FRAME_INTERVAL_S = 1.0 / 30.0


def _pair(
    stamp_s: float, x_m: float, y_m: float = 0.5, yaw_rad: float = 0.2, travel_m: float | None = None
) -> tuple[PieceEstimate, Observation]:
    travel = BELT_SPEED_MPS * stamp_s if travel_m is None else travel_m
    estimate = PieceEstimate(
        pose=Pose2D(x_m=x_m, y_m=y_m, yaw_rad=yaw_rad, frame=Frame.WORLD, stamp_s=stamp_s),
        length_m=0.18,
        width_m=0.09,
        confidence=0.9,
        method="test",
    )
    observation = Observation(
        stamp_s=stamp_s,
        belt_travel_m=travel,
        belt_speed_mps=BELT_SPEED_MPS,
        joint_pos_rad=np.zeros(6),
        gripper_width_m=0.14,
    )
    return estimate, observation


def _carried_track(samples: int = 8, x0_m: float = -0.6) -> BeltTracker:
    """A product riding the belt without slipping."""
    tracker = BeltTracker()
    for i in range(samples):
        stamp = 1.0 + i * FRAME_INTERVAL_S
        tracker.update(*_pair(stamp, x0_m + BELT_SPEED_MPS * stamp))
    return tracker


def test_a_carried_product_is_a_constant_in_belt_coordinates() -> None:
    state = _carried_track().state
    assert state.x_belt_m == pytest.approx(-0.6, abs=1e-9)
    assert state.slip_mps == pytest.approx(0.0, abs=1e-9)
    assert state.residual_m == pytest.approx(0.0, abs=1e-12)


def test_prediction_is_bookkeeping_not_extrapolation() -> None:
    """Half a second ahead, with no noise, must be exact rather than merely close."""
    tracker = _carried_track()
    state = tracker.state
    meet = state.last_stamp_s + 0.5
    predicted = tracker.predict(meet)
    truth = Pose2D(x_m=-0.6 + BELT_SPEED_MPS * meet, y_m=0.5, yaw_rad=0.2, frame=Frame.WORLD, stamp_s=meet)
    assert prediction_error_m(predicted, truth) == pytest.approx(0.0, abs=1e-12)


def test_slip_appears_as_a_slope_and_is_carried_into_the_prediction() -> None:
    """Slip does not break the model, it becomes a term in it."""
    slip = -0.02
    tracker = BeltTracker()
    for i in range(8):
        stamp = 1.0 + i * FRAME_INTERVAL_S
        drift = slip * (stamp - 1.0)
        tracker.update(*_pair(stamp, -0.6 + BELT_SPEED_MPS * stamp + drift))
    state = tracker.state
    assert state.slip_mps == pytest.approx(slip, abs=1e-9)
    horizon = 0.4
    predicted = tracker.predict(state.last_stamp_s + horizon)
    expected_x = -0.6 + BELT_SPEED_MPS * (state.last_stamp_s + horizon) + slip * (state.last_stamp_s + horizon - 1.0)
    assert predicted.x_m == pytest.approx(expected_x, abs=1e-9)


def test_averaging_reduces_position_noise_with_the_sample_count() -> None:
    """The reason for writing the state in belt coordinates: every observation
    measures the same constant, so the error falls as 1/sqrt(n)."""
    rng = np.random.default_rng(20260908)
    sigma = 0.0005
    errors = {}
    for samples in (1, 4, 16):
        residuals = []
        for _ in range(400):
            tracker = BeltTracker(history=max(samples, 4))
            for i in range(samples):
                stamp = 1.0 + i * FRAME_INTERVAL_S
                noise = rng.normal(0.0, sigma)
                tracker.update(*_pair(stamp, -0.6 + BELT_SPEED_MPS * stamp + noise))
            residuals.append(tracker.state.x_belt_m + 0.6)
        errors[samples] = float(np.std(residuals))
    assert errors[1] == pytest.approx(sigma, rel=0.2)
    assert errors[16] < errors[4] < errors[1]
    # The state is the fitted value at the most recent stamp, not the mean, so
    # the standard error is the ordinary-least-squares prediction variance at
    # the end of the window: sigma^2 * (1/n + 3(n-1)/(n(n+1))). A plain mean
    # would give sigma/4 at n=16; spending two degrees of freedom on the slip
    # slope costs most of that, which is the price of detecting slip at all.
    for samples in (4, 16):
        expected = sigma * math.sqrt(1 / samples + 3 * (samples - 1) / (samples * (samples + 1)))
        assert errors[samples] == pytest.approx(expected, rel=0.12)


def test_a_pose_and_an_encoder_from_different_instants_are_refused() -> None:
    """At 300 mm/s one frame of skew between image and encoder is 10 mm."""
    tracker = BeltTracker()
    estimate, _ = _pair(1.0, -0.3)
    _, stale = _pair(1.0 - FRAME_INTERVAL_S, -0.3)
    with pytest.raises(ValueError, match="must describe the same instant"):
        tracker.update(estimate, stale)


def test_a_camera_frame_pose_is_refused() -> None:
    tracker = BeltTracker()
    _, observation = _pair(1.0, -0.3)
    camera_pose = PieceEstimate(
        pose=Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0, frame=Frame.CAMERA, stamp_s=1.0),
        length_m=0.18,
        width_m=0.09,
        confidence=1.0,
        method="test",
    )
    with pytest.raises(ValueError, match="expected a pose in world"):
        tracker.update(camera_pose, observation)


def test_heading_averaging_handles_the_wrap() -> None:
    """+89 and -89 degrees describe nearly the same axis. Averaging them
    arithmetically gives 0, which is square to both."""
    tracker = BeltTracker()
    for i, yaw_deg in enumerate([89.0, -89.0, 89.0, -89.0, 88.0, -88.0]):
        stamp = 1.0 + i * FRAME_INTERVAL_S
        tracker.update(*_pair(stamp, -0.6 + BELT_SPEED_MPS * stamp, yaw_rad=math.radians(yaw_deg)))
    assert abs(math.degrees(tracker.state.yaw_rad)) == pytest.approx(90.0, abs=1.0)


def test_residual_exposes_a_product_that_is_not_following_the_model() -> None:
    tracker = BeltTracker()
    for i in range(8):
        stamp = 1.0 + i * FRAME_INTERVAL_S
        bump = 0.01 if i == 4 else 0.0
        tracker.update(*_pair(stamp, -0.6 + BELT_SPEED_MPS * stamp + bump))
    assert tracker.state.residual_m > 0.002


def test_finite_difference_velocity_amplifies_position_noise() -> None:
    """Why the encoder is the velocity source. Differencing two poses one frame
    apart turns 0.5 mm of position noise into 21 mm/s of velocity noise."""
    sigma = 0.0005
    rng = np.random.default_rng(7)
    errors = []
    for _ in range(500):
        earlier, _ = _pair(1.0, 0.0 + rng.normal(0, sigma))
        later, _ = _pair(1.0 + FRAME_INTERVAL_S, BELT_SPEED_MPS * FRAME_INTERVAL_S + rng.normal(0, sigma))
        velocity, dt = finite_difference_velocity(earlier, later)
        assert dt == pytest.approx(FRAME_INTERVAL_S)
        errors.append(float(velocity[0]) - BELT_SPEED_MPS)
    assert float(np.std(errors)) == pytest.approx(sigma * math.sqrt(2) / FRAME_INTERVAL_S, rel=0.15)


def test_finite_difference_refuses_unordered_estimates() -> None:
    earlier, _ = _pair(1.0, 0.0)
    with pytest.raises(ValueError, match="ordered in time"):
        finite_difference_velocity(earlier, earlier)


def test_an_empty_tracker_says_so_rather_than_returning_zeros() -> None:
    tracker = BeltTracker()
    with pytest.raises(RuntimeError, match="no observations"):
        _ = tracker.state


def test_reset_clears_the_history_between_products() -> None:
    tracker = _carried_track()
    tracker.reset()
    with pytest.raises(RuntimeError, match="no observations"):
        _ = tracker.state
