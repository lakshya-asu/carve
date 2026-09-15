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

Input, `LegPerception` (`src/applications/pork_leg_alignment/grasping/leg_perception.py`, ROS 2 `meat_cell_msgs/LegPerception`):
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
square to it (`tests/applications/pork_leg_alignment/grasping/test_shank_grasp_rule.py`).

## Policy B: learned

Same input and output types. Specified now, trained only after policy A has run the protocol below.

- Input features (`learned_grasp_policy.grasp_features`, 126 values): for each of the 40 cross
  sections, width, top height and centreline offset across the axis; then length, volume, where the
  centre of gravity sits along the leg, the outline centre's offset from it, belt speed and belt
  acceleration. Only what `LegPerception` carries, so the ROS 2 message is enough to run it.
- Output: grasp offset along and across the axis from the deterministic grasp, jaw-line turn, and
  a tilt class of 0, 15 or 30 degrees, ignored on an arm that cannot tilt. A zero output is the
  deterministic grasp exactly (`tests/applications/pork_leg_alignment/grasping/test_learned_grasp_policy.py`).
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
- The lift check: the simulated arms still sag under a leg, so holding through a 5 mm lift cannot be
  scored yet, and grip force against the leg's weight is unmeasured.
- UR20 IK through MoveIt's KDL plugin can return a solution on a different arm configuration from
  the seed; the executor has to reject solutions far from the current joints before timing them.

## Results

The protocol above has not run. What has run, 2026-09-15, is a shakedown of the chain through
ROS 2 and MoveIt against the simulated cell, one leg per run, to find what breaks before the
protocol is worth running.

Setup: MoveIt 2.5.9 in the RoboStack conda env `ros_moveit` (installed without sudo); robot
descriptions generated from the simulator's arm constants (`applications/pork_leg_alignment/sim/
robot_description.py`), checked against MuJoCo's tool site within 0.1 mm at random joints; MoveIt's
`compute_ik` for the UR20 checked on three tool poses, one tilted 30 degrees, all within 0.001 mm;
the SR-20iA's IK in closed form on the same `GetPositionIK` interface. `ros2 launch
pork_leg_cell_ros sim_grasp.launch.py`: the MuJoCo bridge publishes the camera's leg (edge effects
on), `grasp_policy_node` runs the shank rule, `grasp_executor_node` plans the intercept, solves IK
and sends one timed trajectory; the bridge scores the tool against the true shank point at the
meeting time and reads the jaw opening 0.3 s after the jaws should have closed. Default leg, belt
0.30 m/s, outline centre 450 mm across the belt.

Fixes found on the way, each a defect in the chain rather than the arms: the camera renderer's EGL
context was used from another thread; move_group aborts (not refuses) when the IK seed names a joint
its model lacks (the belt joint in `joint_states`); rclpy's synchronous `send_goal` waits for the
whole trajectory, so the jaws were opened only after arrival; trajectories are now stamped with the
planning time; and edge-effect pixels made the perceived leg 1.52 m long, putting the grasp 155 mm
off on both arms (fixed in `perceive_leg`, now tested with edge effects).

Runs after those fixes:

| Arm | Leg yaw | Tool to true shank point at the meeting, mm | along belt / across / height | Joint tracking error, max | Jaw opening after closing, mm (shank 101) |
|---|---|---|---|---|---|
| SR-20iA | 0 | 19.4 | -11.5 / +10.5 / +11.6 | 0.02 rad | 115.7 |
| SR-20iA | -35 | 16.9 | -8.5 / +10.0 / +10.6 | 0.02 rad | 110.5 |
| UR20 | +35 | 52.1 | -15.9 / -4.6 / +49.4 | 0.05 rad | 110.1 |
| UR20 | 0 | 476.5 | +424.9 / +121.9 / +177.7 | 2.41 rad | 19.9 |

- The chain works end to end on both arms from the camera: perception, policy, intercept, IK
  through MoveIt or the closed form, timed trajectory, gripper.
- The SR-20iA meets the true grasp point within 17 to 19 mm, with a consistent 10 to 12 mm too
  high; its tilt refusal also works through ROS (15 degrees asked, refused before planning).
- UR20 at yaw 0: KDL's answer put the arm on a configuration up to 2.4 rad from where it stood, and
  the arm could not get there in the 2.1 s planned. At yaw +35 the tool was 49 mm too high.
- Correction, same day: the first reading of the jaw column was wrong. It compared the opening with
  the shank's width at the two-thirds point (101 mm), and called 110 to 116 mm a miss. The pads are
  120 mm long along a leg that widens toward the ham. A rerun of the SR-20iA square case with the
  bridge checking contact in MuJoCo: gripper opened to 142 mm at 1.45 s, close commanded at 2.91 s
  (the meeting), opening 115.7, 115.0 and 114.9 mm at 0.9, 1.2 and 1.6 s after, the widest section
  under the pads 113.0 mm, and both pads in contact with the leg at all three. So the SR-20iA square
  run closed on the leg. The SR-20iA -35 and UR20 +35 runs (both 110 mm) very likely did too, but
  contact was not checked on them; the UR20 yaw 0 run closed on nothing (20 mm).
- In the first SR-20iA run the executor then received further grasp actions and refused them with a
  predicted closing position of 16 m, which points at the belt state after the bridge's first
  trajectory; not yet diagnosed.

## Decision taken and why

Not yet taken.
