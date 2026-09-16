---
title: Pork-leg alignment, grasp-and-rotate against pick-and-place, on a SCARA and a six-axis arm
date: 2026-09-15
tags: [experiment, meat-cell, alignment, scara, six-axis, gripper, saw, simulation]
status: decided
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
- Simulator: MuJoCo 3.12.0, `applications.pork_leg_alignment.sim` in this repo (was `meat_cell_sim`), timestep 2 ms, implicitfast, elliptic
  cone, 3 no-slip iterations (cell.xml).
- Legs: `leg_population(20, seed=0)` from `src/applications/pork_leg_alignment/sim/product.py`: 655 to 815 mm, 9.0 to
  15.5 kg, both hands, bend up to about 60 mm. Hock at 76 percent of length (assumed).
- Arrival: leg centre of gravity at x = -0.30 m, y uniform in 0.40 to 0.60 m, yaw uniform in
  plus or minus 35 degrees about square to the belt with the trotter toward the open edge, drawn
  from `numpy.random.default_rng(20260915)`; the same 20 arrivals for every condition.
- Belt: 0.30 m/s (assumed; not measured on the line).
- Saw: `SawConfig()` defaults, blade plane 30 mm outside the open edge at x = 1.10 m, feed
  resistance 60 N. Hold-down belt: `HoldDownConfig()` defaults, 150 N.
- Arms: UR20 and FANUC SR-20iA (`src/robotics/hardware/arms.py`), mounted behind the far rail at
  x = 0, y = 1.10 m.
- Grippers: Zimmer GEH6180IL-sized jaw (1800 N) and OnRobot 3FG25-sized three-finger (450 N)
  (`src/robotics/hardware/assets/`). Pad friction 0.5 (assumed).
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

Amended 2026-09-15, before any condition ran its 20 legs, after shakedown runs on legs 0 to 2 of the
population. Every change is in the code with the measurement that motivated it; the protocol,
trial counts and success definition are unchanged.

- Cell layout. At 0.30 m/s a grasp-and-rotate cycle needs about 1.1 m of belt after the pick
  (grasp 1.9 s, turn and release 1.75 s, measured on the default leg), so the saw and hold-down
  moved from x = 1.10 m to x = 1.75 m, the hold-down's pressing section is 0.50 m long (lead-in
  from x = 1.11 m), the belt is 4 m long, and the SR-20iA is mounted at x = 0.35 m so its 1.1 m
  reach covers both the pick and the set-down. The UR20 stays at x = 0. The layout is a design
  output of this work, not a fact about the plant.
- Ready pose. Both arms wait over the open-edge side of the belt at (x -0.10, y 0.25, 0.21 m up)
  between legs, and return there after release; from mid-belt the SR-20iA swept its open jaws
  through a 766 mm leg's ham on the way to the shank.
- Arm servos. Integral action (10 /s), velocity feedforward and a ten-times stiffer UR20 position
  loop; SR-20iA J4 at 8000 N m/rad. Before: 5 mm lifts of 1.6 and 2.6 mm; 30 to 40 mm tracking
  lag on fast moves. After: lifts within 0.1 mm, a moving grasp point met within 1 mm on both
  arms. All gains remain assumptions (`src/robotics/hardware/arms.py`).
- Grasp. The shank grasp moved from 0.66 to 0.70 of the leg's length so the jaw's 120 mm pads
  clear the waist by 37 mm; the pads are 90 mm tall, tip 35 mm below the tool point, in three
  segments so a pad has a line of contacts rather than one point; the tilted tool's grasp rises
  to keep the pad's downhill corner off the belt. Tool tilt is about the finger axis, positive
  leaning the tool body toward the ham.
- Proof lift. The part may lag the tool by 2 mm rather than 1 mm on the 5 mm lift: the
  three-finger hold on a trotter settles 1.6 to 1.8 mm whatever the lift height, which is contact
  settling, not slip. The jaw on a shank lags under 0.1 mm.
- Three-finger gripper on the shank. Dropped for a geometric reason, not a margin: a centric
  gripper's off-axis fingers sit half the open radius from the tool axis, so two of three fingers
  land on any shank wider than half the 155 mm opening, and every shank is 78 to 110 mm wide.
- Hold-down. The lead-in ramp is a separate body that rides up with the plate but does not move
  along the belt: rewinding an inclined surface drilled it into a ham and jammed the leg. Ramp at
  15 degrees over 0.40 m (was 25 over 0.30), friction 0.1.
- The old slab cutter lane beyond the open edge is removed from the cell; the UR20's wrist hit
  it reaching for an overhanging trotter.

Amended 2026-09-14, before any approach ran, after the grasp check (task 4): a three-finger
gripper closing round a vertical axis cannot straddle a shank lying on the belt (it failed its
jaw-fit precondition on both arms), so Lakshya gave it an end-on grasp at the trotter on the UR20
(`src/applications/pork_leg_alignment/skills/trotter_grasp.py`). That grasp needs a tool that tilts, so the SR-20iA
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

Approach B, jaw on the shank, from ground-truth pose. Two runs of the same protocol on
2026-09-15, both kept in `experiments/data/2026-09-15-alignment-approaches/`: the first at git
b42a2e7 plus the amendments above (`B-*-b42a2e7.csv`), the second after the skills were moved onto
the `LegEstimate` layer with a second estimate after the grasp (`B-*-truth-2406215.csv`), which is
the code the videos in the plan were filmed from. The saw is the judge; "entry offset" and "cut
angle" are the blade's first contact relative to the hock, over the cut legs.

| Condition | Successes / trials, final run (jaws close on a ramp) | Entry offset median, p95 mm | Cut angle median, p95 deg | Cycle median s | Failures | Earlier runs |
|---|---|---|---|---|---|---|
| B, SR-20iA, jaw, tilt 0 | 14 / 20 | 3.4, 19.9 | 2.1, 11.8 | 3.80 | unreachable x2 (legs 10 and 19, arrivals -25 and -12 deg); slipped in the turn x2; cut angle 5.3 and 9.2 deg | 14, then 13 |
| B, UR20, jaw, tilt 0 | 15 / 20 | 1.7, 12.2 | 1.3, 11.4 | 4.00 | slipped in the turn x1; cut angle 8.5 and 9.2 deg; cut offset 12.2 mm and -9.4 mm entry with the leg turned during the cut | 12, then 12 |
| B, UR20, jaw, tilt 15 | 17 / 20 | 1.0, 10.0 | 1.2, 9.0 | 4.00 | cut angle 8.4 and 9.0 deg; cut offset 10.1 mm | 16, then 17 |
| B, UR20, jaw, tilt 30 | 15 / 20 | 0.8, 8.2 | 1.2, 8.8 | 4.00 | grasp slipped on the proof lift x1; cut angle 13.4 and 8.8 deg; cut offset 19.1 and -9.7 mm | 16, then 15 |
| A, SR-20iA, jaw, tilt 0 | 14 / 20 | 3.6, 18.9 | 2.1, 11.8 | 3.80 | unreachable x2; slipped in the carry x2; cut angle 5.3 and 9.3 deg | 12 |
| A, UR20, jaw, tilt 0 | 16 / 20 | 2.8, 9.0 | 1.2, 8.3 | 4.00 | slipped in the carry x1; cut angle 12.0, 7.6 and 8.3 deg | 16 |

Three runs of the protocol are in the data directory: `*-b42a2e7.csv` (before the leg-estimate
layer), `*-truth-2406215.csv` (estimate layer, jaws closing as a step) and `*-truth-7125e18.csv`
(jaws closing on a 0.6 s ramp), which is the final run and the one the videos were filmed from.
The ramp came from watching the videos: the step close drove the leg 21 mm along its axis in the
first 0.1 s of closing, which on film looked like the leg snapping into the jaws; on the ramp the
leg moves 0.5 mm during the close and the grasp shift over 20 legs is 2.4 mm median, 10.7 mm
worst (UR20), against 20 to 25 mm before.

Approach A (`PickAndPlace` in `skills/rotate_on_belt.py`) is the same skill and path as B with the
shank carried 100 mm up instead of 20 mm, plus a check at carry height that no part of the leg
touches the belt (it did not on any leg gripped, both arms). Loads reported at carry height, 18
legs per arm: flange 88 to 147 N; moment about the jaw line 18 to 42 N m; inertia about the
tool's vertical axis 0.49 to 1.47 kg m^2, over the SR-20iA J4 rating of 0.45 kg m^2 on every leg.
The simulated arms have no torque limits (Caveats), so the SR-20iA carried every leg regardless.

Paired by leg, tool vertical, final run: UR20, A won 1 leg (15) and lost none, 16 against 15;
SR-20iA, A and B passed and failed the same legs, 14 and 14. Hock at release, median: UR20 A
1.4 mm, B 0.9 mm; SR-20iA 2.2 mm both. Loads at carry height: flange 88 to 147 N, moment 21 to
44 N m, inertia about the tool axis 0.6 to 1.6 kg m^2, over the SR-20iA J4 rating on every leg.

Not run: the three-finger end-on conditions (the trotter grasp does not yet track a moving belt).

What B is in this simulation. The `airborne` check run at B's 20 mm carry height on legs 0, 8 and
15 on both arms found no part of the leg touching the belt on any of them: the rigid jaw holds the
rigid leg's pitch, so the ham does not stay down and pivot. B as run is a carry at 20 mm and A a
carry at 100 mm, which is why their per-leg slips agree to within a millimetre. H1's premise (B
never carries the leg's weight) does not hold for a rigid leg; a real ham hanging 350 mm from the
grip would droop and stay on the belt. Testing a true turn needs a leg model that bends at the
grip or the shank, which is the first item under caveats.

Between the runs one grasp detail was tried and reverted: taking the jaw line from the
centreline's local direction at the shank instead of the leg's overall heading dropped the
SR-20iA to 8 of 20 (two lifts stalled, two slips, two more cuts out of tolerance) while the UR20
moved by one leg; the heading is kept, and the reason the SCARA is sensitive to a few degrees of
jaw yaw is not yet understood.
| B, UR20, three-finger end-on | not run | | | | the end-on grasp does not yet track a moving belt |
| A, all | not run | | | | approach A is not built |

Where the failures come from, from the per-episode rows and the traces behind them:

- At release the arms do better than the saw sees. The hock's median distance from the blade
  plane at release is 2.3 mm on the SR-20iA (18 legs gripped) and 1.3 mm on the UR20 (20 legs,
  tool vertical); the turn itself is accurate on both arms.
- The hold-down's lead-in disturbs the aligned leg. Traced on leg 10 (arrival -25 deg): square
  within 3 degrees at release, turned to 13 degrees and 10 mm inboard while the ramp lifted over
  the ham. On the largest leg (15, 799 mm, 14.6 kg) the ramp rolled the ham over before the saw.
  Both arms suffer this equally; it is a limitation of the rigid plate-and-ramp hold-down model
  (`sim/hold_down.py`), not of either approach. Every cut-angle failure above 5 degrees is of this
  kind.
- Legs arriving 16 to 31 degrees off square with the trotter swung downstream (arrival -16 to -31)
  are set down 6 to 10 mm inboard on the SR-20iA, a direction-dependent bias not yet explained.
- The SR-20iA cannot reach two of the 20 arrivals from its mount at x = 0.35 m; the UR20 reaches
  all 20.
- Tilting the UR20's tool 15 or 30 degrees did not hurt: 17 and 15 of 20 against 12 of 20
  vertical. H2 (tilt gains no more than 2 legs) is not supported on this sample, but the
  difference is inside the failures the hold-down causes, so it is not a tilt result either.

Camera in the loop (UR20, tilt 0, 3 legs, same runner with `--pose-source camera`): 0 of 3. The
first camera estimate put the hock 19 to 21 mm from the truth along the leg and the heading
within 3 degrees; with the jaws closing on a ramp the turn set those two legs down 14 and 18 mm
outboard, which is that estimate error; the longest leg's hock came out 60 mm off and the fit
check refused the grasp. (Before the ramp, the step close added a 25 mm shift the camera could
not see because the leg had left its field.)

## Decision taken and why

By the rule written before the runs: the SCARA stayed in only if grasp-and-rotate won and tilt
gained at most 2 legs of 20. Grasp-and-rotate did not win on the UR20 (15 against 16 carrying, tool
vertical), tilt gained 2 legs (17 against 15), and carrying exceeds the SR-20iA's wrist rating on
every leg. The decision the rule gives is the six-axis arm for the pilot cell. H1 is not supported, and
could not be on a rigid leg (see "What B is in this simulation" above); H2 is not supported; H3
holds for the SCARA (every carried leg over the J4 rating, in both approaches) and does not bind
the UR20 (every leg inside its payload curve).

Caveat that goes with the decision: the largest single cause of failure on every condition is the
rigid hold-down model turning aligned legs on entry, which is the same for both arms and both
approaches, so the margins between conditions (1 to 5 legs) are inside what a compliant top belt
could move. The six-axis conditions were not filmed or run with the three-finger gripper. What the
results also say:

- The grasp moves the leg. Closing the jaws on the tapered shank drives the leg about 20 to
  25 mm toward its thin end (ground truth, every leg tried). Whatever is planned after the grasp
  must be planned on where the leg is after it, so the cell needs a look at the leg between grasp
  and turn: a camera over the pick zone, or the pick made inside the first camera's field.
- The camera's field must cover the longest leg at any arrival across the belt.
- The camera pipeline's along-leg station error (20 to 25 mm) is larger than the 10 mm cut
  tolerance, so the hock has to be found as a landmark rather than as a fraction of a noisy length.
- The hold-down model has to become a belt before its numbers count against an approach.

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
  2026-09-14, `tests/robotics/hardware/test_grippers.py`). The leg is a convex mesh hull, which goes through the same
  general convex collision, so the jaw's hold on a leg may read about 30 percent weak. That
  penalises approach A on the jaw; a grip failure on A with the jaw is reported with this caveat
  and re-run with a rounded-pad jaw before it counts against A.
