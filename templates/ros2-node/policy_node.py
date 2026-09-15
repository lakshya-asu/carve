"""Template ROS 2 node that runs a learned policy at a fixed rate with a watchdog.

Pattern: subscribe to observations, hold the latest, tick a timer at the
control rate, publish an action only if observations are fresh. Stop
publishing (safe default) if observations go stale.
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSPresetProfiles
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray


class PolicyNode(Node):
    """Runs a policy at `control_rate_hz` with an observation staleness watchdog."""

    def __init__(self) -> None:
        """Declare parameters, then build the timer and subscriptions from them."""
        super().__init__("policy_node")
        self.declare_parameter("control_rate_hz", 20.0)
        self.declare_parameter("obs_timeout_s", 0.2)
        rate_hz = self.get_parameter("control_rate_hz").get_parameter_value().double_value
        self._obs_timeout_s = self.get_parameter("obs_timeout_s").get_parameter_value().double_value

        self._latest_obs: JointState | None = None
        self._latest_obs_time = self.get_clock().now()

        self._obs_sub = self.create_subscription(
            JointState, "joint_states", self._on_obs, QoSPresetProfiles.SENSOR_DATA.value
        )
        self._cmd_pub = self.create_publisher(Float64MultiArray, "policy_action", 10)
        self._timer = self.create_timer(1.0 / rate_hz, self._tick)
        self.get_logger().info(f"policy_node running at {rate_hz:.1f} Hz, timeout {self._obs_timeout_s:.2f} s")

    def _on_obs(self, msg: JointState) -> None:
        self._latest_obs = msg
        self._latest_obs_time = self.get_clock().now()

    def _tick(self) -> None:
        if self._latest_obs is None:
            return
        age_s = (self.get_clock().now() - self._latest_obs_time).nanoseconds * 1e-9
        if age_s > self._obs_timeout_s:
            self.get_logger().warn(f"observation stale ({age_s:.3f} s), holding", throttle_duration_sec=1.0)
            return
        action = self._policy(self._latest_obs)
        self._cmd_pub.publish(Float64MultiArray(data=action))

    def _policy(self, obs: JointState) -> list[float]:
        """Replace with the real policy. Must be bounded by the safety limits."""
        return [0.0] * len(obs.position)


def main() -> None:
    """Entry point."""
    rclpy.init()
    node = PolicyNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
