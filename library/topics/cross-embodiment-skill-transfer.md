---
title: "Cross-embodiment skill transfer: one learned leg reorientation on a SCARA and a six-axis arm"
date: 2026-09-15
tags: [topic, cross-embodiment, transformers, attention, action-representation, scara, six-axis, mujoco, skill-library, imitation-learning, meat-cell, demo]
status: draft
source:
  - https://arxiv.org/abs/1706.03762
  - https://arxiv.org/abs/2310.08864
  - https://arxiv.org/abs/2405.12213
  - https://arxiv.org/abs/2408.11812
  - https://arxiv.org/abs/2409.20537
  - https://arxiv.org/abs/2410.24164
  - https://arxiv.org/abs/1609.07088
  - https://arxiv.org/abs/2307.03719
  - https://arxiv.org/abs/2203.11931
  - https://arxiv.org/abs/2402.19249
  - https://arxiv.org/abs/2409.03403
  - https://arxiv.org/abs/2503.00774
  - https://arxiv.org/abs/2402.10329
  - https://arxiv.org/abs/2409.15585
  - https://arxiv.org/abs/2606.22836
  - https://arxiv.org/abs/2506.14608
  - https://github.com/kevinzakka/mink
  - https://mujoco.readthedocs.io/en/stable/programming/simulation.html
  - local code, src/meat_cell_sim and src/skill_library, read 2026-09-15
---

# Cross-embodiment skill transfer: one learned leg reorientation on a SCARA and a six-axis arm

Versions read, in full unless marked: Vaswani et al. v7; Octo v2; pi0 v4; UMI v3; CrossFormer v1;
HPT v1; Devin et al. v1; Polybot v1; MetaMorph v1; Mirage v3; RoVi-Aug v2; Shadow v1; XMoP v2
(tables checked). Cloak v1 and Latent Action Diffusion v4 were read at abstract level only. UniAct,
X-VLA, GR00T N1, RDT-1B, "Data Analogies" and "Embedding Morphology into Transformers" were read
through a summarising fetch tool, so their numbers carry "(unverified)". RT-X and Octo facts not
restated here are in their paper entries, read 2026-09-05.

## What it is

A policy trained on data from one set of bodies is run on a body whose kinematics, degrees of
freedom, actuation or sensors differ. Three things can be shared across the bodies: the network
weights, the action space the weights emit, and a latent space between a per-robot encoder and a
per-robot decoder. Published work falls into three claims that are easy to confuse:

1. **Co-training, evaluated on robots seen in training.** One model on many robots' data (RT-X,
   Octo pretraining, CrossFormer, pi0). The claim is that pooling does not hurt, or helps, each
   robot in the mix.
2. **Adaptation with new per-robot modules.** A pretrained trunk, a new stem or head trained on
   target-robot demos (HPT, Octo's new heads, Polybot, UniAct). The claim is fewer target demos.
3. **Zero-shot to a held-out robot.** The same checkpoint on a robot with no data in training
   (UMI's Franka run, Mirage, RoVi-Aug, Shadow, CrossFormer's quadcopter, Cloak, XMoP). The claim
   is that the skill survives the body change.

The Wednesday demo (plan (`plan/wednesday-2026-09-16.md`), proof of concept) makes claim 3:
one learned reorientation skill, one checkpoint, a FANUC SR-20iA (x, y, z, yaw; tool always
vertical) and a UR20. Everything in this note is organised around what makes that claim true and
what makes it hollow.

## Why it matters in the field

The arm in a customer cell is often the customer's choice, and for this cell it is still open
([arm-selection-scara-vs-six-axis](arm-selection-scara-vs-six-axis.md)). A skill that has to be
re-demonstrated per arm is a cost per deployment. The published evidence on how much transfers is
thinner than the framing around it:

- RT-X found positive transfer from pooling 9 embodiments, most strongly for small datasets and the
  55B model, and RT-1-X underfit data-rich domains
  ([RT-X entry](../papers/open-x-embodiment-collaboration-2023-rt-x.md)).
- CrossFormer, 20 embodiments and 900K trajectories, states "Our results do not yet show
  significant positive transfer across embodiments" (Sec. 5); its gain is absorbing heterogeneous
  data "without negative transfer" ([Doshi et al. 2024](https://arxiv.org/abs/2408.11812)).
- pi0 trains on 7 robot configurations but never evaluates a robot held out of pretraining, and has
  no single-robot ablation of itself ([Black et al. 2024](https://arxiv.org/abs/2410.24164), Sec.
  V-C, VI-A; [entry](../papers/black-2024-pi0.md)).
- The strongest zero-shot numbers on real arms (UMI 18/20; RoVi-Aug 30 to 100 percent over 10
  trials per cell; Mirage 30 to 90 percent, trial count not stated) all come from expressing
  actions as end-effector poses and letting each robot's own controller reach them. None of those papers crosses a DOF gap where the target cannot reach
  a commanded orientation.

No paper found in this pass transfers a manipulation policy to a 4-DOF arm or a SCARA. The lowest
DOF case with numbers is a 5-joint SO-101 co-trained with a Panda in simulation, not held out
("Embedding Morphology into Transformers", arXiv 2603.00182, unverified). The demo is outside the
published envelope in that one respect, and the design below is shaped to make that gap small.

## Methods

### Attention, as far as this note needs it

Scaled dot-product attention, Eq. 1 of [Vaswani et al.](https://arxiv.org/abs/1706.03762) (v7,
Sec. 3.2.1), for queries and keys of dimension d_k:

```
Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k)) V

MultiHead(Q, K, V) = Concat(head_1, ..., head_h) W^O
head_i             = Attention(Q W^Q_i, K W^K_i, V W^V_i)
W^Q_i, W^K_i in R^(d_model x d_k),  W^V_i in R^(d_model x d_v),  W^O in R^(h d_v x d_model)
```

Self-attention and cross-attention differ only in where Q comes from. With X an (n x d_model)
token sequence and Y an (m x d_model) one:

```
self-attention:   Z = Attention(X W^Q, X W^K, X W^V)     # Z is n x d_v
cross-attention:  Z = Attention(Y W^Q, X W^K, X W^V)     # Z is m x d_v, one row per query in Y
```

Vaswani's decoder uses the second form with "the queries come from the previous decoder layer, and
the memory keys and values come from the output of the encoder" (Sec. 3.2.3). Illegal connections
are removed "by masking out (setting to -inf) all values in the input of the softmax" (same
section), which is written as an additive mask M:

```
Attention_M(Q, K, V) = softmax(Q K^T / sqrt(d_k) + M) V,    M_ij = 0 or -inf
```

Tokenising a robot. Octo turns language into 16 T5 tokens and each image into flattened patches
(256 tokens for the 256x256 third-person view, 64 for the 128x128 wrist view), adds learned
position embeddings, and inserts readout tokens that attend to observations but are attended by
nothing; a small diffusion head decodes an action chunk from the readout embeddings
([Octo v2](https://arxiv.org/abs/2405.12213), Sec. III-A; [entry](../papers/octo-model-team-2024-octo.md)).
HPT uses cross-attention as a compressor: 16 learnable query tokens attend to a proprioception
feature and 16 to ResNet-18 features, so every robot enters the shared trunk as a fixed 32 tokens
([Wang et al. v1](https://arxiv.org/abs/2409.20537), Sec. 3.1). CrossFormer emits actions through
readout tokens, one per action in the chunk, into one linear head per action type
([Doshi et al. v1](https://arxiv.org/abs/2408.11812), Sec. 3.3). pi0 routes the state and 50 noisy
action tokens through a separate 300M "action expert" that interacts with the VLM only through
self-attention under a block mask ([entry](../papers/black-2024-pi0.md)). Discrete action tokens
(RT-1, OpenVLA, FAST) are covered in
[vision-language-action-models](vision-language-action-models.md).

Why a transformer can take a variable robot description. Nothing in W^Q, W^K, W^V or W^O depends
on the number of tokens n: the same matrices apply to a sequence of 4 tokens or 8. Attention has
"no recurrence and no convolution", so order enters only through positional encodings (Vaswani,
Sec. 3.5), and a missing token is removed with M rather than by changing the architecture. That
is the mechanism every morphology-aware policy uses. MetaMorph gives each limb a token carrying a
morphology descriptor (limb shape, joint type, range, axis, gear) plus its proprioception,
serialises the kinematic tree depth-first, zero-pads to N tokens, adds learned position embeddings,
and decodes one action per joint, so the action length equals the robot's joint count
([Gupta et al. v1](https://arxiv.org/abs/2203.11931), Sec. 4.2, Appendix A.1). XMoP, a motion
planner over 8 link-pose tokens, handles a 6-DoF arm as "we mask out one pose-token and pass 0"
([XMoP v2](https://arxiv.org/html/2409.15585v2), Sec. III-B). Octo fully masks tokens of
non-existing observations (Sec. III-A). The mechanism admits variable bodies; it does not make a
policy generalise to them. MetaMorph's zero-shot score dropped about 75 percent when the node
order was reversed (Appendix B.3), and AnyBody reports 0 percent when extrapolating to an unseen
link structure on its push task (arXiv 2505.14986, unverified).

### Cross-embodiment approaches

**Shared weights, one coarsely aligned end-effector action (RT-X).** 60 datasets mapped to a 7-D
end-effector vector (x, y, z, roll, pitch, yaw, gripper) normalised per dataset, frames not aligned;
nothing per robot except de-normalisation
([entry](../papers/open-x-embodiment-collaboration-2023-rt-x.md)). The same token means different
motions on different robots.

**Shared trunk, per-embodiment input and output modules.** Octo adds a new head at fine-tuning
(14-D joint actions for ALOHA, 80 percent over 20 trials; ViperX, a robot not in pretraining, 100
percent) ([entry](../papers/octo-model-team-2024-octo.md)). CrossFormer: 130M parameters, one
backbone, one ResNet-26 encoder per observation type (not per robot), four heads: single-arm 7-D
end-effector delta chunk 4, navigation 2-D waypoint chunk 4, bimanual 14-D joints chunk 100,
quadruped 12-D joints chunk 1 (Sec. 3.3). HPT: per-embodiment stem and head, shared trunk of 3.1M
to 1.1B parameters, and transfer "reinitialize[s] the head and stem ... and freeze[s] the weights
of the trunk" (Sec. 3.3). GR00T N1 uses "an MLP per embodiment" into a shared embedding (arXiv
2503.14734, Sec. 2.1, unverified). UniAct decodes a shared 256-code action codebook with per-robot
MLP heads of about 4M of 500M parameters (arXiv 2501.10105, unverified). X-VLA gives each
embodiment learnable soft prompts, "only 0.04%" of parameters, on a common end-effector action of
xyz, 6-D rotation and gripper (arXiv 2510.10274, Sec. 4.2.2, unverified).

**Modular robot and task networks (Devin et al. 2017).** The policy is f_r(g_k(o_T), o_R): a task
module g_k shared across robots reads task observations (image, object positions), a robot module
f_r shared across tasks reads joint state and outputs torques, and the interface is an unsupervised
latent kept small and regularised with dropout; the paper gives neither the width nor the rate
([Devin et al. v1](https://arxiv.org/abs/1609.07088), Sec. III-B to III-D). The robots are 3-link,
3-link with different lengths, 4-link and 5-link arms in MuJoCo. It is the template for "shared
latent, per-robot decoder", and its own limitation is the practical one: "different task-robot
combinations [must] be trained simultaneously" (Sec. V).

**Shared encoder latent, per-robot action heads (Polybot).** Shared CNN encoder and trunk, three
robot-specific heads (WidowX 250S, Franka, Sawyer, all real), front-mounted wrist cameras to shrink
the view gap, a triplet loss aligning latents by end-effector pose, and a common delta-pose API
into each robot's controller with shared IK ([Yang, Sadigh, Finn v1](https://arxiv.org/abs/2307.03719),
Sec. 3). It separates heads because the achieved pose differs per robot even under the same IK.
"Our method is not able to transfer policies to a new robot with no demonstrations" (Sec. 6).

**Zero-padded unified vector.** pi0 pads state and action to 18 dims, "the largest robot in the
dataset", and masks missing cameras; no embodiment token exists in the paper (Sec. V-A). pi0.5
normalises actions to [-1, 1] by the 1st and 99th percentile per dataset and declares the control
mode in the prompt ([entry](../papers/physical-intelligence-2025-pi05.md)). RDT-1B places each
robot's quantities into named slots of a 128-D vector (arXiv 2410.07864, Sec. 4.2, unverified).

**Shared end-effector pose, per-robot controller, visual bridging.** Mirage keeps the source policy
unchanged, repaints the target robot as the source robot in the image ("cross-painting"), steps the
policy's action on the source robot's forward dynamics, and has the target's blocking controller
reach the resulting pose; its assumptions include "known isomorphic kinematics" and tasks both
robots "can perform using similar strategies" ([Chen et al. v3](https://arxiv.org/abs/2402.19249),
Sec. III, V). RoVi-Aug does the repainting offline with a diffusion model per robot pair and trains
one policy on absolute end-effector actions ([v2](https://arxiv.org/abs/2409.03403)). Shadow
replaces both robots with a composite black mask and needs one policy per source-target pair
([Lepert, Doshi, Bohg v1](https://arxiv.org/abs/2503.00774), A.1). Cloak masks the end-effector
from the wrist camera and reports zero-shot transfer to "another gripper, another arm, and a
five-fingered hand" from a single-gripper dataset ([Piseno, Tevet, Liu v1](https://arxiv.org/abs/2606.22836),
abstract; per-arm numbers unverified).

**Embodiment-free data (UMI).** A hand-held gripper records relative end-effector trajectories with
no robot present; the same checkpoint then runs on a UR5 and a Franka FR2
([entry](../papers/chi-2024-umi.md)). The robot is never in the training data, so every arm is held
out by construction.

**Latent action spaces across end-effectors.** Latent Action Diffusion trains contrastive encoders
into a shared latent for two robot hands, a human hand and a parallel gripper and reports "up to
25.3% improved manipulation success rates" from co-training ([Bauer, Nava, Katzschmann v4](https://arxiv.org/abs/2506.14608),
abstract). The arm is fixed; the end-effector varies.

### Action representations for a 4-DOF SCARA and a 6-DOF arm

**1. End-effector or object-frame actions, per-robot IK.** The policy emits a pose of the tool, or
of the grasped object, in a task frame; each robot converts it with its own IK and controller.

- For. The SR-20iA's reachable set is exactly position plus yaw with the tool vertical
  ([arm-selection](arm-selection-scara-vs-six-axis.md), section 1), so a planar-plus-height action
  is native to it and a strict subset of what the UR20 can do. UMI's relative end-effector
  trajectory ran on a second arm at 18/20 after 20/20 on the first; in its ablation absolute actions
  scored 5/20 and deltas 16/20 on the UR5 ([entry](../papers/chi-2024-umi.md)). The repo's IK
  already serves both arms: `solve_ik` holds the tool down and turns it to a yaw, and on the SCARA
  the orientation rows are satisfied by construction (`src/meat_cell_sim/arm.py`, module docstring).
- Against. The controller gap does not disappear. Mirage's state-based transfer to a UR5e with a
  blocking controller kept Square at 74 percent (source 81); executing the same delta actions
  without it gave 10 percent (Tables I and VIII, simulation, episode count not stated). The target
  can still hit joint limits: UMI's two Franka failures were joint-limit violations, and the FR2
  needed a mount rotating the gripper 90 degrees because of its limited end-effector pitch (v3,
  supplement). Tool frames differ: Shadow notes that the Robotiq 2F-85 and Franka gripper put the
  control point at different flange distances (Sec. 4.2); Mirage had grippers mounted 45 and 90
  degrees apart (Sec. VI-B).

**2. Project a 6-DOF action onto the SCARA's feasible set.** If a policy emits a full rotation R
(for example a VLA trained on 7-D end-effector data), the SCARA can execute only R' = Rz(psi)
R_down. The nearest such rotation in Frobenius norm has a closed form, with M = R R_down^T:

```
psi*       = atan2(M_10 - M_01, M_00 + M_11)
tilt_drop  = arccos(-R_22)          # angle between commanded tool z and straight down
```

Checked numerically on 2026-09-15 (numpy 2.4.6): over 200 random rotations the closed form agrees
with a 200,001-point brute-force search to 1.5e-5 rad, the grid step; a yaw of 0.7 rad followed by
a 20 degree tilt about tool x recovers 0.7 rad and reports 20 degrees dropped. Position passes
through; z is clipped to the 300 mm stroke
([arm-models-for-sim](../hardware/arm-models-for-sim.md)).

- For. One action head for both arms, and an explicit number (tilt dropped) to gate on.
- Against. It silently changes the task whenever the demonstrations used tilt. No paper found
  evaluates projection as a transfer method for a lower-DOF arm (search in this pass; absence, not
  a result). Cloak reports the opposite pressure: its IK regularisation "suppress[es] tilting
  behaviors" and limits generalisation (limitations section, unverified).

**3. Embodiment tokens or prompts.** A learned vector per robot enters the sequence (X-VLA's soft
prompts; "Data Analogies", arXiv 2603.06450, uses an embodiment token with joint-space actions,
unverified). X-VLA reports adaptation success rising from 64.6 to 73.8 percent when soft prompts are
added (Table 1, unverified).

- For. One set of weights can absorb per-robot dynamics that a controller does not hide.
- Against. The token is learned from that robot's data, so the robot is seen, not held out. With
  two robots and two days, a checkpoint with an embodiment token trained on both arms is two
  policies sharing storage, and should be called co-training.

**4. Shared latent, per-robot decoders.** Devin, Polybot, HPT, UniAct, Latent Action Diffusion.

- For. Robots with unrelated action spaces (joint torques on different link counts, a hand and a
  gripper) can share what the task needs.
- Against. Every decoder is trained on its robot's data. Devin's zero-shot result is on a held-out
  robot-task pair whose robot was in training with other tasks: final distance 0.08 to 0.28 against
  1.16 to 1.35 for a random network, four test positions, trial count not given (Table I). Polybot
  on real robots: 0.7 to 1.0 success with 5 target demos, 0.0 to 0.6 zero-shot on a new task, 10
  trials per cell (Tables 1, 2), and no transfer to a robot without demonstrations.

## Evidence table

| Method (version) | Embodiments, sim or real | Shared / per-embodiment | What transfers | Key number | Trials | Source |
|---|---|---|---|---|---|---|
| RT-X, RT-2-X 55B | 9 in training mix, 22 in dataset; real | Weights and 7-D EE action / per-dataset normalisation | Bridge (WidowX) skills to the Google Robot, which never saw them | Emergent skills 75.8% vs RT-2 27.3%; 42.8% without Bridge data | 3600 over 6 robots; per cell not stated | [entry](../papers/open-x-embodiment-collaboration-2023-rt-x.md) |
| Octo-Base | 25 OXE datasets; real | Trunk / new head at fine-tune | New robot (ViperX), new 14-D joint action space | 100% ViperX Coke; 80% bimanual; 72% avg vs 20% scratch | 20 per domain | [entry](../papers/octo-model-team-2024-octo.md) |
| CrossFormer (v1) | 20: single arms, ALOHA, LoCoBot, Go1, Tello; real | Backbone, per-observation-type encoders / per-action-type readout tokens and heads | Pooling without negative transfer; unseen Tello via existing nav head | 0.73 avg vs 0.68 same-arch single-robot vs 0.51 best prior; Tello 0.82 vs 0.68 | 116 total; Tello 3 | [Doshi et al.](https://arxiv.org/abs/2408.11812), Table 3 |
| HPT-B/XL (v1) | 52 datasets pretrain; real Franka with new sensors and action space | Trunk / stem and head per embodiment | New stem and head on a pretrained trunk | Sweep Leftover 70.0% (HPT-B) and 76.7% (XL) vs 43.3% scratch; Fig. 12 disagrees for the same task | 15 per task (caption says 45 per approach) | [Wang et al.](https://arxiv.org/abs/2409.20537), Table 3 |
| pi0 (v4) | 7 configurations, 6 to 17-D action; real | Weights, 18-D padded state and action / none | Co-training only; no held-out robot | No single-robot ablation of pi0; UR5e-only OpenVLA baseline figure-only | 10 per task | [Black et al.](https://arxiv.org/abs/2410.24164), Sec. V-A, VI-A |
| Devin et al. (v1) | 3, 4, 5-link arms; MuJoCo sim | Task module / robot module, unsupervised latent interface | Unseen robot-task pair | Final distance 0.08 to 0.28 vs 1.16 to 1.35 random (reach); no zero-shot on drawer task | 4 test positions | [Devin et al.](https://arxiv.org/abs/1609.07088), Tables I, II |
| Polybot (v1) | WidowX 250S, Franka, Sawyer; real | Encoder, trunk, contrastive latent / action head | New task variant to third robot | 0.7 to 1.0 with 5 demos vs 0.0 to 0.3 single-robot; 0.0 to 0.6 zero-shot | 10 per cell | [Yang et al.](https://arxiv.org/abs/2307.03719), Tables 1, 2 |
| MetaMorph (v1) | 100 train, 100 test UNIMAL morphologies, 15 to 20 DoF; sim | All weights; limb tokens with morphology descriptors | Unseen morphologies | No zero-shot number; fine-tuning 2 to 3x more sample-efficient than scratch | 3 runs, curves | [Gupta et al.](https://arxiv.org/abs/2203.11931), Sec. 5.4 |
| Mirage (v3) | Franka source; UR5e, IIWA, Gen3, Sawyer, Jaco sim; UR5 real | Policy, EE pose / URDF, renderer, blocking controller, camera matrices | Zero-shot to held-out arm | Real Franka to UR5: 90, 60, 50, 30% vs 0% unmodified; delta actions in sim, Square 10% vs 74% | Not stated (real results in 10% steps) | [Chen et al.](https://arxiv.org/abs/2402.19249), Tables I, IV, VIII |
| RoVi-Aug (v2) | Franka and UR5; real | One diffusion policy on absolute EE actions / ControlNet per robot pair | Zero-shot both directions | Franka to UR5 Drawer 90% vs 0% no augmentation | 10 per cell | [Chen et al.](https://arxiv.org/abs/2409.03403), Table 1 |
| Shadow (v1) | Panda source; Sawyer, IIWA, UR5e sim; UR5e, Panda+Franka gripper real | Absolute EE pose / one policy per pair, masks, calibration | Zero-shot to held-out arm | Sim Stack 0.97 on UR5e vs 0.02 black-only; real UR5e Mug 0.98 falls to 0.64 at 1 cm, 5 deg calibration noise | 100 sim; 50 real; 25 in noise table | [Lepert et al.](https://arxiv.org/abs/2503.00774), Tables 1, 3 |
| UMI (v3) | Hand-held gripper data; UR5, Franka FR2; real | Checkpoint, relative EE trajectory / robot controller, mount adapter | Same checkpoint on a second arm | 20/20 UR5, 18/20 FR2 (2 joint-limit faults) | 20 | [entry](../papers/chi-2024-umi.md) |
| XMoP (v2) | 7 unseen arms incl. 6-DoF UR5, UR10, Gen3; sim and real | Planner weights, 8 link-pose tokens / mask for 6-DoF | Zero-shot motion planning, not a task policy | UR5 70.8%, Gen3 6-DoF 67.6% vs 7-DoF 78.2%; real 50 to 80% | 500 problems per robot; 10 real per domain | [XMoP](https://arxiv.org/html/2409.15585v2), Tables I, II |
| Cloak (v1) | DROID Franka data; another gripper, another arm, a hand; real | VLA with end-effector masked in wrist view | Zero-shot to unseen bodies | Abstract: transfers "while preserving the source embodiment's performance"; table numbers unverified | Unverified | [Piseno et al.](https://arxiv.org/abs/2606.22836) |
| Latent Action Diffusion (v4) | Two robot hands, parallel gripper (and human hand data); real | Diffusion policy in shared latent / contrastive encoder and decoder per end-effector | Co-training across end-effectors, same arm | "up to 25.3%" improvement | Unverified | [Bauer et al.](https://arxiv.org/abs/2506.14608), abstract |

## Design for the SCARA and six-axis demo

Everything in this section is a design proposal unless a line cites a source or a file. It follows
the order of the plan's open questions: what is learned, what representation, how much can be real
by Wednesday.

### Recommendation

Learn the reorientation as a sequence of planar poses of the grasped point in the belt frame,
trained by imitation from a scripted expert driving a floating gripper, and run the unchanged
checkpoint through each arm's own IK. Neither arm appears in the training data, so both are
held out in the UMI sense, and the transfer claim reduces to a measurable question: does the arm's
execution (reach, servo sag, IK failure, dynamics) change the outcome relative to the floating
gripper.

Reasoning in four steps.

1. **The only grasp both arms can make is the shank grasp from above.** The trotter end-on grasp
   needs a tool that tilts and fails its precondition on the SR-20iA
   (`src/meat_cell_sim/skills/trotter_grasp.py`; [alignment experiment](../../experiments/2026-09-15-alignment-approaches.md),
   amendment of 2026-09-14). `SelectShankGrasp` and `AcquireShank` already run on both arms with
   the tool vertical (`src/meat_cell_sim/skills/grasp.py`). So the reorientation that both arms
   share is approach B, grasp-and-rotate on the belt, with the tool vertical throughout.
2. **With the tool vertical, the task's action lives in (x, y, yaw) plus a fixed height.** That set
   is the SCARA's native space and a subset of the UR20's, so no projection is needed and both arms
   receive identical Cartesian targets. This is representation 1 above, the one with the strongest
   real-robot transfer evidence (UMI, Mirage, RoVi-Aug). Projection (representation 2) stays in the
   code only as a guard that rejects any commanded rotation whose tilt_drop exceeds 1 degree.
3. **Embodiment tokens and per-robot decoders would need data from each arm,** which turns the
   demo into co-training (representation 3 and 4 against arguments). Keep them out of this
   checkpoint; they belong in a later demo whose claim is fleet co-training.
4. **Excluding joint state from the observation removes the arm from the policy's input.** Octo's
   authors found proprioception made policies worse through causal confusion
   ([entry](../papers/octo-model-team-2024-octo.md)); here the reason is simpler: joint state is the
   one input that differs in dimension (6 against 4) and meaning between the two arms.

### What is learned

`OrientLeg` policy, one checkpoint:

- Observation, belt frame at time t, all embodiment-free: leg planar pose (x_m, y_m, yaw_rad) of
  the trotter axis relative to the saw target line; leg length_m and mass_kg; belt speed_mps; the
  grasp point's current planar pose (x, y, yaw) measured from the tool pose; grasp fraction along
  the leg; time since the grasp closed. Ground-truth leg pose for the demo, stated as such, as the
  alignment experiment already does.
- Action: a chunk of 8 future grasp-point poses (x, y, yaw) in the belt frame at 10 Hz, plus a
  release logit. Height is held at the grasp height by the deterministic executor. Absolute poses,
  not deltas, following UMI's and Mirage's ablations above and the position-over-velocity finding
  in [conveyor-tracking](conveyor-tracking-and-visual-servoing.md).
- The yaw must be a directed angle. `wrap_axis_angle` in `src/meat_cell_sim/contracts.py` folds
  headings into (-pi/2, pi/2] because a slab has no head or tail; a leg does, and the trotter must
  end toward the saw. Use a full (-pi, pi] angle for this skill.
- Model: an MLP with L1 loss on the chunk. The expert is deterministic and unimodal, so a diffusion
  head buys nothing measurable here, and OpenVLA-OFT found L1 regression matched a diffusion head
  ([entry](../papers/kim-2025-openvla-oft.md)). A transformer is not needed either: the observation
  is a fixed-size, embodiment-free vector by construction, which is exactly the problem attention
  over variable tokens solves. Say that out loud in the demo rather than wrapping an MLP's job in a
  transformer.
- Why learn at all, when a scripted expert exists: the expert acts on privileged state (true leg
  pose, true friction) and replans at every step; the policy learns its closed-loop behaviour from
  the observed state across 20 leg shapes and randomised friction. It may do no better than the
  expert. The pre-registered [learned-versus-scripted record](../../experiments/2026-09-15-meat-cell-learned-vs-scripted.md)
  exists because that outcome is live, and this demo shows transfer, not that learning beats
  scripting.

### Demonstrations

- Expert: a closed-loop planar controller that turns the grasped point about the leg's centre of
  gravity until the trotter axis meets the saw line within tolerance, then releases; it reads true
  leg pose each step.
- Body: a floating gripper (a MuJoCo mocap body carrying the same jaw asset) welded to the leg at
  the shank grasp. Sim analogue of UMI's hand-held gripper: no arm in the data.
- Domain randomisation, per [Tobin et al.](../papers/tobin-2017-domain-randomization.md): the 20
  legs of `leg_population(20, seed=0)` (655 to 815 mm, 9.0 to 15.5 kg,
  [alignment record](../../experiments/2026-09-15-alignment-approaches.md)); arrival y and yaw from
  that record's distributions; belt-leg friction swept over 0.15 to 0.5, the range the arm-selection
  note says any push simulation must report
  ([section 8](arm-selection-scara-vs-six-axis.md)); belt speed around the assumed 0.30 m/s.
- Split: 15 legs for training, 5 held out for test. Successful expert episodes only, with the
  discard count in the `DATASET.md`.

### What is deterministic

- Perception: ground truth for Wednesday.
- Grasp: `SelectShankGrasp`, `AcquireShank`, unchanged.
- Executor: each 10 Hz pose target goes from belt to world frame by belt travel, through
  `solve_ik(position_m, yaw_rad, arm=cell.arm)`, seeded from the previous solution, and to the
  position servos through the existing interpolated `move_arm`. `UnreachableError` is an outcome,
  never retried (`src/meat_cell_sim/arm.py`).
- Shield, as preconditions and per-step checks with numbers in the evidence: IK residual, joint
  limits, tilt_drop under 1 degree, SR-20iA radius inside its 331 to 1100 mm annulus
  ([arm-models-for-sim](../hardware/arm-models-for-sim.md)), speed at `SPEED_FRACTION`, release
  and clearance before the hold-down ramp.
- Published limits the simulator does not enforce, logged per episode: leg inertia about the tool
  axis against the SR-20iA's 0.45 kg m^2 J4 limit, and flange load against the UR20 payload curve.
  Neither built arm has torque limits (`src/meat_cell_sim/arms.py` docstring).
- Recovery on the task graph (`src/skill_library/graph.py` refuses a graph with an unrouted
  outcome): `unreachable` and `shield_rejected` release and let the leg pass to the manual station;
  `slipped` re-grasps once, then lets pass.

### Contract for the learned skill

| Field | Content |
|---|---|
| Inputs | `lift_proof` and `shank_grasp` from `AcquireShank`; leg estimate; saw target line in the belt frame; checkpoint path and its SHA-256 |
| Preconditions | Grip proven by the 5 mm lift; checkpoint hash matches the record; start pose reachable by this arm's IK |
| Outputs | Leg pose at release, belt frame; number of policy steps; max tilt_drop; max IK residual |
| Success | Trotter axis within 5 degrees of the saw line and offset within 10 mm at release (the alignment record's assumed tolerances); then the saw's `CutResult` judges the episode |
| Failures | `unreachable`, `shield_rejected`, `slipped`, `leg_slid_not_turned`, `timeout` |
| Recovery | On the task graph, as above |

### How the same checkpoint drives both arms, and how to show it honestly

Six conditions, the same held-out legs and the same arrival list for each, paired by episode:

| Condition | Driver | Body | Role |
|---|---|---|---|
| E0 | Expert | Floating gripper | Source ceiling |
| E1, E2 | Expert | UR20, SR-20iA | Executor gap with no learning |
| P0 | Policy | Floating gripper | Policy on its training body |
| P1, P2 | Policy | UR20, SR-20iA | Zero-shot transfer |

Transfer is P1 and P2 against P0; the executor's share of any drop is E1 and E2 against E0. If
P2 minus P0 is close to E2 minus E0, the SCARA's losses come from execution, not from the skill,
and the claim "the skill transferred" holds. Report k/n with Wilson intervals and McNemar on the
paired outcomes ([policy-evaluation](policy-evaluation.md)): 5 held-out legs times 20 arrivals is
100 episodes per condition. One checkpoint file, its hash printed on both videos, and the same
episode seeds.

What counts as transfer: one checkpoint, zero data from either arm in training, no per-arm
parameters other than the `ArmSpec` and its IK. What does not: training on UR20-executed demos and
testing on the UR20 (in-domain), adding an embodiment token, or fine-tuning per arm. If a stricter
cross-arm result is wanted, add P3: policy trained on UR20-executed demos, tested on the SR-20iA.

Write the experiment record with these conditions before the first episode, per
`sops/experiment-protocol.md`.

### Build order for 1 to 2 days (estimate, unverified)

1. Floating gripper body and the planar expert; expert runs E0 on one leg.
2. `OrientLeg` executor taking pose chunks; E1 and E2 on one leg with expert chunks. This is the
   test of the executor and must pass before anything trains.
3. Demonstration generation over 15 legs with randomisation; dataset parity test between stored
   and live observations.
4. Train the MLP on CPU. The `rll` env has numpy 2.4.6 and MuJoCo 3.12.0 but no torch (checked
   2026-09-15), and `nvidia-smi` reported "Failed to initialize NVML: Driver/library version
   mismatch" the same day, so install a CPU torch build or train in numpy. Training time is
   unmeasured.
5. Run the six conditions, the statistics, two videos.

### What could go wrong

- **The SCARA succeeds in simulation at a move the real arm cannot make.** A leg gripped through its
  centre of gravity is 1.06 times the SR-20iA's J4 inertia limit, and 4.06 times at a shank grasp
  350 mm away ([arm-models-for-sim](../hardware/arm-models-for-sim.md), section 5). The demo video
  must carry that number next to the SCARA run.
- **The leg slides instead of turning.** The alignment record's own counter-hypothesis; planar
  friction under a deformable piece is indeterminate
  ([arm-selection](arm-selection-scara-vs-six-axis.md), section 4). A policy trained over one
  friction value learns that value, which is why friction is randomised.
- **The two arms track the same target differently.** The UR20 raised its tool 1.6 mm of a
  commanded 5 mm under a leg (`src/meat_cell_sim/skills/grasp.py`, measured 2026-09-14). Closed-loop
  replanning at 10 Hz on the observed grasp point absorbs a steady lag; Mirage's delta-action
  collapse (74 to 10 percent on Square) is the evidence for keeping targets absolute.
- **The floating gripper proposes poses one arm cannot reach.** The SR-20iA reaches 1.1 m against
  the UR20's 1.75 m. Reachability failures on the SCARA are expected and are the result, not a bug:
  count them as `unreachable`, as UMI counted its joint-limit faults.
- **The 300 mm quill stroke** already forces lower approach heights on the SCARA
  (`APPROACH_CLEARANCES_M` in `grasp.py`).
- **Contact modelling biases the jaw.** A flat jaw holds 0.60 to 0.70 of its friction rating on a
  cylinder in MuJoCo ([alignment record](../../experiments/2026-09-15-alignment-approaches.md),
  caveats), so a slip may be the contact model.
- **Small n.** 100 paired episodes per condition gives a Wilson half-width of roughly 8 points near
  80 percent success; a 5 point difference between arms is not a finding.

## Gotchas

- **Co-training is not transfer.** CrossFormer, the largest heterogeneous policy read here, states
  it does "not yet show significant positive transfer"
  ([Doshi et al.](https://arxiv.org/abs/2408.11812), Sec. 5). Ask whether the target robot was in
  training before accepting a cross-embodiment claim.
- **Delta actions do not survive a body change; the target's controller has to reach the pose.**
  Mirage in simulation: Square 74 percent with a blocking controller, 10 percent executing deltas,
  from a source rate of 81 ([Chen et al.](https://arxiv.org/abs/2402.19249), Tables I, VIII).
- **Joint limits on the second arm.** UMI's only failures on the FR2 were joint-limit violations,
  and a custom adapter rotating the gripper 90 degrees was needed because of its end-effector pitch
  ([UMI v3](https://arxiv.org/abs/2402.10329), supplement).
- **Calibration sensitivity is steep.** Shadow on a real UR5e: Mug 0.98 to 0.64 at 1 cm and 5
  degrees of extrinsic noise, 0.20 at 2 cm and 10 degrees, 25 rollouts
  ([Lepert et al.](https://arxiv.org/abs/2503.00774), Table 3). Mirage: a 5 cm z-offset in
  proprioception dropped Tiger to 20 percent (Table VI).
- **Token order is part of the model.** Reversing MetaMorph's node order cut zero-shot performance by
  about 75 percent until same-depth nodes were shuffled in training
  ([Gupta et al.](https://arxiv.org/abs/2203.11931), Appendix B.3).
- **Read the tables, not the prose.** HPT's text, legends and appendix disagree on model size, trial
  counts and learning rate, and its Table 3 and Fig. 12 give different numbers for the same task
  ([Wang et al.](https://arxiv.org/abs/2409.20537)); Polybot's text quotes a Franka S5 of 1.0 where
  Table 1 has 0.9 ([Yang et al.](https://arxiv.org/abs/2307.03719), Sec. 5).
- **MuJoCo has no IK.** "The opposite mapping is called inverse kinematics but it is not uniquely
  defined and is not implemented in MuJoCo"
  ([docs](https://mujoco.readthedocs.io/en/stable/programming/simulation.html)). mink adds a QP
  differential IK with `FrameTask`, `ConfigurationLimit` and `VelocityLimit`
  ([mink](https://github.com/kevinzakka/mink)); the repo uses its own damped least squares.
  Menagerie has no UR20 and no SCARA model at commit 8161bba (2026-09-04), so both demo arms are
  the repo's own builds ([menagerie](https://github.com/google-deepmind/mujoco_menagerie)).

## Open questions

- Does any published policy transfer to a 4-DOF arm with a measured success rate? None found in
  this pass; the nearest is a 5-joint SO-101 in co-training, not held out.
- How large is E2 minus E0 on this cell, the executor gap with no learning in it? It decides whether
  a SCARA result is about the skill.
- Does the policy's closed-loop behaviour survive perception noise, once the depth pipeline's hock
  and yaw error replaces ground truth (plan (`plan/wednesday-2026-09-16.md`), item 5)?
- Is a residual on the scripted planar controller a better learned part than the whole trajectory,
  when both are measured on P1 and P2?
- Gemini Robotics 1.5 claims "Motion Transfer" across ALOHA 2, Apollo and bi-arm Franka, but the
  mechanism is not described and results are figure-only (arXiv 2510.03342); what is shared there?
- Which parts of a VLA on top of this skill library would need tilt, and therefore could not run on
  the SCARA through projection without changing the task?

## Related entries

- [vision-language-action-models](vision-language-action-models.md) (model lineage, action heads, fine-tuning)
- [RT-X](../papers/open-x-embodiment-collaboration-2023-rt-x.md), [Octo](../papers/octo-model-team-2024-octo.md), [pi0](../papers/black-2024-pi0.md), [pi0.5](../papers/physical-intelligence-2025-pi05.md), [UMI](../papers/chi-2024-umi.md), [OpenVLA-OFT](../papers/kim-2025-openvla-oft.md)
- [arm-selection-scara-vs-six-axis](arm-selection-scara-vs-six-axis.md), [arm-models-for-sim](../hardware/arm-models-for-sim.md)
- [conveyor-tracking-and-visual-servoing](conveyor-tracking-and-visual-servoing.md) (belt frame under the policy)
- [imitation-learning](imitation-learning.md), [policy-evaluation](policy-evaluation.md), [sim-to-real](sim-to-real.md), [domain randomisation](../papers/tobin-2017-domain-randomization.md), [safety-for-learned-policies](safety-for-learned-policies.md)
- [policy-composition-latent-skills](../papers/policy-composition-latent-skills.md), [meat-cell-architecture](meat-cell-architecture.md)
- Experiments: [alignment-approaches](../../experiments/2026-09-15-alignment-approaches.md), [learned-vs-scripted](../../experiments/2026-09-15-meat-cell-learned-vs-scripted.md); plan: `plan/wednesday-2026-09-16.md`
- Code: `src/meat_cell_sim/arm.py`, `src/meat_cell_sim/arms.py`, `src/meat_cell_sim/skills/grasp.py`, `src/meat_cell_sim/skills/trotter_grasp.py`, `src/skill_library/contract.py`, `src/skill_library/graph.py`

## Sources

- Vaswani et al., Attention Is All You Need, arXiv 1706.03762 v7: https://arxiv.org/abs/1706.03762
- Open X-Embodiment Collaboration, RT-X, arXiv 2310.08864 (v9, via library entry): https://arxiv.org/abs/2310.08864
- Octo Model Team, Octo, arXiv 2405.12213 v2: https://arxiv.org/abs/2405.12213
- Doshi, Walke, Mees, Dasari, Levine, Scaling Cross-Embodied Learning (CrossFormer), arXiv 2408.11812 v1: https://arxiv.org/abs/2408.11812
- Wang, Chen, Zhao, He, Heterogeneous Pre-trained Transformers, NeurIPS 2024, arXiv 2409.20537 v1: https://arxiv.org/abs/2409.20537
- Black et al., pi0, arXiv 2410.24164 v4: https://arxiv.org/abs/2410.24164 ; pi0.5 via library entry: https://arxiv.org/abs/2504.16054
- Devin, Gupta, Darrell, Abbeel, Levine, Learning Modular Neural Network Policies for Multi-Task and Multi-Robot Transfer, ICRA 2017, arXiv 1609.07088 v1: https://arxiv.org/abs/1609.07088
- Yang, Sadigh, Finn, Polybot, CoRL 2023, arXiv 2307.03719 v1: https://arxiv.org/abs/2307.03719
- Gupta, Fan, Ganguli, Fei-Fei, MetaMorph, ICLR 2022, arXiv 2203.11931 v1: https://arxiv.org/abs/2203.11931
- Chen, Hari, Dharmarajan, Xu, Vuong, Goldberg, Mirage, RSS 2024, arXiv 2402.19249 v3: https://arxiv.org/abs/2402.19249
- Chen et al., RoVi-Aug, CoRL 2024, arXiv 2409.03403 v2: https://arxiv.org/abs/2409.03403
- Lepert, Doshi, Bohg, Shadow, CoRL 2024, arXiv 2503.00774 v1: https://arxiv.org/abs/2503.00774
- Chi et al., UMI, RSS 2024, arXiv 2402.10329 v3: https://arxiv.org/abs/2402.10329
- XMoP, cross-embodiment motion planning, arXiv 2409.15585 v2: https://arxiv.org/html/2409.15585v2
- Piseno, Tevet, Liu, Cloak, arXiv 2606.22836 v1 (abstract): https://arxiv.org/abs/2606.22836
- Bauer, Nava, Katzschmann, Latent Action Diffusion for Cross-Embodiment Manipulation, arXiv 2506.14608 v4 (abstract): https://arxiv.org/abs/2506.14608
- Read through a summarising fetch, numbers unverified: UniAct arXiv 2501.10105 https://arxiv.org/abs/2501.10105 ; X-VLA arXiv 2510.10274 https://arxiv.org/abs/2510.10274 ; GR00T N1 arXiv 2503.14734 https://arxiv.org/abs/2503.14734 ; RDT-1B arXiv 2410.07864 https://arxiv.org/abs/2410.07864 ; Data Analogies arXiv 2603.06450 https://arxiv.org/abs/2603.06450 ; Embedding Morphology into Transformers arXiv 2603.00182 https://arxiv.org/abs/2603.00182 ; AnyBody arXiv 2505.14986 https://arxiv.org/abs/2505.14986 ; Gemini Robotics 1.5 arXiv 2510.03342 https://arxiv.org/abs/2510.03342
- MuJoCo documentation, simulation, coordinate frames: https://mujoco.readthedocs.io/en/stable/programming/simulation.html ; mink: https://github.com/kevinzakka/mink and https://kevinzakka.github.io/mink/ ; MuJoCo Menagerie: https://github.com/google-deepmind/mujoco_menagerie
- Local: `src/meat_cell_sim/arm.py`, `arms.py`, `contracts.py`, `skills/grasp.py`, `skills/trotter_grasp.py`; `src/skill_library/contract.py`, `graph.py`; `experiments/2026-09-15-alignment-approaches.md`; projection check script run in the `rll` env on 2026-09-15 (numpy 2.4.6), not committed
