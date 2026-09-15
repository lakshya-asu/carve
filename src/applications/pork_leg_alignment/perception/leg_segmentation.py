"""Find a whole pork leg in the overhead depth image by its height above the belt.

Pipeline step 1, the geometric method (`experiments/2026-09-15-leg-segmentation.md`).
A learned segmenter is measured against it on the same frames before either is
chosen, and the two can run together: this one as the check on the other.

Why height, and why these limits
--------------------------------
A leg on the belt stands 25 mm or more above it almost everywhere, and nothing
else inside the belt region does. Height is measured against an image of the
empty belt rather than a fitted plane, so any fixed error in the camera's depth
cancels, and averaging several empty frames cancels most of the reference's own
noise.

The belt region is tested on each point's position in the world, not on its
pixel. A flat region drawn on the image at belt height cuts a tall ham near the
far rail: a point 200 mm up and 330 mm from the camera's axis projects 90 mm
further out than the belt point beneath it, past the region's edge.

The region runs from 150 mm past the open edge, where the trotter overhangs, to
10 mm short of the far rail. The height band stops at 300 mm so that the arm,
when it is over the belt, is not taken for a leg.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from robotics.core.camera_frame import CameraFrameData
from robotics.perception.depth_geometry import (
    MIN_VALID_DEPTH_M,
    PLANE_FIT_SAMPLES,
    Plane,
    fit_plane_ransac,
    ray_directions,
)
from robotics.perception.segmentation import largest_component

# Reference points within this of the fitted plane count as belt. About four
# standard deviations of the modelled depth noise at 0.95 m, after averaging.
PLANE_TOLERANCE_M = 0.004
HEIGHT_CUT_M = 0.010
HEIGHT_CEILING_M = 0.300
BRIDGE_PX = 15
MIN_LEG_PIXELS = 5000


@dataclass(frozen=True)
class BeltRegion:
    """Where on the belt a leg may be, world frame, metres.

    The strip past the open edge must be clear of hardware within the camera's
    view: anything standing 10 to 300 mm above the belt plane there is taken for
    a leg. An arm pedestal on the near side breaks this (found with the UR5e
    cell in the tests); the pilot cell mounts its arm behind the far rail.

    Attributes:
        x_min_m: Upstream limit.
        x_max_m: Downstream limit.
        y_min_m: Open-edge side, past the edge so an overhanging trotter counts.
        y_max_m: Far side, short of the rail.
    """

    x_min_m: float = -1.6
    x_max_m: float = 1.6
    # 300 mm past the open edge: the longest leg's trotter tip reaches 230 mm past it
    # when the leg lies square with its far end near the rail. The first run allowed
    # 150 mm and cut trotters off.
    y_min_m: float = 0.15 - 0.30
    y_max_m: float = 0.857 - 0.010

    def contains(self, x_m: np.ndarray, y_m: np.ndarray) -> np.ndarray:
        """Boolean array, True where the point lies inside the region."""
        return np.asarray((x_m >= self.x_min_m) & (x_m <= self.x_max_m) & (y_m >= self.y_min_m) & (y_m <= self.y_max_m))


@dataclass(frozen=True)
class EmptyBeltReference:
    """Depth of the empty belt, averaged over frames, and the belt plane fitted to it.

    Past the open edge the empty frame sees the floor, not the belt, so a height
    measured against the empty frame there is the height above the floor: an
    overhanging trotter reads as a metre tall and fails the height ceiling. The
    first run lost trotters that way (up to 50 mm of centroid error). So the
    reference records where it actually saw the belt, and height elsewhere is
    measured against the fitted belt plane instead.

    Attributes:
        depth_m: (H, W) float32, mean depth where every frame returned.
        valid: (H, W) bool, pixels every frame returned.
        on_belt: (H, W) bool, pixels whose reference point lies on the belt plane.
        plane: Belt plane fitted to the reference points, normal pointing up.
        frames: How many frames were averaged.
    """

    depth_m: np.ndarray
    valid: np.ndarray
    on_belt: np.ndarray
    plane: Plane
    frames: int

    @classmethod
    def from_frames(
        cls, frames: list[CameraFrameData], belt_area: BeltRegion | None = None, seed: int = 0
    ) -> EmptyBeltReference:
        """Average frames of the empty belt taken through the same camera, and fit its plane.

        Args:
            frames: Frames of the empty belt.
            belt_area: Where the belt surface itself is, world frame; the plane is
                fitted only to points there. Defaults to the belt 20 mm in from both edges.
            seed: Seeds the plane fit.

        Raises:
            ValueError: If no frames are given, or too little of the belt came back to fit a plane.
        """
        belt_area = belt_area or BeltRegion(y_min_m=0.15 + 0.02, y_max_m=0.857 - 0.02)
        if not frames:
            raise ValueError("need at least one empty-belt frame")
        stack = np.stack([f.depth_m.astype(np.float32) for f in frames])
        valid = np.all(stack > MIN_VALID_DEPTH_M, axis=0)
        mean = np.where(valid, stack.mean(axis=0), 0.0).astype(np.float32)
        points = frames[0].camera.position_m.astype(np.float32) + ray_directions(frames[0]) * mean[..., None]
        rng = np.random.default_rng(seed)
        # Fit only to points on the belt itself. With the camera's wide side across
        # the belt, the floor either side fills more of the image than the 700 mm
        # belt does, and a fit over the whole frame found the floor (first attempt,
        # 2026-09-15: offset 0, every leg refused).
        on_belt_area = valid & belt_area.contains(points[..., 0], points[..., 1])
        rows, cols = np.nonzero(on_belt_area)
        if rows.size < 3:
            raise ValueError("the empty-belt frames show almost no belt")
        take = rng.choice(rows.size, min(PLANE_FIT_SAMPLES, rows.size), replace=False)
        plane = fit_plane_ransac(points[rows[take], cols[take]], PLANE_TOLERANCE_M, rng)
        on_belt = valid.copy()
        on_belt[valid] = np.abs(plane.height_of(points[valid])) < PLANE_TOLERANCE_M
        return cls(depth_m=mean, valid=valid, on_belt=on_belt, plane=plane, frames=len(frames))


@dataclass(frozen=True)
class LegSegmentation:
    """The leg mask, or why there is none.

    Attributes:
        mask: (H, W) bool, the leg; all False when refused.
        refused: None when accepted, otherwise the reason in words.
        elapsed_ms: Time spent segmenting this frame.
        diagnostics: Numbers behind the decision.
    """

    mask: np.ndarray
    refused: str | None
    elapsed_ms: float
    diagnostics: dict[str, float] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        """True when a leg mask was produced."""
        return self.refused is None


def _bridge_and_keep_largest(candidate: np.ndarray, bridge_px: int) -> np.ndarray:
    """Close dropout gaps, keep the largest piece, fill its holes.

    The region test runs before this, so the largest piece is chosen among
    things on the belt; otherwise the arm or the rail could win it.
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (bridge_px, bridge_px))
    bridged = cv2.morphologyEx(candidate.astype(np.uint8), cv2.MORPH_CLOSE, kernel).astype(bool)
    biggest = largest_component(bridged)
    if not biggest.any():
        return biggest
    contours, _ = cv2.findContours(biggest.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros(candidate.shape, dtype=np.uint8)
    cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)
    return np.asarray(filled > 0)


class LegSegmenter:
    """Height above the empty belt, inside the belt region, one piece."""

    name = "depth-height-leg"

    def __init__(
        self,
        reference: EmptyBeltReference,
        region: BeltRegion | None = None,
        height_cut_m: float = HEIGHT_CUT_M,
        height_ceiling_m: float = HEIGHT_CEILING_M,
        bridge_px: int = BRIDGE_PX,
        min_pixels: int = MIN_LEG_PIXELS,
    ) -> None:
        """Configure the segmenter; defaults are the pre-registered values."""
        if not 0.0 < height_cut_m < height_ceiling_m:
            raise ValueError("need 0 < height cut < height ceiling")
        self.reference = reference
        self.region = region or BeltRegion()
        self.height_cut_m = height_cut_m
        self.height_ceiling_m = height_ceiling_m
        self.bridge_px = bridge_px
        self.min_pixels = min_pixels

    def segment(self, frame: CameraFrameData) -> LegSegmentation:
        """Find the leg in one frame, or refuse and say why."""
        started = time.perf_counter()
        if frame.depth_m.shape != self.reference.depth_m.shape:
            raise ValueError("frame and empty-belt reference come from different image sizes")
        depth = frame.depth_m
        valid = depth > MIN_VALID_DEPTH_M
        directions = ray_directions(frame)
        points = frame.camera.position_m.astype(np.float32) + directions * depth[..., None]
        # Where the reference saw the belt, height is the depth difference along
        # the same ray, which cancels any fixed error in the camera's depth.
        # Elsewhere (past the open edge, over the rail) it is the height above
        # the fitted belt plane.
        height = np.zeros(depth.shape, dtype=np.float32)
        height[valid] = self.reference.plane.height_of(points[valid]).astype(np.float32)
        use_reference = valid & self.reference.on_belt
        height[use_reference] = (self.reference.depth_m[use_reference] - depth[use_reference]) * np.abs(
            directions[..., 2][use_reference]
        )
        in_region = self.region.contains(points[..., 0], points[..., 1])
        candidate = valid & in_region & (height > self.height_cut_m) & (height < self.height_ceiling_m)
        mask = _bridge_and_keep_largest(candidate, self.bridge_px) if candidate.any() else candidate
        pixels = int(mask.sum())
        diagnostics = {
            "valid_fraction": float(valid.mean()),
            "candidate_pixels": float(candidate.sum()),
            "mask_pixels": float(pixels),
            "median_height_m": float(np.median(height[mask])) if pixels else 0.0,
        }

        def finish(refused: str | None) -> LegSegmentation:
            kept = mask if refused is None else np.zeros_like(mask)
            return LegSegmentation(kept, refused, 1000.0 * (time.perf_counter() - started), diagnostics)

        if pixels == 0:
            return finish("nothing above the belt")
        if pixels < self.min_pixels:
            return finish(f"largest piece is {pixels} px, under {self.min_pixels}")
        if mask[0, :].any() or mask[-1, :].any() or mask[:, 0].any() or mask[:, -1].any():
            return finish("leg runs off the image edge")
        return finish(None)
