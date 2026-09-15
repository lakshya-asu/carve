---
title: "Latent Skill Representations: Skill Priors, Discovered Skills, Latent Actions and Cross-Embodiment Transfer"
date: 2026-09-15
tags: [topic, skills, latent-space, skill-priors, skill-discovery, latent-actions, cross-embodiment, composition, skill-contracts, runtime-monitoring, scara, six-axis, pork-leg]
status: draft
source:
  - https://arxiv.org/abs/2010.11944
  - https://arxiv.org/abs/2107.10253
  - https://arxiv.org/abs/2010.13611
  - https://arxiv.org/abs/1812.01483
  - https://arxiv.org/abs/2406.17768
  - https://arxiv.org/abs/2407.15840
  - https://arxiv.org/abs/2402.10450
  - https://arxiv.org/abs/1802.06070
  - https://arxiv.org/abs/1907.01657
  - https://arxiv.org/abs/2004.12974
  - https://arxiv.org/abs/2310.08887
  - https://arxiv.org/abs/2402.15391
  - https://arxiv.org/abs/2410.11758
  - https://arxiv.org/abs/2501.10105
  - https://arxiv.org/abs/2502.00379
  - https://arxiv.org/abs/2402.19249
  - https://arxiv.org/abs/2307.03719
  - https://arxiv.org/abs/2306.11706
  - https://arxiv.org/abs/2406.01968
  - https://arxiv.org/abs/2506.14608
  - https://arxiv.org/abs/1910.14033
  - https://arxiv.org/abs/2410.04640
  - https://arxiv.org/abs/2503.08558
---

# Latent Skill Representations

Texts read in full from arXiv, 2026-09-14, version in brackets: SPiRL (v1), SkiLD (v1), OPAL (v3),
CompILE (v2), EXTRACT (v3), QueST (v3), PRISE (v3), LOTUS (v4), DIAYN (v6), DADS (v2), off-DADS
(v1), LSD (v2), CSD (v3), METRA (v2), Jansonnie et al. (v1), Genie (v1), LAPA (v2), IGOR (v1),
Moto (v4), UniAct (v2), GR00T N1 (v2), villa-X (v3), CLAM (v2), Nikulin et al. (v5), Open
X-Embodiment (v9), Octo (v2), CrossFormer (v1), HPT (v1), Polybot (v1), Mirage (v3), Shadow (v1),
Wang et al. 2024 (v1), Latent Action Diffusion (v4), Devin et al. (v1), Hejna et al. (v2),
Im2Flow2Act (v2), ATM (v3), Track2Act (v2), XSkill (v2), UniSkill (v4), RDT-1B (v2), AnyBody (v1),
Tang et al. (v1), CPV (v2), Play-LMP (v2), TAP (v3), LDCQ (v1), Julian et al. (v3), Sentinel (v2),
FAIL-Detect (v3), Wong et al. (v1), ACT (v1), HULC (v2), Bowman et al. (v4). Read in part:
Locatello et al. (v4, main paper without appendices), RoboCat (v2, Sec. 3, 5.1 to 5.4, App. C, F,
G.4.3), Interactive Language (v1, action space and hardware only), 3DFlowAction (v1, Sec. 5 and
App. B). Values marked "read from plot" are approximate readings of a figure, not printed numbers.

MCP, Hausman et al. 2018, He et al. 2018 and Xu et al. 2023 are covered in
[policy-composition-latent-skills](../papers/policy-composition-latent-skills.md) and are not
repeated. VQ-BeT has its own note ([lee-2024-vq-bet](../papers/lee-2024-vq-bet.md)).

## What it is

A latent skill representation maps a segment of behaviour to a vector z or a discrete code k, and a
decoder maps (state, z) back to actions. The families differ in what the encoder sees and what
trains it.

- **Skill priors from offline data.** Encode an H-step action chunk or state-action window with a
  KL-regularised autoencoder, learn a state-conditioned prior over z, then run RL, imitation or
  planning in z (SPiRL, SkiLD, OPAL, CompILE, EXTRACT, QueST, PRISE).
- **Unsupervised skill discovery.** No data: an RL agent maximises a dependency measure between z
  and the states it visits (DIAYN, DADS, LSD, CSD, METRA).
- **Latent actions from observation pairs.** An inverse dynamics model reads (o_t, o_{t+H}) with no
  action labels, quantises the change, and a forward model must reconstruct o_{t+H} from o_t and
  the code (Genie, LAPA, Moto, IGOR, villa-X, CLAM). Labels are needed only to decode codes into
  robot commands.

The cross-embodiment question cuts across all three: whether the same z, or the same action vector,
produces the same effect on a different robot. The latent itself never carries a name, a
precondition or a success test; those have to come from outside it.

## Why it matters in the field

A skill space makes long-horizon offline RL work where flat action spaces fail in simulation. OPAL
reaches 70.3 ± 2.9 percent on antmaze-large-diverse against 14.9 ± 3.2 for CQL on the same data,
4 seeds ([Ajay et al. 2020](https://arxiv.org/abs/2010.13611), Table 1).

Latent actions are how current generalist policies consume unlabelled video. GR00T N1 trains on
human egocentric video with LAPA-style latent targets only
([NVIDIA 2025](https://arxiv.org/abs/2503.14734), Sec. 2.2). LAPA pretraining took 272 H100-hours
against 21,500 A100-hours for OpenVLA. LAPA also beat OpenVLA on a real Franka, 50.09 against 43.87
partial-credit percent over 54 rollouts per model
([Ye et al. 2024](https://arxiv.org/abs/2410.11758), Table 16).

Cross-embodiment models have converged on a shared trunk with per-embodiment input and output
modules, not on one shared action vector: Octo, CrossFormer, HPT, GR00T N1, UniAct. The CrossFormer
authors state their results "do not yet show significant positive transfer across embodiments"
([Doshi et al. 2024](https://arxiv.org/abs/2408.11812)). That is the gap the SCARA plus six-axis
proof of concept sits in.

## Methods

### 1. Skill priors and skill spaces from offline data

**SPiRL** ([Pertsch, Lee, Lim, CoRL 2020](https://arxiv.org/abs/2010.11944)).

```
Skill VAE (Eq. 1):
  log p(a_{1:H}) >= E_q[ log p(a_{1:H} | z) - beta * ( log q(z | a_{1:H}) - log p(z) ) ]
Skill prior (Sec. 3.2):
  min  E_{(s, a_{1:H}) ~ D} [ KL( sg(q(z | a_{1:H})) || p_a(z | s_1) ) ]
Downstream RL (Eq. 3), SAC with the entropy bonus replaced:
  J(theta) = E_pi[ sum_t r~(s_t, z_t) - alpha * KL( pi(z_t | s_t) || p_a(z_t | s_t) ) ]
```

- a_{1:H}: H consecutive actions.
- q: encoder, LSTM over actions only, no states.
- p(a|z): open-loop decoder.
- p(z) = N(0, I).
- beta: KL weight, 1e-2 on maze and block stacking, 5e-4 on kitchen.
- sg: stop-gradient.
- p_a(z|s): learned prior.
- r~: reward summed over the H steps.
- alpha: tuned against a target divergence delta.
- |Z| = 10.

The high-level policy picks z every H steps and is pulled toward the prior. The prior is the only
thing that says which z fits a state.

- **Maze.** Only SPiRL reached the goal; "none of the baseline policies reaches the goal during
  training" (Fig. 4, 3 seeds).
- **Horizon and dimension** (curves only). The block-stacking ablation sweeps H in {3, 10, 30} and
  |Z| in {2, 10, 30}. Too short an H gives no temporal abstraction, and beyond a minimum |Z|
  "does not have a major influence" (Fig. 6).
- **Noisy data.** With 75 percent random data the prior still stacked 1.0 blocks, against 1.5 for
  the best baseline trained on clean data (App. G, Table 1).
- **State-conditioned decoder.** It "did not improve downstream learning and can even lead to worse
  performance" (App. D).
- **Hardware.** All simulation, no real robot.

**SkiLD** ([Pertsch et al., CoRL 2021](https://arxiv.org/abs/2107.10253)) replaces the open-loop
decoder with a closed-loop low-level policy and adds a demonstration posterior.

```
Skill model (Eq. 2):
  max E_q[ sum_{t=0}^{H-2} log pi_phi(a_t | s_t, z) - beta * ( log q_omega(z | s_{0:H-1}, a_{0:H-2}) - log p(z) ) ]
Demo posterior (Eq. 3):   min E_{D_demo}[ KL( q_omega(z | s, a) || q_zeta(z | s_0) ) ]
Downstream (Eq. 4):
  J_t = r~ - alpha_q * KL( pi(z|s) || q_zeta(z|s) ) * D(s) - alpha * KL( pi(z|s) || p_a(z|s) ) * (1 - D(s))
  r~  = (1 - kappa) * r(s, z) + kappa * [ log D(s) - log(1 - D(s)) ]
```

- D(s): a learned discriminator that estimates whether s is inside the demonstration support.
- kappa = 0.9.
- H = 10, z is 10-dimensional.

Inside the support the policy follows the demo posterior. Outside it the policy follows the task
prior.

- **Evidence.** Learning curves on simulated maze, Franka kitchen and WidowX office cleanup, 3 seeds,
  no tables (Fig. 4).
- **Ablation.** "post-only" "fails since the agent follows the skill posterior outside its support"
  (Fig. 6).

**OPAL** ([Ajay et al., ICLR 2021](https://arxiv.org/abs/2010.13611)).

```
Primitive learning (Eq. 1 to 2):
  min  E_{tau ~ D, z ~ q_phi(z|tau)} [ - sum_{t=0}^{c-1} log pi_theta(a_t | s_t, z) ]
  s.t. E_tau[ KL( q_phi(z | tau) || rho_omega(z | s_0) ) ] <= eps_KL      (penalty weight beta = 0.1)
Offline RL: relabel reward data as (s_0, z ~ q_phi, sum_t gamma^t r_t, s_c) and train pi_psi(z|s) with CQL.
```

- tau: a c-step state-action window, with c = 10.
- q_phi: bidirectional GRU encoder.
- pi_theta: closed-loop primitive policy.
- rho_omega: state-conditioned prior.
- dim(Z) = 8.

Results on D4RL in simulation, 4 seeds:

| Setting | OPAL | Comparison |
|---|---|---|
| antmaze-medium-diverse | 81.1 ± 3.1 | CQL 53.7 ± 6.1 |
| kitchen-partial | 80.2 ± 2.4 | CQL 50.1 ± 1.0 |
| Few-shot BC, antmaze-large, 10 expert trajectories | 63.5 ± 2.3 | BC 9.2 ± 2.5 |
| Latent dimension 4 / 8 / 16 | 68.7 / 81.1 / 81.3 | n/a |
| c = 1 (no temporal abstraction) | 55.3 ± 3.8 | c = 10: 81.1 |

Sources for the table: Tables 1, 2 and 5, and App. E.

OPAL states the collapse risk in words: if one stationary policy generated the data, "a VAE-optimal
policy pi_theta can simply ignore the latent z" (Sec. 4.1).

**CompILE** ([Kipf et al., ICML 2019](https://arxiv.org/abs/1812.01483)) learns variable-length
segments with discrete codes.

```
Generative model (Eq. 3):
  p(a_{1:T} | s_{1:T}) = sum_{b, z} prod_i [ prod_{j in segment i} pi_theta(a_j | s_j, z_i) ] p(b_i | b_{i-1}) p(z_i)
  p(b_i | b_{i-1}) proportional to Poisson(b_i - b_{i-1}; lambda)  (Eq. 4, lambda = 3)
ELBO = E_q[ log p(a | s, b, z) + log p(b, z) - log q(b, z | a, s) ]   (Gumbel-softmax relaxation of b and z)
```

- b_i: segment boundaries.
- z_i: a code per segment, uniform categorical with K = 10.
- The Poisson prior exists "to avoid two failure modes: collapse of segments to unit length, and a
  single segment covering the full sequence length".

Results on a simulated 2-link reacher, 5 runs:

| Setting | Segmentation accuracy |
|---|---|
| CompILE, 3 tasks | 62.0 ± 4.5 |
| CompILE, 5 tasks (generalisation) | 41.7 ± 8.0 |
| Gaussian latent instead of discrete, 3 tasks | 45.2 ± 13.8 |
| Supervised boundaries | 99.8 ± 0.1 |

Sources: Tables 1 and 2.

On semantics, in its grid world the model learned "a location-specific latent code", while the
ground-truth tasks were specific to object type (Sec. 4.4).

**Successors, 2023 to 2025.**

EXTRACT ([Zhang et al., CoRL 2024](https://arxiv.org/abs/2406.17768)) builds discrete skill ids and
continuous arguments.

```
EXTRACT skill ids:  e_t = VLM(s_t) - VLM(s_1)  ->  K-means (K = 8)  ->  median filter  ->  skill id d
EXTRACT skill model (Eq. 2, maximised):
  E[ sum_t log p_a(a_t, l | z, d) + beta * KL( q(z | a, d) || N(0, I) ) + log p_d(d | s_1) + log p_z(sg(z) | s_1, d) ]
```

- d: discrete skill id from clustering R3M embedding differences, average skill length about
  30 steps.
- z: continuous 5-dimensional argument.
- l: predicted progress in [0, 1]. Execution stops at l = 1.
- The "+ beta * KL" is printed that way inside a maximisation.

EXTRACT evidence:

- **Real robot.** On a Franka running FurnitureBench one-leg assembly, EXTRACT completed 1.90
  subtasks out of 5 before and 2.50 after 100 episodes of real RLPD. SPiRL scored 1.55 after.
  20 trials, one run, no variance (Table 1).
- **Ablation.** Automatic KL tuning was "unstable", so the KL weights were fixed.

QueST ([Mete et al. 2024](https://arxiv.org/abs/2407.15840), "Preprint. Under review" in v3,
publication venue unverified) drops the KL term and quantises instead.

```
QueST:  L_recon = || psi( FSQ( phi(a_{t:t+T-1}) ) ) - a_{t:t+T-1} ||_1 ;
        prior = GPT over tokens,  - sum_i log pi(z_i | z_<i, obs, task)
```

- phi: causal convolutional and attention encoder.
- FSQ: finite scalar quantisation, levels [8, 5, 5, 5], 1000 codes.
- T = 32 actions become 8 tokens.
- The encoder does not see the state.

QueST evidence, simulated LIBERO:

| Setting | QueST | Comparison |
|---|---|---|
| LIBERO-90 multitask, 4 seeds, 40 rollouts per task | 88.6 | VQ-BeT 81.3, Diffusion Policy 75.4 |
| LIBERO-LONG 5-shot, 9 seeds | 68.8 | VQ-BeT 65.2 |
| Observation-conditioned decoder, LIBERO-90 | 81.9 ± 1.1 | full QueST 88.6 ± 0.4 |
| Observation-conditioned decoder, few-shot | 61.3 ± 2.2 | full QueST 68.8 ± 1.7 |

Sources: Fig. 2 and Table 1.

PRISE ([Zheng et al., ICML 2024](https://arxiv.org/abs/2402.10450)) vector-quantises single actions,
then compresses code sequences with byte pair encoding into variable-length skill tokens. Its
Stage I loss is L = L_dyn + beta * L_act_decode, with a latent forward-dynamics term. Without that
term "the decoder may learn to depend solely on z_t... leading to the collapse of action codes".
Mean pairwise KL between the action distributions of different codes is 72.42 with the dynamics
loss and 14.53 without it (Sec. 5.4, simulation).

LOTUS ([Wan et al., ICRA 2024](https://arxiv.org/abs/2311.02058)) clusters DINOv2 features into a
growing library of discrete skills, each a visuomotor policy. A meta-controller picks a skill index
and a subgoal embedding every step.

- **Sim.** LIBERO-Object forward transfer 74.0 ± 3.0 against 56 for experience replay, 3 seeds,
  20 trials per task.
- **Real robot.** Results are reported without trial counts and without naming the robot.

### 2. Unsupervised skill discovery by mutual information, and its limits

**DIAYN** ([Eysenbach et al., ICLR 2019](https://arxiv.org/abs/1802.06070)).

```
F(theta) = I(S; Z) + H[A | S] - I(A; Z | S) = H[Z] - H[Z | S] + H[A | S, Z]          (Eq. 1 to 2)
lower bound G(theta, phi) = H[A | S, Z] + E_{z ~ p(z), s ~ pi(z)} [ log q_phi(z | s) - log p(z) ]
reward (Eq. 3): r_z(s, a) = log q_phi(z | s) - log p(z)                                 (SAC, alpha = 0.1)
```

- S: states. A: actions. Z: skill.
- p(z): fixed uniform categorical, 50 skills in most runs.
- q_phi: discriminator that guesses the skill from the state.

Evidence is all simulated MuJoCo with plots only. The authors report that ant skills move in arcs
and none walks straight, and that a handstand cannot be imitated.

**DADS** ([Sharma et al., ICLR 2020](https://arxiv.org/abs/1907.01657)) makes skills predictable
rather than distinguishable.

```
I(s'; z | s) = H(s' | s) - H(s' | s, z) >= E[ log q_phi(s' | s, z) - log p(s' | s) ]     (Eq. 2, 4)
reward (Eq. 6): r_z(s, a, s') = log( q_phi(s' | s, z) / sum_{i=1}^{L} q_phi(s' | s, z_i) ) + log L,   z_i ~ p(z)
planning (Eq. 7, MPPI in skill space): mu_i = sum_k [ exp(gamma R_k) / sum_p exp(gamma R_p) ] z_{k,i}
```

- q_phi(s'|s,z): "skill-dynamics" model, a Gaussian mixture over state deltas.
- L = 500 samples for continuous skills.
- R_k: return of plan k rolled out through q_phi.
- Each z is held for HZ steps. The planner replans after the first skill.

Zero-shot navigation by planning over skills beats model-based RL baselines on simulated Ant
(Fig. 7, plots only, no seed count in text). An RL meta-controller could not compose DIAYN skills.
On DADS skills it matched MPPI but needed 200,000 extra samples per goal (Fig. 8).

The real-robot follow-up, off-DADS ([Sharma et al., RSS 2020](https://arxiv.org/abs/2004.12974)),
trained on a D'Kitty 12-DOF quadruped:

- **Training.** 20 h of effective training and about 300,000 samples over 3 days, with a 2-D skill
  space.
- **Skills.** Random skills from the prior travel 2.17 ± 0.59 m in 10 s with 5 percent falls, over
  20 trials (Fig. 8).
- **Navigation.** Planned navigation on hardware is qualitative only.
- **Operations.** Motors had to be replaced, screws loosened, and the reset detector gave false
  positives (Sec. V-F).

**The collapse argument, LSD, CSD and METRA.** Park et al. argue that MI is invariant to any
invertible transformation of the state. MI objectives therefore "can be fully maximized even with
small differences in states", and converge to "simple and static skills"
([LSD, ICLR 2022](https://arxiv.org/abs/2202.00914), Sec. 1 and 3.1). METRA states it again:
MI methods "often end up discovering simple, static behaviors with limited state coverage", because
KL "only focuses on the distinguishability of behaviors, regardless of 'how different' they are"
([Park, Rybkin, Levine, ICLR 2024](https://arxiv.org/abs/2310.08887), Sec. 2).

```
LSD (Eq. 6):   J = E[ (phi(s_T) - phi(s_0))^T z ]   s.t. ||phi(x) - phi(y)|| <= ||x - y||   (spectral norm)
CSD (Eq. 15):  replace ||x - y|| by d_CSD(s, s') = (s' - mu_theta(s))^T Sigma_theta(s)^{-1} (s' - mu_theta(s))
METRA (Eq. 8): sup_{pi, phi} E[ sum_t (phi(s_{t+1}) - phi(s_t))^T z ]   s.t. ||phi(s) - phi(s')||_2 <= 1 for adjacent (s, s')
               reward r(s, z, s') = (phi(s') - phi(s))^T z
```

- phi: a learned state embedding in the same space as z.
- LSD bounds phi by Euclidean state distance.
- CSD bounds it by the negative log-likelihood of a learned transition density, so hard-to-reach
  transitions count as far apart.
- METRA bounds it by temporal distance: the number of environment steps between two states
  (Thm. B.3). METRA is the Wasserstein dependency measure I_W(S; Z) with that metric (Eq. 2 to 7).

Results:

- **LSD, simulated point goals** (8 runs). Zero-shot success at goal range 80 is 0.92 ± 0.03,
  against 0.05 for DIAYN (Table 2).
- **CSD, simulated Kitchen** (16 discrete skills, 8 seeds). CSD solves 10 of 13 tasks on average,
  LSD 2, DIAYN 4 and DADS 0 (Fig. 7).
- **METRA.** It is "the only method that discovers locomotion skills in pixel-based Quadruped and
  Humanoid", from simulated curves, 8 seeds (Sec. 5).
- **METRA limits.** It is stated to prefer straight lines in latent space and to be sample
  inefficient. A later study found METRA converges to high-velocity skills and a "rolling behavior"
  without an upright bonus ([Atanassov et al. 2024](https://arxiv.org/abs/2410.07877), App. A.6).

**Manipulation evidence.** No 2022 to 2025 paper found in this pass trains MI- or metric-based
discovery on a real manipulator with trial counts.

The closest real-arm result is Cho et al. They pretrained DADS-style skills in simulated Fetch and
ran them on a real UR3 without fine-tuning. Real results appear only as figure lines, with no
numbers or trial counts ([Cho, Kim, Kim, RA-L 2022](https://arxiv.org/abs/2204.13906)).

Jansonnie et al. benchmark MI and metric baselines on a simulated Franka with an object prior, 3
seeds ([arXiv 2410.04855](https://arxiv.org/abs/2410.04855), Table I):

| Method | Success, "Larger" task |
|---|---|
| LSD | 0.17 |
| DADS | 0.06 |
| DIAYN | 0.00 |

The failure modes they describe: DADS skills "collapse to either ignoring the object or moving it
along a fixed path", and LSD throws the object off the table.

### 3. Discrete and continuous latent actions

VQ-BeT autoencodes action chunks with residual VQ, so its codes come from actions, not video. Its
numbers are in [lee-2024-vq-bet](../papers/lee-2024-vq-bet.md). This subsection covers codes
learned from observation pairs.

**Genie latent action model** ([Bruce et al. 2024](https://arxiv.org/abs/2402.15391)). The paper
gives no LAM loss equation beyond "a VQ-VAE-based objective".

- **Architecture.** The encoder reads x_{1:t} and x_{t+1}. The decoder predicts x_{t+1} from
  x_{1:t} and the codes. The codebook has 8 codes, one per transition at 10 FPS.
- **Inference.** Only the codebook is kept, and a user chooses one of 8 integers. Meaning is found
  by trial, like "learning the buttons on a new controller".
- **Robotics.** Trained on RT-1 plus QT-Opt video without actions. A 2.5B model reaches FVD 82.7,
  with no control results.
- **Behaviour cloning.** A policy was trained on latent codes of CoinRun expert video, then mapped
  to real actions with a code-to-action dictionary filled from labelled sequences. The paper states
  it matches the oracle "given as few as 200 expert samples". Read from plot: easy mode about 48.5
  at 200 samples against an oracle of about 54.5, 5 seeds (Fig. 14).

**LAPA** ([Ye et al., ICLR 2025](https://arxiv.org/abs/2410.11758), App. A).

```
d_1 = e_2 - e_1                                   (spatio-temporal transformer embeddings of x_1 and x_{1+H})
z_1 = argmin_k || d_1 - z_k ||^2                                         (Eq. 1)
d^_1 = d_1 + ( || d_1 - z_1 || / || v || ) * v,   v ~ N(0, I)            (Eq. 2, noise-substitution VQ)
x^_2 = D( Attn( sg[p_1], d^_1, d^_1 ) )                                  (Eq. 3)
L = || x_2 - x^_2 ||_2^2                                                 (Eq. 4)
```

- p_1: patch embeddings of the first frame.
- Codebook size |C| = 8, with s = 4 tokens per step.
- H is set so the target frame is 0.6 s ahead in robot video, and 2.4 s ahead in human video.

Stage two pretrains a 7B VLM to predict z from (image, instruction). The latent head is then
discarded and a new head trained on labelled end-effector delta actions.

LAPA evidence:

| Setting | Data | Success |
|---|---|---|
| SIMPLER WidowX, sim, 24 rollouts per task | Bridge latent pretraining, 100 labelled trajectories | LAPA 57.3; scratch 34.4; OpenVLA 36.4; labelled-action pretraining 63.5 (Table 11) |
| Real Franka, 54 rollouts | Bridge (WidowX video) pretraining | LAPA 36.83; OpenVLA 30.76 (Table 16) |
| Real Franka, 54 rollouts | SSv2 human video pretraining | LAPA 34.02; scratch 21.22 (Table 16) |

The Bridge-to-Franka row is cross-embodiment transfer. The latent vocabulary sweep 2 / 4 / 8 gave
about 39 / 54 / 57 on SIMPLER (read from plot, Fig. 5). On SSv2, some latent codes move the camera
down, right or up (App. E, qualitative).

**Successors.**

- **Moto** ([Chen et al. 2024](https://arxiv.org/abs/2412.04445)).
  - Architecture: 8 latent motion tokens from a codebook of 128 per frame pair, predicted
    autoregressively. Action query tokens read the motion tokens out into actions.
  - Real FANUC LR Mate 200iD, not in its pretraining mix, 30 demos per task, 10 trials per task:
    average 60 percent against 23.33 without motion tokens (Fig. 8).
  - CALVIN ABC to D with 1 percent of labels: 52.5 percent task success against 0 without motion
    tokens (Fig. 11).
- **IGOR** ([Chen et al. 2024](https://arxiv.org/abs/2411.00785)).
  - Filtered about 40 percent of open-world video for camera motion.
  - The only control result is in SIMPLER, where drawer success rose from about 3.5 to about
    21 percent (read from plot, trial counts not stated, Fig. 6a).
  - Latents predict position better than rotation or gripper (Fig. 6b).
- **UniAct** ([Zheng et al. 2025](https://arxiv.org/abs/2501.10105)). Not a video model: a codebook
  learned only through action-supervised behaviour cloning across 28 embodiments.

  ```
  u* = sum_i w_i u_i,  w_i = softmax( (log p(u_i | o, g) + eps_i) / tau )      (Eq. 3 to 4, Gumbel-softmax)
  a^(k) = h_k(u*, o)                                                            (Eq. 5, head per embodiment k)
  min_{U, theta} sum_k E[ L_k( a^(k), a^(k)_true ) ]                            (Eq. 6)
  ```

  - U: a 256 by 128 codebook.
  - h_k: MLP head for embodiment k.
  - A straight-through estimator "caused codebook collapse", so Gumbel-softmax was used (App. A).
  - Unseen AIRBOT arm with a new 4M-parameter head and 100 demos per interface, easy / hard:

    | Interface | UniAct | OpenVLA | Octo |
    |---|---|---|---|
    | Relative EEF | 57.5 / 40.0 | 32.5 / 22.5 | 5.0 / 12.5 |
    | Absolute joint | 70.0 / 30.0 | 2.5 / 7.5 | 0.0 / 0.0 |

    Trial counts are not stated (Fig. 5).
  - On a real WidowX, 190 rollouts, UniAct averaged 63 against 65 for OpenVLA (Fig. 3).
- **villa-X** ([Chen et al. 2025](https://arxiv.org/abs/2507.23682)).
  - Adds a proprioceptive forward model conditioned on an embodiment context c_e (dataset id and
    control frequency).
  - On an unseen Realman RM75 with 375 trajectories and 10 trials per task, the latent version won
    5 of 7 tasks and lost 2: pick-in 30 against 40 and stack 50 against 60 (Table 4).
  - The embodiment context reduced the zero-shot proprioception probe loss on that robot from 0.165
    to 0.152 (App. D.3).
- **GR00T N1** ([NVIDIA 2025](https://arxiv.org/abs/2503.14734)). In RoboCasa simulation co-training,
  100 trials, pseudo-labelling generated video with LAPA latents against an inverse dynamics model:

  | Demos per task | LAPA latents | IDM labels |
  |---|---|---|
  | 30 | 21.6 | 21.2 |
  | 300 | 52.9 | 56.4 |

  Codebook size and H are not reported (Fig. 9).
- **CLAM** ([Liang et al. 2025](https://arxiv.org/abs/2505.04999)). Continuous 16-dimensional
  latents, with an action decoder trained jointly on a small labelled set.

  ```
  L_CLAM = MSE(o^_{t+1}, o_{t+1}) + beta * MSE( p_omega(z_t), a_t ),   beta = 1
  ```

  - MetaWorld ablation, simulation: discrete without joint training 16 percent, continuous with
    joint training 74 percent (Table II).
  - Real WidowX, 10 trials, block task: 7 against 2 for a small-backbone LAPA reimplementation
    (Table III).

**Distractors.** Nikulin et al.
([ICML 2025](https://arxiv.org/abs/2502.00379)) test latent action models on Distracting Control
Suite: background video, camera shake and colour change, 4 tasks, 3 seeds. Probe MSE is linear-probe
error from latents to true actions.

| Model | Probe MSE without distractors | Probe MSE with distractors |
|---|---|---|
| LAPO with VQ | 16.41 | 29.17 |
| LAPO without VQ | 2.55 | 22.09 |

- Their fixes bring distracted probe MSE back to 2.74: multi-step inverse dynamics, no quantisation,
  latent dimension 8192, prediction in latent space, augmentations (Fig. 5 and 6).
- Adding a small supervised action head during latent training (128 labelled trajectories out of
  5000) gives 0.44 normalised return. LAPO alone reaches about 0.10 (read from plot, Fig. 1).
- In leave-one-embodiment-out pretraining, nothing beat behaviour cloning from scratch (Fig. 10).

### 4. What carries a skill to another robot

Four representations have published evidence. They differ in what is shared and what is per robot.

**(a) Task-frame end-effector actions with per-robot inverse kinematics.**

```
Open X-Embodiment action:  a = [x, y, z, roll, pitch, yaw, gripper] (+ terminate), each dim -> 256 bins,
                           loss = categorical cross-entropy; frames NOT aligned across datasets
Mirage transfer:           p^_{t+1}^source = f_source(p_t, delta_a_t)      (per-dimension linear FDM in real runs)
                           target robot reaches p^_{t+1}^source with a blocking controller;
                           the target robot is inpainted out and the source robot rendered in ("cross-painting")
```

Open X-Embodiment says "the same action vector may induce very different motions for different
robots" ([v9](https://arxiv.org/abs/2310.08864)). Transfer was still positive between
robots in the training mix. RT-2-X showed 75.8 percent on WidowX-derived emergent skills on the
Google robot, against 27.3 percent for RT-2 (Table II, per-task trial counts not stated).

Mirage ([Chen et al., RSS 2024](https://arxiv.org/abs/2402.19249)) assumes "known isomorphic
kinematics" and full 6-DoF poses on both robots. It maps frames with a known rigid transform, which
"allows us to transfer between robots with different numbers of joints". Evidence:

- **Real Franka to UR5, zero target data** (per-cell trial counts not stated, Table IV):

  | Method | Four tasks on the UR5 |
  |---|---|
  | Mirage | 90 / 60 / 50 / 30 |
  | Diffusion Policy, no transfer method | 0 / 0 / 0 / 0 |
  | Octo | 0 / 0 / 0 / 0 |

- **Sim, deltas executed directly** with a non-blocking controller on UR5e: Square task 10 percent
  (Table VIII). Mirage's own wording is that "the difference in the forward dynamics between robots
  cannot be ignored".

Polybot ([Yang, Sadigh, Finn 2023](https://arxiv.org/abs/2307.03719)) shares a 7-D delta
end-effector action but keeps per-robot output heads. Trials are on a real WidowX, Franka and
Sawyer, 10 per cell (Tables 2 and 4):

| Condition | Success |
|---|---|
| 5-shot, pooled data | 0.7 to 1.0 across five scenarios |
| Shared action space with blocking controllers, pen in cup (needs rotation) | 0 on all three robots |

The authors explain the rotation failure: "variations in the length of the wrist link can lead to
large discrepancies in the radius of the rotation".

RoboCat is the closest published setup to a SCARA
([Bousmalis et al. 2023](https://arxiv.org/abs/2306.11706), App. C.1.1).

- **Action space.** Its real Sawyer runs "a 4-DoF end-effector Cartesian velocity control" plus
  gripper, "restricting the gripper to be oriented vertically (3D translation and 1D rotation along
  the vertical axis)". One model is shared with 6-DoF Cartesian arms.
- **Results** (100 evaluation episodes per task): stacking red on blue reached 80 percent (Table 1).
  A held-out Sawyer 4-DoF task went from 0 percent zero-shot to 82 percent with 100 human demos and
  88 percent with 500 (Table 3).
- **Gap.** No experiment isolates transfer between the 4-DoF and 6-DoF control modes.

Interactive Language drives an xArm6, a six-axis arm, with "the delta 2D cartesian setpoint of the
end effector" of a stick tool constrained to a plane
([Lynch et al. 2022](https://arxiv.org/abs/2210.06407)). A six-axis arm running a planar subset of
its pose space is an established configuration, not a hypothetical one.

Shadow ([Lepert, Doshi, Bohg 2025](https://arxiv.org/abs/2503.00774)) uses absolute Cartesian poses
and masks out the robot in images. It is "well suited to work with commonly used robots that have
parallel jaw grippers and full 6-DOF end-effector control". On a UR5e mug task with 25 rollouts,
calibration noise of 1 cm and 5 degrees gave 0.64 success, and 2 cm and 10 degrees gave 0.20
(App. A.4).

**(b) Embodiment-conditioned models: per-robot heads, stems or tokens.**

```
HPT:          min sum_k E_{(o, a) ~ D_k} Huber_{0.1}( head_k( trunk( stem_k(o) ) ), a_normalised )
CrossFormer:  L1( head_type(readout tokens), a_{t:t+c} ),  head_type in {single-arm 7-D EE delta, bimanual 14-D joints, nav 2-D, quadruped 12-D}
RDT-1B:       one 128-D physical-unit vector with fixed slots (joint pos 0-9, EE pos 30-32, EE 6-D rot 33-38, ...),
              unused slots zero-padded and flagged by a 0/1 availability mask
```

- stem_k / head_k: small per-embodiment input and output modules.
- trunk: shared transformer.
- RDT: "For a robot arm with only 6 DoF, its joint positions will be filled in the first 6 of the
  10 corresponding positions" ([Liu et al. 2024](https://arxiv.org/abs/2410.07864)).

Evidence:

- **Octo, new head per robot** ([Octo Model Team 2024](https://arxiv.org/abs/2405.12213), Table I).
  With about 100 demos and full fine-tuning under 5 h on one A5000, the average over six real
  setups was 72 percent against 20 from scratch. Setups included a joint-position action space and
  a 14-D ALOHA; 20 trials per domain, 10 for bimanual.
- **CrossFormer** (Table 3). 116 real trials averaged 0.73 against 0.68 for single-robot models. The
  authors report no significant cross-embodiment transfer.
- **HPT** ([Wang et al. 2024](https://arxiv.org/abs/2409.20537), Table 3). On a real Franka sweep
  task with 15 trials, the fine-tuned XL model scored 76.7 ± 3.3 against 43.3 ± 3.8 from scratch.
  Every real transfer target is a Franka.
- **RoboCat zero-shot on a new action space.** The 14-D KUKA with a three-finger hand scored 0
  percent zero-shot and 69 percent after fine-tuning (Table 3).

**(c) Shared latent with per-robot encoders and decoders.**

```
Devin et al. 2017:  pi(a | o) = f_robot( g_task(o_task), o_robot )           (guided policy search, sim)
Hejna et al. 2020:  high level outputs an x-y subgoal delta; per-morphology low level outputs torques (SAC)
Wang et al. 2024:   per-robot state/action encoders and decoders around a 4-D latent state and 4-D latent action,
                    aligned from unpaired data with adversarial + cycle-consistency + latent-dynamics losses
LAD 2025:           per-end-effector MLP encoders into a 16-D latent, pairwise InfoNCE across embodiments,
                    then diffusion policy over [latent end-effector action, explicit wrist pose]
```

- **Devin et al.** ([arXiv 1609.07088](https://arxiv.org/abs/1609.07088)) composed a held-out
  4-link arm with a reaching task in simulation. Distance was 0.08 to 0.28 against 1.16 to 1.35 for
  a random network, units not stated (Table I).
- **Hejna et al.** ([ICML 2020](https://arxiv.org/abs/2003.01709)), simulation, 5 seeds by 100
  episodes:
  - Transfer works only "where all agents can similarly cover the task state space".
  - The 2-link arm "was unable to complete [PegInsert] due to its limited range of motion".
  - Zero-shot Block Push with a 4-link low level scored 0.89 under its own high level and 0.24
    under a high level from PointMass.
- **Wang et al.** ([arXiv 2406.01968](https://arxiv.org/abs/2406.01968), Table III), simulated
  Panda to a real xArm6 with joint-velocity actions, 10 episodes:
  - Lift: 70 percent success, 20 percent collisions.
  - PickPlace: 60 percent success.
- **Latent Action Diffusion** ([Bauer et al., ICRA 2026](https://arxiv.org/abs/2506.14608),
  Fig. 3):
  - Only the end effector goes through the latent. The Franka arm is the same in every condition.
  - Co-training improved by "up to 25.3% (average 13.4%)".
  - On pick-place with the Franka gripper, co-training made it worse: place 16.6 to 11.1 percent,
    25 trials.
  - Values are read from figure labels, and bar order is assumed.

**(d) Object-centric flow as the shared interface.**

```
Track2Act:     2-D point tracks -> lift with depth -> per-step rigid SE(3) of the object via PnP -> apply to grasp pose -> IK
3DFlowAction:  3-D object flow from a video world model -> optimise EE poses in SE(3) to follow flow keypoints, with IK and collision checks
```

- **3DFlowAction** ([Zhi et al. 2025](https://arxiv.org/abs/2506.06199), Table 2) is the one case run
  on two different real arms with no robot-specific training: Franka 67.5 percent and Dobot
  XTrainer 70.0 percent, 40 trials each. The rigid object-gripper assumption holds during placing.
- **Im2Flow2Act** ([Xu et al., CoRL 2024](https://arxiv.org/abs/2407.15208)) reached 95 / 80 / 90 /
  70 percent over four tasks on a real UR5e from human video, 20 trials each. It states 2-D flow
  "struggles with tasks involving out-of-plane rotation", and it needs play data from each robot.
- **Track2Act** ([Bharadhwaj et al., ECCV 2024](https://arxiv.org/abs/2405.01527)) lists "trying to
  execute a non-feasible motion" among its failures. Its rigid-transform lift cannot represent a
  deformable object.
- **Tang et al.** ([arXiv 2409.10032](https://arxiv.org/abs/2409.10032)) had to move the robot base
  "due to the lack of support for inverse kinematics".

### 5. Composition, interpolation and planning in latent space

The composition operators in MCP (weighted product), Hausman et al. (interpolation of z) and He et
al. (MPC over z) are analysed in
[policy-composition-latent-skills](../papers/policy-composition-latent-skills.md). The additions
here are arithmetic, planning over quantised trajectories, and hardware interpolation.

**Arithmetic: Compositional Plan Vectors** ([Devin et al., NeurIPS 2019](https://arxiv.org/abs/1910.14033)).

```
policy:        pi_theta( a_t | o_t, g(o^ref_0, o^ref_T) - g(o_0, o_t) )
L_IL   = sum_i sum_t - log pi_theta( a^i_t | o^i_t, g(ref_i) - g(o^i_0, o^i_t) )
L_Hom  = sum_i sum_t l_tri( g(o^i_0, o^i_t) + g(o^i_t, o^i_T),  g(o^i_0, o^i_T),  g(o^j_0, o^j_T) )
L_Pair = sum_i sum_t l_tri( g(o^i_0, o^i_T),  g(ref_i),  g(ref_j) )
l_tri(a, p, n) = max( ||a - p||_2 - ||a - n||_2 + 1, 0 )
composition:   condition on g(ref_A) + g(ref_B); success requires both tasks done
```

- g: trajectory encoder. Subtraction measures remaining work, and addition composes tasks.
- Addition is commutative, so the plan vector cannot encode task order (Sec. 3).

Crafting grid world in simulation, 3 seeds (Table 1):

| Setting | Success |
|---|---|
| One-shot, 4 skills | 73 ± 2 |
| 1+1 addition | 76 ± 3 |
| 4,4 addition | 30 ± 10 |
| Without the homomorphism loss, 1+1 addition | 2 ± 3 |

Simulated pick and place (Table 2): adding two 1-skill vectors scored 56 ± 6 against 54 ± 4 for a
direct 2-skill reference.

**Planning over quantised trajectories: TAP** ([Jiang et al., ICLR 2023](https://arxiv.org/abs/2208.10291)).

```
score(s_1, z_1..z_M) = sum_t gamma^t r^_t + gamma^T R^_T + alpha * ln min( p(z_1..z_M | s_1), beta^M )     (Eq. 3)
```

- z_i: VQ codes, each covering L = 3 steps.
- p: autoregressive prior.
- beta = 0.05 penalises out-of-distribution code sequences.
- Search is beam search in code space.
- Only the first decoded action is executed.

Simulated D4RL, 5 seeds by 20 episodes (Sec. 4.3 and the ablations):

| Result | Value |
|---|---|
| Adroit mean | TAP 51.9; CQL 40.3; Trajectory Transformer 20.1 |
| Planning time at horizon 15 | under 0.05 s; Trajectory Transformer 32 s on Adroit-pen |
| Uniform latent sampling instead of the prior | minus 37.9 percent |

**Q-learning over sampled latents: LDCQ** ([Venkatraman et al. 2023](https://arxiv.org/abs/2309.06599),
venue not stated in v1, ICLR 2024 unverified).

```
beta-VAE (Eq. 4):  E[ sum_{t<H} log pi_theta(a_t | s_t, z) ] - beta * KL( q(z | tau^H) || p_omega(z | s_0) ),   beta = 0.05
Q target (Eq. 8):  Q(s_t, z) <- r_{t:t+H} + gamma^H Q( s_{t+H}, argmax_{z_i ~ p_psi(z | s_{t+H})} Q(s_{t+H}, z_i) )
```

- p_psi: a latent diffusion prior.
- antmaze-large-diverse scored 57.7 ± 1.8, or 73.6 ± 1.3 for the goal-conditioned variant, against
  47.5 for IQL. Seed counts are not stated (Table 1).
- On a 1-D random walk whose data actions lie only in [-1, -0.8] and [0.8, 1], a Gaussian VAE prior
  sampled actions in between. BCQ with that prior averaged -66 reward, against -2.2 with the
  diffusion prior (App. D).

**Interpolation on a real robot** ([Julian et al. 2018](https://arxiv.org/abs/1809.10253), venue
not stated in v3, ISER 2018 unverified). Skills were trained in simulation and run on a real Sawyer
with joint-space control.

- **Reaching.** Linear interpolation z = lambda z_a + (1 - lambda) z_b produced a path between
  goals, qualitative only. The latent reaching midway between goals A and B lay "much closer to the
  latent vector for goal A than for goal B".
- **Box pushing.** The mean of two skill latents gave movement whose "magnitude and direction of
  block movement was not easily predictable". It "was not reliable for half of the synthetic goals
  we tried", with the number of goals not stated.

**Gating and selection.**

- MCP gates Gaussian primitives multiplicatively (existing note).
- UniAct selects one code per step with Gumbel-softmax (Sec. 3 above).
- EXTRACT splits the choice into a discrete skill id and a continuous argument, with a progress head
  for termination.
- LOTUS re-selects a skill index every step.

### 6. Failure modes

**Posterior collapse.**

```
ELBO = E_q[ log p(x | z) ] - KL( q(z | x) || p(z) ) <= log p(x)
collapse: q(z | x) = p(z) for all x, KL term = 0, decoder ignores z
```

Bowman et al. report that "most training runs with most hyperparameters yield models that
consistently set q(z|x) equal to the prior p(z)". Without KL annealing and word dropout, training
"reliably results in models with equivalent performance to the baseline RNNLM, and zero KL
divergence" ([arXiv 1511.06349](https://arxiv.org/abs/1511.06349), Sec. 3.1 and 4).

Robot evidence, all inferred from task success rather than a measured KL:

- **HULC.** A skill VAE on CALVIN in simulation, 3 seeds, 1000 chains. At beta = 0.01 it completed
  5 tasks in a row 28.3 percent of the time. At beta = 0.1 that fell to 16.2 percent, described as
  "an over-regularized model which learns to ignore the latent plans"
  ([Mees et al., RA-L 2022](https://arxiv.org/abs/2204.06252), Fig. 3).
- **ACT.** Removing the CVAE on human data dropped simulated success from 35.3 to 2 percent. On
  scripted data it "makes almost no difference" (seed count for this ablation not stated;
  [Zhao et al. 2023](https://arxiv.org/abs/2304.13705), Sec. VI-B). ACT decodes with z = 0 at test
  time.
- **Discrete versions of collapse:**
  - PRISE code separation fell from 72.42 to 14.53 (Sec. 1 above).
  - UniAct's straight-through estimator collapsed the codebook.
  - Offline CARML in OPAL's appendix "effectively uses only 6 skills as the other 4 skills had
    p(z)=0" ([Ajay et al.](https://arxiv.org/abs/2010.13611), App. F).

None of SPiRL, SkiLD, OPAL, CompILE, EXTRACT or QueST ablates beta.

**Non-identifiable latents.**

```
Locatello et al., Theorem 1: for d > 1 and factorised p(z), there exist infinitely many bijections f with
all partial derivatives nonzero such that z and f(z) have the same marginal, so p(x) cannot tell a
disentangled model from an entangled one.
```

- In a study of more than 12,000 models, the objective and the regularisation strength explained 59
  percent of disentanglement score variance, and "the rest is due to the random seed"
  ([Locatello et al., ICML 2019](https://arxiv.org/abs/1811.12359), Sec. 5.3).
- For skills, CompILE's codes came out location-specific while the tasks were object-specific.
- Every semantic claim in EXTRACT, LOTUS, LAPA and UniAct rests on visual inspection. UniAct found
  "at least 40%" of 256 codes consistent across robots by manual check.

**Latents that encode the wrong change.**

- **Camera motion.** LAPA's human-video codes encode it.
- **Distractors.** They raise probe MSE from 2.55 to 22.09 (Nikulin et al.).
- **Rotation and gripper.** IGOR latents predict position better than either.
- **Embodiment.** Conditioning on it helped villa-X only modestly, from 0.165 to 0.152 probe loss.
- **Static skills.** MI discovery prefers them (LSD, METRA).

**Latents between modes.**

- LDCQ's Gaussian prior sampled actions absent from the data (-66 against -2.2).
- Julian et al.'s mean latent was unreliable for half the synthetic push goals.
- CPV addition fell from 76 to 30 as composed tasks lengthened.

**A latent with no contract.** Across the offline skill papers, no latent carries a learned
precondition or an explicit success detector:

- SPiRL, SkiLD and OPAL skills run a fixed H or c steps.
- CompILE trains a separate termination network.
- EXTRACT predicts progress.
- QueST and PRISE execute tokens open-loop for a fixed length.

## Evidence table

| Method | Data | Robot or sim | Key number | Trials | Source |
|---|---|---|---|---|---|
| SPiRL | 37k scripted stacking sequences, 75 percent random | Sim | 1.0 blocks stacked vs 1.5 best baseline on clean data | Seeds not stated (App. G) | [2010.11944](https://arxiv.org/abs/2010.11944) v1 Table 1 |
| OPAL | D4RL antmaze | Sim | 70.3 ± 2.9 vs CQL 14.9 ± 3.2 (large-diverse) | 4 seeds | [2010.13611](https://arxiv.org/abs/2010.13611) v3 Table 1 |
| OPAL | Same, latent dim 4 / 8 / 16 | Sim | 68.7 / 81.1 / 81.3 | 4 seeds | same, Table 5 |
| CompILE | Reacher demos | Sim | Segmentation 62.0 ± 4.5 (3 tasks), 41.7 ± 8.0 (5 tasks) | 5 runs | [1812.01483](https://arxiv.org/abs/1812.01483) v2 Table 1 |
| EXTRACT | 500 FurnitureBench demos + 100 RL episodes | Real Franka | 2.50 vs SPiRL 1.55 subtasks of 5 | 20 trials, 1 run | [2406.17768](https://arxiv.org/abs/2406.17768) v3 Table 1 |
| QueST | LIBERO-90 | Sim | 88.6 vs VQ-BeT 81.3 | 4 seeds × 40 per task | [2407.15840](https://arxiv.org/abs/2407.15840) v3 Fig. 2 |
| PRISE | LIBERO, Metaworld | Sim | Code separation 72.42 vs 14.53 without dynamics loss | 5000 states | [2402.10450](https://arxiv.org/abs/2402.10450) v3 Sec. 5.4 |
| off-DADS | Unsupervised, 300k samples, 20 h | Real D'Kitty | 2.17 ± 0.59 m per 10 s skill, 5 percent falls | 20 trials | [2004.12974](https://arxiv.org/abs/2004.12974) v1 Fig. 8 |
| LSD | Unsupervised | Sim point goal | Zero-shot 0.92 vs DIAYN 0.05 at range 80 | 8 runs | [2202.00914](https://arxiv.org/abs/2202.00914) v2 Table 2 |
| CSD | Unsupervised, 16 skills | Sim Kitchen | 10 of 13 tasks vs LSD 2, DIAYN 4, DADS 0 | 8 seeds | [2302.05103](https://arxiv.org/abs/2302.05103) v3 Fig. 7 |
| LSD / DADS / DIAYN on a Franka | Object prior | Sim | 0.17 / 0.06 / 0.00 on "Larger" | 3 seeds | [2410.04855](https://arxiv.org/abs/2410.04855) v1 Table I |
| Genie LAM + BC | CoinRun video, 200 labelled samples | Sim game | About 48.5 vs oracle about 54.5 (read from plot) | 5 seeds × 100 levels | [2402.15391](https://arxiv.org/abs/2402.15391) v1 Fig. 14 |
| LAPA | Bridge video latents, then 450 labelled demos | Real Franka (cross-embodiment) | 36.83 vs OpenVLA 30.76 | 54 rollouts | [2410.11758](https://arxiv.org/abs/2410.11758) v2 Table 16 |
| LAPA | Open-X latents, then 450 labelled demos | Real Franka | 50.09 vs OpenVLA 43.87 | 54 rollouts | same |
| LAPA | SSv2 human video | Real Franka | 34.02 vs scratch 21.22 | 54 rollouts | same |
| Moto | Open-X latents, 30 demos per task | Real FANUC LR Mate 200iD | 60 vs 23.33 without motion tokens | 10 per task × 3 | [2412.04445](https://arxiv.org/abs/2412.04445) v4 Fig. 8 |
| UniAct | 1M demos, 28 embodiments, 100 demos per interface | Real AIRBOT, unseen | Absolute joint 70.0 vs OpenVLA 2.5 (easy) | Not stated | [2501.10105](https://arxiv.org/abs/2501.10105) v2 Fig. 5 |
| villa-X | 1.6M robot + 3.6M human clips, 375 target trajectories | Real Realman RM75, unseen | Latent wins 5 of 7 tasks, loses 2 | 10 per task | [2507.23682](https://arxiv.org/abs/2507.23682) v3 Table 4 |
| GR00T N1 | RoboCasa generated video, 300 demos | Sim | LAPA latents 52.9 vs IDM labels 56.4 | 100 trials | [2503.14734](https://arxiv.org/abs/2503.14734) v2 Fig. 9 |
| CLAM | About 50k play + 5k labelled transitions | Real WidowX | Block 7/10 vs LAPA reimplementation 2/10 | 10 trials | [2505.04999](https://arxiv.org/abs/2505.04999) v2 Table III |
| LAPO under distractors | DCS, 5M transitions | Sim | Probe MSE 2.55 to 22.09 | 4 envs × 3 seeds | [2502.00379](https://arxiv.org/abs/2502.00379) v5 Fig. 5 |
| RT-2-X | Open X-Embodiment, 9 embodiments | Real Google robot | Emergent skills 75.8 vs 27.3 | Not stated per task | [2310.08864](https://arxiv.org/abs/2310.08864) v9 Table II |
| Octo, new head | About 100 demos per setup | Real, 6 setups | 72 vs scratch 20 average | 20 per domain (10 bimanual) | [2405.12213](https://arxiv.org/abs/2405.12213) v2 Table I |
| CrossFormer | 900k trajectories, 20 embodiments | Real, 4 robot types | 0.73 vs single-robot 0.68 | 116 total | [2408.11812](https://arxiv.org/abs/2408.11812) v1 Table 3 |
| HPT | Pretraining + fine-tuning | Real Franka | 76.7 ± 3.3 vs scratch 43.3 ± 3.8 | 15 trials | [2409.20537](https://arxiv.org/abs/2409.20537) v1 Table 3 |
| Polybot | Pooled data from 3 robots | Real WidowX, Franka, Sawyer | 5-shot 0.7 to 1.0; shared-action rotation task 0 | 10 per cell | [2307.03719](https://arxiv.org/abs/2307.03719) v1 Tables 2, 4 |
| Mirage | Franka source policy, no UR5 data | Real UR5 | 90 / 60 / 50 / 30 vs 0 / 0 / 0 / 0 | Not stated | [2402.19249](https://arxiv.org/abs/2402.19249) v3 Table IV |
| Mirage, direct deltas | Sim, non-blocking controller | Sim UR5e | Square 10 percent | Not stated | same, Table VIII |
| RoboCat | Sawyer 4-DoF vertical-gripper data | Real Sawyer | Held-out task 0 zero-shot, 82 with 100 demos | 100 episodes | [2306.11706](https://arxiv.org/abs/2306.11706) v2 Table 3 |
| Shadow | Absolute EE pose, calibration noise | Real UR5e | 0.64 at 1 cm / 5 deg, 0.20 at 2 cm / 10 deg | 25 rollouts | [2503.00774](https://arxiv.org/abs/2503.00774) v1 App. A.4 |
| Latent alignment | Unpaired data, sim Panda source | Real xArm6 | Lift 70, PickPlace 60 percent | 10 episodes | [2406.01968](https://arxiv.org/abs/2406.01968) v1 Table III |
| Latent Action Diffusion | Retargeted hand data, 4 end effectors | Real Franka | Up to +25.3; Franka gripper place 16.6 to 11.1 | 25 to 70 | [2506.14608](https://arxiv.org/abs/2506.14608) v4 Fig. 3 |
| Hejna et al. | Sim arms | Sim | Block Push 0.89 own high level vs 0.24 transferred | 5 seeds × 100 | [2003.01709](https://arxiv.org/abs/2003.01709) v2 |
| 3DFlowAction | Human and robot video, no robot training | Real Franka and Dobot XTrainer | 67.5 and 70.0 percent | 40 each | [2506.06199](https://arxiv.org/abs/2506.06199) v1 Table 2 |
| CPV | 40k crafting demos | Sim | Addition 1+1 76 ± 3; 4,4 30 ± 10; no homomorphism loss 2 ± 3 | 3 seeds | [1910.14033](https://arxiv.org/abs/1910.14033) v2 Table 1 |
| Play-LMP | Play data | Sim 8-DOF arm | 85.5 (states) vs BC 70.3 | 3 seeds | [1903.01973](https://arxiv.org/abs/1903.01973) v2 Fig. 6a |
| TAP | D4RL Adroit | Sim | 51.9 vs CQL 40.3; under 0.05 s per plan | 5 seeds × 20 | [2208.10291](https://arxiv.org/abs/2208.10291) v3 |
| Julian et al. interpolation | Sim-trained skill embedding | Real Sawyer | Mean latent unreliable on half the synthetic push goals | Not stated | [1809.10253](https://arxiv.org/abs/1809.10253) v3 |
| HULC beta | CALVIN | Sim | 28.3 (beta 0.01) vs 16.2 (beta 0.1) five in a row | 3 seeds, 1000 chains | [2204.06252](https://arxiv.org/abs/2204.06252) v2 Fig. 3 |
| Sentinel | Diffusion policy, Push Chair | Real Kinova Gen3 | TPR 1.00, TNR 0.90 | 20 rollouts | [2410.04640](https://arxiv.org/abs/2410.04640) v2 Table 2 |
| FAIL-Detect logpZO | Flow and diffusion policies | Real bimanual Franka | Top-1 in 8 of 12 hardware settings; 0.04 s per step vs STAC 1.45 s | 20 to 50 rollouts | [2503.08558](https://arxiv.org/abs/2503.08558) v3 |
| cVAE reconstruction monitor | iGibson kitchen tasks | Sim Fetch | Precision 85.8 to 100, recall 85.9 to 100 (expert data) | 3 seeds × 30 | [2112.05251](https://arxiv.org/abs/2112.05251) v1 Table 2 |

## Latent skills inside a contract-based skill library

A latent skill enters the library as one unit with one contract wrapped around the policy and its
decoder. Individual codes do not get contracts. The existing note reaches the same boundary for MCP
and skill embeddings
([policy-composition-latent-skills](../papers/policy-composition-latent-skills.md#how-the-four-relate)).
What can and cannot be written down for each field:

| Field | Can be written down | Cannot come from the latent | Candidate runtime check |
|---|---|---|---|
| Inputs | Observation schema with frame, units, timestamp and rate, the four fields every cell contract carries ([meat-cell-architecture](meat-cell-architecture.md#why-contracts-first)) | Units or meaning of z | Schema and frame-tag assertion at the seam |
| Preconditions | Explicit, checked outside the policy: object detected, pose in the task frame, belt speed inside the trained range, every target in the chunk inside this robot's reach set. Statistical: observation inside the training distribution | A precondition over z itself. A z between trained modes can decode to actions never seen in data (LDCQ App. D; Julian et al.) | IK feasibility per chunk; observation-density score with a conformal threshold (logpZO, 0.04 s per step on an A6000, [FAIL-Detect](https://arxiv.org/abs/2503.08558)); cVAE reconstruction error (simulation only, [Wong et al.](https://arxiv.org/abs/2112.05251)) |
| Outputs | The decoded action space, its frame, bounds and chunk period | Semantics of the code that produced it | Shield: workspace, speed and force limits (deterministic, never learned) |
| Success | A measured outcome from an independent sensor, e.g. object pose error below a bound | Nothing. The latent has no success test (Methods, Sec. 6) | Verification camera measurement after the skill |
| Failure | Timeout, shield rejection, monitor alarm, verification miss | A failure signature for a region of z | Action-distribution inconsistency between consecutive chunks (STAC: TPR 0.99, TNR 0.94 on a simulated task, 3 seeds; TPR 1.00, TNR 0.90 real with a VLM, 20 rollouts, [Sentinel](https://arxiv.org/abs/2410.04640)); progress head reaching 1 (EXTRACT) |
| Recovery | Owned by the supervisor: abort, retreat, re-observe, retry or reject | Any recovery behaviour inside the skill that can be guaranteed | Episode terminates with a reason code |

Three limits on those monitors come from the papers:

- **STAC cost.** It needs B sampled chunks per step: 1.45 s per step with 256 samples on an A6000
  ([FAIL-Detect](https://arxiv.org/abs/2503.08558)). That rules it out inside a 10 Hz loop.
- **Calibration data.** Sentinel calibrated on demonstrations instead of rollouts "led to a
  significant increase" in false positives.
- **Shortcuts.** FAIL-Detect's learned scores sometimes latched onto gripper state instead of vision.

One monitor is untested in any of these papers: the gap between the commanded z and an inference
network's estimate of z from the executed trajectory. The existing note proposes it for Hausman et
al.'s q_psi.

## Recipe for the pork-leg cell

**The task.** One learned reorientation skill for a bone-in pork leg on the belt, run on a SCARA
(x, y, z, yaw, tool axis always vertical) and a six-axis arm. No published paper runs one learned
skill on a SCARA and a six-axis arm. Every recommendation below is assembled from the nearest
evidence, and each prediction is marked as mine.

**Step 1: define the skill on the intersection of what both arms can do.**

- **What both arms can do.** The SCARA has no tilt axis. It also cannot pivot a gripped leg about its
  wrist: a 12.7 kg, 0.9 m leg gripped at the hock is about 1.78 kg m² about the wrist, against
  SCARA R-axis maxima of 0.45 to 1.0 kg m² in the 20 kg class
  ([arm-selection-scara-vs-six-axis](arm-selection-scara-vs-six-axis.md#3-payload-arithmetic-and-why-inertia-binds-long-before-mass-does)).
  So the shared skill is planar: push or nudge the leg on the belt with a vertical tool.
- **Six-axis mode.** The six-axis arm runs the same skill with roll and pitch locked. A reorientation
  that needs tilt or grasp-and-pivot is a separate six-axis-only skill with its own contract.
- **Why the intersection.** Hejna et al. found transfer holds only "where all agents can similarly
  cover the task state space" ([ICML 2020](https://arxiv.org/abs/2003.01709)). The shared skill's
  workspace is the intersection of both reach sets. Its z range fits the shorter vertical stroke:
  180 to 420 mm on SCARAs, per the arm note.
- **Why the policy is closed-loop.** Point pushing is not repeatable even on engineered surfaces.
  2000 identical 150 mm pushes spread by 3.4 to 11.7 mm and 1.3 to 4.5 degrees standard deviation
  ([Yu et al. 2016](https://arxiv.org/abs/1604.04038), Table IV). The skill has to re-observe and
  correct.

**Step 2: action representation. Absolute task-frame targets, with a deterministic per-robot
decoder.**

```
action chunk element (belt frame, moves with the encoder count):
  x_m, y_m     TCP target in the belt plane
  z_m          TCP height above the belt surface, inside the smaller Z stroke
  yaw_rad      tool rotation about the belt normal
  no roll or pitch: the tool axis is along the belt normal on both robots
chunk: k absolute targets at a fixed period (positions, not velocities, not deltas)
decoder, per robot, not learned: IK -> jerk-limited filter -> vendor driver; any target outside
  this robot's reach set rejects the whole chunk before execution
```

Why this representation:

- **The frame.** The belt frame makes the leg quasi-static in the policy's coordinates and keeps
  belt speed out of the learned part
  ([conveyor-tracking-and-visual-servoing](conveyor-tracking-and-visual-servoing.md#visual-servoing)).
- **Absolute targets, not deltas.** Mirage's direct-delta run fell to 10 percent on a precision
  task, and its fix is an absolute target reached by a blocking controller
  ([Chen et al. 2024](https://arxiv.org/abs/2402.19249), Table VIII).
- **Positions, not velocities.** Diffusion Policy with position control consistently beat velocity
  control ([Chi et al. 2023](https://arxiv.org/abs/2303.04137), Sec. 4.3).
- **The 4-DoF subset.** It is the action space RoboCat already runs on a real Sawyer (80 percent
  stacking, 100 episodes). A six-axis xArm6 running a constrained planar subset is how Language Table
  data was collected ([Lynch et al. 2022](https://arxiv.org/abs/2210.06407)).
- **Where yaw pivots.** Define yaw about the TCP at the contact point, not the flange. Polybot's
  rotation failure came from different wrist-link lengths changing the rotation radius
  ([Yang et al. 2023](https://arxiv.org/abs/2307.03719)). Calibrate both TCPs against the same
  fixture before any transfer trial: Shadow lost success from 0.64 to 0.20 when calibration error
  went from 1 cm / 5 deg to 2 cm / 10 deg.

**Step 3: robot-agnostic observations.**

```
leg_pose_belt:   (x_m, y_m, yaw_rad) plus keypoints (hock, trotter tip, ham end) in the belt frame, stamped at exposure
tcp_pose_belt:   (x_m, y_m, z_m, yaw_rad) from each robot's forward kinematics, same frame and stamp
contact_force_n: only if both arms carry the same F/T sensor model
embodiment_id:   one-hot {scara, six_axis}, fed only to a per-robot head (Step 4), absent from the base policy
```

- **Keep the arm out of the image.** Use a fixed overhead camera and pass pose features, not wrist
  images with the arm in them.
- **Why.** Mirage and Shadow need inpainting because image-based policies see the arm and fail when
  it changes. Octo with no alignment scored 0 in all four tasks on an unseen UR5 (Mirage Table IV).
  Octo also found proprioception inputs made policies "generally worse". If proprioception hurts
  here, drop tcp_pose_belt and keep leg_pose_belt.

**Step 4: where a latent belongs, and where it does not.**

- **Inside the skill, as the generative action head** over the task-frame chunk. Push demos at the
  hock and at the ham end are two modes, and a unimodal regressor averages them. An ACT-style CVAE
  mattered on human data (35.3 against 2 percent without it). A quantised head such as VQ-BeT or
  QueST FSQ is the alternative with fewer collapse knobs.
- **Collapse check.** Log KL per dimension during training. HULC lost 12 points by moving beta from
  0.01 to 0.1.
- **Not as the cross-robot interface.** A shared learned latent with per-robot decoders has thin
  real evidence: 70 and 60 percent over 10 episodes for sim Panda to xArm6 (Wang et al.). LAD kept
  the arm explicit and identical. Neither compares against an aligned task-frame action on the same
  robots.
- **An embodiment token or per-robot head, only after the zero-shot test fails.** It is there to
  absorb tracking lag and dynamics the IK decoder does not. The published budget is about 100 demos
  per new head (Octo, 72 percent average over six real setups).
- **Not from unsupervised discovery.** No MI or metric discovery method has real manipulator results
  with trial counts, and on a simulated Franka they reached 0.00 to 0.17.
- **Latent action pretraining from line video: later, and only in the belt frame.** The belt moves
  every background pixel, which is the distractor case that took probe MSE from 2.55 to 22.09
  (Nikulin et al.). The prediction that camera-frame codes on a belt would encode belt motion is
  mine, untested. If tried: belt-stabilised crops, a supervised action head on a few labelled
  trajectories (LAOM plus supervision), and a comparison against behaviour cloning from scratch,
  which won in their cross-embodiment test.

**Step 5: experiments, sim first.**

Write the protocol before the first trial ([policy-evaluation](policy-evaluation.md),
[sim-first-workflow](sim-first-workflow.md)). The success criterion is the leg pose error at the end
of the skill against the target: lateral offset under 5 mm and yaw under 5 degrees, the bound
pre-registered for the deformable product until the cutter window replaces it
([meat-cell-architecture](meat-cell-architecture.md#the-subsystems)). Use at least 20 trials per arm
per condition, the floor in [imitation-learning](imitation-learning.md), reported as k/N with an
interval.

| Condition | Demos | Policy | What it tests | My prediction from the evidence |
|---|---|---|---|---|
| A | Pooled from both arms, same action spec | One policy, no embodiment id | Main hypothesis | On the six-axis, close to C |
| B | As A, plus about 100 per arm | Per-robot head or embodiment id | Whether residual dynamics need conditioning | Helps only if A shows a per-robot gap |
| C | Per arm | Joint-space actions, one policy per arm | Baseline without transfer | Upper bound on each arm, zero transfer |
| D | Six-axis in 4-DoF mode only | One policy, zero-shot to SCARA | Pure transfer | Below A on the SCARA if tracking dynamics differ (Mirage direct-delta result) |
| E | Pooled | Shared learned latent, per-robot learned decoders | Option (c) against option (a) | Not better than A; no published head-to-head |

Log on every trial:

- the commanded and executed TCP path in the belt frame;
- the logpZO-style observation score and the chunk-to-chunk action inconsistency;
- the verification camera pose.

These logs calibrate the contract monitors from real rollouts rather than demos, per Sentinel's
finding.

## Gotchas

- **An unaligned action vector gives zero transfer to an unseen arm.** Octo scored 0 in all four
  real tasks on a UR5 it was not trained on
  ([Mirage](https://arxiv.org/abs/2402.19249), Table IV).
- **Executing another robot's deltas directly fails on precision tasks.** Mirage's Square task fell
  to 10 percent on a simulated UR5e until a forward-dynamics model and blocking controller were
  added (Table VIII).
- **A shared delta action loses rotations across wrist geometries.** Polybot's pen-in-cup task
  scored 0 on all three robots with a shared action space
  ([Yang et al.](https://arxiv.org/abs/2307.03719), Table 4).
- **Calibration error dominates absolute-pose transfer.** 2 cm and 10 degrees took Shadow from 0.64
  to 0.20 on a real UR5e ([Lepert et al.](https://arxiv.org/abs/2503.00774), App. A.4).
- **Beta too high and the decoder ignores the plan.** HULC dropped from 28.3 to 16.2 percent at
  beta 0.1 ([Mees et al.](https://arxiv.org/abs/2204.06252), Fig. 3).
- **Codes collapse without a term that forces them to mean different dynamics.** PRISE's code
  separation fell from 72.42 to 14.53 without its forward-dynamics loss
  ([Zheng et al.](https://arxiv.org/abs/2402.10450), Sec. 5.4).
- **Straight-through quantisation collapsed UniAct's codebook.** They switched to Gumbel-softmax
  ([Zheng et al. 2025](https://arxiv.org/abs/2501.10105), App. A).
- **Vector arithmetic needs a loss that makes it valid.** CPV addition scored 2 ± 3 without the
  homomorphism loss ([Devin et al.](https://arxiv.org/abs/1910.14033), Table 1).
- **Averaging two push latents does not average two pushes.** It was unreliable on half the
  synthetic goals on a real Sawyer ([Julian et al.](https://arxiv.org/abs/1809.10253)).
- **Latent actions learned from video absorb background and camera motion.** Probe MSE rose from
  2.55 to 22.09 under distractors ([Nikulin et al.](https://arxiv.org/abs/2502.00379)). LAPA codes
  moved the camera ([Ye et al.](https://arxiv.org/abs/2410.11758), App. E).
- **MI skill discovery on an arm ignores or throws the object.** DADS skills "collapse to either
  ignoring the object or moving it along a fixed path"; LSD throws it
  ([Jansonnie et al.](https://arxiv.org/abs/2410.04855), Sec. VI-A).
- **Unsupervised skill learning on hardware wears the robot.** off-DADS needed motor replacements,
  and its reset detector gave false positives
  ([Sharma et al. 2020](https://arxiv.org/abs/2004.12974), Sec. V-F).
- **Automatic KL tuning was unstable in EXTRACT.** The authors fixed the weights by hand
  ([Zhang et al.](https://arxiv.org/abs/2406.17768)).
- **Monitors calibrated on demos over-alarm.** Sentinel calibrated on demonstrations "led to a
  significant increase" in false positives ([Agia et al.](https://arxiv.org/abs/2410.04640), C.1).
  Learned failure scores latched onto gripper state
  ([Xu et al.](https://arxiv.org/abs/2503.08558)).
- **A morphology that cannot reach a state cannot run the transferred skill.** Hejna's 2-link arm
  could not do PegInsert ([Hejna et al.](https://arxiv.org/abs/2003.01709)).

## Open questions

- **4-DoF and 6-DoF transfer.** How much transfers between a 4-DoF vertical-tool control mode and
  6-DoF Cartesian control within one policy. RoboCat trained both, but no experiment isolates it.
- **Deformable pushing across arms.** Whether a push-reorientation policy on a deformable leg keeps
  its success when SCARA and six-axis tracking lag differ at belt speed. No published data on
  deformables on a moving belt for any of the representations above.
- **Collapse on repetitive data.** Whether a CVAE or FSQ head collapses on push demos that are
  nearly unimodal. OPAL predicts the latent is ignored when one stationary policy explains the data.
- **Observation frame.** Whether the leg frame, not the belt frame, is the better frame for
  observations, giving invariance to where the leg lies. No paper read tests object-frame against
  task-frame observations for pushing.
- **Consistency monitors in the control loop.** Whether STAC-style consistency can run inside the
  loop with fewer samples, or whether only density scores such as logpZO fit the latency budget.
- **Unverified venues.** Open X-Embodiment (ICRA 2024), CrossFormer (CoRL 2024), ATM (RSS 2024),
  RDT-1B (ICLR 2025), RoboCat (TMLR), LDCQ (ICLR 2024), FAIL-Detect (RSS 2025), Julian et al. (ISER
  2018), Bowman et al. (CoNLL 2016). QueST's publication status is also unverified.

## Related

- [policy-composition-latent-skills](../papers/policy-composition-latent-skills.md): MCP, Hausman 2018, He 2018, Xu 2023, and the contract tension
- [policy-composition-primitives-controllers-diffusion](../papers/policy-composition-primitives-controllers-diffusion.md), [policy-composition-energy-products](../papers/policy-composition-energy-products.md)
- [lee-2024-vq-bet](../papers/lee-2024-vq-bet.md), [zhao-2023-aloha-act](../papers/zhao-2023-aloha-act.md), [imitation-learning](imitation-learning.md)
- [open-x-embodiment-collaboration-2023-rt-x](../papers/open-x-embodiment-collaboration-2023-rt-x.md), [octo-model-team-2024-octo](../papers/octo-model-team-2024-octo.md), [vision-language-action-models](vision-language-action-models.md)
- [arm-selection-scara-vs-six-axis](arm-selection-scara-vs-six-axis.md), [conveyor-tracking-and-visual-servoing](conveyor-tracking-and-visual-servoing.md), [meat-cell-architecture](meat-cell-architecture.md), [control-architecture-selection](control-architecture-selection.md)
- [deformable-object-manipulation](deformable-object-manipulation.md), [policy-evaluation](policy-evaluation.md), [safety-for-learned-policies](safety-for-learned-policies.md), [sim-to-real](sim-to-real.md), [sim-first-workflow](sim-first-workflow.md)

## Sources

Skill priors and skill spaces:

- Pertsch, Lee, Lim, SPiRL, CoRL 2020: https://arxiv.org/abs/2010.11944
- Pertsch, Lee, Wu, Lim, SkiLD, CoRL 2021: https://arxiv.org/abs/2107.10253
- Ajay, Kumar, Agrawal, Levine, Nachum, OPAL, ICLR 2021: https://arxiv.org/abs/2010.13611
- Kipf et al., CompILE, ICML 2019: https://arxiv.org/abs/1812.01483
- Zhang et al., EXTRACT, CoRL 2024: https://arxiv.org/abs/2406.17768
- Mete et al., QueST, 2024: https://arxiv.org/abs/2407.15840
- Zheng et al., PRISE, ICML 2024: https://arxiv.org/abs/2402.10450
- Wan, Zhu, Shah, Zhu, LOTUS, ICRA 2024: https://arxiv.org/abs/2311.02058

Unsupervised skill discovery:

- Eysenbach, Gupta, Ibarz, Levine, DIAYN, ICLR 2019: https://arxiv.org/abs/1802.06070
- Sharma, Gu, Levine, Kumar, Hausman, DADS, ICLR 2020: https://arxiv.org/abs/1907.01657
- Sharma, Ahn, Levine, Kumar, Hausman, Gu, off-DADS, RSS 2020: https://arxiv.org/abs/2004.12974
- Park, Choi, Kim, Lee, Kim, LSD, ICLR 2022: https://arxiv.org/abs/2202.00914
- Park, Lee, Lee, Abbeel, CSD, ICML 2023: https://arxiv.org/abs/2302.05103
- Park, Rybkin, Levine, METRA, ICLR 2024: https://arxiv.org/abs/2310.08887
- Cho, Kim, Kim, transferable manipulation skill discovery, RA-L 2022: https://arxiv.org/abs/2204.13906
- Jansonnie, Wu, Perez, Peters, 2024: https://arxiv.org/abs/2410.04855
- Atanassov et al., constrained skill discovery, 2024: https://arxiv.org/abs/2410.07877

Latent actions:

- Bruce et al., Genie, 2024: https://arxiv.org/abs/2402.15391
- Ye et al., LAPA, ICLR 2025: https://arxiv.org/abs/2410.11758
- Chen et al., IGOR, 2024: https://arxiv.org/abs/2411.00785
- Chen et al., Moto, 2024: https://arxiv.org/abs/2412.04445
- Zheng et al., UniAct, 2025: https://arxiv.org/abs/2501.10105
- NVIDIA, GR00T N1, 2025: https://arxiv.org/abs/2503.14734
- Chen et al., villa-X, 2025: https://arxiv.org/abs/2507.23682
- Liang et al., CLAM, 2025: https://arxiv.org/abs/2505.04999
- Nikulin et al., Latent action learning requires supervision in the presence of distractors, ICML 2025: https://arxiv.org/abs/2502.00379
- Lee et al., VQ-BeT, ICML 2024: https://arxiv.org/abs/2403.03181

Cross-embodiment:

- Open X-Embodiment Collaboration, RT-X: https://arxiv.org/abs/2310.08864
- Octo Model Team, Octo: https://arxiv.org/abs/2405.12213
- Doshi, Walke, Mees, Dasari, Levine, CrossFormer: https://arxiv.org/abs/2408.11812
- Wang, Chen, Zhao, He, HPT: https://arxiv.org/abs/2409.20537
- Liu et al., RDT-1B: https://arxiv.org/abs/2410.07864
- Bousmalis et al., RoboCat: https://arxiv.org/abs/2306.11706
- Lynch et al., Interactive Language: https://arxiv.org/abs/2210.06407
- Yang, Sadigh, Finn, Polybot: https://arxiv.org/abs/2307.03719
- Chen et al., Mirage, RSS 2024: https://arxiv.org/abs/2402.19249
- Lepert, Doshi, Bohg, Shadow: https://arxiv.org/abs/2503.00774
- Wang, Bhatt, Wang, Atanasov, cross-embodiment skill transfer by latent space alignment: https://arxiv.org/abs/2406.01968
- Bauer, Nava, Katzschmann, Latent Action Diffusion, ICRA 2026: https://arxiv.org/abs/2506.14608
- Devin et al., modular policies for multi-robot transfer: https://arxiv.org/abs/1609.07088
- Hejna, Abbeel, Pinto, hierarchically decoupled imitation for morphological transfer, ICML 2020: https://arxiv.org/abs/2003.01709
- Xu et al., Im2Flow2Act, CoRL 2024: https://arxiv.org/abs/2407.15208
- Wen et al., ATM: https://arxiv.org/abs/2401.00025
- Bharadhwaj, Mottaghi, Gupta, Tulsiani, Track2Act, ECCV 2024: https://arxiv.org/abs/2405.01527
- Zhi et al., 3DFlowAction: https://arxiv.org/abs/2506.06199
- Tang et al., embodiment-agnostic action planning via object-part scene flow: https://arxiv.org/abs/2409.10032
- Xu et al., XSkill: https://arxiv.org/abs/2307.09955
- Kim et al., UniSkill, CoRL 2025: https://arxiv.org/abs/2505.08787
- Parakh et al., AnyBody: https://arxiv.org/abs/2505.14986

Composition and planning:

- Devin, Geng, Abbeel, Darrell, Levine, Compositional Plan Vectors, NeurIPS 2019: https://arxiv.org/abs/1910.14033
- Lynch et al., Learning Latent Plans from Play, CoRL 2019: https://arxiv.org/abs/1903.01973
- Jiang et al., TAP, ICLR 2023: https://arxiv.org/abs/2208.10291
- Venkatraman et al., LDCQ: https://arxiv.org/abs/2309.06599
- Julian et al., composable robot skills sim-to-real: https://arxiv.org/abs/1809.10253

Failure modes and monitors:

- Bowman et al., Generating sentences from a continuous space: https://arxiv.org/abs/1511.06349
- Locatello et al., Challenging common assumptions in unsupervised disentanglement, ICML 2019: https://arxiv.org/abs/1811.12359
- Mees, Hermann, Burgard, HULC, RA-L 2022: https://arxiv.org/abs/2204.06252
- Zhao, Kumar, Levine, Finn, ACT, RSS 2023: https://arxiv.org/abs/2304.13705
- Agia et al., Sentinel, CoRL 2024: https://arxiv.org/abs/2410.04640
- Xu et al., FAIL-Detect: https://arxiv.org/abs/2503.08558
- Wong et al., error-aware imitation learning, CoRL 2021: https://arxiv.org/abs/2112.05251

Cell context:

- Yu, Bauza, Fazeli, Rodriguez, More than a million ways to be pushed, IROS 2016: https://arxiv.org/abs/1604.04038
- Chi et al., Diffusion Policy, 2023: https://arxiv.org/abs/2303.04137
