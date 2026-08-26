"""Replaceable vision-model interface shared by rendered and learned adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .contracts import ObjectObservation, SimTime


@dataclass(frozen=True)
class PinholeCalibration:
    camera_x_world_m: float
    camera_y_world_m: float
    camera_z_world_m: float
    fx_px: float
    fy_px: float
    cx_px: float
    cy_px: float
    belt_surface_z_world_m: float
    calibration_position_sigma_m: float
    calibration_yaw_sigma_rad: float

    def __post_init__(self) -> None:
        if self.fx_px <= 0.0 or self.fy_px <= 0.0:
            raise ValueError("Pinhole focal lengths must be positive")
        if self.camera_z_world_m <= self.belt_surface_z_world_m:
            raise ValueError("Overhead camera must be above the belt surface")
        if self.calibration_position_sigma_m < 0.0 or self.calibration_yaw_sigma_rad < 0.0:
            raise ValueError("Calibration uncertainty must be nonnegative")


@runtime_checkable
class VisionModel(Protocol):
    model_name: str

    def infer(
        self,
        rgb: Any,
        depth_m: Any,
        exposure_time: SimTime,
        calibration: PinholeCalibration,
    ) -> tuple[ObjectObservation, ...]: ...
