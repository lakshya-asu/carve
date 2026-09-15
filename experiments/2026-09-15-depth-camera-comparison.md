---
title: Overhead depth camera, Orbbec Gemini 335L against RealSense D455, in simulation
date: 2026-09-15
tags: [experiment, meat-cell, perception, depth-camera, simulation]
status: reviewed
decision: which RGB-D camera the cell models first and specifies for the bench test on real legs
---

# Experiment: depth-camera-comparison

Written before any run, per the [experiment protocol](../sops/experiment-protocol.md). Chosen by
Lakshya on 2026-09-15: model both cameras and compare them on the same legs before choosing.

## Hypothesis

H1. Mounted 950 mm above the belt, both cameras see the whole belt width and every leg of the
20-leg population completely, at every arrival pose in the set below.

H2. On the leg's upper surface, the two cameras' depth errors differ by less than 10 percent,
because their baselines are equal (95 mm) and their focal lengths differ by 7 percent
(computed from the datasheet fields of view: Gemini 335L 640 px, D455 686 px across).

H3. The number of depth pixels on the shank, where the gripper closes and where the hock is
found, differs between the cameras by less than 15 percent.

If H2 and H3 hold, the choice is made on the plant's terms: washdown rating (Gemini 335L is IP65,
the D455 has none), hardware sync, and price.

## Decision this informs

Which camera the simulated cell uses as its overhead depth sensor from now on, and which one is
ordered for the bench test on real legs, where the simulation's noise model gets checked.

## Setup

- Git SHA: filled at run start.
- Simulator: MuJoCo 3.12.0, `applications.pork_leg_alignment.sim` (was `meat_cell_sim`), timestep 2 ms.
- Cameras, modelled in `src/robotics/hardware/cameras.py` from datasheet fields:
  - Orbbec Gemini 335L: depth 1280 x 800, 90 x 65 deg, 30 fps, range 0.17 to 20 m, 95 mm baseline
    ([Orbbec](https://www.orbbec.com/products/stereo-vision-camera/gemini-335l/)).
  - RealSense D455: depth 1280 x 720, 86 x 57 deg, up to 90 fps, range 0.6 to 6 m
    ([Intel](https://www.intel.com/content/www/us/en/products/sku/205847/intel-realsense-depth-camera-d455/specifications.html));
    95 mm baseline from the library's hardware note.
- Mount: both at the existing overhead position, 950 mm above the belt, looking straight down,
  image height across the belt. Two real cameras cannot share one position; in simulation this
  removes mounting as a variable.
- Depth noise model (the same for both, from each camera's own geometry): Intel's triangulation
  model, RMS = Z^2 x subpixel / (focal length px x baseline), subpixel 0.08 px, independent
  Gaussian per pixel; depth rounded to 1 mm; zero outside the camera's range; zero where the
  colour image is saturated white (specular). Assumptions, flagged: subpixel 0.08 is Intel's
  typical figure for a textured target and is applied to the Orbbec camera too; measured noise
  on a white wall runs 3 to 5 times this floor
  (`library/topics/depth-primary-segmentation.md`, section 2); real stereo noise is spatially
  correlated and has no published model on meat.
- Legs: `leg_population(20, seed=0)`. Arrival poses per leg: leg centre at x = -0.40 m (under
  the camera), y in {0.40, 0.50, 0.60} m, yaw in {-35, 0, +35} deg about square, belt at 0.30 m/s:
  9 poses, 180 frames per camera. Noise seed 20260915.

## What is measured, per camera

- Legs completely inside the image (mask not touching the border): count of 180.
- Belt-plane depth error: RMS against the rendered truth over belt pixels, mm.
- Leg upper-surface depth error: RMS and 95th percentile against truth over leg pixels, mm.
- Valid depth on the leg: share of leg pixels with a return.
- Pixels on the shank (the 0.55 to 0.76 span of the leg length) and on the whole leg, median.
- Ground sampling distance at the belt, mm per pixel (computed).

## Evaluation protocol

- Truth is the simulator's noiseless depth render and segmentation mask for the same frame.
- No perception algorithm runs in this experiment. It measures what each camera delivers to
  perception; the hock keypoint step is the next experiment and uses the chosen camera.
- Reported as a table per camera, with all 180 frames per camera, medians and 95th percentiles.

## Results

Run 2026-09-15, `scripts/measure/depth_cameras.py`, 20 legs × 9 poses per camera, raw rows in
`data/2026-09-15-depth-cameras.json`. A one-leg smoke run first exposed a placement bug in the
script (the leg's outline offset was applied along x instead of along the leg), so every leg sat
160 mm toward the open edge; it was fixed before this run, and the smoke numbers are discarded.

| Camera | Legs fully in view | Belt depth RMS mm | Leg depth RMS mm (median, p95 over frames) | Leg depth p95 mm (median) | Valid depth on leg (median) | Leg px (median) | Shank px (median) | mm/px at belt |
|---|---|---|---|---|---|---|---|---|
| Orbbec Gemini 335L | 158/180 | 1.22 | 0.94, 1.00 | 1.84 | 81.9% | 52,482 | 7,531 | 1.48 |
| RealSense D455 | 140/180 | 1.14 | 0.88, 0.94 | 1.73 | 81.7% | 58,818 | 8,037 | 1.38 |

- H1 fails for both cameras. Clipped frames: Gemini 22 (y 0.60: 18, y 0.50 square: 4); D455 40
  (y 0.60: 33, y 0.50 square: 6, y 0.40 square: 1). With the image's short axis across the belt,
  the vertical field at the leg's upper surface (about 120 mm above the belt) spans about
  ±0.52 m on the Gemini and ±0.45 m on the D455 around y = 0.50. A 700 to 815 mm leg lying across
  the belt centred at y 0.60 reaches past that, and past the far rail at y 0.857, so part of this
  pose set is not physically reachable.
- H2 holds: leg depth RMS differs by 6 percent, in line with the 7 percent focal length difference.
  Both cameras measure within 3 percent of the noise model, which is expected: the model is what
  generated the noise.
- H3 holds: shank pixels differ by 6 percent.
- Valid depth on the leg is 82 percent for both, and the loss is entirely the specular term firing
  on MuJoCo's rendered highlights on the pale leg (diagnostic on leg 0: 3 to 14 percent of leg
  pixels saturated, none lost to range). It does not separate the cameras and says nothing about
  wet meat.
- Found on viewing the video, after the run: the same term also deletes depth across most of the
  white belt, because the cell's lighting renders the belt at full white. The belt depth error in
  the table is therefore measured only on the belt's unsaturated outer band. Those pixels are still
  valid samples of the noise model, but the valid-depth figures are a rendering artefact, not a
  camera property. The specular term needs a physical basis (the surface's material, not rendered
  saturation) before it is used again, and the cell's lighting overexposes, which also affects any
  colour-based perception measured in this scene.

Follow-up, not pre-registered: the same run with both cameras turned 90 degrees on the mount, so
the long image axis lies across the belt (`--mount-yaw-deg 90`, raw rows in
`data/2026-09-15-depth-cameras-mount-yaw-90.json`).

| Camera, long side across the belt | Legs fully in view | Leg depth RMS mm (median) | Valid on leg (median) | Leg px (median) | Shank px (median) |
|---|---|---|---|---|---|
| Orbbec Gemini 335L | 158/180 | 0.93 | 82.3% | 54,890 | 7,932 |
| RealSense D455 | 157/180 | 0.88 | 81.4% | 61,777 | 8,971 |

The D455's clipped frames fell from 40 to 23; the Gemini's stayed at 22. Every remaining clipped
frame on both cameras is at y 0.60 with yaw ±35 degrees (21 and 22) or y 0.50 square (1 each).
Diagnostic on leg 0 at y 0.60, 0.2 s after placement: at yaw ±35 degrees the placement put the
ham butt at y 0.903 m, through the far rail's inner face at 0.857 m, and the contact threw the leg
off the belt (body 1.3 to 2.1 m above the belt, tilted 66 and 88 degrees); at yaw 0 the butt rested
on the rail at y 0.970 m, tilted 4 degrees. Those frames are placement failures in the test harness,
not field-of-view limits. With the long side across the belt, no physically placed leg left the
image on either camera. The pose set must be clamped to legs that fit between the rail and the
open edge before this measurement is used again.

## Proposed decision, for Lakshya

H2 and H3 hold, so by this record's rule the choice falls to the plant's terms: the Gemini 335L,
for IP65 and hardware sync across cameras. Mount it with the long image axis across the belt; the
follow-up shows that mounting removes field-of-view clipping for both cameras, so the D455's
narrower field is not a reason on its own. Noise does not decide it (6 percent apart, both from
the datasheet model), and the real decider on wet meat, dropout and noise on the product, can only
come from the bench test.

## Decision taken and why

2026-09-15: Lakshya signed off the Orbbec Gemini 335L, mounted 950 mm above the belt with the image's long
side across it, "for now". Reasons on record: depth noise within 6 percent of the D455, every leg
that fits the belt in view with the long side across, IP65 washdown and hardware sync. The choice is
revisited when a bench test on wet meat measures real noise and dropout.

## Caveats

- The noise model is a datasheet-derived floor, not a measurement. The bench test on real legs
  replaces it.
- Rendered colour has no real specular behaviour of wet meat, so the specular dropout term only
  fires where MuJoCo's lighting saturates the image.
- IR interference, auto-exposure, rolling effects and USB timing are not modelled.
