---
title: Computer vision fundamentals for a robot learning engineer
date: 2026-09-06
tags: [topic, perception, cameras, calibration, segmentation, depth, attention, conveyors, evaluation]
status: draft
source: synthesis   # primary links inline and under Sources; unverified items tagged
---

# Computer vision fundamentals for a robot learning engineer

Companion notes: `perception-foundation-models.md` (model zoo, licences),
`perception-3d-sensing.md` (depth sensors, hand-eye, point clouds),
`perception-for-policy-learning.md` (encoders, perception-action interface).
This note goes under those: image formation, the classical tools still in
daily use, training and judging a segmenter on a customer's parts, which
depth method to trust, and what the attention layers in a policy do with
the camera.

## What it is

The chain from photons to a tensor a policy can act on. Each link has
parameters that can be wrong: lens (intrinsics, distortion), sensor
(shutter, exposure, gain), scene optics (specularity, polarization, motion),
and the operator that turns pixels into masks, depths, keypoints, or
features. A robot learning engineer rarely writes a new operator; they
diagnose which link broke when the policy fails under plant lighting.

## Why it matters in the field

- Most policy failures at a customer site trace to the image, not the
  network: auto-exposure flaring on a wet floor, a fisheye wrist camera
  undistorted with the wrong model, a rolling-shutter smear during a fast
  reach. The existing notes assume clean images; this one is about making
  them.
- A segmenter on 200 plant images is a two-day job when the labelling loop
  exists and a two-week job when it does not. That loop repeats on every
  engagement.
- Conveyor work is a different regime from tabletop: parts move at 0.3 to
  2 m/s, so shutter, strobe, trigger, and encoder sync decide whether any
  learning is possible (from field, unverified).
- Attention sits inside every policy that matters (ACT, Diffusion Policy,
  π0). Reading attention maps is the fastest way to tell whether a policy is
  looking at the camera or at proprioception.

## Image formation and camera models

### Pinhole, distortion, fisheye

The pinhole model maps a 3D point through `K = [[fx,0,cx],[0,fy,cy],[0,0,1]]`
after a rigid transform; OpenCV's `calib3d` module documents the full chain
including the radial (`k1..k6`), tangential (`p1, p2`), thin-prism
(`s1..s4`) and tilted-sensor (`tau_x, tau_y`) coefficients that
`cv::calibrateCamera` can estimate, with flags to fix any subset
([OpenCV calib3d](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html)).
The planar-target method behind it is Zhang's
([Zhang 2000, TPAMI](https://doi.org/10.1109/34.888718)).

The plumb-bob model diverges past roughly 120 degrees of field of view; wide
wrist cameras and ceiling cameras need the equidistant fisheye model
(Kannala-Brandt, four coefficients `k1..k4`) in `cv::fisheye`
([OpenCV fisheye](https://docs.opencv.org/4.x/db/d58/group__calib3d__fisheye.html),
[Kannala and Brandt 2006](https://doi.org/10.1109/TPAMI.2006.153)). A fisheye
calibrated with the pinhole model fits the centre and fails at the edges,
which is where the gripper appears in most wrist-camera mounts (from field,
unverified). ROS 2 `CameraInfo` carries `distortion_model` as a string
(`plumb_bob`, `rational_polynomial`, `equidistant`); a driver that publishes
the wrong string silently breaks `image_proc` rectification
([CameraInfo.msg](https://raw.githubusercontent.com/ros2/common_interfaces/humble/sensor_msgs/msg/CameraInfo.msg)).

### Shutter, motion blur, exposure and gain

A rolling-shutter sensor exposes rows sequentially, so a fast arm or a
belt at 1 m/s skews vertical edges; a global shutter exposes all rows at
once. RealSense D435i and ZED 2i RGB are rolling shutter; D455, ZED X and
Gemini 335L are global (see `perception-3d-sensing.md`). Blur in pixels is
`v * t_exp * f / Z`: 1 m/s, 1 m away, 700 px focal length, 2 ms exposure
smears 1.4 px; 10 ms smears 7 px. Short exposure needs light, so plant
cameras use strobes or LED bars and fixed gain.

Auto-exposure and auto-gain change the input distribution frame to frame.
Wet stainless and wet product throw specular highlights that drive
auto-exposure down and blacken everything else. Fix exposure and gain per
camera in the driver, write the values into `DATASET.md`, and treat any
change as a new dataset condition (from field, unverified). If dynamic range
is genuinely too large, use sensor-level HDR (multi-slope or dual-exposure,
vendor specific, unverified) or a multi-exposure merge; OpenCV documents
Debevec, Robertson and Mertens fusion
([OpenCV HDR tutorial](https://docs.opencv.org/4.x/d2/df0/tutorial_py_hdr.html)),
and Mertens needs no response curve.

### Polarization

Specular reflections off wet or glossy surfaces are partially polarized;
a sensor with an on-chip four-direction polarizer array (Sony Polarsens
IMX250MZR and successors, 0, 45, 90, 135 degrees on a 2x2 pixel block)
captures degree and angle of linear polarization in one shot
([Sony Polarsens](https://www.sony-semicon.com/en/technology/industry/polarsens.html)).
Plant uses: glare suppression on wet trays, separating plastic film from
product, normals on shiny featureless parts (shape from polarization; scene
dependent, unverified). The cheap first step is a linear polarizer on the
lens and polarized lighting at 90 degrees, which removes most specular
return for about two stops of light (from field, unverified).

## Classical tools still used daily

| Tool | Where it still wins | OpenCV entry point |
|---|---|---|
| Intrinsic calibration and undistortion | Every camera, every time; precomputed maps make undistortion a lookup | `calibrateCamera`, `initUndistortRectifyMap`, `remap` ([calib3d](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html)) |
| Background subtraction | Fixed camera over a conveyor: foreground = product, no training | `BackgroundSubtractorMOG2` ([doc](https://docs.opencv.org/4.x/d7/d7b/classcv_1_1BackgroundSubtractorMOG2.html)); fixed-belt reference image and a threshold is often enough |
| Connected components, blobs, contours | Turn a mask into instances with area, centroid, bounding box, orientation in microseconds | `connectedComponentsWithStats`, `findContours`, `minAreaRect`, `moments` ([imgproc shape](https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html)) |
| Morphological ops | Clean learned masks: open to remove specks, close to fill holes, erode before grasp point selection so the grasp lands inside the part | `morphologyEx` ([tutorial](https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html)) |
| Colour spaces | Food: HSV or CIELAB thresholds separate fat, lean, bone, and belt; hue is roughly illumination invariant, L*a*b* `a*` tracks redness | `cvtColor` ([colour conversions](https://docs.opencv.org/4.x/de/d25/imgproc_color_conversions.html)); which channel separates which product class is empirical (unverified) |
| Template matching | Fixed-orientation fiducials, printed labels, repeated fixtures | `matchTemplate` ([tutorial](https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html)); fails on rotation and scale |
| Fiducials | Calibration targets, hand-eye, conveyor tracking, ground truth for pose evaluation | `cv::aruco` with ChArUco boards ([tutorial](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html)); AprilTag 3 library for flexible layouts and better false-positive rejection ([repo](https://github.com/AprilRobotics/apriltag), [Krogius et al. 2019](https://april.eecs.umich.edu/papers/details.php?name=krogius2019iros)) |

Run the classical pipeline as baseline and monitor: a MOG2 foreground count
is the per-shift sanity check on the segmenter's instance count. Cleanup
runs after the network: a 5 px mask erosion before the grasp centroid
removed the "grasp on the edge" failure more than once (from field, unverified).

## Segmentation in depth

### Taxonomy

| Kind | Output | When a robot needs it | Representative models |
|---|---|---|---|
| Semantic | one class per pixel | belt vs product vs hand for safety; fat vs lean | Mask2Former semantic head ([arXiv 2112.01527](https://arxiv.org/abs/2112.01527)), SegFormer |
| Instance | mask per object | picking: which fillet, which parcel | YOLO-seg ([Ultralytics segment task](https://docs.ultralytics.com/tasks/segment/)), Mask2Former instance head |
| Panoptic | instance for things, semantic for stuff | scene understanding for mobile manipulation | Mask2Former: 57.8 PQ COCO, 50.1 AP COCO instance, 57.7 mIoU ADE20K ([abstract](https://arxiv.org/abs/2112.01527)) |
| Promptable | mask from a point, box, text, or exemplar | first demo with no labels; labelling assistant | SAM 2 ([repo](https://github.com/facebookresearch/sam2)), SAM 3 with text and exemplar prompts and released fine-tuning code ([repo](https://github.com/facebookresearch/sam3)) |

Licences matter: Ultralytics YOLO is AGPL-3.0 with a paid commercial licence
([Ultralytics licensing](https://www.ultralytics.com/license)); Mask2Former
code is MIT with backbone-specific terms ([repo](https://github.com/facebookresearch/Mask2Former));
SAM 2 is Apache 2.0 and SAM 3 is under the SAM License (see the foundation
models note).

### Training a small segmenter from 200 labelled images

The realistic starting point at a customer is 100 to 300 frames of the
actual product on the actual belt. What works:

1. Capture across conditions on purpose: every shift and lighting state,
   wet and dry belt, full and sparse belt, gripper in frame. A stratified
   200 beats a random 2000 from one afternoon (from field, unverified).
2. Label with a promptable model in the loop. CVAT ships SAM interactive
   segmentation as a serverless function ([CVAT](https://github.com/cvat-ai/cvat), MIT);
   Label Studio has a SAM ML backend ([Label Studio](https://github.com/HumanSignal/label-studio), Apache 2.0,
   [ML backend](https://github.com/HumanSignal/label-studio-ml-backend));
   Roboflow hosts SAM-assisted labelling commercially ([Roboflow](https://roboflow.com)).
   A click per instance plus an edge-correction pass is 10 to 30 s per
   frame on simple product (from field, unverified).
3. Fine-tune something small. YOLO11-seg n/s from COCO weights converges on
   200 images in under an hour on a laptop GPU (from field, unverified;
   Ultralytics publishes no low-data curve). Mask2Former Swin-T when
   semantic and instance are both needed. SAM 2 or SAM 3 fine-tuning when
   the object is hard (thin film, translucent) and the inference budget
   allows.
4. Handle imbalance in the loss, not by dropping data: focal loss
   ([Lin et al. 2017](https://arxiv.org/abs/1708.02002)) or Dice loss
   ([Milletari et al. 2016](https://arxiv.org/abs/1606.04797)), inverse
   frequency weights as the fallback. A class with 5 instances in 200
   frames is not learnable; collect more or merge it.
5. Augment for the plant, not ImageNet: colour jitter bounded by the
   measured lighting range, motion blur along the belt axis, specular
   overlays, random erase where the gripper occludes
   ([Albumentations](https://github.com/albumentations-team/albumentations)).
   Flips are wrong if belt direction is a feature.

### Metrics

mIoU (mean over classes of intersection over union) is the semantic
metric; AP at IoU thresholds 0.5:0.95 over instances is the COCO instance
metric ([COCO detection eval](https://cocodataset.org/#detection-eval)).
Both hide what a robot cares about, so also report instance count error per
frame and centroid error in millimetres after back-projection. A segmenter
at 0.92 mIoU that merges two touching fillets has 0% pick success there.

### Domain shift under plant lighting

Sodium and fluorescent lighting, skylights, and shift changes move colour
temperature further than any lab augmentation covers unless it is measured.
Order of fixes: lock exposure and white balance in the driver; put a grey
card in the scene and normalise per frame; augment with the measured range;
last, label a small set per condition and fine-tune. Test-time adaptation is
unproven here (unverified).

## Depth modelling

### Stereo: classical to learned

Semi-global matching aggregates a pixelwise matching cost along 8 or 16
paths with smoothness penalties `P1`, `P2`
([Hirschmüller 2008](https://doi.org/10.1109/TPAMI.2007.1166)); OpenCV's
`StereoSGBM` exposes `numDisparities`, `blockSize`, `P1`, `P2`, and
`uniquenessRatio` ([doc](https://docs.opencv.org/4.x/d2/d85/classcv_1_1StereoSGBM.html)).
It runs on a CPU at camera rate for VGA and fails on textureless regions,
which is why active-stereo cameras project a pattern.

RAFT-Stereo replaces cost aggregation with iterative GRU updates over a
correlation volume ([Lipson et al. 2021](https://arxiv.org/abs/2109.07547),
[repo](https://github.com/princeton-vl/RAFT-Stereo)). FoundationStereo
(NVIDIA, CVPR 2025) trains a RAFT-style network on a large synthetic set
with a monocular-depth prior for zero-shot use on unseen cameras
([Wen et al. 2025](https://arxiv.org/abs/2501.09898),
[repo](https://github.com/NVlabs/FoundationStereo); weights licence
unverified). Learned stereo needs a GPU and rectified pairs; the payoff is
dense depth on wet, dark, and shiny product where active stereo has holes.

### Monocular metric depth

Depth Anything 3 (metric variants), Metric3D v2, and UniDepthV2 predict
metric depth from one RGB frame conditioned on intrinsics (links and
licences in `perception-foundation-models.md`); a wrong focal length scales
the whole map. Strength: completeness. Weakness: absolute accuracy on flat
textureless belts, where the network guesses from priors.

### When to trust which

| Situation | Trust | Why |
|---|---|---|
| Opaque, textured, dry parts within sensor range | RGB-D sensor depth | Metric, calibrated, fast; see `perception-3d-sensing.md` |
| Wet, specular, dark product on a belt | Learned stereo (FoundationStereo, RAFT-Stereo) on the sensor's raw IR pair | Fills projector-loss holes; still metric via the baseline (accuracy on your product unverified) |
| Single RGB camera only, relative layout needed | Monocular relative depth | Ordering and shape, not metres |
| Single RGB camera, grasp height needed | Monocular metric + one known plane (belt height) as a scale anchor | Anchoring removes the focal-length scale error (from field, unverified) |
| Transparent packaging | Depth completion trained on transparent objects, or tactile | Sensors return the background ([ClearGrasp](https://arxiv.org/abs/1910.02550)) |

### Depth completion and multi-camera fusion

Holes on wet reflective surfaces are missing data returned as 0; any mean
over the patch is biased. Order of attempts: mask the holes and let the
grasp planner use the surrounding surface; guided filtering with the RGB
edge map; a learned completion network (ClearGrasp, TransCG; links in the
3D note) if holes cover the grasp region. Multi-camera fusion is
transform-and-concatenate when extrinsics are good and TSDF integration
when a surface is needed
([Open3D RGBD integration](https://www.open3d.org/docs/release/tutorial/pipelines/rgbd_integration.html)).
Cameras that disagree on an overlap region by more than their noise have
drifted extrinsics; log the overlap residual as a calibration monitor (from
field, unverified).

## Attention and transformer internals as used in perception and policies

### The mechanism

Scaled dot-product attention computes `softmax(Q K^T / sqrt(d)) V`;
self-attention has Q, K, V from the same token set, cross-attention takes Q
from one set and K, V from another
([Vaswani et al. 2017](https://arxiv.org/abs/1706.03762)). A ViT cuts the
image into patches (16x16 or 14x14 px), linearly embeds each, adds a
positional embedding, and runs self-attention over the resulting tokens
([Dosovitskiy et al. 2020](https://arxiv.org/abs/2010.11929)). The number of
tokens is `(H/p) * (W/p)`: 224x224 at patch 14 is 256 tokens; 480x640 at
patch 14 is about 1560. Attention cost is quadratic in that count, which is
why policies downsample or resample tokens.

### The tools policies use

- **FiLM** scales and shifts feature maps with a conditioning vector
  (`gamma * x + beta`) ([Perez et al. 2017](https://arxiv.org/abs/1709.07871)).
- **Perceiver resampler**: a fixed number of learned latent queries
  cross-attend to all visual tokens, so the token budget is constant across
  resolution and camera count ([Perceiver](https://arxiv.org/abs/2103.03206),
  [Flamingo](https://arxiv.org/abs/2204.14198)). TokenLearner does the same
  with learned spatial attention, 81 to 8 tokens per image in RT-1
  ([TokenLearner](https://arxiv.org/abs/2106.11297), [RT-1](https://arxiv.org/abs/2212.06817)).
- **DETR-style queries**: a fixed set of query vectors cross-attend to
  encoder tokens and each yields one output ([Carion et al. 2020](https://arxiv.org/abs/2005.12872));
  Mask2Former restricts each query to its predicted mask
  ([arXiv 2112.01527](https://arxiv.org/abs/2112.01527)).

### How three policies wire the camera in

**ACT.** Each of 4 cameras at 480x640 goes through a ResNet-18 to a
15x20x512 feature map, flattened to 300 tokens with a 2D sinusoidal
position embedding; all cameras give 1200 tokens, plus one token for joint
positions and one for the CVAE style variable `z`, for a 1202x512 encoder
input. A 4-layer self-attention encoder feeds a 7-layer decoder whose
queries are fixed sinusoidal embeddings of size `k x 512`; the decoder output
is projected to `k x 14` actions. Hidden dim 512, 8 heads
([Zhao et al. 2023](https://arxiv.org/abs/2304.13705), appendix). The
chunk is cross-attention from chunk-position queries onto image tokens: if
decoder attention concentrates on the joint token, the cameras are unused.

**Diffusion Policy.** A ResNet-18 per camera with spatial softmax pooling
and GroupNorm gives observation features; the CNN variant conditions the
1D U-Net on them with FiLM, the transformer variant feeds them to the
decoder through cross-attention. Image horizon is short (`To = 2`) and the
CNN vision variant degrades as it grows
([Chi et al. 2023](https://arxiv.org/abs/2303.04137)).

**π0.** PaliGemma (SigLIP encoder, Gemma 2B) takes 2 or 3 images and a
prompt; robot state `q_t` and the noisy action chunk (H = 50) are separate
token blocks routed to a 300M-parameter action expert with its own weights. A blockwise causal mask lets
`[images, language]` attend only within itself, `[q_t]` attend to the
images and language, and `[actions]` attend to everything; the experts
interact only in the self-attention layers
([Black et al. 2024](https://www.pi.website/download/pi0.pdf), appendix B).
Images go in at PaliGemma's 224x224, 256 tokens per image at patch 14
([PaliGemma](https://arxiv.org/abs/2407.07726)); a 480x640 wrist camera
loses 3x linear resolution first, and thin edges vanish (from field, unverified).

### What to inspect when a policy ignores the camera

1. Attention mass by source: per decoder layer, sum weights over image
   tokens vs proprio tokens; a healthy policy puts most mass near the
   gripper during contact (from field, unverified). Attention rollout gives
   the aggregate ([Abnar and Zuidema 2020](https://arxiv.org/abs/2005.00928)).
2. Input ablation: zero or shuffle the image and measure the action change;
   if it barely moves, the policy is a proprio copycat (shortcut evidence in
   `perception-for-policy-learning.md`).
3. Gradient saliency ([Grad-CAM](https://arxiv.org/abs/1610.02391)) for
   CNN encoder variants where attention maps do not exist.
4. Resolution check: view the image at the policy's actual input size. If a
   human cannot see the part at 224x224, neither can the policy. A ViT run
   at a resolution other than its training one also needs interpolated
   positional embeddings; custom exports often skip this (unverified).

## Representation abstractions: what to hand the policy

| Representation | Right interface when | Fails when | Evidence |
|---|---|---|---|
| Raw pixels (1 to 4 cameras) | Contact-rich, deformable, or when you cannot say in advance what matters; enough demos (50+) | Lighting and viewpoint shift; needs augmentation and fixed exposure | ACT, Diffusion Policy ([ACT](https://arxiv.org/abs/2304.13705), [DP](https://arxiv.org/abs/2303.04137)) |
| Frozen features (DINOv2, SigLIP, R3M, VC-1) | Few demos; want pretrained invariance; policy head trains in minutes | Fine spatial detail lost; features not metric | [R3M](https://arxiv.org/abs/2203.12601), [VC-1](https://arxiv.org/abs/2303.18240), evidence table in `perception-for-policy-learning.md` |
| Keypoints | Task is about a few points (hook, hole, handle); interpretable; VLM-writable constraints | Occluded keypoints; deformables | [ReKep](https://arxiv.org/abs/2409.01652), [KAT](https://arxiv.org/abs/2403.19578) |
| Masks (instance) | Pick-and-place of rigid or near-rigid product on a belt; grasp from mask + depth | Touching instances merge; thin objects | This note, foundation models note |
| 3D points (masked cloud) | Grasping under viewpoint change; sim-to-real (geometry transfers better than pixels) | Depth holes on wet or transparent product | [DP3](https://arxiv.org/abs/2403.03954) |
| Object 6D pose | CAD exists; grasps pre-annotated; assembly | No CAD; symmetric or deformable objects | FoundationPose (foundation models note) |
| Scene graph | Multi-object language tasks; long-horizon planning | Real-time manipulation; graph construction latency | [ConceptGraphs](https://arxiv.org/abs/2309.16650) |
| Learned latent (world model) | Model-based RL, prediction | Interpretability, debugging in the field | Beyond this note; see `real-world-rl.md` |

Rule of thumb: pick the most abstract representation that still contains
the information the task needs, because abstraction is what survives a
lighting change, and pick pixels when you cannot name that information.

## High-speed and line-scan vision for conveyors

- **Global shutter and strobe.** A global-shutter sensor and a strobed LED
  (tens of microseconds) fired from the camera's exposure output freeze
  motion; ambient light then contributes little, which also removes the
  shift-change lighting problem (from field, unverified).
- **Trigger and sync.** One hardware pulse makes multi-camera frames
  simultaneous; GigE Vision and USB3 Vision cameras expose trigger and
  exposure-active lines through GenICam (feature names unverified).
- **Encoder-triggered acquisition.** One frame (or one line) per N encoder
  pulses makes image geometry independent of belt speed; Basler and
  Teledyne DALSA line-scan cameras take a shaft encoder input (vendor docs,
  unverified for the exact model).
- **Line-scan.** One row of 2k to 16k pixels; along-belt resolution equals
  belt travel per line. Suits wide belts and flat product. A speed change
  without encoder triggering stretches the image and the segmenter fails
  (from field, unverified).
- **Latency budget.** Frame at t0, robot at the pick point at t0 + 400 ms:
  the part has moved `v * 0.4 s`. The pick pose needs the belt encoder value
  at capture time; `sensors-and-actuators.md` covers the encoder side.

## Evaluation practice

Hold out by day and by condition, never by random frame: a random split from
one afternoon reports 0.9 mIoU and the plant reports 0.6 (from field,
unverified). Report every metric per condition (shift, lighting, wetness,
density) with the frame count; the worst cell, not the mean, decides
readiness. Test calibration drift on purpose: re-run the fiducial check
after a shift of vibration and after any camera bump, log the pixel residual
against the commissioning value. Grasp offsets that grow together across all
objects are a calibration problem, not a model problem.

## Practical recipe: labelling to deployment for a new object class

1. **Define the class and the metric.** One sentence for what counts as an
   instance (a fillet with skin on and off is one class or two). Decide the
   acceptance metric before labelling: e.g. instance count error under 2%
   and centroid error under 5 mm at the belt on 100 held-out frames.
2. **Capture.** 200 to 300 frames stratified by shift, lighting, wetness,
   and density; fixed exposure and gain; write `DATASET.md`.
3. **Label.** CVAT with the SAM function or Label Studio with the SAM
   backend; one annotator, one reviewer; export COCO JSON. Keep 50 frames
   from a separate day as held-out and never open them in the tool.
4. **Train.** YOLO11-seg s from COCO weights or Mask2Former Swin-T; focal
   or Dice loss for the rare class; Albumentations set bounded by the
   measured lighting range; 5-fold on the 200 to pick epochs, then one run
   on all 200. Record in `experiments/` with the hypothesis and the seed.
5. **Evaluate per condition** on the held-out day: AP, count error,
   centroid error, per shift and per belt state. Report trial counts.
6. **Export** to ONNX and TensorRT FP16 on the deployment device; compare
   masks with PyTorch on 20 fixed frames (IoU over 0.98 per frame; from
   field, unverified).
7. **Deploy behind a monitor.** MOG2 foreground count vs segmenter count
   per frame; log disagreements with the frame; alert above a threshold.
8. **On drift**, re-run intrinsics and the fiducial check before blaming the
   model.

## Practical gotchas

- Plumb-bob undistortion on a fisheye lens leaves centimetre errors at the
  edges where the gripper sits (from field, unverified).
- Auto white balance flips between sodium and daylight in the same shift;
  a segmenter trained on one fails on the other. Lock it in the driver.
- Rolling-shutter smear during a fast reach reads as a shape change to the
  encoder; global-shutter RGB or a shorter exposure fixes it.
- SAM-assisted masks hug specular highlights and cut the object; reviewers
  must correct edges, not just clicks (from field, unverified).
- TensorRT masks differ from PyTorch masks at thin edges; the 3D note's
  numerical-drift warning applies to segmenters too.

## What a forward-deployed engineer must be able to do

1. Calibrate any camera with the right distortion model and verify with a
   ChArUco reprojection error.
2. Configure exposure, gain, white balance, trigger, and strobe for moving
   product and write the values into the dataset record.
3. Stand up a labelling loop (CVAT or Label Studio with SAM) and train a
   segmenter on 200 frames in a day, with a held-out-by-day evaluation.
4. Choose and defend a depth source per scene from the table above; run
   FoundationStereo or RAFT-Stereo on a raw IR pair and compare with the
   sensor's depth on the actual product.
5. Read attention and saliency from ACT, Diffusion Policy, and π0 to tell
   whether the camera is being used, and change resolution or token budget
   when it is not.
6. Explain the representation table to a customer: why masks plus depth for
   their belt, why pixels for their contact task.
7. Write the per-condition evaluation and the drift monitor before the
   model ships.

## Open questions

- FoundationStereo on the RealSense or Gemini raw IR pair vs the vendor's
  active-stereo depth on wet fillets, against a laser-scanner ground truth.
- Labelled frames needed for SAM 3 fine-tuning to match YOLO11-seg trained
  on 200, and the inference cost on Orin.
- Whether policies trained on encoder-triggered conveyor frames transfer
  across belt speeds.
- Whether attention mass on camera tokens at training time predicts field
  success rate.

## Related entries

- `library/topics/perception-foundation-models.md`, `perception-3d-sensing.md`, `perception-for-policy-learning.md`
- `library/topics/sensors-and-actuators.md` (conveyor encoders, line lasers)
- `library/topics/imitation-learning.md`, `policy-evaluation.md`
- `library/hardware/depth-cameras.md`

## Sources

- Image formation: [OpenCV calib3d](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html), [OpenCV fisheye](https://docs.opencv.org/4.x/db/d58/group__calib3d__fisheye.html), [Zhang 2000](https://doi.org/10.1109/34.888718), [Kannala and Brandt 2006](https://doi.org/10.1109/TPAMI.2006.153), [CameraInfo.msg](https://raw.githubusercontent.com/ros2/common_interfaces/humble/sensor_msgs/msg/CameraInfo.msg), [OpenCV HDR](https://docs.opencv.org/4.x/d2/df0/tutorial_py_hdr.html), [Sony Polarsens](https://www.sony-semicon.com/en/technology/industry/polarsens.html)
- Classical tools: [MOG2](https://docs.opencv.org/4.x/d7/d7b/classcv_1_1BackgroundSubtractorMOG2.html), [imgproc shape](https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html), [morphology](https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html), [colour conversions](https://docs.opencv.org/4.x/de/d25/imgproc_color_conversions.html), [template matching](https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html), [ArUco](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html), [AprilTag repo](https://github.com/AprilRobotics/apriltag), [Krogius et al. 2019](https://april.eecs.umich.edu/papers/details.php?name=krogius2019iros)
- Segmentation: [Mask2Former](https://arxiv.org/abs/2112.01527), [Mask2Former repo](https://github.com/facebookresearch/Mask2Former), [Ultralytics segment](https://docs.ultralytics.com/tasks/segment/), [Ultralytics licence](https://www.ultralytics.com/license), [SAM 2](https://github.com/facebookresearch/sam2), [SAM 3](https://github.com/facebookresearch/sam3), [CVAT](https://github.com/cvat-ai/cvat), [Label Studio](https://github.com/HumanSignal/label-studio), [Label Studio ML backend](https://github.com/HumanSignal/label-studio-ml-backend), [Roboflow](https://roboflow.com), [focal loss](https://arxiv.org/abs/1708.02002), [Dice loss](https://arxiv.org/abs/1606.04797), [Albumentations](https://github.com/albumentations-team/albumentations), [COCO eval](https://cocodataset.org/#detection-eval)
- Depth: [SGM](https://doi.org/10.1109/TPAMI.2007.1166), [StereoSGBM](https://docs.opencv.org/4.x/d2/d85/classcv_1_1StereoSGBM.html), [RAFT-Stereo](https://arxiv.org/abs/2109.07547), [RAFT-Stereo repo](https://github.com/princeton-vl/RAFT-Stereo), [FoundationStereo](https://arxiv.org/abs/2501.09898), [FoundationStereo repo](https://github.com/NVlabs/FoundationStereo), [ClearGrasp](https://arxiv.org/abs/1910.02550), [Open3D RGBD integration](https://www.open3d.org/docs/release/tutorial/pipelines/rgbd_integration.html)
- Attention and policies: [Vaswani et al. 2017](https://arxiv.org/abs/1706.03762), [ViT](https://arxiv.org/abs/2010.11929), [DETR](https://arxiv.org/abs/2005.12872), [FiLM](https://arxiv.org/abs/1709.07871), [Perceiver](https://arxiv.org/abs/2103.03206), [Flamingo](https://arxiv.org/abs/2204.14198), [TokenLearner](https://arxiv.org/abs/2106.11297), [ACT](https://arxiv.org/abs/2304.13705), [Diffusion Policy](https://arxiv.org/abs/2303.04137), [π0](https://www.pi.website/download/pi0.pdf), [PaliGemma](https://arxiv.org/abs/2407.07726), [RT-1](https://arxiv.org/abs/2212.06817), [attention rollout](https://arxiv.org/abs/2005.00928), [Grad-CAM](https://arxiv.org/abs/1610.02391)
- Representations: [R3M](https://arxiv.org/abs/2203.12601), [VC-1](https://arxiv.org/abs/2303.18240), [ReKep](https://arxiv.org/abs/2409.01652), [KAT](https://arxiv.org/abs/2403.19578), [DP3](https://arxiv.org/abs/2403.03954), [ConceptGraphs](https://arxiv.org/abs/2309.16650)
