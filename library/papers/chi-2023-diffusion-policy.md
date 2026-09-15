---
title: "Diffusion Policy: Visuomotor Policy Learning via Action Diffusion"
date: 2026-09-05
tags: [paper, imitation-learning, diffusion, action-chunking, multimodality]
status: draft
source: https://arxiv.org/abs/2303.04137
---

# Diffusion Policy (Chi, Xu, Feng, Cousineau, Du, Burchfiel, Tedrake, Song)

Read from arXiv v5 (14 Mar 2024), the extended IJRR version. It adds a control-theory
section, vision-encoder ablations, and three bimanual real-world tasks to the RSS 2023
paper.

## Problem

Behaviour cloning regresses observation to action, but demonstration data is multimodal (go
left or right around the block), temporally correlated, and demands precision. Explicit
regressors average modes; mixture and discretised heads are hyperparameter-sensitive and
collapse modes; energy-based implicit policies (IBC) need negative sampling and train
unstably (Sec. 4.4, Fig. 6).

## Core idea

Represent the policy as a conditional denoising diffusion model over an action *sequence*.
Starting from Gaussian noise, a network predicts the noise to subtract for K iterations,
conditioned on the last T_o observations. The model learns the score of the action
distribution, so it needs no normalising constant, expresses arbitrary multimodal
distributions, and scales to high-dimensional outputs. Three engineering pieces make it a
robot policy: receding-horizon execution (predict T_p, execute T_a, replan), visual features
as conditioning rather than part of the diffused variable, and a time-series diffusion
transformer variant for sharp, high-frequency actions.

## Method details that matter for reimplementation

- Horizons (Table 7, CNN variant, nearly every task): T_o = 2, T_a = 8, T_p = 16. Real tasks
  use T_a = 6. Block Push (scripted, Markovian data) is the exception at T_o = 3, T_a = 1,
  T_p = 12. Fig. 5 shows T_a = 8 as the sweet spot; Appendix B.1 shows vision policies
  prefer T_o = 2.
- Action space: position control (absolute end-effector pose) beats velocity control for
  Diffusion Policy, while baselines prefer velocity (Fig. 4, Sec. 4.2). Rotations use the 6D
  representation of Zhou et al. for position control. Normalise each action dimension to
  [-1, 1]; do not use zero-mean unit-variance because DDPM clips to [-1, 1] (Appendix A.1).
- CNN variant: 1D temporal U-Net from Janner et al. with FiLM conditioning on observation
  features and diffusion step. Works "out of the box" with little tuning; over-smooths fast
  action changes. Recommended first try.
- Transformer variant: minGPT decoder; noisy action tokens as input, diffusion step
  embedding prepended, observation embeddings via cross-attention, causal mask. Better on
  state-based tasks with fast action changes, but attention dropout and weight decay needed
  per-task tuning (Table 8).
- Vision encoder: ResNet-18 from scratch, per camera, global average pool replaced with
  spatial softmax, BatchNorm replaced with GroupNorm (needed with EMA). Random crop
  augmentation (84 to 76 px in sim, 320x240 to 288x216 real). Table 5 ablation on robomimic
  Square: fine-tuning a CLIP ViT-B/16 at 10x lower lr reached 98%; frozen pretrained
  encoders were worst (40 to 70%).
- Noise schedule: squared-cosine (iDDPM). Sim: 100 DDPM steps train and inference. Real:
  DDIM with 100 train steps and 16 inference steps (Table 7; Sec. 3.4 quotes 10 steps at 0.1
  s latency on an RTX 3080).
- Optimiser: lr 1e-4, weight decay 1e-6 (CNN), cosine schedule with 500 (CNN) or 1000
  (transformer) warmup steps, batch 256 state / 64 image, EMA weights. Sim trains 4500
  epochs (state) or 3000 (image).
- Real Push-T data: 136 demos. Sauce tasks: 50 demos each, 90% for training. Bimanual: 210
  (egg beater), 162 (mat), 284 (shirt).

## Result that matters

Simulation (Tables 1, 2, 4): 15 tasks across robomimic, Push-T, Block Push, Franka Kitchen;
3 seeds x 50 initial conditions (22 for robomimic because of an evaluation bug the authors
disclose), reporting max checkpoint / mean of last 10 checkpoints. Average relative
improvement over the best baseline: 46.9% (definition in Appendix B.2). Example,
Transport-mh image: DP-C 0.89/0.69 versus LSTM-GMM 0.44/0.24 and IBC 0.

Real, UR5, Push-T (Table 6, 20 episodes per method, same initial states, 10 Hz commands
interpolated to 125 Hz): end-to-end DP 95% success and 0.80 IoU versus human 0.84; LSTM-GMM
best 20%; IBC 0%. R3M-pretrained encoder 80% but jittery; ImageNet-pretrained 15%.

Real, Franka Panda, 20 trials each: Mug Flip 90% (LSTM-GMM 0%); Sauce Pour success 79% and
IoU 0.74 versus human 0.79; Sauce Spread 100% and coverage 0.77 versus human 0.79. Bimanual,
20 trials each: Egg Beater 55%, Mat Unrolling 75%, Shirt Folding 75%. Egg Beater demos were
only feasible with haptic teleop (0/10 without, 10/10 with).

## What it changes in practice

- Default recipe for a new manipulation task: CNN Diffusion Policy, T_o 2, T_a 8, T_p 16,
  absolute EE position actions, end-to-end ResNet-18 with GroupNorm and spatial softmax,
  DDIM 16 steps for real-time inference. The sauce tasks reused Push-T hyperparameters and
  worked first try.
- Idle actions in demos (pauses, pouring) no longer need filtering; single step policies
  overfit to them and freeze.
- Position control plus action sequences tolerated up to 4 steps of simulated latency
  without loss (Fig. 5 right).

## Known limitations and follow-ups

- Inference cost: 10 to 16 denoising passes per action chunk. VQ-BeT (arXiv 2403.03181)
  reports 5x faster single-step inference; UMI (arXiv 2402.10329) uses this policy as its
  learner with latency matching.
- Transformer variant hyperparameters vary "greatly" across tasks (Appendix A.4).

## Open questions

- The receding-horizon assumption fails on imprecise hardware (VQ-BeT paper, Table 11, Hello
  Robot Stretch). Where is the controller-accuracy threshold below which T_a must drop to 1?
- Why does the CNN always gain from more parameters while the transformer sometimes loses depth?

## Sources

- Paper: https://arxiv.org/abs/2303.04137 (v5, 14 Mar 2024). Sec. 3, 4.3, 5.2, 6, 7; Tables
  1, 2, 5, 6, 7, 8; Appendix A, C, D.
- Code and data: https://diffusion-policy.cs.columbia.edu
