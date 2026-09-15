---
title: Segmenting a whole pork leg from the overhead depth camera on a moving belt
date: 2026-09-15
tags: [experiment, meat-cell, perception, segmentation, depth-camera, simulation]
status: reviewed
decision: whether depth-height segmentation is accurate enough to feed the centre-of-gravity, grasp-point and intercept steps, or a learned or appearance-based stage is needed
---

# Experiment: leg-segmentation

Written before any run, per the [experiment protocol](../sops/experiment-protocol.md). Pipeline
step 1, chosen by Lakshya on 2026-09-15: segment the leg first, then the centre of gravity
(geometry baseline, then learned), then grasp point and intercept.

## Hypothesis

H1. A leg on the belt stands at least 25 mm above it everywhere except its rounded lower edges, so
cutting at 10 mm above an empty-belt reference finds every leg, one mask each, with no refusals, on
all 20 legs and all poses below.

H2. The depth mask misses a thin band around the leg where the rounded side drops below the 10 mm
cut, so recall is below precision. Intersection over union is at least 0.93 and precision at least
0.98.

H3. The mask centroid, projected onto the belt plane, lies within 3 mm of the true silhouette's
centroid, because the missing band is roughly symmetric.

## Decision this informs

Whether the centre-of-gravity estimator (step 2) can read its input from this mask, or whether a
boundary refinement or a learned segmenter must come first. Proposed gate, for Lakshya to set:
IoU at least 0.93, centroid within 3 mm, no refusals on single legs.

## Setup

- Git SHA: filled at run start.
- Simulator: MuJoCo 3.12.0, `meat_cell_sim`, timestep 2 ms, belt 0.30 m/s.
- Arm: UR20 at the far-side mount with the jaw gripper, at home, as in the alignment experiment.
- Camera: Orbbec Gemini 335L model (`src/meat_cell_sim/cameras.py`), 950 mm above the belt, long
  image side across the belt (mount yaw 90 degrees), the choice proposed in
  `2026-09-15-depth-camera-comparison.md`. Depth noise from the datasheet model, no glare term.
- Empty-belt reference: the mean of 10 noisy frames of the belt with the leg out of view.
- Legs: `leg_population(20, seed=0)`, trotter toward the open edge. Poses per leg: yaw in
  {-35, 0, +35} degrees about square, and three cross-belt placements: the leg's far end 20 mm,
  70 mm and 120 mm from the far rail's inner face (y 0.857 m), computed from each leg's length and
  width so no leg touches the rail. Nine poses, 180 frames, captured when the leg's outline centre
  passes under the camera (x -0.40 m). Noise seed 20260915.

## Method under test

`src/meat_cell_sim/leg_segmentation.py`: height above the empty-belt reference; keep pixels
between 10 mm and 300 mm (the far rail stands 90 mm but lies outside the belt region; the arm
stands taller than 300 mm when over the belt); keep only the belt region, which runs from 150 mm
past the open edge (the overhanging trotter) to 10 mm short of the far rail; close gaps; keep the
largest connected piece; refuse if it touches the image border or is smaller than 5,000 px.

## What is measured

Per frame: accepted or refused with the reason; IoU, boundary F1 at 2 px, precision and recall
against the simulator's silhouette; mask centroid error on the belt plane, mm; area ratio; time
per frame, ms. Reported per yaw and per placement, medians and worst case over 180 frames.

## Pre-registered addition: learned segmenter against geometry

Added 2026-09-15 before any training, at Lakshya's request that every step compares a geometric
and a learned method, including what the learned one costs to run.

- Model: a small U-Net (`src/meat_cell_sim/learned_segmentation.py`), input colour plus depth at
  320 × 200, output a leg probability per pixel, thresholded at 0.5 and upsampled; the same
  post-processing as the geometric method (largest piece, refuse on empty or border).
- Training data: `leg_population(100, seed=1)`, a different population from the 20 test legs
  (seed 0); 10 frames per leg at random feasible poses (yaw ±40 degrees, far end 10 to 150 mm from
  the rail, anywhere under the camera) plus one empty-belt frame per leg; the same Gemini 335L noise
  model; validation on the last 10 training legs.
- Test: the same 180 frames and metrics as above, same noise seed.
- Compute: milliseconds per frame on this machine's 12-core CPU for both methods, and the
  combination (geometry mask intersected with the learned mask, and the union).
- Decision rule: the learned segmenter is kept only if it beats geometry by at least 0.01 IoU median
  or 1 mm centroid median with no extra refusals; otherwise geometry stays and learning waits for
  real data, where appearance and wet-surface depth loss may change the answer.

## Results

Three runs of `scripts/measure_leg_segmentation.py`, each on the full 180 frames. Two exposed
defects in the segmenter; the third is the result.

**Run 1** (raw rows `data/2026-09-15-leg-segmentation-run1.json`). All 180 accepted, precision
1.000, but recall fell with distance from the rail: 0.999 at a 20 mm gap, 0.972 at 70 mm, 0.934 at
120 mm; centroid error median 11.1 mm, worst 49.6 mm (leg 15, square, 120 mm gap). Diagnostic on
the worst frame: all 8,139 missed pixels were dropped by the 300 mm height ceiling. Past the open
edge the empty-belt reference sees the floor, so the overhanging trotter measured 0.99 m above its
reference. Some missed pixels lay up to 40 mm inside the edge, because their rays graze past the
belt to the floor; 538 also lay past the region's 0.0 m limit.

**Run 2**, after the first fix (height against a fitted belt plane where the reference did not see
the belt; region widened to 300 mm past the edge): all 180 refused, "nothing above the belt". The
plane fit found the floor (normal up, offset 0, 54 percent inliers): with the long image side
across the belt, the floor either side fills more of the view than the 700 mm belt. The data file
from this run was overwritten; the table above is the evidence. Fixed by fitting only inside the
belt; a test now checks that the fitted plane is the belt surface.

**Run 3** (raw rows `data/2026-09-15-leg-segmentation.json`):

| Group | Frames | Accepted | IoU median (worst) | Boundary F1 | Precision | Recall | Centroid error mm median (worst) | ms median (worst) |
|---|---|---|---|---|---|---|---|---|
| all | 180 | 180 | 1.000 (1.000) | 1.000 (1.000) | 1.000 (1.000) | 1.000 (1.000) | 0.003 (0.011) | 96.5 (190.5) |

Every yaw and rail-gap group is the same to three decimals. Checked for a scoring bug on leg 15
(square, trotter well past the edge): the found and true masks differ by 2 of 67,526 pixels; the
true height at the silhouette boundary is at least 28.5 mm (5th percentile 50.7 mm, median
104.3 mm); no leg pixel lies between 5 and 15 mm; pixels just outside are belt at 0 mm.

- H1 holds: every leg found, one mask each, no refusals.
- H2 is rejected. There is no thin missed band: seen from above, a leg's outline is its widest
  part, well above the belt, so a 10 mm cut has at least 18 mm of margin against 1 mm of noise.
- H3 holds, trivially.
- This is an upper bound, not a camera result. MuJoCo renders a perfectly sharp depth step at the
  silhouette; real active stereo spreads the edge by about a pixel and mixes near and far depth
  there, which the camera model does not yet include.
- Time per frame, 96.5 ms median on this machine's CPU (worst 190.5 ms while other jobs ran), is
  over the 33 ms a 30 fps camera allows; the full-resolution float operations are the cost and have
  not been optimised.
- Test cell defect found on the way: the default UR5e's near-side pedestal stands inside the strip
  past the open edge and was found as "leg" on an empty belt. The tests now use the experiment's
  UR20 behind the far rail, and the belt region's documentation says the strip must be clear.

**Run 4, with edge effects** (raw rows `data/2026-09-15-leg-segmentation-edges.json`). Run 3
was exact because the renderer's depth edge is sharp, so the camera model gained the three edge
artefacts in `EdgeEffects` (`src/meat_cell_sim/cameras.py`): about 1 px of sideways jitter near
outlines (a D435 below 0.7 m, Halmetschlager-Funek et al., IEEE RAM 2019, Table 2), a ±2 px band
where half the pixels report the near depth, the far depth or a blend (assumed), and no return
past 75 degrees incidence (the end of Fankhauser et al.'s ICAR 2015 fit; the cut-off assumed).
Same legs, poses and noise seed.

| Group | Frames | Accepted | IoU median (worst) | Boundary F1 | Precision | Recall | Centroid error mm median (worst) | ms median (worst) |
|---|---|---|---|---|---|---|---|---|
| all | 180 | 180 | 0.967 (0.955) | 0.998 (0.992) | 0.967 (0.955) | 1.000 (0.999) | 1.08 (2.38) | 217 (382) |

Yaw and rail-gap groups agree within 0.003 IoU and 0.23 mm centroid median.

- The mask grows outward. Recall stays at 1.000 and precision drops to 0.967: belt pixels just
  outside the outline take the leg's near depth, stand above the 10 mm cut and join the mask.
- Centroid error rises from 0.003 mm to 1.08 mm median, 2.38 mm worst: still inside the 3 mm gate.
- The time is not comparable with run 3: the U-Net training and Segment Anything ran on the same
  CPU during this run.

**Learned segmenter, training** (log `outputs/checkpoints/legunet-simlegs100-8f953aa.json`, not
committed). 482,881 parameters; 990 training frames from 90 legs, 110 validation frames from 10;
data seed 20260916, training seed 1; datasheet noise, no edge effects. 15 epochs in 3,290 s on 6 CPU
threads while other jobs ran. Validation IoU 0.966 after epoch 1, 0.991 after 4, 0.9998 after 15;
best and last checkpoint `legunet-simlegs100-8f953aa-930.pt`. A duplicate of this training ran for
its first half and was stopped; it wrote the same file names from the same data and seeds.

**Learned segmenter against geometry** (`scripts/compare_leg_segmenters.py`, raw rows
`data/2026-09-15-leg-segmenter-comparison-legunet-simlegs100-8f953aa-930[-edges].json`). Same 180
frames and noise seed; U-Net on 6 CPU threads while another training job ran.

| Camera model | Method | IoU median (worst) | Precision | Recall | Boundary F1 | Centroid mm median (worst) | ms median |
|---|---|---|---|---|---|---|---|
| noise | geometry | 1.000 (1.000) | 1.000 | 1.000 | 1.000 | 0.00 (0.01) | 110.6 |
| noise | learned | 0.968 (0.948) | 0.984 | 0.984 | 0.833 | 3.02 (4.28) | 131.5 |
| noise | both, AND | 0.984 (0.972) | 1.000 | 0.984 | 0.911 | 2.10 (2.69) | sum |
| noise | both, OR | 0.984 (0.975) | 0.984 | 1.000 | 0.926 | 1.60 (3.55) | sum |
| noise + edges | geometry | 0.967 (0.955) | 0.967 | 1.000 | 0.998 | 1.08 (2.38) | 116.1 |
| noise + edges | learned | 0.967 (0.946) | 0.983 | 0.983 | 0.816 | 3.06 (4.07) | 133.3 |
| noise + edges | both, AND | 0.972 (0.954) | 0.988 | 0.983 | 0.907 | 2.85 (3.79) | sum |
| noise + edges | both, OR | 0.963 (0.948) | 0.963 | 1.000 | 0.917 | 1.59 (3.20) | sum |

All 180 frames accepted by every method. Accepted all round, the learned model is 0.032 IoU and
3 mm worse than geometry on clean frames and level on IoU, 2 mm worse on centroid, with edges.

- Defect found: validation IoU was 0.9998 but test 0.968 with a near-constant 3 mm centroid error.
  `mask_to_target` shrank labels with nearest-neighbour sampling, which takes each 4 x 4 block's
  top-left pixel; the segmenter grows its output back centre-aligned. Measured on a synthetic
  ellipse: the label round trip moved the mask 1.54 px right and 1.50 px down (IoU 0.983 against
  the original); with area shrinking, 0.04 px (IoU 0.998). 1.5 px diagonal at 1.48 mm/px is 3.1 mm.
  The depth input had the same offset against the colour input. Both fixed with area resizing
  (dropout-aware for depth), with tests; the edge-effect training in progress was stopped because
  it used the same labels.
- Decision by the pre-registered rule for this checkpoint: not kept; geometry stays. The AND
  combination on edge frames (+0.005 IoU) is under the 0.01 bar. The rule is applied again to the
  models retrained on corrected labels.
- Both methods are over the 33 ms a 30 fps camera allows on this CPU; neither is optimised.

**Retrained on corrected labels** (both models from commit fd5ecb5, 15 epochs each on 6 CPU
threads, trained side by side: validation IoU 0.9982 in 3,130 s without edge effects, 0.9978 in
3,368 s with them; raw rows
`data/2026-09-15-leg-segmenter-comparison-legunet-simlegs100[edges]-fd5ecb5-930[-edges].json`):

| Camera model | Training frames | Method | IoU median (worst) | Precision | Recall | Centroid mm median (worst) | ms median |
|---|---|---|---|---|---|---|---|
| noise | noise | geometry | 1.000 (1.000) | 1.000 | 1.000 | 0.00 (0.01) | 95 |
| noise | noise | U-Net | 0.984 (0.976) | 0.991 | 0.994 | 0.58 (2.42) | 132 |
| noise | noise | both, AND | 0.994 (0.990) | 1.000 | 0.994 | 0.31 (0.88) | sum |
| noise + edges | noise | geometry | 0.967 (0.955) | 0.967 | 1.000 | 1.08 (2.38) | 93 |
| noise + edges | noise | U-Net | 0.984 (0.976) | 0.991 | 0.994 | 0.63 (2.98) | 132 |
| noise + edges | noise | both, AND | 0.985 (0.978) | 0.991 | 0.994 | 0.29 (1.48) | sum |
| noise + edges | noise + edges | U-Net | 0.984 (0.976) | 0.991 | 0.994 | 0.64 (2.71) | 129 |
| noise + edges | noise + edges | both, AND | 0.985 (0.978) | 0.991 | 0.994 | 0.32 (1.62) | sum |

All 180 frames accepted by every method.

- The label fix removed the constant offset: centroid error 3.02 mm before, 0.58 mm after, on the
  same frames.
- Decision by the pre-registered rule on the idealised camera: not kept; geometry is exact there.
- Decision by the rule on the camera with edge effects: kept. The U-Net beats geometry by 0.017 IoU
  median (0.984 against 0.967) with no extra refusals. The AND combination is best on the centre,
  0.3 mm, so the cell uses the U-Net's mask checked by geometry, with geometry running every frame.
- Training on edge-effect frames changed nothing measurable (0.984 IoU either way).
- The edge effects are a model with assumed band width and cut-off; the decision is re-taken on the
  real camera.
- Cost on this CPU under load: geometry 93 to 105 ms, U-Net about 130 ms, both about 230 ms,
  against 33 ms at 30 fps. Speed is the next piece of work on this step.

## Addition: real plant footage

Added 2026-09-15 at Lakshya's request to test segmentation on the real line, where a learned
method is expected to matter more than in simulation. The clips are phone video (IMG_1005,
IMG_1008 in `field-notes/customer/meat-men/`, not committed), so there is colour and no depth and
the depth-height segmenter cannot run.

- Frames: 21, one every 2 s (IMG_1005: 8, IMG_1008: 13), 720 × 1280 portrait.
- Deterministic: a Lab colour rule sampled on two of the frames (meat a* 135 to 157, b* 144 to
  157; belt, shadow, steel and gloves outside it), opened and closed, one instance per connected
  piece (`scripts/segment_real_footage.py`).
- Learned proposals, deterministic decision: Segment Anything ViT-B (Kirillov et al. 2023,
  arXiv 2304.02643) automatic masks, 16 × 16 prompt points; a region is kept when at least 60
  percent of it passes the same colour rule, and a region mostly inside a kept one is dropped.
- No hand-drawn masks exist, so scoring is by eye from the side-by-side overlays, per frame: legs
  lying on the belt and wholly or mostly in view; for each method, how many of those come out as
  one complete, separate piece; merges (two legs in one piece); splits (one leg in several pieces);
  false pieces (anything that is not a leg on the belt). Time per frame on this 12-core CPU.
- A known bias: the colour rule was tuned on two of these same frames.

### Results, real footage

Graded by eye by Claude on 2026-09-15; per-frame grades and times in
`data/2026-09-15-real-footage-grades.json`.

| Method | Legs whole and separate | Pieces holding 2+ legs | Legs cut into parts | Legs not found | False pieces | Time per frame |
|---|---|---|---|---|---|---|
| Colour rule | 14 / 55 | 15 | 10 | 0 | 1 | 27 ms median (16 to 252) |
| SAM ViT-B + colour rule | 36 / 55 | 1 | 10 | 7 | 0 | 61.4 s median (52.9 to 85.9) |

By clip: IMG_1005 (8 frames, 18 legs) colour 7, SAM + colour 14; IMG_1008 (13 frames, 37 legs)
colour 7, SAM + colour 22. Times on the 12-core CPU with 6 torch threads, while U-Net training
ran; the SAM figure is not a clean measurement but is three orders of magnitude over budget
either way.

- Touching legs decide it. The colour rule cannot separate connected meat-coloured regions; SAM
  proposes the boundary between them.
- SAM cuts legs where a glove, shadow or blur crosses the shank (10 legs, 9 in IMG_1008).
- 6 of the 7 lost legs are in IMG_1008 with lean red faces up. Diagnostic on IMG_1008-t003: SAM
  proposed both legs whole, and only 44 and 37 percent of their pixels pass the colour rule, under
  the 60 percent keep threshold, so the deterministic step discarded them. On IMG_1008-t013 SAM did
  not propose the leg as one region.
- SAM cannot run in the cell on CPU. Proposed next test, not run: SAM as an offline labeller on
  real frames, distilled into the small U-Net; re-sample the colour rule on both clips.

## Decision taken and why

On the camera model with edge effects, the U-Net retrained on corrected labels passes the
pre-registered rule (0.984 against 0.967 IoU median, no extra refusals) and is kept, its mask
checked by the geometric one (0.985 IoU, 0.3 mm centroid), with geometry running every frame as
the monitor. On the idealised camera geometry is exact and would stay. Both are re-decided on the
real camera, whose edge behaviour the model only assumes.

## Caveats

- One leg at a time. Touching legs, the normal state in IMG_1008, are a separate sub-step that
  needs a second leg in the scene.
- The noise model is the datasheet floor, with no glare or flying pixels at edges; real depth on
  wet meat will lose edge pixels this run does not.
- The silhouette used as truth is the rendered skin, which is the drawn shape, not a physical
  tolerance.
