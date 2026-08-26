"""In-process ROS 2 probe used by the Scene 2.0 integration gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from isaac_sim.scene2_ros_bridge import JOINT_NAMES, Ros2TopicNames


@dataclass
class ProbeSnapshot:
    clocks: int = 0
    joint_states: int = 0
    rgb_images: int = 0
    depth_images: int = 0
    camera_info: int = 0
    last_rgb_bytes: int = 0
    last_depth_bytes: int = 0
    last_joint_positions: tuple[float, ...] = ()


class Scene2RosProbe:
    """Observe bridge publications and issue checked joint commands."""

    def __init__(self, topics: Ros2TopicNames | None = None) -> None:
        import rclpy
        from rosgraph_msgs.msg import Clock
        from sensor_msgs.msg import CameraInfo, Image, JointState

        self._rclpy = rclpy
        self._JointState = JointState
        self.topics = topics or Ros2TopicNames()
        self.snapshot = ProbeSnapshot()
        self.node = rclpy.create_node("carve_scene2_integration_probe")
        self.command_pub = self.node.create_publisher(JointState, self.topics.joint_command, 10)
        self.node.create_subscription(Clock, self.topics.clock, self._on_clock, 10)
        self.node.create_subscription(JointState, self.topics.joint_states, self._on_joint_state, 10)
        self.node.create_subscription(Image, self.topics.rgb, self._on_rgb, 2)
        self.node.create_subscription(Image, self.topics.depth, self._on_depth, 2)
        self.node.create_subscription(CameraInfo, self.topics.camera_info, self._on_camera_info, 2)
        self.commands_published = 0

    def _on_clock(self, _message: Any) -> None:
        self.snapshot.clocks += 1

    def _on_joint_state(self, message: Any) -> None:
        self.snapshot.joint_states += 1
        self.snapshot.last_joint_positions = tuple(float(value) for value in message.position)

    def _on_rgb(self, message: Any) -> None:
        self.snapshot.rgb_images += 1
        self.snapshot.last_rgb_bytes = len(message.data)

    def _on_depth(self, message: Any) -> None:
        self.snapshot.depth_images += 1
        self.snapshot.last_depth_bytes = len(message.data)

    def _on_camera_info(self, _message: Any) -> None:
        self.snapshot.camera_info += 1

    def publish_command(self, positions: tuple[float, ...]) -> None:
        message = self._JointState()
        message.name = list(JOINT_NAMES)
        message.position = list(positions)
        self.command_pub.publish(message)
        self.commands_published += 1

    def publish_invalid_partial_command(self, positions: tuple[float, ...]) -> None:
        message = self._JointState()
        message.name = list(JOINT_NAMES[:-1])
        message.position = list(positions[:-1])
        self.command_pub.publish(message)
        self.commands_published += 1

    def spin_once(self) -> None:
        self._rclpy.spin_once(self.node, timeout_sec=0.0)

    def close(self) -> None:
        self.node.destroy_node()
