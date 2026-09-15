"""Grasp pipeline for one arm: belt state, grasp policy and the arm's executor.

    ros2 launch meat_cell_ros grasp_pipeline.launch.py arm:=ur20 policy:=shank-at-fraction

Expects, from elsewhere: `joint_states` carrying the arm joints and the belt joint, `leg/perception`
from the perception side, MoveIt's move_group (for `compute_ik`) and the arm's trajectory
controller. `meat_cell_sim` must be importable (PYTHONPATH to the lab repo's src).
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    """Three nodes; the arm is chosen by which config file the executor loads."""
    arm = LaunchConfiguration("arm")
    policy = LaunchConfiguration("policy")
    tilt = LaunchConfiguration("tool_tilt_deg")
    return LaunchDescription(
        [
            DeclareLaunchArgument("arm", default_value="ur20", description="ur20 or sr20ia: which config/<arm>.yaml"),
            DeclareLaunchArgument("policy", default_value="shank-at-fraction", description="Grasp policy name"),
            DeclareLaunchArgument("tool_tilt_deg", default_value="0.0", description="Tool lean the policy asks for"),
            Node(package="meat_cell_ros", executable="belt_state_node", name="belt_state"),
            Node(
                package="meat_cell_ros",
                executable="grasp_policy_node",
                name="grasp_policy",
                parameters=[{"policy": policy, "tool_tilt_deg": tilt}],
            ),
            Node(
                package="meat_cell_ros",
                executable="grasp_executor_node",
                name="grasp_executor",
                parameters=[PathJoinSubstitution([FindPackageShare("meat_cell_ros"), "config", [arm, ".yaml"]])],
            ),
        ]
    )
