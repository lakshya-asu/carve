# Carve ROS 2 and MoveIt workspace

This workspace contains the external planning boundary for the Isaac Sim cell.
It does not install ROS 2 or MoveIt.

Prerequisites:

- ROS 2 Humble
- MoveIt 2 for Humble
- `control_msgs`, `moveit_msgs`, `moveit_ros_move_group`, and `moveit_configs_utils`
- the vendored `fanuc_m10_description` package copied or linked into `src`

Build and launch:

```bash
cp -r ../assets/vendor/fanuc_description/fanuc_m10_description src/
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
ros2 launch carve_moveit_config isaac_moveit.launch.py
```

Start Isaac Sim separately with `scripts/validate_scene2_ros.ps1`. When
`control_msgs` is available in Isaac's ROS environment, the simulator exposes
`/carve/arm_controller/follow_joint_trajectory` and MoveIt executes against the
actual Isaac articulation.

The checked-in package is statically tested in this repository. A live MoveIt
run requires an existing authorized ROS 2 environment and remains a separate
commissioning gate.

