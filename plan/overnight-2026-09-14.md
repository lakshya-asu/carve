---
title: Overnight queue 2026-09-14
date: 2026-09-14
tags: [plan, overnight, autonomous]
status: draft
---

# Overnight queue, night of 2026-09-14

For [[wednesday-2026-09-16]] item 3 (both approaches on both arms). Work top to bottom. Each task
has a check that decides pass or fail; a failed check is written up verbatim in
`daily/2026-09-15.md` and the next task starts only if it does not depend on the failed one.
Nothing here needs the network, a GPU, or a package install. Commits stage explicit paths only.

Decisions already taken by Lakshya: UR20 and SR-20iA; far-side mount; gripper is a variable
(Zimmer GEH6180IL-sized, OnRobot 3FG25-sized); both approaches in parallel on one grasp skill;
hold-down belt at the saw.

## 1. Arm choice inside the cell

Make the arm a `CellConfig` choice (`ArmModel`), mounted behind the far rail, and remove every
hard-coded UR5e name from `cell.py`, `sensing.py`, `arm.py` and the tests. `Observation` carries
as many joint positions as the arm has.

Check: full test suite passes; for each arm, a new test builds the cell, holds home for 1 s within
0.01, and IK with the tool pointing down reaches a grid over the belt (x from -0.4 to 1.0 m, y
from 0.15 to 0.85 m, at three heights). The reachable fraction per arm is recorded in the daily
note.

Done 2026-09-14 evening, before the unattended run (commit 302f9c3): 158 tests pass; holds home
within 0.02 with the gripper attached; UR20 120/120 points at all three heights, SR-20iA 101/120
at 50 and 180 mm and 0/120 at 350 mm (stroke tops out 275 mm above the belt from this mount).

## 2. Two grippers as assets

`jaw_gripper.xml` sized to the Zimmer GEH6180IL (80 mm per jaw, 900 N per jaw, 2.6 kg, pads long
enough for a shank) and `three_finger_gripper.xml` sized to the OnRobot 3FG25 (18 to 155 mm, 450 N,
1.6 kg), both exposing the names `gripper.py` measures.

Check: `measure_geometry` reports stroke within 5 percent of the datasheet; a test closes each on
a fixed 90 mm cylinder and records the pull-out force along the cylinder, which must reach at
least 80 percent of the rated friction force at the pad friction used.

## 3. Pre-register the approach experiment

Write `experiments/2026-09-15-alignment-approaches.md` before any approach runs: hypothesis,
the decision it informs (SCARA or six-axis; grasp-and-rotate or pick-and-place; tool tilt), 20
legs from `leg_population(20, seed=0)`, arrival yaw uniform in plus or minus 35 degrees, both
arms, both grippers, success defined at the saw (cut offset and angle, with the tolerances marked
as assumptions), and what is reported.

Check: the record exists and is committed before task 4 produces a number.

Written 2026-09-14 evening: `experiments/2026-09-15-alignment-approaches.md` (18 conditions, 360
episodes, success judged by the saw with assumed tolerances of 10 mm and 5 degrees).

## 4. Grasp skill with a contract

First skill in the skill library layout Neil asked for: inputs, preconditions, outputs, success,
failure, recovery, as code. Grasp the shank on the hock side of the leg's centre of gravity.

Check: on the default leg, placed square, each arm and gripper pair closes on the shank, and a
5 mm lift moves the leg with the gripper; pass or fail per pair recorded.

Progress 2026-09-14 evening: interface chosen by Lakshya (typed contract plus task graph) and
built in `src/skill_library/` with 12 tests (commit 5c5a955). Grasp skill built in
`src/meat_cell_sim/skills/grasp.py`; check run: UR20 + jaw success (3.8 mm rise), SR-20iA + jaw
success (3.7 mm), both arms + three-finger precondition failed (38 mm spare, 40 mm required).
Task 4 check done. Open question for Lakshya: keep the three-finger gripper in tasks 5 and 6 as a
from-above grasp that fails its precondition, or give it a different grasp (end-on at the
trotter, tool tilted, six-axis only).

## 4b. Stop the arms sagging under a leg

Found during task 4: on a 5 mm proof lift the UR20 raised its tool 1.60 mm and the SR-20iA 2.60 mm,
because the servo gains in `arms.py` are assumptions and nothing compensates the payload. That
error would land in every cut offset. Raise the gains or add payload feedforward, whichever holds
the arm steady at the rated payload without the servos ringing.

Check: holding the default leg by the shank, the tool reaches a commanded 5 mm lift to within
0.5 mm on both arms; both arms still hold home within 0.02 with no load; full suite passes.

## 5. Approach B: grasp and rotate about the centre of gravity

Rotate the leg on the belt until the hock sits on the blade plane, square, then release before
the hold-down belt. Six-axis arm: tool tilt 0, 15 and 30 degrees as a variable. SCARA: tilt 0 only.

Check: runs end to end on all 20 legs for every pair; the table of cut offset, cut angle, cycle
time and failures is written to the daily note. Not a pass bar on the numbers.

## 6. Approach A: pick by the foot and place

Grasp near the trotter, lift, move, set down aligned. Same 20 legs and pairs, plus the payload
and moment at the flange against each arm's published limit.

Check: same table as task 5, plus flange load against the UR20 payload curve and the SR-20iA J4
inertia limit.

## 7. Morning summary

Write what ran, what passed, what failed (verbatim), and the videos made, at the top of
`daily/2026-09-15.md`.
