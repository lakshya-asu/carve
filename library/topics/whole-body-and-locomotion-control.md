---
title: Locomotion and whole-body control as a learning engineer meets it
date: 2026-09-06
tags: [topic, locomotion, whole-body-control, reinforcement-learning, humanoid, quadruped, sim-to-real, teleop, isaac-lab, mujoco]
status: draft
source: synthesis (links inline)
---

# Locomotion and whole-body control as a learning engineer meets it

Companion entries: `library/hardware/mobile-robots-and-humanoids.md` (the platforms and their
SDKs), `library/topics/sim-to-real.md` (the general sim gap), `library/tools/isaac-lab.md` and
`library/tools/mujoco.md` (install and versions), `library/topics/teleoperation-and-data-collection.md`
(teleop hardware), `library/topics/safety-for-learned-policies.md` (standards map and the shield
pattern). This entry covers the part a manipulation engineer inherits when the arm is bolted to
something that walks: how the leg controller was made, what it expects from you, and how not to
knock it over.

## What it is

Three layers, three rates, three owners.

| Layer | Runs at | Typical owner | What it consumes | What it emits |
|---|---|---|---|---|
| Motor PD loop | 500 Hz to 1 kHz on the motor boards or the vendor's real-time host | Vendor firmware | Target joint position `q`, velocity `dq`, feedforward torque `tau`, gains `kp`, `kd` per joint (Unitree `MotorCmd_` fields exactly: `mode, q, dq, tau, kp, kd`, [unitree_sdk2 IDL](https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2/main/include/unitree/idl/go2/MotorCmd_.hpp)) | Motor torque |
| Locomotion or whole-body controller | 50 Hz (learned policy) or 100 to 500 Hz (MPC plus QP WBC) | Vendor, or you if the vendor's controller is released | Base velocity command, or a reference motion for every joint | Joint targets for the PD loop |
| Task policy (your ACT, DP, VLA) | 5 to 30 Hz | You | Camera images, proprioception | Base velocity plus arm targets, or an end-effector trajectory |

The learned locomotion policy in every open pipeline outputs joint position targets that a PD
loop turns into torque, `tau = kp (q_des - q) - kd dq`. The policy never touches torque directly.
In Isaac Lab's velocity task the action term is `JointPositionAction` with `scale=0.5` (0.25 in
Unitree's own configs) and `use_default_offset=True`, so the network outputs a scaled delta around
the standing pose ([velocity_env_cfg.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py),
[g1.yaml](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/configs/g1.yaml)).

A model-based whole-body controller (WBC) solves for joint torques or accelerations that satisfy a
prioritized list of tasks (contact constraints, base motion, swing foot, arm end-effector) subject
to dynamics and friction cones. `legged_control` describes the hierarchical QP: it "solves the QP
problem in the null space of the higher priority tasks' linear constraints and tries to minimize
the slacking variables of inequality constraints"
([legged_control](https://github.com/qiayuanl/legged_control)). MPC sits above the WBC and plans
contact forces or centroidal motion over a horizon.

## Why it matters in the field

- The base you are handed is a black box with a velocity input. On a Unitree Go2 or G1 the
  factory "sport mode" controller owns the motors; low-level control requires releasing it through
  `MotionSwitcherClient::ReleaseMode()` before anything you publish on `rt/lowcmd` has effect
  ([g1_ankle_swing_example.cpp](https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2/main/example/g1/low_level/g1_ankle_swing_example.cpp)).
  On Spot the arm and body share one command stream and the body will move to extend the arm's
  reach under `FollowArmCommand` ([Spot arm concepts](https://dev.bostondynamics.com/docs/concepts/arm/arm_concepts)).
  Either way, your policy's output is a command into someone else's controller.
- Production controllers are now hybrids. Boston Dynamics ships an RL policy that receives
  "navigation commands, terrain observations, and gait state" and outputs "step adjustments and
  postural corrections" on top of the existing MPC, replacing the parallel MPC instances they used
  to run ([BD blog](https://bostondynamics.com/blog/starting-on-the-right-foot-with-reinforcement-learning/)).
  Knowing which layer is learned tells you which failure modes to expect.
- Humanoid data collection is a whole-body control problem before it is a teleop problem. TWIST2
  reports "100 demonstrations in 15 minutes with an almost 100% success rate" only because a
  tracking controller keeps the robot upright while the operator moves
  ([TWIST2, arXiv:2511.02832](https://arxiv.org/abs/2511.02832)). HumanPlus's low-level policy is
  what lets a 33-DoF, 180 cm humanoid shadow a person from one RGB camera
  ([HumanPlus, arXiv:2406.10454](https://arxiv.org/abs/2406.10454)).
- A learned manipulation policy can be reused across bases if the interface is right. UMI on Legs
  passes "end-effector trajectories in the task frame" from a UMI diffusion policy to a whole-body
  controller trained in sim, and reports over 70% success and zero-shot transfer of a fixed-arm
  policy to a quadruped ([UMI on Legs, arXiv:2407.10353](https://arxiv.org/abs/2407.10353)).
- The failure cost is different. An arm faulting stops. A legged robot faulting falls on the arm, the payload, or a person.

## Key methods table

### RL locomotion

| Method | Idea | Deployed on | Source |
|---|---|---|---|
| Massively parallel PPO with terrain curriculum | Thousands of robots on one GPU, few steps per robot per update, time-out bootstrapping; rough-terrain policy in under 20 minutes | ANYmal | [Rudin 2021, arXiv:2109.11978](https://arxiv.org/abs/2109.11978); `library/papers/rudin-2021-learning-to-walk-in-minutes.md` |
| Actuator network | LSTM or MLP trained on real motor data replaces the sim actuator; Isaac Lab ships `anydrive_3_lstm_jit.pt` with saturation effort 120 N m and velocity limit 7.5 rad/s for ANYmal C and reuses it for D because no D network is public | ANYmal | [Hwangbo 2019, arXiv:1901.08652](https://arxiv.org/abs/1901.08652), [anymal.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_assets/isaaclab_assets/robots/anymal.py) |
| Teacher-student (privileged learning) | Teacher sees terrain and friction; student reconstructs them from a proprioception history; zero-shot to mud, snow, rubble | ANYmal | [Lee 2020, arXiv:2010.11251](https://arxiv.org/abs/2010.11251) |
| RMA | Adaptation module infers an environment latent from recent proprioception online, no fine-tuning | A1 | [Kumar 2021, arXiv:2107.04034](https://arxiv.org/abs/2107.04034) |
| Perceptive locomotion with belief encoder | Attention-based recurrent encoder gates exteroception against proprioception; alpine hike "in the time recommended for human hikers" | ANYmal | [Miki 2022, arXiv:2201.08117](https://arxiv.org/abs/2201.08117) |
| DreamWaQ | Implicit terrain imagination from proprioception alone | quadruped | [Nahrendra 2023, arXiv:2301.10602](https://arxiv.org/abs/2301.10602) |
| Walk These Ways (MoB) | One policy exposes gait, footswing, posture, speed as runtime parameters instead of retraining | Go1 | [Margolis 2022, arXiv:2212.03238](https://arxiv.org/abs/2212.03238) |
| Extreme Parkour | Depth-camera policy distilled from a privileged teacher; jumps 2x body height and 2x body length | small quadruped | [Cheng 2023, arXiv:2309.14341](https://arxiv.org/abs/2309.14341) |
| Causal transformer over history | Proprioception-action history in, next action out, in-context adaptation; zero-shot outdoors | Digit (robot not named in the abstract, unverified) | [Radosavovic 2023, arXiv:2303.03381](https://arxiv.org/abs/2303.03381) |
| BD hybrid RL over MPC | RL picks step and posture adjustments, MPC executes; trained over "a million simulations" | Spot | [BD blog](https://bostondynamics.com/blog/starting-on-the-right-foot-with-reinforcement-learning/) |
| High-performance RL on Spot | Full RL policy through the Joint Control API on the RL Researcher Kit (Jetson AGX Orin payload); "over 5.2 m/s", more than triple the default controller; Isaac Lab plus CMA-ES on sim parameters | Spot | [Miller 2025, arXiv:2504.17857](https://arxiv.org/abs/2504.17857) |

### Whole-body and model-based control

| Method | Idea | Rate claims | Source |
|---|---|---|---|
| Convex MPC (MIT Cheetah 3) | Single rigid body model, ground reaction forces as decision variables | (paper not fetched, unverified) | Di Carlo et al., IROS 2018, DOI 10.1109/IROS.2018.8594448 |
| WBIC (Mini Cheetah) | MPC reaction forces plus whole-body impulse control; 3.7 m/s, six gaits | (rates not in abstract, unverified) | [Kim 2019, arXiv:1909.06586](https://arxiv.org/abs/1909.06586) |
| OCS2 | C++ MPC toolbox: SLQ, iLQR, SQP, SLP, IPM; legged example with centroidal model, Pinocchio, self-collision constraints; `main` for ROS 1, `ros2` branch | n/a | [ocs2](https://github.com/leggedrobotics/ocs2) |
| legged_control | OCS2 NMPC plus hierarchical-QP WBC on ros_control; ANYmal, A1, Aliengo, Go1; NMPC "close to 200Hz" on an 11th-gen NUC; ROS Noetic; "not supported anymore" | ~200 Hz NMPC | [legged_control](https://github.com/qiayuanl/legged_control) |
| Crocoddyl | DDP-family solvers (FDDP) with contact dynamics on Pinocchio; C++ and Python | n/a | [crocoddyl](https://github.com/loco-3d/crocoddyl), Mastalli et al. ICRA 2020 |
| MuJoCo MPC | Sampling-based predictive control in MuJoCo | (not fetched, unverified) | [mujoco_mpc](https://github.com/google-deepmind/mujoco_mpc) |

### Composing an upper-body policy with a locomotion controller

| Pattern | Interface between layers | Example | Source |
|---|---|---|---|
| Decoupled: RL legs, teleop or IL arms | Lower-body policy takes velocity and height commands and treats upper-body joints as a disturbance it was trained under (upper-body pose curriculum) | HOMIE, ~$500 cockpit | [arXiv:2502.13013](https://arxiv.org/abs/2502.13013) |
| Unified policy | One network outputs all joints; "Regularized Online Adaptation" and "Advantage Mixing" | Go1 plus arm | [Fu 2022, arXiv:2210.10044](https://arxiv.org/abs/2210.10044) |
| End-effector trajectory as interface | Manipulation policy emits EE trajectory in the task frame; WBC tracks it | UMI on Legs, Go2 plus arm | [arXiv:2407.10353](https://arxiv.org/abs/2407.10353) |
| Trajectory optimization plus RL tracking | Hybrid dataset from TO handles out-of-distribution whole-body commands; 29-DoF G1 | AMO | [arXiv:2505.03738](https://arxiv.org/abs/2505.03738) |
| Multi-mode distillation | One policy trained to accept root velocity, joint angle, or keypoint commands per body part | HOVER | [arXiv:2410.21229](https://arxiv.org/abs/2410.21229) |
| Vendor body-assist | Base moves to extend arm workspace | Spot `FollowArmCommand` | [Spot arm concepts](https://dev.bostondynamics.com/docs/concepts/arm/arm_concepts) |
| Single VLA for manipulation and locomotion | GR00T N1.7 `UNITREE_G1_SONIC` embodiment: "single policy produces language-conditioned, coordinated manipulation and locomotion end-to-end" | G1 | [Isaac-GR00T](https://github.com/NVIDIA/Isaac-GR00T) |

### Humanoid teleop and motion imitation

| System | Input | Low-level controller | Robot | Source |
|---|---|---|---|---|
| ExBody | Mocap datasets; upper body imitates, legs track velocity only | RL | H1 | [arXiv:2402.16796](https://arxiv.org/abs/2402.16796) |
| H2O / OmniH2O | VR, RGB, language, GPT-4o through one kinematic-pose interface; teacher-student sim-to-real; OmniH2O-6 dataset | RL | H1 | [arXiv:2406.08858](https://arxiv.org/abs/2406.08858) |
| HumanPlus | Single RGB camera pose estimate; HST tracks it; HIT learns tasks from up to 40 demos at 60 to 100% success | RL | custom 33-DoF humanoid on Unitree hardware | [arXiv:2406.10454](https://arxiv.org/abs/2406.10454) |
| TWIST / TWIST2 | Mocap (TWIST) then PICO 4U VR plus a ~$250 neck (TWIST2); RL plus BC tracker with privileged future frames | RL+BC | G1 | [arXiv:2505.02833](https://arxiv.org/abs/2505.02833), [arXiv:2511.02832](https://arxiv.org/abs/2511.02832) |
| ASAP | Pretrain tracker on retargeted motion; learn a delta action model from real rollouts to cancel the dynamics gap | RL plus residual | G1 | [arXiv:2502.01143](https://arxiv.org/abs/2502.01143) |
| BeyondMimic | One tracker config learns cartwheels, spin-kicks, sprints; guided latent diffusion for goals and inpainting; zero-shot to hardware | RL plus diffusion | humanoid | [arXiv:2508.08241](https://arxiv.org/abs/2508.08241) |
| GMR (retargeting) | IK plus optimization on mink and MuJoCo; SMPL-X (AMASS), BVH (LAFAN1), FBX (OptiTrack), Xsens live, PICO streaming, GVHMR video; 18 robots; 60 to 70 fps on a Threadripper 7960X, 35 to 45 on an i9-13900K; MIT licence | n/a | G1, H1, T1, K1, GR3, R1 Pro and others | [GMR](https://github.com/YanjieZe/GMR) |
| GR00T N1.7 | LeRobot v2 dataset plus `modality.json`; `groot` policy type in LeRobot; inference on 16 GB+ VRAM, fine-tune 40 GB+ | vendor or SONIC | G1, AgiBot G1, arms | [Isaac-GR00T](https://github.com/NVIDIA/Isaac-GR00T) |

### Frameworks

| Framework | Backend | Status 2026-09 | Source |
|---|---|---|---|
| legged_gym | Isaac Gym Preview 3, Python 3.8, PyTorch 1.10 | Migrated: "we have migrated all the environments from this work to Isaac Lab" | [legged_gym](https://github.com/leggedrobotics/legged_gym) |
| rsl_rl | PyTorch, Python 3.9+ | "PPO and Student-Teacher Distillation"; plugs into Isaac Lab, legged_gym, mjlab, MuJoCo Playground | [rsl_rl](https://github.com/leggedrobotics/rsl_rl) |
| Isaac Lab velocity tasks | PhysX (Newton in 3.0 beta) | Manager-based tasks for ANYmal, Go2, G1, H1, Spot and more | [velocity_env_cfg.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py); `library/tools/isaac-lab.md` |
| unitree_rl_gym | Isaac Gym | Go2, H1, H1_2, G1; train, play, sim2sim (MuJoCo), sim2real; robot must be in debug mode | [unitree_rl_gym](https://github.com/unitreerobotics/unitree_rl_gym) |
| unitree_rl_lab | Isaac Lab 2.3.0+ | Go2, H1, G1-29dof; deploys through compiled C++ on unitree_sdk2 (`./g1_ctrl --network eth0`) | [unitree_rl_lab](https://github.com/unitreerobotics/unitree_rl_lab) |
| MuJoCo Playground | MJX (JAX) and MuJoCo Warp | `pip install playground`; joystick envs for Go1, Spot, Barkour, Op3, G1, H1, T1, Apollo, Berkeley Humanoid; Go1 getup, handstand, footstand; `train-jax-ppo` and `train-rsl-ppo`; "train policies in minutes on a single GPU" | [mujoco_playground](https://github.com/google-deepmind/mujoco_playground), [locomotion registry](https://raw.githubusercontent.com/google-deepmind/mujoco_playground/main/mujoco_playground/_src/locomotion/__init__.py), [arXiv:2502.08844](https://arxiv.org/abs/2502.08844) |
| mjlab | MuJoCo Warp | Isaac Lab manager API on MJWarp; `Mjlab-Velocity-Flat-Unitree-G1`, motion imitation; NVIDIA GPU for training | [mjlab](https://github.com/mujocolab/mjlab) |
| Humanoid-Gym | Isaac Gym plus MuJoCo sim2sim | XBot-S and XBot-L zero-shot | [arXiv:2404.05695](https://arxiv.org/abs/2404.05695) |

## Practical recipe

The numbers below are the defaults in the open configs, quoted so you can recognise a policy's
contract when someone hands you a checkpoint.

1. **Observation space** (Isaac Lab velocity task, policy group): base linear velocity (noise
   +/-0.1), base angular velocity (+/-0.2), projected gravity (+/-0.05), velocity command, joint
   positions (+/-0.01), joint velocities (+/-1.5), last actions, and a height scan (+/-0.1,
   clipped to +/-1)
   ([velocity_env_cfg.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py)).
   Unitree's deployable G1 policy drops base linear velocity (no reliable estimate on the real
   robot) and uses 47 observations: angular velocity x0.25, gravity, command scaled by
   `[2.0, 2.0, 0.25]`, joint position x1.0, joint velocity x0.05, last action, and a gait phase
   sinusoid; 50 privileged observations for the critic; no history buffer
   ([g1.yaml](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/configs/g1.yaml),
   [deploy_real.py](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/deploy_real.py),
   [g1_config.py](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/legged_gym/envs/g1/g1_config.py)).
2. **Action space and rates**: 12 leg joint targets on G1 (arms and waist held by a separate PD
   set), `action_scale 0.25`, `control_dt 0.02` (50 Hz), sim `dt 0.005` with `decimation 4`,
   episode 20 s. Isaac Lab uses the same 0.005 / 4 / 20 s
   ([g1.yaml](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/configs/g1.yaml),
   [velocity_env_cfg.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py)).
3. **PD gains are part of the policy.** G1 legs: kp 100 (hip), 150 (knee), 40 (ankle); kd 2, 4,
   2. Go2 in unitree_rl_gym: kp 20, kd 0.5 on every joint; Isaac Lab's Go2 asset uses
   `DCMotorCfg` with stiffness 25, damping 0.5, effort limit 23.5 N m, velocity limit 30 rad/s.
   Isaac Lab's G1 and H1 assets use stiffness 150 to 200 on legs, 20 on feet, 40 on arms
   ([g1.yaml](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/configs/g1.yaml),
   [go2_config.py](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/legged_gym/envs/go2/go2_config.py),
   [unitree.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_assets/isaaclab_assets/robots/unitree.py)).
   A checkpoint deployed with different gains is a different controller; record kp and kd with the
   checkpoint name.
4. **Domain randomization terms** that ship by default: friction (Isaac Lab static 0.8 and dynamic
   0.6 as the material, unitree_rl_gym G1 friction range [0.1, 1.25]), added base mass
   (Isaac Lab +/-5 kg, G1 [-1, 3] kg), base pushes (Isaac Lab every 10 to 15 s at up to
   0.5 m/s; G1 every 5 s up to 1.5 m/s), reset pose jitter. Isaac Lab's base config has no
   actuator gain randomization term
   ([velocity_env_cfg.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py),
   [g1_config.py](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/legged_gym/envs/g1/g1_config.py)).
   Your arm and payload change the base mass and inertia; check the added-mass range covers them
   before assuming the shipped policy will carry your gripper.
5. **Rewards**: track linear velocity xy (1.0) and yaw rate (0.5); penalties on vertical velocity
   (-2.0), roll and pitch rate (-0.05), torques (-1e-5), joint acceleration (-2.5e-7), action rate
   (-0.01), undesired contacts (-1.0); feet air time bonus (0.125). G1 adds feet slide (-0.1), joint
   deviation on hips, arms, fingers and torso (-0.1, -0.05), ankle limits (-1.0), and a -200
   termination penalty; termination on torso contact
   ([velocity_env_cfg.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py),
   [g1 rough_env_cfg.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/g1/rough_env_cfg.py)).
6. **Algorithm**: PPO from rsl_rl. unitree_rl_gym's G1 uses `ActorCriticRecurrent` (LSTM 64,
   one layer), entropy 0.01, initial noise std 0.8, 10,000 iterations
   ([g1_config.py](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/legged_gym/envs/g1/g1_config.py)).
   For perceptive or adaptive variants train a privileged teacher first and distil (rsl_rl's
   Student-Teacher Distillation).
7. **Sim2sim before sim2real**: run the exported policy in MuJoCo (unitree_mujoco, or Playground)
   with the same observation scaling. A policy that only walks in the training simulator is
   overfit to that simulator's contact model ([unitree_rl_gym](https://github.com/unitreerobotics/unitree_rl_gym),
   [Humanoid-Gym, arXiv:2404.05695](https://arxiv.org/abs/2404.05695)).
8. **Sim2real on Unitree**, as `deploy_real.py` does it: robot hoisted, zero-torque mode,
   `L2+R2` on the remote enters debug mode, wired Ethernet at 192.168.123.99/24; the script waits
   for `start` in zero-torque state, interpolates to the default pose over 2 s, waits for `A`,
   then runs the 50 Hz loop writing `q`, `kp`, `kd` per motor to `rt/lowcmd`; left stick is
   velocity, right stick yaw; `select` exits through a damping command. The shipped real-robot
   configs are `g1.yaml`, `h1.yaml`, `h1_2.yaml` only; there is no Go2 real-deploy config in that
   repo ([deploy_real README](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/README.md),
   [deploy_real.py](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/deploy_real.py),
   [unitree_ros2 README](https://raw.githubusercontent.com/unitreerobotics/unitree_ros2/master/README.md)).
   On Go2 the sport service must be switched off first (`ServiceSwitch("sport_mode", 0)` in the
   robot state client, or the Python README's warning that it must be disabled "to prevent command
   conflicts") ([go2_robot_state_client.cpp](https://github.com/unitreerobotics/unitree_sdk2/blob/main/example/go2/go2_robot_state_client.cpp),
   [unitree_sdk2_python](https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2_python/master/README.md)).
   The compiled C++ route in unitree_rl_lab does the same through unitree_sdk2
   ([unitree_rl_lab](https://github.com/unitreerobotics/unitree_rl_lab)). The SDK example's
   own low-level loop runs at `control_dt_ 0.002` (500 Hz), with kp 60 to 100 and kd 1 to 2 for
   its slow demo motions ([g1_ankle_swing_example.cpp](https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2/main/example/g1/low_level/g1_ankle_swing_example.cpp)).
9. **Putting an arm policy on top**: pick the interface from the composition table. Cheapest
   working default for a manipulation team: base velocity plus torso height into the vendor or
   RL locomotion controller, arm joint targets into a separate PD set, and a policy that was
   trained with the arm moving (HOMIE's upper-body pose curriculum is the reason it works
   ([arXiv:2502.13013](https://arxiv.org/abs/2502.13013))). Log both command streams with one
   clock.
10. **Retargeting for humanoid demos**: GMR from SMPL-X, BVH, Xsens or a PICO stream at 35 to
    70 fps, then a tracking controller (TWIST-style) on the robot; ASAP's delta action model is the
    documented fix when the tracker is worse on hardware than in sim
    ([GMR](https://github.com/YanjieZe/GMR), [ASAP, arXiv:2502.01143](https://arxiv.org/abs/2502.01143)).

## Practical gotchas

- **Releasing the factory controller is a mode switch, not a topic.** Publishing to `rt/lowcmd`
  while the sport service is active fights it; the G1 SDK example polls `CheckMode` and calls
  `ReleaseMode` every 5 s until no mode is active, and the Go2 path is `ServiceSwitch("sport_mode",
  0)` ([g1_ankle_swing_example.cpp](https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2/main/example/g1/low_level/g1_ankle_swing_example.cpp),
  [go2_robot_state_client.cpp](https://github.com/unitreerobotics/unitree_sdk2/blob/main/example/go2/go2_robot_state_client.cpp)).
  Switch it back on (`ServiceSwitch("sport_mode", 1)`) before handing the robot to anyone who
  expects the remote to work. The Unitree developer docs are JS-rendered and did not fetch on
  2026-09-06, so the documented remote-only procedure is (unverified).
- **Spot joint control is a licence, not a flag.** The Joint Control API is beta, streams at
  100 to 333 Hz, needs a special-permissions licence, and every command carries an `end_time`;
  optional velocity safety limits raise a behavior fault when exceeded
  ([Joint Control API](https://dev.bostondynamics.com/docs/concepts/joint_control/readme)).
- **Observation scaling mismatches walk badly, not obviously.** The G1 deploy config multiplies
  joint velocity by 0.05 and angular velocity by 0.25; a bridge that forgets one scale produces a
  policy that stands and stumbles rather than one that refuses
  ([g1.yaml](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/configs/g1.yaml)).
- **Joint order.** `leg_joint2motor_idx` and `arm_waist_joint2motor_idx` map policy indices to
  motor indices; URDF order, Isaac Lab order and motor index order differ
  ([g1.yaml](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/configs/g1.yaml)).
- **Base linear velocity is not observable on hardware** without a state estimator, which is
  why the deployable Unitree config leaves it out while the Isaac Lab default includes it.
  Training with it and deploying without it is a silent distribution shift
  ([deploy_real.py](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/deploy_real.py)).
- **The actuator model is the sim gap.** Isaac Lab reuses ANYmal C's LSTM actuator net for
  ANYmal D with a written warning that transfer may suffer; Unitree assets use a plain DC motor
  model with a saturation effort, so torque-rate and thermal limits are not modelled
  ([anymal.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_assets/isaaclab_assets/robots/anymal.py),
  [unitree.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_assets/isaaclab_assets/robots/unitree.py)).
- **Spot's E-Stop is a heartbeat.** Registered endpoints must check in within their timeout with
  stop level `NONE` or power is cut; `SETTLE_THEN_CUT` sits the robot first. A laptop that sleeps
  is an E-Stop. From release 3.3 a client may run without the service
  ([Spot E-Stop service](https://dev.bostondynamics.com/docs/concepts/estop_service)).
- **Spot's arm has no obstacle avoidance**, stated twice in the vendor docs; the body will walk to
  follow a Cartesian arm target ([Spot arm concepts](https://dev.bostondynamics.com/docs/concepts/arm/arm_concepts)).
- **legged_control and legged_gym are frozen.** Both READMEs say so; port to Isaac Lab or OCS2's
  `ros2` branch rather than patching Noetic code
  ([legged_control](https://github.com/qiayuanl/legged_control), [legged_gym](https://github.com/leggedrobotics/legged_gym)).
- **Every open locomotion checkpoint assumes its payload.** Isaac Lab's base-mass randomization
  is +/-5 kg; an arm plus gripper plus compute at the front of a Go2 is a mass and a moment. Test
  standing, then walking on a harness, before trusting it (from field, unverified).
- **Damping mode is the safe state, not zero torque.** unitree_rl_gym exits through
  `create_damping_cmd`; zero torque drops the robot
  ([deploy_real.py](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/deploy_real.py)).

## Safety for legged robots in human spaces

The standards map in `library/topics/safety-for-learned-policies.md` already lists ISO 13482
(personal care robots), ISO 3691-4 (driverless industrial trucks) and ISO 10218 (industrial arms).
None of them was written for a walking machine with an arm. A draft ISO part for legged
industrial mobile robots and an IEEE humanoid safety effort were reported in 2025; neither
catalogue page was reachable on 2026-09-06, so number and status are (unverified). Until a standard
lands, the practical controls are the vendor's:

- Heartbeat E-Stops with a settle-then-cut level (Spot,
  [E-Stop service](https://dev.bostondynamics.com/docs/concepts/estop_service)); damping mode as
  the terminal state on Unitree ([deploy_real.py](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/deploy_real.py)).
- A harness or gantry for every first run of a new checkpoint, and a floor plan with a taped
  exclusion zone equal to the robot's fall radius plus arm reach (from field, unverified).
- Fall handling as a controller feature: Hwangbo 2019 trained recovery from arbitrary fallen
  configurations ([arXiv:1901.08652](https://arxiv.org/abs/1901.08652)); Playground ships
  `Go1Getup` and `SpotGetup` tasks ([locomotion registry](https://raw.githubusercontent.com/google-deepmind/mujoco_playground/main/mujoco_playground/_src/locomotion/__init__.py)).
  A robot that can stand up on its own still fell on whatever was under it.
- Lease and timeout semantics on the base command: if your arm policy's process dies, the base
  must stop, not continue the last velocity. Spot's lease and E-Stop endpoints enforce this;
  on a raw `rt/lowcmd` stream nothing does unless you write the watchdog (from field, unverified).

## Evaluation and the metrics used

| Metric | Definition | Where used |
|---|---|---|
| Velocity tracking error | Mean of the exp-tracking reward, or RMS of commanded minus measured base velocity over an episode | Isaac Lab `track_lin_vel_xy_exp`, `track_ang_vel_z_exp` ([velocity_env_cfg.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py)) |
| Cost of transport | COT = E / (m g d) = P / (m g v), dimensionless; a walking human is about 0.34 ([Wikipedia](https://en.wikipedia.org/wiki/Cost_of_transport)) | Energy comparisons across gaits and controllers |
| Terrain level reached | Curriculum level per robot on the tiled terrain | Rudin 2021 curriculum, Isaac Lab `terrain_levels_vel` |
| Fall rate, mean distance between falls | Count over a fixed course or duration | BD reports "less likely to fall" on slick surfaces without a number ([BD blog](https://bostondynamics.com/blog/starting-on-the-right-foot-with-reinforcement-learning/)) |
| Agility course score | Timed obstacle course modelled on dog agility; custom quadruped at about half a dog's speed | [Barkour, arXiv:2305.14654](https://arxiv.org/abs/2305.14654) |
| Motion tracking error | Per-joint and keypoint error against the retargeted reference | ASAP, TWIST, BeyondMimic ([arXiv:2502.01143](https://arxiv.org/abs/2502.01143)) |
| Task success under whole-body control | Success rate over N trials with the demo count stated | HumanPlus 60 to 100% with up to 40 demos ([arXiv:2406.10454](https://arxiv.org/abs/2406.10454)); UMI on Legs over 70% ([arXiv:2407.10353](https://arxiv.org/abs/2407.10353)) |
| Sim benchmarks | HumanoidBench (H1 with hands; the authors report that current RL algorithms "struggle with most tasks"), LocoMuJoCo (IL over quadrupeds, bipeds, musculoskeletal models) | [arXiv:2403.10506](https://arxiv.org/abs/2403.10506), [arXiv:2311.02496](https://arxiv.org/abs/2311.02496) |

For a manipulation deployment on a legged base, report task success with the base controller and
checkpoint named, falls or protective stops per 100 episodes, and the payload during the trials.

## What a forward-deployed engineer must be able to do

- [ ] Name the three layers on a given robot, who owns each, at what rate, and prove the rates
      with a timestamped log.
- [ ] Put a Unitree Go2 or G1 into low-level mode and back, on a harness, with the damping exit
      tested before the first policy step.
- [ ] Train the Isaac Lab or Playground velocity task for the base on hand, run sim2sim in
      MuJoCo, and deploy it with observation scales and joint order checked line by line.
- [ ] Read a checkpoint's contract (observations, scales, action scale, kp, kd, control_dt) from
      its config into the experiment record, next to the checkpoint name.
- [ ] Add the arm and gripper as payload on the sim asset, re-randomize mass, and show the
      retrained policy walks with the real arm at the same success as without.
- [ ] Wire an arm policy to a locomotion controller through one of the composition patterns and
      log both command streams on one clock.
- [ ] Set up an E-Stop or heartbeat that stops the base when the policy process dies, and prove
      it by killing the process.
- [ ] Run a GMR-plus-tracker teleop session on a humanoid and record whole-body data in LeRobot
      format; report falls per 100 episodes alongside task success.

## Open questions to learn hands-on

- How much added front mass the shipped Go2 and G1 policies tolerate before gait degrades; a
  sweep in 0.5 kg steps on the harness, 20 trials each.
- Whether an arm policy trained on a fixed base transfers to the same arm on a walking base
  through the end-effector-trajectory interface (UMI on Legs pattern) without new demos.
- Real latency from policy output to motor torque on Unitree over `rt/lowcmd` versus the C++ path in unitree_rl_lab.
- Which E-Stop path is acceptable to a customer's safety officer for a legged robot with no
  applicable standard yet: vendor heartbeat, a wireless hardware stop, or both.
- How a walking base's oscillation appears in wrist-camera images, and whether the manipulation policy needs a base-motion observation or just demos taken while walking.

## Related entries

- `library/hardware/mobile-robots-and-humanoids.md`, `library/papers/rudin-2021-learning-to-walk-in-minutes.md`
- `library/topics/sim-to-real.md`, `library/topics/sim-first-workflow.md`, `library/tools/isaac-lab.md`, `library/tools/mujoco.md`
- `library/topics/teleoperation-and-data-collection.md`, `library/topics/safety-for-learned-policies.md`
- `library/topics/connecting-to-real-robots.md` (Unitree DDS and Spot gRPC rows), `library/topics/state-estimation-and-localization.md`

## Sources

- RL locomotion: [Rudin 2021](https://arxiv.org/abs/2109.11978), [Hwangbo 2019](https://arxiv.org/abs/1901.08652), [Lee 2020](https://arxiv.org/abs/2010.11251), [RMA](https://arxiv.org/abs/2107.04034), [Miki 2022](https://arxiv.org/abs/2201.08117), [DreamWaQ](https://arxiv.org/abs/2301.10602), [Walk These Ways](https://arxiv.org/abs/2212.03238), [Extreme Parkour](https://arxiv.org/abs/2309.14341), [Radosavovic 2023](https://arxiv.org/abs/2303.03381), [BD RL blog](https://bostondynamics.com/blog/starting-on-the-right-foot-with-reinforcement-learning/)
- Frameworks and configs: [legged_gym](https://github.com/leggedrobotics/legged_gym), [rsl_rl](https://github.com/leggedrobotics/rsl_rl), [Isaac Lab velocity_env_cfg.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py), [G1 rough_env_cfg.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/g1/rough_env_cfg.py), [unitree.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_assets/isaaclab_assets/robots/unitree.py), [anymal.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_assets/isaaclab_assets/robots/anymal.py), [unitree_rl_gym](https://github.com/unitreerobotics/unitree_rl_gym), [g1.yaml](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/configs/g1.yaml), [deploy_real.py](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/deploy_real.py), [g1_config.py](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/legged_gym/envs/g1/g1_config.py), [go2_config.py](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/legged_gym/envs/go2/go2_config.py), [unitree_rl_lab](https://github.com/unitreerobotics/unitree_rl_lab), [unitree_sdk2 MotorCmd IDL](https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2/main/include/unitree/idl/go2/MotorCmd_.hpp), [g1_ankle_swing_example.cpp](https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2/main/example/g1/low_level/g1_ankle_swing_example.cpp), [MuJoCo Playground](https://github.com/google-deepmind/mujoco_playground), [Playground paper](https://arxiv.org/abs/2502.08844), [Playground locomotion registry](https://raw.githubusercontent.com/google-deepmind/mujoco_playground/main/mujoco_playground/_src/locomotion/__init__.py), [mjlab](https://github.com/mujocolab/mjlab), [Humanoid-Gym](https://arxiv.org/abs/2404.05695)
- Whole-body control: [OCS2](https://github.com/leggedrobotics/ocs2), [legged_control](https://github.com/qiayuanl/legged_control), [Crocoddyl](https://github.com/loco-3d/crocoddyl), [WBIC](https://arxiv.org/abs/1909.06586), [MuJoCo MPC](https://github.com/google-deepmind/mujoco_mpc), [Spot arm concepts](https://dev.bostondynamics.com/docs/concepts/arm/arm_concepts)
- Composition: [Fu 2022](https://arxiv.org/abs/2210.10044), [HOMIE](https://arxiv.org/abs/2502.13013), [UMI on Legs](https://arxiv.org/abs/2407.10353), [AMO](https://arxiv.org/abs/2505.03738), [HOVER](https://arxiv.org/abs/2410.21229), [Isaac-GR00T](https://github.com/NVIDIA/Isaac-GR00T)
- Teleop and imitation: [ExBody](https://arxiv.org/abs/2402.16796), [OmniH2O](https://arxiv.org/abs/2406.08858), [HumanPlus](https://arxiv.org/abs/2406.10454), [TWIST](https://arxiv.org/abs/2505.02833), [TWIST2](https://arxiv.org/abs/2511.02832), [ASAP](https://arxiv.org/abs/2502.01143), [BeyondMimic](https://arxiv.org/abs/2508.08241), [GMR](https://github.com/YanjieZe/GMR)
- Spot: [Joint Control API](https://dev.bostondynamics.com/docs/concepts/joint_control/readme), [High-performance RL on Spot](https://arxiv.org/abs/2504.17857), [go2_robot_state_client.cpp](https://github.com/unitreerobotics/unitree_sdk2/blob/main/example/go2/go2_robot_state_client.cpp), [unitree_sdk2_python](https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2_python/master/README.md), [deploy_real README](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/README.md)
- Safety and evaluation: [Spot E-Stop service](https://dev.bostondynamics.com/docs/concepts/estop_service), [Barkour](https://arxiv.org/abs/2305.14654), [HumanoidBench](https://arxiv.org/abs/2403.10506), [LocoMuJoCo](https://arxiv.org/abs/2311.02496), [Cost of transport](https://en.wikipedia.org/wiki/Cost_of_transport)
