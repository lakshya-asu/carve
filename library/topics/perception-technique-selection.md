---
title: Choosing the perception technique for grasp pose and alignment axis on a belt
date: 2026-09-08
tags: [topic, perception, selection, segmentation, grasp-pose, meat-cell, yolo, sam, 6d-pose]
status: draft
source: synthesis
---

# Choosing the perception technique for grasp pose and alignment axis on a belt

## What this decides

One question, one application: a meat piece lies on a moving belt under fixed lighting, and something has to emit
a grasp pose and an alignment axis before the piece leaves the pick window. Every candidate is judged against
that, not against a benchmark. The cell and the latency budget are in
[meat-cutting-automation](meat-cutting-automation.md) and
[conveyor-tracking-and-visual-servoing](conveyor-tracking-and-visual-servoing.md); the techniques themselves are in
[computer-vision-fundamentals](computer-vision-fundamentals.md) and
[perception-foundation-models](perception-foundation-models.md). Numbers marked *measured here* come from
`snippets/pose_from_mask.py`, run 2026-09-08 with OpenCV 4.5.4 on an Intel i7-8750H; reproduce with
`python3 -m pytest snippets/pose_from_mask.py` (5 passed).

## The output contract

Write this before choosing anything. The intercept planner, the gripper and the fixture want different things.

| Field | Units and frame | Tolerance to aim at |
|---|---|---|
| Grasp point | x, y in the belt frame at the encoder count of the shutter; z from the belt plane plus piece height | Cross-belt error is what matters; along-belt error is partly absorbed by the encoder ([conveyor note](conveyor-tracking-and-visual-servoing.md#tracking)) |
| Grasp clearance | mm from the grasp point to the nearest mask edge | Greater than the pad radius, or the cup leaks onto the belt |
| Approach and tool axis | yaw about the belt normal; roll and pitch only if the piece is not flat | Set by the principal axis and the pad geometry |
| Alignment axis | yaw of the long axis, modulo 180 degrees | 5 degrees at the fixture, per [deformable-object-manipulation](deformable-object-manipulation.md#placement-and-alignment-into-a-fixture) |
| Side-up | discrete label: fat cap, skin, cut face | Separate from yaw; a 180-degree flip is a different failure from an angle error |
| Confidence and stamp | scalar plus the encoder count at shutter | A pose without a count is unusable |

The two required outputs are not the same problem: a grasp point is a position where a cup or a pad can sit, an
alignment axis is a direction, and several candidates give one and not the other. Each is judged below on output,
sufficiency for grasping, sufficiency for alignment, labelled data, latency with the hardware named, behaviour on
a wet reflective surface, and licence.

## 1. Classical: belt subtraction, components, moments, PCA, rotated rectangle

**Output.** A per-instance binary mask, then the image-moment centroid, the PCA principal axis, the minimum-area
rotated rectangle, and the largest inscribed circle. OpenCV entry points: `absdiff` and `threshold`,
`morphologyEx`, `connectedComponentsWithStats`, `findContours`, `moments`, `minAreaRect`
([imgproc shape](https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html)). Fixed camera, fixed lighting,
uniform belt, one object class: the best case for classical vision, and why the portioner vendors ship it.

**Sufficient for grasping.** Yes, with two corrections that are easy to get wrong. The moment centroid is the area
centroid, not the box centre. The minimum-area rectangle's centre is the centre of the *box*, so on a 200 by 80 mm
trapezoid narrowing to a third of its wide end it sits 16.7 mm from the area centroid at every rotation (*measured
here*; analytically `h(2b + a) / (3(a + b))` from the wide end). Use `moments` for the point and `minAreaRect` only
for the axis and the extent.

The area centroid can leave the piece. For a curved cut modelled as a 40 mm wide annular band of outer radius
130 mm, the centroid is on the mask at a 126 degree arc and off it at a 160 degree arc (*measured here*). The fix
is a different point, not a better centroid: the maximum of the distance transform is the centre of the largest
inscribed circle, is inside the mask by construction, and its value is the clearance in millimetres. For that
40 mm band the radius is 21.0 mm, so a 20 mm cup fits and a 25 mm cup does not.

**Sufficient for alignment.** Yes while the piece is elongated, and not otherwise. PCA axis error against the true
angle, 200 random rotations per row, 1 mm pixels, 10 percent of pixels deleted at random for specular drop-outs
(*measured here*):

| Long/short aspect | Median axis error | p95 | Max |
|---|---|---|---|
| 2.50 | 0.08 deg | 0.24 deg | 0.35 deg |
| 1.60 | 0.10 deg | 0.33 deg | 0.44 deg |
| 1.20 | 0.27 deg | 0.83 deg | 1.50 deg |
| 1.05 | 1.06 deg | 2.81 deg | 4.60 deg |
| 1.00 | 47.3 deg | 84.9 deg | 89.9 deg |

The axis is not gradually worse on a round piece, it is undefined. Measure the aspect distribution before promising a
yaw tolerance, and gate at runtime: if the second PCA eigenvalue is within a few percent of the first, publish "no
axis" rather than a number. The other error term is under-segmentation. Losing a strip of width `d` along one long
edge, which is what a specular blowout or a gripper shadow produces, moves the centroid by exactly `d / 2` and moves
the axis by essentially nothing: on a 200 by 80 mm slab losing 10 percent of its width, the measured centroid shift is
4.3 mm median while axis error stays under 0.25 degrees (*measured here*, 30 rotations per case). Monitor mask width
against the product's known width distribution and that asymmetry gives a live detector for the dominant centroid
error term, with no labels.

**Labelled data.** None: a belt reference image and a threshold. **Latency.** 12.9 ms per frame at 1920 by 1200
for the whole pipeline (difference, threshold, open, close, connected components, contours, moments, rotated
rectangle on two instances), 50 frames, i7-8750H, OpenCV 4.5.4, no GPU (*measured here*), a tenth of the conveyor
note's segmentation budget.

**Wet and reflective.** Failures: highlights read as belt (mask holes), purge fluid and fat smear read as product,
belt seams the static reference does not cover, gripper shadows, and two touching pieces merged into one
component. Dome lighting plus a crossed polarizer and analyzer is the standard suppression
([Advanced Illumination](https://advancedillumination.com/a-practical-guide-to-machine-vision-lighting/)); a Sony
IMX250MZR polarization sensor separates the specular component directly
([Sony](https://www.sony-semicon.com/en/products/is/industry/polarization.html),
[Wen 2021](https://doi.org/10.1109/tip.2021.3104188)). Touching pieces this method cannot fix.

**Licence.** OpenCV is Apache 2.0 from 4.5.0 ([licence](https://opencv.org/license/)). No obligation downstream.

## 2. YOLO detection, axis-aligned box: why a box is not a pose

**Output.** `(class, score, x_min, y_min, x_max, y_max)`. Two corners. No orientation, no shape, no contact point.
The axis-aligned box of an `L` by `W` rectangle rotated by `theta` has sides

```
w(theta) = L |cos theta| + W |sin theta|        A_box = L*W + (L^2 + W^2) * sin(2 theta) / 2
h(theta) = L |sin theta| + W |cos theta|
```

**The box inflates fast, and the excess peaks at 45 degrees whatever the aspect ratio.** For a 200 by 80 mm slab:

| theta | Box, mm | Box area / piece area | Fraction of the box that is belt | Box aspect |
|---|---|---|---|---|
| 0 deg | 200 x 80 | 1.00 | 0.0 % | 2.50 |
| 5 deg | 206 x 97 | 1.25 | 20.1 % | 2.12 |
| 10 deg | 211 x 113 | 1.50 | 33.2 % | 1.86 |
| 20 deg | 215 x 144 | 1.93 | 48.2 % | 1.50 |
| 30 deg | 213 x 169 | 2.26 | 55.7 % | 1.26 |
| 45 deg | 198 x 198 | 2.45 | 59.2 % | 1.00 |

At 10 degrees of rotation a third of the box is already belt, so any heuristic that sets gripper opening from box
width, or assumes the box interior is product, is wrong by that fraction.

**The box carries no axis, and at 45 degrees it carries anti-information.** `w = h` exactly when
`(L - W)(|cos theta| - |sin theta|) = 0`, that is at 45 degrees for every aspect ratio. The box is square there,
so its longer side is a coin flip and the inferred yaw jumps 90 degrees on sensor noise. Between 30 and 60 degrees
the box aspect stays under 1.26 for a piece whose true aspect is 2.5, so even the crude "long side of the box is
the long axis" rule has no margin. Nothing recovers yaw from two corners.

**The box centre equals the true centroid only for a piece with 180-degree rotational symmetry.** The common
intuition is wrong in both directions here. For a perfect rectangle the two coincide exactly at every angle, so a
rectangle is the wrong test case. For a real piece the offset is non-zero and is a function of `theta` whose shape
depends on the piece, so no fixed calibration offset removes it (*measured here*):

| Shape | 0 deg | 15 deg | 30 deg | 45 deg | Box centre on the piece? |
|---|---|---|---|---|---|
| Tapered slab, 200 x 80 mm, narrowing to 27 mm | 16.7 mm | 15.3 mm | 8.4 mm | 3.3 mm | yes |
| Curved cut, 126 deg arc, 40 mm band | 4.7 mm | 15.0 mm | 22.6 mm | 26.6 mm | no, at any angle |

The tapered case shrinks with rotation, the curved case grows with it. To know the offset you need the shape, and
if you have the shape you no longer need the box. On the curved piece the box centre is never on the product, so a
suction cup commanded there lands on the belt.

**Sufficient for grasping.** No, except on a piece that is convex, symmetric under 180 degrees, and much larger than
the pad. **Sufficient for alignment.** No, at any angle. **What the box is genuinely good for.** Triggering, counting,
classifying (product versus foreign object versus glove), rejecting doubles by area, and cropping a region of interest
so an expensive estimator runs on 200 by 200 pixels instead of 2 megapixels. Keep YOLO for that and put the pose
estimator behind it. The recommendation is not "drop YOLO", it is "stop asking the box for a pose". **Labelled data**:
boxes are the cheapest label, 2 to 5 s per instance. **Latency**: Ultralytics publishes detect numbers on an Amazon
EC2 P4d instance with T4 TensorRT export ([detect docs](https://docs.ultralytics.com/tasks/detect/)). **Wet and
reflective**: a detector trained on plant frames handles glare better than a threshold, and fails more quietly, since
a plausible box still appears around a merged pair or a puddle. **Licence**: AGPL-3.0 with a paid enterprise option
([Ultralytics licensing](https://www.ultralytics.com/license)); AGPL inside a customer's cell is a legal question, so
raise it before the pilot.

## 3. YOLO-OBB and YOLO-seg

**YOLO-OBB.** Output `(cx, cy, w, h, angle)`: centre, extent and yaw in one head at detector speed, the minimum
viable answer for this task. Ultralytics stores the angle in radians in `[-pi/4, 3pi/4)` and trains the released
OBB models on DOTAv1 at 1024 px ([OBB docs](https://docs.ultralytics.com/tasks/obb)). YOLO26-obb, DOTAv1, speed
averaged over val images on an Amazon EC2 P4d instance:

| Model | mAP50-95 | mAP50 | CPU ONNX | T4 TensorRT10 | Params |
|---|---|---|---|---|---|
| YOLO26n-obb | 52.4 | 78.9 | 97.7 ± 0.9 ms | 2.8 ± 0.0 ms | 2.4 M |
| YOLO26x-obb | 56.7 | 81.7 | 1485.7 ± 11.5 ms | 30.5 ± 0.9 ms | 57.6 M |

Two cautions. The angle range wraps, so the loss sees a discontinuity at the seam and the model confuses 0 and 179
degrees near it unless the training yaw distribution is uniform. And the rectangle centre is a box centre again, so
the tapered-slab offset returns at 16.7 mm, constant across rotation (*measured here*). An OBB gives the axis; take
the point from a mask or a keypoint.

**YOLO-seg.** Output is a per-instance mask, so everything in section 1 applies with a learned segmenter in place
of the threshold. This is the combination that fits: learned mask, classical pose from the mask. YOLO26-seg, COCO
val2017, same measurement setup ([segment docs](https://docs.ultralytics.com/tasks/segment)):

| Model | mAP-box | mAP-mask | CPU ONNX | T4 TensorRT10 | Params |
|---|---|---|---|---|---|
| YOLO26n-seg | 39.6 | 33.9 | 53.3 ± 0.5 ms | 2.1 ± 0.0 ms | 2.7 M |
| YOLO26x-seg | 56.5 | 47.0 | 787.0 ± 6.8 ms | 16.4 ± 0.1 ms | 62.8 M |

COCO mAP-mask says nothing about millimetres of centroid error on one product class: it picks a model size, it is
not an acceptance criterion. OBB polygons and masks cost 10 to 30 s per frame with a promptable model in the loop
([labelling recipe](computer-vision-fundamentals.md#training-a-small-segmenter-from-200-labelled-images)) against
2 to 5 s for a box, so on a single-product line the labelling is one afternoon.

## 4. Instance segmentation: Mask2Former, SAM 2, SAM-assisted labelling

**Mask2Former.** One architecture for semantic, instance and panoptic: 57.8 PQ on COCO panoptic, 50.1 AP on COCO
instance, 57.7 mIoU on ADE20K ([arXiv 2112.01527](https://arxiv.org/abs/2112.01527)), MIT code with
backbone-specific terms ([repo](https://github.com/facebookresearch/Mask2Former)). Worth it when fat versus lean
versus belt and per-piece instances are both needed from one network. Heavier than YOLO-seg, no published edge
latency (unverified).

**SAM 2 with a box or point prompt.** Promptable, so no training on the product, with a memory that propagates
masks across frames. Apache 2.0. Tiny 38.9 M to Large 224.4 M parameters; 91 FPS tiny and 39.5 FPS large on an
A100, roughly 1 FPS in PyTorch on a Jetson without TensorRT ([repo](https://github.com/facebookresearch/sam2),
[arXiv 2408.00714](https://arxiv.org/abs/2408.00714)). The distilled variants are the deployable ones: NanoSAM at
8.1 ms full pipeline on an AGX Orin ([NanoSAM](https://github.com/NVIDIA-AI-IOT/nanosam)), MobileSAM at 39 ms on
the same part ([MobileSAM](https://github.com/ChaoningZhang/MobileSAM)). SAM 2 does not detect; it always sits
behind a detector or a click.

**SAM-assisted labelling to train a small fast model.** The pattern that wins on a line: prompt SAM interactively in
CVAT (MIT, ships SAM as a serverless function) or Label Studio (Apache 2.0), correct the edges, export COCO, fine-tune
YOLO-seg or Mask2Former, deploy the small model. You pay the foundation model once at labelling time and never at line
rate; the full recipe is in
[computer-vision-fundamentals](computer-vision-fundamentals.md#practical-recipe-labelling-to-deployment-for-a-new-object-class).

**Sufficient for grasping and alignment.** Yes for both, through section 1's estimators; the mask serves both
required outputs from one inference, which is why it is the default. **Wet and reflective.** A learned segmenter
recovers pixels a threshold loses to glare, because glare is labelled as product in training, but it fails
differently: on a condition absent from training it degrades with no visible signal. Report metrics per condition
and keep a threshold foreground count as the per-shift monitor
([drift monitor](computer-vision-fundamentals.md#domain-shift-under-plant-lighting)).

## 5. Keypoint regression: semantic and relational keypoints

**kPAM.** Detect a fixed set of semantic 3D keypoints per category, then express the task as costs and constraints
on those points instead of on a pose ([Manuelli 2019](https://arxiv.org/abs/1903.06684)). Measured: shoes onto a
rack, 20 held-out shoes, 100 trials, 98 percent placed, heel error 1.09 ± 1.29 cm and toe error 4.34 ± 3.05 cm;
mugs upright on a shelf, 40 mugs, 80 trials from upright, 100 percent placed with 97.5 percent inside 3 cm.
Training cost: 117 scenes labelled on 3D reconstructions, "less than four hours of manual annotation time",
yielding "over 100,000 labeled images", because a label placed once on a reconstruction projects into every view.

**What a keypoint buys over a mask.** A mask is geometry with no semantics. Where the cut is referenced to an
anatomical landmark rather than the centre of area, the landmark is what the fixture needs: the tip, the heel, the
fat edge. A principal axis through a curved or tapered piece can be the wrong line even when estimated perfectly.
Keypoints also survive deformation: three labelled points on a folded fillet are still the same three points,
whereas the mask's principal axis moves with the fold.

**The limit, stated by the authors.** kPAM's action is a rigid transform fitted to the keypoints, and the paper
says plainly that "this abstraction does not work for deformable objects". Keypoints are the right *observation*
for a deformable piece and the wrong *action parametrisation*. Use them for the alignment axis (a line through two
keypoints) and the grasp point (one keypoint plus a clearance check), and keep the action as
pick-pixel-plus-place-pixel, which is what works on soft goods
([deformable note](deformable-object-manipulation.md#learning-approaches)).

**ReKep.** Keypoints proposed by clustering DINOv2 features inside SAM masks, constraints written as Python
functions over them and solved hierarchically; the first solve is dual annealing plus SLSQP at around 1 s,
subsequent local solves near 10 Hz ([arXiv 2409.01652](https://arxiv.org/abs/2409.01652)). Real-robot success with
automatically generated constraints was 68.6 percent against 44.3 percent for the VoxPoser baseline, 10 trials per
task on a Franka. It buys constraints expressed *relationally* ("this edge of the piece parallel to that edge of
the fixture") rather than as an absolute pose, so the alignment target survives a piece that is not the shape you
assumed. It costs a VLM in the loop, 10 Hz, and no per-instance repeatability. Not a line-rate estimator in 2026;
a good source of the constraint formulation to hand-write.

## 6. Learned grasp pose: Dex-Net, GraspNet-1Billion, Contact-GraspNet, AnyGrasp

| Method | Published result, with conditions | Licence |
|---|---|---|
| Dex-Net 3.0 (suction), 4.0 (ambidextrous) | 3.0: 350 physical trials on an ABB YuMi, 98 % prismatic and cylindrical, 82 % typical, 58 % adversarial ([arXiv:1709.06670](https://arxiv.org/abs/1709.06670)). 4.0: 95 % reliability at 300 mean picks per hour on heaps of up to 50 novel objects, trained on over 5 M grasps over 1,664 objects ([Science Robotics 2019](https://doi.org/10.1126/scirobotics.aau4984)) | Berkeley, check repo |
| GraspNet-1Billion | 87,040 RGB-D images, over 370 M annotated grasp poses, analytic evaluator ([arXiv 1912.13470](https://arxiv.org/abs/1912.13470)) | non-commercial only ([repo](https://github.com/graspnet/graspnet-baseline)) |
| AnyGrasp | successor to the above | licensed SDK, licence key required ([sdk](https://github.com/graspnet/anygrasp_sdk)) |
| Contact-GraspNet | 6-DoF grasps from a depth cloud by treating points as contacts, pose reduced to 4 DoF; 17 M simulated grasps, over 90 % success on unseen objects in structured clutter ([arXiv 2103.14127](https://arxiv.org/abs/2103.14127)) | `License.pdf` in the repo, no SPDX id; read before a commercial pilot (unverified) |

**Does any of this suit a slab on a belt?** No, for a structural reason rather than a tuning one. All were built
for the bin, where the hard part is choosing *which* object and *from which direction* out of a heap where most
approaches are blocked. On a belt there is one object, it is flat, it is isolated, and the approach is straight
down: the 4-to-6 DoF search these networks perform is over a space the application has already collapsed to two
numbers. None outputs the alignment axis at all, because a grasp pose about a suction axis is symmetric under
rotation about that axis, which is exactly the freedom the cutter needs pinned down. They also assume a rigid
object, so the quality score has no term for tearing or folding; the quantitative grasp scoring for deformables is
DefGraspSim and DefGraspNets ([deformable note](deformable-object-manipulation.md#grasp-planning-for-deformables)),
and those are offline FEM tools. Do not put a bin-picking grasp network on this belt; keep them for the upstream
unload step if product ever arrives in a tote instead of a single layer.

## 7. Model-based 6D pose: FoundationPose, MegaPose

**Output.** `T_cam_obj` in SE(3): the rigid transform mapping a canonical object model into the scene.
FoundationPose estimation runs at about 0.5 FPS at 720p on a Jetson AGX Orin via Isaac ROS and roughly 1.3 s per
object on an RTX 3090, tracking near 32 Hz once initialised ([arXiv 2312.08344](https://arxiv.org/abs/2312.08344),
[Isaac ROS](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_pose_estimation/blob/release-4.6/README.md)), under the
NVIDIA Source Code License, non-commercial. MegaPose is render-and-compare, seconds per object, Apache 2.0
([arXiv 2212.06870](https://arxiv.org/abs/2212.06870)).

**Why it fails here, specifically.** The output is defined only if a canonical model exists. Both methods take a
CAD mesh or reference views that reconstruct one, and both assume the observed object is that model moved rigidly.
A meat piece has neither property: there is no mesh for "this pork loin end", there is a distribution of shapes,
and every individual differs from every other by a non-rigid deformation, so `T_cam_obj` is not merely hard to
estimate, it does not exist. The metrics make this concrete: BOP's VSD, MSSD and MSPD are all distances between
model points transformed by the estimated pose and the same points transformed by the true pose
([BOP](https://bop.felk.cvut.cz/challenges/)); with no model there are no model points and the error is undefined.
Even given a template, a slab is near-symmetric under 180 degrees about its normal and near-continuous about its
long axis, so the rotation is ill-posed in exactly the components the cutter cares about. And the piece deforms
between shutter and grasp, so a pose valid at the image is not valid at contact.

**The honest alternative in this family** is non-rigid registration of a template to the observed cloud, Coherent
Point Drift ([Myronenko and Song 2010](https://doi.org/10.1109/tpami.2010.46)), which transfers a cut line from an
annotated template to this piece: a per-piece correspondence, not a pose, and the right tool if the customer's cut
is defined on an anatomical template. Minutes, not milliseconds, in its plain form (real-time is unverified).

## 8. Depth-driven: plane fit, height map, point cloud PCA

**Output.** Fit the belt plane by RANSAC: `pcd.segment_plane(distance_threshold, ransac_n, num_iterations)` returns
a 4-vector plane model and the inlier indices
([Open3D](https://www.open3d.org/docs/release/python_api/open3d.geometry.PointCloud.html)); the outliers above it
are product. Then a height map, and per instance an oriented box by PCA of the convex hull
(`get_oriented_bounding_box`) or the minimal-volume box (`get_minimal_oriented_bounding_box`).

**What depth adds beyond the mask.** Four things the mask cannot give.

1. **Segmentation colour cannot do.** Height above the belt separates product from stain, purge fluid and belt
   print with no appearance model, and splits two touching pieces whose colours are identical.
2. **Grasp height and surface normal.** A cup needs the z of the top surface at the grasp point, not the belt's z,
   and a cup on a 20-degree slope leaks; a local plane fit gives the tilt to compensate or the reason to reject.
3. **Thickness, the cutter's real input.** Weight-and-shape portioning works from a height map; JBT's DSI waterjet
   cells scan one and portion from it ([DSI](https://jbtmarel.com/en/products/dsi-waterjet-portioning-systems/)).
4. **The parallax correction on the mask itself.** A single overhead camera calibrated to the belt plane
   back-projects the mask at the wrong scale for a thick piece: the top surface is closer than the belt, so the
   mask is magnified by roughly `f / (f - t)` in the pinhole model, `t` being thickness relative to working
   distance. At 1.0 m working distance and a 50 mm piece that is a 5 percent scale error, about 5 mm on a 100 mm
   half-length. This is the largest systematic error in a mask-only pipeline and depth removes it.

**Sufficient for grasping and alignment.** Yes for both, and the only candidate that gets item 4 right. Point-cloud
PCA has the same aspect-ratio degeneracy as the 2D version plus a 180-degree ambiguity that a side classifier must
break ([meat note](meat-cutting-automation.md#perception-on-meat)). **Latency and hardware.** The sensor is the cost,
not the arithmetic. Photoneo MotionCam-3D M: 10 ms acquisition, up to 20 fps, under 0.5 mm accuracy in camera mode
([spec](https://www.photoneo.com/products/motioncam-3d-m/)). Zivid 2+ M130: 320 um at 1.3 m, 100 to 500 ms capture,
and shiny scenes "typically require 3 HDR acquisitions" ([Zivid guide](https://support.zivid.com/en/latest/camera/academy/camera/capturing-high-quality-point-clouds/dealing-with-highlights-and-shiny-objects.html)).
Laser line triangulation builds the map from belt motion and is what the portioner vendors ship; the sensor table with
washdown ratings is in the [meat note](meat-cutting-automation.md#perception-on-meat).

**Wet and reflective.** Depth is where wet meat hurts most: specular returns leave holes and interreflection
produces points on no surface, both worse on a wet belt than on the product. Blue-laser triangulation and
multi-exposure HDR are the vendor answers. Three HDR acquisitions is a different chain from a 10 ms MotionCam
frame, though camera time is paid in belt distance rather than cycle time as long as the belt between camera and
pick zone is long enough
([latency chain](conveyor-tracking-and-visual-servoing.md#sensing-chain-and-latency-budget)). **Licence.** Open3D
is MIT ([repo](https://github.com/isl-org/Open3D)); PCL is BSD-3-Clause.

## Candidate comparison

| Candidate | Output | Grasp point | Alignment axis | Labels | Latency, hardware named | Wet surface | Licence |
|---|---|---|---|---|---|---|---|
| Classical mask pipeline | mask, centroid, axis, rect, inscribed circle | yes | yes if aspect > 1.2 | none | 12.9 ms at 1920x1200, i7-8750H CPU (*measured here*) | holes from glare, merges on touch | Apache 2.0 |
| YOLO detect | axis-aligned box | no | no | boxes, 2-5 s each | few ms, T4 TensorRT | box survives glare, silently wrong | AGPL-3.0 or paid |
| YOLO-OBB | rotated rect | box centre, not centroid | yes | polygons, 10-30 s/frame | 2.8 ms (n) to 30.5 ms (x), T4 TensorRT10, 1024 px | as above | AGPL-3.0 or paid |
| YOLO-seg | instance mask | yes | yes | masks, 10-30 s/frame | 2.1 ms (n) to 16.4 ms (x), T4 TensorRT10, 640 px | degrades silently off-distribution | AGPL-3.0 or paid |
| Mask2Former | semantic + instance masks | yes | yes | masks | no edge number published (unverified) | as YOLO-seg | MIT, backbone terms |
| SAM 2, prompted | mask from box or point | yes | yes | none, needs a prompt | 91 FPS tiny on A100; ~1 FPS PyTorch on Jetson; NanoSAM 8.1 ms AGX Orin | good zero-shot, unmeasured on meat | Apache 2.0 |
| kPAM keypoints | k semantic 3D points | yes, point + clearance | yes, line through two points | ~117 scenes, under 4 h annotation | detector alone not published (unverified) | inherits the segmenter's | MIT-family, verify |
| ReKep | keypoints + constraints | yes | yes, relationally | none | ~1 s first solve, ~10 Hz after, Franka + RTX | inherits SAM's | check repo terms (unverified) |
| Dex-Net / GraspNet / Contact-GraspNet | 6-DoF grasp candidates | yes | no, symmetric about the grasp axis | pretrained | Contact-GraspNet needs 8 GB VRAM; time not published (unverified) | depth holes drop candidates | non-commercial or licensed SDK |
| FoundationPose / MegaPose | SE(3) pose | needs a model | needs a model | CAD or reference views | 0.5 FPS AGX Orin, ~1.3 s RTX 3090 | undefined without a model | NVIDIA non-commercial / Apache 2.0 |
| Depth plane fit + cloud PCA | plane, height map, 3D OBB | yes, with true z and normal | yes, same aspect limit | none | 10 ms MotionCam to 500 ms Zivid HDR capture | holes and interreflection; blue laser or HDR | Open3D MIT, PCL BSD-3 |

## Selection

Read down the column that matches the cell, not across.

| Requirement | Classical only | Learned mask + classical pose | Add depth | Add keypoints |
|---|---|---|---|---|
| Placement accuracy needed | 10 mm and 5 deg or looser | 5 mm and 3 deg | under 5 mm, or thickness matters | landmark-referenced, not centroid-referenced |
| Cycle time | any | any, with a T4-class GPU | camera capture must fit the belt distance | not at line rate today |
| Piece geometry varies | one shape family, aspect > 1.2 | shape varies, still separable by appearance | pieces touch, stack, or vary in thickness | anatomy matters to the cut |
| Labels exist | none needed | 200 to 300 frames | none extra | 100+ scenes, 3D-annotated |
| Depth available | not required | not required | required | helps, not required |

Overrides. If the product's aspect distribution has meaningful mass below 1.2, no axis-from-shape method meets a
yaw spec and the answer is datum-based alignment
([push to a hard stop](deformable-object-manipulation.md#placement-and-alignment-into-a-fixture)) with vision only
verifying. If pieces touch on the belt, fix the infeed spacing first: a splitting segmenter is a worse solution
than a spreader. If AGPL is blocked, Mask2Former under MIT replaces YOLO-seg and nothing else changes.

**Recommended default: learned instance segmentation, classical pose from the mask, depth for height and normal.**
YOLO detect or YOLO-seg for the trigger and the region of interest; a fine-tuned YOLO-seg or Mask2Former mask per
piece; then from the mask the image-moment centroid, the PCA principal axis with an eigenvalue-ratio gate, the
minimum-area rectangle for the extent, and the distance-transform maximum for the contact point with its clearance
radius. Depth from a belt-plane RANSAC fit supplies the grasp z, the surface normal, and the parallax correction
on the mask scale. Labels come from a SAM-assisted pass over 200 to 300 stratified frames. Why this: it emits both
required outputs from one inference, the pose step is deterministic and free, the learned part is the one thing
that genuinely needs learning (which pixels are product under plant lighting), and every number it produces is
measurable against the ground truth defined below.

**Fallback: the classical pipeline alone**, with a fixed belt reference and dome plus polarized lighting. It is
the day-one baseline and stays in the deployed system as the monitor, comparing its foreground count and mask
width against the learned segmenter's every frame. If the model is unavailable, the licence blocked, or there is
no GPU in the cell, it meets a 10 mm and 5 degree spec on elongated product with no labels at all.

**What evidence would change the recommendation.**

- **Aspect ratio below 1.2 for more than about 10 percent of pieces.** The axis cannot then come from shape: move
  to keypoints or a landmark model, or move the alignment burden to a mechanical datum.
- **Centroid error dominated by parallax rather than segmentation.** Depth becomes required, not optional, and the
  sensor budget changes. **Touching pieces above a few percent of arrivals.** The infeed changes, or the mask model
  is trained on touching pairs, and count error replaces centroid error as the acceptance gate.
- **A cut defined anatomically rather than geometrically.** If the spec is "cut 30 mm behind the fat edge", the
  centroid and the principal axis are the wrong quantities and kPAM-style keypoints become the primary output.
- **A measured SAM-class latency on the deployment device that fits the budget.** The labelling step shrinks,
  because a prompted model can run online. **Product arriving in totes rather than a single layer.** The
  bin-picking grasp networks come back into scope for the unload step.

## How to settle this by measurement

Opinions are cheap and the head-to-head is not. Run it before the pilot, in sim, where truth is known exactly.

**The rig.** A simulated overhead camera above a simulated belt, the deformable slab models from the
[sim-first workflow](sim-first-workflow.md) and the [deformable note](deformable-object-manipulation.md), rendering
RGB and depth at the deployment camera's intrinsics and mounting height. Randomise per frame: shape from the
measured size table, yaw uniform in [0, 180), lateral offset, belt speed, lighting colour temperature and
intensity inside the measured plant range, wet-specular strength, and a fraction of frames with two pieces
touching. Fix and log the seed; about 500 frames, stratified so every condition has at least 50.

**Ground truth, defined once for every candidate.** The step that decides whether the comparison means anything.
Project the piece's surface mesh onto the belt plane and take: **true centroid** `p*`, the area centroid of that
polygon in belt-frame millimetres; **true axis** `theta*`, its principal axis from the eigenvector of the
second-moment matrix with the larger eigenvalue, modulo 180 degrees; **true aspect** `a*`, the square root of the
eigenvalue ratio, logged per frame so results can be sliced by it; **true side-up**, the label of the surface
facing the camera. Where a candidate's native output is not a centroid and an axis (a box, a grasp pose), the
adapter that converts it is part of that candidate and is written down. No candidate gets a bespoke ground truth.

**Metrics.**

- **Centroid error** `e_c = || p_hat - p* ||_2` in millimetres, plus its components `e_along` along the belt and
  `e_across` across it, reported separately. Median, p95, max, with `n`. The split matters because the encoder
  absorbs part of `e_along` and none of `e_across`
  ([conveyor note](conveyor-tracking-and-visual-servoing.md#tracking)).
- **Axis error** `e_theta = min(d, 180 - d)` where `d = |theta_hat - theta*| mod 180`, in degrees. Median, p95,
  and the fraction above the fixture's guide angle. Undirected, so a 180-degree flip scores zero by construction;
  report the **flip rate** (wrong side-up label) separately, because a flip and an angle error recover differently.
- **Grasp validity**: fraction of predicted grasp points lying inside the true mask. **Grasp clearance** `r_hat`:
  the true distance transform at the predicted point in millimetres, with the fraction below the pad radius, since
  a point inside the mask but 3 mm from the edge is not a grasp.
- **Instance count error** per frame, plus the **merge rate** (two pieces reported as one), the **split rate**,
  and the **no-pose rate** (candidate emits nothing, or a below-threshold result, inside the belt distance budget).
- **Latency**: p50 and p99 wall clock from frame arrival to pose published, batch 1, on the named device, in the
  named export format (PyTorch, ONNX, TensorRT FP16). Latency on a laptop is not evidence about a Jetson.

Report every metric sliced by true aspect ratio and by wetness; the aggregate hides the case that decides the
design. **Protocol and decision rule.** Follow [experiment-protocol](../../sops/experiment-protocol.md): the hypothesis
and the acceptance thresholds go in `experiments/` before the first run. All candidates see identical frames, so
compare them paired (Wilcoxon signed-rank on per-frame errors) rather than by independent means, and put a
bootstrap confidence interval on each p95 instead of quoting the point estimate. A candidate wins only if it beats
the classical baseline on `e_across` p95 and `e_theta` p95 *and* fits the latency budget on the deployment device.

**The limitation to state out loud.** A simulated wet meat surface is not a wet meat surface. The sim head-to-head
ranks sensitivity to geometry, occlusion and rotation, which is what sections 1 to 3 are about, and says close to
nothing about behaviour under real specular highlights. Follow it with a real held-out set: about 200 plant
frames, two annotators drawing the mask independently, the inter-annotator centroid and axis disagreement reported
as the noise floor. A candidate whose error is below that floor is not better than the others below it, it is
unmeasurable, and the argument moves to latency, licence and maintainability.

## Practical gotchas

- The minimum-area rectangle's centre is not the area centroid: use `moments` for the point. On the tapered slab
  above the difference is 16.7 mm, three times the placement budget. The area centroid is not always on the piece
  either, so use the distance-transform maximum for a suction or single-pad contact and take the clearance radius
  from the same call.
- PCA on a near-square mask returns a number, not an axis. Gate on the eigenvalue ratio and publish "no axis"
  rather than a confident wrong yaw. Under-segmentation along one edge moves the centroid by half the lost width
  and leaves the axis untouched, so an axis that looks fine is no evidence the centroid is fine.
- A mask-only pipeline back-projected onto the belt plane over-estimates the piece by roughly
  `thickness / working distance`. Measure it once on a block of known size before blaming the model.
- COCO mAP and DOTA mAP do not convert to millimetres; keep them out of the acceptance criteria. Ultralytics
  AGPL-3.0 reaches the customer's deployed system; settle it before the pilot. And every pose needs the encoder
  count at the shutter attached, or it is already wrong by the belt distance travelled during inference.

## What a forward-deployed engineer must be able to do

- Derive on a whiteboard why an axis-aligned box cannot carry yaw, and quote the 45-degree square-box result and
  the belt-fraction number for the customer's own product dimensions.
- Write the mask-to-pose estimator from scratch in twenty lines of OpenCV, say what each of centroid, axis,
  rectangle and inscribed circle is for, and state the aspect ratio below which the yaw spec is unachievable from
  shape alone.
- Name, for any candidate a vendor proposes, its output, its labelled-data cost, its latency on the device that
  will run it, and its licence, without looking them up. Set up the paired head-to-head above, define the ground
  truth once for all candidates, and report p95 with trial counts rather than a mean.

## Open questions

- What is the real aspect ratio distribution of the customer's product? Everything above turns on it and no paper
  can answer it. What is the inter-annotator centroid and axis disagreement on wet meat? That is the noise floor,
  and no published figure was found (unverified).
- Does a polarization camera reduce mask edge error enough to change the centroid error materially, or only the
  visual quality? Measurable with the same rig, one extra condition.
- Is there a real-time non-rigid registration that transfers an anatomical cut line at line rate, and do the
  distilled SAM variants hold their zero-shot quality on wet specular tissue, where their training distribution is
  thin? Nothing published found for either (unverified).

## Related entries

[meat-cutting-automation](meat-cutting-automation.md) · [conveyor-tracking-and-visual-servoing](conveyor-tracking-and-visual-servoing.md) · [deformable-object-manipulation](deformable-object-manipulation.md) ·
[computer-vision-fundamentals](computer-vision-fundamentals.md) · [perception-foundation-models](perception-foundation-models.md) · [perception-3d-sensing](perception-3d-sensing.md) ·
[policy-evaluation](policy-evaluation.md) · `snippets/pose_from_mask.py`

## Sources

Every claim above carries its source inline. The primary references, collected:
[OpenCV imgproc shape](https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html), [licence](https://opencv.org/license/) ·
Ultralytics [OBB](https://docs.ultralytics.com/tasks/obb), [segment](https://docs.ultralytics.com/tasks/segment), [detect](https://docs.ultralytics.com/tasks/detect), [licensing](https://www.ultralytics.com/license) ·
Mask2Former [arXiv 2112.01527](https://arxiv.org/abs/2112.01527), [repo](https://github.com/facebookresearch/Mask2Former) ·
SAM 2 [arXiv 2408.00714](https://arxiv.org/abs/2408.00714), [repo](https://github.com/facebookresearch/sam2), [NanoSAM](https://github.com/NVIDIA-AI-IOT/nanosam), [MobileSAM](https://github.com/ChaoningZhang/MobileSAM) ·
kPAM [arXiv:1903.06684](https://arxiv.org/abs/1903.06684) · ReKep [arXiv:2409.01652](https://arxiv.org/abs/2409.01652) ·
Dex-Net [3.0](https://arxiv.org/abs/1709.06670) and [4.0](https://doi.org/10.1126/scirobotics.aau4984) ·
GraspNet-1Billion [paper](https://arxiv.org/abs/1912.13470), [repo](https://github.com/graspnet/graspnet-baseline), [AnyGrasp SDK](https://github.com/graspnet/anygrasp_sdk) ·
Contact-GraspNet [paper](https://arxiv.org/abs/2103.14127), [repo](https://github.com/NVlabs/contact_graspnet) ·
FoundationPose [paper](https://arxiv.org/abs/2312.08344), [repo](https://github.com/NVlabs/FoundationPose), [Isaac ROS node](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_pose_estimation/blob/release-4.6/README.md) ·
MegaPose [arXiv:2212.06870](https://arxiv.org/abs/2212.06870) · [BOP metrics](https://bop.felk.cvut.cz/challenges/) ·
Coherent Point Drift [Myronenko and Song 2010](https://doi.org/10.1109/tpami.2010.46) ·
Open3D [API](https://www.open3d.org/docs/release/python_api/open3d.geometry.PointCloud.html), [repo](https://github.com/isl-org/Open3D) ·
[Photoneo MotionCam-3D M](https://www.photoneo.com/products/motioncam-3d-m/) · [Zivid highlights guide](https://support.zivid.com/en/latest/camera/academy/camera/capturing-high-quality-point-clouds/dealing-with-highlights-and-shiny-objects.html) ·
[Sony polarization sensors](https://www.sony-semicon.com/en/products/is/industry/polarization.html) · [Wen et al. 2021](https://doi.org/10.1109/tip.2021.3104188) ·
[Advanced Illumination lighting guide](https://advancedillumination.com/a-practical-guide-to-machine-vision-lighting/) · [JBT DSI waterjet](https://jbtmarel.com/en/products/dsi-waterjet-portioning-systems/).

Measurements marked *measured here*: `snippets/pose_from_mask.py`, OpenCV 4.5.4, Intel i7-8750H, 2026-09-08,
`python3 -m pytest snippets/pose_from_mask.py` (5 passed).
