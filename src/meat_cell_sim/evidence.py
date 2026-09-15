"""Find the product by geometry, bound it by appearance, then check the answer.

The measured case for this design is in
`library/topics/perception-ingestion.md` and the sweep in
`experiments/data/2026-09-11-segmentation.json`. In short: over 40 poses per
condition no appearance-based segmenter held the 2 mm bound across conditions.
A colour threshold failed it on a clean render and was 9.4 mm out under modest
sensor noise; an edge method held 0.081 mm clean and was put 815 mm out by three
specular highlights, because a highlight makes a closed contour that beats the
product on area.

The product stands 30 mm proud of a flat belt. That is geometry, and the depth
camera measures it directly. Colour drift does not change height, a lighting
ramp does not change height, and a specular highlight is a bright patch at belt
level. So depth proposes, appearance refines the boundary, and colour only gets
a vote on whether to believe the result.

Three roles, because the channel that reliably *finds* the product is rarely the
one that best *delimits* it:

`ProposalChannel`
    Frame in, candidate mask and a confidence out. `DepthHeightProposal` is the
    only one built. Thermal, near-infrared and a trained segmenter each become
    one more of these, which is the whole extension point.
`RefinementStage`
    Mask and frame in, better-bounded mask out. The boundary sets the pose, so
    this is where accuracy comes from.
`Confirmation`
    Mask and frame in, an agreement score out, mask unchanged. Its only job is
    turning a confident wrong answer into a refusal.

`Segmenter` runs them and keeps a record of what every stage said, so a bad pose
is attributable to one stage rather than appearing as a mysterious miss at the
cutter.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Protocol

import cv2
import numpy as np

from meat_cell_sim.perception import point_image
from meat_cell_sim.segmentation import largest_component
from meat_cell_sim.sensing import CameraFrameData

logger = logging.getLogger(__name__)

# Product is 30 mm thick. A height cut well below that separates it from the
# belt with room for a slab that has settled or is thinner than nominal, while
# staying far above the depth sensor's own noise. See `DepthHeightProposal` for
# why this is not simply half the thickness.
DEFAULT_HEIGHT_CUT_M = 0.008

# Upper bound on what counts as product. "Everything standing proud of the belt"
# is not the product: the cell's guide rails stand 90 mm above the belt surface
# and are far larger than a slab, so a largest-component rule with no ceiling
# selects a rail every time. The ceiling also rejects a stack of two pieces,
# which is a thing to refuse rather than to grasp.
DEFAULT_HEIGHT_CEILING_M = 0.060

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


@dataclass(frozen=True)
class BeltReference:
    """A depth image of the empty belt, and the plane fitted to it.

    Fitting a plane per frame removes a flat belt but not the sensor's own
    distortion. A depth camera carries a fixed, smooth calibration error that is
    not planar and therefore cannot be absorbed by a plane fit: on a RealSense
    D415 that error ranged over 29.57 mm across a 500 to 1500 mm working
    distance (Servi et al. 2021), which at this cell's scale is the size of the
    product being looked for.

    A reference image cancels it. Both frames are taken through the same optics
    with the same error, so subtracting one from the other removes everything
    that does not move, leaving only what is standing on the belt. It also
    removes the per-frame plane fit, which was the most expensive stage.

    The cost is that the reference has to be maintained: it is valid only while
    the camera and the belt do not move relative to one another, and a knock to
    the camera silently invalidates it. `rms_residual_m` against a fresh fit is
    the number to watch for that.

    Attributes:
        depth_m: Depth of the empty belt, per pixel.
        normal: Plane normal fitted to the empty belt, pointing up.
        valid: Pixels where the reference has a depth return.
        rms_residual_m: How far the empty belt departed from a plane. Large
            values are the sensor's distortion, and are exactly what the
            reference is there to remove.
    """

    depth_m: np.ndarray
    normal: np.ndarray
    valid: np.ndarray
    rms_residual_m: float

    @classmethod
    def from_frame(cls, frame: CameraFrameData, plane_tolerance_m: float = 0.004, seed: int = 0) -> BeltReference:
        """Capture a reference from a frame of the empty belt.

        Raises:
            ValueError: If the frame has too little valid depth to fit a plane.
        """
        rng = np.random.default_rng(seed)
        valid = frame.depth_m > MIN_VALID_DEPTH_M
        if valid.sum() < 3:
            raise ValueError("the reference frame has almost no depth")
        directions = ray_directions(frame)
        rows, cols = np.nonzero(valid)
        take = rng.choice(rows.shape[0], min(PLANE_FIT_SAMPLES, rows.shape[0]), replace=False)
        points = (
            frame.camera.position_m
            + directions[rows[take], cols[take]] * frame.depth_m[rows[take], cols[take]][:, None]
        )
        plane = fit_plane_ransac(points, plane_tolerance_m, rng)
        return cls(
            depth_m=frame.depth_m.copy(),
            normal=plane.normal,
            valid=valid.copy(),
            rms_residual_m=plane.rms_residual_m,
        )


@dataclass(frozen=True)
class ChannelMask:
    """One channel's opinion about where the product is.

    Attributes:
        mask: Candidate product pixels.
        confidence: In [0, 1]. What it means is the channel's business; what it
            must do is fall when the channel is out of its depth.
        name: Which channel, for the record.
        diagnostics: Numbers worth keeping when this frame is argued about.
    """

    mask: np.ndarray
    confidence: float
    name: str
    diagnostics: dict[str, float] = field(default_factory=dict)


class ProposalChannel(Protocol):
    """Produces a candidate mask from a frame. The extension point."""

    name: str

    def propose(self, frame: CameraFrameData) -> ChannelMask:
        """Find the product, or return an empty mask with low confidence."""
        ...


class RefinementStage(Protocol):
    """Improves a mask's boundary without deciding whether it is product."""

    name: str

    def refine(self, mask: np.ndarray, frame: CameraFrameData) -> np.ndarray:
        """Return a better-bounded mask covering the same object."""
        ...


class Confirmation(Protocol):
    """Scores whether a mask really is product. Never edits it."""

    name: str

    def agreement(self, mask: np.ndarray, frame: CameraFrameData) -> float:
        """Agreement in [0, 1]."""
        ...


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


class DepthHeightProposal:
    """Find the product by how far it stands above the belt.

    Immune to everything that broke the appearance methods, because none of it
    changes height: a colour drift, a lighting ramp, and a specular highlight
    that is a bright patch sitting at belt level.

    Product is a height *band*, not everything above the belt. The cell's guide
    rails stand 90 mm proud and dwarf a slab, so without a ceiling the largest
    connected component above the belt is a rail on every single frame.

    What it is not immune to is depth itself failing. Active stereo returns
    nothing where it cannot find a correspondence, and wet specular product is
    exactly that case. Missing returns are excluded rather than treated as belt,
    and the fraction of the frame that came back is reported so a caller can see
    the sensor degrading rather than infer it from a bad pose.
    """

    name = "depth-height"

    def __init__(
        self,
        height_cut_m: float = DEFAULT_HEIGHT_CUT_M,
        height_ceiling_m: float = DEFAULT_HEIGHT_CEILING_M,
        plane_tolerance_m: float = 0.004,
        hole_bridge_px: int = 15,
        reference: BeltReference | None = None,
        seed: int = 0,
    ) -> None:
        """Configure the height band, the plane tolerance and the hole bridging.

        Args:
            height_cut_m: Lowest height above the belt that counts as product.
            height_ceiling_m: Highest. The guide rails stand 90 mm up.
            plane_tolerance_m: RANSAC inlier distance for the per-frame fit.
            hole_bridge_px: Width of dropout gap to close before choosing the
                largest component.
            reference: A depth image of the empty belt. When given, height comes
                from the difference against it, which cancels the sensor's fixed
                distortion and skips the per-frame plane fit. When absent, a
                plane is fitted to every frame, which is correct only if the
                camera's depth error is itself planar.
            seed: Seeds the RANSAC sampling so a run replays.
        """
        if height_cut_m <= plane_tolerance_m:
            raise ValueError(
                f"height cut {height_cut_m} m must exceed the plane tolerance {plane_tolerance_m} m, "
                "or belt noise is classified as product"
            )
        if height_ceiling_m <= height_cut_m:
            raise ValueError(f"ceiling {height_ceiling_m} m must exceed the cut {height_cut_m} m")
        self.height_cut_m = height_cut_m
        self.height_ceiling_m = height_ceiling_m
        self.plane_tolerance_m = plane_tolerance_m
        self.hole_bridge_px = hole_bridge_px
        self.reference = reference
        self._rng = np.random.default_rng(seed)

    def _propose_against_reference(
        self, frame: CameraFrameData, directions: np.ndarray, valid: np.ndarray, returned: float
    ) -> ChannelMask:
        """Height from the difference against the empty belt, not from a fitted plane.

        A point sits at `camera + depth * direction`, so its height above the
        plane is linear in depth and the height difference between this frame
        and the reference is `(reference_depth - depth) * |normal . direction|`.
        Every fixed error in the optics appears in both terms and cancels.
        """
        reference = self.reference
        assert reference is not None
        usable = valid & reference.valid
        scale = np.abs(directions @ reference.normal.astype(np.float32))
        height = (reference.depth_m - frame.depth_m) * scale
        height[~usable] = 0.0
        in_band = (height > self.height_cut_m) & (height < self.height_ceiling_m)
        mask = _close_and_fill(usable & in_band, self.hole_bridge_px)
        return ChannelMask(
            mask=mask,
            # No plane is fitted per frame, so the confidence is how much of the
            # frame both images agree they can see.
            confidence=float(usable.mean()),
            name=self.name,
            diagnostics={
                "depth_returned": returned,
                "reference_overlap": float(usable.mean()),
                "reference_rms_m": reference.rms_residual_m,
                "median_height_m": float(np.median(height[mask])) if mask.any() else 0.0,
            },
        )

    def propose(self, frame: CameraFrameData) -> ChannelMask:
        """Find the product: against the belt reference if there is one, else by fitting."""
        valid = frame.depth_m > MIN_VALID_DEPTH_M
        returned = float(valid.mean())
        if returned < 0.2:
            return ChannelMask(
                mask=np.zeros_like(valid),
                confidence=0.0,
                name=self.name,
                diagnostics={"depth_returned": returned},
            )
        directions = ray_directions(frame)
        if self.reference is not None:
            return self._propose_against_reference(frame, directions, valid, returned)
        # Fit the plane from a subsample. Back-projecting the whole frame to fit
        # a plane costs 1.2 million points to estimate three numbers.
        # Draw pixels at random and keep the valid ones, rather than listing
        # every valid pixel first: np.nonzero over a million-pixel frame cost
        # 7 ms to build an index we then threw almost all of away.
        flat_valid = valid.reshape(-1)
        drawn = self._rng.integers(0, flat_valid.size, size=4 * PLANE_FIT_SAMPLES)
        drawn = drawn[flat_valid[drawn]][:PLANE_FIT_SAMPLES]
        if drawn.size < 3:
            return ChannelMask(
                mask=np.zeros_like(valid), confidence=0.0, name=self.name, diagnostics={"depth_returned": returned}
            )
        rows, cols = np.unravel_index(drawn, valid.shape)
        sample_dirs = directions[rows, cols]
        sample_points = frame.camera.position_m + sample_dirs * frame.depth_m[rows, cols][:, None]
        try:
            plane = fit_plane_ransac(sample_points, self.plane_tolerance_m, self._rng)
        except ValueError:
            return ChannelMask(
                mask=np.zeros_like(valid), confidence=0.0, name=self.name, diagnostics={"depth_returned": returned}
            )

        # Height above the plane without building the point cloud: a point is
        # camera + depth * direction, so its signed height is linear in depth.
        #     h = (n . camera + offset) + depth * (n . direction)
        base = float(plane.normal @ frame.camera.position_m) + plane.offset_m
        height = base + frame.depth_m * (directions @ plane.normal.astype(np.float32))
        height[~valid] = 0.0
        in_band = (height > self.height_cut_m) & (height < self.height_ceiling_m)
        mask = _close_and_fill(valid & in_band, self.hole_bridge_px)
        return ChannelMask(
            mask=mask,
            # Two things have to hold for this channel to be trusted: the belt
            # was found convincingly, and the sensor actually returned a frame.
            confidence=float(plane.inlier_fraction * returned),
            name=self.name,
            diagnostics={
                "depth_returned": returned,
                "plane_inlier_fraction": plane.inlier_fraction,
                "plane_rms_m": plane.rms_residual_m,
                "median_height_m": float(np.median(height[mask])) if mask.any() else 0.0,
            },
        )


def _close_and_fill(mask: np.ndarray, bridge_px: int) -> np.ndarray:
    """Bridge dropout gaps, keep the largest piece, then fill its interior holes.

    A missing depth return inside the product is missing data, not background.
    Without this, a dropout patch landing on the product cuts it in two and the
    largest-component rule keeps one half, which moves the centroid by tens of
    millimetres while looking like a perfectly good mask. Measured before this
    was added: 1.9 mm mean at 10 percent of the frame lost, 14.0 mm at 50
    percent.

    Filling happens after the component is chosen, so a hole in the belt is
    never filled into the product.
    """
    if not mask.any():
        return mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (bridge_px, bridge_px))
    bridged = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    biggest = largest_component(bridged.astype(bool))
    if not biggest.any():
        return biggest
    contours, _ = cv2.findContours(biggest.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros(mask.shape, dtype=np.uint8)
    cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)
    return np.asarray(filled > 0)


class EdgeSnapRefinement:
    """Move the boundary onto the strongest image gradient nearby.

    Depth finds the product reliably and bounds it softly: the depth edge is
    blurred by the sensor and by interpolation across the silhouette. The
    boundary is what sets the pose, so it is worth taking from the sharp channel
    even though that channel cannot be trusted to find the product.

    Each contour point is moved along the contour's local normal to the strongest
    gradient within a band. When product and belt are the same colour there is no
    gradient to find and the point stays where depth put it, which is the
    behaviour worth having: the boundary loses sharpness rather than the piece
    being lost.
    """

    name = "edge-snap"

    def __init__(self, band_px: int = 6, min_gradient: float = 12.0) -> None:
        """Set how far to search and how strong a gradient must be to move to."""
        if band_px < 1:
            raise ValueError(f"band must be at least 1 px, got {band_px}")
        self.band_px = band_px
        self.min_gradient = min_gradient

    def refine(self, mask: np.ndarray, frame: CameraFrameData) -> np.ndarray:
        """Snap the mask's outer contour to the nearest strong image edge."""
        if not mask.any():
            return mask
        contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not contours:
            return mask
        contour = max(contours, key=cv2.contourArea).reshape(-1, 2).astype(np.float64)
        if contour.shape[0] < 8:
            return mask

        # The gradient is only read within a band of the contour, so compute it
        # only there. Running Sobel over the whole million-pixel frame to sample
        # a few thousand points near its edge was most of this stage's cost.
        margin = self.band_px + 6
        full_h, full_w = frame.depth_m.shape
        x0 = max(0, int(contour[:, 0].min()) - margin)
        y0 = max(0, int(contour[:, 1].min()) - margin)
        x1 = min(full_w, int(contour[:, 0].max()) + margin + 1)
        y1 = min(full_h, int(contour[:, 1].max()) + margin + 1)
        patch = cv2.GaussianBlur(cv2.cvtColor(frame.rgb[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY), (5, 5), 1.2)
        gradient = cv2.magnitude(
            cv2.Sobel(patch, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(patch, cv2.CV_32F, 0, 1, ksize=3)
        )
        normals = _contour_normals(contour)
        offsets = np.arange(-self.band_px, self.band_px + 1, dtype=np.float64)
        height, width = gradient.shape

        # Sample the gradient along each point's normal in one vectorised pass:
        # (points, band) coordinates in patch space, clipped so the search
        # cannot walk off the patch and wrap round to its far side.
        samples_x = np.clip(contour[:, 0:1] - x0 + normals[:, 0:1] * offsets[None, :], 0, width - 1)
        samples_y = np.clip(contour[:, 1:2] - y0 + normals[:, 1:2] * offsets[None, :], 0, height - 1)
        values = gradient[np.rint(samples_y).astype(int), np.rint(samples_x).astype(int)]

        best = np.argmax(values, axis=1)
        strong = values[np.arange(values.shape[0]), best] >= self.min_gradient
        shift = np.where(strong, offsets[best], 0.0)
        moved = contour + normals * shift[:, None]

        snapped = np.zeros_like(mask, dtype=np.uint8)
        cv2.drawContours(snapped, [np.rint(moved).astype(np.int32)], -1, 255, thickness=cv2.FILLED)
        return np.asarray(snapped > 0)


def _contour_normals(contour: np.ndarray) -> np.ndarray:
    """Outward unit normals of a closed contour, from its local tangents."""
    tangents = np.roll(contour, -1, axis=0) - np.roll(contour, 1, axis=0)
    normals = np.stack([tangents[:, 1], -tangents[:, 0]], axis=-1)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)
    # OpenCV traces an outer contour counter-clockwise in image coordinates,
    # where y runs down, so this construction already points outward. Checking
    # against the centroid keeps that true for any contour it does not.
    outward = contour - contour.mean(axis=0)
    flip = np.sum(normals * outward, axis=1) < 0
    normals[flip] *= -1
    return np.asarray(normals)


class ColourConfirmation:
    """Score whether the enclosed region looks like the product it claims to be.

    Never edits the mask. This exists because every defect found in this cell so
    far produced a confident wrong answer rather than an error, and a channel
    that cannot be wrong quietly is worth more than a channel that is slightly
    more accurate.

    Comparison is in chromaticity, `(r, g) / (r + g + b)`, not in raw RGB. A
    lighting change scales all three channels together and leaves chromaticity
    alone, so this test does not fail on the one axis the whole design exists to
    be immune to. Comparing raw RGB rejected a correctly segmented product that
    happened to sit at the dim end of a lighting gradient.

    The reference is supplied by the caller rather than learned from the frame,
    because a model updated from whatever was last segmented converges onto the
    belt.
    """

    name = "colour-confirm"

    def __init__(self, reference_rgb: np.ndarray, tolerance: float = 0.12) -> None:
        """Set the expected product colour and how far its chromaticity may drift."""
        self.reference_chromaticity = _chromaticity(np.asarray(reference_rgb, dtype=float))
        self.tolerance = tolerance

    def agreement(self, mask: np.ndarray, frame: CameraFrameData) -> float:
        """One minus the normalised chromaticity distance, clipped to [0, 1]."""
        if not mask.any():
            return 0.0
        # cv2.mean with a mask beats fancy-indexing a million-pixel frame.
        means = cv2.mean(frame.rgb, mask=mask.astype(np.uint8))
        observed = _chromaticity(np.array(means[:3], dtype=float))
        distance = float(np.linalg.norm(observed - self.reference_chromaticity))
        return float(np.clip(1.0 - distance / self.tolerance, 0.0, 1.0))


def _chromaticity(rgb: np.ndarray) -> np.ndarray:
    """Red and green fractions of total intensity, invariant to overall brightness."""
    total = float(np.sum(rgb))
    if total <= 0:
        return np.zeros(2)
    return np.asarray(rgb[:2] / total, dtype=float)


@dataclass(frozen=True)
class SegmentationResult:
    """One frame's answer and the record behind it.

    Attributes:
        mask: The product, or empty if the frame was refused.
        confidence: The winning proposal's confidence.
        agreement: The confirmation score.
        instances: How many separate pieces the splitter found.
        rejected_by: Stage that refused the frame, or None.
        reason: Why, in words, or None.
        record: Every stage's diagnostics, keyed by stage name.
    """

    mask: np.ndarray
    confidence: float
    agreement: float
    instances: int
    rejected_by: str | None = None
    reason: str | None = None
    record: dict[str, dict[str, float]] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        """Whether this frame produced a usable mask."""
        return self.rejected_by is None and bool(self.mask.any())


class HeightWatershedSplit:
    """Separate touching pieces using the height map rather than the picture.

    Two slabs in contact still have a valley between them, because the valley is
    geometry. Colour cannot see it and neither can an edge detector, since the
    seam between two pieces of the same product has no step in brightness.

    Markers come from the distance transform, which peaks once per piece. A
    single piece yields one marker and the splitter returns immediately, so the
    cost is only paid on the frames that need it. That matters because
    over-segmenting a single piece is the expensive failure here: it turns one
    good grasp into two refusals.
    """

    name = "height-split"

    def __init__(self, peak_fraction: float = 0.55, plane_tolerance_m: float = 0.004, seed: int = 0) -> None:
        """Set how tall a distance-transform peak must be to count as a piece."""
        if not 0.0 < peak_fraction < 1.0:
            raise ValueError(f"peak fraction must be in (0, 1), got {peak_fraction}")
        self.peak_fraction = peak_fraction
        self.plane_tolerance_m = plane_tolerance_m
        self._rng = np.random.default_rng(seed)

    def split(self, mask: np.ndarray, frame: CameraFrameData) -> list[np.ndarray]:
        """Return one mask per piece. A single piece comes back unchanged."""
        if not mask.any():
            return []
        distance = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
        peaks = distance > self.peak_fraction * float(distance.max())
        marker_count, markers = cv2.connectedComponents(peaks.astype(np.uint8))
        if marker_count <= 2:  # background plus one piece
            return [mask]

        height = self._height_image(frame)
        span = float(height.max() - height.min())
        scaled = ((height - height.min()) / span * 255.0) if span > 0 else np.zeros_like(height)
        surface = cv2.cvtColor(scaled.astype(np.uint8), cv2.COLOR_GRAY2BGR)
        # Watershed wants the unknown region labelled zero and the background
        # labelled non-zero, so shift the piece markers up and claim everything
        # outside the mask as background.
        labels = markers.astype(np.int32) + 1
        labels[~mask] = 1
        labels[mask & ~peaks] = 0
        cv2.watershed(surface, labels)
        return [np.asarray((labels == index) & mask) for index in range(2, marker_count + 1)]

    def _height_image(self, frame: CameraFrameData) -> np.ndarray:
        valid = frame.depth_m > MIN_VALID_DEPTH_M
        points = point_image(frame)
        height = np.zeros(valid.shape, dtype=np.float32)
        if valid.sum() >= 3:
            plane = fit_plane_ransac(points[valid], self.plane_tolerance_m, self._rng)
            height[valid] = plane.height_of(points[valid]).astype(np.float32)
        return height


class Segmenter:
    """Run the channels in order and keep the record.

    The fusion step is `max` over proposal confidences, which with one channel is
    an identity function. It is exercised from the first day on purpose: adding a
    second channel is then a registration, not a rewrite.
    """

    def __init__(
        self,
        proposals: list[ProposalChannel],
        refinements: list[RefinementStage] | None = None,
        confirmation: Confirmation | None = None,
        splitter: HeightWatershedSplit | None = None,
        min_confidence: float = 0.30,
        min_agreement: float = 0.25,
    ) -> None:
        """Assemble a pipeline. Only `proposals` is required."""
        if not proposals:
            raise ValueError("a segmenter needs at least one proposal channel")
        self.proposals = proposals
        self.refinements = refinements or []
        self.confirmation = confirmation
        self.splitter = splitter
        self.min_confidence = min_confidence
        self.min_agreement = min_agreement

    def segment(self, frame: CameraFrameData) -> SegmentationResult:
        """Find the product, or say which stage refused the frame and why."""
        record: dict[str, dict[str, float]] = {}
        candidates = [channel.propose(frame) for channel in self.proposals]
        for candidate in candidates:
            record[candidate.name] = {"confidence": candidate.confidence, **candidate.diagnostics}
        best = max(candidates, key=lambda c: c.confidence)
        record["fuse"] = {"channels": float(len(candidates)), "chose_confidence": best.confidence}

        empty = np.zeros_like(best.mask)
        if not best.mask.any():
            return SegmentationResult(empty, best.confidence, 0.0, 0, best.name, "no candidate mask", record)
        if best.confidence < self.min_confidence:
            return SegmentationResult(
                empty,
                best.confidence,
                0.0,
                0,
                best.name,
                f"confidence {best.confidence:.3f} below {self.min_confidence:.3f}",
                record,
            )

        mask = best.mask
        for stage in self.refinements:
            refined = stage.refine(mask, frame)
            record[stage.name] = {"pixels_before": float(mask.sum()), "pixels_after": float(refined.sum())}
            if not refined.any():
                return SegmentationResult(
                    empty, best.confidence, 0.0, 0, stage.name, "refinement emptied the mask", record
                )
            mask = refined

        instances = 1
        if self.splitter is not None:
            pieces = self.splitter.split(mask, frame)
            instances = len(pieces)
            record[self.splitter.name] = {"instances": float(instances)}
            if instances > 1:
                # Grasping one of two touching pieces risks dragging the other
                # into the cutter. A skipped piece costs one cycle; a double
                # feed costs a stoppage.
                return SegmentationResult(
                    empty, best.confidence, 0.0, instances, self.splitter.name, f"{instances} touching pieces", record
                )
            mask = pieces[0] if pieces else mask

        agreement = 1.0
        if self.confirmation is not None:
            agreement = self.confirmation.agreement(mask, frame)
            record[self.confirmation.name] = {"agreement": agreement}
            if agreement < self.min_agreement:
                return SegmentationResult(
                    empty,
                    best.confidence,
                    agreement,
                    instances,
                    self.confirmation.name,
                    f"agreement {agreement:.3f} below {self.min_agreement:.3f}",
                    record,
                )

        return SegmentationResult(mask, best.confidence, agreement, instances, None, None, record)
