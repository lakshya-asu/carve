---
title: "Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World"
date: 2026-09-05
tags: [paper, sim-to-real, domain-randomization, perception, object-localization, mujoco]
status: draft
source: https://arxiv.org/abs/1703.06907
---

# Domain randomization (Tobin, Fong, Ray, Schneider, Zaremba, Abbeel 2017)

## Problem

Networks trained on rendered images did not transfer to real cameras, and the
standard fixes (system identification, photorealistic rendering, domain
adaptation on real labels) were slow, expensive or needed real data. No one
had yet shown a deep network trained only on simulated RGB doing a precision
robot task in the real world ([Tobin et al. 2017, Sec. I](https://arxiv.org/abs/1703.06907)).

## Core idea

Do not match the real world; randomize the simulator so widely that the real
world looks like one more sample. Train an object localizer on hundreds of
thousands of MuJoCo renders with random non-photorealistic textures, lighting,
camera pose and distractors, then run it unchanged on a real webcam. It
localizes to about 1.5 cm and supports grasping in clutter
([Sec. I, III](https://arxiv.org/abs/1703.06907)).

## Method details that matter for reimplementation

- Randomized per sample: number and shape of distractors (0 to 10), position
  and texture of every object, textures of table, floor, skybox and robot,
  camera position (10 x 5 x 10 cm box), orientation (up to 0.1 rad) and field
  of view (up to 5 %), number, pose and specularity of lights, image noise
  ([Sec. III-A](https://arxiv.org/abs/1703.06907)).
- Textures are one of: flat random RGB, gradient between two random RGB
  values, checkerboard of two random RGB values. The target object's color is
  random too, so the detector must key on shape and size only
  ([Sec. III-A](https://arxiv.org/abs/1703.06907)).
- Task simplification: table height is fixed, so the single uncalibrated
  monocular image gives a 2D estimate lifted to (x, y, z) ([Sec. III-A](https://arxiv.org/abs/1703.06907)).
- Network: VGG-16 convolutional stack, fully connected layers cut to 256 and
  64, no dropout, 224 x 224 input, L2 loss on object coordinates, Adam at
  about 1e-4 (1e-3 collapses to predicting the table center). Small sweep over
  learning rates {1e-4, 2e-4} and batch sizes {25, 50, 100}
  ([Sec. III-B, IV-A, Fig. 2](https://arxiv.org/abs/1703.06907)).
- ImageNet pretraining was assumed necessary and turned out not to be: with
  enough data, random initialization matches or beats it; pretraining helps
  only in the low-data regime ([Sec. IV-C, Fig. 4](https://arxiv.org/abs/1703.06907)).

## Result that matters (with n and hardware)

Real test set: 480 webcam images, 8 geometric objects x 60 images (20 alone,
20 with distractors, 20 partially occluded), camera fixed 70 to 105 cm from
the objects, lighting and background uncontrolled, ground truth from a grid on
the table ([Sec. IV-B](https://arxiv.org/abs/1703.06907)).

- Mean error about 1.5 cm across objects. Examples (object only /
  distractors / occluded, cm): cone 1.3 / 1.5 / 1.4, cube 1.3 / 1.8 / 1.4,
  hexagonal prism 0.7 / 0.6 / 1.0, tetrahedron 0.8 / 1.0 / 3.2. Simulated
  error is 0.3 to 0.5 cm, so the detector still overfits the simulator
  ([Table I](https://arxiv.org/abs/1703.06907)).
- Data sweep: usable from 5k samples with pretraining, improving to about 50k
  ([Fig. 4](https://arxiv.org/abs/1703.06907)). Texture sweep at 10k images:
  accuracy degrades sharply below 1000 unique texturizations; at 1000
  textures, 10k images is no better than 1k, so in the low-data regime
  texture variety matters more than pose variety ([Fig. 5](https://arxiv.org/abs/1703.06907)).
- Ablation at 20k images (object only / distractors / occluded, cm): full
  method 1.3 / 1.8 / 2.4; no noise 1.4 / 1.9 / 2.4; no camera randomization
  2.0 / 2.4 / 2.9; no distractors in training 1.5 / 7.2 / 7.4
  ([Table II](https://arxiv.org/abs/1703.06907)).
- Grasping on a Fetch robot with off-the-shelf motion planning: 38 of 40
  trials over 20 increasingly cluttered scenes for two detectors, including
  distractor poses not seen in training. A detector for a YCB Spam can
  trained with geometric distractors and tested with unseen food items: 9 of
  10 ([Sec. IV-D](https://arxiv.org/abs/1703.06907)).

## What it changes in practice

This is the origin of the visual randomization defaults now built into Isaac
Lab and MuJoCo pipelines. The transferable numbers: at least ~1000 distinct
texturizations, distractors in training if there will be clutter at test, and
camera-pose jitter in place of calibration. The negative result on pretraining
means a from-scratch detector is a fair baseline when sim data is plentiful.

## Known limitations and follow-ups

- 2D localization on a fixed-height table, no orientation, one object class
  per detector ([Sec. III-A, IV-A](https://arxiv.org/abs/1703.06907)).
- Accuracy is comparable to, not better than, classical monocular pose
  pipelines of the time at higher resolution ([Sec. IV-B](https://arxiv.org/abs/1703.06907)).
- Visual randomization only; physics randomization is cited (Mordatch,
  Antonova) but not combined here ([Sec. II-C](https://arxiv.org/abs/1703.06907)).
- Authors list higher resolution, stereo or depth, and combining with domain
  adaptation as next steps ([Sec. V](https://arxiv.org/abs/1703.06907)).

## Open questions

- Which of the seven randomization axes the 1000-texture threshold depends
  on; the sweep varies textures and lighting together.
- How the 1.5 cm figure scales with camera distance beyond 105 cm.

## Sources

- [Tobin, Fong, Ray, Schneider, Zaremba, Abbeel. Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World. arXiv 1703.06907](https://arxiv.org/abs/1703.06907)
- [Project videos](https://sites.google.com/view/domainrandomization/)
