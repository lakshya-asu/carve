from __future__ import annotations

import math
from typing import Any

from .models import EpisodeResult, Failure, Scenario
from .physics import available_friction_force_n, required_hold_force_n, trapezoidal_motion_time_s


def _candidate_intercept(config: dict[str, Any], scenario: Scenario) -> tuple[float, float, float] | None:
    conveyor = config["conveyor"]
    robot = config["robot"]
    estimated_now_x = (
        scenario.observation_position_error_m
        + scenario.encoder_speed_mps * (scenario.latency_s + scenario.timestamp_error_s)
    )
    move_time = trapezoidal_motion_time_s(
        robot["home_to_pick_distance_m"],
        robot["max_tcp_speed_mps"],
        robot["max_tcp_accel_mps2"],
    )
    required = (
        move_time
        + robot["grasp_close_s"]
        + robot["command_latency_s"]
        + robot["timing_reserve_s"]
    )
    if robot["max_tcp_speed_mps"] < 1.1 * scenario.belt_speed_mps:
        return None

    x = conveyor["pick_x_min_m"]
    while x <= conveyor["pick_x_max_m"] + 1e-9:
        time_after_decision = (x - estimated_now_x) / scenario.encoder_speed_mps
        if time_after_decision >= required:
            return x, scenario.latency_s + time_after_decision, time_after_decision - required
        x += conveyor["candidate_step_m"]
    return None


def _capture_and_hold(
    config: dict[str, Any], scenario: Scenario, result: EpisodeResult
) -> EpisodeResult | None:
    candidate = _candidate_intercept(config, scenario)
    if candidate is None:
        return result.fail(Failure.UNREACHABLE)

    intercept_x, intercept_t, margin = candidate
    result.intercept_x_m = intercept_x
    result.intercept_time_s = intercept_t
    result.motion_margin_s = margin

    actual_x = scenario.belt_speed_mps * intercept_t
    capture_position_error = abs(
        intercept_x
        - actual_x
        + scenario.calibration_position_error_m
        + scenario.actuation_position_error_m
    )
    capture_angle_error = abs(
        scenario.observation_angle_error_deg
        + scenario.yaw_rate_deg_s * scenario.timestamp_error_s
        + scenario.calibration_angle_error_deg
        + scenario.actuation_angle_error_deg
    )
    result.capture_position_error_m = capture_position_error
    result.capture_angle_error_deg = capture_angle_error

    gripper = config["gripper"]
    if capture_position_error > gripper["pick_position_tolerance_m"]:
        return result.fail(Failure.CAPTURE_POSITION)
    if capture_angle_error > gripper["pick_angle_tolerance_deg"]:
        return result.fail(Failure.CAPTURE_ANGLE)

    pressure = gripper["normal_force_n"] / gripper["contact_area_m2"]
    result.grip_pressure_pa = pressure
    if pressure > gripper["max_pressure_pa"]:
        return result.fail(Failure.EXCESSIVE_FORCE)

    available = available_friction_force_n(
        scenario.friction,
        gripper["normal_force_n"],
        int(gripper["contact_count"]),
    )
    required = required_hold_force_n(scenario.mass_kg, config["robot"]["transfer_accel_mps2"])
    result.hold_margin = available / required
    if result.hold_margin < 1.0:
        return result.fail(Failure.INSUFFICIENT_HOLD)

    result.slipped = (
        abs(scenario.slip_position_error_m) > 0.005
        or abs(scenario.slip_angle_error_deg) > 1.5
    )
    return None


def evaluate_direct(config: dict[str, Any], scenario: Scenario) -> EpisodeResult:
    result = EpisodeResult(episode=scenario.episode, architecture="direct")
    if not scenario.detected:
        return result.fail(Failure.MISSED_DETECTION)
    if scenario.latency_s >= 0.12:
        return result.fail(Failure.STALE_TARGET)
    failed = _capture_and_hold(config, scenario, result)
    if failed is not None:
        return failed
    if not scenario.cutter_ready:
        return result.fail(Failure.CUTTER_NOT_READY)

    cutting = config["cutting"]
    pick_time_error = result.capture_position_error_m / scenario.belt_speed_mps
    result.placement_position_error_m = abs(
        scenario.calibration_position_error_m
        + scenario.actuation_position_error_m
        + scenario.slip_position_error_m
        + scenario.z_cut_position * cutting["direct_position_sigma_m"]
    )
    result.placement_angle_error_deg = abs(
        scenario.calibration_angle_error_deg
        + scenario.actuation_angle_error_deg
        + scenario.slip_angle_error_deg
        + scenario.z_cut_angle * cutting["direct_angle_sigma_deg"]
    )
    result.placement_timing_error_s = abs(
        pick_time_error + scenario.z_cut_timing * cutting["direct_timing_sigma_s"]
    )
    result.placement_speed_error_mps = abs(
        scenario.z_cut_speed * cutting["direct_speed_sigma_mps"]
    )
    result.cycle_time_s = result.intercept_time_s + trapezoidal_motion_time_s(
        config["robot"]["transfer_distance_m"],
        config["robot"]["max_tcp_speed_mps"],
        config["robot"]["max_tcp_accel_mps2"],
    )
    return _placement_gate(config, result)


def evaluate_buffered(config: dict[str, Any], scenario: Scenario) -> EpisodeResult:
    result = EpisodeResult(episode=scenario.episode, architecture="buffered")
    if not scenario.detected:
        return result.fail(Failure.MISSED_DETECTION)
    if scenario.latency_s >= 0.12:
        return result.fail(Failure.STALE_TARGET)
    failed = _capture_and_hold(config, scenario, result)
    if failed is not None:
        return failed

    buffer_cfg = config["buffer"]
    if scenario.cutter_block_s > buffer_cfg["max_hold_s"]:
        return result.fail(Failure.BUFFER_TIMEOUT)

    result.placement_position_error_m = abs(
        (scenario.calibration_position_error_m + scenario.actuation_position_error_m + scenario.slip_position_error_m)
        * buffer_cfg["centering_position_factor"]
        + scenario.z_cut_position * buffer_cfg["feed_position_sigma_m"]
    )
    result.placement_angle_error_deg = abs(
        (scenario.calibration_angle_error_deg + scenario.actuation_angle_error_deg + scenario.slip_angle_error_deg)
        * buffer_cfg["centering_angle_factor"]
        + scenario.z_cut_angle * buffer_cfg["feed_angle_sigma_deg"]
    )
    result.placement_timing_error_s = abs(
        scenario.z_cut_timing * buffer_cfg["feed_timing_sigma_s"]
    )
    result.placement_speed_error_mps = abs(
        scenario.z_cut_speed * buffer_cfg["feed_speed_sigma_mps"]
    )
    result.cycle_time_s = (
        result.intercept_time_s
        + trapezoidal_motion_time_s(
            config["robot"]["transfer_distance_m"],
            config["robot"]["max_tcp_speed_mps"],
            config["robot"]["max_tcp_accel_mps2"],
        )
        + buffer_cfg["settle_s"]
        + scenario.cutter_block_s
        + buffer_cfg["feed_s"]
    )
    return _placement_gate(config, result)


def _placement_gate(config: dict[str, Any], result: EpisodeResult) -> EpisodeResult:
    cutting = config["cutting"]
    checks = (
        (result.placement_position_error_m, cutting["position_tolerance_m"], Failure.PLACEMENT_POSITION),
        (result.placement_angle_error_deg, cutting["angle_tolerance_deg"], Failure.PLACEMENT_ANGLE),
        (result.placement_timing_error_s, cutting["timing_tolerance_s"], Failure.PLACEMENT_TIMING),
        (result.placement_speed_error_mps, cutting["speed_tolerance_mps"], Failure.PLACEMENT_SPEED),
    )
    for value, limit, failure in checks:
        if value is None or value > limit:
            return result.fail(failure)
    result.success = True
    result.failure = Failure.NONE
    return result


def evaluate(config: dict[str, Any], scenario: Scenario) -> EpisodeResult:
    architecture = config["architecture"]
    if architecture == "direct":
        return evaluate_direct(config, scenario)
    if architecture == "buffered":
        return evaluate_buffered(config, scenario)
    raise ValueError(f"Unsupported architecture: {architecture}")
