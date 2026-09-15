"""The grasp policy, swappable by a parameter: perceived leg in, arm-agnostic grasp action out.

Subscribes to `leg/perception` and publishes `grasp/action`, both reliable with keep-last 10: each
message is a decision about one leg, and none may be dropped silently. The policy is chosen by the
`policy` parameter; every policy implements `meat_cell_sim.grasp_policy.GraspPolicy`, so adding the
learned one does not change this node's interface or any executor.
"""

from __future__ import annotations

import math

import rclpy
from meat_cell_msgs.msg import GraspAction, LegPerception
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.node import Node
from rclpy.qos import QoSProfile

from meat_cell_ros.conversions import grasp_action_to_msg, leg_perception_from_msg
from meat_cell_sim.grasp_policy import GraspPolicy, GraspRefusedError, ShankGraspRule


class GraspPolicyNode(Node):
    """Runs one grasp policy on every perceived leg."""

    def __init__(self) -> None:
        """Declare parameters, build the policy, and wire topics."""
        super().__init__("grasp_policy")

        def parameter(name: str, default: object, description: str) -> object:
            return self.declare_parameter(name, default, ParameterDescriptor(description=description)).value

        name = str(parameter("policy", "shank-at-fraction", "Which policy decides grasps: shank-at-fraction"))
        if name != ShankGraspRule.name:
            raise ValueError(f"unknown policy {name!r}; the learned policy is not wired into ROS yet")
        max_opening_m = float(parameter("max_opening_m", 0.0, "Gripper's widest opening, m; 0 to skip the check"))
        self.policy: GraspPolicy = ShankGraspRule(
            fraction=float(parameter("shank_fraction", 0.66, "Grasp station as a fraction of length from the ham")),
            spare_opening_m=float(parameter("spare_opening_m", 0.040, "Opening beyond the shank width, m")),
            max_opening_m=max_opening_m or None,
            tool_tilt_rad=math.radians(float(parameter("tool_tilt_deg", 0.0, "Tool lean about the finger axis, deg"))),
            approach_height_m=float(parameter("approach_height_m", 0.15, "Approach distance along the tool axis, m")),
            close_s=float(parameter("close_s", 0.6, "Time for the jaws to close while following the belt, s")),
        )
        self.publisher = self.create_publisher(GraspAction, "grasp/action", QoSProfile(depth=10))
        self.create_subscription(LegPerception, "leg/perception", self.on_leg, QoSProfile(depth=10))
        self.get_logger().info(f"grasp policy: {self.policy.name}")

    def on_leg(self, msg: LegPerception) -> None:
        """Decide and publish a grasp for one leg, or log why the policy refused."""
        try:
            action = self.policy.decide(leg_perception_from_msg(msg))
        except GraspRefusedError as refusal:
            self.get_logger().warning(
                f"no grasp for the leg seen at {msg.header.stamp.sec}.{msg.header.stamp.nanosec:09d}: {refusal}"
            )
            return
        self.publisher.publish(grasp_action_to_msg(action, msg.belt_travel_m))


def main() -> None:
    """Run the node until shutdown."""
    rclpy.init()
    node = GraspPolicyNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
