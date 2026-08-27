from launch import LaunchDescription
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder


def generate_launch_description() -> LaunchDescription:
    moveit_config = (
        MoveItConfigsBuilder("carve_m10id12", package_name="carve_moveit_config")
        .robot_description(file_path="robot/carve_m10id12.urdf.xacro")
        .robot_description_semantic(file_path="config/carve_m10id12.srdf")
        .robot_description_kinematics(file_path="config/kinematics.yaml")
        .joint_limits(file_path="config/joint_limits.yaml")
        .trajectory_execution(file_path="config/moveit_controllers.yaml")
        .planning_pipelines(pipelines=["ompl"])
        .to_moveit_configs()
    )
    common_parameters = [moveit_config.to_dict(), {"use_sim_time": True}]
    return LaunchDescription(
        [
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=common_parameters,
                remappings=[("/joint_states", "/carve/joint_states")],
                output="screen",
            ),
            Node(
                package="moveit_ros_move_group",
                executable="move_group",
                parameters=common_parameters,
                remappings=[("/joint_states", "/carve/joint_states")],
                output="screen",
            ),
            Node(
                package="carve_moveit_config",
                executable="publish_cell_scene.py",
                parameters=[{"use_sim_time": True}],
                output="screen",
            ),
        ]
    )

