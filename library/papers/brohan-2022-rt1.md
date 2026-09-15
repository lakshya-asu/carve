---
title: "RT-1: Robotics Transformer for Real-World Control at Scale"
date: 2026-09-05
tags: [paper, vla, imitation-learning, transformer, google, mobile-manipulation]
status: draft
source: https://arxiv.org/abs/2212.06817
---

# RT-1 (Brohan et al., 2022)

## Problem

Multi-task imitation learning had reached about 100 tasks (BC-Z) or one real
task (Gato). The paper asks whether one Transformer policy can absorb a large,
broad real-robot dataset, run at a control rate a real arm needs, and
generalize to instructions, objects and rooms it never saw.

## Core idea

Treat vision-language-to-action as sequence modelling, but keep the model small
enough for 3 Hz closed-loop control: compress each image into 8 tokens before
the Transformer, discretize every action dimension into 256 bins, and train
with cross-entropy on 130k human demonstrations spanning 744 instructions.

## Method details that matter for reimplementation

- Backbone: ImageNet-pretrained EfficientNet-B3 on 300x300 images, output
  9x9x512 flattened to 81 tokens. The language instruction is embedded with
  Universal Sentence Encoder and injected through FiLM layers inside the
  EfficientNet. FiLM dense layers are zero-initialized so the pretrained
  network starts as identity (Sec. 5.1). Tokenizer is 16M parameters.
- TokenLearner reduces 81 tokens to 8 per image. History of 6 images gives
  48 tokens into a decoder-only Transformer with 8 self-attention layers,
  19M parameters. Total model 35M parameters.
- Action head: 11 dimensions (arm x, y, z, roll, pitch, yaw, gripper; base
  x, y, yaw; a 3-way mode switch arm/base/terminate), each discretized into
  256 uniform bins within per-dimension bounds. Loss is categorical
  cross-entropy with causal masking. Actions are not decoded
  autoregressively; the ablation found autoregressive actions gave no gain and
  slowed inference by more than 2x (Appendix D.4).
- Inference: token computation is cached across the overlapping 6-frame
  window. TokenLearner and caching give 2.4x and 1.7x speedups respectively.
  Network inference is 15 ms; the system waits a fixed 280 ms after image
  capture before applying an action to avoid jitter (Appendix C.1).
- Data: about 130k episodes, 13 Everyday Robots mobile manipulators, 17
  months, teleoperated with two VR remotes in "robot classroom" kitchen
  mockups. 744 instructions across 12 skills; "move X near Y" alone is 337.
  Training compute (batch size, steps, accelerator) is not stated.

## Result that matters

All numbers are real-robot success rates on Everyday Robots mobile
manipulators, from Table 2 and the 3000-trial evaluation described in Sec. 6.
Seen tasks cover more than 200 instructions; unseen is 21 instructions;
distractors is 30 task runs; backgrounds is 22 task runs. Per-instruction
trial counts are not given.

| Model | Seen | Unseen | Distractors | Backgrounds |
|-------|------|--------|-------------|-------------|
| Gato (37M, retrained on RT-1 data) | 65 | 52 | 43 | 35 |
| BC-Z | 72 | 19 | 47 | 41 |
| RT-1 | 97 | 76 | 83 | 59 |

Data ablation (Table 7): removing 25% of tasks while keeping 97% of the data
hurt generalization as much as cutting the dataset by 49%.

Heterogeneous data (Tables 4 and 5): adding sim data raised real success on
sim-only objects from 23% to 87% with no loss on real objects. Adding 209k
Kuka QT-Opt bin-picking episodes raised Everyday Robots bin-picking from 22%
to 39% at a 2-point cost on the standard eval.

Long horizon (Table 6): inside SayCan, RT-1 executed 67% of 15 long-horizon
instructions (about 10 steps each) in both Kitchen1 and Kitchen2; BC-Z fell
to 13% and Gato to 0% in Kitchen2.

## What it changes in practice

- Discretized actions with cross-entropy beat a Gaussian MSE head by 29
  points on seen tasks and 46 on distractors (Table 13). This is the design
  choice most later VLAs inherit.
- ImageNet pretraining of the vision tower is worth 33 points on unseen tasks
  (Table 13). Do not train the encoder from scratch on robot data alone.
- The latency budget drove the architecture: under 100 ms for the network to
  hit 3 Hz. Measure end-to-end latency before choosing a model size.
- Code released at github.com/google-research/robotics_transformer (stated in
  the paper). Licence, checkpoint release and on-robot inference hardware are
  not stated (unverified). A retrained RT-1-X checkpoint later shipped with
  Open X-Embodiment (see that entry).

## Known limitations and follow-ups

- Pure imitation: cannot exceed the demonstrators. Generalization is limited
  to recombining seen verbs and nouns; no new motions appear (Sec. 7).
- Skills are coarse pick, place, open, close, knock; nothing dexterous.
- Successors: RT-2 (VLM backbone, same action tokens), RT-1-X and RT-2-X
  (cross-embodiment retraining on Open X-Embodiment).

## Open questions

- No per-instruction trial counts or confidence intervals; the 97% seen-task
  number is a skill-weighted average (Appendix D.1).
- Fixed 280 ms action delay: does the policy implicitly learn to compensate?
- Would diversity-over-quantity hold with a larger model, or is it an
  artifact of a 35M-parameter capacity ceiling?

## Sources

- Paper: https://arxiv.org/abs/2212.06817 (arXiv HTML read 2026-09-05)
- Project page: https://robotics-transformer1.github.io
- Code: https://github.com/google-research/robotics_transformer
