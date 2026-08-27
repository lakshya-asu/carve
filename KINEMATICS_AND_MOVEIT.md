# Carve kinematics and MoveIt plan

Date: 2026-08-27

## Decision

The final in-simulator pipeline uses Isaac Sim Lula inverse kinematics and the Isaac articulation controller. Isaac Sim owns physics, rendered sensors, contacts, simulation time, collision-clear motion phases, trajectory sampling, and actuator execution.

ROS 2 Humble and MoveIt 2 remain the proposed external production-style planner boundary. A live MoveIt process was not installed or commissioned during this build.

Windows 11 is the supported Humble configuration for the installed Isaac Sim 6.0.1 bridge. Ubuntu under WSL 2 is already present on this workstation, but ROS 2 and MoveIt are not installed there. The project does not install them automatically.

## Implemented in-simulator kinematics

`isaac_sim/run_scene2_integrated.py` solves FANUC flange targets with the project Lula robot description. It uses a collision-clear pregrasp, vertical descent, timed interception, finger-only closure while the arm holds measured state, Cartesian lift and carry segments, cutter-frame alignment, release, and retract. Each controller command is checked against joint position, velocity, and acceleration limits. The final A and B runs recorded zero violations.

The product is coupled to the moving conveyor through a deterministic fixed-step kinematic fixture before grasp. Bilateral pad contact is mandatory. After confirmation the product becomes a dynamic PhysX rigid body. Lift, transport, buffer handling, alignment, and release perform no product pose writes.

This internal controller is the validated simulator path. It is not an OEM controller model and does not claim real collision margins or dynamic performance.

## Deliberate external MoveIt limits

The first version does not use MoveIt Task Constructor, MoveIt Servo, or a custom planner. It uses:

- one MoveIt planning group from `base_link` to `flange`
- the KDL inverse-kinematics plugin
- OMPL RRTConnect for collision-aware transit motion
- standard `FollowJointTrajectory` execution
- simulation-time interpolation at the Isaac 240 Hz physics rate
- a fixed planning scene for the conveyor, pedestal, camera gantry, cutter, guards, and reject bin

The final conveyor interception segment will be planned to a predicted future pose and arrival time. Continuous servo tracking is deferred until measured tests show that thresholded replanning is insufficient.

## Process boundaries

### Isaac Sim

Inputs:

- six-joint position command
- PLC permissive, fault, and emergency-stop state
- scenario and recipe configuration

Outputs:

- `/clock` from fixed simulation time
- measured J1 through J6 position and velocity
- overhead RGB, depth, and camera calibration
- contact, grasp, slip, and placement observations
- simulated PLC state and cycle events

### MoveIt

Inputs:

- robot URDF and SRDF
- measured joint state
- static and dynamic collision objects
- target flange pose and requested arrival time

Outputs:

- a collision-checked, time-parameterized six-joint trajectory

### Perception and tracking

Inputs:

- RGB, depth, camera calibration, conveyor encoder, and simulation time

Outputs:

- detections and masks
- calibrated product pose
- track identity and confidence
- conveyor-relative velocity
- predicted intercept pose and time

### Cell coordinator

Inputs:

- tracked workpiece
- MoveIt planning result
- cutter readiness and PLC permissives
- robot and grasp state

Outputs:

- reserve, plan, execute, cancel, reject, and recover decisions

## Proposed external command path

MoveIt sends `control_msgs/action/FollowJointTrajectory` to the Carve trajectory bridge. The bridge validates joint names, limits, timestamps, and start-state tolerance. It samples the accepted trajectory using `/clock` and publishes one six-joint command for each Isaac physics step. Isaac applies the command through the FANUC articulation controller and returns measured state.

MoveIt never writes directly to an Isaac joint. YOLO never sends a robot command.

## Visual feed

The overhead sensor publishes synchronized RGB, metric depth, and `CameraInfo` at 15 Hz. The messages share a simulation timestamp and `overhead_camera_optical` frame. Raw images are the verification baseline. Compressed RGB is optional for remote viewing and must not replace the raw feed used by the primary perception test.

The viewer should show:

- RGB with mask, track ID, confidence, and predicted intercept marker
- depth under the cursor and invalid-depth fraction
- current robot state and active trajectory phase
- PLC permissives, cutter readiness, and faults
- timing age from exposure to track, plan, command, and contact

## First acceptance gate, passed in Isaac Sim

1. Isaac publishes nonempty `/clock`, measured joints, RGB, depth, and camera calibration.
2. A ROS 2 probe publishes a six-joint command.
3. Isaac receives the command and moves the actual FANUC articulation.
4. The measured joint state returns over ROS 2 and reaches the commanded tolerance.
5. Message timestamps come from fixed simulation time.
6. Partial or reordered joint names, nonfinite values, and limit violations are rejected.

The headless gate passed twice on 2026-08-26 with the same saved-stage hash and identical ROS metrics. Each run published 720 clock messages, 180 measured joint states, 45 RGB frames, 45 depth frames, and 45 camera calibration messages. The in-process DDS probe received every stream type. Isaac rejected the deliberately partial command. It accepted one complete command and applied it through the FANUC articulation controller. The maximum final joint error was 0.000836 rad.

The focused ROS gate does not test MoveIt, a trajectory action server, stale trajectory cancellation, or dynamic MoveIt collision objects. ROS 2 and MoveIt are not installed in the existing WSL 2 environment, and this project does not install system software without separate authorization.

The complete conveyor interception task is nevertheless validated inside Isaac Sim through the internal Lula and articulation path described above. This is separate from, and does not imply, MoveIt validation.

## Standard trajectory transport now implemented

`meatcell/trajectory.py` defines a strict six-joint trajectory contract and a simulation-clock sampler. `isaac_sim/scene2_ros_bridge.py` subscribes to `/carve/arm_controller/joint_trajectory` using `trajectory_msgs/msg/JointTrajectory`. It rejects incomplete or reordered names, nonfinite values, nonmonotonic timestamps, and limit violations. Accepted trajectories are sampled from Isaac simulation time and sent to the actual FANUC articulation controller.

The integrated task runner saves the articulation commands it actually executed to `robot_joint_trajectory.json`. This proves trajectory shape, timestamp order, endpoint agreement, and articulation execution. It is compatible evidence, not a claim that MoveIt generated the path.

The focused ROS gate now publishes one standard JointTrajectory over DDS. The bridge accepted and completed it, sampled 113 commands against the Isaac clock, applied them through the actual FANUC articulation controller, and reached 0.000842 rad maximum final joint error. Evidence is `results/full_suite/20260827_114303264/scene2/scene2_validation.json`.

The next external gate adds `control_msgs/action/FollowJointTrajectory`, starts a real MoveIt process in an authorized ROS 2 environment, builds the FANUC planning scene, and replaces at least one internal transit path with a collision-checked MoveIt result. That external gate remains open.

## Sources

- NVIDIA Isaac Sim ROS 2 installation and standalone bridge documentation
- MoveIt launch, planning scene, controller, and trajectory execution documentation
- Official FANUC ROS 2 driver Humble branch and MoveIt configuration guidance

These sources define software interfaces. They do not validate a physical robot, controller, gripper, cutter, or safety system.
