from __future__ import annotations

import math
from collections import Counter
from typing import Any, Callable

from .models import EpisodeResult


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return ordered[low]
    weight = index - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _values(results: list[EpisodeResult], getter: Callable[[EpisodeResult], float | None]) -> list[float]:
    return [value for result in results if (value := getter(result)) is not None]


def summarize(results: list[EpisodeResult]) -> dict[str, Any]:
    count = len(results)
    successes = sum(result.success for result in results)
    failures = Counter(result.failure.value for result in results if not result.success)
    cycle_times = _values(results, lambda item: item.cycle_time_s if item.success else None)
    placement_positions = _values(results, lambda item: item.placement_position_error_m)
    placement_angles = _values(results, lambda item: item.placement_angle_error_deg)
    placement_timing = _values(results, lambda item: item.placement_timing_error_s)
    capture_positions = _values(results, lambda item: item.capture_position_error_m)
    margins = _values(results, lambda item: item.motion_margin_s)
    hold_margins = _values(results, lambda item: item.hold_margin)
    mean_cycle = sum(cycle_times) / len(cycle_times) if cycle_times else None

    upper_bound_cycles_per_min = 60.0 / mean_cycle if mean_cycle else None
    expected_successes_per_min = (
        upper_bound_cycles_per_min * successes / count
        if upper_bound_cycles_per_min is not None and count
        else None
    )

    return {
        "architecture": results[0].architecture if results else None,
        "episodes": count,
        "successes": successes,
        "success_rate": successes / count if count else 0.0,
        "failure_counts": dict(sorted(failures.items())),
        "slip_observation_rate": sum(item.slipped for item in results) / count if count else 0.0,
        "cycle_time_s": {
            "mean": mean_cycle,
            "p50": percentile(cycle_times, 0.50),
            "p95": percentile(cycle_times, 0.95),
        },
        "sequential_service_upper_bound_cycles_per_min": upper_bound_cycles_per_min,
        "screening_expected_successes_per_min": expected_successes_per_min,
        "capture_position_error_m": {
            "p50": percentile(capture_positions, 0.50),
            "p95": percentile(capture_positions, 0.95),
        },
        "placement_position_error_m": {
            "p50": percentile(placement_positions, 0.50),
            "p95": percentile(placement_positions, 0.95),
        },
        "placement_angle_error_deg": {
            "p50": percentile(placement_angles, 0.50),
            "p95": percentile(placement_angles, 0.95),
        },
        "placement_timing_error_s": {
            "p50": percentile(placement_timing, 0.50),
            "p95": percentile(placement_timing, 0.95),
        },
        "motion_margin_s": {
            "p05": percentile(margins, 0.05),
            "p50": percentile(margins, 0.50),
        },
        "hold_margin": {
            "p05": percentile(hold_margins, 0.05),
            "p50": percentile(hold_margins, 0.50),
        },
    }
