import math

import pytest

from isaac_sim.scene2_ros_bridge import JOINT_NAMES, Ros2TopicNames, validate_joint_command


LOWER = tuple([-math.pi] * 6)
UPPER = tuple([math.pi] * 6)


def test_ros_topics_are_namespaced_and_clock_is_global() -> None:
    topics = Ros2TopicNames()
    assert topics.clock == "/clock"
    for value in (topics.joint_states, topics.joint_command, topics.rgb, topics.depth, topics.camera_info):
        assert value.startswith("/carve/")


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

