#include <cmath>
#include <memory>
#include <stdexcept>
#include <thread>

#include <geometry_msgs/msg/pose.hpp>
#include <moveit/move_group_interface/move_group_interface.h>
#include <rclcpp/rclcpp.hpp>

namespace
{
double duration_seconds(const builtin_interfaces::msg::Duration & duration)
{
  return static_cast<double>(duration.sec) + static_cast<double>(duration.nanosec) / 1.0e9;
}

void stretch_trajectory(moveit_msgs::msg::RobotTrajectory & trajectory, double requested_duration_s)
{
  auto & points = trajectory.joint_trajectory.points;
  if (points.empty() || requested_duration_s <= 0.0) {
    return;
  }
  const double planned_duration_s = duration_seconds(points.back().time_from_start);
  if (requested_duration_s + 1.0e-9 < planned_duration_s) {
    throw std::runtime_error("Requested arrival is faster than the time-parameterized plan");
  }
  if (planned_duration_s <= 0.0) {
    throw std::runtime_error("MoveIt returned a trajectory with no duration");
  }
  const double scale = requested_duration_s / planned_duration_s;
  for (auto & point : points) {
    const double seconds = duration_seconds(point.time_from_start) * scale;
    point.time_from_start = rclcpp::Duration::from_seconds(seconds).to_builtin_time();
    for (double & velocity : point.velocities) {
      velocity /= scale;
    }
    for (double & acceleration : point.accelerations) {
      acceleration /= scale * scale;
    }
  }
}
}  // namespace

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto options = rclcpp::NodeOptions().automatically_declare_parameters_from_overrides(true);
  auto node = rclcpp::Node::make_shared("carve_plan_to_pose", options);
  rclcpp::executors::SingleThreadedExecutor executor;
  executor.add_node(node);
  std::thread spin_thread([&executor]() {executor.spin();});

  int exit_code = 1;
  try {
    moveit::planning_interface::MoveGroupInterface move_group(node, "manipulator");
    move_group.setPlanningPipelineId("ompl");
    move_group.setPlannerId("RRTConnect");
    move_group.setPoseReferenceFrame("world");
    move_group.setPlanningTime(node->declare_parameter("planning_time_s", 3.0));
    move_group.setMaxVelocityScalingFactor(node->declare_parameter("velocity_scale", 0.35));
    move_group.setMaxAccelerationScalingFactor(node->declare_parameter("acceleration_scale", 0.30));

    geometry_msgs::msg::Pose target;
    target.position.x = node->declare_parameter("target_x", 1.05);
    target.position.y = node->declare_parameter("target_y", -0.82);
    target.position.z = node->declare_parameter("target_z", 1.20);
    target.orientation.x = node->declare_parameter("target_qx", 0.0);
    target.orientation.y = node->declare_parameter("target_qy", 0.70710678);
    target.orientation.z = node->declare_parameter("target_qz", 0.0);
    target.orientation.w = node->declare_parameter("target_qw", 0.70710678);
    move_group.setPoseTarget(target, "flange");

    moveit::planning_interface::MoveGroupInterface::Plan plan;
    const bool planned = static_cast<bool>(move_group.plan(plan));
    if (!planned) {
      RCLCPP_ERROR(node->get_logger(), "MoveIt found no collision-free path");
    } else {
      stretch_trajectory(plan.trajectory_, node->declare_parameter("requested_duration_s", 0.0));
      const bool plan_only = node->declare_parameter("plan_only", false);
      const bool executed = plan_only || static_cast<bool>(move_group.execute(plan));
      if (executed) {
        RCLCPP_INFO(node->get_logger(), plan_only ? "Plan passed" : "Plan executed through FollowJointTrajectory");
        exit_code = 0;
      } else {
        RCLCPP_ERROR(node->get_logger(), "MoveIt execution failed");
      }
    }
  } catch (const std::exception & error) {
    RCLCPP_ERROR(node->get_logger(), "%s", error.what());
  }

  rclcpp::shutdown();
  executor.cancel();
  spin_thread.join();
  return exit_code;
}

