---
title: "OpenVLA: An Open-Source Vision-Language-Action Model"
date: 2026-09-05
tags: [paper, vla, vlm, open-weights, lora, quantization, cross-embodiment]
status: draft
source: https://arxiv.org/abs/2406.09246
---

# OpenVLA (Kim et al., 2024)

## Problem

RT-2 showed a VLM fine-tuned to emit action tokens generalizes far better
than a from-scratch policy, but weights, backbone and API were closed. The
paper builds the same kind of model on open components, trains it on the
largest OXE mixture to date, and shows how to fine-tune and serve it in a lab.

## Core idea

Fine-tune the Prismatic-7B VLM (SigLIP + DINOv2 vision, Llama 2 7B) on 970k
OXE trajectories with the RT-2 action-as-text recipe, release everything, and
show that LoRA fine-tuning on one A100 and 4-bit inference on a 16 GB GPU keep
performance intact.

## Method details that matter for reimplementation

- Backbone: Prismatic-7B: SigLIP and DINOv2 features concatenated
  channel-wise (600M), 2-layer MLP projector, Llama 2 7B. Prismatic beat
  LLaVA by about 10 points, LLaVA beat IDEFICS-1 by 35, on Bridge pilots.
- Action tokenization: 7-D action, 256 uniform bins per dimension between
  the 1st and 99th percentile (RT-2 used min-max). The 256 least-used Llama
  tokens are overwritten. Next-token cross-entropy on action tokens only;
  autoregressive decoding, 7 tokens per step.
- 224x224 images (384 gave no gain at 3x cost). Vision encoder fine-tuned,
  not frozen; freezing hurt (Sec. 3.4).
- Data: OXE filtered to single-arm end-effector control with a third-person
  camera, Octo mixture weights, plus DROID at 10% for the first two thirds
  of training, then removed because its action-token accuracy stayed low.
  970k trajectories. First transition of every Bridge episode dropped
  because it is an all-zero action (Appendix C).
- Training: 27 epochs, fixed lr 2e-5, no warmup, batch 2048, 64 A100s for
  14 days, 21,500 A100-hours, until action-token accuracy passed 95%.
- Inference: 15 GB in bfloat16, about 6 Hz on one RTX 4090 without
  compilation (Sec. 3.5). A remote inference server ships with the code.

## Result that matters

All real-robot numbers are A/B evaluations with matched initial states.

Out of the box (Sec. 5.1, Tables 4 and 6):

| Platform | Trials per policy | RT-1-X | Octo | RT-2-X 55B | OpenVLA |
|----------|------------------|--------|------|-----------|---------|
| WidowX BridgeData V2, 17 tasks | 170 | 18.5 +/- 2.7 | 20.0 +/- 2.6 | 50.6 +/- 3.5 | 70.6 +/- 3.2 |
| Google Robot, 12 tasks | 60 | 33.3 +/- 6.1 | 26.7 +/- 5.8 | 78.3 +/- 5.4 | 85.0 +/- 4.6 |

RT-2-X led only on semantic generalization. On Bridge, RT-2-X was queried
for its second-most-likely action because its top action was often all
zeros, the same workaround the OXE authors used (Appendix C).

Fine-tuning on Franka (Sec. 5.2, 7 tasks, 10 to 150 demos each, 129
rollouts per policy): full fine-tuning had the highest aggregate and was the
only method at or above 50% on every task. Diffusion Policy from scratch won
narrow single-instruction tasks; OpenVLA and Octo won multi-object language
tasks. Full fine-tuning cost 8 A100s for 5 to 15 hours per task.

Parameter-efficient fine-tuning (Table 1, 33 rollouts per row, Franka
tabletop, SigLIP-only variant): full FT 69.7 +/- 7.2%; LoRA rank 32
68.2 +/- 7.5% with 1.4% of parameters trained, 59.7 GB at batch 16; last
layer only 30.3%; frozen vision 47.0%. LoRA: one A100, 10 to 15 hours/task.

Quantization (Table 2, 80 rollouts per row, 8 Bridge tasks): bf16
71.3 +/- 4.8% at 16.8 GB; int8 58.1 +/- 5.1% at 10.2 GB; int4 71.9 +/- 4.7%
at 7.0 GB. The int8 drop is attributed to 1.2 Hz inference on an A5000
breaking the 5 Hz controller dynamics, not to token accuracy.

LIBERO (Table 12, 3 seeds x 500 trials per suite): OpenVLA fine-tuned
76.5 +/- 0.6% average vs Octo 75.1 and Diffusion Policy 72.4.

## What it changes in practice

- Weights and PyTorch code released (openvla.github.io; HuggingFace
  AutoModel, FSDP, FlashAttention, LoRA, quantized inference). Licence not
  stated; code MIT, weights under the Llama 2 community licence (unverified).
- Default fine-tuning recipe: LoRA rank 32 on all linear layers, one A100,
  10 to 15 hours, vision encoder unfrozen. Never freeze vision.
- Serving: bf16 on a 16 GB GPU, about 6 Hz on a 4090; int4 fits 7 GB; avoid
  int8. Inference rate must match the training controller or success drops.
- Quantile bins and dropping no-op transitions both mattered and are cheap.

## Known limitations and follow-ups

- Single image, no proprioception, no history, one action per pass; 3 to
  6 Hz rules out 50 Hz bimanual setups such as ALOHA (Sec. 6).
- Typical success below 90% even on tested tasks; robot-only fine-tuning
  costs semantic generalization relative to RT-2-X.
- OpenVLA-OFT (Kim et al., 2025) fixes the speed problem with parallel
  decoding, chunking and an L1 head; see that entry.

## Open questions

- Sec. 5.3 and 5.4 use a smaller SigLIP-only model on the Octo mixture
  (footnote 4). Do those conclusions hold for the released DinoSigLIP model?
- DROID never fit at 10% weight: mixture weight or capacity?
- Base VLM size, web co-training and vision features are untested (Sec. 6).

## Sources

- Paper: https://arxiv.org/abs/2406.09246 (arXiv HTML read 2026-09-05)
- Project page, code and weights: https://openvla.github.io
