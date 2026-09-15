"""Sensing tests: timestamps, exposure, and the oracle boundary.

The gate for this step is that an observation's timestamp matches the instant of
the state it describes, to under a millisecond. These tests check that against
the simulator's own clock rather than against the code's arithmetic.
"""

import numpy as np
import pytest

from meat_cell_sim.contracts import Frame
from meat_cell_sim.scene import CellConfig, build_model
from meat_cell_sim.sensing import CameraSpec, Sensors

pytest.importorskip("mujoco")
import mujoco

CAMERA = "overhead"
BELT_SPEED_MPS = 0.30


@pytest.fixture(scope="module")
def cell() -> tuple[mujoco.MjModel, mujoco.MjData, CellConfig]:
    config = CellConfig(belt_speed_mps=BELT_SPEED_MPS)
    model, data = build_model(config)
    return model, data, config


def _settled(model: mujoco.MjModel, data: mujoco.MjData, config: CellConfig, seconds: float = 0.5):
    mujoco.mj_resetData(model, data)
    adr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "slab_free")]
    data.qpos[adr : adr + 7] = [-0.50, 0.50, 0.90 + config.slab.half_extents_m[2], 1, 0, 0, 0]
    data.ctrl[0] = config.belt_speed_mps
    for _ in range(int(seconds / model.opt.timestep)):
        mujoco.mj_step(model, data)
    return data


def test_capture_does_not_disturb_the_caller_state(cell) -> None:
    """Exposure is rendered by stepping the simulator forward and restoring it.
    If the restore is wrong, every episode drifts and nothing else reveals it."""
    model, data, config = cell
    _settled(model, data, config)
    before = np.empty(mujoco.mj_stateSize(model, mujoco.mjtState.mjSTATE_FULLPHYSICS))
    mujoco.mj_getState(model, data, before, mujoco.mjtState.mjSTATE_FULLPHYSICS)
    with Sensors(model, {CAMERA: CameraSpec(CAMERA, 320, 240, exposure_s=0.005)}) as sensors:
        sensors.capture(data, CAMERA)
    after = np.empty_like(before)
    mujoco.mj_getState(model, data, after, mujoco.mjtState.mjSTATE_FULLPHYSICS)
    assert after == pytest.approx(before, abs=1e-12)


def test_stamp_is_the_exposure_midpoint_not_the_call_instant(cell) -> None:
    """At 300 mm/s a 5 ms exposure spans 1.5 mm, most of a 2 mm bound."""
    model, data, config = cell
    _settled(model, data, config)
    exposure = 4 * 0.002
    with Sensors(model, {CAMERA: CameraSpec(CAMERA, 320, 240, exposure_s=exposure)}) as sensors:
        frame = sensors.capture(data, CAMERA)
    assert frame.stamp_s == pytest.approx(data.time + exposure / 2, abs=1e-9)


def test_exposure_is_quantised_to_whole_timesteps_and_the_stamp_says_so(cell) -> None:
    """A requested exposure that is not a whole number of steps cannot be
    rendered. Reporting the requested midpoint anyway leaves up to half a
    timestep of error in the timestamp the whole chain hangs off, which is the
    entire 1 ms sensing gate at a 2 ms step."""
    model, data, config = cell
    _settled(model, data, config)
    with Sensors(model, {CAMERA: CameraSpec(CAMERA, 320, 240, exposure_s=0.005)}) as sensors:
        frame = sensors.capture(data, CAMERA)
    offset = frame.stamp_s - data.time
    assert offset == pytest.approx(0.002, abs=1e-12)
    assert (2 * offset) % model.opt.timestep == pytest.approx(0.0, abs=1e-12)


def test_zero_exposure_stamps_the_present_instant(cell) -> None:
    model, data, config = cell
    _settled(model, data, config)
    with Sensors(model, {CAMERA: CameraSpec(CAMERA, 320, 240, exposure_s=0.0)}) as sensors:
        assert sensors.capture(data, CAMERA).stamp_s == pytest.approx(data.time, abs=1e-12)


def test_encoder_is_read_at_the_same_instant_as_the_image(cell) -> None:
    """The seam this catches: an image stamped at the exposure midpoint paired
    with an encoder latched at the exposure start. Half an exposure of skew is
    0.9 mm at 300 mm/s, and it looks like a calibration error until someone
    changes the line speed."""
    model, data, config = cell
    _settled(model, data, config)
    # Four timesteps, so the requested exposure needs no rounding and the
    # arithmetic below is exact rather than approximately right.
    exposure = 4 * 0.002
    with Sensors(model, {CAMERA: CameraSpec(CAMERA, 320, 240, exposure_s=exposure)}) as sensors:
        observation, frame = sensors.observe(data, CAMERA)
    assert frame is not None
    assert observation.stamp_s == pytest.approx(frame.stamp_s, abs=1e-12)
    travel_at_call = float(data.sensordata[0])
    expected = travel_at_call + BELT_SPEED_MPS * exposure / 2
    assert observation.belt_travel_m == pytest.approx(expected, rel=1e-4)
    assert observation.belt_travel_m > travel_at_call


def test_exposure_smears_the_image_and_zero_exposure_does_not(cell) -> None:
    """The smear is the physical effect the midpoint stamp is the answer to."""
    model, data, config = cell
    _settled(model, data, config)
    with Sensors(
        model,
        {
            "sharp": CameraSpec(name=CAMERA, width_px=320, height_px=240, exposure_s=0.0),
            "smeared": CameraSpec(name=CAMERA, width_px=320, height_px=240, exposure_s=0.060),
        },
    ) as sensors:
        sharp = sensors.capture(data, "sharp")
        smeared = sensors.capture(data, "smeared")
    edges = lambda img: float(np.abs(np.diff(img.astype(float).mean(axis=2), axis=1)).mean())  # noqa: E731
    assert edges(smeared.rgb) < edges(sharp.rgb)


def test_observation_carries_no_ground_truth(cell) -> None:
    """The oracle boundary. An estimator handed an Observation cannot cheat."""
    model, data, config = cell
    _settled(model, data, config)
    with Sensors(model, {CAMERA: CameraSpec(CAMERA, 320, 240, exposure_s=0.0)}) as sensors:
        observation, _ = sensors.observe(data, CAMERA)
    fields = set(vars(observation))
    assert not fields & {"piece_pose", "piece_mask", "piece_velocity_mps", "piece_top_z_m"}
    assert fields == {
        "stamp_s",
        "belt_travel_m",
        "belt_speed_mps",
        "joint_pos_rad",
        "gripper_width_m",
        "rgb",
        "depth_m",
    }


def test_ground_truth_reports_the_product_and_flags_a_clipped_mask(cell) -> None:
    model, data, config = cell
    _settled(model, data, config)
    with Sensors(model, {CAMERA: CameraSpec(CAMERA, 320, 240, exposure_s=0.0)}) as sensors:
        truth = sensors.ground_truth(data, CAMERA)
        assert truth.piece_mask is not None
        assert truth.piece_mask.any()
        assert not truth.mask_touches_border
        assert truth.piece_pose.frame is Frame.WORLD
        # 50 um of slack: the product settles into the belt by the contact
        # solver's penetration depth, measured at 8.6 um here. That depth is
        # physical, not numerical noise, and perception sees the settled height.
        assert truth.piece_top_z_m == pytest.approx(0.90 + 2 * config.slab.half_extents_m[2], abs=5e-5)
        assert float(truth.piece_velocity_mps[0]) == pytest.approx(BELT_SPEED_MPS, abs=0.01)

        # The camera sees x from about -0.90 to +0.10, so the product has to go
        # further out than it used to before it runs off the frame. Raising the
        # camera to fit a pork leg widened the field from 741 to 981 mm.
        adr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "slab_free")]
        data.qpos[adr] = -0.94
        mujoco.mj_forward(model, data)
        assert sensors.ground_truth(data, CAMERA).mask_touches_border


def test_unknown_camera_is_refused_at_construction(cell) -> None:
    model, _, _ = cell
    with pytest.raises(ValueError, match="no camera named"):
        Sensors(model, {"nonexistent": CameraSpec("nonexistent")})


def test_resolution_beyond_the_offscreen_buffer_is_refused_with_the_fix(cell) -> None:
    """MuJoCo silently gives a smaller image otherwise, and every metric shifts."""
    model, _, _ = cell
    with pytest.raises(ValueError, match="offwidth"):
        Sensors(model, {CAMERA: CameraSpec(CAMERA, 4096, 4096)})


def test_intrinsics_follow_the_declared_resolution(cell) -> None:
    model, _, _ = cell
    with Sensors(model, {CAMERA: CameraSpec(CAMERA, 640, 480)}) as sensors:
        intr = sensors.intrinsics(CAMERA)
    assert (intr.width_px, intr.height_px) == (640, 480)
    assert intr.fx == pytest.approx(480 / 2 / np.tan(np.radians(52.0) / 2))


def test_negative_exposure_is_refused() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        CameraSpec(CAMERA, exposure_s=-0.001)
