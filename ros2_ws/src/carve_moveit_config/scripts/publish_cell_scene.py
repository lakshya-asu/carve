#!/usr/bin/env python3
"""Publish the fixed Isaac cell obstacles to MoveIt's planning scene."""

from pathlib import Path

import rclpy
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Pose
from moveit_msgs.msg import CollisionObject, PlanningScene
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from shape_msgs.msg import SolidPrimitive
import yaml


class CellScenePublisher(Node):
    def __init__(self) -> None:
        super().__init__("carve_cell_scene_publisher")
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.publisher = self.create_publisher(PlanningScene, "/planning_scene", qos)
        path = Path(get_package_share_directory("carve_moveit_config")) / "config" / "cell_collision_objects.yaml"
        self.description = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.timer = self.create_timer(0.5, self.publish_once)

    def publish_once(self) -> None:
        scene = PlanningScene()
        scene.is_diff = True
        frame_id = self.description["frame_id"]
        for item in self.description["objects"]:
            collision = CollisionObject()
            collision.header.frame_id = frame_id
            collision.id = item["id"]
            box = SolidPrimitive()
            box.type = SolidPrimitive.BOX
            box.dimensions = [float(value) for value in item["size"]]
            pose = Pose()
            pose.position.x, pose.position.y, pose.position.z = [float(value) for value in item["position"]]
            pose.orientation.w = 1.0
            collision.primitives.append(box)
            collision.primitive_poses.append(pose)
            collision.operation = CollisionObject.ADD
            scene.world.collision_objects.append(collision)
        self.publisher.publish(scene)
        self.get_logger().info(f"Published {len(scene.world.collision_objects)} Isaac cell collision objects")
        self.timer.cancel()


def main() -> None:
    rclpy.init()
    node = CellScenePublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

