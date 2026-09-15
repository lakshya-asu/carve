---
title: "Implicit Behavioral Cloning"
date: 2026-09-05
tags: [paper, imitation-learning, energy-based-model, multimodality]
status: draft
source: https://arxiv.org/abs/2109.00137
---

# Implicit Behavioral Cloning (Florence et al., CoRL 2021)

Read from arXiv v1 (1 Sep 2021). Robotics at Google. The paper that made the field take
multimodality and discontinuity in BC seriously; Diffusion Policy is best read as the answer
to its training-stability problem.

## Problem

Standard BC fits an explicit function a = F(o) with MSE or a mixture density head. A
continuous regressor must take every intermediate value across a discontinuity (switch from
approach to insert) and averages multi-valued targets. Fine manipulation is full of both.
The paper asks whether the *form* of the policy, not the loss or the data, is the
bottleneck.

## Core idea

Learn an energy E(o, a) and act by optimising: a* = argmin_a E(o, a). Train E with an
InfoNCE-style contrastive loss where the demonstrated action is the positive and sampled
actions are negatives. Section 3 shows on 1-D toy functions that an implicit MLP fits step
discontinuities sharply, represents set-valued targets, and extrapolates piecewise linearly,
while an MSE MLP of the same size interpolates across the step. Theorems 1 and 2 (Sec. 5)
show argmin over a continuous E can represent any closed-graph set-valued function to
arbitrary accuracy, with bounded Lipschitz constant in E even when the target function is
steep.

## Method details that matter for reimplementation

Three inference/training variants (Appendix B), all Adam:

- Derivative-free optimisation (DFO). Negatives drawn uniformly in the action bounds
  (per-dimension data min/max plus a 0.05 range buffer, clipped to environment limits).
  Batch 512, 256 counter-examples per sample, lr 1e-3 with 0.99 decay every 100 steps, no
  dropout. Inference: sample N actions, softmax over negative energies, resample with
  replacement, add Gaussian noise, shrink the noise scale, repeat. Paper defaults:
  sigma_init 0.33, shrink K 0.5, 3 iterations, 16,384 samples. Real-robot setting: 1024
  samples, 3 iterations. Works for action dimension of about 5 or less.
- Autoregressive DFO. One energy model per action dimension, each conditioned on the
  dimensions before it. Scales to 16-D on the particle task but needs D separate models.
- Langevin MCMC. Gradient-based sampling with a polynomially decaying step size,
  stop_gradient through the chain, spectral norm plus a gradient penalty for stability,
  twice as many inference steps as training steps. Best on D4RL (100 Langevin iterations, 8
  counter-examples).

Architecture: late-fusion ConvMLP for images; the image is encoded once and the action is
concatenated afterward, so visual compute matches the explicit baseline. For image tasks,
spatial soft-argmax pooling beat average pooling for EBMs (Table 4). Real-robot config
(Table 7): 90x120 images, 4-layer ConvMaxPool, 1024x4 MLP, batch 128, 100k steps, 5.0 h on
8x V100.

Real robot: xArm6 constrained to a plane above the table, cylindrical end-effector, one
RealSense D415 RGB stream at 640x360, policy at 5 Hz, action = delta Cartesian setpoint
interpolated to 100 Hz. Demos via a mouse interface. Inference 7.22 ms (EBM) versus 3.49 ms
(MSE) on an RTX 2080 Ti.

## Result that matters

Real robot (Table 4; 20 rollouts x 3 seeds = 60 trials per method per task):
Push-Red-then-Green 85.0 +/- 5.0% versus MSE 35.0 +/- 18.0%; Push-Red/Green-Multimodal 88.3
+/- 7.6% versus 55.0 +/- 18.0%; Insert-Blue (1 mm tolerance) 83.3 +/- 3.8% versus 6.7 +/-
9.4%; Sort-Blue-from-Yellow 48.3 +/- 4.6% versus 19.6 +/- 1.5%. Demo counts: 95, 410, 223,
502.

Simulation: D4RL human-expert tasks (Table 2; 3 seeds x 100 evals): implicit BC matched or
beat CQL and S4RL on several tasks without rewards (kitchen-complete 3.37 vs S4RL 3.08;
door-human 361 vs 234.3). Bimanual sweeping, 12-DoF, image input, 1000 scripted demos: EBM
78.2 +/- 2.7% versus MSE 63.9 +/- 7.7% (Table 5). Simulated pushing from pixels, 2000 demos:
EBM 100%, MSE 87.0%, MDN 10.0% (Table 3). N-D particle: 95% success up to 16-D for implicit
versus 8-D for MSE at fixed 2000 demos.

## What it changes in practice

- Diagnostic: if a BC policy hesitates at a decision boundary or lands between two
  demonstrated behaviours, the policy class is the suspect before the data is.
- Insert-Blue is the cleanest evidence that mm-precision from RGB at 5 Hz is a modelling
  problem: same data, same encoder, 6.7% to 83.3%.
- Spatial soft-argmax pooling is the right image head for energy models; Diffusion Policy
  inherited this choice.

## Known limitations and follow-ups

- Training instability. Diffusion Policy (Sec. 4.4, Fig. 6) shows IBC's training loss
  decreasing while action accuracy does not, and success oscillating between checkpoints;
  the IBC authors themselves evaluate every checkpoint and report the best. On hardware this
  means many eval runs to pick a policy.
- DFO does not scale past about 5 action dimensions; autoregressive needs D models; Langevin
  needs gradient penalties and spectral norm.

## Open questions

- Does the discontinuity argument (Sec. 3) explain the real-robot gains, or is it mostly
  multimodality? The coordinate-regression experiment (Fig. 4) has no multimodality and
  still shows 1 to 2 orders of magnitude lower error, which argues for the former.
- Would a modern sampler (annealed Langevin, or diffusion as the sampler for the same
  energy) recover IBC's expressivity without the instability?

## Sources

- Paper: https://arxiv.org/abs/2109.00137 (v1, 1 Sep 2021). Sec. 2 to 5, Tables 2 to 7,
  Appendix B, C.2, C.3, D.5, H.
- Diffusion Policy comparison: https://arxiv.org/abs/2303.04137 Sec. 4.4.
