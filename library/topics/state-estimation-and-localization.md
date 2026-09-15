---
title: State estimation, SLAM, and localization for mobile manipulation
date: 2026-09-05
tags: [topic, perception, slam, localization, vio, lidar, nav2, mobile-manipulation, ros2]
status: draft
source: synthesis
---

# State estimation, SLAM, and localization for mobile manipulation

Companion entries: `library/topics/perception-3d-sensing.md` (sensors, LiDAR
specs, time sync, REP 103/105 frames) and
`library/topics/perception-foundation-models.md` (open-vocabulary detectors
that feed semantic maps). This entry covers where the robot is, where the
things are, and how a policy or a planner consumes that.

## What it is

Three estimates, three consumers, three failure modes.

| Consumer | Needs | Frame | Tolerates jumps? |
|---|---|---|---|
| Manipulation policy (ACT, DP, VLA) | Smooth, low-latency base pose; object pose relative to the gripper camera; usually no map at all | `odom` or `base_link` | No. A pose jump mid-episode is an out-of-distribution observation |
| Navigation (Nav2) | Globally consistent pose in a metric map; a costmap; a goal | `map` | Yes. AMCL and SLAM corrections are expected |
| Task planner (LLM/VLM) | Semantic map: which object, which room, where; a place to send a goal | `map` plus labels | Yes, slowly |

REP 105 fixes the contract: `odom` is continuous but drifts without bound,
`map` is drift-free but may jump, the tree is `map -> odom -> base_link`
([REP 105](https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-0105.rst)).
The odometry source (wheels, VIO, LiDAR odometry) publishes `odom -> base_link`;
the localizer or SLAM (AMCL, slam_toolbox, ZED area memory) publishes the
correction `map -> odom`. `robot_localization` documents the same split: a
filter fusing "continuous position data such as wheel encoder odometry, visual
odometry, or IMU data" keeps `world_frame = odom`; one fusing "global absolute
position data that is subject to discrete jumps" sets `world_frame = map` and
"must look up the odom_frame to base_link_frame transformation and use it to
compute and broadcast the map_frame to odom_frame transformation"
([robot_localization docs](https://github.com/cra-ros-pkg/robot_localization/blob/ros2/doc/state_estimation_nodes.rst)).

## Why it matters in the field

- A mobile manipulator's policy is only as good as its base pose during the
  episode. Learned policies conditioned on base odometry see the drift as
  state noise and the loop-closure correction as a discontinuity; neither was
  in the training data unless you put it there.
- RealSense T265 is gone. Intel's PCN 118463-00 (2021-08-31) discontinued the
  T265 and T261 with last order 2022-02-28 and last shipment 2022-03-31, with
  the guidance "T265 will be best replaced by ... D455 or D435i with 3rd Party
  SLAM SW" ([Intel PCN](https://www.therobotreport.com/wp-content/uploads/2021/09/intel-realsense-end-of-life.pdf)).
  Every deployment now needs a software VIO decision.
- Nav2 is the default mobile stack and it expects the REP 105 tree, a
  `sensor_msgs/LaserScan` or `PointCloud2` for costmaps, and a `PoseStamped`
  goal in `map`; handing it a VLM's answer is a frame-conversion problem, not
  a research problem ([Nav2 Simple Commander](https://docs.nav2.org/rolling/configuration_and_development/simple_commander_api/simple_commander_api/)).
- Loop closure and relocalization are what make a long demo work at all:
  after tracking loss ORB-SLAM3 "starts a new map" and merges it "with
  previous maps when revisiting mapped areas"
  ([ORB-SLAM3, arXiv:2007.11898](https://arxiv.org/abs/2007.11898)); ZED's
  `area_memory` parameter is literally "Enable Loop Closing"
  ([ZED ROS 2 node](https://docs.stereolabs.com/docs/ros2/zed-node.md)).
- Semantic maps are how language reaches a nav goal: VLMaps "translate natural
  language commands into a sequence of open-vocabulary navigation goals ...
  directly localized in the map" ([VLMaps, arXiv:2210.05714](https://arxiv.org/abs/2210.05714)).

## Key methods table

### Visual and visual-inertial odometry

| System | Type | Sensors | ROS 2 | Notes | Source |
|---|---|---|---|---|---|
| ZED SDK positional tracking | Proprietary stereo VIO + SLAM, GPU | ZED stereo + IMU | Official `zed-ros2-wrapper`: publishes `map -> odom -> base_link` per REP 105, `odom` from "visual odometry" only, `map` from the fused tracker; `publish_map_tf`, `area_memory`, `floor_alignment`, `two_d_mode`, `save_area_memory_db_on_exit`; services `reset_odometry`, `set_pose` | Default SDK frame is IMAGE, y-down, millimetres; select `RIGHT_HANDED_Z_UP_X_FORWARD` and metres for ROS ([coordinate frames](https://docs.stereolabs.com/docs/positional-tracking/coordinate-frames.md)); needs CUDA | [ZED node docs](https://docs.stereolabs.com/docs/ros2/zed-node.md), [positional tracking](https://docs.stereolabs.com/docs/positional-tracking.md) |
| RealSense T265 | Proprietary VIO on-device | fisheye stereo + IMU | EOL | Do not design around it; see PCN above | [Intel PCN](https://www.therobotreport.com/wp-content/uploads/2021/09/intel-realsense-end-of-life.pdf) |
| Isaac ROS Visual SLAM (cuVSLAM) | GPU stereo VIO + loop closure | stereo (RealSense, ZED, Hawk GMSL), optional IMU, multi-camera | ROS 2 Jazzy on Jetson Orin/Thor, x86 Ampere+ | KITTI 2012: 0.94% translation, 0.0019 deg/m rotation, 0.007 s/frame on AGX Xavier (vendor figures) | [Isaac ROS VSLAM](https://nvidia-isaac-ros.github.io/repositories_and_packages/isaac_ros_visual_slam/index.html) |
| OpenVINS | MSCKF sliding-window EKF | mono or synchronized stereo + IMU | ROS 1 and ROS 2 builds | Online calibration of camera-IMU transform, time offset, camera and inertial intrinsics; won IROS 2019 FPV VIO competition | [docs](https://docs.openvins.com/), [repo](https://github.com/rpng/open_vins) |
| VINS-Fusion | Optimization-based, loop closure | mono+IMU, stereo, stereo+IMU, +GPS demo | README targets ROS Kinetic/Melodic; ROS 2 via community forks (unverified) | Online spatial and temporal camera-IMU calibration | [repo](https://github.com/HKUST-Aerial-Robotics/VINS-Fusion) |
| Kimera | VIO + pose graph + mesh + metric-semantic map, CPU | stereo + IMU, semantic images | ROS 1 in the original release; ROS 2 status (unverified) | Basis of Hydra's front end | [Kimera, arXiv:1910.02490](https://arxiv.org/abs/1910.02490), [Kimera-VIO](https://github.com/MIT-SPARK/Kimera-VIO) |
| ORB-SLAM3 | Feature-based, MAP visual-inertial, multi-map | mono/stereo/RGB-D, pinhole or fisheye, +IMU | No official ROS 2; community wrappers (unverified) | Stereo-inertial 3.6 cm average on EuRoC, 9 mm on TUM-VI room | [arXiv:2007.11898](https://arxiv.org/abs/2007.11898), [repo](https://github.com/UZ-SLAMLab/ORB_SLAM3) |

### LiDAR SLAM and odometry

| System | Type | Sensors | ROS 2 | Notes | Source |
|---|---|---|---|---|---|
| SLAM Toolbox | 2D pose-graph SLAM, sync/async/localization/lifelong modes | 2D `LaserScan` + odometry | "the currently supported ROS2-SLAM library"; publishes `map -> odom` | Serialize the pose graph and continue mapping later; "5x+ real-time up to about 30,000 sq. ft." | [repo](https://github.com/SteveMacenski/slam_toolbox), [JOSS 2021](https://joss.theoj.org/papers/10.21105/joss.02783) |
| Cartographer | 2D/3D graph SLAM | LiDAR + IMU (+ odom) | ROS fork "only maintained in a limited capacity" | Upstream: "no longer actively maintained ... no new development"; fine for existing configs, not for new ones | [cartographer](https://github.com/cartographer-project/cartographer) |
| FAST-LIO2 | Tightly coupled iterated EKF, direct raw-point registration, ikd-Tree | 3D LiDAR + IMU (must be synchronized) | Upstream is ROS 1 (Melodic+); ROS 2 via community port | Livox Avia/Horizon/Mid-360, Velodyne, Ouster; "up to 100 Hz odometry and mapping" | [arXiv:2107.06829](https://arxiv.org/abs/2107.06829), [repo](https://github.com/hku-mars/FAST_LIO), [ROS 2 port](https://github.com/Ericsii/FAST_LIO_ROS2) |
| LIO-SAM | Factor-graph LiDAR-inertial with loop closure and GPS factor | 3D LiDAR with ring and time fields + 9-axis IMU | `ros2` branch | "only works with a 9-axis IMU"; loop closure is "proof of concept" ICP | [arXiv:2007.00258](https://arxiv.org/abs/2007.00258), [repo](https://github.com/TixiaoShan/LIO-SAM) |
| KISS-ICP | Point-to-point ICP odometry, adaptive threshold, no features | 3D LiDAR only, no IMU | ROS 2 package; `pip install kiss-icp` | "just works ... without tunning any parameter"; faster than sensor rate on all reported datasets; odometry only, no loop closure | [arXiv:2209.15397](https://arxiv.org/abs/2209.15397), [repo](https://github.com/PRBonn/kiss-icp) |
| Drivers | Ouster: `/ouster/points`, `/ouster/imu`, branch `ros2` for Humble to Lyrical. Livox ROS Driver 2: HAP, Mid-360, Avia2; Foxy/Humble/Jazzy; PointCloud2 or Livox custom message | | | Livox custom message keeps per-point time for de-skew | [ouster-ros](https://github.com/ouster-lidar/ouster-ros), [livox_ros_driver2](https://github.com/Livox-SDK/livox_ros_driver2) |

### Nav2 in 2026

From the [Nav2 docs](https://docs.nav2.org/rolling/) (Rolling; Jazzy and
Lyrical in active support):

- **BT Navigator** runs a behaviour tree that calls planner, controller,
  behavior, smoother, docking, and route servers over actions. Swap the XML,
  not the code, to change recovery logic.
- **Localization**: AMCL against a static map, `min_particles` 500 /
  `max_particles` 2000 default, `laser_model_type` beam / likelihood_field /
  likelihood_field_prob, update after 0.25 m or 0.2 rad, `tf_broadcast`
  publishes `map -> odom`, `transform_tolerance` 1.0 s
  ([AMCL](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/others/configuring_amcl/)).
  slam_toolbox in localization mode is the alternative when the map evolves.
- **Costmaps**: static, obstacle, voxel, range, inflation, denoise layers;
  keepout, speed, and binary filters
  ([costmap_2d](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/costmap_2d/)).
- **Planners**: NavFn; Smac 2D ("circular or omnidirectional robots"), Smac
  Hybrid-A* ("ackermann and car-like"), Smac State Lattice ("arbitrary robot
  kinematics"); Theta*. On a 75 m path: Hybrid-A* 144 ms, Lattice 113 ms,
  2D 243 ms, NavFn 146 ms ([Smac](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/planners_plugins/smac/)).
- **Controllers**: DWB, MPPI (sampling-based MPC, diff/omni/ackermann motion
  models, plugin critics, "100+ Hz on a modest Intel processor"), Regulated
  Pure Pursuit, Rotation Shim, Graceful
  ([MPPI](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/controller_plugins/mppi_controller/configuring_mppic/)).
- **Docking**: `opennav_docking` server with `SimpleChargingDock` and
  `SimpleNonChargingDock` plugins; dock pose from a database or an external
  detector (`use_external_detection_pose`, offsets "setup to work out of the
  box with Apriltags detectors in image_proc and isaac_ros"); BT nodes
  `DockRobot` / `UndockRobot`
  ([docking server](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/configuring_docking_server/)).
- **Route Server**: graph-based routing from a file (GeoJSON loader) that can
  "fully replace freespace planning" along fixed corridors
  ([route server](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/route_server/configuring_route_server/)).
- **Handing a goal from a VLM or policy**: the Simple Commander API takes
  `PoseStamped` (`goToPose`), a list (`goThroughPoses`, `followWaypoints`),
  or a dock (`dockRobot(dock_id)`), and `waitUntilNav2Active(navigator=
  'bt_navigator', localizer='amcl')` blocks until lifecycle nodes are active
  ([Simple Commander](https://docs.nav2.org/rolling/configuration_and_development/simple_commander_api/simple_commander_api/)).
  The VLM's job is to produce an (x, y, yaw) in `map`; the semantic map's job
  is to turn "the red mug on the kitchen counter" into that triple.

### Semantic mapping and task planning

| System | Representation | What it gives a planner | Source |
|---|---|---|---|
| Hydra | Real-time 3D scene graph: mesh, places from an ESDF, rooms via community detection, objects; loop closure with hierarchical descriptors and scene-graph optimization | Rooms and places to route between; objects with poses | [arXiv:2201.13360](https://arxiv.org/abs/2201.13360), [Hydra-ROS (ROS 2 Jazzy)](https://github.com/MIT-SPARK/Hydra-ROS) |
| ConceptGraphs | Open-vocabulary object graph built from 2D foundation models fused by multi-view association; edges are spatial relations | Language queries over objects and relations, "without the need to collect large 3D datasets or finetune models" | [arXiv:2309.16650](https://arxiv.org/abs/2309.16650), [repo](https://github.com/concept-graphs/concept-graphs) |
| VLMaps | Dense visual-language features fused into a 3D reconstruction | Open-vocabulary goals localized in the map, including spatial phrases ("three meters to the right of the chair") | [arXiv:2210.05714](https://arxiv.org/abs/2210.05714), [repo](https://github.com/vlmaps/vlmaps) |
| Clio | Task-driven open-set scene graph via information bottleneck | Keeps only objects and regions relevant to the listed tasks | [arXiv:2404.13696](https://arxiv.org/abs/2404.13696) |
| GraphEQA | Hydra-style scene graph plus task images as VLM memory; hierarchical planning over the graph | Embodied QA and exploration; beat baselines on HM-EQA and OpenEQA "with higher success rates and fewer planning steps"; real home and office demos | [arXiv:2412.14480](https://arxiv.org/abs/2412.14480), [repo](https://github.com/SaumyaSaxena/GraphEQA) |

### Evaluation

- **ATE** (absolute trajectory error): associate estimate and ground truth by
  timestamp, align with SVD (SE(3), optionally Sim(3) for monocular), report
  "RMSE absolute translational error in meters after alignment". **RPE**
  (relative pose error): error of relative motion over a fixed delta (time,
  distance, angle, frames), "suitable to measure drift"
  ([TUM RGB-D tools](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/tools)).
- **evo** computes both: `evo_ape`, `evo_rpe`; reads TUM, KITTI, EuRoC CSV,
  ROS 1 and ROS 2 bags; `pip install evo`, Python 3.10+
  ([evo](https://github.com/MichaelGrupp/evo)).
- **Benchmarks**: [TUM RGB-D](https://cvg.cit.tum.de/data/datasets/rgbd-dataset)
  (handheld, motion capture ground truth), [EuRoC MAV](https://projects.asl.ethz.ch/datasets/doku.php?id=kmavvisualinertialdatasets)
  (stereo + IMU on a drone, Vicon/Leica ground truth),
  [KITTI odometry](https://www.cvlibs.net/datasets/kitti/eval_odometry.php)
  (car; translation error in % and rotation in deg/m over segments).
- **In the field** there is no ground truth. Substitutes: return-to-start
  error (drive a loop, measure the closing gap before loop closure), a
  total-station or tape survey of 5 to 10 floor marks and the robot's pose
  at each, and AprilTag-relative pose repeatability at a fixed dock.

## Practical recipe

1. **Decide what the policy consumes.** Default: base pose from `odom` only,
   never `map`, and object pose from the wrist camera. If the task needs the
   map (long-horizon fetch), put the discontinuity where the policy is not
   running: navigate in `map`, then hand off to the policy with a fresh
   `odom` origin. ZED's `reset_odometry` service does exactly this, "setting
   the new odometry value to the latest camera pose"
   ([ZED node docs](https://docs.stereolabs.com/docs/ros2/zed-node.md)).
2. **Pick the odometry source.** Wheeled indoor with a 2D LiDAR: wheel odom
   + IMU through `robot_localization` EKF (`world_frame = odom`,
   `two_d_mode: true`). Legged, tracked, or outdoor: LiDAR-inertial
   (FAST-LIO2 or LIO-SAM) or a stereo VIO (ZED, cuVSLAM, OpenVINS). Livox
   Mid-360 plus FAST-LIO2 is the common low-cost 3D choice
   ([FAST-LIO](https://github.com/hku-mars/FAST_LIO)).
3. **Pick the map and localizer.** Flat indoor: slam_toolbox to map, then
   AMCL or slam_toolbox localization mode. Multi-floor or 3D: LIO-SAM map
   with loop closure, then a 3D-to-2D projection for Nav2 costmaps, or
   Hydra if you need rooms and objects.
4. **Wire the frames.** Exactly one publisher of `odom -> base_link` and one
   of `map -> odom`. Disable the second one (`publish_map_tf: false` on ZED,
   `tf_broadcast: false` on AMCL) or the tree forks. Verify with
   `ros2 run tf2_tools view_frames`.
5. **Calibrate and time-sync.** Camera-IMU extrinsics and time offset with
   Kalibr, or let OpenVINS estimate them online; LiDAR-IMU must be
   "Synchronized" (FAST-LIO README). Put LiDAR on PTP where supported
   (`perception-3d-sensing.md`). Log `|t_lidar - t_imu|` and the IMU rate.
6. **Fuse.** `robot_localization` EKF with `odom0` (wheels), `imu0`, and
   optionally `odom1` (VIO); set per-sensor `_config` masks in the sensor's
   frame, use `_differential: true` for a second absolute yaw source to avoid
   oscillation, `imu0_remove_gravitational_acceleration: true`
   ([robot_localization docs](https://github.com/cra-ros-pkg/robot_localization/blob/ros2/doc/state_estimation_nodes.rst)).
7. **Evaluate before the policy sees it.** Record a bag, run `evo_rpe` with
   `--delta 1 --delta_unit m` against the best available reference (LiDAR
   SLAM trajectory as pseudo ground truth for a VIO under test is acceptable
   if stated). Report drift per metre and per minute in the experiment record.
8. **Connect the planner.** VLM or scene-graph query returns an object;
   look up its `map` pose; offset by a standoff; `goToPose`; on arrival
   `reset_odometry` (or equivalent) and start the manipulation policy.
   Log the nav goal, the arrival pose, and the residual for every episode.
9. **Docking and resets.** Use `opennav_docking` with an AprilTag on the dock
   so every episode starts from a repeatable pose; that pose is your best
   free ground truth.

## Practical gotchas

- **Loop closure jumps break policies.** `map` is "subject to discrete
  jumps" by design ([robot_localization docs](https://github.com/cra-ros-pkg/robot_localization/blob/ros2/doc/state_estimation_nodes.rst));
  a policy reading `map -> base_link` will see the base teleport. Feed
  policies `odom` and treat corrections as episode boundaries.
- **Two TF publishers.** ZED (`publish_map_tf`) and AMCL both want
  `map -> odom`; ZED and the EKF both want `odom -> base_link`. Symptom: the
  robot in RViz flickers between two poses. Fix per step 4 above.
- **Units and axes from the ZED SDK.** Defaults are millimetres and an image
  frame (y down); ROS needs metres and `RIGHT_HANDED_Z_UP_X_FORWARD`
  ([coordinate frames](https://docs.stereolabs.com/docs/positional-tracking/coordinate-frames.md)).
  The ROS 2 wrapper handles it; raw SDK use does not.
- **Wheel slip.** Wheel odometry integrates slip as motion; on smooth floors,
  ramps, and during hard stops the EKF trusts it unless the covariance says
  otherwise. Fuse an IMU yaw rate with wheels and cap wheel-odom covariance
  low only when the floor is known (from field, unverified).
- **IMU requirements differ.** LIO-SAM needs a 9-axis IMU with orientation;
  FAST-LIO2 accepts 6-axis; KISS-ICP needs none. Buying the wrong IMU is a
  week of debugging ([LIO-SAM](https://github.com/TixiaoShan/LIO-SAM)).
- **Point cloud fields.** LIO-SAM needs `ring` and per-point `time`; Livox
  exposes per-point time only in its custom message, not in plain
  PointCloud2 XYZI ([livox_ros_driver2](https://github.com/Livox-SDK/livox_ros_driver2)).
- **AMCL needs a kick.** Without `set_initial_pose` or an `initial_pose`
  message it waits; and `transform_tolerance` post-dates the transform, so a
  1 s default can mask a stalled localizer ([AMCL](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/others/configuring_amcl/)).
- **Cartographer configs are a dead end.** Upstream states "no new
  development is currently taking place, including issue response"
  ([cartographer](https://github.com/cartographer-project/cartographer)).
- **Time offsets between camera and IMU** of a few milliseconds ruin VIO;
  OpenVINS and VINS-Fusion estimate the offset online for a reason. Measure
  it with Kalibr once per rig.
- **GPU VIO on the same Jetson as the policy** competes for the GPU; ZED
  neural depth plus tracking plus a diffusion policy on one Orin needs a
  measured budget (from field, unverified).
- **Semantic maps go stale.** ConceptGraphs and VLMaps are built once;
  moved objects stay where they were. Re-query with the wrist camera before
  grasping.

## What a forward-deployed engineer must be able to do

- [ ] Draw the REP 105 tree for a given robot, name every publisher, and
      prove it with `view_frames`.
- [ ] Bring up one VIO (ZED or cuVSLAM) and one LiDAR odometry (KISS-ICP or
      FAST-LIO2) in ROS 2 Humble and compare them with `evo_rpe` on the same bag.
- [ ] Configure `robot_localization` EKF for wheels + IMU (+ VIO) with
      correct frames, `two_d_mode`, and differential settings.
- [ ] Map a site with slam_toolbox, save the pose graph, and localize on it
      the next day with AMCL and with slam_toolbox localization mode.
- [ ] Configure Nav2 for the robot's footprint and kinematics: pick a Smac
      planner, MPPI or RPP, and write the BT XML for the recovery you want.
- [ ] Send a goal from Python via the Simple Commander, handle the result,
      and hand off to a manipulation policy with a fresh odometry origin.
- [ ] Set up `opennav_docking` with an AprilTag and measure docking
      repeatability over 20 trials.
- [ ] Build a semantic map (ConceptGraphs or Hydra) of one room and answer a
      "where is X" query with a `map` pose.
- [ ] Explain ATE vs RPE to a customer and report drift per metre.

## Open questions to learn hands-on

- How much odometry drift per metre does our manipulation policy tolerate
  before success rate drops? Inject synthetic drift into the base pose input
  and count trials.
- ZED tracking vs cuVSLAM on the same stereo pair in the customer's
  environment (glass, long corridors): `evo_rpe` at 1 m deltas over 200 m.
- Whether KISS-ICP alone (no IMU) is enough for the base at our speeds, or
  FAST-LIO2 is needed.
- Real cost of running Hydra or ConceptGraphs online on the deployment
  compute, and whether a once-per-visit offline map is enough.
- Time-to-relocalize after a kidnapped-robot event for AMCL vs ZED area
  memory vs slam_toolbox localization mode.
- Whether a VLM should output a `map` pose directly or a scene-graph node id
  that a deterministic lookup converts. The second is auditable.

## Related entries

- `library/topics/perception-3d-sensing.md` (LiDAR specs, PTP, de-skew, REP 103)
- `library/topics/perception-foundation-models.md` (detectors behind semantic maps)
- `library/topics/vision-language-action-models.md` (what a VLA expects as state)
- `library/topics/policy-evaluation.md` (trial counts, reporting)
- `library/tools/ros2-humble.md`
- `sops/field-deployment-checklist.md`

## Sources

- Frames and fusion: [REP 105](https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-0105.rst), [robot_localization state estimation nodes](https://github.com/cra-ros-pkg/robot_localization/blob/ros2/doc/state_estimation_nodes.rst), [robot_localization repo](https://github.com/cra-ros-pkg/robot_localization)
- VIO: [ZED node docs](https://docs.stereolabs.com/docs/ros2/zed-node.md), [ZED positional tracking](https://docs.stereolabs.com/docs/positional-tracking.md), [ZED coordinate frames](https://docs.stereolabs.com/docs/positional-tracking/coordinate-frames.md), [Intel PCN 118463-00](https://www.therobotreport.com/wp-content/uploads/2021/09/intel-realsense-end-of-life.pdf), [Isaac ROS Visual SLAM](https://nvidia-isaac-ros.github.io/repositories_and_packages/isaac_ros_visual_slam/index.html), [OpenVINS docs](https://docs.openvins.com/), [open_vins](https://github.com/rpng/open_vins), [VINS-Fusion](https://github.com/HKUST-Aerial-Robotics/VINS-Fusion), [Kimera paper](https://arxiv.org/abs/1910.02490), [Kimera-VIO](https://github.com/MIT-SPARK/Kimera-VIO), [ORB-SLAM3 paper](https://arxiv.org/abs/2007.11898), [ORB_SLAM3](https://github.com/UZ-SLAMLab/ORB_SLAM3)
- LiDAR: [slam_toolbox](https://github.com/SteveMacenski/slam_toolbox), [SLAM Toolbox JOSS](https://joss.theoj.org/papers/10.21105/joss.02783), [cartographer](https://github.com/cartographer-project/cartographer), [FAST-LIO2 paper](https://arxiv.org/abs/2107.06829), [FAST_LIO](https://github.com/hku-mars/FAST_LIO), [FAST_LIO_ROS2](https://github.com/Ericsii/FAST_LIO_ROS2), [LIO-SAM paper](https://arxiv.org/abs/2007.00258), [LIO-SAM](https://github.com/TixiaoShan/LIO-SAM), [KISS-ICP paper](https://arxiv.org/abs/2209.15397), [kiss-icp](https://github.com/PRBonn/kiss-icp), [ouster-ros](https://github.com/ouster-lidar/ouster-ros), [livox_ros_driver2](https://github.com/Livox-SDK/livox_ros_driver2)
- Nav2: [docs home](https://docs.nav2.org/rolling/), [AMCL](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/others/configuring_amcl/), [costmap_2d](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/costmap_2d/), [Smac planners](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/planners_plugins/smac/), [MPPI](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/controller_plugins/mppi_controller/configuring_mppic/), [docking server](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/configuring_docking_server/), [route server](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/route_server/configuring_route_server/), [Simple Commander API](https://docs.nav2.org/rolling/configuration_and_development/simple_commander_api/simple_commander_api/)
- Semantic maps: [Hydra](https://arxiv.org/abs/2201.13360), [Hydra-ROS](https://github.com/MIT-SPARK/Hydra-ROS), [ConceptGraphs](https://arxiv.org/abs/2309.16650), [concept-graphs](https://github.com/concept-graphs/concept-graphs), [VLMaps](https://arxiv.org/abs/2210.05714), [vlmaps](https://github.com/vlmaps/vlmaps), [Clio](https://arxiv.org/abs/2404.13696), [GraphEQA](https://arxiv.org/abs/2412.14480), [GraphEQA repo](https://github.com/SaumyaSaxena/GraphEQA)
- Evaluation: [TUM RGB-D tools](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/tools), [TUM RGB-D dataset](https://cvg.cit.tum.de/data/datasets/rgbd-dataset), [EuRoC MAV](https://projects.asl.ethz.ch/datasets/doku.php?id=kmavvisualinertialdatasets), [KITTI odometry](https://www.cvlibs.net/datasets/kitti/eval_odometry.php), [evo](https://github.com/MichaelGrupp/evo)
