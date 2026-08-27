import math

import pytest

from isaac_sim.scene2_ros_bridge import JOINT_NAMES, Ros2TopicNames, validate_joint_command
from meatcell.trajectory import TrajectoryPoint, sample_joint_trajectory, validate_joint_trajectory


LOWER = tuple([-math.pi] * 6)
UPPER = tuple([math.pi] * 6)


def test_ros_topics_are_namespaced_and_clock_is_global() -> None:
    topics = Ros2TopicNames()
    assert topics.clock == "/clock"
    for value in (topics.joint_states, topics.joint_command, topics.joint_trajectory, topics.rgb, topics.depth, topics.camera_info):
        assert value.startswith("/carve/")
    assert topics.follow_joint_trajectory == "/carve/arm_controller/follow_joint_trajectory"


def test_moveit_compatible_joint_trajectory_validates_and_samples() -> None:
    command = validate_joint_trajectory(
        expected_joint_names=JOINT_NAMES,
        joint_names=JOINT_NAMES,
        points=(
            TrajectoryPoint(0.0, (0.0,) * 6),
            TrajectoryPoint(1.0, (1.0,) * 6),
        ),
        lower_limits=LOWER,
        upper_limits=UPPER,
    )
    assert sample_joint_trajectory(command, 0.5) == pytest.approx((0.5,) * 6)
    assert sample_joint_trajectory(command, 1.5) == pytest.approx((1.0,) * 6)


def test_joint_trajectory_rejects_nonmonotonic_time() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        validate_joint_trajectory(
            expected_joint_names=JOINT_NAMES,
            joint_names=JOINT_NAMES,
            points=(TrajectoryPoint(0.0, (0.0,) * 6), TrajectoryPoint(0.0, (0.1,) * 6)),
            lower_limits=LOWER,
            upper_limits=UPPER,
        )


def test_complete_finite_joint_command_passes() -> None:
    positions, velocities = validate_joint_command(
        list(JOINT_NAMES), [0.0, 0.1, 0.2, 0.3, 0.4, 0.5], [], LOWER, UPPER
    )
    assert positions == (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)
    assert velocities is None


@pytest.mark.parametrize(
    ("names", "positions"),
    [
        (list(reversed(JOINT_NAMES)), [0.0] * 6),
        (list(JOINT_NAMES[:-1]), [0.0] * 5),
        (list(JOINT_NAMES), [0.0, 0.0, 0.0, 0.0, 0.0, float("nan")]),
        (list(JOINT_NAMES), [0.0, 0.0, 0.0, 0.0, 0.0, math.pi + 0.01]),
    ],
)
def test_invalid_joint_commands_are_rejected(names: list[str], positions: list[float]) -> None:
    with pytest.raises(ValueError):
        validate_joint_command(names, positions, [], LOWER, UPPER)
