---
title: "FoundationPose: Unified 6D Pose Estimation and Tracking of Novel Objects"
date: 2026-09-06
tags: [paper, perception, 6d-pose, tracking, rgbd, synthetic-data, rigid-objects]
status: draft
source: https://arxiv.org/abs/2312.08344
---

# FoundationPose (Wen, Yang, Kautz, Birchfield, NVIDIA)

Read from arXiv v2 (26 Mar 2024), the CVPR 2024 version with supplementary material.
Licence and weights notes come from the GitHub README and LICENSE, not the paper.

## Problem

Instance-level 6D pose estimators are trained per object from a textured CAD model, and
category-level methods generalise only within trained categories. Novel-object methods
split into model-based (CAD at test time) and model-free (a few reference images), and
tracking methods repeat the split. No one network covered all four cases (Sec. 1).

## Core idea

One render-and-compare pipeline for all four tasks. From an RGB-D frame and a 2D detection,
sample global pose hypotheses, refine each by comparing a rendering at that pose against a
pose-conditioned crop of the observation, then pick the winner with a ranking network that
attends across all hypotheses at once. The model-free setup becomes model-based by fitting
a neural SDF to the reference images and extracting a textured mesh once (Sec. 3.2).
Training is purely synthetic, with object textures diversified by ChatGPT prompts fed to a
text-to-texture diffusion model (Sec. 3.1).

## Method details that matter for reimplementation

- Inputs at test time: RGB-D image, intrinsics, a 2D detection or mask from an external
  detector (Mask R-CNN or CNOS), and either a CAD mesh or about 16 posed reference RGB-D
  images (Sec. 3.3, Suppl. 5.1, 5.2). Depth is eroded and bilateral-filtered first.
- Initialisation: translation from the median depth inside the detected box; rotations
  from Ns = 42 icosphere viewpoints times Ni = 12 in-plane rotations, 504 hypotheses
  (Sec. 3.3, Suppl. 5.2).
- Refiner: shared ResNet-34-style CNN encoder (Fig. 9) over rendered and observed RGB-D
  crops of 160 x 160, features concatenated and tokenised, then two transformer encoders
  (dim 512, 4 heads) emit a camera-frame translation update and a left-applied axis-angle
  rotation update; disentangling them stabilised training (Sec. 3.3, Suppl. 5.3). Training
  perturbations up to 2, 2, 5 cm and 20 deg. Iterations: 1 train, 5 estimate, 1 track.
- Selector: the same encoder gives a 512-d alignment feature per hypothesis; self-attention
  over all K features, no positional encoding, outputs one score each. Pose-conditioned
  triplet loss, margin 0.1, positives within 10 deg, K = 5 in training (Sec. 3.4, Suppl.
  5.2). InfoNCE instead cost 2.1 ADD AUC points (Table 6).
- Neural object field (model-free only): hash-encoded SDF plus colour MLP, truncation 1 cm,
  about 2k steps, "often within seconds"; then marching cubes to a mesh (Sec. 3.2, Suppl. 5.2).
- Training data: Objaverse-LVIS (over 40K objects, 1156 categories) plus Google Scanned
  Objects, path-traced in Isaac Sim, 70 to 90 objects per scene scaled to 5 to 30 cm, 662
  HDR backgrounds; about 600K scenes, 1.2M images (Sec. 3.1, Suppl. 5.2). Gains saturate
  near 1M images (Fig. 7). Training takes about one week on 4 V100s (Suppl. 5.2).

## Result that matters

Model-free estimation, YCB-Video, 16 reference images, no fine-tuning, perturbed GT boxes
as detections (Table 1): AUC of ADD 91.5 and ADD-S 97.4, versus FS6D-DPM (fine-tuned on
the target split) at 42.1 and 88.4. LINEMOD ADD-0.1d (Table 2): 99.0 to 100.0 per object.

Model-based estimation, BOP AR with Mask R-CNN detections (Table 3): LM-O 78.8, T-LESS
83.0, YCB-V 88.0, mean 83.3, versus MegaPose-RGBD 58.6 and instance-level SurfEmb + ICP
79.7. First on the BOP unseen-objects leaderboard at submission (Suppl. 5.1).

Tracking, YCBInEOAT robot manipulation videos, no re-initialisation after loss, ADD AUC
over all objects (Table 4): 93.09 from a GT initial pose, 93.22 when initialised by the
paper's own estimator, versus instance-trained se(3)-TrackNet at 92.66 and BundleSDF at
86.95. YCB-Video, all frames, ADD (Table 5): 96.0 model-based, 93.7 model-free.

Ablations, YCB-Video model-free, ADD AUC (Table 6): full 91.52; no LLM texture
augmentation 90.83; no transformer 90.77; no hierarchical comparison 89.05. Four reference
images still beat FS6D with 16 (Fig. 6).

## What it changes in practice

- Inference cost (Sec. 4.5, i9-10980XE plus RTX 3090): estimation about 1.3 s per object
  (4 ms init, 0.88 s refinement, 0.42 s selection); tracking about 32 Hz, one refinement
  pass per frame. Intended loop: estimate once, then track.
- Licence: NVIDIA Source Code License, "for research or evaluation purposes only"
  (repository LICENSE). A customer deployment needs a separate NVIDIA agreement. Isaac ROS
  wraps it with TensorRT (README).
- Weights: Google Drive links in the README. Public checkpoints skip the diffusion-augmented
  textures (Stable Diffusion and LAION restrictions); the README expects "slight
  performance degradation", and Table 6 prices that at 0.7 ADD AUC points.
- Meat cell fit: the object must be rigid with a CAD model or posed reference views.
  Primal cuts deform under the knife and differ per carcass, so neither exists; the paper's
  own future-work line is "state estimation beyond single rigid object" (Sec. 5). It does
  fit the rigid parts of the cell: tools, trays, fixtures, pucks, the knife (our inference).
- Detection is external, and the authors name false or missing detections as the most
  frequent bottleneck (Suppl. 5.4). SAM 2 masks are the natural feed (our inference).

## Known limitations and follow-ups

- Single rigid object per track; no articulated or deformable support (Sec. 5, Suppl. 5.4).
- Fails when texture-less, heavily occluded, and low-edge conditions coincide (Fig. 11).
- Model-free reference images need poses from an external SLAM or BundleSDF run (Suppl.
  5.2). Depth is required. Recovery after a tracking loss costs a 1.3 s estimation call.

## Open questions

- How does tracking hold on symmetric, textureless steel tooling under wet, specular light?
- Does the released checkpoint lose more than the paper's 0.7-point ablation on real data?
- Can the refiner alone track near-rigid bone-in cuts, or does the rigid assumption break?

## Sources

- Paper: https://arxiv.org/abs/2312.08344 (v2, 26 Mar 2024). Sec. 1, 3, 4, 5; Tables 1
  to 6; Figs. 6, 7, 9, 11; Supplementary 5.1 to 5.4.
- Code, weights, data: https://github.com/NVlabs/FoundationPose (README and LICENSE read
  2026-09-06). Project page: https://nvlabs.github.io/FoundationPose/
