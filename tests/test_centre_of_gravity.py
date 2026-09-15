"""Centre of gravity from depth: solid columns under the seen surface, against the outline's centre."""

import math

import numpy as np
import pytest

from meat_cell_sim.centre_of_gravity import column_centroid, silhouette_centroid
from meat_cell_sim.evidence import Plane
from meat_cell_sim.frames import CameraPose, Intrinsics
from meat_cell_sim.sensing import CameraFrameData

CAMERA_HEIGHT_M = 0.95
BELT = Plane(normal=np.array([0.0, 0.0, 1.0]), offset_m=0.0, inlier_fraction=1.0, rms_residual_m=0.0)
# Two flat-topped blocks side by side, (x min, x max, y min, y max, height) in metres: a tall block
# and a low one with half its footprint, so the outline's centre and the volume's centre differ.
BLOCKS = ((-0.15, 0.05, -0.05, 0.05, 0.10), (0.05, 0.15, -0.05, 0.05, 0.03))
BLOCKS_VOLUME_M3 = 0.2 * 0.1 * 0.10 + 0.1 * 0.1 * 0.03
BLOCKS_CENTRE_M = np.array(
    [(0.002 * -0.05 + 0.0003 * 0.10) / BLOCKS_VOLUME_M3, 0.0, (0.002 * 0.05 + 0.0003 * 0.015) / BLOCKS_VOLUME_M3]
)


def _intrinsics(width: int = 640, height: int = 480, focal_px: float = 600.0) -> Intrinsics:
    return Intrinsics(focal_px, focal_px, (width - 1) / 2, (height - 1) / 2, width, height)


def _frame(depth_m: np.ndarray, intrinsics: Intrinsics, camera: CameraPose) -> CameraFrameData:
    rgb = np.zeros((*depth_m.shape, 3), dtype=np.uint8)
    return CameraFrameData(0.0, rgb, depth_m.astype(np.float32), intrinsics, camera)


def _looking_down_at_blocks() -> tuple[CameraFrameData, np.ndarray]:
    intr = _intrinsics()
    cols, rows = np.meshgrid(np.arange(intr.width_px), np.arange(intr.height_px))
    ray_x, ray_y = (cols - intr.cx) / intr.fx, -(rows - intr.cy) / intr.fy
    depth = np.full((intr.height_px, intr.width_px), CAMERA_HEIGHT_M)
    for x0, x1, y0, y1, top in sorted(BLOCKS, key=lambda block: -block[4]):
        z = CAMERA_HEIGHT_M - top
        seen = (ray_x * z >= x0) & (ray_x * z < x1) & (ray_y * z >= y0) & (ray_y * z < y1)
        depth[seen & (depth == CAMERA_HEIGHT_M)] = z  # the taller block hides what is behind it
    camera = CameraPose(np.array([0.0, 0.0, CAMERA_HEIGHT_M]), np.eye(3))
    return _frame(depth, intr, camera), depth < CAMERA_HEIGHT_M - 0.005


def test_columns_find_the_volume_centre_of_two_blocks() -> None:
    frame, mask = _looking_down_at_blocks()
    estimate = column_centroid(frame, mask, BELT)
    assert np.allclose(estimate.position_m, BLOCKS_CENTRE_M, atol=0.002)
    assert estimate.volume_m3 == pytest.approx(BLOCKS_VOLUME_M3, rel=0.03)


def test_the_outline_centre_ignores_how_tall_each_part_is() -> None:
    frame, mask = _looking_down_at_blocks()
    outline = silhouette_centroid(frame, mask, BELT)
    columns = column_centroid(frame, mask, BELT)
    # By area the two blocks balance at x = 0; by volume the tall block pulls the centre 30 mm over.
    assert np.allclose(outline.position_m, [0.0, 0.0, 0.0], atol=0.002)
    assert outline.volume_m3 == 0.0
    assert outline.position_m[0] - columns.position_m[0] > 0.025


def test_a_tilted_camera_weights_each_pixel_by_the_belt_it_covers() -> None:
    tilt = math.radians(15.0)
    rotation = np.array(
        [[1.0, 0.0, 0.0], [0.0, math.cos(tilt), -math.sin(tilt)], [0.0, math.sin(tilt), math.cos(tilt)]]
    )
    camera = CameraPose(np.array([0.0, -CAMERA_HEIGHT_M * math.tan(tilt), CAMERA_HEIGHT_M]), rotation)
    intr = _intrinsics()
    cols, rows = np.meshgrid(np.arange(intr.width_px), np.arange(intr.height_px))
    rays = np.stack([(cols - intr.cx) / intr.fx, -(rows - intr.cy) / intr.fy, -np.ones(cols.shape)], axis=-1)
    rays = rays @ rotation.T
    plate_top_m = 0.01  # a 200 mm square plate, 10 mm thick, centred under the optical axis
    depth = (plate_top_m - camera.position_m[2]) / rays[..., 2]
    hits = camera.position_m + rays * depth[..., None]
    mask = (np.abs(hits[..., 0]) <= 0.1) & (np.abs(hits[..., 1]) <= 0.1)
    estimate = column_centroid(_frame(depth, intr, camera), mask, BELT)
    # Far pixels cover more belt than near ones; unweighted, the centre slides about 2 mm toward the camera.
    assert np.allclose(estimate.position_m[:2], [0.0, 0.0], atol=0.001)
    assert estimate.volume_m3 == pytest.approx(0.2 * 0.2 * plate_top_m, rel=0.02)


def test_pixels_without_depth_are_left_out() -> None:
    frame, mask = _looking_down_at_blocks()
    whole = column_centroid(frame, mask, BELT)
    frame.depth_m[230:250, 250:270] = 0.0  # a patch of lost depth inside the tall block (rows 204 to 274)
    holed = column_centroid(frame, mask, BELT)
    assert holed.pixels == whole.pixels - 400
    assert holed.volume_m3 < whole.volume_m3


def test_a_mask_with_no_depth_is_refused() -> None:
    frame, mask = _looking_down_at_blocks()
    frame.depth_m[mask] = 0.0
    with pytest.raises(ValueError, match="valid depth"):
        column_centroid(frame, mask, BELT)
