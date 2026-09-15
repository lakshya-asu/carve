---
title: "Arm and gripper parameters for the pork leg cell sim: UR20, FANUC SR-20iA, long-stroke grippers"
date: 2026-09-14
tags: [hardware, robot-arm, scara, six-axis, gripper, mujoco, kinematics, meat-cell]
status: draft
sources:
  - https://www.universal-robots.com/articles/ur/application-installation/dh-parameters-for-calculations-of-kinematics-and-dynamics/
  - https://www.universal-robots.com/manuals/EN/TechSheets/UR20_techsheet_pdf_online/UR20_techsheet_en.pdf
  - https://www.universal-robots.com/manuals/EN/PDF/SW5_19/user-manual-UR20-PDF_online/718-818-00_UR20_User_Manual_en_Global.pdf
  - https://www.fanucamerica.com/uploads/files/data-sheets/sr-20ia-datasheet.pdf
  - https://www.fanucamerica.com/products/robot/sr-20ia
  - https://www.fanuc.eu/eu-en/product/robot/sr-20ia
  - https://global.yamaha-motor.com/business/robot/lineup/ykxg/proof/pdf/index/YK1000XGP_E_0707.pdf
  - https://onrobot.com/storage/datasheets/3fg25/datasheet_3fg25_v1.3_en.pdf
  - https://www.zimmer-group.com/fileadmin/pim/MER/GD/PG/MER_GD_PG_GEH6180IL-03-B__SEN__APD__V1.pdf
  - https://www.zimmer-group.com/en/products/components/handling-technology/2-jaw-parallel-grippers/individualizations/hygienic-design
  - https://schunk.com/us/en/gripping-systems/parallel-gripper/pfh/pfh-150/p/000000000000302000
  - https://www.zimmer-group.com/en-us/products/components/handling-technology/2-jaw-parallel-grippers/series-gh6000/products/gh64100-b
  - https://robotiq.com/hubfs/Product-sheets/Adaptive%20Grippers/Product-sheet-Adaptive-Grippers-EN.pdf
  - https://www.universal-robots.com/media/1800257/rg6-gripper-datasheet.pdf
  - https://doi.org/10.1016/j.afres.2026.101880
---

# Arm and gripper parameters for the pork leg cell sim

Numbers for building a UR20, a FANUC SR-20iA and a long-stroke gripper in MuJoCo, and for the
two grasp modes on the 700 mm belt: (A) grasp the shank or trotter and lift, (B) grasp and
rotate the leg about its centre of gravity while the belt carries it. Candidate lists, washdown
ratings and the SCARA versus six-axis argument are in
[arm-selection-scara-vs-six-axis](../topics/arm-selection-scara-vs-six-axis.md) and are not
repeated. All pages and PDFs below were fetched 2026-09-14. Neither arm needed a substitute:
UR publishes UR20 kinematics and dynamics, and the SR-20iA link lengths follow from two
dimensions on FANUC's own datasheet drawing.

## 1. Universal Robots UR20

### DH parameters

From UR's [DH parameters for calculations of kinematics and dynamics](https://www.universal-robots.com/articles/ur/application-installation/dh-parameters-for-calculations-of-kinematics-and-dynamics/)
page, theta is the joint variable in every row.

| Joint | a [m] | d [m] | alpha [rad] |
|---|---|---|---|
| 1 | 0 | 0.2363 | pi/2 |
| 2 | -0.8620 | 0 | 0 |
| 3 | -0.7287 | 0 | 0 |
| 4 | 0 | 0.2010 | pi/2 |
| 5 | 0 | 0.1593 | -pi/2 |
| 6 | 0 | 0.1543 | 0 |

The page does not state whether this is standard (distal) or modified DH. Verify by comparing
forward kinematics against a pose read off the pendant before trusting the MJCF.

### Link masses, centres of mass and inertia

Same page. UR numbers the UR20 links 0 to 5 (the UR5e table on the same page uses 1 to 6). UR
describes each centre of mass as "an offset from the given joint frame for each corresponding
link". The inertia matrices are printed as 3x3 row-major lists with no unit and no statement of
whether they are about the centre of mass or the joint frame origin; kg m^2 about the CoM is the
reading consistent with the magnitudes (unverified).

| Link | Mass [kg] | CoM [m] | Inertia matrix, row-major |
|---|---|---|---|
| 0 | 16.343 | [0, -0.0610, 0.0062] | [0.0887, -0.0001, -0.0001, -0.0001, 0.0763, 0.0072, -0.0001, 0.0072, 0.0842] |
| 1 | 29.632 | [0.5226, 0, 0.2098] | [0.1467, 0.0002, -0.0516, 0.0002, 4.6659, 0.0000, -0.0516, 0.0000, 4.6348] |
| 2 | 7.879 | [0.3234, 0, 0.0604] | [0.0261, -0.0001, -0.0290, -0.0001, 0.7576, -0.0000, -0.0290, -0.0000, 0.7533] |
| 3 | 3.054 | [0, -0.0026, 0.0393] | [0.0056, -0.0000, -0.0000, -0.0000, 0.0054, 0.0004, -0.0000, 0.0004, 0.0040] |
| 4 | 3.126 | [0, 0.0024, 0.0379] | [0.0059, -0.0000, 0.0000, -0.0000, 0.0058, -0.0004, 0.0000, -0.0004, 0.0043] |
| 5 | 0.846 | [0, -0.0003, -0.0318] | [0.0009, 0.0000, 0.0000, 0.0000, 0.0009, 0.0000, 0.0000, 0.0000, 0.0012] |

The six link masses sum to 60.88 kg against the published 64 kg arm weight; the 3.1 kg difference
is unaccounted for on the page (base casing or cabling, unverified).

### Performance and limits

| Quantity | Value | Source |
|---|---|---|
| Rated payload | 20 kg | [techsheet](https://www.universal-robots.com/manuals/EN/TechSheets/UR20_techsheet_pdf_online/UR20_techsheet_en.pdf), [manual 2.1](https://www.universal-robots.com/manuals/EN/PDF/SW5_19/user-manual-UR20-PDF_online/718-818-00_UR20_User_Manual_en_Global.pdf) |
| Expanded payload | 25 kg, tool vertical down, CoG within the expanded curve | manual 2.2 |
| Payload versus CoG offset | full performance 20 kg to 200 mm offset, falling to 16 kg at 400 mm and 8 kg at 800 mm; expanded 25 kg to 200 mm, meeting the full curve at 400 mm (read off the chart, unverified to better than 1 kg) | manual 2.2, p. 18 |
| Reach | 1750 mm | techsheet |
| Arm mass | 64 kg without cable | techsheet, manual 2.1 |
| Pose repeatability | ±0.1 mm per ISO 9283 | techsheet |
| Joint ranges | ±360 deg, all six joints | techsheet |
| Max joint speed, base and shoulder | 120 deg/s (2.094 rad/s) | techsheet |
| Max joint speed, elbow | 150 deg/s (2.618 rad/s) | techsheet |
| Max joint speed, wrists 1 to 3 | 210 deg/s (3.665 rad/s) | techsheet |
| Max TCP speed | 5 m/s on the techsheet; "Approx. 2 m/s" in the SW 5.19 manual. The two UR documents disagree | techsheet, manual 2.1 |
| Flange F/T sensor range | ±200 N, ±20 N m | techsheet |
| Per-joint torque limits | not found. The manual says exceeding "the internal joint torque limit (each joint) results in a Cat 03" (read as a Category 0 stop with footnote 3) and that it "is not accessible to the user; it is a factory setting" | manual, safety function table |
| Base loads, normal operation | Mz 1850 N m, Fz 2750 N, Mxy 1890 N m, Fxy 1580 N | manual 7, stand dimensioning |
| Base loads, category 0/1/2 stop | Mz 2220 N m, Fz 3380 N, Mxy 2950 N m, Fxy 2120 N (UR: worst-case nominal times a safety factor of 2.5) | same |
| Allowable wrist inertia | not found. The manual says only that the controller "automatically adjusts accelerations" when payload mass, CoG and inertia are set | manual 2.2, p. 19 |
| Protection | arm IP65 | techsheet |

## 2. FANUC SR-20iA

### Link lengths

FANUC does not print J1 and J2 arm lengths as numbers. The work envelope drawing on the
[datasheet](https://www.fanucamerica.com/uploads/files/data-sheets/sr-20ia-datasheet.pdf) gives
R 1100 (outer J4 path), R 550 (on the J1-limit construction) and R 331 (inner J4 boundary). With
L1 + L2 = 1100 mm, the inner boundary at the J2 limit of 145 deg is

```
r_min = sqrt(L1^2 + L2^2 + 2 L1 L2 cos 145°)
      = sqrt(1100^2 - 2 L1 L2 (1 - cos 145°))
L1 = L2 = 550 mm  ->  r_min = 330.8 mm
```

The drawing's R 331 matches only L1 = L2 = 550 mm, because L1 L2 is fixed by r_min and a fixed
sum and product have one solution. Treat 550/550 as derived from FANUC's drawing, not as a FANUC
statement (unverified until checked against the mechanical unit manual). The same drawing gives
the base as 140 + 140 mm wide and 224 mm behind the J1 axis, and the forearm end as 197 mm wide.

### Specification

| Quantity | Value | Source |
|---|---|---|
| J1 / J2 arm length | 550 / 550 mm (derived above, unverified) | datasheet drawing |
| Reach | 1100 mm | datasheet |
| J1 range | ±145 deg | datasheet |
| J2 range | ±145 deg | datasheet |
| J3 (z) stroke | 300 mm, 450 mm option | datasheet |
| J4 range | ±720 deg | datasheet |
| J1 max speed | 440 deg/s | datasheet |
| J2 max speed | 500 deg/s | datasheet |
| J3 max speed | 2800 mm/s | datasheet |
| J4 max speed | 1700 deg/s | datasheet |
| Payload | 20 kg "max. load capacity at wrist"; no separate rated figure published | datasheet |
| J4 allowable moment | "-", which the datasheet legend defines as "not available" | datasheet |
| J4 allowable inertia | 0.45 kg m^2 | datasheet, [FANUC America page](https://www.fanucamerica.com/products/robot/sr-20ia) |
| Push force | 250 N | datasheet |
| Mechanical weight | 64 kg | datasheet |
| Repeatability | ±0.020 mm (J1, J2), ±0.01 mm (J3), ±0.005 deg (J4) | datasheet |
| Standard cycle time | not found | |
| Protection | IP20 body and wrist, footnote "IP65 Environmental option available" | datasheet, [FANUC EU page](https://www.fanuc.eu/eu-en/product/robot/sr-20ia) |
| Link masses, base height, flange height | not found | |

### Cross-check SCARA that publishes arm lengths

If the 550/550 derivation is rejected, Yamaha publishes arm lengths directly. From the
[YK1000XGP datasheet](https://global.yamaha-motor.com/business/robot/lineup/ykxg/proof/pdf/index/YK1000XGP_E_0707.pdf):
X arm 600 mm, Y arm 400 mm, rotation X ±130 deg, Y ±150 deg, R ±360 deg; Z stroke 200 or 400 mm;
maximum speed 10.6 m/s (XY resultant), Z 2.3 m/s (200 mm) or 1.7 m/s (400 mm), R 920 deg/s;
maximum payload 20 kg; R-axis tolerable moment of inertia 1.0 kg m^2; repeatability ±0.02 mm XY,
±0.01 mm Z, ±0.004 deg R; standard cycle 0.59 s with 2 kg on the 300 mm by 25 mm arch; weight
60 kg (Z 200) or 62 kg (Z 400); "Equivalent to IP65". Push force not found on that sheet.

## 3. Grippers for an 80 to 100 mm shank

Criteria from the brief: at least 120 mm stroke and more than 400 N grip force.

| Gripper | Type | Stroke | Grip force | Mass | IP | Food or hygienic variant | Source |
|---|---|---|---|---|---|---|---|
| Zimmer GEH6180IL-03-B | electric 2-jaw parallel, IO-Link, self-locking | 80 mm per jaw (160 mm total) | 150 to 1800 N nominal | 2.6 kg | IP54 | GEH6000IL is one of three series Zimmer offers in "hygienic design" individualization: FDA-compliant materials, IP40/IP54/IP65 | [datasheet](https://www.zimmer-group.com/fileadmin/pim/MER/GD/PG/MER_GD_PG_GEH6180IL-03-B__SEN__APD__V1.pdf), [hygienic design](https://www.zimmer-group.com/en/products/components/handling-technology/2-jaw-parallel-grippers/individualizations/hygienic-design) |
| OnRobot 3FG25 | electric 3-finger centric | external grip diameter 18 to 155 mm | 50 to 450 N | 1.6 kg | IP67 | none found | [datasheet v1.3](https://onrobot.com/storage/datasheets/3fg25/datasheet_3fg25_v1.3_en.pdf) |
| Schunk PFH 150 | pneumatic 2-finger parallel | 150 mm per jaw | 2120 N closing | 18.9 kg | IP30 | none found | [Schunk](https://schunk.com/us/en/gripping-systems/parallel-gripper/pfh/pfh-150/p/000000000000302000) |

Zimmer GEH6180IL detail: maximum finger length 160 mm, maximum finger mass 1 kg, 50 mm/s per jaw,
repeatability ±0.02 mm. Zimmer's force diagram "shows the arithmetic total of the individual
forces that occur on the gripper fingers", so 1800 N total is 900 N squeeze per jaw, and the
diagram derates force with finger length (the curve values were not transcribed). 3FG25 force-fit
payload 15 kg, form-fit 25 kg. The Schunk PFH 150 recommends 11.2 kg workpieces and is listed
here only to show the cost of long stroke plus high force in pneumatics: at 18.9 kg it leaves
1.1 kg of either arm's 20 kg for the leg. Zimmer's pneumatic GH64100-B (100 mm per jaw, 3200 N
closing, 14 kg, IP40, [Zimmer](https://www.zimmer-group.com/en-us/products/components/handling-technology/2-jaw-parallel-grippers/series-gh6000/products/gh64100-b))
fails the same way.

Comparison grippers that meet stroke but not force: Robotiq 2F-140, 140 mm, 10 to 125 N, 1 kg,
IP40, 2.5 kg friction payload ([product sheet](https://robotiq.com/hubfs/Product-sheets/Adaptive%20Grippers/Product-sheet-Adaptive-Grippers-EN.pdf));
OnRobot RG6, 0 to 160 mm, 25 to 120 N, 1 kg ([datasheet v1.6](https://www.universal-robots.com/media/1800257/rg6-gripper-datasheet.pdf),
IP rating not stated in that version).

The 3FG25 datasheet does not say whether 450 N is per finger or a total (not found); the
arithmetic below treats it as a total, the conservative reading.

## 4. Grip force needed

### Friction coefficients used

Belt 0.45 is the value given in the cell brief. No measured meat-on-belting coefficient exists in
the literature reviewed in [meat-piece-properties](../topics/meat-piece-properties.md) section 2.8,
so 0.45 has no primary source. Pad on wet meat 0.5 is an assumption. The nearest published number
is chicken fillet on stainless steel at 0.5, back-calculated from a simulation fit rather than
measured on a tribometer ([Vink et al. 2026](https://doi.org/10.1016/j.afres.2026.101880)). Wet
pad friction is likely lower, which raises every force below.

Common inputs: m = 11 kg, g = 9.81 m/s^2, W = m g = 107.9 N, L = 0.722 m, leg treated as a
slender body with uniform line load W/L on the belt. Jaws close horizontally across the shank,
pad normals horizontal. F is the squeeze on each jaw; the gripper rating to compare against is
2F (Zimmer convention above).

### (a) Rotate the leg on the belt about a vertical axis

Belt friction torque for a uniform line load rotating about a vertical axis at distance a and b
from the two ends:

```
T_belt = mu_b (W/L) (a^2 + b^2) / 2

through the CoG, a = b = L/2:   T_belt = mu_b W L / 4 = 0.45 x 107.9 x 0.722 / 4 = 8.76 N m
```

Two pads at radius r (half the shank diameter) slide tangentially when the leg yaws, so their
friction torque capacity is 2 mu_p F r:

```
F = T_belt / (2 mu_p r)
r = 0.040 m (80 mm shank):   F = 8.76 / (2 x 0.5 x 0.040) = 219 N  ->  2F = 438 N
r = 0.050 m (100 mm shank):  F = 8.76 / (2 x 0.5 x 0.050) = 175 N  ->  2F = 351 N
```

That is quasi-static. Angular acceleration adds I_cg alpha (I_cg = 0.478 kg m^2, section 5). At
an assumed alpha = 10 rad/s^2 that is 4.78 N m, adding 96 to 119 N per jaw, so 2F rises to 542 to
677 N.

The CoG of a real leg is in the ham, where the section is far wider than 100 mm, so a grasp near
the CoG is not a shank grasp. If the grasp stays on the shank 350 mm from the CoG (a = 0.711 m,
b = 0.011 m), the belt torque roughly doubles:

```
T_belt = 0.45 x (107.9 / 0.722) x (0.711^2 + 0.011^2) / 2 = 17.0 N m
r = 0.040 m:  F = 425 N  ->  2F = 850 N
r = 0.050 m:  F = 340 N  ->  2F = 680 N
```

The uniform line load understates this, because the real mass sits at the ham end, far from a
hock grasp (unverified until a leg is weighed and its CoG measured).

### (b) Hold the leg by the shank against gravity, CoG 350 mm from the grasp

Load at the grasp: shear W = 107.9 N and moment M = W d = 107.9 x 0.35 = 37.8 N m, about the
horizontal axis along the pad normal, so both are carried by pad friction. Model each pad as two
contact points s apart along the shank. Each of the four points carries W/4 of shear and M/(2s)
from the moment, and each point's friction capacity is mu_p F / 2:

```
mu_p F / 2 >= W/4 + M/(2 s)      ->      F >= (W/2 + M/s) / mu_p

s = 0.20 m:  F = (54.0 + 188.8) / 0.5 = 486 N  ->  2F =  971 N
s = 0.15 m:  F = (54.0 + 251.8) / 0.5 = 611 N  ->  2F = 1223 N
s = 0.10 m:  F = (54.0 + 377.7) / 0.5 = 863 N  ->  2F = 1727 N
```

Static, 1 g, no safety factor, no arm acceleration. The trotter is 150 to 200 mm long, which caps
s. Against the picks: the 3FG25 at 450 N fails every case; the GEH6180IL at 1800 N nominal clears
s = 100 mm by 4 percent before finger-length derating and any dynamic load, so it is marginal.

Turning the jaws so the pads bear on the top and bottom of the shank changes the mechanism: the
moment is then carried by a normal-force couple, F >= M/s, which is 378 N at s = 100 mm with no
dependence on pad friction, and only the shear W needs friction or a supporting lower pad
(inference for rigid pads, ignores tissue crush, unverified).

## 5. Wrist and J4 inertia check

Slender body of mass m and length L about a perpendicular axis:

```
through the CoG:                 I_cg   = m L^2 / 12 = 11 x 0.722^2 / 12 = 0.478 kg m^2
grasp 350 mm from the CoG:       I_hock = I_cg + m d^2 = 0.478 + 11 x 0.35^2 = 1.825 kg m^2
```

The gripper's own inertia about the same axis is excluded and adds to both.

| Axis | Allowable inertia | Ratio at CoG grasp (0.478) | Ratio at hock grasp (1.825) | Source |
|---|---|---|---|---|
| FANUC SR-20iA, J4 | 0.45 kg m^2 | 1.06, over | 4.06, over | [datasheet](https://www.fanucamerica.com/uploads/files/data-sheets/sr-20ia-datasheet.pdf) |
| Yamaha YK1000XGP, R | 1.0 kg m^2 | 0.48, within | 1.83, over | [datasheet](https://global.yamaha-motor.com/business/robot/lineup/ykxg/proof/pdf/index/YK1000XGP_E_0707.pdf) |
| FANUC M-20iD/25, J6 (reference) | 1.2 kg m^2 | 0.40, within | 1.52, over | [arm-selection note](../topics/arm-selection-scara-vs-six-axis.md) section 3 |
| UR20, wrist 3 | not found | n/a | n/a | [manual 2.2](https://www.universal-robots.com/manuals/EN/PDF/SW5_19/user-manual-UR20-PDF_online/718-818-00_UR20_User_Manual_en_Global.pdf) |

The SR-20iA is over its J4 limit even for a grasp through the CoG, which in mode (B) is the axis
it would use. UR gives no inertia ceiling; the binding UR20 constraint is the payload versus CoG
offset curve. With the GEH6180IL (2.6 kg) and the leg held at the hock, combined mass is 13.6 kg
and the horizontal CoG offset is 11 x 0.35 / 13.6 = 0.283 m before any vertical offset. The chart
reading in section 1 gives about 18 kg at 283 mm and about 16 kg at 400 mm, so 13.6 kg sits under
the full-performance curve (unverified, chart read by eye, vertical tool length not yet known).

## What I could not find

- UR20 per-joint torque limits. UR states they exist as a factory setting and does not publish
  them.
- UR20 allowable wrist inertia. Not published; the controller derates acceleration from the
  configured payload.
- Whether UR's DH table is standard or modified convention, and the units and reference point of
  the printed inertia matrices. Not stated on the page.
- UR20 maximum TCP speed. The techsheet says 5 m/s and the SW 5.19 manual says approx. 2 m/s.
- SR-20iA J1 and J2 arm lengths as stated numbers (derived as 550/550 above), link masses, base
  and flange heights, J4 allowable moment, rated (as opposed to maximum) payload, and standard
  cycle time. The FANUC EU flyer PDF returned HTTP 410.
- A measured friction coefficient for pork on belting or on gripper pads, wet or dry.
- Grip force convention (per finger or total) for the OnRobot 3FG25 and Schunk PFH.
- IP rating in the RG6 datasheet v1.6.
- A food-grade variant of the 3FG25 or PFH 150.
