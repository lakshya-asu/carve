---
title: The sim-first daily workflow
date: 2026-09-05
tags: [topic, simulation, digital-twin, isaac-lab, mujoco, gazebo, ros2, evaluation, ci, workflow]
status: draft
source: synthesis (primary links inline and in Sources)
---

# The sim-first daily workflow

## What it is

The sim-first workflow is the daily loop of an engineer who has a GPU every day and a real robot
cell on office days: build a simulation of that specific cell, run every change in it first, and
book robot time only for what the sim cannot answer. This note is the engineering playbook for
that loop. [sim-to-real](sim-to-real.md) already compares simulators and covers transfer
techniques (domain randomization, system identification, teacher-student); this note answers the
narrower questions: which simulator for this task, how to build a twin of this cell you can trust,
how to make one codebase drive both, how to evaluate at scale, and what to check before walking to
the robot.

The 2026 tool state as of this note's date. NVIDIA shipped Isaac Sim 5.0 (Aug 2025), 5.1 (Oct
2025) and 6.0 (Jun 2026; 6.0.1 on 22 Jun 2026)
([releases](https://github.com/isaac-sim/IsaacSim/releases)). Isaac Lab 2.3 GA (30 Oct 2025) runs
on Isaac Sim 5.1 ([announcement](https://github.com/isaac-sim/IsaacLab/discussions/3898)); Isaac Lab
3.0 is in beta (beta 2 on 23 Jun 2026) on Isaac Sim 6.0 with multi-backend physics (PhysX and
Newton), a pluggable renderer and a kit-less install mode
([beta 2 notes](https://github.com/isaac-sim/IsaacLab/discussions/6249)). MuJoCo cuts releases
monthly and is at 3.12.0 (20 Aug 2026); the 3.5 release (13 Feb 2026) made MuJoCo Warp official as
part of the Newton project and added delayed actuators and sensors plus a system identification
toolbox ([MuJoCo 3.5](https://github.com/google-deepmind/mujoco/discussions/3094),
[3.12.0](https://github.com/google-deepmind/mujoco/releases/tag/3.12.0)). MJX now has two backends,
MJX-JAX and MJX-Warp ([MJX docs](https://mujoco.readthedocs.io/en/stable/mjx.html)). Gazebo Jetty
(LTS, Sep 2025 to May 2031) pairs with ROS 2 Lyrical and Rolling; Harmonic (LTS, to May 2029) with
Jazzy; Ionic (to Dec 2026) with Kilted; Humble's default is still Fortress
([Gazebo releases](https://gazebosim.org/docs/latest/releases/),
[pairing](https://gazebosim.org/docs/latest/ros_installation/)). ManiSkill 3.0.1 (21 Apr 2026) and
Genesis World 1.3.3 (13 Aug 2026) are the current PyPI releases
([mani-skill](https://pypi.org/project/mani-skill/), [genesis-world](https://pypi.org/project/genesis-world/)).

## Why it matters in the field

- Robot days are scarce and the cell is shared. Every bug found in sim is a bug not found while a
  customer watches. The TRI LBM study ran 1,800 controlled real trials and 200 sim rollouts per task
  per policy per condition, and states that real testing alone is "prohibitively expensive and time
  consuming" for meaningful statistics ([Barreiros et al. 2025](https://arxiv.org/abs/2507.05331)).
  A field budget is one to two orders of magnitude smaller, so sim carries the statistical load.
- A twin that matches the cell turns "the policy shook on hardware" from a robot-day incident into
  an afternoon debug session. Most such reports trace to control-rate and gain mismatches that a
  twin exposes ([sim-to-real gotchas](sim-to-real.md#practical-gotchas-from-the-field-and-the-literature)).
- Sim evaluation ranks checkpoints when it is visually matched to the cell; SimplerEnv reports rank
  correlation against ~1,500 paired real trials ([Li et al. 2024](https://arxiv.org/abs/2405.05941)).
  Without matching, sim numbers mislead.
- The same-code pattern means the stack that ran overnight in CI is the one that runs on the cell.
  Divergent code paths are where field failures hide (from field, unverified).

## Simulator choice by task class

The lab default is ROS 2 Humble (CLAUDE.md), which fixes the Gazebo pairing and the bridge choice.

| Task class | First choice (2026) | Why | ROS 2 path | Second choice |
|---|---|---|---|---|
| Tabletop manipulation, state or RGB-D policies | Isaac Lab 2.3.x on Isaac Sim 5.1 for training; ManiSkill3 for cheap RGB eval | PhysX GPU articulations, RTX sensors, mature URDF importer; ManiSkill3 renders RGBD plus segmentation at 30k+ FPS on a 4090 and ships real2sim examples ([Tao et al. 2024](https://arxiv.org/abs/2410.00425)) | Isaac Sim `isaacsim.ros2.bridge`, Humble and Jazzy with bundled ROS 2 libs ([ROS 2 install](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_ros.html)); ManiSkill3 has no ROS 2 path (none documented) | MuJoCo 3.12 + `mujoco_ros2_control` when the cell has no RTX GPU |
| Contact-rich manipulation (insertion, screwing, cables) | MuJoCo 3.12 (CPU) for fidelity, MuJoCo Warp for scale | Soft-contact model with explicit `solref`/`solimp`; MJWarp still lacks `noslip`, PGS and plugin actuators ([mujoco_warp](https://github.com/google-deepmind/mujoco_warp)) | `mujoco_ros2_control` ([ros-controls](https://github.com/ros-controls/mujoco_ros2_control)) | Isaac Lab FORGE/AutoMate envs (2.2+) ([release notes](https://isaac-sim.github.io/IsaacLab/main/source/refs/release_notes.html)) |
| Mobile manipulation | Isaac Sim + Isaac Lab | Nav2 and MoveIt talk to the same bridge; lidar and depth are RTX-simulated | Isaac Sim ROS 2 bridge; `IsaacSim-ros_workspaces` has `humble_ws` and `jazzy_ws` with Nav2/MoveIt examples ([repo](https://github.com/isaac-sim/IsaacSim-ros_workspaces)) | Gazebo + `ros_gz` for integration only |
| Legged locomotion, humanoid whole-body | Isaac Lab (PhysX) or mjlab / MuJoCo Warp | Thousands of envs per GPU; mjlab reproduces the Isaac Lab manager API on MJWarp ([mjlab](https://github.com/mujocolab/mjlab)) | Deploy over ROS 2 at the same control rate; no sim bridge needed during training | MuJoCo Playground on MJX-JAX or MJWarp ([playground](https://github.com/google-deepmind/mujoco_playground)) |
| Perception-heavy (visual servoing, RGB policies, VLA eval) | Isaac Sim with Replicator; NuRec (Gaussian-splat) scenes for photoreal twins, since 5.0 | Ray-traced sensors; NuRec renders a phone-scanned cell ([5.0 notes](https://docs.isaacsim.omniverse.nvidia.com/5.0.0/overview/release_notes.html), [NVIDIA blog](https://developer.nvidia.com/blog/reconstruct-a-scene-in-nvidia-isaac-sim-using-only-a-smartphone/)) | Bridge publishes `sensor_msgs/Image` and `CameraInfo` | ManiSkill3 with real background overlay ([SimplerEnv](https://github.com/simpler-env/SimplerEnv)) |
| ROS 2 stack integration, customer demo | Gazebo (Fortress on Humble; Harmonic on Jazzy) | Reference sim for ROS 2; `ros_gz` and `gz_ros2_control` are first-party ([pairing](https://gazebosim.org/docs/latest/ros_installation/)) | `ros_gz_bridge` ([ros_gz](https://github.com/gazebosim/ros_gz)) | Isaac Sim when RTX sensors matter |
| Deformables, fluids, soft grippers | Genesis World 1.3.x, or Isaac Lab 3.0 beta VBD cloth | Genesis couples MPM/FEM/PBD and parses URDF, MJCF and USD; every 1.2 and 1.3 minor carried a "Breaking" section; no ROS bridge documented ([releases](https://github.com/Genesis-Embodied-AI/genesis-world/releases)) | None documented; wrap in Python | Real data; see [decision guide](sim-to-real.md#decision-guide-invest-in-sim-or-collect-real-data) |

Rules that follow. Train where the GPU is (Isaac Lab, MJWarp, ManiSkill3); integrate where ROS 2 is
native (Gazebo, Isaac Sim bridge); never build a customer twin in a simulator with no ROS 2 path
unless the policy is proprioceptive. Pin one Isaac Sim + Isaac Lab pair per project and do not
chase 6.0 / 3.0 beta mid-deployment: 6.0 moved to Python 3.12 and driver 595+, and its Newton
backend is labelled experimental ([6.0 announcement](https://github.com/isaac-sim/IsaacSim/discussions/538),
[requirements](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html)).

## Building the digital twin (procedure)

Build in the order that catches the biggest errors first: geometry and kinematics, then mass and
limits, then control, then sensors, then contact. Every value goes into a `TWIN.md` next to the
scene with its provenance (measured, datasheet, vendor file, guessed), mirroring the `DATASET.md`
rule in CLAUDE.md.

### 1. Robot model

1. Get the vendor URDF and meshes. Franka FR3 and Panda, UR5e, xArm7, Unitree Go2 and G1, Robotiq
   2F-85, LEAP hand and Spot have MJCF ports in MuJoCo Menagerie with A+ to C quality grades and
   per-model licences ([mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie)).
   Prefer the vendor URDF over a community one; diff joint limits against the datasheet.
2. Convert. Isaac Lab ships `scripts/tools/convert_urdf.py`, `convert_mjcf.py` and
   `convert_mesh.py` ([import new asset](https://isaac-sim.github.io/IsaacLab/main/source/how-to/import_new_asset.html));
   the Isaac Sim extensions are `isaacsim.asset.importer.urdf` and `isaacsim.asset.importer.mjcf`.
   MuJoCo loads URDF directly and its `compile` sample writes MJCF
   ([URDF extensions](https://mujoco.readthedocs.io/en/stable/modeling.html#urdf-extensions));
   `obj2mjcf` splits meshes and runs CoACD convex decomposition ([obj2mjcf](https://github.com/kevinzakka/obj2mjcf)).
3. Check what conversion dropped. Print each link's mass and inertia diagonal from the loaded
   model and compare to CAD or the URDF. The Isaac Sim URDF importer uses one convex hull per link
   unless "Convex Decomposition" is chosen, computes inertia from density unless "Import Inertia
   Tensor" is on, and gives massless links a "Default Density"
   ([URDF importer](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/importer_exporter/ext_isaacsim_asset_importer_urdf.html));
   MuJoCo also collides on the convex hull of each mesh. Run a zero-torque drop test and a
   gravity-compensation hold and compare with the real arm with brakes released.
4. Collision geometry. Decompose the links that touch things (fingers, wrist, forearm). Isaac Sim
   6.0's importer merges over-constrained joints into one D6 joint; check the joint count after
   import ([6.0 notes](https://docs.isaacsim.omniverse.nvidia.com/latest/overview/release_notes.html)).

### 2. Cell geometry and fixtures

1. Measure: table height, robot base pose in the world frame, fixture positions, camera mounts.
   Use the real TF frame names (REP 103/105, CLAUDE.md).
2. Scan what cannot be measured. RialTo's pipeline is a phone scan (Polycam, nerfstudio), GLTF to
   USD, then a GUI to articulate drawers and doors, then Isaac Sim
   ([Torne et al. 2024](https://arxiv.org/abs/2403.03949)). Photogrammetry: RealityScan (free under
   USD 1M revenue, else USD 1,250 per seat per year), Meshroom
   ([RealityScan licence](https://www.realityscan.com/en-US/license), [Meshroom](https://github.com/alicevision/Meshroom)).
   Splats give appearance; a physics mesh comes from SuGaR or 2D Gaussian Splatting surface
   extraction ([Guedon and Lepetit 2024](https://arxiv.org/abs/2311.12775),
   [Huang et al. 2024](https://arxiv.org/abs/2403.17888)). URDFormer predicts articulation from an
   image ([Chen et al. 2024](https://arxiv.org/abs/2405.11656)); by hand is faster for one cell.

### 3. Objects and asset sources

| Source | Content | Licence | Note |
|---|---|---|---|
| Your own scans or customer CAD | The customer's parts | Yours | CAD beats scans; photogrammetry for matte parts, splats for shiny |
| [YCB](https://www.ycbbenchmarks.com/) | 77 household objects | (unverified; site unreachable 2026-09-05) | Standard for grasp benchmarks |
| [Google Scanned Objects](https://research.google/blog/scanned-objects-by-google-research-a-dataset-of-3d-scanned-common-household-items/) | 1,030 scanned products | CC BY 4.0 | Clutter distractors |
| [OmniObject3D](https://github.com/omniobject3d/OmniObject3D) | 6,000 scanned objects, 190 categories | CC BY 4.0 | ([Wu et al. 2023](https://arxiv.org/abs/2301.07525)) |
| [Objaverse 1.0](https://arxiv.org/abs/2212.08051) / [XL](https://arxiv.org/abs/2307.05663) | 800k / 10M web objects | Dataset ODC-By 1.0; per object 721k CC-BY, 25k CC-BY-NC, 52k CC-BY-NC-SA ([HF card](https://huggingface.co/datasets/allenai/objaverse)) | Filter by licence; no scale, mass or watertightness |
| ManiSkill3 assets | Curated task objects | CC BY-NC 4.0 ([licence](https://github.com/mani-skill/ManiSkill#license)) | Not for commercial deliverables |
| NVIDIA SimReady packs | Warehouse and factory props | "Isaac Sim Additional Software and Materials License" ([FAQ](https://docs.isaacsim.omniverse.nvidia.com/latest/common/license-faq.html)); SimReady terms unverified | Ship with mass and collision ([spec](https://docs.omniverse.nvidia.com/simready/latest/overview/simready-spec.html)) |

### 4. Cameras

1. Calibrate with `camera_calibration` (image_pipeline; models `plumb_bob`, `rational_polynomial`,
   `equidistant`) and read `k`, `d`, `distortion_model` from the published `CameraInfo` (lowercase
   field names in ROS 2) ([camera_calibration](https://github.com/ros-perception/image_pipeline/tree/rolling/camera_calibration),
   [CameraInfo.msg](https://github.com/ros2/common_interfaces/blob/rolling/sensor_msgs/msg/CameraInfo.msg)).
   Multi-camera and camera-IMU rigs: kalibr ([ethz-asl/kalibr](https://github.com/ethz-asl/kalibr)).
2. Hand-eye: `cv::calibrateHandEye` (Tsai, Park, Horaud, Andreff, Daniilidis) behind
   `easy_handeye2` or the `ros2` branch of `moveit_calibration` (maturity unverified)
   ([OpenCV](https://github.com/opencv/opencv/blob/4.x/modules/calib3d/include/opencv2/calib3d.hpp),
   [easy_handeye2](https://github.com/marcoesposito1988/easy_handeye2),
   [moveit_calibration](https://github.com/moveit/moveit_calibration)). Publish the result as a
   static TF and copy the same transform into the scene.
3. Set the sim camera from intrinsics, not by eye. Isaac Sim's `Camera` takes the OpenCV matrix
   with `set_opencv_pinhole_properties(cx, cy, fx, fy)` (square pixels only); MuJoCo and ManiSkill
   take a vertical FOV, so derive it from fy and image height
   ([Isaac Sim camera](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/py/source/extensions/isaacsim.sensors.camera/docs/index.html)).
   Same resolution, same rate, same mounting transform. Leave distortion at zero in sim and rectify
   on the real side so both paths see the same model.

### 5. Control rate and gains

1. Record the real control chain: policy rate, controller rate, command type (position, velocity,
   torque), PD gains, torque limits, filtering, and observation-to-command latency. Franka's inner
   loop is 1 kHz and `RobotState` exposes `tau_J` and `tau_ext_hat_filtered`
   ([libfranka](https://frankarobotics.github.io/libfranka/0.15.0/structfranka_1_1RobotState.html)).
2. Set sim `dt` and decimation so policy rate and inner-loop rate match exactly (Isaac Lab:
   `sim.dt` and `decimation`; MuJoCo: `timestep` and substeps).
3. Match the actuator model. Isaac Lab has `ImplicitActuatorCfg`, `IdealPDActuatorCfg`,
   `DCMotorCfg`, and `ActuatorNetMLP` / `ActuatorNetLSTM` after Hwangbo et al.
   ([actuators API](https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.actuators.html),
   [Hwangbo et al. 2019](https://www.science.org/doi/10.1126/scirobotics.aau5872)). MuJoCo since
   3.5 injects measured latency through `mjData.history` delays on actuators and sensors
   ([MuJoCo 3.5](https://github.com/google-deepmind/mujoco/discussions/3094)).

### 6. System identification of friction and the gripper

1. Joint friction: constant-velocity sweeps at several speeds per joint, log torque, fit Coulomb
   plus viscous terms; the least-squares base-parameter method with exciting trajectories is
   Gautier and Khalil ([IJRR 1992](https://journals.sagepub.com/doi/abs/10.1177/027836499201100408));
   the MuJoCo sysid toolbox (since 3.5) fits MJCF parameters to logs. Write the fitted
   `frictionloss`, `damping` and `armature` into the model.
2. Gripper: measure closing time, stall force and pad friction on the real part. Model it as a
   position-controlled joint with a force limit; parallel-jaw contact is where PhysX and MuJoCo
   diverge most from reality (from field, unverified).
3. Latency: step input, encoder log, measure delay, randomize around it
   ([Tan et al. 2018](https://arxiv.org/abs/1804.10332)).

### 7. Contact and materials

Set friction per material pair (steel on aluminium fixture, rubber pad on plastic). A global 1.0
is how sim "succeeds" at grasps the real gripper drops.

## The same-code pattern

One codebase drives sim and real. The seam is one robot interface with two implementations.

- **ros2_control as the seam.** Controllers are written once. On hardware a
  `hardware_interface::SystemInterface` plugin talks to the vendor driver; in Gazebo
  `gz_ros2_control` provides it; in MuJoCo `mujoco_ros2_control/MujocoSystemInterface` does, with
  `mujoco_model` and `sim_speed_factor` params in the URDF; with no simulator,
  `mock_components/GenericSystem` echoes commands to states so launch files and controllers run on
  a laptop ([mock components](https://control.ros.org/rolling/doc/ros2_control/hardware_interface/doc/mock_components_userdoc.html),
  [hardware component guide](https://control.ros.org/rolling/doc/ros2_control/hardware_interface/doc/writing_new_hardware_component.html),
  [gz_ros2_control](https://github.com/ros-controls/gz_ros2_control),
  [mujoco_ros2_control demo URDF](https://github.com/ros-controls/mujoco_ros2_control/blob/main/mujoco_ros2_control_demos/demo_resources/robot/test_robot.urdf)).
  Isaac Sim has no ros2_control plugin (none documented); its bridge publishes `JointState` and
  subscribes to joint commands, so the controller runs inside Isaac Sim and the policy talks
  topics. Isaac Lab 2.x has no ROS 2 extension either; it ships `*ros_inference_env_cfg.py` files
  that fix observation order for an Isaac ROS inference node
  ([gear assembly deployment](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/policy_deployment/02_gear_assembly/gear_assembly_policy.html)).
  Keep the topic contract identical across all four.
- **Policy side.** Same topics, same QoS, same message types, frame names and units in sim and on
  hardware; the only launch-time differences are `use_sim_time` and which hardware plugin loads.
  No `if sim:` branches in policy code.
- **Replay real bags through perception.** Record with `--storage mcap`, replay with
  `ros2 bag play --clock` (publishes `/clock` only during playback) and `use_sim_time:=true` on
  every node, run perception unchanged ([rosbag2](https://github.com/ros2/rosbag2)). Foxglove opens
  MCAP natively and connects live over Foxglove Bridge
  ([Foxglove ROS 2](https://docs.foxglove.dev/docs/connecting-to-data/frameworks/ros2)). This is
  the cheapest real-data test and needs no robot.
- **Observation parity test.** Pull one observation from the twin and one from a bag; assert equal
  shapes, dtypes, frame ids, resolution and value ranges. Catches 640x480 versus 1280x720 and BGR
  versus RGB before a checkpoint is trained on the wrong thing.
- **Twin in the deployment loop.** Real-is-Sim has the policy act on the sim robot while the real
  one tracks it and the sim is corrected from real measurements ([Abou-Chakra et al. 2025](https://arxiv.org/abs/2504.03597)).

## Evaluation in sim

- **Parallel envs and seeds.** Isaac Lab and ManiSkill3 vectorize over `num_envs`. Seed every run,
  and log seed, simulator version, physics backend and driver in the experiment record
  (CLAUDE.md). Isaac Lab determinism holds only for the same hardware and Isaac Sim/PhysX version,
  rigid bodies and articulations; GPU scheduling can reorder ops
  ([reproducibility](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/features/reproducibility.html)).
- **Initial conditions.** Sample a fixed list once, save it, evaluate every checkpoint on it.
  LIBERO exposes `get_task_init_states(task_id)`; the 50-trials-per-task, 500-per-suite convention
  comes from OpenVLA's eval script ([LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO),
  [OpenVLA eval](https://github.com/openvla/openvla/blob/main/experiments/robot/libero/run_libero_eval.py)).
  Report k/n with a Wilson interval ([policy-evaluation](policy-evaluation.md)).
- **Success criteria.** Write the predicate before training (pose tolerance, gripper closed on
  object, no fixture collision, timeout) and log the failure reason per episode.
- **Visual matching for real-trained policies.** SimplerEnv overlays real background images and
  adjusts foreground textures; its metrics are MMRV (mean maximum rank violation) and Pearson
  correlation ([Li et al. 2024](https://arxiv.org/abs/2405.05941),
  [repo](https://github.com/simpler-env/SimplerEnv)). ManiSkill3 ships four BridgeData v2 twins with
  this overlay, GPU-parallel; the SimplerEnv `maniskill3` branch runs policies in them
  ([digital twins](https://maniskill.readthedocs.io/en/latest/tasks/digital_twins/index.html)).
  Build the same overlay for your cell: one real photo per camera, sim objects at measured poses.
- **Perturbation split.** LIBERO-Pro and LIBERO-Plus show policies above 90% nominal fall below 30%
  under camera and initial-state perturbations ([arXiv 2510.03827](https://arxiv.org/abs/2510.03827),
  [arXiv 2510.13626](https://arxiv.org/abs/2510.13626)). Add a split with camera pose +-2 cm and
  +-2 deg, object pose noise and a lighting change to every eval.
- **Domain randomization that gets used.** In Isaac Lab it is the `events` manager: `EventTermCfg`
  with mode `startup`, `reset` or `interval` over `randomize_rigid_body_mass`,
  `randomize_rigid_body_material`, `randomize_rigid_body_com`, `randomize_actuator_gains`,
  `randomize_joint_parameters`, `randomize_visual_texture_material`, `push_by_setting_velocity`,
  `apply_external_force_torque`; observation noise via `isaaclab.utils.noise`
  (`UniformNoiseCfg`, `GaussianNoiseCfg`, `NoiseModelWithAdditiveBiasCfg`)
  ([mdp API](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/api/lab/isaaclab.envs.mdp.html),
  [noise API](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/api/lab/isaaclab.utils.noise.html)).
  Randomize physics materials at startup, not at runtime, on GPU (reproducibility page above).
  Locomotion recipes in the legged_gym lineage use friction 0.5 to 1.25, mass +-10%, gains +-20%,
  pushes every 10 to 15 s and latency 0 to 1 control step ([Rudin et al. 2022](https://arxiv.org/abs/2109.11978));
  manipulation recipes randomize object mass, friction, initial pose, camera pose and lighting and
  keep identified gains fixed. Start from measured uncertainty; widen only on plateaus
  ([sim-to-real](sim-to-real.md#techniques)).

## Setup and containers

- **Driver and GPU.** Isaac Sim 5.1 needs Linux driver 580.65.06 or newer; 6.0 needs 595.58.03.
  Both need an RTX GPU with RT cores (A100 and H100 are not supported), 16 GB VRAM (RTX 4080
  class), 32 GB RAM, Ubuntu 22.04 or 24.04; pip installs need GLIBC 2.35, so no 20.04
  ([5.1 requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html),
  [6.0 requirements](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html)).
  5.x runs on Python 3.11, 6.0 on 3.12. Run `nvidia-smi` and compare before anything else.
- **Containers.** `nvcr.io/nvidia/isaac-sim:5.1.0` (and 6.0.x). Run with `--gpus all`,
  `-e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y`, `--network=host`, and the documented cache volume
  mounts or every start re-downloads extensions. The container "supports running our Python apps
  and standalone examples in headless mode only"; GUI mode on a monitor-less server aborts with
  `vkCreateSwapchain` because there is no Vulkan swapchain
  ([container install](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_container.html)).
  EGL and Vulkan inside any container need `NVIDIA_DRIVER_CAPABILITIES` to include `graphics`
  ([container toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html)).
  Isaac Lab wraps this in `docker/container.py` (`base` and `ros2` profiles) and publishes
  `nvcr.io/nvidia/isaac-lab:2.3.2`; the `ros2` profile installs Humble via apt but the 2.3.0 notes
  say the image "is not currently expected to work" after the Python 3.11 move
  ([Isaac Lab docker](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/deployment/docker.html),
  [release notes](https://isaac-sim.github.io/IsaacLab/main/source/refs/release_notes.html)).
  Working pattern: Isaac Sim uses its bundled ROS 2 Humble libs, ROS nodes run on the host or in a
  second container, all on `--net=host` with a shared `FASTRTPS_DEFAULT_PROFILES_FILE`
  ([ROS 2 in Docker](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_ros.html)).
- **X-less rendering.** Isaac Lab scripts take `--headless`, `--enable_cameras` (needed for any
  rendered sensor), `--video` with `--video_length` and `--video_interval`, and `--livestream 2`
  for a WebRTC view (TCP 49100, UDP 47998); standalone Isaac Sim uses
  `SimulationApp({"headless": True})`, which appends `--no-window`
  ([RL scripts](https://isaac-sim.github.io/IsaacLab/main/source/overview/reinforcement-learning/rl_existing_scripts.html),
  [livestream](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/manual_livestream_clients.html)).
  MuJoCo: `MUJOCO_GL=egl` for GPU offscreen, `osmesa` for CPU software rendering, set before import
  ([visualization](https://mujoco.readthedocs.io/en/stable/programming/visualization.html)).
  Gazebo: `gz sim -s` with `--headless-rendering` for EGL cameras
  ([Gazebo headless](https://gazebosim.org/api/sim/8/headless_rendering.html)).
- **Sim CI.** Nightly on a self-hosted GPU runner: pull the pinned image, build the workspace, run
  unit tests, a smoke episode per task with fixed seed and init list, then the full eval of the
  latest checkpoint. Fail on crash, on success below the last accepted value minus the Wilson
  half-width, and on any change in observation shapes. Isaac Lab itself runs `build.yml` on
  `[self-hosted, gpu]` per pull request and `daily-compatibility.yml` on a 04:00 cron, with
  `./isaaclab.sh --test` as the entry point
  ([workflows](https://github.com/isaac-sim/IsaacLab/tree/main/.github/workflows),
  [contributing](https://isaac-sim.github.io/IsaacLab/main/source/refs/contributing.html)). For a
  lab, one 4090 workstation on `cron` writing results into `experiments/` is enough.
- **Interpreters kept apart.** Pure-ML in `rll` (3.11), ROS in `rosdev` (3.10); Humble's
  `setup.bash` leaks `PYTHONPATH` ([ros2-humble](../tools/ros2-humble.md)). Isaac Sim's `python.sh` is a third.

## Daily checklist before robot time

Run the evening before an office day. Every item is a sim or bag result attached to the
experiment record.

1. Twin still matches: joint limits, base pose, camera transforms and control rate diffed against
   the last real calibration files; no unexplained edits in `TWIN.md`.
2. The exact checkpoint to deploy, by name (`<model>-<dataset>-<git-sha>-<step>.pt`), passes the
   nominal eval on the fixed init list and the perturbed split, k/n and interval recorded.
3. The same checkpoint runs through the ROS 2 policy node against `mock_components/GenericSystem`
   at the real control rate without deadline misses; loop-period histogram logged.
4. Perception on the most recent real bag from that cell reproduces the last visit's detections
   or poses (regression, not a new claim).
5. Observation parity test passes between twin and bag.
6. Safety envelope verified in sim: joint velocity and torque limits, workspace box, table
   collision, gripper force limit; numbers copied into the
   [field deployment checklist](../../sops/field-deployment-checklist.md).
7. Failure playbook: the three most common sim failure modes for this task, what they look like on
   video, and what you will change on site for each.
8. Bag recording launch tested in sim with `--storage mcap`; topic list and disk space checked.
9. Versions written down: simulator, Isaac Lab or MuJoCo, driver, ROS distro, checkpoint hash,
   twin git sha.
10. Time budget for the day: which trials, how many, in what order, and the stop rule
    ([experiment protocol](../../sops/experiment-protocol.md)).

## Practical gotchas

- **Version pairs are strict.** Isaac Lab 2.3.x needs Isaac Sim 5.1; 3.0 beta needs 6.0. Mixing
  gives import errors ([release notes](https://isaac-sim.github.io/IsaacLab/main/source/refs/release_notes.html)).
- **Humble plus Harmonic is a non-default pairing.** It installs from OSRF's non-official packages
  and then breaks apt dependencies of `ros-humble-*` packages that expect Fortress; the Gazebo docs
  say not to unless you must ([pairing](https://gazebosim.org/docs/latest/ros_installation/)).
- **MuJoCo Warp is not feature-complete.** No `noslip`, PGS, plugin actuators or `IMPLICITFAST`
  midpoint; flex experimental; PyPI classifier still "Alpha"
  ([mujoco_warp](https://github.com/google-deepmind/mujoco_warp), [PyPI](https://pypi.org/project/mujoco-warp/)).
  Tune on CPU MuJoCo and confirm MJWarp reproduces the rollout before scaling.
- **Convex hulls change grasps.** One hull per finger pad grasps differently from the real
  chamfered pad. Inspect collision geometry in the viewer, not the visual mesh.
- **Sim cameras default to what the renderer prefers.** Set resolution and rate from `CameraInfo`
  and the real driver; check the published rate in sim (from field, unverified).
- **`use_sim_time` mismatch silently breaks TF.** One node without it and transforms time out;
  grep launch files before every sim run.
- **Bridges drop messages under load.** Isaac Sim publishes from the render loop; a render stall
  drops topic rates and a policy trained on steady 30 Hz sees gaps. Log topic rates in sim as on
  hardware (from field, unverified).
- **Vendor FPS is for their scene.** A 500k-triangle scanned collider destroys parallel
  throughput; measure with the real cell loaded ([sim-to-real](sim-to-real.md#practical-gotchas-from-the-field-and-the-literature)).
- **Web assets have no physics.** Objaverse objects lack scale, mass, friction and watertightness;
  a non-watertight mesh falls through the table.

## What a forward-deployed engineer must be able to do

- Stand up a pinned Isaac Sim + Isaac Lab container on a fresh machine, verify driver and GPU, and
  run a headless training smoke test within an hour.
- Build a twin of a new cell in two days: robot import with verified inertias, measured fixtures,
  calibrated cameras, matched control rate, identified friction, and a `TWIN.md` with provenance.
- Wire one ros2_control stack that runs on hardware, in Gazebo or MuJoCo, and with mock hardware,
  from the same launch file.
- Replay a customer bag through perception and produce a regression report.
- Write the sim evaluation protocol (init list, success predicate, perturbation split, seeds, N)
  and the nightly CI job that runs it.
- Build a SimplerEnv-style overlay for the cell and report rank correlation against the last
  real eval.

## Open questions to learn hands-on

- How many real trials per checkpoint does the cell's visual-matching eval need before its
  ranking stabilizes, and does the perturbation split change that number?
- Is the MuJoCo sysid toolbox good enough for a geared low-cost arm, or does an actuator net still
  win on the customer's hardware?
- How much Isaac Lab throughput survives a scanned-mesh cell versus a primitive-only twin, and
  where is the break-even for grasp fidelity?
- Does a NuRec render of a phone-scanned cell close the RGB gap enough that a real-trained policy
  evaluates correctly without the SimplerEnv overlay?
- Do Isaac Lab 3.0's Newton backend and mjlab give the same rollout from the same MJCF, so one
  twin definition serves both?
- What nightly CI budget (envs x episodes) makes the success-rate interval tighter than the
  checkpoint-to-checkpoint differences we care about?

## Related entries

- [sim-to-real](sim-to-real.md): simulator comparison, transfer techniques, decision guide
- [policy-evaluation](policy-evaluation.md): intervals, trial counts, protocols
- [deployment-engineering](deployment-engineering.md): latency and control loops on hardware
- [perception-3d-sensing](perception-3d-sensing.md): camera choices and calibration
- [tools/isaac-lab](../tools/isaac-lab.md), [tools/mujoco](../tools/mujoco.md), [tools/ros2-humble](../tools/ros2-humble.md)
- SOPs: [field deployment checklist](../../sops/field-deployment-checklist.md), [experiment protocol](../../sops/experiment-protocol.md)

## Sources

- Isaac Sim: releases https://github.com/isaac-sim/IsaacSim/releases ; 6.0 announcement https://github.com/isaac-sim/IsaacSim/discussions/538 ; 5.0 notes https://docs.isaacsim.omniverse.nvidia.com/5.0.0/overview/release_notes.html ; 6.0 notes https://docs.isaacsim.omniverse.nvidia.com/latest/overview/release_notes.html ; 5.1 requirements https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html ; 6.0 requirements https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html ; container https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_container.html ; ROS 2 install https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_ros.html and https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_ros.html ; URDF importer https://docs.isaacsim.omniverse.nvidia.com/5.1.0/importer_exporter/ext_isaacsim_asset_importer_urdf.html ; camera https://docs.isaacsim.omniverse.nvidia.com/5.1.0/py/source/extensions/isaacsim.sensors.camera/docs/index.html ; livestream https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/manual_livestream_clients.html ; licence FAQ https://docs.isaacsim.omniverse.nvidia.com/latest/common/license-faq.html ; ROS workspaces https://github.com/isaac-sim/IsaacSim-ros_workspaces ; NuRec smartphone blog https://developer.nvidia.com/blog/reconstruct-a-scene-in-nvidia-isaac-sim-using-only-a-smartphone/
- Isaac Lab: 2.3 GA https://github.com/isaac-sim/IsaacLab/discussions/3898 ; 3.0 beta 2 https://github.com/isaac-sim/IsaacLab/discussions/6249 ; release notes https://isaac-sim.github.io/IsaacLab/main/source/refs/release_notes.html ; import asset https://isaac-sim.github.io/IsaacLab/main/source/how-to/import_new_asset.html ; actuators https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.actuators.html ; mdp https://isaac-sim.github.io/IsaacLab/v2.3.2/source/api/lab/isaaclab.envs.mdp.html ; noise https://isaac-sim.github.io/IsaacLab/v2.3.2/source/api/lab/isaaclab.utils.noise.html ; reproducibility https://isaac-sim.github.io/IsaacLab/v2.3.2/source/features/reproducibility.html ; docker https://isaac-sim.github.io/IsaacLab/v2.3.2/source/deployment/docker.html ; gear assembly deployment https://isaac-sim.github.io/IsaacLab/v2.3.2/source/policy_deployment/02_gear_assembly/gear_assembly_policy.html ; RL scripts https://isaac-sim.github.io/IsaacLab/main/source/overview/reinforcement-learning/rl_existing_scripts.html ; workflows https://github.com/isaac-sim/IsaacLab/tree/main/.github/workflows ; contributing https://isaac-sim.github.io/IsaacLab/main/source/refs/contributing.html
- MuJoCo: 3.12.0 https://github.com/google-deepmind/mujoco/releases/tag/3.12.0 ; 3.5 https://github.com/google-deepmind/mujoco/discussions/3094 ; MJX https://mujoco.readthedocs.io/en/stable/mjx.html ; MuJoCo Warp https://github.com/google-deepmind/mujoco_warp and https://pypi.org/project/mujoco-warp/ ; URDF extensions https://mujoco.readthedocs.io/en/stable/modeling.html#urdf-extensions ; visualization https://mujoco.readthedocs.io/en/stable/programming/visualization.html ; Menagerie https://github.com/google-deepmind/mujoco_menagerie ; Playground https://github.com/google-deepmind/mujoco_playground ; obj2mjcf https://github.com/kevinzakka/obj2mjcf ; mjlab https://github.com/mujocolab/mjlab
- ROS 2 and Gazebo: mujoco_ros2_control https://github.com/ros-controls/mujoco_ros2_control ; gz_ros2_control https://github.com/ros-controls/gz_ros2_control ; ros_gz https://github.com/gazebosim/ros_gz ; Gazebo pairing https://gazebosim.org/docs/latest/ros_installation/ ; Gazebo releases https://gazebosim.org/docs/latest/releases/ ; Gazebo headless https://gazebosim.org/api/sim/8/headless_rendering.html ; mock components https://control.ros.org/rolling/doc/ros2_control/hardware_interface/doc/mock_components_userdoc.html ; hardware component https://control.ros.org/rolling/doc/ros2_control/hardware_interface/doc/writing_new_hardware_component.html ; rosbag2 https://github.com/ros2/rosbag2 ; Foxglove https://docs.foxglove.dev/docs/connecting-to-data/frameworks/ros2 ; camera_calibration https://github.com/ros-perception/image_pipeline/tree/rolling/camera_calibration ; CameraInfo https://github.com/ros2/common_interfaces/blob/rolling/sensor_msgs/msg/CameraInfo.msg ; kalibr https://github.com/ethz-asl/kalibr ; easy_handeye2 https://github.com/marcoesposito1988/easy_handeye2 ; moveit_calibration https://github.com/moveit/moveit_calibration ; OpenCV calib3d https://github.com/opencv/opencv/blob/4.x/modules/calib3d/include/opencv2/calib3d.hpp ; libfranka RobotState https://frankarobotics.github.io/libfranka/0.15.0/structfranka_1_1RobotState.html ; NVIDIA Container Toolkit https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html
- Other simulators: ManiSkill 3 https://arxiv.org/abs/2410.00425 ; https://github.com/mani-skill/ManiSkill ; https://pypi.org/project/mani-skill/ ; digital twins https://maniskill.readthedocs.io/en/latest/tasks/digital_twins/index.html ; SimplerEnv https://arxiv.org/abs/2405.05941 ; https://github.com/simpler-env/SimplerEnv ; Genesis World https://github.com/Genesis-Embodied-AI/genesis-world/releases ; https://pypi.org/project/genesis-world/
- Papers: Barreiros et al. 2025, TRI LBM https://arxiv.org/abs/2507.05331 ; Abou-Chakra et al. 2025, Real-is-Sim https://arxiv.org/abs/2504.03597 ; LIBERO https://github.com/Lifelong-Robot-Learning/LIBERO ; OpenVLA LIBERO eval https://github.com/openvla/openvla/blob/main/experiments/robot/libero/run_libero_eval.py ; LIBERO-Pro https://arxiv.org/abs/2510.03827 ; LIBERO-Plus https://arxiv.org/abs/2510.13626 ; Rudin et al. 2022 https://arxiv.org/abs/2109.11978 ; Tan et al. 2018 https://arxiv.org/abs/1804.10332 ; Hwangbo et al. 2019 https://www.science.org/doi/10.1126/scirobotics.aau5872 ; Gautier and Khalil 1992 https://journals.sagepub.com/doi/abs/10.1177/027836499201100408 ; Torne et al. 2024, RialTo https://arxiv.org/abs/2403.03949 ; Chen et al. 2024, URDFormer https://arxiv.org/abs/2405.11656 ; Guedon and Lepetit 2024, SuGaR https://arxiv.org/abs/2311.12775 ; Huang et al. 2024, 2DGS https://arxiv.org/abs/2403.17888
- Assets: Objaverse https://arxiv.org/abs/2212.08051 and https://huggingface.co/datasets/allenai/objaverse ; Objaverse-XL https://arxiv.org/abs/2307.05663 ; OmniObject3D https://arxiv.org/abs/2301.07525 ; Google Scanned Objects https://research.google/blog/scanned-objects-by-google-research-a-dataset-of-3d-scanned-common-household-items/ ; YCB https://www.ycbbenchmarks.com/ ; RealityScan licence https://www.realityscan.com/en-US/license ; Meshroom https://github.com/alicevision/Meshroom ; nerfstudio https://github.com/nerfstudio-project/nerfstudio ; SimReady spec https://docs.omniverse.nvidia.com/simready/latest/overview/simready-spec.html
