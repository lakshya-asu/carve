---
title: Glossary
date: 2026-09-06
tags: [reference]
status: draft
source: synthesis
---

# Glossary

Terms a robot learning field engineer meets across this library, each with the note that
covers it and carries the sources. Only terms this library covers are listed; numbers here
are copied from the linked note and carry that note's verification status.

## A

- **Action chunking.** A policy predicts a short horizon of future actions (ACT uses
  k = 100 at 50 Hz; VLAs 8 to 50) instead of one step, which hides inference latency and
  creates seams at chunk boundaries. See [imitation-learning](imitation-learning.md) and
  [vision-language-action-models](vision-language-action-models.md).
- **ACT (Action Chunking with Transformers).** The ALOHA policy: a CVAE transformer that
  outputs a chunk of absolute joint positions, smoothed at runtime by temporal ensembling.
  See [zhao-2023-aloha-act](../papers/zhao-2023-aloha-act.md).
- **Admittance control.** Force control that measures a wrench and commands a motion so the
  tool behaves as a mass-spring-damper about the commanded pose; the mirror of impedance
  control, and the usual outer loop under a learned policy on a stiff position-controlled
  arm. See [perception-tactile-and-force](perception-tactile-and-force.md).
- **AMCL (Adaptive Monte Carlo Localization).** Nav2's particle-filter localizer against a
  static map; it publishes the `map -> odom` correction. See
  [state-estimation-and-localization](state-estimation-and-localization.md) and
  [nav2](../tools/nav2.md).
- **ATE (absolute trajectory error).** RMSE of estimated versus ground-truth positions
  after timestamp association and an SE(3) (or Sim(3)) alignment; the companion RPE
  measures drift over a fixed delta. UMI reports 6.1 mm ATE against MoCap. See
  [state-estimation-and-localization](state-estimation-and-localization.md) and
  [chi-2024-umi](../papers/chi-2024-umi.md).

## B

- **Behaviour cloning (BC).** Supervised learning of a policy from demonstration
  observation-action pairs; fails by compounding error and by averaging multimodal demos,
  which DAgger and generative heads respectively address. See
  [imitation-learning](imitation-learning.md).

## C

- **Change bar.** In the manual rendered from this library, a 3 px bar in the margin next to
  any claim tagged unverified (a dagger in the text); it marks what has not been checked,
  not what changed. The rule is recorded in the repository file DESIGN.md.
- **CiA 402.** The CANopen device profile for drives, carried over EtherCAT (CoE) or CAN:
  a shared state machine (switch on, enable operation, fault reset), an object dictionary
  (0x6040 controlword, 0x6041 statusword, 0x6060 mode), and modes such as CSP, CSV, CST.
  See [sensors-and-actuators](sensors-and-actuators.md).
- **Costmap.** Nav2's 2D occupancy grid with inflation layers; a rolling local costmap for
  the controller and a global one for the planner. See [nav2](../tools/nav2.md).

## D

- **DAgger (Dataset Aggregation).** Iteratively roll out the learner, relabel its visited
  states with expert actions, retrain; the human-gated variant (HG-DAgger) is the practical
  form on hardware. See [imitation-learning](imitation-learning.md).
- **DDS (Data Distribution Service).** The default ROS 2 middleware family under `rmw`
  (selected by `RMW_IMPLEMENTATION`, one vendor per robot): multicast discovery, UDP or
  shared-memory transport, QoS on every topic. See [ros2-in-depth](ros2-in-depth.md).
- **DEXA (dual-energy X-ray absorptiometry).** Two-energy X-ray that reads material
  composition; in meat plants it gives chemical lean and bone maps that drive cut paths.
  See [meat-cutting-automation](meat-cutting-automation.md) and
  [sensors-and-actuators](sensors-and-actuators.md).
- **Diffusion policy.** A policy that samples an action chunk by iteratively denoising
  noise conditioned on observations; handles multimodal demonstrations that regression
  averages away. See [imitation-learning](imitation-learning.md) and
  [chi-2023-diffusion-policy](../papers/chi-2023-diffusion-policy.md).
- **Domain randomization.** Randomize simulator visuals or physics so the real world
  looks like one more sample of the training distribution; ADR grows the ranges
  automatically. See [sim-to-real](sim-to-real.md) and
  [tobin-2017-domain-randomization](../papers/tobin-2017-domain-randomization.md).

## E

- **EGM (Externally Guided Motion).** ABB's UDP streaming interface for external position
  or joint commands at 4 ms, with 10 to 20 ms control lag; needs RobotWare option 689-1.
  See [connecting-to-real-robots](connecting-to-real-robots.md).
- **EHEDG.** European Hygienic Engineering and Design Group; its guidelines (Doc 8, Doc
  13) and component certification define cleanable equipment for wet food areas. See
  [meat-cutting-automation](meat-cutting-automation.md) and
  [compliant-mechanisms-and-actuation](compliant-mechanisms-and-actuation.md).
- **EtherCAT.** The 1 to 4 kHz industrial fieldbus for drives and I/O terminals; reaches
  ROS 2 through `ethercat_driver_ros2`. See [sensors-and-actuators](sensors-and-actuators.md)
  and [ros2-field-integrations](ros2-field-integrations.md).
- **Executor.** The ROS 2 object that runs callbacks; single-threaded, multi-threaded, and
  (Lyrical) events executors differ in CPU cost and in how a blocking callback stalls the
  rest of a callback group. See [ros2-in-depth](ros2-in-depth.md).

## F

- **FCI (Franka Control Interface).** The 1 kHz external control mode of Franka arms,
  enabled from Desk; the ROS 2 driver and `libfranka` sit on it. See
  [operating-robot-arms](operating-robot-arms.md).
- **Flow matching.** A generative action head that learns a velocity field from noise to
  action and integrates it in a few steps (π0 uses 10); a cheaper cousin of diffusion. See
  [imitation-learning](imitation-learning.md) and [black-2024-pi0](../papers/black-2024-pi0.md).
- **FRI (Fast Robot Interface).** KUKA's UDP interface for LBR iiwa and Med arms, served
  by a Sunrise application; the send period is set on the smartPAD (10 ms in the
  `lbr_fri_ros2_stack` default). See
  [connecting-to-real-robots](connecting-to-real-robots.md).
- **F/T sensor.** A six-axis force/torque sensor, usually at the wrist, that feeds
  admittance control and the force-threshold hold in a policy shield. See
  [perception-tactile-and-force](perception-tactile-and-force.md) and
  [safety-for-learned-policies](safety-for-learned-policies.md).

## G

- **GMSL2.** A serial camera link over coax (6 Gbit/s, beyond 15 m) used by ZED X and
  other Jetson cameras; removes the USB bandwidth problem and ties the kernel module to a
  JetPack version. See [depth-cameras](../hardware/depth-cameras.md) and
  [compute](../hardware/compute.md).

## H

- **Hand-eye calibration.** Solving the static transform between a camera and either the
  tool flange (eye-in-hand, `tool0 -> camera_link`) or the base (eye-to-hand) from a set of
  robot poses and target detections; its residual caps grasp precision. See
  [perception-3d-sensing](perception-3d-sensing.md).
- **HIL-SERL.** Human-in-the-loop SERL: real-world RL where teleop interventions during
  rollouts enter the buffer as demonstrations; reported near-perfect success in 1 to 2.5 h
  of training. See [real-world-rl](real-world-rl.md) and
  [luo-2024-hil-serl](../papers/luo-2024-hil-serl.md).

## I

- **IK (inverse kinematics).** Solving joint angles for a target tool pose; numerical
  solvers (TRAC-IK, pink, mink) differ in joint-limit handling and behaviour near
  singularities. See [kinematics-dynamics-and-rotations](kinematics-dynamics-and-rotations.md).
- **Impedance control.** Force control that measures position and commands a force or
  torque so the tool behaves as a mass-spring-damper; native on torque-controlled arms
  (Franka, KUKA iiwa). See [perception-tactile-and-force](perception-tactile-and-force.md).
- **IP69K.** Ingress protection per ISO 20653 for high-pressure, high-temperature
  washdown; the rating expected of anything inside a meat cell. See
  [meat-cutting-automation](meat-cutting-automation.md) and
  [sensors-and-actuators](sensors-and-actuators.md).

## J

- **Jacobian.** The 6 x n matrix mapping joint rates to tool twist; its rank drop is a
  singularity, and the analytic variant adds the singularities of the chosen orientation
  parameterization. See [kinematics-dynamics-and-rotations](kinematics-dynamics-and-rotations.md).
- **JetPack.** NVIDIA's Jetson software stack (L4T, CUDA, TensorRT, cuDNN); TensorRT
  engines are per-GPU and per-JetPack version, and JetPack 6 versus 7 splits Orin from
  Thor. See [compute](../hardware/compute.md) and
  [perception-foundation-models](perception-foundation-models.md).

## L

- **LeRobot dataset (v3).** Hugging Face's episode format with Parquet metadata and
  sharded video; call `finalize()` before pushing. See
  [teleoperation-and-data-collection](teleoperation-and-data-collection.md) and
  [lerobot](../tools/lerobot.md).
- **LOTO (lockout/tagout).** Energy isolation under 29 CFR 1910.147; an authorized
  employee locks out to service a machine, and outside personnel never remove a lock that
  is not theirs. See [field-engineer-handbook](field-engineer-handbook.md).

## M

- **MCAP.** The rosbag2 storage format that replaced sqlite3 as default from Iron;
  Humble needs `ros-humble-rosbag2-storage-mcap` and `-s mcap`. See
  [ros2-in-depth](ros2-in-depth.md) and [fleet-operations](fleet-operations.md).
- **MoveIt Servo.** MoveIt 2's real-time Cartesian or joint jogging node with singularity
  and collision scaling; a hop between a policy and the controller, and not a substitute
  for a Ruckig-filtered loop at the driver rate. See
  [conveyor-tracking-and-visual-servoing](conveyor-tracking-and-visual-servoing.md) and
  [connecting-to-real-robots](connecting-to-real-robots.md).
- **MPM (material point method).** Particle-plus-grid simulation that handles plasticity,
  splitting, and merging; the engine behind PlasticineLab and Genesis. See
  [deformable-object-manipulation](deformable-object-manipulation.md).
- **MTBF.** Mean time between failures of a repairable system; count it per robot so a lemon
  shows. See [fleet-operations](fleet-operations.md).

## O

- **odom and map frames.** REP 105's contract: `odom` is continuous and drifts, `map` is
  drift-free and may jump, tree `map -> odom -> base_link`. A manipulation policy wants
  `odom`; navigation wants `map`. See
  [state-estimation-and-localization](state-estimation-and-localization.md).
- **OEE (overall equipment effectiveness).** Availability x Performance x Quality; for a
  policy cell, availability counts protective stops, faults, and policy-PC downtime. See
  [fleet-operations](fleet-operations.md).
- **OPC UA (IEC 62541).** The PLC integration protocol to reach for first with Siemens,
  Beckhoff, or B&R; self-describing tags, subscriptions, default 100 ms publishing
  interval. See [ros2-field-integrations](ros2-field-integrations.md).

## P

- **PFL (power and force limiting).** The collaborative mode where contact is allowed
  under body-region force and pressure limits from ISO/TS 15066. See
  [safety-for-learned-policies](safety-for-learned-policies.md).
- **PL d.** Performance Level d under ISO 13849-1, a PFHd band for safety functions;
  typical for robot e-stop inputs, safety laser scanners, and safety mats. See
  [safety-for-learned-policies](safety-for-learned-policies.md) and
  [sensors-and-actuators](sensors-and-actuators.md).
- **PREEMPT_RT.** The Linux real-time preemption patch, mainline since 6.12; required for
  1 kHz control loops, and checked with `uname -a` and `cyclictest`, not by the label. See
  [connecting-to-real-robots](connecting-to-real-robots.md).
- **Protective stop.** A safety-rated stop triggered by a safeguard input (light curtain,
  scanner, SI0/SI1 on a UR) as opposed to an e-stop; the field engineer clears it and
  reads the fault code. See [operating-robot-arms](operating-robot-arms.md) and
  [safety-for-learned-policies](safety-for-learned-policies.md).

## Q

- **QDD (quasi-direct drive).** A large outrunner motor with a single planetary stage under
  10:1; back-drivable, torque readable from current, heat-limited. See
  [sensors-and-actuators](sensors-and-actuators.md) and
  [compliant-mechanisms-and-actuation](compliant-mechanisms-and-actuation.md).
- **QoS (Quality of Service).** The per-topic DDS contract (reliability, durability,
  history, deadline); subscriptions request, publishers offer, and an incompatible pair
  fails silently. See [ros2-in-depth](ros2-in-depth.md).
- **Quaternion (wxyz versus xyzw).** Unit quaternion for orientation; ROS messages, scipy,
  and pinocchio store `xyzw`, Isaac Lab, Eigen constructors, and MuJoCo store `wxyz`, and
  reading one as the other is the commonest integration bug in this library. See
  [kinematics-dynamics-and-rotations](kinematics-dynamics-and-rotations.md).

## R

- **RCC (remote centre compliance).** A passive compliant wrist whose centre of compliance
  sits at the tool tip so lateral error corrects itself on insertion (Whitney). See
  [compliant-mechanisms-and-actuation](compliant-mechanisms-and-actuation.md).
- **REP 103 and REP 105.** ROS conventions for units and frame handedness (103) and the
  `map -> odom -> base_link` frame tree (105). See
  [state-estimation-and-localization](state-estimation-and-localization.md).
- **RLDS.** TFRecord episode format used by Open X-Embodiment, RT-X, Octo, and OpenVLA;
  heavy TensorFlow dependency, good for streaming from cloud buckets. See
  [teleoperation-and-data-collection](teleoperation-and-data-collection.md).
- **ros2_control.** The controller-manager framework where a hardware interface exposes
  joint state and command interfaces and controllers are written once for sim and
  hardware. See [sim-first-workflow](sim-first-workflow.md) and
  [connecting-to-real-robots](connecting-to-real-robots.md).
- **RPE (relative pose error).** Error of relative motion over a fixed time or distance;
  the drift metric that complements ATE. See
  [state-estimation-and-localization](state-estimation-and-localization.md).
- **RTDE (Real-Time Data Exchange).** Universal Robots' state and I/O interface over TCP,
  paired with the reverse command channel that `ur_robot_driver` uses. See
  [connecting-to-real-robots](connecting-to-real-robots.md) and
  [operating-robot-arms](operating-robot-arms.md).
- **Ruckig.** Jerk-limited, time-optimal online trajectory generation per control cycle;
  the filter that belongs between a 10 to 30 Hz action stream and a 1 kHz joint loop. See
  [kinematics-dynamics-and-rotations](kinematics-dynamics-and-rotations.md).

## S

- **SEA (series elastic actuator).** A spring between the reduction and the load; torque is
  read from spring deflection, bandwidth is lower, and a policy sees a soft joint. See
  [compliant-mechanisms-and-actuation](compliant-mechanisms-and-actuation.md) and
  [sensors-and-actuators](sensors-and-actuators.md).
- **SLAM.** Simultaneous localization and mapping; slam_toolbox on a mobile base,
  ORB-SLAM3 inside the UMI gripper, ZED area memory on the camera. Texture, not
  compute, is the usual failure. See
  [state-estimation-and-localization](state-estimation-and-localization.md).
- **SROS2.** ROS 2 security: keystore and enclaves that enable DDS authentication, access
  control, and encryption; needed when the robot shares a plant network. See
  [ros2-in-depth](ros2-in-depth.md).

## T

- **TCP (tool centre point).** The tool tip pose in the flange frame, set on the pendant and
  found by the 4-point touch routine; distinct from TCP the transport protocol that RTDE
  and the xArm SDK run over. See
  [kinematics-dynamics-and-rotations](kinematics-dynamics-and-rotations.md) and
  [connecting-to-real-robots](connecting-to-real-robots.md).
- **Temporal ensembling.** Averaging the overlapping predictions of successive action
  chunks with exponential weights `w_i = exp(-m i)` so execution is smooth without
  waiting for a chunk to finish (ACT). See [imitation-learning](imitation-learning.md).
- **tf2.** The ROS 2 transform tree; `/tf_static` is latched, the buffer keeps 10 s, and a
  lookup at `now()` without a timeout throws. See [ros2-in-depth](ros2-in-depth.md).
- **TOPP-RA.** Time-optimal path parameterization under velocity, acceleration, or torque
  limits; for re-timing a planned path offline, not for online reaction. See
  [kinematics-dynamics-and-rotations](kinematics-dynamics-and-rotations.md).
- **Transporter Networks.** Pick-and-place from a top-down image by cross-correlating a
  crop around the pick pixel with dense scene features; goal-conditioned variants take a
  goal image. See [deformable-object-manipulation](deformable-object-manipulation.md) and
  [seita-2021-deformable-ravens](../papers/seita-2021-deformable-ravens.md).
- **TS 15066 (ISO/TS 15066:2016).** Collaborative operation modes and the body-region force
  and pressure limits for PFL; absorbed as normative text into ISO 10218:2025. See
  [safety-for-learned-policies](safety-for-learned-policies.md).

## U

- **URCap and URCapX.** Universal Robots' plugin formats (PolyScope 5 and PolyScope X); the
  External Control URCap must be in the running program for `ur_robot_driver` to take
  over. See [operating-robot-arms](operating-robot-arms.md) and
  [connecting-to-real-robots](connecting-to-real-robots.md).
- **URDF.** The XML robot description consumed by ros2_control, MoveIt, and the simulator
  importers; prefer the vendor file and diff joint limits against the datasheet. See
  [sim-first-workflow](sim-first-workflow.md).

## V

- **Visual servoing.** Closing a control loop on image features (image-based) or on an
  estimated pose (position-based); action-chunking policies replan at chunk boundaries
  rather than servo within them. See
  [conveyor-tracking-and-visual-servoing](conveyor-tracking-and-visual-servoing.md).
- **VLA (vision-language-action model).** A policy built on a vision-language model that
  takes images, a language instruction, and usually proprioception and outputs actions as
  tokens or through a diffusion or flow head. See
  [vision-language-action-models](vision-language-action-models.md).

## W

- **Washdown.** Daily high-pressure, hot, chemical cleaning of a food line; everything in
  the cell must survive it (IP69K, EHEDG materials) and it sets the maintenance window.
  See [meat-cutting-automation](meat-cutting-automation.md) and
  [fleet-operations](fleet-operations.md).
- **Wilson interval.** A binomial confidence interval that stays sane at small n and
  extreme p; at n = 10 and p about 0.8 the 95% width is about 0.45, which is why success
  rates need trial counts. See [policy-evaluation](policy-evaluation.md).

## Z

- **Zenoh.** The non-DDS `rmw_zenoh_cpp` middleware, Tier 1 from Kilted; the choice for
  crossing a WAN or WiFi where multicast discovery fails, with DDS kept inside the cell.
  See [ros2-in-depth](ros2-in-depth.md) and [fleet-operations](fleet-operations.md).
