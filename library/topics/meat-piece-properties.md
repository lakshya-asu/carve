---
title: Meat piece properties for simulation (mass, mechanics, belt presentation)
date: 2026-09-08
tags: [topic, meat, food, material-properties, deformable, simulation, mujoco, meat-cell]
status: draft
source: synthesis (primary links inline and in Sources)
---

# Meat piece properties for simulation (mass, mechanics, belt presentation)

Companion entries: [meat cutting automation](meat-cutting-automation.md) for the cell this feeds,
[deformable object manipulation](deformable-object-manipulation.md) for how to represent the object
in a solver, [grasp selection for soft slabs](grasp-selection-for-soft-slabs.md) for what the beam
mechanics do with the numbers below, [meat cell architecture](meat-cell-architecture.md) for where
S1 (cell physics) sits in the build order.

This note answers one question: what does a piece of meat actually measure, weigh, and mechanically
do, as it arrives at an intercept-and-align station on a belt. It is written to hand numbers directly
to a MuJoCo model, not to survey the field. Every number below is tagged by how solid it is:
**measured** (a primary paper reports it from a real sample), **machine spec** (a vendor states it as
what their equipment accepts, not a distribution of the real product), or **assumption** (nothing
found, a modeling choice is proposed and labeled as such). Do not read a machine spec as a population
statistic; a portioner's "max product length 900 mm" tells you the largest thing the infeed will take,
not the mean or the spread of what actually arrives.

The honest summary going in: dimensions and masses are documented mostly as trade weight classes and
machine envelopes, not as measured population distributions. Mechanical properties are documented in
kPa-scale detail for porcine, bovine, and (once) rabbit muscle, almost never for the exact species,
muscle, and temperature this cell will see. Friction and belt presentation are the two thinnest areas
in the entire literature search; treat every number for those as needing a plant-side measurement,
not a citation, before it goes into a customer-facing sim.

## 1. Product envelope

### 1.1 Chicken breast fillets (boneless, skinless)

Machine specs (what a portioning/cutting line accepts, not what a fillet actually measures):

- Marel MARELEC PORTIO 3-300 fixed-weight portion cutter: product up to 800 x 290 x 150 mm (L x W x
  H), belt width 305 mm, cutting rate up to 14 cuts/s
  ([MARELEC](https://www.marelec.com/industries/poultry/portioning/portion-cutter-portio-3-300/)).
- Marel I-Cut 36: product up to 900 x 300 x 150 mm, infeed belt speed 20 to 500 mm/s, up to 1000
  cuts/min (reseller listing, not independently confirmed on marel.com, treat as lower confidence:
  [Normart Trading](https://www.normartrading.no/en/products/marel-i-cut-36/)).
- I-Cut 122 TrimSort: 2000 cuts/min per lane, dual lane, cutting angles 45/60/75/90 degrees; no
  product size range published on the page
  ([JBT Marel](https://jbtmarel.com/en/products/i-cut-122-portioncutter/poultry/)).

Measured population data:

- U.S. Grade A boneless skinless chicken breast comes from ready-to-cook broilers 1.36 to 2.72 kg
  (3.0 to 6.0 lb) live-equivalent weight, per commodity spec, not a fillet weight
  ([USDA AMS](https://www.ams.usda.gov/book/chicken-breast-grade)).
- Single pectoralis major fillet (one side), mean mass 400.6 to 425.5 g (SE approximately 4.5 g),
  n = 103, Cobb 500 broilers at 52 to 53 days ([Lake et al. 2020, Front
  Physiol](https://pmc.ncbi.nlm.nih.gov/articles/PMC7154160/)).
- Breast yield (both fillets), 596.58 +/- 67.44 g, broilers in the 2.0 to 2.5 kg live-weight group,
  the heaviest of three groups sampled ([Islam et al. 2026, J Adv Vet Anim
  Res](https://pmc.ncbi.nlm.nih.gov/articles/PMC13197668/)).
- A frequently repeated weight-class breakdown (light 95.9 to 123.8 g, medium 130.3 to 178.6 g, heavy
  180.9 to 228.9 g, attributed to Zhuang and Savage 2012, *Poultry Science* 91(7):1695-1702, DOI
  10.3382/ps.2011-01884) could not be checked against the primary text in this pass; the journal
  blocked automated access. Report it only as an unconfirmed secondary claim.

No source in this search gives a length x width x thickness distribution for raw fillets from a
population study. Every dimension number above is a machine's maximum accepted envelope, not a
measured spread. Thickness in particular varies a great deal along one fillet, thin at the tip and
thick at the head end; no measured figure for that taper was found, so treat any specific taper you
model as an assumption pending your own caliper measurements.

### 1.2 Pork loin (whole loin, chops, steaks)

All figures are USDA AMS Institutional Meat Purchase Specifications (IMPS), Fresh Pork Series 400,
effective November 2014, a procurement document, not a measured distribution
([USDA AMS IMPS 400](https://www.ams.usda.gov/sites/default/files/media/IMPS_400_Fresh_Pork%5B1%5D.pdf)).
Weight classes are purchaser-selectable bands, converted here at 1 lb = 0.4536 kg:

| Item | Cut | Weight classes (kg, from lb) |
|---|---|---|
| 410 | Whole loin, bone-in | 6.4-8.2 / 8.2-10.9 / 10.9-up |
| 413 | Whole loin, boneless ("long cut") | 3.6-4.5 / 4.5-5.9 / 5.9-up |
| 412 | Center-cut, 8 ribs, bone-in | 2.7-3.6 / 3.6-5.0 / 5.0-up |
| 412B | Center-cut, 8 ribs, boneless | 1.8-2.3 / 2.3-3.2 / 3.2-up |

Chop-specific tolerances from the same document: standard tail length at or below 1.0 in (25 mm) from
the muscle edge, with optional 2 in (50 mm) or 3 in (75 mm, frenched) tails; stuffed-chop pocket depth
1/4 to 1/2 in (6 to 13 mm) of intact lean from the cut edge. General portion-thickness tolerance
(same IMPS family, section 3.5.1, applies across products unless the purchaser overrides it):
thickness at or below 1 in (25 mm) gets a tolerance of +/- 3/16 in (5 mm); thickness above 1 in gets
+/- 1/4 in (6 mm).

No peer-reviewed measured population study (mean, SD, or histogram) for raw pork loin chop dimensions
or mass was found. IMPS gives trade weight bands and shape/trim tolerances, not a distribution.

### 1.3 Beef primals and steaks

Also USDA AMS IMPS, Fresh Beef Series 100
([USDA AMS IMPS 100](https://www.ams.usda.gov/sites/default/files/media/IMPS_100_Fresh_Beef%5B1%5D.pdf)),
same caveat: procurement classes, not measured distributions.

| Item | Cut | Weight classes (kg, from lb) |
|---|---|---|
| 175 | Strip loin, bone-in | 5.0-6.4 / 6.4-8.2 / 8.2-10.0 / 10.0-up |
| 180 | Strip loin, boneless | 3.6-4.5 / 4.5-5.4 / 5.4-6.4 / 6.4-up |
| 112 | Ribeye roll | 2.3-2.7 / 2.7-3.6 / 3.6-4.5 / 4.5-up |
| 118 | Brisket | 5.4-6.4 / 6.4-7.7 / 7.7-9.1 / 9.1-up |

Portion-cut (steak) weight ranges, given directly in ounces by IMPS:

- Item 1112, ribeye steak, boneless: 4 to 12 oz (113 to 340 g)
- Item 1180, strip loin steak, boneless: 6 to 20 oz (170 to 567 g)
- Item 1184, top sirloin butt steak, boneless: 4 to 24 oz (113 to 680 g)
- Item 1188/1189, tenderloin steak, bone-in / boneless: 3 to 8 oz / 4 to 14 oz (85 to 227 g / 113 to
  397 g)

General portion weight tolerance (IMPS 100, section 3.5.1): under 6.0 oz (170 g), +/- 1/4 oz (7 g);
6.0 to 12.0 oz (170 to 340 g), +/- 1/2 oz (14 g); 12.01 to 24.0 oz (341 to 680 g), +/- 3/4 oz (21 g);
24.01 oz (681 g) and over, +/- 1 oz (28 g). The same thickness tolerance table from section 1.2
applies here too.

No peer-reviewed measured population study for beef primal or steak dimensions or mass was found;
only USDA procurement class midpoints exist.

### 1.4 Salmon fillets

Machine specs:

- I-Cut 130 PortionCutter (fish): max product 980 x 270 x 150 mm, cutting speed up to 1000 cuts/min,
  belt speed 20 to 500 mm/s ([JBT Marel](https://jbtmarel.com/en/products/i-cut-130/fish/)).
- MSC 90/180 slicers: max product length 700 mm, max product height 40 to 45 mm; Marel's own
  benchmark throughput figures are calculated "at 1.2 kg fillets," which is a reference weight for
  stating a rate, not a measured mean. MSC 650-45 recommends a fillet temperature of -2 to +4 C
  for cutting ([Marel salmon slicing
  brochure](https://jbtmarel.com/media/pyxmiysb/salmon-slicing-marel.pdf)). That -2 C figure is the
  single most direct industrial confirmation found that portioning lines deliberately run product at
  or just below 0 C to firm it for a clean cut, matching the "crust-frozen" framing of this note.

A retail listing (weak, non-authoritative, not an industry grading standard) gives Norwegian salmon
fillets around 1.3 to 1.8 kg
([seafood-connection.com](https://seafood-connection.com/index.php/product/norwegian-salmon-fillet/)).
No authoritative size-class standard (Norwegian Seafood Council or equivalent) for fillet weight was
found; the commonly cited whole-fish weight classes at the Nasdaq Salmon Index refer to head-on-gutted
weight, not fillet weight, and could not be re-verified in this pass. No measured length x width x
thickness distribution for salmon fillets was found anywhere in this search.

### 1.5 Bacon slabs / pork bellies

USDA AMS IMPS Fresh Pork Series 400, item 408 (skin-on, boneless, as fed to slicing): weight classes
5.4-7.3 / 7.3-9.1 / 9.1-up kg (12-16 / 16-20 / 20-up lb); item 409 (skinless): 4.1-5.4 / 5.4-6.8 /
6.8-up kg (9-12 / 12-15 / 15-up lb). Dimensional control in this spec is relative, not absolute: no
side of the belly may be more than 2.0 in (5.0 cm) longer than the opposing side, and fat trim is
specified as distance from a scribe line, not an absolute slab length or width
([USDA AMS IMPS 400](https://www.ams.usda.gov/sites/default/files/media/IMPS_400_Fresh_Pork%5B1%5D.pdf)).
No vendor bacon-slicer datasheet with a numeric infeed slab dimension was found in this pass (Baader,
Marel, and Weber bacon-line pages either lacked numeric specs or returned errors during the search).

### Cross-cutting note on section 1

Nearly every hard number above is either a USDA procurement weight class (a trade band a buyer
selects, not a distribution) or a machine's maximum accepted envelope (a ceiling, not a typical
piece). Only chicken breast had a measured mass with a reported spread (SD or SE). No product in this
review had a measured population dimension dataset. Measuring a sample of the actual product on the
target line, length, width, thickness, and mass, with a caliper and a scale, before finalizing sim
ranges, would outrank everything in this section.

## 2. Mechanical properties

This is the hardest section to source well, and the literature does not converge cleanly. Numbers
below come from different species, muscles, temperatures, and loading modes; they are reported
separately rather than averaged together, because averaging across, say, rabbit tendon-adjacent
muscle and porcine gluteus would manufacture false precision.

### 2.1 Elastic modulus, compression

Bovine, raw, *longissimus dorsi*, 22 C, unconfined compression on an Instron with a 5.7 cm circular
punch, crosshead 5 cm/min, USDA Select beef within 48 h post mortem, linear region fitted up to 5%
strain: **E = 1.53 +/- 0.31 kPa** by direct mechanical measurement, 2.12 +/- 0.91 kPa by an
ultrasound-derived method that assumed a Poisson's ratio of 0.49 ([Chen et al. 1996, IEEE Trans
Ultrason Ferroelectr Freq Control](https://doi.org/10.1109/58.484478)). A companion study by the same
group, same species and setup, 10 samples, initial linear region below 2% strain: roughly 3.0 kPa on
the Instron, 6.0 kPa on a second mechanical rig, and 4.5 kPa by ultrasound; method-to-method spread
was 10 to 50%, occasionally reaching 100% (Chen, Novakofski, Jenkins, O'Brien, 1994 IEEE Ultrasonics
Symposium, DOI 10.1109/ULTSYM.1994.401848, PDF hosted at brl.uiuc.edu).

Porcine, raw, gluteus, pre-rigor (tested within 3 h post mortem, deliberately before rigor sets in),
unconfined compression, Cauchy stress at 30% strain, quasi-static rate (0.05%/s): fibre direction
0.63 +/- 0.14 kPa, cross-fibre 1.10 +/- 0.17 kPa; after a 300 s relaxation hold, fibre 0.61 +/- 0.11
kPa, cross-fibre 0.90 +/- 0.05 kPa ([Van Loocke, Lyons, Simms 2008, J
Biomech](https://doi.org/10.1016/j.jbiomech.2008.02.007)). Fitting a strain-dependent modulus model
to the same data gives a zero-strain tangent modulus of about 1.0 kPa along the fibre and 1.3 kPa
across it, both rising steeply and nonlinearly as compressive strain increases; by 30% strain the
tangent modulus is several times the zero-strain value. A related indentation study on the same
muscle type reports a long-term shear modulus of 700 +/- 300 Pa (Palevski et al. 2006, *J Biomech
Eng* 128(5):782-787, as reported inside Van Loocke 2008).

### 2.2 Elastic modulus, tension

Rabbit (species differs from the target list; included because it is the most complete tension
dataset found), extensor digitorum longus, fresh, linear modulus at low strain rate (0.05%/s, chosen
to suppress viscoelastic effects): longitudinal (along fibre) 447 +/- 97.7 kPa, transverse 22.4 +/-
14.7 kPa, longitudinal shear 3.87 +/- 3.39 kPa; ultimate stress longitudinal 163 +/- 75.7 kPa,
transverse 27.5 +/- 9.9 kPa; failure strain longitudinal 0.505 +/- 0.222, transverse 1.82 +/- 0.924
([Morrow, Haut Donahue, Odegard, Kaufman 2010, J Mech Behav Biomed
Mater](https://doi.org/10.1016/j.jmbbm.2009.03.004)). Gastrocnemius from the same group, with the
aponeurosis (the flat tendon sheet) left intact rather than dissected away: longitudinal 767 kPa,
transverse 81 kPa, roughly 1.7 times stiffer than the isolated-muscle values, showing the aponeurosis
carries a large share of tensile load.

Porcine, *longissimus dorsi*, fresh, uniaxial tension with optical non-contact strain measurement
(abstract-level detail only; the full text was paywalled in this pass): the transverse (cross-fibre)
response is broadly linear, about 77 kPa stress at a stretch ratio of 1.1, failing near 1.15; the
fibre-direction response is strongly nonlinear, about 10 kPa at the same stretch, failing much later
near 1.65 ([Takaza, Moerman, Gindre, Lyons, Simms 2013, J Mech Behav Biomed
Mater](https://doi.org/10.1016/j.jmbbm.2012.09.001)).

The Morrow paper quotes Van Loocke's porcine compression data recalculated at 30% strain as
longitudinal 2.04 kPa, transverse 4.56 kPa, two to three orders of magnitude below the rabbit tension
numbers. Tensile and compressive moduli of muscle are not interchangeable, and the gap between species
and loading modes here is large enough that picking "the" modulus for a simulation is a judgment
call, not a lookup.

### 2.3 Anisotropy: fibre direction is not consistently the stiff or the soft one

The direction of anisotropy reported in the literature is inconsistent, and that inconsistency is
itself the finding worth carrying into a sim design decision.

- Compression, porcine (Van Loocke 2008): cross-fibre stiffer than fibre, ratio about 1.76 at 30%
  compression by direct Cauchy stress, or about 2.24 by the fitted modulus model at the same strain.
  At a faster compression rate (5%/s) the same paper reports the trend inverts and the fibre direction
  becomes the stiffer one.
- Tension, porcine (Takaza 2013): cross-fibre stiffer, ratio about 7.7 at a stretch of 1.1.
- Tension, rabbit (Morrow 2010): the opposite direction, fibre stiffer than cross-fibre, ratio about
  20 for isolated muscle or about 9.5 with the aponeurosis intact. Morrow's own discussion flags this
  contradiction against Van Loocke directly and attributes it to species, loading mode, or aponeurosis
  presence, without resolving which.
- Chicken pectoralis, both modes (abstract only, full text paywalled): tensile response is two orders
  of magnitude larger than compressive in every direction tested; in compression the cross-fibre
  direction is stiffest, matching the porcine compression result; in tension the 45-degree direction
  is stiffest, which the authors note differs from the porcine tension result
  ([Mohammadkhah, Murphy, Simms 2016, J Mech Behav Biomed
  Mater](https://doi.org/10.1016/j.jmbbm.2016.05.021)).

Do not carry a single anisotropy ratio across species or loading modes. If the sim needs one number,
state which species, which mode (tension vs compression), and which strain rate it came from.

### 2.4 Poisson's ratio

Measured values in tension: Takaza et al. 2013, porcine *longissimus dorsi*, report four separate
ratios: V_LT = V_LT' = 0.47, V_TT' = 0.28, V_TL = 0.74 (confirmed directly against the abstract text).
A second measured value, on a different tissue: bovine extraocular muscle, tension, micro-CT
elongation to 30 to 35% strain at 37 C, gives V = 0.457 +/- 0.004 across 14 specimens ([Kim, Yoo,
Shin, Demer 2013, BioMed Res Int](https://doi.org/10.1155/2013/197479)).

Outside those two measurements, Poisson's ratio for skeletal muscle is almost always assumed, not
measured, at a value near 0.45 to 0.4999 to represent near-incompressibility (Chen et al. 1996 assumed
0.49 for their ultrasound correction; a review of finite-element soft-tissue models found reported
values spanning 0.4500 to 0.4999 with no single value fitting all loading conditions, arXiv:2312.04108).
No compression-mode measurement of Poisson's ratio for intact skeletal muscle was found in this search;
that is a real gap, not an oversight of this note.

### 2.5 Viscoelasticity and stress relaxation

Raw chicken breast, non-myopathic control tissue, compression to 30% strain at 4 C, five-parameter
generalized Maxwell fit: fast time constant tau_1 = 2.49 +/- 0.15 s, slow time constant tau_2 = 21.10
+/- 0.69 s ([Li et al. 2021, Foods](https://doi.org/10.3390/foods10010195)). This is the most directly
usable time-constant pair found for raw poultry at a temperature close to the fresh-chilled range this
cell will run in.

Rat tibialis anterior, in vivo, transverse compression, incompressible Ogden viscoelastic fit:
tau = 6.01 +/- 0.42 s (Bosboom, Hesselink, Oomens, Bouten, Drost, Baaijens 2001, *J Biomech* 34(11):
1365-1368, DOI 10.1016/S0021-9290(01)00083-5). In porcine gluteus, the viscoelastic contribution is
roughly half of the total stress response at a compression rate of 0.5%/s (Van Loocke 2008).

Flagged as not applicable: processed, comminuted chicken sausage shows relaxation times of roughly
2500 to 5000 s at 25 C (Andres, Zaritzky, Califano 2008, *Meat Science* 79(3):589-594, DOI
10.1016/j.meatsci.2007.12.013), two to three orders of magnitude longer than the intact-muscle values
above. A comminuted, formulated product is not a valid stand-in for intact fibrous muscle; it is
included here only to warn against reusing a "chicken relaxation time" number without checking whether
the sample was whole muscle or emulsified product.

### 2.6 Shear force, cutting force, and toughness

The standard meat-science toughness measurement, Warner-Bratzler shear force (WBSF), is defined and
validated on **cooked** meat: crosshead 200 or 250 mm/min, a 1.27 cm diameter core taken parallel to
the fibre direction so the blade shears across the fibres, minimum six cores per sample, steaks
chilled to 2 to 5 C only to firm them for clean coring before cooking and shearing ([Wheeler,
Shackelford, Koohmaraie 1997, Proc Recip Meat
Conf](https://www.ars.usda.gov/ARSUserFiles/30400510/1997500068.pdf)). No AMSA-family protocol for
raw-meat shear force was found; WBSF as an instrument does not apply to raw product.

Beef WBSF tenderness categories (cooked): very tender at or below 3.4 kgf, slightly tender 3.41 to
4.40 kgf, slightly tough 4.41 to 5.40 kgf, very tough above 5.40 kgf, with bid price in one consumer
study falling by $1.02/kg for every 1 kgf increase in shear force ([Platter, Tatum, Belk, Koontz,
Chapman, Smith 2005, J Anim Sci](https://doi.org/10.2527/2005.834890x), PMID 15753345, confirmed
directly against the abstract). A separate threshold of 4.6 kgf as the boundary of "slightly tender"
consumer acceptability is widely cited from Shackelford et al. 1991, reproduced in Wheeler et al. 1997
above.

Raw cutting-force data, the actual gap this note is meant to expose: no WBSF-equivalent, standardized
raw-meat shear or cutting force protocol was found anywhere in this search. Two adjacent data points
exist. Waterjet cutting of raw boneless chicken breast needed 179 to 224 MPa water pressure at a
nozzle traverse speed at or below 100 mm/s (0.127 mm orifice) to produce a clean cut ([Bansal and
Walker 1999, J Food Process Eng](https://doi.org/10.1111/j.1745-4530.1999.tb00487.x), abstract only,
not convertible to a blade force without further assumptions about the cutting mechanism). Single
porcine muscle fibres fracture in tension at 10.9% extension when raw, versus 130% extension after
cooking (1 h at 80 C), a more than tenfold difference in failure strain between raw and cooked tissue
(Mutungi, Purslow, Warkup 1995, *Meat Science* 40(2):217-234, DOI 10.1016/0309-1740(94)00054-B). That
raw-versus-cooked gap matters directly for this cell: any mechanical parameter borrowed from a cooked-
meat study (which is most of the WBSF literature) likely understates the toughness and failure strain
of the raw product this cell actually handles.

### 2.7 Temperature: fresh chilled versus crust-frozen versus frozen

No source in this search reports a continuous modulus-versus-temperature curve for raw whole muscle
spanning the fresh-chilled-to-crust-frozen range (roughly +4 to -2 C). The two papers most likely to
answer this directly, on cutting-force behavior of frozen meat under an oscillating knife, could not
be accessed in this pass (King 1997, *Meat Science* 46(4):387-399, DOI
10.1016/S0309-1740(97)00033-8; King 1999, *Meat Science* 51(3):261-269, DOI
10.1016/S0309-1740(98)00132-6; both paywalled). These are the highest-priority items to obtain before
trusting any temperature-dependent modulus number in a customer deliverable.

What is documented: a partial-freezing and superchilling study on beef held at -5, -4, -2.8, -1.8, 2,
and 6 C for 21 days found firmness decreasing with storage time at every temperature, fit to a
first-order kinetic model with an Arrhenius activation energy of 52.87 kJ/mol for the firmness decay
([Mwakosya, Alvarez, Ndoye 2025, Foods](https://doi.org/10.3390/foods14152687)). That is a kinetic
model of firmness loss over days of storage, not an instantaneous modulus-versus-temperature
relationship, and the paper's absolute firmness values per temperature were not retrievable in this
pass (MDPI blocked full-text access).

Crust freezing as an industrial practice is documented at the process-parameter level. Chicken surface
crust-freezing has been tested at -5, -15, and -27 C setpoints in a microbiology study, which also
found crust freezing increased drip loss, more so at the colder setpoints ([Haughton, Lyng, Cronin,
Fanning, Whyte 2012, Food Microbiology](https://doi.org/10.1016/j.fm.2012.05.004)). Crust-freeze air
chilling of turkey breast at -12 C and 1.0 m/s air velocity brought the meat core to 4 C in 1 to 1.5 h,
versus 5.5 h for water-immersion chilling to the same endpoint ([Medellin-Lopez, Sansawat, Strasburg,
Marks, Kang 2014, Poultry Science](https://doi.org/10.3382/ps.2013-03531)). Marel's own salmon slicer
datasheet recommends a fillet temperature of -2 to +4 C for cutting (cited in section 1.4), the
clearest confirmation that real lines deliberately run product at or just below 0 C to firm it, without
freezing it solid.

The practical takeaway: "crust-frozen" in the industrial sense means a thin, firmed or lightly frozen
surface layer over a liquid, unfrozen core, not a fully frozen block. Modeling this as a stiffened
outer shell over a soft core is a defensible simulation approximation, but no source in this search
quantifies how much stiffer that shell is in kPa; that gap is called out explicitly in section 5 and
should be closed with the customer's own hardness measurement of their crust-frozen product, not
guessed. Meat's initial freezing point is commonly reported as roughly -1 to -2 C, lower than pure
water because of dissolved solutes in the tissue fluid (unverified: this is a widely repeated
food-science fact, but no primary source measuring it for the specific products in section 1 was
checked in this pass).

### 2.8 Friction

Chicken fillet against stainless steel: coefficient of friction 0.5. This number comes from a real,
recent, open-access paper, but it was back-calculated by fitting a physics simulation of a fillet
sliding off a conveyor ledge to observed behavior on a real poultry line, not measured directly on a
tribometer; the steel finish, wet-or-dry state, normal load, and sliding speed behind that fit could
not be confirmed in this pass because the publisher blocked full-text access ([Vink, Shi, Jovanova,
Kortlever, Schott 2026, Applied Food
Research](https://doi.org/10.1016/j.afres.2026.101880)). Treat 0.5 as a provisional, one-source value,
not a settled tribology measurement.

No friction data for pork, beef, or salmon against stainless steel was found. No friction data for any
species against food-grade conveyor belting material (PVC, polyurethane, or modular plastic), wet or
dry, was found anywhere in this search. This is the single thinnest area in the entire review. Generic
engineering figures exist for rubber against steel (dry roughly 0.5 to 0.6, water-lubricated below
0.2), but those come from bulk-materials-handling references, not food tribology, and should not be
attributed to meat; they are noted here only as an order-of-magnitude sanity check that wet friction
drops sharply relative to dry, a pattern plausible for meat on a belt but unconfirmed for meat
specifically.

### 2.9 Density

The ICRU-44 reference composition for "muscle, skeletal" gives 1.04 g/cm3 (1040 kg/m3), a standardized
tissue-substitute value used in radiation dosimetry, not a direct measurement of a real cut (ICRU
Report 44, 1989, values hosted at [NIST](https://physics.nist.gov/cgi-bin/Star/compos.pl?matno=201)).
Rabbit skeletal muscle, measured directly across many anatomical regions and three age cohorts, gives
a recommended single constant of 1.0558 g/cm3 (1055.8 kg/m3) for adults and 1.0502 g/cm3 (1050.2
kg/m3) for juveniles, with a note that density varies significantly by anatomical region and rises
with age ([Leonard, Worden, Boettcher, Dickinson 2021, Sci
Rep](https://doi.org/10.1038/s41598-021-81489-w)). Directly measured on chicken by Archimedes buoyancy
method, n = 9 broilers, chilled to 5 C, 24 h post slaughter: 1041 to 1068 kg/m3 for meat from
ritually-bled birds, 1036 kg/m3 for meat from birds not bled per that protocol, and 1021 to 1022 kg/m3
for unbled birds, with the paper noting SD in the range of 5.3 to 15.6% of 1000 kg/m3 across groups
(Adam, Sulieman, Elssfah, Veettil 2017, *Advances in Bioresearch* 8(6):154-160, open PDF at
soeagra.com). That same source also reports pork at 970 kg/m3 and blood at 620 kg/m3, both attributed
to a secondary citation the authors did not themselves measure; 970 kg/m3 for lean pork muscle is
below water and physically implausible for intact muscle, so do not use it.

Across these three independent measurements the working range is roughly 1020 to 1070 kg/m3,
converging near 1040 to 1060 kg/m3. No dedicated primary density measurement for pork loin, beef
muscle, or salmon muscle specifically was found; using the chicken and rabbit range across species is
an extrapolation, not a species-specific measurement.

## 3. Presentation on the belt

Belt speeds documented on real portioning-line vendor spec sheets cluster in a fairly narrow band. The
I-Cut 130 fish portioner states an infeed belt speed range of 20 to 500 mm/s (1.2 to 30 m/min)
alongside a cutting rate up to 1000 cuts/min ([JBT Marel](https://jbtmarel.com/en/products/i-cut-130/fish/)).
FleXicut Salmon states a maximum belt speed of 0.38 m/s (22.8 m/min) at 36 fillets/min ([JBT
Marel](https://jbtmarel.com/en/products/flexicut-salmon/)); a separate FleXicut product page states
50 fillets/min for what appears to be a different configuration, and the two vendor pages were not
reconciled in this search. A poultry StripCutter/Splitter states belt speed up to 30 m/min ([JBT
Marel](https://jbtmarel.com/en/products/stripcutter-splitter-poultry/)). No numeric belt speed was
found for any bacon or pork-loin-specific line; the JBT DSI waterjet portioner and Treif slicer
datasheets publish cut rates and blade RPM but not belt speed.

Throughput: I-Cut 122 (poultry) states 2000 cuts/min per lane, dual lane ([JBT
Marel](https://jbtmarel.com/en/products/i-cut-122-portioncutter/poultry/)); BAADER 358 (fish) states
2170 to 2200 cuts/min single lane ([Baader](https://www.baader.com/product/baader-358)); Marel
SingleFeed, a dedicated singulator, states it singulates up to 200 pieces/min per lane for boneless
poultry pieces weighing 5 to 400 g, on a lightly moistened belt, with "no manual input" ([JBT
Marel](https://jbtmarel.com/en/products/singlefeed/)).

How pieces get onto the belt in the first place, and how they sit once there, is documented at the
level of mechanism, not numbers. Three mechanisms recur across vendor and research sources:

1. **Mechanical singulation and alignment upstream.** Key Technology sells a three-stage vibratory
   feed built specifically for meat, poultry, and seafood ahead of robotic pick-and-place: a
   "Separating Shaker" that spreads product evenly, a "Singulating Shaker" that lanes it into single
   file, and an "Aligning Shaker" that orients it, describing this precision as "atypical in
   conventional conveying systems," meaning raw product does not arrive well-spaced or aligned on its
   own ([Key Technology](https://www.food-safety.com/articles/8962-new-conveying-systems-for-robotic-pick-and-place-packaging-from-key-technology)).
2. **A dedicated singulator with vision behind it**, such as Marel SingleFeed above, or Marel
   RoboOptimizer, which scans each fillet with a laser for length, width, and orientation and uses a
   robot to reposition it into the correct lane before cutting, explicitly to avoid cutting across the
   fibre grain ([JBT Marel RoboOptimizer](https://jbtmarel.com/en/news/get-to-know-the-7-ps-of-the-robooptimizer-for-i-cut-122/)).
3. **Accept an uncontrolled pose off the upstream process and measure it per piece with vision
   immediately before the robot acts.** Ahlin (2022) states this directly for poultry rehang: "the
   relative position and orientation of the bird are not predictable," solved with RGB-D sensing
   rather than fixturing ([Ahlin 2022, Animal
   Frontiers](https://pmc.ncbi.nlm.nih.gov/articles/PMC9056036/)). Khodabandehloo (2022) lays out a
   three-way taxonomy for how a robot can be given a known pose: the robot itself performs the
   separation, a fixture presents the meat in a known position and orientation with the carcass held
   static, or the carcass sits on a moving conveyor with the robot tracking its motion, which is the
   mode closest to this cell's scenario ([Khodabandehloo 2022, Animal
   Frontiers](https://pmc.ncbi.nlm.nih.gov/articles/PMC9056033/)).

No source found in this search gives a numeric yaw-angle distribution, piece-to-piece spacing, or
overlap and touching rate for loose meat, poultry, or fish pieces on a flat belt. The closest anchor
found anywhere is shackle center-to-center pitch on whole-bird poultry cut-up lines, 10 to 12 inches
(254 to 305 mm), which describes hanging carcasses on hooks, not loose pieces on a belt, and should
not be reused directly, only as an order-of-magnitude reference for how tightly a line can pack
product ([Foodmate, via Meat+Poultry](https://www.meatpoultry.com/articles/28355-thriving-in-the-next-phase)).
Yaw distribution, spacing, and overlap rate for this sim are assumptions; how wide to set them should
depend on which of the three mechanisms above the target line actually uses.

A 2025 review reports 3D machine vision achieving 85 to 92% cutting accuracy on meat versus 70 to 80%
for 2D vision ([Frontiers in Robotics and AI
2025](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2025.1578318/full)).
The relevant implication for a simulation meant to stress-test a perception-and-control pipeline: real
lines with real vision systems still miss or misplace 8 to 30% of the time, so a sim built to validate
that pipeline should not assume near-perfect pose knowledge as its baseline case.

## 4. What varies and breaks assumptions

**Exudate and purge.** Lean fresh meat is roughly 70% water by mass ([CSIRO Meat Technology
Update 02/6](https://meatupdate.csiro.au/data/MEAT_TECHNOLOGY_UPDATE_02-6.pdf)). Drip loss from
primals in the first 48 h after boning typically runs 1 to 10 mL/kg (0.1 to 1%); vacuum-packed primals
commonly show 1 to 2%, while individual cut or trimmed pieces can reach 5 to 10% (same CSIRO source).
Pork carcass drip loss runs 2.4 to 3% at typical commercial lines, versus 1.4% on a reported low-drip
line ([Genesus/The Pig Site 2023](https://www.thepigsite.com/news/2023/09/genesus-technical-report-drip-loss-the-hidden-loss)).
A commercial Japanese pork loin study measured mean drip of 2.89% (range 1.00 to 7.62%) at 4 C over
24 h, correlated with pH ([PMC5933991](https://pmc.ncbi.nlm.nih.gov/articles/PMC5933991/)). Chicken
breast drip accumulates close to linearly with time rather than front-loading: one method reports
1.72%, 2.70%, and 3.62% at 24, 48, and 72 h, a rate of roughly 0.04% per hour for 10 to 20 mm thick
samples ([PMC8068865](https://pmc.ncbi.nlm.nih.gov/articles/PMC8068865/)). The implication for a sim:
belt-surface wetness and any friction model tied to it should drift over the length of a shift, not
sit at a single fixed value.

**Fat versus lean under variable lighting.** Naive color-threshold segmentation (Otsu) achieved 99.77%
fat detection but a 41.24% false-positive rate on beef marbling images, because frost and specular
reflection visually resemble fat; a homomorphic-filtering approach brought the false-positive rate down
to 4.97% at 92.68% detection ([Sensors 2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC13306314/)). A
sim built to validate a perception system should model illumination artifacts and specular highlights
on wet meat, not treat fat and lean as cleanly color-separable classes.

**Sticking to the belt.** Conveyor belt vendors design specifically against this: Intralox's Series
800 Nub Top uses raised nubs to reduce belt-to-product contact area and aid release, explicitly framed
as solving a "considerable problem" in poultry handling, and Series 560 in polyketone is marketed to
"reduce stickiness" on meat and poultry lines ([Intralox meat/poultry
page](https://www.intralox.com/industries/food/meat-poultry)). No quantitative before-and-after
friction or adhesion number was found; treat this as a qualitative confirmation that stock flat belting
in a naive sim will overstate sticking relative to production belting engineered against it.

**Folding, curling, and non-flat presentation.** Real lines pay for a dedicated correction step for
this rather than treating it as an edge case. Marel RoboOptimizer (cited in section 3) exists to scan
each fillet's actual shape and reposition it before cutting; SmartSplitter and a dedicated Flattening
Machine exist upstream purely to normalize fillet thickness before portioning
([JBT Marel](https://jbtmarel.com/en/poultry/broilers/portion-cutting/)). A vision-guided robot
deployment at a seafood processor reshapes breaded fish fillets that arrive non-flat, scaling from 4
to 20 units within a year ([Vision Systems
2024](https://www.vision-systems.com/factory/robotics/article/55240964/vision-guided-robot-shapes-breaded-fish-into-uniform-shapes)).
A flat rigid slab is a simplification this note's own sources treat as false often enough to build
dedicated machinery around; say so explicitly when presenting sim results.

**Membranes and silverskin.** The epimysium (silverskin) is a fascia sheath, mostly collagen with an
elastin component, that does not gelatinize on cooking and stays tough, which is why it is trimmed
([Silver skin, Wikipedia, citing McCracken 1999](https://en.wikipedia.org/wiki/Silver_skin)).
Quantitatively, intramuscular connective tissue shear resistance in wooden-breast-affected broiler
muscle rises from 2.05 N in normal tissue to 5.55 N in severely affected tissue, a 171% increase,
alongside a 67 to 90% increase in collagen fibril diameter
([PMC10297311](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10297311/)). No tensile or shear modulus
for silverskin itself, as distinct from intramuscular connective tissue, was found in this search;
that is the single largest quantitative gap in the mechanical-properties section. A 2025 review notes
that automated trimming on red meat is harder than on more uniform product precisely because "its
greater deformability... necessitates constant adaptation of the cutting trajectory," and that force
feedback improves accuracy but reduces throughput ([Frontiers in Robotics and AI
2025](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2025.1578318/full)).

**Bone fragments.** Boneless poultry product is capped by regulation at 1% bone solids by weight (9
CFR 381.117, [Cornell LII](https://www.law.cornell.edu/cfr/text/9/381.117)); mechanically separated
poultry must have at least 98% of bone particles at or below 1.5 mm and none above 2.0 mm (9 CFR
381.173). Marel's SensorX X-ray system states 99% detection of bone fragments larger than 2 mm with a
false-positive rate at or below 3% ([JBT
Marel](https://jbtmarel.com/en/products/sensorx-x-ray-bone-inspection-system/)); a third-party
inspection vendor states it has found fragments as small as 0.7 mm that had already passed inline
detection ([FlexXray](https://flexxray.com/bone-and-organic-material-contamination-in-food-staging/)).
No population-level prevalence rate (fragments per kg of boneless product) was found in any FSIS
source; this is a known and regulated risk with no published base rate.

**Temperature drift over a shift.** FSIS defines the food-safety danger zone as 4.4 to 60 C (40 to
140 F), in which bacteria can double in as little as 20 minutes ([FSIS Danger
Zone](https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/food-safety-basics/danger-zone-40f-140f)).
Trade-source design targets for beef fabrication rooms specify air temperature 4 to 7 C +/- 1 C,
product surface critical limit 7 C, and a product weight-loss target of 0.1 to 0.3% per 8 h shift
([engineering trade reference, not independently verified against a regulatory
primary](https://ingener.by/refrigeration-systems/food-processing-refrigeration/meat-processing/beef-processing/fabrication-rooms/)).

**Sanitation cycles.** 9 CFR Part 416 requires written Sanitation SOPs, pre-operational cleaning
procedures completed before production starts, specified frequencies for all other cleaning, and daily
records retained at least 6 months ([9 CFR
416.12-416.17](https://www.law.cornell.edu/cfr/text/9/416.12)). Trade-press sources report the average
plant running roughly 20 h of production before a 4 h sanitizing shutdown, with allergen-specific
cleanups taking 2 to 4 h ([Provisioner](https://www.provisioneronline.com/articles/103139-sanitation-in-meat-and-poultry-plants),
[Food Engineering](https://www.foodengineeringmag.com/articles/7-steps-for-minimizing-downtime-during-cleaning-shutdowns)).
No formal source for the temperature-recovery time or restart-verification duration after a washdown
was found; only the regulatory requirement for a documented pre-operational SSOP check before restart
is confirmed.

## 5. Simulation implications

Worked example: a MuJoCo rigid or flex body representing a 180 x 90 x 30 mm slab (roughly a large
chicken breast fillet or a small pork chop). Volume = 4.86e-4 m3.

| Property | Simulator parameter | Recommended starting value | Status |
|---|---|---|---|
| Mass | body mass (kg) | 4.86e-4 m3 x ~1050 kg/m3 = approx. 0.51 kg | Computed from a measured density (section 2.9); not itself a direct measurement of a slab this size. |
| Half extents | geom size (m) | 0.090, 0.045, 0.015 | Assumption: represents the slab as a rigid box. Real fillets are irregular and taper in thickness along their length (section 1.1), so this understates shape variability. |
| Friction, dry, meat on stainless steel | geom friction[0] | 0.5 | Provisional measured: single source (Vink et al. 2026), back-calculated from a simulation fit, not a tribometer reading. Treat as a starting point pending verification. |
| Friction, wet, or meat on plastic belting (any state) | geom friction[0] | 0.2 to 0.3 as a lowered placeholder | Assumption: no food-specific wet-friction or belt-friction number exists in the literature reviewed (section 2.8). Borrowed order-of-magnitude only from non-food engineering references. |
| Contact softness | solref, solimp | Soften from MuJoCo rigid-body defaults, e.g. solref = "0.02 1", loosen solimp to admit a few mm of local compliance | Assumption: no direct kPa-to-solref mapping exists. The measured small-strain moduli in section 2.1-2.2 (roughly 1 to 5 kPa) are far softer than a default rigid contact; the exact softening factor is a tuning choice to reproduce observed grasp and belt-contact behavior, not a derived value. |
| Flex Young's modulus | flexcomp elasticity, E | 1 to 5 kPa small-strain baseline (fresh, cross-fibre direction, quasi-static), rising nonlinearly with strain | Measured (Van Loocke et al. 2008, porcine gluteus), but flag that MuJoCo flex solvers often need stiffness inflated 10 to 100x above the physical value for numerical stability at practical timesteps. If you do this, log it as a numerical choice, not a physical property. |
| Flex Poisson's ratio | flexcomp poisson | 0.45 | Assumption: measured values run 0.47 to 0.49 (Takaza 2013, Kim 2013), but flex/FEM solvers are commonly detuned lower to avoid volumetric locking. State the detuning explicitly rather than reporting 0.45 as a physical property. |
| Flex damping | flexcomp damping | Tune so the fast relaxation mode matches a time constant near 2 to 3 s | Measured basis: Li et al. 2021, raw chicken breast at 4 C, tau_1 = 2.49 s, tau_2 = 21.1 s (section 2.5). MuJoCo flex exposes a single damping term; use the fast constant since contact events in this cell happen on 0.1 to 1 s timescales. |
| Anisotropy (across-fibre vs along-fibre stiffness) | per-direction stiffness scaling in flex, if the element supports it | Ratio approximately 1.5 to 2x, cross-fibre stiffer than along-fibre, in compression at 30% strain | Measured, porcine, compression only (section 2.3). Do not treat as universal; tension-mode and rabbit data reverse the direction. |
| Crust-frozen shell stiffness | stiffer outer contact/flex layer, if modeling a firmed surface | No literature value found; raise the outer few mm's modulus by at least an order of magnitude over the fresh-chilled baseline as a starting assumption | Unverified (unsourced): flag to the customer explicitly as needing a plant-side hardness measurement of their actual crust-frozen product, since this is exactly the process condition several real portioning lines use (section 2.7). |

## 6. Open questions the customer must answer

- What is the measured mass and dimension distribution (mean, SD, min/max) of the actual product on
  their line? Nothing in the literature reviewed gives a piece-level population distribution for pork,
  beef, or salmon, and only partial data exists for chicken breast.
- Do they run a singulator or aligner upstream (a Key Technology-style shaker stage, a Marel
  SingleFeed or RoboOptimizer), or does the piece genuinely arrive with an uncontrolled pose? This
  decides whether the sim's yaw and spacing assumptions should be tight or wide.
- What belt material and surface condition do they actually run, wet or dry, and can they measure a
  friction coefficient for their specific product against it? No source in this review measured
  meat-on-plastic-belting friction at all.
- Is their "crust-frozen" state a firmed surface skin over a soft core, or closer to fully hard-frozen
  through? That distinction determines whether a two-layer (stiff shell, soft core) sim model or a
  single stiffened modulus is the right approximation, and no source quantified the difference.
- What is their pose-error tolerance at the cutter (lane offset, yaw, thickness variation), and is it
  set by yield economics or by a hard mechanical limit of the cutter itself?
- Can they run, or commission, an in-house compression test on their specific raw product at their
  process temperature? Every modulus number in section 2 comes from a different species, muscle, or
  temperature than the customer's exact product; one in-house test at the line's actual temperature
  would outrank most of this note.

## Related entries

- [[library/topics/meat-cutting-automation]] (the cell, conveyor, and hygiene envelope this note feeds)
- [[library/topics/deformable-object-manipulation]] (how to represent and simulate the object once you
  have these numbers)
- [[library/topics/grasp-selection-for-soft-slabs]] (what the beam-mechanics grasp rule does with
  modulus and thickness)
- [[library/topics/meat-cell-architecture]] (where these numbers plug into the S1 cell-physics
  subsystem)

## Sources

- Product envelope, machine specs: MARELEC PORTIO 3-300 https://www.marelec.com/industries/poultry/portioning/portion-cutter-portio-3-300/ ; Marel I-Cut 36 (reseller listing) https://www.normartrading.no/en/products/marel-i-cut-36/ ; JBT Marel I-Cut 122 TrimSort https://jbtmarel.com/en/products/i-cut-122-portioncutter/poultry/ ; JBT Marel I-Cut 130 fish https://jbtmarel.com/en/products/i-cut-130/fish/ ; Marel salmon slicing brochure (MSC series) https://jbtmarel.com/media/pyxmiysb/salmon-slicing-marel.pdf ; JBT Marel FleXicut Salmon https://jbtmarel.com/en/products/flexicut-salmon/ ; JBT Marel FleXicut https://jbtmarel.com/en/products/flexicut/ ; JBT Marel StripCutter/Splitter poultry https://jbtmarel.com/en/products/stripcutter-splitter-poultry/ ; BAADER 358 https://www.baader.com/product/baader-358 ; Marel SingleFeed https://jbtmarel.com/en/products/singlefeed/ ; JBT Marel RoboOptimizer https://jbtmarel.com/en/news/get-to-know-the-7-ps-of-the-robooptimizer-for-i-cut-122/ ; JBT Marel SmartSplitter/Flattening https://jbtmarel.com/en/poultry/broilers/portion-cutting/ ; JBT Marel SensorX https://jbtmarel.com/en/products/sensorx-x-ray-bone-inspection-system/ ; Key Technology conveying for robotic pick-and-place https://www.food-safety.com/articles/8962-new-conveying-systems-for-robotic-pick-and-place-packaging-from-key-technology ; Intralox meat and poultry https://www.intralox.com/industries/food/meat-poultry ; seafood-connection.com salmon fillet listing (weak source) https://seafood-connection.com/index.php/product/norwegian-salmon-fillet/ ; Foodmate cut-up rate via Meat+Poultry https://www.meatpoultry.com/articles/28355-thriving-in-the-next-phase
- USDA procurement and grading: USDA AMS Chicken Breast Grade A https://www.ams.usda.gov/book/chicken-breast-grade ; USDA AMS IMPS Fresh Pork Series 400 https://www.ams.usda.gov/sites/default/files/media/IMPS_400_Fresh_Pork%5B1%5D.pdf ; USDA AMS IMPS Fresh Beef Series 100 https://www.ams.usda.gov/sites/default/files/media/IMPS_100_Fresh_Beef%5B1%5D.pdf
- Measured product mass and yield: Lake, Brannick, Papah, Lousenberg, Velleman, Abasht 2020, Front Physiol, PMC7154160 https://pmc.ncbi.nlm.nih.gov/articles/PMC7154160/ ; Islam et al. 2026, J Adv Vet Anim Res, PMC13197668 https://pmc.ncbi.nlm.nih.gov/articles/PMC13197668/
- Muscle mechanics, modulus and anisotropy: Chen, Novakofski, Jenkins, O'Brien 1996, IEEE Trans Ultrason Ferroelectr Freq Control, DOI 10.1109/58.484478 https://doi.org/10.1109/58.484478 ; Chen et al. 1994 IEEE Ultrasonics Symposium (brl.uiuc.edu PDF) ; Van Loocke, Lyons, Simms 2008, J Biomech, DOI 10.1016/j.jbiomech.2008.02.007 https://doi.org/10.1016/j.jbiomech.2008.02.007 ; Van Loocke, Lyons, Simms 2006, J Biomech, DOI 10.1016/j.jbiomech.2005.10.016 ; Morrow, Haut Donahue, Odegard, Kaufman 2010, J Mech Behav Biomed Mater, DOI 10.1016/j.jmbbm.2009.03.004 https://doi.org/10.1016/j.jmbbm.2009.03.004 ; Takaza, Moerman, Gindre, Lyons, Simms 2013, J Mech Behav Biomed Mater, DOI 10.1016/j.jmbbm.2012.09.001 https://doi.org/10.1016/j.jmbbm.2012.09.001 ; Mohammadkhah, Murphy, Simms 2016, J Mech Behav Biomed Mater, DOI 10.1016/j.jmbbm.2016.05.021 https://doi.org/10.1016/j.jmbbm.2016.05.021
- Poisson's ratio: Kim, Yoo, Shin, Demer 2013, BioMed Res Int, PMC3591112, DOI 10.1155/2013/197479 https://doi.org/10.1155/2013/197479 ; Fougeron, Trebbi, Keenan, Payan, Chagnon, arXiv:2312.04108 https://arxiv.org/abs/2312.04108
- Viscoelasticity and relaxation: Li, Yang, Zhang, Lu, Zhang, Qi, Wang, Xu 2021, Foods, DOI 10.3390/foods10010195, PMC7835742 https://doi.org/10.3390/foods10010195 ; Bosboom, Hesselink, Oomens, Bouten, Drost, Baaijens 2001, J Biomech, DOI 10.1016/S0021-9290(01)00083-5 ; Andres, Zaritzky, Califano 2008, Meat Science, DOI 10.1016/j.meatsci.2007.12.013
- Shear force, cutting force, and toughness: Wheeler, Shackelford, Koohmaraie 1997, Proc Recip Meat Conf, USDA-ARS PDF https://www.ars.usda.gov/ARSUserFiles/30400510/1997500068.pdf ; Platter, Tatum, Belk, Koontz, Chapman, Smith 2005, J Anim Sci, DOI 10.2527/2005.834890x https://doi.org/10.2527/2005.834890x ; Bansal and Walker 1999, J Food Process Eng, DOI 10.1111/j.1745-4530.1999.tb00487.x https://doi.org/10.1111/j.1745-4530.1999.tb00487.x ; Mutungi, Purslow, Warkup 1995, Meat Science, DOI 10.1016/0309-1740(94)00054-B
- Temperature effects: King 1997, Meat Science, DOI 10.1016/S0309-1740(97)00033-8 (inaccessible, priority follow-up) ; King 1999, Meat Science, DOI 10.1016/S0309-1740(98)00132-6 (inaccessible, priority follow-up) ; Mwakosya, Alvarez, Ndoye 2025, Foods, DOI 10.3390/foods14152687 https://doi.org/10.3390/foods14152687 ; Haughton, Lyng, Cronin, Fanning, Whyte 2012, Food Microbiology, DOI 10.1016/j.fm.2012.05.004 https://doi.org/10.1016/j.fm.2012.05.004 ; Medellin-Lopez, Sansawat, Strasburg, Marks, Kang 2014, Poultry Science, DOI 10.3382/ps.2013-03531 https://doi.org/10.3382/ps.2013-03531
- Friction: Vink, Shi, Jovanova, Kortlever, Schott 2026, Applied Food Research, DOI 10.1016/j.afres.2026.101880 https://doi.org/10.1016/j.afres.2026.101880
- Density: ICRU Report 44 muscle composition, hosted at NIST https://physics.nist.gov/cgi-bin/Star/compos.pl?matno=201 ; Leonard, Worden, Boettcher, Dickinson 2021, Sci Rep, DOI 10.1038/s41598-021-81489-w https://doi.org/10.1038/s41598-021-81489-w ; Adam, Sulieman, Elssfah, Veettil 2017, Advances in Bioresearch 8(6), open PDF https://soeagra.com/abr/abr_nov2017/23.pdf
- Belt presentation and pose: Ahlin 2022, Animal Frontiers, PMC9056036 https://pmc.ncbi.nlm.nih.gov/articles/PMC9056036/ ; Khodabandehloo 2022, Animal Frontiers, PMC9056033 https://pmc.ncbi.nlm.nih.gov/articles/PMC9056033/ ; Frontiers in Robotics and AI review 2025 https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2025.1578318/full
- What varies and breaks assumptions: CSIRO Meat Technology Update 02/6 https://meatupdate.csiro.au/data/MEAT_TECHNOLOGY_UPDATE_02-6.pdf ; Genesus/The Pig Site 2023 https://www.thepigsite.com/news/2023/09/genesus-technical-report-drip-loss-the-hidden-loss ; pork loin drip loss PMC5933991 https://pmc.ncbi.nlm.nih.gov/articles/PMC5933991/ ; chicken breast drip timeline PMC8068865 https://pmc.ncbi.nlm.nih.gov/articles/PMC8068865/ ; fat/lean segmentation under lighting, Sensors 2026, PMC13306314 https://pmc.ncbi.nlm.nih.gov/articles/PMC13306314/ ; Intralox meat and poultry belting https://www.intralox.com/industries/food/meat-poultry ; vision-guided fillet reshaping, Vision Systems 2024 https://www.vision-systems.com/factory/robotics/article/55240964/vision-guided-robot-shapes-breaded-fish-into-uniform-shapes ; silverskin definition, Wikipedia citing McCracken 1999 https://en.wikipedia.org/wiki/Silver_skin ; wooden breast connective tissue shear, PMC10297311 https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10297311/ ; boneless poultry bone limit 9 CFR 381.117 https://www.law.cornell.edu/cfr/text/9/381.117 ; mechanically separated poultry 9 CFR 381.173 https://www.law.cornell.edu/cfr/text/9/381.173 ; FlexXray bone fragment detection https://flexxray.com/bone-and-organic-material-contamination-in-food-staging/ ; FSIS Danger Zone https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/food-safety-basics/danger-zone-40f-140f ; beef fabrication room design targets (trade reference) https://ingener.by/refrigeration-systems/food-processing-refrigeration/meat-processing/beef-processing/fabrication-rooms/ ; Sanitation SOP regulations 9 CFR 416.12-416.17 https://www.law.cornell.edu/cfr/text/9/416.12 ; sanitation shutdown durations, Provisioner https://www.provisioneronline.com/articles/103139-sanitation-in-meat-and-poultry-plants and Food Engineering https://www.foodengineeringmag.com/articles/7-steps-for-minimizing-downtime-during-cleaning-shutdowns
