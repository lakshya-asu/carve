---
title: "Learning to Rearrange Deformable Cables, Fabrics, and Bags with Goal-Conditioned Transporter Networks"
date: 2026-09-06
tags: [paper, deformable, cable, cloth, bags, transporter-networks, goal-conditioned, imitation-learning, benchmark]
status: draft
source: https://arxiv.org/abs/2012.03385
---

# DeformableRavens (Seita, Florence, Tompson, Coumans, Sindhwani, Goldberg, Zeng, 2021)

Read from arXiv 2012.03385v4 (18 Jun 2023). Venue not stated in the text (ICRA 2021,
unverified). A 12-task PyBullet benchmark for cables, fabrics, and bags, plus two ways to
condition Transporter Networks on a goal image, with one physical cable experiment.

## Problem

Goals for deformables cannot be a pose. "Put the item in the bag" has no compact target,
and the object may need several pick-and-place actions with feedback. Transporter Networks
(Zeng et al. 2020) learned pick-and-place from a few demos on rigid tasks and one rope
task; nothing existed for 2D and 3D deformables with image goals (Sec. I, V-A).

## Core idea

Keep the Transporter structure (an FCN picks a pixel; a crop around it is cross-correlated
with dense features of the whole scene to score every place pose) and add the goal image
in a way that preserves spatial structure. Transporter-Goal-Stack concatenates current and
goal images channel-wise. Transporter-Goal-Split runs the goal through a fourth FCN and
multiplies its features element-wise into both the query and key features before the
cross-correlation (Sec. IV-A). Training uses hindsight relabelling: the goal for a sample
is the final observation of its own demonstration episode.

## Method details that matter for reimplementation

- Observation: top-down orthographic 320x160x6 (RGB plus three depth channels) built from
  three calibrated RGB-D cameras over a 0.5 x 1 m table, 3.125 mm per pixel; UR5 with a
  suction-style grasp that locks the nearest vertex to the end effector (Sec. V-B).
- Actions are two SE(2) poses; the primitive approaches until contact, grasps, lifts to a
  task-dependent height, moves, lowers until contact, releases. Bag tasks lift higher
  when pulling the bag than when opening it.
- Every FCN is a 43-layer, 9.9M-parameter residual FCN; 24 discrete rotations. The same
  random rotation and translation augments current and goal images together.
- Sim: PyBullet soft bodies on the FEM-based mass-spring solver with self-collision;
  cables are bead chains; fabrics and bags are Blender meshes; a bead ring is attached to
  the bag mouth for drawstring stability (Sec. V-A).
- Data: 1000 scripted demos per task; bag demonstrators succeed only 32.5 to 60.2% of the
  time and only successes are kept (Table I). Models trained for 20K iterations, batch 1
  (Transporter) or 128 (ground-truth MLP baselines), 3 seeds, 20 evaluation episodes per
  snapshot, best of 10 snapshots reported (Sec. VII).

## Result that matters

Simulation, success rate over 60 test episodes at the best snapshot (Table II), Transporter
variants versus a ground-truth-state MLP that sees object poses and vertices:

| Task (demos) | GT-State MLP | Transporter (or Goal-Stack / Goal-Split) |
|---|---|---|
| cable-ring (1000) | 0.0 | 68.3 |
| cable-shape (100) | 1.0 | 90.1 |
| fabric-cover (10) | 25.0 | 100.0 |
| fabric-flat (100) | 65.6 | 89.5 |
| bag-alone-open (1000) | 43.3 | 63.3 |
| bag-items-1 (1000) | 31.7 | 51.7 |
| bag-items-2 (1000) | 8.3 | 46.7 |
| cable-line-notarget (10, goal image) | 45.3 | 99.7 / 94.7 |
| cable-shape-notarget (1000, goal image) | 65.9 | 97.0 / 93.7 |
| fabric-flat-notarget (1000, goal image) | 64.1 | 89.1 / 88.1 |
| bag-color-goal (10, goal image) | 0.5 | 0.0 / 29.8 |

Bag policies beat their own demonstrators (51.7 versus 41.7 and 46.7 versus 32.5) because
failed demos were filtered. bag-color-goal is the failure: one seed, at most 29.8%, and it
gets worse with more demos because the policy takes actions that collapse the bag opening
(Sec. VII-B, Fig. 5).

Physical (Sec. VIII): Franka Panda, wrist Azure Kinect returning to a home pose for each
image, 45 cm bead chain on a 60 x 30 cm foam mat, binary segmentation mask as input, 24
human demos for training and 6 for validation, gripper yaw from a local tangent fit. 10
episodes with 10 distinct goal images, up to 10 actions each: 7/10 reached a cable-mask
IoU of 0.25 with the goal, in about 7 actions on average. One failure was repeated grasp
failure on a self-overlapping cable; two were policies oscillating without reaching the
threshold.

## What it changes in practice

- A goal image without markers is enough to specify a deformable target when the
  architecture keeps the image geometry; the ground-truth-state MLP with full vertex
  information lost on every task. Spatial structure in the network beat privileged state.
- Discrete pick-and-place with a return-to-home camera is slow (7 actions per episode) but
  needs 24 demos. It is the right first baseline for a slab-into-fixture task; the
  deformables topic note sketches that pipeline.
- The success threshold in the real experiment (IoU 0.25) was chosen to forgive
  calibration error. Report the threshold with the rate, as here.

## Known limitations and follow-ups

- Planar SE(2) actions, no recovery within an action; items fall out of lifted bags.
  Physical results are cables only (Sec. IX). Goal-Split versus Goal-Stack is
  task-dependent and the paper does not pick one.

## Open questions

- Table II reports the best of 10 snapshots by test performance, so the numbers are
  optimistic by an unreported margin.
- Would a real suction grasp reproduce the simulated vertex-locking grasp on fabric? The
  physical run used a parallel jaw on a bead chain, the easiest case.

## Sources

- Paper: https://arxiv.org/abs/2012.03385 (v4, 18 Jun 2023). Sec. III to IX; Table I, II; Fig. 2, 3, 5, 6.
- Code, data, appendix: https://berkeleyautomation.github.io/bags/
