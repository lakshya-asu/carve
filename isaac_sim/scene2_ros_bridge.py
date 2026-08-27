"""ROS 2 core-message bridge for the Scene 2.0 Isaac cell.

The module imports ROS packages only when a bridge is constructed. This keeps
ordinary unit tests independent of the Isaac Sim bundled ROS environment.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


JOINT_NAMES = ("J1", "J2", "J3", "J4", "J5", "J6")


@dataclass(frozen=True)
class Ros2TopicNames:
    clock: str = "/clock"
    joint_states: str = "/carve/joint_states"
    joint_command: str = "/carve/robot/joint_command"
    rgb: str = "/carve/camera/overhead/color/image_raw"
    depth: str = "/carve/camera/overhead/depth/image_rect_raw"
    camera_info: str = "/carve/camera/overhead/camera_info"


@dataclass(frozen=True)
class JointCommand:
    positions: tuple[float, ...]
    velocities: tuple[float, ...] | None
    sequence: int


def validate_joint_command(
    names: list[str] | tuple[str, ...],
    positions: list[float] | tuple[float, ...],
    velocities: list[float] | tuple[float, ...],
    lower: tuple[float, ...],
    upper: tuple[float, ...],
) -> tuple[tuple[float, ...], tuple[float, ...] | None]:
    if tuple(names) != JOINT_NAMES:
        raise ValueError(f"Expected exact joint order {JOINT_NAMES}, received {tuple(names)}")
    if len(positions) != len(JOINT_NAMES):
        raise ValueError("A command must contain all six joint positions")
    position_tuple = tuple(float(value) for value in positions)
    if not all(math.isfinite(value) for value in position_tuple):
        raise ValueError("Joint positions must be finite")
    if any(value < low or value > high for value, low, high in zip(position_tuple, lower, upper, strict=True)):
        raise ValueError("Joint command exceeds an imported FANUC limit")
    velocity_tuple: tuple[float, ...] | None = None
    if velocities:
        if len(velocities) != len(JOINT_NAMES):
            raise ValueError("Joint velocity commands must contain all six joints")
        velocity_tuple = tuple(float(value) for value in velocities)
        if not all(math.isfinite(value) for value in velocity_tuple):
            raise ValueError("Joint velocities must be finite")
    return position_tuple, velocity_tuple


class Scene2RosBridge:
    def __init__(
        self,
        articulation: Any,
        camera: Any,
        *,
        lower_limits: tuple[float, ...],
        upper_limits: tuple[float, ...],
        joint_indices: tuple[int, ...] = tuple(range(6)),
        topics: Ros2TopicNames | None = None,
    ) -> None:
        import rclpy
        from rosgraph_msgs.msg import Clock
        from sensor_msgs.msg import CameraInfo, Image, JointState

        if not rclpy.ok():
            rclpy.init()
        self._rclpy = rclpy
        self._Clock = Clock
        self._CameraInfo = CameraInfo
        self._Image = Image
        self._JointState = JointState
        self.articulation = articulation
        self.camera = camera
        self.lower_limits = lower_limits
        self.upper_limits = upper_limits
        if len(joint_indices) != len(JOINT_NAMES):
            raise ValueError("The ROS bridge requires six FANUC articulation indices")
        self.joint_indices = joint_indices
        self.topics = topics or Ros2TopicNames()
        self.node = rclpy.create_node("carve_isaac_scene2")
        self.clock_pub = self.node.create_publisher(Clock, self.topics.clock, 10)
        self.joint_pub = self.node.create_publisher(JointState, self.topics.joint_states, 10)
        self.rgb_pub = self.node.create_publisher(Image, self.topics.rgb, 2)
        self.depth_pub = self.node.create_publisher(Image, self.topics.depth, 2)
        self.info_pub = self.node.create_publisher(CameraInfo, self.topics.camera_info, 2)
        self.command_sub = self.node.create_subscription(
            JointState, self.topics.joint_command, self._command_callback, 10
        )
        self._latest_command: JointCommand | None = None
        self._command_sequence = 0
        self.rejected_commands = 0
        self.published_clock = 0
        self.published_joint_states = 0
        self.published_rgb = 0
        self.published_depth = 0
        self.last_rejection = ""

    @staticmethod
    def _stamp(seconds: float) -> Any:
        from builtin_interfaces.msg import Time

        whole = int(seconds)
        nanoseconds = int(round((seconds - whole) * 1_000_000_000))
        if nanoseconds >= 1_000_000_000:
            whole += 1
            nanoseconds -= 1_000_000_000
        return Time(sec=whole, nanosec=nanoseconds)

    def _command_callback(self, message: Any) -> None:
        try:
            positions, velocities = validate_joint_command(
                message.name,
                message.position,
                message.velocity,
                self.lower_limits,
                self.upper_limits,
            )
        except ValueError as exc:
            self.rejected_commands += 1
            self.last_rejection = str(exc)
            return
        self._command_sequence += 1
        self._latest_command = JointCommand(positions, velocities, self._command_sequence)

    def spin_once(self) -> None:
        self._rclpy.spin_once(self.node, timeout_sec=0.0)

    def consume_command(self) -> JointCommand | None:
        command = self._latest_command
        self._latest_command = None
        return command

    def publish_clock(self, sim_seconds: float) -> None:
        message = self._Clock()
        message.clock = self._stamp(sim_seconds)
        self.clock_pub.publish(message)
        self.published_clock += 1

    def publish_joint_state(self, sim_seconds: float) -> None:
        message = self._JointState()
        message.header.stamp = self._stamp(sim_seconds)
        message.header.frame_id = "base_link"
        message.name = list(JOINT_NAMES)
        positions = self.articulation.get_joint_positions()
        velocities = self.articulation.get_joint_velocities()
        message.position = [float(positions[index]) for index in self.joint_indices]
        message.velocity = [float(velocities[index]) for index in self.joint_indices]
        self.joint_pub.publish(message)
        self.published_joint_states += 1

    def publish_camera(self, sim_seconds: float) -> None:
        import numpy as np

        rgb = self.camera.get_rgb()
        depth = self.camera.get_depth()
        if rgb is None or depth is None:
            return
        rgb_array = np.asarray(rgb)
        if rgb_array.dtype != np.uint8:
            multiplier = 255.0 if float(rgb_array.max(initial=0.0)) <= 1.0 else 1.0
            rgb_array = np.clip(rgb_array * multiplier, 0, 255).astype(np.uint8)
        rgb_array = np.ascontiguousarray(rgb_array[..., :3])
        depth_array = np.ascontiguousarray(np.asarray(depth, dtype=np.float32))
        stamp = self._stamp(sim_seconds)

        rgb_message = self._Image()
        rgb_message.header.stamp = stamp
        rgb_message.header.frame_id = "overhead_camera_optical"
        rgb_message.height, rgb_message.width = rgb_array.shape[:2]
        rgb_message.encoding = "rgb8"
        rgb_message.is_bigendian = False
        rgb_message.step = rgb_message.width * 3
        rgb_message.data = rgb_array.tobytes()
        self.rgb_pub.publish(rgb_message)

        depth_message = self._Image()
        depth_message.header.stamp = stamp
        depth_message.header.frame_id = "overhead_camera_optical"
        depth_message.height, depth_message.width = depth_array.shape
        depth_message.encoding = "32FC1"
        depth_message.is_bigendian = False
        depth_message.step = depth_message.width * 4
        depth_message.data = depth_array.tobytes()
        self.depth_pub.publish(depth_message)

        intrinsics = np.asarray(self.camera.get_intrinsics_matrix(), dtype=float)
        info = self._CameraInfo()
        info.header.stamp = stamp
        info.header.frame_id = "overhead_camera_optical"
        info.height = rgb_message.height
        info.width = rgb_message.width
        info.distortion_model = "plumb_bob"
        info.d = [0.0] * 5
        info.k = intrinsics.reshape(-1).tolist()
        info.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        info.p = [
            intrinsics[0, 0], 0.0, intrinsics[0, 2], 0.0,
            0.0, intrinsics[1, 1], intrinsics[1, 2], 0.0,
            0.0, 0.0, 1.0, 0.0,
        ]
        self.info_pub.publish(info)
        self.published_rgb += 1
        self.published_depth += 1

    def close(self) -> None:
        self.node.destroy_node()

    def metrics(self) -> dict[str, object]:
        return {
            "accepted_commands": self._command_sequence,
            "rejected_commands": self.rejected_commands,
            "last_rejection": self.last_rejection,
            "published_clock": self.published_clock,
            "published_joint_states": self.published_joint_states,
            "published_rgb": self.published_rgb,
            "published_depth": self.published_depth,
        }
