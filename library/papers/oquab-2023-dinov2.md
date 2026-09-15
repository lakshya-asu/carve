---
title: "DINOv2: Learning Robust Visual Features without Supervision"
date: 2026-09-06
tags: [paper, perception, self-supervised, visual-representation, vit, policy-backbone]
status: draft
source: https://arxiv.org/abs/2304.07193
---

# DINOv2 (Oquab, Darcet, Moutakanni, Vo, Szafraniec, Khalidov, ... Joulin, Bojanowski)

Read from arXiv v2 (2 Feb 2024), the TMLR (01/2024) version, Meta AI Research with Inria.
Register variants (arXiv 2309.16588) are repo-only and not covered.

## Problem

Self-supervised vision models (DINO, iBOT, MAE) were trained on ImageNet-1k and either need
supervised fine-tuning (MAE) or fall well behind CLIP-style encoders when used frozen.
Scaling them to uncurated web data degraded features because dominant image modes swamp
the rest (Sec. 1, 2). The question is whether a frozen, text-free encoder can match
OpenCLIP at both image level and pixel level.

## Core idea

Keep the discriminative recipe (DINO image-level loss plus iBOT masked patch-level loss)
and fix the two things that stopped it scaling. Data: build LVD-142M by retrieving nearest
neighbours of curated seed datasets from 1.2B deduplicated web images, using image
embeddings only, no text or metadata (Sec. 3, Fig. 3). Training: stabilisation and
efficiency changes (Table 1) let a 1.1B-parameter ViT-g/14 train on 142M images, which is
then distilled into ViT-S/B/L. The frozen patch tokens carry depth and object-part
information readable with a linear layer (Sec. 7.4, 7.5).

## Method details that matter for reimplementation

- Loss: L_DINO on class tokens of two global crops plus L_iBOT on masked patch tokens, with
  separate heads (sharing hurts at scale, Sec. 4), Sinkhorn-Knopp teacher centering, KoLeo
  regulariser weight 0.1 (Appendix B.1), teacher EMA momentum cosine 0.994 to 1.
- Recipe deltas over iBOT, ImageNet-1k k-NN / linear, ViT-L on ImageNet-22k (Table 1):
  LayerScale plus stochastic depth 0.4 cost linear accuracy (82.0 from 83.2) but stop NaN
  losses; 128k prototypes, KoLeo (+2.3 k-NN), SwiGLU, patch 14, batch 3k, untied heads
  bring the total to 82.0 / 84.5 versus iBOT 72.9 / 82.3.
- Architecture (Table 17): ViT-S/14 384d 6 heads 12 blocks; ViT-B/14 768d 12 heads 18
  blocks (not the usual 12); ViT-L/14 1024d 16 heads 24 blocks; ViT-g/14 1536d 24 heads 40
  blocks, sized so each head is 64 dims for the custom FlashAttention. Distilled models use
  MLP FFN, from-scratch models SwiGLU.
- Training (Table 16): 625k iterations, AdamW, lr 3.5e-4 batch 3072 from scratch (drop
  rate 0.4) or lr 1e-3 batch 2048 distilled (drop rate 0), 100k warmup, weight decay
  cosine 0.04 to 0.2, float16 with FSDP. Global crops 224, local crops 98, sequence packing
  with a block-diagonal mask. Final 10k iterations at 518x518 with compressed schedules and
  lower base lr (Appendix B.2); Fig. 6 shows this recovers most of full high-res training.
- Distillation (Sec. 5): same loop with a frozen ViT-g teacher, no masking, no stochastic
  depth, iBOT loss on both global crops, EMA of the student as the final model. Distilled
  ViT-L beats from-scratch ViT-L on all 12 benchmarks (Fig. 5).
- Data (Appendix A, Table 15): 1.3B crawled images, self-dedup (k = 64, cosine > 0.6) to
  1.1B, then removal of anything within 0.45 of any evaluation split to 744M. Retrieval
  k = 4 per query (k = 32 for ImageNet-1k) or cluster sampling capped at 1M per small seed.
- Dense feature taps (Sec. 7.4): last layer plus class token, or patch tokens from layers
  3, 6, 9, 12 (S/B), 5, 12, 18, 24 (L), 10, 20, 30, 40 (g).

## Result that matters

Frozen features, linear probe, ImageNet-1k val top-1 at 224 (Table 4): ViT-S/14 81.1,
ViT-B/14 84.5, ViT-L/14 86.3, ViT-g/14 86.5, against OpenCLIP ViT-G/14 86.2 and iBOT
ViT-L/16 82.3. Fine-tuning ViT-g adds only +2.0 to +2.2 points (Table 5).

Dense tasks, frozen backbone (Tables 10, 11): ADE20k linear 49.0 mIoU for ViT-g versus
OpenCLIP-G 39.3; NYUd depth RMSE with a DPT head 0.279 (g), 0.293 (L), 0.317 (B) versus
OpenCLIP-G 0.414 and iBOT 0.358, and the NYUd head transfers to SUN RGB-D at 0.338.
Dropping the iBOT patch loss costs 2.9 mIoU on ADE20k (Table 3b), so the patch objective
is what makes dense features usable.

Domain shift (Table 6, linear probe): ImageNet-A 75.9 for ViT-g versus iBOT 41.5 and
OpenCLIP-G 63.8. Curated LVD-142M beats 142M random crawl images on all but ADE20k (Table 2).

## What it changes in practice

- Licence and weights: code and models under Apache 2.0 (Sec. 5, repo LICENSE). Repo
  README lists 21M (S), 86M (B), 300M (L), 1,100M (g). The XRay-DINO variant added Dec
  2025 carries a separate noncommercial licence, so check which checkpoint you load.
- Inference cost: the paper gives no latency. Patch 14 at 224 is 256 tokens, at 518 it is
  1369; measure on the target GPU (unverified).
- As a frozen policy backbone: patch tokens linearly encode depth and parts (Table 11,
  Fig. 1, 9, 10), which is why later policies pick DINOv2 over CLIP. Whether meat surfaces,
  far from the object-centric seed sets, get the same part structure is untested in the
  paper; ImageNet-A and SUN RGB-D transfer argue yes (our inference, untested).
- Retraining is out of reach: ViT-g took 22,016 A100-40GB GPU-hours (Table 14) and the
  data pipeline two days on 160 V100s (Sec. 3). Fine-tune or distil instead. Note ViT-B/14
  has 18 blocks, so multi-layer tap indices differ from a stock ViT-B.

## Known limitations and follow-ups

- Bias: Dollar Street accuracy drops 25.7 points Europe to Africa (Table 12).
- Depth Anything V2 (yang-2024-depth-anything-v2.md, Table 13) finds the register ViT-g
  transfers worse for depth than the original. DINOv3 (repo note, Aug 2025) supersedes
  this line; not read (unverified).
- Nothing here tests the features inside a closed-loop policy. The Diffusion Policy
  encoder ablation (chi-2023-diffusion-policy.md, Table 5) shows frozen encoders can lose
  to end-to-end ResNets; frozen DINOv2 needs a per-task ablation.

## Open questions

- Which taps carry the geometry a cutting policy needs: last-block tokens, or the
  four-layer concatenation the depth probe uses?
- Does the KoLeo spread that helps retrieval (Table 3a) help or hurt a control head?

## Sources

- Paper: https://arxiv.org/abs/2304.07193 (v2, 2 Feb 2024). Sec. 3, 4, 5, 6, 7.1, 7.4,
  7.5, 8; Tables 1 to 6, 10, 11, 12, 14 to 17; Fig. 5, 6; Appendix A, B.
- Code and weights: https://github.com/facebookresearch/dinov2 (README and LICENSE read
  2026-09-06 for parameter counts and licence).
