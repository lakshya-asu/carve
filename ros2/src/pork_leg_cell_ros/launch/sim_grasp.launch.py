"""The whole grasp chain against the simulated cell: bridge, IK, belt state, policy, executor.

    ros2 launch pork_leg_cell_ros sim_grasp.launch.py arm:=ur20
    ros2 launch pork_leg_cell_ros sim_grasp.launch.py arm:=sr20ia tool_tilt_deg:=15   # refused before motion

For the UR20, IK comes from MoveIt's move_group (cell_moveit_config); for the SR-20iA from
scara_ik_node. Everything runs on the simulator's clock. Needs the ros_moveit environment and
the repository's src/ on PYTHONPATH.
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchContext, LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def _nodes(context: LaunchContext) -> list:
    arm = LaunchConfiguration("arm").perform(context)
    sim_time = {"use_sim_time": True}
    nodes = [
        Node(
            package="pork_leg_cell_ros",
            executable="mujoco_bridge_node",
            name="mujoco_bridge",
            output="screen",
            parameters=[
                {
                    "arm": arm,
                    "belt_speed_mps": float(LaunchConfiguration("belt_speed_mps").perform(context)),
                    "arrival_yaw_deg": float(LaunchConfiguration("arrival_yaw_deg").perform(context)),
                }
            ],
        ),
        Node(
            package="meat_cell_ros",
            executable="belt_state_node",
            name="belt_state",
            parameters=[{"belt_joint": "belt_x"}, sim_time],
        ),
        Node(
            package="meat_cell_ros",
            executable="grasp_policy_node",
            name="grasp_policy",
            output="screen",
            parameters=[
                {
                    "policy": LaunchConfiguration("policy"),
                    "tool_tilt_deg": float(LaunchConfiguration("tool_tilt_deg").perform(context)),
                },
                sim_time,
            ],
        ),
        Node(
            package="meat_cell_ros",
            executable="grasp_executor_node",
            name="grasp_executor",
            output="screen",
            parameters=[PathJoinSubstitution([FindPackageShare("meat_cell_ros"), "config", f"{arm}.yaml"])],
        ),
    ]
    if arm == "ur20":
        nodes.append(
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare("cell_moveit_config"), "launch", "move_group.launch.py"])
                ),
                launch_arguments={"arm": arm}.items(),
            )
        )
    else:
        urdf = Path(get_package_share_directory("cell_description")) / "urdf" / f"{arm}_cell.urdf"
        nodes += [
            Node(package="pork_leg_cell_ros", executable="scara_ik_node", name="scara_ik", parameters=[sim_time]),
            # move_group brings its own for the UR20; the executor reads the tool position from TF.
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=[{"robot_description": urdf.read_text()}, sim_time],
            ),
        ]
    return nodes


def generate_launch_description() -> LaunchDescription:
    """The grasp chain for one arm against the simulator."""
    return LaunchDescription(
        [
            DeclareLaunchArgument("arm", default_value="ur20", description="ur20 or sr20ia"),
            DeclareLaunchArgument("policy", default_value="shank-at-fraction"),
            DeclareLaunchArgument("tool_tilt_deg", default_value="0.0"),
            DeclareLaunchArgument("belt_speed_mps", default_value="0.30"),
            DeclareLaunchArgument("arrival_yaw_deg", default_value="0.0"),
            OpaqueFunction(function=_nodes),
        ]
    )
