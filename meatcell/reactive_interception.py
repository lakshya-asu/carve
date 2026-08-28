"""Fail-closed bounded target refresh for a committed interception."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .contracts import Contract, ContractEnum, InterceptionPlan, ObjectTrack, SimTime, TrackLifecycle, Transform, Vector3
from .frames import compose


class ReactiveUpdateReason(ContractEnum):
    APPLIED = "applied"
    BELOW_DEADBAND = "below_deadband"
    IDENTITY_MISMATCH = "identity_mismatch"
    STALE = "stale"
    NO_RETURN = "no_return"
    PLC_BLOCKED = "plc_blocked"
    EMERGENCY_STOP = "emergency_stop"
    TRACK_NOT_CONFIRMED = "track_not_confirmed"
    SEQUENCE_REJECTED = "sequence_rejected"
    UPDATE_LIMIT = "update_limit"
    TOTAL_CORRECTION_LIMIT = "total_correction_limit"
    OSCILLATION = "oscillation"


@dataclass(frozen=True)
class ReactiveInterceptionConfig:
    no_return_lead_s: float = 0.25
    maximum_observation_age_s: float = 0.15
    maximum_cartesian_correction_m: float = 0.025
    maximum_total_correction_m: float = 0.050
    maximum_yaw_correction_rad: float = math.radians(5.0)
    maximum_update_count: int = 3
    deadband_m: float = 0.010
    deadband_yaw_rad: float = math.radians(3.0)
    oscillation_threshold_m: float = 0.005
    correction_quantum_m: float = 0.020
    yaw_correction_quantum_rad: float = math.radians(4.0)

    def __post_init__(self) -> None:
        for name in (
            "no_return_lead_s",
            "maximum_observation_age_s",
            "maximum_cartesian_correction_m",
            "maximum_total_correction_m",
            "maximum_yaw_correction_rad",
            "deadband_m",
            "deadband_yaw_rad",
            "oscillation_threshold_m",
            "correction_quantum_m",
            "yaw_correction_quantum_rad",
        ):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if self.maximum_total_correction_m < self.maximum_cartesian_correction_m:
            raise ValueError("maximum_total_correction_m cannot be smaller than one correction")
        if self.maximum_update_count < 1:
            raise ValueError("maximum_update_count must be positive")
        if self.correction_quantum_m > self.maximum_cartesian_correction_m:
            raise ValueError("correction_quantum_m cannot exceed one correction")
        if self.yaw_correction_quantum_rad > self.maximum_yaw_correction_rad:
            raise ValueError("yaw_correction_quantum_rad cannot exceed one yaw correction")


@dataclass(frozen=True)
class ReactiveUpdateDecision(Contract):
    accepted: bool
    reason: ReactiveUpdateReason
    sequence: int
    observation_age_s: float
    no_return_time: SimTime
    raw_correction_m: Vector3
    applied_correction_m: Vector3
    raw_yaw_correction_rad: float
    applied_yaw_correction_rad: float
    target_pose_world: Transform | None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("Reactive update sequence must be positive")
        if self.accepted != (self.target_pose_world is not None):
            raise ValueError("Accepted reactive updates must contain exactly one target pose")
        if self.accepted != (self.reason is ReactiveUpdateReason.APPLIED):
            raise ValueError("Accepted reactive updates must use reason APPLIED")


def _angle_delta(target: float, current: float) -> float:
    return math.atan2(math.sin(target - current), math.cos(target - current))


def _quantize(value: float, quantum: float) -> float:
    steps = math.floor(abs(value) / quantum + 0.5)
    return math.copysign(steps * quantum, value) if steps else 0.0


def _reject(
    reason: ReactiveUpdateReason,
    *,
    sequence: int,
    age_s: float,
    no_return_time: SimTime,
    raw: Vector3 = Vector3(0.0, 0.0, 0.0),
    raw_yaw: float = 0.0,
) -> ReactiveUpdateDecision:
    return ReactiveUpdateDecision(
        False,
        reason,
        sequence,
        age_s,
        no_return_time,
        raw,
        Vector3(0.0, 0.0, 0.0),
        raw_yaw,
        0.0,
        None,
    )


def propose_reactive_update(
    *,
    plan: InterceptionPlan,
    track: ObjectTrack,
    now: SimTime,
    current_target_world: Transform,
    sequence: int,
    last_sequence: int,
    applied_count: int,
    previous_applied_correction_m: Vector3 | None,
    plc_ready: bool,
    emergency_stop: bool,
    config: ReactiveInterceptionConfig = ReactiveInterceptionConfig(),
) -> ReactiveUpdateDecision:
    """Propose one bounded correction without bypassing execution gates."""

    no_return_time = SimTime(
        plan.intercept_at.nanoseconds - SimTime.from_seconds(config.no_return_lead_s).nanoseconds
    )
    age_s = now.seconds - track.last_exposure_time.seconds
    common = {"sequence": sequence, "age_s": age_s, "no_return_time": no_return_time}
    if emergency_stop:
        return _reject(ReactiveUpdateReason.EMERGENCY_STOP, **common)
    if not plc_ready:
        return _reject(ReactiveUpdateReason.PLC_BLOCKED, **common)
    if track.track_id != plan.track_id or plan.grasp.track_id != plan.track_id:
        return _reject(ReactiveUpdateReason.IDENTITY_MISMATCH, **common)
    if track.lifecycle is not TrackLifecycle.CONFIRMED:
        return _reject(ReactiveUpdateReason.TRACK_NOT_CONFIRMED, **common)
    if sequence <= last_sequence:
        return _reject(ReactiveUpdateReason.SEQUENCE_REJECTED, **common)
    if applied_count >= config.maximum_update_count:
        return _reject(ReactiveUpdateReason.UPDATE_LIMIT, **common)
    if now >= no_return_time:
        return _reject(ReactiveUpdateReason.NO_RETURN, **common)
    if age_s < 0.0 or age_s > config.maximum_observation_age_s:
        return _reject(ReactiveUpdateReason.STALE, **common)

    remaining_s = max(0.0, plan.intercept_at.seconds - track.state_time.seconds)
    product_at_intercept = Transform.planar(
        track.pose_belt.translation.x_m + track.twist_belt.linear_mps.x_m * remaining_s,
        track.pose_belt.translation.y_m + track.twist_belt.linear_mps.y_m * remaining_s,
        track.pose_belt.translation.z_m + track.twist_belt.linear_mps.z_m * remaining_s,
        track.pose_belt.yaw_rad + track.twist_belt.angular_radps.z_m * remaining_s,
    )
    requested = compose(product_at_intercept, plan.grasp.grasp_in_product)
    raw = Vector3(
        requested.translation.x_m - current_target_world.translation.x_m,
        requested.translation.y_m - current_target_world.translation.y_m,
        requested.translation.z_m - current_target_world.translation.z_m,
    )
    raw_yaw = _angle_delta(requested.yaw_rad, current_target_world.yaw_rad)
    raw_norm = math.sqrt(raw.x_m * raw.x_m + raw.y_m * raw.y_m + raw.z_m * raw.z_m)
    if raw_norm <= config.deadband_m and abs(raw_yaw) <= config.deadband_yaw_rad:
        return _reject(ReactiveUpdateReason.BELOW_DEADBAND, raw=raw, raw_yaw=raw_yaw, **common)

    total = Vector3(
        requested.translation.x_m - plan.interception_pose_world.translation.x_m,
        requested.translation.y_m - plan.interception_pose_world.translation.y_m,
        requested.translation.z_m - plan.interception_pose_world.translation.z_m,
    )
    total_norm = math.sqrt(total.x_m * total.x_m + total.y_m * total.y_m + total.z_m * total.z_m)
    if total_norm > config.maximum_total_correction_m:
        return _reject(ReactiveUpdateReason.TOTAL_CORRECTION_LIMIT, raw=raw, raw_yaw=raw_yaw, **common)

    if previous_applied_correction_m is not None:
        previous_norm = math.sqrt(
            previous_applied_correction_m.x_m**2
            + previous_applied_correction_m.y_m**2
            + previous_applied_correction_m.z_m**2
        )
        dot = (
            raw.x_m * previous_applied_correction_m.x_m
            + raw.y_m * previous_applied_correction_m.y_m
            + raw.z_m * previous_applied_correction_m.z_m
        )
        if raw_norm >= config.oscillation_threshold_m and previous_norm >= config.oscillation_threshold_m and dot < 0.0:
            return _reject(ReactiveUpdateReason.OSCILLATION, raw=raw, raw_yaw=raw_yaw, **common)

    scale = min(1.0, config.maximum_cartesian_correction_m / max(raw_norm, 1e-12))
    bounded = Vector3(raw.x_m * scale, raw.y_m * scale, raw.z_m * scale)
    quantized = Vector3(
        _quantize(bounded.x_m, config.correction_quantum_m),
        _quantize(bounded.y_m, config.correction_quantum_m),
        _quantize(bounded.z_m, config.correction_quantum_m),
    )
    quantized_norm = math.sqrt(
        quantized.x_m * quantized.x_m
        + quantized.y_m * quantized.y_m
        + quantized.z_m * quantized.z_m
    )
    if quantized_norm > config.maximum_cartesian_correction_m:
        components = (quantized.x_m, quantized.y_m, quantized.z_m)
        dominant_index = max(range(3), key=lambda index: abs(components[index]))
        dominant = [0.0, 0.0, 0.0]
        dominant[dominant_index] = components[dominant_index]
        applied = Vector3(*dominant)
    else:
        applied = quantized
    bounded_yaw = max(-config.maximum_yaw_correction_rad, min(config.maximum_yaw_correction_rad, raw_yaw))
    applied_yaw = _quantize(bounded_yaw, config.yaw_correction_quantum_rad)
    if (
        abs(applied.x_m) < 1e-12
        and abs(applied.y_m) < 1e-12
        and abs(applied.z_m) < 1e-12
        and abs(applied_yaw) < 1e-12
    ):
        return _reject(ReactiveUpdateReason.BELOW_DEADBAND, raw=raw, raw_yaw=raw_yaw, **common)
    target = Transform.planar(
        current_target_world.translation.x_m + applied.x_m,
        current_target_world.translation.y_m + applied.y_m,
        current_target_world.translation.z_m + applied.z_m,
        current_target_world.yaw_rad + applied_yaw,
    )
    target_total = Vector3(
        target.translation.x_m - plan.interception_pose_world.translation.x_m,
        target.translation.y_m - plan.interception_pose_world.translation.y_m,
        target.translation.z_m - plan.interception_pose_world.translation.z_m,
    )
    target_total_norm = math.sqrt(
        target_total.x_m * target_total.x_m
        + target_total.y_m * target_total.y_m
        + target_total.z_m * target_total.z_m
    )
    if target_total_norm > config.maximum_total_correction_m + 1e-12:
        return _reject(ReactiveUpdateReason.TOTAL_CORRECTION_LIMIT, raw=raw, raw_yaw=raw_yaw, **common)
    return ReactiveUpdateDecision(
        True,
        ReactiveUpdateReason.APPLIED,
        sequence,
        age_s,
        no_return_time,
        raw,
        applied,
        raw_yaw,
        applied_yaw,
        target,
    )
