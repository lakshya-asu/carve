"""Grasp pose and alignment axis from a binary mask, and what a box loses instead.

Companion to ``library/topics/perception-technique-selection.md``. Two things live here:

1. ``aabb_of_rotated_rect`` and ``box_centre_offset_mm`` quantify what an axis-aligned
   detection box gives up against the mask it approximates.
2. ``pose_from_mask`` is the classical estimator the note recommends as the default:
   image-moment centroid, PCA principal axis, minimum-area rotated rectangle, and the
   largest inscribed circle for a suction or single-pad contact point.

Coordinates are millimetres in the belt plane; angles are degrees modulo 180 (the long
axis of a piece has no head or tail, so 180 degrees is the natural period).

Run ``python snippets/pose_from_mask.py`` or ``pytest snippets/pose_from_mask.py``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class MaskPose:
    """Pose of one piece read off its mask.

    Attributes:
        centroid_mm: Area centroid from image moments, (x, y).
        axis_deg: Principal axis from PCA of the mask points, in [0, 180).
        rect_centre_mm: Centre of the minimum-area rotated rectangle, (x, y).
        rect_size_mm: (long side, short side) of that rectangle.
        rect_angle_deg: Angle of the rectangle's long side, in [0, 180).
        inscribed_centre_mm: Centre of the largest circle that fits inside the mask.
        inscribed_radius_mm: Radius of that circle.
    """

    centroid_mm: tuple[float, float]
    axis_deg: float
    rect_centre_mm: tuple[float, float]
    rect_size_mm: tuple[float, float]
    rect_angle_deg: float
    inscribed_centre_mm: tuple[float, float]
    inscribed_radius_mm: float


def aabb_of_rotated_rect(length_mm: float, width_mm: float, theta_deg: float) -> tuple[float, float, float]:
    """Axis-aligned box of a rectangle rotated by ``theta_deg``.

    Returns:
        (box width, box height, box area / rectangle area). The area obeys the closed
        form ``L*W + (L^2 + W^2) * sin(2 theta) / 2`` for theta in [0, 90] degrees, so
        the excess is maximal at 45 degrees whatever the aspect ratio.
    """
    c = abs(math.cos(math.radians(theta_deg)))
    s = abs(math.sin(math.radians(theta_deg)))
    box_w = length_mm * c + width_mm * s
    box_h = length_mm * s + width_mm * c
    return box_w, box_h, box_w * box_h / (length_mm * width_mm)


def polygon_area_centroid(poly_mm: np.ndarray) -> tuple[float, np.ndarray]:
    """Area and area centroid of a simple polygon given as (N, 2) vertices."""
    x, y = poly_mm[:, 0], poly_mm[:, 1]
    x_next, y_next = np.roll(x, -1), np.roll(y, -1)
    cross = x * y_next - x_next * y  # (N,) float64
    area2 = cross.sum()
    cx = ((x + x_next) * cross).sum() / (3.0 * area2)
    cy = ((y + y_next) * cross).sum() / (3.0 * area2)
    return abs(area2) / 2.0, np.array([cx, cy])


def rotate(poly_mm: np.ndarray, theta_deg: float) -> np.ndarray:
    """Rotate an (N, 2) polygon about the origin."""
    t = math.radians(theta_deg)
    rot = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])
    return np.asarray(poly_mm @ rot.T, dtype=np.float64)


def box_centre_offset_mm(poly_mm: np.ndarray, theta_deg: float) -> float:
    """Distance from the axis-aligned box centre to the true area centroid, after rotation.

    Zero for any shape with 180-degree rotational symmetry, which is why a rectangle is
    the wrong test case for this failure.
    """
    rotated = rotate(poly_mm, theta_deg)
    _, centroid = polygon_area_centroid(rotated)
    lo = rotated.min(axis=0)
    hi = rotated.max(axis=0)
    return float(np.linalg.norm((lo + hi) / 2.0 - centroid))


def pose_from_mask(mask: np.ndarray, mm_per_px: float = 1.0) -> MaskPose:
    """Estimate centroid, principal axis, rotated rectangle and inscribed circle.

    Args:
        mask: (H, W) uint8, non-zero on the piece, one connected instance.
        mm_per_px: Belt-plane scale. Valid only for a camera looking down a fixed
            distance onto a flat belt; on a thick piece the top surface is closer than
            the belt and this scale is wrong by the parallax term (see the note).

    Returns:
        A ``MaskPose`` in millimetres, origin at the mask's pixel origin.
    """
    moments = cv2.moments(mask, binaryImage=True)
    if moments["m00"] == 0.0:
        raise ValueError("empty mask: no pixels above zero")
    centroid = np.array([moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]])

    pts = np.column_stack(np.nonzero(mask)[::-1]).astype(np.float64)  # (N, 2) x, y
    centred = pts - pts.mean(axis=0)
    _, _, vt = np.linalg.svd(centred, full_matrices=False)
    axis_deg = math.degrees(math.atan2(vt[0, 1], vt[0, 0])) % 180.0

    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    (rx, ry), (rw, rh), rang = cv2.minAreaRect(max(contours, key=cv2.contourArea))
    if rw < rh:
        rw, rh, rang = rh, rw, rang + 90.0

    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)
    iy, ix = np.unravel_index(int(dist.argmax()), dist.shape)

    return MaskPose(
        centroid_mm=(centroid[0] * mm_per_px, centroid[1] * mm_per_px),
        axis_deg=axis_deg,
        rect_centre_mm=(rx * mm_per_px, ry * mm_per_px),
        rect_size_mm=(rw * mm_per_px, rh * mm_per_px),
        rect_angle_deg=rang % 180.0,
        inscribed_centre_mm=(float(ix) * mm_per_px, float(iy) * mm_per_px),
        inscribed_radius_mm=float(dist[iy, ix]) * mm_per_px,
    )


def axis_error_deg(a_deg: float, b_deg: float) -> float:
    """Smallest angle between two undirected axes, in [0, 90]."""
    d = abs(a_deg - b_deg) % 180.0
    return min(d, 180.0 - d)


def _tapered_slab(length_mm: float = 200.0, wide_mm: float = 80.0) -> np.ndarray:
    """A trimmed loin end: trapezoid tapering to a third of its wide end."""
    n = wide_mm / 6.0
    return np.array(
        [[-length_mm / 2, -wide_mm / 2], [length_mm / 2, -n], [length_mm / 2, n], [-length_mm / 2, wide_mm / 2]]
    )


def _crescent(half_angle_rad: float = 1.4, r_outer_mm: float = 130.0, r_inner_mm: float = 90.0) -> np.ndarray:
    """A curved cut (thigh, belly trim) as an annular sector, centred on its area centroid."""
    ang = np.linspace(-half_angle_rad, half_angle_rad, 200)
    outer = np.column_stack([r_outer_mm * np.cos(ang), r_outer_mm * np.sin(ang)])
    inner = np.column_stack([r_inner_mm * np.cos(ang[::-1]), r_inner_mm * np.sin(ang[::-1])])
    poly = np.vstack([outer, inner])
    return np.asarray(poly - polygon_area_centroid(poly)[1], dtype=np.float64)


def _rasterise(poly_mm: np.ndarray, pad_px: int = 40) -> np.ndarray:
    """Fill a polygon into a uint8 mask at 1 px per mm."""
    shifted = poly_mm - poly_mm.min(axis=0) + pad_px
    size = np.ceil(shifted.max(axis=0)).astype(int) + pad_px
    mask = np.zeros((size[1], size[0]), np.uint8)
    cv2.fillPoly(mask, [shifted.astype(np.int32)], 255)
    return mask


def test_aabb_area_matches_closed_form_and_peaks_at_45_degrees() -> None:
    """Box area is L*W + (L^2+W^2) sin(2 theta)/2; at 45 degrees the box is square."""
    length_mm, width_mm = 200.0, 80.0
    for theta in (0.0, 10.0, 30.0, 45.0, 80.0):
        box_w, box_h, _ = aabb_of_rotated_rect(length_mm, width_mm, theta)
        closed = length_mm * width_mm + (length_mm**2 + width_mm**2) * math.sin(math.radians(2 * theta)) / 2
        assert abs(box_w * box_h - closed) < 1e-6
    assert abs(aabb_of_rotated_rect(length_mm, width_mm, 10.0)[2] - 1.50) < 0.01
    box_w, box_h, ratio = aabb_of_rotated_rect(length_mm, width_mm, 45.0)
    assert abs(box_w - box_h) < 1e-9  # square: the box carries no axis at all
    assert abs(ratio - 2.45) < 0.01  # 59 percent of the box is belt


def test_box_centre_offset_is_theta_dependent_and_never_calibrated_out() -> None:
    """A symmetric piece hides the offset; a tapered or curved one does not."""
    rect = np.array([[-100.0, -40.0], [100.0, -40.0], [100.0, 40.0], [-100.0, 40.0]])
    assert box_centre_offset_mm(rect, 37.0) < 1e-9

    slab = _tapered_slab()
    offsets = [box_centre_offset_mm(slab, t) for t in (0.0, 15.0, 30.0, 45.0)]
    assert abs(offsets[0] - 16.7) < 0.1  # h(2b+a)/(3(a+b)) from the wide end
    assert abs(offsets[-1] - 3.3) < 0.1  # shrinks here, so no fixed offset fixes it

    curved = _crescent()
    curved_offsets = [box_centre_offset_mm(curved, t) for t in (0.0, 45.0)]
    assert curved_offsets[1] > 3 * curved_offsets[0]  # grows here instead


def test_mask_centroid_can_fall_off_a_curved_piece_but_the_inscribed_circle_cannot() -> None:
    """The reason a suction point is the inscribed-circle centre, not the centroid."""
    curved = _crescent(half_angle_rad=1.4)
    mask = _rasterise(curved)
    pose = pose_from_mask(mask)
    contour = max(cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea)
    assert cv2.pointPolygonTest(contour, pose.centroid_mm, False) < 0
    assert cv2.pointPolygonTest(contour, pose.inscribed_centre_mm, False) > 0
    assert 18.0 < pose.inscribed_radius_mm < 22.0  # half the 40 mm band width


def test_pca_axis_degrades_as_the_piece_becomes_round() -> None:
    """Elongated pieces give a sub-degree axis; a square piece has no axis to find."""
    rng = np.random.default_rng(0)
    p95 = {}
    for aspect in (2.5, 1.05, 1.0):
        errors = []
        for _ in range(60):
            theta = float(rng.uniform(0.0, 180.0))
            short = 200.0 / aspect
            rect = np.array([[-100.0, -short / 2], [100.0, -short / 2], [100.0, short / 2], [-100.0, short / 2]])
            mask = _rasterise(rotate(rect, theta))
            mask[rng.random(mask.shape) < 0.10] = 0  # specular drop-outs on a wet surface
            errors.append(axis_error_deg(pose_from_mask(mask).axis_deg, theta))
        p95[aspect] = float(np.percentile(errors, 95))
    assert p95[2.5] < 0.5
    assert 1.0 < p95[1.05] < 6.0
    assert p95[1.0] > 45.0  # degenerate: PCA reports an arbitrary axis


def test_a_lost_edge_strip_moves_the_centroid_by_half_its_width_and_not_the_axis() -> None:
    """Under-segmentation along one long edge is the dominant centroid error term."""
    rng = np.random.default_rng(1)
    length_mm, width_mm = 200.0, 80.0
    rect = np.array(
        [
            [-length_mm / 2, -width_mm / 2],
            [length_mm / 2, -width_mm / 2],
            [length_mm / 2, width_mm / 2],
            [-length_mm / 2, width_mm / 2],
        ]
    )
    for lost_fraction in (0.10, 0.30):
        shifts, axis_errors = [], []
        for _ in range(30):
            theta = float(rng.uniform(0.0, 180.0))
            full = _rasterise(rotate(rect, theta))
            truth = pose_from_mask(full)
            strip = rect.copy()
            strip[0, 1] = strip[1, 1] = width_mm / 2 - lost_fraction * width_mm
            damaged = full.copy()
            origin = rotate(rect, theta).min(axis=0)
            cv2.fillPoly(damaged, [(rotate(strip, theta) - origin + 40).astype(np.int32)], 0)
            seen = pose_from_mask(damaged)
            shifts.append(math.dist(seen.centroid_mm, truth.centroid_mm))
            axis_errors.append(axis_error_deg(seen.axis_deg, theta))
        assert abs(float(np.median(shifts)) - lost_fraction * width_mm / 2) < 0.6  # d/2, exactly
        assert max(axis_errors) < 0.5


if __name__ == "__main__":
    test_aabb_area_matches_closed_form_and_peaks_at_45_degrees()
    test_box_centre_offset_is_theta_dependent_and_never_calibrated_out()
    test_mask_centroid_can_fall_off_a_curved_piece_but_the_inscribed_circle_cannot()
    test_pca_axis_degrades_as_the_piece_becomes_round()
    test_a_lost_edge_strip_moves_the_centroid_by_half_its_width_and_not_the_axis()
    print("pose_from_mask: 5 checks passed")
