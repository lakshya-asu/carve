"""One captured camera frame and the geometry needed to interpret it.

Written by whatever reads a camera (the simulated cell's `Sensors`, or a driver) and read by
perception, so it sits below both.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from robotics.core.frames import CameraPose, Intrinsics


@dataclass(frozen=True)
class CameraFrameData:
    """One captured frame and the geometry needed to interpret it.

    Attributes:
        stamp_s: Simulation time at the middle of the exposure.
        rgb: (H, W, 3) uint8.
        depth_m: (H, W) float32, distance along the optical axis in metres.
        intrinsics: Pinhole model matching this render.
        camera: Where the camera was during the exposure, world frame.
    """

    stamp_s: float
    rgb: np.ndarray
    depth_m: np.ndarray
    intrinsics: Intrinsics
    camera: CameraPose
