import math

import pytest

np = pytest.importorskip("numpy")

from isaac_sim.perception_adapter import RenderedColorDepthSegmentationModel
from isaac_sim.yolo_perception import YOLO26SegmentationModel
from meatcell.contracts import ObservationSource, SimTime
from meatcell.perception import PinholeCalibration, VisionModel


def test_rendered_segmentation_is_replaceable_and_uses_rgb_depth() -> None:
    rgb = np.zeros((100, 120, 3), dtype=np.uint8)
    rgb[40:60, 50:80, 0] = 220
    rgb[40:60, 50:80, 1] = 20
    rgb[40:60, 50:80, 2] = 15
    depth = np.full((100, 120), 2.9, dtype=np.float32)
    model = RenderedColorDepthSegmentationModel(seed=7, latency_sigma_s=0.0, timestamp_jitter_sigma_s=0.0, position_noise_sigma_m=0.0, yaw_noise_sigma_rad=0.0)
    assert isinstance(model, VisionModel)
    calibration = PinholeCalibration(1.0, 0.0, 3.0, 100.0, 100.0, 60.0, 50.0, 0.04, 0.0, 0.0)
    observations = model.infer(rgb, depth, SimTime.from_seconds(0.5), calibration)
    assert len(observations) == 1
    observation = observations[0]
    assert observation.source is ObservationSource.SEGMENTATION
    assert observation.instance_mask_rle
    assert observation.delivery_time.seconds == 0.53
    assert observation.pose_belt.translation.x_m > 1.0
    assert observation.visible_fraction > 0.0


def test_noise_and_latency_are_seeded() -> None:
    rgb = np.zeros((80, 80, 3), dtype=np.uint8)
    rgb[20:50, 20:55] = (200, 10, 10)
    depth = np.full((80, 80), 2.9, dtype=np.float32)
    calibration = PinholeCalibration(0.0, 0.0, 3.0, 80.0, 80.0, 40.0, 40.0, 0.04, 0.002, math.radians(0.2))
    first = RenderedColorDepthSegmentationModel(seed=3)
    second = RenderedColorDepthSegmentationModel(seed=3)
    assert first.infer(rgb, depth, SimTime(0), calibration) == second.infer(rgb, depth, SimTime(0), calibration)


@pytest.mark.parametrize(
    ("species", "rendered_color"),
    [
        ("beef", (200, 10, 10)),
        ("pork", (211, 127, 120)),
        ("chicken", (216, 167, 140)),
    ],
)
def test_species_specific_rendered_colors_produce_observations(species, rendered_color) -> None:
    rgb = np.zeros((100, 120, 3), dtype=np.uint8)
    rgb[35:65, 35:85] = rendered_color
    depth = np.full((100, 120), 2.9, dtype=np.float32)
    calibration = PinholeCalibration(1.0, 0.0, 3.0, 100.0, 100.0, 60.0, 50.0, 0.04, 0.0, 0.0)
    model = RenderedColorDepthSegmentationModel(
        seed=11,
        product_species=species,
        latency_sigma_s=0.0,
        timestamp_jitter_sigma_s=0.0,
        position_noise_sigma_m=0.0,
        yaw_noise_sigma_rad=0.0,
    )
    observations = model.infer(rgb, depth, SimTime(0), calibration)
    assert len(observations) == 1
    assert observations[0].geometry_quality == pytest.approx(0.5)
    assert model.model_name == f"rendered_color_depth_segmentation_v3_{species}"


def test_yolo_adapter_converts_learned_mask_and_depth_to_observation(tmp_path, monkeypatch) -> None:
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"test-checkpoint")
    monkeypatch.setattr("isaac_sim.yolo_perception.ultralytics_version", lambda: "test")
    model = YOLO26SegmentationModel(
        weights_path=weights,
        seed=7,
        latency_sigma_s=0.0,
        timestamp_jitter_sigma_s=0.0,
        position_noise_sigma_m=0.0,
        yaw_noise_sigma_rad=0.0,
    )
    mask = np.zeros((100, 120), dtype=bool)
    mask[40:60, 50:80] = True
    monkeypatch.setattr(model, "_predict_masks", lambda image: ((mask, 0.91, "item"),))
    rgb = np.zeros((100, 120, 3), dtype=np.uint8)
    depth = np.full((100, 120), 2.9, dtype=np.float32)
    calibration = PinholeCalibration(1.0, 0.0, 3.0, 100.0, 100.0, 60.0, 50.0, 0.04, 0.0, 0.0)
    observations = model.infer(rgb, depth, SimTime.from_seconds(0.5), calibration)
    assert len(observations) == 1
    assert observations[0].confidence == pytest.approx(0.91)
    assert observations[0].class_name == "meat_reference"
    assert observations[0].instance_mask_rle
    assert observations[0].detection_id.startswith("yolo26-")


def test_yolo_adapter_converts_visible_surface_depth_to_object_center(tmp_path, monkeypatch) -> None:
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"test-checkpoint")
    monkeypatch.setattr("isaac_sim.yolo_perception.ultralytics_version", lambda: "test")
    model = YOLO26SegmentationModel(
        weights_path=weights,
        seed=7,
        latency_sigma_s=0.0,
        timestamp_jitter_sigma_s=0.0,
        position_noise_sigma_m=0.0,
        yaw_noise_sigma_rad=0.0,
        surface_to_center_offset_m=0.04,
    )
    mask = np.zeros((100, 120), dtype=bool)
    mask[40:60, 50:80] = True
    monkeypatch.setattr(model, "_predict_masks", lambda image: ((mask, 0.91, "item"),))
    rgb = np.zeros((100, 120, 3), dtype=np.uint8)
    depth = np.full((100, 120), 2.05, dtype=np.float32)
    calibration = PinholeCalibration(1.0, 0.0, 3.0, 100.0, 100.0, 60.0, 50.0, 0.84, 0.0, 0.0)

    observation = model.infer(rgb, depth, SimTime(0), calibration)[0]

    assert observation.pose_belt.translation.z_m == pytest.approx(0.91)
