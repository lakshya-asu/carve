"""Depth camera models: the lens MuJoCo renders, and the depth the camera reports.

The geometry checks go through MuJoCo's renderer, because the failure that
matters is MuJoCo ignoring the declared lens and quietly rendering a square-pixel
camera, which a test written from the same algebra would never notice.
"""

import math

import mujoco
import numpy as np
import pytest

from meat_cell_sim.cameras import (
    DEPTH_CAMERAS,
    GEMINI_335L,
    REALSENSE_D455,
    EdgeEffects,
    add_depth_camera,
    apply_edge_effects,
    intrinsics_from_model,
    sense_depth,
)
from meat_cell_sim.frames import CameraPose, world_to_pixel

MOUNT_HEIGHT_M = 0.95


@pytest.mark.parametrize("camera", DEPTH_CAMERAS, ids=lambda c: c.name)
def test_focal_lengths_reproduce_the_datasheet_fields_of_view(camera) -> None:
    intr = camera.intrinsics
    assert math.degrees(2 * math.atan(intr.width_px / 2 / intr.fx)) == pytest.approx(camera.hfov_deg)
    assert math.degrees(2 * math.atan(intr.height_px / 2 / intr.fy)) == pytest.approx(camera.vfov_deg)


MARKER_TOP_M = 0.001


def _rig(camera, marker_offset_m: tuple[float, float], yaw_deg: float = 0.0) -> tuple[mujoco.MjModel, mujoco.MjData]:
    """A camera 0.95 m above a floor, a thin flat square on the floor off the optical axis.

    Flat, because a sphere seen off axis shows a silhouette whose centroid is not
    the projection of any known point; with a sphere this test failed by 2 px on a
    lens that is correct to 0.3 px.
    """
    spec = mujoco.MjSpec()
    spec.worldbody.add_body(name="overhead_cam_mount", pos=[0.0, 0.0, MOUNT_HEIGHT_M])
    add_depth_camera(spec, camera, yaw_deg=yaw_deg)
    spec.worldbody.add_geom(type=mujoco.mjtGeom.mjGEOM_PLANE, size=[3.0, 3.0, 0.1])
    spec.worldbody.add_geom(
        name="marker",
        type=mujoco.mjtGeom.mjGEOM_BOX,
        size=[0.01, 0.01, MARKER_TOP_M / 2],
        pos=[*marker_offset_m, MARKER_TOP_M / 2],
    )
    model = spec.compile()
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data


@pytest.mark.parametrize("yaw_deg", [0.0, 90.0])
@pytest.mark.parametrize("camera", DEPTH_CAMERAS, ids=lambda c: c.name)
def test_renderer_places_an_off_axis_point_where_the_datasheet_lens_predicts(camera, yaw_deg) -> None:
    """Off axis in both directions, so a wrong focal length in either axis moves the marker.

    At 90 degrees the image width lies across the belt, and a swapped axis would
    put the marker hundreds of pixels away.
    """
    model, data = _rig(camera, (0.30, 0.20), yaw_deg)
    cam_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, camera.name)
    intr = intrinsics_from_model(model, cam_id)
    assert intr is not None
    assert (intr.fx, intr.fy) == pytest.approx((camera.intrinsics.fx, camera.intrinsics.fy), rel=1e-6)

    pose = CameraPose(data.cam_xpos[cam_id].copy(), data.cam_xmat[cam_id].reshape(3, 3).copy())
    with mujoco.Renderer(model, camera.height_px, camera.width_px) as renderer:
        renderer.enable_segmentation_rendering()
        renderer.update_scene(data, camera=camera.name)
        seg = renderer.render()
    marker = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "marker")
    rows, cols = np.nonzero(seg[:, :, 0] == marker)
    assert rows.size > 0, "marker not in view"
    predicted = world_to_pixel(intr, pose, np.array([0.30, 0.20, MARKER_TOP_M]))
    assert cols.mean() == pytest.approx(predicted[0], abs=0.5)
    assert rows.mean() == pytest.approx(predicted[1], abs=0.5)


@pytest.mark.parametrize("camera", DEPTH_CAMERAS, ids=lambda c: c.name)
def test_depth_noise_on_a_flat_surface_matches_the_model(camera) -> None:
    flat = np.full((400, 400), MOUNT_HEIGHT_M)
    reported = sense_depth(flat, camera, np.random.default_rng(0))
    expected_rms = float(camera.depth_rms_m(MOUNT_HEIGHT_M))
    # Rounding to 1 mm adds a uniform term of 1 mm / sqrt(12) in quadrature.
    expected = math.hypot(expected_rms, camera.depth_unit_m / math.sqrt(12))
    assert float(np.std(reported)) == pytest.approx(expected, rel=0.05)
    assert float(np.mean(reported)) == pytest.approx(MOUNT_HEIGHT_M, abs=1e-4)


def test_depth_is_lost_outside_the_camera_range() -> None:
    close = np.full((10, 10), 0.4)  # inside the Gemini's 0.17 m minimum, outside the D455's 0.6 m
    assert np.all(sense_depth(close, GEMINI_335L, np.random.default_rng(1)) > 0)
    assert np.all(sense_depth(close, REALSENSE_D455, np.random.default_rng(1)) == 0)


def test_depth_is_reported_in_whole_depth_units() -> None:
    reported = sense_depth(np.full((50, 50), 0.9531), GEMINI_335L, np.random.default_rng(2))
    steps = reported / GEMINI_335L.depth_unit_m
    assert np.allclose(steps, np.round(steps), atol=1e-3)


def test_saturated_colour_loses_depth() -> None:
    depth = np.full((60, 60), MOUNT_HEIGHT_M)
    rgb = np.zeros((60, 60, 3), dtype=np.uint8)
    rgb[20:30, 20:30] = 255
    reported = sense_depth(depth, GEMINI_335L, np.random.default_rng(3), rgb=rgb)
    assert np.all(reported[22:28, 22:28] == 0)
    assert np.all(reported[50:, 50:] > 0)


def test_edge_effects_leave_a_flat_surface_alone() -> None:
    flat = np.full((120, 160), MOUNT_HEIGHT_M, dtype=np.float32)
    out = apply_edge_effects(flat, GEMINI_335L.intrinsics, EdgeEffects(), np.random.default_rng(5))
    assert np.array_equal(out, flat)


def test_edge_effects_stay_inside_the_band_around_a_depth_step() -> None:
    depth = np.full((120, 160), MOUNT_HEIGHT_M, dtype=np.float32)
    depth[:, 80:] = MOUNT_HEIGHT_M - 0.10  # a 100 mm step at column 80
    effects = EdgeEffects(max_incidence_deg=89.9)
    out = apply_edge_effects(depth, GEMINI_335L.intrinsics, effects, np.random.default_rng(6))
    changed_cols = np.nonzero(np.any(out != depth, axis=0))[0]
    assert changed_cols.size > 0
    assert changed_cols.min() >= 80 - effects.band_px - 1
    assert changed_cols.max() <= 80 + effects.band_px
    mixed = out[:, 76:84]
    assert np.any((mixed > MOUNT_HEIGHT_M - 0.10 + 1e-4) & (mixed < MOUNT_HEIGHT_M - 1e-4))


def test_edge_effects_drop_a_surface_seen_nearly_edge_on() -> None:
    intr = GEMINI_335L.intrinsics
    rows = np.arange(200, dtype=np.float32)[:, None] * np.ones((1, 160), dtype=np.float32)
    # Depth rising 10 mm per pixel down the image: a surface tilted about 85 degrees from the ray.
    steep = (0.5 + 0.010 * rows).astype(np.float32)
    out = apply_edge_effects(steep, intr, EdgeEffects(jump_m=1.0), np.random.default_rng(7))
    assert np.mean(out[50:150, 20:140] == 0) > 0.9
