---
title: "Skill Composition: Action-Based, Outcome-Based and Input-Based"
date: 2026-09-15
tags: [topic, skill-composition, skill-architecture, value-composition, successor-features, boolean-task-algebra, reward-machines, product-of-experts, emergence, pork-leg]
status: draft
source:
  - https://roboti.us/lab/papers/TodorovNIPS09.pdf
  - https://proceedings.mlr.press/v97/van-niekerk19a.html
  - https://arxiv.org/abs/1812.02216
  - https://arxiv.org/abs/2001.01394
  - https://www.raillab.org/publication/nangue-2022-generalisation/
  - https://arxiv.org/abs/1606.05312
  - https://arxiv.org/abs/1901.10964
  - https://doi.org/10.1073/pnas.1907370117
  - https://arxiv.org/abs/2106.13105
  - https://proceedings.mlr.press/v80/icarte18a.html
  - https://arxiv.org/abs/2303.02557
  - https://arxiv.org/abs/1802.05335
  - https://arxiv.org/abs/1609.07088
  - https://arxiv.org/abs/1511.02799
  - https://arxiv.org/abs/2302.11552
  - https://arxiv.org/abs/2403.05110
  - https://arxiv.org/abs/2307.03659
  - worked examples computed with Python 3.10.12 and numpy 1.21.5 (system interpreter, not the rll env) on 2026-09-14
---

# Skill Composition: Action-Based, Outcome-Based and Input-Based

What was read, and which version. In full: Todorov 2009 (NIPS author PDF); van Niekerk et al. 2019
(PMLR 97 PDF and supplement); Hunt et al. (arXiv 1812.02216 v2, 5 Jul 2019, main text and
Appendices A to C); Nangue Tasse, James, Rosman 2020 (arXiv 2001.01394 v2, main text and supplement
Sections 1 to 7.1); Nangue Tasse et al. 2022 world value functions (arXiv 2206.11940 v1, 6 pages);
Barreto et al. 2017 (arXiv 1606.05312 v2, main text and supplement A, B.1); Barreto et al. 2018
(arXiv 1901.10964 v1, main text and supplement A); Barreto et al. 2019 option keyboard (arXiv
2106.13105 v1, main text and supplement A to C.1); Toro Icarte et al. 2018 (PMLR 80 PDF, main text);
Wu and Goodman 2018 (arXiv 1802.05335 v3, main text); Devin et al. 2017 (arXiv 1609.07088 v1);
Andreas et al. 2016 (arXiv 1511.02799 v4); Brooks 1986 (IEEE J. Robotics and Automation scan with a
text layer, pp. 14 to 23); Arkin 1987 (ICRA 1987 paper, pp. 264 to 271; the IJRR 1989 journal version
was not read); Koren and Borenstein 1991 (ICRA 1991 paper, CMU mirror). Main text only, appendices
not read: Nangue Tasse et al. ICLR 2022 (RAIL lab PDF); Barreto et al. PNAS 2020 (PMC full text, SI
appendix not read); Adamczyk et al. UAI 2023 (arXiv 2303.02557 v2); Du et al. 2023 (arXiv 2302.11552
v6, Sections 1 to 6); Gao et al. 2024 (arXiv 2403.05110 v2, Sections I to VI); Xie et al. 2023 (arXiv
2307.03659 v1). Abstract and introduction only: Terrés-Caballero and van Hoof 2026 (arXiv 2606.04053
v1). Not read: Khatib 1986 (IJRR, paywalled), Haarnoja et al. 2018 beyond what the
[energy products note](../papers/policy-composition-energy-products.md) records (its numbers were
re-checked against the arXiv v1 text on 2026-09-14, as were the MCP and CEP numbers quoted below).

This note builds on three paper notes and does not repeat their derivations:
[energy products](../papers/policy-composition-energy-products.md) (soft-Q sums, CEP, HiPBI, PoENS),
[latent skills](../papers/policy-composition-latent-skills.md) (MCP, skill embeddings, latent MPC),
[primitives, nullspace controllers, diffusion](../papers/policy-composition-primitives-controllers-diffusion.md)
(Morrow and Khosla, Sharma et al., PoCo), and the score-composition section of
[generative models](generative-models-vae-and-diffusion.md).

## What it is

Objects first, because the three types differ in which object the composition operator touches.

```text
skill k        = (O_k, c_k, pi_k, spec_k)
  O_k : S -> X_k                 what the skill observes (its input map)
  c_k                            what it is conditioned on (goal, language, preference vector w)
  pi_k(a | O_k(s), c_k)          a distribution over actions (or action chunks) given its input
  spec_k                         what it is for: reward r_k, goal set G_k in S, or success predicate
outcome of k   = P_k(tau)        distribution over trajectories when pi_k runs in dynamics p,
                                 scored by spec_k (return J_k, or P(terminal state in G_k))
value summary  = V_k             any stored object that summarises pi_k's future under spec_k:
                                 desirability z_k, Q_k, extended Q-bar_k, successor features psi_k
```

A skill is a probability distribution in two senses: over actions given state (pi_k), and over
trajectories and outcomes (P_k). Composing skills is an operation on one of those distributions, or
on the inputs that feed them. The three definitions below say which.

**Action-based composition.** The composed policy is a fixed map F of the constituents' action
distributions, evaluated at the current state only:

```text
pi_C(. | s) = F( pi_1(. | x_1, c_1), ..., pi_n(. | x_n, c_n) ; s )
```

F acts on the action distributions or on their parameters, energies, scores or commands: mixture,
product (sum of log-probabilities, energies, soft Q-functions or diffusion scores), vector sum,
nullspace projection, priority gating. Nothing in F refers to where the closed loop ends up. The
composed outcome P_C is determined jointly by F, the constituents and the dynamics, and it is in
general not a function of P_1, ..., P_n. Guarantees, where they exist, are statements about the
action at one step.

**Outcome-based composition.** The composed skill is defined by an operator G on the constituents'
specifications, and pi_C is (approximately) optimal for the result, computed from stored value
summaries instead of from the constituents' actions:

```text
spec_C = G( spec_1, ..., spec_n )        e.g. r_C = max_k r_k (OR), min_k r_k (AND),
                                          r_U + r_empty - r (NOT), phi^T w (weighted), reward machine
pi_C(s) in argmax_a  Phi( V_1, ..., V_n )(s, a)
guarantee:  J(pi_C; spec_C) = J*(spec_C)            exact, under stated assumptions
       or   J(pi_C; spec_C) >= J*(spec_C) - bound   with the bound written out
```

pi_C(s) need not equal, or be any combination of, pi_k(s). The designer states what must be true at
the end; the theory says when the stored values are enough to act on that statement without new
learning.

**Input-based composition.** The composed skill is one policy whose input is built by an operator H
over what several sources observe or condition on:

```text
pi_C(a | s) = pi( a | H( O_1(s), ..., O_m(s), c_1, ..., c_j ) )
```

H is posterior fusion of modality-specific encoders, wiring of perception or task modules into a
policy module, attention over inputs, or a composed goal or task vector. The constituents are input
channels and perception modules, not policies. Guarantees, where they exist, are statements about
the fused belief or embedding (for example an exact posterior), never directly about actions or
outcomes: the downstream policy still has to be competent on the composed input.

| Type | What is combined | Operator | What is guaranteed | Example |
|---|---|---|---|---|
| Action-based | Constituents' action distributions or commands at the current state | Mixture; product, that is sum of energies, log-probs, soft Q or scores; vector sum; nullspace projection; priority gate | Only a property of the instantaneous action: product mode is the precision-weighted mean ([MCP Eq. 3](https://arxiv.org/abs/1905.09808)); nullspace keeps the primary task rate to first order ([Sharma et al.](../papers/policy-composition-primitives-controllers-diffusion.md)). Nothing about the terminal state | CEP reaching through clutter; subsumption; Sawyer stack-while-avoid |
| Outcome-based | Task specifications (rewards, goal sets, event orders) plus value summaries z, Q, Q-bar, psi | Weighted log-sum-exp of desirabilities; max for OR; min over extended values for AND; Q-bar_U + Q-bar_empty - Q-bar for NOT; psi^T w then max over policies; reward machine product MDP | Exact optimality (Todorov 2009; van Niekerk 2019; Nangue Tasse 2020; DC given its correction term), or a lower bound (GPI: at least the best stored policy minus 2 epsilon/(1 - gamma)) | Boolean task algebra XOR from two base tasks; SF and GPI policy that avoids objects no constituent was trained to avoid |
| Input-based | What skills observe or are conditioned on: encoders, goal or task vectors, attention maps, modules | Product of Gaussian posterior experts; f_robot(g_task(o_T), o_R); combine[and] over attentions; composed w | Exact Bayesian fusion only if modalities are conditionally independent given the latent and each posterior lies in its variational family (Wu and Goodman Eq. 3 to 4); otherwise none | MVAE; modular task and robot networks; neural module networks on SHAPES |

Where the types overlap, precisely:

- Summing soft Q-functions is both. As an operator on policies it is a product (action-based). As
  a claim about the averaged reward it is outcome-based, and the difference between the two is the
  fixed point C* in Haarnoja et al.'s bound, which Hunt et al. show can be learned and subtracted
  exactly. C* is the price of implementing an outcome specification with an action operator.
- Todorov's exact outcome composition is realised as an action mixture, but with state-dependent
  weights m_k(x) proportional to w_k z_k(x) that require each component's desirability. A mixture
  with fixed weights is only action-based and not optimal.
- Successor features with GPI, and the option keyboard, are outcome-based, and their runtime
  interface is input-based: the preference vector w is the conditioning input. When w itself is
  chosen per state by a learned policy (Barreto et al. 2020, "preferences as actions") a
  hierarchical layer sits on top.
- MCP is an action-based product whose weights come from a gate that is the only part that sees the
  goal ([latent skills note](../papers/policy-composition-latent-skills.md)); PoCo's domain
  composition sums scores of policies with different observation spaces. Both are action-based
  composition of skills with different inputs.
- Reward machines specify outcomes in time (which events, in which order). The three operators above
  are concurrent; sequencing is a separate axis, and a reward machine is the outcome-based way to
  state it.

## Why it matters in the field

The pork-leg station aligns an 11 kg, 720 mm bone-in leg on a moving belt so the trotter hangs over
the edge ([primitives note](../papers/policy-composition-primitives-controllers-diffusion.md)). Its
skill list is observe, intercept, grasp, orient, release, verify. The skill library for the cell gives
each skill a typed contract (inputs, preconditions, outputs, success, failure, recovery) and composes
skills as a task graph, built in `src/skill_library/`
(overnight plan, task 4 (`plan/overnight-2026-09-14.md`)). Each composition type has a
natural home in that list, and each carries a different kind of promise.

- Sequencing observe, intercept, grasp, orient, release, verify is temporal composition. Its
  specification is an event order, which a reward machine states formally (Icarte et al. 2018) and
  the task graph executes.
- Intercept is concurrent: track the belt, stay clear of the cutter housing, respect joint limits.
  That requirement is about the action at every instant, so it is action-based (CEP-style energies,
  nullspace priority), and nothing guarantees the tool reaches the leg; the contract's failure signal
  has to detect stalls.
- Orient has an outcome as its success condition: hock on the blade plane within a yaw tolerance and
  trotter overhang past the belt edge. "Orient AND keep the trotter over the edge" is a conjunction of
  goal sets. The exact conjunction theorem needs deterministic dynamics and a shared finite terminal
  set; a wet leg sliding on a belt has neither, so only bounds apply (Nangue Tasse et al. 2022,
  Theorem 1(i)).
- Observe and verify are input-based: depth keypoints, the belt encoder and a second camera fused
  into one pose estimate ([meat cell architecture](meat-cell-architecture.md),
  [conveyor tracking](conveyor-tracking-and-visual-servoing.md)).

At plant scale the customer's line is staffed by people doing jobs such as hand-placing legs onto
the belt ([pork processing line](pork-processing-line.md)). A skill tree in which each human job is a
composition of skills raises one question per new job: can it be run from stored skills without
retraining? The outcome-based theorems answer yes only under their assumptions; for action-based
and input-based composites the answer comes from evaluating the new combination, and the robot
evidence (Gao et al. 2024, below) says some combinations compose and some do not.

## Methods

### Action-based composition

```text
mixture:        pi_C(a|s) = sum_k w_k(s) pi_k(a|s),   sum_k w_k = 1
product:        pi_C(a|s) proportional to prod_k pi_k(a|s)^beta_k
                <=> log pi_C = sum_k beta_k log pi_k + const(s)
                    (sum of energies, of soft Q/alpha, of diffusion scores)
vector sum:     v(s) = sum_k v_k(s)                      motor schemas, potential fields
nullspace:      a = a_1 + (I - J_1^+ J_1) a_2            strict first-order priority
priority gate:  a = a_{k*(s)},  k*(s) = highest layer whose output is active   subsumption
```

The three linked paper notes derive the product, the nullspace projector and score sums, with
worked examples. The additions here are the behaviour-based roots and what each operator promises.

Subsumption ([Brooks 1986](https://doi.org/10.1109/JRA.1986.1087032)). Layers of asynchronous finite
state machines; a higher layer suppresses a lower module's input (replacing it for a fixed time) or
inhibits its output, while the lower layers keep running. Level 0 (avoid) sums repulsive forces from
12 sonar returns; level 1 (wander) adds a random heading every 10 s or so, and its Avoid module
combines that heading with the repulsive force. The promise is architectural: a working lower layer
is never modified. There is no claim about which goal is reached.

Motor schemas ([Arkin 1987](https://doi.org/10.1109/ROBOT.1987.1088037)). Each schema instance
outputs a velocity vector; a move-robot schema adds them and clips the result. Avoid-static-obstacle
uses a linear field, zero beyond the sphere of influence S, (S - d)/(S - R) times a gain inside it,
infinite inside the obstacle radius R, and an obstacle produces no field until its perceptual schema
is confident. Arkin states the known failure himself: "Potential fields can have problems with dead
spots or plateaus where the robot can become stranded" (Sec. 3.1). Evidence is simulation only (VAX
750, 64 by 64 grid).

What action-based operators guarantee, from the linked notes: a product of Gaussians has the
precision-weighted mean (MCP Eq. 3); a sum of Q-functions is optimal for the summed reward at horizon
1 and degrades with horizon (CEP appendix, [energy products note](../papers/policy-composition-energy-products.md));
nullspace projection keeps J_1 a equal to the primary rate to first order. Robot evidence, also from
those notes: Sawyer stack-while-avoid composed from two soft-Q policies succeeded 100 % (stack-only
30 %), 10 trials; CEP on RSS 2021 simulated reaching reached 89 % in Cage I and 46 % in Cage II; PoCo's
composed multitask policy scored 60 % against 65 % for single-task policies, 10 trials per tool.

### Outcome-based composition

#### Linearly solvable control (Todorov 2009)

```text
problem:   x' ~ u(.|x),  cost rate q(x) + KL( u(.|x) || p(.|x) ),  final cost f(x) on boundary B
           desirability z(x) = exp(-v(x)),  G[z](x) = E_{x'~p(.|x)} z(x')
solution:  u*(x'|x) = p(x'|x) z(x') / G[z](x)          exp(q(x)) z(x) = G[z](x)   (Eq. 1, linear)
compose:   K components share p, q, interior I and boundary B, differ only in f_k
           f(x) = -log sum_k w_k exp(-f_k(x))  on B    =>  z = sum_k w_k z_k  everywhere  (Eqs. 4-5)
           u*(.|x) = sum_k m_k(x) u*_k(.|x),   m_k(x) = w_k z_k(x) / sum_s w_s z_s(x)       (Eqs. 7-8)
continuous time: dx = a(x)dt + B(x)(u dt + sigma dw), cost q + |u|^2/(2 sigma^2);
           u*(x) = sum_k m_k(x) u*_k(x) with the same weights (Eq. 9)
```

Exact, not a bound. Assumptions: same passive dynamics, same state cost, same interior and boundary
sets, KL (or control-quadratic) control cost, first-exit or finite-horizon formulation. The composite
final cost is a soft minimum of the component costs, which is an OR over targets. For linear dynamics
with Gaussian noise the components are LQG controllers and the composite, with a non-quadratic final
cost, is solved in closed form (Sec. 4). Primitives from an SVD of the Green's function are not
positive everywhere, so the composite desirability can go non-positive and -log z is undefined near
the boundary (Fig. 2B). Evidence: a 2-link arm model with about 20 million discrete states solved in
about 30 iterations and under 2 min of CPU; mixing the controllers for two targets gave a switching
controller that picks a target by start position and switches online after a perturbation (Fig. 3C,
qualitative).

#### OR in entropy-regularised and standard RL (van Niekerk et al. 2019)

```text
setting:   total-reward MDPs with absorbing set G, finite A, KL-regularised with temperature tau,
           DETERMINISTIC transitions s' = f(s,a), tasks differ only in rewards on G
Thm 2:     if r(s,a) = tau log || exp(r_vec(s,a)/tau) ||_w  for s in G,  ||w||_1 = 1
           then Q*_tau(s,a) = tau log || exp(Q*_tau,vec(s,a)/tau) ||_w  for all s        (exact)
Cor. 1:    tau -> 0 and r = max_k r_k  =>  max_k Q*_k = Q*                              (exact)
Lemma 3:   AND by averaging (Haarnoja 2018): Q_ave >= Q*_ave >= Q_ave - C*               (bound)
```

The proof exponentiates Q and uses linearity of the backup operator, which needs a deterministic
next state. The paper gives a counterexample with stochastic dynamics, recomputed in worked example
2: max-composition returns 0.9 where the optimum is 1.0. Evidence: pixel-input video game, one DQN per
base task trained 1.5 M steps; PurpleOrBlue composed zero-shot with multimodal value function (Fig.
2, box plots over 50k episodes); weighted composition swept in steps of 0.05, 80 runs of 100 episodes
per weight (Fig. 3); AND by averaging leaves local optima in the value function (Fig. 4).

#### Convex reward combinations: bound, exact correction, max-ent GPI (Haarnoja 2018; Hunt et al. 2019)

```text
target:    r_b = b r_i + (1-b) r_j,  both constituents alpha-max-ent optimal, same dynamics
CO:        Q_CO = b Q_i + (1-b) Q_j,   pi_CO proportional to pi_i^b pi_j^(1-b)          (upper bound on Q*_b)
DC:        Q*_b = b Q_i + (1-b) Q_j - C_b,                                             (Thm 3.2, exact)
           C_b(s,a) = -alpha gamma E_{s'} log INT pi_i(a'|s')^b pi_j(a'|s')^(1-b) exp(-C_b(s',a')/alpha) da'
max-ent GPI: pi proportional to exp( max_i Q^i(s,a) / alpha )  =>  Q^pi >= max_i Q^i    (Thm 3.1, lower bound)
```

DC is exact for any convex combination once C_b is known, and the N-policy version is in Appendix A.3;
the cost is learning C_b(s, a, b) for each pair by TD, which the authors say gets harder with more
policies, so GPI is more practical for many. The first iterate of C_b is gamma alpha (1 - b) times the
Rényi divergence of order b between the two policies. Hunt et al. show the two cheap operators fail in
complementary ways on an 8 by 8 tabular world (Fig. 1): CO fails when the subtasks are incompatible
(left versus right: it will not commit), GPI fails to exploit compatibility (left and up), and both
fail on the "tricky" task where the optimum resembles neither constituent. DC recovers the optimum
there. Continuous evidence: 2-D point mass (5 seeds), 5-DoF planar manipulator, 3-DoF jumping ball and
8-DoF ant, all simulated; DC goes to the jointly rewarded target where CO and GPI mostly go to one
constituent's target (box plots only). The ICML version is titled "Entropic Policy Composition with
Generalized Policy Improvement and Divergence Correction" (cited so in the option keyboard paper).

#### Boolean task algebra and world value functions (Nangue Tasse, James, Rosman 2020, 2022)

```text
Assumption 1:  shared S, A, DETERMINISTIC dynamics; rewards differ only on the absorbing set G
Assumption 2:  terminal rewards take only two values {r_empty, r_U}  (needed for the algebra, not for Thm 3)
tasks:         r_{A or B} = max(r_A, r_B),  r_{A and B} = min(r_A, r_B),  r_{not A} = r_U + r_empty - r_A
extended reward:  r-bar(s,g,a) = r-bar_MIN  if g != s and s in G,  else r(s,a)
                  r-bar_MIN <= min( r_MIN, (r_MIN - r_MAX) D ),  D = MDP diameter
extended value:   Q-bar(s,g,a) = r-bar(s,g,a) + INT V-bar(s',g) p(ds'|s,a)
recover:          Q*(s,a) = max_g Q-bar*(s,g,a)                                      (Lemma 1)
Thm 3 (exact):    Q-bar*_{A or B} = max, Q-bar*_{A and B} = min, Q-bar*_{not A} = Q-bar*_U + Q-bar*_empty - Q-bar*_A
act:              pi(s) in argmax_a max_g Q-bar(s,g,a)
```

Why regular value functions cannot do AND: each encodes the value of the nearest desired goal only,
so for states whose nearest goals differ between tasks there is no information about the shared goal
(Sec. 3.2). Worked example 1 shows the consequence. Evidence: Four Rooms, extended value functions
cost a constant factor more samples than regular ones (100 runs, Fig. 3a); with 40 goals, 7 base
tasks suffice against 40 for disjunction-only composition (Fig. 3c); pixel video game, OR, AND and XOR
of "blue" and "square" at the optimal return (Fig. 6, 1000 episodes, values in the plot). The
supplement relaxes the assumptions in the deterministic Four Rooms: dense rewards and non-shared
absorbing sets gave policies "identical or very close to optimal" for most of the 16 tasks (100000
episodes). The stochastic part of that supplement was not read.

The ICLR 2022 paper extends the algebra to discounted, stochastic tasks and states what survives:

```text
Thm 1 (i)  any dynamics:   ||Q* - Q^pi||_inf <= 2/(1-gamma) * ( (1[T != T_F] + 1[r not in {r_g}]) r_Delta + eps )
Thm 1 (ii) deterministic:  ||Q* - Q_F||_inf  <= 1[T != T_F] r_Delta + eps
Thm 2:     ceil(log |G|) <= lim N_t <= |G|   tasks learned to generalise over any task distribution
```

T is the true binary goal vector of the new task, T_F the vector reconstructed by a sum-of-products
Boolean expression over learned tasks, r_Delta = r_MAX - r_MIN. In deterministic dynamics, a task
expressible in the algebra is solved to the base tasks' epsilon; in stochastic dynamics it is a
2/(1 - gamma) bound. Evidence: MiniGrid PickUpObj with 15 goals, 4 base tasks spanning 32768 tasks,
4 runs; stochastic Four Rooms with 40 goals (about 10^12 tasks), 25 runs. Stated limitation: binary
goal rewards only.

World value functions (arXiv 2206.11940) drop the assumption that tasks share goals set by the
environment: the goal space is every state where the agent saw a terminal transition, and Theorem 4
recovers the optimal policy of any new goal-reaching task from one learned WVF plus the new task's
terminal rewards, in deterministic dynamics. The WVF also encodes the transition model, which the
authors use for Dyna-style planning (Four Rooms, 25 seeds). A 2026 technical report (Terrés-Caballero
and van Hoof, abstract and introduction read) proves that in deterministic MDPs every optimal extended
Q is determined by the universal and empty tasks, which makes the logarithmic base-task set
redundant, and gives a stochastic counterexample in which optimal composition may need exponentially
many policies in the number of goals.

#### Successor features, GPI and the option keyboard (Barreto et al. 2017, 2018, 2019, 2020)

```text
tasks:     r_w(s,a,s') = phi(s,a,s')^T w,   phi in R^d fixed, shared dynamics and gamma
SF:        psi^pi(s,a) = E^pi[ sum_i gamma^i phi_{t+i+1} | s, a ]     =>  Q_w^pi = psi^pi(s,a)^T w     (exact GPE)
GPI:       pi(s) in argmax_a max_i Q~^{pi_i}(s,a),  |Q - Q~| <= eps
           =>  Q^pi(s,a) >= max_i Q^{pi_i}(s,a) - 2 eps/(1-gamma)                              (2017 Thm 1)
           Q*_i - Q^pi_i <= 2/(1-gamma) ( phi_max min_j ||w_i - w_j|| + eps )                  (2017 Thm 2)
any reward r:  ||Q* - Q^pi||_inf <= 2/(1-gamma) ( ||r - r_i||_inf + min_j ||r_i - r_j||_inf + eps ) (2018 Prop. 1)
option keyboard: extended cumulants e over histories with a termination action tau;
           combined option  w~_e(h) in argmax_{a in A+} max_j sum_i w_i Q_{e_i}^{w_{e_j}}(h,a)
```

Nothing here is exact for the composed task. The guarantee is improvement over every stored policy,
plus a bound that shrinks as the target w approaches a stored task. Stochastic dynamics are allowed.
The action GPI picks in a state can differ from every constituent's action, so composed behaviour is
not an alternation of skills (PNAS 2020; option keyboard Sec. 3.2). Evidence, all simulated:

- Four-room continuous navigation, 250 reward-changing tasks, 30 runs: SFQL improves average return
  over probabilistic policy reuse by more than 100 %, which itself improves over Q-learning by about
  100 % (2017, Fig. 2). Two-joint reacher, trained on 4 targets and tested on 12, 30 runs (Fig. 3).
- 3-D DeepMind Lab from first-person pixels, 10 runs: near-instant transfer to test tasks including
  negative rewards never seen in the base tasks (2018, Fig. 3). Linearly dependent base tasks degrade
  transfer only mildly (Fig. 4). The authors note that spanning the reward space does not span
  behaviour: with all-negative base rewards the stored policies stand still and GPI cannot recover
  a positive task.
- 10 by 10 grid with two object types, 100 runs: composing policies for w = [1, 0] and [0, 1] into
  w = [1, -1] reached more than 70 % of Q-learning's performance after 10^6 transitions, and matched
  Q-learning at about 6 x 10^4 transitions, with no learning on the task; the composed policy avoids
  type-2 objects although neither constituent was trained to avoid anything. Inferring w by
  regression from random-policy data took about 800 transitions against about 60000 for Q-learning
  (PNAS 2020, Figs. 5 and 6).
- Option keyboard: foraging world with 2 nutrients, 10 runs; 8-DoF simulated quadruped trained on
  3 directional options (0, 120, 240 degrees) and driven in any direction by combined options, 10
  runs; GPE and GPI beat additive entropy-regularised value composition on the same keyboard (Fig. 4,
  curves only).

#### General reward transforms: double-sided bounds (Adamczyk et al. 2023)

For composite rewards F(r_1, ..., r_M) with F convex and sublinear (or concave and superlinear) in each
argument, in stochastic dynamics with rewards anywhere, the optimal composite Q is bracketed by F
applied to the constituents' Q plus or minus the optimal value C of an auxiliary task with reward
f(r) + gamma E V_f(s') - f(Q). One side needs no training:

```text
standard RL:  OR   Q~ >= max_k Q_k      AND  Q~ <= min_k Q_k
              NOT  Q~ >= -Q             conical sum  Q~ <= sum_k alpha_k Q_k
regret of the zero-shot policy pi_f: Q~ - Q~^{pi_f} <= D, D the value of pi_f on an auxiliary task
```

With deterministic dynamics the convexity condition is not needed. Evidence: deterministic 6 by 6
gridworld, DQN, 50 trials: clipping the composite Q to the bound during training sped learning, and
clipping only at test time gave high returns while bound violations stayed high (Figs. 1 and 2).

#### Reward machines as outcome specifications (Toro Icarte et al. 2018)

```text
RM = < U, u0, delta_u : U x 2^P -> U, delta_r : U x U -> [S x A x S -> R] >,  labelling L : S -> 2^P
MDP with RM  ==  MDP on S x U with p'((s',u')|(s,u),a) = p(s'|s,a) if u' = delta_u(u, L(s'))   (Obs. 1)
expressible: any Markov reward (one state); any history-dependent reward that distinguishes
             histories by regular expressions over P; not counting beyond a regular language
QRM:         one q~_u per RM state; after each real step update every u off-policy:
             q~_u(s,a) <- r + gamma max_a' q~_{delta_u(u, L(s'))}(s',a')                        (Alg. 1)
```

Tabular QRM converges to an optimal policy (Theorem 4.1), where options and hierarchical RL over the
same events can converge to suboptimal policies because the hierarchy prunes the policy space.
Evidence: office gridworld, 4 tasks, 30 trials; Minecraft-like world, 10 tasks on 10 maps with 3 trials
each (hierarchical baselines converge to suboptimal returns, Fig. 3); continuous water world, 10 tasks
on 10 maps with Double DQN (Fig. 4, curves only). A reward machine composes outcomes in time; it is
the formal counterpart of the cell's task graph.

#### Exact versus bounded, in one place

| Operation | Exact when | Otherwise |
|---|---|---|
| Soft-OR of desirabilities (Todorov) | Linearly solvable control: shared passive dynamics, state cost and boundary; KL control cost; components differ only in final cost | Not defined outside the class |
| Weighted soft-OR / max of Q (van Niekerk) | Deterministic dynamics, rewards differ only on a shared absorbing set, total reward | Stochastic counterexample: 0.9 against 1.0 (worked example 2); GPI lower bound still holds |
| Average of soft Q for averaged reward (Haarnoja) | Never in general | Q_ave >= Q* >= Q_ave - C*, C* a discounted Rényi-divergence fixed point, not computable without the dynamics |
| Divergence correction (Hunt) | Given the learned C_b, any convex combination, any dynamics | Error of the learned C_b |
| min / max / negation of extended Q (Nangue Tasse) | Deterministic, shared absorbing set, binary terminal rewards for the algebra | Stochastic, discounted: 2/(1 - gamma) bound (ICLR 2022 Thm 1 i) |
| SF and GPI, option keyboard (Barreto) | Never exact for the composite | >= best stored policy - 2 eps/(1 - gamma); distance-to-nearest-task bound |
| OR, AND, NOT, conical sums for general rewards (Adamczyk) | Never exact | One-sided zero-shot bound; double-sided with a learned C |
| QRM (Icarte) | Tabular, converges to optimal for the RM task | DQRM: no guarantee |

### Input-based composition

#### Product of experts over sensor modalities (Wu and Goodman 2018)

```text
generative model:  p(x_1..x_N, z) = p(z) prod_i p(x_i | z)     modalities conditionally independent given z
posterior:         p(z | x_1..x_N)  proportional to  prod_i p(z | x_i) / prod_{i=1}^{N-1} p(z)     (Eq. 3)
MVAE:              q(z | X) proportional to p(z) prod_{x_i in X} q~(z | x_i)     any subset X        (Eq. 4)
Gaussian experts:  mu = (sum_i mu_i T_i)(sum_i T_i)^-1,  V = (sum_i T_i)^-1,  T_i = V_i^-1
training:          ELBO(all) + sum_i ELBO(x_i) + k random-subset ELBOs per minibatch               (Eq. 5)
```

Exact only when the conditional independence holds and each unimodal posterior lies in its
variational family (footnote 1); otherwise the product is a tractable approximation. A missing
modality is handled by dropping its expert, which is the property a sensor dropout needs. Why the
subsampled objective matters: a product of Gaussians does not identify its factors, so training only
on complete data never trains the single-modality encoders (Sec. 2.2). Evidence: on FashionMNIST the
MVAE matched a fully supervised classifier with about two orders of magnitude fewer paired examples
(Fig. 3); English-Vietnamese translation with 1 % aligned pairs (1330) reached test log-likelihood
-483.23 against -478.12 with all pairs, 3 runs (Table 4). Image and language benchmarks, no robot.

#### Modular task and robot networks (Devin et al. 2017)

```text
observation split:  o = (o_T task-specific, o_R robot-specific)
policy mean:        phi_{rk}(o) = f_r( g_k(o_T), o_R )          f_r robot module, g_k task module  (Eq. 1)
cost assumption:    c(x, u) = c_R(x_R, u) + c_T(x_T)
unseen world:       compose f_{r_test} and g_{k_test} trained in different worlds; no joint training
```

The composition operator is wiring: the task module's latent output becomes part of the robot
module's input. Nothing forces the interface to mean the same thing across modules except training
on many robot-task pairs with a narrow bottleneck and dropout (Sec. III-D). Evidence, MuJoCo with
guided policy search: a 4-link arm reaching a colour-specified block, with that pair held out of 12,
ended 0.08 to 0.28 from the block over 4 test positions, against 1.16 to 1.35 for a random network and
1.65 to 2.41 with the wrong task module (Table I); a held-out 4-link block push ended 0.19 to 0.48 from
the goal against 0.94 to 1.79 (Table II). On the held-out 3-link horizontal drawer pull, zero-shot
composition failed and served only as an initialisation that learned faster than training from
scratch with reward shaping (Fig. 7).

#### Attention composition in neural module networks (Andreas et al. 2016)

```text
modules:   attend[c]: image -> attention      re-attend[c]: attention -> attention
           combine[c]: attention x attention -> attention      classify[c], measure[c] -> label
layout:    parser -> e.g. measure[is](combine[and](attend[red], re-attend[above](attend[circle])))
```

The composed input of each module is another module's attention map; the layout comes from a
dependency parser. The names are notation only: combine[and] is not fixed to compute an intersection,
it learns whatever the end-to-end loss rewards (Sec. 5). Evidence: SHAPES, 244 questions on 15616
images, NMN 90.6 % against 65.3 % for VIS+LSTM and 63.0 % majority; trained without any 6-module
question it still scored 89.7 % on them (Table 2). VQA test 55.1 % against 54.1 % (Table 3). Most parse
errors were on complex questions (hand inspection of 50 parses).

#### Conditioning on a composed goal

In SF and GPI the composed task vector w is the conditioning input of a fixed set of policies; in the
ICLR 2022 algebra a sum-of-products Boolean expression over learned binary task vectors picks which
extended values to combine; in MCP only the gating network sees the goal. The input-level operator is
cheap. Whether the downstream skill is competent on the composed input is a separate question,
answered by the outcome theorems in the first two cases and by nothing in the third.

## Worked examples

All numbers below were computed with the script at the end of this section (Python 3.10.12, numpy
1.21.5, 2026-09-14), deterministic, no random seeds.

### 1. Corridor: action-based averaging versus outcome-based conjunction

States 0 to 8 on a line; goal states {0, 3, 4}; actions left, right, done. Done at a goal ends the
episode with +2 if the goal is desired and -2 otherwise; every other step costs -0.1. Start at 5.
Task A desires {0, 3}, task B desires {0, 4}, so A AND B desires {0}, A OR B desires {0, 3, 4} and
A XOR B desires {3, 4}. This is Assumption 1 and 2 of Nangue Tasse et al.: deterministic, shared
absorbing set, two terminal reward values.

| Quantity at state 5 | left | right | done |
|---|---|---|---|
| Q_A (nearest desired goal 3) | 1.80 | 1.60 | 1.70 |
| Q_B (nearest desired goal 4) | 1.90 | 1.70 | 1.80 |
| Q_avg = (Q_A + Q_B)/2, action-based | 1.85 | 1.65 | 1.75 |
| Q* for A AND B | 1.50 | 1.30 | 1.40 |
| min over extended values, then max over goals, outcome-based | 1.50 | 1.30 | 1.40 |

Acting greedily on Q_avg (the same argmax as the product of the two Boltzmann policies): at state 4 it
prefers left (1.85 against 1.75, done is 0.00 because goal 4 is undesired for A); at state 3 it prefers
right (1.85 against 1.75). The policy oscillates 5, 4, 3, 4, 3, ... with a margin of 0.10 at every
step, never terminates, and returns -4.0 over 40 steps. The outcome-based composite equals Q* for the
conjunction at every state and action, walks 5, 4, 3, 2, 1, 0, done, and returns 1.5. The same
construction reproduces Q* for OR (max of the regular Q-functions) and for XOR (via negation
Q-bar_U + Q-bar_empty - Q-bar), which walks 5, 4, done for a return of 1.9.

Haarnoja's own target, the averaged reward, is a different task from AND: its optimum at state 5 is
[1.50, 1.30, 1.40] here (goals 3 and 4 are worth 0 on average, goal 0 is worth 2), and Q_avg exceeds it
by 0.35 for every action. That is the direction of Haarnoja's inequality Q_ave >= Q*, although the
example is undiscounted standard RL, not the max-ent setting the bound is proved in.

The continuous analogue is two equal-variance Gaussian reach policies with gain 1 toward -2 and +3.
Their product has the average velocity as its mean, and integrating from 0 with step 0.1 settles at
x = 0.5, a point that is neither goal.

### 2. Stochastic outcomes break max-composition

The counterexample from van Niekerk et al. (Sec. 4.1): one start state, actions a, b, c, and
terminal outcomes Red, Purple, Blue with probabilities a = (0.1, 0.8, 0.1), b = (0.1, 0.1, 0.8),
c = (0, 0.5, 0.5). Task A rewards Purple, task B rewards Blue.

| Action | Q_A | Q_B | max(Q_A, Q_B) | (Q_A + Q_B)/2 | true Q for A OR B |
|---|---|---|---|---|---|
| a | 0.8 | 0.1 | 0.8 | 0.45 | 0.9 |
| b | 0.1 | 0.8 | 0.8 | 0.45 | 0.9 |
| c | 0.5 | 0.5 | 0.5 | 0.50 | 1.0 |

Max-composition picks a (or b) and gets 0.9; the optimum is c at 1.0. The GPI lower bound still
holds (0.9 >= 0.8). Averaging picks c here, which is a property of these numbers, not a guarantee:
in example 1 averaging was the operator that failed. Neither operator's answer is justified once the
exactness assumptions are gone; only the bound is.

### 3. Input-based fusion of two hock-position estimates

A depth camera reports the hock's lateral position as 102 mm with standard deviation 4 mm, a laser
line reports 96 mm with 2 mm, and the prior is 100 mm with 20 mm (illustrative numbers, not measured).
The product of Gaussian experts, as in the MVAE posterior with a prior expert:

| Inputs | Fused mean (mm) | Fused sd (mm) |
|---|---|---|
| prior + camera + laser | 97.22 | 1.78 |
| prior + camera (laser dropped out) | 101.92 | 3.92 |
| prior + camera + laser biased by +10 mm (106, sd 2) | 105.16 | 1.78 |
| naive mean of camera and laser | 99.00 | not defined |

Dropping an expert is handled by construction. A biased expert that reports a small variance drags
the fused estimate 8 mm and leaves the reported uncertainty unchanged at 1.78 mm: the product carries
no signal that the experts disagree. A shared cause, such as the gripper occluding both sensors,
violates the conditional independence the exact posterior needs.

```python
import numpy as np

N, GOALS, STEP, RMAX, RMIN = 9, (0, 3, 4), -0.1, 2.0, -2.0
RBAR = min(RMIN, (RMIN - RMAX) * (N - 1))          # Nangue Tasse 2020, Def. 2
ACTS = ("left", "right", "done")                   # done at a goal ends the episode

def step(s, a):
    return max(s - 1, 0) if a == "left" else min(s + 1, N - 1) if a == "right" else s

def solve(terminal):                               # terminal(s) -> reward for done at goal s
    V = np.zeros(N)
    for _ in range(300):
        Q = np.array([[terminal(s) if a == "done" and s in GOALS else STEP + V[step(s, a)]
                       for a in ACTS] for s in range(N)])
        V = Q.max(1)
    return Q

task = lambda G: (lambda s: RMAX if s in G else RMIN)
def extended(G):                                   # Q-bar[s, g, a]
    return np.stack([solve(lambda s, g=g: (RMAX if s in G else RMIN) if s == g else RBAR)
                     for g in GOALS], axis=1)

def rollout(Q, s, reward, horizon=40):
    ret, path = 0.0, [s]
    for _ in range(horizon):
        a = ACTS[int(Q[s].argmax())]
        if a == "done" and s in GOALS:
            return round(ret + reward(s), 2), path + [f"done@{s}"]
        ret, s = ret + STEP, step(s, a); path.append(s)
    return round(ret, 2), path

A, B, s0 = {0, 3}, {0, 4}, 5
QA, QB = solve(task(A)), solve(task(B))
Qavg = 0.5 * (QA + QB)                             # action-based: product of Boltzmann policies
QAND = solve(task(A & B))
QbA, QbB = extended(A), extended(B)
Qmin = np.minimum(QbA, QbB).max(axis=1)            # outcome-based AND, then max over goals
QbU, Qb0 = extended(set(GOALS)), extended(set())
NOT = lambda Qb: QbU + Qb0 - Qb
Qxor = np.maximum(np.minimum(QbA, NOT(QbB)), np.minimum(QbB, NOT(QbA))).max(axis=1)
Qstar_avg = solve(lambda s: 0.5 * (task(A)(s) + task(B)(s)))

print("Q_A(5)", QA[s0], "Q_B(5)", QB[s0], "Q_avg(3), (4)", Qavg[3], Qavg[4])
print("avg-Q on A AND B:", rollout(Qavg, s0, task(A & B)))
print("min-extended on A AND B:", rollout(Qmin, s0, task(A & B)), np.allclose(Qmin, QAND))
print("max(Q_A,Q_B) == Q*_OR:", np.allclose(np.maximum(QA, QB), solve(task(A | B))))
print("XOR:", rollout(Qxor, s0, task(A ^ B)), np.allclose(Qxor, solve(task(A ^ B))))
print("Q_avg(5) - Q*_avgreward(5):", Qavg[s0] - Qstar_avg[s0])

P = np.array([[0.1, 0.8, 0.1], [0.1, 0.1, 0.8], [0.0, 0.5, 0.5]])   # rows a, b, c
QA2, QB2, QOR = P[:, 1], P[:, 2], P[:, 1] + P[:, 2]
print("stochastic: max picks", "abc"[np.maximum(QA2, QB2).argmax()], QOR[np.maximum(QA2, QB2).argmax()],
      "| average picks", "abc"[(QA2 + QB2).argmax()], QOR[(QA2 + QB2).argmax()], "| optimum", QOR.max())

def poe(mus, sds):
    T = 1 / np.square(sds); return round(float((T * mus).sum() / T.sum()), 2), round(float(T.sum() ** -0.5), 2)
print("PoE prior+cam+laser", poe(np.array([100, 102, 96.]), np.array([20, 4, 2.])),
      "laser missing", poe(np.array([100, 102.]), np.array([20, 4.])),
      "laser biased", poe(np.array([100, 102, 106.]), np.array([20, 4, 2.])))
```

## Emergence and non-additivity

Definition used here. A composition is additive for an operator when the composite's outcome equals
the same operator applied to the constituents' outcomes: for AND, the composite reaches exactly the
states both constituents' specifications accept; for OR, either. The exact outcome-based theorems
are precisely the cases where additivity is proven. Non-additivity is any departure. Emergence is a
departure that produces an outcome in neither constituent's outcome set, useful or harmful. Doing X
and Y together gives the union of X's and Y's outcomes only inside those theorems' assumptions.

The mechanisms, with evidence:

The composite visits states neither constituent visited. Haarnoja's C* and D* take expectations of
the constituents' divergence along the composite's own state distribution; if the constituents
disagree there, the bound is loose and the behaviour is new. Hunt et al.'s "tricky" tasks are built
so the optimum resembles neither constituent, and CO and GPI both miss it.

Value functions summarise only the nearest goal. Averaging or multiplying them has no access to the
shared goal (Nangue Tasse et al. 2020 Sec. 3.2), which produces the oscillation in worked example 1.

Superposed fields cancel. Koren and Borenstein, on the 125 kg CARMEL platform at up to 0.8 m/s with
obstacles written into the grid for repeatability, list four problems inherent to potential fields:
traps at local minima, no passage between closely spaced obstacles (the summed repulsion points away
from a doorway), oscillation near obstacles, and oscillation in narrow corridors. They derive a
stability condition for motion along a wall, 1 - N V (tau + T) > 0 with speed V, steering time
constant tau and sampling delay T, and show a narrow corridor driving the robot into oscillation and a
collision with f = 0.8, T = 0.065 s, tau = 0.3 s, V = 0.8 m/s (Fig. 6); they abandoned potential fields
for vector field histograms ([Koren and Borenstein 1991](https://www.cs.cmu.edu/~motionplanning/papers/sbp_papers/integrated1/borenstein_potential_field_limitations.pdf)).
Their paper attributes the local-minimum problem to Andrews and Hogan 1983 and Tilove 1989 and the
potential-field idea to Andrews and Hogan 1983 and Khatib 1985; Khatib's 1986 IJRR paper was not
read. Arkin's schemas stall on a
blocked sidewalk where the stay-on-path and avoid fields cancel (Fig. 8), fixed by lowering the
stay-on-path gain through inter-schema communication, and on a head-on approach plateau (Fig. 9),
for which he proposes a low-magnitude random noise schema. Computed here for the head-on case, with a
constant-magnitude attractor of 1 toward a goal at x = 5 and Arkin's linear repulsion (gain 1.5,
S = 2, R = 0.5) from an obstacle centred at x = 3 on the same line: the robot stops at x = 2.0, 1.0
from the obstacle centre, whatever the distance to the goal, because the stall depends only on the
gain ratio.

Priority composition stalls and higher layers rescue it. Brooks's physical robot under level 2
sometimes picks a goal behind a wall from bad sonar; it then sits where the goal's attraction is
within Avoid's threshold of the wall's repulsion, issues no heading, and is "defeated by the
obstacle" until the Whenlook module notices it is idle and starts a new corridor search (Sec. V-B).
The same architecture shows useful emergence: under level 0 alone the robot sits in open space, and
"two people together can successfully herd the robot just about anywhere".

The sampler is not the product. Adding diffusion scores and running reverse diffusion does not sample
the product distribution, because the noised product is not the product of noised marginals (Du et
al. Eqs. 11 to 12). On CLEVR, composing a one-object-location model with itself for 1 to 5 objects,
reverse diffusion placed all objects correctly 70.8, 68.2, 66.3, 64.1 and 57.4 % of the time; an
energy-parameterised model with HMC reached 91.6, 82.9, 80.1, 76.5 and 72.7 % (Table 2, same number of
score evaluations). ImageNet 128 by 128 classifier guidance accuracy went from 18.64 % to 94.61 %
(Table 3). The MCMC samplers take up to about 5 times longer (Sec. 6).

Learned policies compose some factor pairs and not others. Gao et al. (WidowX 250, "put fork in
container", 4 values per factor, 9 unseen combinations per factor pair) trained on data that varied
one factor at a time plus BridgeData V2 as prior data: 59/90 unseen pairwise combinations succeeded,
28/90 without prior data, 22/90 with prior data but no in-domain variation (Table I). Physical factor
pairs composed worst: object position with table height 2/9, container type with table height 5/9;
object type composed with everything at 8/9. Frozen R3M and VC-1 encoders scored 2/27 and 0/27 on
three pairs (Table II). In two unseen kitchens, the best data strategy (Stair, co-fine-tuned with
BridgeData V2) succeeded 31/40, against 1/40 without in-domain variation (Table III). In Xie et al.
(RT-1 on a mobile manipulator, 12 trials per condition), success fell from 91.7 % to 52.8 % for a new
table texture and 45.8 % for a new camera pose, but pairing a new texture with a new background
(55.6 %) or new distractors (50.0 %) was no worse than the texture alone; in simulation 16 of 21
factor pairs stayed within 6 % of the harder single factor (Sec. 5.1). Devin et al.'s modular
policy composed zero-shot for reaching and pushing but not for the drawer pull. MCP lost to training
from scratch on its only held-out test (holdout Ant 0.812 against 0.951,
[latent skills note](../papers/policy-composition-latent-skills.md)).

Useful emergence, with numbers. The SF and GPI policy for w = [1, -1] avoided type-2 objects that
no constituent was trained to avoid (PNAS 2020, 100 runs). The option keyboard drove the quadruped
in directions between its three trained options. The Boolean algebra's composed value functions
reached goals by XOR and NOR that no base task singled out (Nangue Tasse et al. 2020, Fig. 2). The
composed Sawyer policy stacked while avoiding in 10/10 trials where stacking alone collided every
time ([energy products note](../papers/policy-composition-energy-products.md)). On the real robot, a
policy trained on two sub-datasets, one missing the evaluation camera pose and one missing the table
texture, succeeded 10/10 with prior data against 1/10 and 6/10 for each sub-dataset alone (Gao et al.
Table V).

## Recipe

How to pick the composition type for a new composed skill:

1. Write the requirement as a check on the result first (goal set, event order, success predicate at
   the saw). If it can be written, it is the contract's success condition whatever the
   implementation, and it is the thing to evaluate.
2. The requirement is a Boolean expression over a finite set of goal states, the dynamics are close
   to deterministic, and per-goal values can be trained: use extended value functions with min, max
   and negation. Exact under the assumptions; with stochastic dynamics budget the 2/(1 - gamma)
   bound and test.
3. The requirement is a weighting of measurable features over shared dynamics (overhang, cycle time,
   contact force): use successor features and GPI. Expect at least the best stored skill; store skills
   near the weights you will use (the distance term in the bound).
4. The requirement is an order of events: task graph with explicit contracts; a reward machine if the
   sequence is learned rather than scripted.
5. The requirement is about the motion at each instant (strict priority, keep-out, a compliant
   axis): action-based. Nullspace projection for strict priority, energy or product sums for a
   compromise, hard limits in the deterministic shield. Nothing guarantees the outcome, so the
   contract needs stall and oscillation detectors.
6. Skills fail because they see different things, or a sensor drops out: input-based fusion with
   calibrated variances and a check that the sources do not share a failure cause; then test the
   downstream skill on the fused input.
7. Anything not covered by an exactness theorem is evaluated on the grid of combinations before
   release, with prior data in training if the skill is learned (Gao et al.).

## Practical gotchas

- Max-composition of Q-functions is not optimal once dynamics are stochastic: 0.9 against 1.0 in the
  three-outcome example ([van Niekerk et al. 2019](https://proceedings.mlr.press/v97/van-niekerk19a.html), Sec. 4.1).
- Averaging regular Q-functions cannot represent a conjunction when the constituents' nearest goals
  differ ([Nangue Tasse et al. 2020](https://arxiv.org/abs/2001.01394), Sec. 3.2); in worked example 1
  it oscillates forever.
- Compositional optimism fails for incompatible constituents and GPI fails to exploit compatible
  ones; both fail when the optimum resembles neither ([Hunt et al.](https://arxiv.org/abs/1812.02216), Fig. 1).
- Spanning the reward space does not span behaviour: all-negative base tasks give standing-still
  policies that GPI cannot turn into a positive task ([Barreto et al. 2018](https://arxiv.org/abs/1901.10964), Sec. 5.3).
- Good returns do not mean the composite values are right: test-time clipping scored well while bound
  violations stayed high ([Adamczyk et al. 2023](https://arxiv.org/abs/2303.02557), Fig. 2).
- Summed diffusion scores with reverse diffusion do not sample the product; accuracy on five composed
  object locations was 57.4 % against 72.7 % with HMC ([Du et al. 2023](https://arxiv.org/abs/2302.11552), Table 2).
- Potential-field composites oscillate at speed and with sampling delay, and a narrow corridor
  produced a collision on a real robot ([Koren and Borenstein 1991](https://www.cs.cmu.edu/~motionplanning/papers/sbp_papers/integrated1/borenstein_potential_field_limitations.pdf), Fig. 6).
- A product-of-experts fusion trained only on complete multimodal data never trains the
  single-modality encoders, so it fails when a sensor drops out ([Wu and Goodman 2018](https://arxiv.org/abs/1802.05335), Sec. 2.2).
- Module names do not constrain module behaviour: combine[and] is not fixed to an intersection
  ([Andreas et al. 2016](https://arxiv.org/abs/1511.02799), Sec. 5).
- Real-robot compositional generalisation roughly halved without prior robot data (59/90 to 28/90)
  and physical factor pairs composed worst ([Gao et al. 2024](https://arxiv.org/abs/2403.05110), Table I).
- Desirability primitives from an SVD go non-positive near the boundary, where the composite is
  undefined ([Todorov 2009](https://roboti.us/lab/papers/TodorovNIPS09.pdf), Fig. 2B).

## Open questions

- Whether conjunction over extended values is useful for orient on a deformable leg sliding on a wet
  belt, where the dynamics are stochastic and the exact theorem does not apply. For a task the
  algebra expresses exactly, the ICLR 2022 bound is 2 epsilon/(1 - gamma): at gamma = 0.99 the base
  skills' error is multiplied by 200, and any mismatch in the goal vector adds 200 r_Delta.
- How to define a finite goal set for continuous poses (hock yaw, trotter overhang) so the Boolean
  results apply; every paper here uses discrete goals.
- No outcome-based exact composition in the papers read was demonstrated on a real robot; the only
  real-robot value composition is Haarnoja's averaged soft Q, which is a bound.
- Whether the depth camera and a laser line on wet meat are conditionally independent given the hock
  pose, or share failures through occlusion and specular returns.
- The cell's own factor grid (leg length, arrival yaw, belt speed, arm) for action-based and learned
  composites, evaluated with a one-factor-at-a-time data strategy as in Gao et al.
- Whether an action-based composite with an outcome check in the verify skill is enough in practice,
  compared with synthesising the composite from value summaries.

## Related entries

- [Composing policies as products](../papers/policy-composition-energy-products.md)
- [Policy composition with latent skills](../papers/policy-composition-latent-skills.md)
- [Task primitives, nullspace controllers, diffusion composition](../papers/policy-composition-primitives-controllers-diffusion.md)
- [Generative models behind learned skills](generative-models-vae-and-diffusion.md)
- [Meat cell architecture](meat-cell-architecture.md), [control architecture selection](control-architecture-selection.md), [conveyor tracking](conveyor-tracking-and-visual-servoing.md)
- [Arm selection](arm-selection-scara-vs-six-axis.md), [deformable object manipulation](deformable-object-manipulation.md), [pork processing line](pork-processing-line.md)
- [Safety for learned policies](safety-for-learned-policies.md), [real-world RL](real-world-rl.md), [imitation learning](imitation-learning.md)

## Sources

- Todorov, Compositionality of optimal control laws, NIPS 2009: https://roboti.us/lab/papers/TodorovNIPS09.pdf ; https://papers.nips.cc/paper/3842-compositionality-of-optimal-control-laws
- van Niekerk, James, Earle, Rosman, Composing value functions in reinforcement learning, ICML 2019: https://proceedings.mlr.press/v97/van-niekerk19a.html ; supplement https://proceedings.mlr.press/v97/van-niekerk19a/van-niekerk19a-supp.pdf
- Haarnoja et al., Composable deep RL for robotic manipulation, ICRA 2018: https://arxiv.org/abs/1803.06773
- Hunt, Barreto, Lillicrap, Heess, Composing entropic policies using divergence correction, ICML 2019: https://arxiv.org/abs/1812.02216
- Nangue Tasse, James, Rosman, A Boolean task algebra for reinforcement learning, NeurIPS 2020: https://arxiv.org/abs/2001.01394
- Nangue Tasse, James, Rosman, Generalisation in lifelong reinforcement learning through logical composition, ICLR 2022: https://www.raillab.org/publication/nangue-2022-generalisation/nangue-2022-generalisation.pdf
- Nangue Tasse, Rosman, James, World value functions: knowledge representation for learning and planning, 2022: https://arxiv.org/abs/2206.11940
- Terrés-Caballero, van Hoof, A goal-set characterization of task composition in the Boolean task algebra, 2026: https://arxiv.org/abs/2606.04053
- Barreto et al., Successor features for transfer in reinforcement learning, NIPS 2017: https://arxiv.org/abs/1606.05312
- Barreto et al., Transfer in deep RL using successor features and generalised policy improvement, ICML 2018: https://arxiv.org/abs/1901.10964
- Barreto et al., The option keyboard: combining skills in reinforcement learning, NeurIPS 2019: https://arxiv.org/abs/2106.13105
- Barreto, Hou, Borsa, Silver, Precup, Fast reinforcement learning with generalized policy updates, PNAS 117(48) 2020: https://doi.org/10.1073/pnas.1907370117 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC7720214/
- Adamczyk et al., Bounding the optimal value function in compositional reinforcement learning, UAI 2023: https://arxiv.org/abs/2303.02557
- Toro Icarte, Klassen, Valenzano, McIlraith, Using reward machines for high-level task specification and decomposition in RL, ICML 2018: https://proceedings.mlr.press/v80/icarte18a.html
- Wu, Goodman, Multimodal generative models for scalable weakly-supervised learning, NeurIPS 2018: https://arxiv.org/abs/1802.05335
- Devin, Gupta, Darrell, Abbeel, Levine, Learning modular neural network policies for multi-task and multi-robot transfer, 2016: https://arxiv.org/abs/1609.07088
- Andreas, Rohrbach, Darrell, Klein, Deep compositional question answering with neural module networks, arXiv v4 2017 (venue not checked): https://arxiv.org/abs/1511.02799
- Brooks, "A robust layered control system for a mobile robot", IEEE J. Robotics and Automation 2(1), 1986: https://doi.org/10.1109/JRA.1986.1087032 ; copy read https://www.robolabo.etsit.upm.es/asignaturas/irin/papers/Brooks86RobustLayeredControl.pdf
- Arkin, Motor schema based navigation for a mobile robot, ICRA 1987: https://doi.org/10.1109/ROBOT.1987.1088037 ; copy read http://www.robolabo.etsit.upm.es/asignaturas/irin/papers/arkinMotorSchemas.pdf ; IJRR 1989 version (not read) https://doi.org/10.1177/027836498900800406
- Koren, Borenstein, Potential field methods and their inherent limitations for mobile robot navigation, ICRA 1991, pp. 1398-1404: https://www.cs.cmu.edu/~motionplanning/papers/sbp_papers/integrated1/borenstein_potential_field_limitations.pdf
- Khatib, Real-time obstacle avoidance for manipulators and mobile robots, IJRR 1986 (not read): https://doi.org/10.1177/027836498600500106
- Du et al., Reduce, reuse, recycle: compositional generation with energy-based diffusion models and MCMC, ICML 2023: https://arxiv.org/abs/2302.11552
- Gao, Xie, Xiao, Finn, Sadigh, Efficient data collection for robotic manipulation via compositional generalization, arXiv v2 2024 (venue not checked): https://arxiv.org/abs/2403.05110
- Xie, Lee, Xiao, Finn, Decomposing the generalization gap in imitation learning for visual robotic manipulation, 2023: https://arxiv.org/abs/2307.03659
- Peng et al., MCP, NeurIPS 2019: https://arxiv.org/abs/1905.09808 ; Urain et al., Composable energy policies, RSS 2021: https://arxiv.org/abs/2105.04962
