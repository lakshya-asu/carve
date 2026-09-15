# meat_cell_ros

ROS 2 Humble nodes for the pork leg cell's grasp pipeline. The cell logic is not here: it is the
numpy-only part of `meat_cell_sim` (`belt_state`, `intercept`, `grasp_action`, `grasp_policy`,
`grasp_execution`), so the simulator and these nodes run the same code.

## The split that makes it work on any arm

```
camera + segmenter + centre of gravity  ->  leg/perception    (LegPerception, belt frame)
encoder (joint_states belt joint)       ->  belt/state        (BeltState: travel, speed, acceleration)
grasp_policy_node  (deterministic or learned, by parameter)
                                         ->  grasp/action      (GraspAction: point on the leg, jaw line, tilt, opening)
grasp_executor_node  (one per arm, config/<arm>.yaml)
    intercept plan -> timed tool waypoints -> MoveIt compute_ik -> FollowJointTrajectory + GripperCommand
```

Nothing upstream of the executor names a robot. A new arm is a new config file and a MoveIt config;
the policy, messages and planner do not change. An arm that cannot do what an action asks refuses it
with a declared outcome (`tool_cannot_tilt` on the SR-20iA) before anything moves.

## Nodes, topics and QoS

| Node | Subscribes | Publishes / serves | QoS |
|---|---|---|---|
| `belt_state` | `joint_states` (belt joint) | `belt/state` | in: sensor data; out: reliable, depth 10 |
| `grasp_policy` | `leg/perception` | `grasp/action` | reliable, depth 10 |
| `grasp_executor` | `belt/state`, `joint_states`, `grasp/action` | action `execute_grasp`; calls `compute_ik`, the trajectory and gripper actions | reliable, depth 10; joint states sensor data |

Frames: poses are in `world` (REP 103). The executor reads the TF from `world` to its tip link and
publishes no transforms. Messages are in `meat_cell_msgs`; field meanings never change without a
new message type.

## Build and run

```
rosdev   # sources /opt/ros/humble and ~/ros2_ws (alias in ~/.bashrc)
cd ~/robot-learning-lab/ros2 && colcon build && source install/setup.bash
export PYTHONPATH=$PYTHONPATH:~/robot-learning-lab/src
ros2 launch meat_cell_ros grasp_pipeline.launch.py arm:=ur20
```

## What is not in place yet (checked 2026-09-15)

Built and checked: `meat_cell_msgs` compiles and imports; the numpy modules import under the Humble
Python 3.10. Not yet possible on this PC without installs:

- MoveIt pieces `move_group` needs to plan and execute: `ros-humble-moveit` (brings OMPL, configs
  utils, simple controller manager, setup assistant, RViz plugin), and `ros-humble-pick-ik`.
- Robot descriptions: `ros-humble-ur-description` (whether it has a UR20 on Humble is unchecked);
  no URDF or MoveIt config exists for the SR-20iA, so one has to be written from the DH values in
  `meat_cell_sim/arms.py`.
- The simulator link: MuJoCo is installed only in the `rll` env (Python 3.11), not in the Humble
  Python, so a bridge node publishing `joint_states` and serving FollowJointTrajectory from MuJoCo
  needs `mujoco` in the Humble Python or `mujoco_ros2_control` built from source.
- The learned grasp policy is not wired into `grasp_policy_node`; it raises for any other policy name.
