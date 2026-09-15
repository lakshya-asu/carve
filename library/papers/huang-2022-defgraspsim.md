---
title: "DefGraspSim: Physics-Based Simulation of Grasp Outcomes for 3D Deformable Objects"
date: 2026-09-06
tags: [paper, deformable, grasping, simulation, fem, isaac-gym, food-handling]
status: draft
source: https://arxiv.org/abs/2203.11274
---

# DefGraspSim (Huang, Narang, Eppner, Sundaralingam, Macklin, Bajcsy, Hermans, Fox, RA-L 2022)

Read from arXiv 2203.11274v1 (21 Mar 2022), the RA-L version, DOI 10.1109/LRA.2022.3158725.
arXiv 2107.05778v1 (12 Jul 2021, "DefGraspSim: Simulation-based grasping of 3D deformable
objects") is the same work at an earlier stage and carries the appendix with the
feature-importance analysis the RA-L text omits. Numbers below are RA-L unless marked.

## Problem

A rigid grasp is judged by force or form closure on a fixed geometry. A grasp on tofu,
fruit, or a flexible bottle changes the geometry, and the fields that decide whether it
damaged the object (stress, deformation) cannot be measured in the real world. Prior
deformable grasp metrics were 2D, strain-energy proxies, or tested only on rigid objects
(Sec. II).

## Core idea

Run every candidate grasp through GPU FEM, record field quantities that a real sensor
cannot see, define seven performance metrics over them, define seven pre-pickup grasp
features a real robot can measure, and release the pipeline and dataset so the features
can be learned as predictors of the metrics.

## Method details that matter for reimplementation

- Simulator: Isaac Gym co-rotational linear FEM on tetrahedral meshes (fTetWild), Coulomb
  contact with a generic Franka parallel-jaw gripper, GPU Newton implicit integration at
  1500 Hz; 5 to 10 fps, 2 to 7 min per grasp experiment (Sec. III). The 2021 version gives
  the dataset cost as 2080 GPU hours in Sec. II and about 1400 in Appendix B, unreconciled.
- Objects: 34, primitives plus scaled YCB, ShapeNet, Thingiverse, and Real Food models,
  smoothed in Blender to avoid stress singularities. Density 1000 kg/m^3, Poisson 0.3,
  friction 0.7, Young's modulus in {2e4, 2e5, 2e6, 2e9} Pa (human skin to ABS). Values
  below about 1e3 Pa were excluded for interpenetration (2021 version, Appendix B).
- Grasps: 50 antipodal samples per object, table collisions disabled so grasps can come from
  below. Squeeze force F_p = 1.3 mg/mu from a force-based torque controller with a low-pass
  filter on contact force.
- Four experiments per grasp: pickup (success if contact held 5 s under gravity),
  reorientation to 64 states, linear acceleration along 16 directions at 1000 m/s^3 jerk
  to a 50 m/s^2 cap, angular acceleration about 16 axes at 2500 rad/s^3 jerk to a 1000
  rad/s^2 cap (Sec. IV). Finger joints are frozen after pickup for the last three.
- Seven metrics (Sec. V): pickup success, max von Mises stress, max nodal deformation after
  removing the best-fit rigid transform, strain energy, linear instability, angular
  instability (mean loss-of-contact acceleration), and deformation controllability (max
  deformation over the 64 reorientations).
- Seven features (Table II): contact patch distance and perpendicular distance to centroid,
  number of contact points, contact patch distance to finger edge, squeezing distance,
  gripper separation, alignment with gravity; all measurable with encoders or cameras.
- Dataset: 34 objects, 6800 grasp evaluations, 1.1M measurements.

## Result that matters

The dataset and pipeline are the result; the sim-to-real section (Sec. VIII) is a pilot:

- Tofu, 3 grasps at 1 N and 2 N: sagging ordering matches; real fracture at 2 N occurs
  where simulated stress exceeds the literature breaking stress of about 3 kPa. FEM does
  not simulate fracture.
- Latex tubes, 3 grasps at 15 N: indentation shapes and vertical extent match. Under a
  90 degree rotation an end grasp sweeps the tube tip through 47 degrees versus 83 for a
  middle grasp, "closely" matching sim (sim numbers not printed).
- Bleach bottle, 5 grasps, volume change measured by filling with rice: ordering matches
  except one pair, explained by a 1 mm neck wall versus 0.85 mm base wall that the uniform
  wall model misses; the same error inflates the two hardest simulated grasps.
- Plastic cup, 4 grasps, filled with metal balls until contact loss: stability ordering
  matches; failure weights do not, because the real Franka has no precise force control.

From the 2021 appendix (Appendix F): on prisms and spheroids the feature with the highest
Gini importance for every metric is contact patch distance to centroid; grasps that squeeze
the ends of prisms, spheroids, and cylinders have the highest deformation controllability
and instability because they leave a long cantilever moment arm.

## What it changes in practice

- For a meat slab or fillet the transferable rule is the mechanics, not the dataset:
  stress concentrates where contact area is small and curvature changes, deformation is
  largest where geometric stiffness is lowest, and end grasps let the free length sag. See
  `library/topics/deformable-object-manipulation.md`.
- The pipeline can score a candidate gripper geometry on a scanned object before printing
  it, given a plausible modulus. Homogeneous isotropic material is a hard limit of the
  simulator; layered tissue (skin over fat over muscle) is outside it.
- Material parameters were not tuned to the real objects (2021 version, Sec. IV); the
  pilot shows ordering agreement under literature moduli, which is the field situation.

## Known limitations and follow-ups

- No fracture, plasticity, anisotropy, or wall-thickness variation. Sim-to-real is 4
  objects and 15 grasps total.
- DefGraspNets (arXiv 2303.16138) learns a GNN surrogate on this data, "up to 1500 times
  faster than the FEM simulator" (quoted via the deformables topic note).

## Open questions

- The RA-L text drops the 2021 feature-importance study (random forest on top and bottom
  30th percentiles); no reason is given.
- 2 to 7 min per grasp was 2022 Isaac Gym; no timing for current PhysX FEM is in this
  library (unverified).

## Sources

- Paper: https://arxiv.org/abs/2203.11274 (v1, 21 Mar 2022). Sec. III to VI, VIII; Table
  I, II; Fig. 9 to 14.
- Earlier version with appendices: https://arxiv.org/abs/2107.05778 (v1). Sec. II, IV;
  Appendix B, E, F.
- Code and dataset: https://github.com/NVlabs/DefGraspSim ; https://sites.google.com/nvidia.com/defgraspsim
