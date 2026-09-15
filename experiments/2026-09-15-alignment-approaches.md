---
title: Pork-leg alignment, grasp-and-rotate against pick-and-place, on a SCARA and a six-axis arm
date: 2026-09-15
tags: [experiment, meat-cell, alignment, scara, six-axis, gripper, saw, simulation]
status: draft
decision: which approach and which arm class the Wednesday plan proposes for aligning legs to the trotter saw, and whether the tool must tilt
---

# Experiment: alignment-approaches

Written before any approach runs, per the [experiment protocol](../sops/experiment-protocol.md).
Trial counts, the success definition and what is reported do not change after the first episode.
Context: [[wednesday-2026-09-16]] item 3, [[neil-requirements]], [[line-videos]].

## Hypothesis

H1. Grasp-and-rotate (B), gripping the shank and turning the leg on the belt about its centre of
gravity, reaches the saw-alignment tolerance on more of the 20 legs than pick-and-place (A),
gripping near the foot and lifting, on both arms, because B never carries the leg's weight.

H2. On B, the six-axis arm with the tool tilted does not beat the six-axis arm with the tool
vertical by more than 2 legs of 20, so the SCARA's inability to tilt costs little on B.

H3. On A, the SCARA fails where the leg's inertia about the tool axis exceeds its published J4
limit, and the six-axis arm fails where the flange load exceeds the UR20 payload curve.

Counter-hypotheses are live: A may win if rotating on the belt drags the ham against belt
friction and the leg slides instead of turning; tilt may matter if a vertical jaw cannot close
round a shank lying on the belt without its pads striking the belt.

## Decision this informs

- The approach the technical plan proposes for the orient skill: B, A, or both with a rule for
  choosing between them per leg.
- The arm class: if B wins and tilt does not matter, the SCARA stays in the running on cost and
  speed; if A or tilt is needed, the plan proposes the six-axis arm.
- The gripper: whether the 450 N three-finger gripper is enough for B, or the 1800 N jaw is needed.

## Setup

- Git SHA: filled at run start.
- Simulator: MuJoCo 3.12.0, `meat_cell_sim` in this repo, timestep 2 ms, implicitfast, elliptic
  cone, 3 no-slip iterations (cell.xml).
- Legs: `leg_population(20, seed=0)` from `src/meat_cell_sim/product.py`: 655 to 815 mm, 9.0 to
  15.5 kg, both hands, bend up to about 60 mm. Hock at 76 percent of length (assumed).
- Arrival: leg centre of gravity at x = -0.30 m, y uniform in 0.40 to 0.60 m, yaw uniform in
  plus or minus 35 degrees about square to the belt with the trotter toward the open edge, drawn
  from `numpy.random.default_rng(20260915)`; the same 20 arrivals for every condition.
- Belt: 0.30 m/s (assumed; not measured on the line).
- Saw: `SawConfig()` defaults, blade plane 30 mm outside the open edge at x = 1.10 m, feed
  resistance 60 N. Hold-down belt: `HoldDownConfig()` defaults, 150 N.
- Arms: UR20 and FANUC SR-20iA (`src/meat_cell_sim/arms.py`), mounted behind the far rail at
  x = 0, y = 1.10 m.
- Grippers: Zimmer GEH6180IL-sized jaw (1800 N) and OnRobot 3FG25-sized three-finger (450 N)
  (`src/meat_cell_sim/assets/`). Pad friction 0.5 (assumed).
- Perception: ground-truth leg pose for this experiment, stated as such. The perception question
  is a separate record; this one isolates the manipulation.

## Conditions

| Approach | Arm | Gripper and grasp | Tool tilt | Legs |
|---|---|---|---|---|
| B rotate | UR20 | jaw on the shank | 0, 15, 30 deg | 20 each |
| B rotate | UR20 | three-finger end-on at the trotter | horizontal, along the leg | 20 |
| B rotate | SR-20iA | jaw on the shank | 0 deg | 20 |
| A pick and place | UR20 | jaw on the shank | chosen by IK | 20 |
| A pick and place | UR20 | three-finger end-on at the trotter | horizontal, along the leg | 20 |
| A pick and place | SR-20iA | jaw on the shank | 0 deg | 20 |

8 conditions, 160 episodes. Deterministic simulation, so one episode per leg per condition.

Amended 2026-09-14, before any approach ran, after the grasp check (task 4): a three-finger
gripper closing round a vertical axis cannot straddle a shank lying on the belt (it failed its
jaw-fit precondition on both arms), so Lakshya gave it an end-on grasp at the trotter on the UR20
(`src/meat_cell_sim/skills/trotter_grasp.py`). That grasp needs a tool that tilts, so the SR-20iA
with the three-finger gripper is dropped, and it needs the trotter to overhang the open edge by
the fingers' open radius, so legs that arrive with the trotter on the belt end in
`precondition_failed` and count as failures for that condition.

## Evaluation protocol

- Episode: the leg arrives; the orient skill runs; the leg rides through the hold-down belt and
  the saw; the saw's `CutResult` is the judge. No human judgement.
- Success, all of:
  - the saw reports `cut`;
  - entry and exit offsets from the hock within plus or minus 10 mm (assumed tolerance, the
    customer has not given one);
  - cut angle within plus or minus 5 degrees of square (assumed);
  - the arm has released the leg and cleared the belt before the leg reaches the hold-down ramp
    (x = 0.48 m); no drop off the belt, no arm collision with the belt, rail or saw.
- Failure modes recorded per episode: unreachable, grasp slipped, leg dropped, leg slid instead of
  turning, arm collision, released late, cut out of tolerance (with the numbers), stalled cut.
- Reported per condition: successes out of 20; median and 95th percentile absolute entry offset
  and angle over all cut legs; median cycle time from grasp to release; failure-mode counts; for
  A, peak flange load against the UR20 payload curve and peak leg inertia about the SCARA J4 axis
  against 0.45 kg m^2.
- Comparisons for the hypotheses: paired by leg, McNemar on success between B and A for each arm
  and gripper; H2 counted as legs gained by tilt over vertical.

## Results

Not run.

| Condition | Successes / trials | Notes |
|-----------|--------------------|-------|

## Decision taken and why

Not yet taken.

## Caveats

- Rigid legs. Soft tissue, skin sliding over bone and the drape of an overhanging trotter are not
  modelled, and all three change how a leg turns and how a gripper holds it.
- Tolerances, belt speed, saw feed force and hold-down force are assumptions. A condition that
  passes only at these values is not a result about the line.
- Ground-truth pose. Perception error adds to every offset reported here.
- Both arms have no joint torque limits in simulation; H3 is checked against published limits,
  not against the simulation failing.
- MuJoCo's flat-box contact against a cylinder holds only 0.60 to 0.70 of the friction rating under
  a steady pull along the cylinder, while the same jaw on a capsule holds to 1.0 (measured
  2026-09-14, `tests/test_grippers.py`). The leg is a convex mesh hull, which goes through the same
  general convex collision, so the jaw's hold on a leg may read about 30 percent weak. That
  penalises approach A on the jaw; a grip failure on A with the jaw is reported with this caveat
  and re-run with a rounded-pad jaw before it counts against A.
