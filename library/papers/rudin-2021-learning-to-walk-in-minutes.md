---
title: "Learning to Walk in Minutes Using Massively Parallel Deep Reinforcement Learning"
date: 2026-09-05
tags: [paper, reinforcement-learning, legged-locomotion, sim-to-real, isaac-gym, ppo, curriculum]
status: draft
source: https://arxiv.org/abs/2109.11978
---

# Learning to Walk in Minutes (Rudin, Hoeller, Reist, Hutter 2021)

## Problem

Sim-trained locomotion policies took hours to days: 12 h for blind rough
terrain, 82 to 120 h for perceptive locomotion in the cited prior work. Slow
iteration hides reward bugs, and CPU simulators cap parallel robots at the
core count ([Rudin et al. 2021, Sec. 1](https://arxiv.org/abs/2109.11978)).

## Core idea

Run simulation, observation and reward computation, policy inference and the
PPO update all on one GPU with Isaac Gym, simulate thousands of ANYmal robots
in a single scene, and adapt PPO to that regime: few steps per robot per
update, very large mini-batches, and bootstrapped values at time-outs. Add a
terrain curriculum where each robot's difficulty level follows its own
progress on a tiled mesh. A perceptive rough-terrain policy trains in under
20 minutes and walks on the real robot
([Sec. 2, 3, 4](https://arxiv.org/abs/2109.11978)).

## Method details that matter for reimplementation

- Batch B = n_robots x n_steps. Below about 25 consecutive steps per robot
  (0.5 s at 50 Hz) GAE has too little temporal context and learning fails;
  the deployed config uses 24, so treat the threshold as approximate.
  Episode time-out is 20 s, so one episode spans many updates ([Sec. 2.2.1](https://arxiv.org/abs/2109.11978)).
- Time-out bootstrapping: distinguish termination from time-out and add the
  critic's value estimate to the reward at time-outs. Gym does not expose
  this; Stable-Baselines ignores it. Worth 10 to 20 % total reward on both
  terrains ([Sec. 2.2.2, Appendix A.2](https://arxiv.org/abs/2109.11978)).
- PPO settings for the deployed policy: 4096 robots x 24 steps = 98304
  samples per update, mini-batch 24576, 5 epochs, clip 0.2, entropy 0.01,
  gamma 0.99, GAE lambda 0.95, adaptive learning rate targeting KL 0.01
  (halve by 1.5x above 2x target, grow by 1.5x below 0.5x target), 1500
  updates ([Appendix A.4](https://arxiv.org/abs/2109.11978)).
- Curriculum: five terrain types (flat, slope, rough, discrete obstacles,
  stairs) tiled as 8 m squares by level. Walking off the tile promotes a
  robot; covering under half the commanded distance demotes it; top-level
  robots respawn at a random level. Steps grow 5 to 20 cm, slopes 0 to 25
  degrees ([Sec. 3.1](https://arxiv.org/abs/2109.11978)).
- Observations: base linear and angular velocity, projected gravity, joint
  positions and velocities, previous actions, 108 terrain heights around the
  base. Actions: PD joint targets at 50 Hz. No gait terms ([Sec. 3.2](https://arxiv.org/abs/2109.11978)).
- Reward: nine weighted terms (Appendix A.3): exp(-||v error||^2 / 0.25)
  tracking, penalties on torques, joint accelerations, action rate and
  collisions, and a feet-air-time bonus.
- Sim-to-real: friction uniform in [0.5, 1.25], base pushes up to 1 m/s every
  10 s, uniform observation noise from hardware data (joint pos 0.01 rad,
  joint vel 1.5 rad/s, heights 0.1 m), and an LSTM actuator network for the
  series-elastic ANYdrives ([Sec. 3.3, Appendix A.5](https://arxiv.org/abs/2109.11978)).
- Throughput: sim dt 0.005 s (4 sim steps per policy step, limited by the
  actuator net), collision bodies pruned to feet, shanks, knees and base.
  4096 robots need 6 GB VRAM headless, 9 GB rendered ([Appendix A.1](https://arxiv.org/abs/2109.11978)).

## Result that matters (with n and hardware)

Hardware: i9-11900K CPU and one RTX A6000 ([Sec. 4.2, footnote](https://arxiv.org/abs/2109.11978)).

- Rough-terrain perceptive policy for ANYmal C: 4096 robots, 1500 updates,
  under 20 minutes. Flat terrain under 4 minutes (abstract; no separate
  config table, so the flat setup is unverified).
- Parallelism sweep (5 runs per point, reward after 1500 updates, curriculum
  disabled): training time scales almost linearly up to 4000 robots; too many
  robots at fixed batch size cuts steps per robot and reward drops sharply;
  the sweet spot is 2048 to 4096 robots with a 100k to 200k batch
  ([Fig. 4](https://arxiv.org/abs/2109.11978)).
- Simulation success (forward command 0.75 m/s): near 100 % on stairs to
  0.2 m; obstacles degrade steadily; slopes fail above 25 degrees going up ([Fig. 5](https://arxiv.org/abs/2109.11978)).
- Same setup retrains ANYmal B and ANYmal C with an arm unchanged; Unitree A1
  needs gains, torque penalties and default pose changed and no actuator
  net; Cassie needs a single-foot-support reward ([Sec. 4.2](https://arxiv.org/abs/2109.11978)).
- Real ANYmal C: policy runs unfiltered from an elevation map built from
  lidar; imperfect maps forced the command limit down to 0.6 m/s. The robot
  climbs and descends stairs and crosses obstacles. No real-world trial
  counts or success rates are reported ([Sec. 4.3](https://arxiv.org/abs/2109.11978)).

## What it changes in practice

This is the paper behind `legged_gym` and, through it, the Isaac Lab
locomotion workflow. Twenty-minute training turns reward shaping into an
interactive loop: change a weight, retrain, watch. The time-out bootstrapping
fix and the "about 25 steps per robot" floor apply to any GPU-parallel PPO,
including manipulation. The curriculum needs no generator network.

## Known limitations and follow-ups

- Stated goal is training speed, not peak performance; the authors point to
  Miki et al.'s teacher-student policy as more reliable on hardware ([Sec. 4.3, 5](https://arxiv.org/abs/2109.11978)).
- Without reward tuning the policy converges to a trot with artifacts such as
  a dragged leg or odd base height ([Sec. 4.2](https://arxiv.org/abs/2109.11978)).
- Rough terrain caps parallelism near 16k robots on one workstation GPU
  ([Sec. 4.1](https://arxiv.org/abs/2109.11978)).

## Open questions

- How much of the 20 minutes is the curriculum versus raw throughput. The
  paper ablates parallelism and bootstrapping but not the curriculum itself.

## Sources

- [Rudin, Hoeller, Reist, Hutter. Learning to Walk in Minutes. arXiv 2109.11978 (v3, Aug 2022)](https://arxiv.org/abs/2109.11978)
- [legged_gym code](https://leggedrobotics.github.io/legged_gym/)
