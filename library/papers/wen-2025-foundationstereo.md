---
title: "FoundationStereo: Zero-Shot Stereo Matching"
date: 2026-09-06
tags: [paper, perception, stereo, depth, foundation-model, synthetic-data]
status: draft
source: https://arxiv.org/abs/2501.09898
---

# FoundationStereo (Wen, Trepte, Aribido, Kautz, Gallo, Birchfield; NVIDIA)

Read from arXiv v4 (4 Apr 2025). CVPR 2025 (venue unverified from the paper text). The
GitHub README and LICENSE (NVlabs/FoundationStereo) were consulted for licence, weights
and deployment notes; those items are marked as such.

## Problem

RAFT-Stereo ([lipson-2021-raft-stereo.md](lipson-2021-raft-stereo.md)) and IGEV reach low
error only after fine-tuning on the target domain. Trained on SceneFlow (40K pairs) they
fail on reflective, textureless, translucent and thin structures (Sec. 1). Real stereo
ground truth is sparse (LiDAR) or tiny.

## Core idea

Scale stereo like a foundation model on three fronts. Data: a 1M-pair synthetic dataset
(FSD) rendered in Omniverse with randomised baseline, focal length, lighting and layouts,
self-curated by regenerating samples the current model cannot solve. Features: a
side-tuning adapter fuses a frozen Depth Anything V2 ViT
([yang-2024-depth-anything-v2.md](yang-2024-depth-anything-v2.md)) with a small CNN, so
matching gets a monocular prior for ambiguous regions without the ViT's scale ambiguity.
Cost filtering: separable 3D convolutions plus a transformer along the disparity axis give
a good initial disparity that RAFT-style GRU iterations then refine (Sec. 3, Fig. 2).

## Method details that matter for reimplementation

- Side-Tuning Adapter (STA, Sec. 3.1, Fig. 3): take the feature just before the Depth
  Anything V2 output head, downscale with a 4x4 stride-4 conv, concatenate with the 1/4
  level of an EdgeNeXt-S CNN pyramid. ViT stays frozen; unfreezing raises Middlebury BP-2
  from 1.97 to 3.94 (Table 5). Depth Anything V2 Large beats Base, Small and DINOv2-L
  (BP-2 1.97 / 2.11 / 2.22 / 2.46, Table 5). A second STA with residual blocks makes the
  context features that seed the GRU hidden states at 1/4, 1/8, 1/16.
- Hybrid cost volume at 1/4 resolution (Eq. 1): group-wise correlation (G = 8) on
  L2-normalised features, concatenated with disparity-shifted features cut to 14 channels.
- Axial-Planar Convolution (APC): each 3x3x3 hourglass conv becomes a Ks x Ks x 1 spatial
  conv then a 1 x 1 x Kd disparity conv, Kd = 17 (Table 6). Dense 5x5x5 ran out of 80 GB.
- Disparity Transformer (DT): 4x4x4 stride-4 conv on the volume, tokens of length D/16,
  cosine position encoding, 4 encoder blocks with 4-head FlashAttention over disparity
  only, upsampled and summed with the hourglass output. Full-volume attention is worse
  (BP-2 2.25 vs 1.97, Table 6).
- Initial disparity by soft-argmin (Eq. 2), then three-level ConvGRU refinement as in
  RAFT-Stereo, each step looking up the filtered hybrid volume and a plain correlation
  volume (Eq. 10). Loss (Eq. 11): smooth L1 on d0 plus gamma-weighted L1, gamma = 0.9.
- Training (Sec. 4.1): FSD plus SceneFlow, Sintel, CREStereo, FallingThings, InStereo2K,
  Virtual KITTI 2. 200K steps, batch 128 on 32 A100s, AdamW, lr 1e-4 decaying by 0.1 at
  80% of training, 320x736 crops, 22 GRU iterations. Inference: 32 iterations, max disp 416.
- FSD (Sec. 3.5, Appendix 11): 1M pairs at 1280x720, 12 scene models, >5K assets, path
  tracing, 48 A40 GPUs for 10 days. Layouts are "chaotic" (flying distractors) or
  "realistic" in navigation, driving and manipulation styles; manipulation points the
  camera front or down at close-range grocery items. Self-curation regenerates samples
  with BP-2 above 60%, twice (Table 8: 1.15 vs 1.27 BP-2 with vs without).

## Result that matters

Zero-shot with a fixed model (Table 2; Middlebury BP-2 at half resolution non-occluded,
ETH3D BP-1, KITTI-12 and KITTI-15 D1): 1.1 / 0.5 / 2.3 / 2.8, against Selective-IGEV
trained on any non-target data at 7.5 / 3.4 / 3.2 / 4.5. Trained on SceneFlow only, the
same architecture gives 5.5 / 1.8 / 3.2 / 4.9 versus RAFT-Stereo 12.6 / 3.3 / 4.7 / 5.5.

ETH3D test leaderboard (Table 4): zero-shot BP-0.5 2.31, BP-1 1.52, EPE 0.13, beating
fine-tuned Selective-IGEV (3.06 / 1.23 / 0.12) on two of three metrics. After 50K
fine-tuning steps on ETH3D train: 1.26 / 0.26 / 0.09, first at submission, as on Middlebury.

Booster, half resolution, specular and transparent objects, zero-shot (Appendix 9): BP-2
9.6 and EPE 2.2 versus Selective-IGEV 15.0 and 6.6. Ablations on a 100K FSD subset,
Middlebury training set BP-2 (Table 7): CNN only 2.48, STA 2.21, STA with APC 2.16, STA
with DT 2.05, all three 1.97. Adding FSD to the public mix drops BP-2 from 2.34 to 1.15,
and FSD lifts IGEV from 8.8 to 7.8 (Table 9).

## What it changes in practice

- Licence: NVIDIA Source Code License-NC, research use only, from the repo LICENSE file;
  the paper does not state it. Production use in a cell needs an agreement with NVIDIA.
- Weights: ViT-Large model (repo name 23-51-11) recommended for general use, plus a second
  checkpoint (11-33-40, size unverified), on Google Drive via the README. FSD is over 1 TB.
- Cost: 0.7 s per 375x1242 pair on an A100 (Sec. 5). RTX 3090, Middlebury (Table 10): full
  resolution 8.14 s and 18.5 GB peak, half 2.97 s and 10.5 GB, quarter 0.55 s and 2.3 GB.
  The README claims about 6x speedup with TensorRT FP16 on a 3090 and lists Jetson Orin as
  tested (not in the paper).
- For the cutting cell (our inference, untested): the STA prior is what handles glossy,
  low-texture surfaces, and Booster is the closest published proxy for wet meat. Runtime
  rules out per-frame use at 1280x720 without TensorRT or quarter-resolution input.

## Known limitations and follow-ups

- Speed and memory are stated as unaddressed (Sec. 5). FSD holds few transparent objects.
- Zero-shot numbers are half-resolution Middlebury non-occluded unless noted;
  full-resolution BP-2 is 4.8 (Table 10). Concurrent work with a similar monocular prior
  ([3] in Sec. 1) is not compared directly.

## Open questions

- Does metric scale stay consistent frame to frame when the monocular prior dominates in
  textureless regions? Only per-frame disparity error is evaluated.
- How far can the ViT backbone shrink or quantise before the Booster gains vanish?

## Sources

- Paper: https://arxiv.org/abs/2501.09898 (v4, 4 Apr 2025). Sec. 1, 3.1 to 3.5, 4.1 to
  4.5, 5; Tables 1 to 7; Appendix 7 to 11 with Tables 8 to 10; Fig. 2 to 4.
- Code, weights, dataset: https://github.com/NVlabs/FoundationStereo (README and LICENSE
  consulted 2026-09-06). Project page: https://nvlabs.github.io/FoundationStereo/
