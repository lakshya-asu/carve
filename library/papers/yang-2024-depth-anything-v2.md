---
title: "Depth Anything V2"
date: 2026-09-06
tags: [paper, perception, monocular-depth, synthetic-data, pseudo-labels, dinov2]
status: draft
source: https://arxiv.org/abs/2406.09414
---

# Depth Anything V2 (Yang, Kang, Huang, Zhao, Xu, Feng, Zhao)

Read from arXiv v2 (20 Oct 2024), the NeurIPS 2024 version, HKU and TikTok. Builds on
Depth Anything V1 (arXiv 2401.10891) and DINOv2 (oquab-2023-dinov2.md).

## Problem

Monocular depth models trained on real labelled data inherit the sensor's failures: depth
cameras miss transparent objects, stereo labels fail on textureless surfaces, SfM labels
break on moving objects, and all are coarse at boundaries (Sec. 2, Fig. 3, 4), giving
over-smoothed depth and wrong depth on glass and mirrors. Diffusion models (Marigold) get
fine detail from synthetic data but run at seconds per image (Table 1).

## Core idea

Train only on synthetic images, whose depth labels are exact at every pixel, and cross the
synthetic-to-real gap with two levers: a large teacher (DINOv2-G encoder, 1.3B params)
that transfers where smaller encoders do not (Fig. 5), and 62M unlabelled real images the
teacher pseudo-labels. Students (ViT-S/B/L/G) train only on the pseudo-labelled real
images; synthetic images are dropped at that stage (Sec. 5.1, Table 5). Distillation is at
the label level through real images, not the feature level (Sec. 4, 8).

## Method details that matter for reimplementation

- Architecture: DINOv2 encoder plus DPT decoder, as in V1 (Sec. 7.1); output is
  affine-invariant inverse depth, so base models give relative depth only (Sec. 5.2).
- Teacher synthetic set (Table 7): BlendedMVS 115K, Hypersim 60K, IRS 103K, TartanAir
  306K, VKITTI 2 20K, total 595K. Hypersim and IRS (indoor) transfer best; VKITTI 2 scores
  worst but sharpens thin structures (Table 9, ViT-L).
- Pseudo-labelled real set (Table 7): BDD100K, Google Landmarks, ImageNet-21K, LSUN,
  Objects365, Open Images V7, Places365, SA-1B, total 62M; 62M diverse images beat 11M
  (SA-1B only) at equal iterations (Table 11).
- Losses: MiDaS scale-and-shift-invariant loss plus gradient-matching loss at ratio 1:2
  (Sec. 7.1); the gradient term only helps with exact synthetic labels (Appendix B.7). On
  pseudo-labelled images a DINOv2 feature alignment loss is added and the top 10%
  largest-loss pixels per sample are ignored (Sec. 5.2).
- Training (Sec. 7.1): 518x518 crops after resizing the short side to 518. Teacher batch
  64, 160K iterations; students batch 192, 480K. Adam, lr 5e-6 encoder, 5e-5 decoder.
- Encoder choice (Appendix B.6, Table 13, synthetic-only): DINOv2-L beats BEiT-L, SAM-L
  and SynCLR-L (NYU-D AbsRel 0.048 versus 0.068, 0.186, 0.344); DINOv2-G with registers
  is worse than plain DINOv2-G (0.061 versus 0.044), so original DINOv2 is used.
- Mixing even 5% real labelled data (HRWSI) into the teacher set destroys the fine detail
  (Appendix B.9). Test-time resolution can go 2x to 4x above 518 (Appendix B.8).

## Result that matters

Standard zero-shot relative benchmarks (Table 2, AbsRel / delta-1): V2 ViT-L KITTI 0.074 /
0.946, NYU-D 0.045 / 0.979, about equal to V1 ViT-L (0.076 / 0.947, 0.043 / 0.981) and
better than MiDaS V3.1. The authors argue these test sets are too noisy (Sec. 6.1, Fig. 8).

DA-2K, the authors' own 1K-image, 2K-pair relative-depth benchmark over eight scenarios
(Table 3, pairwise ordering accuracy): ViT-S 95.3, ViT-B 97.0, ViT-L 97.1, ViT-G 97.4,
versus V1 88.5, Marigold 86.8, Geowizard 88.1; transparent/reflective 96.3 for ViT-L
(Table 14). The authors' model voted on which pairs got human review (Sec. 6.2).

Transparent surfaces (Table 12, NTIRE 2024 Transparent Surface Challenge, delta-1):
zero-shot V2 0.836 versus V1 0.535 and MiDaS 0.259; fine-tuned 0.912 against 0.758 from a
plain DINOv2 initialisation and 0.917 for first place.

Metric depth after in-domain fine-tuning via the ZoeDepth pipeline (Table 4): NYU-D ViT-L
AbsRel 0.056, RMSE 0.206 m, delta-1 0.984; KITTI ViT-L AbsRel 0.045, RMSE 1.861 m. ViT-S
(NYU-D AbsRel 0.073) beats ZoeDepth ViT-L (0.077). Pseudo-labels lift ViT-S DA-2K from
89.8 to 95.3 (Table 5) and beat DIML's own labels (Table 6, NYU-D AbsRel 0.062 vs 0.074).
Speed (Fig. 1, V100, resolution unspecified, the only latency numbers in the paper):
ViT-S 60 ms at 25M params, ViT-L 213 ms at 335M params, Marigold 5.2 s.

## What it changes in practice

- Licence (repo README, not the paper): Small under Apache 2.0; Base, Large and Giant under
  CC-BY-NC-4.0, so for a commercial cell only the 24.8M-parameter Small is usable without
  a separate agreement. Giant weights were "coming soon" on 2026-09-06.
- Metric depth: released metric models are fine-tuned on Hypersim (indoor, max depth
  20 m) and Virtual KITTI (outdoor, 80 m), not NYU or KITTI, because real labels
  reintroduce noise (Sec. 7.3; max-depth values from the repo metric_depth README). No
  metric accuracy is reported for these releases, only Fig. 15. At sub-metre cutting range
  a 20 m model gives coarse scale; fine-tune on our own stereo labels (our inference, untested).
- Wet, specular meat: the transparent-surface gains (Table 12) are the nearest evidence
  the recipe helps on specular material. No organic or food scenes appear in the training
  tables or DA-2K keywords (Table 15); untested. ViT-S at 60 ms on a V100 is the only
  real-time option; Jetson-class timing is unmeasured (unverified).

## Known limitations and follow-ups

- Appendix D: 62M-image training is expensive and the synthetic sets lack diversity.
  Failures before pseudo-labelling (Fig. 6) were sky and human heads, absent from the
  synthetic sets. Any domain missing from both sources is at risk.
- DA-2K only pops out pairs with predicted depth ratio above 3 (Appendix C.3), so it
  measures coarse ordering, not metric accuracy. Prompt Depth Anything (Dec 2024, repo
  news) adds LiDAR prompting; not read (unverified).

## Open questions

- How much fine detail survives with the encoder frozen inside a policy, without the DPT head?
- Would a teacher tuned on synthetic meat renders plus pseudo-labels on our own footage
  reproduce the Table 5 gains at our scale?

## Sources

- Paper: https://arxiv.org/abs/2406.09414 (v2, 20 Oct 2024). Sec. 2 to 7; Tables 2 to 7,
  9, 11 to 15; Fig. 1, 5, 6, 8, 10 to 12, 15; Appendix B.6 to B.9, C.3, D.
- Code and weights: https://github.com/DepthAnything/Depth-Anything-V2 (README and
  metric_depth/README read 2026-09-06 for licence, parameters, max-depth settings).
