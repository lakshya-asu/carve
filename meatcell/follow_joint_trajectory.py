"""Runtime-neutral state machine for FollowJointTrajectory execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from meatcell.trajectory import JointTrajectoryCommand, sample_joint_trajectory


class TrajectoryExecutionStatus(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"
    ABORTED = "aborted"


@dataclass(frozen=True)
class TrajectoryTolerances:
    start_position_rad: float = 0.15
    path_position_rad: float = 0.20
    goal_position_rad: float = 0.02
    goal_time_s: float = 0.50


@dataclass(frozen=True)
class TrajectoryExecutionUpdate:
    status: TrajectoryExecutionStatus
    desired_positions: tuple[float, ...] | None
    measured_positions: tuple[float, ...]
    error_positions: tuple[float, ...]
    elapsed_s: float
    message: str = ""


class FollowJointTrajectoryExecution:
    """Validate execution tolerances against measured articulation state.

    Time is supplied by the caller. In Isaac Sim this is the fixed-step
    simulation clock, never wall time.
    """

    def __init__(self, tolerances: TrajectoryTolerances | None = None) -> None:
        self.tolerances = tolerances or TrajectoryTolerances()
        self.command: JointTrajectoryCommand | None = None
        self.started_s: float | None = None
        self.status = TrajectoryExecutionStatus.IDLE
        self.message = ""

    @staticmethod
    def _positions(values: Iterable[float]) -> tuple[float, ...]:
        return tuple(float(value) for value in values)

    def start(
        self,
        command: JointTrajectoryCommand,
        *,
        measured_positions: Iterable[float],
        sim_seconds: float,
    ) -> None:
        measured = self._positions(measured_positions)
        if len(measured) != len(command.joint_names):
            raise ValueError("Measured state does not match the trajectory joint count")
        start_error = max(
            abs(desired - actual)
            for desired, actual in zip(command.points[0].positions, measured, strict=True)
        )
        if start_error > self.tolerances.start_position_rad:
            raise ValueError(
                f"Trajectory start error {start_error:.6f} rad exceeds "
                f"{self.tolerances.start_position_rad:.6f} rad"
            )
        self.command = command
        self.started_s = float(sim_seconds)
        self.status = TrajectoryExecutionStatus.ACTIVE
        self.message = ""

    def cancel(self) -> None:
        if self.status == TrajectoryExecutionStatus.ACTIVE:
            self.status = TrajectoryExecutionStatus.CANCELED
            self.message = "Trajectory canceled"

    def update(
        self,
        *,
        measured_positions: Iterable[float],
        sim_seconds: float,
    ) -> TrajectoryExecutionUpdate:
        measured = self._positions(measured_positions)
        if self.command is None or self.started_s is None:
            return TrajectoryExecutionUpdate(self.status, None, measured, (), 0.0, self.message)
        elapsed = max(0.0, float(sim_seconds) - self.started_s)
        desired = sample_joint_trajectory(self.command, elapsed)
        errors = tuple(
            desired_value - measured_value
            for desired_value, measured_value in zip(desired, measured, strict=True)
        )
        maximum_error = max(abs(value) for value in errors)

        if self.status == TrajectoryExecutionStatus.ACTIVE and elapsed < self.command.duration_s:
            if maximum_error > self.tolerances.path_position_rad:
                self.status = TrajectoryExecutionStatus.ABORTED
                self.message = (
                    f"Path tolerance violated: {maximum_error:.6f} rad exceeds "
                    f"{self.tolerances.path_position_rad:.6f} rad"
                )
        elif self.status == TrajectoryExecutionStatus.ACTIVE:
            if maximum_error <= self.tolerances.goal_position_rad:
                self.status = TrajectoryExecutionStatus.SUCCEEDED
                self.message = "Goal tolerance satisfied"
            elif elapsed > self.command.duration_s + self.tolerances.goal_time_s:
                self.status = TrajectoryExecutionStatus.ABORTED
                self.message = (
                    f"Goal tolerance violated: {maximum_error:.6f} rad exceeds "
                    f"{self.tolerances.goal_position_rad:.6f} rad"
                )

        return TrajectoryExecutionUpdate(
            self.status,
            desired,
            measured,
            errors,
            elapsed,
            self.message,
        )

