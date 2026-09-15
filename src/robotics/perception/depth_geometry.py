"""Depth pixels to world points, and the belt plane heights are measured against.

Every depth-based module needs these and none of them needs a segmenter, so they sit apart from
`staged_segmenter.py`: the world ray through each pixel, the RANSAC plane fit, and the threshold
below which a depth value is a missing return.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from robotics.core.camera_frame import CameraFrameData

# Points used to fit the belt plane. Three numbers do not need a million points,
# and back-projecting the whole frame to get them dominated the frame time.
PLANE_FIT_SAMPLES = 8000


# Probability that RANSAC has drawn at least one outlier-free trio before it
# stops. Drives the adaptive iteration count.
RANSAC_CONFIDENCE = 0.9999


# Depth values at or below this are missing returns, not surfaces. Active stereo
# reports zero where it has no correspondence, which is exactly where the
# specular highlights are.
MIN_VALID_DEPTH_M = 1e-4


@dataclass(frozen=True)
class Plane:
    """A fitted plane, with the evidence for it.

    Attributes:
        normal: Unit normal, world frame, pointing up.
        offset_m: Plane is the set of points p with `normal . p + offset_m = 0`.
        inlier_fraction: Share of sampled points within the fit tolerance. This
            is the proposal's confidence: a belt seen clearly gives a very high
            value, and a frame where the belt is mostly occluded or the depth
            has collapsed gives a low one.
        rms_residual_m: Spread of the inliers about the fitted plane.
    """

    normal: np.ndarray
    offset_m: float
    inlier_fraction: float
    rms_residual_m: float

    def height_of(self, points_m: np.ndarray) -> np.ndarray:
        """Signed height of points above the plane, metres."""
        return np.asarray(points_m @ self.normal + self.offset_m, dtype=float)


def fit_plane_ransac(
    points_m: np.ndarray,
    tolerance_m: float,
    rng: np.random.Generator,
    iterations: int = 120,
    sample_cap: int = PLANE_FIT_SAMPLES,
) -> Plane:
    """Fit the dominant plane by RANSAC, then refit by least squares on its inliers.

    The belt is the largest flat surface in view, so the fit is heavily
    over-determined and a plain RANSAC is enough. Refitting on the inliers
    afterwards matters more than the number of iterations: the three points that
    won the vote are themselves noisy, and the least-squares refit removes that.

    Args:
        points_m: (N, 3) world points, already filtered for valid depth.
        tolerance_m: Inlier distance. Set it from the sensor's noise, not by
            taste: too tight and the belt fails to reach consensus, too loose
            and a 30 mm product counts as belt.
        rng: Seeded generator, so a run replays.
        iterations: RANSAC trials.
        sample_cap: Points used for the vote. A million-pixel depth image does
            not need a million points to find a plane.

    Raises:
        ValueError: If there are too few points to fit anything.
    """
    if points_m.shape[0] < 3:
        raise ValueError(f"need at least 3 points to fit a plane, got {points_m.shape[0]}")
    sample = points_m
    if sample.shape[0] > sample_cap:
        sample = points_m[rng.choice(points_m.shape[0], sample_cap, replace=False)]

    best_inliers = np.zeros(sample.shape[0], dtype=bool)
    best_count = 0
    needed = float(iterations)
    for attempt in range(iterations):
        trio = sample[rng.choice(sample.shape[0], 3, replace=False)]
        normal = np.cross(trio[1] - trio[0], trio[2] - trio[0])
        norm = float(np.linalg.norm(normal))
        if norm < 1e-12:  # three collinear points name no plane
            continue
        normal = normal / norm
        offset = -float(normal @ trio[0])
        inliers = np.abs(sample @ normal + offset) < tolerance_m
        count = int(inliers.sum())
        if count > best_count:
            best_inliers, best_count = inliers, count
            # Standard adaptive stopping. With the belt filling most of the
            # frame the inlier ratio is high, three points are needed per
            # sample, and the chance of having drawn a clean trio saturates
            # after a handful of tries. Running a fixed 120 iterations spent
            # 24 ms per frame proving something already certain.
            ratio = best_count / sample.shape[0]
            if ratio > 0.999:
                needed = float(attempt + 1)
            else:
                needed = math.log(1.0 - RANSAC_CONFIDENCE) / math.log(1.0 - ratio**3)
        if attempt + 1 >= needed:
            break

    if best_inliers.sum() < 3:
        raise ValueError("RANSAC found no plane: fewer than 3 points ever agreed")

    inlier_points = sample[best_inliers]
    centroid = inlier_points.mean(axis=0)
    _, _, right = np.linalg.svd(inlier_points - centroid, full_matrices=False)
    normal = right[-1]
    if normal[2] < 0:  # point it up, so height above the belt is positive
        normal = -normal
    offset = -float(normal @ centroid)
    residuals = inlier_points @ normal + offset
    return Plane(
        normal=np.asarray(normal, dtype=float),
        offset_m=offset,
        inlier_fraction=float(best_inliers.mean()),
        rms_residual_m=float(np.sqrt(np.mean(residuals**2))),
    )


_DIRECTION_CACHE: dict[tuple[int, int, float, float, bytes], np.ndarray] = {}


def ray_directions(frame: CameraFrameData) -> np.ndarray:
    """World-frame ray direction per pixel, (H, W, 3), scaled so z along the axis is 1.

    A point is then `camera + depth * direction`, with depth as MuJoCo reports
    it: distance along the optical axis, not range. Cached on the camera's
    intrinsics and pose, because a fixed overhead camera recomputes the same
    million vectors on every frame otherwise.
    """
    intr = frame.intrinsics
    key = (intr.width_px, intr.height_px, intr.fx, intr.cx, frame.camera.rotation.tobytes())
    cached = _DIRECTION_CACHE.get(key)
    if cached is None:
        rows, cols = np.mgrid[0 : intr.height_px, 0 : intr.width_px].astype(np.float32)
        camera_frame = np.stack([(cols - intr.cx) / intr.fx, -(rows - intr.cy) / intr.fy, -np.ones_like(cols)], axis=-1)
        # float32 throughout: the height field is a million values and the
        # extra precision buys nothing against millimetre-scale decisions.
        cached = np.asarray(camera_frame @ frame.camera.rotation.T.astype(np.float32), dtype=np.float32)
        _DIRECTION_CACHE[key] = cached
    return cached
