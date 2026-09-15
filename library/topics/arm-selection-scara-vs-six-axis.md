---
title: "Arm selection for the pork leg station: SCARA versus six-axis"
date: 2026-09-11
tags: [topic, hardware, robot-arm, scara, six-axis, washdown, meat-cell, selection]
status: draft
source: vendor datasheets and product pages (links inline), standards and papers cited
---

# Arm selection for the pork leg station: SCARA versus six-axis

## The question this note answers

The station handles whole bone-in pork legs on a white modular plastic belt in a chilled
washdown pork plant. IMPS item 401 (Pork Leg) weight class B is 20 to 28 lb, 9.1 to 12.7 kg,
and class C is 28 lb and up ([USDA AMS IMPS Fresh Pork Series
400](https://www.ams.usda.gov/sites/default/files/media/IMPS_400_Fresh_Pork%5B1%5D.pdf),
weight-range table, converted at 1 lb = 0.4536 kg). The piece is roughly 700 to 900 mm long
(cell brief; no measured population study for pork leg dimensions exists, see
[meat-piece-properties](meat-piece-properties.md) section 1), with mass concentrated at the ham
end and tapering through the hock to the trotter.

The station has not been defined yet. It either ORIENTS the piece in the belt plane so the
cutter receives it correctly, or it PICKS it and places it. The arm choice follows from that
definition, and the two candidate definitions do not select the same arm.

The short answer, defended below:

1. If the station picks the piece up at all, a SCARA is out. Not on payload, which two or three
   SCARAs have, and not on reach, which several have. It is out on allowable wrist inertia,
   where the gap is a factor of tens rather than a margin, and on the wash, where the best rating
   in the whole SCARA market is IP65.
2. If the station orients the piece by pushing, the arm class is the wrong argument to be having.
   A nominally identical 150 mm push of a rigid steel block on a flat manufactured plate, repeated
   2000 times under Vicon by an industrial robot, lands with a standard deviation of 3.4 to
   11.7 mm and 1.3 to 4.5 degrees depending only on the plate material (section 4). Point-pushing
   a deformable piece over a wet belt will not beat that, and no arm fixes it. A line contact
   pushed against a mechanical datum does, and then the cheapest mechanism that can execute it
   wins, which is probably not an arm of either kind.
3. If any part of the piece has to reach the cutter tilted out of the belt plane, the SCARA
   cannot do it with any gripper, because it has no axis that produces the motion.

There is also a precedent worth knowing before the argument starts. Mayekawa's CELLDAS pork
deboning cell uses three Stäubli six-axis robots, TX2-60 HE and TX2-90 HE, two of them
"responsible for handling and positioning the pieces of pork" and the third carrying the knife,
with 3D scanning and X-ray upstream, taking "about 40 seconds to debone the hip bone and
tailbone of a pork leg"
([Stäubli, Deboning pork with robots and AI](https://www.staubli.com/global/en/robotics/industries/food/protein-processing/deboning-of-pork.html)).
The only publicly documented cell doing this exact job on this exact product uses six-axis arms
for the handling role, not the cutting role alone.

---

## 1. The kinematic difference, stated precisely

A SCARA has four joints: two revolute joints whose axes are vertical and parallel (shoulder and
elbow), one prismatic joint along the vertical (Z), and one revolute joint about the vertical at
the tool (R). Every joint axis is parallel to the base z axis. The forward kinematics map into a
four-dimensional subset of SE(3): position (x, y, z) and yaw. The tool z axis points along the
base z axis in every configuration the arm can reach. There is no configuration in which the
tool tilts.

The reachable set is a cylinder: an annulus in the horizontal plane bounded inside by
|L1 - L2| and outside by L1 + L2, swept over the Z stroke, with yaw free within the R-axis
range. Vertical travel on a SCARA is one to four hundred millimetres, not a metre: Stäubli TS2,
200 mm with a 400 mm option; Epson G20, 180 or 420 mm; Yamaha YK-XG, 200 or 400 mm. That is a
workspace fact before it is a payload fact, and it matters if the cutter infeed is at a different
height from the belt.

A six-axis arm reaches a six-dimensional neighbourhood of SE(3) within its joint limits. Every
tool orientation is available somewhere in the workspace, at the cost of singularities, a larger
footprint, and a heavier machine for the same payload: FANUC's 20 kg SCARA SR-20iA weighs 64 kg,
its 25 kg six-axis M-20iD/25 weighs 250 kg
([SR-20iA](https://www.fanucamerica.com/products/robots/series/scara/sr-20ia),
[M-20iD/25](https://www.fanucamerica.com/products/robots/series/m-20/m-20id-25)).

### What "selective compliance" actually meant

SCARA is Makino's acronym and it expands to Selective Compliance Assembly Robot Arm. The
"Articulated Robot Arm" expansion in circulation is a later misreading; Makino's own retrospective
uses "Assembly" throughout. The first prototype was built at the University of Yamanashi in
October 1978, the second in May 1980, and five manufacturers began selling SCARA-type robots in
1981 ([Makino, "Development of the SCARA", J. Robotics and Mechatronics 26(1):5-8, 2014, CC
BY-ND](https://doi.org/10.20965/jrm.2014.p0005),
[full text](https://www.jstage.jst.go.jp/article/jrobomech/26/1/26_5/_pdf/-char/en)). The
contemporaneous papers are Makino and Furuya, "Selective compliance assembly robot arm", Proc.
1st Int. Conf. on Assembly Automation, Brighton, pp. 77-86, 1980 (cited as reference [1] of the
2014 retrospective; the conference paper itself was not obtained, **unverified**), and Furuya and
Makino, "Research and Development of Selective Compliance Assembly Robot Arm (1st Report)",
J. Japan Society of Precision Engineering, 1980
([DOI 10.2493/jjspe1933.46.1525](https://doi.org/10.2493/jjspe1933.46.1525)), with a 2nd Report
in 1983 ([DOI 10.2493/jjspe1933.49.835](https://doi.org/10.2493/jjspe1933.49.835)).

Makino states the design requirement directly. For vertical peg-in-hole assembly to succeed,
"the compliance of the peg holder should differ with the direction: large compliance for
horizontal force, small compliance for vertical force, large rotational compliance about the
vertical axis, small rotational compliance about the horizontal axes"
([Makino 2014](https://doi.org/10.20965/jrm.2014.p0005)). His own analogy in the same paper is a
byōbu, a Japanese folding screen, which moves easily in one direction and is stiff in the other.

The SCARA geometry delivers all four by construction. A vertical force at the tool is carried by
the ball screw or ball spline in compression and by the shoulder and elbow bearings axially, with
no joint torque resisting it: a short, stiff load path. A horizontal force is carried entirely by
joint torque at the shoulder and elbow through their gear trains, so tool deflection is
`dx = J K_theta^-1 J^T f` with `K_theta` the joint torsional stiffnesses, and both the gear-train
compliance and the long moment arm from joint to tool appear here and nowhere in the vertical
path. Rotation about the vertical is one motor through one reducer, compliant. Rotation about a
horizontal axis is resisted by structure and bearings rather than by any actuator, stiff.

So the anisotropy is structural and not a naming convention, and it is compliant in exactly the
plane in which this station's loads act if the task is pushing.

### The honest limit of that argument

The anisotropy is real; its size is not on any datasheet. No SCARA and no six-axis arm reached in
this pass published a Cartesian stiffness in N/mm or a joint stiffness in Nm/deg, including
Epson's full specifications catalog, which lists payload, repeatability, allowable moment of
inertia and downward force per joint and never stiffness. Repeatability is not stiffness: ISO 9283
defines pose accuracy and pose repeatability at maximum speed and maximum payload, and no static
compliance characteristic appears in its described scope. No ISO standard defining a
static-stiffness test for industrial manipulators was located (iso.org blocks automated access;
**unverified** either way).

The nearest number is academic. Klimchik et al. identified joint elastostatic parameters of a KUKA
KR-270 under 250 to 280 kg of applied end load tracked by laser tracker, reporting per-joint
compliances of 0.302, 0.406, 3.002, 3.303 and 2.365 rad um/N for joints 2 to 6 plus 0.144 for the
compensator, identification errors 1.3 to 4.9 percent
([arXiv:1311.6810](https://arxiv.org/abs/1311.6810), ICRA 2013, Table IV). That is a virtual-joint
compliance on a 270 kg six-axis machine, so it does not transfer to a SCARA, and no equivalent
measurement for any SCARA exists.

So "a SCARA is compliant in the plane of your loads" is true, is unquantified by any public data,
and is therefore not the argument that decides this station. Two datasheet facts decide it: the
absence of a tilt axis (section 6) and the allowable wrist inertia (section 3). If the station
pushes, arm deflection under the push force belongs in the acceptance test, not in an assumption.

---

## 2. Hardware that can work in a chilled washdown pork plant

Standards, food-contact regulation and the IP69K test conditions for this cell are in
[meat-cutting-automation](meat-cutting-automation.md) and are not repeated. IP69K's current home
is ISO 20653:2023, which absorbed DIN 40050-9
([ISO catalogue entry](https://www.iso.org/standard/76116.html)).

### Six-axis, food and hygienic variants

| Arm | Payload | Reach | Protection | Food-grade details | Source |
|---|---|---|---|---|---|
| Stäubli TX2-60 / 60L HE | 4.5 / 3.7 kg | 670 / 920 mm | IP65, IP67 with the pressurized version | NSF H1 food oil, stainless joints, EHEDG-aligned | [Stäubli HE range](https://www.staubli.com/global/en/robotics/products/industrial-robots/hygienic-humid.html) |
| Stäubli TX2-90 / 90L / 90XL HE | 14 / 12 / 7 kg | 1000 / 1200 / 1450 mm | same | same | same |
| Stäubli TX2-140 HE | 40 kg | 1510 mm | same | same | same |
| Stäubli TX2-160 / 160L HE | 40 / 25 kg | 1710 / 2010 mm | same | same | same |
| Stäubli TX2-200 / 200L HE | 170 / 110 kg | 2209 / 2609 mm | same | same | same |
| FANUC M-20iD/25, Food Grade Option | 25 kg | 1831 mm | body IP54 standard, IP65 option; wrist and J3 arm IP67 | Option named on the page; lubricant not named | [FANUC](https://www.fanucamerica.com/products/robots/series/m-20/m-20id-25) |
| FANUC M-710iC/50 food variant | 50 kg | 2050 mm | body IP54 standard, IP67 option; wrist and J3 arm IP67 | Epoxy-coated white body, food-grade grease | [FANUC](https://www.fanucamerica.com/products/robot/m-710ic-50) |
| FANUC CRX-10iA Food Grade (cobot) | 10 kg | 1249 mm | IP67 body, wrist and J3 arm | NSF H1 grease, white epoxy paint, rust and chemical resistant plating | [FANUC](https://www.fanucamerica.com/products/robot/crx-10ia-food-grade) |
| FANUC CRX-30iA Food Grade (cobot) | 30 kg | 1889 mm | IP67 body, wrist and J3 arm | same | [FANUC](https://www.fanucamerica.com/products/robot/crx-30ia-food-grade) |
| FANUC LR Mate 200iD/7LC | 7 kg | 911 mm | IP67 standard, IP69K option "for hot high pressure cleaning" | Lubricant not stated | [FANUC](https://www.fanucamerica.com/products/robot/lr-mate-200id-7lc) |
| KUKA KR AGILUS HM | 6 to 11 kg | 726 to 1101 mm | IP65, IP67 (KR 10 R1100 HM-SC) | Corrosion-resistant surfaces, food-compatible lubricants, stainless parts, direct foodstuff contact | [KR AGILUS](https://www.kuka.com/en-de/products/robot-systems/industrial-robots/kr-agilus), [meat processing](https://www.kuka.com/en-us/industries/consumer-goods-industry/meat-processing-automation) |
| KUKA KR CYBERTECH HO (KR 20 R1810 HO) | 10 to 20 kg total load | up to 2013 mm | IP65, IP67 | Listed under "Version environment: Food" | [KR CYBERTECH](https://www.kuka.com/en-de/products/robot-systems/industrial-robots/kr-cybertech) |
| KUKA KR IONTEC HO (KR 50 R2100 HO) | 50 kg total load | 2101 mm | IP65, IP67 | same | [KR IONTEC](https://www.kuka.com/en-de/products/robot-systems/industrial-robots/kr-iontec) |
| KUKA KR QUANTEC HO | 120 to 240 kg total load | 2700 to 3100 mm | up to IP67 | same | [KR QUANTEC](https://www.kuka.com/en-de/products/robot-systems/industrial-robots/kr-quantec) |
| ABB IRB 2600 | 12 kg at 1.65 and 1.85 m, 20 kg at 1.65 m | 1650 / 1850 mm | IP67 standard, Foundry Plus 2 option | No NSF H1 claim found on the product page | [ABB IRB 2600](https://web.archive.org/web/2024/https://new.abb.com/products/robotics/robots/articulated-robots/irb-2600) |
| ABB IRB 1300 | up to 11 kg | up to 1400 mm | IP67, Foundry Plus 2, ISO 4 cleanroom | Food and beverage named as a target industry; no lubricant claim found | [ABB IRB 1300](https://web.archive.org/web/2024/https://new.abb.com/products/robotics/robots/articulated-robots/irb-1300) |
| Universal Robots UR20 | 20 kg | 1750 mm | IP65 and cleanroom | No food-grade lubricant claim | [UR20](https://www.universal-robots.com/products/ur20-robot/) |

KUKA's "total load" is payload plus supplementary load, not flange payload. Read the load diagram
before sizing against it.

Three reality checks. Almost nothing here is IP69K: the only explicit primary-source IP69K claim
on a six-axis arm found in this pass is FANUC's LR Mate 200iD/7LC, a 7 kg machine, and Stäubli,
the vendor with the deepest food record, claims IP65 with IP67 on the pressurized version and no
IP69K anywhere on its own product pages. The industry's working answer is IP67 plus NSF H1 grease
plus epoxy or stainless surfaces. Whether that is acceptable is the plant QA's call, and it should
be asked before the arm list is drawn.

Yaskawa could not be verified: the model names in circulation (MPK2F, MPK50, MH12, HP20F, MH24) do
not appear on the current Motoman site, whose catalogue is organised around GP, HC, NEX, PL, SG and
MPP families, and the food and beverage campaign page names software rather than robots. Open item,
not an absence.

Price bands are **not found**. No vendor publishes a list price for any arm in this table and every
distributor site tried returned HTTP 403. The integrator quote is the only route.

### What Stäubli claims for the HE range, in its own words

Hygienic design aligned with EHEDG recommendations; NSF H1 compliant food oil "with no loss of
performance"; "no micro organic penetration due to design and pressurization"; fully encapsulated
design up to IP65/67; integrated user harness, tubing and valves with all connections protected
under the base; "unrestricted pH suitability from 4.5 to 8.5 (with validation from 2 to 12
feasible)"; kinematic pressurization; stainless steel joints
([source](https://www.staubli.com/global/en/robotics/products/industrial-robots/hygienic-humid.html)).
The pH range is the most useful number on that page, because it is the one the plant's sanitation
chemistry actually has to satisfy. Get the caustic and acid SDS pH values from the plant before
accepting it.

Beyond the CELLDAS cell, Stäubli cites a Tyrolean cheese dairy running a TX2-90 HE for derinding
"in an environment subject to washing by high-pressure lance", with intensive basic cleaning at
least twice a week
([Stäubli](https://www.staubli.com/global/en/robotics/industries/food/dairy-products/automated-derinding-of-cheese.html)).
Both are vendor marketing, so treat the survival claims as claims; they are still the closest
public evidence that a pressurized IP65/IP67 six-axis arm lives in a wet protein plant.

The Mayekawa page also names a selection criterion no datasheet line captures: the knife "can
unexpectedly hit bones in the meat, become jammed in the bone, and suddenly release", so "strong
and irregular torques are exerted on the drivetrain", and the gears must carry them. A station
that grips a bone-in leg and swings it has a milder version of the same problem, and drivetrain
torque reserve is not published as a number by anyone.

### SCARA, washdown and food variants

| Arm | Payload rated / max | Reach | R-axis allowable inertia, rated / max | Protection | Source |
|---|---|---|---|---|---|
| Stäubli TS2-40 / 60 / 80 / 100 (incl. HE) | 8.4 kg max, all four | 460 / 620 / 800 / 1000 mm | not published | IP65 | [Stäubli HE range](https://www.staubli.com/global/en/robotics/products/industrial-robots/hygienic-humid.html) |
| FANUC SR-6iA | 6 kg | 650 mm | 0.12 kg m2 (J4, max) | IP20 body and wrist | [datasheet](https://www.fanucamerica.com/uploads/files/data-sheets/sr-6ia-datasheet.pdf) |
| FANUC SR-12iA | 12 kg | 900 mm | 0.3 kg m2 (J4, max) | IP20 body and wrist | [datasheet](https://www.fanucamerica.com/uploads/files/data-sheets/sr-12ia-datasheet.pdf) |
| FANUC SR-20iA | 20 kg | 1100 mm | 0.45 kg m2 (J4, max) | IP20, footnoted "IP65 Environmental option available" | [datasheet](https://www.fanucamerica.com/uploads/files/data-sheets/sr-20ia-datasheet.pdf) |
| Denso HM-40x0 | 10 kg | 600 to 1000 mm | 0.25 kg m2 | IP65 dust and mist proof configuration available | [Denso HM series](https://www.densorobotics.com/products/4-axis/hm-series/) |
| Denso HM-4Ax0 | 20 kg | 600 to 1000 mm | 0.45 kg m2 | IP65 dust and mist proof configuration available | same |
| Epson G20-A0x | 10 / 20 kg | 1000 mm | 0.050 / 0.450 kg m2 | Standard, ISO 3 cleanroom, or "Protected IP54 and IP65" | [Epson specifications catalog](https://mediaserver.goepson.com/ImConvServlet/imconv/1e573dc9fbf44d823b1007ebbc2787dda394783d/original?assetDescr=Epson_Robots_Specifications_Catalog_CPD-54833R4_FInal_NoCrop.pdf) |
| Epson LS20-BA04 | 10 / 20 kg | 1000 mm | 0.050 / 1.000 kg m2 | Standard or ISO 4 cleanroom only, no IP option listed | same |
| Yamaha YK500XGP | 10 kg max | 500 mm | 0.3 kg m2 | "Equivalent to IP65 (IEC 60529)" | [datasheet](https://global.yamaha-motor.com/business/robot/lineup/ykxg/proof/pdf/index/YK500XGP_E_0707.pdf) |
| Yamaha YK700XGP | 20 kg max | 700 mm | 1.0 kg m2 | "Equivalent to IP65" | [datasheet](https://global.yamaha-motor.com/business/robot/lineup/ykxg/proof/pdf/index/YK700XGP_E_0707.pdf) |
| Yamaha YK1000XGP | 20 kg max | 1000 mm | 1.0 kg m2 | "Equivalent to IP65" | [datasheet](https://global.yamaha-motor.com/business/robot/lineup/ykxg/proof/pdf/index/YK1000XGP_E_0707.pdf) |
| Yamaha YK1200X | 50 kg max | 1200 mm | 2.45 kg m2 | no protection rating claimed | [datasheet](https://global.yamaha-motor.com/business/robot/lineup/ykxg/large/pdf/index/yk1200x.pdf) |

FANUC's SCARA range page states that "select models feature a white coating and waterproof IP65
rating" for food handling and secondary food packaging
([FANUC SCARA series](https://www.fanucamerica.com/products/robots/series/scara)). The model
datasheets make the split explicit: every SR is IP20 as built, and the SR-20iA sheet carries the
footnote "IP65 Environmental option available". FANUC's separate food and clean "/C" SCARA
variants (SR-3iA/C, SR-6iA/C, SR-12iA/C) are IP54 with white epoxy coating, food-grade grease and
ISO Class 5 cleanroom rating, and they stop at 12 kg
([FANUC EU SCARA filter page](https://www.fanuc.eu/at/en/robots/robot-filter-page/scara-series)).
So FANUC's actual food SCARA is IP54 at 12 kg, and its 20 kg machine gets a generic environmental
IP65, not a food package. Ask which of the two the quote is for.

### How thin this market is above 10 kg

Counting only SCARAs with a published protection rating better than IP20, the entire field above
10 kg payload clusters at exactly one number, 20 kg, across four independent vendors:

- Denso HM-4Ax0, 20 kg, IP65 dust and mist proof configuration, 0.45 kg m2 allowable inertia.
- FANUC SR-20iA, 20 kg, IP65 environmental option, 0.45 kg m2.
- Epson G20, 20 kg maximum payload, "Protected IP54 and IP65" listed at platform level. No
  distinct IP65 SKU was found at the 20 kg size, only standard and cleanroom, so the availability
  of IP65 at full payload is **unverified**.
- Yamaha YK1000XGP, 20 kg, "equivalent to IP65", 1.0 kg m2.

Above 20 kg the protection ratings stop entirely. Yamaha's YK1200X is 50 kg and carries no IP
rating at all. The clustering is not coincidence: bigger arms need bigger bellows and heavier
gearing, so vendors either cap payload at 5 to 12 kg with a food coating (FANUC /C, Denso HS-A1)
or cap the whole washdown line at 20 kg.

Nothing in the SCARA market is IP69K, and nothing is IP67. Every washdown claim in the class is
IP65 or a vendor's own paraphrase of it.

Stäubli, whose SCARA the only public robotic meat cells use (two TS2-60 HE in JBT Marel's DSI
Dual Robotic Harvester, see [meat-cutting-automation](meat-cutting-automation.md)), caps its
entire TS2 line at 8.4 kg at every one of its four reaches. The food-grade SCARA the industry
actually deploys cannot lift one pork leg.

The Yamaha datasheet carries the sentence that settles this for a meat plant: "Do not use robots
where the bellows section is directly exposed to water jet"
([YK1000XGP, Note 4](https://global.yamaha-motor.com/business/robot/lineup/ykxg/proof/pdf/index/YK1000XGP_E_0707.pdf)).
A pork plant's sanitation crew cleans with a directed jet, twice a shift. An IP65-equivalent SCARA
whose vendor excludes water jets on the bellows needs an enclosure, and an enclosure around a
SCARA removes the footprint advantage that was the reason to consider one.

### Delta and parallel robots

The delta payload ceiling is higher than the reputation suggests, and the hygiene ratings are the
best in this note.

| Robot | Payload | Reach | Axes | Protection | Source |
|---|---|---|---|---|---|
| ABB IRB 360-1/800, -1/1130, -3/1130, -8/1130, -1/1600, -6/1600 | 1 to 8 kg | 800 to 1600 mm | 4 | IP54 standard; IP67 Wash-Down; IP69K Wash-Down Stainless (option 3328-3) | [ABB product specification 3HAC079010-001](https://search.abb.com/library/Download.aspx?DocumentID=3HAC079010-001&LanguageCode=en&Action=Launch) |
| FANUC M-2iA/6HL | 6 kg | 1130 mm | 6 | IP69K body and wrist | [datasheet](https://www.fanucamerica.com/uploads/files/data-sheets/m-2ia-6hl-datasheet.pdf) |
| FANUC M-3iA/12H | 12 kg | 1350 mm (envelope ø1350 x 500 mm) | 3 | IP67 body and wrist | [datasheet](https://www.fanucamerica.com/uploads/files/data-sheets/m-3ia-12h-datasheet.pdf) |
| Codian D4-1600-HD041 and HD siblings | 20 kg | 1600 mm, working area 1600 x 550 mm | 4 | IP69K, FDA-compliant materials | [Codian HD series](https://codian-robotics.com/robots/hd-series/), [D4-1600-HD041](https://codian-robotics.com/blog/producten/d4-1600-hd041-3/) |
| Penta Veloce | 10 kg | 1400 to 2200 mm working diameter | 4 | IP65/IP67, hygienic design | [archived spec sheet](https://web.archive.org/web/2020id_/http://pentarobotics.com/wp-content/uploads/2018/05/Spec_sheet_Veloce_A4-2.pdf) (pentarobotics.com is a dead domain) |
| Yaskawa MPP3H / MPP3S | 3 kg | ø800 to 1300 mm | 4 | IP67, NSF H1 food-grade lubricants, anti-corrosive coating | [datasheet](https://www.motoman.com/getmedia/88ea7ba5-a4d6-48e5-b5c4-83058daa62e3/MPP3H_MPP3S.pdf.aspx) |
| FANUC DR-3iB/6 STAINLESS, M-2iA; KUKA KR DELTA HM | 6 kg | 1200 to 1350 mm | 4 | IP69K (KUKA: IP67 body, IP69K axis 4 only) | [meat-cutting-automation](meat-cutting-automation.md) |

So payload is not the disqualifier. Codian's hygienic D4 carries 20 kg at IP69K with FDA-compliant
materials, more payload at a better protection rating than any SCARA or six-axis arm in this note.
Three other things rule the delta out. **Degrees of freedom**: the four-axis delta has the same
four as a SCARA and the same inability to tilt, and the 12 kg FANUC M-3iA/12H is worse, a
three-axis hollow-wrist machine that cannot even yaw the piece; Codian's D5 adds rotate and tilt
at 35 kg but states no washdown rating, so its food status is **unverified**. **Envelope**:
Codian's D4-1600 working area is 1600 x 550 mm and FANUC's M-3iA/12H is ø1350 x 500 mm, a shallow
dome over the belt, right for a transfer and wrong for reaching into a cutter infeed. **Inertia**:
the architecture exists to move small masses fast on a light end plate, and none of these
datasheets publishes a wrist inertia limit at all (**not found**), which is itself the answer
about what the machine is for.

### Gantry and cartesian

Food plants run far more linear axes than arms, and a gantry is the option most often skipped in
an arm-versus-arm argument. A cartesian machine decouples the three translations, so payload is a
beam and bearing sizing problem rather than a cantilever moment problem. Vertical stroke is
whatever you build, the footprint is a frame over the belt rather than a pedestal beside it, and
the wet-zone parts can be a sealed rail and a bellows-covered screw with the motors outside the
zone.

**Macron Dynamics MSS-R20**, a stainless washdown linear actuator, is the one catalogue product
found with both an IP69K rating and full numbers: sealed FDA belt, stainless steel I-beam, maximum
speed 3000 mm/s horizontal and vertical, maximum load 500 lb (227 kg) horizontal and 250 lb
(113 kg) vertical, repeatability ±0.025 mm, positional accuracy ±0.4 mm/m, moment load 248 N m,
maximum acceleration 5 g, system mass (travel in metres x 32.79) + 10.02 kg
([Macron](https://www.macrondynamics.com/products/mss-r20/)). One axis of it carries 13 times the
flange load section 3 computed, at a protection rating no arm in this note reaches.

**Güdel** rates gantry payload as force: FP-3 at 300, 500 or 800 N depending on speed tier (150,
112.5 or 75 m/min), up to FP-7 at 12,500 to 31,250 N, repeatability ±0.02 mm
([FP](https://www.gudel.com/products/linearaxis/fp)); TrackMotion rails run 12,000 N (TMF-1) to
200,000 N (TMF-6) ([TMF](https://www.gudel.com/products/linear-tracks-for-robots/tmf)). No IP
rating is published for either line and no hygienic Güdel gantry was found. **Rollon** sells
stainless corrosion-resistant ELM and ROBOT actuators, repeatability ±0.05 mm on ELM PLUS CR,
strokes to 6000 mm, marketed at "meat, fish, dairy, and baked goods processing"
([food page](https://www.rollon.com/usa/en/your-challenges/linear-motion-food-processing/),
[ELM CR](https://my.rollon.com/corp/en/product/elm-cr/)); payload, speed and IP live behind a
JavaScript configurator and were **not obtained**. Bosch Rexroth and Festo, both hygienic linear
suppliers, were unreachable in this pass, which is a research gap and not an absence.

The trade is degrees of freedom: a three-axis gantry with a rotating wrist is kinematically the
same four degrees of freedom as a SCARA, with a far larger envelope and far more payload and still
no tilt, and adding tilt means adding an axis. But if the station turns out to be "push a line
contact against a datum", two stainless IP69K linear axes and a paddle beat both arm classes on
hygiene, payload and price, and should be priced before either arm.

---

## 3. Payload arithmetic, and why inertia binds long before mass does

### The mass

Rated payload has to cover the gripper plus the product plus whatever the vendor's load diagram
says about where their combined centre of gravity sits. Taking the worst of IMPS class B:

```
product          12.7 kg   (IMPS 401 class B upper bound)
gripper           4.0 kg   (design input, not yet chosen; a washdown gripper that
                            holds a 13 kg bone-in leg is not a 1 kg part)
------------------------
flange load       16.7 kg
```

That alone eliminates every Stäubli TS2 (8.4 kg) and every FANUC SR below the SR-20iA. It leaves
the FANUC SR-20iA, Epson G20 and Yamaha YK700/1000XGP at 20 kg maximum with 3.3 kg of headroom,
which is thin once a camera, a valve pack or a wash shroud goes on the flange. On the six-axis
side it is comfortable: FANUC M-20iD/25 at 25 kg, KUKA KR 20 R1810 HO at 20 kg total load,
Stäubli TX2-90 HE at 14 kg (tight), TX2-140 HE at 40 kg.

### The inertia, which is the number that actually decides

Every SCARA R axis and every six-axis wrist axis carries a published allowable moment of inertia.
The load's inertia about that axis, not its mass, limits acceleration. Model the leg as a uniform
slender rod of length L and mass m, which is a lower bound for a piece whose mass concentrates at
the ham end:

```
about its own centre          I = m L^2 / 12
 9.1 kg, 0.7 m   ->  0.37 kg m^2
12.7 kg, 0.9 m   ->  0.86 kg m^2

about one end                 I = m L^2 / 3
 9.1 kg, 0.7 m   ->  1.49 kg m^2
12.7 kg, 0.9 m   ->  3.43 kg m^2

grasped at the hock, about 0.2 L from the end, CoM at mid-length
                              I = m L^2 (1/12 + 0.09)
12.7 kg, 0.9 m   ->  1.78 kg m^2
```

Vendors publish the allowable inertia in two tiers, and the distinction is the whole story. Epson
prints both: for the G20 at 1000 mm, Joint #4 allowable moment of inertia is 0.050 kg m2 RATED and
0.450 kg m2 MAXIMUM; for the LS20-BA04, 0.050 rated and 1.000 maximum
([Epson specifications catalog](https://mediaserver.goepson.com/ImConvServlet/imconv/1e573dc9fbf44d823b1007ebbc2787dda394783d/original?assetDescr=Epson_Robots_Specifications_Catalog_CPD-54833R4_FInal_NoCrop.pdf)).
Rated is where the robot runs at its published speed. Maximum is where it still runs, derated.
FANUC and Yamaha publish only the upper figure, so the numbers below compare against the most
generous interpretation of each machine.

| Axis | Allowable inertia | vs 1.78 kg m2 (hock grasp, 12.7 kg, 0.9 m) | vs 3.43 kg m2 (end grasp) |
|---|---|---|---|
| Epson G20, J4 rated | 0.050 kg m2 | 36x over | 69x over |
| FANUC SR-20iA, J4 | 0.45 kg m2 | 4.0x over | 7.6x over |
| Epson G20, J4 maximum | 0.450 kg m2 | 4.0x over | 7.6x over |
| Yamaha YK1000XGP, R | 1.0 kg m2 | 1.8x over | 3.4x over |
| Epson LS20-BA04, J4 maximum | 1.000 kg m2 | 1.8x over | 3.4x over |
| Yamaha YK1200X, R | 2.45 kg m2 | within | 1.4x over |
| FANUC M-20iD/25, J4 and J5 | 2.4 kg m2 | within | 1.4x over |
| FANUC M-20iD/25, J6 | 1.2 kg m2 | 1.5x over | 2.9x over |

Three conclusions come straight off that table. A SCARA that can carry the leg's mass cannot
rotate it about its wrist near the hock, which is exactly the motion "orient by grasp-and-pivot"
asks for, and it is over by a factor rather than a margin. The six-axis arm has roughly five
times the allowable wrist inertia at a comparable payload, which is the concrete form of "more
machine for the same payload". And on either machine the grasp geometry decides the outcome: hold
the leg near its centre of mass and the inertia drops by a factor of five.

The real leg is worse than the rod model for a hock grasp, because the ham end carries more mass,
so the lever arm from a hock grasp to the centre of mass exceeds 0.3 L. Get the centre of mass
from a weighed, measured sample before committing to a grasp point.

Epson also prints the qualification that catches people out: those inertia figures hold "when
payload center of gravity is aligned with Joint #4; if not aligned with Joint #4, set parameters
using the INERTIA command" (same catalog). A 900 mm leg held off-axis is precisely the case the
footnote is warning about, and the controller cannot apply the correction unless you give it the
numbers.

### How derating actually works

Two vendors state the mechanism rather than publishing a curve.

Yamaha, on every XG-series datasheet: "The acceleration coefficient is set automatically in
accordance with the tip weight and R-axis moment of inertia settings" (Note 3,
[YK1000XGP](https://global.yamaha-motor.com/business/robot/lineup/ykxg/proof/pdf/index/YK1000XGP_E_0707.pdf)).
The controller derates you; the datasheet does not say by how much.

FANUC publishes the limit rather than the derating: a moment in N m and an inertia in kg m2 per
wrist axis, which the motion planner respects. M-20iD/25 is 52 N m and 2.4 kg m2 on J4 and J5,
32 N m and 1.2 kg m2 on J6
([M-20iD/25](https://www.fanucamerica.com/products/robots/series/m-20/m-20id-25)).

Only one vendor publishes the derating itself: ABB's IRB 360 product specification tabulates picks
per minute at three payloads on a fixed cycle, and it costs 37.5 percent of the rate to go from
1 kg to the rated 8 kg on the same machine. That table is in section 5, and it is the only
published payload-versus-throughput curve found in this pass. No six-axis load diagram (payload
against centre-of-gravity offset) was obtained (**not found**; ABB, KUKA and Stäubli articulated-arm
datasheet PDFs were unreachable behind WAFs and login walls). The practical consequence is the
same either way: a datasheet cycle time is not this station's cycle time, and the only route to a
real number is the vendor's own offline tool with the real load and the real inertia, or the
machine itself.

---

## 4. Push or grasp: the question that decides the arm

### What pushing theory guarantees, and what it does not

Mason's voting theorem gives the one thing about planar pushing that survives not knowing the
support pressure distribution. Define the centre of friction as the centroid of that pressure
distribution. For a quasi-static push at a single contact with a uniform coefficient of friction,
three lines in the plane vote on the sense of rotation: the line of pushing and the two edges of
the friction cone at the contact. Each votes clockwise or counterclockwise according to the sign
of its moment about the centre of friction, and the majority decides
([Mason, "Mechanics and Planning of Manipulator Pushing Operations", IJRR 5(3):53-71,
1986](https://doi.org/10.1177/027836498600500303); restated more precisely as Theorem 7.4 of his
*Mechanics of Robotic Manipulation*, MIT Press 2001).

Read that carefully, because it is narrower than it sounds. The theorem determines a SIGN. It does
not determine the rate of rotation, the final angle, or the translation. Those come from the limit
surface: for a given pressure distribution p(x, y) under the object, the set of friction wrenches
(fx, fy, mz) the support can transmit is bounded by a surface that is "closed, convex, and
encloses the origin of wrench space", and during slip the frictional load wrench lies on that
surface with the velocity twist normal to it, the plasticity analogue of an associative flow rule
([Goyal, Ruina, Papadopoulos, "Planar sliding with dry friction, Part 1: Limit
surface and moment function", Wear 143(2):307-330,
1991](https://doi.org/10.1016/0043-1648\(91\)90104-3); [Part 2: Dynamics of motion, Wear
143(2):331-352](https://doi.org/10.1016/0043-1648\(91\)90105-4)). The standard working
approximation replaces that surface with an ellipsoid ([Howe and Cutkosky, "Practical Force-Motion
Models for Sliding Manipulation", IJRR 15(6):557-572,
1996](https://doi.org/10.1177/027836499601500603)).

The limit surface is a function of p(x, y). Change the pressure distribution and the mapping from
applied wrench to motion changes with it. For this product, p(x, y) is not merely unknown, it is
not stationary:

- No measured friction coefficient for meat on plastic belting exists. The only measured food
  friction number found anywhere in this project was chicken fillet on stainless at 0.5,
  back-calculated from a simulation fit rather than read off a tribometer, and the working
  placeholder for wet meat on belting is 0.2 to 0.3 with no source at all
  ([meat-piece-properties](meat-piece-properties.md), sections 2.8 and 6).
- Purge from chilled primals runs 1 to 10 mL/kg in the first 48 h after boning, so belt wetness
  and therefore friction drift over a shift rather than holding constant (same note, section 2.8).
- The piece is deformable. Pushing it changes which parts of it bear on the belt, which changes
  p(x, y) during the push, which changes the limit surface during the push.

### How many millimetres and degrees, measured

This is the number the station specification turns on, and it has been measured, on hardware far
cleaner than anything in a pork plant. The MIT planar pushing dataset used an ABB IRB 120, a
9.5 mm steel cylindrical pusher, an ATI Gamma force-torque sensor, Vicon tracking better than
0.5 mm and water-jet-cut stainless objects of 0.75 to 1.4 kg ([Yu, Bauza, Fazeli, Rodriguez,
"More than a Million Ways to Be Pushed", IROS 2016,
arXiv:1604.04038](https://arxiv.org/abs/1604.04038)). Their Table IV repeats one nominally
identical push 2000 times: the rect1 object, 20 mm/s, 150 mm of pusher displacement. The spread of
the outcome:

| Surface | Mean outcome (dx mm, dy mm, dtheta deg) | Translation SD | Rotation SD |
|---|---|---|---|
| Delrin | 38.8, -50.7, 78.5 | 3.4 mm (5.2%) | 1.3 deg (1.6%) |
| ABS | 40.1, -67.6, 74.7 | 5.5 mm (7.1%) | 3.2 deg (4.3%) |
| Plywood | 36.4, -93.6, 70.2 | 8.1 mm (8.0%) | 4.2 deg (6.0%) |
| Polyurethane | 40.2, -85.0, 69.3 | 11.7 mm (12.5%) | 4.5 deg (6.5%) |

Their own summary: "even when trying to replicate the same initial conditions with an accurate
vision system and an accurate robot, a determined pushing interaction yields appreciable and
structured uncertainty at the outcome". The distributions are explicitly non-Gaussian and
multi-modal, with at least three modes.

So the answer to "can push-to-orient hold a few millimetres and a few degrees" is no, and by how
much: a rigid steel block pushed 150 mm across a flat manufactured plate lands with a standard
deviation of 3.4 to 11.7 mm and 1.3 to 4.5 degrees, depending only on which plate. A single
standard deviation of the best case is already at the limit of the tolerance, and the worst case is
three times outside it.

Two follow-ups bound how much of that is reducible. Bauza and Rodriguez fitted heteroscedastic
Gaussian processes to the same data and found "the magnitude of the noise is in between 10% and
40% of the magnitude of the expected output", attributing it to "the pushing process and not from
sensor noise" ([arXiv:1704.03033](https://arxiv.org/abs/1704.03033), ICRA 2017). Ma and Rodriguez
re-analysed the 2000-push set and showed that an isotropic-friction model leaves residuals of
4.74 deg, 2.84 mm and 8.57 mm on plywood; fitting anisotropic friction cuts that to 2.07 deg,
0.91 mm and 3.39 mm, and no further, with the remainder attributed to "heterogeneity and aging of
the surface" ([RA-L 3(4):3232-3239, 2018](https://doi.org/10.1109/LRA.2018.2851026),
arXiv:1802.10089). A perfectly identified friction model on a perfectly flat steel-on-plywood pair
still leaves 2 degrees.

The pork plant's version of that experiment is a wet, chemically cleaned, articulated modular
plastic belt carrying a deformable object of varying geometry, and no one has run it. There is no
basis for expecting it to come out better than polyurethane.

For scale on what the tolerance is worth: a review of robotic meat cutting values a 5 mm
improvement in cut position at roughly 300,000 USD per year on a 180-carcass-per-hour pork line
and about 1M USD per year on a 400-head-per-hour lamb line, and beef scribing precision at 48 US
cents per millimetre per head ([Khodabandehloo, "Achieving robotic meat cutting", Animal Frontiers
12(2):7-17, 2022](https://doi.org/10.1093/af/vfac012)). The same review treats "a handling and
holding solution that presents the meat to the robot in a known position and orientation" as a
precondition of the cut, not as something a push achieves.

### What makes pushing determinate

Lynch and Mason state the problem and the cure in one abstract: "the motion of a pushed object is
generally unpredictable due to unknown support friction forces. With multiple pushing contact
points, however, it is possible to find pushing directions that cause the object to remain fixed
to the manipulator" ([Lynch and Mason, "Stable Pushing: Mechanics, Controllability, and Planning",
IJRR 15(6):533-556, 1996](https://doi.org/10.1177/027836499601500602)). A line or edge contact at
the right pushing direction removes the friction indeterminacy by preventing the object from
slipping relative to the pusher. A single point contact cannot.

The plant-engineering version is older than the theory: push the piece against a fixed datum. A
fence, a rail, a converging funnel or a weir sets the final pose geometrically, and the friction
field only has to be good enough to get the piece there. Final accuracy becomes the accuracy of
the fence, which is a machining tolerance rather than a friction estimate. Chavan Dafle et al.
measured exactly this effect on an ABB IRB140 over 50-trial batches: pushing a grasped object
against a rigid post produced sub-millimetre position error, the mechanism being that pinning a
contact against a known fixture zeroes the uncertainty
([Extrinsic Dexterity, ICRA 2014](https://doi.org/10.1109/icra.2014.6907062)). Sensorless
orienting by a planned sequence of squeezes against flat jaws is the same idea taken to its limit
([Goldberg, Algorithmica 10:201-225, 1993](https://doi.org/10.1007/BF01891840); extended to
deformable polygons by [Kristek and Shell, IROS 2012](https://doi.org/10.1109/IROS.2012.6386165),
citation confirmed, full text not obtained).

The design rule this produces:

- Point push, no datum: the outcome is a sign, not a pose, with a standard deviation of several
  millimetres and several degrees even on steel and plywood. Do not write a millimetre tolerance
  against it.
- Line contact against a mechanical datum: the datum sets the pose. Millimetres are achievable
  because the fence, not the push, holds them.
- Point push with closed-loop vision fast enough to correct within the push: possible, and the
  pusher-slider feedback literature exists precisely because open-loop pushing is unpredictable
  ([Hogan and Rodriguez, WAFR 2016, arXiv:1611.08268](https://arxiv.org/abs/1611.08268)). It
  converts a mechanical problem into a tracking problem with the belt moving underneath. Cost it
  before choosing it.

### Grasp-and-pivot, and why it is determinate where pushing is not

Grasp the hock. The hock contains bone, so a form-closing grip around it reaches a geometric
constraint rather than relying on friction against flesh. Once the grip closes, the piece's pose
is the wrist pose composed with the grasp transform, and the error budget is a short list of
things that can be measured on a bench:

1. Where perception put the hock, measurable against ground truth.
2. How the grip seated on the bone, repeatable within the gripper's mechanics and observable if
   the gripper reports position.
3. How far the flesh moves relative to the bone during the swing, which is a stiffness and
   acceleration question, not a friction-field question.

None of those depends on the pressure distribution under the piece, because the piece is not
resting on the belt during the move. Hou, Jia and Mason put the mechanism plainly for pivoting:
"the object motion is kinematically determined by the motion of gripper under quasi-static
assumptions" ([ICRA 2018](https://doi.org/10.1109/icra.2018.8462834)). That is the sense in which
grasp-and-pivot is determinate and pushing is not: the error sources are enumerable and each is
separately measurable. The caveat from the same paper is worth carrying: their one hardware
failure came from "an underestimation of the friction coefficient between the object and the
table", so a pivot that keeps any part of the piece dragging on the belt re-inherits the friction
unknown it was meant to escape. Lift clear, or pivot about a contact you control.

Grasp-and-pivot is also where the SCARA dies, for the reason in section 3. Pivoting a 12.7 kg,
0.9 m leg about a wrist axis near the hock is 1.78 kg m2, which exceeds the maximum allowable
inertia of every SCARA in the market and exceeds the rated figure by more than an order of
magnitude.

---

## 5. Cycle time

Three vendors define the benchmark cycle on the datasheet, and they do not agree on the horizontal
leg. ABB, in the IRB 360 product specification: "Cycle 1 is a 25 - 305 - 25 movement, with 90
degrees rotation of axis 4", with 35 ms of air activation for the pick and 35 ms for the place
included in the time
([3HAC079010-001](https://search.abb.com/library/Download.aspx?DocumentID=3HAC079010-001&LanguageCode=en&Action=Launch)).
Epson: "Cycle time based on round-trip arch motion (300 mm horizontal, 25 mm vertical) with 2 kg
payload (path coordinates optimized for maximum speed)". Yamaha: "When reciprocating 25 mm in
vertical direction and 300 mm in horizontal direction (rough-positioning arch motion)", at 2 kg.
The 305 mm figure is a foot, and it is the older form; the Japanese SCARA vendors round it to 300.
No primary source for the trade name "Adept cycle" was found (**unverified as a term**), but the
motion is confirmed as the industry benchmark by three vendors' current documents. Note that
ABB's version includes a 90 degree tool rotation and a real air-activation delay and Epson's and
Yamaha's do not, so a 25/305/25 number from one vendor is not directly comparable to a 300/25
number from another.

Published figures, same test definition throughout:

| Class | Model | Payload rated / max | Test payload | Standard cycle |
|---|---|---|---|---|
| Small SCARA | Epson GX4 | 2 / 4 kg | 2 kg | 0.33 to 0.35 s |
| Large SCARA | Epson G20-A0x | 10 / 20 kg | 2 kg | 0.42 s |
| Large SCARA | Epson LS20-BA04 | 10 / 20 kg | 2 kg | 0.43 s |
| Large SCARA | Yamaha YK1000XGP | 20 kg max | 2 kg | 0.59 s |
| Large SCARA | Yamaha YK1200X | 50 kg max | 2 kg | 0.91 s |
| Six-axis, same vendor | Epson C4 | 1 / 4 kg | 1 kg | 0.37 to 0.47 s |
| Six-axis, same vendor | Epson C8 | 3 / 8 kg | 1 kg | 0.31 to 0.53 s |
| Six-axis, same vendor | Epson C12XL | 3 / 12 kg | 1 kg | 0.50 s |
| Six-axis, same vendor | Epson VT6L | 3 / 6 kg | not stated | 0.60 s |

Epson is the only vendor found that publishes the identical arch cycle for both its SCARA and its
six-axis lines, which makes it the only clean same-test cross-class comparison available. At
matched low payload the SCARA advantage is real and modest: GX4 at 0.33 to 0.35 s against C4 at
0.37 to 0.47 s, roughly 25 to 35 percent. Across Yamaha's own SCARA range, the 50 kg machine is 75
percent slower than the 20 kg machine on the identical 2 kg cycle, because at that size the arm's
own inertia dominates.

### The one published payload derating curve

ABB prints what the SCARA vendors do not: the same machine, the same cycle, at three payloads.
From the IRB 360 product specification, Cycle 1 in picks per minute, the IRB 360-8/1130 runs 160
at 1.0 kg, 140 at 4.0 kg and 100 at its rated 8.0 kg; the IRB 360-6/1600 runs 140, 125 and 100 at
1.0, 3.0 and 6.0 kg; the IRB 360-3/1130 runs 150 at both 0.1 and 1.0 kg and 115 at 3.0 kg. Loading
an 8 kg machine to its rating costs 37.5 percent of its rate. ABB also notes the table is "valid
for robots with protection class Standard and WashDown", which excludes the IP69K stainless
version, whose manipulator weighs 145 kg against 120 kg standard. The hygiene option costs speed
as well as money, and ABB does not say how much.

Penta's hygienic Veloce gives the same lesson at a payload closer to ours: on the 25/305/25 cycle,
tested at the University of Twente, 1.37 s per cycle at 10.0 kg, about 44 cycles per minute, on a
machine specified for 10 m/s and 200 m/s2
([archived spec sheet](https://web.archive.org/web/2020id_/http://pentarobotics.com/wp-content/uploads/2018/05/Spec_sheet_Veloce_A4-2.pdf)).
Every arch cycle in the SCARA table above is quoted at 2 kg. At 10 kg the same standard motion
takes three times longer on a machine designed for speed.

What the published numbers do not tell you, and this is the part that matters here:

- Nothing about 17 kg. Every SCARA figure is at 1 kg or 2 kg, which is where moving mass is the
  arm and the payload is noise. The SCARA speed advantage that makes it the default for
  electronics assembly is measured in exactly that regime. At 17 kg on the flange with 1.8 kg m2
  about the wrist, the payload is no longer noise, and every SCARA vendor stops quoting.
- Nothing about this motion. A 300 mm arch with a 25 mm lift is not an intercept on a moving belt
  with a 700 to 900 mm object swinging on the flange.
- Nothing comparable for the six-axis arms actually on the shortlist. FANUC, KUKA and Stäubli
  publish axis speeds and repeatability, not a standardised cycle; ABB publishes relative claims
  for its articulated arms ("up to 50 percent shorter cycle times than competing robots",
  [IRB 1600](https://web.archive.org/web/2024/https://new.abb.com/products/robotics/robots/articulated-robots/irb-1600))
  that cannot be set against an Epson or Yamaha arch number.

For a rate sanity check at this product size, the only public figure on a comparable job is
Mayekawa's roughly 40 s per leg to remove hip and tail bones with three six-axis robots
([Stäubli](https://www.staubli.com/global/en/robotics/industries/food/protein-processing/deboning-of-pork.html)).
A single orient or place operation is a small fraction of that, but it anchors the order of
magnitude: this is a seconds-per-piece station, not a 0.4 s station, and the SCARA's half-second
arch cycle is not what will set the line rate.

---

## 6. Hygiene and mechanical design, arm-specific

The standards, food-contact regulation and the IP69K test conditions are in
[meat-cutting-automation](meat-cutting-automation.md). What follows is specific to choosing
between these two arm classes.

**An IP number that applies to part of the arm is not an IP number for the arm.** Several arms
above carry a split rating: FANUC M-20iD/25 is IP67 on the wrist and J3 arm but IP54 as standard
on the body, with IP65 as an option; Stäubli's HE range is IP65 and only reaches IP67 with the
pressurized version; KUKA KR DELTA HM is IP67 with IP69K on axis 4 only. In every case the
marketing headline quotes the best of the set. Read the specification table, not the feature
list, and write the body rating into the purchase specification.

**The wash is the design load, and it attacks the joints and the cables.** What survives a meat
plant is a sealed, pressurized, cable-free exterior. Stäubli's HE argument is precisely that:
fully encapsulated, no external cables, integrated harness and tubing, all connections protected
under the base, positive internal pressure so contamination cannot migrate inward through a seal.
ABB's IP69K FlexPicker makes a different bet, lubricant-free joints and rinse-off surfaces. Both
are answers to the same failure mode, which is fluid and cleaning chemical finding a path into a
joint or a connector.

**Bellows are the weak point of the SCARA answer.** A SCARA gets its Z-axis protection from a
bellows over the ball screw and spline, because the ball screw has to telescope. Yamaha rates the
result "equivalent to IP65" and then tells you not to put a water jet on the bellows. A six-axis
arm has no telescoping element; every joint is a rotary seal, which is the sealing geometry that
reaches IP67 and IP69K in practice. That, and not marketing, is why the IP ladder stops at IP65
for SCARAs and continues past it for articulated arms and deltas.

**Joint count is not the cleaning argument it looks like.** A SCARA has four joints against six,
so fewer seals. But cleanability is about drainable surfaces, absence of crevices and horizontal
ledges, and radiused internal corners, not about the number of rotary joints, and the SCARA's
geometry works against it on exactly those criteria: a large horizontal upper-arm surface directly
over the product with a vertical ball screw and bellows descending through it, which is a
horizontal ledge plus a convoluted flexible surface in the worst possible place. A six-axis arm
mounted beside or above the belt can be oriented so no horizontal surface sits over open product.
Neither arrangement is EHEDG-certified, because no robot appears on the EHEDG certified equipment
list at all ([meat-cutting-automation](meat-cutting-automation.md)), so this goes to the plant's
QA with photographs before it becomes a specification.

**Food-grade lubricant is a yes-or-no question; ask it in writing.** Stäubli claims NSF H1 food
oil across the HE range; FANUC names NSF H1 grease on the CRX Food Grade cobots and the stainless
delta but names only a "Food Grade Option" on the M-20iD/25; KUKA claims food-compatible
lubricants on HM and HO; ABB's six-axis pages made no NSF H1 claim. Since 21 CFR 178.3570 is the
basis of H1 registration and the plant's SSOP will name your cell, the answer has to be a
registration number on a document, not a phrase on a web page.

**There are robot-specific hygienic design documents; neither is a certificate.** EHEDG publishes
Doc 62 Part 1, "Hygienic Design Criteria for Robotic Systems in Food Processing Environments, Part
1: Fundamental Requirements for Robots", and 3-A publishes standard 103-00, "Robot-based
Automation Systems", last revised 2016. Both are members-only or paid documents and neither was
read in this pass, so their content is **unverified** here, but their existence changes the
conversation with a vendor from "is it hygienic" to "which clauses of EHEDG 62 and 3-A 103 do you
meet". That is separate from certification: no robot appears on the EHEDG certified equipment list,
which remains the position in [meat-cutting-automation](meat-cutting-automation.md).

**What the sourced failure mode actually is: grease, not water.** Timken engineers writing in Food
Engineering describe the chain directly: "Washdown can lead to ingress of water-based detergents
and sanitizers that alters the chemical properties of the grease by diluting the base oil and
degrading the thickener", under "high-temperature and high-pressure water jets, caustic and acidic
chemicals, as well as chlorine-based sanitizers"
([Food Engineering, 24 Feb 2020](https://www.foodengineeringmag.com/articles/98734)). A companion
piece traces it to the end: ingress dilutes the lubricant, the film is lost, and the rings and
rolling elements are damaged, with escaped lubricant also becoming a food-contamination path
([Food Engineering, 1 Jul 2024](https://www.foodengineeringmag.com/articles/102265)). Both are
trade press authored by a bearing vendor, so tag them accordingly, but the mechanism is consistent
with what the hygienic robot lines are built to defend: Stäubli's own pitch for the HE series is
that the "fully enclosed and pressurized structure prevents microorganism penetration and
condensation" and that there are "no external cables: all connections run through the arm and
base" ([Food Engineering, 4 Oct 2023](https://www.foodengineeringmag.com/articles/101590)). The
named defences are condensation into joints and external cable and connector damage, which tells
you what breaks.

Corrosion of the bearing itself is documented in the same industry, though not on a robot: Pilgrim's
Pride in Farmerville, Louisiana replaced cast-iron oven-infeed conveyor bearings that corroded
under daily high-pressure washdown, heat and load, with the maintenance manager noting "durability
of the bearings was as much an issue as corrosion resistance" after a composite replacement cracked
under oven heat ([Food Engineering, 1 Jan 2007](https://www.foodengineeringmag.com/articles/85724-keep-the-rust-out)).
No case study of a robot-specific condensation failure in a chilled room, and no documented instance
of a bellows or sleeve as the water-ingress path on a robot joint, was found (**not found**), which
is why this note still carries no "practical gotchas" section.

**Protective covers do not solve the SCARA's rating problem.** The enclosure that an IP65 SCARA
would need in this cell has no off-the-shelf answer with a food claim: Roboworld's Robosuit is
rated by temperature tolerance (120 to 1800 degrees F) with no IP rating and no food-grade or
hygiene certification found anywhere, including its UR marketplace listing
([Roboworld](https://roboworld.com/robosuit)), and Dou Yee is an ESD and cleanroom-apparel
supplier with no robot-cover line. Neither appears on the EHEDG or 3-A certified lists. Treat "put
a cover on it" as an unpriced, uncertified custom build, not a catalogue fix.

---

## 7. Decision table by station definition

| Station definition | Arm class | Why | The disqualifying constraint |
|---|---|---|---|
| Orient by point pushing in the belt plane, no datum | Neither, as specified | The indeterminacy is in the physics, not the arm. Measured spread of an identical repeated push on steel and plywood is 3.4 to 11.7 mm and 1.3 to 4.5 degrees, non-Gaussian and multi-modal, and a perfectly fitted anisotropic friction model still leaves 2 degrees. | The station specification itself. Redefine it before selecting an arm. |
| Orient by line-contact push against a fixed datum | SCARA, or cheaper still a two-axis pusher | Loads are horizontal, motion is planar, no tilt needed, flange load is a paddle rather than a leg. Pose accuracy comes from the fence. | For six-axis: paying for six axes and a 250 kg machine to execute a planar sweep. For SCARA: still nothing above IP65, so it needs an enclosure. |
| Orient by grasp-and-pivot in the belt plane | Six-axis | Wrist inertia. 1.78 kg m2 at a hock grasp of a 12.7 kg, 0.9 m leg exceeds every SCARA R-axis maximum on the market and the rated figure by more than 30x. | For SCARA: allowable R-axis inertia, rated 0.05 kg m2 (Epson G20), maximum 0.45 to 1.0 kg m2 across the 20 kg class. Hard stop. |
| Pick and place, flat in, flat out, no reorientation | Six-axis | On kinematics alone a SCARA would do it, and at 20 kg three models exist. It loses on the wash. | For SCARA: nothing above IP65, and the IP65 models carry a vendor instruction not to jet the bellows. An enclosure removes the footprint advantage that motivated the choice. |
| Pick and place with any tilt at the cutter | Six-axis | A tilt is an orientation the SCARA cannot produce in any configuration with any gripper. | For SCARA: four degrees of freedom, all joint axes vertical. Not a tuning problem. |
| Pick from a moving belt with an intercept, place into a fixture | Six-axis | Intercept geometry and approach direction both want orientation freedom, and the piece's inertia wants the larger wrist rating. | For SCARA: wrist inertia, and orientation if the fixture is not parallel to the belt. |
| Very high rate, light product, flat transfer (not this station) | Delta | What the architecture is for, and the food-rated deltas carry the best hygiene ratings in this note, up to 20 kg at IP69K (Codian HD). | Degrees of freedom and envelope: the 4-axis deltas cannot tilt, the 12 kg FANUC M-3iA/12H has three axes and cannot even yaw, and the working volume is a shallow dome 500 to 550 mm deep. |

The first row is the one that matters. Four of the six remaining rows choose a six-axis arm on a
hard kinematic or datasheet constraint, and one chooses something that is not an arm at all.
Settling whether the station pushes or grasps is worth more than any further comparison between
arm families.

---

## 8. What simulation can settle, and what it cannot

Build the cell per [meat-cell-architecture](meat-cell-architecture.md) and
[sim-first-workflow](sim-first-workflow.md), and run both arm classes through it.

Four things simulation answers credibly, because all four are geometry or rigid-body dynamics.
Reach coverage: sample the measured distribution of piece poses on the belt and check that both
arms hit every grasp or push pose with the belt moving, without a joint limit or a wrist
singularity. Whether four degrees of freedom suffice: if any required approach or delivery pose
has a non-vertical tool axis, the SCARA fails and the comparison stops there. Cycle time under
the real payload and the real inertia, with the leg modelled by its measured mass and inertia
tensor rather than a point mass, run in the vendor's own offline tool so the controller's own
derating applies; this is the only route to the number section 5 says the datasheets will not
give. And intercept feasibility inside the belt window, given belt speed and piece spacing, along
with collision, footprint, guarding and sanitation access.

Four things it will not answer and must not be asked to:

- **The friction field.** No measured meat-on-belting coefficient exists
  ([meat-piece-properties](meat-piece-properties.md) section 2.8), so any push simulation is
  parameterised on a guess and its accuracy claims are the guess's. Sweep the coefficient across
  0.15 to 0.5 and report the spread, never a single trajectory. The MIT dataset's spatial standard
  deviations of 0.016 to 0.064 on engineered surfaces are a floor on the variability to expect,
  not an estimate of it.
- **The support pressure distribution**, which is the whole content of section 4. A rigid-body
  contact model assumes a p(x, y) it cannot know; a deformable model assumes a constitutive law
  for chilled pork that is itself an approximation.
- **Whether the grip holds.** Flesh tearing, purge-slicked skin and bone geometry are bench
  questions, not solver questions. See
  [grasp-selection-for-soft-slabs](grasp-selection-for-soft-slabs.md).
- **Whether the arm survives the plant.** IP ratings, chemical compatibility, pH range and seal
  life are document-and-reference questions. Ask each vendor for a meat-plant reference site and
  go and look at a three-year-old machine.

The decision procedure that follows:

1. Settle push versus grasp first, on the physics in section 4, not on arm preference.
2. If grasp: compute the inertia about the intended wrist axis from a weighed, measured sample,
   and treat it as a hard filter on the arm list before anything else is considered.
3. Simulate both classes for reach, orientation feasibility and cycle time with the real payload.
4. Ask every shortlisted vendor, in writing, for the body IP rating (not the wrist), the NSF H1
   registration number of the lubricant, the chemical and pH compatibility of the seals, and a
   meat-plant reference.

---

## Open questions

- Does the station orient or pick? Everything above depends on it and it is not settled.
- What is the centre of mass of a whole bone-in pork leg as a fraction of length from the hock?
  Section 3's inertia figures are a uniform-rod approximation and the real value is worse.
- Does Epson's "Protected IP54 and IP65" option actually exist at the G20's 20 kg size? The
  catalog lists it at platform level and no IP65 SKU was found at that payload.
- Yaskawa's food-grade SIX-AXIS range. The MPP3 delta is confirmed (3 kg, IP67, NSF H1), but the
  legacy six-axis food model names are gone from the Motoman catalogue and nothing replaced them
  with a published IP rating.
- What are Bosch Rexroth's and Festo's hygienic linear axes rated at? Both sites were unreachable,
  and both are known suppliers into this sector.
- Does Codian's 5-axis D5 at 35 kg have a washdown rating? It is the only parallel machine found
  with a tilt axis at this payload, and its food status is unstated.
- Is there any published static stiffness figure, in N/mm, for any industrial arm of either class?
  None was found, and it is the number that would settle section 1's argument rather than bounding
  it.
- What do EHEDG Doc 62 P1 and 3-A 103-00 actually require of a robot? Both are paywalled and
  neither was read here, and together they are the only robot-specific hygienic design documents
  found.
- Is there a documented robot failure from chilled-room condensation, or from a bellows as the
  ingress path? The bearing grease-washout chain is sourced; these two are not, and they are the
  ones that would settle the SCARA bellows argument with evidence rather than a vendor caveat.

## Related entries

- [operating-robot-arms](operating-robot-arms.md), the pendant-level view of the arms shortlisted here
- [meat-cutting-automation](meat-cutting-automation.md), the cell, the hygiene standards and the washdown parts list
- [meat-cell-architecture](meat-cell-architecture.md), the twelve subsystems and their contracts
- [compliant-mechanisms-and-actuation](compliant-mechanisms-and-actuation.md), where compliance belongs if not in the arm
- [meat-piece-properties](meat-piece-properties.md), the product's mass, friction and deformation data and its gaps
- [grasp-selection-for-soft-slabs](grasp-selection-for-soft-slabs.md), choosing the grasp this note sizes the arm around
- [sim-first-workflow](sim-first-workflow.md), how to run section 8

## Sources

All product URLs fetched 2026-09-11. Sites that block automated fetches are marked.

- Stäubli (403 to direct fetches; read through a text-rendering proxy): HE range spec tables https://www.staubli.com/global/en/robotics/products/industrial-robots/hygienic-humid.html ; Mayekawa CELLDAS pork deboning https://www.staubli.com/global/en/robotics/industries/food/protein-processing/deboning-of-pork.html ; cheese derinding under a high-pressure lance https://www.staubli.com/global/en/robotics/industries/food/dairy-products/automated-derinding-of-cheese.html ; TS2-100 archived spec page https://web.archive.org/web/20230330103643/https://www.staubli.com/at/en/robotics/products/industrial-robots/ts2-100.html
- FANUC SCARA: series page https://www.fanucamerica.com/products/robots/series/scara ; datasheets https://www.fanucamerica.com/uploads/files/data-sheets/sr-6ia-datasheet.pdf , .../sr-12ia-datasheet.pdf , .../sr-20ia-datasheet.pdf (the SR-20iA's "IP65 Environmental option available" footnote) ; "/C" food and clean variants at IP54 https://www.fanuc.eu/at/en/robots/robot-filter-page/scara-series
- FANUC articulated and cobot: M-20iD/25 https://www.fanucamerica.com/products/robots/series/m-20/m-20id-25 ; M-710iC/50 https://www.fanucamerica.com/products/robot/m-710ic-50 ; CRX-10iA Food Grade https://www.fanucamerica.com/products/robot/crx-10ia-food-grade ; CRX-30iA Food Grade https://www.fanucamerica.com/products/robot/crx-30ia-food-grade ; LR Mate 200iD/7LC, the only six-axis IP69K claim found https://www.fanucamerica.com/products/robot/lr-mate-200id-7lc
- FANUC delta: M-2iA/6HL https://www.fanucamerica.com/uploads/files/data-sheets/m-2ia-6hl-datasheet.pdf ; M-3iA/12H https://www.fanucamerica.com/uploads/files/data-sheets/m-3ia-12h-datasheet.pdf
- KUKA: meat processing model list https://www.kuka.com/en-us/industries/consumer-goods-industry/meat-processing-automation ; KR AGILUS https://www.kuka.com/en-de/products/robot-systems/industrial-robots/kr-agilus ; KR CYBERTECH .../kr-cybertech ; KR IONTEC .../kr-iontec ; KR QUANTEC .../kr-quantec
- ABB (new.abb.com unreachable directly; product pages via Wayback): IRB 360 product specification 3HAC079010-001, the source of the IP54/IP67/IP69K option list, the manipulator masses, the 25-305-25 cycle definition and the picks-per-minute against payload table https://search.abb.com/library/Download.aspx?DocumentID=3HAC079010-001&LanguageCode=en&Action=Launch ; IRB 360, IRB 2600, IRB 1300, IRB 1600 https://web.archive.org/web/2024/https://new.abb.com/products/robotics/robots/delta-robots/irb-360 and articulated-robots siblings
- Denso: HM series, 10 and 20 kg with an IP65 configuration https://www.densorobotics.com/products/4-axis/hm-series/ ; HS-A1 https://www.densorobotics.com/products/4-axis/hs-a1-series-old/
- Epson: specifications catalog CPD-54833R4, the source of the rated-versus-maximum allowable moment of inertia, the arch cycle definition and times, and the "Protected IP54 and IP65" installation environments, linked from https://epson.com/scara-robots : https://mediaserver.goepson.com/ImConvServlet/imconv/1e573dc9fbf44d823b1007ebbc2787dda394783d/original?assetDescr=Epson_Robots_Specifications_Catalog_CPD-54833R4_FInal_NoCrop.pdf
- Yamaha: range pages https://global.yamaha-motor.com/business/robot/lineup/ykxg/proof/ and .../ykxg/large/ ; per-model datasheets .../ykxg/proof/pdf/index/YK500XGP_E_0707.pdf , .../YK700XGP_E_0707.pdf , .../YK1000XGP_E_0707.pdf , .../ykxg/large/pdf/index/yk1200x.pdf , .../YK1200XG.pdf
- Other parallel and hygienic machines: Codian HD series https://codian-robotics.com/robots/hd-series/ and D4-1600-HD041 https://codian-robotics.com/blog/producten/d4-1600-hd041-3/ ; Penta Veloce archived spec sheet (pentarobotics.com is a dead domain) https://web.archive.org/web/2020id_/http://pentarobotics.com/wp-content/uploads/2018/05/Spec_sheet_Veloce_A4-2.pdf ; Yaskawa MPP3H/MPP3S https://www.motoman.com/getmedia/88ea7ba5-a4d6-48e5-b5c4-83058daa62e3/MPP3H_MPP3S.pdf.aspx ; Universal Robots UR20 https://www.universal-robots.com/products/ur20-robot/
- Gantry and linear: Macron Dynamics MSS-R20 https://www.macrondynamics.com/products/mss-r20/ ; Güdel FP https://www.gudel.com/products/linearaxis/fp and TrackMotion TMF https://www.gudel.com/products/linear-tracks-for-robots/tmf ; Rollon food processing https://www.rollon.com/usa/en/your-challenges/linear-motion-food-processing/ , ELM PLUS CR https://my.rollon.com/corp/en/product/elm-cr/ , ROBOT PLUS CR https://my.rollon.com/corp/en/product/robot-cr/
- Standards and product spec: IP69K is ISO 20653:2023 https://www.iso.org/standard/76116.html (paywalled; test conditions restated in [meat-cutting-automation](meat-cutting-automation.md)) ; USDA AMS IMPS Fresh Pork Series 400, item 401 weight ranges https://www.ams.usda.gov/sites/default/files/media/IMPS_400_Fresh_Pork%5B1%5D.pdf
- SCARA origin and measured compliance: Makino, "Development of the SCARA", J. Robot. Mechatron. 26(1):5-8, 2014, https://doi.org/10.20965/jrm.2014.p0005 , full text https://www.jstage.jst.go.jp/article/jrobomech/26/1/26_5/_pdf/-char/en (CC BY-ND) ; Furuya and Makino, 1st Report, JJSPE 1980, https://doi.org/10.2493/jjspe1933.46.1525 and 2nd Report, 1983, https://doi.org/10.2493/jjspe1933.49.835 ; Makino and Furuya, "Selective compliance assembly robot arm", Proc. 1st ICAA, Brighton, pp. 77-86, 1980 (cited in the 2014 retrospective, not fetched, **unverified**) ; Klimchik, Wu, Dumas, Caro, Furet, Pashkevich, "Identification of geometrical and elastostatic parameters of heavy industrial robots", ICRA 2013, https://arxiv.org/abs/1311.6810 (KUKA KR-270 joint compliances, Table IV)
- Pushing mechanics: Mason, IJRR 5(3):53-71, 1986, https://doi.org/10.1177/027836498600500303 (the voting theorem is restated more precisely as Theorem 7.4 of his *Mechanics of Robotic Manipulation*, MIT Press 2001) ; Goyal, Ruina, Papadopoulos, Wear 143(2), 1991, Part 1 pp. 307-330 https://doi.org/10.1016/0043-1648(91)90104-3 (open PDF http://ruina.mae.cornell.edu/research/topics/friction_and_fracture/planar_sliding_i.pdf) and Part 2 pp. 331-352 https://doi.org/10.1016/0043-1648(91)90105-4 ; Goyal's thesis, Cornell 1989, http://ruina.mae.cornell.edu/research/topics/friction_and_fracture/GoyalPhDThesis.pdf ; Howe and Cutkosky, IJRR 15(6):557-572, 1996, https://doi.org/10.1177/027836499601500603 ; Lynch and Mason, IJRR 15(6):533-556, 1996, https://doi.org/10.1177/027836499601500602 ; Yu, Bauza, Fazeli, Rodriguez, IROS 2016, https://arxiv.org/abs/1604.04038 (repeated-push spread, Table IV; friction variability, section V) ; Bauza and Rodriguez, ICRA 2017, https://arxiv.org/abs/1704.03033 ; Ma and Rodriguez, RA-L 3(4):3232-3239, 2018, https://doi.org/10.1109/LRA.2018.2851026 , arXiv:1802.10089 ; Hogan and Rodriguez, WAFR 2016, https://arxiv.org/abs/1611.08268
- Determinate alternatives: Chavan Dafle et al., "Extrinsic Dexterity", ICRA 2014, https://doi.org/10.1109/icra.2014.6907062 (sub-millimetre error pushing against a rigid post, 50-trial batches on an ABB IRB140) ; Hou, Jia, Mason, ICRA 2018, https://doi.org/10.1109/icra.2018.8462834 (pivoting is kinematically determined by the gripper) ; Dogar and Srinivasa, RSS 2011, https://doi.org/10.15607/rss.2011.vii.009 (push-grasp funnels pose uncertainty; no mm or degree tolerance reported) ; Goldberg, Algorithmica 10:201-225, 1993, https://doi.org/10.1007/BF01891840 ; Kristek and Shell, IROS 2012, https://doi.org/10.1109/IROS.2012.6386165 (citation confirmed, full text not obtained)
- Meat-cutting tolerance and its value: Khodabandehloo, "Achieving robotic meat cutting", Animal Frontiers 12(2):7-17, 2022, https://doi.org/10.1093/af/vfac012
- Hygienic design documents for robots specifically (both paid, neither read here, content **unverified**): EHEDG Doc 62 Part 1, "Hygienic Design Criteria for Robotic Systems in Food Processing Environments, Part 1: Fundamental Requirements for Robots", https://www.ehedg.org/guidelines-working-groups/guidelines/guidelines/ ; 3-A Sanitary Standard 103-00, "Robot-based Automation Systems", revised 2016, https://www.3-a.org/ . Background standards: EN 1672-2:2020, ISO 14159:2002, NSF/ANSI 169-2023, ISO 21469:2006
- Washdown failure modes (trade press, bearing-vendor authored where noted): Timken on grease dilution and thickener degradation, Food Engineering 24 Feb 2020, https://www.foodengineeringmag.com/articles/98734 ; Timken on the IP69K ingress-to-failure chain, 1 Jul 2024, https://www.foodengineeringmag.com/articles/102265 ; Pilgrim's Pride Farmerville conveyor bearing corrosion, 1 Jan 2007, https://www.foodengineeringmag.com/articles/85724-keep-the-rust-out ; Stäubli HE coverage, 4 Oct 2023, https://www.foodengineeringmag.com/articles/101590 ; Roboworld Robosuit, https://roboworld.com/robosuit
- NSF H1: https://www.nsf.org/knowledge-library/food-grade-lubricants-registrations ; 21 CFR 178.3570 https://www.law.cornell.edu/cfr/text/21/178.3570 (10 ppm incidental-contact ceiling; NSF took over registration after USDA discontinued its programme in 1998)

The four pushing-mechanics DOIs and the two Makino JJSPE DOIs were verified against Crossref
metadata on 2026-09-11. The Yu and Bauza figures were read from the arXiv PDFs, not the abstracts.
