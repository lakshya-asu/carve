"""Turn a segmentation mask into a metric pose for the arm.

The module takes a mask and a captured frame and returns a `PieceEstimate` in
the world frame. It never touches the simulator. Scoring against ground truth
lives in `scoring.py`, which is the only place allowed to hold both.

Two estimators are here because the choice between them is a measured result,
not a preference:

`estimate_from_depth`
    Back-projects the masked pixels with the depth image, keeps the points on
    the product's upper surface, and takes the centroid and principal axis of
    those points. Needs a depth sensor.

`estimate_from_mask`
    Back-projects the mask centroid alone onto an assumed horizontal plane.
    Needs only a colour camera, and is what a plain detector plus a hand-eye
    calibration gives you.

Measured over 200 random poses of the 180 x 90 x 30 mm product, fully inside the
frame, on the overhead camera at 1280 x 960 (`experiments/2026-09-08-perception-
ingestion.md`): the depth estimator holds 0.12 mm mean and 0.47 mm worst-case
position error; the monocular estimator is 1.14 mm mean and 4.01 mm worst case
against the best available plane assumption, and 4.71 mm mean against the belt
plane. The 2 mm bound therefore rules the monocular estimator out on its own,
and the reason is the product's thickness seen off-axis, not pixel resolution:
ground sampling distance at the pick is 0.58 mm per pixel.

The border guard is not defensive programming. A product that runs off the edge
of the frame still yields a clean mask and a confident centroid, and that
centroid was measured 9.8 mm wrong. Nothing else in the pipeline can detect it.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np

from meat_cell_sim.contracts import Frame, PieceEstimate, Pose2D, wrap_axis_angle
from meat_cell_sim.frames import CameraPose, Intrinsics, pixel_to_plane
from meat_cell_sim.sensing import CameraFrameData

logger = logging.getLogger(__name__)

# A mask smaller than this is noise, not product. The product covers roughly
# 48000 pixels at the pick distance, so this rejects anything under 1 percent of
# the expected area without touching a real detection.
MIN_MASK_PIXELS = 400

# Points within this distance of the median surface height count as the upper
# surface. Wide enough to hold a real product's thickness variation and its
# settling into the belt.
SURFACE_BAND_M = 0.003

# Minimum vertical component of a point's surface normal for it to count as
# upper surface rather than side wall. cos(60 degrees): a product's top may
# slope, a cut edge is near vertical, and the two do not overlap.
#
# This test is what removes the side wall, and it has to exist. A height band
# alone keeps a strip of wall as tall as the band, and that strip sits entirely
# on the camera-facing side, so it drags the centroid toward the camera by an
# amount proportional to the band width and to how far off the optical axis the
# product is. Measured on this cell with a 3 mm band: 0.26 mm of bias 180 mm
# before nadir and -0.39 mm 260 mm past it. That is a spatial ramp, and a
# spatial ramp swept at belt speed becomes a phantom slip in the tracker.
NORMAL_Z_MIN = 0.5


class PerceptionRejectedError(Exception):
    """The frame cannot yield a trustworthy estimate, and why.

    Raised rather than returned as a low confidence, because every condition
    that raises this makes the numbers wrong rather than uncertain, and a wrong
    number with a low confidence still gets used by something eventually.
    """


@dataclass(frozen=True)
class SurfaceCloud:
    """Points on the product's upper surface, in world metres.

    Attributes:
        points_m: (N, 3) world coordinates of the surface points.
        height_m: Median height of the surface above the world origin.
        pixel_count: Size of the mask the cloud came from.
    """

    points_m: np.ndarray
    height_m: float
    pixel_count: int


def mask_touches_border(mask: np.ndarray) -> bool:
    """Whether the mask reaches any image edge, meaning the product is cut off."""
    return bool(mask[0, :].any() or mask[-1, :].any() or mask[:, 0].any() or mask[:, -1].any())


def backproject(mask: np.ndarray, frame: CameraFrameData) -> SurfaceCloud:
    """Lift the masked pixels into world coordinates and keep the upper surface.

    Three things happen here, and each removes a distinct fault.

    The mask is eroded by one pixel. Depth values at a silhouette edge are
    interpolated across the discontinuity, and on this cell 32 pixels out of
    48841 read up to 2.1 mm above the true surface because of it. Eroding also
    gives every remaining pixel four neighbours inside the product, which is
    what the normals need.

    The surface height is taken as the **median** of the masked points. Using
    the maximum looks equivalent and is not: a band below the maximum keeps only
    the outliers above, which put the centroid 16 mm out with the principal axis
    turned 90 degrees.

    Points are kept only where the surface normal points up. A height band alone
    keeps a strip of side wall, always on the camera-facing side, which biases
    the centroid toward the camera in proportion to how far off-axis the product
    sits. See `NORMAL_Z_MIN`.

    Raises:
        PerceptionRejectedError: If the mask is too small, runs off the frame, or
            has no coherent upper surface left after filtering.
    """
    _check_mask(mask, frame)
    interior = _erode(mask)
    if int(interior.sum()) < MIN_MASK_PIXELS:
        raise PerceptionRejectedError(f"mask has {int(interior.sum())} interior pixels after eroding its border")
    points = point_image(frame)
    normals = _normal_image(points)
    height = float(np.median(points[interior][:, 2]))
    keep = interior & (np.abs(points[:, :, 2] - height) < SURFACE_BAND_M) & (np.abs(normals[:, :, 2]) >= NORMAL_Z_MIN)
    surface = points[keep]
    if surface.shape[0] < MIN_MASK_PIXELS:
        raise PerceptionRejectedError(
            f"only {surface.shape[0]} of {int(interior.sum())} interior points lie on one upward surface; "
            "the product is probably folded, on edge, or occluded"
        )
    return SurfaceCloud(points_m=surface, height_m=height, pixel_count=int(mask.sum()))


def _erode(mask: np.ndarray) -> np.ndarray:
    """Mask pixels whose four neighbours are all inside the mask."""
    inner = mask.copy()
    inner[1:, :] &= mask[:-1, :]
    inner[:-1, :] &= mask[1:, :]
    inner[:, 1:] &= mask[:, :-1]
    inner[:, :-1] &= mask[:, 1:]
    inner[0, :] = inner[-1, :] = False
    inner[:, 0] = inner[:, -1] = False
    return np.asarray(inner)


def point_image(frame: CameraFrameData) -> np.ndarray:
    """World coordinates of every pixel, (H, W, 3).

    Computed over the whole image rather than over the mask alone so that
    neighbouring pixels stay adjacent in the array, which is what the normal
    estimate needs. The masked-out entries are never read.
    """
    intr = frame.intrinsics
    rows, cols = np.mgrid[0 : intr.height_px, 0 : intr.width_px].astype(float)
    directions_cam = np.stack([(cols - intr.cx) / intr.fx, -(rows - intr.cy) / intr.fy, -np.ones_like(cols)], axis=-1)
    directions_world = directions_cam @ frame.camera.rotation.T
    return np.asarray(frame.camera.position_m + directions_world * frame.depth_m[:, :, None])


def _normal_image(points: np.ndarray) -> np.ndarray:
    """Unit surface normals from central differences of the point image.

    The cross product of the two image-space tangents. Only the vertical
    component is used, and only its magnitude, so the sign convention does not
    matter here.
    """
    d_col = np.zeros_like(points)
    d_row = np.zeros_like(points)
    d_col[:, 1:-1] = points[:, 2:] - points[:, :-2]
    d_row[1:-1, :] = points[2:, :] - points[:-2, :]
    normals = np.cross(d_col, d_row)
    length = np.linalg.norm(normals, axis=-1, keepdims=True)
    return np.asarray(np.divide(normals, length, out=np.zeros_like(normals), where=length > 0))


def _check_mask(mask: np.ndarray, frame: CameraFrameData) -> None:
    if mask.shape != (frame.intrinsics.height_px, frame.intrinsics.width_px):
        raise PerceptionRejectedError(f"mask is {mask.shape}, frame is {frame.depth_m.shape}")
    count = int(mask.sum())
    if count < MIN_MASK_PIXELS:
        raise PerceptionRejectedError(f"mask has {count} pixels, below the {MIN_MASK_PIXELS} floor")
    if mask_touches_border(mask):
        raise PerceptionRejectedError(
            "mask touches the image border, so the product is partly outside the frame; "
            "the centroid of a clipped mask is confidently wrong, measured at 9.8 mm on this cell"
        )


def principal_axis(points_xy_m: np.ndarray) -> tuple[np.ndarray, float, float, float]:
    """Centroid, heading and extents of a planar point set, by principal components.

    Returns:
        (centroid, yaw of the long axis in radians folded to (-pi/2, pi/2],
        extent along the long axis in metres, extent along the short axis).

    The heading is the eigenvector of the point covariance with the larger
    eigenvalue. As the two eigenvalues approach each other the heading stops
    being identifiable: a square has no long axis, and the estimate becomes a
    coin flip between two answers 90 degrees apart. `anisotropy` measures how
    far from that failure the piece is, and callers must check it.
    """
    centroid = points_xy_m.mean(axis=0)
    centred = points_xy_m - centroid
    covariance = centred.T @ centred / centred.shape[0]
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    long_axis = eigenvectors[:, int(np.argmax(eigenvalues))]
    yaw = wrap_axis_angle(float(np.arctan2(long_axis[1], long_axis[0])))
    short_axis = np.array([-long_axis[1], long_axis[0]])
    along = centred @ long_axis
    across = centred @ short_axis
    return centroid, yaw, float(along.max() - along.min()), float(across.max() - across.min())


def anisotropy(points_xy_m: np.ndarray) -> float:
    """How identifiable the long axis is, in [0, 1]. Zero means no long axis exists.

    One minus the ratio of the smaller to the larger covariance eigenvalue. For a
    uniform rectangle of aspect ratio r this is 1 - 1/r^2, so it falls off fast:
    an aspect ratio of 2 gives 0.75, of 1.2 gives 0.31, and of 1.05 gives 0.093.
    That collapse is the honest signal that a near-square product's measured
    heading should not be acted on.
    """
    centred = points_xy_m - points_xy_m.mean(axis=0)
    eigenvalues = np.linalg.eigvalsh(centred.T @ centred / centred.shape[0])
    largest = float(eigenvalues.max())
    if largest <= 0.0:
        return 0.0
    return float(1.0 - eigenvalues.min() / largest)


def estimate_from_depth(mask: np.ndarray, frame: CameraFrameData) -> PieceEstimate:
    """Pose of the product from its mask and the depth image. The default estimator.

    Raises:
        PerceptionRejectedError: If the mask fails a guard.
    """
    cloud = backproject(mask, frame)
    centroid, yaw, length, width = principal_axis(cloud.points_m[:, :2])
    if width > length:  # pragma: no cover - extents come from sorted eigenvalues
        raise PerceptionRejectedError(f"extents came out inverted: {length} by {width}")
    return PieceEstimate(
        pose=Pose2D(
            x_m=float(centroid[0]),
            y_m=float(centroid[1]),
            yaw_rad=yaw,
            frame=Frame.WORLD,
            stamp_s=frame.stamp_s,
        ),
        length_m=length,
        width_m=width,
        confidence=anisotropy(cloud.points_m[:, :2]),
        method="depth-surface-pca",
    )


def estimate_from_mask(mask: np.ndarray, frame: CameraFrameData, assumed_height_m: float) -> PieceEstimate:
    """Pose from the mask alone, back-projected onto an assumed horizontal plane.

    The monocular baseline. Its error is set by how wrong `assumed_height_m` is
    and by how far off the optical axis the product sits:

        lateral error = height error * horizontal offset / camera height

    and by a second term this signature cannot fix, which is that the centroid
    of a thick product's silhouette is not the projection of any fixed point on
    it. Measured worst case on this cell is 4.0 mm with the best plane and
    8.3 mm with the belt plane, against a 2 mm bound.

    Args:
        mask: Product silhouette.
        frame: The captured frame.
        assumed_height_m: World z of the plane the product is assumed to lie on.

    Raises:
        PerceptionRejectedError: If the mask fails a guard.
    """
    _check_mask(mask, frame)
    rows, cols = np.nonzero(mask)
    centre = _plane_point(frame.intrinsics, frame.camera, float(cols.mean()), float(rows.mean()), assumed_height_m)
    corners = np.array(
        [
            _plane_point(frame.intrinsics, frame.camera, float(u), float(v), assumed_height_m)
            for u, v in zip(cols, rows, strict=True)
        ]
    )
    _, yaw, length, width = principal_axis(corners)
    return PieceEstimate(
        pose=Pose2D(x_m=float(centre[0]), y_m=float(centre[1]), yaw_rad=yaw, frame=Frame.WORLD, stamp_s=frame.stamp_s),
        length_m=length,
        width_m=width,
        confidence=anisotropy(corners),
        method=f"mask-plane-{assumed_height_m:.3f}",
    )


def _plane_point(intr: Intrinsics, cam: CameraPose, u_px: float, v_px: float, plane_z_m: float) -> np.ndarray:
    return pixel_to_plane(intr, cam, u_px, v_px, plane_z_m)[:2]


def grip_axis_rad(estimate: PieceEstimate) -> float:
    """Finger axis for a parallel jaw: across the product, not along it.

    Jaws close along their own axis, so they must approach square to the long
    axis to press the two long sides together. Getting this 90 degrees wrong
    produces a grasp that is geometrically valid, fits in the gripper, and
    squeezes the product across its narrow dimension, where there is least
    material to hold.
    """
    return wrap_axis_angle(estimate.pose.yaw_rad + math.pi / 2)
