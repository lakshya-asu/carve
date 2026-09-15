---
title: "Evaluating Real-World Robot Manipulation Policies in Simulation (SIMPLER)"
date: 2026-09-05
tags: [paper, evaluation, real-to-sim, simulation, generalist-policies, benchmark, sapien]
status: draft
source: https://arxiv.org/abs/2405.05941
---

# SIMPLER (Li, Hsu, Gu, Pertsch, Mees et al. 2024)

## Problem

Generalist manipulation policies are evaluated on real robots, which is slow,
expensive and hard to reproduce across labs, and the burden grows with policy
breadth. Validation MSE on held-out demos, the cheap alternative, does not
track real performance ([Li et al. 2024, Sec. 1, Table I](https://arxiv.org/abs/2405.05941)).

## Core idea

Build simulated copies of two common real setups (Google Robot from the RT
papers, WidowX from BridgeData V2) that are "realistic enough" for policy
rankings to match real rankings, not digital twins. Close the control gap with
offline system identification of PD gains from replayed demos, and close the
visual gap by green-screening the real background behind simulated foreground
and baking real textures onto objects and the arm. Judge the pipeline with a
rank-aware metric (MMRV) alongside Pearson r ([Sec. III, IV](https://arxiv.org/abs/2405.05941)).

## Method details that matter for reimplementation

- MMRV: for each policy take the largest real-performance gap |R_i - R_j|
  among pairs the simulator mis-orders, then average over policies. Range
  [0, 1], lower is better; it ignores mis-orderings between policies whose
  real success rates are within noise ([Eq. 1, 2, Fig. 3](https://arxiv.org/abs/2405.05941)).
- Control gap: replay recorded demo actions open-loop in sim, minimize mean
  end-effector translation error plus arcsin of the rotation Frobenius error
  over stiffness and damping with three rounds of simulated annealing on a
  shrinking search range. Uses existing RT-1 and Bridge demos, no new data
  ([Sec. IV-A, Eq. 3 to 5, Fig. 4](https://arxiv.org/abs/2405.05941)).
- Visual gap: inpaint robot and objects out of the first real video frame,
  take the sim segmentation mask of arm and interactable objects, composite
  I = M * I_sim + (1 - M) * I_real. Then project real textures onto object
  meshes and bucket-paint arm texture colors from real frames. Because the
  real arm's apparent color shifts during motion, evaluate with four tuned arm
  colors and average ([Sec. IV-B, Fig. 5](https://arxiv.org/abs/2405.05941)).
- Asset pipeline: URDFs from public repos or ROS export, intrinsics via fSpy
  from video, meshes from Objaverse or single-view reconstruction, CoACD
  collision shapes, camera pose aligned to fixed scene edges ([Sec. V](https://arxiv.org/abs/2405.05941)).
- Simulator: SAPIEN at 500 Hz, about 3.5k steps/s at 640 x 512 on an RTX 4090
  (7x real time); reproduced in Isaac Sim ([Sec. V, VI-D, Fig. 10](https://arxiv.org/abs/2405.05941)).
- Variant Aggregation (randomize scene factors and average) is the tested
  alternative and correlates worse ([Sec. IV-B, Table I](https://arxiv.org/abs/2405.05941)).

## Result that matters (with n and hardware)

Policies: RT-1 at three checkpoints (Begin, 15 %, Converged), RT-1-X, RT-2-X,
Octo-Base, Octo-Small. Real trials per Google Robot task: pick coke can 75
(3 orientations x 25 grid points), move near 60, open/close drawer 54, open
drawer and place apple 27. Bridge tasks 24 trials each. Octo sim results
average three seeds; Google Robot sim results average four arm colors. About
1500 evaluation episodes total across real and sim ([Fig. 1, Appendix B](https://arxiv.org/abs/2405.05941)).

- Visual Matching on Google Robot: pick coke can MMRV 0.031, r 0.976; move
  near MMRV 0.111, r 0.855; open/close drawer MMRV 0.055, r 0.915; drawer and
  apple MMRV 0.000, r 0.969. Bridge tasks averaged: MMRV 0.014, r 0.890
  ([Fig. 6, 7](https://arxiv.org/abs/2405.05941)).
- Validation MSE as the ranking signal: pick coke can MMRV 0.412, r 0.464;
  move near MMRV 0.408, r 0.230 ([Table I](https://arxiv.org/abs/2405.05941)).
- Real success on pick coke can, for scale: RT-1 Converged 85.3 %, RT-1 15 %
  92.0 %, RT-1-X 76.0 %, RT-2-X 90.7 %, Octo-Base 29.3 %, RT-1 Begin 13.3 %
  ([Table IV](https://arxiv.org/abs/2405.05941)).
- Distribution-shift deltas match: camera pose shift cost RT-1 (no aug) 46
  points real vs 47 sim; table texture 39 vs 14; lighting 8 vs 6. Patterned
  tables hurt more than solid colors in both (25 % vs 4 % real, 24 % vs 2 %
  sim) ([Fig. 8, Sec. VI-C](https://arxiv.org/abs/2405.05941)).
- Novel-shift prediction: sim showed Octo-Base dropping from 29.3 % to 0 %
  on arm-texture change; gift-wrapping the real arm reproduced it, RT-1-X
  held up ([Fig. 9, Table VIII](https://arxiv.org/abs/2405.05941)).
- Ablations: perturbing identified PD gains raises MMRV; green screen alone
  or texture tuning alone gives no gain over raw sim ([Table II, III](https://arxiv.org/abs/2405.05941)).

## What it changes in practice

A checkpoint sweep of a VLA on Google Robot or WidowX tasks can run in sim
overnight and the ranking is trustworthy at the granularity of the reported
MMRV. Two habits transfer to any customer setup: identify controller gains
from replayed demos before trusting a sim, and fix every visible surface
(background, objects, arm) at once, since partial matching buys nothing.
Report MMRV, not just Pearson r, when validating a proxy evaluation.

## Known limitations and follow-ups

- Rigid objects only; no deformables or liquids ([Sec. VII](https://arxiv.org/abs/2405.05941)).
- Green screen assumes a fixed camera and drops shadows ([Sec. VII](https://arxiv.org/abs/2405.05941)).
- Articulated assets (the drawer cabinet) are hand-built, the slowest step ([Sec. V](https://arxiv.org/abs/2405.05941)).
- RT-1 15 % and Octo-Base shift most between real and sim; absolute sim
  numbers are not real numbers ([Sec. VI-B](https://arxiv.org/abs/2405.05941)).
- One real drawer evaluation stopped after 2 trials for safety; that MMRV is
  an upper bound ([Table IV footnotes](https://arxiv.org/abs/2405.05941)).

## Open questions

- How many real trials per task are needed before MMRV on a new setup is
  itself stable; the paper uses 24 to 75.
- Whether the pipeline holds for wrist cameras, where the arm fills much of
  the image and the "background" moves.

## Sources

- [Li, Hsu, Gu, Pertsch, Mees, Walke, Fu, Lunawat, Sieh, Kirmani, Levine, Wu, Finn, Su, Vuong, Xiao. SIMPLER. arXiv 2405.05941](https://arxiv.org/abs/2405.05941)
- [Project page and code](https://simpler-env.github.io)
