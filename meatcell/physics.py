from __future__ import annotations

import math


GRAVITY_MPS2 = 9.80665


def latency_travel_m(speed_mps: float, latency_s: float) -> float:
    return speed_mps * latency_s


def trapezoidal_motion_time_s(distance_m: float, max_speed_mps: float, max_accel_mps2: float) -> float:
    """Minimum symmetric rest-to-rest time under speed and acceleration limits."""
    if distance_m < 0 or max_speed_mps <= 0 or max_accel_mps2 <= 0:
        raise ValueError("Distance must be nonnegative and limits must be positive")
    accel_distance = max_speed_mps * max_speed_mps / max_accel_mps2
    if distance_m <= accel_distance:
        return 2.0 * math.sqrt(distance_m / max_accel_mps2)
    return 2.0 * max_speed_mps / max_accel_mps2 + (distance_m - accel_distance) / max_speed_mps


def required_hold_force_n(mass_kg: float, transfer_accel_mps2: float) -> float:
    return mass_kg * math.hypot(GRAVITY_MPS2, transfer_accel_mps2)


def available_friction_force_n(friction: float, normal_force_n: float, contact_count: int) -> float:
    return max(0.0, friction) * normal_force_n * contact_count
