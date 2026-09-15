---
title: "Precise and Dexterous Robotic Manipulation via Human-in-the-Loop Reinforcement Learning (HIL-SERL)"
date: 2026-09-05
tags: [paper, reinforcement-learning, real-world-rl, manipulation, human-in-the-loop, bimanual, rlpd]
status: draft
source: https://arxiv.org/abs/2410.21845
---

# HIL-SERL (Luo, Xu, Wu, Levine 2024)

## Problem

SERL showed real-world RL working on short single-arm tasks. Harder tasks
(dual-arm assembly, deformable belts, dynamic whipping) have larger state and
action spaces and longer horizons, and the sample complexity of exploring them
from 20 demonstrations alone puts real-world training out of reach
([Luo et al. 2024, Sec. 3.4](https://arxiv.org/abs/2410.21845)).

## Core idea

Keep the SERL stack ([luo-2024-serl.md](luo-2024-serl.md): RLPD, pretrained
ResNet-10, classifier reward, relative frames, limited impedance) and add a human who can grab a
SpaceMouse at any timestep during training. Intervention actions go into both
the demo buffer and the RL buffer; the policy's own transitions around the
intervention go only into the RL buffer. Interventions are frequent early and
taper to zero. Gripper commands get a separate discrete critic trained with
DQN ([Sec. 3.2 to 3.4, Fig. 2](https://arxiv.org/abs/2410.21845)).

## Method details that matter for reimplementation

- Two replay buffers, sampled 50/50 per batch: a demo buffer holding 20 to 30
  teleoperated episodes plus all interventions, and an RL buffer holding all
  on-policy transitions plus interventions ([Sec. 3.2, 3.4](https://arxiv.org/abs/2410.21845)).
- Reward classifier: ResNet-10 plus 2-layer MLP, cross-entropy, Adam 3e-4,
  100 iterations. Data: about 200 positives and 1000 negatives labelled by a
  SpaceMouse button during teleop (roughly 10 trajectories, about 5 minutes),
  plus extra false-positive and false-negative examples where needed.
  Reported classifier accuracy 95 to 99 % per task ([Sec. 3.5, Appendix B, Tables 2 to 12](https://arxiv.org/abs/2410.21845)).
- Images cropped to the task region and resized to 128 x 128, random-crop
  augmentation; proprio encoder 64 units; policy MLP 256 x 256; discount 0.96
  to 0.985; Adam 3e-4; 10 Hz environment step; 100 to 200 step episodes
  ([Appendix A tables](https://arxiv.org/abs/2410.21845)).
- Gripper: a second MDP over discrete actions {open, close, stay} (9
  combinations for two grippers), critic trained with the DQN target and a
  Polyak-averaged target network; at inference take argmax and concatenate
  with the continuous twist. A small penalty on gripper actions discourages
  needless toggling ([Sec. 3.3, Eq. 3](https://arxiv.org/abs/2410.21845)).
- Controller: 1 kHz impedance with reference limiting for contact tasks;
  for Jenga whipping and pan flipping the policy outputs a 3-DoF feedforward
  wrench in the end-effector frame, converted to torques by the Jacobian
  transpose, no closed-loop acceleration control ([Appendix D.2](https://arxiv.org/abs/2410.21845)).
- Intervention discipline: avoid long, sparse interventions that carry the
  episode to success early in training; they inflate the value estimate and
  destabilize training. Short targeted corrections work better ([Sec. 3.5](https://arxiv.org/abs/2410.21845)).
- Jenga whipping uses 30 offline demos and a human end-of-episode label
  instead of live corrections; learning rate decays 3e-4 to 3e-5 at 70 %
  success ([Sec. 4.2, Table 11](https://arxiv.org/abs/2410.21845)).

## Result that matters (with n and hardware)

Training on a single RTX 4090, all evaluations over 100 trials per task except
the chained IKEA assembly (10 trials). Baseline is HG-DAgger with the same
number of episodes and interventions ([Table 1a](https://arxiv.org/abs/2410.21845)):

| Task | Train time (h) | HG-DAgger success | HIL-SERL success | Cycle time BC vs RL (s) |
|---|---|---|---|---|
| RAM insertion | 1.5 | 29 % | 100 % | 8.3 vs 4.8 |
| SSD assembly | 1 | 79 % | 100 % | 6.7 vs 3.3 |
| USB grasp-insertion | 2.5 | 26 % | 100 % | 13.4 vs 6.7 |
| Car dashboard (dual arm) | 2 | 41 % | 100 % | 20.3 vs 8.8 |
| Timing belt (dual arm) | 6 | 2 % | 100 % | 9.1 vs 7.2 |
| Jenga whipping | 1.25 | 8 % (flat BC, 50 demos) | 100 % | n/a |
| Object flipping | 1 | 46 % (flat BC, 200 demos) | 100 % | 3.9 vs 3.8 |
| Average over 13 rows | | 49.7 % | 100 % | 9.6 vs 5.4 |

Ablations on RAM insertion, dashboard and flipping ([Table 1b](https://arxiv.org/abs/2410.21845)):
RL from scratch scored 0 % on all three; SERL-style training with 200 demos
and no interventions scored 48 %, 0 % and 100 %; Diffusion Policy with 200
demos scored 27 %, 18 % (28 % in the text) and 56 %; IBRL 75 %, 0 %, 95 %; Residual RL 0 %, 0 %, 97 %.
The arm model is not named in the paper text; figures and the released code
point to Franka arms (unverified).

## What it changes in practice

The recipe for a new precision skill is now: 5 minutes of classifier data,
20 to 30 demos, then 1 to 2.5 hours of supervised online training with an
operator holding a SpaceMouse. Corrections, not more demos, are what make the
dual-arm tasks train at all. The learning curves in Fig. 5 give a stopping
rule: stop when intervention rate reaches zero and cycle time plateaus.

## Known limitations and follow-ups

- No claim about long-horizon tasks; the authors expect sample complexity to
  bite and suggest pretraining or VLM task segmentation ([Sec. 6](https://arxiv.org/abs/2410.21845)).
- Little randomization and no unstructured-environment testing; start-pose
  ranges are 2 to 8 cm and 1 to 10 degrees ([Sec. 6, Appendix A](https://arxiv.org/abs/2410.21845)).
- Timing belt took 6 hours, outside the "1 to 2.5 hours" headline.
- A LeRobot port exists ([docs](https://huggingface.co/docs/lerobot/hilserl)); parity with the paper is unverified.

## Open questions

- How operator skill affects the result. One lab's operators produced these
  numbers; the paper does not measure variance across operators.
- How the value-overestimation failure from long interventions shows up in
  logs, so an operator can catch it early.

## Sources

- [Luo, Xu, Wu, Levine. HIL-SERL. arXiv 2410.21845](https://arxiv.org/abs/2410.21845)
- [Project page, videos, code](https://hil-serl.github.io/)
