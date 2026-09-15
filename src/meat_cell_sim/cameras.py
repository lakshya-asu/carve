"""Overhead depth cameras, modelled from their datasheets.

Two candidates for the camera over the belt, chosen by Lakshya on 2026-09-15 to be
compared in simulation before one is bought: the Orbbec Gemini 335L and the
RealSense D455. Each is described by the fields its vendor publishes, and the
simulated depth image is built from those fields rather than from one shared
guess, so a difference between the two cameras in simulation traces back to a
difference on their datasheets.

What the model covers
---------------------
Lens: horizontal and vertical fields of view give separate focal lengths, so
pixels need not be square. MuJoCo 3.12 cameras accept a resolution and focal
lengths in pixels, and the cell sets both.

Depth noise: active stereo triangulates, so its error grows with the square of
range. Intel publishes the model:

    RMS (m) = Z^2 x subpixel / (focal length px x baseline m)

with a subpixel matching error "< 0.1 and even approaching 0.05" on a textured
target. That is a floor: measured noise on a white wall runs three to five times
higher (`library/topics/depth-primary-segmentation.md`, section 2), and no
measurement on wet meat exists. `measured_over_floor` scales the floor when a
bench measurement arrives.

Readout: depth is rounded to the camera's depth unit, lost outside its range,
and lost where the colour image is saturated, because a specular highlight is
also where stereo matching fails.

Not modelled: spatially correlated stereo noise, flying pixels at edges,
auto-exposure, IR interference between cameras, and USB timing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import mujoco
import numpy as np

from meat_cell_sim.appearance import depth_dropout_where_specular
from meat_cell_sim.frames import Intrinsics

# Physical pixel pitch given to MuJoCo. It only sets the units MuJoCo stores the
# focal lengths in; the image geometry depends on focal length in pixels alone.
PIXEL_PITCH_M = 3.0e-6
MOUNT_BODY = "overhead_cam_mount"

# Intel's typical stereo matching error on a textured target, pixels
# (dev.realsenseai.com, "Tuning depth cameras for best performance"). Applied to
# both cameras; for the Orbbec camera it is an assumption.
TYPICAL_SUBPIXEL_PX = 0.08


@dataclass(frozen=True)
class DepthCameraModel:
    """One RGB-D camera as its datasheet describes it.

    Attributes:
        name: Camera name in the MuJoCo model.
        label: Product name, for tables and video captions.
        width_px: Depth image width.
        height_px: Depth image height.
        frame_rate_hz: Depth frame rate at that resolution.
        hfov_deg: Depth horizontal field of view.
        vfov_deg: Depth vertical field of view.
        baseline_m: Distance between the stereo imagers.
        min_range_m: Nearest usable depth.
        max_range_m: Farthest usable depth.
        depth_unit_m: Smallest depth step the camera reports.
        subpixel_px: Stereo matching error the noise model assumes.
        measured_over_floor: Multiplier on the theoretical noise; 1 until measured.
        washdown: Ingress rating as published, or "none".
        sources: Where each field comes from.
    """

    name: str
    label: str
    width_px: int
    height_px: int
    frame_rate_hz: float
    hfov_deg: float
    vfov_deg: float
    baseline_m: float
    min_range_m: float
    max_range_m: float
    depth_unit_m: float = 0.001
    subpixel_px: float = TYPICAL_SUBPIXEL_PX
    measured_over_floor: float = 1.0
    washdown: str = "none"
    sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not (0.0 < self.hfov_deg < 180.0 and 0.0 < self.vfov_deg < 180.0):
            raise ValueError(f"{self.label}: fields of view must be in (0, 180) degrees")
        if not 0.0 < self.min_range_m < self.max_range_m:
            raise ValueError(f"{self.label}: need 0 < min range < max range")
        if self.baseline_m <= 0.0 or self.depth_unit_m <= 0.0 or self.subpixel_px <= 0.0:
            raise ValueError(f"{self.label}: baseline, depth unit and subpixel must be positive")

    @property
    def intrinsics(self) -> Intrinsics:
        """Pinhole model of the depth image, with the principal point at the image centre."""
        return Intrinsics(
            fx=0.5 * self.width_px / math.tan(math.radians(self.hfov_deg) / 2.0),
            fy=0.5 * self.height_px / math.tan(math.radians(self.vfov_deg) / 2.0),
            cx=(self.width_px - 1) / 2.0,
            cy=(self.height_px - 1) / 2.0,
            width_px=self.width_px,
            height_px=self.height_px,
        )

    def depth_rms_m(self, range_m: float | np.ndarray) -> float | np.ndarray:
        """Depth noise standard deviation at a range, metres."""
        floor = np.square(range_m) * self.subpixel_px / (self.intrinsics.fx * self.baseline_m)
        return floor * self.measured_over_floor

    def ground_sample_m(self, range_m: float) -> float:
        """Width of one pixel on a surface facing the camera at `range_m`, metres."""
        return range_m / self.intrinsics.fx


def add_depth_camera(
    spec: mujoco.MjSpec, camera: DepthCameraModel, mount_body: str = MOUNT_BODY, yaw_deg: float = 0.0
) -> None:
    """Mount a depth camera looking straight down from `mount_body`, with its datasheet lens.

    The camera takes its resolution and separate focal lengths in pixels, so
    MuJoCo renders the datasheet's fields of view rather than a square-pixel
    approximation. The offscreen buffer is raised if the camera needs more.

    Args:
        spec: Cell spec to add the camera to.
        camera: The camera model.
        mount_body: Body the camera hangs from, looking along its -z.
        yaw_deg: Rotation about the vertical. At 0 the image width runs along the
            belt; at 90 it runs across the belt.
    """
    intr = camera.intrinsics
    mounted = spec.body(mount_body).add_camera(name=camera.name)
    half_yaw = math.radians(yaw_deg) / 2.0
    mounted.quat = [math.cos(half_yaw), 0.0, 0.0, math.sin(half_yaw)]
    mounted.resolution = [camera.width_px, camera.height_px]
    mounted.sensor_size = [camera.width_px * PIXEL_PITCH_M, camera.height_px * PIXEL_PITCH_M]
    mounted.focal_pixel = [intr.fx, intr.fy]
    mounted.principal_pixel = [0.0, 0.0]
    spec.visual.global_.offwidth = max(spec.visual.global_.offwidth, camera.width_px)
    spec.visual.global_.offheight = max(spec.visual.global_.offheight, camera.height_px)


def intrinsics_from_model(model: mujoco.MjModel, camera_id: int) -> Intrinsics | None:
    """Pixel intrinsics of a camera declared with a resolution and sensor size, else None.

    MuJoCo stores focal lengths in the sensor's length units; dividing by the
    pixel pitch recovers them in pixels.
    """
    sensor_w, sensor_h = (float(v) for v in model.cam_sensorsize[camera_id])
    if sensor_w <= 0.0 or sensor_h <= 0.0:
        return None
    width, height = (int(v) for v in model.cam_resolution[camera_id])
    focal_x, focal_y, principal_x, principal_y = (float(v) for v in model.cam_intrinsic[camera_id])
    return Intrinsics(
        fx=focal_x * width / sensor_w,
        fy=focal_y * height / sensor_h,
        cx=(width - 1) / 2.0 + principal_x * width / sensor_w,
        cy=(height - 1) / 2.0 + principal_y * height / sensor_h,
        width_px=width,
        height_px=height,
    )


def sense_depth(
    true_depth_m: np.ndarray, camera: DepthCameraModel, rng: np.random.Generator, rgb: np.ndarray | None = None
) -> np.ndarray:
    """What the camera reports for a noiseless depth render.

    Args:
        true_depth_m: (H, W) float, rendered depth along the optical axis, metres.
        camera: The camera model.
        rng: Noise source; seed it per run.
        rgb: (H, W, 3) uint8 colour image of the same frame; saturated pixels lose
            depth. None skips that term.

    Returns:
        (H, W) float32 depth in metres, 0 where the camera returns nothing.
    """
    depth = true_depth_m.astype(np.float64)
    noisy = depth + rng.normal(0.0, 1.0, depth.shape) * camera.depth_rms_m(depth)
    noisy = np.round(noisy / camera.depth_unit_m) * camera.depth_unit_m
    noisy[(depth < camera.min_range_m) | (depth > camera.max_range_m)] = 0.0
    out = noisy.astype(np.float32)
    if rgb is not None:
        out = depth_dropout_where_specular(out, rgb)
    return np.asarray(out)


GEMINI_335L = DepthCameraModel(
    name="gemini_335l",
    label="Orbbec Gemini 335L",
    width_px=1280,
    height_px=800,
    frame_rate_hz=30.0,
    hfov_deg=90.0,
    vfov_deg=65.0,
    baseline_m=0.095,
    min_range_m=0.17,
    max_range_m=20.0,
    washdown="IP65",
    sources=("https://www.orbbec.com/products/stereo-vision-camera/gemini-335l/",),
)

REALSENSE_D455 = DepthCameraModel(
    name="realsense_d455",
    label="RealSense D455",
    width_px=1280,
    height_px=720,
    frame_rate_hz=90.0,
    hfov_deg=86.0,
    vfov_deg=57.0,
    # Baseline from library/hardware/depth-cameras.md; Intel's spec page does not list it.
    baseline_m=0.095,
    min_range_m=0.6,
    max_range_m=6.0,
    sources=(
        "https://www.intel.com/content/www/us/en/products/sku/205847/intel-realsense-depth-camera-d455/specifications.html",
    ),
)

DEPTH_CAMERAS: tuple[DepthCameraModel, ...] = (GEMINI_335L, REALSENSE_D455)
