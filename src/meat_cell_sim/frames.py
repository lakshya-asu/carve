"""Camera geometry: pixels to metres, and metres between frames.

This is the layer that turns a perception result into something the arm can be
commanded with. It is built and tested before perception on purpose. A centroid
measured to a tenth of a pixel is worthless if the transform under it is wrong,
and a wrong transform produces numbers that look entirely reasonable.

Two conventions, fixed here and not re-derived anywhere else:

* MuJoCo cameras look along their own -z with +y up and +x right. Image row
  index increases downward, so image v runs against camera y.
* A transform named ``T_a_b`` maps a point expressed in frame b into frame a.

The monocular height problem
----------------------------
An overhead camera measures a direction, not a position. Turning a pixel into a
point on the belt needs one more number: the height of the surface the point
lies on. Using the belt height for a point that is really on top of a 30 mm
slab puts the answer sideways by

    lateral error = height error * horizontal offset / camera height

so the error is zero directly below the camera and grows with obliquity. See
``height_error_to_lateral_error_m``; the numbers for this cell are in
``library/topics/pixels-to-metres.md``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from meat_cell_sim.contracts import Frame, Pose2D

# Robot base sits on top of the pedestal; `arm_mount` in cell.xml is at this
# height above the world origin, with no rotation. Kept as one constant because
# every world-to-base conversion in the cell uses it.
BASE_HEIGHT_M = 0.90


@dataclass(frozen=True)
class Intrinsics:
    """Pinhole intrinsics in pixels.

    Attributes:
        fx: Focal length along image x, pixels.
        fy: Focal length along image y, pixels.
        cx: Principal point column, pixels.
        cy: Principal point row, pixels.
        width_px: Image width.
        height_px: Image height.
    """

    fx: float
    fy: float
    cx: float
    cy: float
    width_px: int
    height_px: int

    @classmethod
    def from_fovy(cls, fovy_deg: float, width_px: int, height_px: int) -> Intrinsics:
        """Intrinsics of a MuJoCo camera, which specifies only a vertical field of view.

        MuJoCo pixels are square, so one focal length serves both axes. The
        principal point is the image centre, which for pixel centres at integer
        indices is at (n - 1) / 2, not n / 2. Half a pixel of error here is
        0.3 mm on the belt at this cell's scale, which is not negligible against
        a 2 mm bound.
        """
        if width_px <= 0 or height_px <= 0:
            raise ValueError(f"image size must be positive, got {width_px}x{height_px}")
        if not 0.0 < fovy_deg < 180.0:
            raise ValueError(f"fovy must be in (0, 180) degrees, got {fovy_deg}")
        f = 0.5 * height_px / math.tan(math.radians(fovy_deg) / 2.0)
        return cls(
            fx=f, fy=f, cx=(width_px - 1) / 2.0, cy=(height_px - 1) / 2.0, width_px=width_px, height_px=height_px
        )

    @property
    def matrix(self) -> np.ndarray:
        """The 3x3 K matrix, for handing to OpenCV or to a calibration file."""
        return np.array([[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0.0, 0.0, 1.0]])

    def metres_per_pixel_at(self, range_m: float) -> float:
        """Ground sampling distance of a fronto-parallel surface ``range_m`` away."""
        return range_m / self.fx


@dataclass(frozen=True)
class CameraPose:
    """Where a camera is and which way it points, in the world frame.

    Attributes:
        position_m: Camera optical centre in world coordinates, (3,).
        rotation: World-from-camera rotation, (3, 3). Columns are the camera's
            x, y and z axes expressed in world coordinates.
    """

    position_m: np.ndarray
    rotation: np.ndarray

    def __post_init__(self) -> None:
        if self.position_m.shape != (3,):
            raise ValueError(f"position must be (3,), got {self.position_m.shape}")
        if self.rotation.shape != (3, 3):
            raise ValueError(f"rotation must be (3, 3), got {self.rotation.shape}")
        # A rotation that has quietly picked up a scale or a reflection produces
        # positions that are wrong by a smooth factor, which is the hardest kind
        # of calibration fault to notice downstream.
        if not np.allclose(self.rotation.T @ self.rotation, np.eye(3), atol=1e-6):
            raise ValueError("rotation is not orthonormal")
        if np.linalg.det(self.rotation) < 0:
            raise ValueError("rotation is a reflection, determinant is negative")

    @property
    def optical_axis(self) -> np.ndarray:
        """Unit vector the camera looks along, in world coordinates."""
        return -self.rotation[:, 2]


def pixel_ray(intr: Intrinsics, u_px: float, v_px: float) -> np.ndarray:
    """Direction of the ray through pixel (u, v), in the camera frame, unnormalised.

    Args:
        intr: Camera intrinsics.
        u_px: Column, increasing right.
        v_px: Row, increasing down.

    Returns:
        (3,) direction with z = -1, so scaling it by a distance gives a point at
        that depth along the optical axis.
    """
    return np.array([(u_px - intr.cx) / intr.fx, -(v_px - intr.cy) / intr.fy, -1.0])


def pixel_to_plane(intr: Intrinsics, cam: CameraPose, u_px: float, v_px: float, plane_z_m: float) -> np.ndarray:
    """Intersect the ray through a pixel with the horizontal plane z = ``plane_z_m``.

    This is the only way to get a metric position from one camera and no depth,
    and it is exact only if the observed point really lies on that plane. For a
    piece of product the plane is its top surface, not the belt.

    Raises:
        ValueError: If the ray runs parallel to the plane or points away from it.
    """
    direction = cam.rotation @ pixel_ray(intr, u_px, v_px)
    if abs(direction[2]) < 1e-12:
        raise ValueError("ray is parallel to the plane")
    t = (plane_z_m - cam.position_m[2]) / direction[2]
    if t <= 0:
        raise ValueError(f"plane z={plane_z_m} is behind the camera")
    return np.asarray(cam.position_m + t * direction, dtype=float)


def world_to_pixel(intr: Intrinsics, cam: CameraPose, point_world_m: np.ndarray) -> np.ndarray:
    """Project a world point into the image. Inverse of `pixel_to_plane`.

    Returns:
        (2,) array of (column, row) in pixels. May fall outside the image.

    Raises:
        ValueError: If the point is behind the camera.
    """
    p_cam = cam.rotation.T @ (np.asarray(point_world_m, dtype=float) - cam.position_m)
    depth = -p_cam[2]
    if depth <= 1e-9:
        raise ValueError("point is behind the camera or at its optical centre")
    return np.array([intr.cx + intr.fx * p_cam[0] / depth, intr.cy - intr.fy * p_cam[1] / depth], dtype=float)


def height_error_to_lateral_error_m(cam: CameraPose, point_world_m: np.ndarray, height_error_m: float) -> float:
    """Lateral position error caused by assuming the wrong surface height.

    The ray is fixed by the pixel, so moving the assumed plane slides the answer
    along that ray. The horizontal component of the slide is the error:

        lateral = height error * horizontal offset from camera / height below camera

    Zero directly under the camera, and equal to the height error itself when the
    ray is at 45 degrees.
    """
    delta = np.asarray(point_world_m, dtype=float) - cam.position_m
    drop = -delta[2]
    if drop <= 0:
        raise ValueError("point must be below the camera")
    return abs(height_error_m) * float(np.hypot(delta[0], delta[1])) / float(drop)


def world_to_base(point_world_m: np.ndarray) -> np.ndarray:
    """World coordinates to robot base coordinates. The two differ by height only."""
    point = np.asarray(point_world_m, dtype=float)
    return np.asarray(point - np.array([0.0, 0.0, BASE_HEIGHT_M]), dtype=float)


def base_to_world(point_base_m: np.ndarray) -> np.ndarray:
    """Robot base coordinates to world coordinates."""
    point = np.asarray(point_base_m, dtype=float)
    return np.asarray(point + np.array([0.0, 0.0, BASE_HEIGHT_M]), dtype=float)


def pose_world_to_base(pose: Pose2D) -> Pose2D:
    """Retag a planar world pose as a base-frame pose.

    The base frame is the world frame translated in z, so a planar pose's x, y
    and yaw are unchanged. The function exists so that the frame tag changes in
    exactly one place and no caller ever relabels a pose by hand.
    """
    pose.in_frame(Frame.WORLD)
    return Pose2D(x_m=pose.x_m, y_m=pose.y_m, yaw_rad=pose.yaw_rad, frame=Frame.BASE, stamp_s=pose.stamp_s)
