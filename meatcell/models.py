from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class Failure(str, Enum):
    NONE = "none"
    MISSED_DETECTION = "missed_detection"
    STALE_TARGET = "stale_target"
    UNREACHABLE = "unreachable"
    CAPTURE_POSITION = "capture_position"
    CAPTURE_ANGLE = "capture_angle"
    EXCESSIVE_FORCE = "excessive_force"
    INSUFFICIENT_HOLD = "insufficient_hold"
    CUTTER_NOT_READY = "cutter_not_ready"
    BUFFER_TIMEOUT = "buffer_timeout"
    PLACEMENT_POSITION = "placement_position"
    PLACEMENT_ANGLE = "placement_angle"
    PLACEMENT_TIMING = "placement_timing"
    PLACEMENT_SPEED = "placement_speed"


@dataclass(frozen=True)
class Scenario:
    episode: int
    detected: bool
    belt_speed_mps: float
    encoder_speed_mps: float
    latency_s: float
    timestamp_error_s: float
    observation_position_error_m: float
    observation_angle_error_deg: float
    yaw_rate_deg_s: float
    mass_kg: float
    friction: float
    calibration_position_error_m: float
    calibration_angle_error_deg: float
    actuation_position_error_m: float
    actuation_angle_error_deg: float
    slip_position_error_m: float
    slip_angle_error_deg: float
    cutter_ready: bool
    cutter_block_s: float
    z_cut_position: float
    z_cut_angle: float
    z_cut_timing: float
    z_cut_speed: float


@dataclass
class EpisodeResult:
    episode: int
    architecture: str
    success: bool = False
    failure: Failure = Failure.NONE
    intercept_x_m: float | None = None
    intercept_time_s: float | None = None
    motion_margin_s: float | None = None
    capture_position_error_m: float | None = None
    capture_angle_error_deg: float | None = None
    grip_pressure_pa: float | None = None
    hold_margin: float | None = None
    slipped: bool = False
    placement_position_error_m: float | None = None
    placement_angle_error_deg: float | None = None
    placement_timing_error_s: float | None = None
    placement_speed_error_mps: float | None = None
    cycle_time_s: float | None = None

    def fail(self, reason: Failure) -> "EpisodeResult":
        self.failure = reason
        self.success = False
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
