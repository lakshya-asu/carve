---
title: "Data Scaling Laws in Imitation Learning for Robotic Manipulation"
date: 2026-09-05
tags: [paper, imitation-learning, data-collection, scaling, generalization, umi, diffusion]
status: draft
source: https://arxiv.org/abs/2410.18647
---

# Data Scaling Laws in Imitation Learning (Lin, Hu, Sheng, Wen, You, Gao)

Read from arXiv v4 (26 Jun 2026). Tsinghua, Shanghai Qi Zhi, Shanghai AI Lab. An empirical
study of what to scale in single-task BC data: more environments, more objects, or more
demos per pair. 40k+ UMI demos and 15k+ real rollouts.

## Problem

Single-task BC policies trained in one room on one object rarely work in a new room on a new
object. The field has assumed more data fixes this but has not measured which axis of data
matters. The paper asks: for a fixed task, how does zero-shot generalisation to unseen
environments and unseen same-category objects scale with the number of training environments
M, objects N, and demos per pair K?

## Core idea

Hold the learner fixed (Diffusion Policy with a fine-tuned DINOv2 ViT-L/14 encoder), collect
with UMI across 32 environments and 32 objects, and sweep M, N, K on a 2^m grid. Measure a
tester-assigned normalised score on unseen environments and objects under a blinded,
shuffled protocol. Fit log(1 - score) against log(M), log(N), or log(M x N pairs) and read
off whether it is a power law.

## Method details that matter for reimplementation

- Data: UMI hand-held grippers without side mirrors (Appendix F). About 90% of demos survive
  SLAM filtering. Four grippers, four collectors.
- Policy (Appendix C, Table 3): CNN U-Net Diffusion Policy, DDIM 16 inference steps, action
  horizon 16, 224x224 observations, environment frequency 5 Hz, AdamW betas 0.95/0.999,
  diffusion lr 3e-4, encoder lr 3e-5, cosine decay, batch 256, BF16. ACT-style temporal
  ensemble with 8 steps and adaptation rate -0.01 to remove chunk-boundary jerk.
- Observation horizon 2 by default; 3 for Pour Water and Unplug Charger, with the extra
  frame 0.25 s or 0.5 s back so the policy can tell "about to pour" from "finished pouring".
- Model: encoder plus U-Net exceed 396M parameters. Epochs scaled with dataset size so every
  policy converges: 800 epochs (5.3e4 steps) for the smallest, 75 epochs (5e5 steps, 75 h on
  8x A800) for the largest. Final checkpoint used. Larger datasets are supersets of smaller
  ones.
- Scoring: each task has 2 to 3 steps, each scored 0 to 3 by the tester; normalised score =
  total / (3 x steps). Policies from one sweep are evaluated in the same session, shuffled,
  at identical initial states. Scores from different sessions are not comparable (Appendix
  E.2).

## Result that matters

Evaluation unit throughout: 8 unseen environments and/or objects, 5 trials each, 40 trials
per policy, normalised score with 95% CI in the figures.

- Object generalisation (Fig. 2, 21 policies per task): with 8 training objects both tasks
  exceed 0.8; with 32 objects above 0.9. With 32 objects, 12.5% of demos per object matches
  100%.
- Environment generalisation (Fig. 3): steady gains with more environments, lower slope than
  objects; 50% and 100% demo fractions overlap.
- Power law (Fig. 5): 1 - score versus objects, environments, or pairs fits a line in
  log-log with high Pearson r; exponents are in the figure legend and not reproduced here
  (unverified in text). Demos alone at fixed M, N show no clear power law (r = -0.62 and
  -0.79, Fig. 7 left). Extrapolation: 0.99 score on Mouse Arrangement would need 1,191
  pairs.
- Demo threshold (Fig. 7): with 8, 16, 32 pairs performance plateaus at 400, 800, 1600 total
  demos, so about 50 per pair. With 16 environments x 4 objects, plateau at 800 of 6400.
- Recipe verified on two new tasks (Table 1; 32 pairs x 50 demos, collected by 4 people in
  one afternoon): Fold Towels score 0.95 +/- 0.062, success 87.5 +/- 17.1%; Unplug Charger
  0.887 +/- 0.14, success 90.0 +/- 14.1%. Pour Water 85.0 +/- 19.4%; Mouse Arrangement 92.5
  +/- 9.7%. Standard deviations are across the 8 environments.
- Model side (Table 2, Pour Water, 32 pairs, 50% demos): DINOv2 ViT-L/14 full fine-tune
  0.90; from scratch 0.03; frozen 0.00; LoRA rank 8 0.72. ViT-S 0.66, ViT-B 0.81, ViT-L
  0.90. U-Net small/base/large 0.88/0.90/0.83.
- Validation MSE is unreliable as a proxy: r = -0.98 in one sweep but -0.73 in another, and
  LoRA had lower MSE than full fine-tuning while scoring worse (Appendix E.1).

## What it changes in practice

- Data plan for a new single-task deployment: about 32 distinct environment-object pairs,
  one object per environment, roughly 50 demos each, so about 1,600 demos. The paper got
  around 90% success on unseen sites with that budget.
- Spend collection time moving between sites, not on more repetitions at one site. Past 16
  environments, extra objects per environment add nothing.
- Fine-tune the whole DINOv2 encoder; frozen features and LoRA both lose. Scale the encoder,
  not the U-Net.
- Do not select checkpoints or compare policies on validation MSE.
- UMI field notes (Appendix B.2): randomise the hand-held start pose, check scene texture in
  Pangolin before collecting, avoid large occluding objects like drawers, standardise
  collector behaviour to limit multimodality.

## Known limitations and follow-ups

- Single-task only, four tasks, one learner, one embodiment. Task-level generalisation is
  explicitly out of scope.
- Power-law fits use 6 points each; the authors decline a three-parameter fit with an
  irreducible-error term for that reason.
- Tasks are quasi-static at 5 Hz. Dexterous or dynamic tasks may need more than 50 demos per
  pair (authors' own caveat).

## Open questions

- Does the 32-pair, 50-demo threshold hold for ACT or VQ-BeT, or is it a property of
  Diffusion Policy with a large encoder?
- Environments had the lower slope. Which factors (lighting, clutter, table texture) carry it?

## Sources

- Paper: https://arxiv.org/abs/2410.18647 (v4, 26 Jun 2026). Sec. 3 to 6; Tables 1 to 3;
  Fig. 2 to 7; Appendix B.2, C, E, F.
- Project page, code, data: https://data-scaling-laws.github.io/
