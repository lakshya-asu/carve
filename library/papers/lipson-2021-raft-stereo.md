---
title: "RAFT-Stereo: Multilevel Recurrent Field Transforms for Stereo Matching"
date: 2026-09-06
tags: [paper, perception, stereo, depth, iterative-refinement]
status: draft
source: https://arxiv.org/abs/2109.07547
---

# RAFT-Stereo (Lipson, Teed, Deng)

Read from arXiv v1 (15 Sep 2021), the only version. Published at 3DV 2021. The GitHub
README and LICENSE (princeton-vl/RAFT-Stereo) were consulted for licence, weights and
flags; those items are marked as such.

## Problem

Deep stereo in 2021 meant a 3D cost volume filtered by 3D convolutions. That costs memory
and compute, caps the working resolution (megapixel Middlebury images need patching or
downsampling), and generalises poorly outside the training domain (Sec. 1, 2). Optical flow
had already moved to iterative refinement with RAFT, which runs at high resolution with 2D
operations only, but wastes effort on a 4D all-pairs volume stereo does not need.

## Core idea

Specialise RAFT to rectified stereo. Replace the 4D all-pairs correlation with a 3D volume
that only correlates pixels on the same image row, computed as one matrix multiply (Eq. 1).
Keep the GRU update operator that repeatedly looks up the correlation pyramid at the current
disparity and predicts a residual. The new part is a multilevel GRU: hidden states at 1/8,
1/16 and 1/32 resolution, cross-connected, so context spreads across large textureless
regions in few iterations while only the finest GRU touches the correlation volume and
emits the disparity update (Sec. 3.3, Fig. 3).

## Method details that matter for reimplementation

- Two encoders: a feature encoder (instance norm, both images) for correlation, and a
  context encoder (batch norm, left image only) that initialises the hidden state and is
  injected every iteration. Output at 1/4 or 1/8 resolution, 256 channels (Sec. 3.1).
- Correlation pyramid: 4 levels by 1D average pooling (kernel 2, stride 2) along the
  disparity axis only, so image resolution is kept at every level (Sec. 3.2). Lookup uses
  integer offsets around the current disparity with linear interpolation (Fig. 2). The full
  W x W volume is computed, negative disparities included, because a matmul is faster.
- Update: correlation features and current disparity each pass 2 conv layers, join the
  context, feed a ConvGRU, predict the delta from d0 = 0. Convex upsampling as in RAFT.
  Loss: L1 over all N iterates with weights gamma^(N-i), gamma = 0.9 (Eq. 2). Nothing else.
- Training (Sec. 4): SceneFlow only, 200k steps, batch 8, AdamW, one-cycle lr with minimum
  1e-4, random 360x720 crops, 22 iterations in training, 32 at test (80 for the ETH3D and
  Table 1 numbers). Augmentation: saturation 0 to 1.4, vertical perturbation of the right
  image to mimic imperfect rectification, and image plus disparity stretch by a factor in
  [2^-0.2, 2^0.4] to widen the disparity distribution. Hardware: two RTX 6000.
- Slow-fast GRU (Sec. 3.4, Table 6): update the 1/32, 1/16 and 1/8 states 30, 20 and 10
  times instead of 32 each, same weights. Runtime on 1248x384 drops from 0.132 s to
  0.063 s; FlyingThings3D 1px error rises from 9.40 to 9.98.
- Real-time variant (Sec. 4.7): shared backbone, two GRU levels, slow-fast, custom CUDA
  bilinear sampler. 26 FPS on 1248x384; the GPU is not stated (unverified). README flags:
  `--shared_backbone --n_downsample 3 --n_gru_layers 2 --slow_fast_gru --valid_iters 7`.
- 1/4-resolution model: 1px error 7.92 vs 9.40 at 0.338 s vs 0.132 s and 4x memory (Table 6).

## Result that matters

Zero-shot, SceneFlow-trained, mean of six runs after 200k steps, error = % pixels above
threshold (Table 1): KITTI-15 5.74 (3px), Middlebury full 18.33, half 12.59, quarter 9.36
(2px), ETH3D 3.28 (1px). Next best in the same setting, DSMNet: 6.5 / 21.8 / 13.8 / 8.1 /
6.2. RAFT-Stereo wins everywhere except Middlebury quarter.

ETH3D test leaderboard, synthetic-only training plus greyscale gamma-augmented SceneFlow
fine-tuning (Sec. 4.3, Table 3): bad-1px 2.44 vs next best HITNet 2.79, AvgErr 0.18 px.
First among published methods at submission.

Middlebury test leaderboard after fine-tuning on the 23 training pairs (4000 steps, batch 2,
384x1000 crops; Sec. 4.4, Table 4): bad-2px 4.74%, AvgErr 1.27 px, bad-1px 9.37% vs HITNet
13.3%. Output at full 1900x3000, which 33 of the 34 other top entries could not do.
KITTI-15 after 5k fine-tuning steps: D1-all 1.96 (Table 2).

Synthetic mix (Table 5, single hidden state, two runs): adding Falling Things and TartanAir
to SceneFlow drops KITTI-15 error 6.37 to 5.76 and Middlebury full 23.40 to 20.65.

## What it changes in practice

- Licence: MIT (repo LICENSE file, not stated in the paper). Checkpoints for SceneFlow,
  Middlebury, ETH3D and real-time on Google Drive; the README recommends Middlebury.
- Cost: 11.2M parameters. 0.132 s per 1248x384 pair base, 0.063 s slow-fast, 26 FPS
  real-time variant (Table 6, Sec. 4.7; GPU unstated). Memory scales with the correlation
  volume; the README's `--corr_implementation alt` computes it on the fly at a speed cost.
- Iteration count trades accuracy for time at inference with the same weights.
- For the cutting cell (our inference, untested): SceneFlow-only training is a weak prior
  for wet, specular meat. Keep the vertical-perturbation augmentation for rigs that flex
  under washdown, and start from the Middlebury checkpoint or a fine-tune on our own
  captures. FoundationStereo ([wen-2025-foundationstereo.md](wen-2025-foundationstereo.md))
  keeps this update loop and adds a monocular prior aimed at exactly these regions.

## Known limitations and follow-ups

- Final models use 40K SceneFlow pairs; Table 5 shows generalisation depends heavily on the
  synthetic mix, which the released models did not use. Transparency and specular surfaces
  are not tested. Megapixel runtime is not reported.
- Follow-ups that keep the GRU loop: IGEV (arXiv 2303.06615), Selective-IGEV, and
  FoundationStereo, whose Table 2 reports zero-shot Middlebury BP-2 of 1.1 vs 12.6 here.

## Open questions

- How much of the zero-shot gain is the multilevel GRU versus dropping 3D convolutions?
  Table 6 gives only 9.40 vs 9.64 for 3 levels vs 1 on FlyingThings3D.
- What rate does the real-time variant reach on an embedded GPU at 1280x720? Not measured.

## Sources

- Paper: https://arxiv.org/abs/2109.07547 (v1, 15 Sep 2021). Sec. 3.1 to 3.5, 4.1 to 4.7;
  Tables 1 to 6; Fig. 1 to 3, 6.
- Code and weights: https://github.com/princeton-vl/RAFT-Stereo (MIT; README consulted
  2026-09-06 for flags and checkpoints).
