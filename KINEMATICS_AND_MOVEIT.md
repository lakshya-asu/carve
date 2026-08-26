# Carve kinematics and MoveIt plan

Date: 2026-08-26

## Decision

Use ROS 2 Humble and MoveIt 2 outside Isaac Sim. Isaac Sim owns physics, rendered sensors, contacts, simulation time, and articulation execution. MoveIt owns collision-aware arm planning and trajectory timing.

Windows 11 is the supported Humble configuration for the installed Isaac Sim 6.0.1 bridge. Ubuntu under WSL 2 is already present on this workstation, but ROS 2 and MoveIt are not installed there. The project does not install them automatically.

## Deliberate limits

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

## Command path

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

The gate does not test MoveIt, a trajectory action server, stale trajectory cancellation, dynamic collision objects, or conveyor interception. ROS 2 and MoveIt are not installed in the existing WSL 2 environment, and this project does not install system software without separate authorization.

The next gate implements the standard trajectory action bridge, builds the FANUC MoveIt configuration in an existing ROS 2 environment, and replaces the probe command with a collision-checked trajectory.

## Sources

- NVIDIA Isaac Sim ROS 2 installation and standalone bridge documentation
- MoveIt launch, planning scene, controller, and trajectory execution documentation
- Official FANUC ROS 2 driver Humble branch and MoveIt configuration guidance

These sources define software interfaces. They do not validate a physical robot, controller, gripper, cutter, or safety system.
