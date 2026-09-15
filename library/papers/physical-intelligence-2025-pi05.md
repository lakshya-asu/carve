---
title: "π0.5: a Vision-Language-Action Model with Open-World Generalization"
date: 2026-09-05
tags: [paper, vla, flow-matching, co-training, mobile-manipulation, hierarchical, physical-intelligence]
status: draft
source: https://arxiv.org/abs/2504.16054
---

# pi0.5 (Physical Intelligence, 2025)

## Problem

pi0 did long dexterous tasks in the environments it was trained in. The
paper asks whether a VLA can clean a kitchen or bedroom in an unseen home
given only about 400 hours of mobile-manipulator data from about 100 homes,
betting that co-training on other robots, environments, web data and subtask
labels closes the gap.

## Core idea

One transformer, two training phases, two inference levels. Pretrain as a
plain autoregressive VLM where actions are FAST-compressed text tokens next
to captioning, VQA, boxes and subtask labels. Post-train by adding a
pi0-style flow-matching action expert, keeping the token losses. At run time
the model emits a subtask in text, then a 50-step action chunk conditioned
on it.

## Method details that matter for reimplementation

- Architecture (Appendix A-E): PaliGemma backbone as in pi0 (width 2048,
  depth 18, mlp 16384); action expert width 1024, mlp 4096, 300M, horizon
  50. State is discretized into text tokens. Flow timestep enters the expert
  via its own MLP and adaptive RMSNorm per layer. Full prefix mask over
  images, prompt and state; FAST action tokens attend to the prefix and
  causally to each other; flow tokens never attend to FAST tokens.
- Loss (Eq. 1): cross-entropy on text tokens (FAST action tokens included)
  plus alpha times the flow-matching squared error; alpha = 0 in
  pretraining, 10 in post-training.
- Pretraining: 280k steps, discrete tokens only. Data: MM (about 400 h of
  mobile manipulators in about 100 homes), ME (static single and dual arms
  in many homes), CE (lab cross-embodiment data plus OXE; a superset of the
  pi0 mix), HL (manual subtask labels and bounding boxes), WD (CapsFusion,
  COCO, Cambrian-7M, PixMo, VQAv2, indoor localization). Control mode is
  declared in the prompt. Actions normalized to [-1, 1] by 1st and 99th
  percentile per dataset, zero-padded to the largest action space.
- Post-training: 80k steps, action expert from random init; MM and ME
  filtered to successful short episodes; WD and multi-environment HL kept;
  CE dropped. Adds VI (verbal instruction) data, an expert driving the robot
  live by typing subtask commands, about 11% of high-level MM examples. Batch
  size, learning rate and accelerators are not stated.
- Robots: two mobile manipulator types, two 6-DoF arms, parallel grippers,
  holonomic base, torso lift, four cameras (front, back, two wrist), 18 or
  19-D state and action. 50 Hz targets tracked by PD controllers, no planner
  or collision check. Inference is text then 10 denoising steps; timing not
  reported.

## Result that matters

All evaluations are in environments absent from training; rubric scores
(Appendix A-B) approximate percent of steps completed; 10 trials per policy
and task; results are figures only. Real homes (Fig. 7): three unseen homes,
"items in drawer", "laundry basket", "dishes in sink", both robot types.
pi0.5 succeeded consistently; mock-home numbers were representative.

Scaling with environments (Fig. 8): post-training on MM data from 3, 12, 22,
53, 82 and 104 locations at a fixed 40k steps. Mock-home performance on four
tasks rose with location count; the 104-location model matched a control
trained on the test homes. Two baselines without co-training (one on
test-home data, one on the 104 locations) were far worse. Language following
(Fig. 9) rose likewise on seen and unseen object categories.

Mixture ablations (Figs. 10, 11): removing ME or CE cut mock-home
performance sharply, both more so. Removing web data did not change the four
tasks significantly but hurt OOD-object language following and high-level
inference.

Versus pi0 (Fig. 12): pi0.5 beat pi0 and a pi0-FAST+Flow variant (hybrid
training, action data only) on the same robot data, even with pi0 at 300k
steps. High-level inference (Fig. 13): full pi0.5 best, above a human oracle
high-level policy; implicit HL (subtask data in training, skipped at run
time) second; no VI, no WD and no HL each cost; zero-shot GPT-4 was worst.

## What it changes in practice

- FAST tokens for pretraining, flow expert for deployment, is the
  compute-efficient recipe; Fig. 12 supports it against pure flow training.
- Subtask data helps even if the high-level step is skipped at inference;
  subtask annotation and verbal-instruction demos are cheap next to teleop.
- Environment count, not hours, bought generalization.
- No weights with the paper. pi0.5 checkpoints later appeared in openpi
  under Apache 2.0 (from the repository, not the paper; unverified).
  Inference hardware is not stated.

## Known limitations and follow-ups

- Failures on unfamiliar drawer handles and stiff cabinets; occlusion by the
  arm; high-level inference sometimes loops (open, close, open a drawer).
  Simple prompts, short context, no memory across rooms.

## Open questions

- Mock-home to real-home gap per task is not tabulated. Which web subset
  carries the OOD-object effect?

## Sources

- Paper: https://arxiv.org/abs/2504.16054 (arXiv HTML read 2026-09-05)
- Blog: https://www.pi.website/blog/pi05
- Predecessor entry: [pi0](black-2024-pi0.md)
- Code and weights, post-publication: https://github.com/Physical-Intelligence/openpi (unverified against paper)
