---
title: "SpeedFolding: Learning Efficient Bimanual Folding of Garments"
date: 2026-09-06
tags: [paper, deformable, cloth, bimanual, self-supervised, pick-and-place, throughput]
status: draft
source: https://arxiv.org/abs/2208.10552
---

# SpeedFolding (Avigal, Berscheid, Asfour, Kröger, Goldberg, 2022)

Read from arXiv 2208.10552v2 (9 Sep 2022); venue not stated (IROS 2022, unverified). A
bimanual ABB YuMi takes a crumpled garment to folded in about two minutes, with the
smoothing policy learned on the real robot from 4300 actions.

## Problem

Folding needs the garment smooth first. Prior smoothing was single-arm quasi-static
pick-and-place needing many actions, or heuristic pipelines at 10 to 20 min per garment
(3 to 6 folds per hour, Sec. II). FlingBot reaches about 80% coverage in 3 flings but its
4-DoF parameterisation fixes the distance and rotation between the two grasp points,
cannot finish smoothing, and loses the grasp in more than 25% of actions.

## Core idea

Predict two unconstrained planar gripper poses (x, y, theta) for each arm with one network,
BiMaMa-Net, over a small set of primitives, and let a learned "sufficiently smoothed"
classifier, not coverage, decide when to switch from smoothing to folding. Folds are then
executed from user-drawn folding lines on a template mask, so the same system folds a
towel or a t-shirt by changing the instruction, not the model.

## Method details that matter for reimplementation

- Primitives (Sec. IV-A). Learned: fling (pick two points, lift, stretch to a force
  threshold on the arm's internal sensors, fling forward and back), pick-and-place with the
  second arm pinning the cloth, drag away from the mask centroid. Heuristic: fold (both
  arms pick-and-place at once), move (drag the centroid toward the robot for reach). All
  grasps approach 4 cm above, tilt 8 degrees so one fingertip is lower, and slide 1 cm.
- BiMaMa-Net (Sec. IV-B): ResNeXt-50 shared encoder on a 256x192x2 depth-plus-grayscale
  image; a classification head picks the primitive; a U-Net decoder outputs value maps for
  N = 20 orientations; sampled poses become descriptors (value, position, sin and cos of
  theta, primitive, learned embedding); a final head scores descriptor pairs. Training
  samples poses proportional to sqrt(Q), inference to Q^2. Separate decoders when the two
  poses have distinct roles (pick versus place).
- Reachability (Sec. IV-C): a one-time IK boundary search per arm and per theta gives
  binary masks that gate sampling, so every action has at least one reachable pose per
  arm; inter-arm collision is checked and the next-best pair used if needed.
- Reward for self-supervision: clipped tanh of weighted coverage change plus classifier
  confidence change. Human-annotated actions get a fixed reward r_h = 0.8 and a Gaussian
  target around the pixel; only actions with reward at or above r_c = 0.3 train the
  classification head. Exploration samples the top N_s = 50 actions; resets are a random
  grasp and drop.
- Data (Sec. V-A): 600 scenes annotated in 1 h, 2200 self-supervised actions in 16 h, 1500
  copied and re-annotated in 3 h, total 4300, one t-shirt. Augmentation: translation,
  rotation, flip, resize, brightness, contrast.
- Hardware: ABB YuMi with printed teeth on the fingertips, a sponge mat so fingers get
  under the cloth, Photoneo PhoXi for depth and grayscale, a 1080p webcam for coverage
  because the PhoXi field of view often misses the garment. RTX 2080 Ti; 126 ms per action.
- Folding (Sec. IV-E): a particle-swarm optimiser registers the template to the mask by
  an affine transform; for each folding line the two pick points maximise the area of the
  quadrilateral formed with the line's mask entry and exit points, and place poses mirror
  the picks across the line. "2-second fold" is a t-shirt-only heuristic; fling-to-fold
  merges the first fling with the first fold using known t-shirt dimensions.

## Result that matters

End-to-end, 15 trials per row, success by majority of three reviewers, horizon 10 actions,
motion-planning aborts excluded (Table I):

| Smoothing net | Folding | Garment | Smoothing actions | Success | Cycle time s | Folds/h |
|---|---|---|---|---|---|---|
| Max value map (no correspondence) | Instruction | trained t-shirt | 5.1 | 80% | 167.4 | 21.5 |
| BiMaMa-Net | Instruction | trained t-shirt | 3.0 | 93% | 116.9 | 30.8 |
| BiMaMa-Net | 2-second fold | trained t-shirt | 3.0 | 53% | 182.4 | 19.7 |
| BiMaMa-Net | Fling-to-fold | trained t-shirt | 1.8 | 93% | 87.9 | 40.9 |
| BiMaMa-Net | Instruction | unseen towel | 1.7 | 87% | 59.2 | 52.9 |
| BiMaMa-Net | Instruction | unseen t-shirt | 4.8 | 80% | 141.1 | 20.4 |

The unseen rows are my reading of the two-column table; the towel needed 20 extra
"sufficiently smoothed" images and a retrain, the unseen t-shirt did not (Sec. V-D). Grasp
success on the known garment is above 96%. FlingBot's pretrained model did not reach 80%
coverage in this cell, attributed to grasp failures in the different setup (Sec. V-B).

## What it changes in practice

- The throughput unit is folds per hour including failures, and the paper reports cycle
  time over both successes and failures. That is the number a line manager wants; success
  rate alone hides a 182 s cycle at 53%.
- Coverage is the wrong stop criterion for anything that will be folded or placed in a
  fixture; a learned "ready" classifier trained on a few hundred images replaced it here
  and is cheap to collect.
- 4300 actions in about 20 h on one garment, then transfer to a different colour and
  stiffness with no retraining, is the data budget for a fling-style cloth cell. Shape
  transfer needed extra classifier images.

## Known limitations and follow-ups

- Most grasp failures are the cloth slipping during the pre-fling stretch (Sec. V-E).
- Fling is a cloth move; a fillet does not survive it. The transferable pieces for meat are
  the pair-of-poses network, the reachability masks, and the template-line placement.

## Open questions

- 15 trials per row gives a Wilson 95% interval of 0.70 to 0.99 at 14/15 (see
  `library/topics/policy-evaluation.md`); the 80% versus 93% gap is suggestive, not settled.
- Motion-planning aborts were excluded from every row; the abort rate is not reported.

## Sources

- Paper: https://arxiv.org/abs/2208.10552 (v2, 9 Sep 2022). Sec. IV, V; Table I; Fig. 2, 7, 8.
- Code, video, datasets: https://pantor.github.io/speedfolding
