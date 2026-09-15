---
title: "RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control"
date: 2026-09-05
tags: [paper, vla, vlm, imitation-learning, google, mobile-manipulation]
status: draft
source: https://arxiv.org/abs/2307.15818
---

# RT-2 (Brohan et al., 2023)

## Problem

RT-1 recombined seen verbs and nouns but knew nothing outside the robot
data. Web-scale VLMs know what a "rock" or "the number 3" is. The paper asks
whether a VLM can be fine-tuned to emit low-level actions directly, so that
semantic knowledge lands in closed-loop control rather than a separate planner.

## Core idea

Write the RT-1 action (8 integers in 0..255) as a text string, e.g.
"1 128 91 241 5 101 127", and fine-tune an existing VLM (PaLI-X or PaLM-E) to
answer "Q: what action should the robot take to [instruction]? A:" with that
string. Co-fine-tune on the original web data at the same time so the model
does not forget what it knew. The paper coins the term VLA for this.

## Method details that matter for reimplementation

- Backbones: RT-2-PaLI-X at 5B and 55B (ViT-22B vision encoder, 32B-parameter
  UL2-style encoder-decoder, 50 layers) and RT-2-PaLM-E at 12B (decoder-only
  PaLM with ViT-4B). A PaLI-3B variant (ViT-G/14 2B + UL2-3B) was used only
  for the Language-Table sim benchmark (Appendix D).
- Action tokenization: 7 continuous dimensions (6-DoF end-effector delta plus
  gripper) each uniformly binned into 256, plus a discrete terminate flag.
  PaLI-X has unique tokens for integers up to 1000, so bins map to number
  tokens. PaLM-E has no such tokens, so the 256 least-used vocabulary tokens
  are overwritten. Output vocabulary is constrained to valid action tokens
  when the prompt is a robot task (Sec. 3.2).
- Data mixture: the RT-1 robot dataset (13 robots, 17 months) plus the VLM's
  own web mixture (WebLI filtered to about 1B examples, VQA, captioning).
  Robot data is weighted to about 50% of each batch for PaLI-X and about 66%
  for PaLM-E (Appendix B).
- Training compute (Appendix E): PaLI-X-55B, lr 1e-3, batch 2048, 80k steps.
  PaLI-X-5B, same lr and batch, 270k steps. PaLM-E-12B, lr 4e-4, batch 512,
  1M steps. Accelerator type and wall-clock are not stated.
- Inference: multi-TPU cloud service queried over the network. 55B runs at
  1 to 3 Hz, 5B at about 5 Hz (Sec. 3.3). No on-robot GPU numbers.
- Chain-of-thought variant: PaLM-E fine-tuned a few hundred steps with a
  "Plan: ..." step before the action string (Sec. 4.4). Qualitative only.

## Result that matters

About 6000 real-robot trajectories on the 7-DoF Everyday Robots mobile
manipulator. Generalization (Table 6) used over 280 tasks; each instruction
ran 1 to 5 times. Emergent-skill tasks (Table 7) ran 5 times each, A/B
against baselines in identical conditions.

| Model | Seen | Unseen avg | Emergent avg |
|-------|------|-----------|--------------|
| RT-1 (35M) | 92 | 32 | 17 |
| MOO | 75 | 35 | not run |
| RT-2-PaLI-X-55B | 91 | 62 | 60 |
| RT-2-PaLM-E-12B | 93 | 62 | 40 |

Unseen splits into objects, backgrounds, environments, each easy and hard;
the two RT-2 models trade wins across splits and tie on average. Emergent
tasks cover symbol understanding ("move apple to 3"), reasoning ("move apple
to cup with same color") and person recognition; none appear in the robot
data. PaLM-E won on math (35 vs 25), attributed to its pretraining mixture.

Ablations (Table 8, PaLI-X): 5B from scratch 9% unseen average; 5B
fine-tune only 42%; 5B co-fine-tune 44%; 55B fine-tune 52%; 55B co-fine-tune
63%. Scale and co-fine-tuning both help.

Language-Table sim (Table 3): RT-2-PaLI-3B 90 +/- 10 vs RT-1 74 +/- 13 and
LAVA 77 +/- 4.

## What it changes in practice

- Actions as text tokens means zero new parameters; any VLM with a
  fine-tuning API is a VLA candidate. OpenVLA reproduced this on open weights.
- Co-fine-tuning with web data is the recipe detail that preserves semantic
  generalization; robot-only fine-tuning loses 11 points at 55B.
- No weights, code, or API were released. Backbones are Google-internal.
  Reproduction has to go through OpenVLA or a comparable open VLM.
- 1 to 3 Hz from a cloud TPU service is the deployment reality at 55B; the
  paper flags this as a bottleneck for high-frequency control.

## Known limitations and follow-ups

- No new motions emerge from web pretraining; physical skills stay inside
  the robot data distribution (Sec. 5, Appendix G).
- Compute cost rules out on-robot inference at this size; quantization and
  distillation are named as future work.
- RT-2-X (Open X-Embodiment entry) retrains the 55B PaLI-X variant on 9
  embodiments.

## Open questions

- With 1 to 5 trials per instruction in Table 6, the "hard" cells rest on
  very few rollouts; intervals are not reported.
- Is the PaLM-E-12B vs PaLI-X-55B parity on unseen tasks a real
  architecture effect or a pretraining-data effect? The paper notes PaLM-E's
  pretraining included robot images (Table 6 footnote).
- How much of the emergent-skill gain survives at 5B, the size a lab could
  serve?

## Sources

- Paper: https://arxiv.org/abs/2307.15818 (arXiv HTML read 2026-09-05)
- Project page: https://robotics-transformer2.github.io
