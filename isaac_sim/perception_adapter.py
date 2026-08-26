"""Color and depth segmentation baseline for actual rendered Isaac frames.

This is deterministic image processing behind a replaceable `VisionModel`
interface. It is not a learned model and does not use simulator ground truth.
"""

from __future__ import annotations

import math
import random
from typing import Any

from meatcell.contracts import (
    BoundingBox,
    ObjectObservation,
    ObservationSource,
    SimTime,
    Transform,
    Vector3,
)
from meatcell.perception import PinholeCalibration


class RenderedColorDepthSegmentationModel:
    def __init__(
        self,
        *,
        seed: int,
        product_species: str = "beef",
        latency_mean_s: float = 0.030,
        latency_sigma_s: float = 0.006,
        timestamp_jitter_sigma_s: float = 0.001,
        position_noise_sigma_m: float = 0.003,
        yaw_noise_sigma_rad: float = math.radians(0.8),
        minimum_component_pixels: int = 80,
    ) -> None:
        if latency_mean_s < 0.0 or latency_sigma_s < 0.0 or timestamp_jitter_sigma_s < 0.0:
            raise ValueError("Perception latency and jitter values must be nonnegative")
        if position_noise_sigma_m < 0.0 or yaw_noise_sigma_rad < 0.0 or minimum_component_pixels <= 0:
            raise ValueError("Perception noise must be nonnegative and component size positive")
        if product_species not in {"beef", "pork", "chicken"}:
            raise ValueError("Product species must be beef, pork, or chicken")
        self._rng = random.Random(seed)
        self.product_species = product_species
        self.model_name = f"rendered_color_depth_segmentation_v3_{product_species}"
        self.latency_mean_s = latency_mean_s
        self.latency_sigma_s = latency_sigma_s
        self.timestamp_jitter_sigma_s = timestamp_jitter_sigma_s
        self.position_noise_sigma_m = position_noise_sigma_m
        self.yaw_noise_sigma_rad = yaw_noise_sigma_rad
        self.minimum_component_pixels = minimum_component_pixels
        self._frame_index = 0

    @staticmethod
    def _mask_rle(mask: Any) -> str:
        import numpy as np

        flattened = np.asarray(mask, dtype=np.uint8).ravel()
        if flattened.size == 0:
            return ""
        changes = np.flatnonzero(np.diff(flattened)) + 1
        boundaries = np.concatenate(([0], changes, [flattened.size]))
        return ";".join(
            f"{int(flattened[start])}:{int(end - start)}"
            for start, end in zip(boundaries[:-1], boundaries[1:], strict=True)
        )

    def infer(
        self,
        rgb: Any,
        depth_m: Any,
        exposure_time: SimTime,
        calibration: PinholeCalibration,
    ) -> tuple[ObjectObservation, ...]:
        import numpy as np
        from scipy import ndimage

        image = np.asarray(rgb)
        depth = np.asarray(depth_m, dtype=np.float32)
        if image.ndim != 3 or image.shape[2] < 3 or depth.shape != image.shape[:2]:
            raise ValueError("Vision input requires HxWx3 RGB and matching HxW depth")
        colors = image[..., :3].astype(np.float32)
        if colors.max(initial=0.0) > 1.5:
            colors /= 255.0
        red = colors[..., 0]
        green = colors[..., 1]
        blue = colors[..., 2]
        if self.product_species == "chicken":
            mask = (
                (red > 0.50)
                & (green > red * 0.45)
                & (green < red * 0.90)
                & (blue > red * 0.35)
                & (blue < red * 0.85)
            )
        elif self.product_species == "pork":
            mask = (
                (red > 0.55)
                & (green > red * 0.45)
                & (green < red * 0.75)
                & (blue > red * 0.40)
                & (blue < red * 0.72)
            )
        else:
            mask = (red > 0.28) & (red > green * 1.45) & (red > blue * 1.45) & (green < 0.38)
        labels, count = ndimage.label(mask)
        observations = []
        self._frame_index += 1
        latency_s = max(0.0, self._rng.gauss(self.latency_mean_s, self.latency_sigma_s))
        jitter_s = self._rng.gauss(0.0, self.timestamp_jitter_sigma_s)
        jittered_exposure = SimTime.from_seconds(max(0.0, exposure_time.seconds + jitter_s))
        delivery = jittered_exposure.plus_seconds(latency_s)
        for label_id in range(1, count + 1):
            component = labels == label_id
            rows, columns = np.nonzero(component)
            if rows.size < self.minimum_component_pixels:
                continue
            valid_depth = depth[component]
            valid_depth = valid_depth[np.isfinite(valid_depth) & (valid_depth > 0.0)]
            if valid_depth.size < max(10, rows.size // 10):
                continue
            distance = float(np.median(valid_depth))
            u = float(columns.mean())
            v = float(rows.mean())
            x_world = calibration.camera_x_world_m + (u - calibration.cx_px) / calibration.fx_px * distance
            y_world = calibration.camera_y_world_m - (v - calibration.cy_px) / calibration.fy_px * distance
            z_world = calibration.camera_z_world_m - distance
            centered = np.column_stack((columns - u, -(rows - v)))
            covariance = centered.T @ centered / max(1, centered.shape[0] - 1)
            eigenvalues, eigenvectors = np.linalg.eigh(covariance)
            major = eigenvectors[:, int(np.argmax(eigenvalues))]
            yaw = math.atan2(float(major[1]), float(major[0]))
            # The reference workpiece is 180 degree symmetric in the image.
            # Keep the observable planar axis in a canonical half turn.
            yaw = (yaw + math.pi / 2.0) % math.pi - math.pi / 2.0
            x_world += self._rng.gauss(0.0, self.position_noise_sigma_m)
            y_world += self._rng.gauss(0.0, self.position_noise_sigma_m)
            yaw += self._rng.gauss(0.0, self.yaw_noise_sigma_rad)
            quality = min(1.0, rows.size / 3_000.0)
            depth_spread = float(np.std(valid_depth))
            position_variance = (
                self.position_noise_sigma_m**2
                + calibration.calibration_position_sigma_m**2
                + min(0.01, depth_spread) ** 2
            )
            observations.append(
                ObjectObservation(
                    detection_id=f"vision-{self._frame_index:06d}-{label_id:03d}",
                    exposure_time=jittered_exposure,
                    delivery_time=delivery,
                    class_name="meat_reference",
                    confidence=max(0.05, quality),
                    bbox=BoundingBox(float(columns.min()), float(rows.min()), float(columns.max() + 1), float(rows.max() + 1)),
                    instance_mask_rle=self._mask_rle(component),
                    pose_belt=Transform.planar(x_world, y_world, max(calibration.belt_surface_z_world_m, z_world), yaw),
                    position_variance_m2=Vector3(position_variance, position_variance, position_variance),
                    yaw_variance_rad2=self.yaw_noise_sigma_rad**2 + calibration.calibration_yaw_sigma_rad**2,
                    visible_fraction=min(1.0, rows.size / 2_000.0),
                    geometry_quality=quality,
                    source=ObservationSource.SEGMENTATION,
                )
            )
        observations.sort(key=lambda item: (item.pose_belt.translation.x_m, item.pose_belt.translation.y_m))
        return tuple(observations)
