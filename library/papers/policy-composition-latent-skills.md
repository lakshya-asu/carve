---
title: "Policy composition with latent skills: MCP, skill embeddings, latent MPC, composite motion"
date: 2026-09-14
tags: [paper, skills, composition, hierarchical-rl, latent-space, mpc, sim-to-real, skill-contracts]
status: draft
source:
  - https://arxiv.org/abs/1905.09808
  - https://openreview.net/forum?id=rk07ZXZRb
  - https://arxiv.org/abs/1810.02422
  - https://arxiv.org/abs/2305.03286
---

# Policy composition with latent skills

Four papers read in full, 2026-09-14, against Neil's skill-contract architecture (every skill
declares inputs, preconditions, outputs, success, failure and recovery; tasks are compositions;
deterministic wherever reliable) and the first application: aligning bone-in pork legs (about
11 kg, 720 mm, figures from Neil's brief) on a moving belt so the trotter hangs off the edge.
Cell context lives in [meat-cell-architecture](../topics/meat-cell-architecture.md),
[control-architecture-selection](../topics/control-architecture-selection.md) and
[arm-selection-scara-vs-six-axis](../topics/arm-selection-scara-vs-six-axis.md).

Texts read: MCP arXiv v1 (23 May 2019) with supplementary; Hausman et al. ICLR camera-ready
PDF (OpenReview is behind a bot challenge, so read from the
[Wayback copy of the OpenReview PDF](https://web.archive.org/web/2019/https://openreview.net/pdf?id=rk07ZXZRb));
He et al. arXiv v1, diffed against v2 and v3; Xu et al. arXiv v1 (5 May 2023) with appendix.

## 1. MCP: multiplicative compositional policies (Peng et al., NeurIPS 2019)

**Citation.** Xue Bin Peng, Michael Chang, Grace Zhang, Pieter Abbeel, Sergey Levine. NeurIPS
2019. [arXiv 1905.09808](https://arxiv.org/abs/1905.09808),
[NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2019/hash/95192c98732387165bf8e396c0f2dad2-Abstract.html),
[project page](https://xbpeng.github.io/projects/MCP/).

**Problem.** Hierarchical policies and mixtures of experts pick one primitive per timestep, which
limits what a high-DoF body can do when several subtasks must run at once (walk and carry). MCP
learns primitives in pre-training that a new gating policy can activate simultaneously on a
transfer task, so the transfer task is learned in an 8-D weight space instead of the raw action
space (Sec. 1, 2).

**Composition operator.** Each primitive i is a diagonal Gaussian over actions that sees only the
state, pi_i(a|s) = N(mu_i(s), Sigma_i(s)). A gating network outputs non-negative weights w_i(s, g)
from state and goal. The composite policy is a weighted product (Eq. 2, Eq. 4):

    pi(a|s,g) = (1 / Z(s,g)) * prod_{i=1..k} pi_i(a|s)^{w_i(s,g)}

Z is the normalizer, k the number of primitives (8 in all experiments). For Gaussians the product
is Gaussian, per action dimension j (Eq. 3; the paper writes sigma_i^j for the variance):

    mu^j   = sum_i (w_i / var_i^j) * mu_i^j  /  sum_i (w_i / var_i^j)
    var^j  = 1 / sum_i (w_i / var_i^j)

In words: each primitive's vote on dimension j counts in proportion to its gating weight times its
precision on that dimension. A primitive that is confident about joint j (small variance) and
unconfident about joint m effectively controls j and abstains on m. Weights are bounded to [0, 1]
by a sigmoid (Fig. 3). Composition is CONCURRENT (spatial, across action dimensions) inside a
two-level HIERARCHY (gating over primitives). There is no temporal abstraction; the authors name
that as future work (Sec. 6).

**Learned vs hand-designed.** Learned: primitives and gating, end to end with PPO on motion
imitation of mocap walking and turning clips (230 s for biped and humanoid, 11 s of keyframed
animation for the T-Rex; supplementary Sec. 8). Hand-designed: the reference corpus, the
asymmetric input split (goal visible only to the gate, which the authors use to stop one primitive
absorbing every goal, Sec. 3.2), k, and each transfer task's reward. On a new task the primitives
are frozen and a new gating policy omega(w|s,g) is trained with RL (Algorithm 1). New tasks are
not solved without training; the primitives are reused, the composer is retrained.

**Guarantees.** None. The closed form in Eq. 3 is exact for Gaussian primitives. The authors give
an informal argument: with equal variances across primitives, w selects a point in the convex hull
of the primitive means (Sec. 5.2).

**Evidence.** Simulation only: 14-DoF Gym Ant, 23-DoF biped, 34-DoF humanoid, 55-DoF T-Rex, PD
targets at 30 Hz. Metric is normalized return over about 100 episodes, 3 seeds per method (Sec.
5.2). Table 1 and supplementary Table 2:

- Dribble, T-Rex: MCP 0.781 ± 0.021; latent space model 0.115 ± 0.013; MOE 0.070 ± 0.017;
  finetune 0.074 ± 0.011.
- Carry, biped: MCP 0.575 ± 0.032; latent space 0.456 ± 0.031; finetune 0.324 ± 0.014; MOE
  0.013 ± 0.013.
- Dribble, humanoid: MCP 0.805 ± 0.006; latent space 0.751 ± 0.006.
- Heading, humanoid (Table 2): finetune 0.975 ± 0.008 beats MCP 0.970 ± 0.003. Heading, T-Rex:
  finetune 0.953 ± 0.004 beats MCP 0.932 ± 0.007.
- Holdout Ant (train on headings in [0, 3pi/2], transfer to [3pi/2, 2pi]): scratch 0.951 ± 0.093,
  finetune 0.885 ± 0.062, MCP 0.812 ± 0.030, latent space 0.745 ± 0.060.

Primitive count (supplementary): no noticeable difference between k = 4 and 8; learning slows at
16 and 32. Fig. 7 shows gating weights tracking left and right stance phase, consistent across
runs.

**Limitations.** Stated: no temporal abstraction; the reference corpus must be chosen with care.
Visible: every result is an animated character; "manipulation" in Carry attaches the 5 kg box
with a virtual joint on contact (supplementary Sec. 9), so grasping is not tested. MCP loses to
training from scratch on the only out-of-distribution test. Three seeds. If all weights go to zero
the composite variance diverges (follows from Eq. 3). Primitives have no names or specs; the
walk-cycle specialization in Fig. 7 was found after training by inspection.

**Fit with Neil's architecture.** MCP belongs inside one learned skill, as that skill's action
head. Its primitives are basis functions without success conditions, so they cannot be contract
units. The contract wraps the composite: inputs (state, goal), precondition (state inside the
pre-training distribution), success and failure from the skill's own verify step, recovery owned
by task logic. Testability is mixed. Frozen primitives mean a regression on a new gating policy
cannot break other tasks that share them, and the logged w_i(t) is a cheap diagnostic, but "why
did the arm do that" resolves to "primitive 5 had weight 0.8", which nobody can check against a
spec. One idea the paper does not test: a classical controller can be written as a Gaussian with
chosen variance and multiplied in as a fixed primitive, so a deterministic tracker owns the axes
where its variance is small and learned primitives fill the rest (my inference, untested).

**Fit with pork-leg alignment.** Weak for the core task. The candidate sub-skill is a contact
nudge that rotates or slides the leg on the belt while tracking it, where belt tracking is
deterministic and the contact response is uncertain. For that to work: a simulator in which a
deformable 11 kg leg slides and rotates on a belt credibly, a pre-training corpus of arm motions
(scripted or teleoperated) that covers the needed behaviours, and a per-task RL budget for the
gate. MCP's evidence is in locomotion, not arm manipulation.

## 2. Learning an embedding space for transferable robot skills (Hausman et al., ICLR 2018)

**Citation.** Karol Hausman, Jost Tobias Springenberg, Ziyu Wang, Nicolas Heess, Martin
Riedmiller. ICLR 2018. [OpenReview](https://openreview.net/forum?id=rk07ZXZRb),
[PDF](https://openreview.net/pdf?id=rk07ZXZRb). A shorter workshop version with a different
title ("Learning Skill Embeddings for Transferable Robot Skills") is on the
[first author's site](https://karolhausman.github.io/pdf/hausman17nips-ws2.pdf); not used here.

**Problem.** Multi-task RL learns one solution per task and nothing reusable. The paper learns a
continuous latent skill space from a set of training tasks, regularized so different latents do
distinguishably different things, and then solves new tasks by controlling the latent instead of
joint torques (Sec. 1, 4).

**Composition operator.** A task id t (one-hot) goes through a linear embedding network to a
Gaussian p_phi(z|t); z conditions a shared policy pi_theta(a|s, z); an inference network
q_psi(z | a, s^H) tries to recover z from the last H states. The per-step augmented reward is
(Eq. 3):

    r_hat(s_i, a_i, z, t) = r_t(s_i, a_i) + alpha2 * log q_psi(z | a_i, s^H_i)
                            + alpha3 * H[pi_theta(a | s_i, z)]
    L(theta, phi, psi) = E[ sum_i gamma^i * r_hat ] + alpha1 * E_t H[p_phi(z|t)]

r_t is the task reward, gamma the discount, H[.] entropy, alpha1..3 weights (all 1e3, Table in
App. E.2). The first entropy term spreads each task over a wide region of z, the log q term
rewards trajectories from which z can be identified, the policy entropy stops collapse. At
transfer the policy is frozen and a new network z = f_vartheta(x) is trained with RL to output
latents (Sec. 6). Composition is HIERARCHICAL; the high-level network produces interpolation (a z
between two skill clusters) and SEQUENCING (z changing over time). It does not blend in action
space.

**Learned vs hand-designed.** Learned: embedding, policy, inference network, Q-function (Retrace
with stochastic value gradients, off-policy), and the transfer mapping f. Hand-designed: the set
of pre-training tasks and their rewards, embedding dimension (3-D Gaussian), a shared observation
and action space across all tasks. New tasks need RL training of f; the skills are not retrained.

**Guarantees.** Eq. 2 is a variational lower bound on policy entropy that holds for any choice of
q (Theorem 1, App. B). Retrace importance weights give an unbiased estimator in the limit
(footnote 2). No guarantee on transfer performance or on what an arbitrary z does.

**Evidence.** Simulation only. A 2-D point mass and three manipulation tasks on a simulated arm
with 7 joint torques and a 27-D state (App. E.1; the arm model is not named in the text).
Spring-wall (pre-trained on spring and wall separately, tests interpolation), L-wall (pre-trained
on push and lift), rail-push (pre-trained on rail-lift and on-table push, tests sequencing).
Results are learning curves only, average reward over 10 episodes, 16 workers (Fig. 5); no table
and no seed count. Reported outcomes: on rail-push only the full method finds a solution; on L-wall
it is "considerably more successful than all the baselines"; on spring-wall the no-inference-net
ablation reaches similar asymptotic reward. On the four-goal point mass a Bernoulli embedding
found all four goals and a Gaussian embedding reached two (Fig. 3). With two identical tasks under
different ids, KL between their embeddings went to about zero (Fig. 3 right).

**Limitations.** Stated: the high-level and skill policies must share the same observation space
(App. E.1), and changed dynamics reach the agent only through the task id. Visible: no real robot,
no quantitative table, no seed count; the Gaussian embedding missed modes in the one test that
checked for it; the only evidence that interpolation is meaningful is three hand-picked task
triples.

**Fit with Neil's architecture.** A latent skill library plus a learned selector. It sits at the
skill layer, with f acting as a learned piece of task logic. The shared-observation requirement
cuts across Neil's separation of perception and skills: the embedding only generalizes if every
skill consumes the same state vector. A deterministic skill cannot live inside the embedding; it
can sit beside the whole latent skill as a separate contract-bearing unit. The contract for "the
latent skill at z" has no precondition you can write down beyond "states seen in pre-training",
and no success condition beyond the reward of whichever task produced that region of z. One useful
piece: q_psi is a trained detector of "which z produced this trajectory". Monitoring the gap
between the commanded z and q_psi's estimate at runtime is a candidate failure signal (my
suggestion; the paper uses q only as a training regularizer).

**Fit with pork-leg alignment.** Low. Interpolation between, say, a push-to-datum skill and a
rotate skill trained in sim could cover leg-to-leg variation, but the evidence is three simulated
tasks and learning curves. What would have to be true: a sim good enough to pre-train contact
skills on legs, a shared state vector for all of them, and a tolerance for training f by RL for
each new task variant.

## 3. Zero-shot skill composition and sim-to-real by learning task representations (He et al., 2018)

**Citation.** Zhanpeng He, Ryan Julian, Eric Heiden, Hejia Zhang, Stefan Schaal, Joseph J. Lim,
Gaurav Sukhatme, Karol Hausman. [arXiv 1810.02422](https://arxiv.org/abs/1810.02422),
[v1 PDF](https://arxiv.org/pdf/1810.02422v1). Venue and id, as verified on arXiv: v1 (4 Oct
2018) and v2 (13 Nov 2018) carry the comment "Submitted to ICRA 2019"; v3 (27 Jan 2021) carries
"Presented at NeurIPS 2018 Workshop: Deep Reinforcement Learning" and the arXiv listing title
changed to "Simulator Predictive Control: Using Learned Task Representations and MPC for
Zero-Shot Generalization and Sequencing". The PDF title and body are unchanged across all three
versions (text diff). I found no ICRA 2019 proceedings entry (unverified: dblp blocked the query),
so treat it as a workshop paper. Companion paper with the real-robot skill embedding and search
baselines: [Julian et al., ISER 2018, arXiv 1809.10253](https://arxiv.org/abs/1809.10253)
(abstract only read).

**Problem.** Sim-to-real policies transfer one task at a time. The paper pre-trains a
latent-conditioned multi-skill policy in simulation, transfers it to a real Sawyer, and solves
unseen tasks with no further training by planning over skill latents, using the same simulator
as the MPC model (Sec. I, IV-C).

**Composition operator.** Skills are learned with the Hausman et al. objective (Eq. 1), trained
with PPO in MuJoCo, z held fixed for a whole pre-training rollout. The "composer" (Algorithm 1)
at each replanning step:

    sample z_1..z_k ~ p(z) = E_{t ~ p(t)} p_phi(z|t)
    for each z_i: set sim state to observed real state s_real, roll out T steps in sim with
        a_j ~ pi_theta(a | s_j, z_i), s_{j+1} = S(s_j, a_j)
        R_i = sum_{j=0..T} gamma^j * r_new(s_j, a_j)
    z* = argmax_i R_i
    run pi_theta(a | s, z*) on the real robot for N < T steps; repeat until done

k is the number of candidate latents, T the sim horizon, N the real execution horizon, r_new the
new task's reward, S the simulator. The authors set T to at most 2N, because a skill that only
partly completes the task gets penalized if scored over too long a horizon (Sec. IV-C).
Composition is SEQUENTIAL (a chosen sequence of latents) and HIERARCHICAL (planner over frozen
skill policy). It is random-shooting MPC with one latent per candidate held constant over the
horizon.

**Learned vs hand-designed.** Learned in sim: embedding, skill policy, inference network.
Hand-designed: the pre-training skill set (8 reach goals on a 3-D rectangular box for drawing; 4
push directions of 20 cm for pushing), rewards (Euclidean distance to target), MPC constants.
New tasks: zero-shot with respect to training. Only a new reward and a simulator that can be
reset to the real state are needed.

**Guarantees.** None. MPC here is greedy over k random samples with a sim model; no optimality,
feasibility or convergence claims.

**Evidence.** Real Sawyer and MuJoCo sim. Reported in Sec. VI, all as single runs with no trial
count, no success rate and no baseline on the real robot:

- Drawing (k = 15, T = 4, N = 2). Sim: rectangle with 54 latents, triangle with 56. Real robot:
  rectangle with 62 latents in 2 minutes, triangle with 53 latents in under 2 minutes (Figs. 7, 8).
- Pushing a box through waypoints (k = 50, T = 30, N = 10). Sim: up-left in under 30 s and
  right-up-left in under 40 s of equivalent real time. Real robot: left-down with 3 latents in
  about 1 minute, up-left with 8 latents in about 1.5 minutes (Fig. 10).
- Qualitative: on the real push task the robot moved the box back to fix an earlier error, a
  behaviour not trained explicitly (Sec. VI-C).

**Limitations.** Stated: horizon choice matters a lot; long skill horizons mis-score locally
useful skills. Visible: n = 1 per task, no success rates, no timing breakdown, no compute
hardware. The real-state-to-sim reset needs the box pose on the real robot and the paper does not
say how it was measured. Figure references in the results text point at the wrong figures (for
example "Fig. 2" for a drawing result), Figs. 7 and 8 both caption the real triangle, and the
pushing action bound is printed as "up to ±0.03 cm". Tasks are free-space point sequences and
planar pushing of a rigid box: contact, but not deformable and not moving.

**Fit with Neil's architecture.** The closest of the four. The composer is a planner in the task
logic layer that picks a skill and its parameters by simulating each candidate from the current
real state, then runs the chosen skill for a short window and replans. That transfers directly
if the latent space is replaced by an explicit, discrete library of contract-bearing skills with
continuous parameters (push-to-datum with offset, rotate by angle), and the MPC scores candidates
in sim. Contracts then come free: each candidate's precondition is checked before rollout, and
the sim rollout itself predicts success or failure. Deterministic and learned skills can both be
candidates because the composer only needs to execute them in sim. With an opaque z, the planner
still works, but the logs say "z = [0.3, -1.1, 0.4] scored best", which tells a debugging engineer
nothing about intent.

**Fit with pork-leg alignment.** Plausible for the orient and place decision, conditional on
three things. (a) A leg simulator that predicts slide, rotation and trotter drape well enough
that the ranking of candidates is right; absolute accuracy matters less than ranking (my
inference). (b) Pose and shape estimation fast enough to reset the sim to the real leg each
replan. (c) k rollouts of T steps finishing inside the replan period while the belt moves. The
paper reports whole-task wall-clock times of 1 to 2 minutes for simple tasks, so the sim budget
at conveyor speed is untested and would need its own measurement.

## 4. Composite motion learning with task control (Xu et al., SIGGRAPH 2023)

**Citation.** Pei Xu, Xiumin Shang, Victor Zordan, Ioannis Karamouzas. ACM TOG 42(4), SIGGRAPH
2023. [arXiv 2305.03286](https://arxiv.org/abs/2305.03286),
[DOI 10.1145/3592447](https://doi.org/10.1145/3592447),
[code](https://github.com/xupei0610/CompositeMotion) (PyTorch 1.12, IsaacGym Preview 4, per
README).

**Problem.** Physics-based character controllers imitate full-body clips, so every combination
(punch while running) needs its own reference motion. The paper trains one policy to imitate
different clips on different body parts at once while meeting goal rewards, and adds an
incremental scheme that reuses a trained policy for new composites (Sec. 1).

**Composition operator.** Two operators.

(a) Multi-discriminator imitation plus multi-critic balancing. The body is split into groups
(upper and lower body, or arms and the rest). Group i has an ensemble of N discriminators D^i
trained with a hinge loss and gradient penalty on that group's pose trajectory o^i_t (Eq. 2, 3).
Its imitation reward is r^{D_i}_t = (1/N) sum_n Clip(D^i_n(o^i_t), -1, 1) (Eq. 5). Each objective
k (imitation per group, plus each goal reward) gets its own critic and advantage, standardized
separately (Eq. 8), and the policy maximizes (Eq. 7):

    L_pi = sum_{k=1..K} E_t[ omega_k * Abar^k_t * log pi(a_t | s_t, g_t) ],  sum_k omega_k = 1

Abar^k is objective k's advantage minus its mean, divided by its standard deviation, so each
objective pushes the policy at a scale set by omega_k and not by its raw reward magnitude. Each
critic uses PopArt value normalization. This is CONCURRENT composition, fixed at training time.

(b) Incremental meta and cooperative policy (Eq. 10). A frozen pre-trained meta policy proposes
a_meta; the new policy outputs mu_t, sigma_t and a per-DoF weight vector w_t:

    pi(a_t | s_t, g_t, a_meta) = N(mu_t + w_t * Stop(a_meta), sigma_t^2)

Stop is a gradient stop; * is element-wise. w_t near 1 on a DoF means the meta policy's action
passes through there; near 0 means the new policy drives that DoF. This is HIERARCHICAL plus
CONCURRENT per DoF. Structurally it is a learned, state-dependent residual over a frozen base.

**Learned vs hand-designed.** Learned: policy, discriminators, critics, w_t. Hand-designed: body
split, reference clips per group, goal rewards, omega_k (0.5 shared across goal objectives in
most tasks, App. C), and some simplified mechanics (juggling balls attach to a hand when close
and detach every 20 frames; the racket is fixed to the hand). Every new composite needs training;
the authors state the system "can not create new composite activities without performing
additional training" (Sec. 7). The incremental scheme cuts that cost.

**Guarantees.** None formal. The standardization in Eq. 8 makes per-objective update scale equal
to omega_k by construction. The claim that output is "guaranteed to be physically valid" means it
runs in a physics simulator (Sec. 1).

**Evidence.** Simulated humanoid only, 15 links and 28 DoF, IsaacGym at 120 Hz, policy at 30 Hz,
one V100 (Sec. 6.1). No robot.

- Imitation error by dynamic time warping, metres (Table 1): Chest Open 0.11 ± 0.02 with Front
  Jumping Jack lower body 0.16 ± 0.03; Punch 0.17 ± 0.03 with Run 0.14 ± 0.01. Trial count for
  Table 1 is not stated.
- Training cost: about 1.5 h and 20M samples for pure composite imitation; 15 to 30 h and 2e8 to
  4e8 samples for goal-directed tasks from scratch; 30 min to 2 h with incremental learning
  (Sec. 6.1). Aiming+Run: 1.5 h and about 20M samples incremental versus about 20 more hours and
  about 300M more samples without (Sec. 6.6, Fig. 11, 10 trials).
- Ablation (Fig. 10, 10 trials): summing rewards instead of multi-objective updates lets one body
  group win; in Punch+Run the policy "almost gives up on learning how to run".
- Fig. 7 and 8: w_t distributions over 5,000 frames show lower-body DoFs taken from a locomotion
  meta policy and upper-body DoFs driven by the new policy.

**Limitations.** Stated (Sec. 7): no multi-phase behaviours because discriminators are not
phase-aware; body splits are assumed in advance; a left/right split imitating walk and jump fails
to an in-between motion (Fig. 12); juggling while running at about 3.5 m/s fails to juggle; the
system cannot tell whether two behaviours are compatible, a human decides. Visible: GAN rewards
make the objective non-stationary and hard to audit; no success-rate metric for goal tasks.

**Fit with Neil's architecture.** Eq. 10 is the useful part. Replace the learned meta policy with
a deterministic controller (conveyor tracking plus scripted approach) and train a cooperative
policy that owns only the DoFs where the base is not reliable. The logged w_t then states which
axes the learned part controls at each instant, which is inspectable in a way a latent code is
not. The paper does not test a classical base (my inference). The contract risk: the base
controller's success guarantee holds only on DoFs where w stays near 1, and nothing forces it to,
so the composite skill needs its own verify step, and a clamp on w per DoF is a design choice to
test. The multi-critic update in Eq. 7 and 8 is directly reusable for any learned skill with
several reward terms (track belt, rotate, do not drop) whose scales differ.

**Fit with pork-leg alignment.** Candidate sub-skill: "orient while tracking", with a
deterministic belt-tracking and transport base and a learned cooperative term on wrist
orientation and release timing so the trotter drapes over the edge. What would have to be true: a
sim in which leg drape is credible, a definition of success as a measurable pose (trotter overhang
past the belt edge), and w bounded or monitored on the tracking axes. The paper's evidence covers
character animation with attached objects, so transfer to an 11 kg deformable object is untested.

## How the four relate

**Additive mixture versus multiplicative product.** A mixture of experts (MCP Eq. 1) samples
from sum_i w_i * pi_i(a|s) with the w_i summing to 1. Sampling picks one expert with probability
w_i and draws its action, so at each timestep one primitive decides the whole action vector.
Averaging the means instead of sampling gives a single action, but every dimension is averaged
with the same weights, so an expert that is right about the wrist and wrong about the elbow pulls
both. The product in MCP Eq. 2 weights each primitive per dimension by w_i / var_i^j. Precision
is per dimension, so a primitive can dominate one joint and abstain on another in the same step.
That is why the product composes skills "in space" and the mixture only "in time" (Sec. 1).

Worked example, one action dimension, MCP weighted product (standard deviations s_i; MCP's
formula uses variance s_i^2):

    primitive 1: mu_1 = 0.0, s_1 = 0.1, w_1 = 1.0   ->  w_1 / s_1^2 = 1.0 / 0.01 = 100
    primitive 2: mu_2 = 1.0, s_2 = 0.2, w_2 = 0.5   ->  w_2 / s_2^2 = 0.5 / 0.04 = 12.5
    total weighted precision = 112.5
    composite mean = (100 * 0.0 + 12.5 * 1.0) / 112.5 = 0.111
    composite var  = 1 / 112.5 = 0.00889,  std = 0.0943

The composite sits close to the confident primitive, and its standard deviation (0.094) is below
both inputs (0.1 and 0.2). Precisions add, so with every weight at least 1 the product is at least
as sharp as its sharpest factor; a weight below 1 scales down that factor's precision. With w = (1, 1) the answer
is mean 0.200, std 0.089. The additive mixture with the same weights normalized to (2/3, 1/3) is
bimodal: mean 0.333, std 0.492, and a sample lands near 0.0 two times in three and near 1.0 once.

Two dimensions show the concurrency. Primitive A: dim 1 mean 0.0 std 0.05, dim 2 mean 5.0 std
1.0. Primitive B: dim 1 mean 2.0 std 1.0, dim 2 mean 1.0 std 0.05. Weights (1, 1). Composite:
dim 1 mean 0.005 std 0.050, dim 2 mean 1.010 std 0.050. A controls dim 1, B controls dim 2, in
the same timestep. A mixture returns either A (dim 2 at 5.0) or B (dim 1 at 2.0). All numbers
computed from Eq. 3 with Python on 2026-09-14.

Xu et al.'s Eq. 10 reaches per-DoF concurrency by a different route: an explicit per-DoF weight
on an additive residual over one frozen policy, without precision weighting. Their related-work
argument is the same as MCP's: a linear combination of full-body expert actions cannot keep one
expert's legs and another's arms (Sec. 5).

**What a skill embedding buys and costs.** Hausman et al. and He et al. put skills in a
continuous z. Bought: interpolation (spring-wall solved by a z between two trained clusters),
cheap sequencing (change z over time), a low-dimensional search space (3-D in Hausman et al.) for
RL or planning, and structured exploration (Hausman Fig. 4 right; MCP Fig. 6 for its weight
space). Cost: an arbitrary z has no name, no precondition and no success test. MCP's Table 1 also
shows a cost in capability: its latent space baseline overfit to pre-training behaviours and fell
to 0.115 on T-Rex dribble and 0.745 on holdout Ant, which the authors attribute to the decoder
restricting reachable actions (Sec. 5.2). MCP's own weights are a latent space too, only a more
structured one.

**MPC over latents turns composition into planning.** Hausman et al. and MCP learn the composer
with RL on each new task. He et al. replace the learned composer with search: sample candidate
latents, simulate each from the real state, execute the best for N steps, replan. New tasks then
cost a reward function and simulator time, no gradient steps. The price is a simulator in the
loop at run time whose ranking of candidates must match reality, and a planner that only
considers a constant z over each horizon.

**The tension with explicit contracts.** A contract says, in terms an operator can check, when a
skill may start, what it promises and how it fails. A latent skill can promise only "behaves like
the training distribution near this z". Three ways to live with that, ordered by how much I trust
them: (1) keep latent composition below the contract boundary, one contract around the whole
learned skill, with a deterministic verify step after it; (2) plan over explicit skills with sim
lookahead in the He et al. style and drop the latent space; (3) use the learned side-models as
runtime monitors (Hausman's q_psi, Xu's discriminators, MCP's gating weights) to flag
out-of-distribution execution. (3) is untested in any of these papers.

## Comparison

| Paper | Operator | Seq / conc / hier | Latent vs explicit | Composable without retraining? | Real robot? | Key limitation |
|---|---|---|---|---|---|---|
| MCP (Peng 2019) | Weighted product of Gaussian primitives, gate w(s,g) in [0,1] | Concurrent within hierarchical | Primitives and weights latent; goal explicit | No. Primitives frozen, new gating policy trained by RL per task | No. Simulated ant, biped, humanoid, T-Rex | No temporal abstraction; lost to scratch on holdout Ant (0.812 vs 0.951) |
| Hausman 2018 | Task-conditioned embedding p(z|t) into shared policy pi(a|s,z); new mapping z = f(x) | Hierarchical; sequencing and interpolation in z | z latent; training task ids explicit | No. f trained by RL per task; skills frozen | No. Simulated 7-joint arm, point mass | Curves only; shared observation space required |
| He 2018 | Random-shooting MPC over sampled z, simulator as model, replan every N steps | Sequential, hierarchical | z latent; reward and sim state explicit | Yes, zero-shot for new rewards | Yes, Sawyer: drawing and box pushing | n = 1 per task, no success rates; needs sim reset from real state |
| Xu 2023 | Multi-discriminator per body group plus multi-critic; meta policy with per-DoF weight residual | Concurrent; hierarchical in incremental mode | Body split and w_t explicit; policy features latent | No. Every composite trained; incremental 30 min to 2 h | No. Simulated humanoid, 28 DoF | Split and compatibility decided by hand; left/right split fails |

## What I am not sure about

- He et al.'s real-robot results are single runs described in prose. Whether 62 latents in 2
  minutes for a rectangle is typical or best of several attempts is not stated.
- How He et al. observed the real box pose to reset the simulator. Not in the text.
- Whether He et al. appeared anywhere archival beyond the NeurIPS 2018 Deep RL workshop. dblp
  blocked the lookup; the arXiv comments are the only venue evidence I have.
- Hausman et al.'s arm model and seed count. Neither is in the paper body or appendix I read.
- Whether a deterministic controller multiplied in as a fixed MCP primitive, or used as Xu et al.'s
  meta policy, keeps its accuracy on the axes it is meant to own. Plausible from the equations,
  untested in all four papers.
- Whether any of these composition schemes survives a deformable, 11 kg object on a moving belt.
  None of the four touches deformables or conveyors, and only He et al. touches hardware.
- Sim speed for He-style lookahead on a deformable leg at conveyor rates. The paper gives no
  per-step compute figure to extrapolate from.
- Xu et al. Table 1 row pairing is read from the extracted PDF layout (upper-body clip listed
  first in each pair); the Chest Open with Jumping Jack pairing matches Fig. 4 row 1, the rest I
  did not cross-check against the figure.
