"""ROS 2 core-message bridge for the Scene 2.0 Isaac cell.

The module imports ROS packages only when a bridge is constructed. This keeps
ordinary unit tests independent of the Isaac Sim bundled ROS environment.
"""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import math
from typing import Any

from meatcell.follow_joint_trajectory import (
    FollowJointTrajectoryExecution,
    TrajectoryExecutionStatus,
    TrajectoryTolerances,
)
from meatcell.trajectory import JointTrajectoryCommand, TrajectoryPoint, sample_joint_trajectory, validate_joint_trajectory


JOINT_NAMES = ("J1", "J2", "J3", "J4", "J5", "J6")


@dataclass(frozen=True)
class Ros2TopicNames:
    clock: str = "/clock"
    joint_states: str = "/carve/joint_states"
    joint_command: str = "/carve/robot/joint_command"
    joint_trajectory: str = "/carve/arm_controller/joint_trajectory"
    rgb: str = "/carve/camera/overhead/color/image_raw"
    depth: str = "/carve/camera/overhead/depth/image_rect_raw"
    camera_info: str = "/carve/camera/overhead/camera_info"
    follow_joint_trajectory: str = "/carve/arm_controller/follow_joint_trajectory"


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
        from trajectory_msgs.msg import JointTrajectory

        if not rclpy.ok():
            rclpy.init()
        self._rclpy = rclpy
        self._Clock = Clock
        self._CameraInfo = CameraInfo
        self._Image = Image
        self._JointState = JointState
        self._JointTrajectory = JointTrajectory
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
        self.trajectory_sub = self.node.create_subscription(
            JointTrajectory, self.topics.joint_trajectory, self._trajectory_callback, 10
        )
        self._latest_command: JointCommand | None = None
        self._active_trajectory: JointTrajectoryCommand | None = None
        self._trajectory_started_s: float | None = None
        self._command_sequence = 0
        self.rejected_commands = 0
        self.published_clock = 0
        self.published_joint_states = 0
        self.published_rgb = 0
        self.published_depth = 0
        self.last_rejection = ""
        self.accepted_trajectories = 0
        self.completed_trajectories = 0
        self.action_server_available = False
        self.accepted_action_goals = 0
        self.completed_action_goals = 0
        self.canceled_action_goals = 0
        self.aborted_action_goals = 0
        self._latest_sim_seconds = 0.0
        self._action_goal_handle: Any | None = None
        self._action_execution = FollowJointTrajectoryExecution()
        self._configure_action_server()

    def _configure_action_server(self) -> None:
        """Expose the standard action when control_msgs is in the ROS runtime."""
        try:
            from control_msgs.action import FollowJointTrajectory
            from rclpy.action import ActionServer, CancelResponse, GoalResponse
        except ImportError:
            self._FollowJointTrajectory = None
            self._CancelResponse = None
            self._GoalResponse = None
            self.action_server = None
            return
        self._FollowJointTrajectory = FollowJointTrajectory
        self._CancelResponse = CancelResponse
        self._GoalResponse = GoalResponse
        self.action_server = ActionServer(
            self.node,
            FollowJointTrajectory,
            self.topics.follow_joint_trajectory,
            execute_callback=self._execute_action_goal,
            goal_callback=self._action_goal_callback,
            cancel_callback=self._action_cancel_callback,
        )
        self.action_server_available = True

    def _trajectory_from_message(self, message: Any) -> JointTrajectoryCommand:
        points = tuple(
            TrajectoryPoint(
                self._duration_seconds(item.time_from_start),
                tuple(float(value) for value in item.positions),
                tuple(float(value) for value in item.velocities) if item.velocities else None,
            )
            for item in message.points
        )
        return validate_joint_trajectory(
            expected_joint_names=JOINT_NAMES,
            joint_names=message.joint_names,
            points=points,
            lower_limits=self.lower_limits,
            upper_limits=self.upper_limits,
        )

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

    @staticmethod
    def _duration_seconds(value: Any) -> float:
        return float(value.sec) + float(value.nanosec) / 1_000_000_000.0

    def _trajectory_callback(self, message: Any) -> None:
        if self._action_goal_handle is not None:
            self.rejected_commands += 1
            self.last_rejection = "A FollowJointTrajectory action goal is active"
            return
        try:
            trajectory = self._trajectory_from_message(message)
        except ValueError as exc:
            self.rejected_commands += 1
            self.last_rejection = str(exc)
            return
        self.accepted_trajectories += 1
        self._active_trajectory = JointTrajectoryCommand(
            trajectory.joint_names,
            trajectory.points,
            self.accepted_trajectories,
        )
        self._trajectory_started_s = None

    def _action_goal_callback(self, goal_request: Any) -> Any:
        if self._action_goal_handle is not None or self._active_trajectory is not None:
            return self._GoalResponse.REJECT
        try:
            self._trajectory_from_message(goal_request.trajectory)
        except ValueError as exc:
            self.rejected_commands += 1
            self.last_rejection = str(exc)
            return self._GoalResponse.REJECT
        return self._GoalResponse.ACCEPT

    def _action_cancel_callback(self, goal_handle: Any) -> Any:
        if goal_handle == self._action_goal_handle:
            self._action_execution.cancel()
            return self._CancelResponse.ACCEPT
        return self._CancelResponse.REJECT

    def _measured_joint_positions(self) -> tuple[float, ...]:
        values = self.articulation.get_joint_positions()
        return tuple(float(values[index]) for index in self.joint_indices)

    @staticmethod
    def _largest_positive_tolerance(items: Any, default: float) -> float:
        values = [float(item.position) for item in items if float(item.position) > 0.0]
        return max(values, default=default)

    async def _execute_action_goal(self, goal_handle: Any) -> Any:
        goal = goal_handle.request
        command = self._trajectory_from_message(goal.trajectory)
        requested_goal_time_s = self._duration_seconds(goal.goal_time_tolerance)
        tolerances = TrajectoryTolerances(
            path_position_rad=self._largest_positive_tolerance(goal.path_tolerance, 0.20),
            goal_position_rad=self._largest_positive_tolerance(goal.goal_tolerance, 0.02),
            goal_time_s=requested_goal_time_s if requested_goal_time_s > 0.0 else 0.50,
        )
        self._action_execution = FollowJointTrajectoryExecution(tolerances)
        try:
            self._action_execution.start(
                command,
                measured_positions=self._measured_joint_positions(),
                sim_seconds=self._latest_sim_seconds,
            )
        except ValueError as exc:
            result = self._FollowJointTrajectory.Result()
            result.error_code = self._FollowJointTrajectory.Result.INVALID_GOAL
            result.error_string = str(exc)
            self.aborted_action_goals += 1
            goal_handle.abort()
            return result
        self._action_goal_handle = goal_handle
        self.accepted_action_goals += 1
        while self._action_execution.status == TrajectoryExecutionStatus.ACTIVE:
            await asyncio.sleep(0)
        result = self._FollowJointTrajectory.Result()
        result.error_string = self._action_execution.message
        if self._action_execution.status == TrajectoryExecutionStatus.SUCCEEDED:
            result.error_code = self._FollowJointTrajectory.Result.SUCCESSFUL
            self.completed_action_goals += 1
            goal_handle.succeed()
        elif self._action_execution.status == TrajectoryExecutionStatus.CANCELED:
            result.error_code = self._FollowJointTrajectory.Result.SUCCESSFUL
            self.canceled_action_goals += 1
            goal_handle.canceled()
        else:
            result.error_code = self._FollowJointTrajectory.Result.PATH_TOLERANCE_VIOLATED
            self.aborted_action_goals += 1
            goal_handle.abort()
        self._action_goal_handle = None
        return result

    def spin_once(self) -> None:
        self._rclpy.spin_once(self.node, timeout_sec=0.0)

    def consume_command(self) -> JointCommand | None:
        command = self._latest_command
        self._latest_command = None
        return command

    def consume_trajectory_sample(self, sim_seconds: float) -> JointCommand | None:
        if self._action_goal_handle is not None:
            update = self._action_execution.update(
                measured_positions=self._measured_joint_positions(),
                sim_seconds=sim_seconds,
            )
            if update.status != TrajectoryExecutionStatus.ACTIVE:
                return None
            if update.desired_positions is not None:
                feedback = self._FollowJointTrajectory.Feedback()
                feedback.joint_names = list(JOINT_NAMES)
                feedback.desired.positions = list(update.desired_positions)
                feedback.actual.positions = list(update.measured_positions)
                feedback.error.positions = list(update.error_positions)
                self._action_goal_handle.publish_feedback(feedback)
                self._command_sequence += 1
                return JointCommand(update.desired_positions, None, self._command_sequence)
            return None
        if self._active_trajectory is None:
            return None
        if self._trajectory_started_s is None:
            self._trajectory_started_s = sim_seconds
        elapsed_s = max(0.0, sim_seconds - self._trajectory_started_s)
        positions = sample_joint_trajectory(self._active_trajectory, elapsed_s)
        self._command_sequence += 1
        command = JointCommand(positions, None, self._command_sequence)
        if elapsed_s >= self._active_trajectory.duration_s:
            self.completed_trajectories += 1
            self._active_trajectory = None
            self._trajectory_started_s = None
        return command

    def publish_clock(self, sim_seconds: float) -> None:
        self._latest_sim_seconds = float(sim_seconds)
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
        if self.action_server is not None:
            self.action_server.destroy()
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
            "accepted_trajectories": self.accepted_trajectories,
            "completed_trajectories": self.completed_trajectories,
            "action_server_available": self.action_server_available,
            "accepted_action_goals": self.accepted_action_goals,
            "completed_action_goals": self.completed_action_goals,
            "canceled_action_goals": self.canceled_action_goals,
            "aborted_action_goals": self.aborted_action_goals,
        }
