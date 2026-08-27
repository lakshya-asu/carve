"""YOLO26 instance segmentation adapter for rendered Isaac RGB and depth."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import random
import time
from typing import Any

from meatcell.contracts import BoundingBox, ObjectObservation, ObservationSource, SimTime, Transform, Vector3
from meatcell.perception import PinholeCalibration

from .yolo_runtime import load_yolo_class, ultralytics_version


_MODEL_CACHE: dict[str, Any] = {}


class YOLO26SegmentationModel:
    """Turn YOLO26 masks plus rendered depth into stamped planar observations.

    The configured checkpoint must contain a ``meat_reference`` segmentation
    class. Official COCO weights are only the pretrained starting point. They
    are not treated as a meat detector.
    """

    def __init__(
        self,
        *,
        weights_path: str | Path,
        seed: int,
        confidence_threshold: float = 0.20,
        latency_mean_s: float = 0.030,
        latency_sigma_s: float = 0.006,
        timestamp_jitter_sigma_s: float = 0.001,
        position_noise_sigma_m: float = 0.003,
        yaw_noise_sigma_rad: float = math.radians(0.8),
        minimum_component_pixels: int = 40,
        device: str = "cpu",
        refine_color_mask: bool = False,
        refinement_species: str = "pork",
        surface_to_center_offset_m: float = 0.0,
    ) -> None:
        path = Path(weights_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"YOLO checkpoint was not found: {path}")
        if not 0.0 < confidence_threshold <= 1.0:
            raise ValueError("YOLO confidence threshold must be in (0, 1]")
        if latency_mean_s < 0.0 or latency_sigma_s < 0.0 or timestamp_jitter_sigma_s < 0.0:
            raise ValueError("Perception latency and jitter values must be nonnegative")
        if (
            position_noise_sigma_m < 0.0
            or yaw_noise_sigma_rad < 0.0
            or minimum_component_pixels <= 0
            or surface_to_center_offset_m < 0.0
        ):
            raise ValueError("Perception noise must be nonnegative and component size positive")
        self.weights_path = path
        self.weights_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        self.package_version = ultralytics_version()
        self.model_name = f"ultralytics_yolo26_seg_meat_reference_v1@{self.weights_sha256[:12]}"
        self.confidence_threshold = confidence_threshold
        self.latency_mean_s = latency_mean_s
        self.latency_sigma_s = latency_sigma_s
        self.timestamp_jitter_sigma_s = timestamp_jitter_sigma_s
        self.position_noise_sigma_m = position_noise_sigma_m
        self.yaw_noise_sigma_rad = yaw_noise_sigma_rad
        self.minimum_component_pixels = minimum_component_pixels
        self.surface_to_center_offset_m = surface_to_center_offset_m
        self.device = device
        if refinement_species not in {"beef", "pork", "chicken"}:
            raise ValueError("Refinement species must be beef, pork, or chicken")
        self.refine_color_mask = refine_color_mask
        self.refinement_species = refinement_species
        if refine_color_mask:
            self.model_name = (
                f"ultralytics_yolo26_seg_plus_{refinement_species}_color_refinement_v1@"
                f"{self.weights_sha256[:12]}"
            )
        self._rng = random.Random(seed)
        self._frame_index = 0
        self.last_wall_inference_s: float | None = None

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

    def _model(self) -> Any:
        key = str(self.weights_path)
        if key not in _MODEL_CACHE:
            yolo = load_yolo_class()
            _MODEL_CACHE[key] = yolo(key, task="segment")
        return _MODEL_CACHE[key]

    def _predict_masks(self, image: Any) -> tuple[tuple[Any, float, str], ...]:
        import numpy as np
        from PIL import Image

        rgb8 = np.asarray(image)
        if rgb8.dtype != np.uint8:
            rgb8 = np.clip(rgb8 * (255.0 if rgb8.max(initial=0.0) <= 1.0 else 1.0), 0, 255).astype(np.uint8)
        started = time.perf_counter()
        result = self._model().predict(
            source=Image.fromarray(rgb8[..., :3]),
            imgsz=640,
            conf=self.confidence_threshold,
            device=self.device,
            verbose=False,
        )[0]
        self.last_wall_inference_s = time.perf_counter() - started
        if result.masks is None or result.boxes is None:
            return ()
        masks = result.masks.data.detach().cpu().numpy()
        confidences = result.boxes.conf.detach().cpu().numpy()
        classes = result.boxes.cls.detach().cpu().numpy().astype(int)
        height, width = rgb8.shape[:2]
        predictions = []
        for mask, confidence, class_index in zip(masks, confidences, classes, strict=True):
            if mask.shape != (height, width):
                import cv2

                mask = cv2.resize(mask.astype(np.float32), (width, height), interpolation=cv2.INTER_LINEAR)
            class_name = str(result.names[int(class_index)])
            predictions.append((mask >= 0.5, float(confidence), class_name))
        return tuple(predictions)

    def infer(
        self,
        rgb: Any,
        depth_m: Any,
        exposure_time: SimTime,
        calibration: PinholeCalibration,
    ) -> tuple[ObjectObservation, ...]:
        import numpy as np

        image = np.asarray(rgb)
        depth = np.asarray(depth_m, dtype=np.float32)
        if image.ndim != 3 or image.shape[2] < 3 or depth.shape != image.shape[:2]:
            raise ValueError("Vision input requires HxWx3 RGB and matching HxW depth")
        self._frame_index += 1
        latency_s = max(0.0, self._rng.gauss(self.latency_mean_s, self.latency_sigma_s))
        jitter_s = self._rng.gauss(0.0, self.timestamp_jitter_sigma_s)
        jittered_exposure = SimTime.from_seconds(max(0.0, exposure_time.seconds + jitter_s))
        delivery = jittered_exposure.plus_seconds(latency_s)
        observations = []
        for detection_index, (component, confidence, class_name) in enumerate(self._predict_masks(image), start=1):
            # Ultralytics YOLO26 currently serializes a single-class model as
            # ``item`` even when the dataset YAML names it ``meat_reference``.
            # Both labels refer to class index zero in this dedicated checkpoint.
            if class_name not in {"meat_reference", "item"}:
                continue
            if self.refine_color_mask:
                colors = image[..., :3].astype(np.float32)
                if colors.max(initial=0.0) > 1.5:
                    colors /= 255.0
                red, green, blue = colors[..., 0], colors[..., 1], colors[..., 2]
                if self.refinement_species == "chicken":
                    color_mask = (
                        (red > 0.50)
                        & (green > red * 0.45)
                        & (green < red * 0.90)
                        & (blue > red * 0.35)
                        & (blue < red * 0.85)
                    )
                elif self.refinement_species == "pork":
                    color_mask = (
                        (red > 0.45)
                        & (red > green * 1.45)
                        & (red > blue * 1.35)
                        & (green < 0.55)
                        & (blue < 0.60)
                    )
                else:
                    color_mask = (red > 0.28) & (red > green * 1.45) & (red > blue * 1.45) & (green < 0.38)
                from scipy import ndimage

                labels, label_count = ndimage.label(color_mask)
                proposal = np.asarray(component, dtype=bool)
                overlapping_labels, overlap_counts = np.unique(
                    labels[proposal & (labels > 0)],
                    return_counts=True,
                )
                if overlapping_labels.size:
                    # Keep exactly one connected component. A broad proposal can
                    # touch red machine geometry as well as the product. Unioning
                    # every touched component biases the centroid toward that
                    # stationary geometry even while the product is moving.
                    selected_label = int(overlapping_labels[int(np.argmax(overlap_counts))])
                    refined = labels == selected_label
                    if int(np.count_nonzero(refined)) >= self.minimum_component_pixels:
                        component = refined
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
            # A depth camera observes the visible top surface. Downstream robot
            # planning consumes an object-center pose, so a recipe-specific
            # surface-to-center offset is applied explicitly instead of hiding
            # the correction in a task script.
            z_world = calibration.camera_z_world_m - distance - self.surface_to_center_offset_m
            centered = np.column_stack((columns - u, -(rows - v)))
            covariance = centered.T @ centered / max(1, centered.shape[0] - 1)
            eigenvalues, eigenvectors = np.linalg.eigh(covariance)
            major = eigenvectors[:, int(np.argmax(eigenvalues))]
            yaw = math.atan2(float(major[1]), float(major[0]))
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
                    detection_id=f"yolo26-{self._frame_index:06d}-{detection_index:03d}",
                    exposure_time=jittered_exposure,
                    delivery_time=delivery,
                    class_name="meat_reference",
                    confidence=confidence,
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
