"""Camera geometry tests.

These check the transform against MuJoCo's own renderer rather than against my
algebra, because the failure mode that matters is a convention mismatch, and a
self-consistent wrong convention passes any test written from the same algebra.
"""

import math

import mujoco
import numpy as np
import pytest

from meat_cell_sim.contracts import Frame, Pose2D
from meat_cell_sim.frames import (
    BASE_HEIGHT_M,
    CameraPose,
    Intrinsics,
    base_to_world,
    height_error_to_lateral_error_m,
    pixel_ray,
    pixel_to_plane,
    pose_world_to_base,
    world_to_base,
    world_to_pixel,
)


@pytest.fixture
def intr() -> Intrinsics:
    return Intrinsics.from_fovy(52.0, 1280, 960)


@pytest.fixture
def overhead() -> CameraPose:
    """The cell's overhead camera: 600 mm above the belt, looking straight down."""
    return CameraPose(position_m=np.array([-0.40, 0.50, 1.50]), rotation=np.eye(3))


def test_focal_length_matches_the_declared_field_of_view(intr: Intrinsics) -> None:
    """Half the image height must subtend half the vertical field of view."""
    assert math.degrees(2 * math.atan(intr.height_px / 2 / intr.fy)) == pytest.approx(52.0)
    assert intr.fx == intr.fy
    assert (intr.cx, intr.cy) == (639.5, 479.5)


def test_principal_point_is_the_pixel_centre_not_the_pixel_count(intr: Intrinsics) -> None:
    """Half a pixel of offset is 0.3 mm on the belt, which is not free at a 2 mm bound."""
    assert intr.cx == (intr.width_px - 1) / 2
    assert intr.cy != intr.width_px / 2


def test_projection_round_trips_through_the_plane(intr: Intrinsics, overhead: CameraPose) -> None:
    for point in ([-0.40, 0.50, 0.93], [-0.62, 0.44, 0.93], [-0.18, 0.55, 0.93]):
        pixel = world_to_pixel(intr, overhead, np.array(point))
        back = pixel_to_plane(intr, overhead, pixel[0], pixel[1], 0.93)
        assert back == pytest.approx(point, abs=1e-9)


def test_projection_matches_mujocos_renderer() -> None:
    """The check that catches a convention mismatch: agree with the actual pixels.

    A product is placed at a known pose, the segmentation mask is rendered, and
    the mask centroid must land on the projection of the product's top-face
    centre. Nadir is used because there the silhouette centroid and the face
    centre coincide exactly, so any disagreement is the transform's.
    """
    pytest.importorskip("mujoco")
    from meat_cell_sim.scene import CellConfig, build_model

    config = CellConfig()
    model, data = build_model(config)
    adr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "slab_free")]
    half_thickness = config.slab.half_extents_m[2]
    data.qpos[adr : adr + 7] = [-0.40, 0.50, 0.90 + half_thickness, 1, 0, 0, 0]
    mujoco.mj_forward(model, data)

    cam_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, "overhead")
    intr = Intrinsics.from_fovy(float(model.cam_fovy[cam_id]), 1280, 960)
    cam = CameraPose(data.cam_xpos[cam_id].copy(), data.cam_xmat[cam_id].reshape(3, 3).copy())

    with mujoco.Renderer(model, 960, 1280) as renderer:
        renderer.enable_segmentation_rendering()
        renderer.update_scene(data, camera="overhead")
        seg = renderer.render()
    geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "slab_geom")
    rows, cols = np.nonzero(seg[:, :, 0] == geom)
    predicted = world_to_pixel(intr, cam, np.array([-0.40, 0.50, 0.90 + 2 * half_thickness]))
    assert cols.mean() == pytest.approx(predicted[0], abs=0.5)
    assert rows.mean() == pytest.approx(predicted[1], abs=0.5)


def test_ray_through_the_principal_point_is_the_optical_axis(intr: Intrinsics, overhead: CameraPose) -> None:
    assert pixel_ray(intr, intr.cx, intr.cy) == pytest.approx([0.0, 0.0, -1.0])
    assert overhead.optical_axis == pytest.approx([0.0, 0.0, -1.0])


def test_image_row_runs_against_camera_y(intr: Intrinsics) -> None:
    """Row index increases downward; camera y increases upward. Getting this
    backwards mirrors the scene and survives any test done at nadir centre."""
    assert pixel_ray(intr, intr.cx, intr.cy + 100)[1] < 0


def test_height_error_scales_with_obliquity(overhead: CameraPose) -> None:
    """Zero under the camera, and equal to the height error at 45 degrees."""
    nadir = np.array([-0.40, 0.50, 0.90])
    assert height_error_to_lateral_error_m(overhead, nadir, 0.030) == pytest.approx(0.0)
    at_45 = np.array([-0.40 + 0.60, 0.50, 0.90])
    assert height_error_to_lateral_error_m(overhead, at_45, 0.030) == pytest.approx(0.030)
    # The cell's real case: a 30 mm product 150 mm off axis, 570 mm below.
    off_axis = np.array([-0.25, 0.50, 0.93])
    assert height_error_to_lateral_error_m(overhead, off_axis, 0.030) == pytest.approx(0.0079, abs=1e-4)


def test_non_orthonormal_rotation_is_refused() -> None:
    """A scaled or reflected rotation biases every position smoothly, which is
    the hardest calibration fault to notice downstream."""
    with pytest.raises(ValueError, match="not orthonormal"):
        CameraPose(np.zeros(3), np.eye(3) * 1.01)
    with pytest.raises(ValueError, match="reflection"):
        CameraPose(np.zeros(3), np.diag([1.0, 1.0, -1.0]))


def test_plane_behind_the_camera_is_refused(intr: Intrinsics, overhead: CameraPose) -> None:
    with pytest.raises(ValueError, match="behind the camera"):
        pixel_to_plane(intr, overhead, intr.cx, intr.cy, 2.0)
    with pytest.raises(ValueError, match="behind the camera"):
        world_to_pixel(intr, overhead, np.array([-0.40, 0.50, 2.0]))


def test_base_frame_differs_from_world_by_the_pedestal_only() -> None:
    point = np.array([0.3, -0.45, 0.92])
    assert world_to_base(point)[2] == pytest.approx(0.92 - BASE_HEIGHT_M)
    assert base_to_world(world_to_base(point)) == pytest.approx(point)


def test_pose_retagging_refuses_a_pose_that_is_not_in_the_world_frame() -> None:
    world = Pose2D(x_m=0.1, y_m=0.2, yaw_rad=0.3, frame=Frame.WORLD, stamp_s=1.0)
    assert pose_world_to_base(world).frame is Frame.BASE
    assert pose_world_to_base(world).x_m == world.x_m
    with pytest.raises(ValueError, match="expected a pose in world"):
        pose_world_to_base(Pose2D(x_m=0.1, y_m=0.2, yaw_rad=0.3, frame=Frame.CAMERA, stamp_s=1.0))
