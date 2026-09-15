---
title: "DROID: A Large-Scale In-The-Wild Robot Manipulation Dataset"
date: 2026-09-05
tags: [paper, dataset, imitation-learning, teleoperation, franka, diffusion-policy, data-collection]
status: draft
source: https://arxiv.org/abs/2403.12945
---

# DROID (Khazatsky, Pertsch et al. 2024)

## Problem

Existing large manipulation datasets come from a handful of scenes in one or
two labs, so policies trained on them see little variation in rooms, objects,
viewpoints and workspace locations. Collecting outside the lab is a logistics
and safety problem, and inconsistent hardware across sites makes the data hard
to use together ([Khazatsky et al. 2024, Sec. I, II](https://arxiv.org/abs/2403.12945)).

## Core idea

Standardize one portable Franka rig, replicate it 18 times across 13
institutions on three continents, and run a collection protocol that forces
diversity: new scene every ~20 minutes, tasks sampled at random from a
per-scene list, periodic prompts to move cameras, change lighting or add
clutter. The result is 76k successful episodes (350 h) across 564 scenes, 52
buildings and 86 de-duplicated verbs, with three calibrated stereo streams and
crowd-sourced language labels. Co-training a diffusion policy 50/50 with DROID
beats both in-domain-only training and co-training with Open X-Embodiment
([Sec. III, IV, V](https://arxiv.org/abs/2403.12945)).

## Method details that matter for reimplementation

- Rig: Franka Emika Panda 7-DoF, Robotiq 2F-85 gripper, two Zed 2 stereo
  cameras on tripods, one Zed Mini on the wrist, Meta Quest 2 controllers for
  6-DoF teleop plus continuous gripper, Polymetis controller at 15 Hz logging
  both joint-space and end-effector actions, NUC plus laptop GUI, all on a
  wheeled height-adjustable desk with one power cable ([Sec. III-A, Fig. 2](https://arxiv.org/abs/2403.12945)).
- Protocol: extrinsic calibration with a checkerboard and OpenCV at each new
  scene; the GUI samples the task for each episode from the operator's list;
  operators mark success or failure; up to ~100 episodes or 20 minutes per
  scene ([Sec. III-B](https://arxiv.org/abs/2403.12945)).
- Labels: up to three independent language instructions per episode from
  tasq.ai crowd workers; verbs de-duplicated with GPT-4; scene types assigned
  with GPT-4V ([Sec. III-B, IV](https://arxiv.org/abs/2403.12945)).
- The 16k episodes marked "not successful" are released but excluded from the
  76k count and from training ([Sec. III-B, V-A](https://arxiv.org/abs/2403.12945)).
- Post-hoc calibration release: camera-to-base for ~36k scenes, a curated 24k
  superset with both cameras, quality metrics included ([Sec. III-B, Appendix G](https://arxiv.org/abs/2403.12945)).
- Policy used in experiments: Robomimic diffusion policy, two external RGB
  streams at 128 x 128 with color jitter and random crop to 116 x 116,
  ImageNet ResNet-50 per camera, frozen DistilBERT language embedding,
  gripper position and state, MLP [1024, 512, 512], U-Net head [256, 512,
  1024], observation horizon 2, predicts 16 absolute end-effector steps and
  executes 8, DDIM, EMA 0.75, batch 128, Adam 1e-4 linear decay, 25k steps
  (50k for Cook Lentils OOD) ([Appendix F, Table II](https://arxiv.org/abs/2403.12945)).
- Co-training mixes batches 50/50 between the in-domain demos and DROID
  (or the Octo-curated OXE split minus Language Table) ([Sec. V-B](https://arxiv.org/abs/2403.12945)).

## Result that matters (with n and hardware)

Six tasks in four locations (lab, office, two households), each with an
in-distribution and an out-of-distribution variant, 50 to 150 in-domain demos
per task, evaluated head-to-head with 10 rollouts per task, setting and
method on the DROID rig ([Sec. V-A, V-B, Fig. 7](https://arxiv.org/abs/2403.12945)).

- Averaged over tasks, DROID co-training beats the next best method by 22
  points absolute success in-distribution and 17 points out of distribution;
  the intro rounds this to "20 % on average". Per-task bars are in Fig. 8;
  the text does not tabulate them ([Fig. 8, Sec. I](https://arxiv.org/abs/2403.12945)).
- Scene diversity control: 7362 episodes from the 20 largest scenes versus
  7362 uniformly sampled episodes; the diverse subset wins on the OOD tasks,
  and the full dataset matches or beats both ([Sec. V-C, Fig. 10](https://arxiv.org/abs/2403.12945)).
- Diversity analysis versus RT-1, Bridge V2, RH20T: 564 scenes across 10
  scene types (an order of magnitude more), 1417 unique third-person
  viewpoints, first-grasp locations spread across the workspace instead of one
  table plane ([Fig. 4 to 6](https://arxiv.org/abs/2403.12945)).
- Training compute: Google TPU Research Cloud (acknowledgements); TPU type
  and hours are not stated (unverified).

## What it changes in practice

DROID is the reference for what a field data-collection SOP looks like: one
replicable rig, a GUI that randomizes tasks and nags for scene augmentation,
success labels at collection time, and calibration you can audit later. For
policy work on a Franka with external cameras, mixing DROID 50/50 into a
small in-domain set is a cheap, tested win, especially for OOD evaluations.
The hardware guide is public, so the rig can be reproduced at a customer site.

## Known limitations and follow-ups

- Single embodiment and gripper; cross-embodiment transfer is not tested here
  ([Sec. III-A](https://arxiv.org/abs/2403.12945)).
- Evaluation is 10 rollouts per cell, so per-task differences are noisy; the
  paper reports standard error only on the average ([Fig. 8](https://arxiv.org/abs/2403.12945)).
- Initial checkerboard calibration was unreliable enough to need a post-hoc
  fix ([Sec. III-B, Appendix G](https://arxiv.org/abs/2403.12945)).
- No zero-shot result in a scene with no in-domain demos; the authors list
  this as an open question ([Sec. VI](https://arxiv.org/abs/2403.12945)).

## Open questions

- How the 50/50 mixing ratio should change with in-domain set size.
- Whether the "not successful" 16k episodes help as negatives for reward or
  value learning.

## Sources

- [Khazatsky, Pertsch, Nair, Balakrishna, Dasari, Karamcheti, Nasiriany et al. DROID. arXiv 2403.12945 (v2, Apr 2025)](https://arxiv.org/abs/2403.12945)
- [Dataset, visualizer, hardware guide (CC-BY 4.0)](https://droid-dataset.github.io)
