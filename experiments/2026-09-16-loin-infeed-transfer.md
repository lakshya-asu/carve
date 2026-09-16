---
title: Loin puller infeed, the leg cell's skills on a second product, in simulation
date: 2026-09-16
tags: [experiment, meat-cell, transfer, loin, skill-library, simulation]
status: decided
decision: whether the leg cell's skill graph carries to a second cell by re-parameterisation alone, and which files the transfer touches
---

# Experiment: loin-infeed-transfer

Written before any loin runs, per the [experiment protocol](../sops/experiment-protocol.md). The
design is Section 14 of the plan (`plan/leg-cell-plan.html`), which names file by file what carries
unchanged, what is re-parameterised, and what is re-measured. This record tests that design in the
simulator. The leg cell's evidence is in [[2026-09-15-alignment-approaches]].

## Hypothesis

H1, as Section 14.4 states it: the leg cell's skill graph, re-parameterised as in Section 14.2 and
with no change to any file under `src/robotics/`, aligns at least as many of 20 loins as it did
legs (14 of 20 on the SR-20iA, 16 of 20 on the UR20 at 15 degrees of tilt, Results table of the
leg record) against the assumed tolerance. The conditions run here are both arms with the tool
vertical, whose leg comparators on the square set of the final leg run are 17 of 20 (UR20) and
14 of 20 (SR-20iA).

The counter-hypothesis is live: a piece with no rigid handle slips in the jaws during the turn,
which the leg did once in 20.

H2, the software claim: the transfer touches one file outside `src/applications/`, the runner
`scripts/measure/alignment_approaches.py` (Section 14.4, "Runner"). Counted after the fact as
files changed by the transfer's commits, code and non-code reported apart.

A refusal before any motion is a live outcome too. The jaw-fit precondition in `AcquireShank`
refuses a grasp whose widest section under the pads leaves less than 20 mm of spare opening each
side; the jaw opens 180 mm, so it refuses anything over 140 mm across. Section 14.2 says whether
the centre-of-gravity grasp rule holds a loin "is the first thing the runs measure", and a fit
refusal on every piece counts as that measurement, not as a bug.

## Decision this informs

- Whether Section 14's transfer claim (Neil's "reuse most of the graph and change only what is
  novel") holds in simulation, and where it breaks if it does not.
- What the loin cell needs before hardware: a plant measurement of the piece, a vendor tolerance,
  a gripper sized to the piece, or a different grasp rule.
- Whether the plan's Section 14 file-by-file lists are right, and what to correct in them.

## Setup

- Git SHA: run one f427cf0 (`*-jaw_geh6180-*-f427cf0.csv`); run two a00b943 for both square sets and the
  SR-20iA any set, f99fede for the UR20 any set (`*-wide_jaw-*.csv`; the a00b943 run of that
  condition died at piece 10 in the runner's post-release park, see run two).
- Gripper: run one the GEH6180-sized jaw (180 mm opening, 90 mm pads); run two the wide jaw
  placeholder (`src/robotics/hardware/assets/wide_jaw_gripper.xml`: 20 to 320 mm opening, the
  Schunk PFH 150's stroke, 100 mm pads, the GEH6180's 1800 N and 2.6 kg kept so the stroke is the
  one variable changed; force and mass unverified for a real jaw of that stroke).
- Simulator: MuJoCo 3.12.0, `applications.pork_leg_alignment.sim`, timestep 2 ms, implicitfast,
  elliptic cone, 3 no-slip iterations (cell.xml). The loin cell reuses the leg cell's belt and rail
  XML; the loin, the infeed fixture and the camera mount position are `CellConfig` values.
- Pieces: `loin_population(20, seed=0)` from `src/applications/pork_leg_alignment/sim/loin.py`,
  drawn as `random_leg` draws legs: one size variable, scatter on top, so a heavy piece is also a
  long one. One rigid body, no weld, flat underside, the bone edge the taller edge, bone on the
  left or the right of the piece 50/50.
- Arrival: piece centre of gravity at x = -0.30 m, y uniform in 0.40 to 0.60 m, heading drawn from
  `numpy.random.default_rng(20260915)` exactly as the leg's "square" (within 35 degrees) and "any"
  (full circle) sets, each about the loin's own target heading rather than the leg's; the same 20
  draws for every condition. The "any" set's shift across the belt keeps both ends of a piece
  pointing at the rail on the belt, with the piece's centre of gravity at 0.5 of its length.
- Belt: 0.30 m/s.
- Fixture: `InfeedFixtureConfig` at the saw's x for each arrival set (1.95 m square, 2.60 m any),
  datum line at y = 0.80 m on the far-rail side, a drawn guide with no collision response; the
  piece's pose is read as its leading end crosses the fixture's plane and again as its trailing
  end leaves it.
- Arms: UR20 and FANUC SR-20iA at the leg's mounts per arrival set (UR20 at x = 0 square and
  0.85 any; SR-20iA at 0.45 square and 0.60 any; y = 1.10 m, base turned to face the belt).
- Gripper: the Zimmer GEH6180IL-sized jaw, 180 mm opening, 120 mm pads.
- Perception: ground-truth pose, stated as such. The loin has no camera pipeline yet (Section
  14.3); `--pose-source camera` is refused for it.

### Assumptions, every one

No source in the library gives the piece's dimensions, the belt speed at the station or the pose
the machine needs (Section 14, opening). Each number below is named in code where it is used.

| Assumption | Value | Where it comes from | In code |
|---|---|---|---|
| Loin mass, nominal | 12.3 kg | USDA cutout: loin primal 25.17 percent of a 97.5 kg carcass, 24.5 kg per carcass, halved (`pork-processing-line.md` 4.1). The piece at the plant is unmeasured | `loin.py` docstring, `NOMINAL_MASS_KG` |
| Loin mass, range | 9.8 to 14.8 kg | Nominal plus or minus 20 percent, for the spread of carcass weights; the spread is unmeasured | `MASS_RANGE_KG` |
| Loin length, nominal and range | 0.72 m; 0.64 to 0.80 m | No source; a market pig's thoracolumbar spine. Unverified | `LENGTH_RANGE_M` |
| Cross section at the widest | 0.20 m across, 0.10 m tall | Derived: 12.3 kg at 1050 kg/m^3 is 0.0117 m^3, over 0.72 m is 0.0163 m^2 of section, and a flat-bottomed section 0.20 by 0.10 m with a skewed top holds about that. Unverified | `LOIN_PROFILE` |
| Density | 1050 kg/m^3 | Assumed for bone-in pork; used only in the derivation above | record only |
| Bone side | the taller edge, ridge at 0.4 of the half width toward the bone; left or right 50/50 | A chine and rib edge stands higher than the loin's belly edge; sides mirror between the two loins of a carcass. Unverified | `BONE_SKEW`, `bone_on_left` |
| Flat underside | 30 percent of each section below the belt plane | The leg's value, for the same reason (a soft piece conforms). Unverified | `flatten_fraction` |
| Belt friction on the piece | 0.45 | The leg's value. Unverified | `friction_slide` |
| Belt speed at the station | 0.30 m/s | The leg's assumption (Section 14.2 holds 0.20 and 0.40 out) | runner `BELT_SPEED_MPS` |
| Fixture plane x | 1.95 m (square), 2.60 m (any) | The leg's saw positions, a layout output of the leg runs, not a plant fact | runner `ARRIVAL_KINDS` |
| Datum line | y = 0.80 m, far-rail side, 57 mm inside the rail face | Which side of the belt the loin puller's datum is on is unknown (Section 14.2). Chosen so the datum is on the arms' side | `InfeedFixtureConfig.datum_y_m` |
| Target pose | piece along belt travel, bone edge on the datum line; heading 0 when the bone lies on the piece's left, pi when on its right | Section 14.3's working assumption, "square to belt travel, bone side toward a datum line", read as the piece squared up to the direction of travel | `loin_infeed.py` `infeed_heading_rad` |
| Tolerance | 10 mm on the bone edge's offset at the fixture plane, 5 degrees of heading | The leg's assumed tolerance, until the vendor or the plant gives numbers | runner `OFFSET_TOLERANCE_M`, `ANGLE_TOLERANCE_RAD` |
| Grasp station | the centreline section nearest the centre of gravity, jaws across the piece | Section 14.2's starting rule; no rigid handle is sourced on a loin | `loin_infeed.py` `centre_of_gravity_station` |
| Camera mount | over the pick zone at x = -0.40 m, raised so the field's short axis holds the longest piece | The overhead camera's field must cover the longest piece at any arrival (Section 14.2). Height set by test | `CellConfig.overhead_camera_mount_m` |
| Arm mounts, ready pose, servo gains, turn bounds, proof lift, jaw pads | the leg's | Section 14.1: about belts, arms and grippers, not legs | unchanged |

## Evaluation protocol

- Episode: the piece arrives; estimate from ground truth; select the grasp at the centre-of-gravity
  station; acquire with the jaw and prove the grip with the 5 mm lift; rotate on the belt to the
  target pose with the verify-and-correct turn; release; the arm returns to its ready pose; the
  piece rides to the fixture. The fixture's `InfeedResult` is the judge. No human judgement.
- Trials: 20 pieces per condition, one episode each (deterministic simulation). Conditions: B,
  UR20, jaw, tilt 0; B, SR-20iA, jaw, tilt 0. Square arrivals first; any arrivals if the square set
  runs clean (every episode reaches a verdict with no exception and no arm collision).
- Success, all of:
  - the fixture reports `crossed`;
  - the bone edge's offset from the datum, read at entry and at exit, within plus or minus 10 mm;
  - the heading error at entry within plus or minus 5 degrees;
  - the arm has released the piece before any part of it reaches the fixture plane; no drop off
    the belt; no arm collision with the belt or rail.
- Failure modes recorded per episode, in the order the runner's `judge` applies them: estimate,
  select or acquire refused (with the precondition's number), grasp slipped on the proof lift,
  unreachable, slipped in the turn, misaligned, released late, dropped, arm collision, fixture
  offset or heading out of tolerance (with the numbers).
- Reported per condition: successes out of 20; median and 95th percentile absolute entry offset
  and heading error over crossed pieces; median cycle time from arrival to release; failure-mode
  counts.
- H2: files changed outside `src/applications/` by the transfer's commits, listed.

## Results

Two runs of the protocol. Run one with the leg cell's jaw stands as the finding that the gripper
does not fit the piece; run two with the wide jaw placeholder shows the transfer past the gripper.

### Run one: the leg cell's jaw

Run 2026-09-16, git f427cf0, approach B, GEH6180-sized jaw, tool vertical, ground-truth pose, 20
loins per condition, 80 episodes. The square set ran clean by the protocol's definition (every episode
reached a fixture verdict, no exception, no arm collision), so the any set ran too. Wall time
0.4 to 0.6 s per episode.

| Set | Condition | Successes / trials | Cycle median s | Failures |
|---|---|---|---|---|
| square | B, UR20, jaw, tilt 0 | 0 / 20 | none gripped | grasp: precondition_failed x20 (jaw fit) |
| square | B, SR-20iA, jaw, tilt 0 | 0 / 20 | none gripped | grasp: precondition_failed x20 (jaw fit) |
| any | B, UR20, jaw, tilt 0 | 0 / 20 | none gripped | grasp: precondition_failed x20 (jaw fit) |
| any | B, SR-20iA, jaw, tilt 0 | 0 / 20 | none gripped | grasp: precondition_failed x20 (jaw fit) |

What failed and why. Every episode ended at `AcquireShank`'s jaw-fit precondition, before the arm
moved: the estimate and the grasp selection succeeded on every piece, and the check found less
spare opening than the 40 mm (20 mm a side) it requires. The numbers, from the population at the
grasp station (0.47 of the length on every piece, the section nearest the centre of gravity):
width at the station 164 to 211 mm, median 190; widest section under the 120 mm pads 169 to
215 mm; the jaw opens 180 mm, so the spare opening is -35 to +11 mm against 40 required. The two
640 mm pieces (loins 2 and 18) are the only ones the jaw would physically straddle, at 11 and 3 mm
of spare, and both are refused by the margin the check keeps for pose error. The pieces rode on
untouched, and the fixture read them as they crossed: square set, bone edge 127 to 321 mm inboard
of the datum (median 232 mm) and heading 0.5 to 31.7 degrees off (median 15.0); any set, median
328 mm and 76.9 degrees, 95th percentile 393 mm and 157.6 degrees. No piece passes the fixture by
arriving near the target; a pass needs the manipulation.

The chain on a loin the jaw fits, outside the protocol. `test_loin_infeed.py` and a probe run the
same skills on a loin at width scale 0.60 (115 mm across at mid length), UR20 at the square-set
mount, arrival 25 degrees off the target heading, both bone sides. Grasp: success, opening 116 mm,
proof-lift lag 0.03 and 0.59 mm. Turn: success, 25 degrees, no correcting pass, slip 1.0 and
1.6 mm. At release the bone edge sat 4.3 and 4.5 mm past the datum and the heading 0.08 and
0.60 degrees off, cycle 1.86 s from the start of the turn to the tool clear; the fixture read the
same 4.3 and 4.5 mm at entry and at exit, so the skill's own reading and the judge's agree on the
point. The 4 to 5 mm past-datum bias on both sides is inside the assumed tolerance and not
explained: the correcting pass reads the piece after the turn and found it within 3 mm, so the
bias arises in the set-down, open or retreat. One piece, two runs; not a measurement of the rule.
Traced in run two, below.

### Run two: the wide jaw

Run 2026-09-16, approach B, wide jaw, tool vertical, ground-truth pose, 20 loins per condition, 80
episodes, everything else as run one. Square sets and the SR-20iA any set at git a00b943; the UR20
any set at f99fede, after the runner's post-release park was made to retry from the home seed (the
a00b943 run of that condition raised `UnreachableError` on loin 10, the ready pose solved from the
wrist's post-turn joints converging 130 degrees off; pieces 0 to 9 of the two runs gave the same
outcomes). The fixture is the judge.

| Set | Condition | Successes / trials | Entry offset median, p95 mm | Heading error median, p95 deg | Cycle median s | Failures |
|---|---|---|---|---|---|---|
| square | B, UR20, wide jaw, tilt 0 | 20 / 20 | 0.7, 5.1 | 0.41, 1.18 | 4.92 | none |
| square | B, SR-20iA, wide jaw, tilt 0 | 20 / 20 | 0.4, 1.0 | 0.29, 0.81 | 4.38 | none |
| any | B, UR20, wide jaw, tilt 0 | 4 / 20 | 30.8, 199.1 | 1.82, 9.61 | 5.50 | slipped in the turn x11; dropped x4; arm collision x1 |
| any | B, SR-20iA, wide jaw, tilt 0 | 10 / 20 | 1.3, 213.9 | 0.79, 6.21 | 4.68 | slipped in the turn x6; dropped x2; set-down unreachable x1; arrival unreachable x1 |

Square sets, both arms, every piece gripped, turned, released before the fixture and read within
tolerance: UR20 bone edge at release -5.6 to +0.6 mm (median -0.7, 12 of 20 past the datum),
SR-20iA -1.0 to +1.0 mm (median -0.1, 11 of 20 past); heading at release median -0.21 and -0.14
degrees; 2 of 20 (UR20) and 10 of 20 (SR-20iA) took a correcting pass; slip in the turn median 1.9
and 4.1 mm; the fixture's entry reading equalled the release reading on every piece (median
difference 0.00 mm) and its exit reading equalled its entry, so nothing moves the piece after the
jaws open. The SR-20iA's set-down reach, which cost it 5 of 20 legs on the square set, cost it no
loin: the loin's arrival and target both lie along the belt near its mount.

The 4 to 5 mm datum bias did not recur on the population. It recurs on the narrow piece it was
first seen on (width scale 0.60, 115 mm across, 100 mm tall) with either jaw: -4.3 mm on the
GEH6180, -4.2 mm on the wide jaw. Traced tick by tick through the release
(`scripts/measure/loin_turn_trace.py --piece 0 --gripper jaw_geh6180 --width-scale 0.60 --ticks`,
UR20, the square set's arrival for piece 0): at set-down the piece sat rolled -11.4 degrees in the
jaws with its origin 7.6 mm above the belt, the pads pressing 926 and 942 N, and the bone edge read
+0.5 mm; in the first 80 ms of the retreat, as the jaws opened from 111 to 158 mm and the pad
forces fell to 11 to 37 N, it rolled flat (-10.4, -8.1, -4.2, +0.8, +1.9, then 0.0 degrees at
20 ms ticks) and the scored bone edge went to -8.9 mm, settling at -7.5 by 0.18 s, where it stayed
through the clear and the ride to the fixture. The scored edge is the centreline at 42 mm height
projected across the piece, and 42 mm times sin 11.4 degrees is 8.3 mm. So the "bias" is the piece
un-rolling when released: the jaws had rolled the narrow, tall piece onto one edge, the turn's
check read the bone edge in that rolled pose and found it within 3 mm, and the release let the
piece settle flat several millimetres nearer the datum (4.3 mm at 8 degrees of roll on a
hand-placed 20 degree arrival, 7.5 mm at 11.4 degrees here). The full-width loin, 200 mm across
and 100 mm tall, does not roll in the jaws and shows no bias. Whether a real loin rolls in a real
jaw is unmeasured; a verification look after release, which Table 10.1 of the plan already lists
as not built, is what would catch it.

Any sets: 14 of the 16 failures are on pieces arriving more than 40 degrees off the target heading
(turns of 47 to 163 degrees); the other two are piece 11 (9 degree turn, the UR20's finger arm met
the rail 41 times, 23 mm slip) and piece 2 (38 degrees, set down 54 mm short of the datum, then
read as off the belt). The mechanism, measured with contact counts per phase on two failing pieces
(`scripts/measure/loin_turn_trace.py --arrivals any --piece 3`, and `--arm sr20ia --piece 4`):
UR20 piece 3 (arrives +126 degrees) met the far rail 436 times during its first turn, its far end
reaching y = 0.858 m against the rail face at 0.857, and was lifted 104 mm (rolled up against the
rail), with 35 gripper-rail and 107 gripper-belt contacts on the way; SR-20iA piece 4 (arrives -83
degrees) met the rail 158 times during the turn, was held 47 to 50 mm up, and fell 43 mm past the
datum when released. The turn interpolates the centre of gravity from its arrival y (0.40 to
0.60 m) to the target y (about 0.70 m) while the heading turns, so a piece whose ends lie 0.32 to
0.40 m from its centre of gravity passes through headings across the belt with its centre already
near 0.65 m, and its end sweeps past the rail. The leg never did this because its target lays it
across the belt with the trotter over the open edge. The turn's slip check names it (the piece
lags the plan by 74 to 296 mm), and the record names it here; what to change is the cell's or the
manoeuvre's to decide: the datum on the open-edge side (Section 14.2 says which side is
unverified), a turn that completes the rotation before the shift toward the datum, or a sweep
check before the turn. None was changed for this run.

Film: `~/Videos/meat-cell/2026-09-16/loin-approach-b-ur20-tilt0-leg0.mp4` (full view) and
`loin-approach-b-closeup-ur20-tilt0-leg0.mp4` (tracking), loin 0 of the square set on the UR20 with
the wide jaw, 10.0 s each at 25 fps, checked frame by frame on a contact sheet: ready pose, the
intercept and close across the piece, the 6 degree turn toward the datum, release, the retreat
upstream, and the piece riding through the fixture's plane along the drawn guide.

### What carried, what changed

Carried unchanged, by file: everything under `src/robotics/` (core, hardware, perception) and
`ros2/`; `git diff a1e838b..HEAD -- src/robotics ros2` is empty. Inside the application, the whole
of `AcquireShank` (approach heights, ramped close, proof lift, fit check), the whole of
`RotateOnBelt`'s manoeuvre (lift, turn, verify-and-correct, lower, open, retreat, clear), the
arrival draws, the mounts, the ready pose, the servo gains, the turn bounds and the tolerances.

Re-parameterised, inside `src/applications/pork_leg_alignment/`: `sim/product.py` (the face
indexing became `loft_mesh` so the loin does not copy it; `product_body_ids`; `LegConfig` answers
`centreline_m` and `half_width_m`), `sim/scene.py` (`loin`, `infeed_fixture` and
`overhead_camera_mount_m` fields, a `product` property), `sim/cell.py` (steps the fixture as it
steps the saw; `product_centreline_world`; `release_before_x_m`), `skills/leg_estimate.py` (the
on-belt precondition shared), `skills/shank_grasp.py` (the station is a rule given to
`SelectShankGrasp`; `shank_station` is the leg's), `skills/rotate_on_belt.py` (what aligned means is
an `AlignmentTarget` given to the skill; `SawTarget` is the leg's; `hock_offset` became
`datum_offset`; `leg_touches_belt` became `product_touches_belt` over the product's bodies).

New, inside the application: `sim/loin.py`, `sim/infeed_fixture.py`, `skills/loin_estimate.py`,
`skills/loin_infeed.py`, and their four test files under `tests/applications/pork_leg_alignment/`.

Outside `src/applications/`, code, run one: `scripts/measure/alignment_approaches.py`, the one file
Section 14.4 predicted (a `Product` record and the `--product` flag; the episode loop, `judge` and
`summarise` unchanged); and `scripts/view/approach_b_videos.py`, three caption lines that read the
runner's renamed columns (`judge`, `angle_deg`, `datum_offset_mm`), six lines changed, no logic.
Run two added `src/robotics/hardware/grippers.py` and `assets/wide_jaw_gripper.xml` (a fourth
gripper model, the kind of addition ARCHITECTURE.md's "adding a robot" describes; no existing
gripper changed) with `tests/robotics/hardware/test_grippers.py`; the runner again (the park retry);
and the video script again (`--product`, `--gripper`, captions worded per product). Non-code: this
record, its data directory, and ARCHITECTURE.md (the tree listing and a known gap). H2 held for
the skills and the cell in both runs, missed by one file on a rename in run one, and in run two the
transfer needed a piece of hardware, which is the plant claim's cost and not the software's. The
transfer needed no new package: the loin lives in `pork_leg_alignment/` because the dependency rule
forbids one application importing another's `Cell` and skills, which ARCHITECTURE.md now says under
known gaps.

Not built, as Section 14.3 lists: the loin's segmenter, centre-of-gravity corrector, the bone-side
reading from a camera and the `LoinPerception` message; `--pose-source camera` is refused for the
loin.

## Decision taken and why

Run one: H1 not supported, 0 of 20 against the leg's 17 and 14, on both arms and both arrival
sets. The refusal is at the first primitive, grasp, and it is the hardware's number against the
product's: the jaw the leg cell chose opens 180 mm, the fit check keeps 40 mm for pose error, and a
loin derived from the cutout is 164 to 211 mm across where the centre-of-gravity rule closes the
jaws. No software ran past that check in the protocol.

Run two, with a jaw that fits: H1 supported on the square set, 20 of 20 on both arms against the
leg's 17 and 14, with the same grasp and turn skills, the loin's estimate, station and target, and
no change under `src/robotics/` but the gripper itself. Not supported on the any set, 4 and 10 of
20 against the leg's 17 and 9, and the reason is measured: a loin turning through more than about
40 degrees toward a datum 57 mm from the far rail sweeps its end into the rail, which is the cell's
layout meeting the piece's length, not a skill failing. The counter-hypothesis (a piece with no
rigid handle slips in the jaws during the turn) is not what the any-set slips are: the piece is
pushed by the rail, and the slip check reports the push. On the square set slip in the turn is 1.9
and 4.1 mm median, inside the leg's.

What the loin cell needs, in order: the plant's piece dimensions, since run one turned on 190 mm
against 140; a gripper of the wide jaw's stroke selected for real (the placeholder's force and
mass are the GEH6180's); the datum side, or a turn that rotates before it shifts, before any piece
arriving more than 40 degrees off the target is attempted; a verification look after release for
a piece that rolls in the jaws; then this protocol again.

Corrections to Section 14 from these runs: the loin lives in the leg cell's package (14.4 implies
a new one); the transfer touched two files outside `src/applications/`, not one, because product
names in the runner's CSV columns had to go, and a gripper model on top of that; 14.2's sentence
"the jaw-fit precondition already refuses a grasp wider than the opening" understates it, since the
check refuses anything within 40 mm of the opening, which on this population is every piece; and
14.1's "Cell layout" lesson gains a line: the datum's side of the belt sets how far a piece's ends
sweep during the turn, and a loin's ends sweep 0.4 m.

## Caveats

- Everything about the piece is derived or assumed; see the table. A result here is about the
  software's transfer to an invented loin, not about the plant's loin (Section 14.4, "Effort").
- Rigid piece. A real loin is soft along its length and the jaw's hold on it is not modelled.
- Ground-truth pose. The loin's segmenter, centre-of-gravity corrector and bone-side reading are
  not built (Section 14.3), so perception error is absent from every number here.
- The fixture is a reading plane and a drawn guide, not a machine: nothing at the fixture pushes
  back on the piece, so the leg cell's largest failure cause (the hold-down's lead-in turning an
  aligned piece) has no counterpart here, and the loin's numbers are not comparable to the leg's
  on that axis.
- The arms have no joint torque limits in simulation.
- The wide jaw is a placeholder: its force and mass are another gripper's, its stroke is a real
  part's, and a real part of that stroke (the PFH 150 at 18.9 kg) would take most of the arms'
  payload with a 15 kg loin. Run two's numbers are about the stroke, not about a gripper.
- The jaw's hold on a rigid loin is MuJoCo's box-on-hull contact, the same caveat the leg record
  carries: it may read about 30 percent weak under a steady pull along the piece.
