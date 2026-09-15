---
title: "ALOHA / ACT: Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware"
date: 2026-09-05
tags: [paper, imitation-learning, bimanual, teleoperation, action-chunking, transformer]
status: draft
source: https://arxiv.org/abs/2304.13705
---

# ALOHA / ACT (Zhao, Kumar, Levine, Finn, 2023)

Read from arXiv v1 (23 Apr 2023). Two contributions: a sub-$20k bimanual leader-follower
teleop rig (ALOHA) and an imitation learning algorithm that predicts action chunks with a
transformer trained as a CVAE (ACT).

## Problem

Fine manipulation (open a condiment cup, slot a battery, thread a velcro tie) needs
millimetre precision and closed-loop visual feedback. Cheap arms are imprecise (ViperX
accuracy 5 to 8 mm per the paper) and single-step behaviour cloning compounds errors and
fails on non-Markovian human data such as pauses. Prior teleop rigs that reach this
dexterity cost 5 to 10 times more.

## Core idea

Two ideas, one hardware and one learning. Hardware: joint-space teleop by backdriving a
smaller WidowX "leader" whose joints are mirrored by a ViperX "follower", recorded at 50 Hz
with four webcams. Learning: predict the next k target joint positions as one chunk (k = 100
at 50 Hz, so 2 s of motion), query the policy every step, and average overlapping chunks per
timestep with exponential weights (temporal ensemble). Train the chunk predictor as a
conditional VAE so multimodal human data does not average into mush.

## Method details that matter for reimplementation

- Action: absolute target joint positions of the *leader* arms, 14-D (7 per arm including
  gripper). Leader, not follower, because the leader-follower gap encodes the force applied
  through the motor PID. Delta joint actions degraded performance (Sec. IV-C).
- Observation: four 480x640 RGB images (front, top, two wrist) plus 14-D follower joint
  positions. No history.
- Policy (CVAE decoder): ResNet18 per camera to a 15x20x512 feature map, flattened, 2D
  sinusoidal position embedding, concatenated over 4 cameras (1200x512), plus projected
  joints and style variable z (1202x512 into the transformer encoder). Transformer decoder
  with k fixed sinusoidal queries cross-attends and outputs kx512, down-projected to kx14.
- CVAE encoder (train only): BERT-style transformer over [CLS], joints, and the k-step
  action sequence; [CLS] output predicts diagonal Gaussian z. At test time z = 0. Images are
  excluded from the encoder for speed.
- Loss: L1 reconstruction (better than L2 for precision, per the paper) plus beta-weighted
  KL, beta = 10.
- Table III hyperparameters: lr 1e-5, batch 8, 4 encoder layers, 7 decoder layers, hidden
  512, feedforward 3200, 8 heads, chunk 100, dropout 0.1.
- Temporal ensemble weights w_i = exp(-m i), w_0 on the oldest prediction. The paper does
  not state the value of m; the public repo default is 0.01 (unverified).
- About 80M parameters, trained from scratch per task, roughly 5 h on one 11 GB RTX 2080 Ti;
  inference about 0.01 s on the same GPU.
- Data: 50 demos per task (100 for Thread Velcro), 8 to 14 s each at 50 Hz, so 10 to 20 min
  of data per task and 30 to 60 min wall-clock including resets. Checkpoint with the lowest
  validation loss is deployed.

## Result that matters

Table I and II, real tasks: 1 seed, 25 trials each, ALOHA hardware. Final-stage success:
Slide Ziploc 88%, Slot Battery 96%, Open Cup 84%, Thread Velcro 20%, Prep Tape 64%, Put On
Shoe 92%. Best baseline (BeT) scored 0% final success on every real task. Sim (Transfer
Cube, Bimanual Insertion; 3 seeds x 50 trials): ACT 97/82 and 90/60 (scripted/human data on
cube), 86/50 and 93/76 on insertion, versus at most 60/16 for BeT.

Ablations (Fig. 7, sim, averaged over 4 settings): success rises from 1% at k = 1 to 44% at
k = 100 without temporal ensemble, then dips slightly toward k = episode length. Temporal
ensemble adds 3.3% for ACT and 4% for BC-ConvMLP but hurts the non-parametric VINN. Removing
the CVAE on human data drops success from 35.3% to 2%; on scripted data it makes no
difference. A 6-person user study found 5 Hz teleop takes 62% longer than 50 Hz (p < 0.001,
repeated measures).

## What it changes in practice

- Chunking is the transferable lesson: it helped BC-ConvMLP and VINN too, so a chunked
  output head is a cheap upgrade for any BC policy on high-frequency data.
- Use leader (commanded) positions as the action label, not measured follower positions,
  when the low-level controller is a stiff PID.
- The CVAE only matters for human data. If demos are scripted, drop it.
- 50 demos and one GPU-afternoon per task is the budget this recipe assumes; the failure
  cases below are what to expect when perception is the limit.
- Joint-space leader-follower teleop avoids IK singularities near the workspace edges, which
  is where fine tasks live on a 6-DoF arm.

## Known limitations and follow-ups

- Thread Velcro at 20%: the black tie on a black table occupies few pixels; errors of a few
  mm at grasp become >10 mm at insertion (Sec. V-C).
- Two attempted tasks failed outright (Appendix F): unwrapping candy (0/10 final stage on
  the first protocol, 3/5 candies on a second) and opening a flat ziploc bag. The authors
  blame perception and data volume.
- Hardware: motors lack torque for heavy or sealed objects; no multi-finger tasks; no
  fingernail-style actions.

## Open questions

- How does k = 100 interact with control rates other than 50 Hz? The paper fixes both; the
  right chunk in seconds versus steps is untested.
- Is L1 over L2 a general result or specific to joint-position targets?
- The 1-seed, 25-trial real evaluations give wide confidence intervals; a reproduction
  should budget at least 3 seeds before quoting deltas.

## Sources

- Paper: https://arxiv.org/abs/2304.13705 (v1, 23 Apr 2023). Tables I to III, Sec. IV-C,
  Sec. VI, Appendix D and F.
- Project page and code: https://tonyzhaozh.github.io/aloha
