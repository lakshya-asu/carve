import math

import numpy as np
import pytest

from meat_cell_sim.contracts import (
    Frame,
    GraspChoice,
    Observation,
    Outcome,
    PieceEstimate,
    PlacementResult,
    Pose2D,
    axis_error_rad,
    wrap_axis_angle,
)


def _pose(frame: Frame = Frame.BASE, yaw: float = 0.0) -> Pose2D:
    return Pose2D(x_m=0.1, y_m=0.2, yaw_rad=yaw, frame=frame, stamp_s=1.0)


def test_frame_guard_blocks_a_camera_pose_used_as_a_base_pose() -> None:
    """The seam guard that stops S3 output being planned against directly."""
    camera_pose = _pose(Frame.CAMERA)
    with pytest.raises(ValueError, match="expected a pose in base, got one in camera"):
        camera_pose.in_frame(Frame.BASE)
    assert _pose(Frame.BASE).in_frame(Frame.BASE) is not None


def test_pose_rejects_nonfinite_position_and_negative_stamp() -> None:
    with pytest.raises(ValueError, match="must be finite"):
        Pose2D(x_m=float("nan"), y_m=0.0, yaw_rad=0.0, frame=Frame.BASE, stamp_s=0.0)
    with pytest.raises(ValueError, match="non-negative"):
        Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0, frame=Frame.BASE, stamp_s=-0.1)


@pytest.mark.parametrize(
    ("raw_deg", "expected_deg"),
    [(0, 0), (45, 45), (90, 90), (91, -89), (100, -80), (179, -1), (180, 0), (-100, 80), (270, 90)],
)
def test_axis_angle_folds_into_a_half_turn(raw_deg: float, expected_deg: float) -> None:
    """A slab has no head or tail, so headings are undirected."""
    assert math.degrees(wrap_axis_angle(math.radians(raw_deg))) == pytest.approx(expected_deg, abs=1e-9)


def test_axis_error_is_small_across_the_wrap() -> None:
    """+80 and -100 degrees describe the same alignment; a naive difference reports 180."""
    err = axis_error_rad(math.radians(80.0), math.radians(-100.0))
    assert math.degrees(err) == pytest.approx(0.0, abs=1e-9)
    assert math.degrees(axis_error_rad(math.radians(89.0), math.radians(-89.0))) == pytest.approx(2.0, abs=1e-9)
    assert 0.0 <= axis_error_rad(1.2, -0.7) <= math.pi / 2


def test_observation_rejects_wrong_shapes() -> None:
    ok = {"stamp_s": 0.0, "belt_travel_m": 0.0, "belt_speed_mps": 0.0, "gripper_width_m": 0.0}
    with pytest.raises(ValueError, match=r"joint_pos_rad must be \(n,\)"):
        Observation(joint_pos_rad=np.zeros((2, 3)), **ok)
    with pytest.raises(ValueError, match=r"joint_pos_rad must be \(n,\)"):
        Observation(joint_pos_rad=np.zeros(0), **ok)
    Observation(joint_pos_rad=np.zeros(4), **ok)  # a SCARA has four joints
    with pytest.raises(ValueError, match=r"depth_m must be \(H, W\)"):
        Observation(joint_pos_rad=np.zeros(6), depth_m=np.zeros((4, 4, 4), dtype=np.float32), **ok)
    Observation(joint_pos_rad=np.zeros(6), **ok)


def test_piece_estimate_requires_length_to_be_the_longer_extent() -> None:
    """Swapping length and width silently flips the axis by 90 degrees."""
    with pytest.raises(ValueError, match="must be the longer extent"):
        PieceEstimate(pose=_pose(), length_m=0.09, width_m=0.18, confidence=1.0, method="pca")
    with pytest.raises(ValueError, match=r"confidence must be in \[0, 1\]"):
        PieceEstimate(pose=_pose(), length_m=0.18, width_m=0.09, confidence=1.4, method="pca")


def test_grasp_choice_must_be_in_the_base_frame() -> None:
    with pytest.raises(ValueError, match="expected a pose in base"):
        GraspChoice(pose=_pose(Frame.PIECE), width_m=0.05, approach_height_m=0.08, rule="centroid")
    GraspChoice(pose=_pose(Frame.BASE), width_m=0.05, approach_height_m=0.08, rule="centroid")


def test_placement_result_cannot_report_a_measurement_it_did_not_make() -> None:
    with pytest.raises(ValueError, match="must report lane offset and yaw"):
        PlacementResult(outcome=Outcome.PLACED, cycle_time_s=3.0, seed=1)
    with pytest.raises(ValueError, match="must not report a placement measurement"):
        PlacementResult(outcome=Outcome.DROPPED, cycle_time_s=3.0, seed=1, lane_offset_m=0.001, lane_yaw_rad=0.0)
    PlacementResult(outcome=Outcome.DROPPED, cycle_time_s=3.0, seed=1)


def test_within_bound_matches_the_pre_registered_rigid_limit() -> None:
    inside = PlacementResult(
        outcome=Outcome.PLACED, cycle_time_s=3.0, seed=1, lane_offset_m=0.0019, lane_yaw_rad=math.radians(1.9)
    )
    outside_mm = PlacementResult(
        outcome=Outcome.PLACED, cycle_time_s=3.0, seed=1, lane_offset_m=0.0021, lane_yaw_rad=0.0
    )
    outside_deg = PlacementResult(
        outcome=Outcome.PLACED, cycle_time_s=3.0, seed=1, lane_offset_m=0.0, lane_yaw_rad=math.radians(2.1)
    )
    assert inside.within
    assert not outside_mm.within
    assert not outside_deg.within
    assert not PlacementResult(outcome=Outcome.TIMEOUT, cycle_time_s=9.0, seed=1).within
