---
title: Depth-primary segmentation, belt plane to millimetre boundary
date: 2026-09-11
tags: [meat-cell, perception, depth, segmentation, plane-fitting, project]
status: draft
source: synthesis of primary literature, vendor datasheets, and this cell's geometry
---

# Depth-primary segmentation, belt plane to millimetre boundary

The decision this note serves: find the product in depth, not in colour. A slab stands 30 mm proud of a flat belt, and that is
geometry. Geometry does not care that the belt darkened over the shift, that the LED panel falls off in one corner, or that a
wet fat cap threw a specular highlight into the red channel. Colour then does one job, refining the boundary depth found, and
one check, confirming the thing depth found looks like meat.

Pose comes from the boundary, so the boundary is the deliverable and its unit is millimetres. Technique selection across the
full candidate space is settled in [perception technique selection](perception-technique-selection.md); this note assumes
depth-driven won and builds it. The pose estimator downstream is [perception ingestion](perception-ingestion.md).

The uncomfortable part is section 3. The design bets on depth being immune to appearance, and published evidence that depth
survives wet, specular, dark product does not exist. What does exist points the right way, and is thin.

## The geometry, as numbers

Derived from the four numbers the cell fixes: camera 570 mm above the product top surface, 0.58 mm per pixel there, product 180
x 90 x 30 mm, belt flat, 30 fps.

| Quantity | Value | From |
|---|---|---|
| Focal length | 983 px | `f = Z / s = 570 / 0.58` |
| Belt distance | 600 mm | 570 + 30 |
| Scale at the belt | 0.611 mm/px | `600 / 983` |
| Product footprint | 310 x 155 px, about 48 000 px | 180/0.58, 90/0.58 |
| Product perimeter | 931 px | 540 mm / 0.58 |
| Frame period | 33.3 ms | 30 fps |
| Depth step per disparity pixel | 5.88 mm | `Z^2 / (f B)`, f 1004.6, B 55 mm |
| Depth quantisation at 1/32 disparity | 0.18 mm | 5.88 / 32 |

That focal length is a fingerprint. Intel's D415 at 1280 x 720 has a 65 degree horizontal depth field of view, which by Intel's
own formula `f(px) = 0.5 x Xres / tan(HFOV/2)` is 1004.6 px, within 2 percent of the 983 px the cell's numbers imply. The cell
is specified around a D415-class camera at 1280 x 720, whose 450 mm minimum depth distance at that resolution leaves 120 mm of
margin ([D400 series datasheet, Tables 3-49 and 4-12](https://www.realsenseai.com/product-datasheets/)).

Two consequences set the whole design.

**A silhouette back-projected to the wrong plane is wrong by 9.5 mm.** A 180 mm slab subtends 310 px at 570 mm. Read that
contour against the belt plane at 600 mm and it measures `310 x 0.611 = 189.5 mm`. The error is 5.3 percent of every length,
systematic, and untouched by any amount of edge refinement. Only the height of each boundary point removes it, which is the
first hard argument for depth being primary rather than a sanity check.

**Off-axis slabs show their side walls.** A point `u` px off the principal point is seen at `tan(theta) = u / 983`. At the edge
of a 1280 px frame `u = 640` and `tan(theta) = 0.651`, so a 30 mm slab throws its base outline `30 x 0.651 = 19.5 mm` inboard of
its top outline. The visible envelope is the top face outboard and the base inboard, with up to 19 mm of exposed side wall
between. A contour drawn at "anything above the belt" is the base outline at image centre and a mixture out at the edges. Both
fixes are in the recipe: contour near the top surface, and project each contour point with its own measured height.

## 1. Fitting the belt plane properly

The model is `n . x + d = 0` with `|n| = 1`, three points is the minimal sample, and the residual is a signed point-to-plane
distance that doubles as the height map.

### The estimator family, and which parts earn their keep

RANSAC samples three points, counts inliers, keeps the best. Fischler and Bolles give the iteration count directly for the
three-point case as `k = log(1 - G) / log(1 - w^3)` ([CACM 1981, p. 390](https://doi.org/10.1145/358669.358692)), and Hartley
and Zisserman tabulate it: at `p = 0.99` and `s = 3`, an outlier fraction of 5 percent needs 3 samples, 20 percent needs 7, 30
percent needs 11, 50 percent needs 35 (*Multiple View Geometry*, 2nd ed., Table 4.3, p. 119). One slab on a belt puts us at the
left end of that table, so sampling is free.

The inlier count is not: at a 30 percent outlier fraction, 11 passes over 1280 x 720 is 10.1 million point-to-plane evaluations,
which will not fit in 33 ms alongside everything else. Subsample a few thousand points for the hypothesis loop and evaluate the
winner once over the full image.

Five names come up. Two earn a place here.

- **MSAC and MLESAC** replace the binary count with a clamped squared error and with a Gaussian-plus-uniform mixture likelihood
  ([Torr and Zisserman, CVIU 2000](https://doi.org/10.1006/cviu.1999.0832)). Their verdict on MSAC: it "yields a modest to hefty
  benefit ... with absolutely no additional computational burden. Once this is understood there is no reason to use RANSAC in
  preference to this method." Take it. MLESAC recovers the inlier fraction by EM, which the empty-belt calibration already gives
  us.
- **LO-RANSAC** optimises locally on each new best model ([Chum, Matas and Kittler, DAGM
  2003](https://cmp.felk.cvut.cz/~matas/papers/chum-dagm03.pdf)). In their experiment A, at a 61 percent inlier ratio, samples
  fell from 383 to 115 and efficiency reached 1.01 while wall time went *up*, 0.018 s to 0.019 s. At a high inlier ratio
  sampling was never the bottleneck, which is our regime.
- **PROSAC** samples in order of a quality prior ([Chum and Matas, CVPR
  2005](https://cmp.felk.cvut.cz/~matas/papers/chum-prosac-cvpr05.pdf)). In their 79 percent inlier case RANSAC finished in 15
  samples and PROSAC in 1. It needs an a priori per-point quality score, which a raw depth image does not have.
- **MAGSAC++** marginalises model quality over noise scale, and its score "does not require the inlier-outlier decision"
  ([Barath, Noskova, Ivashechkin and Matas, CVPR 2020](https://arxiv.org/abs/1912.05909)). It does **not** remove the threshold,
  it replaces it with `sigma_max`, "a user-defined maximum noise level", to which results are far less sensitive. The right tool
  when the sensor's noise is unknown. Ours is measurable.

### The threshold, from the sensor

A plane in 3D has codimension 1: only the perpendicular distance is measured, so `d^2 / sigma^2` is chi-squared with one degree
of freedom and the threshold is `t^2 = F^-1(alpha) sigma^2` (Hartley and Zisserman, eq. 4.17 and Table 4.2). That gives **1.96
sigma for 95 percent** and **2.58 sigma for 99 percent**. Torr and Zisserman set exactly `T = 1.96 sigma` "so that Gaussian
inliers are only incorrectly rejected five percent of the time". The habitual "2.5 or 3 sigma" is more conservative, 3 sigma
being alpha = 0.9973 on one degree of freedom.

`sigma` comes from a fitted sensor model, not a guess. The cleanest published instance: Holz and Behnke collected 100 range
images at each of 10 scenes, computed per-pixel mean and standard deviation, least-squares fit `sigma(d) = 0.00263 d^2 - 0.00518
d + 0.00752` for a Kinect, and used `2 sigma(d)` as the maximum allowed point-to-model deviation ([IAS-12, 2012, eq.
5](https://www.ais.uni-bonn.de/papers/IAS_2012_Holz.pdf)). Copy the procedure, not the coefficients. This cell also gets a
simplification for free: an overhead camera on a flat belt has the plane normal near the optical axis, so axial depth noise *is*
point-to-plane noise and the chi-squared argument is clean. Tilt the camera and you must project a mix of axial and lateral
noise onto the normal.

### Refit on the inliers, always

The winning model came from three points and carries the noise of three points. Refit by orthogonal distance regression. NIST's
reference implementation states the result exactly: the data centroid must lie on the least-squares plane, the normal solves
`(M^T M) a = lambda a`, and "the value of lambda is the objective function, hence the correct eigenvector for the least-squares
solution corresponds to the smallest eigenvalue"; they add that the eigenvectors are the singular vectors of `M`, so "we gain
numerical stability by applying the singular value decomposition (SVD) to M without ever computing M^T M" ([Shakarji, NIST J.
Res. 1998, section 2.1](https://nvlpubs.nist.gov/nistpubs/jres/103/6/j36sha.pdf)). Microseconds, and it cuts the normal's random
error by roughly the square root of the inlier count. Hartley and Zisserman then iterate the fit and the reclassification until
the inlier count converges (section 4.7.2).

### Inlier fraction is a health signal, not a confidence

Open3D stores `fitness = inliers / total` as the model score, feeds it back into the adaptive termination bound, logs it beside
the inlier RMSE, and breaks ties by RMSE
([PointCloudSegmentation.cpp](https://github.com/isl-org/Open3D/blob/main/cpp/open3d/geometry/PointCloudSegmentation.cpp)). Use
both numbers at runtime. Inlier fraction falls when product covers the belt (expected, and predictable from product area), when
water film kills returns, when someone knocked the camera, and when the belt is replaced. Area down with RMS flat means
occlusion; area down with RMS up means the plane model is wrong. One number cannot separate those, and I found no published
inlier floor for a conveyor, so ours comes from the empty-belt calibration.

### Faster paths for an organised cloud

A depth image is an organised point cloud, so planes can be grown by connectivity rather than sampled. Measured, per 640 x 480
frame:

| Method | Time | Hardware | Source |
|---|---|---|---|
| Sequential RANSAC | 127-607 ms | i7-8700 3.2 GHz | [Roychoudhury et al., ICRA 2021](https://www.hrl.uni-bonn.de/publications/roychoudhury21icra.pdf) |
| PCL connected components | 35-41 ms | i7-8700 3.2 GHz | same |
| Flood fill | 34-56 ms | i7-8700 3.2 GHz | same |
| PCL `OrganizedMultiPlaneSegmentation` | 33.5 +/- 3.1 ms per callback, 29.8 Hz | i7 2.6 GHz, normals and segmentation **in parallel** | [Trevor, Gedikli, Rusu and Christensen, SPME 2013](http://web.archive.org/web/20151220132644if_/http://www.cc.gatech.edu/~atrevor/resources/publications/spme_2013_segmentation.pdf) |
| PEAC agglomerative clustering | 27.3 +/- 6.9 ms, over 35 Hz; over 50 Hz without refinement | i7-2760QM 2.4 GHz, single thread | [Feng, Taguchi and Kamat, ICRA 2014](https://www.merl.com/publications/docs/TR2014-066.pdf) |
| CAPE grid of planar cells | about 3 ms, roughly 300 Hz | i5-5257U, single core | [Proenca and Gao, IROS 2018](https://arxiv.org/abs/1803.02380) |
| Polylidar3D plane extraction | 1.6-1.7 ms (11.4 ms whole pipeline) | Ryzen 3900X, D435i at 424 x 240 | [Castagno and Atkins, Sensors 2020](https://doi.org/10.3390/s20174819) |

Four things to take from that table.

Four things follow. Trevor et al. state that "normal estimation and plane segmentation were run in parallel, which is necessary
for real-time performance", so their serial cost is 48 to 55 ms, not 33. **PEAC degrades in exactly our geometry**: CAPE's
authors timed both on a synthetic noise-free wall and got "2.6 and 34 ms with a 20x20 patch and 5.8 and 300 ms with 10x10
patch", attributing PEAC's collapse to clustering that "gets slower when the camera faces closely one wall, which increases the
number of merging attempts". A camera 570 mm from one dominant flat surface is that case, so do not pick PEAC on its headline
number. **Accuracy is the catch for all of them**: PEAC reports plane normal deviation from ground truth of 1.7 +/- 0.1 degrees
on SegComp ABW and 2.4 +/- 1.2 degrees on PERCEPTRON, and across our 742 mm field 1.7 degrees is 22 mm of height error corner to
corner against a 30 mm product. **PCL's defaults are a trap**: `OrganizedMultiPlaneSegmentation` ships with a 3.0 degree angular
threshold, a 0.02 m distance threshold, 1000 minimum inliers and maximum curvature 0.001 ([PCL
API](https://pointclouds.org/documentation/classpcl_1_1_organized_multi_plane_segmentation.html)), and 20 mm is two thirds of
our product height. Out of the box, the slab joins the belt.

### What this cell should do

Split the two jobs. Calibrate the belt offline from several hundred empty frames and store a **per-pixel reference height
image**, not four plane coefficients. Per frame, run subsampled MSAC plus refit only to detect drift; if the normal or offset
leaves tolerance, alarm and stop, never quietly re-reference.

The reason for an image is measured. A D415 against a certified flat plane over 500 to 1500 mm showed systematic depth error of
mean 0.62 mm, standard deviation 4.57 mm, and a full range of 29.57 mm; a D455 ranged 34.24 mm, an L515 17.06 mm ([Servi et al.,
Sensors 2021, Table 8](https://doi.org/10.3390/s21227770)). A D415 at 1000 mm had a maximum deviation from the best-fit plane of
26.5 mm with a standard deviation of only 4.74 mm ([Carfagni et al., Sensors 2019](https://doi.org/10.3390/s19030489)). That bow
is sensor warp, not noise, and on a D415 it is the size of the whole product. A global plane plus a 15 mm threshold finds
product in empty corners. A per-pixel reference subtracts the bias at the pixel where it was measured.

## 2. Depth noise, and what it says about the two thresholds

Two thresholds matter: the plane inlier band and the height that means "product". Both come from the sensor's noise, and the
sensor's noise is smaller than its bias.

### The theoretical floor

Intel publishes the model and it is plain triangulation: `Depth RMS error (mm) = Distance(mm)^2 x Subpixel / (focal length(px) x
Baseline(mm))`, with `focal length(px) = 0.5 x Xres / tan(HFOV/2)`, and states that "for a well-textured target you can expect
to see Subpixel < 0.1 and even approaching 0.05", with over 0.2 px meaning the camera needs recalibration ([Intel, Tuning depth
cameras for best performance](https://dev.realsenseai.com/docs/tuning-depth-cameras-for-best-performance)). For a D415 at 1280 x
720 (f 1004.6 px, B 55 mm) at 570 mm that is **0.47 mm RMS** at Intel's own subpixel of 0.08. Quantisation at 1/32 disparity is
0.18 mm, so quantisation is not the limit.

The model has no reflectivity term: surface quality is absorbed entirely into `Subpixel`, and Intel's test target is "a flat
wall painted with a flat (or matte) white paint" (Intel, *Depth Testing Methodology*, which also defines RMS error as "an RMS
deviation of depth values from the best-fit plane to the data"). Section 3 is what happens when the target is meat. The
datasheet's contractual limit is a percentage, RMS error at or under 2 percent of range for a D415, which at 570 mm is 11.4 mm:
a factory acceptance floor 25 times the typical figure, useless as a design number.

### The measured reality near our standoff

| Measurement | Value | Conditions |
|---|---|---|
| D415 plane residual, 200 mm | mean 0.004 mm, sigma 0.345 mm, max 1.6 mm | plane certified flat to 50 um ([Carfagni 2019](https://doi.org/10.3390/s19030489)) |
| D415 plane residual, 1000 mm | mean 0.237 mm, sigma 4.74 mm, max 26.5 mm | same |
| D415 plane fit, 0.63 m | sigma 2.1 mm, 88.7 percent of points surviving | white wall, 640 x 480 ([Curto and Araujo 2022](https://doi.org/10.3390/s22197378)) |
| D415 sphere diameter, 150-450 mm | 2.1 mm average error | 25.4 mm sphere, matte white spray ([Servi 2021](https://doi.org/10.3390/s21227770)) |
| D415 object reconstruction, about 500 mm | mean 0.11 mm, sigma 0.90 mm, range 10.37 mm | matte-sprayed tangram ([Servi 2021](https://doi.org/10.3390/s21227770)) |
| D435 vs Kinect v2 below 1 m | D435 more precise, "results more scattered" | 20 x 20 px patch, 100 frames, plane fit ([Halmetschlager-Funek et al. 2019](https://doi.org/10.1109/MRA.2018.2852795)) |

Interpolating Carfagni between 200 mm and 1000 mm puts the plane residual sigma at 570 mm somewhere between 1.5 and 2.5 mm,
three to five times the 0.47 mm theoretical floor, on a white matte target. Design against the measured figure. The Kinect v1
literature says the same about model versus reality: `sigma_Z = (m / (f b)) Z^2 sigma_d'` with a calibrated `|m/(f b)| = 2.85e-5
/cm` and `sigma_d' = 0.5 px` predicts 0.46 mm at 570 mm, while the measured RANSAC plane residual at 0.5 m was "a few
millimeters" ([Khoshelham and Elberink, Sensors 2012, section 4.3](https://doi.org/10.3390/s120201437)).

### Range and incidence angle

Axial noise grows roughly quadratically with range and steeply once the surface tilts past about 45 degrees. The only fully open
closed-form model I could verify is for the Kinect v2:

```
sigma_z(z, theta) [mm] = 1.5 - 0.5 z + 0.3 z^2 + 0.1 z^1.5 theta^2 / (pi/2 - theta)^2
sigma_L = 1.6 mm  (edges without shadowing),  3.1 mm  (edges with shadowing)
z in metres, theta in radians, fitted over 0.7-3.1 m and 0-75 degrees
```

with the authors stating "sigma_z < 4 mm for angles 0 < theta < 45 degrees, but it increases quickly for angles theta > 45
degrees" ([Fankhauser et al., ICAR 2015](https://doi.org/10.1109/ICAR.2015.7251485)). The Kinect v1 model of [Nguyen, Izadi and
Lovell, 3DIMPVT 2012](https://doi.org/10.1109/3dimpvt.2012.84) has the same shape, quadratic in `z` plus a `theta^2 / (pi/2 -
theta)^2` hyperbolic term; that paper is paywalled and its coefficients are not reproduced here, but Fankhauser quotes its
operating points as 2.0 mm axial at (1.0 m, 45 degrees) and 12 mm at (2.8 m, 10 degrees), lateral 1.4 mm and 3.9 mm. **No
published incidence-angle noise model exists for any RealSense camera** (searched 2026-09-11). Intel does not publish one.

For an overhead camera on a flat belt `theta` is the field angle of each ray, so the corners of a 65 degree field sit near 32
degrees, where the angle term is still small. It grows where the product tilts, which is where the per-instance top-surface fit
is needed anyway.

### Two settings worth more than any filter

- **Set depth units to 100 um.** Intel recommends this below 2 m. At the default 1 mm, output quantisation is five times the
  sensor's own 0.18 mm disparity step and eats a real part of the noise budget.
- **Set the A-factor to 0.08.** Left at 0, depth linearity oscillates by about 0.5 percent of range on the High Density preset,
  roughly 2.9 mm at 570 mm, and about double that on High Accuracy. A systematic, range-dependent offset sitting directly on a
  30 mm measurement ([Intel, Subpixel Linearity Improvement for D400
  Series](https://dev.realsenseai.com/docs/white-paper-subpixel-linearity-improvement-for-intel-realsense-depth-cameras/)).

### What that sets

- **Plane inlier threshold.** `2.58 sigma` per pixel. At a measured sigma of 2 mm that is about 5 mm. A 1.5 mm band is not
  defensible; 5 to 8 mm is.
- **Height threshold.** 30 mm is roughly 15 sigma, a luxurious margin that should be spent rejecting false positives, not on
  sensitivity. At `5 sigma` the one-sided false-positive rate is about 3e-7 per pixel, a quarter of a pixel per frame, which a
  morphological opening erases.
- **Lateral noise owns the boundary.** Axial noise moves the surface up and down and the threshold absorbs it. Lateral noise
  moves the boundary sideways and nothing downstream absorbs it. A D435 measures 1 px of lateral noise below 0.7 m, which at our
  scale is 0.58 mm ([Halmetschlager-Funek et al., IEEE RAM 2019, Table 2](https://doi.org/10.1109/MRA.2018.2852795)). Erode the
  height mask by 2 to 3 px before using it for anything except the contour, and let the contour handle the edge explicitly.

## 3. The risk this design runs: wet, specular and dark

Evidence, not assertion, and where there is no evidence this says so.

### Intel's numbers do not describe our scene

Every Intel depth spec is measured on a matte white wall and the RMS model has no reflectivity term. Two further statements from
Intel's own documents bear on us. The D400 datasheet's variant comparison says specular reflections "may cause image saturation"
on a standard D400, and that saturation is "mitigated" on the narrow-band filtered D400f (rev 337029-017, Table 3-50). The
tuning document adds that "it is not uncommon to see a passive target or LED projector give >30% better depth than a laser-based
projector", because laser coherence generates speckle. A wet surface is an efficient speckle generator.

### Albedo, and a dark belt

Intel's own researchers published the only reflectivity law I could find: `r_expected ~ r_(rho=95%) x sqrt(cos theta_target x
alpha x cos^7 theta_FOV)`, with `alpha` the albedo, so range to a given fill rate scales as the square root of albedo
([Keselman, Woodfill, Grunnet-Jepsen and Bhowmik, CVPR Workshops 2017, section 4.2.8](https://arxiv.org/abs/1705.05548)). A
white target at 0.9 against black belting near 0.05 is roughly a four-fold range penalty. That paper characterises the R200, and
says so.

Measured at almost exactly our standoff: a coded structured-light SR305 returned **100.0000 percent invalid points on black
cardboard at 0.63 m**, including with nothing in the light path, while a D415 returned **0.0000 percent invalid on the same
cardboard** ([Curto and Araujo, Sensors 2022, Table 3](https://doi.org/10.3390/s22197378)). Active stereo falls back on passive
texture matching; coded structured light cannot. That single result decides the sensor class for a dark belt.

### Translucency, and the failure mode that should frighten us

Raw muscle at 850 nm, the band the projector works in, is a scattering medium: the pattern goes in, diffuses, comes back late.
The published measurements use proxies, and they are unambiguous. Diluted milk in a 79 mm cylinder at 1.2 m, 200 frames per
sample ([Sarbolandi, Lefloch and Kolb, CVIU 2015, section 4.6](https://arxiv.org/abs/1505.05459)):

- **Kinect v1, structured light.** Above 3.12 percent milk, "almost no invalid pixels and a signed error in the range of [1,
  1.5] mm". Below that, "the number of invalid pixels increases dramatically to above 90%".
- **Kinect v2, time of flight.** "A positive distance error between 12 and 378 mm, but does not mark any measurements as
  invalid, i.e. the number of invalid pixels is negligible."

A block of wax, a strong subsurface scatterer, under a Kinect One at 120 MHz at about 1 m: depth RMSE **42.5 mm**, and "the
measured depth of the wax candle is overestimated"; their correction brings it to 13.4 mm, and a plastic mannequin went 8.71 mm
to 5.35 mm ([Naik, Kadambi, Rhemann, Izadi, Raskar and Kang, CVPR 2015](https://arxiv.org/abs/1501.04878)).

The rule that follows: **structured light fails loudly, time of flight fails silently**, reporting confident depth tens of
millimetres too far, always in the same direction. A height-above-belt pipeline cannot detect a uniform positive bias on the
product; it just measures a thinner slab with an outward-shifted boundary. Active stereo gives holes, which are detectable and
which a validity mask carries downstream.

### Specular return at normal incidence

An overhead camera on a flat wet belt is the worst geometry for a mirror-like film: the specular lobe goes straight back into
the lens. Whiteboard on a turntable at 1.7 m, 0 to 90 degrees, 20 frames per step (Sarbolandi section 4.7):

- Kinect v1 structured light: below 10 degrees incidence "up to 100% of the pixels are marked invalid"; above 15 degrees, nearly
  none.
- Kinect v2 ToF: below 10 degrees, errors "up to 800 mm" not flagged invalid; between 10 and 30 degrees "up to 100% invalid
  pixel"; above 35 degrees, error below 50 mm.

Tilting the camera off vertical is a real mitigation, and it makes the parallax term above worse. That trade is an experiment,
not an argument.

### Flying pixels at the silhouette

A pixel straddling a depth step integrates light from both surfaces and the recovered phase or disparity lands between them
([Chugunov et al., Mask-ToF, CVPR 2021](https://arxiv.org/abs/2103.16693)). The honest bound: the error is capped by the step it
straddles and can take any value inside it, so at our 30 mm step an edge pixel can report any height in 30 mm. No published
distribution exists within that bound. A single "flying pixels are X mm off" figure is wrong in principle, because it is a
property of the scene, not of the sensor.

Measured edge behaviour, from a rotating 3D Siemens star against a wall at 1.8 m (Sarbolandi section 4.8): invalid pixels on the
edge arc were **7.0 percent for Kinect v1 and 10.9 percent for Kinect v2** in the static case. At 100 rpm, which sweeps 35 px
per 33 ms frame, the structured-light sensor degraded to 100 percent false foreground. A conveyor is motion, and this artefact
is what the boundary is made of.

One warning that changes how a fill rate should be read: "due to the sensors' internal post-processing pipeline, the flying
pixels are identified and removed from the depth map" ([Vasudevan et al., MMSP 2024](https://arxiv.org/abs/2410.08084)). A clean
fill rate can mean the vendor deleted the evidence.

### What has been measured on meat: nothing

A search result, not an assumption (OpenAlex, Crossref and Europe PMC, 2026-09-11). Three primary papers put RGB-D cameras over
wet meat and **none reports a single depth-quality statistic**: GTRI's poultry workbench with a RealSense over post-chill birds
([Ahlin, Animal Frontiers 2022](https://doi.org/10.1093/af/vfab079)), the RoBUTCHER pig carcass set with six D415s ([Data in
Brief 2022](https://doi.org/10.1016/j.dib.2022.107945)), and LaksData's salmon fillets at 0.7 m over a running plant conveyor
([Data in Brief 2026](https://doi.org/10.1016/j.dib.2026.112771)). One review offers only that "blood and other fluids in the
cutting environment introduces additional challenges for sensor-based recognition" ([Lyu et al., Frontiers in Robotics and AI
2025](https://doi.org/10.3389/frobt.2025.1578318)). The nearest quantitative work reports the end task: chicken carcasses on a
moving line under a Kinect v2 restricted to 0.2 to 0.6 m gave volume estimates at R^2 = 0.9988 and 2.125 percent average
relative error ([Poultry Science 2024](https://doi.org/10.1016/j.psj.2024.104232)). No published comparison of depth sensors on
wet organic material exists; the proxies are milk, water and wax.

### Where that leaves the design

The evidence supports the sensor class and does not yet support the accuracy claim. Active stereo, not time of flight and not
coded structured light, because of the dark belt and because of silent ToF bias on scattering material. Holes over confident
lies. The three numbers that would confirm or kill the design, the dropout rate on wet product, the silhouette bias on wet
product, and how both vary across the field, exist nowhere and have to be produced here.

## 4. What the portioning industry actually uses

Every fixed-weight portioner on the market builds its height map with a scanning laser line. Worth taking seriously before
committing to a snapshot design.

A laser projects a line, a camera views it obliquely, and the line's position on the sensor encodes height. One exposure gives
one profile; the belt supplies the second axis, so the map is stacked from profiles indexed by encoder ticks. The hardware shows
in the datasheet: SICK's Ranger3 parts list reads "CMOS sensor M30, scheimpflug adapter, replaceable, optical filter,
replaceable, C-mount lens", with "maximum 3D height resolution: 16 bits, 1/16 subpixel" ([SICK Ranger3, part
1091560](https://www.sick.com/media/pdf/7/47/947/dataSheet_V3DR3-60NE31111_1091560_en.pdf)). Three structural differences from a
snapshot camera follow.

- **Z and X resolution are decoupled and both depend on standoff.** LMI states Z resolution "is better closer to the sensor.
  This is reflected in the Gocator datasheets as the two numbers quoted for Z resolution", and X resolution is "based on the
  number of camera columns used to cover the field of view (FOV) at a particular measurement range" over a trapezoidal field
  ([LMI Gocator line profile sensors manual 6.0.21.13, pp. 60-63](https://www.lakewoodautomation.com/support/manuals/LMI/15159-6.0.21.13_MANUAL_User_Gocator_Line_Profile_Sensors_EN-US.pdf)).
- **Y resolution is belt speed over profile rate, and it is the worst axis.** Marel's I-Cut 11 runs a "laser vision system with
  200 Hz camera technology" at 10 to 340 mm/s ([I-Cut 11](https://jbtmarel.com/en/products/i-cut-11/)). At 340 mm/s that is a
  1.7 mm along-belt pitch, three times coarser than our 0.58 mm.
- **No encoder, no scale.** "Establishing the correct encoder resolution is required for correct scaling of the scan of the
  target object in the direction of travel", with a constant-speed fallback for lines without one. Every belt slip becomes a Y
  scale error, then a volume error, then a weight error.

| Sensor | Clearance | Range | FOV | Z repeatability | X resolution | Rate | Ingress |
|---|---|---|---|---|---|---|---|
| Gocator 2350 | 300 mm | 400 mm | 158-365 mm | 2 um | 0.150-0.300 mm | 0.17-5 kHz | IP67 |
| Gocator 2380 | 350 mm | 800 mm | 390-1260 mm | 12 um | 0.375-1.100 mm | 0.17-5 kHz | IP67 |
| SICK TriSpector1060 | 291-1091 mm working range | | 540 x 200 mm | 80-670 um resolution | 0.43 mm/px | 5 kHz | IP67 |
| Keyence LJ-X8400 | 380 mm | +/- 60 mm | 180-240 mm | 5 um | | 16 kHz | |

Sources: [Gocator 2300 datasheet](https://www.lakewoodautomation.com/support/manuals/LMI/DATASHEET_Gocator_2300_US_WEB.pdf),
[TriSpector1000 part 1060428](https://www.sick.com/media/pdf/5/45/145/dataSheet_V3T13S-MR62A8_1060428_en.pdf), [Keyence LJ-X8000
specifications](https://www.keyence.com/products/measure/laser-2d/lj-x8000/specs/). Read the conditions first. Keyence's
repeatability figures are "values measured by averaging 4096 times at the reference distance", a laboratory ceiling, and LMI
warns "Linearity Z, Resolution Z, and Repeatability Z may vary for other laser classes". The Gocator 2350, a 158 to 365 mm line
at 300 mm clearance, is the closest match to our geometry and beats our camera on both axes.

### What the machines do with it, and what they publish

Marel describes the chain in one sentence: "a laser highlights the surface of the raw material and the vision system scans its
contour. This calculates the volume, and by multiplying with the density, it provides a full view" ([I-Cut 610
announcement](https://jbtmarel.com/en/news/meet-the-new-i-cut-610-portioncutter/)). **JBT Marel publishes no giveaway percentage
and no portion weight standard deviation** on any I-Cut page (checked 2026-09-11). Accuracy numbers come from research instead.

- Laser profile to Delaunay volume to uniform density, on real product: mean absolute weight error **4.53 to 5.96 percent for
  chicken breast and 3.63 to 5.78 percent for fish fillet**, gage R&R total variation below 10 percent ([Thongprasith et al.,
  PeerJ Computer Science 2025](https://doi.org/10.7717/peerj-cs.3377)). Fish did better "due to flatter morphology and more
  complete point cloud acquisition", which is specular dropout in polite form.
- A built system: two Gocator 2150s top and bottom, 0.5 m/s belt, encoder-triggered, frozen hake. Portion weights over 150
  measurements per portion gave standard deviations of 0.38 to 1.80 g against a customer tolerance of plus or minus 10 g, with a
  systematic positive bias of 2 to 5 g attributed to saw kerf loss ([Gonzalez et al., ICPRAM
  2019](https://www.scitepress.org/Papers/2019/74824/74824.pdf)). Precision was never the problem. Bias was.
- The bar is a checkweigher: Baader's TrueGrader 1810 grades "up to 250 pieces per minute with an impressive accuracy of +/- 1
  gram per one deviation" ([Baader](https://www.baader.com/poultry/process/grading/truegrader-1810)).

Where geometry is not enough, the industry reaches for X-ray, not a better camera. SensorX "detects 99% of bone and other hard
contaminants as small as 2 mm" ([SensorX](https://jbtmarel.com/en/products/sensorx-x-ray-bone-inspection-system/)); FleXicut
locates pinbones "to an accuracy of 0.2mm" at up to 50 fillets per minute
([FleXicut](https://jbtmarel.com/en/products/flexicut/)); Marel's own engineers write that "the X-ray image data can also be
used to estimate density and thereby the thickness throughout the fillet" ([Einarsdottir, Gudmundsson and Omarsson, Animal
Frontiers 2022](https://doi.org/10.1093/af/vfac020)).

### The costs the brochures do not lead with

LMI's manual is unusually candid and all of it applies to us.

- **Ambient light and occlusion.** "The imager used in this product is highly sensitive to ambient light. Do not operate this
  device near windows or lighting fixtures that could influence measurement", and "sensors should not be installed near objects
  that might occlude a camera's view of the projected light". A narrowband filter buys SNR margin, not immunity, and the
  triangulation angle that gives Z resolution is the angle that casts a shadow off a 30 mm step. That is why Gonzalez et al.
  used two opposed sensors.
- **Specular dropout is named, and the fix is interpolation.** The Gap Filling filter "fills gaps where no data is detected,
  which can be due to the surface reflectivity, for example dark or specular surface areas". That is invented height flowing
  into the volume integral. LMI also documents deliberate "specular mounting", rotating the sensor about X for shiny targets,
  and the Gocator 2500 datasheet publishes separate diffuse and specular fields of view.
- **Speckle is the floor.** Coherent illumination on a rough surface sets a fundamental limit on triangulation precision through
  wavelength, observation aperture and speckle contrast ([Dorsch, Hausler and Herrmann, Applied Optics 33(7):1306,
  1994](https://doi.org/10.1364/AO.33.001306)). The formula is behind a paywall and is not reproduced here.
- **Laser class and wavelength.** Class 2 needs nothing; class 3B brings remote interlock, key control, beam attenuator,
  emission indicator, signage, a laser safety officer and eye protection, so reaching for a brighter laser to punch through a
  wet surface can drag the cell into that regime. The food-oriented TriSpector1000 is class 2 only, which is not an accident.
  Blue is the vendor answer for organic material: the Gocator 2500 series and the Keyence LJ-X8000 are 405 nm throughout, and
  Micro-Epsilon markets blue for "metals and organic materials". I found no peer-reviewed measurement of that penetration bias
  on meat (searched 2026-09-11), so treat it as practice, not result.
- **Washdown.** Every profiler I could verify is IP67: Gocator 2300, Gocator 2500, TriSpector1000; the Ranger3 is IP20 bare.
  IP69K, defined by ISO 20653, means surviving 80 degree C water at 80 to 100 bar from 10 to 15 cm. None carry it, so they go in
  a 316 stainless housing; APG's LL series is IP68 and NEMA 4X and its drawing is titled "Gocator 2350A" ([APG LL
  datasheet](https://apgvision.com/files/LL/ll-bv.pdf)). Our RGB-D camera has the same problem and needs the same box.

### The honest verdict

The industry is right, for its deliverable. A portioner's output is a weight, weight is volume, volume is a height integral, so
a sensor with 2 um Z repeatability and its own light source is the correct instrument. If our output were fixed-weight portions,
the snapshot design would be wrong and this note would be shorter.

Our output is a grasp pose and an alignment into a cutter, and three things break the comparison. **A profiler cannot
re-observe**: it builds one map as the product passes, after which the product has left the sensor, while our arm has to track a
moving piece and may have to look again after the gripper deformed it. **We need colour anyway**, for the refinement in section
5 and the confirmation check. **Our target is millimetres of boundary, not grams**, and the error budget is dominated by
parallax and edge bias rather than sampling pitch. So they are complements, and the likely end state is both: a line profiler
upstream if the cell ever needs a true volume, and the snapshot RGB-D at the pick zone for pose and tracking. The trigger to
revisit is in section 9.

## 5. Getting a boundary out of a height map

The pipeline now holds a height field `H(u, v)` in millimetres above the belt reference. A boundary is a level set of that
field, not a property of a binary mask, and treating it as the former is where the millimetres are won.

Marching squares walks the grid, finds which cell edges the level `h0` crosses, and places each crossing by linear interpolation
between corner values, the 2D case of marching cubes ([Lorensen and Cline, SIGGRAPH 1987](https://doi.org/10.1145/37401.37422)),
one `O(N)` pass. scikit-image's `measure.find_contours` implements it and states that "array values are linearly interpolated to
provide better precision for the output contours" ([scikit-image
API](https://scikit-image.org/docs/stable/api/skimage.measure.html)).

The error difference is arithmetic. A binary mask boundary is quantised to the grid at plus or minus half a pixel, 0.29 mm here.
An interpolated crossing is limited by `sigma_x = sigma_H / |dH/dx|`: a 30 mm step smeared over 5 px gives `|dH/dx| = 6 mm/px`,
and at `sigma_H = 2 mm` the crossing is located to 0.33 px, or 0.19 mm. That is precision, not accuracy: where the crossing
lands depends on `h0` and on the shape of the smearing, and the smearing comes from a block-matching window several pixels wide
that fattens the near surface. Repeatability is free; the systematic offset between iso-contour and true edge is not, and has to
be calibrated against a known object, stored as a signed millimetre offset, and applied.

### Snapping the contour to the colour edge

Colour is where the sharp edge lives, limited by lens MTF and pixel pitch rather than a correlation window. Sub-pixel edge
detectors reach position bias near zero with "standard deviation ... less than one tenth of a pixel" ([Devernay, INRIA RR-2724,
1995](https://inria.hal.science/inria-00073970)), 0.058 mm at our scale. Four ways to move the contour there, cheapest first.
**None needs training data.** They are deterministic optimisers over the image in front of them with parameters that have units,
which is why this pipeline can be commissioned on a customer's line in a day rather than after a labelling campaign.

1. **1D search along the contour normal.** Sample the colour image along the outward normal, convolve the profile with a
   derivative-of-Gaussian, take the sub-pixel extremum. The industrial caliper: HALCON's `measure_pos` averages grey values "in
   slices perpendicular to the major axis of the rectangle ... in order to obtain a one-dimensional edge profile", then computes
   sub-pixel locations "by convolving the profile with the derivatives of a Gaussian smoothing kernel" ([MVTec
   docs](https://www.mvtec.com/doc/halcon/2211/en/measure_pos.html)). For 931 contour points and a 21-sample window that is 20
   000 samples and 931 short convolutions, microseconds. It gives one answer per point plus a per-point confidence, so it can
   say "no edge here" instead of inventing one. MVTec publishes no single accuracy figure (checked 2026-09-11).
2. **Active contours.** Internal elasticity and bending terms plus an image force ([Kass, Witkin and Terzopoulos, IJCV
   1988](https://doi.org/10.1007/bf00133570)). The internal terms stop one bad gradient dragging the contour; they also shrink
   corners, and the capture range is short, which is why gradient vector flow exists ([Xu and Prince, IEEE TIP
   1998](https://doi.org/10.1109/83.661186)).
3. **Region-based level sets.** Chan-Vese minimises a piecewise-constant fit instead of following gradients, handling boundaries
   "not necessarily defined by gradient" ([Chan and Vese, IEEE TIP 2001](https://doi.org/10.1109/83.902291)). That matters where
   a wet edge has no gradient at all.
4. **Graph cuts.** Minimise a boundary-plus-region energy exactly by max-flow ([Boykov and Jolly, ICCV
   2001](https://doi.org/10.1109/iccv.2001.937505)), reported to run "in less than a second for most 2D images (up to 512 x
   512)" on a 333 MHz Pentium III. It needs seeds and the height map hands them over: above 25 mm is definite product, within 2
   mm of the reference is definite belt. Geometric seeds with a colour-driven cut is the cleanest expression of "depth finds it,
   colour refines it". GrabCut is the same machinery with iteratively re-estimated colour models ([Rother, Kolmogorov and Blake,
   SIGGRAPH 2004](https://doi.org/10.1145/1015706.1015720)).

## 6. Separating touching slabs by geometry

Two slabs arriving flush break a connected-components mask, and colour cannot help because both pieces are the same meat.

Flood the inverted height field from its minima and label the catchment basins ([Vincent and Soille, IEEE TPAMI
1991](https://doi.org/10.1109/34.87344)). The algorithm is linear in pixel count; their own numbers were about 2.5 s for 256 x
256 on a SUN SPARCstation 1, and 6.3 s on a 512 x 512 8-bit elevation model against 68 s for the sequential algorithm and 51 s
for arrowing. Only the linearity carries over from 1991, and the linearity is the point: this is not the expensive stage.

Unseeded it gives one region per local minimum, hundreds on a noisy height map. Marker-controlled watershed floods only from
chosen markers ([Meyer and Beucher, JVCIR 1990](https://doi.org/10.1016/1047-3203(90)90014-m)), and marker selection is the
whole design. Use two sources together: **h-maxima of the Euclidean distance transform** of the binary mask, where a 90 mm slab
peaks 45 mm (77.6 px) from its edges and two flush slabs give peaks 155 px apart with a saddle between, so markers at least 60
px apart with an h-parameter of at least 20 px yield exactly one marker per slab; and **maxima of the height map itself**,
flooding from the top surfaces downward, which catches pieces that overlap or leave a crease where the outline is not pinched at
all. **Concavity splitting** checks both: detect concave contour points, pair them across the neck, cut ([Kumar et al., Pattern
Recognition 2006](https://doi.org/10.1016/j.patcog.2005.11.014)). A legitimate split line ends on two concavities.

**No published split accuracy figure exists for touching soft meat slabs on a conveyor** (searched 2026-09-11; the measured
numbers in this literature are all for cell nuclei and grains, with different shape statistics). That number has to be produced,
not cited.

The two failure directions cost differently and that drives the tuning. Over-segmentation presents one slab as two, so the
cutter portions an object that does not exist, costing scrap or rework on one piece. Under-segmentation presents two slabs as
one: the gripper closes on a centroid between them, the pose is wrong by tens of millimetres, and the cutter sees a
double-thickness feed, a misfeed and possibly a stop. Under-segmentation stops the line, so tune the markers toward
over-segmentation and merge back with a shape prior. Anything failing the prior goes to a reject lane with the frame recorded. A
reject is cheap; a guess is not.

## 7. Filtering depth without eating the edge

Every filter that makes the height map look better moves the boundary. The question is by how much and whether you measured it.

- **Bilateral filter.** Weight neighbours by spatial distance and value difference ([Tomasi and Manduchi, ICCV
  1998](https://doi.org/10.1109/iccv.1998.710815)), naive cost `O(N r^2)`. On a 1600 x 1200 image at sigma_s 16 and sigma_r 0.1,
  direct computation "lasts about one hour whereas our approximation requires one second" on an Intel Xeon 2.8 GHz in C++
  ([Paris and Durand, ECCV 2006](https://doi.org/10.1007/11744023_44)). On a GPU the bilateral grid is "linear in the image
  size, ranging from 4.5 ms for 1 megapixel to 44.7 ms for 10 megapixels" on a GeForce 8800 GTX ([Chen, Paris and Durand,
  SIGGRAPH 2007](https://doi.org/10.1145/1276377.1276506)). It holds a step and rounds a corner, because the range weight cannot
  tell a corner from a ramp. A 7 px spatial sigma is 4 mm and will visibly change our slab corners.
- **Guided filter.** Output is a local linear transform of a guide image, `O(N)` and independent of kernel radius, with a
  subsampled variant at `O(N / s^2)` giving ">10x [speedup] when s = 4 ... with almost no visible degradation" ([He and Sun,
  arXiv:1505.00996](https://arxiv.org/abs/1505.00996); original [He, Sun and Tang, IEEE TPAMI
  2013](https://doi.org/10.1109/tpami.2012.213)). No gradient reversal, which the bilateral filter can show at strong edges.
- **Joint bilateral upsampling.** Filter low-resolution depth using full-resolution colour as the range guide ([Kopf, Cohen,
  Lischinski and Uyttendaele, SIGGRAPH 2007](https://doi.org/10.1145/1275808.1276497)). Its failure mode has a name and we will
  meet it: texture copying. Where colour has an edge with no depth edge, the filter carves one. On raw meat that means every
  fat-lean boundary, blood smear and belt print becomes a false height discontinuity. The prior "colour edges imply depth edges"
  is right at the silhouette and wrong everywhere inside it, so mask this filter to a band around the contour or leave it out.

librealsense ships four filters that touch depth values, plus a rotation filter, and two of the four are disqualified here
([librealsense post-processing
docs](https://github.com/IntelRealSense/librealsense/blob/master/doc/post-processing-filters.md)).

| Filter | What it does | Verdict |
|---|---|---|
| Decimation | 2x2 to 8x8, median for 2-3, mean for 4-8, rescales intrinsics | Throws away the resolution the boundary needs. No. |
| Spatial edge-preserving | 1D horizontal and vertical passes, high-order domain transform, linear time; magnitude 1-5, alpha 0.25-1, delta 1-50 | Yes, for normals and the plane fit. Measure its edge shift before contouring a filtered map. |
| Temporal | Exponential moving average over frames; the docs warn it "may introduce visible blurring/smearing artifacts, and therefore is best-suited for static scenes" | No. The belt moves. |
| Hole filling | Copies a neighbour: `fill_from_left`, `farest_from_around` (default), `nearest_from_around` | No, not near the contour. |

The spatial filter's edge-preserving term is the domain transform of [Gastal and Oliveira, SIGGRAPH
2011](https://doi.org/10.1145/1964921.1964964), a good choice: linear time, cost independent of kernel size.

The hole-filling row deserves its own sentence. A hole beside the product edge is information: the sensor failed there.
`farest_from_around` fills it with belt depth and shrinks the product; `nearest_from_around` fills it with product depth and
grows it. Either way the boundary moves by the width of the hole and nothing downstream can tell. Keep holes as holes, carry a
validity mask, and let the contour logic decide. **The rule:** filter the copy of the height map used for normals, curvature and
the plane fit; contour the unfiltered map, or measure the edge shift the filter introduces on a calibration target and subtract
it. Never both silently.

## 8. The recipe

`sigma` below means the per-pixel depth noise measured in step 0, never a datasheet number.

**Step 0, offline calibration.** Set depth units to 100 um and the A-factor to 0.08 first (section 2), because both change what
the calibration measures. Then produce four artefacts, stored and versioned.

1. Intrinsics, and depth-to-colour extrinsics good to better than 0.3 px, which is 0.17 mm at the product plane. Worse than that
   and step 9 moves the contour in the wrong direction.
2. A per-pixel belt reference height image `R(u, v)` from at least 300 empty-belt frames: per-pixel median, plus `sigma(u, v) =
   1.4826 x MAD`. This absorbs the sensor warp that section 1 measured at up to 29.57 mm of range.
3. A contour bias: scan a machined block of known 30 mm height and known outline, run the per-frame chain on it, and store the
   signed millimetre offset between the recovered contour and truth as a function of radial image position.
4. The colour channel with the best meat-against-belt contrast on the customer's actual belt. Measure it; do not assume a
   channel.

**Per frame.**

1. Acquire, timestamp at exposure midpoint. **Temporal filter off** (the belt moves), **hole filling off** (it moves the
   boundary silently).
2. `H = R - Z`, with a validity mask from the sensor's invalid pixels plus `|H| < 200 mm`. Carry the mask everywhere. A hole
   never becomes a number.
3. Drift check, not re-referencing. Subsample 4000 valid pixels with `H < 3 sigma`, run 15 MSAC iterations at `2.58 sigma`,
   refit by SVD on the centred inliers. If the normal moved more than 0.05 degrees (0.65 mm across the 742 mm field) or the
   offset more than 1 mm, alarm and stop.
4. Candidate mask `H > max(8 mm, 5 sigma)`. Open with a 5 px disc to kill isolated noise, close with a 9 px disc to bridge
   specular holes up to 5 mm across. Record the area the closing added; more than a few percent means the surface is failing,
   and step 10 should say so.
5. Split touching pieces. Markers from h-maxima of the Euclidean distance transform (h at least 20 px, minimum separation 60 px,
   against the 77.6 px half-width of one slab) unioned with maxima of `H`. Marker-controlled watershed, then merge back anything
   failing the shape prior: area 48 000 px within 30 percent, extent 310 x 155 px within 15 percent.
6. Per instance, fit the top surface by MSAC plus SVD refit on points above half the instance's 95th-percentile height. This
   gives the tilt the grasp needs and the mean top height `t`.
7. Contour by marching squares at `h0 = 0.7 t`, on a copy of `H` smoothed by a guided filter of radius 4 px. Contour high, not
   at half height: a low contour traces the base outline for off-axis pieces.
8. Project each contour point with its own measured height, `X_i = (u_i - cx) Z_i / f`, with `Z_i` read from the height map at
   that point. Then apply the step 0 contour bias.
9. Colour refinement. For each of the roughly 931 contour points, search the chosen channel along the outward normal over plus
   or minus 12 px (7 mm), convolving a derivative-of-Gaussian at sigma 1.5 px, and take the sub-pixel extremum. Accept a
   displacement only if the gradient magnitude clears threshold and the displacement is under 6 px. Median-filter accepted
   displacements over 15 points of arc length before applying, so one spurious edge cannot dent the outline.
10. Emit four confidence numbers and gate on all four: belt inlier fraction, fraction of contour points with an accepted colour
    edge, instance area against the prior, and top-surface residual RMS.
11. Pose from the refined contour, per [perception ingestion](perception-ingestion.md).

**Budget.** Every stage is `O(N)` or better except the per-instance work: subsampled MSAC is microseconds, the guided filter is
linear and radius independent, distance transform and watershed are linear, marching squares is one pass, and the colour search
is 931 short convolutions. 33 ms should be comfortable on a CPU, which is an argument, not a measurement. If the plane fit
becomes the bottleneck, section 1's table says an image-space method beats sequential RANSAC by 10 to 100 times at VGA, and CAPE
is the one to try first.

### Measured, not assumed

| Must be measured on the real cell | May be taken from theory |
|---|---|
| `sigma(u, v)` at the belt and on wet product | Iteration count from `w`, `s`, `p` |
| The reference image `R`, re-taken after any belt change | The chi-squared threshold multiplier |
| The contour bias, per radial position | Marching squares interpolation |
| Depth-to-colour extrinsics, and their drift over a shift | Watershed and distance transform behaviour |
| Best colour channel for meat against this belt | Guided filter complexity |
| Dropout rate on wet product, and where it falls | |
| Encoder scale and belt speed | |
| Rolling shutter readout time (the D415 is rolling shutter) | |

## 9. Open questions, and the experiment that closes each

1. **What is the silhouette bias of the depth edge on wet meat at 570 mm?** The number the whole design rests on, and nobody has
   published it. Machined step block first for instrument bias, then real slabs against a backlit 2D silhouette as ground truth,
   200 frames each, bias and standard deviation reported against radial position.
2. **What is the dropout rate on wet product versus blotted, on the customer's belt?** 30 slabs, 100 frames each, both
   conditions. Count invalid pixels inside the product and, separately, within 10 px of the boundary, because a hole at the
   boundary costs far more than a hole in the middle.
3. **What is the split failure rate on touching slabs?** 200 staged pairs at gaps of 0, 2, 5 and 10 mm, over- and
   under-segmentation reported separately per gap, since their costs differ.
4. **Does colour refinement help or hurt on a wet dark belt?** Step 9 on and off against the same ground truth. A specular sheen
   at the product edge could make colour worse than depth there.
5. **Is a rolling shutter admissible?** The D415, which the close-range characterisations favour, is rolling shutter; the D455
   is global shutter but its 520 mm minimum depth distance at 1280 x 720 leaves only 50 mm of margin. Measure the readout time
   and the skew at the target belt speed before choosing.
6. **Does a line profiler close enough of the gap to earn cell space?** Rule from section 4: if measured boundary accuracy on
   wet product misses target by more than a factor of two, it stops being optional.

Questions 1, 2 and 4 can start before hardware arrives, on two public datasets that are both wet meat under RealSense cameras.

- **Pig carcasses, six D415s**, raw bags with depth and intrinsics, from RoBUTCHER ([Data in Brief
  2022](https://doi.org/10.1016/j.dib.2022.107945); data at [dataverse.no
  doi:10.18710/GDGHZR](https://dataverse.no/dataset.xhtml?persistentId=doi:10.18710/GDGHZR)).
- **Salmon fillets on a running plant conveyor**, cameras 0.7 m above the belt, two D415 and one D435 ([LaksData, Data in Brief
  2026](https://doi.org/10.1016/j.dib.2026.112771)). 0.7 m over a wet conveyor is within 25 percent of our standoff.

## Related entries

- [Perception ingestion](perception-ingestion.md)
- [3D sensing and geometric perception](perception-3d-sensing.md)
- [Meat cell architecture](meat-cell-architecture.md)
- [Computer vision fundamentals](computer-vision-fundamentals.md)
- [Perception technique selection](perception-technique-selection.md)

## Sources

Every claim above links its primary source inline. The load-bearing ones, grouped:

- **Estimation:** [Fischler and Bolles 1981](https://doi.org/10.1145/358669.358692), [Torr and Zisserman
  2000](https://doi.org/10.1006/cviu.1999.0832), [Barath et al. 2020](https://arxiv.org/abs/1912.05909), [Shakarji, NIST
  1998](https://nvlpubs.nist.gov/nistpubs/jres/103/6/j36sha.pdf), Hartley and Zisserman, *Multiple View Geometry*, 2nd ed.,
  section 4.7.
- **Organised-cloud plane segmentation:** [Trevor et al. 2013](http://web.archive.org/web/20151220132644if_/http://www.cc.gatech.edu/~atrevor/resources/publications/spme_2013_segmentation.pdf),
  [Feng, Taguchi and Kamat 2014](https://www.merl.com/publications/docs/TR2014-066.pdf), [Proenca and Gao
  2018](https://arxiv.org/abs/1803.02380), [Castagno and Atkins 2020](https://doi.org/10.3390/s20174819), [Roychoudhury et al.
  2021](https://www.hrl.uni-bonn.de/publications/roychoudhury21icra.pdf), [Holz and Behnke
  2012](https://www.ais.uni-bonn.de/papers/IAS_2012_Holz.pdf).
- **Sensor noise:** [Intel D400 datasheets](https://www.realsenseai.com/product-datasheets/), [Intel tuning
  whitepaper](https://dev.realsenseai.com/docs/tuning-depth-cameras-for-best-performance), [Khoshelham and Elberink
  2012](https://doi.org/10.3390/s120201437), [Fankhauser et al. 2015](https://doi.org/10.1109/ICAR.2015.7251485), [Carfagni et
  al. 2019](https://doi.org/10.3390/s19030489), [Servi et al. 2021](https://doi.org/10.3390/s21227770), [Halmetschlager-Funek et
  al. 2019](https://doi.org/10.1109/MRA.2018.2852795).
- **Failure on hard surfaces:** [Keselman et al. 2017](https://arxiv.org/abs/1705.05548), [Sarbolandi, Lefloch and Kolb
  2015](https://arxiv.org/abs/1505.05459), [Curto and Araujo 2022](https://doi.org/10.3390/s22197378), [Naik et al.
  2015](https://arxiv.org/abs/1501.04878), [Chugunov et al. 2021](https://arxiv.org/abs/2103.16693).
- **Meat and profiling:** [SICK Ranger3](https://www.sick.com/media/pdf/7/47/947/dataSheet_V3DR3-60NE31111_1091560_en.pdf), [LMI
  Gocator manual](https://www.lakewoodautomation.com/support/manuals/LMI/15159-6.0.21.13_MANUAL_User_Gocator_Line_Profile_Sensors_EN-US.pdf),
  [Dorsch, Hausler and Herrmann 1994](https://doi.org/10.1364/AO.33.001306), [Thongprasith et al.
  2025](https://doi.org/10.7717/peerj-cs.3377), [Gonzalez et al. 2019](https://www.scitepress.org/Papers/2019/74824/74824.pdf),
  [Einarsdottir et al. 2022](https://doi.org/10.1093/af/vfac020), [RoBUTCHER pig
  dataset](https://doi.org/10.1016/j.dib.2022.107945), [LaksData](https://doi.org/10.1016/j.dib.2026.112771).
- **Contours, splitting, filtering:** [Lorensen and Cline 1987](https://doi.org/10.1145/37401.37422), [Devernay
  1995](https://inria.hal.science/inria-00073970), [Boykov and Jolly 2001](https://doi.org/10.1109/iccv.2001.937505), [Vincent
  and Soille 1991](https://doi.org/10.1109/34.87344), [He, Sun and Tang 2013](https://doi.org/10.1109/tpami.2012.213),
  [librealsense post-processing](https://github.com/IntelRealSense/librealsense/blob/master/doc/post-processing-filters.md).

Absent or unverified, flagged so nobody fills them in later: no published incidence-angle noise model for any RealSense camera;
no published dropout, fill-rate or bias measurement for any depth camera on wet meat; no published split-failure rate for
touching meat slabs; no published giveaway percentage from any portioner vendor; no peer-reviewed measurement of blue-laser
penetration bias on meat; no published timing benchmark for Open3D's `segment_plane`. The Dorsch speckle formula and the Nguyen
coefficients are behind paywalls and are not reproduced here.
