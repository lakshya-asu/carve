"""Orientation-aware grasp selection from an instance mask and metric depth.

This is a deterministic geometric classifier. It is not a learned grasp
network. The interface is intentionally replaceable by a learned model after
real product data is available.
"""

from __future__ import annotations

from dataclasses import replace
import math
from typing import Any

from .contracts import GraspClass, ObjectObservation, Transform, Vector3, VisionGraspProposal
from .perception import PinholeCalibration


CLASSIFIER_NAME = "mask_pca_clearance_v2"


def classify_grasp_yaw(yaw_rad: float) -> GraspClass:
    """Classify the undirected product major-axis angle for tool selection."""
    yaw = math.atan2(math.sin(yaw_rad), math.cos(yaw_rad))
    if yaw > math.pi / 2.0:
        yaw -= math.pi
    elif yaw < -math.pi / 2.0:
        yaw += math.pi
    degrees = math.degrees(yaw)
    if abs(degrees) <= 15.0:
        return GraspClass.LONGITUDINAL
    if abs(degrees) >= 60.0:
        return GraspClass.TRANSVERSE
    return GraspClass.DIAGONAL_LEFT if degrees > 0.0 else GraspClass.DIAGONAL_RIGHT


def _robust_extent(values: Any) -> tuple[float, float]:
    import numpy as np

    return float(np.percentile(values, 2.0)), float(np.percentile(values, 98.0))


def select_mask_grasp(
    *,
    mask: Any,
    depth_m: Any,
    observation: ObjectObservation,
    track_id: str,
    calibration: PinholeCalibration,
    surface_to_center_offset_m: float,
) -> VisionGraspProposal:
    """Return an interior, orientation-aware grasp that is safe to visualize.

    The point is selected near the center of the mask while maximizing robust
    clearance in the product major and minor axes. Metric depth converts the
    selected pixel into the same belt frame consumed by interception planning.
    """
    import numpy as np

    mask_array = np.asarray(mask, dtype=bool)
    depth = np.asarray(depth_m, dtype=float)
    if mask_array.ndim != 2 or depth.shape != mask_array.shape:
        raise ValueError("Grasp selection requires a 2D mask and matching depth")
    rows, columns = np.nonzero(mask_array)
    if rows.size < 30:
        raise ValueError("Grasp selection requires at least 30 mask pixels")

    valid_depth = depth[mask_array]
    valid_depth = valid_depth[np.isfinite(valid_depth) & (valid_depth > 0.0)]
    if valid_depth.size < 10:
        raise ValueError("Grasp selection requires valid metric depth")
    distance_m = float(np.median(valid_depth))

    points = np.column_stack((columns.astype(float), -rows.astype(float)))
    center = np.median(points, axis=0)
    centered = points - center
    covariance = centered.T @ centered / max(1, centered.shape[0] - 1)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    major = eigenvectors[:, int(np.argmax(eigenvalues))]
    if major[0] < 0.0:
        major = -major
    minor = np.asarray((-major[1], major[0]), dtype=float)
    major_projection = centered @ major
    minor_projection = centered @ minor
    major_min, major_max = _robust_extent(major_projection)
    minor_min, minor_max = _robust_extent(minor_projection)

    central = (
        (major_projection >= major_min + 0.25 * (major_max - major_min))
        & (major_projection <= major_max - 0.25 * (major_max - major_min))
        & (minor_projection >= minor_min)
        & (minor_projection <= minor_max)
    )
    candidate_indices = np.flatnonzero(central)
    if candidate_indices.size == 0:
        candidate_indices = np.arange(points.shape[0])
    major_values = major_projection[candidate_indices]
    minor_values = minor_projection[candidate_indices]
    clearance_px = np.minimum.reduce(
        (
            major_values - major_min,
            major_max - major_values,
            minor_values - minor_min,
            minor_max - minor_values,
        )
    )
    # A pure clearance maximum can choose the first pixel on a broad plateau.
    # That created a long lever arm on uniform products. Keep candidates near
    # the best clearance, then choose the one closest to the robust mask center.
    maximum_clearance_px = float(np.max(clearance_px))
    safe_indices = candidate_indices[clearance_px >= 0.9 * maximum_clearance_px]
    safe_major = major_projection[safe_indices] / max(1.0, 0.5 * (major_max - major_min))
    safe_minor = minor_projection[safe_indices] / max(1.0, 0.5 * (minor_max - minor_min))
    normalized_center_distance = np.hypot(safe_major, safe_minor)
    selected_index = int(safe_indices[int(np.argmin(normalized_center_distance))])
    selected_u = float(columns[selected_index])
    selected_v = float(rows[selected_index])

    local_row_min = max(0, int(selected_v) - 3)
    local_row_max = min(depth.shape[0], int(selected_v) + 4)
    local_col_min = max(0, int(selected_u) - 3)
    local_col_max = min(depth.shape[1], int(selected_u) + 4)
    local = depth[local_row_min:local_row_max, local_col_min:local_col_max]
    local = local[np.isfinite(local) & (local > 0.0)]
    selected_distance_m = float(np.median(local)) if local.size else distance_m

    x_world = calibration.camera_x_world_m + (selected_u - calibration.cx_px) / calibration.fx_px * selected_distance_m
    y_world = calibration.camera_y_world_m - (selected_v - calibration.cy_px) / calibration.fy_px * selected_distance_m
    z_world = max(
        calibration.belt_surface_z_world_m,
        calibration.camera_z_world_m - selected_distance_m - surface_to_center_offset_m,
    )
    yaw = observation.pose_belt.yaw_rad
    delta_x = x_world - observation.pose_belt.translation.x_m
    delta_y = y_world - observation.pose_belt.translation.y_m
    cosine = math.cos(yaw)
    sine = math.sin(yaw)
    local_x = cosine * delta_x + sine * delta_y
    local_y = -sine * delta_x + cosine * delta_y

    meters_per_pixel = selected_distance_m / max(1.0, 0.5 * (calibration.fx_px + calibration.fy_px))
    major_span_px = max(1.0, major_max - major_min)
    minor_span_px = max(1.0, minor_max - minor_min)
    estimated_width_m = minor_span_px * meters_per_pixel
    selected_clearance_px = float(
        np.minimum.reduce(
            (
                major_projection[selected_index] - major_min,
                major_max - major_projection[selected_index],
                minor_projection[selected_index] - minor_min,
                minor_max - minor_projection[selected_index],
            )
        )
    )
    boundary_clearance_m = max(0.001, selected_clearance_px * meters_per_pixel)
    anisotropy = max(0.0, min(1.0, 1.0 - minor_span_px / major_span_px))
    interior_score = max(0.0, min(1.0, boundary_clearance_m / max(estimated_width_m * 0.45, 1e-6)))
    classifier_confidence = max(0.0, min(1.0, 0.55 * observation.geometry_quality + 0.45 * anisotropy))
    quality = max(0.0, min(1.0, observation.confidence * (0.65 + 0.35 * interior_score)))

    return VisionGraspProposal(
        proposal_id=f"{track_id}-mask-grasp",
        track_id=track_id,
        classifier_name=CLASSIFIER_NAME,
        grasp_class=classify_grasp_yaw(yaw),
        grasp_point_u_px=selected_u,
        grasp_point_v_px=selected_v,
        grasp_pose_belt=Transform.planar(x_world, y_world, z_world, yaw),
        grasp_in_product=Transform.planar(local_x, local_y, 0.07, 0.0),
        jaw_yaw_rad=yaw,
        approach_vector_belt=Vector3(0.0, 0.0, -1.0),
        estimated_width_m=max(0.04, min(0.18, estimated_width_m)),
        boundary_clearance_m=max(0.012, boundary_clearance_m),
        capture_margin_m=max(0.018, min(0.045, 0.45 * estimated_width_m)),
        quality=quality,
        confidence=classifier_confidence,
    )


def generate_mask_grasp_candidates(
    *,
    mask: Any,
    depth_m: Any,
    observation: ObjectObservation,
    track_id: str,
    calibration: PinholeCalibration,
    surface_to_center_offset_m: float,
    candidate_count: int = 5,
) -> tuple[VisionGraspProposal, ...]:
    """Generate several mask-interior proposals around the geometric baseline.

    All returned points satisfy the same mask and metric-clearance boundary as
    the deterministic proposal. The learned scorer may rank them but may not
    introduce a point outside this set.
    """
    import numpy as np

    if candidate_count < 3 or candidate_count % 2 == 0:
        raise ValueError("Candidate count must be an odd integer of at least three")
    baseline = select_mask_grasp(
        mask=mask,
        depth_m=depth_m,
        observation=observation,
        track_id=track_id,
        calibration=calibration,
        surface_to_center_offset_m=surface_to_center_offset_m,
    )
    mask_array = np.asarray(mask, dtype=bool)
    depth = np.asarray(depth_m, dtype=float)
    rows, columns = np.nonzero(mask_array)
    valid = np.isfinite(depth[rows, columns]) & (depth[rows, columns] > 0.0)
    rows = rows[valid]
    columns = columns[valid]
    if rows.size < 30:
        raise ValueError("Grasp candidate generation requires valid mask depth")

    points = np.column_stack((columns.astype(float), rows.astype(float)))
    center = np.asarray((baseline.grasp_point_u_px, baseline.grasp_point_v_px), dtype=float)
    major = np.asarray((math.cos(observation.pose_belt.yaw_rad), -math.sin(observation.pose_belt.yaw_rad)))
    minor = np.asarray((-major[1], major[0]))
    centered = points - center
    major_projection = centered @ major
    minor_projection = centered @ minor
    major_min, major_max = _robust_extent(major_projection)
    minor_min, minor_max = _robust_extent(minor_projection)
    distance_m = float(np.median(depth[rows, columns]))
    meters_per_pixel = distance_m / max(1.0, 0.5 * (calibration.fx_px + calibration.fy_px))
    required_clearance_px = max(1.0, 0.012 / meters_per_pixel)
    clear = (
        (major_projection - major_min >= required_clearance_px)
        & (major_max - major_projection >= required_clearance_px)
        & (minor_projection - minor_min >= required_clearance_px)
        & (minor_max - minor_projection >= required_clearance_px)
    )
    safe_indices = np.flatnonzero(clear)
    if safe_indices.size < candidate_count:
        raise ValueError("Mask does not contain enough geometry-safe grasp candidates")

    half = candidate_count // 2
    fractions = [0.0]
    for index in range(1, half + 1):
        value = 0.42 * index / half
        fractions.extend((-value, value))
    usable_span = min(abs(major_min), abs(major_max))
    proposals: list[VisionGraspProposal] = []
    used_pixels: set[tuple[int, int]] = set()
    for rank, fraction in enumerate(fractions):
        target_major = fraction * usable_span
        normalized_major = (major_projection[safe_indices] - target_major) / max(1.0, usable_span)
        normalized_minor = minor_projection[safe_indices] / max(1.0, 0.5 * (minor_max - minor_min))
        distance_to_target = np.hypot(normalized_major, normalized_minor)
        selected_index = int(safe_indices[int(np.argmin(distance_to_target))])
        selected_u = float(columns[selected_index])
        selected_v = float(rows[selected_index])
        pixel_key = (int(selected_u), int(selected_v))
        if pixel_key in used_pixels:
            continue
        used_pixels.add(pixel_key)
        local_row_min = max(0, int(selected_v) - 3)
        local_row_max = min(depth.shape[0], int(selected_v) + 4)
        local_col_min = max(0, int(selected_u) - 3)
        local_col_max = min(depth.shape[1], int(selected_u) + 4)
        local_depth = depth[local_row_min:local_row_max, local_col_min:local_col_max]
        local_depth = local_depth[np.isfinite(local_depth) & (local_depth > 0.0)]
        selected_distance_m = float(np.median(local_depth)) if local_depth.size else distance_m
        x_world = calibration.camera_x_world_m + (selected_u - calibration.cx_px) / calibration.fx_px * selected_distance_m
        y_world = calibration.camera_y_world_m - (selected_v - calibration.cy_px) / calibration.fy_px * selected_distance_m
        z_world = max(
            calibration.belt_surface_z_world_m,
            calibration.camera_z_world_m - selected_distance_m - surface_to_center_offset_m,
        )
        yaw = observation.pose_belt.yaw_rad
        delta_x = x_world - observation.pose_belt.translation.x_m
        delta_y = y_world - observation.pose_belt.translation.y_m
        cosine = math.cos(yaw)
        sine = math.sin(yaw)
        local_x = cosine * delta_x + sine * delta_y
        local_y = -sine * delta_x + cosine * delta_y
        clearance_px = min(
            major_projection[selected_index] - major_min,
            major_max - major_projection[selected_index],
            minor_projection[selected_index] - minor_min,
            minor_max - minor_projection[selected_index],
        )
        boundary_clearance_m = max(0.012, float(clearance_px) * meters_per_pixel)
        center_penalty = min(1.0, abs(fraction))
        quality = max(0.0, min(1.0, baseline.quality * (1.0 - 0.15 * center_penalty)))
        proposals.append(
            replace(
                baseline,
                proposal_id=f"{track_id}-mask-candidate-{rank}",
                grasp_point_u_px=selected_u,
                grasp_point_v_px=selected_v,
                grasp_pose_belt=Transform.planar(x_world, y_world, z_world, yaw),
                grasp_in_product=Transform.planar(local_x, local_y, 0.07, 0.0),
                boundary_clearance_m=boundary_clearance_m,
                quality=quality,
            )
        )
    if len(proposals) < 3:
        raise ValueError("Mask candidate generation produced fewer than three unique safe points")
    return tuple(proposals)
