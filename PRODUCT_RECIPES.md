# Product recipe definition

## Scope

The first cutter-loading cell supports three prepared, separated, boneless product recipes:

1. Beef center-cut tenderloin
2. Pork boneless loin
3. Chicken boneless skinless breast fillet

The robot does not perform primary butchery, deboning, trimming, or cutting. It picks one prepared product from a moving source conveyor, reorients it, and releases it into the stationary cutter-entry tray. The cutter owns product holding, scanning, blade operation, and portion cutting.

One recipe is active during a production run. A plant may change recipes between runs. The software catalog is extensible, but a new recipe is not physically qualified until its gripper, tray, payload, perception, and cutter constraints have been checked.

The machine-readable source is `configs/product_recipes.yaml`.

The integrated Isaac runner accepts a catalog recipe with `--recipe`. The safe launcher keeps results separate:

```powershell
.\run_recipe.ps1 -Recipe beef_center_cut_tenderloin -Solution a
.\run_recipe.ps1 -Recipe pork_boneless_loin -Solution a
.\run_recipe.ps1 -Recipe chicken_breast_fillet -Solution a
```

The current workpiece remains a rigid rectangular compliance proxy. Recipe selection changes its visible nominal dimensions, mass, color, USD metadata, PLC recipe ID, traces, and metrics. The named shape family is recorded, but tapered, curved, folding, and tissue deformation geometry is not yet physically modeled.

## Version 1 engineering envelopes

| Recipe | Mass | Length | Width | Height | Shape model | Handling compliance |
|---|---:|---:|---:|---:|---|---|
| Beef center-cut tenderloin | 1.0 to 3.0 kg | 280 to 600 mm | 70 to 150 mm | 50 to 100 mm | Tapered capsule | Medium |
| Pork boneless loin | 2.0 to 3.2 kg | 300 to 620 mm | 100 to 200 mm | 55 to 100 mm | Elongated rounded prism | Medium |
| Chicken breast fillet | 95 to 230 g | 140 to 210 mm | 90 to 180 mm | 20 to 45 mm | Asymmetric teardrop slab | High |

The beef and pork mass ranges follow published USDA product definitions and commercial portion-cutter examples. The chicken mass and dimension ranges are based on commercial-plant and broiler studies. Beef and pork length, width, and height are provisional equipment envelopes because standardized product dimensions were not found. They remain below the selected reference cutter limit of 650 by 250 by 100 mm.

Sources:

- [USDA beef institutional meat specifications](https://www.ams.usda.gov/sites/default/files/media/IMPS100SeriesDraft2020.pdf)
- [USDA pork institutional meat specifications](https://www.ams.usda.gov/sites/default/files/media/IMPS400SeriesDraft2020.pdf)
- [USDA chicken trade descriptions](https://www.ams.usda.gov/sites/default/files/media/Chicken_Trade_Descriptions.pdf)
- [Marel I-Cut 11 input examples and machine limits](https://marel.com/media/bpclpsv3/me21_br_271_i-cut11_en_lq.pdf)
- [Commercial chicken fillet weight study](https://www.sciencedirect.com/science/article/pii/S003257911940299X)
- [Commercial broiler fillet dimensions](https://pmc.ncbi.nlm.nih.gov/articles/PMC10031490/)

## Shape variation

The catalog separates overall dimensions from shape variation.

### Beef

- Elongated, approximately cylindrical muscle
- Diameter changes along its length
- Mild curvature is allowed
- Thick and narrow ends are distinguishable
- Exposed fat may shift the visible outline and grasp friction

### Pork

- Elongated rounded rectangular form
- More uniform cross-section than the selected beef profile
- Mild taper and curvature are allowed
- A trimmed fat cap may remain on one face

### Chicken

- Thin asymmetric slab
- Thick cranial end and tapered caudal end
- Large outline variation relative to mass
- May curl, sag, or fold during pickup
- Muscle-quality variation can change thickness and stiffness

Each simulated piece samples dimensions, taper, curvature, and asymmetry within its recipe. A real production run should use a narrower lot-specific distribution measured from the actual supplier and cut specification.

## Compliance model

Raw meat is nonlinear, viscoelastic, and anisotropic. Stiffness changes with fibre direction, strain, loading rate, temperature, age, moisture, and test method. Published values therefore cannot be treated as interchangeable material constants.

The catalog records two different quantities:

1. `effective_compression_modulus_kpa` is a literature-informed sensitivity envelope. It is not a calibrated constitutive model.
2. `compliance_index` is a dimensionless simulation control from zero to one. A higher number creates more centroid shift, sag, grasp uncertainty, and slip sensitivity in the current rigid-body proxy.

The first catalog uses:

| Recipe | Effective compression sensitivity range | Compliance index | Interpretation |
|---|---:|---:|---|
| Beef tenderloin | 15 to 310 kPa | 0.25 to 0.50 | Thick product with moderate whole-piece bending |
| Pork loin | 10 to 60 kPa | 0.30 to 0.55 | Moderate bending and surface deformation |
| Chicken breast | 40 to 185 kPa | 0.60 to 0.90 | Thin geometry produces high whole-piece bending and folding |

Uncooked steak has been measured at roughly 14.6 to 38.7 kPa over one low-strain compression region. A review reports a substantially higher beef tenderloin value under a different test method. Fresh chicken breast compression has produced about 48.6 kPa in one automation study, while directional tests demonstrate much higher stiffness along fibres than across them. Passive porcine muscle tests also demonstrate nonlinear, directional response.

Sources:

- [Uncooked beef compression measurements](https://www.frontiersin.org/journals/physics/articles/10.3389/fphy.2022.917842/full)
- [Review of instrumental meat texture measurements](https://pmc.ncbi.nlm.nih.gov/articles/PMC8787436/)
- [Raw chicken fillet compression model](https://www.sciencedirect.com/science/article/pii/S2772502226002209)
- [Chicken breast anisotropy measurements](https://link.springer.com/article/10.1007/s11340-026-01315-0)
- [Passive porcine muscle model](https://pmc.ncbi.nlm.nih.gov/articles/PMC10511390/)

The handling compliance class includes geometry. Chicken is classified as highly compliant because a thin slab bends much more readily than a thick loin, even when a local compression test reports a similar or higher modulus.

## Surface and grip assumptions

All three recipes are modeled as chilled and damp. The initial friction coefficient sweep is 0.20 to 0.50 with a nominal value of 0.35. This is an uncalibrated engineering range, not a published species property.

The following values are intentionally unresolved:

- Safe grip force
- Safe contact pressure
- Wet friction against the selected pad material
- Adhesion and release behavior
- Permanent indentation or tissue damage threshold
- Slip under acceleration
- Compliance after marination, freezing, thawing, or ageing

These require benchtop tests using the selected gripper pads and representative chilled products. Web research cannot establish them reliably.

## Required cutter-entry pose

The stationary tray defines a common `cut_target_frame`.

- Product long axis aligns with cutter X.
- Product is centered laterally in the tray.
- Beef enters thick end first.
- Pork enters square end first.
- Chicken enters thick cranial end first with the smooth side down.
- The robot releases only after the cutter reports ready and the tray is clear.

These orientations are provisional recipe choices. The selected cutter vendor and desired finished portion pattern must confirm them.

## Current Isaac gripper and tray implementation

The reference gripper has a fixed 175 mm open gap. Its controller selects a closing travel from the active recipe's nominal width and commands an 8 mm compliance deflection per pad. The USD compliance coefficient is 0.00016 m/N at a 50 N force setpoint. These values are integration assumptions only. They are not safe-force limits or tissue-damage measurements.

The robot releases the product into a stationary tray. The expected product speed at verification is zero. The PLC cutter feed speed describes the cutter's later internal feed motion after the tray handoff. It is not a required robot release speed.

All three initial nominal widths fit the reference opening. Range extremes, nonuniform cross-sections, wet-pad friction, and product damage still require physical testing.

## Extension process

A new product recipe must define:

1. Species and named cut
2. Process state, including bone, skin, temperature, and marination
3. Mass and three-dimensional geometry envelope
4. Shape family and expected variation
5. Compliance sensitivity and surface condition
6. Valid grasp regions and prohibited contact regions
7. Required tray orientation
8. Cutter compatibility and recipe identifier
9. Robot payload and gripper-opening compatibility
10. Evidence source and unresolved assumptions

Bone-in cuts, whole birds, frozen blocks, bellies, and loose piles are separate mechanical families. Adding a name to the software catalog does not make the current gripper or tray suitable for them.
