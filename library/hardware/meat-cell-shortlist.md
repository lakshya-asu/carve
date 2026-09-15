---
title: Meat cell hardware shortlist (intercept-and-align)
date: 2026-09-06
tags: [hardware, meat-cell, washdown, gripper, 3d-camera, encoder, safety, compute, shortlist]
status: draft
source: library notes and vendor pages linked inline; rows without a fetched page are marked unverified
---

# Meat cell hardware shortlist

A shortlist, not a bill of materials. Every row either links a library note that quotes the
vendor page, or the vendor page itself; rows where no page was fetched say so. The filter that
removes most candidates is washdown: IP69K means 80 to 100 bar water at 80 C from 10 to 15 cm
([IP code](https://en.wikipedia.org/wiki/IP_code)), and "hygienic robot" is a vendor claim
because no robot, gripper or camera housing is on the EHEDG certified list
([meat note, hygiene](../topics/meat-cutting-automation.md)). Anything in the wet zone that
is not IP69K needs a cover or an enclosure, and the plant's QA has the final word.

The open questions at the end decide which rows survive. Read them first if you are talking to
the customer this week.

## Arms

The task needs a lane offset, a yaw and a side flip, so a 4-axis delta covers pick-on-the-fly
placement if the piece never needs to be tilted or flipped; a 6-axis arm is needed the moment
the fat cap or cut face has to be turned. Vendor pages checked Sep 2026 in the meat note.

| Arm | Protection | Payload / reach | Why it is on the list | Concern | Source |
|---|---|---|---|---|---|
| FANUC LR Mate 200iD/7WP (6-axis) | IP67, IP69K optional | 7 kg, 717 mm | Smallest washdown-option 6-axis; FANUC iRPickTool line tracking | Food grease not stated | [meat note table](../topics/meat-cutting-automation.md), [FANUC](https://www.fanucamerica.com/products/robots/series/lr-mate/lr-mate-200id-7wp) |
| KUKA KR AGILUS HM (6-axis) | IP65 / IP67 | Not fetched (unverified) | Food-compatible lubricants, stainless parts, KUKA.ConveyorTech | Not IP69K; needs a cover in the wet zone | [KUKA](https://www.kuka.com/en-us/products/robotics-systems/industrial-robots/kr-agilus) |
| Stäubli TX2 HE (6-axis), TS2-60 HE (SCARA) | In use in JBT Marel's washdown harvester | Not fetched (unverified; Stäubli page returned 403 on 2026-09-06) | The only arm family with a public reference in a meat cell at 240 picks per minute | Specs and ROS path unverified | [JBT Marel harvester](https://jbtmarel.com/en/products/dsi-dual-robotic-harvester-automated-meat-processing/) |
| FANUC DR-3iB/6 STAINLESS (delta) | IP69K | 6 kg, 1200 mm | Stainless, NSF H1, true IP69K; right if the piece needs no tilt | 4 axes: no side flip | [FANUC](https://www.fanucamerica.com/products/robot/dr-3ib-6-stainless) |
| KUKA KR DELTA HM | IP67 body, IP69K on axis 4 only | 6 kg | Stainless, NSF H1, LFGB and FDA | "IP69K on axis 4 only is not IP69K" (meat note gotcha) | [KUKA](https://www.kuka.com/en-us/products/robotics-systems/industrial-robots/kr-delta) |
| ABB IRB 360 stainless (delta) | Unverified | Unverified | ABB publishes the only conveyor-tracking accuracy figures (2 mm at 150 mm/s) | Page not fetched | [ABB conveyor tracking manual](https://search.abb.com/library/Download.aspx?DocumentID=3HAC050991-001&LanguageCode=en&DocumentPartId=&Action=Launch) |
| Universal Robots e-Series with a washdown cover | IP54 base (unverified) | UR7e 7.5 kg, 850 mm | Development and office arm: vendor ROS 2 driver, RTDE 500 Hz, `track_conveyor_linear`, the arm the sim baseline models | Not a plant-floor arm without a cover; cover vendor unverified | [robot arms note](robot-arms.md), [UR conveyor tracking](https://www.universal-robots.com/articles/ur/programming/new-conveyor-tracking-guide-cb3-38-and-e-series-52/) |

Recommendation for the first conversation: ask which controller family the integrator already
runs (ABB, FANUC, KUKA) and use its conveyor tracking; the meat note's rule is that vendor
tracking has been tuned on more belts than we will ever see. The UR stays the office arm.

## Grippers for wet soft slabs

The decision table in [compliant mechanisms](../topics/compliant-mechanisms-and-actuation.md)
says: wet surface, encompassing soft fingers or a support plate; slippery and over 1 kg, a
support plate plus a light pinch; must not mark, smooth silicone or non-contact. Whether the
customer accepts any surface marking is the question that picks the family.

| Gripper | Type | Washdown and food status | Why | Concern | Source |
|---|---|---|---|---|---|
| Schmalz mGrip (ex Soft Robotics) | Pneumatic soft fingers | IP69K, FDA-compliant POM, silicone, stainless; up to 10 kg, 120 picks/min; listed for "meat, fish and dough pieces" | The only soft finger gripper with an IP69K claim and a meat listing | Pneumatic (valve latency, oil-free air); no position or force feedback for the policy | [meat note](../topics/meat-cutting-automation.md), [Schmalz mGrip](https://www.schmalz.com/en-us/products/automation-743270/other-gripping-technologies-746237/finger-grippers-312388) |
| Vacuum: Piab FCM bellows or Schmalz SI-MD cups with an ejector | Suction | Food-contact silicone; SI-MD metal-detectable | Proven at 240 picks/min on wet flesh in the JBT harvester | Leaks at cut faces and bone; size the pump for flow; ring marks; test on product, not a dry sample | [meat note grasping](../topics/meat-cutting-automation.md), [Piab cups](https://www.piab.com/en-us/suction-cups-and-soft-grippers), [Schmalz food](https://www.schmalz.com/en-us/solutions/industries-and-applications/food) |
| Piab piSOFTGRIP | Vacuum-driven silicone | FDA 21 CFR and EU 1935/2004 | One part, no joints, uses the vacuum line already on the arm | Grip force limited by atmosphere times area; page not fetched in the compliant note | [Piab](https://www.piab.com/en-us/suction-cups-and-soft-grippers/soft-grippers/pisoftgrip-vacuum-driven-soft-gripper-/sg.x) |
| Support plate or scoop plus pinch (custom) | Non-prehensile support | Depends on build; DTI prints food-contact metal-detectable nylon fingers | Removes the tear constraint in transport, only slip remains; the meat note's pusher-paddle idea avoids lifting entirely | Custom build; doubles cycle time if a regrasp is needed | [deformable note, transport](../topics/deformable-object-manipulation.md), [DTI nylon gripper](https://www.dti.dk/services/3d-printed-robotic-gripper-in-nylon-8211-approved-for-food-contact/41428) |
| Zimmer hygienic-design parallel gripper | Servo or pneumatic parallel | FDA materials, NSF H1 grease, IP40 to IP65 | Position feedback for the policy; fits custom wide pads | Not IP69K; needs a cover | [Zimmer](https://www.zimmer-group.com/en/products/components/handling-technology/2-jaw-parallel-grippers/individualizations/hygienic-design) |
| Robotiq 2F-140 with silicone pads | Servo parallel, 140 mm stroke, 10 to 125 N | IP40 | Office and sim gripper only; the stroke matches a 40 to 120 mm slab; object-detected flag for datasets | Not for the wet zone | [grippers note](grippers-and-end-effectors.md) |
| OnRobot Soft Gripper | Electric soft fingers | FDA "for non-fatty food items", EC 1935/2004; 2.2 kg | Electric, dishwasher-safe cups; office trials | The non-fatty scope excludes meat; ask for migration test conditions | [OnRobot](https://onrobot.com/en/products/soft-gripper) |
| Schmalz SNG needle gripper | Needles 0.8 to 2.0 mm | No meat application listed | Only if the customer accepts punctures | Punctures product | [Schmalz needle grippers](https://www.schmalz.com/en-us/products/automation-743270/other-gripping-technologies-746237/needle-grippers-306131) |

Verification rule from the compliant note: 20 picks per product class per candidate, logging
success, drop, tear, mark and alignment residual; choose on the failure modes.

## 3D cameras for wet reflective surfaces

Meat is wet, specular, low-texture and deforms when touched; the sensor comparison is in the
[meat note, perception](../topics/meat-cutting-automation.md) and general depth cameras in
[depth cameras](depth-cameras.md). The camera sits in the wet zone behind a window, so the
housing matters as much as the sensor.

| Camera | Principle | Behaviour on meat | Speed | Washdown | Source |
|---|---|---|---|---|---|
| Photoneo MotionCam-3D M | Parallel structured light for moving scenes | Vendor claims glossy and dark surfaces; no meat data found | 10 ms acquisition, up to 20 fps, under 0.5 mm in camera mode | IP rating not on the fetched page (unverified) | [Photoneo](https://www.photoneo.com/products/motioncam-3d-m/) |
| Zivid 2+ M130 | Structured light, multi-exposure HDR | Shiny scenes "typically require 3 HDR acquisitions"; Reflection Filter; use a dark absorptive background | 100 to 500 ms per capture, which costs 150 mm of belt at 300 mm/s | IP65; needs an enclosure | [Zivid spec](https://www.zivid.com/zivid-2-plus-m130), [shiny objects guide](https://support.zivid.com/en/latest/camera/academy/camera/capturing-high-quality-point-clouds/dealing-with-highlights-and-shiny-objects.html) |
| LMI Gocator 2500 or Keyence LJ-X8000 | Blue laser line triangulation, builds the 3D map from belt motion | The portioner vendors' choice; blue laser for dark and specular targets | 16 to 20 kHz profiles | IP67; stainless housings exist | [Gocator (archived)](http://web.archive.org/web/20251003155338/https://lmi3d.com/series/gocator-2500-series/), [Keyence](https://www.keyence.com/products/measure/laser-2d/lj-x8000/specs/) |
| Orbbec Gemini 335L | Active stereo, global shutter | Not tested on meat; specular holes expected as with any stereo | 1280 x 800 at 30 fps | IP65; hardware sync and unified timestamps across units | [depth cameras note](depth-cameras.md) |
| RealSense D435 / D455 | Active stereo | Fine for the bench; specular highlights leave holes | 30 to 90 fps | None | [depth cameras note](depth-cameras.md) |
| Polarization camera on Sony IMX250MZR | 2D, four-angle on-chip polarizers | Separates specular from diffuse on wet surfaces | 163 fps | Standard housing | [Sony](https://www.sony-semicon.com/en/products/is/industry/polarization.html) |

Supporting parts, same source note: autoVimation Dolphin V4A stainless IP69K enclosures
([autoVimation](https://www.autovimation.com/en/enclosures-en/dolphin-en)); Smart Vision Lights
LZEW300 IP69K washdown lights ([catalog](https://smartvisionlights.com/product-category/washdown/));
a diffuse dome plus a polarizer and analyzer pair for specular glare
([Advanced Illumination](https://advancedillumination.com/a-practical-guide-to-machine-vision-lighting/));
hardware-triggered GigE, not USB, because USB cameras on one host skew by 5 to 30 ms
([Chef Robotics](https://www.chefrobotics.ai/post/latency-aware-vision-language-action-models-vlas-with-system-identification-for-real-time-robot-control)).
Plan a daily recalibration after washdown until the mounts prove otherwise (meat note, unverified).

Bench plan before choosing: the meat note's days 3 to 4, a Zivid 2+ and a RealSense on 10 kg of
the customer's product, 200 frames at three exposures both sides up, hole fraction and point
noise per camera.

## Belt encoders and tracking

Requirements come from the only public document with numbers, the
[ABB conveyor tracking manual](https://search.abb.com/library/Download.aspx?DocumentID=3HAC050991-001&LanguageCode=en&DocumentPartId=&Action=Launch):
5,000 to 10,000 counts per metre after 4x decoding (more does not help, less loses accuracy);
camera trigger pulse in ms under 1000 x trigger distance in mm / max belt speed in mm/s.

| Item | Requirement | Candidates | Status |
|---|---|---|---|
| Incremental encoder on the belt drive | 5,000 to 10,000 counts per metre after quadrature decoding on the belt's roller diameter; stainless housing, IP69K, shaft seal rated for the plant's chemicals | Stainless washdown encoder lines exist from SICK (DBS60 Inox family), Baumer and Kübler | Vendor pages not fetched (SICK's catalog is JavaScript-rendered; fetch returned only the page title on 2026-09-06). Unverified. Get the belt roller diameter and drive ratio from the customer to compute pulses per revolution. |
| Photo-eye trigger | Hardware input to the tracking module, not a software poll | Any washdown photoelectric sensor with a PNP output | Unverified; choose with the integrator |
| Tracking module | Hardware stamp of the encoder count on trigger; object queue | ABB DSQC2000 (4 encoders, 8 sync channels, 254-object queue); UR DI0 to DI3 at up to 40 kHz decode; KUKA.ConveyorTech; FANUC iRPickTool | ABB and UR figures from the meat note; KUKA and FANUC publish no accuracy |

On ROS 2 there is no vendor equivalent; the belt frame is a TF broadcaster driven by the encoder
count ([meat note](../topics/meat-cutting-automation.md), conveyor tracking). The sim baseline
builds exactly that ([2026-09-08 record](../../experiments/2026-09-08-meat-cell-sim-baseline.md), build step 4).

## Safety scanners and controller

The cutter permissive is a hardwired safety function, never the vision chain: guards closed, arm
outside the cutter envelope via the safety controller's safe-zone output, product present
(meat note, cutting technology and interlocks). Standards: ISO 13849-1:2023 performance levels,
IEC 62061:2021, ISO 14119 interlocks, ISO 10218-1 and -2:2025 for the robot, OSHA 1910.212 and
1910.147 ([links in the meat note](../topics/meat-cutting-automation.md)).

| Item | Requirement | Candidates | Status |
|---|---|---|---|
| Safety controller | Configurable, PL d minimum (PL e if the integrator's risk assessment says so), safe-zone or safe-position output from the robot's safety option into it | Pilz PNOZmulti 2, SICK Flexi Soft, or the robot vendor's safety controller (ABB SafeMove, FANUC DCS, KUKA SafeOperation) | Pilz and SICK pages returned 403 or no content on 2026-09-06; unverified. Robot vendor options named in the [robot arms note](robot-arms.md) for ABB only. |
| Safety laser scanner | Area protection at the cell access side; IP65 or better, with a washdown housing option for the wet zone | SICK microScan3 family | Page not fetched; unverified |
| Interlocked guards | ISO 14119 interlocks on every cutter and cell guard; jam-clearing procedure written under 1910.147 before the first jam | Integrator scope | Standard text in the meat note |
| Blade stop | If a band saw is anywhere in the cell: Scott BladeStop stops in under 10 ms on contact, DGUV-certified | Scott | [BladeStop](https://scottautomation.com/en/bladestop) |

The safety concept (guards, safe zone, cutter permissive, jam clearing, PL target) goes to the
integrator before any cutter is powered (meat note, days 7 to 8).

## Compute

From the [compute note](compute.md) and the meat note's cell architecture: the GPU box sits in
the dry zone on a PREEMPT_RT kernel, one NIC to the robot and one to the cameras, `chrony`
between them; the tracking module runs on the robot controller; the PLC owns the cutter start
request.

| Item | Requirement | Candidate | Source |
|---|---|---|---|
| Perception and policy workstation | RTX-class GPU, 16 GB VRAM minimum for Isaac Lab twins, 24 GB or more if a VLA is ever evaluated on site; desktop drivers | RTX PRO 4500 Blackwell (32 GB, 200 W) in a NUC Extreme-class box; rugged Neousys Nuvo-10208GC for two desktop cards on DC power | [compute note, laptop and workstation](compute.md) |
| Real-time control PC | Separate from the GPU box (NVIDIA drivers are not supported on PREEMPT_RT); Ubuntu 22.04 with `linux-realtime-hwe-22.04`; cyclictest max under 100 us over a 3 h soak with cameras running | Any industrial x86 with two NICs | [compute note, real-time](compute.md) |
| Cell PLC | Owns production gate and cutter start request; talks to the safety controller | Integrator's standard | Meat note architecture |
| Training | Not on site; rented RTX 4090 at $0.34 to $0.74 per hour or an 80 GB card for fine-tunes | RunPod, Lambda | [compute note, training](compute.md) |
| Office laptop | ROS 2 and recording machine only; GTX 1050 Ti, 4 GB, Pascal end of life in driver 580 | Existing | [compute note](compute.md) |

## Open questions to confirm with the customer

Each one removes rows above. Ask them in this order.

1. Throughput: pieces per minute at the station today, and the target. Sets pick-on-the-fly
   versus presented piece, belt speed, and whether a delta at 120 to 240 picks per minute or a
   6-axis at a lower rate is the right class.
2. Piece: species and cut, length, width, thickness and mass range, whether it arrives skin-on,
   fat-cap up, or cut-face up, and how much variation between lots. Sets gripper stroke, the
   holding-force calculation `m (g + a) / mu` (compliant note), and the slab parameters in the
   sim baseline.
3. Temperature: chilled, near-frozen, or ambient at the station. A near-frozen piece is rigid
   and needs padded rigid fingers; chilled tissue stiffness drifts across a shift (deformable
   note, unverified as a robotics statement).
4. Hygiene zone and washdown: which zone the station is in, the washdown pressure, temperature
   and chemicals, the plant SSOP (9 CFR 416.12), the QA position on metal-detectable polymers
   and on any surface marking, and their ATP thresholds. Sets IP69K versus covered, and the
   gripper family.
5. Cutter: make and model, its infeed geometry, its acceptance window (lane offset, yaw,
   overlap), whether it exposes its own scan so placement can be scored against it, and whether
   the piece can be pushed into lane on a belt instead of lifted.
6. Belt and encoder: belt speed range, whether it is fixed or variable, roller diameter and
   drive ratio, and whether an encoder already exists.
7. Controller family: which robot and safety controller the plant or integrator already
   supports, and whether a UR-class cobot is acceptable on the floor at all.
8. Failure handling: who clears a jam at the infeed and under what procedure; whether a missed
   piece may pass through to the cutter uncut or must stop the line.

Answers go into the meat note's open questions and into the two experiment records'
assumptions.

## Related entries

- [meat cutting automation](../topics/meat-cutting-automation.md) (industry map, perception,
  grasping, hygiene, cell architecture)
- [compliant mechanisms and actuation](../topics/compliant-mechanisms-and-actuation.md)
  (gripper selection guide)
- [deformable object manipulation](../topics/deformable-object-manipulation.md) (transport limits,
  alignment)
- [robot arms](robot-arms.md), [grippers and end effectors](grippers-and-end-effectors.md),
  [depth cameras](depth-cameras.md), [compute](compute.md)
- [field deployment checklist](../../sops/field-deployment-checklist.md)
- [2026-09-08 sim baseline](../../experiments/2026-09-08-meat-cell-sim-baseline.md),
  [2026-09-15 learned vs scripted](../../experiments/2026-09-15-meat-cell-learned-vs-scripted.md)
