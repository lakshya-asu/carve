"""Perception tests.

Every guard here exists because the condition it catches produces a confident
wrong answer rather than an error. That is the class of defect this cell keeps
finding, so the guards are tested harder than the happy path.
"""

import math

import numpy as np
import pytest

from meat_cell_sim.contracts import Frame, Pose2D
from meat_cell_sim.frames import CameraPose, Intrinsics
from meat_cell_sim.perception import (
    MIN_MASK_PIXELS,
    PerceptionRejectedError,
    anisotropy,
    backproject,
    estimate_from_depth,
    grip_axis_rad,
    mask_touches_border,
    principal_axis,
)
from meat_cell_sim.sensing import CameraFrameData

WIDTH, HEIGHT = 320, 240
SURFACE_Z_M = 0.93
CAMERA_Z_M = 1.50


def _frame(depth_m: np.ndarray) -> CameraFrameData:
    """A nadir camera 570 mm above a flat surface, matching the cell's geometry."""
    return CameraFrameData(
        stamp_s=1.0,
        rgb=np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8),
        depth_m=depth_m.astype(np.float32),
        intrinsics=Intrinsics.from_fovy(52.0, WIDTH, HEIGHT),
        camera=CameraPose(np.array([0.0, 0.0, CAMERA_Z_M]), np.eye(3)),
    )


def _rectangle_mask(length_px: int, width_px: int, angle_rad: float = 0.0) -> np.ndarray:
    """A filled rectangle centred in the image, rotated by `angle_rad`."""
    rows, cols = np.mgrid[0:HEIGHT, 0:WIDTH]
    x = cols - (WIDTH - 1) / 2
    y = -(rows - (HEIGHT - 1) / 2)
    along = x * math.cos(angle_rad) + y * math.sin(angle_rad)
    across = -x * math.sin(angle_rad) + y * math.cos(angle_rad)
    return (np.abs(along) <= length_px / 2) & (np.abs(across) <= width_px / 2)


def _flat_depth() -> np.ndarray:
    return np.full((HEIGHT, WIDTH), CAMERA_Z_M - SURFACE_Z_M, dtype=np.float32)


def test_clipped_mask_is_rejected_not_estimated() -> None:
    """The guard that matters most. A product running off the frame still gives a
    clean mask and a confident centroid, measured 9.8 mm wrong on this cell."""
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    mask[100:140, 0:60] = True
    assert mask_touches_border(mask)
    with pytest.raises(PerceptionRejectedError, match="touches the image border"):
        estimate_from_depth(mask, _frame(_flat_depth()))


def test_tiny_mask_is_rejected() -> None:
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    mask[100:105, 100:105] = True
    with pytest.raises(PerceptionRejectedError, match=f"below the {MIN_MASK_PIXELS} floor"):
        estimate_from_depth(mask, _frame(_flat_depth()))


def test_surface_selection_survives_depth_outliers_at_the_silhouette() -> None:
    """Selecting the surface below the maximum keeps only the outliers.

    On the real cell 32 pixels out of 48841 read up to 2.1 mm high because the
    depth buffer interpolates across the silhouette edge. A max-based band then
    holds nothing but those 32, and the centroid moved 16 mm with the axis
    turned 90 degrees. The median is unmoved by the same outliers.
    """
    mask = _rectangle_mask(120, 60)
    depth = _flat_depth()
    edge = mask & ~np.roll(mask, 1, axis=1)
    depth[edge] -= 0.021  # 21 mm nearer the camera, so 21 mm too high
    cloud = backproject(mask, _frame(depth))
    assert cloud.height_m == pytest.approx(SURFACE_Z_M, abs=1e-6)
    # Not one of the raised pixels survives, and the surface is still most of
    # the product: eroding the border is what costs the rest.
    assert cloud.points_m[:, 2].max() < SURFACE_Z_M + 1e-6
    assert cloud.points_m.shape[0] > 0.9 * (int(mask.sum()) - int(edge.sum()))


def test_folded_product_is_rejected_rather_than_averaged() -> None:
    """Two surfaces at different heights is a folded piece, not a flat one."""
    mask = _rectangle_mask(120, 60)
    depth = _flat_depth()
    half = mask.copy()
    half[:, : WIDTH // 2] = False
    depth[half] -= 0.040
    with pytest.raises(PerceptionRejectedError, match="folded, on edge, or occluded"):
        backproject(mask, _frame(depth))


@pytest.mark.parametrize("angle_deg", [0.0, 15.0, 45.0, 80.0, -35.0])
def test_axis_recovers_the_rectangle_heading(angle_deg: float) -> None:
    mask = _rectangle_mask(140, 56, math.radians(angle_deg))
    estimate = estimate_from_depth(mask, _frame(_flat_depth()))
    assert math.degrees(estimate.pose.yaw_rad) == pytest.approx(angle_deg, abs=0.6)
    assert estimate.pose.frame is Frame.WORLD
    assert estimate.pose.stamp_s == 1.0


def test_centroid_lands_under_the_camera_for_a_centred_product() -> None:
    estimate = estimate_from_depth(_rectangle_mask(140, 56), _frame(_flat_depth()))
    assert estimate.pose.x_m == pytest.approx(0.0, abs=1e-6)
    assert estimate.pose.y_m == pytest.approx(0.0, abs=1e-6)


def test_extents_come_back_in_metres_at_the_right_scale() -> None:
    """A 140 by 56 pixel rectangle 570 mm from a 52 degree camera.

    The extents are of the eroded surface, so each is two pixels short of the
    silhouette. That is 1.2 mm on the long axis here, it is deterministic, and a
    grasp width taken from it is conservative rather than optimistic, which is
    the safe direction.
    """
    frame = _frame(_flat_depth())
    metres_per_pixel = frame.intrinsics.metres_per_pixel_at(CAMERA_Z_M - SURFACE_Z_M)
    estimate = estimate_from_depth(_rectangle_mask(140, 56), frame)
    assert estimate.length_m == pytest.approx((140 - 2) * metres_per_pixel, rel=0.01)
    assert estimate.width_m == pytest.approx((56 - 2) * metres_per_pixel, rel=0.02)


def test_anisotropy_collapses_as_the_product_approaches_square() -> None:
    """The honest confidence signal. A square has no long axis and the heading
    becomes a coin flip between two answers 90 degrees apart."""
    long_piece = anisotropy(_pixel_points(_rectangle_mask(160, 40)))
    squarish = anisotropy(_pixel_points(_rectangle_mask(100, 96)))
    square = anisotropy(_pixel_points(_rectangle_mask(100, 100)))
    assert long_piece > 0.9
    assert 0.0 < squarish < 0.15
    assert square == pytest.approx(0.0, abs=0.01)
    assert long_piece > squarish > square


def _pixel_points(mask: np.ndarray) -> np.ndarray:
    rows, cols = np.nonzero(mask)
    return np.stack([cols.astype(float), rows.astype(float)], axis=-1)


def test_principal_axis_reports_the_longer_extent_first() -> None:
    _, _, length, width = principal_axis(_pixel_points(_rectangle_mask(160, 40)))
    assert length > width


def test_grip_axis_is_square_to_the_product() -> None:
    """Jaws close along their own axis, so they must approach across the piece.
    Ninety degrees out is a valid-looking grasp on the narrowest dimension."""
    estimate = estimate_from_depth(_rectangle_mask(140, 56, math.radians(30.0)), _frame(_flat_depth()))
    assert math.degrees(grip_axis_rad(estimate)) == pytest.approx(-60.0, abs=0.6)


def test_mask_shape_must_match_the_frame() -> None:
    with pytest.raises(PerceptionRejectedError, match="mask is"):
        estimate_from_depth(np.ones((10, 10), dtype=bool), _frame(_flat_depth()))


def test_pose_carries_the_frame_tag_that_stops_it_being_planned_against() -> None:
    estimate = estimate_from_depth(_rectangle_mask(140, 56), _frame(_flat_depth()))
    with pytest.raises(ValueError, match="expected a pose in base"):
        estimate.pose.in_frame(Frame.BASE)
    assert isinstance(estimate.pose, Pose2D)


def test_side_wall_points_are_excluded_by_their_normal_not_their_height() -> None:
    """The seam defect that failed the tracking gate at 0.50 m/s.

    A height band alone keeps a strip of the product's side wall as tall as the
    band. That strip always lies on the camera-facing side, so it drags the
    centroid toward the camera by an amount that grows with distance off the
    optical axis. Swept across the field at belt speed, that spatial ramp
    becomes a phantom slip in the tracker, which then extrapolates it.

    Run at the cell's real resolution rather than the small one the other tests
    use. Ground sampling is what decides whether an edge inside the height band
    can be steep at all: at 2.3 mm per pixel a 3 mm rise spans one pixel and is
    only 52 degrees, so the situation this test is about cannot be built.
    """
    width, height = 1280, 960
    intrinsics = Intrinsics.from_fovy(52.0, width, height)
    frame = lambda depth: CameraFrameData(  # noqa: E731
        stamp_s=1.0,
        rgb=np.zeros((height, width, 3), dtype=np.uint8),
        depth_m=depth.astype(np.float32),
        intrinsics=intrinsics,
        camera=CameraPose(np.array([0.0, 0.0, CAMERA_Z_M]), np.eye(3)),
    )
    rows, cols = np.mgrid[0:height, 0:width]
    x = cols - (width - 1) / 2
    y = -(rows - (height - 1) / 2)
    mask = (np.abs(x) <= 160) & (np.abs(y) <= 70)
    flat = np.full((height, width), CAMERA_Z_M - SURFACE_Z_M, dtype=np.float32)

    # A ramp rising 2 mm per column toward one edge. Ground sampling here is
    # 0.58 mm per pixel, so that is about 74 degrees. Its lowest step sits 2 mm
    # above the flat surface, inside the 3 mm height band, so the band alone
    # would keep it and only the normal test can reject it.
    sloped = flat.copy()
    left = int(cols[mask].min())
    for step in range(3):
        sloped[mask & (cols == left + step)] -= 0.002 * (3 - step)

    flat_cloud = backproject(mask, frame(flat))
    sloped_cloud = backproject(mask, frame(sloped))
    assert sloped_cloud.points_m[:, 2].max() <= sloped_cloud.height_m + 1e-9, (
        "a point on the steep edge survived the normal test"
    )
    assert sloped_cloud.points_m.shape[0] < flat_cloud.points_m.shape[0], "nothing was excluded"

    # The slope is on one side only. Keeping it would drag the centroid that
    # way along x; the cross-axis centroid is untouched either way.
    sloped_estimate = estimate_from_depth(mask, frame(sloped))
    flat_estimate = estimate_from_depth(mask, frame(flat))
    assert sloped_estimate.pose.y_m == pytest.approx(flat_estimate.pose.y_m, abs=1e-9)
    assert sloped_estimate.pose.x_m > flat_estimate.pose.x_m
