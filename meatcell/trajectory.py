"""Validated, simulation-clock joint trajectory contracts and sampling."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class TrajectoryPoint:
    time_from_start_s: float
    positions: tuple[float, ...]
    velocities: tuple[float, ...] | None = None


@dataclass(frozen=True)
class JointTrajectoryCommand:
    joint_names: tuple[str, ...]
    points: tuple[TrajectoryPoint, ...]
    sequence: int = 0

    @property
    def duration_s(self) -> float:
        return self.points[-1].time_from_start_s


def validate_joint_trajectory(
    *,
    expected_joint_names: tuple[str, ...],
    joint_names: Iterable[str],
    points: Iterable[TrajectoryPoint],
    lower_limits: tuple[float, ...],
    upper_limits: tuple[float, ...],
) -> JointTrajectoryCommand:
    names = tuple(joint_names)
    values = tuple(points)
    if names != expected_joint_names:
        raise ValueError(f"Expected exact joint order {expected_joint_names}, received {names}")
    if len(lower_limits) != len(names) or len(upper_limits) != len(names):
        raise ValueError("Trajectory limit vectors must match the joint count")
    if len(values) < 2:
        raise ValueError("A trajectory must contain at least two points")
    previous_time = -math.inf
    for point in values:
        if not math.isfinite(point.time_from_start_s) or point.time_from_start_s < 0.0:
            raise ValueError("Trajectory times must be finite and nonnegative")
        if point.time_from_start_s <= previous_time:
            raise ValueError("Trajectory times must be strictly increasing")
        previous_time = point.time_from_start_s
        if len(point.positions) != len(names):
            raise ValueError("Every trajectory point must contain every joint")
        if not all(math.isfinite(value) for value in point.positions):
            raise ValueError("Trajectory positions must be finite")
        if any(value < low or value > high for value, low, high in zip(point.positions, lower_limits, upper_limits, strict=True)):
            raise ValueError("Trajectory point exceeds an imported joint limit")
        if point.velocities is not None:
            if len(point.velocities) != len(names) or not all(math.isfinite(value) for value in point.velocities):
                raise ValueError("Trajectory velocities must be finite and complete")
    return JointTrajectoryCommand(names, values)


def sample_joint_trajectory(command: JointTrajectoryCommand, elapsed_s: float) -> tuple[float, ...]:
    """Sample positions with smooth-step interpolation on simulation time."""
    if not math.isfinite(elapsed_s):
        raise ValueError("Trajectory sample time must be finite")
    if elapsed_s <= command.points[0].time_from_start_s:
        return command.points[0].positions
    if elapsed_s >= command.points[-1].time_from_start_s:
        return command.points[-1].positions
    for left, right in zip(command.points, command.points[1:]):
        if elapsed_s <= right.time_from_start_s:
            phase = (elapsed_s - left.time_from_start_s) / (right.time_from_start_s - left.time_from_start_s)
            blend = phase * phase * (3.0 - 2.0 * phase)
            return tuple(
                start + (finish - start) * blend
                for start, finish in zip(left.positions, right.positions, strict=True)
            )
    raise RuntimeError("Trajectory sampler did not find a segment")
