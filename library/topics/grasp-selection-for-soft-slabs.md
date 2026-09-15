---
title: Grasp selection for soft slabs
date: 2026-09-08
tags: [topic, grasping, grasp-planning, deformable, meat-cell, suction, beam-mechanics, transport, food-handling]
status: draft
source: synthesis
---

# Grasp selection for soft slabs

This entry is the decision rule, not the hardware and not the object model. Gripper families, suction cups, needle grippers and tactile
devices are in [grippers-and-end-effectors](../hardware/grippers-and-end-effectors.md); compliance placement and sizing in
[compliant-mechanisms-and-actuation](compliant-mechanisms-and-actuation.md); representations, simulators and the pick-place data pipeline in
[deformable-object-manipulation](deformable-object-manipulation.md); the cell, conveyor and hygiene envelope in
[meat-cutting-automation](meat-cutting-automation.md).

**Given a mask or a point cloud of one slab, which grasp does the system emit, and by what rule?**

Generate candidates by eroding the mask with the contact footprint, so the pad, cup or blade physically fits. Among the survivors, minimise
the longest unsupported overhang, because sag grows as the fourth power of overhang. Reject any candidate whose longest overhang exceeds
`L_max`, computed from local thickness, measured effective modulus, and the transport acceleration the cycle time demands. Tie-break on
thickness, seam clearance and reachability. If no single contact survives, add a second contact before you add force; if two do not survive,
put a surface under the piece and stop trying to pinch it. A learned scorer replaces the tie-break, never the `L_max` filter.

## 1. The physics that constrains the choice

### 1.1 The cantilever argument

Model the part of the slab beyond the grip as a prismatic beam of width `b`, thickness `h`, density `rho` and modulus `E`, built in at the
grip line and loaded only by its own weight, `q = rho g b h` per unit length. Tip deflection under a uniformly distributed load is `delta =
q L^4 / (8 E I)` with `I = b h^3 / 12` (Euler-Bernoulli; large-deflection correction in [Bisshopp and Drucker
1945](https://doi.org/10.1090/qam/13360)):

```
delta      = 3 rho g L^4 / (2 E h^2)              sag at the free end
delta / L  = 3 rho g L^3 / (2 E h^2)              sag ratio
L_max      = ( 2 eps E h^2 / (3 rho g) )^(1/3)    for a sag-ratio limit eps
```

Width cancels: a wide slab sags exactly as much as a narrow strip of the same thickness, so "grab more width" does not fix droop. The
exponents are the useful part. `L_max` goes as `h^(2/3)`, `E^(1/3)` and `g^(-1/3)`: doubling thickness buys 59% more overhang, a ten-fold
stiffer piece buys 2.15x, halving acceleration buys 26%. Numbers at `rho` = 1055 kg/m^3 (grand mean over n = 594 muscles, [Leonard et al.
2021](https://doi.org/10.1038/s41598-021-81489-w)) and `eps` = 0.10, so the free end may drop by a tenth of its overhang:

| `E` | `h` = 10 mm | 20 mm | 30 mm | 50 mm |
|---|---|---|---|---|
| 2 kPa | 11 mm | 17 mm | 23 mm | 32 mm |
| 10 kPa | 19 mm | 30 mm | 39 mm | 54 mm |
| 50 kPa | 32 mm | 51 mm | 66 mm | 93 mm |
| 100 kPa | 40 mm | 64 mm | 83 mm | 117 mm |
| 200 kPa | 51 mm | 80 mm | 105 mm | 148 mm |

That `E` column spans the published range for raw muscle, and the range is the whole story (1.4). At 10 kPa and 10 mm thick, nothing more
than 19 mm from the grip line stays up, so a 300 mm belly flap cannot be pinched at all and the only question is which support strategy to
use.

**Tearing is a different constraint and it does not bind.** Moment peaks at the grip line, `M = q L^2 / 2`, so `sigma_max = 3 rho g L^2 /
h`, independent of `E` and `b`, and `L_tear = sqrt(sigma_f h / (3 rho g))`. Rabbit extensor digitorum longus in transverse extension, the
direction a slab stretches when it hangs across the fibre, failed at 27.5 +/- 9.9 kPa (18 muscles, 9 animals, 0.05 %/s, freeze-thawed;
[Morrow et al. 2010](https://doi.org/10.1016/j.jmbbm.2009.03.004)), putting `L_tear` at 94 mm for 10 mm thickness and 163 mm at 30 mm, above
`L_max` at every modulus in the table. The piece droops out of tolerance long before bending tears it. Tearing comes from the pinch, from
stress concentration at the pad edge, and from local weakness: at a fat seam, meat-to-meat adhesive strength is roughly a third of the
perpendicular case when fibres run parallel to the junction ([Purslow et al. 1987](https://doi.org/10.1016/0309-1740\(87\)90060-X)).

**Under acceleration**, replace `g` with `g_eff`, the acceleration of the piece relative to free fall. `L_max` scales as `(g/g_eff)^(1/3)`:
0.92 at 3 m/s^2, 0.87 at 5, 0.79 at 10. Grasp choice and the acceleration cap are one problem. Fix `a_max` from the throughput the customer
needs, compute `L_max` there, and filter with it.

### 1.2 How far from the centroid a grasp can sit, and what two contacts buy

For a slab of length `L_p` along its long axis, a grasp a signed distance `d` from the mid-extent leaves a longer overhang of `L_p/2 + |d|`,
so `|d| <= L_max - L_p/2`. The target is the **mid-extent along the long axis**, not the area centroid: they coincide only on a shape
symmetric about its short axis, and on a tapered piece the centroid sits toward the fat end, lengthening the overhang on the thin end where
`h` is smallest and `L_max` shortest. If `L_p/2 < L_max`, a window of width `2 (L_max - L_p/2)` exists and the slack goes on thickness, seam
clearance and reachability. If `L_p/2` is about `L_max`, only the mid-extent works, to within the 3 to 10 mm pose error of camera and
calibration ([compliant-mechanisms-and-actuation](compliant-mechanisms-and-actuation.md)); a window narrower than the pose error is closed.
If `L_p/2 > L_max`, no single contact works: go to two contacts or a support surface, because grip force does nothing here, the piece is not
slipping but bending.

Two contacts a distance `s` apart leave end overhangs of `(L_p - s)/2` and a span that sags as a simply supported beam, `delta_mid = 5 rho g
s^4 / (32 E h^2)`, which is `5/48` of the cantilever tip sag at the same length; equating the two, ignoring support rotation, gives `s =
0.47 L_p`, and metrology's exact answers are the Bessel points at 0.5594 of the length and the minimum-sag points at 0.5536 ([Airy
points](https://en.wikipedia.org/wiki/Airy_points), [Mechanics and Machines](https://mechanicsandmachines.com/?p=330)). Rule: **two contacts
at 0.47 to 0.56 of the length, centred.** The payoff is not linear: one central grasp overhangs `0.50 L_p`, two contacts at `0.50 L_p`
spacing overhang `0.25 L_p`, and sag goes as the fourth power, so two contacts cut sag by 16, not by 2. That is the argument for a two-arm
cell or a dual-pad tool, and it is why the bimanual cloth results ([SpeedFolding](https://arxiv.org/abs/2208.10552),
[FabricFlowNet](https://arxiv.org/abs/2111.05623)) transfer as a geometry lesson even though their motions do not.

### 1.3 Every assumption, and how a slab of meat breaks it

A slab of meat is not a linear elastic beam. It is a wet, anisotropic, viscoelastic, heterogeneous continuum with a fracture-driven failure
mode. Use the formulas above to **rank candidates and size the search window**, never to predict an absolute sag in millimetres.

| Assumption | How meat breaks it | Error direction | What to do |
|---|---|---|---|
| Linear elastic, one `E` | Viscoelastic: sag keeps growing under a held load, and the curve stiffens with strain | Under-predicts sag for holds beyond a second or two | Fit `E_eff` at the dwell you actually use |
| Isotropic | Pork tension gives 77 kPa across the fibre at stretch 1.10 against 10 kPa along it, and Poisson's ratio is directional, 0.28 to 0.74 ([Takaza et al. 2013](https://doi.org/10.1016/j.jmbbm.2012.09.001)) | Up to 8x, either way | Measure both orientations, plan with the smaller `E`, log fibre direction in `DATASET.md` |
| Homogeneous | Fat seams and membrane act as hinges, so sag localises at the seam, and fracture follows the fibres ([Purslow et al. 1987](https://doi.org/10.1016/0309-1740\(87\)90060-X)) | Badly under-predicts local curvature; `sigma_f` is not a constant | Treat seams as boundaries, not material; fit `sigma_f` per pad geometry |
| Prismatic section | Real slabs taper and dome | Under-predicts sag at the thin end | Use the local `h` along the overhang, not the mean |
| Slender, no shear | Shear-to-bending tip deflection is about `1.18 (h/L)^2` for `nu` = 0.5 and a rectangular shear coefficient near 0.85 ([Cowper 1966](https://doi.org/10.1115/1.3625046)): 1% at `h/L` = 0.1, 11% at 0.3, 29% at 0.5 | Under-predicts sag on thick short overhangs | Treat the linear number as a lower bound when `h/L` > 0.2 |
| Small deflection | Past 10 to 15 degrees of tip slope the beam projects shorter and the moment arm falls ([Bisshopp and Drucker](https://doi.org/10.1090/qam/13360)) | Over-predicts drop, so it is conservative | Accept it; conservative is the right sign for a filter |
| Perfect clamp | A pinch is a finite-width compliant clamp on crushable tissue; the root rotates and tissue creeps out of the pads | Under-predicts sag, sometimes past the beam term | Measure sag with the actual gripper, not over a table edge |
| Gravity only | Wet tissue adheres to the belt, adding a downward pull at lift-off | Under-predicts peak stress at break-away | Add a slow break-away phase before transport |

### 1.4 What the literature says about `E`, and why you still measure it

| Tissue and test | Value | Conditions | Source |
|---|---|---|---|
| Beef longissimus, unconfined compression | 1.53 +/- 0.31 kPa (2.12 +/- 0.91 by ultrasound) | Linear fit to 5% strain, 5.7 cm punch at 5 cm/min, 22 C, within 48 h of death | [Chen et al. 1996](https://doi.org/10.1109/58.484478) ([PDF](http://brl.illinois.edu/Publications/1996/Chen-UFFC-191-1996.pdf)) |
| Pork longissimus, tension across / along fibre | 77 kPa / 10 kPa secant at stretch 1.10; failure near 1.15 / 1.65 | Fresh, optical strain measurement | [Takaza et al. 2013](https://doi.org/10.1016/j.jmbbm.2012.09.001) |
| Raw chicken breast fillet, compression | about 48.6 kPa, calibrating a DEM handling model | Geometry and rate not verified, publisher returned 403 (**unverified**) | [Vink et al. 2026](https://doi.org/10.1016/j.afres.2026.101880) |
| Pig carcass through rigor, shear-wave elastography | Peak 80 to 100 kPa at 32 C ambient; 280 to 300 kPa at 21 C and 1 C, over 50 h, 5 muscles, 9 pigs | Wave-speed derived, one to two orders above quasi-static values | [Kliewer et al. 2021](https://doi.org/10.2214/AJR.20.22915) |
| Raw salmon fillet | No modulus in Pa in any primary source (**not found**); fibres begin to break at 6 to 8 mm penetration | 4 C, iced 3 days, 2 mm/s | [Jonsson et al. 2001](https://doi.org/10.1046/j.1365-2095.2001.00152.x) |

The published numbers do not converge, which is why a lookup table cannot replace a measurement. The value depends on **test mode** (1.5 kPa
at 5% compression against 77 kPa at 10% stretch on comparable tissue, a factor of 50, while a gripper indents 20% to 40%), on **direction**
(about 8x in pork tension), and on **time and temperature** (stiffness rises through rigor, peaks and falls, three times higher at 1 C and
21 C than at 32 C). A single scalar Poisson's ratio is also wrong for muscle, against the 0.45 to 0.49 that soft-tissue FEM conventionally
assumes.

Invert the sag formula and measure what the planner needs: `E_eff = 3 rho g L^4 / (2 delta h^2)`. Slide a piece over the edge of a
food-grade plate so exactly `L` overhangs, hold for the dwell your cycle uses, photograph the profile against a scale bar, read `delta`.
Three overhangs (so you can check the `L^4` scaling holds and reject the pieces where it does not), two orientations relative to the fibre,
ten pieces per class, logging product temperature and dwell because both move the answer (cold shortening below about 15 C changes the tissue itself, minimum shortening at 14 to 19 C, [Locker and Hagyard 1963](https://doi.org/10.1002/jsfa.2740141103)). Report the **10th percentile**, not the median:
the floppiest piece in the batch sets the rule that runs all shift. Worked example: `L` = 80 mm, `h` = 25 mm, `delta` = 20 mm gives `E_eff`
= 51 kPa, and `delta` = 8 mm gives 127 kPa, so a factor of 2.5 in sag is only 1.36 in `L_max`.

## 2. Candidate selection rules

Every rule takes the same input contract: a binary mask `M` of one piece in the belt frame, an aligned height map `h(x, y)`, and a contact
footprint (a disc of radius `r` for a cup, a rectangle for jaw pads, a half-plane for a scoop). It emits a pose and a score.

| Rule | Input | Compute | What it actually optimises | What fails first |
|---|---|---|---|---|
| Mask centroid | mask | image moments, one pass | mean squared distance to the boundary | Non-convex pieces, where the centroid can leave the mask; tapered pieces, where it moves off the mid-extent and lengthens the governing overhang |
| Principal axis, mid-extent | mask | eigenvectors of the second moment matrix, then the mid-point of the projected extent | orientation, and the longer end overhang | Curved pieces, where the straight axis exits the mask; the 180-degree ambiguity needs a side classifier ([meat-cutting-automation](meat-cutting-automation.md)) |
| Largest inscribed circle, distance-transform maximum | mask | [`scipy.ndimage.distance_transform_edt`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.distance_transform_edt.html), argmax; [`skimage.morphology.medial_axis`](https://scikit-image.org/docs/stable/api/skimage.morphology.html) for the ridge | **clearance**: the largest contact patch that fits, furthest from every edge and hole | A feasibility rule, not a sag rule. On a long thin piece the ridge is flat and the argmax is noise; on a two-lobe piece it sits on the fatter lobe and the other lobe hangs |
| Minimum enclosing circle centre | mask, convex hull | hull, then minimise the max distance to hull vertices | **sag**: the longest overhang, for an isotropic contact | Ignores whether the contact fits, and ignores thickness |
| Oriented erosion by the pad footprint | mask, pad rectangle | binary erosion at K orientations | feasibility for a rectangular pad, plus pad angle | K times the cost; still 2D, so it will place a pad across a fat seam |
| Thickest-region grasp | height map | convolve `h` with the pad kernel, argmax | `h`, which enters `L_max` as `h^(2/3)`, and cuts pinch pressure | The thickness peak is often a fat seam or cap, the tissue least able to hold a pinch, and it can sit far from the sag optimum |
| Two-point or two-arm | mask, kinematics | search over pairs near 0.47 to 0.56 `L_p` spacing | sag, by up to 16x (1.2) | Reach, arm-arm collision, cell cost. On a stiff piece the contacts fight and pre-stress the tissue |
| Scoop or spatula under-slide | mask, surface geometry | approach along the lowest-friction lead edge, blade under the whole footprint | it deletes the sag constraint, `L_max` no longer applies | Needs an unobstructed lead edge and low-friction surface; drags rather than lifts, shifting the pose you were controlling; slowest option |
| Suction patch by flatness | organised point cloud | plane-fit residual and normal deviation in a cup-sized window, seal closure by convolution with a cup mask | seal probability | A cut face, fat cap or free moisture leaks. One cup is nearly a point contact, so the overhang is `L_p/2` in every direction at once |
| Needle penetration point | height map | require `h_local` > stroke + margin, and > needle-pattern radius from every edge | holding force without a seal | Puncture acceptance by the customer's QA, then needle pull-through on soft tissue |

### 2.1 Clearance and sag are two different rules, and you need both

This is the point most pipelines get wrong. The distance-transform maximum is the **incentre**, the point furthest from the boundary, where
the largest disc fits. The minimum enclosing circle centre is the **Chebyshev centre**, the point whose distance to the farthest material is
smallest. The first says "the cup will seal here and the pads will not hang off the edge"; the second says "nothing hangs down too far from
here". They are not the same point, and on a two-lobe or L-shaped piece they can be 100 mm apart. Run them in order:

1. **Feasibility by erosion.** Erode `M` by the contact footprint at each candidate orientation; for a disc of radius `r`, survivors are
   exactly the pixels with `EDT > r`. Erode away seams and holes too.
2. **Sag by min-max.** For each survivor `p`, compute `R(p)`, the maximum distance from `p` to the mask, and take the argmin. Evaluating `R`
   against the convex hull vertices makes this cheap: one hull at `O(N log N)`, then a few thousand candidates against a 20-vertex hull,
   inside the 10 ms grasp-plan budget in [meat-cutting-automation](meat-cutting-automation.md).
3. **Filter.** Accept only if `R(p) <= L_max(h(p), E_eff, a_max)`.

On a curved piece, use a geodesic distance inside the mask in step 2: a banana bends along its own length, and the straight line across the
concave side under-states the material being carried. For two contacts, step 2 becomes the 2-centre problem, minimising the maximum distance
from any mask point to the **nearer** contact; a coarse grid search over pairs is adequate and recovers the 0.47 to 0.56 spacing of 1.2
independently.

### 2.2 Thickness, scoop, suction and needles

**Thickness is the cheapest thing you can buy.** `L_max` goes as `h^(2/3)`, so a 30 mm region tolerates twice the overhang of a 7.5 mm
region, which makes the height map the important input, not the mask.

**Scoop and under-slide delete the constraint.** A blade under the whole footprint sets the overhang to zero, leaving only transport
friction, at the cost of cycle time (about 4 s, against 240 picks per minute for a vacuum harvester, [JBT Marel
DSI](https://jbtmarel.com/en/products/dsi-dual-robotic-harvester-automated-meat-processing/)); reach for it when the sag filter rejects
everything, not before. Published devices: a scooping-binding gripper, 536.8 g with 1 mm thick, 10 mm wide plates, handled 20 food items at
five trials each with 17 of 20 at 5/5 (raw shrimp 4/5, Carangidae fish 3/5, raw oyster 4/5) at "approximately 4 s" takt ([Wang et al.
2021](https://doi.org/10.3389/frobt.2021.640805)), and GRIBBOT's beak plus pneumatic supporting plate under the fillet ([Misimi et al.
2016](https://doi.org/10.1016/j.compag.2015.11.021)).

**Suction patch selection is a seal problem, and a cup is nearly a point contact**, so it carries the worst sag geometry, which makes
suction on a slab a multi-cup problem once the piece exceeds about `2 L_max`. For the patch, Jiang et al. define graspability as `Jq = 0.5
Jc + 0.5 Js`, with `Jc` the "normalized distance to the center of the graspable area" and `Js` the "flatness and smoothness of the contact
area", and test seal closure by convolving the surface mask "with a vacuum cup mask (of size 18x18)" so only regions where "the vacuum cup
can make full contact with the surfaces" survive ([arXiv:2111.02571](https://arxiv.org/abs/2111.02571)), which is the erosion idea of 2.1
applied to depth; Seg2Grasp ranks with "three metrics: surface angle theta, distance d from the centroid C_T, and the count of graspable
points" ([arXiv:2607.17757](https://arxiv.org/abs/2607.17757)). None of it sees moisture: a cut face can pass every geometric seal test and
still leak.

**Needle penetration** is governed by the stroke, which runs 3.0 mm on a Schmalz SNG-M with 0.8 mm needles up to a variable 20 mm on the
SNG-AP
([SNG-V](https://www.schmalz.com/en/vacuum-technology-for-automation/vacuum-components/special-grippers/needle-gripper/needle-grippers-sng-v)).
The needle must engage without exiting the far face, so require `h_local > stroke + margin`, and the patch must sit at least one
needle-pattern radius from every edge or the needles tear out sideways. Whether QA accepts punctures decides this row before geometry.

## 3. Learned grasp scoring

**DefGraspSim** ([Huang et al., arXiv:2203.11274](https://arxiv.org/abs/2203.11274)) is the reference for scoring a grasp on a deformable
object by simulating it: "an antipodal sampler" produces "50 candidate grasps" per object, co-rotational FEM in Isaac Gym at 1500 Hz with a
Franka parallel jaw evaluates them over `E` in `{2e4, 2e5, 2e6, 2e9}` Pa and `nu` = 0.3, and seven metrics come out over 34 objects, 6,800
grasps and 1.1M measurements: pickup success, maximum von Mises stress, deformation ("the node-wise displacement field of the object from
pre- to post-pickup, neglecting rigid-body transformations"), strain energy, linear instability ("the minimum acceleration applied to the
gripper ... at which the object loses contact"), angular instability, and deformation controllability ("the maximum deformation when the
object is reoriented under gravity"). Those map onto this note directly: linear instability **is** the acceleration cap of Section 5,
measured rather than assumed; deformation and deformation controllability **are** the sag and fold criteria of Section 1 on a real geometry
instead of a prismatic beam; stress is the tear criterion. Its surrogate **DefGraspNets** predicts the same "3D stress and deformation
fields" "up to 1500 times faster than the FEM simulator" and is differentiable, the only route by which FEM-quality scoring gets inside a 10
ms budget ([arXiv:2303.16138](https://arxiv.org/abs/2303.16138)).

**Dex-Net 3.0** ([Mahler et al., arXiv:1709.06670](https://arxiv.org/abs/1709.06670)) is the model to copy for cups. The cup is a ring of
springs (perimeter springs between adjacent contact-ring vertices, cone springs to the apex, flexion springs between non-adjacent vertices
to resist bending), and a seal forms only if "each of the perimeter springs of C lies entirely on the surface of M", with no cone-face
collision, no hole inside the ring, and spring energy below a threshold. Holding is a wrench problem with five basis wrenches (actuated
normal force, constant vacuum force, tangential friction, torsional friction, elastic restoring torques) under constraints including
`sqrt(3)|fx| <= mu fN` and the peel term `sqrt(2)|tau_x| <= pi r kappa`. Trained on 2.8M point clouds from 1,500 models, its GQ-CNN
"achieves 93.5% classification accuracy on the held-out validation set" and in "350 physical trials on an ABB YuMi" reached "98%, 82%, and
58%" on Basic, Typical and Adversarial objects.

On real meat the end-to-end number is sobering. **ChicGrasp** trains a "conditional diffusion-policy controller" from "only 50 multi-view
teleoperation demonstrations" and "achieves a 40.6% grasp-and-lift success rate" at "38 s" per pick-to-shackle cycle, while
"state-of-the-art implicit behaviour cloning (IBC) and LSTM-GMM baselines fail entirely" ([Davar et al.
2025](https://arxiv.org/abs/2505.08986)): two orders of magnitude from line rate, so an end-to-end learned policy is not the production path
for this step.

A learned **scorer** inside a geometric candidate generator is a different proposition. It sees what the mask cannot, since local stiffness,
seam location, fat cover, moisture and temperature all correlate with appearance and none is in `L_max`, so when the piece varies the
geometric rule keeps proposing the same point and the scorer is what moves it. It trains on the cell's own outcome labels, because the
verification camera in [meat-cutting-automation](meat-cutting-automation.md) labels every cycle. What it does not buy is the sag filter:
`L_max` is physics you already know, it is cheap, and its violation produces the failure the customer notices, so encode it as a hard mask
on the candidate set rather than hoping a network learns it. That is the Dex-Net structure, analytic candidate model plus learned ranker.

## 4. Verification: has it got the piece, and is the piece folded

| Signal | What it proves | When | Blind to |
|---|---|---|---|
| Gripper width at close vs predicted compressed thickness | something is between the jaws | during close | how much. A fold reads thicker than a flat grip and so looks better |
| Part-detected flag (fingers stopped early; Robotiq "built-in part detection", see [grippers-and-end-effectors](../hardware/grippers-and-end-effectors.md)) | contact before the commanded width | during close | a corner grip, or a grip on one lobe of two |
| Vacuum level at the cup, not at the pump | a seal formed | on contact | a partial seal that holds static vacuum and peels under acceleration; a port occluded by tissue |
| Vacuum decay slope during a deliberate hold | leak rate, which is what predicts a drop | 100 to 300 ms | fold |
| F/T payload estimate after lift vs mass predicted from mask area x thickness x density; recursive total least squares is the standard estimator ([Kubus, Kroger, Wahl, IROS 2008](https://www.semanticscholar.org/paper/On-line-estimation-of-inertial-parameters-using-a-Kubus-Kr%C3%B6ger/7748e150487725b75b76679e4b18028950d7a5f5)) | picked none, one, two, or a corner with half left behind | after lift, needs a still pose or the arm dynamic model | fold. A folded piece weighs the same |
| Silhouette after lift, side or backlit camera | fold, directly: projected long-axis length shrinks while vertical extent grows | after lift, one frame | slip that has not started yet |
| Overhead mask area after place vs pre-grasp area | fold and tear, as an area loss | after place | too late for this piece; use it as the training label |
| Tactile slip ([Takacs et al. 2023](https://arxiv.org/abs/2307.05648); regrasp on touch, [Calandra et al. 2018](https://arxiv.org/abs/1805.11085)) | incipient slip | continuous | gel and window survival under washdown |
| In-hand time-of-flight stability prediction, "85.5% on validation and 86.0% on test objects" at 15 Hz before lifting ([DuFrene and Grimm 2026](https://arxiv.org/abs/2605.05461)) | a bad grasp before you commit | pre-lift | trained on rigid objects, unproven on deformables (**unverified**) |

Ordering matters more than the sensor list: width and part-detected before lifting, vacuum decay during a deliberate 200 ms static hold, F/T
mass check at the top of the lift, silhouette fold check once at the same pose every cycle, and overhead area check after placing, which is
the label that trains everything else. Define three outcomes in the state machine, not in the policy: **continue**, **regrasp** (mass wrong
or slip detected: open, retreat, re-image, replan), and **abort and re-present** (fold detected: put the piece back on the belt for the
flattening pass rather than delivering a fold into the cutter). Only the third protects yield.

## 5. Transport constraints

**Friction pinch.** Pads must supply `N >= m |g_eff| / mu`; given the force they may apply without marking, `N_max = p_max A_pad`, the cap
is `a_max <= mu p_max A_pad / m - g`. Measure `mu` by tilting a plate until a piece slides and `p_max` by pressing pads at rising force and
looking for a mark after ten minutes. **There is no published friction coefficient for raw meat against stainless steel, silicone,
polyurethane or belt material**: a search of Europe PMC full text, OpenAlex and Crossref found no peer-reviewed value, no method and no
static-versus-kinetic split for this pair (**not found**, searched 2026-09-08). Industry uses the vendor design table, 0.2 to 0.3 for wet
surfaces, 0.1 for oily, 0.5 for wood, metal and glass, 0.6 for rough, with the caveat that "it is not possible to specify generally valid
values of the friction coefficient between the suction cup and the workpiece" and it "has to be determined correctly through trials with the
condition of the workpiece surface (rough/dry/moist/oily)"
([Schmalz](https://www.schmalz.com/en/support/know-how/vacuum-knowledge/the-vacuum-system-and-its-components/vacuum-suction-cups/design-of-the-suction-cup)).
Use 0.2 as a prior, then measure your own wet, chilled and at end of shift, because `a_max` is linear in `mu` and every other term is known.

**Suction, the vendor arithmetic.** Schmalz gives the required theoretical holding force in three load cases, and SMC publishes the same
three:

```
I    cup horizontal, load vertical      F_TH = m (g + a) S
II   cup horizontal, load horizontal    F_TH = m (g + a/mu) S
III  cup vertical, load vertical        F_TH = (m/mu) (g + a) S
```

`S` is the safety factor, "a minimum value of 1.5 for smooth and dense workpieces" and "2.0 or greater ... for critical, heterogeneous,
porous, rough or oiled workpieces". Per cup, `F_S = F_TH / n`, and cup force is `F [N] = effective area [cm^2] x vacuum [kPa] x 0.1`, so
SMC's worked example of 7.1 cm^2 at -60 kPa gives 42.6 N. Note what case II says: horizontal acceleration is divided by `mu`, so at `mu` =
0.2 a lateral 3 m/s^2 costs the same as 15 m/s^2 of extra gravity. On wet product sideways acceleration is five times as expensive as
vertical, and that term should shape the trajectory before anything else does.

**Where the vendor arithmetic stops.** Static holding force is never the binding constraint on a slab. The two that bind come from the
multi-suction-cup failure model of [Lee, Sun, Bylard and Sentis 2024](https://arxiv.org/abs/2408.03498): suction loss per cup, where "grasp
failure due to suction loss occurs if the pulling force exerted on any suction cup exceeds its suction force", with moment terms bounded by
`r_pad` times the residual normal capacity so the resultant load line stays inside the cup footprint (`e <= r_pad (psi/W - 1)` for a centre
of mass `e` off the cup axis, `W = m |g_eff|`); and whole-grasp slippage, where "slippage occurs if the total force required on the suction
cups to maintain grasp exceeds the friction cone inequality" on the summed wrench. Worked example, a 40 mm cup at 60 kPa on a 0.8 kg piece,
taking 60 N of cup force to allow for the lip: at rest `W` = 7.8 N and `e <= 133 mm`; at `a` = 5 m/s^2, `W` = 11.8 N and `e <= 82 mm`.

That bound is still optimistic for a slab. A rigid box transmits the moment to the cup as a couple; a floppy slab hinges at the cup rim, so
the load becomes a peel line load on one arc of the lip and the right comparison is against peel resistance, which is what Dex-Net's elastic
restoring torque limit models. Treat the rigid-body `e` bound as an upper bound and measure the real one (**unverified reasoning; measure
it**). The fixes are geometric: more cups spread over the footprint so the peel arc is short, cups bracketing the mid-extent rather than one
at the centroid, and a trajectory that keeps acceleration pointing into the cup face.

**Size the pump for leak, not vacuum level.** At a 5 l/min leak a high-vacuum (S) ejector nozzle reaches -72 kPa and a high-flow (L) nozzle
only -45 kPa, but at 40 l/min the S nozzle collapses to -10 kPa while the L nozzle still holds -23 kPa
([SMC](https://www.smcworld.com/catalog/BEST-technical-data-en/pdf/Vacuum-Common_en.pdf)). A cut face or wet fat cap is a leak, so the meat
cell wants the flow-biased generator even though it reads worse in the vacuum column.

**Do not stop at a flat acceleration cap.** A single Cartesian limit is too slow on the easy pieces and too fast on the floppy ones. The
principled version puts grasp failure into time-optimal trajectory parameterisation as second-order constraints: on an 8-cup gripper on a
Kawasaki RS020N across 11 trial motions, constrained trajectories were up to 19.2% longer while the true negative rate rose from 60% to 79%
with weight adjustment, at a 13% false alarm rate, against a baseline that "never predicted a grasp failure"
([arXiv:2408.03498](https://arxiv.org/abs/2408.03498)). A slab adds a constraint the box literature does not have: `L_over <= L_max(h,
E_eff, g_eff)`, which becomes `g_eff <= g (L_max(g) / L_over)^3`. A grasp with 20% sag margin permits 1.73 g, so `a_max` about 7.2 m/s^2; 5%
margin permits 1.16, about 1.5 m/s^2. Margin is worth a lot of throughput, which is the argument for spending planner effort on grasp choice
rather than trajectory smoothing.

## 6. Release and alignment into the fixture

Placement is where the sag budget is spent, not saved: any fold introduced here goes into the cutter.

1. **Descend to contact, not to a position.** Stop on a force threshold or gripper-width change, under admittance control. A
   position-commanded descent onto a 25 mm piece with 5 mm of thickness error either crushes it or drops it.
2. **Keep the drop height small and measure the sensitivity.** Release at height `z` lands at `sqrt(2 g z)`: 0.31 m/s from 5 mm, 0.63 m/s
   from 20 mm, and the energy `m g z` goes into deformation and lateral spread, which is the placement error you were trying to control.
   Sweep `z` at 0, 5, 10, 20 mm and report the residual at each; expect monotone (**unverified**, this is the measurement to run).
3. **Open in two stages, along the long axis.** Compliant pads store energy and a fast full open flicks the piece sideways; open to just
   past contact, pause, then open fully.
4. **Break vacuum actively.** A passive vent leaves residual vacuum and the piece lifts with the tool; a blow-off pulse releases cleanly but
   displaces the piece, so tune it to the minimum that releases and delay the retract until the piece stops moving. Retract vertically
   before any lateral move, or the piece is dragged.
5. **Push to datum under force control.** Alignment by contact beats alignment by placement accuracy; the primitive is in
   [deformable-object-manipulation](deformable-object-manipulation.md). What that entry does not say: push along the short axis, where the
   piece is stiffest in plane, with a face wider than the piece so the contact does not locally indent and rotate it.
6. **Wait for settle.** Viscoelastic tissue keeps moving after release. Define settle as the frame at which the mask centroid moves less
   than 0.5 mm between consecutive frames, measure it per product class, and put it in the cycle budget instead of discovering it as jitter
   in the placement residual.

## 7. Decision table: piece properties to rule

`L_p` is the long-axis length, `w_pad` the contact footprint. "What fails first" is the mode that appears first as the rule is pushed past
its range.

| Piece | Thickness | Stiffness | Wetness | Size vs contact | First rule | Fallback | What fails first |
|---|---|---|---|---|---|---|---|
| Thin flap (belly, skirt, trim) | under 10 mm | low | wet | `L_p` >> `w_pad` | Scoop or under-slide | Belt-assisted transfer, no lift at all | A pinch folds at the pad edge before the piece leaves the belt; `L_max` is smaller than the pad |
| Thin, dry-skinned sheet | under 10 mm | low | dry skin | `L_p` >> `w_pad` | Multi-cup suction on the flattest patches, bracketing the mid-extent | Scoop | Peel at the rim on the first acceleration, well before pull-off |
| Medium slab | 10 to 30 mm | medium | wet | `L_p` 2 to 4x `w_pad` | Eroded feasibility then min-max sag (2.1) | Two-point | End droop past `L_max`, then swing during transport |
| Long medium slab | 10 to 30 mm | medium | wet | `L_p` over 6x `w_pad` | Two contacts at 0.47 to 0.56 `L_p` | Scoop | Reach and arm-arm collision, then mid-span sag if the spacing is wrong |
| Thick block | over 40 mm | medium to high | any | `L_p` about `w_pad` | Thickest-region pinch at the mid-extent | Suction if one face is flat and dry | Pinch pressure marks or crushes the surface before sag matters |
| Chilled or crusted | any | high | dry | any | Treat as rigid, standard antipodal planning | Suction | Nothing in this note. The gripper marks it, and soft fingers stiffen in the cold |
| Fibrous, porous, dry (crumbed) | any | low | dry | any | Needle, only if QA accepts punctures | Scoop | Needle pull-through in soft tissue, then rejection of the marks |
| Piece with a seam or a hole | any | any | any | any | Erode the mask including the hole, then min-max sag | Two contacts straddling the seam | The seam hinges and the piece folds through it regardless of overhang |
| Two-lobe or L-shaped | any | any | any | any | Min-max sag, never the distance-transform maximum | Two contacts, one per lobe | The distance-transform maximum sits on the fat lobe and the thin lobe folds |
| Tapered (loin, tail-on fillet) | varies along `L_p` | varies | any | any | Mid-extent weighted toward the thin end, `L_max` at the local `h` | Two contacts | The area centroid pulls the grasp toward the fat end and the thin end droops |

## 8. How to settle this by measurement

Nothing above is settled. This is the head-to-head that settles it, written before the first run, per `sops/experiment-protocol.md`.

**Setup.** One slab model in MuJoCo `flex` (3D tetrahedral, continuum mode) or Isaac Lab `DeformableObject`, at the versions pinned in
[sim-first-workflow](sim-first-workflow.md), parameterised by `(L_p, b, h, E, nu, rho)` plus taper and curvature. Each rule from Section 2
is a pure function from `(mask, height map, footprint)` to a grasp, run on the rendered observation rather than ground truth, so perception
error sits inside the comparison.

**Sweep**, 20 seeds per cell, every number reported with its count: `E` at 4 levels spanning the measured 10th to 90th percentile from 1.4
plus one decade either side, because DefGraspSim spans orders of magnitude for the same reason; `h` at 10, 20, 30 and 50 mm, the strongest
geometric factor; aspect `L_p/b` at 2, 4 and 8; shape as rectangle, taper, curved, two-lobe and holed, which separates the rules that differ
only on non-convex outlines; transport `a` at 1, 3, 5 and 8 m/s^2, which is both `g_eff` and the throughput knob; contact as 30x60 mm pads,
one 40 mm cup, two 40 mm cups and a scoop; and perception error at 0, 3, 6, 10 mm and 0, 5, 10 deg on the mask, spanning the stated 3 to 10
mm calibration range.

**Metrics**, named to match DefGraspSim so they stay comparable: pickup success (binary); maximum sag ratio in transport, as peak nodal
displacement over the governing overhang, against the `L_max` prediction; maximum von Mises stress at the grip line over the measured tear
stress; fold indicator, the minimum over the episode of projected long-axis length over rest length, with below 0.90 counting as a fold;
linear instability, the acceleration at which contact is lost, against the Section 5 arithmetic; placement residual at the fixture in mm and
degrees, median and 95th percentile; and rule compute time per frame.

**Pass criteria** (proposal; the cutter's tolerance window is the customer's number and this manual has none, **unverified**): the proposed
rule beats the centroid baseline on fold rate in **every** `(E, h)` cell, not on the average,; pickup success at least 98% at the median `E`
and 95% at the 10th percentile; fold rate under 1% at `a_max`; 95th-percentile placement residual inside the cutter's window; compute under
10 ms per frame; and `L_max` matching measured sag within 25% across the sweep.

**The real-world tie-back, without which the sim proves nothing.** Repeat on 20 real pieces per class: the sag test of 1.4 for `E_eff`, a
tear test for `sigma_f`, a tilt test for `mu`, and 50 picks per rule for the top two the sim ranked. The sim earns the right to rank rules
only if its top two match the real top two; otherwise keep it as a candidate generator and select on real trials.

## Practical gotchas

- **Sag is fourth-order, so intuition is wrong.** A 20% error in overhang is a 107% error in sag; a rule that "usually looks about right" on
  screen fails on the tail of the size distribution.
- **The distance-transform maximum is the clearance optimum, not the sag optimum.** Using it alone puts the grasp on the fattest lobe and
  lets the other lobe fold.
- **Suction on a slab fails by peeling, not by pulling.** Sizing the pump for pull-off force and then wondering why pieces drop is the
  standard mistake.
- **Frozen and near-frozen product is a different problem.** Work to fracture in beef semitendinosus peaks between -10 and -15 C, ductile
  above and brittle below, essential work of fracture around 100 to 200 J/m^2 ([Dobraszczyk et al.
  1987](https://doi.org/10.1016/0309-1740\(87\)90040-4)). Plan it as a rigid object.
- **`E_eff` drifts through the shift** as product warms and post-mortem age advances; rigor stiffness peaks then falls, three times higher
  at 1 C than 32 C ([Kliewer et al. 2021](https://doi.org/10.2214/AJR.20.22915)). Measure at start of shift and after four hours
  (**unverified**; this is the measurement, not a result).
- **Warner-Bratzler shear force is not a material property you can use.** It is the number the meat industry will offer, and it is a force
  in kgf on **cooked** meat: beef longissimus 4.6 +/- 1.1 kg over n = 360, and the same sample reads 4.6 kg at 50 mm/min and 3.6 kg at 500
  mm/min ([Wheeler, Shackelford, Koohmaraie 1997](https://www.ars.usda.gov/ARSUserFiles/30400510/1997500068.pdf)).
- **The tear starts at the pad edge**, so rounded edges and a soft perimeter durometer matter more than the pad's average stiffness: the
  stress concentration initiates it, not the mean pressure.
- **A fold passes every "did I get it" check except vision.** Width, part detection, vacuum and mass all read normal on a folded piece; no
  post-lift silhouette check means no fold detection.

## What a forward-deployed engineer must be able to do

- [ ] Derive `L_max` at the whiteboard, state its exponents in `h`, `E` and `g`, and name three assumptions it breaks on meat.
- [ ] Measure `E_eff` from a sag test on 10 pieces and report the 10th percentile with overhangs and dwell.
- [ ] Compute the window `|d| <= L_max - L_p/2` for a customer's product and say whether a single-arm pinch is possible at all, before
      quoting.
- [ ] Implement eroded feasibility plus min-max sag on a mask and a height map, and show it runs under 10 ms.
- [ ] Explain, with the factor-of-16 argument, why a second arm may be cheaper than a stiffer product spec.
- [ ] Set the acceleration cap from the grasp's sag margin using `g_eff <= g (margin)^3`, and run the Schmalz three-load-case arithmetic for
      the suction option.
- [ ] Instrument the verification signals of Section 4 and say which of them detects a fold.
- [ ] Run the head-to-head of Section 8 and report a ranking with trial counts, including the case where the simple rule wins.

## Open questions to learn hands-on

- What is `E_eff` for our product at start of shift and after four hours, and does `L_max` move enough to need a per-batch update?
- What is `mu` for our pads against our product, wet and blotted, at our normal pressure? No published value exists for this material pair,
  so the measurement is the contribution.
- Does the min-max-sag rule beat the centroid on fold rate on real product at 50 picks each, or does perception error swamp the difference?
- At what `L_p / L_max` ratio does a second arm pay back its cost in yield, given the cutter tolerance?
- How much of the rigid-body suction moment bound survives on a slab, once the cup peels at the rim instead of transmitting a couple?
  Measure the offset `e` at which one cup drops the piece at 1, 3 and 5 m/s^2.

## Related entries

- [deformable-object-manipulation](deformable-object-manipulation.md),
  [compliant-mechanisms-and-actuation](compliant-mechanisms-and-actuation.md),
  [grippers-and-end-effectors](../hardware/grippers-and-end-effectors.md), [meat-cutting-automation](meat-cutting-automation.md),
  [conveyor-tracking-and-visual-servoing](conveyor-tracking-and-visual-servoing.md)
- [perception-3d-sensing](perception-3d-sensing.md), [perception-tactile-and-force](perception-tactile-and-force.md),
  [sim-first-workflow](sim-first-workflow.md), [policy-evaluation](policy-evaluation.md)
- `sops/experiment-protocol.md`, `sops/data-collection-protocol.md`

## Sources

- Beam mechanics: [Bisshopp and Drucker 1945](https://doi.org/10.1090/qam/13360) ([free
  PDF](https://pubs.ams.org/journals/qam/1945-03-03/S0033-569X-1945-13360-8/S0033-569X-1945-13360-8.pdf)), [Cowper 1966, The Shear
  Coefficient in Timoshenko's Beam Theory](https://doi.org/10.1115/1.3625046), [Airy points](https://en.wikipedia.org/wiki/Airy_points),
  [Airy, Bessel and minimum-sag support points](https://mechanicsandmachines.com/?p=330)
- Muscle mechanics: [Chen et al. 1996](https://doi.org/10.1109/58.484478), [Takaza et al.
  2013](https://doi.org/10.1016/j.jmbbm.2012.09.001), [Morrow et al. 2010](https://doi.org/10.1016/j.jmbbm.2009.03.004), [Vink et al.
  2026](https://doi.org/10.1016/j.afres.2026.101880), [Kliewer et al. 2021](https://doi.org/10.2214/AJR.20.22915), [Leonard et al. 2021,
  muscle density](https://doi.org/10.1038/s41598-021-81489-w), [Purslow et al. 1987](https://doi.org/10.1016/0309-1740\(87\)90060-X),
  [Dobraszczyk et al. 1987](https://doi.org/10.1016/0309-1740\(87\)90040-4), [Locker and Hagyard
  1963](https://doi.org/10.1002/jsfa.2740141103), [Jonsson et al. 2001](https://doi.org/10.1046/j.1365-2095.2001.00152.x), [Wheeler et al.
  1997, WBSF](https://www.ars.usda.gov/ARSUserFiles/30400510/1997500068.pdf)
- Grasp evaluation on deformables: [DefGraspSim, arXiv:2203.11274](https://arxiv.org/abs/2203.11274), [DefGraspNets,
  arXiv:2303.16138](https://arxiv.org/abs/2303.16138)
- Suction: [Dex-Net 3.0, arXiv:1709.06670](https://arxiv.org/abs/1709.06670), [Jiang et al. 2021,
  arXiv:2111.02571](https://arxiv.org/abs/2111.02571), [Seg2Grasp, arXiv:2607.17757](https://arxiv.org/abs/2607.17757), [Lee, Sun, Bylard,
  Sentis 2024, arXiv:2408.03498](https://arxiv.org/abs/2408.03498), [Mantriota and Messina 2011, flat cups under tangential load](https://doi.org/10.1016/j.mechmachtheory.2011.01.003) (background; paywalled, **unverified**)
- Vendor sizing: [Schmalz theoretical holding
  force](https://www.schmalz.com/en/support/know-how/vacuum-knowledge/the-vacuum-system-and-its-components/system-design-calculation-example/theoretical-holding-force-of-a-suction-cup),
  [Schmalz cup
  design](https://www.schmalz.com/en/support/know-how/vacuum-knowledge/the-vacuum-system-and-its-components/vacuum-suction-cups/design-of-the-suction-cup),
  [Schmalz SNG-V needle
  grippers](https://www.schmalz.com/en/vacuum-technology-for-automation/vacuum-components/special-grippers/needle-gripper/needle-grippers-sng-v),
  [SMC vacuum technical data](https://www.smcworld.com/catalog/BEST-technical-data-en/pdf/Vacuum-Common_en.pdf)
- Learned grasping on meat and food: [ChicGrasp, arXiv:2505.08986](https://arxiv.org/abs/2505.08986), [Wang et al. 2021, scooping-binding
  gripper](https://doi.org/10.3389/frobt.2021.640805), [Misimi et al. 2016, GRIBBOT](https://doi.org/10.1016/j.compag.2015.11.021), [JBT
  Marel DSI harvester](https://jbtmarel.com/en/products/dsi-dual-robotic-harvester-automated-meat-processing/)
- Verification and bimanual: [Kubus, Kroger, Wahl, IROS
  2008](https://www.semanticscholar.org/paper/On-line-estimation-of-inertial-parameters-using-a-Kubus-Kr%C3%B6ger/7748e150487725b75b76679e4b18028950d7a5f5),
  [DuFrene and Grimm 2026, arXiv:2605.05461](https://arxiv.org/abs/2605.05461), [Takacs et al. 2023,
  arXiv:2307.05648](https://arxiv.org/abs/2307.05648), [Calandra et al. 2018, arXiv:1805.11085](https://arxiv.org/abs/1805.11085),
  [SpeedFolding, arXiv:2208.10552](https://arxiv.org/abs/2208.10552), [FabricFlowNet, arXiv:2111.05623](https://arxiv.org/abs/2111.05623)
- Implementation:
  [scipy.ndimage.distance_transform_edt](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.distance_transform_edt.html),
  [skimage.morphology.medial_axis](https://scikit-image.org/docs/stable/api/skimage.morphology.html)
