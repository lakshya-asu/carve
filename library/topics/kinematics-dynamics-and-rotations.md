---
title: Kinematics, dynamics, and rotations for a robot learning engineer
date: 2026-09-06
tags: [topic, kinematics, rotations, quaternions, transforms, jacobian, ik, dynamics, trajectories, conveyor, calibration, action-spaces]
status: draft
source: synthesis (primary links inline and in Sources); snippets run against numpy 2.4.6 and scipy 1.17.1 in the rll env on 2026-09-06
---

# Kinematics, dynamics, and rotations for a robot learning engineer

## What it is

The math between a policy's output tensor and a joint moving: how orientation is written down (and in which of several incompatible orders), how frames compose, how joint angles map to a tool pose and back, how joint rates map to tool velocity, what limits a trajectory must respect, and which mass properties a simulator or an impedance controller needs.

The textbook references used throughout are Lynch and Park, *Modern Robotics* (MR, [free PDF](https://hades.mech.northwestern.edu/images/7/7f/MR.pdf)), chapters 3 to 9 and 11, and Siciliano, Sciavicco, Villani, Oriolo, *Robotics: Modelling, Planning and Control* (SSVO, [Springer](https://link.springer.com/book/10.1007/978-1-84628-642-1)), chapters 2, 3, 4, 7, 9. For quaternion algebra the reference is Solà, *Quaternion kinematics for the error-state Kalman filter* ([arXiv:1711.02508](https://arxiv.org/abs/1711.02508)). The tested code lives in `snippets/kinematics.py`.

## Why it matters in the field

Most integration failures in a learned-policy deployment are convention bugs, not model bugs: a quaternion read as `wxyz` from a `xyzw` message, a delta action applied in the base frame that was recorded in the tool frame, a dataset where the quaternion sign flips halfway through an episode so the network learns a discontinuity, an IK call near a wrist singularity that returns a 3 rad/s joint jump for a 1 cm/s Cartesian command.

None of these throws an exception. The tool moves the wrong way, or the policy trains fine and fails on the robot. Every one of them is caught in under an hour by someone who can write the transform chain on paper and check it numerically, and costs a field day otherwise.

## Rotations and their conventions

A rotation matrix R in SO(3) is nine numbers with six constraints (Rᵀ R = I, det R = 1), composes by multiplication, and has no singularities or sign ambiguity (MR 3.2). Everything else is a compression of it with a trap attached.

### Euler angles and the 24 conventions

Three angles about three axes. Twelve axis sequences (six Tait-Bryan like xyz, six proper Euler like zxz) times intrinsic (axes rotate with the body) or extrinsic (axes stay fixed) gives 24 conventions; REP 103 lists Euler angles last among acceptable representations for this reason ([REP 103](https://www.ros.org/reps/rep-0103.html)). The same three numbers (0.3, −0.5, 1.1) rad read four ways, computed with scipy on 2026-09-06:

| scipy sequence | Meaning | Where the body x axis lands | Angle from the `xyz` reading |
|---|---|---|---|
| `xyz` | extrinsic, fixed axes: R = Rz(1.1) Ry(−0.5) Rx(0.3) | (0.398, 0.782, 0.479) | 0 |
| `XYZ` | intrinsic: R = Rx(0.3) Ry(−0.5) Rz(1.1) | (0.398, 0.787, 0.471) | 35.2 degrees |
| `zyx` | extrinsic, first angle about z | (0.838, −0.274, 0.471) | 69.8 degrees |
| `ZYX` | intrinsic, first angle about z | (0.838, 0.259, 0.479) | 45.8 degrees |

ROS roll-pitch-yaw is *fixed axis* x, y, z, so R = Rz(yaw) Ry(pitch) Rx(roll); in scipy that is `from_euler("xyz", [r, p, y])` (lowercase = extrinsic), which equals `from_euler("ZYX", [y, p, r])` (uppercase = intrinsic), both checked numerically ([scipy from_euler](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.from_euler.html)). At pitch = 90 degrees roll and yaw are not separable (gimbal lock); scipy warns and zeroes the third angle. MuJoCo's `eulerseq` defaults to `"xyz"` and applies to the whole model ([MuJoCo modeling](https://mujoco.readthedocs.io/en/stable/modeling.html)). Rule: Euler angles are for humans reading a config file, never for state, storage, or a loss function.

### Axis-angle and rotation vector

ω̂θ, three numbers, the log map of SO(3) (MR 3.2.3). Singular at θ = π (two vectors for one rotation) and the identity has a removable one; fine for small errors, which is why controllers use it (below), and a reasonable regression target for small relative rotations such as delta actions.

### Quaternions and the order trap

Unit quaternion q = (w, x, y, z) = (cos θ/2, sin θ/2 · ω̂), composition by Hamilton product, `q` and `−q` are the same rotation (double cover, Solà §2). The single most expensive convention bug in this field is storage order:

| Library or format | Order | Evidence |
|---|---|---|
| ROS `geometry_msgs/Quaternion` | x, y, z, w | field order in the [.msg](https://github.com/ros2/common_interfaces/blob/humble/geometry_msgs/msg/Quaternion.msg), default `w=1` |
| scipy `Rotation.as_quat()` / `from_quat()` | x, y, z, w default; `scalar_first=True` for w first | [as_quat](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.as_quat.html) |
| Eigen `Quaternion` | constructor takes `(w, x, y, z)`; `coeffs()` and the 4-vector constructor store `[x, y, z, w]` | [Eigen docs](https://libeigen.gitlab.io/eigen/docs-nightly/classEigen_1_1Quaternion.html) |
| PyTorch3D | w, x, y, z ("real part first") | [transforms](https://pytorch3d.readthedocs.io/en/latest/modules/transforms.html) |
| MuJoCo `quat` attribute, `mjData.xquat` | w, x, y, z | [modeling](https://mujoco.readthedocs.io/en/stable/modeling.html) |
| Isaac Lab `isaaclab.utils.math` | w, x, y, z; `convert_quat(q, to="xyzw")` swaps | [math.py on main](https://github.com/isaac-sim/IsaacLab/blob/main/source/isaaclab/isaaclab/utils/math.py) |
| Isaac Sim core (`get_world_pose`) | w, x, y, z | (unverified against the 6.0 docs; consistent with Isaac Lab) |
| Unity `Quaternion` | x, y, z, w; left-handed, y up | [Unity](https://docs.unity3d.com/ScriptReference/Quaternion.html); handedness (unverified from that page) |
| Unreal `FQuat` | X, Y, Z, W; left-handed, z up, centimeters | (unverified; page fetch failed 2026-09-06) |
| Drake, pinocchio, KDL | Drake `Quaternion<T>` is Eigen (w first in constructor); pinocchio stores Eigen `coeffs()` order xyzw in `q` vectors; KDL `Rotation::GetQuaternion(x, y, z, w)` | (unverified per API; check before use) |

The [isaac-lab](../tools/isaac-lab.md) entry says Isaac Lab 3.0 moved to XYZW; the main-branch docstrings still say `(w, x, y, z)` and the linked 3.0 beta 2 discussion does not mention the change, so treat that claim as unverified and test `convert_quat` on the installed version. Unity and Unreal additionally change handedness, so a quaternion crossing from a right-handed robot frame into a game engine needs an axis remap, not only a reorder (unverified here; a rotation-matrix round trip through a known pose is the test).

### Double cover, sign continuity, and the 6D representation

A logger that writes `q` on one frame and `−q` on the next has recorded the same orientation, and a network regressing the four numbers sees a jump. scipy's `canonical=True` picks `w >= 0`; that still jumps when w crosses zero (rotations near 180 degrees), so for time series enforce sign continuity against the previous sample (snippet 1).

Zhou et al. prove every representation in four or fewer real dimensions is discontinuous for 3D rotations and propose the 6D representation: the first two columns of R, made orthonormal by Gram-Schmidt at decode time ([arXiv:1812.07035](https://arxiv.org/abs/1812.07035), CVPR 2019; `pytorch3d.transforms.rotation_6d_to_matrix`). Use 6D or a rotation vector for regression targets; use quaternions for storage and transport with a documented order and enforced continuity.

### SLERP and quaternion error for control

SLERP interpolates on the unit sphere at constant angular rate; before calling it, flip one endpoint so the dot product is positive or the path goes the long way (Solà §2.7; `scipy.spatial.transform.Slerp` handles the sign). For control, the rotation vector of q_des ⊗ q_cur⁻¹ is the angular displacement in the base frame; the cheap approximation 2 · vec(q_des ⊗ q_cur⁻¹), with a sign flip when the scalar part is negative, agrees to first order and stays sign-blind (Solà §4.3; snippet 1). Without the sign handling a controller commands a 360 degree detour whenever the logger flipped signs.

## Transforms and frames

A homogeneous transform T = [R p; 0 1] in SE(3) composes by multiplication and inverts as [Rᵀ, −Rᵀp] (MR 3.3). Write every transform as `T_a_b`, read "b expressed in a" or "b's pose in frame a"; then chains compose only when adjacent subscripts match, `T_w_tool = T_w_base @ T_base_tool`, and a mismatch is visible in the variable names.

A transform used to *move* a point in one frame (active) and the same matrix used to *re-express* a point in another frame (passive) are the same numbers with opposite meaning; the naming discipline is what keeps them straight (MR 3.3.1). With `T_a_b` naming, `T_a_b @ p_b` re-expresses a point known in b into a (passive use); the same matrix applied to `p_a` moves the point within frame a by b's pose (active use). Decide which one a function does and put it in the docstring.

ROS frames follow REP 103 (SI units, right-handed, body x forward y left z up, camera `_optical` frames z forward x right y down) and REP 105 (`map` → `odom` → `base_link`; `odom` is continuous but drifts without bound, `map` is globally consistent but may jump) ([REP 103](https://www.ros.org/reps/rep-0103.html), [REP 105](https://www.ros.org/reps/rep-0105.html)). A depth camera's point cloud arrives in the optical frame, and the one-time static transform to the camera body frame is a fixed 90 degree pair that is easy to get backwards.

In tf2, `lookup_transform(target_frame, source_frame, time)` returns the transform that takes data from `source_frame` into `target_frame`, which in the naming above is `T_target_source` ([tf2 tutorial](https://docs.ros.org/en/humble/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Listener-Py.html)); its translation is the position of the source origin seen from the target frame. Argument order reversed is the second most common bug after quaternion order, and it is silent when both frames are near the origin. Timing behavior of the lookup is in [ros2-in-depth](ros2-in-depth.md).

## Kinematics

Forward kinematics maps the joint vector q to T_base_tool. Two formalisms give the same answer.

Denavit-Hartenberg assigns four parameters per link (a, α, d, θ) with a frame on each joint axis; it is compact and every vendor datasheet lists it, but it has two flavors (standard, Craig's modified) that assign frames differently, so a DH table copied from a manual into a library that expects the other flavor produces a wrong FK with no error (SSVO 2.8; Craig, *Introduction to Robotics*, 3.4).

Product of exponentials writes T(q) = e^{[S1]q1} … e^{[Sn]qn} M with joint screws S_i = (ω_i, v_i) in the base frame at the zero configuration and M the tool pose at zero; no link frames to assign, and it is what MR builds Jacobians and dynamics on (MR 4.1). Snippet 5 is the whole algorithm in six lines, checked against the closed-form planar 2R.

URDF is closer to PoE than to DH: each joint has an `origin` (parent to child at q = 0), an `axis` in the child frame, and a `type` (`revolute` with limits, `continuous`, `prismatic`, `fixed`); the joint's motion is about that axis ([URDF joint](https://wiki.ros.org/urdf/XML/joint)). `robot_state_publisher` computes FK from the URDF and publishes it to tf2. A policy that needs FK offline should use the same URDF through `pinocchio` or `kdl_parser`, never a hand-typed DH table, because a 1 mm error in one `origin` is invisible in tf and visible on the workpiece.

## Jacobians and singularities

The geometric Jacobian J(q) maps joint rates to tool twist: [v; ω] = J q̇, six by n, with the linear rows depending on where the tool point is and the angular rows on joint axes only (MR 5.1; SSVO 3.1). The analytic Jacobian differentiates a chosen orientation parameterization (Euler angles, quaternion) and adds that parameterization's singularities to the robot's own; controllers written on Euler-angle error inherit gimbal lock through it (SSVO 3.6).

Manipulability w = sqrt(det(J Jᵀ)) goes to zero at a singularity and the ellipsoid of achievable tool velocities collapses along one axis (MR 5.4). A six-axis arm has three classic ones: wrist (axes 4 and 6 aligned), elbow (arm fully stretched), shoulder (wrist center on the axis of joint 1) (SSVO 3.3).

What this does to a policy commanding Cartesian velocities: the controller inverts J, and near the singularity the pseudo-inverse multiplies the commanded 1 cm/s by a factor that grows without bound, the joints saturate, the vendor controller faults, and the episode ends. In the planar 2R check (snippet 5), a 1 cm task-space error at 1e-4 rad from the stretched pose gives a pseudo-inverse joint step above 10 rad and a damped step below 1 rad. Two defenses: damped least squares inside the velocity controller, and a dataset whose demonstrations avoid the stretched or wrist-aligned poses so the policy never asks for them. Log manipulability alongside every episode; a policy that drifts toward low w over an evaluation is a warning sign before it is a fault.

## Inverse kinematics

Closed-form IK exists when the last three axes intersect (spherical wrist, Pieper's condition) and returns all solutions, up to eight for a six-axis arm, in microseconds; vendor controllers use it internally, and the branch (elbow up or down, wrist flipped) is a discrete choice a policy should not be allowed to change mid-motion (MR 6.1; SSVO 2.12).

Numerical IK iterates q ← q + J⁺ e with e the pose error; damped least squares replaces J⁺ with Jᵀ(J Jᵀ + λ²I)⁻¹ so the step stays bounded at singularities at the cost of accuracy there (MR 6.2; SSVO 3.7). Null-space projection adds (I − J⁺J) z to spend redundant degrees of freedom on a secondary goal such as staying near a nominal posture or away from limits (SSVO 3.5). Libraries:

| Library | Method | When |
|---|---|---|
| KDL (`kdl_parser`, Orocos) | Newton on the geometric Jacobian, no joint-limit handling | default in older MoveIt; fails near limits |
| TRAC-IK | KDL Newton with random restarts plus an SQP that handles limits, run concurrently; solve types Speed, Distance, Manip1, Manip2 | drop-in for MoveIt, 6 to 7 DoF arms ([repo](https://github.com/traclabs/trac_ik)) |
| pink | differential IK as a QP over weighted tasks with configuration and velocity limits, on pinocchio, via `qpsolvers` | Python, humanoids and redundant arms ([repo](https://github.com/stephane-caron/pink)) |
| mink | same formulation on MuJoCo, with collision avoidance and closed chains | anything already modeled in MJCF ([repo](https://github.com/kevinzakka/mink)) |
| Drake | `InverseKinematics` (nonlinear program with constraints) and `DifferentialInverseKinematicsIntegrator` (QP with limits) | when the rest of the stack is Drake ([docs](https://drake.mit.edu/doxygen_cxx/group__multibody.html)) |
| pinocchio | FK, Jacobians, dynamics algorithms; IK is a few lines of user code on top | the numeric core under pink and many research stacks ([repo](https://github.com/stack-of-tasks/pinocchio)) |
| cuRobo | GPU batched IK, collision checking, and trajectory optimization; "generates motions for a UR10 within 100ms on a NVIDIA Jetson Orin" | thousands of IK seeds per frame, or sim-side data generation ([docs](https://curobo.org/)) |

For a learned policy that outputs Cartesian targets, differential IK (pink, mink, Drake's integrator) at the control rate is the right shape: it is a velocity controller with limits, not a global search, so it cannot jump branches between ticks. A global solver (TRAC-IK, cuRobo) belongs at episode start, to pick the branch and seed the differential loop.

## Trajectories and limits

Every joint has position, velocity, and acceleration limits, and most vendor controllers also enforce jerk; a trajectory that violates any of them is clipped or rejected downstream, so the policy's action stream must be re-timed before it reaches the servo loop.

Point-to-point profiles: trapezoidal velocity (bang-coast-bang acceleration, discontinuous jerk) and S-curve (bounded jerk) (MR 9.2; SSVO 4.2). Splines (cubic, quintic) pass through waypoints with continuous velocity and acceleration but do not respect limits by construction (MR 9.3). A cubic through the 10 Hz waypoints of an action chunk overshoots between them when consecutive targets reverse direction; a trapezoid between them stops at each one. Neither is what a human demonstrator did.

Two libraries close the gap. Ruckig computes a jerk-limited, time-optimal trajectory from any state to a target state each control cycle and replans when the state deviates, "well-suited for control cycles down to 500 microseconds" ([repo](https://github.com/pantor/ruckig)); it is the right filter between a 10 to 30 Hz policy and a 1 kHz joint loop, since it turns each new action chunk into a limit-respecting motion without a stop. TOPP-RA takes a geometric path and computes the time-optimal parameterization under joint velocity, acceleration, or torque constraints ([repo](https://github.com/hungpham2511/toppra)); it is for offline re-timing of a planned path, not for online reaction.

A policy trained on demonstrations at 10 Hz that are then played through Ruckig at 1 kHz behaves differently from one whose actions are linearly interpolated, and the difference is the acceleration the robot actually sees; record which filter was used with the dataset.

## Dynamics

**Newton-Euler** treats each link as a rigid body: propagate velocities and accelerations outward from the base, then forces and moments inward from the tool, summing f = m a and τ = I α + ω × Iω per link. It is recursive and O(n), and it is the algorithm inside every inverse-dynamics call (MR 8.3; SSVO 7.5).

**Lagrangian** dynamics writes kinetic minus potential energy of the whole chain and differentiates: M(q) q̈ + C(q, q̇) q̇ + g(q) = τ, with M the joint-space mass matrix; it is the form used for analysis and control design and gives the same equation (MR 8.1; SSVO 7.1).

Every link needs ten inertia parameters (mass, center of mass, six inertia tensor entries) plus joint friction and motor rotor inertia for the model to be right. A simulator with placeholder inertias (a URDF `<inertial>` left at identity, or a box guess) integrates the correct kinematics with wrong accelerations, so the contact forces, the settling behavior, and the torque a learned policy sees are all fiction; this is the first thing to fix before trusting sim-to-real numbers ([sim-to-real](sim-to-real.md)).

Gravity compensation τ = g(q) is the minimum a kinesthetic-teaching or hand-guiding setup needs; the arm floats when only g(q) is applied, and a 1 kg error in the payload makes it sag or rise. Impedance control commands τ = Jᵀ(K e + D ė) + g(q), plus M-dependent terms if the desired inertia differs from the robot's, so the quality of g(q) and of the payload estimate sets how transparent a compliant policy feels (MR 11.6; SSVO 9.3). Franka, KUKA iiwa, and UR e-series expose torque or admittance interfaces that assume the vendor's dynamic model plus a user-declared payload; declare the gripper mass and center of mass before running anything compliant, or the arm drifts under its own gripper (from field, unverified on specific firmware).

## Conveyor tracking and interception

A part on a belt lives in a moving frame: T_base_belt(t) = T_base_belt(t0) · Trans(v_belt · (t − t0)) for a straight belt, where v_belt comes from an encoder on the belt drive, integrated in the same clock as the robot. An encoder count is the ground truth; a nameplate speed drifts by a few percent with load (from field, unverified). A camera upstream sees the part at time t_img in the camera frame; its pose in the belt frame is fixed after that, p_belt = T_belt_cam(t_img) · p_cam, and every later pose is that plus belt travel since t_img.

Interception is four phases. **Predict** where the part will be as a function of time. **Meet** it: the earliest time at which the TCP, moving at its speed limit, can reach the predicted point (snippet 4 solves |p_part + v_belt t − p_tcp| = v_max t as a quadratic; a real arm also needs the reach check against its workspace and joint limits at the meeting pose, which is an IK call, and a margin for the acceleration phase the constant-speed model ignores). **Match velocity**, so the tool moves with the belt and the relative velocity is zero before contact; the approach is planned in the belt frame, where the part is stationary. **Act** (grasp, inspect, place) while still tracking, then leave the belt frame.

Cartesian velocity commands during tracking are where the singularity discussion above bites: a belt running through the elbow-stretched region forces a re-timed pick point or a robot moved on its pedestal. Vendor controllers implement encoder integration and belt-frame planning natively (ABB conveyor tracking, Fanuc Line Tracking, KUKA ConveyorTech; product names and features unverified). With ROS or a learned policy the belt frame is a tf2 frame published from the encoder, and the policy's actions are expressed in it so the network never sees the belt speed and a dataset collected at one belt speed transfers to another.

## Calibration

**Hand-eye (AX = XB).** Move the robot through n poses while a camera sees a target; each pair of relative motions A_i (robot) and B_i (camera) satisfies A_i X = X B_i for the unknown camera-to-flange transform X (eye-in-hand) or camera-to-base (eye-to-hand). Tsai and Lenz (1989) solve rotation then translation in closed form; Park and Martin (1994) solve on the Lie group; both are in `cv2.calibrateHandEye` with the method selectable ([OpenCV](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#gaebfc1c9f7434196a374c382abf43439b)). Rotate the robot through large angles about at least two distinct axes between poses or the rotation part is ill-conditioned; translation error scales with rotation error times lever arm (Tsai and Lenz, IEEE T-RA 5(3)).

**TCP calibration** finds the tool tip in the flange frame by touching one fixed point from four or more orientations and solving for the point that stays still; every vendor pendant has the 4-point routine.

**Kinematic calibration** corrects the URDF's link parameters from measured poses (laser tracker or a touched artifact); it moves absolute accuracy from the few-millimeter range of a nominal model toward repeatability, which on industrial arms is tens of micrometers (SSVO 2.11; numbers from vendor specs, unverified for a specific arm).

What a learning engineer must do: calibrate before recording data, store the calibration with the dataset in `DATASET.md`, and recalibrate when the camera mount is touched, because a policy trained on one X and deployed on another is a systematic offset that looks like a bad model.

## Action spaces for learning

Four choices, each with a failure mode:

| Choice | Option A | Option B |
|---|---|---|
| Space | joint targets: unambiguous, no IK, tied to one arm | Cartesian targets: transfer across arms, need IK, a branch policy, and a singularity strategy |
| Reference | absolute: self-correcting under tracking error | delta: easier to learn and chunk, compounds drift, needs the current pose at apply time |
| Frame | base: simple, position-dependent | tool or task frame: invariant to where the arm is (snippet 2) |
| Proprioception | absolute pose or joints | relative history (velocity information without differentiating noise) |

UMI uses "a sequence of SE(3) transforms denoting the desired pose at t relative to the initial EE pose at t₀" and also represents the history of end-effector poses as a relative trajectory, with the relative pose between the two grippers as the key bimanual input ([UMI, arXiv:2402.10329](https://arxiv.org/html/2402.10329)). π0 outputs action chunks with H = 50 at up to 50 Hz in each robot's own configuration space, zero-padding "the configuration and action vectors" to the largest robot's 18 dimensions ([π0, arXiv:2410.24164](https://arxiv.org/html/2410.24164)).

Rule: write the action semantics (frame, absolute or delta, quaternion order, units, rate, and the filter between policy and servo) in `DATASET.md`, and make the deployment node assert on it; see [imitation-learning](imitation-learning.md) and [teleoperation-and-data-collection](teleoperation-and-data-collection.md).

## Numeric hygiene

Units: meters, radians, seconds, newtons, in variable names when ambiguous (`dist_m`, `angle_rad`, `CLAUDE.md`). URDF limits are radians; scipy takes `degrees=True` explicitly; UR script takes radians while the pendant shows degrees.

Precision, measured on 2026-09-06 in the `rll` env: composing a 1 kHz yaw-rate quaternion for one hour without renormalization gives norm 1.0083 in float32 and 1.0000000002 in float64; summing `t += 1e-3` for 3.6 million steps in float32 gives 3530.2 s instead of 3600; summing 0.1 m/s × 1 ms for an hour gives 357.86 m instead of 360. Integrate poses and time in float64, renormalize quaternions after every product, count ticks as integers and derive time from the count, and cast to float32 only at the network boundary.

## Tested snippets

All functions and the asserts described here are in `snippets/kinematics.py` (`pytest snippets/kinematics.py`, 4 passed on 2026-09-06 with numpy 2.4.6, scipy 1.17.1, ruff clean under `tools/pyproject.toml`). scipy's `Rotation` is `xyzw` throughout.

```python
import numpy as np
from scipy.linalg import expm
from scipy.spatial.transform import Rotation as R, Slerp

# 1. Quaternion conventions and error
def wxyz_to_xyzw(q):  # (..., 4); pure reorder, no sign change
    return np.concatenate([q[..., 1:], q[..., :1]], axis=-1)

def xyzw_to_wxyz(q):
    return np.concatenate([q[..., 3:], q[..., :3]], axis=-1)

def continuous(q_xyzw):  # (T, 4): keep each sample on the previous one's hemisphere
    out = q_xyzw.copy()
    for t in range(1, len(out)):
        if np.dot(out[t], out[t - 1]) < 0:
            out[t] = -out[t]
    return out

def orientation_error(q_des_xyzw, q_cur_xyzw):
    """Rotation vector (rad, base frame) taking current to desired: log(R_des R_cur^T)."""
    return (R.from_quat(q_des_xyzw) * R.from_quat(q_cur_xyzw).inv()).as_rotvec()

# 2. Transforms, relative pose, delta actions (T_a_b: b expressed in a)
def inv_T(T):
    out = np.eye(4); out[:3, :3] = T[:3, :3].T; out[:3, 3] = -T[:3, :3].T @ T[:3, 3]
    return out

def relative_pose(T_w_a, T_w_b):
    return inv_T(T_w_a) @ T_w_b  # T_a_b

def delta_in_tool_frame(T_b_t0, T_b_t1):
    """Apply as T_b_t1 = T_b_t0 @ delta. Base-frame delta is T_b_t1 @ inv_T(T_b_t0), applied on the left."""
    return inv_T(T_b_t0) @ T_b_t1

# 3. SE(3) interpolation: linear in position, SLERP in orientation
def interp_se3(T0, T1, s):
    rots = R.from_matrix(np.stack([T0[:3, :3], T1[:3, :3]]))
    T = np.eye(4)
    T[:3, :3] = Slerp([0.0, 1.0], rots)(s).as_matrix()
    T[:3, 3] = (1 - s) * T0[:3, 3] + s * T1[:3, 3]
    return T

# 4. Conveyor intercept: earliest t with |p_part + v_belt t - p_tcp| = v_max t (base frame)
def intercept_time(p_part, v_belt, p_tcp, v_max):
    d = p_part - p_tcp
    a, b, c = v_belt @ v_belt - v_max**2, 2.0 * d @ v_belt, d @ d
    if abs(a) < 1e-12:
        return -c / b if b < 0 else None
    disc = b * b - 4 * a * c
    if disc < 0:
        return None  # the part outruns the arm
    roots = sorted(((-b - disc**0.5) / (2 * a), (-b + disc**0.5) / (2 * a)))
    return next((t for t in roots if t >= 0), None)

# 5. Product-of-exponentials FK, Jacobian by central differences, manipulability, damped step
def se3_hat(S):  # S = (w, v)
    w, v = S[:3], S[3:]
    hat = np.zeros((4, 4))
    hat[:3, :3] = [[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]]
    hat[:3, 3] = v
    return hat

def fk_poe(screws, M, q):  # screws (n, 6) in the base frame at q = 0; M tool pose at q = 0
    T = np.eye(4)
    for S, qi in zip(screws, q, strict=True):
        T = T @ expm(se3_hat(S) * qi)
    return T @ M

def jacobian_fd(screws, M, q, eps=1e-6):  # (6, n), rows (v, w) of the tool in the base frame
    J = np.zeros((6, len(q)))
    for i in range(len(q)):
        dq = np.zeros(len(q)); dq[i] = eps
        Tp, Tm = fk_poe(screws, M, q + dq), fk_poe(screws, M, q - dq)
        J[:3, i] = (Tp[:3, 3] - Tm[:3, 3]) / (2 * eps)
        J[3:, i] = R.from_matrix(Tp[:3, :3] @ Tm[:3, :3].T).as_rotvec() / (2 * eps)
    return J

def manipulability(J):
    return float(np.sqrt(max(np.linalg.det(J @ J.T), 0.0)))

def dls_step(J, err, damping):  # J^T (J J^T + lambda^2 I)^-1 err
    JJt = J @ J.T
    return J.T @ np.linalg.solve(JJt + damping**2 * np.eye(JJt.shape[0]), err)
```

Checks that passed:

- `xyzw_to_wxyz(q)` equals `R.from_quat(q).as_quat(scalar_first=True)` on five random rotations, and the swap round-trips.
- `continuous` repairs a 50-sample yaw sweep with a sign flip injected at sample 25.
- `orientation_error` returns (0, 0, 30 degrees) for a 10 to 40 degree yaw pair and the same for `−q_cur`.
- `T_w_a @ relative_pose(T_w_a, T_w_b) == T_w_b`; `T_w_a @ delta_in_tool_frame(...) == T_w_b`; the base-frame delta applied on the left agrees.
- `interp_se3` at s = 0.5 halves the rotation angle and averages position.
- `fk_poe` on the planar 2R (MR example 4.1) matches (cos q1 + cos(q1 + q2), sin q1 + sin(q1 + q2)); `jacobian_fd` matches the closed-form 2 × 2 Jacobian to 1e-6 and reports angular rate (0, 0, 1) per joint; manipulability is above 0.5 at (0.3, 0.7) rad and below 1e-5 at the stretched pose; at 1e-4 rad from stretched, a 1 cm error gives a pseudo-inverse step above 10 rad and a damped step (λ = 0.1) below 1 rad.
- `intercept_time` gives 2.0 s for a part 1 m downstream on a 0.5 m/s belt with a 1 m/s arm at the origin, 2/3 s for the part approaching, and `None` for a 2 m/s belt.

## Practical gotchas

- Quaternion order is per library, not per language: numpy code that mixes scipy (`xyzw`) with PyTorch3D or Isaac Lab (`wxyz`) tensors is wrong at the boundary and both sides return unit quaternions, so nothing fails until the arm moves ([conventions table](#quaternions-and-the-order-trap)).
- A dataset with `q` and `−q` alternating trains a policy that regresses a discontinuity; check `np.einsum("ij,ij->i", q[1:], q[:-1]).min()` per episode before training (mechanism: double cover, Solà §2).
- `lookup_transform(target, source)` reversed is a silent bug; test the listener against a known static pose before trusting it ([tf2 tutorial](https://docs.ros.org/en/humble/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Listener-Py.html)).
- Camera `_optical` frames (z forward) and body frames (x forward) differ by a fixed rotation that is easy to apply in the wrong direction; a point cloud that appears rotated 90 degrees in RViz is this ([REP 103](https://www.ros.org/reps/rep-0103.html)).
- Float32 accumulation over an hour at 1 kHz loses 70 s of time and 2 m of position (measured, [Numeric hygiene](#numeric-hygiene)).
- A DH table from a manual in the other DH flavor gives a plausible but wrong FK; compare against the vendor pendant's reported TCP at three poses before use (SSVO 2.8).
- Sim link inertias left at the URDF default are wrong physics that still runs; check every link's mass against the datasheet before any dynamics-dependent result ([sim-to-real](sim-to-real.md)).
- Cartesian-velocity policies fault at the wrist singularity with the pseudo-inverse and creep through it with damping; the fault is safer than the creep unless the path was designed to pass through (MR 6.2).
- The constant-speed intercept model ignores acceleration; on a real arm add the ramp time or the TCP arrives late and the part has moved on (mechanism in snippet 4; margin size unverified).

## What a forward-deployed engineer must be able to do

- Write the frame chain for a cell on a whiteboard as `T_a_b` products, name the quaternion order of every library in the stack, and check the whole chain numerically against one measured pose in under an hour.
- Convert a dataset's actions between joint, Cartesian absolute, and Cartesian delta in a stated frame with snippet 2, and prove the round trip.
- Explain to a customer engineer why their policy faulted near a singularity, show manipulability over the episode, and propose the damping or the workspace change.
- Set up hand-eye and TCP calibration, store the results with the dataset, and know from the residuals whether the rotation coverage was sufficient.
- Put Ruckig or an equivalent limit-respecting filter between a 10 to 30 Hz action stream and a 1 kHz joint loop and show the commanded versus measured joint traces.
- Solve the conveyor meeting problem with snippet 4 plus an IK reach check and plan the approach in the belt frame.
- Declare gripper mass and center of mass on the controller before any compliant or torque-controlled experiment.

## Open questions

- Whether Isaac Lab 3.0 changed quaternion order to `xyzw` in its release branch while `main` still documents `wxyz`; needs `convert_quat` tested on the installed version.
- Which orientation target (6D, rotation vector, quaternion with continuity) trains better for ACT and diffusion policies on this lab's data; the Zhou result is for supervised regression, not for action chunks.
- Whether Ruckig between the policy and the servo loop changes success rate versus linear interpolation on a fixed policy checkpoint; needs an A/B with trial counts.
- Hand-eye residual as a function of the number of poses and rotation range on the lab's camera and arm; the textbook guidance is qualitative.
- Encoder-based belt-frame drift over a shift versus a fixed nameplate speed, in millimeters at the pick point.
- The acceleration margin to add to the constant-speed intercept time for a specific arm's velocity and acceleration limits.

## Related entries

- [connecting-to-real-robots](connecting-to-real-robots.md), [deployment-engineering](deployment-engineering.md), [ros2-in-depth](ros2-in-depth.md) (tf2 timing)
- [imitation-learning](imitation-learning.md), [teleoperation-and-data-collection](teleoperation-and-data-collection.md) (action spaces and recording)
- [sim-to-real](sim-to-real.md), [state-estimation-and-localization](state-estimation-and-localization.md) (frames and error-state quaternions)
- Tools: [moveit2](../tools/moveit2.md), [mujoco](../tools/mujoco.md), [isaac-lab](../tools/isaac-lab.md)
- Code: `snippets/kinematics.py`

## Sources

- Lynch and Park, *Modern Robotics* (2017), chapters 3 (rigid-body motions), 4 (forward kinematics, PoE), 5 (velocity kinematics, manipulability), 6 (inverse kinematics, damped least squares), 8 (dynamics), 9 (trajectory generation), 11 (control): https://hades.mech.northwestern.edu/images/7/7f/MR.pdf
- Siciliano, Sciavicco, Villani, Oriolo, *Robotics: Modelling, Planning and Control* (2009), chapters 2 (kinematics, DH, calibration), 3 (differential kinematics, singularities, null space), 4 (trajectories), 7 (dynamics), 9 (force and impedance control): https://link.springer.com/book/10.1007/978-1-84628-642-1
- Craig, *Introduction to Robotics: Mechanics and Control*, chapter 3 (modified DH)
- Solà, Quaternion kinematics for the error-state Kalman filter: https://arxiv.org/abs/1711.02508
- Zhou et al., On the Continuity of Rotation Representations in Neural Networks: https://arxiv.org/abs/1812.07035
- Tsai and Lenz, A new technique for fully autonomous and efficient 3D robotics hand/eye calibration, IEEE T-RA 5(3), 1989; Park and Martin, Robot sensor calibration: solving AX = XB on the Euclidean group, IEEE T-RA 10(5), 1994; OpenCV calibrateHandEye: https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#gaebfc1c9f7434196a374c382abf43439b
- REP 103: https://www.ros.org/reps/rep-0103.html ; REP 105: https://www.ros.org/reps/rep-0105.html ; geometry_msgs/Quaternion: https://github.com/ros2/common_interfaces/blob/humble/geometry_msgs/msg/Quaternion.msg ; URDF joint: https://wiki.ros.org/urdf/XML/joint ; tf2 listener: https://docs.ros.org/en/humble/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Listener-Py.html
- Library conventions: scipy https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.as_quat.html ; Eigen https://libeigen.gitlab.io/eigen/docs-nightly/classEigen_1_1Quaternion.html ; PyTorch3D https://pytorch3d.readthedocs.io/en/latest/modules/transforms.html ; MuJoCo https://mujoco.readthedocs.io/en/stable/modeling.html ; Isaac Lab https://github.com/isaac-sim/IsaacLab/blob/main/source/isaaclab/isaaclab/utils/math.py ; Unity https://docs.unity3d.com/ScriptReference/Quaternion.html
- IK and trajectories: TRAC-IK https://github.com/traclabs/trac_ik ; pink https://github.com/stephane-caron/pink ; mink https://github.com/kevinzakka/mink ; pinocchio https://github.com/stack-of-tasks/pinocchio ; Drake https://drake.mit.edu/doxygen_cxx/group__multibody.html ; cuRobo https://curobo.org/ ; Ruckig https://github.com/pantor/ruckig ; TOPP-RA https://github.com/hungpham2511/toppra
- Action spaces: UMI https://arxiv.org/html/2402.10329 ; π0 https://arxiv.org/html/2410.24164
