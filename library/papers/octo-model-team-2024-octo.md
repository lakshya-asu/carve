---
title: "Octo: An Open-Source Generalist Robot Policy"
date: 2026-09-05
tags: [paper, generalist-policy, diffusion, cross-embodiment, open-weights, finetuning]
status: draft
source: https://arxiv.org/abs/2405.12213
---

# Octo (Octo Model Team, 2024)

## Problem

RT-X showed cross-embodiment pretraining works, but the useful model
(RT-2-X) was closed and both RT-X models lock in one camera and one action
space. The paper wants a pretrained policy anyone can download, that accepts
whatever cameras and task spec a lab has, and that fine-tunes to a new robot,
sensor or action space on one consumer GPU.

## Core idea

A transformer-first policy: shallow CNN patch tokenizers, a ViT-sized
backbone with block-wise attention masks, learned readout tokens, and a small
diffusion head predicting an action chunk. Inputs and outputs are token
blocks, so new encoders or action heads can be added at fine-tuning time
without touching pretrained weights. Trained on 800k OXE episodes.

## Method details that matter for reimplementation

- Tokenizers: frozen T5-base (111M) gives 16 language tokens; a shallow conv
  stack then 16x16 patches gives 256 tokens for the 256x256 third-person
  camera and 64 for the 128x128 wrist camera. 16x16 beat 32x32 on grasping.
- Backbone: Octo-Small 12 layers, width 384, 6 heads, 27M parameters;
  Octo-Base 12 layers, width 768, 12 heads, 93M. Observation tokens attend
  causally to earlier timesteps and to task tokens; readout tokens attend to
  everything before them and are attended by nothing (Sec. III-A).
- Action head: 3-layer MLP, hidden 256, residual, layer norm, on the readout
  embedding. DDPM objective, cosine schedule, 20 denoising steps. Predicts a
  chunk; length is not stated in the paper (released config uses 4,
  unverified). Receding horizon; temporal ensembling did not help.
- Task conditioning: language or goal image, randomly dropped per example;
  unlabeled datasets use hindsight goal images. 2 frames of history.
- Data: 25 OXE datasets with images and delta end-effector control; diverse
  datasets double-weighted, repetitive ones down-weighted; missing cameras
  zero-padded; gripper +1 open, 0 closed (absolute; relative reduced
  retries). Shuffle buffer up to 500k frames, at most 100 steps per
  trajectory (Appendix E).
- Training: AdamW, lr 3e-4, 2000 warmup steps, inverse square-root decay,
  weight decay 0.1, grad clip 1.0, batch 2048, 300k steps. Octo-Base took
  14 hours on a TPU v4-128 pod (Sec. III-D).
- Fine-tuning recipe (Sec. III-C): full model update, same diffusion loss,
  about 100 target demos, 50k steps, cosine decay with linear warmup, same
  hyperparameters everywhere. About 5 hours on one NVIDIA A5000 (24 GB).

## Result that matters

Zero-shot (Fig. 4): WidowX, UR5 and Google Robot, two language tasks per
robot, 10 trials per task. Octo averaged 29 points above the released RT-1-X
checkpoint and was similar to RT-2-X 55B on WidowX and the Google Robot
(RT-2-X WidowX numbers quoted from OpenVLA; Google DeepMind ran the Google
Robot trials). Goal-image conditioning beat language by 25 points on WidowX.

Fine-tuning (Table I, 6 setups, about 100 demos each, 20 trials per domain):

| Setup | Scratch ResNet+Transformer | VC-1 | Octo |
|-------|---------------------------|------|------|
| Berkeley Insertion (adds force-torque input) | 10 | 5 | 70 |
| Stanford Coffee | 45 | 0 | 75 |
| CMU Baking | 25 | 30 | 50 |
| Berkeley Pick-Up (joint-position actions) | 0 | 0 | 60 |
| Berkeley Coke (new robot, ViperX) | 20 | 10 | 100 |
| Berkeley Bimanual (new robot, joint actions) | 20 | 50 | 80 |
| Average | 20 | 15 | 72 |

Ablations on WidowX (Table II, 40 trials over 4 tasks, Octo-Small): full
model 83%; RT-X 11-dataset mix 60%; Bridge only 43%; discretized actions
18%; MSE head 35%; ResNet-50 encoder 70%. Model scale (Fig. 5, 10 trials
per robot): Tiny 10M < Small 27M < Base 93M.

## What it changes in practice

- First fully open generalist manipulation policy: checkpoints (27M, 93M),
  JAX pretraining and fine-tuning code, OXE loaders for JAX and PyTorch, at
  octo-models.github.io. Licence not stated in the paper (MIT per the repo,
  unverified).
- The fine-tuning recipe is a usable default: 100 demos, 50k steps, one
  24 GB GPU, and it takes new inputs (force-torque) and action spaces (joint
  position, bimanual 14-D) by adding a head.
- Diffusion head over discretized or MSE actions is a 48-to-65 point swing.
- ViT-style backbones only win at scale; for 100-demo from-scratch training
  a ResNet+FiLM baseline was better (Sec. IV-C).

## Known limitations and follow-ups

- Wrist cameras hurt more than they helped (27% of the mix has them);
  language trails goal images (56% has language).
- Proprioceptive inputs made policies worse, attributed to causal confusion;
  larger or fine-tuned T5 encoders did not help (Appendix E).
- OpenVLA (7B) beat Octo by 50 points on out-of-distribution BridgeData V2
  tasks; pi0 beat it on dexterous tasks. Octo remains the small, fast option.

## Open questions

- Chunk length and execution horizon for the real-robot runs are not stated.
- Fig. 4 averages hide per-robot numbers at 10 trials per task.
- Would proprioception help with dropout or masking instead of removal?

## Sources

- Paper: https://arxiv.org/abs/2405.12213 (arXiv HTML read 2026-09-05)
- Project page, checkpoints and code: https://octo-models.github.io
