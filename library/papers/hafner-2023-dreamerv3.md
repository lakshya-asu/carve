---
title: "Mastering Diverse Domains through World Models (DreamerV3)"
date: 2026-09-05
tags: [paper, reinforcement-learning, model-based-rl, world-models, fixed-hyperparameters, simulation]
status: draft
source: https://arxiv.org/abs/2301.04104
---

# DreamerV3 (Hafner, Pasukonis, Ba, Lillicrap 2023)

## Problem

Every new RL domain needed its own algorithm variant and hyperparameter search.
Reward scales, observation types, action types and horizon all differ, and
model-based agents in particular were fragile to these differences
([Hafner et al. 2023, Introduction](https://arxiv.org/abs/2301.04104)).

## Core idea

A world model (RSSM with discrete latents), a critic and an actor trained
entirely in imagination, plus a set of normalization tricks that make one
hyperparameter table work everywhere: symlog transforms on inputs and
targets, two-hot categorical regression over exponentially spaced bins for
reward and value, KL balancing with free bits, 1 % uniform mixing in every
categorical, and percentile-based return normalization for the actor. Same
config across 8 domains and 150+ tasks, and larger models are both better and
more data-efficient ([Learning algorithm, Fig. 6](https://arxiv.org/abs/2301.04104)).

## Method details that matter for reimplementation

- World model: encoder q(z_t | h_t, x_t), GRU sequence model h_t = f(h_{t-1},
  z_{t-1}, a_{t-1}) with block-diagonal recurrent weights (8 blocks), dynamics
  predictor p(z_t | h_t), reward, continue and decoder heads. Latents are
  vectors of softmax categoricals with straight-through gradients
  ([Eq. 1, Networks](https://arxiv.org/abs/2301.04104)).
- Losses: prediction weight 1, dynamics KL weight 1, representation KL weight
  0.1, both KLs clipped below 1 nat (free bits). This replaces per-domain KL
  tuning from DreamerV2 ([Eq. 2, 3](https://arxiv.org/abs/2301.04104)).
- symlog(x) = sign(x) ln(|x| + 1) applied to vector observations at input and
  as decoder target; symexp two-hot loss with bins symexp(linspace(-20, 20))
  for reward head and critic. Output weights of reward and critic heads are
  initialized to zero ([Robust predictions, Critic learning](https://arxiv.org/abs/2301.04104)).
- Critic: categorical, trained on lambda-returns (lambda 0.95) over imagined
  trajectories (loss scale 1) and on replayed trajectories (loss scale 0.3),
  regularized toward an EMA copy of itself with decay 0.98. Discount 0.997
  ([Critic learning, Table 4](https://arxiv.org/abs/2301.04104)).
- Actor: Reinforce for both discrete and continuous actions, fixed entropy
  scale 3e-4, advantages divided by max(1, S) where S is an EMA (decay 0.99)
  of the 5th to 95th percentile range of returns ([Eq. 6, 7](https://arxiv.org/abs/2301.04104)).
- Optimizer: LaProp with epsilon 1e-20, learning rate 4e-5, adaptive gradient
  clipping at 0.3 of the weight norm; RMSNorm and SiLU throughout; batch 16
  sequences of length 64; replay capacity 5e6; no annealing, prioritized
  replay, weight decay or dropout ([Table 4, Implementation](https://arxiv.org/abs/2301.04104)).
- Imagination horizon: Table 4 says 15, the main text says T = 16. Treat the
  released code as authoritative (unverified which the runs used).
- Model sizes 12M to 400M; 200M default, 12M matches it on the control suites ([Table 3](https://arxiv.org/abs/2301.04104)).

## Result that matters (with n and hardware)

Every agent trained on a single Nvidia A100. Seeds: 5 per benchmark for
Dreamer and PPO, 1 for ProcGen, 10 for BSuite and Minecraft
([Benchmarks, Seeds and error bars](https://arxiv.org/abs/2301.04104)).

- Fixed hyperparameters across Atari (57 games, 200M frames), ProcGen (16
  games, 50M), DMLab (30 tasks, 100M), Atari100k (26 games, 400k frames),
  Proprio Control (18 tasks, 500k steps), Visual Control (20 tasks, 1M
  steps), BSuite (23 environments, 468 configs), Minecraft. Dreamer beats
  the tuned expert baseline or PPO on each, and on DMLab exceeds IMPALA and
  R2D2+ at 1B steps using 100M ([Fig. 1, Results](https://arxiv.org/abs/2301.04104)).
- Minecraft Diamond: all 10 seeds collected a diamond within 100M steps
  using 1 GPU for 9 days and no human data; IMPALA, Rainbow and PPO reach
  the iron pickaxe at most. VPT needed 720 GPUs for 9 days plus human video
  ([Fig. 5, Previous work](https://arxiv.org/abs/2301.04104)).
- Ablations on 14 tasks: every normalization technique helps on average, the KL
  objective most, then return normalization and two-hot regression. Removing
  reconstruction gradients hurts far more than removing reward and value
  gradients ([Fig. 6a, 6b](https://arxiv.org/abs/2301.04104)).
- Scaling: performance rises monotonically from 12M to 400M and with replay
  ratio; larger models need fewer environment steps ([Fig. 6c, 6d](https://arxiv.org/abs/2301.04104)).
- No physical robot experiments; locomotion and manipulation are DM Control.

## What it changes in practice

For sim-first RL with a new task and no time to tune, DreamerV3 is the
strongest "one config" default, and the 12M model runs on modest hardware.
The normalization tricks (symlog, two-hot value heads, percentile return
scaling) are portable to any actor-critic and are the part to steal if you
stay model-free. The finding that reconstruction, not reward, carries most
of the learning signal argues for pretraining world models on unlabelled robot
video.

## Known limitations and follow-ups

- Wall-clock and sample budgets are large by robot standards: 100M to 200M
  steps on most suites. The paper reports env steps, not hours per run.
- ProcGen ran with a single seed ([Seeds and error bars](https://arxiv.org/abs/2301.04104)).
- Uniform replay only; prioritized replay helped but was left out ([Experience replay](https://arxiv.org/abs/2301.04104)).

## Open questions

- Whether fixed hyperparameters hold for real-robot data rates (a few
  thousand transitions per hour) with a high replay ratio, where the world
  model must not overfit the tiny buffer.
- How the world model handles force and torque inputs that jump orders of
  magnitude at contact; symlog helps but is untested here on contact signals.

## Sources

- [Hafner, Pasukonis, Ba, Lillicrap. Mastering Diverse Domains through World Models. arXiv 2301.04104 (v2, Apr 2024)](https://arxiv.org/abs/2301.04104)
- [Reference implementation](https://github.com/danijar/dreamerv3)
