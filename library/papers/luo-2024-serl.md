---
title: "SERL: A Software Suite for Sample-Efficient Robotic Reinforcement Learning"
date: 2026-09-05
tags: [paper, reinforcement-learning, real-world-rl, manipulation, franka, rlpd, impedance-control]
status: draft
source: https://arxiv.org/abs/2401.16013
---

# SERL (Luo, Hu et al. 2024)

## Problem

Real-world robotic RL had working algorithms but almost no working systems. The
authors argue that implementation details (controller, reward, resets, buffer
handling) matter as much as the algorithm, and that this design space, not the
algorithms, is what stops practitioners from using RL on hardware
([Luo et al. 2024, Sec. 1](https://arxiv.org/abs/2401.16013)).

## Core idea

Ship one vertically integrated stack instead of a menu of algorithms: RLPD as
the learner, a classifier or VICE reward for image tasks, forward-backward
policies for reset-free training, a Gym-style adapter for any arm, and an
impedance controller with reference limiting so random exploration cannot
damage the robot or the part. Then show that this combination learns three
contact-rich tasks in 20 to 105 minutes each with 100 of 100 evaluation
successes ([Sec. 4, Table 2, Fig. 6](https://arxiv.org/abs/2401.16013)).

## Method details that matter for reimplementation

- Learner: RLPD, a SAC variant with high update-to-data ratio, 50/50 batch
  sampling between the demo buffer and the online buffer, and layer norm in
  the critic ([Sec. 4.1](https://arxiv.org/abs/2401.16013)).
- Seeding: 20 teleoperated demonstrations per task, collected with a
  SpaceMouse ([Sec. 5](https://arxiv.org/abs/2401.16013)).
- Reward: hand-specified from end-effector pose for PCB insertion (part held
  rigidly in the gripper); binary image classifier for cable routing and
  relocation, r(s) = log p(success | s). VICE adds every visited state as a
  negative and retrains the classifier each iteration to stop reward hacking
  ([Sec. 4.2](https://arxiv.org/abs/2401.16013)).
- Resets: forward and backward policies, each with its own actor, critic and
  reward, trained by two independent RL agents ([Sec. 4.3](https://arxiv.org/abs/2401.16013)).
- Architecture: three processes (actor, learner, robot environment) so the
  control loop keeps its rate while the learner runs many gradient steps
  ([Sec. 4.4, Fig. 2](https://arxiv.org/abs/2401.16013)).
- Controller: Cartesian impedance F = k_p e + k_d e_dot + F_ff + F_cor at 1 kHz,
  with the RL setpoint arriving at 10 Hz in the paper's example. The safety
  mechanism is clipping the tracking error |e| <= Delta inside the real-time
  loop, which bounds the interaction force to k_p Delta + 2 k_d Delta f. Clipping
  the RL action instead would force micrometre steps for PCB tolerances and
  stall learning ([Sec. 4.5, Fig. 3](https://arxiv.org/abs/2401.16013)).
- Frames: proprioception is expressed relative to the episode's initial
  end-effector frame; the 6-DoF twist action is in the current end-effector
  frame and mapped to the base frame by the adjoint. This is what makes the
  policy tolerate a moved or perturbed target ([Sec. 4.6, Appendix 7.1](https://arxiv.org/abs/2401.16013)).
- Vision: ImageNet-pretrained ResNet-10 feeding a 2-layer MLP; inputs are
  wrist camera images plus end-effector pose, twist, force and torque
  ([Sec. 5](https://arxiv.org/abs/2401.16013)).

## Result that matters (with n and hardware)

Franka Panda, two wrist cameras (one wrist plus one side camera for
relocation), single RTX 4090, 20 demos per task, 100 evaluation trials per task
([Sec. 5, Table 2](https://arxiv.org/abs/2401.16013)):

| Task | Reward | Start-pose bin | Training time | RL success | BC (100 demos) |
|---|---|---|---|---|---|
| PCB component insertion | ground-truth pose | 10 x 10 cm | 20 min | 100/100 | ~10x worse |
| Cable routing | classifier | 20 x 20 cm | 31 min | 100/100 | ~5x worse |
| Object relocation, forward + backward | classifier | 20 x 30 cm | 105 min (two policies) | 100/100 | ~1.7x worse |

The BC ratios are read from Fig. 6; the paper gives them as multipliers, not
as absolute BC percentages. RL cycle times were at least 2x faster than BC and
up to 3x faster than the human demonstrations ([Fig. 7](https://arxiv.org/abs/2401.16013)).
A University of Washington group reproduced the stack on an FMB peg insertion
task: under 3 h setup, 19 min training, 100/100 with 20 demos ([Sec. 5](https://arxiv.org/abs/2401.16013)).

## What it changes in practice

Real-world RL for a single contact-rich skill is a same-day activity when you
have a torque-controlled arm, a wrist camera, 20 demos and a 4090. The
reference-limiting trick is the piece to copy into any impedance controller
you use for exploration, independent of the learner. The relative-frame
formulation should be the default action space for insertion policies.

## Known limitations and follow-ups

- Tasks are short-horizon and single-arm; the authors say classifier rewards
  and forward-backward resets will not fit every setting ([Sec. 6](https://arxiv.org/abs/2401.16013)).
- No human corrections during training. HIL-SERL adds them and reports that
  the harder tasks do not train without them (see
  [luo-2024-hil-serl.md](luo-2024-hil-serl.md)).
- The Table 1 comparison to prior insertion systems mixes setups and is
  qualitative by the authors' own admission ([Sec. 5](https://arxiv.org/abs/2401.16013)).
- The abstract quotes 25 to 50 minutes per policy; Table 2 shows 20, 31 and
  105 minutes, the last covering two policies.

## Open questions

- How much of the 100/100 result depends on the fixed camera rig and the
  small 10 to 20 cm start-pose randomization.
- What the failure mode is when the classifier reward drifts after a lighting
  change on a customer floor. The paper does not test this.
- Whether the stack transfers to a UR or ABB arm without native torque
  control. The impedance design assumes a torque interface.

## Sources

- [Luo, Hu, Xu, Tan, Berg, Sharma, Schaal, Finn, Gupta, Levine. SERL. arXiv 2401.16013](https://arxiv.org/abs/2401.16013)
- [Project page and code](https://serl-robot.github.io/)
