cmake_minimum_required(VERSION 3.8)
project(carve_moveit_config)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch robot
  DESTINATION share/${PROJECT_NAME}
)
install(PROGRAMS scripts/publish_cell_scene.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()

