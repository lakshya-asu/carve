import pytest

from meatcell.follow_joint_trajectory import (
    FollowJointTrajectoryExecution,
    TrajectoryExecutionStatus,
    TrajectoryTolerances,
)
from meatcell.trajectory import JointTrajectoryCommand, TrajectoryPoint


def command() -> JointTrajectoryCommand:
    return JointTrajectoryCommand(
        ("J1", "J2"),
        (
            TrajectoryPoint(0.0, (0.0, 0.0)),
            TrajectoryPoint(1.0, (1.0, -1.0)),
        ),
    )


def test_execution_uses_supplied_simulation_clock_and_succeeds() -> None:
    execution = FollowJointTrajectoryExecution()
    execution.start(command(), measured_positions=(0.0, 0.0), sim_seconds=10.0)
    halfway = execution.update(measured_positions=(0.5, -0.5), sim_seconds=10.5)
    assert halfway.status == TrajectoryExecutionStatus.ACTIVE
    assert halfway.desired_positions == pytest.approx((0.5, -0.5))
    complete = execution.update(measured_positions=(1.0, -1.0), sim_seconds=11.0)
    assert complete.status == TrajectoryExecutionStatus.SUCCEEDED


def test_execution_rejects_large_start_error() -> None:
    execution = FollowJointTrajectoryExecution(TrajectoryTolerances(start_position_rad=0.1))
    with pytest.raises(ValueError, match="start error"):
        execution.start(command(), measured_positions=(0.2, 0.0), sim_seconds=0.0)


def test_execution_aborts_on_path_tolerance() -> None:
    execution = FollowJointTrajectoryExecution(TrajectoryTolerances(path_position_rad=0.05))
    execution.start(command(), measured_positions=(0.0, 0.0), sim_seconds=0.0)
    update = execution.update(measured_positions=(0.0, 0.0), sim_seconds=0.5)
    assert update.status == TrajectoryExecutionStatus.ABORTED
    assert "Path tolerance" in update.message


def test_execution_waits_for_goal_tolerance_then_aborts() -> None:
    execution = FollowJointTrajectoryExecution(
        TrajectoryTolerances(path_position_rad=2.0, goal_position_rad=0.01, goal_time_s=0.2)
    )
    execution.start(command(), measured_positions=(0.0, 0.0), sim_seconds=0.0)
    waiting = execution.update(measured_positions=(0.9, -0.9), sim_seconds=1.1)
    assert waiting.status == TrajectoryExecutionStatus.ACTIVE
    failed = execution.update(measured_positions=(0.9, -0.9), sim_seconds=1.21)
    assert failed.status == TrajectoryExecutionStatus.ABORTED
    assert "Goal tolerance" in failed.message


def test_execution_cancels_without_another_command() -> None:
    execution = FollowJointTrajectoryExecution()
    execution.start(command(), measured_positions=(0.0, 0.0), sim_seconds=0.0)
    execution.cancel()
    update = execution.update(measured_positions=(0.0, 0.0), sim_seconds=0.1)
    assert update.status == TrajectoryExecutionStatus.CANCELED

