---
title: MoveIt 2
date: 2026-09-05
tags: [tool, ros2, moveit, motion-planning, servo, manipulation]
status: draft
source: https://github.com/moveit/moveit2 ; https://moveit.picknik.ai/main/
---

# MoveIt 2

Motion planning, IK, collision checking and trajectory execution for arms on ROS 2. For a
learning engineer it does two jobs: scripted approach and retreat moves around the policy
segment (`move_group` or `MoveItCpp`), and a guarded streaming path for end-effector-space
policy actions (Servo). Its place relative to `ros2_control` and JTC is in
[connecting-to-real-robots](../topics/connecting-to-real-robots.md#moveit-2-for-planning-and-servo-for-streaming).

## Versions (checked 2026-09-05)

| Distro | Branch | Version | Notes |
|---|---|---|---|
| Humble (our `rosdev`) | `humble` | 2.5.10 (1 Sep 2026; apt still 2.5.9) | Old Servo API, no STOMP, `moveit_py` backported in 2.5.10 |
| Jazzy | `jazzy` | 2.12.4 | New Servo, STOMP, `moveit_py` in apt |
| Kilted | `kilted` | 2.14.3 | `.hpp` headers, `.h` deprecated |
| Rolling and Lyrical | `main` | 2.15.1 | No `lyrical` branch; both bloom from `main` |

Sources: `moveit/package.xml` per branch, [rosdistro](https://github.com/ros/rosdistro),
[README](https://github.com/moveit/moveit2/blob/main/README.md). The moveit.ai release table is stale; tutorials exist only at `moveit.picknik.ai/main/` and `/humble/`.

## What it gives

- **Planning scene**: `PlanningSceneMonitor` reads `joint_states`, `collision_object`,
  `attached_collision_object`, `planning_scene`; publishes `monitored_planning_scene` at
  `publish_planning_scene_hz: 4.0`
  ([planning_scene_monitor.cpp](https://github.com/moveit/moveit2/blob/main/moveit_ros/planning/planning_scene_monitor/src/planning_scene_monitor.cpp)).
  Octomap from depth via `sensors_3d.yaml` (`octomap_frame` required, `octomap_resolution`
  silently 0.1 m if missing, `occupancy_map_monitor/PointCloudOctomapUpdater`)
  ([perception pipeline](https://moveit.picknik.ai/main/doc/examples/perception_pipeline/perception_pipeline_tutorial.html)).
- **Planners** (`config/<name>_planning.yaml`, discovered by filename): OMPL
  (`ompl_interface/OMPLPlanner`, RRTConnect and the rest of `ompl_defaults.yaml`), CHOMP
  (`chomp_interface/CHOMPPlanner`), Pilz (`pilz_industrial_motion_planner/CommandPlanner`,
  planner ids `PTP`, `LIN`, `CIRC`; needs `config/pilz_cartesian_limits.yaml` with
  `max_trans_vel`, `max_trans_acc`, `max_trans_dec`, `max_rot_vel`), STOMP
  (`stomp_moveit/StompPlanner`, Jazzy and later)
  ([default_configs](https://github.com/moveit/moveit2/tree/main/moveit_configs_utils/default_configs),
  [Pilz plugins](https://github.com/moveit/moveit2/blob/main/moveit_planners/pilz_industrial_motion_planner/plugins/planning_context_plugin_description.xml)).
  Pilz LIN and CIRC for repeatable approach moves; OMPL for free space.
- **IK** (`kinematics.yaml`: `kinematics_solver`, `kinematics_solver_search_resolution` 0.1,
  `kinematics_solver_timeout` 0.05, loaded under `robot_description_kinematics.<group>`
  ([kinematics_parameters.yaml](https://github.com/moveit/moveit2/blob/main/moveit_ros/planning/kinematics_plugin_loader/src/kinematics_parameters.yaml))):
  KDL `kdl_kinematics_plugin/KDLKinematicsPlugin` (numeric); TRAC-IK
  `trac_ik_kinematics_plugin/TRAC_IKKinematicsPlugin` (`solve_type` Speed | Distance |
  Manipulation1..3; binaries for Jazzy and later, not Humble) ([trac_ik](https://github.com/traclabs/trac_ik));
  pick_ik `pick_ik/PickIkPlugin` (bio_ik's ROS 2 reimplementation, `mode: global`,
  `position_threshold` 0.001; Humble through Lyrical) ([pick_ik](https://github.com/PickNikRobotics/pick_ik));
  IKFast via `auto_create_ikfast_moveit_plugin.sh` (analytic, 6-DoF). LMA removed Dec 2023.
- **Collision checking**: FCL default, Bullet via `collision_detector` (its tutorial still says
  it "is not thread safe"); the Allowed Collision Matrix lives in the SRDF ([loader](https://github.com/moveit/moveit2/blob/main/moveit_ros/planning/collision_plugin_loader/src/collision_plugin_loader.cpp)).

## Setup Assistant for a new arm

`ros2 launch moveit_setup_assistant setup_assistant.launch.py`, load the URDF or xacro, run
self-collision sampling, define virtual joint, groups, poses, end effector and controllers.
It writes `<robot>_moveit_config` with `config/<robot>.srdf`, `kinematics.yaml`,
`joint_limits.yaml`, `pilz_cartesian_limits.yaml`, `moveit_controllers.yaml`,
`ros2_controllers.yaml`, `initial_positions.yaml`, `<robot>.ros2_control.xacro` and thin
launch files (`demo`, `move_group`, `rsp`, `moveit_rviz`, `spawn_controllers`) that call
`moveit_configs_utils.launches.generate_*_launch`
([launches.cpp](https://github.com/moveit/moveit2/blob/main/moveit_setup_assistant/moveit_setup_app_plugins/src/launches.cpp),
[tutorial](https://moveit.picknik.ai/main/doc/examples/setup_assistant/setup_assistant_tutorial.html)).
Every node that plans or solves IK gets its parameters from
`MoveItConfigsBuilder("<robot>").to_moveit_configs()` (`.robot_description_kinematics()`,
`.planning_pipelines()`, `.trajectory_execution()`, `.sensors_3d()`, `.to_dict()`)
([moveit_configs_builder.py](https://github.com/moveit/moveit2/blob/main/moveit_configs_utils/moveit_configs_utils/moveit_configs_builder.py)).
Open MSA bug: the Controllers tab "Auto Add" writes no `action_ns`, so `move_group` reports
"Unable to identify any set of controllers that can actuate the specified joints"; add
`action_ns: follow_joint_trajectory` by hand ([#3566](https://github.com/moveit/moveit2/issues/3566), [#3796](https://github.com/moveit/moveit2/issues/3796)).

## move_group vs MoveItCpp vs moveit_py

`move_group` is one node exposing planning over actions and services, built on `MoveItCpp`
([move_group.cpp](https://github.com/moveit/moveit2/blob/main/moveit_ros/move_group/src/move_group.cpp)).
`MoveGroupInterface` is its C++ client: `allowed_planning_time_ = 5.0`,
`num_planning_attempts_ = 1`, goal tolerances 1e-4 rad, 1e-4 m, 1e-3 rad
([move_group_interface.cpp](https://github.com/moveit/moveit2/blob/main/moveit_ros/planning_interface/move_group_interface/src/move_group_interface.cpp)).
`MoveItCpp` runs the scene monitor and pipelines in your own process with no ROS transport,
"an alternative (not a full replacement) for the existing MoveGroup API"; use it when the
policy loop and the planner share a process
([MoveItCpp tutorial](https://moveit.picknik.ai/main/doc/examples/moveit_cpp/moveitcpp_tutorial.html)).

`moveit_py` binds MoveItCpp, not `move_group`: `from moveit.planning import MoveItPy,
PlanningComponent, PlanRequestParameters`; `arm = MoveItPy(node_name="x").get_planning_component("arm")`,
`arm.set_start_state_to_current_state()`, `arm.set_goal_state(pose_stamped_msg=..., pose_link=...)`,
`plan_result = arm.plan()`, `moveit.execute(plan_result.trajectory, controllers=[])`
([python API tutorial](https://moveit.picknik.ai/main/doc/examples/motion_planning_python_api/motion_planning_python_api_tutorial.html)).
It needs the full MoveItCpp parameter set (SRDF, `moveit_cpp.yaml` with
`planning_pipelines.pipeline_names` and `plan_request_params.planning_time`) in the launch
file, or "Failed to load any planning pipelines" ([#2409](https://github.com/moveit/moveit2/issues/2409)).
Backported to Humble in 2.5.10 by [#3487](https://github.com/moveit/moveit2/pull/3487)
(there `plan()` returns `PlanSolution`); `ros-humble-moveit-py` was built on the farm on
2 Sep 2026 but is not in apt yet. Teardown segfault on Jazzy 2.12.4 is open
([#3721](https://github.com/moveit/moveit2/issues/3721)). No `moveit_commander` in ROS 2.

## Servo for streaming policy actions

Jazzy and later ship the 2023 rewrite ([PR #2224](https://github.com/moveit/moveit2/pull/2224),
2.8.0). `ServoNode` subscribes `~/delta_joint_cmds` (`control_msgs/JointJog`),
`~/delta_twist_cmds` (`geometry_msgs/TwistStamped`), `~/pose_target_cmds`
(`geometry_msgs/PoseStamped`); switch with `~/switch_command_type`
(`moveit_msgs/srv/ServoCommandType`: 0 joint jog, 1 twist, 2 pose), pause with `~/pause_servo`
(`std_srvs/SetBool`) ([servo_node.cpp](https://github.com/moveit/moveit2/blob/main/moveit_ros/moveit_servo/src/servo_node.cpp)).
Parameters under `servo.`, identical on `jazzy`, `kilted`, `main`
([servo_parameters.yaml](https://github.com/moveit/moveit2/blob/main/moveit_ros/moveit_servo/config/servo_parameters.yaml)):

- Rate: `publish_period: 0.01`, `max_expected_latency: 0.1` (period under a third of it),
  `incoming_command_timeout: 0.1`, `thread_priority: 40` (`SCHED_FIFO` when allowed).
- Input: `command_in_type: unitless` ([-1, 1]) or `speed_units` (m/s, rad/s); `scale.linear:
  0.4`, `scale.rotational: 0.8`, `scale.joint: 0.5`; `apply_twist_commands_about_ee_frame: true`.
- Collision: `check_collisions: true`, `collision_check_rate: 10.0` Hz,
  `self_collision_proximity_threshold: 0.01`, `scene_collision_proximity_threshold: 0.02`,
  `check_octomap_collisions: false`.
- Singularity: scale down from condition number `lower_singularity_threshold: 17.0`, stop at
  `hard_stop_singularity_threshold: 30.0`, `leaving_singularity_threshold_multiplier: 2.0`;
  `joint_limit_margins: [0.1]`; `override_velocity_scaling_factor: 0.0`.
- Output: `command_out_type: trajectory_msgs/JointTrajectory` (JTC) or
  `std_msgs/Float64MultiArray` (forward controller), `command_out_topic`; smoothing
  `smoothing_filter_plugin_name: online_signal_smoothing::ButterworthFilterPlugin` (also
  `AccelerationLimitedPlugin`, `RuckigFilterPlugin`; Humble has Butterworth only).

Twist and pose modes need an IK plugin on the group or Servo logs "No IK solver for
planning group" ([command.cpp](https://github.com/moveit/moveit2/blob/main/moveit_ros/moveit_servo/src/utils/command.cpp));
startup waits 5 s for complete `joint_states`, then exits; every command needs a fresh stamp.
The `Servo` C++ class gives the same guards in-process ([tutorial](https://moveit.picknik.ai/main/doc/examples/realtime_servo/realtime_servo_tutorial.html)).

**Humble is the old Servo**: flat parameters (`publish_period: 0.034`, `planning_frame`,
`ee_frame_name`, `robot_link_command_frame`, scalar `joint_limit_margin`,
`low_latency_mode`), no `PoseStamped` input, and `std_srvs/Trigger` services `~/start_servo`,
`~/stop_servo`, `~/pause_servo`, `~/unpause_servo`; nothing moves until `start_servo`
([humble config](https://github.com/moveit/moveit2/blob/humble/moveit_ros/moveit_servo/config/panda_simulated_config.yaml),
[humble tutorial](https://moveit.picknik.ai/humble/doc/examples/realtime_servo/realtime_servo_tutorial.html)).

## Task Constructor

`moveit_task_constructor` builds a task from stages with forward, backward and generator
propagation: containers `SerialContainer`, `Alternatives`, `Fallbacks`, `Merger`; stages
`CurrentState`, `MoveTo`, `MoveRelative`, `Connect`, `GenerateGraspPose`, `ComputeIK`,
`ModifyPlanningScene`, `Pick`; solvers `PipelinePlanner`, `CartesianPath`, `JointInterpolationPlanner`
([ros2 branch](https://github.com/moveit/moveit_task_constructor/tree/ros2),
[tutorial](https://moveit.picknik.ai/main/doc/tutorials/pick_and_place_with_moveit_task_constructor/pick_and_place_with_moveit_task_constructor.html)).
Released as 0.1.3 for Humble, 0.1.8 for Jazzy and Kilted, 0.2.0 for Rolling; the Python
demo `pickplace.py` still imports `moveit_commander` (unverified whether it runs). Use: the
policy proposes the grasp pose, MTC does approach, lift and retreat.

## Humble vs Jazzy

Servo old vs new (above). Pipeline yaml changed in Oct 2023: `planning_plugin: <string>` plus
one `request_adapters` string became `planning_plugins`, `request_adapters` and
`response_adapters` lists ([MIGRATION.md](https://github.com/moveit/moveit2/blob/main/MIGRATION.md)).
STOMP, TRAC-IK binaries and the extra smoothing plugins are Jazzy and later; `ros2_control`
is 2.54 on Humble, 4.48 on Jazzy, 5.18 on Kilted (rosdistro). Hand-eye calibration
(`moveit_calibration`, `ros2` branch) is source-build only and its tutorial is still ROS 1
([README](https://github.com/moveit/moveit_calibration/blob/ros2/README.md)).

## Gotchas

- "Invalid Trajectory: start point deviates from current robot state more than 0.01 at joint
  ..." is `trajectory_execution.allowed_start_tolerance` (0.01 rad; per joint via
  `allowed_start_tolerance_joints.<joint>`). "Controller is taking too long to execute
  trajectory" is `allowed_execution_duration_scaling: 1.1` plus
  `allowed_goal_duration_margin: 0.5`
  ([trajectory_execution_manager.cpp](https://github.com/moveit/moveit2/blob/main/moveit_ros/planning/trajectory_execution_manager/src/trajectory_execution_manager.cpp),
  [#1848](https://github.com/moveit/moveit2/issues/1848)).
- "Didn't receive robot state (joint angles) with recent timestamp within 1 seconds" is
  `use_sim_time` set on one side only, or a `MoveGroupInterface` in a node nobody spins
  ([#3340](https://github.com/moveit/moveit2/issues/3340), [#775](https://github.com/moveit/moveit2/issues/775)).
  "No kinematics solver instantiated for group": `kinematics.yaml` not passed to that node
  ([#2917](https://github.com/moveit/moveit2/issues/2917)).
- Pilz ignores `num_planning_attempts` ([#3500](https://github.com/moveit/moveit2/issues/3500)).
  Servo drift and speed complaints usually trace to `publish_period` versus the controller
  rate, or `joint_states` slower than Servo ([#2191](https://github.com/moveit/moveit2/issues/2191),
  [#3657](https://github.com/moveit/moveit2/issues/3657)).
