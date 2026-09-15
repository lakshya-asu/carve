---
title: "Behavior Generation with Latent Actions (VQ-BeT)"
date: 2026-09-05
tags: [paper, imitation-learning, transformer, vector-quantization, multimodality, inference-speed]
status: draft
source: https://arxiv.org/abs/2403.03181
---

# VQ-BeT (Lee, Wang, Etukuru, Kim, Shafiullah, Pinto, ICML 2024)

Read from arXiv v2 (28 Jun 2024). NYU and SNU. Successor to Behavior Transformers (BeT):
replace k-means action binning with a learned residual VQ-VAE codebook, then predict codes
with a GPT-style transformer.

## Problem

Continuous, multimodal actions do not fit a language-model head directly. BeT discretised
actions with k-means plus a continuous offset, but k-means needs the right k, has no
gradient, and degrades on high-dimensional or chunked actions. Diffusion policies handle
multimodality but need many forward passes per action, which the authors show is a problem
on a cheap mobile manipulator where receding-horizon execution fails outright.

## Core idea

Two stages. Stage 1: train a residual VQ-VAE on actions (or action chunks) with N_q = 2
codebook layers; the first layer gives coarse "primary" codes, the second gives fine
"secondary" codes, and the decoder maps the summed code vectors back to actions. Stage 2: a
minGPT transformer over an observation window (optionally plus goal observations) predicts a
categorical over primary and secondary codes with focal loss, weighted by beta for the
secondary term, plus a continuous offset head with L1 loss so the decoded action is exact.
One forward pass per action.

## Method details that matter for reimplementation

- Residual VQ (Sec. 3.2): loss = L1 reconstruction + codebook term with stop-gradient +
  commitment term (lambda_commit = 1). Codebook vectors updated by moving average, not
  gradients. N_q = 2 everywhere.
- Code loss (Eq. 4): focal loss on primary codes plus beta x focal loss on secondary codes.
  beta = 0.1 on most sim tasks, 0.6 on Ant, 0.5 real. Setting beta = 1 hurts as much as
  removing the residual layer (Fig. 5).
- Offset head (Eq. 6): L1 between the true action and decoded code plus predicted offset;
  ablation shows it is "quite important".
- Autoregressive code prediction (secondary conditioned on primary): hurt in sim Kitchen but
  was important on the real robot; used for nuScenes and real-world runs (Table 13).
- Action chunking: tried where possible, performed worse; the authors run single-step
  actions because inference is fast enough (Sec. 4.6).
- Table 13 hyperparameters: observation window 10 (Kitchen, UR3), 100 (Ant), 3 (BlockPush),
  5 (PushT), 6 (real); predicted action length 1 except UR3 (10), PushT (5), nuScenes (6);
  minGPT 6 layers, 6 heads, embed 120 (BlockPush 4/4/72); VQ latent 512 (BlockPush 256);
  codebook size 16 (Kitchen, UR3, PushT), 10 (Ant, nuScenes), 8 (BlockPush), 8 to 16 real;
  lr 5.5e-5 sim, 3e-4 real; 300 to 2000 epochs. ResNet18 encoder for image sim tasks, Dobb-E
  HPR encoder fine-tuned for the real robot.
- Real setup: Hello Robot Stretch, Dobb-E style "Stick" data collection, 45 demos per task,
  80/20 train/val split, ego camera only, fully closed-loop rollout for every method.

## Result that matters

Simulation, unconditional (Table 2): PushT final IoU 0.78 vs DP-T 0.74; Image PushT 0.68 vs
DP-C 0.66 (DP-T 0.45); Kitchen 3.66/4 tasks vs DP-T 3.44; Multimodal Ant 3.22 vs DP-C 3.12;
UR3 BlockPush 1.84 vs 1.83. Losses: BlockPush 1.79 vs DP-T 1.93; Image Kitchen 2.98 vs DP-C
3.11. Conditional (Table 1): beats C-BeT and BESO variants on all but BlockPush. Seeds and
evaluation counts per cell are not stated in the tables I read (unverified).

Inference (Table 3, Kitchen, DP at 10 denoising steps): VQ-BeT 15.1 ms per step vs DP-C
100.5 ms and DP-T 98.6 ms; multi-step chunk 15.2 ms vs about 100 ms. Real robot (Table 7):
18.06 ms on an RTX A4000 and 207 ms on the Stretch's 4-core CPU, vs 573 ms and 5244 ms for
DP-T.

Real robot, 10 trials per task (Tables 5, 6): five single-phase tasks 47/50 vs DP-T 45/50 vs
MLP-BC 29/50. Three two-phase tasks 19/30 vs DP-T 11/30 (the quoted 73% relative margin).
Four long-horizon tasks of 3 to 4 subtasks, final-subtask success: Task 1 6/10 vs 2/10; Task
2 3/10 vs 1/10; Task 3 7/10 vs 2/10; Task 4 6/10 vs 1/10. DP-T was modified by the authors
to run closed-loop; with receding-horizon execution it completed zero tasks on the Stretch
(Appendix Table 11).

## What it changes in practice

- Discretised action tokens are viable for continuous control when the tokenizer is learned;
  this is the same recipe VLA models later use for action heads, so the ablations here
  (residual layer, offset head, beta) are the ones to check when a token head underperforms.
- 15 ms single-step inference on a workstation and 200 ms on an embedded CPU makes fully
  closed-loop control feasible where diffusion is not.
- Receding-horizon execution assumes the controller tracks commands; on imprecise hardware a
  3-step open-loop segment already leaves the data distribution. Test T_a = 1 before
  concluding a policy failed.

## Known limitations and follow-ups

- Margins over Diffusion Policy in sim are small (0.01 to 0.2) and the method loses on two
  of seven unconditional tasks. The clear wins are inference cost and long-horizon real
  tasks.
- The autoregressive-code ablation disagrees between sim and real; the authors call the sim
  result anomalous without explanation.
- Real evaluation is 10 trials per task, single robot, ego camera only.

## Open questions

- Does a two-layer residual codebook still suffice for 14-D bimanual chunks at 50 Hz, or
  does N_q need to grow with dimension?
- The paper reports no seeds for the sim tables; how large is the variance relative to the
  0.01 to 0.05 margins?

## Sources

- Paper: https://arxiv.org/abs/2403.03181 (v2, 28 Jun 2024). Sec. 3, 4.2, 4.4, 4.6, 4.7;
  Tables 1 to 7, 11, 13; Appendix A.2, C.1.
- Project page: https://sjlee.cc/vq-bet/
