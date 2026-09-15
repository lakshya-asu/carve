---
title: "Efficient Online Reinforcement Learning with Offline Data (RLPD)"
date: 2026-09-05
tags: [paper, reinforcement-learning, offline-to-online, off-policy, sac, sample-efficiency]
status: draft
source: https://arxiv.org/abs/2302.02948
---

# RLPD (Ball, Smith, Kostrikov, Levine 2023)

## Problem

Online RL with a pile of prior data (demos or old rollouts) usually meant
either offline-RL pretraining followed by fine-tuning, with extra
hyperparameters and a performance dip, or explicit constraints that keep the
policy near the data and cap improvement. The question the paper asks is
whether plain off-policy RL can use offline data directly, without pretraining
or imitation terms ([Ball et al. 2023, Sec. 1](https://arxiv.org/abs/2302.02948)).

## Core idea

Yes, if three things are in place: sample every batch half from the offline
buffer and half from the online buffer ("symmetric sampling"), put LayerNorm in
the critic so Q-values cannot extrapolate without bound on unseen actions, and
use a large critic ensemble with a high update-to-data ratio. Naive SAC with
the same offline data diverges; the three changes together beat prior
offline-to-online methods by up to 2.5x with no offline phase
([Sec. 4, Fig. 1, Fig. 2](https://arxiv.org/abs/2302.02948)).

## Method details that matter for reimplementation

- Base algorithm is SAC. Algorithm 1 in the paper is the reference; the
  green-highlighted lines (LayerNorm, ensemble size E, gradient steps G,
  symmetric batch construction) are the method ([Sec. 4.5](https://arxiv.org/abs/2302.02948)).
- Symmetric sampling: batch of N is N/2 from replay R plus N/2 from offline D.
  A 25/75 or 75/25 split changes little; 50/50 is the recommended compromise
  between variance and speed. Seeding the replay buffer with offline data
  instead of sampling symmetrically limits asymptotic improvement
  ([Sec. 5.1, Fig. 10 to 12](https://arxiv.org/abs/2302.02948)).
- LayerNorm argument: with a LayerNorm before the last linear layer,
  |Q(s,a)| <= ||w||, so OOD actions cannot produce values far above those in
  the data ([Sec. 4.2](https://arxiv.org/abs/2302.02948)). On the 22-trajectory
  expert-only Adroit subset, removing LayerNorm collapses learning entirely
  ([Fig. 7](https://arxiv.org/abs/2302.02948)).
- Ensemble: E = 10 critics with random subset distillation (REDQ-style),
  targets computed from a random subset of Z in {1, 2} critics. Ensembling
  beat dropout and weight decay as critic regularizer, especially on sparse
  reward ([Sec. 4.3, Fig. 9](https://arxiv.org/abs/2302.02948)).
- Default hyperparameters (Table 1): batch 128 online + 128 offline, gamma
  0.99, Adam 3e-4, critic EMA 0.005, UTD G = 20 for state-based tasks, width
  256, initial entropy temperature 1.0, target entropy -dim(A)/2. Pixels: action
  repeat 2, 64 x 64 observations, random shift of 4 pixels
  ([Appendix B.2](https://arxiv.org/abs/2302.02948)).
- Environment-specific knobs, to be ablated in this order when a new domain
  fails: clipped double Q (subset Z = 2) versus single critic target (Z = 1);
  entropy term in the backup on or off; 2 versus 3 MLP layers. Table 2 gives
  the choices per suite: locomotion CDQ on, entropy on, 2 layers; AntMaze CDQ
  off, entropy off, 3 layers; Adroit CDQ on, entropy off, 3 layers; DMC
  pixels CDQ off, entropy off, 2 layers ([Sec. 4.4, 4.5, Appendix B.2](https://arxiv.org/abs/2302.02948)).

## Result that matters (with n and hardware)

All results are simulation, 10 seeds, mean and one standard deviation, 100
evaluation trials per evaluation point ([Sec. 5, Appendix B.1](https://arxiv.org/abs/2302.02948)).
Compute hardware is not stated in the paper text beyond use of the Berkeley
Savio cluster (unverified per-run GPU).

- 21 state-based tasks: 3 Sparse Adroit (pen, door, relocate; metric is
  fraction of timesteps solved, so it rewards speed), 6 D4RL AntMaze, 12 D4RL
  locomotion. RLPD matches or exceeds IQL+finetuning (Adroit, AntMaze) and
  Off2On (locomotion) with no pretraining, reaching prior final scores in
  about 10k online steps. Sparse Adroit Door improves 2.5x over the best
  prior result. AntMaze solved on all six tasks within 300k steps, under a
  third of prior step budgets ([Fig. 4](https://arxiv.org/abs/2302.02948)).
- Pixels: V-D4RL walker, cheetah, humanoid (medium and expert data, "10 % DMC"
  budget). RLPD beats the same architecture without offline data and DrQ-v2;
  UTD 10 on cheetah-run-expert gives a large further gain ([Fig. 5, 6](https://arxiv.org/abs/2302.02948)).
- No real-robot experiments in this paper. The real-robot evidence for RLPD is
  downstream: SERL and HIL-SERL use it as the learner
  ([luo-2024-serl.md](luo-2024-serl.md), [luo-2024-hil-serl.md](luo-2024-hil-serl.md)).

## What it changes in practice

When you have demos and can run the robot, skip the offline pretraining stage.
Start online, sample 50/50, keep LayerNorm in the critic, use 10 critics and a
UTD of 10 to 20, and only then tune CDQ, entropy backup and depth. This is the
learner inside SERL, so anything built on that stack inherits these choices.
The LayerNorm result also explains a class of "Q-values exploded" failures
seen in offline-seeded SAC runs.

## Known limitations and follow-ups

- High UTD with 10 critics costs roughly 20 gradient steps per environment
  step; the paper says overhead is negligible relative to pure online RL at
  the same UTD, not relative to UTD 1 ([Sec. 6](https://arxiv.org/abs/2302.02948)).
- The environment-specific choices are empirical; the paper does not give a
  rule to predict them from task properties ([Sec. 4.4](https://arxiv.org/abs/2302.02948)).
- Benchmarks are state-based or low-resolution pixels at 64 x 64; nothing on
  128 x 128 wrist cameras or force inputs.

## Open questions

- Whether 50/50 sampling stays right when the offline buffer is thousands of
  hours of fleet data rather than 20 demos.

## Sources

- [Ball, Smith, Kostrikov, Levine. Efficient Online RL with Offline Data. ICML 2023, arXiv 2302.02948](https://arxiv.org/abs/2302.02948)
- [Code (JAX)](https://github.com/ikostrikov/rlpd)
