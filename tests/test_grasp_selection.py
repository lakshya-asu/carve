import math

import numpy as np
import pytest

from meatcell.contracts import BoundingBox, GraspClass, ObjectObservation, ObservationSource, SimTime, Transform, Vector3
from meatcell.grasp_selection import classify_grasp_yaw, select_mask_grasp
from meatcell.perception import PinholeCalibration


@pytest.mark.parametrize(
    ("yaw_deg", "expected"),
    [
        (0.0, GraspClass.LONGITUDINAL),
        (14.9, GraspClass.LONGITUDINAL),
        (30.0, GraspClass.DIAGONAL_LEFT),
        (-30.0, GraspClass.DIAGONAL_RIGHT),
        (75.0, GraspClass.TRANSVERSE),
        (-75.0, GraspClass.TRANSVERSE),
    ],
)
def test_orientation_classifier_covers_tool_families(yaw_deg: float, expected: GraspClass) -> None:
    assert classify_grasp_yaw(math.radians(yaw_deg)) is expected


def test_mask_grasp_is_inside_mask_and_serializes_as_robot_candidate() -> None:
    mask = np.zeros((120, 160), dtype=bool)
    mask[45:75, 35:125] = True
    depth = np.full(mask.shape, 1.4, dtype=np.float32)
    observation = ObjectObservation(
        "detection-1",
        SimTime(0),
        SimTime.from_seconds(0.03),
        "meat_reference",
        0.91,
        BoundingBox(35.0, 45.0, 125.0, 75.0),
        None,
        Transform.planar(0.0, 0.0, 0.88, 0.0),
        Vector3(1e-5, 1e-5, 1e-5),
        1e-4,
        1.0,
        0.95,
        ObservationSource.SEGMENTATION,
    )
    calibration = PinholeCalibration(0.0, 0.0, 2.28, 500.0, 500.0, 80.0, 60.0, 0.8075, 0.002, 0.002)
    proposal = select_mask_grasp(
        mask=mask,
        depth_m=depth,
        observation=observation,
        track_id="track-1",
        calibration=calibration,
        surface_to_center_offset_m=0.0,
    )
    assert mask[round(proposal.grasp_point_v_px), round(proposal.grasp_point_u_px)]
    assert proposal.grasp_class is GraspClass.LONGITUDINAL
    assert proposal.estimated_width_m == pytest.approx(0.084, abs=0.01)
    assert abs(proposal.grasp_in_product.translation.x_m) < 0.01
    assert abs(proposal.grasp_in_product.translation.y_m) < 0.01
    candidate = proposal.as_candidate()
    assert candidate.track_id == "track-1"
    assert candidate.quality == proposal.quality
    assert candidate.to_json() == candidate.to_json()
