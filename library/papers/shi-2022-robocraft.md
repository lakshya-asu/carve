---
title: "RoboCraft: Learning to See, Simulate, and Shape Elasto-Plastic Objects with Graph Networks"
date: 2026-09-06
tags: [paper, deformable, dough, particles, gnn, learned-dynamics, mpc, model-based]
status: draft
source: https://arxiv.org/abs/2205.02909
---

# RoboCraft (Shi, Xu, Huang, Li, Wu, 2022)

Read from arXiv 2205.02909v1 (5 May 2022). Venue not stated in the text (RSS 2022,
unverified). A Franka with cylindrical fingers pinches Play-Doh into letters using a
particle dynamics model learned from 10 minutes of random pinches.

## Problem

Dough and plasticine have no pose and no fixed topology; a policy needs a state, a model,
and a planner. Particle-GNN simulators (DPI-Net and successors) predict such objects well
but train on ground-truth particle correspondences from a simulator, which a camera does
not provide. Model-free RL ignores the object's structure and fails (Sec. I, II).

## Core idea

Build the particle state from RGB-D, train the GNN with distribution losses (earth mover's
and Chamfer) so no particle-to-particle correspondence is needed, and plan pinches by
gradient-based trajectory optimisation through the learned model with the same loss as the
cost.

## Method details that matter for reimplementation

- Perception (Sec. III-B): four RealSense D415 at 30 Hz, 848x480, calibrated to each other
  and the base. RANSAC plane removal, colour filter for the blue dough, Poisson surface
  reconstruction (alpha shapes and ball pivoting fail under occlusion), sample particles
  inside the mesh by SDF, remove points inside the finger SDFs, patch missing particles
  from the previous frame when the gripper is not in contact ("physics prior"), voxel
  downsample, outlier removal, farthest point sampling to a fixed count.
- Dynamics (Sec. III-C): graph with edges between particles within 0.05 (units not
  stated; metres in the base frame is the likely reading, unverified), edge types for
  internal versus gripper-to-object relations, 3-layer MLP encoders of width 150, one
  propagation layer, 3-layer motion predictor, multi-step message passing. Adam, lr 1e-4,
  batch 4, 100 epochs.
- Loss: 0.9 EMD plus 0.1 Chamfer. Either alone gives similar CD and EMD but the mix drops
  Hausdorff distance from 0.085 (CD only) or 0.107 (EMD only) to 0.079 (Table II, 12,000
  sim frames).
- Action (Sec. III-E): one pinch is {x, y, z, r_z, d}, the grip centre, yaw, and minimum
  finger gap, executed at constant speed. Planner: random shooting, then L-BFGS on the best
  trajectories with gradients through the GNN. Cameras are read only between grips, so it
  is receding-horizon per grip, not per timestep; grips continue until the loss is below a
  threshold or a cap is hit.
- Real data (Sec. IV-B): 50 episodes of 120 frames, three random grips each, 6000 frames,
  10 minutes; dough reset to a 6x6x2.5 cm cuboid in a printed mould, kneaded first to avoid
  wrinkles. Frames are saved only while the gripper is level with the object.
- Benchmark: 26 letters plus five shapes in sim (PlasticineLab-style MPM), seven letters
  plus five shapes on the robot; letters with holes are contour only.

## Result that matters

- Perception: crop-based sampling beats a convex-hull patch baseline, CD 0.0374 versus
  0.0384 and EMD 0.0308 versus 0.0317 over 120 sim frames (Table I). Small margins.
- Planning in sim: gradient descent through the model beats CEM, random shooting, and a
  model-based SAC baseline on letter A (Fig. 7, values in the figure only).
- Tool selection between two finger sizes changes EMD from 0.0345 to 0.0337 (Table III),
  which is within the reported standard deviation of 0.007.
- Real robot: shapes A, B, R, T, X and others from a model trained only on random pinches
  (Fig. 11); open-loop rollouts of the real-data model track the observed particles (Fig.
  10). The real model beats an MPM simulator with hand-set parameters and a GNN trained in
  sim, both transferred to the real robot (Fig. 12, qualitative only).
- Humans: four amateurs, keyboard control in sim (C, E, Y, Z, heart, two attempts each)
  and guided-mode control of the arm on the real dough (A, B, R, T, X). Sim averages,
  Table IV: humans CD 0.0655 and EMD 0.0661, RoboCraft 0.0359 and 0.0340. The authors note
  human results were recognisable even at high distances, so the metric favours the robot.
- Generalisation: circle, triangle, and rectangle starting shapes reach an X; a model
  trained on Play-Doh roughly shapes modelling foam without retraining (Fig. 13, images
  only).

No success rates are reported anywhere; every quantitative result is a point-set distance.

## What it changes in practice

- Ten minutes of random interaction was enough for a usable model because the state is
  structured (particles plus graph) and the loss does not need tracking. The same recipe
  applies to any material that stays one connected blob under the tool.
- Sim-trained dynamics lost to real-trained dynamics on the same hardware (Fig. 12). For
  dough-like materials, budget for real interaction data rather than parameter fitting.
- Replanning only between grips is a stated trade-off against perception time; the
  particle pipeline is too slow to close a loop within a pinch. A slab cell doing one grasp
  and one place is closer to this regime than a continuous shaping task is.

## Known limitations and follow-ups

- No topology change; RoboCook (arXiv 2306.14447) adds tools and skill selection,
  DoughNet (arXiv 2404.12524) adds splitting and merging. See
  `library/topics/deformable-object-manipulation.md`.
- Four cameras around a small fixed platform; the object is fixed by a central rod
  (Sec. IV-A). A conveyor or bin removes both.

## Open questions

- The proximity threshold 0.05 and the particle count after farthest point sampling are
  not given in units or numbers in the text; the released code would settle both.
- Table III's tool-selection gain is inside one standard deviation; the paper calls it an
  improvement.

## Sources

- Paper: https://arxiv.org/abs/2205.02909 (v1, 5 May 2022). Sec. III, IV, V; Table I to IV;
  Fig. 3, 7, 10 to 14.
- Project page and code: http://hxu.rocks/robocraft/
