---
title: "Segment Anything"
date: 2026-09-06
tags: [paper, perception, segmentation, foundation-model, promptable, data-engine]
status: draft
source: https://arxiv.org/abs/2304.02643
---

# Segment Anything (Kirillov, Mintun, Ravi, Mao, Rolland, Gustafson, Xiao, Whitehead, Berg, Lo, Dollár, Girshick)

Read from arXiv v1 (5 Apr 2023), Meta AI Research (FAIR). Main text Sec. 1 to 8 plus
Appendix A (model, training), B (automatic mask generation), and F (dataset and model cards).

## Problem

Segmentation models were trained per task and per dataset, and mask labels are scarce on
the web, so there was no promptable, zero-shot "foundation model" for segmentation.
Interactive segmenters (RITM, FocalClick, SimpleClick) need several clicks and average over
the ambiguity of one click: a point on a shirt could mean shirt or person (Sec. 1, 2; Fig. 3).

## Core idea

Define a "promptable segmentation" task: given any prompt (foreground/background points, a
box, a rough mask, or text), return at least one valid mask even when the prompt is
ambiguous (Sec. 2). Train one model for it on a dataset built by a three-stage data engine
in which the model itself annotates (Sec. 4). The result, SA-1B, has 1.1B masks on 11M
licensed images, 99.1% of them fully automatic (Sec. 5). Downstream tasks are solved by
prompting rather than fine-tuning: detector boxes, a point grid, or CLIP text embeddings
(Sec. 7).

## Method details that matter for reimplementation

- Split (Sec. 3, Appendix A): a heavy image encoder runs once per image; prompt encoder plus
  two-layer mask decoder run per prompt in about 50 ms on CPU in a browser from a cached
  embedding, under 1% of encoder compute. No encoder latency is given.
- Image encoder: MAE-pretrained ViT-H/16, 14x14 windowed attention with four global blocks,
  input 1024x1024 (rescale, pad shorter side), output 256x64x64 after 1x1 and 3x3
  convolutions with layer norm. Sizes (Fig. 13): ViT-B 91M, ViT-L 308M, ViT-H 636M params.
  ViT-H over ViT-L is a marginal gain; over ViT-B it is substantial (Sec. 7.6).
- Prompt encoder: points and boxes are positional encodings plus learned type embeddings;
  masks pass through a small conv stack; text uses the CLIP text encoder (Appendix A).
- Mask decoder: two blocks of token self-attention, two-way cross-attention, and MLP; dim
  256, 8 heads; embedding upsampled 4x by transposed convolutions; mask = dot product of
  upsampled embedding and an MLP-projected output token (Appendix A, Fig. 14).
- Ambiguity: three mask tokens (whole, part, subpart), loss only from the lowest-loss mask;
  an IoU-prediction head (MSE loss) ranks them. A fourth token is the sole output when more
  than one prompt is given (Appendix A).
- Training simulation: first prompt is a foreground point or a box with noise of 10% side
  length (max 20 px); then 8 points from the error region; plus two iterations that only
  feed back the previous logits; 11 iterations total (Appendix A).
- Recipe: AdamW, lr 8e-4 after 250 warmup iters, 90k iters (about 2 SA-1B epochs), batch
  256, weight decay 0.1, drop path 0.4, layer-wise lr decay 0.8, no augmentation, 256 GPUs,
  up to 64 masks per GPU, focal:dice 20:1, masks over 90% of the image dropped (Appendix A).
- Automatic mask generation (Appendix B): 32x32 point grid plus 20 zoomed crops; keep masks
  with predicted IoU at or above 88.0 and stability IoU (logit thresholds -1 and +1) at or
  above 95.0; drop masks covering 95% or more of the image; box NMS at 0.7; remove
  components and fill holes under 100 px.
- Data engine (Sec. 4): assisted-manual, 4.3M masks on 120k images, time per mask fell from
  34 s to 14 s over 6 retrains; semi-automatic, 5.9M more masks on 180k images; fully
  automatic on 11M images. Training on automatic masks alone loses about 0.5 mIoU (Sec. 7.6).

## Result that matters

- Single center-point prompt, 23 zero-shot datasets, mIoU of the most confident mask: SAM
  beats RITM on 16 of 23, by up to about 47 IoU; with an oracle picking the best of its three
  masks it beats RITM on all 23 (Fig. 9a). Human ratings average 7 to 9 on a 1 to 10 scale,
  above RITM on every rated dataset (Fig. 9b). With 9 points the gap closes and SAM is "not
  optimized for the very high IoU regime" (Fig. 9c).
- Instance segmentation with ViTDet-H boxes as prompts (Table 5): mask AP 46.5 on COCO and
  44.7 on LVIS v1 versus 51.0 and 46.6 for fully supervised ViTDet-H. Annotators still rated
  SAM masks above ViTDet masks on LVIS (7.9 versus 7.6, Fig. 11).
- LVIS v1 proposals, AR@1000 (Table 4): SAM 59.3 versus 63.0 for ViTDet-H; SAM wins on
  medium, large, rare, and common objects, loses on small and frequent ones.
- SA-1B mask quality (Sec. 5): on 500 sampled images, 94% of automatic masks have over 90%
  IoU against professionally corrected masks. Data scaling (Fig. 13): 1M images is
  comparable to the full 11M; 0.1M drops sharply.

## What it changes in practice

- Licence and weights: code and weights are Apache 2.0 (Sec. 1 "Release", Appendix F model
  card). SA-1B is released for research under its own terms, faces and plates blurred,
  shortest side 1500 px (Sec. 5, dataset card).
- Inference cost: only the prompt-side latency is reported (about 50 ms on CPU per prompt)
  and the paper calls the full ViT-H pipeline "not real-time" (Sec. 8). SAM 2 later measured
  SAM ViT-H at 21.7 FPS on an A100, batch 10, see ravi-2024-sam2.md.
- For a cutting cell the usable mode is box- or point-prompted masks from a detector or a
  fixture prior; text-to-mask is a stated proof of concept (Sec. 7.5). One encoder pass can
  serve many prompts on a static camera (our inference, untested).

## Known limitations and follow-ups

- Misses fine structures, hallucinates small disconnected components, and gives less crisp
  boundaries than zoom-in methods such as FocalClick; expected to lose to dedicated
  interactive and domain-specific tools (Sec. 8). No prompt design for panoptic segmentation.
- No temporal memory. SAM 2 (arXiv 2408.00714) adds streaming memory and a smaller Hiera
  encoder, and reports higher SA-23 mIoU at 6x the speed. SAM 2 also cites HQ-SAM
  (quality) and EfficientSAM, MobileSAM, FastSAM (speed) as derivatives.

## Open questions

- SA-1B is licensed photographer imagery and the 23-dataset suite has no food-processing
  domain. How far does single-point mIoU fall on glossy, low-texture meat under cell lighting?
- The 88.0 IoU and 95.0 stability thresholds were tuned for SA-1B mask counts. Are they the
  right operating point for a fixed-object cell with few masks per frame?

## Sources

- Paper: https://arxiv.org/abs/2304.02643 (v1, 5 Apr 2023). Sec. 1 to 5, 7, 8; Tables 4, 5; Fig. 9, 11, 13, 14; Appendix A, B, F.
- Code and weights: https://github.com/facebookresearch/segment-anything
- Project and dataset: https://segment-anything.com
