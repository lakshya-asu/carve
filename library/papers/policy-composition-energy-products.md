---
title: "Composing policies as products: soft Q sums, energy sums, products of experts"
date: 2026-09-14
tags: [paper, skill-composition, energy-based-model, product-of-experts, reactive-control, task-priority, skill-architecture]
status: draft
source: https://arxiv.org/abs/1803.06773
---

# Composing policies as products (Haarnoja 2018, Urain 2021/2023, Hansel 2023, Pignat 2020/2022)

Read from full text: Haarnoja arXiv v1 (19 Mar 2018); Urain RSS 2021 arXiv v1 and the IJRR 2023
author PDF from TU Darmstadt; Hansel arXiv v3 (29 Jul 2024); Pignat arXiv v1 (7 Oct 2020). The
published ICRA and IJRR versions of Haarnoja, Hansel and Pignat were not read (IEEE and SAGE
paywalls). Written for Neil's skill-contract architecture and the pork-leg alignment cell.

All four papers compose simultaneously active skills by adding log-probabilities. None addresses
sequencing (observe, then grasp, then transport); that stays in Neil's task layer.

## 1. Haarnoja et al., Composable Deep RL for Robotic Manipulation (ICRA 2018)

Links: [arXiv abs](https://arxiv.org/abs/1803.06773), [PDF](https://arxiv.org/pdf/1803.06773),
[DOI 10.1109/ICRA.2018.8460756](https://doi.org/10.1109/ICRA.2018.8460756),
[code](https://github.com/haarnoja/softqlearning),
[videos](https://sites.google.com/view/composing-real-world-policies/).

Problem. Model-free deep RL needs too many real-robot samples, and every new combination of
objectives normally means training from scratch. The paper shows soft Q-learning (SQL) trains
manipulation skills on a Sawyer in hours, and that max-entropy policies trained separately can be
combined by adding their Q-functions, with a bound on how much the combination loses.

Composition operator. Each skill i is a max-entropy policy pi_i*(a|s) proportional to
exp(Q_i*(s,a) / alpha), trained for reward r_i. For a subset C of skills (Sec. IV-A, Eq. 5-6):

    r_C(s,a) = (1/|C|) * sum_{i in C} r_i(s,a)
    Q_Sigma(s,a) = (1/|C|) * sum_{i in C} Q_i*(s,a)      (approximates Q_C*)
    pi_Sigma(a|s) proportional to exp(Q_Sigma(s,a))

s is the state, a the action, alpha the entropy temperature, Q_i* the optimal soft Q-function
(expected reward plus future entropy) of skill i, Q_C* the unknown optimal soft Q of the averaged
reward. Because exp of a sum is a product, pi_Sigma is proportional to the product of the
constituent policies raised to 1/|C|. The authors frame this as a conjunction ("do X and Y"),
contrasted with Todorov's log-sum-exp over rewards, which is a disjunction. Composition type:
CONCURRENT, with fixed equal weights.

Learned vs hand-designed. Everything is learned: each Q_i and a sampling network per skill. The
rewards are hand-designed (the stacking reward adds a negative log-distance term and a downward
force term). Data: on-robot RL interaction, no demonstrations. Composition needs no new
environment samples, but it does need a training step: SQL must fit a new amortised SVGD sampler
to exp(Q_Sigma), which the authors do on the replay data from the constituent runs (Sec. V-B).
Fig. 3 shows this extraction takes far fewer gradient steps than training the composed task
from scratch; offline SQL on the same data for the composed task failed to converge. Constituents
must share the state and action space.

Guarantee (Lemma 1, Theorem 1, Appendix A-B). Stated for alpha = 1 and two policies; the authors
say the extension is straightforward but do not write it out.

    Q_Sigma(s,a) >= Q_C*(s,a) >= Q_Sigma(s,a) - C*(s,a)
    C*  = fixed point of  C(s,a) <- gamma * E_{s'~p(.|s,a)} [ D_{1/2}(pi_1*(.|s') || pi_2*(.|s'))
                                                             + max_{a'} C(s',a') ]
    Q_C^{pi_Sigma}(s,a) >= Q_C*(s,a) - D*(s,a)
    D*  = fixed point of  D(s,a) <- gamma * E_{s'} E_{a'~pi_Sigma} [ C*(s',a') + D(s',a') ]

gamma is the discount, p the transition density, D_{1/2} the Renyi divergence of order 1/2
between the two optimal constituent policies. C* is the discounted value of an adversary that
collects divergence as reward; D* propagates C* along the composed policy's own state
distribution. Assumptions: both constituents are exactly optimal soft policies for their rewards,
same MDP dynamics, bounded rewards, and composition is on the averaged reward. The authors call the
bound "likely quite loose" and read it qualitatively: regret shrinks when constituents agree on
the states the composed policy visits, and deterministic policies have infinite divergence unless
identical, so they compose badly.

Evidence.
- Simulated planar pushing (MuJoCo), final cylinder-to-goal distance, Table I. SQL composed
  ("merge") vs trained directly ("push"): bottom-left 0.11 +/- 0.05 vs 0.11 +/- 0.11,
  bottom-middle 0.09 +/- 0.09 vs 0.12 +/- 0.09, bottom-right 0.15 +/- 0.14 vs 0.18 +/- 0.17.
  NAF merge bottom-right 0.43 +/- 0.21. Episode count for the table is not stated; Fig. 2 plots
  100 episodes.
- Sawyer reaching: SQL solves it in about 10 minutes; DDPG and NAF slower (Fig. 4, 3 runs each).
- Sawyer Lego stacking: first insertion after 30 min, converged in 2 h, 100 % success on 20
  trials (Sec. V-C2).
- Sawyer composition (Fig. 6, 10 trials each): avoid-only never stacked; stack-only collided
  with the obstacle every time and stacked 30 %; composed policy avoided and stacked 100 %.

Limitations. Stated: loose bound, analysis does not cover DDPG (alpha = 0), future work needs a
correction to the composed Q. Seen by me: the bound cannot be evaluated in practice because it
needs Q_i* and a fixed point over unknown dynamics. Equal weights give no priority, so a safety
skill can be outvoted. Real-robot evidence is one composition on 10 trials. Each constituent's
observation must contain whatever the other skill needs.

Fit with Neil's architecture. Belongs inside one learned skill, not at the task layer. It cannot
compose with a deterministic skill, since it needs a soft Q-function per component. Component
contract: inputs are the shared state vector; precondition is that the state lies in the training
distribution of every constituent; success and failure exist only as reward thresholds. When the
composite fails, nothing tells you which constituent caused it, so testability goes down.

Fit with pork-leg alignment. Weak. It needs soft-Q RL per sub-objective (track belt, rotate leg,
keep trotter over edge) in one observation space, with contact on an 11 kg deformable, which this
paper never tests.

## 2. Urain et al., Composable Energy Policies (RSS 2021; IJRR 2023)

Links: [RSS arXiv abs](https://arxiv.org/abs/2105.04962), [RSS PDF](https://arxiv.org/pdf/2105.04962),
[IJRR DOI 10.1177/02783649231179499](https://doi.org/10.1177/02783649231179499),
[IJRR author PDF](https://www.ias.informatik.tu-darmstadt.de/uploads/Site/EditPublication/urain_2023_cep_ijrr.pdf)
(IJRR 42(10):827-858 per Crossref).

Problem. Reactive controllers (APF, RMP) compute one deterministic action per objective and take a
metric-weighted sum, which can oscillate or stall when components conflict. CEP models each
component as a stochastic policy in its own task space and picks the configuration-space action
that maximises their product. The IJRR abstract softens the RSS claim: "our approach is not
directly able to solve the conflicting policies problem", but richer component shapes reduce
conflicts in some tasks.

Composition operator (IJRR Eq. 1, 8, 10, 16):

    pi_k(a|s) = exp(E_k(a,s)) / Z_k(s)
    a_q* = argmax_{a_q} sum_k beta_k * E^{x_k}( f_q^{x_k}(a_q, s_q) )

a_q is the joint acceleration, s_q = (q, q_dot, environment context), f_q^{x_k} a deterministic
map from configuration space to task space k (forward kinematics and Jacobian), E^{x_k} the energy
of component k in that task space (higher is better in this paper's sign convention), beta_k > 0 an
inverse temperature (dropped in IJRR Eq. 16), Z_k the normaliser, which does not depend on the
action and so drops out of the argmax. Maps can nest, forming an "energy tree". The argmax is solved
by cross-entropy sampling (Algorithm 1), with no warm start between control steps. Composition type:
CONCURRENT. In the RL variant (IJRR Eq. 61-63) an RL agent outputs parameters psi that condition
some energies (target, metric) while fixed prior energies stay in the product, which is
HIERARCHICAL over a CONCURRENT core.

Section 3 shows RMP is the special case where every component is Gaussian with mean g_k and
precision Lambda_k: the product is Gaussian and its mode is
(sum_j Lambda_j)^-1 * sum_k Lambda_k * g_k. Hard constraints come from energies that are 0 on
allowed actions and -inf elsewhere (uniform policy over a half-space), used for obstacle distance
and joint limits (IJRR Table 1, Eq. 46-54).

Learned vs hand-designed. In the reaching experiments all energies are analytic. IJRR derives
them as one-step optimal advantage functions of hand-written rewards: quadratic target reward,
binary obstacle and joint-limit rewards, quadratic joint-velocity penalty. In the puck task the RL
agent (PPO, SAC, DDPG, TD3 tested) learns psi. Section 4.2 proposes learning energies by
behaviour cloning, but the conclusion lists data-driven components as not evaluated. Components are
designed independently and added without retraining; that is the point of the method.

Guarantees. No bound on the composed controller. Appendix A (RSS) / B (IJRR) shows that for a
horizon-1 control-as-inference problem the sum of optimal component Q-functions is optimal for the
summed reward, and that the gap Delta Q grows with horizon (their Eq. 49-51 RSS). The -inf energies
enforce constraints only on sampled candidates for the next step; the authors say the method is
myopic and gives no long-run guarantee (IJRR Sec. 8).

Evidence.
- Simulated 7-DoF KUKA LWR reaching through clutter, 100 random starts per environment, 250 Hz,
  30 s episodes. IJRR Table 2 (3D goal), success out of 100, RMP / APF / CEP: Cage I 29 / 2 / 70,
  Cage II 5 / 0 / 15. Table 3 (6D goal): Cage I 11 / 0 / 30, Cage II 0 / 0 / 5. Zero collisions for
  all methods. The RSS Table I numbers for the same setup differ (CEP Cage I 89, Cage II 46); see
  the last section.
- Compute (IJRR Sec. 6.2.1): 50 particles, one CEM step, AMD Ryzen 9 3900 CPU, about 0.002 s per
  action vs 0.0015 s for RMP and APF, run at 500 Hz in non-optimised Python. Ablation: success
  plateaus beyond 50 particles; below 500 particles the CPU is faster than the GPU.
- Real-robot pick-and-place through a narrow hole in a wall modelled as 67 spheres, 30 runs per
  condition (fixed targets, human pushes, targets moved online): on average above 75 % success,
  CEP better than RMP in every condition (Fig. 10, values only in the plot). The robot model is
  not named in the text I extracted. Failures: stuck in a local minimum entering the wrong hole.
- Puck hitting, simulated 7-DoF iiwa: CEP was the only structured policy with zero table
  collisions during RL exploration across three reward designs (Fig. 13, curves only).

Limitations. Stated: myopic, gets stuck in clutter and narrow passages, suggests adding a planner;
slower than analytic RMP; normaliser under non-bijective maps left for future work. Seen by me: CEM
makes the command stochastic per control step unless the sampler is seeded; if no candidate is
feasible every sample scores -inf and the paper does not say what action is sent; no priority
beyond hard -inf versus soft energies.

Fit with Neil's architecture. Belongs in the motion layer inside a skill such as approach or
transport, below task logic. It composes classical and learned components natively: a PD attractor
is a quadratic energy, a keep-out zone is a -inf energy, a learned energy can be added. Each energy
is a pure function of (state, candidate action) and can be unit-tested in isolation, which helps.
The composite's stall mode needs its own monitor. Example contract for `intercept_approach`:
inputs are q, q_dot, predicted grasp pose in the belt frame, belt velocity, keep-out spheres;
preconditions are a pose estimate younger than the cell's staleness bound and a target inside the
reach window; success is the tool within position and velocity tolerance of the moving target;
failure is best-sample energy of -inf, or distance-to-goal not decreasing over a window (local
minimum), or target leaving the window; recovery is retreat to a safe pose and let the leg pass, or
hand over to a planner.

Fit with pork-leg alignment. Plausible for intercept and approach over a moving belt: attractor to
a grasp point moving at belt speed, -inf energies for belt surface, cutter housing and joint limits.
Needed: a collision model small enough for 500 Hz (the paper uses spheres), a grasp-point predictor,
and a stall detector. It does not address the contact phase of rotating the leg. It needs only FK
and Jacobians, so it does not settle SCARA vs 6-DOF.

## 3. Hansel et al., Hierarchical Policy Blending as Inference (ICRA 2023)

Links: [arXiv abs](https://arxiv.org/abs/2210.07890), [PDF](https://arxiv.org/pdf/2210.07890),
[DOI 10.1109/ICRA48891.2023.10161374](https://doi.org/10.1109/ICRA48891.2023.10161374),
[project page](https://sites.google.com/view/hipbi).

Problem. Reactive blends (RMPflow) are fast but myopic and get trapped in local minima; MPC
re-planning looks ahead but is too slow in high dimensions to stay reactive. HiPBI keeps the RMP
experts at the low level and lets a sampling planner choose their blending weights online.

Composition operator (Sec. IV, Eq. 1):

    pi(a_t | s_t, beta) proportional to prod_{i=1..n} pi_i(a_t | s_t; theta_i)^{beta_i}
    pi_i = N(mu_i(s_t), Lambda_i(s_t)^-1)
    a_t* = argmax_a log pi(a | s_t, beta)
         = (sum_i beta_i Lambda_i)^-1 * sum_i beta_i Lambda_i mu_i

Here the energy convention is pi_i proportional to exp(-E_i), with E_i a quadratic RMP cost;
mu_i is the RMP forcing term, Lambda_i its Riemannian metric (precision), theta_i hand-tuned
hyperparameters, and beta the temperatures, drawn from q(beta; theta) = Dirichlet so they are
positive and sum to one. The closed form is the standard product of Gaussians; the paper states a
closed form exists but does not print it. The high level does iCEM over beta, maximising
J(beta) = E_{q(beta) q_hat(tau)} [ sum_{t..t+h} log p(O_t = 1 | a_t, s_t) + lambda_pi log pi(a_t|beta,s_t) ]
by shooting rollouts over horizon h; lambda_pi = 0 in all experiments. Composition type:
HIERARCHICAL (planner weights experts) over CONCURRENT (product of experts).

Learned vs hand-designed. Nothing is learned. Experts are hand-tuned RMPs; beta is inferred online.
It needs a rollout model of the robot and constant-velocity models of moving obstacles. Experts are
reusable without retraining; only the planner objective is task-specific.

Guarantees. None stated. The Dirichlet guarantees every expert keeps some weight (Sec. V).

Evidence (all simulation).
- 2D point mass, Table I. 2D-Box: RMPflow success 0 %, safety 100 %; asynchronous iCEM-MPC with
  look-ahead 75: 79 % / 85 %; asynchronous HiPBI look-ahead 75: 100 % / 100 %. 2D-Maze: RMPflow
  77 % / 89 %; async iCEM look-ahead 75: 0 % / 0 %; async HiPBI look-ahead 75: 86 % / 87 %.
  Episode counts not stated.
- 7-DoF Panda in PyBullet, eight experts (self-collision, joint and velocity limits, goal,
  floor, boxes, spheres), planner at 10 Hz, look-ahead 25 = 2.5 s. Fig. 5 success, RMPflow vs
  HiPBI look-ahead 50: static, 1 to 5 obstacles 43.1 / 20.0 / 23.5 / 21.6 / 25.5 vs
  72.3 / 66.7 / 61.9 / 63.2 / 70.6; dynamic, 1 to 5 obstacles 90.2 / 76.5 / 82.4 / 64.7 / 64.7 vs
  96.7 / 90.2 / 90.9 / 88.3 / 83.6. Trial counts not stated.

Limitations. Stated: higher compute than RMPflow; real-robot work and a learned prior over beta
are future work. Seen by me: no hardware; safety rate in 2D-Maze stays at 87 % with the planner, so
blending can down-weight an avoidance expert enough to collide; weights sum to one, so raising goal
weight necessarily lowers safety weight; results depend on a rollout model.

Fit with Neil's architecture. A motion-layer skill with an internal two-rate structure: 10 Hz
weight planner, fast expert blend. Experts are classical and individually testable. The beta
trajectory is a useful debug signal (log it). Safety cannot live inside the blend, since weights
trade safety off; keep it in a separate deterministic limiter. Contract failure signals: planner
returns no improving beta, or goal distance stalls.

Fit with pork-leg alignment. The conveyor is a constant-velocity world, which is exactly the
obstacle model HiPBI assumes. It could handle approach around other legs on the belt. It needs a
working RMP expert set first and a real-robot validation the paper does not provide.

## 4. Pignat, Silverio, Calinon, LfD using Products of Experts (arXiv 2020; IJRR 2022)

Links: [arXiv abs](https://arxiv.org/abs/2010.03505), [PDF](https://arxiv.org/pdf/2010.03505),
[DOI 10.1177/02783649211040561](https://doi.org/10.1177/02783649211040561) (IJRR 41(2):163-188
per Crossref), [video](https://sites.google.com/view/poexperts).

Problem. LfD methods often learn task-space distributions (end-effector pose, orientation,
manipulability) separately and fuse them only in the controller. That ignores kinematic
reachability and the coupling between task spaces, and it cannot recover a secondary objective
that demonstrations only show partly because a primary objective masked it. The paper learns a
joint-angle distribution as a renormalised product of task-space experts, trained jointly.

Composition operator (Eq. 2, 17-21):

    p(q | theta_1..M) = prod_m p_m(T_m(q) | theta_m) / integral_z prod_m p_m(T_m(z) | theta_m) dz

q is the joint configuration, T_m a transformation into task space m (forward kinematics, relative
distance, manipulability, a learned invertible network), p_m the expert density there (Gaussian,
matrix Bingham-von Mises-Fisher, ProMP, CDF for inequalities, uni-Gauss). Composition type:
CONCURRENT. PoENS adds a strict HIERARCHY, detailed in the unifying section.

Learned vs hand-designed. The designer picks transformations and expert families; demonstrations
supply expert parameters (targets, variances) and, optionally, transformation parameters such as an
unknown tool offset d (Sec. 6.3). Data: static configuration samples, N = 3 to 3000 per experiment,
typically 30 (10 per situation in the waiter task). Training maximises the joint likelihood; the
normaliser's gradient is estimated with a variational mixture approximation instead of contrastive
divergence (Sec. 2.3). Experts are initialised by independent MLE, then trained jointly. Joint
training is required, and it is the paper's main claim: independent experts give biased secondary
objectives (Table 2, Fig. 12, 14). Training takes 10 s to a minute (Sec. 1.1). Control (Sec. 5):
the negative log-density becomes an LQT cost linearised through each Jacobian, so each expert's
feedback gain scales with its learned precision and unconstrained directions stay compliant
(Algorithms 1-2: 2-10 ms high-level loop in Python, below 1 ms low-level loop in C++).

Guarantees. None on control. Classical nullspace property only to first order (below).

Evidence.
- 2-DoF planar, VI vs contrastive divergence, alpha-divergence to ground truth, Table 1:
  task (a) 0.067 +/- 0.060 vs 0.837 +/- 0.597.
- Hierarchical planar tasks, Table 2, independent / PoE / PoENS: bimanual 1.814 +/- 0.055 /
  0.258 +/- 0.101 / 0.094 +/- 0.024; manipulability 0.812 +/- 0.117 / 0.630 +/- 0.086 /
  0.202 +/- 0.067.
- 7-DoF Panda welding-style dataset, MMD^2_u, Table 3, case (0): 1.3e-3 / 7.0e-4 / -9.8e-6 (negative
  values mean near-zero discrepancy, per the paper's footnote).
- Real Panda waiter task (Fig. 15-16): tray orientation primary over bottle position, learned from
  10 samples in each of 3 situations; qualitative, the robot keeps the tray level when the hand
  is out of reach.
- New end-effector and conditional targets: PoE beats VAE, GMR, NVP and GANs on MMD for all dataset
  sizes (Fig. 19, Table 4; case (c) far target: PoE 3.4e-7, VAE 1.0e-2, GMR 9.0e-2).

Limitations. Stated: sampling a PoE needs approximation, and a new condition costs optimisation
time; PoENS has no evaluable likelihood, only a gradient, so only SVI-type methods apply. Seen by
me: models static configurations, not motions (ProMP experts partly address this); the priority
is first-order and equality-shaped; most quantitative results are on synthetic data from
ground-truth PoEs.

Fit with Neil's architecture. Offline learned component that produces a cost and gains for a
classical LQT controller, so it composes with deterministic control by construction. Experts are
interpretable (a mean and a variance per task space), which helps debugging. The joint training
means one expert cannot be swapped without retraining the product. Contract: inputs q, q_dot and
the condition (target pose); precondition that the condition lies near demonstrated conditions;
success when every expert's task value is within k standard deviations of its mean; failure when
the LQT converges to a mode where a primary expert is outside tolerance; recovery via a scripted
re-approach.

Fit with pork-leg alignment. Candidate for the orient and place pose: learn from a few
demonstrations where the gripper should be relative to the belt edge (primary) and preferred wrist
orientation (secondary), with compliance along directions the demonstrations leave free. Needed:
demonstrations on the real cell, a known pose of the belt edge, and a separate hard safety layer.

## Unifying view: three spellings of one operator

Write any policy as a Gibbs density pi(a|s) proportional to exp(phi(s,a)). Then

    sum_k beta_k * phi_k   is   log prod_k pi_k^{beta_k}   (up to an action-independent constant)

- Haarnoja: phi_k = Q_k*/alpha, beta_k = 1/|C|. Adding soft Q-functions is a product of policies.
- Urain: phi_k = E_k composed with a task map, beta_k fixed. Adding energies is a product of policies.
- Hansel: phi_k = -E_k quadratic, beta ~ Dirichlet chosen by a planner. Weighted product.
- Pignat: phi_m = log p_m(T_m(q)). Multiplying expert densities is adding their log-densities.

In all four the result behaves like AND: it is high only where every component is non-negligible.
A mixture (sum of densities, log-sum-exp of phi) is the OR that Haarnoja contrasts against.

Where they differ.
- What phi measures. Haarnoja: long-horizon soft value, so composition error accumulates over the
  horizon, hence the Renyi fixed-point bound. Urain and Hansel: one-step energies; Urain's appendix
  shows summing is exact for horizon 1 and degrades with horizon, which Hansel patches by planning
  over beta. Pignat: a density over static configurations, not an action distribution.
- Where components live. Haarnoja needs one shared state-action space. The other three put each
  component in its own task space and pull it back through kinematics.
- How an action comes out. Haarnoja trains a sampler on the summed Q. Urain samples candidate
  accelerations with CEM. Hansel has a closed-form Gaussian mode per beta. Pignat tracks the
  log-density with LQT or samples it variationally.
- Normalisation. Irrelevant for picking an action (Z does not depend on a). Pignat's point is
  that it matters for learning: the renormalised product is what couples experts during training,
  so separately fitted experts are not the MLE of the product.
- Priority. Only Pignat gives a strict ordering. Urain gets hard constraints from -inf energies.
  Haarnoja and Hansel only have weights, and weights never make one objective strictly dominate.

### PoENS: strict priority by filtering the gradient

A classical prioritised IK solution (Pignat Eq. 19, Nakamura 1987) is
q_dot = J_1^+ y_1_dot + (I - J_1^+ J_1) z, where J_1 is the Jacobian of the primary task
y_1 = T_1(q), J_1^+ its pseudoinverse, and z anything. N_1 = I - J_1^+ J_1 projects onto joint
motions that do not change y_1 to first order, since J_1 N_1 = 0.

PoENS does not project a velocity command. It redefines the gradient of the PoE log-density with
respect to q (Eq. 21, primary expert 1, secondary expert 2):

    d log p / dq = (d log p_1/dy_1) J_1(q)  +  (d log p_2/dy_2) J_2(q) N_1(q)

Gradients here are row vectors. The secondary expert's pull on q is stripped of every component
that would move y_1, so it can only act inside the primary task's nullspace. Training with this
gradient explains the secondary objective as a preference that holds only where the primary leaves
freedom. That is how PoENS recovers the right secondary target from data where the secondary
target was never reached (Fig. 12). The paper claims an arbitrary number of prioritised tasks; the
text I read writes out only the two-expert case, so the multi-level form is my assumption. The
paper states that PoENS is defined only through this gradient and its unnormalised log-likelihood
cannot be evaluated (Sec. 3); my reading of why is that the filtered field is in general not the
gradient of any scalar.

Tiny example. q in R^2, primary y_1 = q_1 + q_2 so J_1 = [1 1]; secondary y_2 = q_1 so J_2 = [1 0].
J_1^+ = [0.5 0.5]^T, N_1 = [[0.5, -0.5], [-0.5, 0.5]]. A secondary gradient dlog p_2/dy_2 = 1 gives
[1 0] N_1 = [0.5 -0.5]: move q_1 up and q_2 down equally, which leaves q_1 + q_2 unchanged.

Consequences for industrial skills (my reading, not tested in the paper).
- The guarantee is local and first-order: second-order kinematic effects still let a secondary
  expert drift the primary task a little.
- N_1 is built from an equality-style Jacobian and does not switch off. An inequality expert such
  as a CDF joint limit on T(q) = q_0 has J = e_0^T at every q, so placing it as primary would freeze
  joint 0 for every secondary expert even far from the limit. Inequality priorities need an
  activation rule, which this paper does not provide.
- Near singularities of J_1 the nullspace changes rank abruptly, so the filter is discontinuous.
- For "safety outranks reaching", a certified limiter or constrained QP outside the learned model
  is still the right layer. PoENS is better suited to preference ordering, such as tray level over
  bottle position.

### Worked 1-D example: product of two Gaussian experts

Expert 1 N(mean 0, variance 1), for example "stay near the nominal pose". Expert 2 N(mean 2,
variance 0.25), for example "reach the target". Precisions add, and the mean is precision-weighted:

    precision = 1/1 + 1/0.25 = 1 + 4 = 5         variance = 1/5 = 0.2   (std 0.447)
    mean      = (1*0 + 4*2) / 5 = 1.6

Same answer as an energy sum: E = -a^2/2 - 2(a - 2)^2, dE/da = -a - 4(a - 2) = 0 gives a = 1.6.
The product is narrower than either expert and sits near the confident one. For contrast, an equal
mixture of the two has mean 1.0 and variance 1.625: wider, with mass on both experts' modes.

Temperatures: with beta = (0.5, 0.5) the precision is 2.5 (variance 0.4) and the mean stays 1.6;
scaling all betas equally changes sharpness, not location. With beta = (1, 0.25) the effective
precisions are 1 and 1, so the mean is 1.0 and the variance 0.5. Only relative weights move the
mode, which is what Hansel's planner exploits.

A CEP-style hard constraint: multiply by an expert that is uniform on a <= 1.2 and zero above. The
product is the Gaussian above truncated at 1.2, so its mode moves from 1.6 to 1.2. No weight on the
Gaussians can push the mode past 1.2, which is the difference between a constraint and a weight.

## Comparison

| Paper | Operator | Seq / conc / hier | Learned or classical components | Composable without retraining? | Real robot? | Key limitation |
|---|---|---|---|---|---|---|
| Haarnoja 2018 | Mean of soft Q-functions, product of max-ent policies | Concurrent | Learned (SQL), hand-written rewards | No new env data; sampler must be refit to summed Q | Yes, Sawyer, 1 composition, 10 trials | Needs optimal soft Q per skill in one state space; loose, uncomputable bound; no priority |
| Urain 2021/2023 (CEP) | Sum of task-space energies, CEM argmax | Concurrent (hierarchical with RL parameters) | Mostly analytic energies; RL sets parameters; learned energies proposed, not evaluated | Yes | Yes, pick-and-place through hole, 30 runs per condition | Myopic, stalls in narrow passages; stochastic per-step solve |
| Hansel 2023 (HiPBI) | Beta-weighted product of Gaussian RMP experts, planner picks beta | Hierarchical over concurrent | Classical RMP experts, online iCEM planner | Yes | No, simulation only | Weights trade safety against goal; needs rollout model; no hardware |
| Pignat 2020/2022 (PoE, PoENS) | Renormalised product of task-space densities; nullspace-filtered gradient | Concurrent; strict hierarchy with PoENS | Learned from demos, hand-chosen transforms, classical LQT | No, joint training required | Yes, Panda waiter task, qualitative | Static configurations; first-order equality priority; approximate sampling |

## What this changes for the meat cell

- For concurrent skills (approach while avoiding, orient while holding the edge), CEP energy sums
  mix classical and learned terms most directly, with each term unit-testable.
- None of the four is a task-layer sequencer. Recovery, verification and sequencing stay in task
  logic.
- Strict safety stays deterministic and outside these products. None of the four informs the
  perception or SCARA vs 6-DOF decisions; they consume a state estimate and need only kinematics.

## What I am not sure about

- CEP IJRR Tables 2 and 3 say "first three rows are the results from (Urain et al. 2021)" and
  mention a fourth row with the robot hand, but only three rows appear and their numbers differ
  from RSS Table I (CEP Cage I 70 vs 89). I report IJRR values; which setup produced which numbers
  is unverified.
- The real robot used in the CEP IJRR pick-and-place is not named in the extracted text, and the
  per-condition success counts exist only in Fig. 10.
- CEP RSS and IJRR both print the GPU as "RTX-2800" / "RTX 2800", which does not match an Nvidia
  product name I know (unverified; possibly RTX 2080).
- Hansel: the arXiv metadata abstract says "6DoF manipulation", the v3 PDF says 7DoF. The ICRA
  version was not read. Trial counts behind Fig. 5 and Table I are not given in the text.
- Pignat: whether the welding dataset came from the physical Panda or from simulation is not stated.
  In the experiments I read, the designer fixes which expert is primary and demonstrations supply
  targets and variances. I could not confirm whether the ordering itself is ever learned.
- Pignat IJRR 2022 may differ from arXiv v1; SAGE returned HTTP 403 to scripted fetches.
- Haarnoja's claim that the bound extends to more than two policies and any alpha is the authors'
  statement; no proof is given.
- How CEM in CEP behaves when every sampled action violates a -inf energy is not discussed in
  either version.

## Sources

- Haarnoja et al. 2018: https://arxiv.org/abs/1803.06773, https://doi.org/10.1109/ICRA.2018.8460756
- Urain et al. RSS 2021: https://arxiv.org/abs/2105.04962
- Urain et al. IJRR 2023: https://doi.org/10.1177/02783649231179499, https://www.ias.informatik.tu-darmstadt.de/uploads/Site/EditPublication/urain_2023_cep_ijrr.pdf
- Hansel et al. ICRA 2023: https://arxiv.org/abs/2210.07890, https://doi.org/10.1109/ICRA48891.2023.10161374
- Pignat et al. IJRR 2022: https://arxiv.org/abs/2010.03505, https://doi.org/10.1177/02783649211040561
- Crossref (volume, pages): https://api.crossref.org/works/10.1177/02783649231179499, https://api.crossref.org/works/10.1177/02783649211040561
