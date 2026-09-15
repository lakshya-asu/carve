---
title: "π0: A Vision-Language-Action Flow Model for General Robot Control"
date: 2026-09-05
tags: [paper, vla, flow-matching, action-expert, bimanual, mobile-manipulation, physical-intelligence]
status: draft
source: https://arxiv.org/abs/2410.24164
---

# pi0 (Black et al., Physical Intelligence, 2024)

## Problem

Token-based VLAs (RT-2, OpenVLA) decode one discrete action per step at a
few Hz, which rules out 50 Hz bimanual work such as laundry folding. Small
diffusion policies handle dexterity but have no pretrained backbone. The
paper wants both: VLM knowledge and precise high-frequency action chunks.

## Core idea

Keep a VLM (PaliGemma 3B) for images and language, add a second, smaller set
of transformer weights (the "action expert", 300M) for proprioception and a
50-step action chunk, and train that expert with conditional flow matching.
Pretrain on about 10k hours of in-house dexterous data plus OXE, then
post-train on curated task data, as LLMs are pretrained then aligned.

## Method details that matter for reimplementation

- Backbone: PaliGemma, a 3B VLM on Gemma 2B (width 2048, depth 18, mlp
  16384, 18 heads, 1 KV head) with its image encoder. Images (2 or 3 per
  robot) and language route here.
- Action expert: same depth, width 1024, mlp 4096, about 300M parameters,
  from scratch. State q_t and the H = 50 noisy action tokens route here; the
  experts interact only through self-attention (Appendix A-B). 3.3B total.
- Attention: three blocks [images, language], [q_t], [noisy actions],
  bidirectional within a block, no attention to later blocks. q_t in its own
  block keeps its KV cache valid across denoising steps.
- Flow matching: linear-Gaussian path, target A - eps, squared error on the
  vector field. Timestep tau ~ Beta((s - tau)/s; 1.5, 1), s = 0.999,
  weighted toward high noise (Fig. 14). Inference: 10 Euler steps from
  Gaussian noise with the prefix KV cached.
- Data: 903M in-house timesteps (106M single-arm, 797M dual-arm), 7 robot
  configurations, 68 broadly defined tasks; open data (OXE Magic Soup,
  Bridge v2, DROID) is 9.1% of the mix. Task-robot pairs weighted n^0.43.
  Action and state padded to 18 dims; missing cameras masked.
- Training: 700k steps; a 160k-step "compute parity" model is also run.
  Batch size, learning rate and accelerators are not stated. Post-training
  sets are 5 to 100+ hours per task.
- Execution: 20 Hz UR5e and Franka requery every 16 actions (0.8 s); 50 Hz
  bimanual and mobile robots every 25 (0.5 s). Temporal ensembling hurt and
  was dropped (Appendix A-D).
- Inference, RTX 4090, 3 images: encoders 14 ms, observation pass 32 ms, 10
  flow steps 27 ms, 73 ms on board, 86 ms off board over Wi-Fi (Table I).

## Result that matters

All evaluations are real-robot, 10 episodes per task and method, scored by
per-task rubrics (Appendix A-E). Every number is a bar chart; no table.

Out-of-box (Fig. 7; shirt fold, bussing easy and hard, grocery bagging,
toast): pi0 at 700k steps was best on every task, near perfect on shirt fold
and easy bussing. The 160k parity model still beat OpenVLA (160k steps) and
Octo (320k steps) retrained on the same mixture, and pi0-small (470M, no
VLM init). OpenVLA's failure is attributed to no chunking, Octo's to
capacity. Language following (Fig. 9): human subtask commands raised pi0
substantially, a high-level VLM planner less; pi0-small gained from neither.

New tasks after fine-tuning (Fig. 11; 5 tasks, 1 to 5 hours of data each):
pi0 from the base beat pi0 from scratch, ACT, Diffusion Policy, and
fine-tuned OpenVLA and Octo. The strongest prior methods were the
from-scratch ACT and Diffusion Policy. Pretraining gains reached about 2x on
tasks close to the pretraining data.

Multi-stage tasks (Fig. 13; laundry from a bin, mobile laundry, dryer
unloading, table bussing, box building, to-go box, egg packing): pretrain +
post-train exceeded 50% of max score on every task and beat out-of-box and
scratch ablations, with the largest gaps on the hardest tasks. No external
baseline could run these.

## What it changes in practice

- Action expert plus flow matching gives 50 Hz chunked control from a 3B VLM
  at 73 ms per chunk on a consumer GPU. pi0.5 keeps the design.
- Nothing was released with the paper. Weights and JAX code (openpi) came in
  February 2025 under Apache 2.0, with pi0 and pi0-FAST base checkpoints and
  LoRA fine-tuning examples (from the repository, not the paper; unverified).
- Fine-tuning guidance: count hours of consistent demos, not episodes; 1
  hour sufficed for easy tasks, 5 to 100+ for laundry. No temporal ensemble.
- Post-training on only clean data gave brittle policies that did not recover
  from mistakes (Sec. VII); diverse pretraining supplies the recovery.

## Known limitations and follow-ups

- All quantitative results are figures with 10 trials per bar.
- Baselines were undertrained relative to pi0 (Sec. VI-A acknowledges it).
- Mixture composition is untuned; data needs per task are unpredictable.
- pi0.5 (2025) adds discrete-token pretraining, subtask prediction and web
  co-training for unseen homes; see that entry.

## Open questions

- How much is the 10k hours of proprietary data versus the architecture? The
  pi0-small ablation confounds size and VLM init, as the paper admits.
- The Beta timestep schedule is argued, not ablated against uniform tau.
- Off-board Wi-Fi inference on a mobile robot: packet loss is not discussed.

## Sources

- Paper: https://arxiv.org/abs/2410.24164 (arXiv HTML read 2026-09-05)
- Blog: https://www.physicalintelligence.company/blog/pi0
- Code and weights, post-publication: https://github.com/Physical-Intelligence/openpi (unverified against paper)
