---
title: Where a pork leg's centre of gravity is, from the overhead depth camera
date: 2026-09-15
tags: [experiment, meat-cell, perception, centre-of-gravity, depth-camera, simulation]
status: reviewed
decision: whether the turn and grip skills can take the centre of gravity from depth geometry, or need a learned correction
---

# Experiment: centre-of-gravity

Written before any run, per the [experiment protocol](../sops/experiment-protocol.md). Pipeline
step 2, in the order Lakshya set on 2026-09-15: segment the leg, then the centre of gravity
(geometry baseline, then learned), then grasp point and intercept. Input comes from step 1,
[[2026-09-15-leg-segmentation]].

## Why this point

Turning a leg on the belt is planned about its centre of gravity, and a grip has to hold against
the moment the leg's weight makes about the grip. The outline's centre is not that point: a leg's
area runs down a slender hock and trotter that carry little of its mass (`product.py`
docstring). The camera sees only the top surface, so any estimate has to assume something about
what is underneath.

## Hypotheses

H1. The silhouette centroid (every leg pixel dropped onto the belt, weighted by its footprint) lies
at least 15 mm from the true centre of mass on the median frame, and the error runs along the leg
toward the trotter.

H2. The column centroid (every leg pixel a solid column from the belt up to the seen surface,
volume-weighted) lies within 5 mm on the median frame and 10 mm worst, with a remaining bias along
the leg toward the trotter. Reason: under the rounded sides and under the trotter, which lifts clear
of the belt, the columns are partly air, and the rounder cross sections sit toward the trotter.

H3. Feeding the mask from the geometric segmenter instead of the true silhouette, with the camera's
edge effects on, moves the column centroid's median error by under 2 mm.

## Decision this informs

Whether the orient and grip skills read the centre of gravity from the column centroid directly, or
a learned correction comes first. Proposed gate, for Lakshya to set: 5 mm median and 10 mm worst on
the belt plane (assumed; the plant has not given a tolerance, and no measurement yet ties a
centre-of-gravity error to a failed turn).

Gate set by Lakshya on 2026-09-15, after the results: 10 mm worst on the belt plane. The column
centroid alone misses it (15.7 mm worst); the column centroid with the learned offset meets it
(4.6 mm worst, 4.2 with edge effects).

## Setup

- Git SHA: filled at run start.
- Cell, camera, legs and poses exactly as the leg-segmentation experiment: MuJoCo 3.12.0, belt
  0.30 m/s, UR20 at the far mount with the jaw gripper, Gemini 335L model 950 mm up with the long
  side across the belt, `leg_population(20, seed=0)`, yaw {-35, 0, +35} degrees, far end 20, 70 and
  120 mm from the rail; 180 frames; noise seed 20260915; empty-belt reference of 10 frames.
- Truth: the mass-weighted mean of the ham body's and the trotter body's centres of mass as MuJoCo
  computes them from the meshes (uniform density: mass is split between the parts by volume).
  Scoring only; added to `GroundTruth` as `centre_of_mass_m`.

## Methods under test

`src/robotics/perception/centre_of_gravity.py`, both taking a mask, a depth frame and the belt plane from
the empty-belt reference:

- `silhouette_centroid`: footprint-weighted mean of the leg pixels dropped onto the belt plane.
- `column_centroid`: volume-weighted mean of the columns' centres. A pixel's footprint on the belt
  is depth² / (fx fy |d · n|), with d the pixel ray scaled to unit length along the optical axis and
  n the belt normal. Pixels without depth are left out.

Each is run on four inputs per frame: true silhouette or geometric segmenter mask, and datasheet
noise or noise plus edge effects.

## What is measured

Per frame and input: error on the belt plane between estimate and truth, mm, split into along the
leg (positive toward the trotter) and across it; height error, mm; estimated volume, litres; time
per frame, ms. Reported as medians and worst over the 180 frames, per yaw and per rail gap.

## Pre-registered follow-up: learned correction

Only after the geometric result is recorded. A small model trained on simulated legs from
`leg_population(100, seed=1)` (never the 20 test legs) predicts the offset from the column
centroid to the true centre of mass from the masked height map. Decision rule, written now: the
correction is kept only if it cuts the median error on the belt plane by at least 1 mm without
making the worst frame worse, on the same 180 frames, with its time per frame reported next to the
geometric method's.

Design details fixed on 2026-09-15 after the geometric result and before any training
(`src/robotics/perception/learned_centre_of_gravity.py`, `scripts/train/centre_correction.py`,
`scripts/measure/compare_centre_correction.py`):

- Input: the seen surface resampled onto 96 × 96 cells of 10 mm on the belt, centred on the column
  centroid, plus the column centroid's position relative to the camera. The second input is added
  because the geometric error grew with pose, which points at viewing angle.
- Training frames: 10 per leg at random feasible poses, datasheet noise or edge effects chosen at
  random, masks from the geometric segmenter (the cell's real input). Data seed 20260917, training
  seed 1. Target: true centre of mass minus the column centroid, mm on the belt.
- Model: four convolution blocks to 6 × 6, then two dense layers; smooth-L1 loss; AdamW; the
  checkpoint with the lowest validation median error over 60 epochs is the one tested.
- Test: the 180 frames with the segmenter's mask, both camera models, compared against the column
  centroid on the same frames.

## Results

Run 2026-09-15 at commit 392593c (raw rows `data/2026-09-15-centre-of-gravity.json`, 1,440 rows:
180 frames × 2 camera models × 2 masks × 2 methods). Every frame was accepted by the segmenter.
Two U-Net trainings shared the 12-core CPU during the run.

| Camera model | Mask | Method | Error on belt plane, mm median (worst) | Along leg, toward trotter | Across | Height | Volume, l | ms |
|---|---|---|---|---|---|---|---|---|
| noise | true | outline centre | 39.6 (57.9) | +39.3 | -2.8 | -68.0 | | 19.1 |
| noise | true | column centroid | 7.9 (15.7) | +7.2 | -2.7 | -2.4 | 11.9 | 19.6 |
| noise | segmented | outline centre | 39.6 (57.9) | +39.3 | -2.8 | -68.0 | | 19.1 |
| noise | segmented | column centroid | 7.9 (15.7) | +7.2 | -2.7 | -2.4 | 11.9 | 19.6 |
| edges | true | outline centre | 43.1 (61.2) | +42.8 | -2.5 | -73.5 | | 19.4 |
| edges | true | column centroid | 7.6 (16.3) | +6.8 | -2.8 | -2.2 | 11.8 | 19.1 |
| edges | segmented | outline centre | 44.8 (64.4) | +44.6 | -2.3 | -74.6 | | 18.7 |
| edges | segmented | column centroid | 7.7 (16.3) | +6.9 | -2.7 | -2.5 | 11.9 | 18.5 |

Column centroid, true mask, datasheet noise, by pose: yaw -35 degrees 10.6 mm (along +8.9), 0 degrees
7.2 (+6.8), +35 degrees 5.9 (+5.8); far end 20 mm from the rail 9.8 (+9.6), 70 mm 7.4 (+7.1),
120 mm 5.2 (+4.4). The noise rows are identical for both masks because the segmenter's mask on
noise-only frames is the true silhouette to 2 pixels (leg-segmentation run 3).

- H1 holds: the outline centre is 39.6 mm off on the median frame, almost entirely along the leg
  toward the trotter.
- H2 is rejected against its numbers: 7.9 mm median and 15.7 mm worst, against 5 and 10. The
  direction holds, a +7.2 mm bias along the leg toward the trotter, and there is a consistent
  -2.7 mm across the leg that H2 did not predict.
- The error depends on pose: about twice as large at yaw -35 as at +35, and near the rail as far
  from it. A viewing-angle effect (the camera seeing one side of the leg and counting it as
  columns) would do that; not tested.
- H3 holds: the segmenter's mask with edge effects moves the median by under 0.3 mm.
- Cost: 19 ms per frame on this CPU under load, inside a 30 fps budget.

### Learned correction

Trained 2026-09-15 by `scripts/train/centre_correction.py` (log
`outputs/checkpoints/centrenet-simlegs100-84636eb.json`, not committed). 1,000 frames were rendered
from `leg_population(100, seed=1)`; the geometric segmenter refused 64 (legs running off the image
at the random poses), leaving 846 training and 90 validation frames. The offset to learn had a
median of 10.7 mm and a worst of 30.8 mm on those frames. 208,002 parameters, 60 epochs in 167 s on
4 CPU threads; validation median error 12.2 mm after epoch 1, 3.2 after 10, 1.30 at best (the
checkpoint tested, step 1566). The checkpoint's name carries commit 84636eb because the script reads
the commit after rendering and a commit landed in between; the training and model code are those
of commit 6adf1c4 and did not change in 84636eb.

Comparison on the 180 test frames (`scripts/measure/compare_centre_correction.py`, raw rows
`data/2026-09-15-centre-correction-centrenet-simlegs100-84636eb-1566.json`), segmenter's mask,
model on 4 CPU threads:

| Camera model | Method | Error on belt plane, mm median (worst) | Along leg, toward trotter | ms median |
|---|---|---|---|---|
| noise | column centroid | 7.9 (15.7) | +7.2 | 8.2 |
| noise | column centroid + learned offset | 1.2 (4.6) | +0.6 | 17.6 |
| edges | column centroid | 7.7 (16.3) | +6.9 | 8.4 |
| edges | column centroid + learned offset | 1.1 (4.2) | +0.3 | 18.1 |

Times include the column centroid; the correction adds about 10 ms. The column centroid's time
here (8 ms) is lower than in the geometric measurement (19 ms) because fewer jobs shared the CPU.

## Decision taken and why

The column centroid replaces the outline centre in every skill that needs the centre of gravity: it
is five times closer on the same frames at no extra cost. It does not meet the proposed 5 mm and
10 mm gate, and the error is a bias that depends on shape and pose rather than noise, so the
pre-registered learned correction runs next under the rule above. The gate itself is still
Lakshya's to set.

Learned correction: kept. The rule asked for at least 1 mm off the median without a worse worst
frame; it takes 6.7 mm off the median (7.9 to 1.2) and 11.1 mm off the worst (15.7 to 4.6), and the
same with edge effects, and it meets the proposed 5 mm and 10 mm gate. The skills read the column
centroid plus the learned offset; the column centroid is computed underneath every frame, so a
correction far outside the range it was trained on can be seen and refused. Still a uniform-density
simulated leg: a real ham's centre of mass needs weighed and balanced legs from the line.

## Caveats

- The simulated leg has uniform density. A real ham carries bone and fat unevenly, so a real
  centre of mass differs from its volume centre by an amount this experiment cannot measure; that
  needs weighed and balanced legs from the line.
- One leg at a time, stopped belt pose, the same limits as the segmentation experiment.
