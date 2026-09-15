"""Belt state from the encoder: travel, speed and acceleration for the intercept planner.

Subscribes to the belt joint in `joint_states` (the encoder, as ros2_control's joint state
broadcaster publishes it; position is travel in metres) and publishes `belt/state`.

QoS: `joint_states` with the sensor-data profile (best effort, keep last 5), because a late encoder
sample is worth nothing and must not queue; `belt/state` reliable, keep last 10, because the
executor must never plan against a dropped state.
"""

from __future__ import annotations

import rclpy
from meat_cell_msgs.msg import BeltState
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.node import Node
from rclpy.qos import QoSProfile, qos_profile_sensor_data
from sensor_msgs.msg import JointState

from meat_cell_ros.conversions import belt_state_to_msg, seconds
from meat_cell_sim.belt_state import BeltStateEstimator


class BeltStateNode(Node):
    """Fits travel, speed and acceleration over a sliding window of encoder readings."""

    def __init__(self) -> None:
        """Declare parameters and wire the subscription and publisher."""
        super().__init__("belt_state")
        self.joint = self.declare_parameter(
            "belt_joint",
            "belt_joint",
            ParameterDescriptor(description="Joint in joint_states whose position is belt travel, m"),
        ).value
        window_s = self.declare_parameter(
            "window_s", 0.3, ParameterDescriptor(description="Encoder history the fit uses, s")
        ).value
        self.estimator = BeltStateEstimator(window_s=float(window_s))
        self.publisher = self.create_publisher(BeltState, "belt/state", QoSProfile(depth=10))
        self.create_subscription(JointState, "joint_states", self.on_joint_states, qos_profile_sensor_data)

    def on_joint_states(self, msg: JointState) -> None:
        """Fold one encoder reading in and publish the state once the fit has enough readings."""
        if self.joint not in msg.name:
            return
        travel_m = msg.position[msg.name.index(self.joint)]
        try:
            state = self.estimator.update(seconds(msg.header.stamp), float(travel_m))
        except ValueError as error:
            self.get_logger().warning(f"encoder reading dropped: {error}")
            return
        if state is not None:
            self.publisher.publish(belt_state_to_msg(state))


def main() -> None:
    """Run the node until shutdown."""
    rclpy.init()
    node = BeltStateNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
