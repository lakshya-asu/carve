---
title: "Fine-Tuning Vision-Language-Action Models: Optimizing Speed and Success (OpenVLA-OFT)"
date: 2026-09-05
tags: [paper, vla, finetuning, action-chunking, bimanual, aloha, libero, lora]
status: draft
source: https://arxiv.org/abs/2502.19645
---

# OpenVLA-OFT (Kim et al., 2025)

## Problem

Fine-tuning OpenVLA with its own recipe gives 3 to 5 Hz autoregressive
policies that cannot drive a 25 to 50 Hz bimanual robot. The paper isolates
which fine-tuning design choices fix this, keeping the pretrained weights.

## Core idea

Three fine-tuning changes: emit all action tokens in one forward pass with
bidirectional attention (parallel decoding), emit a chunk of K future
actions in that pass, and replace token classification with an MLP head
trained by L1 regression. For multi-camera setups add FiLM on the vision
tower. Result: 26x throughput and the best LIBERO score to date from a base
model pretrained on single-arm data.

## Method details that matter for reimplementation

- Base: OpenVLA 7B, LoRA rank 32, pretraining untouched. Parallel decoding:
  K x D empty action embeddings in, causal mask replaced by bidirectional
  attention; D sequential passes become one.
- Action head: MLP from final hidden states to actions in [-1, 1], mean L1
  loss. A diffusion variant (50 train steps, DDIM at test) matched L1 on
  success but not latency (Table II).
- Chunking: K = 8 on LIBERO, K = 25 on ALOHA at 25 Hz; full chunk executed
  open loop. Extra cameras add 256 patch tokens each through the shared
  projector; proprioception is one token through its own projector.
- FiLM (OFT+): mean language embedding projected to per-block gamma and beta
  of size D_ViT, applied to every patch between self-attention and MLP in
  each ViT block. Modulating per patch instead of per hidden unit failed.
- LIBERO training (Table IV): lr 5e-4, decayed to 5e-5 after 100k steps,
  batch 64 on 8 A100/H100 80 GB, 50k to 150k steps until normalized L1 below
  0.01, 224x224 images, 90% random crop plus color jitter, 279M trainable
  parameters (111M LoRA, 151M action head, 17M proprio projector).
- ALOHA training (Table V): same plus FiLM, batch 32, decay after 50k steps,
  853M trainable (456M of it FiLM projectors).

## Result that matters

LIBERO (Table I; 500 trials per suite = 10 tasks x 50 episodes; average over
Spatial, Object, Goal, Long; filtered demos as in OpenVLA):

| Policy | Inputs | Average SR |
|--------|--------|-----------|
| OpenVLA, original recipe | 3rd-person image | 76.5 |
| + parallel decoding and chunking | same | 90.2 |
| + continuous L1 (OpenVLA-OFT) | same | 95.3 |
| + continuous diffusion | same | 95.4 |
| OpenVLA-OFT | + wrist image, proprio | 97.1 |

With the same inputs, pi0 fine-tuned scored 94.2 and pi0-FAST 85.5 (from
their own papers). Throughput on an A100, 7-D action, 100 queries
(Table II): OpenVLA 4.2 Hz at 240 ms; + parallel decoding 15.9 Hz at 63 ms;
+ chunk 8 108.8 Hz at 74 ms; + L1 head 109.7 Hz at 73 ms; diffusion with 50
test steps 4.2 Hz at 1.9 s; with wrist camera and proprio 71.4 Hz at 112 ms.

ALOHA, two ViperX 300 S arms, 25 Hz, three cameras, 14-D joint targets
(Tables X to XIII, staged rubric 0 to 100, averaged over trials):

| Task | Demos / trials | ACT | Diffusion Policy | RDT-1B | pi0 | OpenVLA-OFT+ |
|------|---------------|-----|-----------------|--------|-----|-------------|
| fold shorts | 20 / 10 | 100 | 100 | 100 | 100 | 100 |
| fold shirt | 30 / 10 | 94 | 100 | 96 | 100 | 100 |
| scoop X into bowl | 45 / 12 | 71.3 | 79.2 | 73.3 | 93.3 | 100 |
| put X into pot | 300 / 24 | 23.8 | 30.8 | 44.2 | 42.1 | 51.3 |

Without FiLM, "scoop X into bowl" fell to 35.0 and language following on the
two language tasks fell to 33%, chance among three options (Sec. VI-C).

ALOHA inference, A100, three images, K = 25 (Table III): OpenVLA 1.8 Hz,
OpenVLA-OFT+ 77.9 Hz at 321 ms, RDT-1B 84.1 Hz, Diffusion Policy 267 Hz,
pi0 292 Hz (JAX), ACT 433 Hz.

## What it changes in practice

- The recipe is the contribution and applies to any autoregressive VLA.
  A single-arm-pretrained 7B model matched or beat pi0 and RDT-1B, both
  pretrained on bimanual data, after this fine-tune.
- Cost: 8 x 80 GB GPUs, batch 32 to 64, 50k to 150k steps per task.
- Code and checkpoints at openvla-oft.github.io (licence unverified).
  321 ms latency with a 25-step chunk at 25 Hz: the policy is blind for the
  first third of each second of motion. Measure this on reactive tasks.

## Known limitations and follow-ups

- L1 fits the median mode; multimodal demonstrations are untested (Sec. VIII).
- Whether OFT choices help pretraining is untested. Language grounding
  without FiLM was fine on LIBERO but at chance on ALOHA; cause unknown.
  ALOHA trials are 10 to 24 per task; the folding ranking is not meaningful.

## Open questions

- Is 97.1% near the LIBERO ceiling, given filtered demos and per-suite runs?
- Parallel decoding plus chunking lifts LIBERO-Long by 33 points but other
  suites by 4 to 11; the paper credits reduced compounding error.

## Sources

- Paper: https://arxiv.org/abs/2502.19645 (arXiv HTML read 2026-09-05)
- Project page and code: https://openvla-oft.github.io
- Base model entry: [OpenVLA](kim-2024-openvla.md)
