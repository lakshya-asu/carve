---
title: Ready for Wednesday 2026-09-16
date: 2026-09-14
tags: [plan, wholestone, alignment, deliverables]
status: draft
---

# Ready for Wednesday 2026-09-16

Neil arrives Wednesday morning and asked for an exact technical plan ([[neil-requirements]]).
Lakshya leads; this list was agreed on 2026-09-14 at 7:17 PM, about 36 hours before.
"Wed" is what must exist Wednesday morning, "week" is what must exist by Sunday 2026-09-20.

Bar set by Lakshya at 7:40 PM: every item is about three quarters done by Wednesday, working end
to end with tuning left, not a sketch. The problem is modelled properly in simulation first,
including the trotter saw, before any approach is compared.

## Direction the plan and deck must carry

Set by Lakshya on 2026-09-14: the cell is the first proving ground for a robot that learns new
skills, reuses and composes the ones it has, runs on any platform, and learns together with other
robots as a fleet, taught by imitation or any other source, with a VLA on top. The plan and the
deck show that path from this cell's skill graph, and say which parts exist, which are next and
which are research. Order of work in the cell: scene first, then each sensor one at a time (choose,
place, test), then perception or a learned policy where the task needs one.

## Proof of concept Lakshya wants to show (added 2026-09-14, late)

One learned skill for reorienting a leg, run on two embodiments, a SCARA and a six-axis arm,
doing the same manoeuvre. Shows transfer of a skill across platforms, which is the company's
direction. To plan with Lakshya after the test videos are reviewed: what is learned (the whole
reorientation, or a residual on a shared deterministic skill), what representation makes it
embodiment-agnostic (tool or object frame actions rather than joint actions), and how much of it
can be real by Wednesday.

Design proposal written 2026-09-14 in [[cross-embodiment-skill-transfer]]: one MLP policy over
belt-frame grasp-point poses, trained from a scripted expert driving a floating gripper (no arm in
the data), run through each arm's own IK, judged in six paired conditions against the expert on
each arm. Open for Lakshya: grasp-and-rotate (on both arms today, SCARA over its J4 inertia) or a
planar push against a datum ([[latent-skill-representations]]).

## 1. Technical plan

- Wed: complete. The alignment task, open questions for Wholestone (tolerance, belt speed,
  spacing, downstream station), the skill graph with a contract per skill, the layer and folder
  layout following Neil's principles, both decisions argued from measurements, a validation plan,
  a week-by-week build order.
- Depends on: 3, 4, 5 for numbers; 6 for the layout.
- [x] Draft (2026-09-14 night: https://claude.ai/artifact/6ud7jyjhkCHin5ohoBho2v, copy in
  `plan/leg-cell-plan.html`)
- [ ] Numbers filled from sim (saw, hold-down, reach and grasp numbers in; approach results wait
  on task 4b)
- [ ] Lakshya review

## 2. Presentation

- Wed: complete, 10 to 12 slides built from the plan: task, architecture, SCARA vs 6-DOF,
  perception, sim demo video, next steps.
- [ ] Deck
- [ ] Demo video embedded
- Videos for the main presentation (Lakshya, 2026-09-15): the depth camera comparison,
  `~/Videos/meat-cell/2026-09-15/depth-cameras.mp4` (Gemini 335L and D455 side by side: colour,
  reported depth, depth error, three arrival angles).
- Pipeline step 1, leg segmentation: `~/Videos/meat-cell/2026-09-15/leg-segmentation.mp4` (true
  and found outline, height above the belt, matched, extra and missed pixels, per-frame readout).
  Checked 2026-09-15. Pair it with `edge-effects.png` (same folder: what stereo edge effects do to
  the outline) and the geometry against learned table on the plan page.
- Real footage: `outputs/real-footage/real-footage-segmentation.mp4` (21 plant frames, colour rule
  against Segment Anything plus the colour rule) and the two stills on the plan page, touching legs
  and lean cut faces.
- [ ] Lakshya review

## 3. Simulation of the station, then two alignment approaches

Order set by Lakshya: model the problem completely, then test approaches.

- Step 1, the saw. A saw on the right-hand side at the downstream end cuts the trotters off. Model
  it running: blade, position against the open belt edge, the cut as an event that separates the
  trotter, and the cut position scored against where it should be on the leg.
- Step 1b, counterforce for the saw (Lakshya, 2026-09-14): a hold-down belt over the main belt at
  the saw presses the leg while the blade cuts. The cut becomes a process with feed resistance
  from the blade, and each pass reports how far the leg slips and turns during the cut, with and
  without the hold-down.
- Step 2, approach A, pick and place: grasp part of the foot, lift, move, set down aligned.
- Step 3, approach B, grasp and rotate about the centre of gravity: grasp and turn the leg on the
  belt. Simpler. Tests must decide whether the tool needs to tilt.
- Wed: saw running and cutting in sim; both approaches running on several of the 20 legs with
  first numbers (success, cut position error, cycle time); tuning left.
- Week: both approaches over all 20 legs with trial counts, tool tilt question answered.
- Current state: scene and leg population done (`src/applications/pork_leg_alignment/sim/product.py`); arm IK and
  gripper exist; no saw, no alignment behaviour yet. The sim arm is a UR5e, rated for 5 kg; the
  legs weigh 9 to 15.5 kg, so the lift test needs a heavier arm model.
- [x] Saw modelled and cutting (2026-09-14: `src/applications/pork_leg_alignment/sim/saw.py`, video
  `~/Videos/meat-cell/saw-cut.mp4`)
- [x] Cut starts at blade contact, leg drawn whole until then
- [x] Hold-down belt and blade push-back (`src/applications/pork_leg_alignment/sim/hold_down.py`,
  `scripts/measure/hold_down.py`; videos `saw-cut-hold-down.mp4`, `saw-cut-no-hold-down.mp4`)
- [ ] Measure or source the saw's feed resistance and the hold-down press force
- [ ] Approach A running on one leg
- [ ] Approach B running on one leg, tilt tested
- [ ] Both on several legs, video
- [ ] Both over 20 legs with trial counts

## 4. SCARA vs 6-DOF evidence

- Wed: spec, cost and washdown table from `library/topics/arm-selection-scara-vs-six-axis.md`;
  both arm types modelled in sim, reach checked against belt and leg sizes.
- Week: cycle time and success on the same alignment task, side by side.
- [ ] Table
- [ ] SCARA model in sim
- [ ] Reach check
- [ ] Side-by-side run

## 5. Perception evidence

- Wed: deterministic depth pipeline measured on legs: hock and trotter position error, leg yaw
  error against ground truth, under the modelled degradations. Criteria for when learned wins.
- Week: a learned baseline on the same test set.
- Current state: pipeline measured on slabs; on a leg the old pose estimator was off by 47 mm and
  19 degrees because it uses the area centroid, not the hock.
- [x] Whole-leg segmentation from depth over 20 legs × 9 poses, with and without edge effects
  (2026-09-15, [[2026-09-15-leg-segmentation]])
- [x] Learned baseline, first pass: small U-Net trailed geometry by 3 mm from a label-shift bug;
  fixed, retraining 2026-09-15
- [x] Real plant footage: colour rule 14 of 55 legs whole and separate, SAM + colour 36
- [ ] Retrained U-Net compared, decision recorded
- [ ] Hock and trotter keypoints from depth
- [ ] Error table over 20 legs

## 6. Skill library skeleton

- Wed: contract interface (inputs, preconditions, outputs, success, failure, recovery), folder
  layout matching Neil's layers, observe, acquire and orient against the sim, with tests.
- [ ] Contract interface
- [ ] Layout
- [ ] Three skills with tests

## 7. Learning plan

- Wed: one page. What is learned and why (keypoints only if 5 fails its numbers; a residual on
  orient if the deterministic controller misses), data source (sim, then teleop on the lab
  cobot), training on local GPUs.
- [ ] Page

## Side tasks

- Lab cobot: model unknown. A photo of the base or controller label identifies it; then a
  connection checklist from `sops/robot-bring-up.md`. Suitable to hand to a teammate.
- Three videos from Neil still to download (IMG_1008, IMG_1003, IMG_1004).

Background reading for 1 and 6: [[policy-composition-primitives-controllers-diffusion]],
[[policy-composition-energy-products]], [[policy-composition-latent-skills]].
