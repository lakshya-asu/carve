---
title: "ChicGrasp: Imitation-Learning based Customized Dual-Jaw Gripper Control for Delicate, Irregular Bio-products Manipulation"
date: 2026-09-06
tags: [paper, food-handling, poultry, diffusion-policy, imitation-learning, gripper, meat-cell]
status: draft
source: https://arxiv.org/abs/2505.08986
---

# ChicGrasp (Davar, Xu, Mahmoudi, Sohrabipour, Pallerla, She, Shou, Crandall, Wang, 2025)

Read from arXiv 2505.08986v1 (13 May 2025). University of Arkansas and Purdue; journal
template, venue not stated. A UR10e with a pneumatic dual-jaw gripper and a diffusion
policy trained on 50 teleop demos picks a raw broiler carcass by both legs and hands it to
a scripted rehang; 41/101 successes. The meat-cutting note cites it as the only learned
grasp of meat in this library.

## Problem

Rehanging chilled broiler carcasses onto a shackle line is manual: 140 birds per minute,
one every 0.43 s, a worker taking under 2 s per bird (Sec. IV). Suction fails on wet
skin and marks the surface; prior automation (GRIBBOT, Robotic Workbench, MFC cutting) is
scripted and does not adapt to leg spacing, size, or orientation (Sec. I).

## Core idea

Co-design a gripper whose jaws close independently so the second jaw does not push the
carcass away before the first engages, and let a diffusion policy output the jaw bits along
with the end-effector position, so the timing of each jaw closure is learned from the
demonstrations rather than scripted.

## Method details that matter for reimplementation

- Gripper (Sec. II-A): about 4 kg, two linear pneumatic jaws (Airtac HFZ double-acting),
  one 5/2 solenoid valve (Tailonz 4V210-08) per jaw, Arduino Uno R4 over USB-C, chevron
  ridges on the jaw faces at 30 degree pitch and 2 mm depth to turn clamping force into
  tangential grip on wet skin without piercing. Eye-in-hand camera on a printed mount that
  keeps both jaws in view.
- Action (Eq. 1): a_t = [x, y, z, g_L, g_R], end-effector position in the base frame plus
  two binary jaw states; orientation is fixed. Jaw logits are thresholded at sigmoid 0.5.
- Observation: stacked RGB from three RealSense D435 at 640x480, 30 Hz (wrist plus left
  and right of the table), joint positions and velocities at 100 Hz, jaw bits at 100 Hz.
- Data: 50 SpaceMouse teleop trajectories of 25 to 40 s on a red table, varying carcass
  pose and lighting (Sec. II-C).
- Policies: Diffusion Policy, LSTM-GMM, and IBC, all on the Diffusion Policy ResNet-18
  encoder with spatial softmax and GroupNorm, trained from scratch, 600 epochs each; batch
  32 on an 80 GB A100 (diffusion), 128 on a V100 (IBC), 64 on a V100 (LSTM-GMM).
- Runtime (Sec. II-E): xyz streamed to the UR velocity controller at 250 Hz; when the
  policy outputs both jaws closed for three consecutive frames, control switches to a
  fixed seven-waypoint lift-and-rehang trajectory.

## Result that matters

Three carcasses differing in size, leg spacing, and skin condition (some aged, with
changed colour and texture). Success needs both legs clamped, a lift of at least 50 mm
without slip, and the scripted rehang completing (Sec. III). Table I:

| Policy | Chicken 1 | Chicken 2 | Chicken 3 | Total |
|---|---|---|---|---|
| Diffusion Policy | 7/15 | 20/31 | 14/55 | 41/101 (40.6%) |
| IBC | 0/10 | 0/10 | 0/10 | 0/30 |
| LSTM-GMM | 0/20 | 0/20 | 1/20 | 1/60 |

The text says "50 pick-and-rehang trials per method" and then reports 101, 30, and 60;
the table totals are what the per-bird counts sum to. Cycle time is 38 s in the text and
28 s in Table I for the diffusion policy; IBC and LSTM-GMM attempts time out at about
60 s. The abstract's "fail entirely" for LSTM-GMM is 1/60 in the table.

Failure modes (Sec. IV): IBC never committed to a trajectory; LSTM-GMM reached the legs
and did not close the jaws; the diffusion policy sometimes stopped slightly below the ideal
grasp height so the legs were held at a poor vertical offset for the rehang. Most failures
were at the pick; once lifted, the scripted rehang held.

## What it changes in practice

- With 50 demos and a from-scratch ResNet, a diffusion head produced 40.6% where two
  standard BC heads produced 0 to 2%. The gap matches the multimodality argument in
  `library/papers/chi-2023-diffusion-policy.md`; here the multimodality is which jaw
  closes first.
- Per-bird spread from 25% to 65% on three exemplars is the number to plan around, not
  the 40.6% mean. Aged skin and different leg spacing were enough to halve success.
- The learned part stops at the grasp. Handing off to a scripted trajectory once a
  learned "grasp stable" predicate fires is a pattern that keeps the unlearned part
  collision-free and is worth reusing in a cutting cell.
- 38 s per bird against a 0.43 s line takt is two orders of magnitude; the authors list
  policy speed, joint velocity, and closed-loop control as the gaps (Sec. IV).

## Known limitations and follow-ups

- No hygiene treatment: a 3D-printed gripper with an Arduino and a USB camera on a red
  plastic table, not a washdown design. See the EHEDG rows in
  `library/topics/meat-cutting-automation.md`.
- No tactile or force feedback; slip is not detected. Legs were presented perpendicular to
  the approach and at the same height (Sec. III), the easiest case.
- CAD, code, dataset, and logs are promised "will be open-source"; no link in v1
  (unverified whether released).

## Open questions

- Why 15, 31, and 55 trials per bird? Unequal counts and a stated 50-per-method protocol
  suggest trials were added on Chicken 3; the ordering of runs is not given.
- Would fixing orientation in the action space (only xyz is commanded) be the limit on
  birds with rotated legs?

## Sources

- Paper: https://arxiv.org/abs/2505.08986 (v1, 13 May 2025). Sec. I to V; Table I, II;
  Fig. 4, 5, 8, 9.
