"""MoveIt move_group and robot_state_publisher for one of the cell's arms.

    ros2 launch cell_moveit_config move_group.launch.py arm:=ur20

Loads the generated URDF from cell_description and this package's SRDF, kinematics, joint limits,
OMPL and controller settings for that arm. Uses simulation time: the MuJoCo bridge publishes /clock.
"""

from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchContext, LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _nodes(context: LaunchContext) -> list:
    arm = LaunchConfiguration("arm").perform(context)
    description = Path(get_package_share_directory("cell_description")) / "urdf" / f"{arm}_cell.urdf"
    config = Path(get_package_share_directory("cell_moveit_config")) / "config" / arm

    def load(name: str) -> dict:
        return yaml.safe_load((config / name).read_text()) or {}

    robot_description = {"robot_description": description.read_text()}
    parameters = [
        robot_description,
        {"robot_description_semantic": (config / f"{arm}_cell.srdf").read_text()},
        {"robot_description_kinematics": load("kinematics.yaml")},
        {"robot_description_planning": load("joint_limits.yaml")},
        {"planning_pipelines": ["ompl"], "ompl": load("ompl_planning.yaml")},
        load("moveit_controllers.yaml"),
        {"use_sim_time": True, "publish_robot_description_semantic": True},
    ]
    return [
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            parameters=[robot_description, {"use_sim_time": True}],
        ),
        Node(package="moveit_ros_move_group", executable="move_group", output="screen", parameters=parameters),
    ]


def generate_launch_description() -> LaunchDescription:
    """move_group for the arm named by the `arm` argument."""
    return LaunchDescription(
        [
            DeclareLaunchArgument("arm", default_value="ur20", description="ur20 or sr20ia"),
            OpaqueFunction(function=_nodes),
        ]
    )
