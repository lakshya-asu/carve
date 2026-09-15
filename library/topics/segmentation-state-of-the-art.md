---
title: Segmentation methods judged on boundary accuracy, not IoU
date: 2026-09-11
tags: [topic, perception, segmentation, boundary-accuracy, sam, yolo, rgb-d, specular, meat-cell]
status: draft
source: synthesis   # primary links in Sources; unverified items are tagged inline
---

# Segmentation methods judged on boundary accuracy, not IoU

## The question this note answers

The cell is an overhead RGB-D camera, 1280 by 960, 570 mm above the product, 0.58 mm per pixel
([geometry](perception-ingestion.md#the-camera-model-checked-against-the-renderer)), watching raw meat slabs on a moving
dark belt while an arm intercepts them and aligns them into a cutter. Pose is read off the segmentation boundary: area
centroid for the point, principal axis of the filled region for the yaw. The bound is 2 mm of centroid error and 2
degrees of axis error.

Nobody publishes on that problem. Every headline number in the segmentation literature is IoU, mask AP or mIoU, and all
three are area-overlap measures nearly blind to where the contour sits. So the note is organised around one substitution:
wherever a method advertises accuracy, ask what it does to the **position** of the contour in millimetres, and if the
paper does not say, say so.

## The error budget, so the rest of the note has a yardstick

Boundary error is not one quantity, and the three kinds behave completely differently. Measured 2026-09-11 on a 200 by 80
mm slab outline at 0.58 mm per pixel, 2000 boundary samples, 300 trials per row, NumPy 1.21.5 on an i7-8750H. Centroid
from the shoelace formula, axis from the **filled polygon's** second moments by Green's theorem: using the outline's
point covariance instead changes the axis numbers by up to a factor of two on the correlated rows.

**Kind 1: independent per-pixel noise. Nearly free.** Errors cancel around the perimeter.

| Boundary noise, std | Correlation length | Centroid p50 | Centroid p95 | Axis p95 |
|---|---|---|---|---|
| 1.0 px (0.58 mm) | 1 point (independent) | 0.035 mm | 0.073 mm | 0.034 deg |
| 5.0 px (2.90 mm) | 1 point (independent) | 0.176 mm | 0.396 mm | 0.179 deg |
| 5.0 px (2.90 mm) | 50 points (about 15 mm of arc) | 1.043 mm | 2.047 mm | 1.183 deg |
| 2.0 px (1.16 mm) | 400 points (about 120 mm of arc) | 1.141 mm | 1.789 mm | 0.915 deg |
| 5.0 px (2.90 mm) | 400 points | 2.655 mm | 4.328 mm | 2.407 deg |

Five pixels of independent jitter costs 0.18 mm. The same 5 px organised into blob-sized patches costs 1.0 mm, and into
whole-edge patches 2.7 mm. **Sharpness is not what we need. Freedom from correlated error is.**

**Kind 2: uniform dilation or erosion. Exactly free.** Growing the whole contour by 1, 2, 5 or 10 px moves the centroid
by 0.000 mm and the axis by 0.000 deg, because the shift is symmetric. A mask that is coarse *evenly* is fine for pose.
It is only a problem for the clearance number the gripper uses.

**Kind 3: one-sided bias and local bites. The whole problem.**

| Perturbation | Centroid error | Axis error |
|---|---|---|
| One long edge pushed out 1 px (0.58 mm) | 0.318 mm | 0.000 deg |
| One long edge pushed out 5 px (2.90 mm) | 1.592 mm | 0.002 deg |
| One long edge pushed out 10 px (5.80 mm) | 3.187 mm | 0.006 deg |
| Bite 10 mm deep over 2 % of the perimeter | 0.952 mm | 0.139 deg |
| Bite 10 mm deep over 10 % of the perimeter | 1.965 mm | 0.647 deg |
| Bite 10 mm deep over 20 % of the perimeter | 3.801 mm | 2.033 deg |

The budget is spent by a 5 px one-sided bias, or by one 10 mm deep bite along a tenth of the outline. A 10 mm bite is 17
px here: the size of one specular blowout. That is the quantitative link between the specular failure and the pose bound.

Read the axis column separately. On a 2.5-aspect slab the centroid is the binding constraint and yaw is forgiving;
nothing short of a fifth of the perimeter being eaten moves it by 2 degrees. The axis only binds when the piece is nearly
round, where it does not degrade but collapses ([aspect table](perception-technique-selection.md)).

## What we already measured, and what it implies

Three classical methods, 40 poses per condition, from `experiments/data/2026-09-11-segmentation.json`:

| Method | Clean, mean / worst centroid | Noise sigma 15 | 3 specular blobs, mean / worst | Purge 15 x 40 px, mean / worst |
|---|---|---|---|---|
| HSV colour threshold | 0.151 / **2.685 mm** | **9.373 mm** | 4.452 / 58.2 mm | 0.086 / 0.442 mm |
| Canny plus contour fill | 0.081 / 0.338 mm | 0.078 mm | 21.7 / **814.9 mm** | 7.59 / **217.7 mm** |
| Adaptive grey threshold | 1.147 / 7.04 mm, 9 failures | 1.144 mm | 1.20 mm, 22 failures | 1.84 mm, 29 failures |

Read against the budget the diagnosis is precise. The edge method has essentially no boundary bias when it works: 0.081
mm is a seventh of a pixel, already sub-pixel, and no refinement method in section 4 can improve on it. Its 815 mm
failure is not a boundary error at all, it is a **topology** error, because a specular highlight closes a contour that
beats the product on area and the wrong connected component is selected. The colour threshold has the opposite profile:
it never picks the wrong object and fails by a drift of the decision level that appears as one-sided bias, kind 3.

**The failures we measured are selection and bias failures, not resolution failures.** A method that produces a prettier
contour on COCO fixes neither. The architecture already in `src/meat_cell_sim/evidence.py` (depth proposes, appearance
refines the boundary, colour confirms) is the right response, and this note surveys what can fill each slot.

## 1. Promptable and foundation segmentation

### The decoder ceiling nobody advertises

Every model in the SAM family emits its mask as a **256 by 256 logit grid** and bilinearly upsamples. This is in the
source, not the papers: SAM 1 runs two `ConvTranspose2d(k=2, s=2)` on the 64 by 64 embedding
([mask_decoder.py](https://github.com/facebookresearch/segment-anything/blob/main/segment_anything/modeling/mask_decoder.py)),
SAM 2 keeps them and adds skips that change what the cells contain rather than the grid
([sam2](https://github.com/facebookresearch/sam2/blob/main/sam2/modeling/sam/mask_decoder.py)), SAM 3 reuses the same
file, and HQ-SAM sums its high-quality logits into the same tensor before upsampling
([mask_decoder_hq.py](https://github.com/SysCV/sam-hq/blob/main/segment_anything/modeling/mask_decoder_hq.py)). On our
frame that is **5.0 px, 2.90 mm per cell**. SAM 2 and SAM 3 make one axis worse by squashing a 4:3 frame to square rather
than letterboxing: `Resize((1024, 1024))` in
[sam2/utils/transforms.py](https://github.com/facebookresearch/sam2/blob/main/sam2/utils/transforms.py) and
`v2.Resize(size=(1008, 1008))` in SAM 3's image processor. Neither paper mentions it. Against the error budget this is
survivable, because logits are interpolated before thresholding so the zero crossing lands inside a cell, putting the
error near the independent-noise row. A systematic sub-cell bias would not be survivable, and nobody has measured whether
one exists.

### Cost, licence, and what each paper actually measures

| Model | Latency, with the conditions stated | Licence | Boundary metric reported |
|---|---|---|---|
| SAM 1 ViT-H | 46.1 ms A100 bf16 compiled **batch 10** ([SAM 2 Table 15](https://arxiv.org/abs/2408.00714)); 446 ms RTX 3090 plain PyTorch ([FastSAM Table 1](https://arxiv.org/abs/2306.12156)); 452 ms unnamed GPU ([MobileSAM](https://arxiv.org/abs/2306.14289)) | Apache 2.0 | none: mIoU, BSDS edge ODS, mask AP, a 1-10 human rating |
| SAM 2 Hiera-B+ / L | 7.7 / 16.3 ms A100 batch 10 image; **43.8 / 30.2 FPS batch 1** video propagation | Apache 2.0, code and checkpoints | J&F only, never split into J and F |
| SAM 3 | 30 ms for one image with 100+ objects, **H200** ([arXiv 2511.16719](https://arxiv.org/abs/2511.16719)) | bespoke "SAM License", field-of-use bans, unilateral amendment clause, gated weights | none |
| HQ-SAM ViT-L | 5.0 to 4.8 FPS, **hardware never stated** ([arXiv 2306.01567](https://arxiv.org/abs/2306.01567)) | Apache 2.0 code and weights; training data is not | mIoU, mBIoU, AP_B |
| MobileSAM | 8 ms encoder + 4 ms decoder, unnamed GPU | Apache 2.0 | none |
| EfficientSAM-Ti / S | 54 / 47 images per second, A100, 1024 px ([arXiv 2312.00863](https://arxiv.org/abs/2312.00863)) | Apache 2.0 | none |
| FastSAM | 40 ms RTX 3090, invariant to prompt count because prompting is post-processing | **AGPL-3.0**, despite the README saying Apache | none |

Two corrections to common claims. **SAM 2's licence did not change**: both LICENSE files have exactly one commit and were
never edited, and SAM 2's README covers checkpoints explicitly. The change is at **SAM 3**. And **FastSAM is a commercial
dead end**: its LICENSE is the unmodified AGPL-3.0 text inherited from the vendored Ultralytics package, and
[Ultralytics licensing](https://www.ultralytics.com/license) names "embedded deployments in hardware, edge devices,
robotics, cameras, or appliances" as requiring the paid Enterprise licence.

Be sceptical of the latency spread: four primary sources give SAM ViT-H's encoder as 500, 452, 446 and 46 ms, a factor of
ten for the same weights, explained entirely by precision, compilation and batching, and almost nobody states all three.
**None of them runs on CPU at line rate**: OpenVINO's committed benchmark for the SAM 2 Hiera-L encoder is 0.61 FPS FP32
and 0.88 FPS INT8 at 1024 px, CPU only, 36 threads
([log](https://github.com/openvinotoolkit/openvino_notebooks/blob/latest/notebooks/sam2-image-segmentation/segment-anything-2-image.ipynb)).

### SAM-HQ's boundary claim, and how much survives

HQ-SAM adds a learnable output token plus early ViT feature fusion, 5.1 M trainable parameters on a frozen SAM, four
hours on 8 RTX 3090. ViT-L with ground-truth box prompts, mIoU / mBIoU: DIS 62.0/52.8 becomes 78.6/70.4, ThinObject-5K
73.6/61.8 becomes 89.5/79.9, average 79.5/71.1 becomes 89.1/81.8. The 8.4-point average gap between SAM's mIoU and mBIoU
is the quantification of "blobby boundaries", and HQ-SAM does not close it: still 7.3 points after the fix.

Three deflations from its own tables. On COCO the boundary gain is **1.1 AP_B** (33.3 to 34.4) against 10.7 mBIoU on
fine-structure sets, and the mask-minus-boundary gap is 15.2 for SAM and 15.1 for HQ-SAM, so on natural photos it narrows
the deficit by nothing. Removing the training splits drops DIS from 78.6/70.4 to 72.9/63.1, so 6 to 9 points is in-domain
training. Recall at a strict Boundary IoU of 0.9 reaches only about 69 percent on COIFT even for HQ-SAM.

**The metric does not certify millimetres.** Boundary IoU's band is set by annotator agreement: d = 2 percent of the
image diagonal, chosen because median agreement between two experts exceeds 0.9 there. On our 1600 px diagonal that is
**32 px, 18.6 mm**, and the strict 1 percent setting is 9.3 mm. A 10-point mBIoU gain is evidence about an 18 mm
tolerance. It is an annotation-agreement metric, deliberately blind below the human labelling floor, and useful to us
only re-run with `dilation_ratio` around 0.003, which is off-label. The only SAM-family boundary error published in pixel
units is medical: Hausdorff distance from **2.19 px (humerus CT) to 23.7 px (heart CT)** with a ground-truth box prompt,
and ViT-H is not consistently better than ViT-B ([arXiv 2304.14660](https://arxiv.org/abs/2304.14660) Table 3).

### Using a depth-derived proposal as the prompt

**Give it a box, not a mask, and not a point.** SAM 2's first-frame ablation over 17 video datasets: 1 click 64.7 J&F,
box 74.4, 3 clicks 75.3, 5 clicks 77.6, ground-truth mask 79.3. On wet specular surgical instruments the box is worth far
more: 89.19 IoU against 53.88 for one point on EndoVis17, beating every supervised baseline while point-prompted SAM
loses to all of them ([arXiv 2304.14674](https://arxiv.org/abs/2304.14674)). The harder and less texture-distinctive the
domain, the more a box buys.

**Box tightness is plausibly the dominant error term, not model choice.** SAM ViT-L on the HQ suite: a ground-truth box
gives 79.5 mIoU / 71.1 mBIoU, a noisy box **48.8 / 42.1**, barely better than a single point
([Stable-SAM, arXiv 2311.15776](https://arxiv.org/abs/2311.15776)). A 2026 study of 25,000 real human boxes reports a
per-object spread of ±12 to ±17 IoU and an adversarial envelope of 14.31 IoU for SAM ViT-H against **30.30 for SAM 2.1
Hiera-L** ([BREPS, arXiv 2601.15123](https://arxiv.org/abs/2601.15123), not independently verified). If the box comes
from a depth threshold rather than a human, SAM 1 ViT-H or SAM-HQ is the safer backbone than SAM 2.1.

**Never hand SAM 2's video mode a mask.** The shipped SAM 2.1 configs set `use_mask_input_as_output_without_sam: true`,
documented in source as "we directly output the mask input (see it as a GT mask) without using a SAM prompt encoder +
mask decoder". A depth-thresholded mask passed to `add_new_mask` is accepted verbatim, never refined, and its errors go
into the memory bank and propagate forward. On the image path the logit scale is `logits = binary * 20.0 - 10.0`; a raw
0/1 float puts background at sigmoid 0.5, an ambiguous prompt at every background pixel, which is probably why vanilla
SAM collapses from 70.4 to 41.8 mBIoU on a coarse-mask prompt.

**Depth should say where, not what shape.** On transparent and reflective objects, adding depth to RGB *costs* boundary
F-measure: MSMFormer falls from 49.6 to 15.9 on PhoCAL ([UOIS-SAM, arXiv 2409.15481](https://arxiv.org/abs/2409.15481)).
The apparent counter-example, ZISVFM reporting 36.7 to 78.5 boundary F on OCID, is an annotation artefact, since OCID's
ground truth is generated by depth differencing; on manually annotated OSD the same comparison is 41.3 against 42.7.

On video mode generally: the memory bank is fixed size and cheap (halving memory attention costs 1.0 J&F for a 1.13x
speedup, while shrinking the image encoder costs 2.8 for 1.33x), but `init_state()` does not stream, there is no camera
predictor in the official repo, and the named failure modes (thin details when fast-moving, confusion between "nearby
objects with similar appearance") both describe identical slabs on a belt.

## 2. Modern instance segmentation

### Boundary AP, and why mask AP is the wrong number

The primary source is Cheng, Girshick, Dollar, Berg and Kirillov, *Boundary IoU: Improving Object-Centric Image
Segmentation Evaluation*, CVPR 2021 ([arXiv 2103.16562](https://arxiv.org/abs/2103.16562),
[code](https://github.com/bowenc0221/boundary-iou-api)). Intersect each mask with a band of width d inside its own
contour and take ordinary IoU of the two bands, so a large correct interior cannot inflate the score. Boundary AP is COCO
AP with the matching IoU replaced by `min(Mask IoU, Boundary IoU)`.

Their controlled experiment is the number to remember. Push ground-truth COCO masks through a 28 by 28 raster and back:

| Metric on ground truth quantised to 28x28 | AP | AP_S | AP_M | AP_L |
|---|---|---|---|---|
| Mask AP | 96.5 | 98.9 | 95.7 | **95.0** |
| Boundary AP | 85.9 | 98.9 | 93.0 | **73.0** |

On large objects, mask AP calls a 28 by 28 staircase 95 percent correct. Our slabs are large objects. Real Mask R-CNN
with ground-truth boxes shows the same shape, 66.0 against 25.9 on large objects. And the fix is not capacity: scaling
R50 to R101 to X101 moves boundary AP by +0.5 then +0.4, while swapping the mask head for PointRend moves large-object
boundary AP by **+8.5**.

### YOLO26, stated carefully, since it is already trained

YOLO26 is an Ultralytics release. Its documentation page first appears in the repo on **2025-09-25**; weights and code
shipped with `v8.4.0` on **2026-01-13/14**, whose release body reads "Ultralytics YOLO26 has arrived"
([release](https://github.com/ultralytics/ultralytics/releases/tag/v8.4.0)); the paper followed on **2026-06-02**
([arXiv 2606.03748](https://arxiv.org/abs/2606.03748)). It is a vendor preprint with no evidence of peer review, but the
NMS-free dual head, DFL removal (`reg_max: 1`, `end2end: True` in the seg YAML), ProgLoss, STAL and the MuSGD optimiser
are no longer blog-only claims. **Licence: AGPL-3.0 or a paid Ultralytics Enterprise licence, for code, models and
documentation alike.** The arXiv paper is CC BY 4.0; that covers the PDF, not the weights, and the two get conflated.

A segmentation variant is fully released, five scales, COCO val2017 at 640, T4 with TensorRT10 (the docs footnote still
says an EC2 P4d, which is stale copy; the paper says T4 FP16): YOLO26n-seg 33.9 mask AP at 2.1 ms and 53.3 ms CPU ONNX,
YOLO26m-seg 44.1 at 6.7 ms, YOLO26x-seg 47.0 at 16.4 ms. That is +1.9 to +3.2 mask AP over YOLO11-seg.

**The mask head is the 2019 YOLACT arrangement and YOLO26 did not change its resolution.** `Segment.__init__` takes
`nm=32` prototypes and wires `Proto` to `ch[0]`, the stride-8 P3 feature, and `Proto` contains exactly one
`ConvTranspose2d(c_, c_, 2, 2, 0)`
([head.py](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/nn/modules/head.py)): 32 prototypes at stride
4 of the model input, 160 by 160 at `imgsz=640`. YOLO26's `Proto26` adds P4 and P5 into the P3 proto input, improving
what the prototypes encode, then calls the same single 2x transpose, and the seg YAML still requests 32. The paper's own
ablation is honest about the size of the win: YOLO11s 32.0 mask AP, plus multi-scale proto 32.4, plus the auxiliary
semantic loss 32.7. Three generations of backbone work, one unchanged mask output resolution.

On our camera: at `imgsz=640` one prototype cell spans 8.0 source px, **4.64 mm**; at 1280, 4.0 px and 2.32 mm; with a P2
head, 2.0 px and 1.16 mm. Two experiments follow and neither needs new labels. Set `retina_masks=True`, which
interpolates the prototype logits once, straight to full sensor resolution, and thresholds there, instead of thresholding
at 640 and resizing a uint8 mask
([ops.py](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/utils/ops.py)); then fit the pose to the
interpolated logit zero crossing rather than to `findContours` on a binarised mask, which is integer-valued by
construction. Retraining at 1280 halves the pitch again. `yolo26-p2.yaml` exists but ships as YAML only with no released
weights, and whether its head actually attaches the proto to P2 needs a read of the YAML before anyone promises it
(unverified). The structural limit no resolution fixes: 32 prototypes is a 32-dimensional linear basis for every mask in
the image, which is probably plenty for one broadly similar shape family and not for a thin fat-trim tail.

### The rest of the field

**RT-DETR has no instance segmentation variant**, in v1, v2 or v3: detection-only in title, abstract and repo, and
Ultralytics' `RTDETR.task_map` returns only `"detect"`. D-FINE and DEIM are likewise detection only, and DEIM's licence
reads NOASSERTION on GitHub.

**RF-DETR-Seg is the licence-clean competitor worth a trial**, Apache-2.0, DINOv2 backbone, NAS over accuracy-latency
Pareto curves ([arXiv 2511.09554](https://arxiv.org/abs/2511.09554), ICLR 2026;
[repo](https://github.com/roboflow/rf-detr)). Roboflow re-measured every row in-house with pycocotools on the full 5,000
image val2017 split, so rows are mutually comparable: RF-DETR-Seg-M is 45.3 mask AP at 5.9 ms and **432 by 432 input**,
against YOLO26-M-Seg at 44.0 and 6.32 ms at 640. A 432 px model beating a 640 px one on mask AP is itself evidence that
the metric is dominated by semantic correctness, not boundary placement. Their mask head is not described in the paper
and I did not read the source (unverified). **Mask2Former** ([arXiv 2112.01527](https://arxiv.org/abs/2112.01527), MIT)
is one of the few architectures reporting Boundary AP alongside mask AP: R50 43.7 against 30.6, Swin-L 50.1 against 36.2,
at 9.7 and 4.0 FPS on a V100 batch 1 including post-processing. A 13-point gap and a 10 FPS ceiling. (That boundary
column was read from an ar5iv rendering rather than the PDF; check before quoting.)

**The work that actually attacks boundaries** is where to steal ideas. PointRend
([arXiv 1912.08193](https://arxiv.org/abs/1912.08193)) reaches a 224 by 224 mask for 0.9 B FLOPs against 34 B dense by
predicting only at uncertain points; BMask R-CNN ([arXiv 2007.08921](https://arxiv.org/abs/2007.08921)) gets +8.0
large-object boundary AP **while keeping a 28 by 28 output**, so boundary supervision is worth nearly as much as 64x the
resolution; Mask Transfiner ([arXiv 2111.13673](https://arxiv.org/abs/2111.13673)) and PatchDCT
([arXiv 2302.02693](https://arxiv.org/abs/2302.02693)) both show a boundary gain about 1.6x their mask gain, which is the
signal the two metrics measure different things. The 2026 work closest to our needs predicts a **signed distance
function** instead of a binary mask, so the boundary is the zero level set of a continuous field
([arXiv 2603.21206](https://arxiv.org/abs/2603.21206)). That is the representation to start from if we write a custom
head.

## 3. RGB-D and depth-primary segmentation

### Early fusion is measurably worse than ignoring depth

FuseNet's Table 2, SUN RGB-D 37-class, VGG-16
([PDF](https://cvg.cit.tum.de/_media/spezial/bib/hazirbasma2016fusenet.pdf)): RGB alone 32.47 IoU, **4-channel RGB-D
stacking 31.95**, RGB-HHA 6-channel 33.64, two-branch FuseNet-SF4 37.76. Gupta's 2014 detection numbers agree, 21.2 mAP
for 4-channel early fusion against 32.5 for late fusion with separate finetuning
([arXiv 1407.5736](https://arxiv.org/abs/1407.5736)). Concatenating a depth channel and retraining is the intuitive move
and the one that loses.

| Two-branch method | NYUv2 mIoU | SUN RGB-D mIoU | Speed, hardware stated |
|---|---|---|---|
| ESANet-R34-NBt1D ([arXiv 2011.06961](https://arxiv.org/abs/2011.06961), ICRA 2021) | 50.30 | 48.17 | **29.7 FPS, Jetson AGX Xavier, TensorRT 7.1, float16, 640x480** |
| EMSAFormer ([repo](https://github.com/TUI-NICR/EMSAFormer), IJCNN 2023) | 51.06 | 48.52 | 36.5 FPS, Jetson AGX Orin 32 GB, TensorRT 8.5.2, float16, 50 W |
| DFormer-L ([arXiv 2309.09668](https://arxiv.org/abs/2309.09668), ICLR 2024) | 57.2 | 52.5 | 35.7 ms, RTX 3090, 480x640 |
| DFormerv2-B ([arXiv 2504.04701](https://arxiv.org/abs/2504.04701), CVPR 2025) | 57.7 | 52.8 | 50.7 ms, RTX 3090, 480x640 |

ESANet is the one to read, for a reason unrelated to accuracy: it avoids complex or tailored operations because they are
"often incompatible for converting to ONNX or NVIDIA TensorRT". That constraint, not mIoU, is what gets a fusion network
to 30 FPS on a Jetson. DFormer's finding also carries: a backbone pretrained with depth reaches 42.8 mIoU on depth alone
against 27.6 for an RGB-pretrained backbone, so ImageNet weights do not encode geometry. **Not one of these papers
reports a boundary metric**, and neither do RedNet, ACNet, SA-Gate, CMX, GeminiFusion or HDBFormer. A 57 mIoU on NYUv2 is
evidence about which pixels get the right class label in a cluttered room and none about where a contour sits.

### Depth-aware convolutions and HHA: both wrong for this cell

Depth-aware CNN ([arXiv 1803.06791](https://arxiv.org/abs/1803.06791)) gates spatial support by
`exp(-alpha * |D(p_i) - D(p_j)|)` with **alpha = 8.3 and depth in metres**, tuned on indoor rooms. Our slab stands 30 mm
proud, so the gate sits at 0.78 across the entire silhouette: close to inactive everywhere, and their own ablation
confirms alpha is a scene-scale parameter (27.8 mIoU at 8.3, 24.9 at 20) needing retuning by orders of magnitude. The
"free" claim is half true, 39.3 against 32.5 ms on a GTX 1080Ti at 425x560, and the repo's last commit is 2018 with an
unanswered issue reporting 0.70 mIoU from the released checkpoints. ShapeConv
([arXiv 2108.10528](https://arxiv.org/abs/2108.10528)) folds into a plain convolution at inference, which is cleaner, but
buys **+0.3 to +2.3 mIoU** and has no per-pixel adaptivity left at test time. The 2023 survey
([arXiv 2303.04315](https://arxiv.org/abs/2303.04315)) says why the family stopped: non-fixed deformed receptive fields
have "sub-optimal suitability for current accelerators". **No boundary metric has ever been published for any operator in
this family.**

HHA encodes depth as horizontal disparity (disparity, not depth, so far range is compressed), height above ground, and
normal angle with inferred gravity. Controlled comparisons against raw depth give **+0.4 to +1.7 mIoU, shrinking as
backbones strengthen**, for 2.5 s per frame optimised and 23 s unoptimised
([issue](https://github.com/charlesCXK/Depth2HHA-python/issues/14)). Moot for us anyway: with a fixed calibrated overhead
camera, gravity is known, channel 2 is slab thickness from the belt reference, and channel 3 is a rigid function of the
extrinsics. Compute the two useful channels directly and skip the encoding and its gravity estimator, which solves a
problem we do not have.

### Geometric segmentation on an organised cloud, and the defaults that will bite

PCL's `OrganizedMultiPlaneSegmentation` is the right shape for a belt: integral-image normals, two-pass 4-connected
components with union-find on `(n1 . n2 > thresh_normal) && (|nd1 - nd2| < thresh_range)`, then a deferred least-squares
fit. VGA timings on a 2.6 GHz Core i7 ([SPME 2013](https://web.archive.org/web/20151220132644if_/http://www.cc.gatech.edu/~atrevor/resources/publications/spme_2013_segmentation.pdf)):
normals 21.6 to 24.0 ms, segmentation 21.3 to 26.1 ms, 29.5 to 32.6 ms with refinement. PEAC
([ICRA 2014](https://www.merl.com/publications/docs/TR2014-066.pdf)) does full plane extraction in **27.3 ± 6.9 ms
single-threaded** by avoiding per-point normals entirely. Nothing here is benchmarked above VGA; our frame is exactly 4x
VGA and the operations are O(N), so 25 to 40 ms on one modern core is a reasonable expectation (unverified).

Four defaults are wrong for a 30 mm slab at 1 m, and each silently disables the thing you wanted.

- `IntegralImageNormalEstimation` flags a depth discontinuity when `|dz| > max_depth_change_factor * (|z| + 1.0) * 2.0`.
  At 1 m with the default 0.02 that is **80 mm**, so a 30 mm slab does not register and normals are smoothed straight
  over the product edge. Set `setMaxDepthChangeFactor(0.00125)` for a 5 mm trip point.
- `BORDER_POLICY_IGNORE` NaNs a border of `normal_smoothing_size_` pixels, 10 by default: a 5.8 mm dead frame.
- `OrganizedEdgeDetection`'s depth test is `|dist| > th_depth_discon * |curr_depth|`, default 0.02, again 20 mm at 1 m.
- `SACSegmentation`'s `max_iterations_` defaults to **50**, adequate only for a dominant plane.

On the belt plane itself, the accepted "on the plane" tolerance for a Kinect-class sensor at 1 m is 4.6 to 9.6 mm RMS
(PEAC's noise model), two to five times our whole budget. **Use a time-averaged per-pixel reference height image from an
empty belt, not a per-frame four-parameter RANSAC plane.** A reference map absorbs sensor systematics, residual
distortion and belt non-flatness together; a plane cannot.

### How good is a depth-derived boundary, really

Badly, and the vendors decline to specify it. Intel's testing methodology says edge fidelity is assessed by "looking at
the point cloud"; the D400 datasheet's four depth-quality metrics are accuracy, fill rate, spatial noise and temporal
noise, and the string "flying pixel" does not appear. From the published error equation
`RMS = Z^2 * subpixel / (focal_px * baseline_mm)` at a well-calibrated subpixel of 0.08:

| Sensor class | Lateral sampling at 1 m | Axial noise at 1 m | Expected lateral edge error |
|---|---|---|---|
| RealSense D435 at 848x480 | 2.36 mm/px | 3.8 mm RMS | 2 to 7 mm |
| RealSense D415 at 1280x720 | 0.995 mm/px | 1.45 mm RMS | 1 to 3 mm |
| Same, dark shiny target | unchanged | **5.8 mm RMS** | **4 to 10 mm, plus holes** |
| PMD Flexx2 ToF | 4.75 mm/px | measured at a real edge | **4.1 to 7.8 mm** ([arXiv 2412.15040](https://arxiv.org/pdf/2412.15040)) |
| Mech-Mind PRO S-GL structured light | 0.417 mm/px | 0.05 mm repeatability | 0.4 to 1.2 mm |
| Keyence LJ-X8900 laser profiler | 0.225 mm pitch | 0.010 mm repeatability | 0.2 to 0.5 mm |
| **Our RGB at 0.58 mm/px** | 0.58 mm/px | n/a | 0.3 to 1.2 mm, estimated |

The dark-shiny row is Intel's own measurement: on a black shiny notebook at 58 cm the subpixel noise goes from 0.07 on
the background to **0.32**, recoverable only with temporal filtering a moving belt does not allow. The same document
warns that hole filling at edges leaves "the impression of a badly torn notebook" and that "for many applications it may
be better to leave a hole, than to give false values". The default post-processing chain is hostile to our problem:
decimation magnitude 2 halves lateral sampling, the spatial filter stops preserving edges at large delta, and hole
filling defaults to "farthest from sensor", pushing the boundary outward.

A geometric amplifier is specific to a relaxed slab: a height threshold converts depth error into lateral error by
`dx = dh / tan(alpha)` for edge slope alpha, so at a 30 degree rolled edge 1 mm of threshold error is 1.73 mm of boundary
displacement and at 10 degrees 5.67 mm. That applies to a laser profiler too and is the hardest constraint in the
problem. The strongest published statement on wet meat is GRIBBOT
([Misimi et al. 2016](https://doi.org/10.1016/j.compag.2015.11.021)): the fillet was "an optically challenging object to
measure because of specular reflections generated by meat texture and slime", citing a result that for highly reflective
materials Kinect v2 distances "can vary by up to 6 cm".

### Depth proposes, RGB refines: the ablation that justifies our architecture

UOIS-Net ([arXiv 2007.08073](https://arxiv.org/abs/2007.08073), IEEE T-RO 2021) runs depth-only for rough masks, then a
Region Refinement Network to "snap the noisy initial mask edges to object edges in RGB". On OSD, the manually annotated
benchmark: Mask R-CNN RGB-only 46.0 overlap F / 29.5 boundary F, depth-only 72.2 / 43.1, RGB-D early fusion 74.1 / 53.8,
UOIS-Net-2D **79.9 / 65.6**, and the same net with refinement removed **80.1 / 52.8**. **The RGB refinement adds 12.8
boundary F points while leaving overlap F unchanged.** That gap is exactly the difference between "the segmentation looks
fine" and "the pose is 2 mm out", and it is the published justification for `EdgeSnapRefinement` sitting behind
`DepthHeightProposal`.

The same paper carries a warning we must act on. On OCID, whose labels are semi-automatically derived by depth
differencing, removing the RGB refinement *improves* the score, and the authors say so: it "further demonstrates the
issue with OCID labels". **If we build ground-truth boundaries by thresholding depth, we build a benchmark that penalises
the refinement we need.**

One caveat on the ordering. UOIS puts depth first because depth is the reliable channel in matte tabletop clutter; on a
dark belt, figure-ground contrast is a gift to RGB and depth is the unreliable channel on wet product. The alternative
ordering, an RGB mask projected onto a high-quality range measurement, is what the best agricultural result uses: a Livox
solid-state LiDAR fused with a RealSense D455 gives 2.0 to 2.75 mm centre standard deviation across 0.5 to 1.8 m against
**10.06 to 13.60 mm for the D455 alone** ([arXiv 2205.00404](https://arxiv.org/pdf/2205.00404)). The best published RGB-D
fruit-centre standard deviations are 3.2 mm at 0.3 to 0.5 m rising to 13.6 mm past 0.9 m, with 4.8 to 5.2 degree
orientation. **Nobody has published 2 mm and 2 degrees from RGB-D on a deformable specular object.** The one public RGB-D
meat dataset is 25 pig carcasses under six D415 cameras, CC BY, with **no pose ground truth at all**
([Data in Brief 41:107945](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8866887/)).

## 4. Boundary refinement

Across DenseCRF, PointRend, CascadePSP, SegFix, SegRefiner, HQ-SAM, BIRefNet, GrabCut, Deep Snake and the matting
literature, **no paper reports boundary error as a displacement in pixels or millimetres.** Every "boundary improvement"
is mask IoU, band-restricted pixel accuracy (mBA), band-restricted F-score, Boundary IoU, or matting SAD/MSE/Grad/Conn.
The one exception is the classical sub-pixel edge literature, which is also the best fit for us.

| Method | Training data needed | Cost, with hardware and resolution | Measured gain |
|---|---|---|---|
| **Devernay sub-pixel Canny** ([IPOL 2017](https://doi.org/10.5201/ipol.2017.216)) | **none** | O(N); "a fraction of a second" for 512x512, 2017 hardware, C source published | **0.05 to 0.1 px localisation error at edge blur sigma = 1**, against synthesised edges at known sub-pixel offsets |
| **Fast bilateral solver** ([arXiv 1511.03296](https://arxiv.org/abs/1511.03296)) | **none** | **187 ± 37 ms for 4 Mpx, 2012 Xeon E5-1650**; 111 ms per VOC image | VOC 2012 +3.75 IoU over DeepLab, at **8 to 10x lower cost than DenseCRF** |
| **Guided filter** ([arXiv 1505.00996](https://arxiv.org/abs/1505.00996)) | none | O(N), O(N/s^2) fast variant; **29.3 ms at 1280x960, OpenCV 4.5.4 ximgproc, i7-8750H (measured here)** | none published as a boundary metric |
| **DenseCRF** ([arXiv 1210.5644](https://arxiv.org/abs/1210.5644)) | none (parameters cross-validated) | **0.2 s for 320x213, one core, i7-930 at 2.80 GHz**; 918 ms per VOC image measured independently | +3 to 5 mIoU with VGG-16, **+1.3 with ResNet-101**; Cityscapes +0.2 mIoU but **+4.3 boundary F** |
| **Chan-Vese / morphological snakes** ([TIP 2001](https://www.math.ucla.edu/~lvese/PAPERS/IEEEIP2001.pdf), [IPOL 2012](https://doi.org/10.5201/ipol.2012.abmh-rtmsa)) | **none** | O(contour length) per iteration for the morphological variant | no sub-pixel accuracy published; the morphological contour is binary and cannot be sub-pixel |
| **GrabCut** ([SIGGRAPH 2004](https://www.microsoft.com/en-us/research/wp-content/uploads/2004/08/siggraph04-grabcut.pdf)) | none | 0.9 s for a 450x300 region on a 2.5 GHz CPU, 2004 | 2.13 ± 0.19 % pixel error on 50 images, **worse** than two-lasso graph cut at 1.36 |
| **PointRend** ([arXiv 1912.08193](https://arxiv.org/abs/1912.08193)) | yes, class-specific, full instance dataset | 0.9 B FLOPs for a 224x224 mask against 34 B dense; "~13 fps", **GPU never named** | +8.5 large-object boundary AP over Mask R-CNN |
| **CascadePSP** ([arXiv 2005.02551](https://arxiv.org/abs/2005.02551)) | **trained once, class-agnostic, none from us** | 4.77 s at 3492x2328, **0.45 s with `fast=True`**, GPU not stated; 3.16 GB at L=900 | +1.3 to +5.5 IoU and **+8.7 to +15.7 mBA** across four base models |
| **SegFix** ([arXiv 2007.04269](https://arxiv.org/abs/2007.04269)) | yes, but targets generated by `distance_transform_edt` from any masks you have | **16 ms at 2048x1024 on a V100**, HRNet-W18 | Cityscapes +1.0 mIoU, **+4.4 boundary F at 1 px**; matches DenseCRF on boundaries at 50x the speed, and they stack to +7.5 |
| **SegRefiner** ([arXiv 2312.12425](https://arxiv.org/abs/2312.12425)) | trained once, class-agnostic | 6 discrete diffusion steps, 8 RTX 3090, per-image runtime not published | best in the cross-method table below |
| **Matting (ViTMatte, RVM)** ([arXiv 2305.15272](https://arxiv.org/abs/2305.15272), [arXiv 2108.11515](https://arxiv.org/abs/2108.11515)) | yes | RVM does 4K at 76 FPS on a GTX 1080Ti | Composition-1k SAD 168.1 closed-form to 20.3 ViTMatte-B |

SegRefiner's Table 1 is the most useful comparison here, because it puts every model-agnostic refiner on the same 100
high-resolution images and the same metric pair, averaged over four base models: SegFix +0.47 IoU / +3.30 mBA, MGMatting
+0.73 / +6.10, CascadePSP +3.58 / +14.05, SegRefiner **+7.43 / +17.33**. Note how badly SegFix does here against its own
Cityscapes self-report: that is the difference between a one-pixel-shift operator and a full refinement network. Note
also that SegFix's own headline (+3.0 mIoU, +11.4 F) is the **oracle**, computed from ground-truth offset maps; the real
numbers are +0.5 to +1.0 mIoU.

**For us the section means something different than for anyone else.** Our edge method already achieves 0.081 mm on a
clean render, a seventh of a pixel, and no refiner listed can improve on that. What refinement buys is the sharpness of
the edge channel while the *selection* comes from depth, which is exactly what `EdgeSnapRefinement` does: move each
contour point along its normal to the strongest gradient inside a 6 px band, and leave it where depth put it if no
gradient passes threshold. It is an active contour with a one-dimensional search and no regularisation. Three upgrades
follow, in order of cost.

1. **Replace the integer gradient maximum with a parabolic fit.** The Devernay correction fits a parabola to three
   gradient samples along the normal and places the edge at its maximum: 0.05 to 0.1 px measured at sigma = 1 blur, which
   is 0.03 to 0.06 mm here, falling further as the edge gets blurrier. Training-free, O(N), and the only method in this
   survey with a published error in pixel units. Use the IPOL paper's modified interpolation (constrain the search to
   strictly horizontal or vertical lines), not Devernay's original, which has a documented half-pixel oscillation on 45
   degree edges. OpenCV's `cv::Canny` returns an integer binary map and does no sub-pixel work, so this comes from the
   IPOL C code, `skimage`, or our own non-maximum suppression.
2. **Regularise the contour.** A per-point independent snap produces exactly the correlated-noise failure the error
   budget punishes. A smoothness term along the contour, or a low-order Fourier or spline fit to the snapped points,
   converts correlated error back toward the independent-noise row, where 5 px of jitter costs 0.18 mm.
3. **Use depth as the guidance channel, not only colour.** This is the lever the whole refinement literature leaves on
   the table. DenseCRF's appearance kernel, the guided filter's guidance image, the bilateral solver's affinity and
   CascadePSP's gradient loss all take a guidance signal and are agnostic about what it is; they assume RGB because their
   benchmarks are RGB. A slab on a flat belt has a genuine height step at its boundary and none at the fat seams, the
   sheen, or the belt joints. A depth-and-colour guidance stack turns this family's dominant failure, snapping to the
   wrong edge, into a non-issue. The permutohedral lattice is d-dimensional; nothing restricts it to three channels.

CascadePSP deserves a trial despite its latency because it needs **no labels from us**: one checkpoint trained on 36,572
binary-foreground images across more than a thousand classes, and the paper states plainly "our model has never seen any
of the following datasets in training". Its mBA band is `[1, (w+h)/300]`, radius 1 to 7 px on our frame, unusually close
to the scale we care about. Its stated failure is also ours: "our refinement still adheres well to the color boundary, it
produces a wrong segmentation due to the lack of semantic information."

## 5. Specular highlights in software

Shafer's dichromatic model splits reflection into a body term with the surface colour and an interface term with the
**illuminant** colour ([Color Research and Application 10(4), 1985](https://doi.org/10.1002/col.5080100409)). Wet meat is
close to the ideal case: a water film at n around 1.33 gives a neutral surface reflection over strongly chromatic tissue.
The precondition every method quietly assumes is stated by Tan and Ikeuchi themselves, who "did not take account of
saturated or blooming pixels". Once a highlight clips at 255 the specular scale factor is unrecoverable and every method
here degenerates. **So the first experiment is not an algorithm. Drop the exposure until the highlights stop clipping and
lift the product back with gain.** It costs nothing, and everything downstream degrades gracefully with unclipped
highlights and catastrophically with clipped ones.

### Which specular geometry actually moves the pose

Measured 2026-09-11, OpenCV 4.5.4 on an i7-8750H, synthetic 1280x960 scene, rotated ellipse on a dark ground with clipped
white blobs, pose from the filled outer contour's image moments:

| Highlight geometry | Highlight dropped from the mask | Highlight unioned into the mask |
|---|---|---|
| 3 blobs entirely inside the silhouette | 0.005 mm, 0.033 deg | 0.005 mm, 0.033 deg |
| 3 blobs straddling the boundary | 1.629 mm, 2.386 deg | **1.116 mm, 1.219 deg** |
| 1 large blob half off the edge | **2.728 mm, 1.480 deg** | 4.518 mm, 2.629 deg |

**Interior highlights cost nothing** when the pose comes from the filled outer contour with `RETR_EXTERNAL`. They are
holes, and a hole moves neither the outer contour nor the filled region's moments. Our measured 815 mm failure was
therefore not caused by brightness; it was the edge method selecting the wrong connected component, because a highlight
makes a closed contour that beats the product on area. **A selection failure, fixed by a proposal channel that cannot
select the wrong region, not by a photometric method.**

**Boundary-straddling highlights spend the budget.** 1.6 mm dropped is most of the allowance, and it matches the
error-budget row for a local bite.

**Unioning the specular mask into the foreground is conditional, not unconditional.** It helps when the highlight
straddles the boundary (1.63 to 1.12 mm) and it *hurts* when a large highlight sits half off the product (2.73 to 4.52
mm), because it pastes the belt-side half into the mask. The rule is to union only components lying entirely inside the
depth-proposed silhouette and treat the rest as missing data. Depth is the only thing in the cell that knows which half
of a straddling highlight is product.

### Cost, detection precision, and what is deployable

Measured here at 1280x960 on the same machine: HSV convert plus `V>200 & S<60` plus a 5x5 dilate, **1.84 ms**; detect,
union, 9x9 close, `findContours` and `minAreaRect`, **7.87 ms**; single-cluster intensity-ratio separation in the Shen
and Zheng form via `cv2.split`/`min`/`max`, **6.51 ms**; `cv2.inpaint` TELEA radius 3 on a 7,595 px mask, full frame,
**15.18 ms**, Navier-Stokes 7.86 ms, TELEA radius 7 **32.18 ms**; `cv2.bilateralFilter` d=5 3.34 ms and d=9 11.20 ms.
`inpaintRadius` is the expensive knob, and both OpenCV inpaint paths are single-threaded (`grep -c parallel_for_` on
`modules/photo/src/inpaint.cpp` returns zero), so they will not scale with cores.

On false positives, the closest published analogue is endoscopy, which shares the physics. Detection **precision** on
1,000 surgeon-annotated real endoscopic images ([Sensors 23(2):974](https://doi.org/10.3390/s23020974)): Arnold 2010
0.497, El Meslouhi 2011 0.372, Alsaleh 2016 0.517, Shen 0.600, Nie 2023 0.758. Read precision, not accuracy: highlights
are about 1 percent of pixels, so predicting "no highlight" everywhere scores 0.99. Classical thresholding on wet tissue
mislabels 37 to 63 percent of what it flags. Our scene should be kinder, because the confuser class there (bright
desaturated *object* content) is absent on red meat over a dark belt, and the realistic false positives here are
stainless rails, droplets, ice and glossy belt patches, all outside the silhouette and removed free by the geometric
gate. That is an argument, not a measurement.

**Deployable.** The published real-time result is Souza, Macedo, Nascimento and Oliveira, SIBGRAPI 2018
([DOI](https://doi.org/10.1109/SIBGRAPI.2018.00014), public-domain
[CUDA code](https://github.com/MarcioCerqueira/RealTimeSpecularHighlightRemoval)): **24 ms for 3840x2160 on a GPU**,
about 3.6 ms scaled to our frame (my extrapolation; the GPU model is not in the abstract). It is Shen and Zheng's
intensity-ratio formulation with better clustering, and my CPU port of the single-cluster case runs in 6.5 ms here.

**Not deployable.** Tan and Ikeuchi is 2 min 36 s for 640x480 on the authors' own Pentium III and 170 s reproduced on an
i5-8250U ([SIHR toolbox](https://github.com/vitorsr/SIHR)); Akashi and Okatani is 140 to 230 s and non-deterministic
because of random initialisation, which is worse than a biased estimator on a repeatable line; exemplar inpainting is
**1,385 s at 1280x720 with 6,837 highlight pixels**, roughly 80,000 times slower than OpenCV's fast-marching inpaint at
the same resolution and mask size.

**Learned specular removal is not a candidate, and the datasets are the reason.** SHIQ's ground truth is produced by RPCA
across an illumination stack, cropped to 200x200 patches, with highlights forced colourless by construction
([CVPR 2021](https://openaccess.thecvf.com/content/CVPR2021/papers/Fu_A_Multi-Task_Network_for_Joint_Specular_Highlight_Detection_and_Removal_CVPR_2021_paper.pdf));
SSHR is rendered under the dichromatic model, which its authors admit is circular; PSD, the only real-capture set, was
built with a polariser, and everything plateaus at 22 to 26 dB on it across five years and every architecture against 34
to 38 dB on the algorithmically derived sets. Compute rules it out anyway: DHAN-SHR is 43.82 ms on an **H800** at what is
almost certainly 256x256, 18.75x fewer pixels than our frame. None of these datasets contains food. The honest use of
this literature is a **detector** trained on our own frames, with pseudo-ground-truth built by translating a specular
mask to an unoccluded region ([Daher et al.](https://doi.org/10.1016/j.media.2023.102994)).

### Multi-illumination, since a polariser is excluded

The per-pixel minimum across illuminations is called the **min composite**, and the people who built the rig rejected it:
"specularities could also be removed by just taking the min composite of the images, but in this case we would have the
presence of shadows" ([Feris, Raskar, Tan, Turk, SIBGRAPI 2004](http://rogerioferis.com/publications/FerisSIB04.pdf)).
Their method is the **median of gradients** plus a Poisson reconstruction, which survives overlapping highlights because
the *boundaries* of the spots rarely coincide even when the spots do, at about five seconds on a 3 GHz Pentium 4 in 2004
with an FFT solve that would be milliseconds now. They also hand over a free detector: the ratio of the reconstructed
image to the max composite is close to 1 only in non-specular regions. Their stated failure applies directly to a flat
conveyor, since the method "fails when specular highlights do not shift among images captured with different flashes".
**Bench that first**: strobe four lights and measure the pixel overlap of the detected highlight masks; above roughly 50
percent overlap, multi-illumination will not help. The one head-to-head against cross-polarisation on wet tissue builds
both probes around the same camera and finds both work
([Micromachines 14(5):1062](https://doi.org/10.3390/mi14051062)), with acquisition "under half a second". Four flashes at
30 fps means a 120 fps sensor plus belt motion between sub-frames, so two flashes at 60 fps is the realistic version,
with Feris's caveat that two flashes only attenuate a highlight's gradient unless you take the minimum gradient.

**Near-infrared makes this worse.** Fresnel surface reflection depends on the real refractive index, near 1.31 to 1.33
for water from the visible through SWIR, so the specular component is essentially unchanged, while the diffuse return
depends on absorption, which rises by orders of magnitude at the 1450 nm and 1940 nm water bands
([Hale and Querry 1973](https://doi.org/10.1364/AO.12.000555)). At a water band the specular-to-diffuse ratio goes
**up**. The 800 to 1000 nm window gives a flatter, brighter diffuse return but washes out the myoglobin chromaticity
every dichromatic method depends on, and a monochrome image kills colour-based separation outright. That reasoning is
mine, not a cited experiment; falsify it with one NIR test shot.

## 6. What food processing actually deploys

### Laser triangulation, and it is not close

JBT's own patent writes the physics into claim language (US10869489B2, *Portioning accuracy analysis*, priority
2018-08-31, [Google Patents](https://patents.google.com/patent/US10869489B2/en)): "the upper, irregular surface of the
workpiece produces an irregular shadow line/light stripe as viewed by a video camera... The video camera detects the
displacement of the shadow line/light stripe from the position it would occupy if no workpiece were present on the
conveyor belt." The only alternative the patent names is X-ray. Marel's brochures agree in product language: the I-Cut 11
has a "laser vision system with 200 Hz camera technology", the I-Cut 56 takes a "360 degree volumetric laser scan"
([brochure](https://jbtmarel.com/media/ql3jfprl/i-cut-56.pdf)), and the DSI waterjet line scans with a J-Scan that
"creates a precise height map" feeding Q-Link portioning software
([DSI](https://jbtmarel.com/en/products/dsi-waterjet-portioning-systems/)). The same technique appears in Formax's 1999
priority patent family (EP1178878B1) and in Nantsune's "3D non-contact shape recognition" slicers. Note that
`marel.com` now redirects to `jbtmarel.com`: JBT and Marel have merged.

**No portioning vendor publishes profile pitch, Z repeatability or profile rate.** They publish portion weight standard
deviation, which is what the customer buys. The I-Cut 56 brochure is the best public giveaway table anywhere: bacon
joints or pork loin at 1.0 to 1.5 percent (1 sigma) and 5500 kg/h, 3 kg pork loin into 100 to 150 g portions at 1.5
percent, a 4.0 kg ribeye at 2.5 percent, a 20 kg chuck at 3.5 to 4.5 percent. Shape variability, not sensor noise, sets
that ladder. Component numbers come from the sensor vendors: SICK's Ranger3 does 1,500 to 46,000 3D profiles per second
at up to 2560x832, IP20/65/67, with the laser line generator sold separately
([family overview](https://web.archive.org/web/2020id_/https://cdn.sick.com/media/familyoverview/4/54/354/familyOverview_Ranger3_g448354_de.pdf));
Keyence's LJ-X8900 covers 510 mm of belt at 980 mm reference with **0.225 mm profile pitch and 10 micrometre Z
repeatability** ([specs](https://www.keyence.com/products/measure/laser-2d/lj-x8000/specs/)).

### X-ray, ultrasound, and where learning actually sits

Scott Technology's boning room is the real deployed meat-cutting robot and it runs on X-ray: "our patented X-Ray system
is designed to determine the skeletal structure of a carcass and identify the ideal cut points"
([Scott](https://scottautomation.com/en/products/meat/grading)), at 10 to 12 carcasses per minute depending on which
Scott page you read. The engineering detail is in the MLA report
([A.MQA.0017](https://www.mla.com.au/contentassets/ab6ab1e8f0214babb6ffecd72211fa5b/a.mqa.0017_final_report.pdf)): a
sandwich detector of two photodiodes separated by a copper filter, ZnSe for low energy and CsI for high, one emission
from a 140 kV tube, "2D X-ray images to identify cutting lines". The DEXA composition models are linear mixed-effects
regressions, R squared 0.89 for fat and 0.74 for lean against CT on about 600 lambs.

Frontmatec's AutoFOM is the best-specified sensor in the industry, because EU carcass grading methods are printed in law:
AutoFOM III has "sixteen 2 MHz ultrasonic transducers, with an operating distance between transducers of 25 mm",
AutoFOM IV has 25 wideband transducers at 16.5 mm, and the lean-meat regression equations are published alongside
([EU 2022/1205](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32022D1205)).

The clearest documented deployment of neural networks is **grading, not geometry**. Baader's director of vision and
machine learning describes ClassifEYE 2.0 as "training of neural networks to detect chickens, virtually decompose them,
and individually assess the quality of their parts", on "a 1.4-megapixel colour camera, optical components like a lens
and an LED flash"
([interview](https://www.baader.com/media/blog/the-future-of-quality-detection-and-vision-technology-an-interview-with-dr-fabian-isernhagen)).
Marel's SensorX says "advanced image analysis algorithms" and never says neural networks. **Geometry and spectroscopy
compute the cut; learning computes the grade.** A learned segmenter that emits a cut path puts us ahead of every shipping
product found, which is an opportunity or a warning depending on timeline.

TOMRA and Key Technology transfer close to nothing. Their sorters are classify-and-eject, and TOMRA's "Biometric
Signature Identification" is a brand name for a multi-band spectral scanner with **no published wavelengths, detector
type or pixel resolution** in any document retrieved; Key's VERYX "Multi-Sensor Pixel Fusion" is the same. Neither
estimates pose or produces a cut path.

### Two findings that should change how this cell is pitched

**The incumbent architecture makes pose irrelevant rather than measuring it.** JBT states of the DSI systems: "The DSI
Waterjet Portioning Systems require no positioning at the input. The waterjet accurately cuts all types of pieces of meat
according to the programmed pattern, regardless of how it's placed on the belt." If the customer can afford a waterjet
with full-belt-width travel, an alignment robot is the wrong answer. Know the regime and be able to say why a fixed blade
plus an aligning arm wins there: cutter cost, product damage, water use, hygiene.

**Alignment is a recognised, money-losing, currently unautomated problem.** Marel sells SensorX Infeed Monitoring, which
"measures spacing, pieces within the scan area, centralisation on lanes, orientation of single breast fillets, and
overlapping pieces" and shows operators a traffic light telling them their presentation quality is bad. The industry
currently solves slab pose by asking a human to do better. That is the gap this cell is aimed at.

For calibration of ambition: RoBUTCHER spent 7.78 M EUR over 2020 to 2023
([CORDIS 871631](https://cordis.europa.eu/project/id/871631)) and its published evaluation is **34 attempted shoulder
removals** ([IJRR 2024](https://doi.org/10.1177/02783649241234035)). And the Australian beef programme's post mortem is
required reading before any sensor is chosen: Scott and Teys locked onto CT under contract pressure, found that "the
chine bone remains clear... but the rib and meat definition are lost in the middle" and that "materials handling clamps
passing through the CT scanner produced artifacts and poor image quality", and concluded "CT technology needs to be
developed last in visioning. Its data quality is outweighed by its associated design challenges"
([P.PIP.0772](https://www.mla.com.au/contentassets/13e2161b4d1145aa846f1587ffaa7eca/p.pip.0772---leap4beef-beef-boning-automation---final-report_approved---clean-copy.pdf)).

One search note worth recording: arXiv returns essentially nothing for "meat factory cell", "pork carcass" with robot, or
"meat cutting" with deep learning. This industry publishes in *Journal of Food Engineering*, *Meat Science*,
*Industrial Robot* and *Computers and Electronics in Agriculture*, and in MLA project reports. Search arXiv for prior art
and you will conclude the field is empty, and you will be wrong.

## 7. Recommendation for this cell

Constraints: no reliable polarising filter, no betting the cell on a learned segmenter alone, depth available, boundary
accuracy in millimetres, modest hardware, minimal labelled data.

| Method | Verdict | Reason |
|---|---|---|
| Depth height-above-belt proposal, per-pixel reference map | **Adopt** | The only channel that cannot select the wrong region. Colour drift, a lighting ramp and a specular blob all leave height unchanged. A reference map absorbs sensor systematics a 4-parameter plane cannot. |
| Sub-pixel edge snap along the contour normal, parabolic fit | **Adopt** | 0.05 to 0.1 px measured at sigma = 1 blur, training-free, O(N), the only method here with a published error in pixel units. Replaces the current integer gradient maximum for free. |
| Contour regularisation before taking moments | **Adopt** | Correlated boundary error costs 15x what independent error costs. A smoothness term converts one into the other. |
| Depth and colour together as the refiner's guidance | **Adopt** | Removes the failure every edge-aware refiner shares. The fat seam and the sheen have no height step; the silhouette does. |
| Exposure set so highlights do not clip | **Adopt** | Zero compute. Every dichromatic method assumes it and none says so loudly. |
| Specular detection by HSV threshold, gated to inside the depth silhouette | **Adopt** | 1.84 ms measured at full resolution. The gate removes the false positives that cost endoscopy 37 to 63 percent precision. |
| Union specular components **only** when wholly inside the silhouette | **Adopt** | Measured: a straddling highlight goes 1.63 to 1.12 mm, a half-off highlight 2.73 to 4.52 mm. Conditional, not unconditional. |
| Boundary AP at a tight `dilation_ratio` in the eval loop | **Adopt** | Mask IoU scored a 28x28 staircase at 95.0 AP_L. The default 2 percent band is 18.6 mm here, so use about 0.003. |
| YOLO26-seg at `imgsz=1280` with `retina_masks=True`, behind the depth proposal | **Trial** | Already trained. Halves the prototype cell to 2.32 mm and removes a threshold-then-resize round trip. Costs compute and an evaluation, nothing else. Keep the AGPL or Enterprise question open before a pilot. |
| Depth-derived **box** prompting SAM-HQ or SAM 1 ViT-H, offline | **Trial** | A labelling engine, not a runtime model. A noisy box costs 29 points of boundary IoU, and SAM 2.1 is about twice as box-sensitive as SAM 1 at equal tight-box accuracy. |
| CascadePSP `fast=True` as an offline refiner for label generation | **Trial** | The only refiner needing no labels from us, +8.7 to +15.7 mBA measured. Too slow for the line, good for ground truth. |
| Fast bilateral solver or fast guided filter with a depth-plus-colour guide | **Trial** | Training-free, 187 ms for 4 Mpx on 2012 silicon, 8 to 10x cheaper than DenseCRF for 1.6 IoU less. Benchmark before assuming 33 ms here. |
| Multi-flash with median-of-gradients | **Trial, gated on one measurement** | Validated on wet tissue without a polariser. Useless if the highlights do not move, so measure highlight-mask overlap first. |
| A laser line profiler instead of, or alongside, the overhead RGB-D | **Trial** | 0.225 mm pitch and 10 micrometre Z at our standoff, washdown-rated, and what every I-Cut and J-Scan uses. The belt motion we already have is the scan axis. Caveat: subsurface scattering on translucent wet meat biases the peak and no vendor publishes a number (unverified). |
| SAM 2 video mode with a depth mask through `add_new_mask` | **Reject** | The shipped config takes the mask as ground truth verbatim and propagates its errors into the memory bank. Use a box on the image path. |
| FastSAM | **Reject** | AGPL-3.0 despite the README, its own authors document square-ish small masks and bounding-box border artefacts, and it has the worst large-object AP of any SAM variant. |
| Any SAM on CPU at line rate | **Reject** | 0.61 FPS FP32 and 0.88 FPS INT8 for the SAM 2 Hiera-L encoder, OpenVINO, 36 threads. |
| Depth-aware convolutions, HHA encoding, 4-channel early fusion | **Reject** | The depth gate is tuned to room scale and inactive across a 30 mm step, with no boundary metric ever published for the family; HHA costs 2.5 to 23 s per frame for +0.4 to +1.7 mIoU and its gravity estimator solves a problem a calibrated overhead camera does not have; early fusion measured **below** RGB alone. |
| Learned specular removal; Tan and Ikeuchi; Akashi; exemplar inpainting | **Reject** | 43.82 ms on an H800 at 256x256 on non-food data, and 170 s, 230 s and 1,385 s per frame respectively. Akashi is also non-deterministic between identical frames. |
| RT-DETR family for masks, Mask2Former on the line | **Reject** | RT-DETR has no segmentation variant in v1, v2 or v3. Mask2Former is 9.7 FPS on a V100 with a 13-point mask-to-boundary gap; fine as an offline labeller. |
| Labelling boundaries by thresholding depth | **Reject** | On OCID, whose labels are depth-derived, removing RGB refinement *improves* the score. We would build a benchmark that penalises the thing we need. |

## 8. Open questions and what to measure

The measurement that decides everything, and which nobody has published in any domain: **boundary displacement in
millimetres, and centroid and axis error in millimetres and degrees, for each candidate on our own frames.** Two
independent search passes found no such number for any SAM-family model, any RGB-D fusion network, or any refiner.

- **The edge-slope distribution of a relaxed slab.** `dx = dh / tan(alpha)` means 1 mm of threshold error is 1.73 mm of
  boundary displacement at a 30 degree edge and 5.67 mm at 10 degrees. Measure alpha over the outer few millimetres on
  real product before promising 2 mm from any depth channel.
- **Whether the sub-cell bias of a learned mask is systematic.** The budget tolerates 5 px of independent noise at 0.18
  mm and fails at 5 px of one-sided bias at 1.59 mm. Render a slab at known sub-pixel offsets, run YOLO26-seg, and plot
  the mean signed normal displacement around the perimeter. If it is zero-mean, the 2.90 mm prototype cell does not
  matter.
- **The aspect-ratio distribution of the product.** The axis is not gradually worse on a round slab, it is undefined.
  Gate on the covariance eigenvalue ratio per frame and publish "no axis" rather than a number.
- **Highlight-mask overlap between two or four strobed illuminations.** One cheap bench measurement decides whether
  multi-illumination is available to us at all.
- **Specular detection precision on plant frames.** The endoscopy analogue says 37 to 63 percent of flagged pixels are
  not specular. Our scene should be much better and the argument for that is geometric, not measured.
- **Whether `imgsz=1280` plus `retina_masks=True` moves centroid error at all**, before anyone retrains anything or adds
  a P2 head.
- **Whether blue-laser triangulation is biased by subsurface scattering on wet meat.** No vendor publishes a number, and
  it is the one thing that could undermine the profiler recommendation.
- **A ground-truth rig.** Copy XYZ-IBD: anti-reflective coating for the ground-truth pass, identical poses for the native
  pass, a published error budget. Without it every number above stays an argument.

## Related entries

- [Perception technique selection](perception-technique-selection.md)
- [Perception ingestion](perception-ingestion.md)
- [Meat cell architecture](meat-cell-architecture.md)
- [Computer vision fundamentals](computer-vision-fundamentals.md)
- [Perception foundation models](perception-foundation-models.md)

## Sources

Measured here, 2026-09-11, Intel i7-8750H, OpenCV 4.5.4, NumPy 1.21.5: the error-budget tables, the specular-geometry
table, and the specular timing figures. Prior measurements over 40 poses per condition:
`experiments/data/2026-09-11-segmentation.json` from `scripts/measure_segmentation.py`. Cell geometry and the 0.58 mm per
pixel figure: `src/meat_cell_sim/sensing.py` and [perception-ingestion](perception-ingestion.md).

**Metrics and instance segmentation.** [Boundary IoU, arXiv 2103.16562](https://arxiv.org/abs/2103.16562) · [boundary-iou-api](https://github.com/bowenc0221/boundary-iou-api) · [YOLO26, arXiv 2606.03748](https://arxiv.org/abs/2606.03748) · [v8.4.0 release](https://github.com/ultralytics/ultralytics/releases/tag/v8.4.0) · [Ultralytics licensing](https://www.ultralytics.com/license) · [segment docs](https://docs.ultralytics.com/tasks/segment/) · [RT-DETR, arXiv 2304.08069](https://arxiv.org/abs/2304.08069) · [RF-DETR, arXiv 2511.09554](https://arxiv.org/abs/2511.09554) · [rf-detr repo](https://github.com/roboflow/rf-detr) · [Mask2Former, arXiv 2112.01527](https://arxiv.org/abs/2112.01527) · [PointRend, arXiv 1912.08193](https://arxiv.org/abs/1912.08193) · [BMask R-CNN, arXiv 2007.08921](https://arxiv.org/abs/2007.08921) · [Mask Transfiner, arXiv 2111.13673](https://arxiv.org/abs/2111.13673) · [PatchDCT, arXiv 2302.02693](https://arxiv.org/abs/2302.02693)

**Promptable segmentation.** [segment-anything](https://github.com/facebookresearch/segment-anything) · [SAM 2, arXiv 2408.00714](https://arxiv.org/abs/2408.00714) · [sam2 repo](https://github.com/facebookresearch/sam2) · [SAM 3, arXiv 2511.16719](https://arxiv.org/abs/2511.16719) · [HQ-SAM, arXiv 2306.01567](https://arxiv.org/abs/2306.01567) · [sam-hq repo](https://github.com/SysCV/sam-hq) · [FastSAM, arXiv 2306.12156](https://arxiv.org/abs/2306.12156) · [MobileSAM, arXiv 2306.14289](https://arxiv.org/abs/2306.14289) · [EfficientSAM, arXiv 2312.00863](https://arxiv.org/abs/2312.00863) · [Stable-SAM, arXiv 2311.15776](https://arxiv.org/abs/2311.15776) · [BREPS, arXiv 2601.15123](https://arxiv.org/abs/2601.15123) · [SAM meets robotic surgery, arXiv 2304.14674](https://arxiv.org/abs/2304.14674) · [SAM for medical images, arXiv 2304.14660](https://arxiv.org/abs/2304.14660) · [UOIS-SAM, arXiv 2409.15481](https://arxiv.org/abs/2409.15481) · [ZISVFM, arXiv 2502.03266](https://arxiv.org/abs/2502.03266) · [OpenVINO SAM 2 CPU benchmark](https://github.com/openvinotoolkit/openvino_notebooks/blob/latest/notebooks/sam2-image-segmentation/segment-anything-2-image.ipynb)

**RGB-D.** [FuseNet](https://cvg.cit.tum.de/_media/spezial/bib/hazirbasma2016fusenet.pdf) · [Gupta et al., arXiv 1407.5736](https://arxiv.org/abs/1407.5736) · [ESANet, arXiv 2011.06961](https://arxiv.org/abs/2011.06961) · [CMX, arXiv 2203.04838](https://arxiv.org/abs/2203.04838) · [DFormer, arXiv 2309.09668](https://arxiv.org/abs/2309.09668) · [DFormerv2, arXiv 2504.04701](https://arxiv.org/abs/2504.04701) · [Depth-aware CNN, arXiv 1803.06791](https://arxiv.org/abs/1803.06791) · [ShapeConv, arXiv 2108.10528](https://arxiv.org/abs/2108.10528) · [depth-as-operation survey, arXiv 2303.04315](https://arxiv.org/abs/2303.04315) · [UOIS-Net, arXiv 2007.08073](https://arxiv.org/abs/2007.08073) · [PEAC, ICRA 2014](https://www.merl.com/publications/docs/TR2014-066.pdf) · [Organized segmentation, SPME 2013](https://web.archive.org/web/20151220132644if_/http://www.cc.gatech.edu/~atrevor/resources/publications/spme_2013_segmentation.pdf) · [RealSense tuning guide](https://dev.realsenseai.com/docs/tuning-depth-cameras-for-best-performance/) · [RealSense post-processing](https://dev.realsenseai.com/docs/depth-post-processing-for-intel-realsense-depth-camera-d400-series/) · [PMD Flexx2 noise model, arXiv 2412.15040](https://arxiv.org/pdf/2412.15040) · [GRIBBOT](https://doi.org/10.1016/j.compag.2015.11.021) · [LiDAR-camera apple, arXiv 2205.00404](https://arxiv.org/pdf/2205.00404) · [Pig carcass RGB-D dataset](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8866887/) · [XYZ-IBD, arXiv 2506.00599](https://arxiv.org/abs/2506.00599)

**Boundary refinement.** [DenseCRF, arXiv 1210.5644](https://arxiv.org/abs/1210.5644) · [DeepLab, arXiv 1606.00915](https://arxiv.org/abs/1606.00915) · [Fast guided filter, arXiv 1505.00996](https://arxiv.org/abs/1505.00996) · [Fast bilateral solver, arXiv 1511.03296](https://arxiv.org/abs/1511.03296) · [Chan-Vese](https://www.math.ucla.edu/~lvese/PAPERS/IEEEIP2001.pdf) · [Morphological snakes, IPOL 2012](https://doi.org/10.5201/ipol.2012.abmh-rtmsa) · [GrabCut](https://www.microsoft.com/en-us/research/wp-content/uploads/2004/08/siggraph04-grabcut.pdf) · [CascadePSP, arXiv 2005.02551](https://arxiv.org/abs/2005.02551) · [CascadePSP repo](https://github.com/hkchengrex/CascadePSP) · [SegFix, arXiv 2007.04269](https://arxiv.org/abs/2007.04269) · [SegRefiner, arXiv 2312.12425](https://arxiv.org/abs/2312.12425) · [Devernay sub-pixel edge detector, IPOL 2017](https://doi.org/10.5201/ipol.2017.216) · [ViTMatte, arXiv 2305.15272](https://arxiv.org/abs/2305.15272) · [Robust Video Matting, arXiv 2108.11515](https://arxiv.org/abs/2108.11515)

**Specular highlights.** [Shafer 1985](https://doi.org/10.1002/col.5080100409) · [Tan and Ikeuchi 2005](https://doi.org/10.1109/TPAMI.2005.36) · [Shen and Zheng 2013](https://doi.org/10.1364/AO.52.004483) · [SIHR toolbox](https://github.com/vitorsr/SIHR) · [Souza et al., SIBGRAPI 2018](https://doi.org/10.1109/SIBGRAPI.2018.00014) · [CUDA implementation](https://github.com/MarcioCerqueira/RealTimeSpecularHighlightRemoval) · [Feris multi-flash](http://rogerioferis.com/publications/FerisSIB04.pdf) · [Niemitz et al. 2023](https://doi.org/10.3390/mi14051062) · [Nie et al. 2023](https://doi.org/10.3390/s23020974) · [Fu et al., CVPR 2021, SHIQ](https://openaccess.thecvf.com/content/CVPR2021/papers/Fu_A_Multi-Task_Network_for_Joint_Specular_Highlight_Detection_and_Removal_CVPR_2021_paper.pdf) · [TSHRNet, arXiv 2309.06302](https://arxiv.org/abs/2309.06302) · [Daher et al.](https://doi.org/10.1016/j.media.2023.102994) · [Hale and Querry 1973](https://doi.org/10.1364/AO.12.000555)

**Industry.** [JBT US10869489B2](https://patents.google.com/patent/US10869489B2/en) · [Marel I-Cut 56 brochure](https://jbtmarel.com/media/ql3jfprl/i-cut-56.pdf) · [Marel I-Cut 11 brochure](https://jbtmarel.com/media/bpclpsv3/me21_br_271_i-cut11_en_lq.pdf) · [DSI waterjet portioning](https://jbtmarel.com/en/products/dsi-waterjet-portioning-systems/) · [DSI J-Scan flyer](https://jbtmarel.com/media/pzrdcgxg/dsi-j-scan-flyer.pdf) · [SensorX Optima](https://jbtmarel.com/en/products/sensorx-optima/) · [Scott automated boning room](https://scottautomation.com/en/products/meat/automated-boning-room) · [Scott grading](https://scottautomation.com/en/products/meat/grading) · [MLA A.MQA.0017, DEXA](https://www.mla.com.au/contentassets/ab6ab1e8f0214babb6ffecd72211fa5b/a.mqa.0017_final_report.pdf) · [MLA P.PIP.0772, Leap4Beef post mortem](https://www.mla.com.au/contentassets/13e2161b4d1145aa846f1587ffaa7eca/p.pip.0772---leap4beef-beef-boning-automation---final-report_approved---clean-copy.pdf) · [EU 2022/1205, AutoFOM III and IV](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32022D1205) · [Baader ClassifEYE 2.0](https://www.baader.com/media/blog/the-future-of-quality-detection-and-vision-technology-an-interview-with-dr-fabian-isernhagen) · [SICK Ranger3](https://web.archive.org/web/2020id_/https://cdn.sick.com/media/familyoverview/4/54/354/familyOverview_Ranger3_g448354_de.pdf) · [Keyence LJ-X8000 specs](https://www.keyence.com/products/measure/laser-2d/lj-x8000/specs/) · [TOMRA Nimbus brochure](https://web.archive.org/web/2018id_/https://www.tomra.com/-/media/documents/food-brochures/archive---old-brochures-2017/new-food-brochures-26072017/brochure-nimbus---en.pdf) · [RoBUTCHER, CORDIS 871631](https://cordis.europa.eu/project/id/871631) · [RoBUTCHER platform paper, IJRR 2024](https://doi.org/10.1177/02783649241234035)
