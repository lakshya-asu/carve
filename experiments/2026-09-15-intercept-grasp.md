---
title: Intercept and grasp a moving leg from perception, deterministic against learned, on two arms
date: 2026-09-15
tags: [experiment, meat-cell, grasp, intercept, learning, ros2, moveit, scara, six-axis]
status: draft
decision: which grasp policy the cell runs, whether the tool needs to tilt, and whether the SCARA stays in the running
---

# Experiment: intercept-grasp

Written before any run, per the [experiment protocol](../sops/experiment-protocol.md). Pipeline
step 3 in the order Lakshya set on 2026-09-15 (segment, centre of gravity, then grasp point and
intercept). Lakshya's brief the same day: feed what perception and the encoder give (outline,
centroid, centre of gravity, belt speed and acceleration) into the grasp; define the inputs and
outputs of a learned grasp model and a deterministic approach; A/B test them on the SCARA and the
six-axis arm; find out whether the tool needs to tilt; send the action over ROS 2 to MoveIt and an
IK engine, modular so it works for other robots.

It absorbs the pre-registered `2026-09-15-alignment-approaches.md` arm and tilt rules, which were
never run, and replaces its ground-truth input with perception.

## The pieces and where they live

| Layer | What it does | Code | State |
|---|---|---|---|
| Perception | Mask, column centre of gravity, outline centre | `leg_segmentation.py`, `centre_of_gravity.py` | measured (steps 1, 2) |
| Leg description | Axis from ham to trotter, width and height profile along it, belt coordinates | `leg_perception.py` | tested against true shank, 2 poses |
| Belt state | Travel, speed, acceleration fitted over 0.3 s of encoder readings | `belt_state.py` | tested on synthetic encoders |
| Policy | `LegPerception` in, `GraspAction` out; deterministic or learned | `grasp_policy.py` | deterministic built; learned specified below |
| Intercept | Meeting time and point with acceleration, latency, pick window, stopped belt | `intercept.py` | tested |
| Waypoints | Above, meet, follow while closing; same for every arm | `grasp_execution.py` | tested |
| Executor | IK per arm, trajectory, gripper; refuses what the arm cannot do | simulator IK now; ROS 2 `grasp_executor_node` with MoveIt `compute_ik` | ROS 2 node built, not run against MoveIt (installs missing) |

## Inputs and outputs of any grasp policy

Input, `LegPerception` (`meat_cell_sim/grasp_action.py`, ROS 2 `meat_cell_msgs/LegPerception`):
exposure stamp and encoder travel; belt surface height; column centre of gravity (3,); outline
centre (2,); axis yaw from ham to trotter; length; volume; 40 cross sections along the axis, each
with its distance from the ham end, centreline point, width and top height. Belt state alongside:
speed and acceleration.

Output, `GraspAction` (`meat_cell_msgs/GraspAction`): grasp point on the leg in belt coordinates (x
along the belt minus travel, y, z); the line the jaws close along; tool tilt about that line;
opening; approach distance; closing time. No joint values and no robot name: that is what lets one
policy drive any arm, and an arm that cannot do what is asked refuses with a declared outcome.

## Policy A: deterministic (`ShankGraspRule`)

Grip the shank at 0.66 of the perceived length from the ham end (the existing skill's station),
at the local centreline, jaws across the local direction of the centreline, opening the local width
plus 40 mm, grasp height the top minus half the width, tool vertical unless a tilt is configured.
Checked on one leg at two yaws in simulation: within 20 mm of the true shank point and 8 degrees of
square to it (`tests/test_grasp_policy.py`).

## Policy B: learned

Same input and output types. Specified now, trained only after policy A has run the protocol below.

- Input features (`learned_grasp_policy.grasp_features`, 126 values): for each of the 40 cross
  sections, width, top height and centreline offset across the axis; then length, volume, where the
  centre of gravity sits along the leg, the outline centre's offset from it, belt speed and belt
  acceleration. Only what `LegPerception` carries, so the ROS 2 message is enough to run it.
- Output: grasp offset along and across the axis from the deterministic grasp, jaw-line turn, and
  a tilt class of 0, 15 or 30 degrees, ignored on an arm that cannot tilt. A zero output is the
  deterministic grasp exactly (`tests/test_learned_grasp_policy.py`).
- Model: a small multilayer perceptron trained in torch and exported to numpy, because the ROS 2
  Python has no torch (`LearnedGraspPolicy` loads the exported weights).
- Labels: for each training state (100 legs of `leg_population(100, seed=1)`, random poses and belt
  speeds 0.20 to 0.40 m/s), candidates on a grid around the deterministic grasp are each executed in
  simulation on the floating gripper (no arm, as in section 6 of the plan) and scored by the outcome
  below; the label is the best-scoring candidate. The model is trained by regression and
  classification on those labels.
- It replaces policy A only under the rule below.

## Protocol

- Legs: `leg_population(20, seed=0)`, the test legs of steps 1 and 2; never used in training.
- Arrivals: yaw {-35, 0, +35} degrees, far end {20, 70, 120} mm from the rail, belt 0.30 m/s, plus
  each at 0.20 and 0.40 m/s held out of training; one arrival set per leg, identical for every
  condition.
- Chain: Gemini 335L model with edge effects, geometric segmenter, column centroid,
  `perceive_leg`, the policy, `plan_intercept` with the belt state from simulated encoder readings,
  waypoints, the arm's IK, the saw's scoring where the approach includes the turn.
- Conditions: policy A and B × UR20 (tilt 0, 15, 30 degrees) and SR-20iA (tilt 0), the jaw gripper.
- Outcome per episode, from the declared set: closed and held through a 5 mm lift with the leg
  following the tool (the existing `lift_followed` check), `no_feasible_intercept`,
  `tool_cannot_tilt`, `ik_failed`, `closed_on_nothing`, `slipped`. Also the miss at the meeting,
  mm, between the jaw centre and the true grasp point; cycle time from command to lift; policy
  compute per decision, ms.

## Decision rules, written before any run

1. Learned against deterministic, per arm: policy B replaces A only if it holds more legs through
   the lift, paired by leg and arrival (McNemar, p < 0.05), and its median meeting miss is not
   worse by more than 2 mm. Otherwise A stays and B is reported.
2. Tilt (from the alignment experiment, H2): the tilted UR20 must beat the vertical UR20 by more
   than 2 legs of 20 under the better policy; otherwise tilt is not needed.
3. Arm (from the alignment experiment): if tilt is not needed and the SR-20iA holds within 2 legs
   of 20 of the UR20, the SCARA stays in the running on cost and speed; if tilt is needed or the
   SCARA falls short, the plan proposes the six-axis arm.

## Blockers before the first run

- Arm servo sag (task 4b): the UR20 rose 1.6 mm and the SR-20iA 2.6 mm of a commanded 5 mm lift, so
  the lift check cannot yet be trusted on either arm.
- A skill that follows the belt while closing: the executor sends timed waypoints, but the simulated
  arms are driven by joint ramps to fixed targets (`cell.move_arm`); the trajectory has to be
  followed on the simulation clock.
- Tilted shank grasps have no IK path yet in the simulator skills (`arm.solve_ik_rotation` exists
  and is used by the trotter grasp).
- ROS 2 and MoveIt: the messages build and the nodes are written; running them needs
  `ros-humble-moveit`, `ros-humble-pick-ik`, robot descriptions and MoveIt configs for both arms, and
  MuJoCo in the Humble Python or `mujoco_ros2_control`. Installing is Lakshya's call.

## Results

Not run.

## Decision taken and why

Not yet taken.
