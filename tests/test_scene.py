"""Tests for the meat cell scene.

The physics tests are the ones that matter. Two calibration errors were found by
hand before these existed: side rails jamming the belt against the world, and a
velocity servo fighting joint damping so the belt ran at two thirds of the
commanded speed. Both were silent, and both would have biased every intercept.
"""

from __future__ import annotations

import mujoco
import numpy as np
import pytest

from meat_cell_sim.scene import CellConfig, SlabConfig, build_model, save_xml

UR5E_MAX_REACH_M = 0.850


def _site(model: mujoco.MjModel, data: mujoco.MjData, name: str) -> np.ndarray:
    return data.site_xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)]


def _settle(model: mujoco.MjModel, data: mujoco.MjData, seconds: float = 0.5) -> None:
    home = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "ur_home")
    mujoco.mj_resetDataKeyframe(model, data, home)
    pan = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "ur_shoulder_pan_joint")
    data.ctrl[1:7] = data.qpos[model.jnt_qposadr[pan] :][:6]
    for _ in range(int(seconds / model.opt.timestep)):
        mujoco.mj_step(model, data)


def test_model_has_the_actuators_and_sensors_a_run_needs() -> None:
    model, _ = build_model()
    names = {mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) for i in range(model.nu)}
    assert names == {
        "belt_drive",
        "ur_shoulder_pan",
        "ur_shoulder_lift",
        "ur_elbow",
        "ur_wrist_1",
        "ur_wrist_2",
        "ur_wrist_3",
        "g_grip",
    }
    sensors = {mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_SENSOR, i) for i in range(model.nsensor)}
    assert {"belt_encoder", "belt_speed", "slab_pos", "slab_quat"} <= sensors
    cameras = {mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_CAMERA, i) for i in range(model.ncam)}
    assert cameras == {"overhead", "verify", "g_wrist"}


def test_cameras_sit_at_the_heights_the_experiment_record_specifies() -> None:
    """950 mm above the belt and 500 mm above the lane, both surfaces at z = 0.90.

    The overhead camera was at 600 mm while the product was a 180 mm slab. A
    whole pork leg is 722 mm long and can lie across the belt as readily as
    along it, so the binding constraint became the field's short axis: it has to
    cover the 700 mm belt width, which puts the camera at 950 mm.
    """
    model, data = build_model()
    _settle(model, data, 0.1)
    for cam_name, expected_m in (("overhead", 0.950), ("verify", 0.500)):
        cam = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, cam_name)
        height = float(data.cam_xpos[cam][2]) - 0.90
        assert height == pytest.approx(expected_m, abs=1e-6), f"{cam_name} sits {height:.3f} m above the surface"


def test_pick_zone_and_cutter_lane_are_inside_the_arm_reach() -> None:
    model, data = build_model()
    _settle(model, data, 0.1)
    base = _site(model, data, "arm_mount")
    for name in ("slab_centre", "lane_centre"):
        reach = float(np.linalg.norm(_site(model, data, name) - base))
        assert reach < UR5E_MAX_REACH_M, f"{name} at {reach:.3f} m is outside the UR5e reach"


def test_slab_rests_on_the_belt_without_sinking() -> None:
    model, data = build_model()
    _settle(model, data, 0.5)  # site_xpos is only valid after a forward pass
    z_start = float(_site(model, data, "slab_centre")[2])
    for _ in range(int(1.0 / model.opt.timestep)):
        mujoco.mj_step(model, data)
    z_end = float(_site(model, data, "slab_centre")[2])
    assert abs(z_end - z_start) < 1e-3, f"slab moved {1000 * (z_start - z_end):.2f} mm vertically at rest"


@pytest.mark.parametrize("speed", [0.10, 0.30])
def test_belt_tracks_commanded_speed_and_carries_the_slab(speed: float) -> None:
    """A velocity servo fighting joint damping ran the belt at two thirds speed."""
    model, data = build_model()
    _settle(model, data, 0.5)
    belt_ctrl = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "belt_drive")
    belt_qpos = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "belt_x")]
    data.ctrl[belt_ctrl] = speed
    for _ in range(200):
        mujoco.mj_step(model, data)  # reach steady state before measuring

    seconds = 1.0
    steps = int(seconds / model.opt.timestep)
    belt_0, slab_0 = float(data.qpos[belt_qpos]), float(_site(model, data, "slab_centre")[0])
    for _ in range(steps):
        mujoco.mj_step(model, data)
    belt_v = (float(data.qpos[belt_qpos]) - belt_0) / seconds
    slab_v = (float(_site(model, data, "slab_centre")[0]) - slab_0) / seconds

    assert abs(belt_v - speed) < 0.002, f"belt ran at {belt_v:.4f} m/s, commanded {speed:.4f}"
    assert abs(slab_v - belt_v) < 0.005, f"slab slipped: belt {belt_v:.4f}, slab {slab_v:.4f} m/s"


def test_config_values_reach_the_compiled_model() -> None:
    config = CellConfig(belt_friction_slide=0.42, slab=SlabConfig(half_extents_m=(0.1, 0.05, 0.02), mass_kg=0.75))
    model, _ = build_model(config)
    belt = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "belt_surface")
    slab = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "slab_geom")
    assert model.geom_friction[belt][0] == pytest.approx(0.42)
    assert model.geom_size[slab] == pytest.approx([0.1, 0.05, 0.02])
    body = model.geom_bodyid[slab]
    assert model.body_mass[body] == pytest.approx(0.75)


def test_slab_rests_on_the_belt_for_any_thickness() -> None:
    """Resting height is derived from thickness, so a sweep cannot start interpenetrating."""
    for thickness in (0.010, 0.030):
        config = CellConfig(slab=SlabConfig(half_extents_m=(0.09, 0.045, thickness)))
        model, data = build_model(config)
        _settle(model, data, 0.5)
        clearance = float(_site(model, data, "slab_centre")[2]) - 0.90 - thickness
        assert abs(clearance) < 1.5e-3, f"thickness {thickness}: slab centre off by {1000 * clearance:.2f} mm"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"belt_speed_mps": 2.0}, "actuator range"),
        ({"timestep_s": 0.0}, "timestep must be positive"),
    ],
)
def test_cell_config_rejects_out_of_range_values(kwargs: dict[str, float], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        CellConfig(**kwargs)


def test_slab_config_rejects_bad_geometry_and_unimplemented_deformable() -> None:
    with pytest.raises(ValueError, match="half extents"):
        SlabConfig(half_extents_m=(0.09, 0.0, 0.015))
    with pytest.raises(ValueError, match="mass must be positive"):
        SlabConfig(mass_kg=0.0)
    with pytest.raises(NotImplementedError, match="flex slab"):
        SlabConfig(deformable=True)


def test_saved_xml_names_every_actuator(tmp_path) -> None:
    """The saved XML references meshes relative to the Menagerie assets directory,
    so it is for inspection and for a launch that sets meshdir, not for reloading
    from a string."""
    out = save_xml(tmp_path / "cell.xml")
    xml = out.read_text()
    for name in ("belt_drive", "g_grip", "ur_shoulder_pan", "overhead"):
        assert name in xml
