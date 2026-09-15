---
title: Ingestion chain gates, sensing through tracking, on the rigid product
date: 2026-09-08
tags: [experiment, meat-cell, perception, sensing, tracking, simulation, mujoco]
status: complete
decision: whether the ingestion chain meets its gates, and whether depth is required
---

# Experiment: perception-ingestion

Records the build and measurement of four subsystems of the meat cell: the
sensor record, the camera geometry, pose from a mask, and prediction forward to
the meet instant. Written per [experiment protocol](../sops/experiment-protocol.md).
The chain and its reasoning are in
[perception ingestion](../library/topics/perception-ingestion.md).

## Question

Does the ingestion chain hold its pre-registered gates on the rigid product, and
is a depth sensor required or can a colour camera plus a plane assumption do the
job?

## Gates, pre-registered in the architecture note

Taken unchanged from [meat cell architecture](../library/topics/meat-cell-architecture.md),
written before this run:

| Step | Gate |
|---|---|
| Sensing | an observation's timestamp matches the simulation time of the state it describes, under 1 ms |
| Frames | a known ground-truth point reaches the base frame within 1 mm |
| Perception | centroid error under 2 mm and axis error under 2 degrees |
| Tracking | predicted position at the meet instant within 2 mm |

The 2 mm figure is ABB's published conveyor tracking error at 150 mm/s, used as
a calibration target for the chain and not as a claim about the simulator. The
customer's cutter infeed window replaces it once known.

## Method

`scripts/measure_perception.py`. For each belt speed, 15 products are spawned at
the upstream end of the belt with uniformly random heading and a 80 mm spread in
cross-belt position. Each product is observed at 30 frames per second through the
overhead camera at 1280 x 960 with a 4 ms exposure rendered as three sub-frames.

Each frame: the product's exact silhouette is taken from a segmentation render
and handed to the estimator, so this measures the geometry and the timing chain
and not the segmentation. Technique selection for the mask itself is the separate
bake-off in [perception technique selection](../library/topics/perception-technique-selection.md).

Observation stops when the product's mask first touches the image border, since
a clipped mask is rejected and no further usable frame exists. Prediction is then
made 0.5 s past the last usable observation, the simulator is advanced to exactly
that instant, and the prediction is compared against ground truth there.

Ground truth is a separate type from the sensor record. No estimator receives it.

## Conditions

- Product: rigid box, 180 x 90 x 30 mm, 0.5 kg, sliding friction 0.35. Assumptions
  pending customer numbers, cross-checked against
  [meat piece properties](../library/topics/meat-piece-properties.md).
- Belt speeds: 0.15, 0.30, 0.50 m/s. The middle value is the design point.
- Camera: overhead, 600 mm above the belt, 400 mm upstream of the pick zone,
  52 degree vertical field of view, 1280 x 960, 4 ms exposure.
- Simulator: MuJoCo 3.12.0, 2 ms timestep, EGL offscreen rendering.
- Seeds 0 to 14 per speed, replayable from the seed alone.

## Results

Raw table in `data/2026-09-08-ingestion.json`. Filled from the run of
2026-09-08.

45 products, 3007 usable frames.

| Belt speed | Products | Usable frames | Frames rejected |
|---|---|---|---|
| 0.15 m/s | 15 | 1682 | 191 |
| 0.30 m/s | 15 | 840 | 57 |
| 0.50 m/s | 15 | 485 | 30 |

Rejected frames are almost all the product running off the edge of the field of
view, which is the border guard doing its job. The count falls with speed simply
because a faster product spends fewer frames crossing the same edge.

| Metric | Gate | 0.15 m/s | 0.30 m/s | 0.50 m/s |
|---|---|---|---|---|
| Perception centroid, mean | 2 mm | 0.101 mm | 0.100 mm | 0.095 mm |
| Perception centroid, worst | 2 mm | 0.313 mm | 0.308 mm | 0.283 mm |
| Perception axis, mean | 2 deg | 0.007 deg | 0.007 deg | 0.008 deg |
| Perception axis, worst | 2 deg | 0.117 deg | 0.146 deg | 0.126 deg |
| Sensing stamp skew, worst | 1 ms | 0.000 ms | 0.000 ms | 0.000 ms |
| Tracking prediction, mean | 2 mm | 0.542 mm | 0.904 mm | 1.377 mm |
| Tracking prediction, worst | 2 mm | 0.584 mm | 0.964 mm | 1.436 mm |
| Monocular centroid, mean | none | 2.008 mm | 2.002 mm | 1.882 mm |
| Monocular centroid, worst | none | 6.471 mm | 6.564 mm | 6.440 mm |
| Belt-frame fit residual, mean | none | 0.004 mm | 0.005 mm | 0.009 mm |
| Encoder speed error | none | under 0.5 mm/s | under 0.5 mm/s | under 0.5 mm/s |
| Vision finite-difference speed error | none | under 0.5 mm/s | under 0.5 mm/s | under 0.5 mm/s |

The frames gate is measured separately as a round trip of a known point through
the camera and back, and returns under 0.001 mm. It is exact by construction in
simulation, which is the reason the hand-eye calibration step deliberately
injects an error rather than relying on this number.

Perception is flat in belt speed, as it should be: the estimate is made from one
exposure and does not care how fast the product is travelling. Tracking is not
flat, and that is the result below.

## Findings

1. **All four gates pass on the rigid product**, at every belt speed in the
   sweep. They did not on the first run: tracking failed at 0.50 m/s with
   2.03 mm mean against a 2 mm gate, and the cause is the seam defect described
   under "the phantom slip" below. The numbers above are after that fix.

2. **Depth is required.** Every monocular variant spends the whole 2 mm bound
   before the arm has moved. The cause is the product's thickness seen off-axis,
   not pixel resolution: ground sampling distance at the pick is 0.58 mm per
   pixel, and the bias comes from the silhouette centroid of a thick object not
   being the projection of any fixed point on it. The plane that would give a
   correct answer moves from 23.5 mm above the belt at 150 mm off axis to 0.2 mm
   at 300 mm off axis, so no single assumed plane serves the whole field.

3. **The belt-frame model holds to the fit residual.** The product is a constant
   in belt coordinates to well under a hundredth of a millimetre on a rigid
   product with no slip, which means the prediction error at the meet is set by
   the position estimate and the belt speed estimate, not by the motion model.

4. **The encoder beats differentiated vision by two orders of magnitude** as a
   velocity source, as the noise arithmetic predicts.

## The phantom slip: a spatial bias becoming a velocity error

The first run failed the tracking gate at 0.50 m/s and passed it at 0.15 and
0.30 m/s. The error was 0.978, 1.447 and 2.033 mm at the three speeds, which
fits 0.53 mm plus 3.0 mm per m/s. A term proportional to speed over a fixed
prediction horizon is a timing error, not a noise error, so the size of the
speed coefficient is a time: 3.0 ms.

Decomposing it: the error was entirely along the belt axis, cross-belt error was
0.06 mm, and the encoder's belt speed matched the product's true velocity to
better than 0.1 micrometres per second, so there was no real slip at all. Yet
the tracker's fitted slip was consistently negative and grew with belt speed:
-0.38, -0.75 and -1.16 mm/s. It was fitting a slide that was not happening.

The source was in perception. The signed position error, plotted against
position in the field of view rather than taken as a magnitude, was a ramp:
+0.29 mm at 180 mm before nadir, 0.000 mm at nadir, and -0.62 mm at 300 mm past
it. Selecting the product's upper surface by height alone keeps a strip of its
side wall as tall as the height band, and that strip always lies on the
camera-facing side. The bias scaled linearly with the band width, which is what
confirmed the mechanism.

**A position bias that varies with position in the image is converted by the
tracker into a velocity, with the belt speed as the conversion factor.** The
product sweeps across the field at belt speed, so a spatial ramp is
differentiated into an apparent slip, which is then extrapolated over the
prediction horizon. The measured ramp of -1.67 mm per metre of travel gives
-0.83 mm/s at 0.5 m/s, close to the -1.16 mm/s observed once the fit window's
position in the field is accounted for.

This is the case the typed contracts exist for. Perception passed its own gate
with room to spare, at 0.65 mm worst against 2 mm. The tracker's motion model
was exact, with a fit residual of 0.013 mm. Both subsystems were correct alone.
The defect lived only at the seam, and it was invisible in the error magnitude.

The fix rejects points by their surface normal rather than by height alone.
Normals come from central differences on the depth image, and the mask is eroded
by one pixel first so that every remaining pixel has four neighbours inside the
product, which also removes the silhouette depth artefacts described below.
Points are kept only where the normal is within 60 degrees of vertical.

| | Before | After |
|---|---|---|
| Bias ramp across the field | -1.67 mm/m | -0.74 mm/m |
| Worst signed bias | -0.62 mm | -0.17 mm |
| Phantom slip at 0.50 m/s | -1.16 mm/s | -0.37 mm/s |
| Perception centroid at 0.50 m/s, mean | 0.198 mm | 0.095 mm |
| Perception centroid at 0.50 m/s, worst | 0.655 mm | 0.283 mm |
| Tracking prediction at 0.50 m/s, mean | 2.033 mm, FAIL | 1.377 mm, PASS |

The second candidate fix, treating slip as a diagnostic that aborts the pick
rather than as something to extrapolate, was not needed and was not made. It
stays on the table for the deformable product, where the argument that slipping
is a transient rather than a steady state is stronger.

## Defects found while building

Seven, listed with sizes in the note's table. All seven produced plausible
numbers rather than errors. The seam defect above is one of them. Two others
would have survived into the field:

- `mj_step` leaves `sensordata` describing the state at the **start** of the
  step, so reading it straight after stepping returns values one timestep stale.
  Worth 0.6 mm at 300 mm/s and growing with line speed, which presents as a
  calibration error rather than a timing fault.
- A product partly outside the frame yields a clean mask and a confident centroid
  measured 9.8 mm wrong, with nothing else in the pipeline able to detect it.

## Caveats

- The mask is exact. Real segmentation error is not modelled here and will
  dominate the numbers above. This experiment bounds the geometry and timing
  error only, and the bound is what the bake-off will be measured against.
- Rigid product only. A deformable product changes the surface-height selection,
  since the upper surface is no longer planar.
- Simulated depth has none of the failure modes real depth has on wet, specular
  product. The measured advantage of depth is an upper bound.
- Camera intrinsics are exact and undistorted, and the camera-to-base transform
  is exact. On hardware both are calibrated quantities with error of their own;
  the calibration step injects that error deliberately.
- Belt speed is held at setpoint. Start and stop transients are not covered, and
  the tracker's prediction assumes constant speed over the horizon.

## What this changes

- The verification camera and the overhead camera both need depth. Recorded
  against the sensor selection for the cell.
- The perception bake-off can now run, since the geometry and timing under it are
  measured and bounded.
- Next number to take, unchanged: in-hand shift at gripper closure, which the
  control architecture analysis identifies as dominating everything measured
  here.
