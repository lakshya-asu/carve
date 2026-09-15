---
title: "Open X-Embodiment: Robotic Learning Datasets and RT-X Models"
date: 2026-09-05
tags: [paper, dataset, cross-embodiment, vla, imitation-learning, rlds]
status: draft
source: https://arxiv.org/abs/2310.08864
---

# Open X-Embodiment and RT-X (Open X-Embodiment Collaboration, 2023)

## Problem

Every lab's dataset is narrow: one robot, one room, a few tasks. The paper
tests whether pooling datasets across robots gives positive transfer (a
policy trained on everyone's data beats one trained on the evaluation
robot's data alone), and packages the pooled data so others can try.

## Core idea

Convert 60 datasets from 22 embodiments into one RLDS format with a coarsely
aligned 7-DoF end-effector action, then retrain RT-1 and RT-2 unchanged on a
9-embodiment mixture. No adapters, no frame alignment. Positive transfer
appears anyway, most strongly for small datasets and for the large model.

## Method details that matter for reimplementation

- Dataset: 1M+ trajectories, 22 embodiments, 60 datasets, 34 labs, 21
  institutions; 527 skills and 160,266 tasks (Sec. VI). Franka has the most
  distinct scenes; xArm and the Google Robot the most trajectories (Fig. 1).
- Action alignment (Sec. IV-A): one canonical camera per dataset, resized to
  a common resolution; actions mapped to a 7-D end-effector vector (x, y, z,
  roll, pitch, yaw, gripper) or their rates, normalized per dataset before
  discretization and de-normalized per embodiment at inference. Frames are
  not aligned and absolute vs relative control is left as in the source, so
  the same token means different motions on different robots.
- RT-1-X: RT-1 architecture, 35M parameters, history of 15 images here (the
  RT-1 paper used 6), 256 bins x 8 dimensions, robot data only.
- RT-2-X: RT-2-PaLI-X (5B and 55B) co-fine-tuned about 1:1 web to robot
  data, cross-entropy over language tokens.
- Training mixture: 9 embodiments from RT-1, QT-Opt, Bridge, Task Agnostic
  Robot Play, Jaco Play, Cable Routing, RoboTurk, NYU VINN, Austin VIOLA,
  Berkeley Autolab UR5, TOTO, Language Table. Octo later called this the
  "RT-X mix" and put it at about 350k episodes.
- Batch size, steps, learning rates and accelerators are not stated; RT-2
  hyperparameters are inherited by reference. Inference at 3 to 10 Hz
  depending on robot; RT-1-X local, RT-2-X from a cloud service.

## Result that matters

3600 real-robot trials across 6 robots (Sec. V). Trial counts per table
cell are not stated.

Small-dataset domains (Fig. 3; Kitchen Manipulation, Cable Routing, NYU Door
Opening, AUTOLab UR5, Robot Play, each run at the originating lab): RT-1-X
beat the creators' own method on 4 of 5, with mean success 50% higher than
either the original method or an RT-1 trained on that dataset alone.
Per-domain numbers are only in the figure.

Large-dataset domains (Table I):

| Eval | Original method | RT-1 | RT-1-X | RT-2-X 55B |
|------|----------------|------|--------|------------|
| Bridge, WidowX, Stanford IRIS | 13 | 40 | 27 | 50 |
| Bridge, WidowX, UCB RAIL | 13 | 30 | 27 | 30 |
| RT-1 6 skills, Google Robot | n/a | 92 | 73 | 91 |

RT-1-X underfits when the target dataset is already large; RT-2-X does not.

Emergent skills on the Google Robot (Table II, Bridge tasks the Google Robot
never saw): RT-2 55B 27.3%, RT-2-X 55B 75.8%; dropping Bridge from training
gives 42.8%, so the skills came from the WidowX data. The RT-2
generalization eval stays flat at 62% vs 61%.

Design ablations (Table II, 5B, emergent skills): history 2 vs none 44.4%
vs 14.5%; web pretraining vs scratch 44.4% vs 0%; co-fine-tuning vs
fine-tuning 44.4% vs 48.7% (no gain, unlike RT-2; attributed to more
diverse robot data).

## What it changes in practice

- The dataset is the deliverable most people use; Octo, OpenVLA and pi0
  train on curated subsets of it.
- The alignment convention (7-D EE delta, per-dataset normalization, no
  frame alignment) became the de facto cross-embodiment interface. Camera
  pose and control mode differ across datasets; a new dataset should record
  both in its DATASET.md.
- RT-1-X checkpoint released for inference and fine-tuning (Sec. III).
  RT-2-X weights were not released; Octo and OpenVLA compared against it via
  an API. Dataset and code licence are not stated in the paper; per-dataset
  licences live on the hosting site (unverified).
- Positive transfer needs capacity: at 35M, pooled data hurt data-rich domains.

## Known limitations and follow-ups

- Only 9 of 22 embodiments were in the training mix at experiment time.
- No robots with different sensing or actuation; no test on a new robot; no
  criterion for when transfer is positive (Sec. VI).
- The dataset has since grown (OpenVLA cites 70+ datasets, 2M+ trajectories).

## Open questions

- The same Bridge tasks at Stanford and Berkeley gave RT-1 40% vs 30% and
  RT-2-X 50% vs 30%. How much of any reported number is site variance?
- Does skipping frame alignment cost precision, and would aligning help a
  small model?

## Sources

- Paper: https://arxiv.org/abs/2310.08864 (arXiv HTML v9, read 2026-09-05)
- Project page and dataset index: https://robotics-transformer-x.github.io
