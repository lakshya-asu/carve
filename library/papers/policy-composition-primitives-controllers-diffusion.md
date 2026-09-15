---
title: "Composing robot skills: task primitives (1997), nullspace controllers (2020), diffusion policies (2024)"
date: 2026-09-14
tags: [paper, skill-architecture, composition, nullspace, diffusion, hybrid-control, pork-leg]
status: draft
source: https://doi.org/10.1109/ROBOT.1997.606800
---

# Composing robot skills: Morrow and Khosla 1997, Sharma et al. 2020, PoCo 2024

What was read. Morrow and Khosla: all six pages of the scanned author copy on the CMU Robotics
Institute server (no text layer, read page by page as images). Sharma et al.: arXiv v2 (13 Nov
2020), main text and Appendices A to E. PoCo: arXiv v3 (1 Dec 2024), main text and Appendices
X-A to X-F. Companion papers cited by these three were not read unless named below.

Context: Neil's skill-contract architecture (inputs, preconditions, outputs, success, failure,
recovery) and the first application, aligning bone-in pork legs (about 11 kg, 720 mm) on a
moving belt so the trotter hangs off the edge. Background on that station lives in
[arm selection](../topics/arm-selection-scara-vs-six-axis.md) and
[conveyor tracking](../topics/conveyor-tracking-and-visual-servoing.md).

## 1. Morrow and Khosla, "Manipulation task primitives for composing robot skills" (ICRA 1997)

J. D. Morrow, P. K. Khosla. Proc. IEEE ICRA 1997, vol. 4, pp. 3354-3359.
DOI [10.1109/ROBOT.1997.606800](https://doi.org/10.1109/ROBOT.1997.606800).
Author copy: [CMU RI PDF](https://www.ri.cmu.edu/pub_files/pub2/morrow_james_1997_1/morrow_james_1997_1.pdf).

**Problem.** Robot programming primitives in 1997 were robot-centred (move to this pose), so every
sensor-based task was integrated from scratch and nothing carried over. Learned black-box skills
(they cite Gullapalli et al.'s neural peg-in-hole) have "no parametric connection between the
skill and the task", so they cannot be re-applied. The paper proposes a taxonomy that tells you
which task-centred, sensor-based primitives to build, so they can be reused across tasks.

**Definitions (Sec. 2, Fig. 1).**
- A *manipulation task primitive* (MTP) lives in task space. Its top level is a class of relative
  motion between two rigid parts (or frames). The class alone is only a "partial description";
  a full MTP adds geometry, mechanics and action details, and which details are needed depends
  on the robot's resources.
- A *sensorimotor primitive* (SMP) is "the solution implementation of a particular MTP": sensing
  and action fused into one command with task meaning. Its execution has three elements: (1) a
  controller, (2) a trajectory, (3) event detectors. Primitives sit at the gross/fine motion
  boundary.
- A *skill* is a composition of SMPs that solves a recurring subgoal.

**The twenty relative motions (Sec. 2, Tables 1 and 2).** Each of the 6 DOF between two frames is
free (1) or constrained (0), giving 2^6 = 64 classes. The authors pair the translation and rotation
about each task-frame axis into one letter: a = trans free / rot free, b = trans free / rot fixed,
c = trans fixed / rot free, d = both fixed. A class is a 3-letter word, and permutations of the
letters mean the same thing. The paper states that twenty classes are unique; that count equals
the number of unordered 3-letter words over 4 letters, C(6,3) = 20 (my arithmetic, the paper does
not show it). Morris and Haynes (ICRA 1987) had called 17 "reasonable" for assembly. Table 2 lists
every class except ddd (fully fixed), grouped by free DOF, with the authors' interpretations:

| Free DOF | Class and interpretation (as printed in Table 2) |
|---|---|
| 6 | aaa: free (unconstrained) motion |
| 5 | aab: edge parallel to surface (no contact); aac: point/plane or edge/edge |
| 4 | aad: ???; abc: edge against surface; abb: surface parallel to surface (no contact); acc: ball-in-slot or ring-in-tube |
| 3 | abd: ???; acd: ???; bbc: surface against surface; bcc: round peg in slot; bbb: translation mechanism; ccc: ball-in-socket |
| 2 | add: round peg-in-hole; bbd: translation mechanism; ccd: rotation mechanism; bcd: X-slider in slot |
| 1 | cdd: hinge/crank; bdd: non-round peg in hole |

The "???" entries are the paper's: the "ad" pair (one fully free axis next to one fully fixed axis)
has no natural contact interpretation. Constraints need not be contacts; a positional constraint
can be held by sensor feedback, which is how vision enters.

**Primitives actually built (Sec. 3).** Hardware: Puma 560, two-finger pneumatic gripper, wrist
force sensor, CCD camera; resolved-rate control, force through damping control, vision through
visual servoing at camera frame rate (about 30 Hz).
- ALIGN (force): aaa -> {abc, bbc}. Guarded move to contact, then a constant force setpoint; the
  damping controller complies to the resulting torque until the flat surfaces align.
- LD, linear dither (force): attains or verifies a full translation constraint (abc -> bbc, peg
  on surface falls into slot). Sinusoidal velocity dither in x,y under damping control plus a
  constant normal force. The event detector is the normalised correlation between reference and
  force-perturbed actual velocity over one dither cycle; it drops when the constraint engages, and
  a threshold fires. Two orthogonal dithers at chosen frequencies trace a Lissajous search.
- Visual servoing on a 4-DOF corner feature (x, y, orientation, corner angle). TVS (translation)
  gives one or two positional constraints (aac, acc); RVS (rotation about the optical axis) gives
  aab; TVS plus RVS gives bcc or abc. AVS uses the projected corner angle
  beta = pi - asin(sin(alpha_0) cos(theta)) - asin(sin(gamma_0) cos(theta)) (Eq. 1), where alpha_0
  and gamma_0 are the initial edge projection angles and theta is rotation out of the image plane,
  to align two surfaces without contact (abb). All of these require the parts to show corners.

**Composition operator (Sec. 4).** A skill is a *sequence* of SMPs, each taking the part from one
motion class to another, with *concurrent* primitives inside a step separated by projection. Worked
task: square peg-in-hole (one free translation). Decomposition 1: ALIGN presses flat surfaces
together to align the insertion axis, then TVS and RVS centre and rotate the peg while contact
holds the axis; with small clearance, dither to mate. Decomposition 2: AVS aligns the axis without
contact, TVS and RVS centre, then a guarded move along the optical axis makes contact. Vision is
used to "enlarge the insertion skill precondition funnel" for the compliant (RCC) insertion. To
stop the vision primitives disturbing the force-held axis, image-derived commands are projected
through the approximate camera-to-task rotation, with n the unit insertion axis:

    w' = (w . n) n          (Eq. 2)  RVS angular velocity w kept only about n
    v' = v - (v . n) n      (Eq. 3)  TVS/AVS velocity v removed along n: force along n, vision in the plane

Eq. 3 is v' = (I - n n^T) v, the same nullspace projector Sharma et al. use 23 years later.

**Learned vs hand-designed.** Everything is hand-designed: classes, primitives, event thresholds,
decompositions. No data. Reuse is the stated point: "re-use costly sensor-based control algorithms".

**Guarantees.** None formal. Eq. 3 removes the vision command's component along n exactly, but only
in the task frame reached through an approximate camera rotation.

**Evidence.** No quantitative results. No trial counts, success rates or timings. Fig. 5b plots beta
against theta for a square corner. Earlier primitive-based BNC and D-connector insertion is cited
to their 1995 ICRA and IROS papers, which I did not read.

**Limitations.** Stated: no finite primitive set spans real manipulation, and "task design remains a
key tool" for avoiding a primitive set's limits (Sec. 5). Seen: rigid two-part relative motion only,
so a deformable 11 kg leg has no clean class; failure and recovery are not part of the SMP definition
(event detectors report success, nothing specifies what happens otherwise); corner features are an
assumption on part geometry.

**Fit with Neil's contract.** This is the closest ancestor. The MTP is the contract type (before
class, after class, geometry), the SMP is the implementation (controller, trajectory, event
detectors), and resources plus strategies are the hardware layer. Preconditions are explicit in
the text (force primitives have tight initial positioning; visual servoing widens that funnel).
Event detectors are success conditions. The two fields Morrow does not define, failure conditions
and recovery, are exactly what Neil adds. Testability is good: each SMP has one detector and a
known before/after class, so it can be tested in isolation against a fixture.

**Fit with the pork leg.** Expressed in the belt frame, a leg lying on the belt is roughly bbc
(surface against surface) if treated as rigid. "Trotter beyond the belt edge" is a positional,
non-contact constraint held by sensor feedback, which Morrow explicitly allows. The Eq. 3 split
maps directly onto a pusher or gripper on a belt: force along the belt normal, vision-driven
motion in the belt plane. What must change: corner features become hock and trotter keypoints from
perception; a failure detector and recovery path per step; and the belt velocity must be removed
by working in the moving belt frame, which the paper does not address.

## 2. Sharma, Liang, Zhao, LaGrassa, Kroemer, "Learning to Compose Hierarchical Object-Centric Controllers for Robotic Manipulation" (CoRL 2020)

[arXiv 2011.04627](https://arxiv.org/abs/2011.04627). Project page:
[sites.google.com/view/compositional-object-control](https://sites.google.com/view/compositional-object-control/),
which links code at [iamlab-cmu/hierarchical-object-controllers](https://github.com/iamlab-cmu/hierarchical-object-controllers).

**Problem.** Many manipulation tasks run subtasks in parallel (push down while turning a screw),
and each subtask is a simple controller along an axis attached to an object. Prior work fixed the
combination by hand or learned a fixed task-frame hierarchy from demonstrations. This paper has an
RL policy choose, every T steps, an ordered list of object-centric controllers, and composes them
by nullspace projection.

**Controllers (Sec. 3.1).** x_c, R_c, f_c are the current end-effector position, orientation and
force in the base frame. P(u) = u u^T projects onto axis u.
- Position: target x_d, axis u (fixed, such as a surface normal, or u = (x_d - x_c)/||x_d - x_c||).
  Error delta_x = P(u)(x_d - x_c).
- Force: same form, delta_f = P(u)(f_d - f_c).
- Rotation: align end-effector axis R_c u with target axis r_d; delta_R = acos((R_c u)^T r_d) ((R_c u) x r_d),
  an angle-axis delta.
- Null controller: zero error, selectable more than once. Appendix A adds task-specific ones,
  for example a "freeze vertical" position controller (x_d = x_c, u = vertical) whose only purpose
  is its nullspace (Hex-Screw controller 3).

**Composition operator (Sec. 3.2).** N(U) = I - U^+ U, the projector onto the nullspace of the rows
of U (U^+ is the pseudoinverse). Indices 0, 1, 2 are decreasing priority; K_x is a gain.

    D0 = K_x delta_x(x_d0, u0, x_c)
    D1 = K_x N([u0]) delta_x(x_d1, u1, x_c)
    D2 = K_x N([u0, u1]) delta_x(x_d2, u2, x_c)
    D  = D0 + D1 + D2                                  (Eqs. 1-4)

Force controllers substitute delta_f, f_d, f_c, K_f. At most 3 position/force controllers (3
translational DOF) and at most 2 rotation controllers: once priority 0 fixes one axis, one rotational
DOF remains. Rotation: D1_R = K_R delta_R(N([R_c u0]) r_d1, u1, N([R_c u0]) R_c), and the total is
D1_R composed with D0_R (Eqs. 5-7). The 6-D delta D goes to task-space impedance control,
tau = J^T (K_S D + K_D dD/dt), gravity and Coriolis terms omitted in the text. Each delta is clipped
in magnitude (Eqs. 9-10); force controllers get an integral term (Eq. 8).

Composition type: CONCURRENT and HIERARCHICAL within one T-step window, SEQUENTIAL across windows
because the RL policy reselects. Controllers need not converge before a switch.

**What is learned.** Hand-designed: every controller, its object axis and target, gains, clips, T.
Learned: only the ordered selection, with PPO (stable-baselines, 8 seeds) in Isaac Gym. Best action
space: the Expanded-MDP, which splits one environment step into N_c = 3 discrete picks with zero
reward until the third, avoiding the O(N^N_c) combinatorial space. Observations include object poses
and contact forces from the simulator. No demonstrations. Controllers are reusable across tasks
without retraining; the selector is trained per task.

**Guarantee and its assumptions.** D1 has no component along u0 (u0^T N([u0]) = 0), so lower-priority
controllers cannot change the commanded delta along a higher-priority axis. For rotation the paper
claims the higher-priority controller "always reaches its goal" and its axis trajectory is unaffected
(Fig. 3). What that rests on, from reading the equations: (a) the separation is on the Cartesian
delta target, not on realised motion; a non-isotropic K_S, the Jacobian-transpose mapping without
inertia decoupling, contact reaction forces and joint limits can all leak motion onto the protected
axis; (b) the total magnitude cap scales the priority-0 part down too; (c) if the targets conflict,
the lower-priority task is simply not achieved, silently.

**Evidence.** Sim: two 2-D block tasks and two Franka tasks in Isaac Gym, 8 seeds. Real: Franka Panda
through frankapy, 10 trials per method, K_S retuned from 1000 to 600 and T from 10 to 30 before
evaluation (Table 4). No fine-tuning on the real robot.

| Result (success, mean over 8 seeds) | EE-Space | 1-Ctrlr | 3-Exp-Single | 3-Exp-Multi | Source |
|---|---|---|---|---|---|
| Block Fit, Test-Large | 0.371 | 0.396 | 0.974 | 0.953 | Table 1 |
| Block Push, Test-Large | 0.518 | 0.152 | 0.751 | 0.788 | Table 1 |
| Hex-Screw, Test-Large (sim) | 0.00 | 0.026 | 0.936 | 0.936 | Table 2 |
| Hex-Screw, real, 10 trials | not run | 0.0 | 0.9 | 0.6 | Table 2 |
| Door-Open, real, 10 trials | not run | 0.0 | 1.0 | 1.0 | Table 2 |

EE-Space (RL on delta end-effector poses) never learned either Franka task (Hex-Screw train
0.002), so it was not run on the robot. Hex-Screw test sizes were scale 0.7 to 1.5 against training
scales 0.9, 1.0, 1.3; real Hex-Screw used 3 screw and key sizes. With T = 80 instead of 10, Block Fit
Expanded-MDP learned in about 30K steps against about 10M (Fig. 15, 4 seeds).

**Limitations.** Stated: the controller set is fixed and manually defined (Sec. 6). Seen: object poses
are observations, and the paper does not say how they were obtained on the real robot; all targets are
static (no moving objects); the priority-2 slot is often redundant and hard to learn (App. E.2);
real Hex-Screw drops from 0.936 to 0.6 for 3-Exp-Multi, attributed to sim-to-real dynamics gaps; rigid
objects only.

**Fit with Neil's contract.** Two layers. The object-axis controllers and the nullspace composer are
deterministic skill-layer code: pure functions from state to a delta target, each unit-testable, and
the projection property is an assertion (u_i^T D_j = 0 for j > i) that can run every control cycle.
The selector is a task-logic policy whose output is a short ordered list, which is easy to log and
replay ("which controllers were active at 12.4 s"). Neil's principle suggests starting with a
hand-written priority schedule (a state machine) and only learning selection if that fails. A
composed-skill contract: inputs are object keypoints and axes, F/T, belt frame; precondition is contact
or grasp established and targets inside the workspace; output is a 6-D delta at control rate; success
is every active controller's error under its tolerance for k cycles; failure is force over limit,
priority-0 error not decreasing within a window, or target leaving the workspace; recovery is a
retreat controller at priority 0.

**Fit with the pork leg.** A plausible alignment skill from these parts, written in the moving belt
frame (x along belt, y across toward the edge, z up):
- Priority 0, force controller along -z with a small f_d: keeps the leg supported on the belt, or
  keeps a pusher in contact.
- Priority 1, position controller on the hock keypoint along y: moves the hock to the lateral target.
- Priority 2, position controller along x tracking the belt, or a freeze controller holding the along-belt
  position relative to the belt.
- Rotation priority 0, align the hock-to-trotter vector with +y about vertical.

On a SCARA (x, y, z, yaw) this uses every DOF, and rotation composition collapses to one yaw
controller, which fits Sharma's structure well. On a 6-axis arm the second rotation controller could
keep the gripper level. What would have to be true: (1) the controllers act on the end effector, so
the leg must be coupled rigidly through a grasp (grasp-and-pivot) or the push contact must be
predictable; the arm-selection note argues pushing is not determinate; (2) hock and trotter keypoints
and the leg axis at control rate from perception; (3) belt velocity fed forward, since the paper's
targets are static; (4) force control on the arm: the paper used a torque-controlled Panda with a
3 kg payload ([franka.de](https://franka.de/research)), far below 11 kg, and whether an industrial
SCARA exposes an impedance or admittance mode is a per-vendor question (unverified).

## 3. Wang, Zhao, Du, Adelson, Tedrake, "PoCo: Policy Composition from and for Heterogeneous Robot Learning" (RSS 2024)

[arXiv 2402.02511](https://arxiv.org/abs/2402.02511) (v3, 1 Dec 2024; comments field "R:SS 2024").
Project page [liruiw.github.io/policycomp](https://liruiw.github.io/policycomp); I found no code link on it.

**Problem.** Robot data comes from simulation, teleoperation and human video, in RGB, point cloud and
tactile modalities. Pooling it into one policy needs aligned observation spaces and careful
balancing. PoCo trains a separate diffusion policy per (modality, domain, task) and combines them,
plus analytic costs, at inference time without retraining.

**Composition operator (Sec. IV).** Each policy is a diffusion model over an action trajectory tau in
R^(H x d) (H horizon, d action dimension). Composition samples from a product of distributions,
p_product(tau) proportional to p_1(tau) p_2(tau) (Eq. 3). In sampling, eps_theta is the denoising
network's noise prediction, gamma a step weight, xi Gaussian noise:
- Task level (Eq. 9): tau_{t-1} = tau_t - gamma_T (eps(tau|t) + alpha (eps(tau|t,T) - eps(tau|t))) + xi.
  This is classifier-free guidance for p(tau) p(T|tau)^alpha; alpha = 0 is unconditional, alpha = 1
  conditional, alpha > 1 pushes harder toward task T.
- Behaviour level (Eq. 10): tau_{t-1} = tau_t - gamma_c (eps(tau|t,T) + grad_tau c(tau)) + xi, for
  p_cost proportional to exp(-c(tau)). Costs used: smoothness ||tau''||^2 and workspace
  ||min(tau - tau_min, 0)||^2 + ||max(tau - tau_max, 0)||^2, on end-effector poses integrated from
  the velocity actions, gradients by autograd.
- Domain level (Eq. 11): tau_{t-1} = tau_t - gamma_D (eps_1(tau|t) + eps_2(tau|t)) + xi, where the
  two networks can take different observations (point cloud in one, RGB in the other).
Algorithm 1 nests all three in one denoising step. Composition type: CONCURRENT only. The limitations
section says it "does not enable temporal composition across long-horizon tasks".

**What is learned.** Learned: every diffusion policy (temporal U-Net, DDPM training with 100 steps;
ResNet-18 for images, PointNet for point clouds, T5 for task text). Hand-designed: the costs and the
weights alpha and gamma, tuned by hand "until the policies became unstable" (App. X-B). Data: about
50,000 simulated data points per tool-object pair from keypoint trajectory optimisation in the
Fleet-Tools benchmark; 50 to 100 teleoperated demonstrations per real task (Oculus Quest Pro); human
RGB-D video labelled with SAM, XMem and ICP, "up to 200 trajectories for 20 minutes". Training:
80,000 steps, about 16 hours on a V100. Components are trained separately and composed later with no
retraining, provided they share action space (6-DOF end-effector velocity), a fixed normalisation,
horizon and frequency; the paper switched from dataset-statistics normalisation for this reason.

**Guarantees and assumptions.** Appendix X-D shows p(tau|A) p(tau|B) = p(tau|A,B) p(tau), hence
proportional to p(tau|A,B), assuming (1) tasks and costs A, B mutually independent, (2) conditionally
independent given tau, (3) p(tau) uniform. When objectives conflict the paper argues only that
samples likely under both will still score highest "in practice". Nothing guarantees a cost is
satisfied: in Table I the workspace cost lowers violation from 0.030 to 0.022, not to zero.

**Evidence.**
- Behaviour composition, simulation (Table I): success / smoothness / workspace violation: normal
  0.70 / 0.027 / 0.030; +smoothness 0.67 / 0.016 / 0.038; +workspace 0.67 / 0.019 / 0.022,
  gamma_c = 0.1. Sim protocol: 10 runs on 50 scenes per task (Sec. VI); the table does not name the task.
- Domain composition, real Franka, hammer reaching a pin, 5 trials in each of 4 settings (Table II):
  human 15%, simulation-trained 90%, real-robot 50%, human+real 65%, sim+real 100% (20/20). The sim
  column is a point-cloud policy trained in simulation and run on the real robot (my reading of
  Sec. VII-A), which is the sim-to-real claim.
- Task composition, real, RGB plus tactile, 10 trials per tool (Table III): single-task 65%;
  multitask unconditioned 50%; multitask conditioned 53%; composition alpha = 2, 60%.
- Ablation (Table IV, relative change, trials not given): data pooling -75%, no tactile -38%, no
  action-chunk rollout -24%.
- Real setup: Franka Panda with a GelSight Svelte hand, D405 wrist and D435 overhead cameras; 10 Hz
  with RGB, 6 Hz with segmented point clouds; composing two policies runs at 5 Hz, and cost grows
  linearly with more (Sec. VIII).

**Limitations.** Stated: no temporal composition; policies must agree on horizon, scale and
frequency; overfitting and failure on delicate contact (Fig. 16: wrench, spatula, knife); 5 Hz; cost
composition only tested in simulation. Seen: composed multitask (60%) still trails single-task
policies (65%) in Table III; human+real is worse than real alone on novel instances (1/5 vs 2/5,
Table II); 20 trials per real condition is too few to separate 90% from 100%; costs were added with
a fixed weight rather than scaled by noise level (see the derivation below).

**Fit with Neil's contract.** A learned skill-layer component, not a task-logic mechanism. Contract
sketch: inputs are observations per component policy plus a task label and cost functions;
preconditions are a shared action space, normalisation and horizon, and each component's observation
within its training distribution; output is an action chunk; success is task-defined outside the
policy; failure has no native signal, since a diffusion sample carries no confidence. A candidate
detector is disagreement between component policies' samples (untested idea). Recovery: the paper
reports retrying behaviour that emerged from data (Fig. 1), not a designed path. Testability:
components can be regression-tested alone, but the composed skill depends on hand-tuned weights and
stochastic sampling, so tests need fixed seeds and N-trial success rates.

**Fit with the pork leg.** Candidate sub-skill: the contact-rich rotate or push of the leg, where a
learned policy from teleop demonstrations (and possibly a sim point-cloud policy through domain
composition) is composed with an analytic cost

    c_edge(tau) = ||max(y_edge + m - y_trotter(tau), 0)||^2

where y_edge is the belt edge in the across-belt axis, m a margin, and y_trotter(tau) the trotter's
lateral position predicted along the trajectory. What would have to be true: y_trotter must be a
differentiable function of the action trajectory, which holds with a rigid grasp (trotter pose = end
effector pose times a grasp transform from perception) and fails for pushing unless a dynamics model
is added; actions expressed in the belt frame so the learned part never sees belt velocity; 5 Hz for
two components must be fast enough relative to belt speed, which is not yet measured for this line;
and because the cost is soft, the hard edge and workspace checks stay in the deterministic safety
layer outside the policy.

## Unifying the three, 1997 to 2024

**Classical view (Morrow).** A skill is a sequence of primitives. Each primitive has a declared
before/after motion class, a controller, a trajectory and an event detector. Composition is done by a
person decomposing the task, and interference between concurrent primitives is removed by projecting
commands onto complementary subspaces (Eq. 3).

**Control-theoretic view (Sharma).** The same projection, generalised: N(U) = I - U^+ U over any
number of prioritised axes from the task-priority redundancy literature (Nakamura et al. 1987, Khatib
1987, as cited by Sharma). What was a design choice in 1997 (which primitive, which order) becomes the
action of an RL policy, while the controllers stay classical.

**Generative view (PoCo).** The components are now distributions, and "run both" means sample from the
product. Projection gives strict priority; a product gives a compromise weighted by confidence.
Neither view says anything about sequencing, which Morrow handled by hand and Sharma by reselection.

**Why diffusion policies compose by adding scores.** Take p_prod(tau) = p1(tau) p2(tau) / Z, where Z is
a normalising constant. Take logs: log p_prod = log p1 + log p2 - log Z. Z does not depend on tau, so
its gradient is zero, and grad log p_prod = grad log p1 + grad log p2. The score of a product is the
sum of scores, and the intractable normaliser drops out. A denoising network trained with the
noise-prediction loss estimates a scaled score, eps(tau_t, t) approximately -sigma_t grad log p_t(tau_t)
([Vincent 2011](https://doi.org/10.1162/NECO_a_00142); [Song et al. 2021](https://arxiv.org/abs/2011.13456)),
so adding noise predictions adds scores. An analytic cost enters as p_cost proportional to exp(-c), whose
score is -grad c, so the matching term in eps-space is +sigma_t grad c. PoCo uses a fixed gamma_c instead
of sigma_t. Two caveats: at intermediate noise the networks estimate scores of noised marginals, and the
product of noised marginals is not the noised product, so reverse diffusion with summed scores does not
sample the product exactly; [Du et al. 2023](https://arxiv.org/abs/2302.11552) (PoCo's ref. 23) attribute
composition failures to the sampler and propose MCMC samplers. And classifier-free guidance
([Ho and Salimans 2022](https://arxiv.org/abs/2207.12598)) is the same identity with p(T|tau)^alpha
written as (p(tau|T)/p(tau))^alpha.

**Worked example: 2-D nullspace projection.** End-effector velocity v = (v_x, v_y). Primary task with
Jacobian row J1 = [2, 2]: the task rate is 2 v_x + 2 v_y, for example the approach rate to a guide
rail lying at 45 degrees.

    J1^+ = J1^T / (J1 J1^T) = [2, 2]^T / 8 = [0.25, 0.25]^T
    J1^+ J1 = [[0.5, 0.5], [0.5, 0.5]]
    N1 = I - J1^+ J1 = [[0.5, -0.5], [-0.5, 0.5]]

Primary command for a task rate of 0.4: v1 = J1^+ 0.4 = (0.1, 0.1).
Secondary command, push along x: v2 = (1, 0).
Projected: N1 v2 = (0.5, -0.5). Check: J1 N1 v2 = 2(0.5) + 2(-0.5) = 0.
Total: v = v1 + N1 v2 = (0.6, -0.4), and J1 v = 0.4, exactly the primary rate.
Without projection: v1 + v2 = (1.1, 0.1) gives J1 v = 2.4, so the secondary push overwhelms the primary.

What survives of v2 is its component along the rail direction (1, -1)/sqrt(2), with length
0.707 of the original. The half of v2 that pointed into the rail is discarded, not deferred. Scaling
J1 does not change N1, and when J1 is a unit row n^T, N1 = I - n n^T, Morrow's Eq. 3. All numbers
checked with NumPy.

## Comparison

| | Operator | Sequential, concurrent, hierarchical | Learned or classical | Composable without retraining | Real robot | Key limitation |
|---|---|---|---|---|---|---|
| Morrow and Khosla 1997 | Hand-built sequence of SMPs between motion classes; projection v' = (I - n n^T) v inside a step | Sequential, with concurrent force/vision inside a step | Classical throughout | Yes, reuse of primitives is the point; each new task needs a hand decomposition | Puma 560 described; no quantitative trials reported | Rigid parts, no metrics, no failure or recovery semantics |
| Sharma et al. 2020 | Prioritised nullspace projection N(U) = I - U^+ U of object-axis controller errors, order chosen by RL | Concurrent and hierarchical in a window, sequential across windows | Classical controllers, learned selector (PPO in Isaac Gym) | Controllers yes; selector retrained per task | Franka Panda, 10 trials: Door-Open 1.0, Hex-Screw 0.9 best | Fixed hand-defined controller set; static known object poses; separation only on the Cartesian target |
| PoCo 2024 | Sum of diffusion noise predictions (scores), plus analytic cost gradients | Concurrent only | Learned diffusion policies, hand-written costs and weights | Yes, if action space, normalisation, horizon and frequency match | Franka Panda with GelSight: sim+real 20/20 on hammer reach; composed multitask 60% vs 65% single-task | 5 Hz with two policies; no temporal composition; costs soft and only tested in sim |

## What I am not sure about

- Morrow's reason for "twenty unique": the C(6,3) count is my arithmetic; the paper only states the number.
- Whether Morrow's 1995 ICRA and IROS papers report success rates for the same primitives. Not read.
- How Sharma et al. obtained screw and door-handle poses on the real robot; the paper does not say.
- PoCo's internal inconsistencies: DDIM 32 test steps (Sec. V) vs 16 (App. X-B); task weight alpha = 1.5
  (Sec. VI-B) vs "conditional scale 0.01" (App. X-B); Fig. 7 caption labels panel (a) task composition,
  while the text calls it (b).
- PoCo's introduction claims "success rate improvements of 20%" over baselines. No single table gives 20 points:
  Table III is 60% vs 50% (20% relative), Table II sim+real is 100% vs 90%.
- Whether summed noise predictions fail measurably for short robot action chunks as they do in Du et al.'s
  image experiments. No robot evidence either way was found.
- Whether PoCo code is public. No link on the project page as of 2026-09-14.

## Sources

- Morrow and Khosla 1997: [CMU RI PDF](https://www.ri.cmu.edu/pub_files/pub2/morrow_james_1997_1/morrow_james_1997_1.pdf),
  [DOI](https://doi.org/10.1109/ROBOT.1997.606800). Secs. 1-5, Tables 1-2, Eqs. 1-3, Figs. 1-7.
- Sharma et al. 2020: [arXiv 2011.04627](https://arxiv.org/abs/2011.04627) v2. Secs. 3-6, Eqs. 1-10, Tables 1-9,
  Figs. 14-16, Apps. A-E. [Project page](https://sites.google.com/view/compositional-object-control/).
- Wang et al. 2024: [arXiv 2402.02511](https://arxiv.org/abs/2402.02511) v3. Secs. III-VIII, Eqs. 1-11,
  Algorithm 1, Tables I-IV, Apps. X-A to X-F. [Project page](https://liruiw.github.io/policycomp).
- Score composition background: [Du et al. 2023](https://arxiv.org/abs/2302.11552) (abstract read),
  [Ho and Salimans 2022](https://arxiv.org/abs/2207.12598), [Song et al. 2021](https://arxiv.org/abs/2011.13456),
  [Vincent 2011](https://doi.org/10.1162/NECO_a_00142) (cited, not reread).
- Franka payload: [franka.de/research](https://franka.de/research), via
  [robot-arms.md](../hardware/robot-arms.md).
