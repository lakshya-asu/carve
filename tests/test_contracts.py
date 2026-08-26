import math

import pytest

from meatcell.contracts import (
    BoundingBox,
    GraspCandidate,
    ObjectObservation,
    ObservationSource,
    Quaternion,
    SimTime,
    Transform,
    Vector3,
    contract_from_json,
)


def observation() -> ObjectObservation:
    return ObjectObservation(
        detection_id="det-1",
        exposure_time=SimTime.from_seconds(1.0),
        delivery_time=SimTime.from_seconds(1.03),
        class_name="meat_reference",
        confidence=0.91,
        bbox=BoundingBox(10.0, 20.0, 110.0, 80.0),
        instance_mask_rle="10x2,20x4",
        pose_belt=Transform.planar(0.2, -0.1, 0.04, 0.3),
        position_variance_m2=Vector3(1e-4, 2e-4, 3e-4),
        yaw_variance_rad2=0.01,
        visible_fraction=0.95,
        geometry_quality=0.88,
        source=ObservationSource.SEGMENTATION,
    )


def test_quaternion_is_normalized_and_rejects_invalid_numbers() -> None:
    value = Quaternion(2.0, 0.0, 0.0, 0.0)
    assert value == Quaternion.identity()
    assert math.sqrt(value.w**2 + value.x**2 + value.y**2 + value.z**2) == pytest.approx(1.0)
    with pytest.raises(ValueError, match="norm"):
        Quaternion(0.0, 0.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="finite"):
        Quaternion(float("nan"), 0.0, 0.0, 0.0)


def test_contract_round_trip_preserves_nested_types_and_equality() -> None:
    original = observation()
    restored = contract_from_json(original.to_json())
    assert restored == original
    assert isinstance(restored, ObjectObservation)
    assert restored.source is ObservationSource.SEGMENTATION
    assert restored.pose_belt.rotation == original.pose_belt.rotation


def test_contracts_are_immutable() -> None:
    value = observation()
    with pytest.raises(Exception):
        value.confidence = 0.1  # type: ignore[misc]


def test_invalid_observation_and_grasp_values_fail() -> None:
    with pytest.raises(ValueError, match="delivery_time"):
        ObjectObservation(
            **{
                **observation().__dict__,
                "delivery_time": SimTime.from_seconds(0.5),
            }
        )
    with pytest.raises(ValueError, match="quality"):
        GraspCandidate("g", "t", Transform.identity(), 1.1, 0.01, 0.01)


def test_planar_helper_preserves_full_transform_contract() -> None:
    pose = Transform.planar(1.0, 2.0, 3.0, -0.8)
    assert pose.translation == Vector3(1.0, 2.0, 3.0)
    assert pose.yaw_rad == pytest.approx(-0.8)
    assert contract_from_json(pose.to_json()) == pose
