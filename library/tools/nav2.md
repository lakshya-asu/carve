---
title: Nav2
date: 2026-09-05
tags: [tool, ros2, nav2, navigation, mobile-manipulation, behavior-tree]
status: draft
source: https://github.com/ros-navigation/navigation2 ; https://docs.nav2.org/rolling/
---

# Nav2

The ROS 2 navigation stack: a behaviour tree that calls planner, controller, smoother,
behaviour, route and docking servers over actions, on top of two costmaps and a lifecycle
manager. For a learning engineer it is what a policy or VLM hands a goal to, and what carries
the base between manipulation episodes. Localization and SLAM choices are in
[state-estimation-and-localization](../topics/state-estimation-and-localization.md#nav2-in-2026).

## Versions (checked 2026-09-05)

| Distro | Branch | Version | Status | What it lacks or adds |
|---|---|---|---|---|
| Humble (our `rosdev`) | `humble` | 1.1.20 | maintained | BT.CPP v3, DWB default controller, no docking or collision monitor in default bringup, `Twist` only |
| Jazzy | `jazzy` | 1.3.13 | active | BT.CPP v4, MPPI default, docking server, `enable_stamped_cmd_vel` (default false), route server |
| Kilted | `kilted` | 1.4.2 | maintained | `TwistStamped` default, `error_code_name_prefixes`, loopback sim, Groot 2 |
| Lyrical | `lyrical` | 1.5.1 | active | `nav2_ros_common`, following server, path handler plugins, RPP `desired_linear_vel` renamed `max_linear_vel` |

Sources: `navigation2/package.xml` per branch, [rosdistro](https://github.com/ros/rosdistro),
[docs distro grid](https://docs.nav2.org/rolling/). The org moved from `ros-planning` to
`ros-navigation` and the docs to `docs.nav2.org` (`/rolling/`, `/jazzy/`, `/lyrical/`;
`/humble/` and `/kilted/` are 404). Migration guides: [Iron to Jazzy](https://docs.nav2.org/rolling/configuration_and_development/migration_guides/iron/Iron/),
[Jazzy to Kilted](https://docs.nav2.org/rolling/configuration_and_development/migration_guides/jazzy/Jazzy/),
[Kilted to Lyrical](https://docs.nav2.org/rolling/configuration_and_development/migration_guides/kilted/Kilted/).

## Bringup structure

`ros2 launch nav2_bringup bringup_launch.py map:=<yaml> params_file:=<nav2_params.yaml>`
includes `localization_launch.py` (map_server plus AMCL, or `slam_launch.py` with
`slam:=True`) and `navigation_launch.py`. Arguments: `namespace`, `autostart true`,
`use_composition True` (one `nav2_container`), `use_respawn False` (non-composed only),
`use_sim_time`, and on main `keepout_mask`, `speed_mask`, `graph`
([bringup_launch.py](https://github.com/ros-navigation/navigation2/blob/main/nav2_bringup/launch/bringup_launch.py)).
`navigation_launch.py` lifecycle nodes on Jazzy: `controller_server`, `smoother_server`,
`planner_server`, `route_server`, `behavior_server`, `velocity_smoother`, `collision_monitor`,
`bt_navigator`, `waypoint_follower`, `docking_server`; Humble has no route, collision
monitor or docking server in the default bringup. The velocity chain is
`controller_server -> cmd_vel_nav -> velocity_smoother -> cmd_vel_smoothed ->
collision_monitor -> cmd_vel` ([nav2_params.yaml](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_bringup/params/nav2_params.yaml)).
`nav2_lifecycle_manager` brings the list up in order with bonds (`bond_timeout 4.0`,
`bond_heartbeat_period` 0.1, 0.25 on Lyrical); a missed heartbeat logs "CRITICAL FAILURE:
SERVER ... IS DOWN" and takes the whole set down
([lifecycle manager](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/configuring_lifecycle_manager/)).

## Behaviour tree

`bt_navigator` loads `navigate_to_pose` and `navigate_through_poses` navigators, each with
a default XML (`navigate_to_pose_w_replanning_and_recovery.xml` and the through-poses
twin) unless `default_nav_to_pose_bt_xml` is set; `bt_loop_duration 10` ms,
`default_server_timeout 20` ms, `plugin_lib_names` (auto-filled since Jazzy, ~45 entries on Humble)
([bt_navigator](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/configuring_bt_navigator/)).
The default tree: `RecoveryNode(6)` around a `PipelineSequence` of `RateController hz=1.0`
-> `ComputePathToPose` (global `ClearEntireCostmap` as its recovery) and `FollowPath` (local
clear); the recovery branch is a `RoundRobin` of clear both, `Spin 1.57`, `Wait 5.0`,
`BackUp 0.30 m at 0.15 m/s` ([behavior_trees/](https://github.com/ros-navigation/navigation2/tree/main/nav2_bt_navigator/behavior_trees)).
Change recovery logic by editing XML, not code; a per-goal tree goes in the action's
`behavior_tree` field. Humble XML is BT.CPP v3; Jazzy and later need `BTCPP_format="4"` and
custom nodes must handle `SKIPPED`. Groot 2 live monitoring returned in Kilted, off by default.

## Servers and the usual plugin choices

Defaults from `nav2_params.yaml` on Jazzy and the
[configuration guide](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/):

- **planner_server** (`expected_planner_frequency 20.0`): `nav2_navfn_planner::NavfnPlanner`
  (default, `tolerance 0.5`, `allow_unknown true`), `nav2_smac_planner::SmacPlanner2D`,
  `SmacPlannerHybrid` (car-like, `motion_model_for_search DUBIN`, `minimum_turning_radius
  0.4`), `SmacPlannerLattice` (lattice file), `nav2_theta_star_planner::ThetaStarPlanner`.
- **controller_server** (`controller_frequency 20.0`, `failure_tolerance 0.3`):
  `nav2_mppi_controller::MPPIController` (default since Jazzy; `time_steps 56`, `model_dt
  0.05`, `batch_size 2000`, `vx_max 0.5`, `wz_max 1.9`, `motion_model diff_drive | omni |
  ackermann`, critics `Constraint, Cost, Goal, GoalAngle, PathAlign, PathFollow, PathAngle,
  PreferForward`), `dwb_core::DWBLocalPlanner` (Humble default),
  `RegulatedPurePursuitController` (`lookahead_dist 0.6`), `RotationShimController` (rotate
  in place, then hand to `primary_controller`), `GracefulController`. `SimpleGoalChecker`
  `xy_goal_tolerance 0.25`, `yaw_goal_tolerance 0.25`; `SimpleProgressChecker`
  `required_movement_radius 0.5`, `movement_time_allowance 10.0`.
- **smoother_server**: `SimpleSmoother` (default), `ConstrainedSmoother` (cost function
  corrected in Lyrical, weights need retuning), `SavitzkyGolaySmoother`.
- **behavior_server**: `nav2_behaviors::Spin`, `BackUp`, `DriveOnHeading`, `Wait`,
  `AssistedTeleop`. **velocity_smoother**: `max_velocity [0.5, 0.0, 2.0]`, `max_accel
  [2.5, 0.0, 3.2]`, `feedback OPEN_LOOP`, `velocity_timeout 1.0`.

## Costmap layers

Two `nav2_costmap_2d::Costmap2DROS` instances. Jazzy defaults: local `rolling_window true`,
`width 3`, `height 3`, `resolution 0.05`, `global_frame odom`, `plugins [voxel_layer,
inflation_layer]`; global `global_frame map`, `track_unknown_space true`, `plugins
[static_layer, obstacle_layer, inflation_layer]`; both `robot_radius 0.22` (or a `footprint`
string), `inflation_radius 0.7`, `cost_scaling_factor 3.0`
([costmap_2d](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/costmap_2d/)).
Layers: `StaticLayer` (`map_topic`, under the layer since Kilted), `ObstacleLayer`
(`observation_sources`, per source `data_type LaserScan | PointCloud2`, `marking`,
`clearing`, `obstacle_max_range 2.5`, `raytrace_max_range 3.0`, `obstacle_min_range` for a
lidar that sees the robot body), `VoxelLayer`, `RangeSensorLayer`, `InflationLayer`,
`DenoiseLayer`, `PluginContainerLayer` (Kilted). Filters `KeepoutFilter`, `SpeedFilter`,
`BinaryFilter` read a mask from `costmap_filter_info_server`. A non-round robot needs the
SE2 `footprint`; Smac Hybrid and Lattice use it ([tuning guide](https://docs.nav2.org/rolling/configuration_and_development/tuning_guide/)).

## Waypoints and docking

`nav2_waypoint_follower` serves `FollowWaypoints` (`poses`, `number_of_loops`, `goal_index`;
result `missed_waypoints`) and `FollowGPSWaypoints` (`GeoPose[]` through
`robot_localization`'s `/fromLL`), with a task executor per stop (`WaitAtWaypoint`,
`PhotoAtWaypoint`, `InputAtWaypoint`) and `stop_on_failure`
([waypoint follower](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/waypoint_follower/)).
Docking (`opennav_docking`, in the metapackage from Jazzy; a separate 0.0.2 release for
Humble): `DockRobot` (`dock_id` or `dock_pose` plus `dock_type`, `navigate_to_staging_pose`)
and `UndockRobot`; plugins `SimpleChargingDock`, `SimpleNonChargingDock` with
`staging_x_offset -0.7`, `use_external_detection_pose` (AprilTag pose from `image_proc` or
Isaac ROS), `docking_threshold 0.05`, `dock_prestaging_tolerance 0.5`; docks come from a
`docks:` map or a `dock_database` yaml ([docking server](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/configuring_docking_server/)).

## Sending goals from a policy or VLM

`nav2_simple_commander` wraps the actions in Python
([robot_navigator.py](https://github.com/ros-navigation/navigation2/blob/main/nav2_simple_commander/nav2_simple_commander/robot_navigator.py),
[API page](https://docs.nav2.org/rolling/configuration_and_development/simple_commander_api/simple_commander_api/)):

```python
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
nav = BasicNavigator()                       # BasicNavigator(node_name='basic_navigator', namespace='')
nav.setInitialPose(init)                     # PoseStamped in map, only when AMCL has no pose yet
nav.waitUntilNav2Active(navigator='bt_navigator', localizer='amcl')
nav.goToPose(goal, behavior_tree='')         # goal: PoseStamped in map; x, y, yaw from the VLM
while not nav.isTaskComplete():
    fb = nav.getFeedback()                   # distance_remaining, navigation_time, number_of_recoveries
    if fb.navigation_time.sec > 120: nav.cancelTask()
if nav.getResult() == TaskResult.SUCCEEDED: ...
```

Other calls: `goThroughPoses(poses)` (`nav_msgs/Goals` from Kilted, `PoseStamped[]` before),
`followWaypoints(poses, number_of_loops=0, goal_index=0)`, `followGpsWaypoints`,
`followPath(path, controller_id='')` for a path from your own planner, `spin`, `backup`,
`driveOnHeading`, `dockRobotByID(dock_id)`, `dockRobotByPose`, `undockRobot`, `getPath`,
`smoothPath`, `changeMap`, `clearAllCostmaps`, `getGlobalCostmap`, `lifecycleStartup`.
Humble lacks `driveOnHeading`, GPS and docking; Jazzy has them. Cancel before switching task
types; same-type calls preempt. No official learned planner or controller plugin exists; the
integration points are a `FollowPath` goal with your own `nav_msgs/Path`, a planner or
controller plugin, or MPPI's `publish_optimal_trajectory`
([plugins list](https://docs.nav2.org/rolling/configuration_and_development/navigation_plugins/)).

## Humble vs Jazzy vs Kilted

- **TwistStamped**: Jazzy added `enable_stamped_cmd_vel` on every `cmd_vel` publisher and
  subscriber, default `false`; Kilted flipped it to `true`, so a Humble-era base driver
  expecting `Twist` gets nothing on Kilted until you set it back (migration guides above).
- **Kilted**: `error_code_names` became `error_code_name_prefixes` (old key rejected at
  startup); `NavigateThroughPoses.poses` became `nav_msgs/Goals` (read `.poses.goals`);
  `use_namespace` removed and param topics relative (`topic: scan` under `/tb4` is `/tb4/scan`).
- **Lyrical**: `nav2::LifecycleNode` and `nav2::qos` replace `nav2_util`, controller API
  `setPlan` -> `newPathReceived`, path pruning moved into a shared `FeasiblePathHandler`,
  `action_server_result_timeout` removed, `RoundRobin wrap_around` default `false`.

## Collision monitor

`nav2_collision_monitor` sits last in the velocity chain and never trusts the planner:
polygons with `action_type stop | slowdown | limit | approach` (approach uses the footprint,
`time_before_collision 1.2` s, `min_points 6`), sources `scan | pointcloud | range | polygon`,
`source_timeout 1.0`, `stop_pub_timeout 2.0`; points are a string `"[[x, y], ...]"` since
Jazzy ([collision monitor](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/collision_monitor/configuring_collision_monitor_node/)).
This is the layer to keep when a learned controller replaces MPPI.

## Gotchas

- TF contract is `map -> odom -> base_link -> sensors` ([setup_transforms](https://docs.nav2.org/rolling/configuration_and_development/first_time_robot_setup_guide/transformation/setup_transforms/));
  since Jazzy the costmap refuses to activate without `base_link` to its `global_frame`
  within `initial_transform_timeout 60.0` s. `use_sim_time` goes in the launch, not the
  yaml, and must also reach `robot_state_publisher`; a mismatch shows up as "Lookup would
  require extrapolation" ([#3769](https://github.com/ros-navigation/navigation2/issues/3769)).
- "Sensor origin at (x, y) is out of map bounds ... cannot raytrace": the local costmap is
  smaller than the sensor offset or odom jumped ([#3992](https://github.com/ros-navigation/navigation2/issues/3992)).
- Big costmaps over DDS: `always_send_full_costmap false` sends `CostmapUpdate` deltas
  (Jazzy); the tuning guide measured Zenoh 4.5 %, FastDDS 6.8 %, CycloneDDS 18.3 % CPU on
  the TB4 sim ([tuning guide](https://docs.nav2.org/rolling/configuration_and_development/tuning_guide/)).
- BT XML from an older distro breaks on `BTCPP_format` and `error_code_name_prefixes` after
  an upgrade ([#5415](https://github.com/ros-navigation/navigation2/issues/5415)). Odometry
  drifts by design; fuse wheel odom and IMU with `robot_localization` before tuning AMCL
  ([setup_odom](https://docs.nav2.org/rolling/configuration_and_development/first_time_robot_setup_guide/odom/setup_odom/)).
