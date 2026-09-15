---
title: "Dex-Net 3.0: Computing Robust Vacuum Suction Grasp Targets in Point Clouds using a New Analytic Model and Deep Learning"
date: 2026-09-06
tags: [paper, grasping, suction, point-cloud, synthetic-data, gq-cnn, bin-picking]
status: draft
source: https://arxiv.org/abs/1709.06670
---

# Dex-Net 3.0 (Mahler, Matl, Liu, Li, Gealy, Goldberg, ICRA 2018)

Read from arXiv 1709.06670v2 (13 Apr 2018). An analytic model of a single suction cup
labels 2.8M synthetic point-cloud grasps, which train a GQ-CNN that ranks suction targets.

## Problem

Suction planners in 2017 used heuristics: aim at the object centroid, or at the centre of
the largest planar patch (Amazon Picking Challenge teams, Sec. II-B). These fail on objects
whose surface near the centroid is curved. Analytic suction models assumed the seal already
existed and the object pose was known exactly.

## Core idea

Split suction success into two testable conditions and evaluate both under perturbation.
Seal formation: a quasi-static spring model of the cup (perimeter, cone, and flexion
springs on an n-gon pyramid of radius r and height h) is projected onto the object mesh
along the approach axis; a seal is feasible if no cone face collides, the surface has no
holes inside the ring, and the energy in every individual spring stays under a threshold.
Wrench resistance: a "suction ring contact" wrench basis with actuated normal force,
constant vacuum force V, tangential friction, torsional friction, and an elastic restoring
torque about the tangent axes, which is the term that lets one cup hold an off-centre load
(Sec. IV-B). Constraints are linear so wrench resistance is a QP. The label is the sample
mean of binary wrench resistance over perturbed object pose, gripper pose, friction, and
disturbing wrenches (Definition 3, "robust wrench resistance", RWR).

## Method details that matter for reimplementation

- Assumptions (Sec. III-A): quasi-static, rigid non-porous objects, singulated on a plane
  in a stable pose, one overhead depth camera with known extrinsics, one disc-shaped cup.
- Dataset: about 350k suction points on 1500 meshes from KIT and 3DNet, rendered into 2.8M
  point-cloud and grasp tuples with about 11.8% positives (Fig. 3). Depth noise is
  multiplicative plus Gaussian-process pixel noise, as in Dex-Net 2.0.
- Model parameters (n, r, h, spring energy threshold, V, mu, kappa, label threshold) were
  set by grid search to maximise average precision on real YuMi grasps of known 3D-printed
  objects (Sec. V). The physical fit is part of the pipeline, not an afterthought.
- GQ-CNN: Dex-Net 2.0 architecture with the pose stream extended by the angle between the
  approach direction and the table normal; depth crop centred on the target and rotated to
  the approach orientation. 80/20 image-wise split, about 12 h on three Titan X, 93.5%
  validation accuracy. Policy is cross-entropy method over surface points and normals.
- Robot: ABB YuMi, Primesense Carmine 1.09, 15 mm silicone single-bellow cup, VM5-NC
  vacuum generator, about 0.9 kg payload. Success is lift and transport to the side of the
  workspace; about 3 s planning per grasp on an i5-6400 and GTX 980; operators blinded to
  the method in the novel-object test.

## Result that matters

Known objects, known pose, 5 adversarial 3D-printed parts, 75 trials per metric (Table II,
Appendix): RWR 100% AP and 92% success; wrench resistance without perturbation 93% AP and
80%; spring stretch 89% and 84%; planarity-centroid 88% and 80%. The main text (Sec. VII-C)
quotes RWR at 99% AP; Table II says 100%.

Novel objects from a single depth image (Table I, Appendix; 125 trials each on Basic and
Typical, 100 on Adversarial, per policy):

| Policy | Basic AP / success | Typical AP / success | Adversarial AP / success |
|---|---|---|---|
| Planarity | 81 / 74 | 69 / 67 | 48 / 47 |
| Centroid | 89 / 92 | 80 / 78 | 47 / 38 |
| Planarity-centroid | 98 / 94 | 94 / 86 | 64 / 62 |
| GQ-CNN trained on adversarial meshes only | 83 / 77 | 75 / 67 | 86 / 81 |
| GQ-CNN on Dex-Net 3.0 | 99 / 98 | 97 / 82 | 61 / 58 |

Object classes: Basic 25 prismatic solids, Typical 25 household objects with planar
patches, Adversarial 5 printed parts with curved or narrow surfaces (Sec. VII-A). The
abstract's 98 / 82 / 58 are the Dex-Net 3.0 row. The most common failure was attempting a
seal on geometry the depth sensor could not resolve; with exact geometry the seal model
catches these (Sec. VII-E).

## What it changes in practice

- The success-versus-attempt-rate curve (Appendix, Fig. 6 and 7) is the operational
  output: threshold the predicted probability, and the system either picks or asks for
  another action. On Basic and Typical objects the GQ-CNN's score tracks real outcomes, so
  low-confidence grasps can be routed elsewhere.
- Planarity-centroid is within a few points of the learned policy on Basic and Typical
  objects and needs no training. The learned model earns its place on complex geometry,
  and only when the training meshes resemble the parts (adversarial-only training: 81%
  versus 58%).
- Every assumption is violated by meat: porous, wet, deformable, non-rigid surface. The
  seal model is the part worth reusing as a feasibility filter on a scanned surface; the
  wrench analysis needs a different contact model. See
  `library/topics/deformable-object-manipulation.md` (suction row).

## Known limitations and follow-ups

- Singulated objects only; heaps, cup shape, and sensor resolution are future work (Sec.
  VIII). Dex-Net 4.0 (Science Robotics 2019) extends to heaps with a suction-or-jaw choice.
- Physical trials are one operator, one cup, one vacuum generator.

## Open questions

- The elastic restoring torque uses a material constant kappa fitted on real grasps. How
  far does one fit transfer to a different cup durometer or diameter?
- 350 trials across 55 objects is 5 to 7 per object per policy; per-object variance is not
  reported.

## Sources

- Paper: https://arxiv.org/abs/1709.06670 (v2, 13 Apr 2018). Sec. III to VII, Appendix I,
  Table I and II, Fig. 3, 5, 6, 7.
- Code, dataset, supplement: http://berkeleyautomation.github.io/dex-net
