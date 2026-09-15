---
title: "Universal Manipulation Interface: In-The-Wild Robot Teaching Without In-The-Wild Robots"
date: 2026-09-05
tags: [paper, data-collection, handheld-gripper, imitation-learning, slam, latency]
status: draft
source: https://arxiv.org/abs/2402.10329
---

# UMI (Chi, Xu, Pan, Cousineau, Burchfiel, Feng, Tedrake, Song, RSS 2024)

Read from arXiv v3 (6 Mar 2024). A hand-held gripper with a GoPro as the only sensor, plus a
policy interface that makes the resulting data deploy on UR5 and Franka arms without a robot
present at collection time.

## Problem

Teleop needs the robot in the loop, so data comes from the lab. Passive human video has an
embodiment gap. Earlier hand-held grippers collected diverse scenes but only quasi-static
pick-and-place transferred, because of four gaps the paper names: too little visual context
from a wrist camera, imprecise monocular SfM actions, latency present at deployment but
absent at collection, and MLP policies that cannot fit multimodal human data.

## Core idea

Fix the demonstration hardware and the policy interface together. Hardware: 155 degree
fisheye GoPro on a 3D-printed parallel-jaw gripper, side mirrors in the periphery for
implicit stereo, GoPro IMU fused with ORB-SLAM3 for metric-scale 6-DoF tracking under fast
motion, continuous gripper width via fiducials on the fingers. Policy interface: Diffusion
Policy with relative end-effector trajectories as both action and proprioception,
inter-gripper relative pose for bimanual tasks, and measured per-stream latency matched at
inference so the robot sees the same timing the GoPro recorded.

## Method details that matter for reimplementation

- Gripper: 780 g, 310 x 175 x 210 mm, 80 mm finger stroke, $73 printed BoM plus $298 GoPro
  and accessories. Soft 95A TPU fingers on both the hand-held and robot grippers, which
  gives passive compliance on a UR5.
- Observation: raw fisheye RGB at 224x224 (not rectified; rectifying a 155 degree image
  wastes the centre), mirror crops digitally reflected and swapped, plus relative EE pose
  history and gripper width. Image and proprio horizon 2 (1 for the in-the-wild ViT-L run).
- Action: sequence of SE(3) poses relative to the EE pose at the current step, plus gripper
  width. Not delta (accumulates error) and not absolute (needs a global frame nobody has in
  the wild). Action horizon T_a 6.
- Latency matching (Sec. III-B, Appendix A): measure camera latency with a rolling QR clock,
  proprio latency from timestamps or half of ping, gripper and arm execution latency by
  cross-correlating commanded and measured sinusoids. Align all observation streams to the
  slowest, drop predicted actions whose timestamp is already past, send the rest early by
  the execution latency.
- SLAM: ORB-SLAM3 monocular-inertial, modified to relocalise to a scene map recorded first
  (about 1 min of scanning) and to use an optional fiducial during mapping only. Roughly 10%
  of demos are dropped by tracking failure in Lin et al. 2024's reuse of the system.
- Policy hyperparameters (Table A1): DDIM 50 train steps, 16 inference steps; 10 Hz for
  quasi-static tasks, 20 Hz for tossing; quasi-static tasks executed at 0.5x demo speed for
  smoothness. Vision encoder ResNet-34 from scratch (tossing, folding) or CLIP ViT-B/16
  fine-tuned at 10x lower lr (cup, dish washing), ViT-L/14 for in-the-wild cup. Diffusion lr
  3e-4, vision lr 3e-5 when pretrained. Batch 512 to 1024, 50 to 350 epochs on 4 to 8 A10g
  GPUs (8x A100 for ViT-L).
- Deployment: UR5 and Franka FR2 with Schunk WSG-50, wrist GoPro Hero 9 streamed through
  Media Mod and an Elgato HD60X capture card.

## Result that matters

Narrow-domain, same scene as collection, 20 trials per method with matched initial states
(Fig. 8):

- Cup arrangement (305 demos, 2 demonstrators): 20/20 on UR5; same checkpoint 18/20 on
  Franka FR2 (2 joint-limit faults). Ablations: no fisheye 11/20; delta actions 16/20;
  absolute actions 5/20; no mirrors 18/20; mirrors without digital reflection 17/20.
- Dynamic tossing (280 demos, 6 YCB objects, bins out of reach): 105/120 objects sorted with
  latency matching, 69/120 with latencies set to 0.
- Bimanual cloth folding (250 demos): 14/20; without inter-gripper proprioception 6/20.
- Dish washing (258 demos, 7 dependent steps, CLIP ViT-B/16): 14/20; ResNet-34 from scratch
  0/10.

In the wild (Sec. VI): 1400 demos, 30 locations, 15 cups, 3 people, 12 person-hours. Two
unseen sites (cafe table, water fountain), 60 trials: 28/40 on training cups, 15/20 on
unseen cups, 43/60 = 71.7% overall. The same ViT backbone trained on narrow-domain data
only: 0%.

Throughput (Fig. 11, 15 min windows including resets): UMI more than 3x SpaceMouse teleop on
cup arrangement at 48% of bare-hand speed; on tossing UMI runs at 64% of bare hand while
teleop produced zero usable demos. SLAM accuracy against MoCap over 14 tasks: ATE 6.1 mm and
3.5 degrees; relative pose between two grippers 10.1 mm and 0.8 degrees.

## What it changes in practice

- Latency is a first-class deployment parameter. Measure it per stream and per actuator
  before blaming the policy; the tossing ablation is a 30 point swing from timing alone.
- Relative EE trajectories make the policy calibration-free with respect to robot base
  placement and transfer across arms; absolute actions were the worst action space even in
  the lab.
- Generalisation came from data diversity (30 locations), not from the pretrained backbone;
  the narrow-data control with the same ViT scored 0%.

## Known limitations and follow-ups

- SLAM needs texture. Blank walls, dark scenes, and large occluding objects (doors, drawers)
  break tracking; kinematic feasibility is only checked after the fact.

## Open questions

- How much of the 0.5x execution speed is compensating for residual latency error, as the
  authors suspect, versus policy smoothness?
- Mirrors moved cup arrangement from 18/20 to 20/20. Is that distinguishable from noise at n = 20?

## Sources

- Paper: https://arxiv.org/abs/2402.10329 (v3, 6 Mar 2024). Sec. III, V, VI, VII, VIII; Fig.
  8, 11, 12; Appendix A, C, D, E, F; Table A1.
- Hardware and code: https://umi-gripper.github.io
