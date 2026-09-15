"""Where a leg's centre of gravity is, seen from the overhead depth camera.

The turn about the centre of gravity, and the grip that has to hold against the leg's weight, both
need this point, and the outline's middle is not it: a leg's area runs down a slender hock and
trotter that carry little of its mass (see `applications/pork_leg_alignment/sim/product.py`). The camera sees only the top surface, so
the geometric estimate treats every leg pixel as a solid column from the belt up to that surface
and takes the volume-weighted centre of the columns. What it cannot see is the underside: under the
rounded sides, and under the trotter where it lifts clear of the belt, the columns are partly air.
That is the part a learned correction would have to supply.

Both estimators take a mask from either leg segmenter and the belt plane from the empty-belt
reference, and return the same result type, so they swap and compare in one line.
Pre-registered in `experiments/2026-09-15-centre-of-gravity.md`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from robotics.core.camera_frame import CameraFrameData
from robotics.perception.depth_geometry import MIN_VALID_DEPTH_M, Plane, ray_directions


@dataclass(frozen=True)
class CentreOfGravityEstimate:
    """One estimate of where a leg's mass is centred.

    Attributes:
        position_m: (3,) world frame. The silhouette method's point lies on the belt plane.
        volume_m3: Volume under the seen surface, down to the belt; 0 for the silhouette method.
        pixels: Leg pixels with valid depth that went into the estimate.
        elapsed_ms: Time taken, not counting segmentation.
    """

    position_m: np.ndarray
    volume_m3: float
    pixels: int
    elapsed_ms: float


def _columns(frame: CameraFrameData, mask: np.ndarray, plane: Plane) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Surface point (N, 3), height above the belt (N,) and footprint on the belt (N,) per usable leg pixel."""
    if mask.shape != frame.depth_m.shape:
        raise ValueError(f"mask {mask.shape} does not match the depth image {frame.depth_m.shape}")
    directions = ray_directions(frame)[mask].astype(np.float64)
    depth_m = frame.depth_m[mask].astype(np.float64)
    usable = depth_m > MIN_VALID_DEPTH_M
    if not usable.any():
        raise ValueError("no pixel in the mask has valid depth")
    directions, depth_m = directions[usable], depth_m[usable]
    points = frame.camera.position_m + directions * depth_m[:, None]
    height_m = np.clip(plane.height_of(points), 0.0, None)
    # Across the optical axis a pixel covers depth^2 / (fx fy) square metres. Laid onto the belt
    # plane that becomes depth^2 / (fx fy |d . n|), with d scaled to unit length along the axis.
    # Leaving it out weights the near side of a tilted view by its denser pixels.
    intrinsics = frame.intrinsics
    footprint_m2 = depth_m**2 / (intrinsics.fx * intrinsics.fy * np.abs(directions @ plane.normal))
    return points, height_m, footprint_m2


def silhouette_centroid(frame: CameraFrameData, mask: np.ndarray, plane: Plane) -> CentreOfGravityEstimate:
    """Centre of the leg's outline on the belt: every leg pixel dropped onto the belt, weighted by its footprint.

    The baseline, and what the earlier slab estimator amounted to. Pixels without depth are left out.

    Raises:
        ValueError: If the mask does not match the image or no pixel in it has depth.
    """
    started = time.perf_counter()
    points, height_m, footprint_m2 = _columns(frame, mask, plane)
    feet = points - height_m[:, None] * plane.normal
    position = (footprint_m2[:, None] * feet).sum(axis=0) / footprint_m2.sum()
    return CentreOfGravityEstimate(position, 0.0, int(height_m.size), 1000.0 * (time.perf_counter() - started))


def column_centroid(frame: CameraFrameData, mask: np.ndarray, plane: Plane) -> CentreOfGravityEstimate:
    """Volume-weighted centre of solid columns from the belt up to the seen surface.

    Pixels without depth are left out, so a patch of lost depth takes its volume with it.

    Raises:
        ValueError: If the mask does not match the image, no pixel in it has depth, or nothing in
            it stands above the belt.
    """
    started = time.perf_counter()
    points, height_m, footprint_m2 = _columns(frame, mask, plane)
    volume_m3 = footprint_m2 * height_m
    total_m3 = float(volume_m3.sum())
    if total_m3 <= 0.0:
        raise ValueError("nothing in the mask stands above the belt")
    centres = points - 0.5 * height_m[:, None] * plane.normal
    position = (volume_m3[:, None] * centres).sum(axis=0) / total_m3
    return CentreOfGravityEstimate(position, total_m3, int(height_m.size), 1000.0 * (time.perf_counter() - started))
