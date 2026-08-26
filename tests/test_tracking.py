import pytest

from meatcell.contracts import (
    BoundingBox,
    ObjectObservation,
    ObservationSource,
    SimTime,
    TrackLifecycle,
    Transform,
    Vector3,
)
from meatcell.tracking import ObjectTracker, TrackerConfig


def observation(detection_id: str, exposure_s: float, delivery_s: float, x_m: float, yaw_rad: float = 0.0) -> ObjectObservation:
    return ObjectObservation(
        detection_id=detection_id,
        exposure_time=SimTime.from_seconds(exposure_s),
        delivery_time=SimTime.from_seconds(delivery_s),
        class_name="meat_reference",
        confidence=0.95,
        bbox=BoundingBox(1.0, 1.0, 20.0, 10.0),
        instance_mask_rle=None,
        pose_belt=Transform.planar(x_m, 0.0, 0.04, yaw_rad),
        position_variance_m2=Vector3(1e-5, 1e-5, 1e-5),
        yaw_variance_rad2=1e-4,
        visible_fraction=1.0,
        geometry_quality=1.0,
        source=ObservationSource.GROUND_TRUTH,
    )


def test_delayed_observation_updates_at_exposure_then_propagates_to_now() -> None:
    tracker = ObjectTracker(TrackerConfig(confirmation_hits=1))
    track = tracker.update(
        observation("piece-1", 0.10, 0.13, 0.224),
        current_time=SimTime.from_seconds(0.13),
        encoder_speed_mps=2.24,
    )
    assert track.last_exposure_time == SimTime.from_seconds(0.10)
    assert track.state_time == SimTime.from_seconds(0.13)
    assert track.pose_belt.translation.x_m == pytest.approx(0.2912)


def test_encoder_informed_velocity_yaw_rate_and_future_uncertainty() -> None:
    tracker = ObjectTracker(TrackerConfig(confirmation_hits=2, velocity_measurement_weight=1.0))
    first = tracker.update(observation("piece-1", 0.0, 0.0, 0.0), current_time=SimTime(0), encoder_speed_mps=2.24)
    second = tracker.update(
        observation("piece-1", 0.1, 0.12, 0.224, 0.05),
        current_time=SimTime.from_seconds(0.12),
        encoder_speed_mps=2.24,
    )
    assert first.lifecycle is TrackLifecycle.TENTATIVE
    assert second.lifecycle is TrackLifecycle.CONFIRMED
    predicted = tracker.predict(second.track_id, SimTime.from_seconds(0.5))
    assert predicted.pose_belt.translation.x_m == pytest.approx(1.12, abs=1e-9)
    assert predicted.pose_belt.yaw_rad == pytest.approx(0.25, abs=1e-9)
    assert predicted.position_variance_m2.x_m > second.position_variance_m2.x_m


def test_track_id_continuity_missed_lost_expired_and_reset() -> None:
    tracker = ObjectTracker(TrackerConfig(confirmation_hits=1, max_missed_updates=1, expiry_s=0.2))
    first = tracker.update(observation("piece-1", 0.0, 0.0, 0.0), current_time=SimTime(0), encoder_speed_mps=2.24)
    second = tracker.update(
        observation("piece-1", 0.05, 0.05, 0.112),
        current_time=SimTime.from_seconds(0.05),
        encoder_speed_mps=2.24,
    )
    assert first.track_id == second.track_id
    tracker.mark_missed(first.track_id, SimTime.from_seconds(0.10))
    lost = tracker.mark_missed(first.track_id, SimTime.from_seconds(0.15))
    assert lost.lifecycle is TrackLifecycle.LOST
    expired = tracker.mark_missed(first.track_id, SimTime.from_seconds(0.25))
    assert expired.lifecycle is TrackLifecycle.EXPIRED
    tracker.reset()
    assert tracker.tracks == ()


def test_nominal_ground_truth_prediction_stays_inside_numerical_bound() -> None:
    tracker = ObjectTracker(TrackerConfig(confirmation_hits=1))
    track = tracker.update(
        observation("piece-9", 1.0, 1.03, 2.24),
        current_time=SimTime.from_seconds(1.03),
        encoder_speed_mps=2.24,
    )
    predicted = tracker.predict(track.track_id, SimTime.from_seconds(1.4))
    assert abs(predicted.pose_belt.translation.x_m - 3.136) < 1e-9


def test_out_of_order_observation_is_rejected() -> None:
    tracker = ObjectTracker(TrackerConfig(confirmation_hits=1))
    tracker.update(observation("piece", 0.1, 0.1, 0.2), current_time=SimTime.from_seconds(0.1), encoder_speed_mps=2.0)
    with pytest.raises(ValueError, match="increase"):
        tracker.update(observation("piece", 0.05, 0.11, 0.1), current_time=SimTime.from_seconds(0.11), encoder_speed_mps=2.0)
