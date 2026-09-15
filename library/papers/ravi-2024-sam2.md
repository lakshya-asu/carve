---
title: "SAM 2: Segment Anything in Images and Videos"
date: 2026-09-06
tags: [paper, perception, segmentation, video, tracking, foundation-model, promptable]
status: draft
source: https://arxiv.org/abs/2408.00714
---

# SAM 2 (Ravi, Gabeur, Hu, Hu, Ryali, Ma, Khedr, Rädle, Rolland, Gustafson, Mintun, Pan, Alwala, Carion, Wu, Girshick, Dollár, Feichtenhofer)

Read from arXiv v2 (28 Oct 2024), Meta FAIR. All numbers in v2 come from the "SAM 2.1"
checkpoints in the repo (footnote 1). Read Sec. 1 to 8 and Appendix A, C, D, E, F, H.

## Problem

SAM segments one image and forgets it. Robotics needs the spatio-temporal extent of an
object (a "masklet") as it moves, deforms, occludes, and reappears, from a few clicks on any
frame. Video object segmentation (VOS) datasets cover whole objects of fixed classes, not
parts, and pairing SAM with a tracker (XMem++, Cutie) means re-annotating frames from
scratch (Sec. 1, 2, 5.1).

## Core idea

Generalise the promptable task to video: clicks, boxes, or masks on any frame define an
object, the model propagates a masklet across the video, and prompts on other frames refine
it (Sec. 3). The model is SAM plus streaming memory: each frame's encoder features attend
over a memory bank of recent and prompted frames before the SAM decoder runs. On a single
image the memory is empty and it behaves as SAM (Sec. 4). A three-phase data engine with
SAM 2 in the loop built SA-V, 50.9K videos and 642.6K masklets (Sec. 5).

## Method details that matter for reimplementation

- Image encoder: MAE-pretrained Hiera; stride-16 and 32 features fused by an FPN into the
  frame embedding; stride-4 and 8 features skip into decoder upsampling for fine boundaries
  (Appendix D.1, Fig. 8). Sizes T, S, B+, L; B+ is default. Relative position bias was
  removed, which lets FlashAttention-2 run at 1024 (Table 10).
- Memory attention: L = 4 blocks of self-attention, cross-attention to memory features and
  object pointers, and MLP; 2D RoPE on spatial tokens (Appendix D.1).
- Memory bank: FIFO of up to N = 6 recent unprompted frames plus up to M prompted frames,
  stored as spatial maps projected to 64 channels (4x smaller, no loss, Table 9d). Temporal
  position is embedded only for recent frames. One object pointer per frame (the mask token)
  helps on SA-V val and LVOSv2, not on the 9 zero-shot sets (Table 11).
- Memory encoder: downsample the predicted mask, add it to the unconditioned encoder
  embedding, fuse with light conv layers. No second image encoder.
- Decoder additions: an occlusion head (extra token, MLP, cross-entropy) says whether the
  object is present. Multiple masks per frame remain; the highest predicted IoU one
  propagates. Multi-object runs memory and decoder per object on shared encoder features,
  with no inter-object communication (Appendix D.1, C).
- Training (Appendix D.2, Table 12): pre-train on SA-1B at 1024x1024, about 90k iters, lr
  4e-4, batch 256, bf16. Then joint training about 150k iters, each batch from either the
  image or the video source, encoder lr 6e-5 and rest 3e-4; 8-frame sequences, up to 2
  prompted frames, initial prompt = GT mask 50%, click 25%, box 25%; 7 correction clicks;
  order reversed 50%; 2x2 mosaic of the same video at 10% to force motion cues. Loss
  focal:dice:IoU(L1):occlusion(CE) = 20:1:1:1. Released model: SA-V manual + internal +
  SA-1B (about 70/15/15%), then a 16-frame fine-tune of 50k iters, encoder frozen.
- Ablations (Appendix A.2): 1024 input beats 512 at 0.22x speed (Table 9a); larger encoders
  help image and video, larger memory attention helps only video (Tables 9e, 9f).

## Result that matters

- Interactive video, 9 zero-shot datasets, 3 clicks per annotated frame: SAM 2 beats SAM+XMem++
  and SAM+Cutie offline and online on all 9, with over 3x fewer interactions (Fig. 5, Sec. 6.1).
- Semi-supervised VOS, 17 datasets, first-frame prompt only, mean J&F (Table 4): SAM 2 64.7
  (1 click), 75.3 (3), 77.6 (5), 74.4 (box), 79.3 (GT mask); SAM+Cutie 56.7, 70.1, 72.2, 69.4, 74.1.
- VOS benchmarks, first-frame GT mask, J&F (Table 6, Hiera-B+ / Hiera-L): MOSE val 76.6 /
  77.9; DAVIS 2017 val 90.2 / 90.7; SA-V val 76.8 / 77.9; SA-V test 77.0 / 78.4; YTVOS 2019
  val 88.6 / 89.3. Best prior on SA-V test is Cutie-base+ at 62.8. The variant on the
  released data mix (Table 17a, ‡) scores SA-V test 76.5 (T), 76.6 (S), 78.2 (B+), 79.5 (L).
- Image task, 1-click mIoU (Tables 5, 15): Hiera-B+ trained on SA-1B alone 58.9 on SA-23
  versus SAM ViT-H 58.1; full mix 61.9 on SA-23 and 69.6 on 14 new video sets versus SAM 59.1.
- Speed, single A100, bf16, compiled encoder (Appendix D.3): image task at batch 10, SAM 2
  130.1 FPS versus SAM ViT-H 21.7 and ViT-B 76.7 (Table 15). Video, batch 1: Hiera-B+ 43.8
  FPS, Hiera-L 30.2 FPS (Sec. 7).
- Data engine (Table 1, controlled study on 169 videos): SAM per frame 37.8 s; SAM plus
  mask propagation 7.4 s; full SAM 2 4.5 s per frame (8.4x faster) at equal or better
  alignment to manual masks. SA-V has 53x the masks of any prior VOS dataset (Table 3).

## What it changes in practice

- Licence and weights: checkpoints, training code, and demo code are Apache 2.0; SA-V is CC
  BY 4.0 (Sec. 1, model card Table 18).
- Inference cost: 30 to 44 FPS for one object on an A100 at 1024 input (Sec. 7). N tracked
  objects cost about N memory-plus-decoder passes on one shared encoder pass (Appendix D.1).
  No figure for lower-end GPUs is given.
- For a cutting cell this is the tracker for a primal or a cut line once a first mask exists
  (fixture prior, detector box, or one operator click), and the occlusion head is the signal
  that the target is behind the blade or gripper (our inference, untested).
- Hiera-B+ replaces SAM ViT-H for still-image prompting at 6x the throughput and higher
  mIoU (Table 5); Hiera-T and S sit 1.6 to 1.7 J&F below B+ on SA-V test (Table 17a).

## Known limitations and follow-ups

- Fails across shot changes; loses or confuses objects in crowds, after long occlusions, and
  in long videos; struggles with thin, fast-moving structures and near-identical neighbours
  (juggling balls). Recovery relies on a human re-prompt (Appendix C).
- No explicit motion model and no inter-object reasoning; both named as future work.
  Training windows are 8 then 16 frames; long-video accuracy rests on LVOS (Table 17b, c).

## Open questions

- With a static overhead camera and a moving blade, does the 6-frame FIFO plus prompted-frame
  memory hold a mask on tissue whose topology changes at every cut? SA-V tests deformation and
  reappearance, not repeated splitting.
- Batch-1 video FPS on an RTX-class or Jetson GPU, and the encoder versus memory-attention
  latency split, are not in the paper and need a bench on our hardware.

## Sources

- Paper: https://arxiv.org/abs/2408.00714 (v2, 28 Oct 2024). Sec. 1, 3 to 7; Tables 1, 3 to 6, 9 to 12, 15, 17, 18; Fig. 5, 8; Appendix A.2, C, D, E, F.3.
- Code, weights, demo: https://github.com/facebookresearch/sam2 and https://ai.meta.com/sam2. Predecessor entry: kirillov-2023-segment-anything.md
