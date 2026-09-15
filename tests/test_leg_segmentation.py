"""Leg segmentation from the overhead depth camera, checked in the real cell.

The frames come from the simulated cell with the Gemini 335L model and its
noise, and the answer is scored against the simulator's own silhouette.
"""

import math

import numpy as np
import pytest

from meat_cell_sim.arms import ArmModel
from meat_cell_sim.cameras import GEMINI_335L, sense_depth
from meat_cell_sim.cell import Cell
from meat_cell_sim.gripper import GripperModel
from meat_cell_sim.leg_segmentation import BeltRegion, EmptyBeltReference, LegSegmenter
from meat_cell_sim.product import LegConfig
from meat_cell_sim.scene import CellConfig
from meat_cell_sim.segmentation import score_mask
from meat_cell_sim.sensing import CameraFrameData, CameraSpec

CAM = GEMINI_335L.name
OUT_OF_VIEW_X_M = 1.3


def _noisy(frame: CameraFrameData, rng: np.random.Generator) -> CameraFrameData:
    return CameraFrameData(
        frame.stamp_s, frame.rgb, sense_depth(frame.depth_m, GEMINI_335L, rng), frame.intrinsics, frame.camera
    )


@pytest.fixture(scope="module")
def cell():
    leg = LegConfig()
    # The experiment's cell: UR20 behind the far rail. The default UR5e stands on the
    # near side, inside the strip past the open edge that the segmenter searches for
    # overhanging trotters, and its base is found as "leg" on an empty belt.
    config = CellConfig(
        belt_speed_mps=0.0,
        leg=leg,
        arm=ArmModel.UR20,
        gripper=GripperModel.JAW_GEH6180,
        depth_cameras=(GEMINI_335L,),
        depth_camera_yaw_deg=90.0,
    )
    spec = {CAM: CameraSpec(CAM, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)}
    with Cell(config, spec) as built:
        built.reset()
        yield built


@pytest.fixture(scope="module")
def segmenter(cell) -> LegSegmenter:
    rng = np.random.default_rng(0)
    cell.place_product(OUT_OF_VIEW_X_M, 0.5, -math.pi / 2, settle_s=0.05)
    empties = [_noisy(cell.observe(CAM)[1], rng) for _ in range(10)]
    return LegSegmenter(EmptyBeltReference.from_frames(empties))


def test_the_reference_plane_is_the_belt_surface_not_the_floor(segmenter) -> None:
    """The floor fills more of this camera's view than the belt; a whole-frame fit found the floor."""
    plane = segmenter.reference.plane
    belt_top_point = np.array([[-0.40, 0.50, 0.90]])
    assert plane.height_of(belt_top_point)[0] == pytest.approx(0.0, abs=0.002)
    assert plane.normal[2] > 0.999


def test_a_trotter_hanging_past_the_open_edge_is_kept(cell, segmenter) -> None:
    """Past the open edge the empty frame sees the floor; the trotter must still count as leg.

    The first measurement lost these pixels to the height ceiling and put the
    centroid up to 50 mm out.
    """
    _place(cell, -0.40, 0.30, 0.0)  # trotter tip about 60 mm past the open edge at y 0.15
    _, frame = cell.observe(CAM)
    truth = cell.ground_truth(CAM).piece_mask
    result = segmenter.segment(_noisy(frame, np.random.default_rng(4)))
    assert result.accepted, result.refused
    assert score_mask(result.mask, truth).recall > 0.97


def _place(cell, x_m: float, y_m: float, yaw_deg: float) -> None:
    leg = cell.config.leg
    heading = -math.pi / 2 + math.radians(yaw_deg)
    cell.place_product(
        x_m - leg.outline_centre_m * math.cos(heading), y_m - leg.outline_centre_m * math.sin(heading), heading, 0.2
    )


def test_a_leg_on_the_belt_is_found_as_one_close_mask(cell, segmenter) -> None:
    _place(cell, -0.40, 0.45, 20.0)
    _, frame = cell.observe(CAM)
    truth = cell.ground_truth(CAM).piece_mask
    result = segmenter.segment(_noisy(frame, np.random.default_rng(1)))
    assert result.accepted, result.refused
    score = score_mask(result.mask, truth)
    assert score.iou > 0.90
    assert score.precision > 0.97


def test_an_empty_belt_is_refused(cell, segmenter) -> None:
    cell.place_product(OUT_OF_VIEW_X_M, 0.5, -math.pi / 2, settle_s=0.05)
    _, frame = cell.observe(CAM)
    result = segmenter.segment(_noisy(frame, np.random.default_rng(2)))
    assert not result.accepted
    assert not result.mask.any()


def test_a_leg_running_off_the_image_is_refused(cell, segmenter) -> None:
    # The image's short side runs along the belt, about 0.6 m either side of the camera.
    _place(cell, -0.40 + 0.62, 0.45, 0.0)
    _, frame = cell.observe(CAM)
    result = segmenter.segment(_noisy(frame, np.random.default_rng(3)))
    assert result.refused == "leg runs off the image edge"


def test_the_region_is_tested_in_the_world_not_on_the_image() -> None:
    """A point high on a ham near the rail is inside the region; its belt-height projection is not."""
    region = BeltRegion()
    camera_y_m, camera_height_m = 0.50, 0.95
    point_y_m, point_height_m = 0.83, 0.20
    projected_y_m = camera_y_m + (point_y_m - camera_y_m) * camera_height_m / (camera_height_m - point_height_m)
    assert region.contains(np.array([0.0]), np.array([point_y_m]))[0]
    assert not region.contains(np.array([0.0]), np.array([projected_y_m]))[0]
