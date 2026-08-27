cmake_minimum_required(VERSION 3.8)
project(carve_moveit_demo)

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(moveit_ros_planning_interface REQUIRED)
find_package(rclcpp REQUIRED)

add_executable(plan_to_pose src/plan_to_pose.cpp)
ament_target_dependencies(plan_to_pose geometry_msgs moveit_ros_planning_interface rclcpp)
install(TARGETS plan_to_pose DESTINATION lib/${PROJECT_NAME})

ament_package()

