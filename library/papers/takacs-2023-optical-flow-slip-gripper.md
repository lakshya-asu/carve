---
title: "Image-Processing Based Methods to Improve the Robustness of Robotic Gripping"
date: 2026-09-06
tags: [paper, meat-cell, gripper, slip-detection, optical-flow, food-handling, robutcher]
status: draft
source: https://arxiv.org/abs/2307.05648
---

# Optical-flow slip detection in a meat-cell gripper (Takács, Nagyné Elek, Haidegger, 2023)

Read from arXiv 2307.05648v1 (11 Jul 2023; authors and title confirmed from the arXiv
record). A short paper, mostly a survey of optical flow in surgical robotics, whose one
original contribution is the slip-detection method inside the RoBUTCHER project's smart
gripper for pig carcass parts. No experiment, trial count, or detection rate is reported.

## Problem

Meat-cell grasping targets vary in size, weight, elasticity, and surface; they are wet,
soft, and slippery; a dropped piece is contaminated and unsellable (Sec. II-B). The
RoBUTCHER Meat Factory Cell puts two high-payload industrial robots with custom
end-of-arm tools around a motorised Carcass Handling Unit, and the gripper is one of the
tools (Sec. I-A).

## Core idea

Put an endoscopic camera inside the passive finger, behind a lens, so that the encircling
motion of the active fingers presses the tissue against the lens at the camera's 2 cm
focal distance. Run Farneback dense optical flow on the cropped image; treat the ~2 cm
circle of tissue as rigid, average the flow field to one velocity, and read slip off the
y component. A nonzero x component is rotation in the grasp and needs no action; a y
velocity is slip, and the gripper either raises its own clamping force or reports to the
cell controller and operator (Sec. II-B).

## Method details that matter for reimplementation

- Gripper mechanics ([Takács et al. 2020], their ref. 23): encircling, centring closure
  that accepts targets 2 to 6 cm across with up to 4 cm of positional error, fail-safe
  grasp, force-controlled clamping. The paper calls this tolerance "robustness by design"
  as opposed to sensing.
- Sensing: endoscopic camera, 640x480 at 30 fps, 2 cm focus, 70 degree field of view,
  built-in LEDs; Raspberry Pi Zero W runs the flow in Python with OpenCV. Frames are
  cropped and downscaled for runtime; the camera housing outside the circular region of
  interest is static and serves as a zero-flow reference (Fig. 4).
- Architecture: the cell is centralised (one computer for sensors, VR, AI, robot control)
  but the gripper and knife are embedded systems with their own compute and links (Sec.
  II-B).
- Waterproofing is the lens; the paper says nothing about washdown rating, cleaning, or
  lens fouling.

## Result that matters

There is none in the quantitative sense. Fig. 4 shows two frames: (a) flow vectors in y
during a real slip, (b) flow in x during in-grasp rotation. No threshold value, latency,
false-positive rate, or trial count is given. The surgical section cites other groups'
numbers (a 74 to 92% gesture-recognition accuracy on JIGSAWS from Sarikaya and Jannin), not
the authors' own gripper.

## What it changes in practice

- A camera behind a lens in the finger is the cheapest slip sensor that survives wet
  tissue, and dense flow on a Pi Zero is fast enough at 30 fps on a cropped frame. That is
  worth copying as a grasp-verification signal; see
  `library/topics/perception-tactile-and-force.md` and the tactile row in
  `library/topics/deformable-object-manipulation.md`.
- The rigid-patch assumption is the whole method. If the tissue inside the 2 cm window
  shears (skin over fat), the average flow reports slip that is not happening. Validate on
  the actual cut before trusting the y threshold.
- The deformables note lists this paper under tactile-verified grasping; with no reported
  rate, treat it as a design reference, not evidence of a working detector.

## Known limitations and follow-ups

- Survey-style paper; no evaluation. The gripper mechanics are in the 2020 CINTI paper
  (their ref. 23, not read).
- Farneback needs texture; wet, specular, uniformly pink surfaces under LED glare are the
  hard case and are not discussed.
- Related RoBUTCHER outputs in this library: Esper et al. 2024 and Mason et al. 2022 in
  `library/topics/meat-cutting-automation.md`.

## Open questions

- What y-velocity threshold, in pixels per frame, separates slip from deformation, and did
  they ever measure it?
- Does the gripper act on slip autonomously (raise force) in the deployed cell, or only
  report? Both are described as options.

## Sources

- Paper: https://arxiv.org/abs/2307.05648 (v1, 11 Jul 2023). Sec. I-A, I-B, II-B; Fig. 2,
  3, 4.
- arXiv record for title and authors:
  https://export.arxiv.org/api/query?id_list=2307.05648
- RoBUTCHER: https://cordis.europa.eu/project/id/871631
