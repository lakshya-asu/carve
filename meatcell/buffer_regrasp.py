"""Deterministic stabilization for RGBD buffer regrasp proposals."""

from __future__ import annotations

import math

from .contracts import Transform


def _quantize(value: float, quantum: float) -> float:
    steps = math.floor(abs(value) / quantum + 0.5)
    return math.copysign(steps * quantum, value) if steps else 0.0


def stabilize_buffer_regrasp_pose(
    observed_pose: Transform,
    *,
    translation_quantum_m: float = 0.010,
    yaw_quantum_rad: float = math.radians(2.0),
) -> Transform:
    """Snap a live RGBD proposal to a bounded deterministic execution grid."""

    if not math.isfinite(translation_quantum_m) or translation_quantum_m <= 0.0:
        raise ValueError("translation_quantum_m must be finite and positive")
    if not math.isfinite(yaw_quantum_rad) or yaw_quantum_rad <= 0.0:
        raise ValueError("yaw_quantum_rad must be finite and positive")
    return Transform.planar(
        _quantize(observed_pose.translation.x_m, translation_quantum_m),
        _quantize(observed_pose.translation.y_m, translation_quantum_m),
        _quantize(observed_pose.translation.z_m, translation_quantum_m),
        _quantize(observed_pose.yaw_rad, yaw_quantum_rad),
    )
