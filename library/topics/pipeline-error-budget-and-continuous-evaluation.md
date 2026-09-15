---
title: "Pipeline error budget and continuous evaluation for the pork-leg alignment cell"
date: 2026-09-15
tags: [topic, error-budget, evaluation, regression-testing, conveyor-tracking, intercept, data-flywheel, meat-cell, assignment]
status: draft
source:
  - https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf
  - https://www.bipm.org/documents/20126/2071204/JCGM_101_2008_E.pdf
  - https://faculty.washington.edu/fscholz/DATAFILES498B2008/TOLSTACK.pdf
  - https://search.abb.com/library/Download.aspx?DocumentID=3HAC050991-001&LanguageCode=en&DocumentPartId=&Action=Launch
  - https://arxiv.org/abs/2105.04830
  - https://ar5iv.labs.arxiv.org/html/1709.06283
  - https://arxiv.org/html/2406.11793
  - https://research.google.com/pubs/archive/46555.pdf
  - https://www.itl.nist.gov/div898/handbook/
  - https://arxiv.org/abs/2305.03270
  - https://arxiv.org/abs/2410.21845
  - https://arxiv.org/html/2305.10272
  - experiments/2026-09-08-perception-ingestion.md
  - computed 2026-09-15 (numpy 2.4.6, scipy 1.17.1, rll env)
---

# Pipeline error budget and continuous evaluation for the pork-leg alignment cell

## What this answers

The team lead wants to run each stage of the leg cell on its own, see that stage's errors, and
end up with a cell that is repeatable and gets better every week. That needs four things written
down: how the stage errors add up at the trotter saw, what the intercept planner has to model
about a belt that ramps and stops, how each stage is scored and regression-tested, and how field
failures turn into the next week's fix. The last section is the recipe for this cell.

This note does not repeat the belt frame, the Kalman tracker and vendor feature table
([conveyor-tracking-and-visual-servoing](conveyor-tracking-and-visual-servoing.md)), the
architecture candidates and their budget
([control-architecture-selection](control-architecture-selection.md)), the subsystem contracts
([meat-cell-architecture](meat-cell-architecture.md)), or binomial intervals and A/B tests
([policy-evaluation](policy-evaluation.md)). It uses all four.

## The chain and what the saw scores

| # | Stage | Output | Error it contributes to the saw | Arch. note subsystem |
|---|---|---|---|---|
| 1 | Perception | hock and trotter keypoints, leg yaw, in base frame, stamped at exposure | keypoint position (mm), yaw (deg) | S2 to S4 |
| 2 | Grasp point selection | grasp pose on the leg | indirect: sets the in-hand shift and whether the grasp holds | S6 |
| 3 | Belt tracking and intercept | meet time, meet pose, velocity-matched trajectory | TCP minus predicted grasp point at contact (mm) | S5, S7 |
| 4 | Grasp execution | leg held, vacuum or jaw state verified | in-hand shift and rotation at closure | S8, S9 |
| 5 | Lift-and-place, or orient-on-belt | leg at the saw-edge pose | arm path error, push residual | S10 |
| 6 | Release | leg free on the belt | shift on opening, settle | S10 |
| 7 | Verification | measured cut offset and angle before the saw start request | estimator error of the scorer itself | S12 |

The saw scores two numbers per leg: **cut offset** (mm, position of the cut relative to the hock
landmark) and **cut angle** (deg). The customer's tolerance on either is unknown. This note uses
the pre-registered deformable bound from the architecture note, 5 mm and 5 deg at the 95th
percentile, as a placeholder.

## 1. How errors compose along the chain

### The rules

**Propagation.** For an output y = f(x_1 ... x_N), the combined standard uncertainty is
u_c²(y) = Σ c_i² u²(x_i), with c_i = ∂f/∂x_i the sensitivity coefficient; this form is "valid only
if the input quantities X_i are independent or uncorrelated"
([JCGM 100:2008](https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf), §5.1.2 eq. 10,
§5.1.3, §5.2.1). With correlation r_ij the cross terms 2 ΣΣ c_i c_j u(x_i) u(x_j) r_ij are added
(eq. 16), and when every r = +1 the result is the linear sum Σ c_i u(x_i) (§5.2.2, note 1).
Root-sum-square is therefore the independent limit and linear addition the fully correlated limit
of the same formula.

**Sensitivity coefficients are geometry.** Yaw from two keypoints a baseline B apart, each with
position sigma σ_k perpendicular to the leg axis, is σ_yaw = √2 σ_k / B radians. A yaw error δθ
acting over a lever L moves a point by L sin δθ, 1.75 mm per degree at 100 mm (computed).

**Worst case versus RSS.** Worst case "assumes all the component dimensions occur at their worst
limit simultaneously", and as the number of parts grows "the component tolerances must be greatly
reduced"; RSS commonly treats a tolerance as ±3σ
([Chase and Parkinson 1991, via ADCATS archive](http://web.archive.org/web/2015/http://adcats.et.byu.edu/Publication/91-1/DesRes_w_figs.html), §2).
With n equal contributions T_RSS = T√n against T_worst = T n
([Scholz 1995, Boeing](https://faculty.washington.edu/fscholz/DATAFILES498B2008/TOLSTACK.pdf), §4.1).
Practitioners inflate RSS to cover non-ideal inputs: correction factors of 1.4 to 1.8 (Chase and
Parkinson, eq. 3) and Bender's 1.5, "based mainly on the fact that production operators will
usually give you 2/3 of the true spread" (Scholz, §4.2; Bender's original not fetched, and the two
reviews disagree on its year).

**Bias is not variance.** GUM assumes "the result of a measurement has been corrected for all
recognized significant systematic effects" (§3.2.4), and says enlarging the uncertainty instead of
applying a known correction "should be avoided" (§6.3.1, note). For a cell this means a measured
bias is a bug ticket with a size, not a term to hide inside a sigma. Uncorrected, it adds
linearly and shifts the whole distribution: with σ = 2.04 mm, the p95 of |e| is 4.00 mm with no
bias, 4.36 mm with 0.90 mm and 4.76 mm with 1.38 mm (computed). Mean shifts sit between the two
limits: Chase and Parkinson's mean-shift model gives worst case when every shift factor is 1 and
RSS when every one is 0 (§2.1).

**Non-Gaussian and dominant terms.** JCGM 101 lists when Monte Carlo propagation is needed: when
contributions are "not of approximately the same magnitude", when the output PDF is not Gaussian,
and when input PDFs "are asymmetric"; the linear framework "may not validly be applicable when
there is an X_i whose assigned distribution is non-Gaussian and the corresponding contribution to
u(y) is dominant"; 10⁶ trials usually give a 95 percent interval correct to one or two
significant digits
([JCGM 101:2008](https://www.bipm.org/documents/20126/2071204/JCGM_101_2008_E.pdf), scope,
§5.7.2 note 4, §7.2.1). In-hand shift on a wet leg is exactly that term: one-sided, heavy-tailed
and the largest.

**Coverage factor.** k = 2 gives about 95 percent for an approximately normal output (JCGM 100,
§6.3.3). A cut offset is scored as a magnitude, so its p95 is 1.96σ, not the one-sided 1.645σ the
architecture note used; that note's p95 figures are about 16 percent optimistic on the Gaussian
part (1.645/1.96 = 0.84, computed).

### A measured correlated pair: the phantom slip

The ingestion experiment already contains the case RSS gets wrong
([2026-09-08-perception-ingestion](../../experiments/2026-09-08-perception-ingestion.md)).
Perception carried a position bias that ramped across the field of view; the tracker, fitting
the product's motion, turned that spatial ramp into an apparent slip of -1.16 mm/s at 0.50 m/s,
and extrapolated it. The perception error and the tracking error had the same cause and the same
sign, so r = +1. Taking the worst signed bias (0.62 mm) and the slip over the 0.5 s horizon
(0.58 mm), RSS gives 0.85 mm and linear addition 1.20 mm (computed). Before the fix the tracking
gate failed at 2.03 mm mean against 2 mm while perception passed its own gate at 0.65 mm worst.
Two stages that pass alone and fail together is what correlated error looks like in a log.

### Reading the measured numbers correctly

From `experiments/data/2026-09-08-ingestion.json` (MuJoCo 3.12.0, rigid 180 x 90 x 30 mm box,
exact mask, 15 products per speed, 2026-09-08), computed on 2026-09-15:

- **Perception centroid** p95/mean is 2.41, 2.42 and 2.40 at 0.15, 0.30 and 0.50 m/s. A 2D
  Gaussian radial error would give 1.95 and a 1D half-normal 2.46, so the error behaves like a
  one-axis Gaussian; σ ≈ p95 / 1.96 = 0.124 mm at 0.30 m/s.
- **Tracking prediction** mean/max is 0.93, 0.94 and 0.96 across 15 products. The spread is tiny
  and the mean is not zero: this term is a bias, about 0.90 mm at 0.30 m/s, with a spread of
  roughly 0.03 mm. A linear fit of the mean over speed gives 0.19 mm + 2.38 mm per m/s, a
  2.4 ms timing-equivalent term over a 0.5 s horizon. It is speed-proportional, so per the
  experiment's own reasoning it is a timing or velocity error, not noise, and it should be found
  and corrected rather than budgeted (unattributed as of this note).
- Stamp skew (0.000 ms) and the frame round trip (under 0.001 mm) are exact by construction in
  simulation and contribute nothing here; on hardware both become calibrated quantities.

### Worked budget for the leg cell at 300 mm/s (computed)

Offset at the saw, one axis, millimetres. "Measured" means the ingestion experiment above. Every
"assumed" value is unverified until the bench measures it; most are taken unchanged from the
architecture note so the two budgets can be compared.

| Term | Stage | Kind | Value | Basis |
|---|---|---|---|---|
| Perception geometry | 1 | σ | 0.124 | measured, rigid box, exact mask |
| Keypoint localisation on a real leg (segmentation, wet surface, depth noise) | 1 | σ | 3.0 | assumed; same as `e_pose` M in the architecture note |
| Hand-eye and belt-frame calibration | 1, 3 | σ | 1.0 | assumed; see the calibration caveat below |
| Tracking prediction | 3 | bias | 0.904 | measured |
| Tracking prediction spread | 3 | σ | 0.030 | measured, (max - mean)/2 over 15 products |
| Arm tracking lag at 300 mm/s | 3 | σ | 2.0 | ABB's ±2 mm at 150 mm/s read as 95 percent, extrapolated linearly (the architecture note's reading) |
| In-hand shift at closure | 4 | p95, one-sided | 6.0 | assumed; no published source |
| Arm local accuracy on the place path | 5 | σ | 0.5 | assumed |
| Release shift | 6 | σ | 1.5 | assumed |
| Settle after release | 6 | p95, one-sided | 1.0 | assumed |
| Verification estimator (only when it corrects) | 7 | σ | 2.0 | assumed |

Four ways to add the open chain (no correction from verification, the leg is released where the
pick model says it is). Monte Carlo draws each Gaussian term from its σ, each one-sided term from
an exponential with the stated p95, adds the bias, and reports the p95 of |e| over 10⁶ samples,
seed 20260915.

| Composition | Open chain p95 | Verification corrects the place (σ_v 2.0) | Same, σ_v 1.0 |
|---|---|---|---|
| Worst case (every term at its 95 percent bound, summed) | 23.88 mm | 8.84 mm | 6.88 mm |
| RSS of 95 percent bounds (all independent, bias included in quadrature) | 10.06 mm | 5.10 mm | 3.80 mm |
| Bias linear + 1.96 x RSS(σ) + one-sided p95s linear (the architecture note's shape, with 1.96) | 15.87 mm | 6.00 mm | 4.67 mm |
| Monte Carlo (JCGM 101 style) | **10.88 mm** | **5.09 mm** | **3.78 mm** |

What the table says:

1. **The open chain cannot meet 5 mm under any composition rule.** The in-hand shift alone is
   6 mm p95. Setting it to zero still leaves 8.4 mm by Monte Carlo (computed).
2. **Where the variance is.** Of the open chain's Gaussian variance, the real-leg keypoint term is
   54.5 percent, arm tracking lag 24.2, release 13.6, calibration 6.1, arm accuracy 1.5, and the
   two measured simulator terms together 0.1 percent (computed). Everything measured so far is
   noise in the budget. The next measurements must be keypoints on real legs and in-hand shift.
3. **Sensitivity.** Calibration at 3.0 mm instead of 1.0 raises the open chain to 12.2 mm; halving
   keypoint error to 1.5 mm lowers it to 9.6 mm; correcting the tracking bias saves 0.8 mm
   (10.9 to 10.1). All computed by Monte Carlo.
4. **Composition rule choice moves the answer by a factor of 2.2** on the same inputs (10.9 by
   Monte Carlo against 23.9 worst case). The linear-p95 rule is 46 percent conservative against
   Monte Carlo on the open chain and 18 percent with verification. Use Monte Carlo for sign-off
   and keep the rule and the distributions in the record.
5. **With verification correcting the place, the chain sits at 5.1 mm**, right on the bound, and
   is set by the verification estimator, the release and the settle.

Calibration caveat. On an eye-in-hand RealSense D415i with an arm rated ±0.03 mm repeatability,
end-to-end localisation after hand-eye calibration converged to about 4.4 mm (Tsai), 4.0 mm
(Horaud), 3.4 mm (Daniilidis) and 2.9 mm with the authors' method, from 12 retained poses
([Hua et al. 2024, Sensors](https://pmc.ncbi.nlm.nih.gov/articles/PMC11207387/)). The 1.0 mm
assumption needs a structured-light camera, a larger pose spread and a check against a measured
reference. Enebuse et al. list what improves it: more robot motions, larger angular spread,
shorter camera-to-target distance, smaller motion between poses
([IEEE Access 2021](https://wrap.warwick.ac.uk/id/eprint/156836/7/WRAP-comparative-review-hand-eye-calibration-techniques-vision-guided-robots-2021.pdf)).

Arm accuracy caveat. ISO 9283 pose repeatability RP is the mean distance from the barycentre plus
three standard deviations ([Barnfather et al., quoting ISO 9283](https://d-nb.info/1107765382/34),
eqs. 2 to 5; ISO text not fetched). ABB's IRB 1300 datasheet gives RP 0.02 to 0.05 mm but path
accuracy AT 0.98 to 1.52 mm at 1.6 m/s on the ISO plane, averaged over "a small number of robots"
([3HAC070393-001 rev. M, distributor mirror](https://cdn.pennair.com/media/2023/11/3HAC070393-PS-IRB-1300-en.pdf), §1.8.3).
A tracked or lift-and-place motion pays path accuracy, not repeatability; UR publishes only
±0.03 mm repeatability for the UR5e, with no test conditions
([UR data sheet, Jan 2023](https://www.universal-robots.com/media/1826690/01_2023_collective_data_sheet-1.pdf)).

Depth caveat. Keypoint σ on a leg is bounded below by the sensor. Zivid 2+ M60: point precision
80 µm (1σ, consecutive measurements at the 600 mm focus distance, Lambertian target, 0 lux)
([datasheet v1.2](https://www.zivid.com/hubfs/User%20guides%20and%20datasheets/Zivid%202+%20M60%20Datasheet.pdf)).
Photoneo MotionCam-3D M in dynamic mode: accuracy 0.50 mm, temporal noise 0.10 mm, statistic not
stated ([datasheet 11/2020](https://photoneo.com/wp-content/uploads/datasheets/MotionCam-3D%20M%20-%20Datasheet%2011_2020.pdf)).
RealSense D415: depth RMS error ≤ 2 percent to 2 m
([D400 datasheet rev 016](https://www.realsenseai.com/wp-content/uploads/2023/07/Intel-RealSense-D400-Series-Datasheet-July-2023.pdf), table 4-14);
the formula RMS = z² x subpixel / (f x baseline) with f ≈ 1005 px, baseline 55 mm and subpixel
0.08 gives 1.4 mm at 1 m
([Intel tuning BKM](https://www.realsenseai.com/wp-content/uploads/2019/11/BKMs_Tuning_RealSense_D4xx_Cam.pdf); arithmetic computed).
The 3.0 mm keypoint assumption is dominated by where a hock "is" on wet tissue, not by the sensor.

### Allocating a tolerance to stages

Three allocation rules, each computed for the 5 mm p95 offset bound on the corrected chain
(verification, arm accuracy, release, with 1.0 mm of one-sided settle taken off the top):

- **Equal share in quadrature.** σ available = (5.0 - 1.0)/1.96 = 2.04 mm; three equal terms get
  1.18 mm each.
- **Fix what cannot move, give the rest to what can.** With arm accuracy 0.5 and release 1.5 held,
  the verification estimator may have σ ≤ 1.29 mm.
- **Cost-weighted.** If making stage i better costs c_i / σ_i, minimising Σ c_i / σ_i subject to
  Σ σ_i² = S gives σ_i ∝ c_i^(1/3) (Lagrange condition, derived here). If verification is eight
  times as costly to improve as the other two, it gets σ 1.67 mm and the others 0.83 mm each.

Then verify by Monte Carlo, because the rule of thumb and the answer differ once a one-sided term
is present. Yaw, same method: keypoint σ 3 mm over an assumed 200 mm hock-to-trotter baseline
(no measured leg dimension in this library; unverified) gives 1.22 deg; with an assumed 2 deg
in-hand rotation and 1 deg release rotation the open chain is 4.99 deg p95, and 2.52 deg with
verification correcting the place using 2 mm keypoints (computed). Angle is on the bound too.

## 2. Intercept planning on a belt that ramps and stops

### Belt models

Position along the belt s(t), speed v(t), measured by the encoder count.

- **Constant velocity (CV).** s(t) = s_0 + v t. The vendor default; ABB filters encoder speed with
  a second-order IIR at 10 Hz and recommends 10 to 15 Hz for stop-and-go conveyors
  ([ABB 3HAC050991-001](https://search.abb.com/library/Download.aspx?DocumentID=3HAC050991-001&LanguageCode=en&DocumentPartId=&Action=Launch),
  sections 3.6, 7.2).
- **Constant acceleration (CA).** s(t) = s_0 + v t + a t²/2, valid only until v reaches the set
  speed or zero, so it is always piecewise in practice.
- **Piecewise by mode.** Run, ramp down, stopped, ramp up. The mode is known to the line PLC
  before the encoder sees it. ABB's OmniCore manual makes this explicit: "The prediction is based
  on constant acceleration", armed by a start or stop signal "set a predefined time before the
  speed change"; with `UseAccProfile` the signal "must be set at least 150 ms before the conveyor
  is starting to accelerate or decelerate", one profile for start and one for stop, and "the
  larger the difference is between these two times the poorer accuracy will be achieved". The
  acceleration-dependent filter defaults to 1 m/s² and should equal the conveyor's maximum
  acceleration, a "trade off between noise reduction and accuracy during acceleration"
  ([ABB 3HAC066561-001 rev. Q](https://library.e.abb.com/public/547ef8c3fb6b477aa0fc12ae92e31cb4/3HAC066561%20AM%20Conveyor%20tracking%20OmniCore-en.pdf),
  sections 11.2 to 11.4). Without the PLC signal, the estimator has to infer the mode: Singer's
  model treats a manoeuvre as random acceleration with a time constant, and the interacting
  multiple model filter runs one Kalman filter per mode with mixed initial conditions at close to
  single-model cost ([Pulford survey, arXiv 1503.07828](https://arxiv.org/pdf/1503.07828), sections
  2.1 and 4; [Blom and Bar-Shalom 1988](https://doi.org/10.1109/9.1299)). For a belt with three
  known modes, the PLC signal is cheaper and exact; the IMM is the fallback when the line gives
  no signal.

What the model choice is worth, computed for a belt that stops from 300 mm/s over 0.2 s
(1.5 m/s², an assumed ramp): a CV prediction over a 0.5 s intercept horizon puts the leg at
150 mm, the belt actually moves 30 mm, a 120 mm error. Even correct CA without the stop clamp
predicts a negative position after 0.2 s. The planner must re-plan every control cycle from the
live count and clamp prediction at v = 0.

### Estimating speed from the encoder

Position comes from the count directly and needs no model; speed is the estimated quantity. A
fixed-window count difference at 10,000 counts per metre resolves 10 mm/s in a 10 ms window and
1 mm/s in 100 ms (computed). That is the fixed-time method's trade: its absolute error is set by
the window and is "independent on speed value", while the fixed-position (period) method is more
accurate at low speed and has no sample at all each cycle when the belt is nearly stopped; low-pass
filtering helps "but the additional lag time introduced by the filter degrade the performance"
([Petrella et al. 2007](https://kth.diva-portal.org/smash/get/diva2:1248310/FULLTEXT01.pdf),
sections II and III). Time-stamping each encoder edge with a fast clock and fitting a polynomial
through the last events avoids both; on a 100-slit encoder at a 1 ms loop, skipping 3 events in the
fit improved velocity by 54 percent and acceleration by 92 percent
([Merry et al. 2010, Mechatronics 20](https://techunited.nl/media/files/velocity_and_acceleration_estimation_for_optical_incremental_encoders.pdf)).
A belt stop is the low-speed case, so the stop is where a fixed-window estimator is weakest.
Vendors expose the same trade as an averaging length: FANUC's "Average (updates)", typically 10;
KUKA's `FILTER_LENGTH`, where "the robot responds more slowly to changes in the velocity";
Yaskawa's averaged travel time of 0 to 3,000 ms, about 200 ms when motion is not smooth, at the
cost that "synchronization responsiveness is lowered" (sources in the table below). The filter's delay converts into position error only over the time it
is extrapolated: a second-order Butterworth low-pass has a DC group delay of √2 / (2π f_c),
22.5 ms at 10 Hz and 15.0 ms at 15 Hz; ABB does not say its IIR is Butterworth, so treat this as
the order of magnitude. During the 1.5 m/s² ramp that lag is a speed error of 34 mm/s at 10 Hz,
worth 0.51 mm over a 12 ms command lag but 17 mm if extrapolated over the 0.5 s plan horizon
(computed). Hence: short extrapolations from the live count are cheap, long ones from a filtered
speed are not.

### Latency compensation

Two different latencies, handled differently (conveyor note, sensing chain):

- **Before the pose exists** (exposure, processing): compensated exactly by stamping the pose in
  the belt frame with the count latched at the shutter. Cost is v x stamp error; 0 ms in the sim
  and under 0.1 ms with a hardware sync input.
- **After** (command lag τ_c, servo lag): predicted. The error is δv τ_c + ½ δa τ_c², where δv and
  δa are the estimation errors. At 300 mm/s and constant speed only δv matters; during a ramp the
  unmodelled acceleration term dominates as τ_c grows.

### Velocity-matched arm motion

Plan along the belt axis in the belt frame, where the leg is stationary and the arm starts with
velocity -v_b; add v_b back at the joint level (conveyor note). Along that axis the minimum-time
problem is to reach the leg's position with the belt's velocity.

Trapezoid, rest to rest over distance D with limits v_max and a_max: T = D/v_max + v_max/a_max when
v_max²/a_max ≤ D, otherwise the profile is a triangle with T = 2√(D/a_max) (rescaled from
[Lynch and Park, Modern Robotics](http://hades.mech.northwestern.edu/images/7/7f/MR.pdf), §9.2.2.2).

Intercept with a triangular profile (derived here, checked by integration). Arm at rest, leg a
distance d_0 ahead and moving at v_b, acceleration limit a: accelerate to v_p, decelerate to v_b,
meet at t. Matching distance and final velocity gives a² t² - 2 a v_b t - (4 a d_0 + v_b²) = 0, so
t = (v_b + √(2 v_b² + 4 a d_0)) / a and v_p = (a t + v_b)/2, valid while v_p ≤ v_max. For
d_0 = 100 mm, v_b = 0.3 m/s, a = 5 m/s²: t = 0.355 s, v_p = 1.04 m/s, meet 207 mm from the arm's
start. A forward-Euler integration at 10 µs reproduces t and the meet point to 0.1 mm. When the
leg is behind the arm or v_p exceeds v_max there is no closed form worth keeping; the snippet's
fixed-point `plan_intercept` covers it.

Jerk-limited. Seven constant-jerk segments (Lynch and Park, §9.2.2.3). Rest-to-rest times computed
here from the double-S closed forms attributed to Biagiotti and Melchiorri 2008 (book not
fetched, unverified) and checked by integrating the jerk profile (D = 0.4 m, j = 50 m/s³ ends at
0.4000 m, v = 0):

| Distance | Trapezoid (v 1.5 m/s, a 5 m/s²) | Double-S, j 50 m/s³ | Double-S, j 20 m/s³ |
|---|---|---|---|
| 0.1 m | 0.283 s | 0.400 s | 0.543 s |
| 0.4 m | 0.566 s | 0.674 s | 0.862 s |
| 1.0 m | 0.967 s | 1.067 s | 1.217 s |

At 300 mm/s the extra 0.11 s of the j = 50 profile over 0.4 m is 33 mm of belt travel, taken from
the window. Ruckig computes "a time-optimal trajectory to an arbitrary target state defined by its
position, velocity, and acceleration limited by velocity, acceleration, and jerk constraints", and
is the first such online algorithm to include non-zero target acceleration. It was tested on over
10⁹ random trajectories, at 19.8 µs mean and 123 µs worst for 7 DoF on an i7-8700K
([Berscheid and Kröger, RSS 2021](https://arxiv.org/abs/2105.04830), abstract, §V.A, table III).
Non-zero target acceleration is what makes a ramping belt tractable: re-target every cycle to
(s_leg, v_belt, a_belt).

### What published conveyor tracking achieves

| Vendor, document | Stated accuracy | Belt speed and conditions | Speed changes | Source |
|---|---|---|---|---|
| ABB Conveyor Tracking, IRC5 RobotWare 6 manual | ±2 mm of the path | 150 mm/s, automatic mode; degrades above 500 mm/s | 10 Hz IIR speed filter, 10 to 15 Hz for stop-and-go | [3HAC050991-001](https://search.abb.com/library/Download.aspx?DocumentID=3HAC050991-001&LanguageCode=en&DocumentPartId=&Action=Launch), §1.2 |
| ABB Conveyor Tracking data sheet, S4Cplus | TCP within ±2 mm; coordinated finepoint ±0.7 mm | up to 350 mm/s, constant speed | not stated | [data sheet](https://library.e.abb.com/public/51c0fc4c87a036f6c1257b1300579b96/Data%20sheet%20Conveyor_tracking.pdf) |
| ABB PickMaster 1.0 product spec, IRB 340 on S4C | ±0.5 mm at 150 mm/s, ±1.1 mm at 350 mm/s; ±2 mm with the robot at full speed and two belts at 150 mm/s | constant speed; recommended maximum 150 mm/s, not above 350 mm/s; encoder sampled every 20 ms | "additional deviation of +/-0.1 mm" per change in speed of 15 "mm2/s" (unit as printed) | [3HAC 5842-1](https://library.e.abb.com/public/36a9e50804973b42c125766d003e8625/PPAspec.pdf), p. 8 and table 1 |
| ABB PickMaster 3.0, IRB 340 | repeatability 1.0 mm at 150, 2.0 at 250 to 500, 5.0 at 500 to 800, 15.0 at 800 to 1,400 mm/s | maximum 1,400 mm/s without camera, 600 mm/s with camera | not stated | [PR10041EN_R7, 2005](https://library.e.abb.com/public/77b700acf06bad86c1257b1300574dcf/PickMast3.0HR.pdf) |
| ABB PickMaster, IRB 340 on IRC5 | repeatability 1.0 mm at 200, 1.5 at 350 to 750, 3.0 to 5.0 at 800 to 1,400 mm/s | brochure figures | "repeatability 3.5mm at 500mm/s and 0.2s start/stop time" | [PR10342EN_R2, 2007](https://library.e.abb.com/public/bfe0a7a82909aa5ac1257b1300579abe/pickmaster_brochure.pdf), footnote 1 |
| ABB Conveyor Tracking, OmniCore | no mm figure | encoder 40 to 20,000 counts/s | constant-acceleration prediction from a signal at least 150 ms ahead of the ramp | [3HAC066561-001](https://library.e.abb.com/public/547ef8c3fb6b477aa0fc12ae92e31cb4/3HAC066561%20AM%20Conveyor%20tracking%20OmniCore-en.pdf), ch. 11 |
| FANUC Line Tracking, R-30iB, B-83474EN/03 | trigger error = belt speed x 2 x ITP time: 3.2 mm at 200 mm/s with 8 ms ITP; 0.8 mm with ACCUTRIG's 2 ms tick | trigger timing only, not total tracking error | encoder averaging, typical 10 updates; tracking filter length is "the time robot has to catch up" | [manual, Jun 2022](https://robochallenge.pl/wp-content/uploads/2023/09/Line-Tracking-Operator-Manual.pdf), appendix A, §3.3.3 |
| KUKA.ConveyorTech 5.0, KSS 8.2 | no mm figure; aim for about 0.03 mm per increment, avoid above 0.1 mm | none stated | `FILTER_LENGTH` averaging; `DELAY_TIME` default 24 ms, "Tests show that the optimal value is 24 ms" | [KST ConveyorTech 5.0](http://supportwop.com/IntegrationRobot/content/5-Applicatifs_metiers_KST/ConveyorTech/KST_ConveyorTech_50_en.pdf), p. 18 |
| Yaskawa DX100 Conveyor Synchronized Function, HW0485517 | deviation "about ten times the difference from repetitive positioning for still-object" | none stated | averaged travel time 0 to 3,000 ms; causes listed include "follow-up delay for the conveyor speed fluctuation" | [manual](https://icdn.tradew.com/file/201606/1569362/pdf/7052388.pdf), §6.2 |
| Mitsubishi CR800 Tracking, BFP-A3520-B | "Approximately ±1 mm" at the handling position | about 300 mm/s; up to 500 mm/s with wide workpiece spacing | older CRn-500 manual exposes a lag correction and a speed-trend extrapolation Vc + k(Vc - Vp) | [CR800 manual](https://eu-assets.contentstack.com/v3/assets/blt5412ff9af9aef77f/bltd4e63e1a1679c64f/61726c56ca617d08ba764819/9a9dd449-a575-11ea-bd9a-b8ca3a62a094_CR800_Controller_-_Tracking_function_Instruction_Manual_bfp-a3520b.pdf), table 3-1 |
| Omron TM Conveyor Tracking, I853-E-03 | "average precision ±1 mm", "only serves as reference" | under 300 mm/s, workpiece angle within ±15 deg | not stated | [manual](https://files.omron.eu/downloads/latest/manual/en/i853_tm_conveyor_tracking_users_manual_en.pdf?v=2) |
| Epson RC+ 7.0 | no mm figure; accuracy-priority mode only at 350 mm/s or less, above that "tracking delay" may occur | 350 mm/s | `Cnv_Accel` up to 5,000 mm/s², default 2,000 | [RC+ 7.0 guide ch. 16](https://files.support.epson.com/far/docs/epson_rc_pl_70_conveyor_tracking_(fromrc_pl_70_manual)_(r4).pdf), §16.19 to 16.20 |

Reading it for the leg cell. Published mm figures cluster at ±0.5 to ±2 mm at 150 to 350 mm/s on
constant-speed belts with light parts. The one number with a ramp, ABB's 3.5 mm at 500 mm/s with a
0.2 s start and stop, is 2.3x the same brochure's 1.5 mm for 350 to 750 mm/s, which is the size of
penalty to expect on a stop-and-go line (unverified for a 9 to 13 kg leg on a six-axis arm). The
FANUC trigger formula, belt speed x 2 x the controller tick, is 4.8 mm at 300 mm/s with an 8 ms
tick; a latched hardware trigger is worth more than any filter tuning. The vendor figures are
statements, not test reports: none gives trial counts. Stäubli, Kawasaki, Denso and newer KUKA,
FANUC iRVision and Yaskawa YRC1000 manuals were not fetchable on 2026-09-15. The one peer-reviewed
moving-conveyor grasp study found reports success, not millimetres: 71.7 percent over 120
attempts at 0 to 220 mm/s with a multi-fingered hand, 90 percent at the slowest step and 50
percent at 220 mm/s, one attempt per object per 20 mm/s step
([Burkhardt et al.](https://arxiv.org/pdf/2310.17923)).

## 3. Per-stage evaluation and regression testing

### Why the stage view is necessary and not sufficient

Sculley et al. name the problem: "Machine learning systems mix signals together, entangling them
and making isolation of improvements impossible ... Changing Anything Changes Everything", and
improving one component "may actually make the system accuracy worse if the remaining errors are
more strongly correlated with the other components"
([NeurIPS 2015](https://papers.nips.cc/paper_files/paper/2015/file/86df7dcfd896fcaf2674f757a2463eba-Paper.pdf)).
The ML Test Score adds the pipeline rule: "each stage can introduce errors that may affect
subsequent stages, possibly even several stages away", so there must be "a fully automated test
that runs regularly and exercises the entire pipeline", and in a survey of 36 Google teams this
integration test had "much lower adoption than most"
([Breck et al. 2017](https://research.google.com/pubs/archive/46555.pdf), Infra 3). The phantom
slip is that sentence in the leg cell: both stages passed their gates. Score each stage, and also
score the seam and the end.

The Amazon Picking Challenge is the cautionary record: "Half of the teams did not score any points
despite having developed impressive sub-systems", with causes including "last minute software
changes, or failures to model the lip of the shelf"
([Correll et al., 26 teams, 31 survey responses](https://ar5iv.labs.arxiv.org/html/1601.05484), §VI).

### Attribution by oracle substitution

Replace one stage's output with ground truth, re-run the rest, and the change in the end metric is
that stage's share. In simulation it is free; on the real cell it needs a measured reference.

- MIT-Princeton's APC pose pipeline passed 49.8 percent on rotation and 66.1 percent on
  translation (15 deg, 5 cm thresholds) over 7,713 images; with ground-truth segmentation, 63.4
  and 88.1 percent, the authors' "performance upper bound" of the fitting stage
  ([Zeng et al. 2017](https://ar5iv.labs.arxiv.org/html/1609.09475), table II).
- FetchBench, 6,000 tasks: ground-truth grasps and mesh reach 67.1 percent with cuRobo; predicted
  grasps with the same mesh 33.6 percent; ground-truth grasps from a point cloud 19.0 percent. Even
  with both oracles, "motion planning fails in 14% of cases reaching the pre-grasp pose and 9%
  reaching the end-state. In another 10% of cases, the object slips"
  ([FetchBench](https://arxiv.org/html/2406.11793), §6.2, table 3).

For this cell the substitution ladder in simulation is: true keypoints, then true grasp point,
then true leg pose at the meet instant, then perfect grasp (no in-hand shift), then perfect release.
Each rung's placement p95 minus the next is that stage's measured contribution, including its
correlation with the stages after it, which a per-stage metric alone misses.

### Failure taxonomy with counts

Cartman (ACRV, Amazon Robotics Challenge 2017): 863 grasp attempts in 7.2 hours, 622 successful
(72 percent); of 168 categorised failures, perception 27.6 percent, physical occlusion 10.3,
unreachable pose 7.5, and grasp failure on a correctly identified, reachable pose 54.6. Forty
percent of all failed grasps were on one item, the scissors
([Morrison et al.](https://ar5iv.labs.arxiv.org/html/1709.06283), §VI, table I). The paper does not
explain why 168 were categorised when 241 attempts failed; a taxonomy that loses 30 percent of
failures is a logging defect. Two taxonomies worth borrowing from: AHA's seven manipulation
failure modes (no grasp, slip, translation offset, incorrect rotation, no rotation, wrong action,
wrong object) ([Duan et al. 2024](https://arxiv.org/html/2410.00371), §3.1), and Honig and
Oron-Gilad's attributes on every failure: functional severity (non-critical, recoverable,
terminal), frequency, condition, symptoms
([Frontiers 2018](https://www.frontiersin.org/articles/10.3389/fpsyg.2018.00861/full)).
REFLECT localised the failing step correctly 93.8 percent of the time on 30 real execution
failures, but explained them correctly 68.8 percent
([Liu et al. 2023](https://ar5iv.labs.arxiv.org/html/2306.15724), table 2): an LLM summariser
over logs is a triage aid, not the attribution.

### Fixed initial-condition suites

Waymo's scenarios "are either harvested from public road driving logs, obtained from closed course
driving logs, or created from scratch in simulation-only workspaces", and re-simulating a software
version against historical logs "gives the ability for individual developers to execute the
evaluation themselves"; Waymo also says neither simulation nor driving alone is sufficient
([Waymo 2020](https://arxiv.org/pdf/2011.00054)). In a 12-practitioner robotics study, one team
runs "an automated system that runs the tests nightly ... used as regression testing" and most
knew simulation's value but few used it
([Afzal et al., ICST 2020](https://clairelegoues.com/assets/papers/AfzalQualitative20.pdf)).
The three suite sources map to this cell as: designed ICs from a seed, ICs harvested from logged
real cycles (the leg's measured keypoints, belt speed profile and timing replayed in sim), and
real canary runs.

### How many trials detect a regression

All computed 2026-09-15 with scipy 1.17.1.

| Question | Test | Trials |
|---|---|---|
| Stage failure rate rose from 2 to 4 percent, known baseline | one-sided binomial, α 0.05, power 0.8, normal approximation ([NIST 7.2.4.2](https://www.itl.nist.gov/div898/handbook/prc/section2/prc242.htm)) | 391 |
| Same, exact binomial | reject at ≥ 16 failures in 500 (α 0.047, power 0.85); ≥ 21 in 700 (α 0.046, power 0.93) | 500 to 700 |
| Same, baseline also estimated | two-sample, pooled | 899 per arm |
| 5 to 10 percent; 10 to 20 percent | one-sided, known baseline | 149; 69 |
| Mean stage error shifted 0.5 mm, σ of the difference 1 mm | paired t, two-sided α 0.05, power 0.8 | 32 pairs (63 per arm unpaired) |
| p95 of placement error, distribution-free 95 percent interval | order statistics X(183) to X(196) of 200 | 200 |
| Sample maximum as a 95 percent upper bound on p95 | 1 - 0.95^n ≥ 0.95 | 59 |
| Zero failures, upper bound on the rate | rule of three, ≈ 3/n ([Hanley and Lippman-Hand 1983](https://jhanley.biostat.mcgill.ca/c607/ch08/zero_numerator.pdf)) | 1,000 clean for 0.3 percent |

Sequential. Wald's SPRT for 2 against 4 percent with α 0.05 and β 0.2 uses thresholds ln 16 = 2.77
and ln 0.21 = -1.56; each failure adds 0.693 and each success -0.0206, so 76 straight successes
accept "no regression" and 4 straight failures reject; the expected run length is 211 trials if
nothing changed and 240 if it did (computed). The thresholds (1-β)/α and β/(1-α) are Wald's
approximations and do not guarantee the error rates when overshoot is ignored
([arXiv 2410.16076, §1](https://arxiv.org/html/2410.16076v3); Wald 1945 not fetched). For
policy-versus-policy comparisons use the near-optimal stopping test already in
[policy-evaluation](policy-evaluation.md).

Continuous monitoring. On a production shift, a p-chart on the per-shift failure fraction uses
UCL = p + 3√(p(1-p)/n) ([NIST 6.3.3.2](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc332.htm));
CUSUM on per-leg cut offset with k half the shift to detect and h around 4 or 5
([NIST 6.3.2.3](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm)); EWMA with λ
0.2 to 0.3, which reacts to "a small or gradual drift" that a Shewhart chart misses
([NIST 6.3.2.4](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm)). For
distribution shift in placement error, the Kolmogorov-Smirnov test is "more sensitive near the
center of the distribution than at the tails"
([NIST 1.3.5.16](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35g.htm)), the wrong
emphasis for a p95 spec; compare p95 with the order-statistic interval above instead.

End-to-end is a product. Six stages at 99, 98, 97, 98, 99 and 99.5 percent give 90.9 percent
(computed, independent stages assumed), so a 1-point regression in any stage is a 1-point
regression at the saw and the end-to-end number alone will not say which.

### Logging needed to attribute a failure

One record per leg, keyed by the trigger encoder count, written by every stage. rosbag2 records
MCAP by default and has a snapshot mode that keeps "an in-memory circular buffer" saved on a
service call ([rosbag2](https://github.com/ros2/rosbag2)); MCAP stores timestamped messages with
log and publish times and carries calibration as attachments ([MCAP spec](https://mcap.dev/spec)).
Minimum per leg:

- **Perception**: exposure count and time, raw depth crop, keypoints with confidence, yaw,
  model version, camera calibration hash.
- **Grasp selection**: candidates with scores, chosen grasp, rule or model version.
- **Tracking and intercept**: belt count and speed estimate at plan time, belt mode (run, ramp,
  stop from the PLC), predicted meet pose and time, trajectory limits, re-plan count, skip reason.
- **Grasp execution**: TCP pose at first contact, vacuum or jaw signal trace, dwell time, hold
  verified, pre-grasp versus post-lift in-hand pose from the transfer camera.
- **Place or orient**: commanded and achieved place pose, push force trace if pushing.
- **Release**: release pose, settle frames.
- **Verification and saw**: measured cut offset and angle, pass or reject, and the saw's own
  scored offset and angle when it reports them, joined by count.
- **Always**: reason code for any terminal outcome from a closed list, software SHA per stage,
  config hash, operator interventions with trigger.

## 4. Continuous improvement loops: published evidence

| System | Loop | Scale | Result with trial counts | Source |
|---|---|---|---|---|
| QT-Opt | offline RL on fleet grasps, then on-policy fine-tuning | 580k grasps, 7 KUKA IIWA, about 800 robot hours | unseen objects 87 percent offline, 96 percent after 28k on-policy grasps (7 robots x 102 attempts); earlier method on 900k grasps 78 percent | [Kalashnikov et al. 2018](https://arxiv.org/abs/1806.10293) |
| MT-Opt | multi-task fleet RL | 7 robots, 800k episodes over 16 months | 89 percent on lift-any, 100 evaluations per task | [Kalashnikov et al. 2021](https://arxiv.org/abs/2104.08212) |
| RT-1 | teleop data engine | about 130k episodes, 13 robots, 17 months, 744 tasks | seen 97, unseen 76 percent over 3000+ trials; capping per-task data at 51 percent drops seen to 71; keeping 97 percent of data but 75 percent of tasks drops unseen to 54 | [Brohan et al. 2022](https://arxiv.org/abs/2212.06817), tables 2 and 7 |
| AutoRT | VLM-directed collection, 1 human per 3 to 5 robots | 77,000 episodes, 7 months, 4 buildings, over 20 robots | co-fine-tuning RT-1 on it: picking at unseen heights 0/24 to 3/24, wiping 1/10 to 3/10 | [Ahn et al. 2024](https://arxiv.org/abs/2401.12963), table 5 |
| RLS waste sorting | deploy, human-label each episode, retrain on all data, promote only if better | 23 robots, 3 buildings, 9,527 hours of experience, 540k classroom episodes | 84.35 percent of objects sorted versus 67.39 sim-only and 71 for a hand-improved script; 4,800 evaluation trials over 240 scenarios | [Herzog et al. 2023](https://arxiv.org/abs/2305.03270) |
| HIL-SERL | human corrections during online RL | 12 tasks, 1 to 2.5 h each (timing belt 6 h), one RTX 4090 | 100 percent on every task over 100 trials each against 49.7 percent for HG-DAgger with the same interventions; cycle time 9.6 to 5.4 s | [Luo et al. 2024](https://arxiv.org/abs/2410.21845), table 1 |
| Sirius | intervention-weighted retraining in rounds | 4 tasks, 3 rounds | 27 percent higher success than prior work on real hardware, 32 trials per method | [Liu et al. 2022](https://arxiv.org/abs/2211.08416) |
| Fleet-DAgger | allocating a few humans across many robots | 100 sim robots; 4 ABB YuMi with 2 remote humans | up to 8.8x return on human effort in sim; physical win "by a small margin" | [Hoque et al. 2022](https://arxiv.org/abs/2206.14349) |
| pi*0.6 (RECAP) | RL from autonomous and corrected deployment episodes | box assembly: 600 autonomous plus 360 intervention trials per iteration | throughput 2x after 2 iterations on box assembly; a targeted failure mode removed to 97 percent success over 2 x 600 trajectories | [Physical Intelligence 2025](https://arxiv.org/abs/2511.14759) |
| Amazon Robin | pick-success predictor retrained on production picks | about 395k production picks for training; A/B of about 1.16M picks per arm | success 95.02 to 96.20 percent, 23.7 percent fewer failures; "retraining the model on more recent data improves performance" | [Li et al. 2023](https://arxiv.org/html/2305.10272) |
| Amazon Robin perception | annotate failures and low-confidence images, add to training | fleet | "In just six months, we halved the number of packages Robin's perception system can't pick" (no baseline given) | [Amazon Science](https://www.amazon.science/latest-news/robin-deals-with-a-world-where-things-are-changing-all-around-it) |
| Ocado On-Grid Robotic Pick | behaviour cloning plus RL, fleet shares errors | 30M+ items picked in 2024, 50+ arms | no success rate published | [Ocado 2025](https://www.ocadogroup.com/newsroom/stories/ocado-robotic-arms) |
| Chef Robotics | field runtime becomes training data | 100M servings by April 2026, more than a dozen facilities | no robot count or model success rate published | [Chef 2026](https://www.chefrobotics.ai/post/100-million-servings-and-counting), [Chef 2025](https://www.chefrobotics.ai/post/weve-raised-43-1m-to-accelerate-our-ai-enabled-robot-deployments) |

What the evidence supports, and what it does not:

- **Promote only on a measured win.** RLS makes each new policy the collector only if it beats the
  previous one, and the loop beat a hand-tuned script by 13 points without more engineering.
- **Hard negatives pay.** QT-Opt's 28k on-policy grasps, 5 percent of the data, bought 9 points;
  the paper credits a "hard negative mining" effect. pi*0.6 removes named failure modes with
  targeted iterations. Neither is a head-to-head against uniform collection, so "failure-targeted
  beats uniform" is plausible and unverified for manipulation.
- **Diversity beats volume.** RT-1's table 7 is the cleanest ablation: fewer tasks with nearly all
  the data cost more generalisation than less data per task.
- **Corrections beat demos for precision.** HIL-SERL's ablation: demonstrations without
  interventions average 49 percent against 100 with them.
- **Company claims carry no denominators.** Ocado, Chef and Covariant publish volumes, not success
  rates tied to a model version; Covariant's RFM-1 pages returned 404 on 2026-09-15, so nothing
  from Covariant is used here. No meat or poultry deployment with a published learning loop was
  found; the closest is a human-in-the-loop meat cutting study with 96 percent hand detection over
  50 trials and no learning from operator edits
  ([Parekh et al. 2025](https://arxiv.org/html/2508.14763)).

## 5. Recipe for the leg cell

### What each stage reports

| Stage | Metric, per leg | Gate (placeholder until the saw window is known) | Ground truth in sim | Ground truth on the real cell |
|---|---|---|---|---|
| 1 Perception | hock and trotter keypoint error (mm), yaw error (deg), no-pose flag; signed error by field position | keypoint σ ≤ 2 mm, yaw p95 ≤ 2 deg, no-pose ≤ 1 percent; no spatial ramp in signed error | privileged state | hand-labelled keypoints on 200 stored depth crops, two labellers, inter-labeller spread reported |
| 2 Grasp selection | chosen grasp versus labelled acceptable region; downstream hold rate by grasp class | inside region ≥ 98 percent | privileged mesh and labels | labelled crops; hold rate from stage 4 joined by count |
| 3 Tracking and intercept | TCP minus predicted grasp point at contact (mm); skip rate; re-plans; error by belt mode | p95 ≤ 2 mm at run speed; skips ≤ 1 percent; stop and ramp cases reported separately | privileged state at first contact | rigid dummy with a fiducial on the belt, TCP camera or touch probe; 3 speeds plus a stop |
| 4 Grasp execution | hold success; in-hand shift and rotation (post-lift minus pre-grasp) | hold ≥ 98 percent; in-hand shift p95 reported, not gated until measured | privileged relative pose | transfer camera, pre-grasp versus in-hand estimate |
| 5 Place or orient | achieved minus commanded place pose (mm, deg) | p95 ≤ 1.5 mm | privileged | verification camera before release |
| 6 Release | pose change from open to settled (mm, deg) | p95 ≤ 2 mm | privileged | verification camera frames before and after |
| 7 Verification | estimator error against the saw's score | σ ≤ 1.3 mm (the allocation above) | privileged | saw-scored offset and angle joined by count, or calipers on 50 cut legs |
| End | cut offset and angle at the saw; legs in tolerance | p95 ≤ 5 mm and 5 deg | privileged | saw score |

### Error budget table for the leg cell

Offset at the saw, 95th percentile of |e|, the architecture this cell is headed for (verification
corrects the place). "Allocated" is what the stage may spend; "current" is the best number in hand.

| Stage | Term | Allocated | Current | Status |
|---|---|---|---|---|
| 1 Perception | keypoint σ, absorbed by verification for placement, sets grasp landing | 2.0 mm σ | 0.12 mm sim geometry; real leg unknown | measure on real crops |
| 1, 3 Calibration | hand-eye and belt frame σ | 1.0 mm σ | assumed 1.0; published eye-in-hand 2.9 to 4.4 mm | measure against a reference |
| 3 Tracking | bias | 0 (corrected) | 0.90 mm at 0.30 m/s, 1.38 at 0.50 | find the 2.4 ms term |
| 3 Arm tracking | σ at run speed | 1.0 mm σ | ABB ±2 mm at 150 mm/s | dummy test at 3 speeds |
| 4 Grasp | in-hand shift p95 | not allocated: verification absorbs it; limits pick success only | assumed 6.0 mm. First simulator measurement, 2026-09-15 (`scripts/measure_grasp_shift.py`, slabs, pinch gripper, belt stopped, aim error up to 10 mm and 10 deg, 72 trials): 0.81 mm p95 at closure, but 0 of 72 lifts succeeded, so it is not yet a grasp result | find why the lift fails, then measure on legs |
| 5 Place | arm path accuracy σ | 0.5 mm σ | IRB 1300 AT 1.0 to 1.5 mm (not σ) | measure on the place path |
| 6 Release | σ | 1.5 mm σ | assumed | measure |
| 6 Settle | one-sided p95 | 1.0 mm | assumed | measure |
| 7 Verification | estimator σ | 1.29 mm σ | assumed 2.0 | measure against saw score |
| End | Monte Carlo p95 | 5.0 mm | 5.09 mm with σ_v 2.0; 3.78 mm with σ_v 1.0 | recompute whenever a row changes |

### Regression suite

Four tiers, all run on every change to any stage, results stored with the SHA per stage.

1. **Contract and seam tests** (seconds, every commit): the existing
   [meat-cell-architecture](meat-cell-architecture.md) seam table, plus two from this note:
   signed perception error against field position must have no slope steeper than the 0.74 mm per
   metre left after the normal-based fix (the phantom slip detector; tighten as the estimator
   improves), and tracking prediction mean minus max over the suite must stay
   under a set fraction (a bias detector).
2. **Designed sim suite** (nightly): a fixed IC list from one seed. Belt profiles: steady at 150,
   300 and 500 mm/s, a ramp down to stop during approach, a stop during dwell, a restart during
   lift. Leg pose: yaw and cross-belt position spread from the logged distribution once there is
   one. 200 ICs per profile gives a distribution-free 95 percent interval on p95 and detects a
   0.5 mm mean shift per stage with paired comparison. Run the oracle substitution ladder weekly,
   not nightly.
3. **Replay suite** (nightly, grows): every real leg that failed at the saw or was rejected is
   added as an IC, with its measured keypoints, belt speed trace from the encoder log, and timing.
   Pass criterion is "no worse than the promoted version on the same ICs", McNemar on the paired
   outcomes. This is the harvested-log tier Waymo describes.
4. **Real canary** (before promotion): one lane, one shift. Pre-registered: at the 2 percent
   baseline failure rate, 500 legs with a reject threshold of 16 failures (α 0.047, power 0.85 to
   see 4 percent), or SPRT stopping at the thresholds above. Cut offset and angle p95 with the
   order-statistic interval, compared against the promoted version.

Promotion rule: tiers 1 to 3 pass, tier 4 is not rejected, and no stage metric regressed beyond its
detection threshold even if the end metric held (the CACE check).

### The improvement loop

Weekly, on production data:

1. **Pareto of reason codes.** Every rejected or out-of-tolerance leg carries a reason code and is
   attributed to a stage by its per-stage metrics; unattributed failures are a logging defect and
   are fixed first (the Cartman gap).
2. **Pick the stage with the largest share of variance or failures** from the budget, not the one
   most recently changed. As of this note that is real-leg keypoints and in-hand shift.
3. **Collect targeted data for that stage.** Perception: label the failed crops and the
   low-confidence ones (Amazon Robin's route). Grasp: log in-hand shift per grasp class and move
   the selection rule. Tracking: add the belt trace to the replay suite.
4. **Retrain or retune one stage.** One variable at a time
   ([experiment-protocol](../../sops/experiment-protocol.md)).
5. **Run the suite and promote only on a win** (RLS's rule), with the canary sized to the
   regression the team cares about.
6. **Update the budget table** with the new measured row and recompute the Monte Carlo. The budget
   is a living record, not a design-time document.
7. **Watch production** with a p-chart on reject fraction per shift and an EWMA on cut offset, so a
   slow drift (belt wear, product change, calibration creep) is seen before the saw scores fall
   out of tolerance.

Operator interventions during commissioning, if any learned stage is added later, are logged as
HIL-SERL and Sirius do: trigger, pre-intervention window, corrected action.

## Practical gotchas

- **Two stages that pass alone can fail together.** Perception passed at 0.65 mm worst, the tracker
  model was exact, and the chain failed its 2 mm gate at 0.50 m/s through a correlated bias
  (ingestion experiment, from field in simulation).
- **A tight max-to-mean ratio means bias.** The tracking term's max is 4 to 8 percent above its
  mean across 15 products; treating it as σ would have hidden a correctable 0.9 mm (computed from
  the experiment data).
- **Simulator reads can be one step stale.** `mj_step` leaves `sensordata` at the start of the
  step: 0.6 mm at 300 mm/s, presenting as calibration error (ingestion experiment).
- **A clipped mask gives a confident wrong centroid**, 9.8 mm, with nothing downstream able to
  notice (ingestion experiment). Border rejection is part of the perception contract.
- **Taxonomies leak.** Cartman categorised 168 of 241 failed grasps
  ([Morrison et al.](https://ar5iv.labs.arxiv.org/html/1709.06283)).
- **Path accuracy is not repeatability.** On the IRB 1300 datasheet path accuracy AT is 20 to 75
  times pose repeatability RP depending on variant (§1.8.3, source above).
- **The architecture note's p95 used 1.645.** For a two-sided magnitude it is 1.96; recompute
  before quoting its table.

## What a forward-deployed engineer must be able to do

- Write the budget for a customer's chain with measured and assumed rows marked, compose it by
  Monte Carlo, and say which two rows to measure next.
- Tell a bias from a variance in a stage's log, and turn a bias into a correction.
- Run the oracle substitution ladder in sim and say which stage owns the placement error.
- Size a canary for a stated regression and defend the number of legs to a line manager.
- Keep the replay suite growing from every real failure without being asked.

## Open questions

- The trotter saw's tolerance on cut offset and angle, and whether the saw reports its score per
  leg in a form that can be joined by encoder count.
- In-hand shift and rotation on a 9 to 13 kg leg during a velocity-matched lift, per gripper type.
- Keypoint localisation error for the hock on wet tissue, and the hock-to-trotter baseline
  distribution.
- The source of the 2.4 ms speed-proportional tracking term in the ingestion experiment.
- The customer belt's real stop and restart ramps, and whether the PLC exposes the mode early.
- Whether a failure-targeted collection policy beats uniform collection for the perception stage
  on this product; no manipulation paper found tests that directly.

## Related entries

- [conveyor-tracking-and-visual-servoing](conveyor-tracking-and-visual-servoing.md), [control-architecture-selection](control-architecture-selection.md), [meat-cell-architecture](meat-cell-architecture.md)
- [policy-evaluation](policy-evaluation.md), [deployment-engineering](deployment-engineering.md), [fleet-operations](fleet-operations.md), [real-world-rl](real-world-rl.md)
- [perception-ingestion](perception-ingestion.md), [pork-plant-skill-tree](pork-plant-skill-tree.md), [luo-2024-hil-serl](../papers/luo-2024-hil-serl.md), [brohan-2022-rt1](../papers/brohan-2022-rt1.md)
- Experiments: [2026-09-08-perception-ingestion](../../experiments/2026-09-08-perception-ingestion.md)

## Sources

Measurement and composition
- JCGM 100:2008, Guide to the expression of uncertainty in measurement: https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf (§3.2.3, 3.2.4, 5.1.2, 5.1.3, 5.2.1, 5.2.2, 6.3.1, 6.3.3)
- JCGM 101:2008, Propagation of distributions using a Monte Carlo method: https://www.bipm.org/documents/20126/2071204/JCGM_101_2008_E.pdf (scope, §5.7.2, 7.2.1)
- Chase and Parkinson, A survey of research in the application of tolerance analysis to the design of mechanical assemblies, Research in Engineering Design 3, 1991, archived ADCATS copy: http://web.archive.org/web/2015/http://adcats.et.byu.edu/Publication/91-1/DesRes_w_figs.html
- Scholz, Tolerance Stack Analysis Methods: A Critical Review, Boeing, 1995: https://faculty.washington.edu/fscholz/DATAFILES498B2008/TOLSTACK.pdf
- Barnfather, Goodfellow, Abram, Positional capability of a hexapod robot for machining applications (ISO 9283 definitions), Int J Adv Manuf Technol, doi:10.1007/s00170-016-9051-0: https://d-nb.info/1107765382/34
- ABB IRB 1300 product specification 3HAC070393-001 rev. M (distributor mirror): https://cdn.pennair.com/media/2023/11/3HAC070393-PS-IRB-1300-en.pdf ; Universal Robots collective data sheet, January 2023: https://www.universal-robots.com/media/1826690/01_2023_collective_data_sheet-1.pdf
- Hua, Su, Xin, Guo, A High-Precision Hand-Eye Coordination Localization Method under Convex Relaxation Optimization, Sensors 2024: https://pmc.ncbi.nlm.nih.gov/articles/PMC11207387/ ; Enebuse et al., A comparative review of hand-eye calibration techniques, IEEE Access 2021: https://wrap.warwick.ac.uk/id/eprint/156836/7/WRAP-comparative-review-hand-eye-calibration-techniques-vision-guided-robots-2021.pdf
- Zivid 2+ M60 datasheet v1.2: https://www.zivid.com/hubfs/User%20guides%20and%20datasheets/Zivid%202+%20M60%20Datasheet.pdf ; Photoneo MotionCam-3D M datasheet 11/2020: https://photoneo.com/wp-content/uploads/datasheets/MotionCam-3D%20M%20-%20Datasheet%2011_2020.pdf ; Intel RealSense D400 datasheet rev 016: https://www.realsenseai.com/wp-content/uploads/2023/07/Intel-RealSense-D400-Series-Datasheet-July-2023.pdf ; Intel D4xx tuning BKM: https://www.realsenseai.com/wp-content/uploads/2019/11/BKMs_Tuning_RealSense_D4xx_Cam.pdf

Belt estimation, intercept and vendor tracking
- ABB Application manual Conveyor tracking, RobotWare 6, 3HAC050991-001: https://search.abb.com/library/Download.aspx?DocumentID=3HAC050991-001&LanguageCode=en&DocumentPartId=&Action=Launch ; OmniCore, 3HAC066561-001 rev. Q: https://library.e.abb.com/public/547ef8c3fb6b477aa0fc12ae92e31cb4/3HAC066561%20AM%20Conveyor%20tracking%20OmniCore-en.pdf
- ABB PickMaster product specification 3HAC 5842-1: https://library.e.abb.com/public/36a9e50804973b42c125766d003e8625/PPAspec.pdf ; PickMaster 3.0 PR10041EN_R7: https://library.e.abb.com/public/77b700acf06bad86c1257b1300574dcf/PickMast3.0HR.pdf ; PickMaster brochure PR10342EN_R2: https://library.e.abb.com/public/bfe0a7a82909aa5ac1257b1300579abe/pickmaster_brochure.pdf ; Conveyor tracking data sheet S4Cplus: https://library.e.abb.com/public/51c0fc4c87a036f6c1257b1300579b96/Data%20sheet%20Conveyor_tracking.pdf
- FANUC Line Tracking Operator's Manual B-83474EN/03: https://robochallenge.pl/wp-content/uploads/2023/09/Line-Tracking-Operator-Manual.pdf
- KUKA.ConveyorTech 5.0 for KSS 8.2: http://supportwop.com/IntegrationRobot/content/5-Applicatifs_metiers_KST/ConveyorTech/KST_ConveyorTech_50_en.pdf
- Yaskawa DX100 Conveyor Synchronized Function HW0485517: https://icdn.tradew.com/file/201606/1569362/pdf/7052388.pdf
- Mitsubishi CR800 Tracking Function manual BFP-A3520-B: https://eu-assets.contentstack.com/v3/assets/blt5412ff9af9aef77f/bltd4e63e1a1679c64f/61726c56ca617d08ba764819/9a9dd449-a575-11ea-bd9a-b8ca3a62a094_CR800_Controller_-_Tracking_function_Instruction_Manual_bfp-a3520b.pdf
- Omron TM Conveyor Tracking manual I853-E-03: https://files.omron.eu/downloads/latest/manual/en/i853_tm_conveyor_tracking_users_manual_en.pdf?v=2 ; Epson RC+ 7.0 conveyor tracking chapter: https://files.support.epson.com/far/docs/epson_rc_pl_70_conveyor_tracking_(fromrc_pl_70_manual)_(r4).pdf
- Petrella, Tursini, Peretti, Zigliotto, Speed measurement algorithms for low-resolution incremental encoder equipped drives, 2007: https://kth.diva-portal.org/smash/get/diva2:1248310/FULLTEXT01.pdf ; Merry, van de Molengraft, Steinbuch, Velocity and acceleration estimation for optical incremental encoders, Mechatronics 20, 2010: https://techunited.nl/media/files/velocity_and_acceleration_estimation_for_optical_incremental_encoders.pdf
- Pulford, survey of manoeuvring target tracking models, arXiv 1503.07828: https://arxiv.org/pdf/1503.07828 ; Blom and Bar-Shalom, The interacting multiple model algorithm, IEEE TAC 33(8), 1988: https://doi.org/10.1109/9.1299
- Lynch and Park, Modern Robotics, 2017 preprint, §9.2.2: http://hades.mech.northwestern.edu/images/7/7f/MR.pdf ; Berscheid and Kröger, Jerk-limited real-time trajectory generation with arbitrary target states, RSS 2021: https://arxiv.org/abs/2105.04830
- Burkhardt et al., Multi-fingered dynamic grasping for unknown objects: https://arxiv.org/pdf/2310.17923

Evaluation, attribution and regression statistics
- Sculley et al., Hidden Technical Debt in Machine Learning Systems, NeurIPS 2015: https://papers.nips.cc/paper_files/paper/2015/file/86df7dcfd896fcaf2674f757a2463eba-Paper.pdf ; Breck et al., The ML Test Score, 2017: https://research.google.com/pubs/archive/46555.pdf
- Correll et al., Analysis and Observations from the First Amazon Picking Challenge: https://ar5iv.labs.arxiv.org/html/1601.05484 ; Zeng et al., Multi-view self-supervised deep learning for 6D pose estimation in the APC, 2017: https://ar5iv.labs.arxiv.org/html/1609.09475 ; Morrison et al., Cartman, 2018: https://ar5iv.labs.arxiv.org/html/1709.06283
- FetchBench: https://arxiv.org/html/2406.11793 ; Duan et al., AHA, 2024: https://arxiv.org/html/2410.00371 ; Liu et al., REFLECT, 2023: https://ar5iv.labs.arxiv.org/html/2306.15724 ; Honig and Oron-Gilad, Understanding and resolving failures in human-robot interaction, Frontiers in Psychology 2018: https://www.frontiersin.org/articles/10.3389/fpsyg.2018.00861/full
- Waymo, Safety Methodologies and Safety Readiness Determinations, 2020: https://arxiv.org/pdf/2011.00054 ; Afzal, Le Goues, Hilton, Timperley, A Study on Challenges of Testing Robotic Systems, ICST 2020: https://clairelegoues.com/assets/papers/AfzalQualitative20.pdf
- rosbag2: https://github.com/ros2/rosbag2 ; MCAP specification: https://mcap.dev/spec
- NIST/SEMATECH e-Handbook: sample sizes 7.2.4.2 https://www.itl.nist.gov/div898/handbook/prc/section2/prc242.htm ; p-chart 6.3.3.2 https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc332.htm ; CUSUM 6.3.2.3 https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm ; EWMA 6.3.2.4 https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm ; K-S 1.3.5.16 https://www.itl.nist.gov/div898/handbook/eda/section3/eda35g.htm
- Hanley and Lippman-Hand, If nothing goes wrong, is everything all right?, JAMA 249(13), 1983: https://jhanley.biostat.mcgill.ca/c607/ch08/zero_numerator.pdf ; SPRT threshold caveat, arXiv 2410.16076: https://arxiv.org/html/2410.16076v3

Deployment and improvement loops
- Kalashnikov et al., QT-Opt, 2018: https://arxiv.org/abs/1806.10293 ; MT-Opt, 2021: https://arxiv.org/abs/2104.08212
- Brohan et al., RT-1, 2022: https://arxiv.org/abs/2212.06817 ; Ahn et al., AutoRT, 2024: https://arxiv.org/abs/2401.12963
- Herzog et al., Deep RL at Scale: Sorting Waste in Office Buildings with a Fleet of Mobile Manipulators, 2023: https://arxiv.org/abs/2305.03270
- Luo, Xu, Wu, Levine, HIL-SERL, 2024: https://arxiv.org/abs/2410.21845 ; Liu et al., Sirius, 2022: https://arxiv.org/abs/2211.08416 ; Hoque et al., Fleet-DAgger, 2022: https://arxiv.org/abs/2206.14349 ; Physical Intelligence, pi*0.6 and RECAP, 2025: https://arxiv.org/abs/2511.14759
- Amazon Robin pick success prediction: https://arxiv.org/html/2305.10272 ; Amazon Science, Robin: https://www.amazon.science/latest-news/robin-deals-with-a-world-where-things-are-changing-all-around-it
- Ocado robotic arms, 2025: https://www.ocadogroup.com/newsroom/stories/ocado-robotic-arms ; Chef Robotics, 100 million servings, 2026: https://www.chefrobotics.ai/post/100-million-servings-and-counting ; Chef Robotics, raise announcement, 2025: https://www.chefrobotics.ai/post/weve-raised-43-1m-to-accelerate-our-ai-enabled-robot-deployments
- Parekh et al., human-in-the-loop meat cutting, 2025: https://arxiv.org/html/2508.14763

Not fetched or not verified, and not used for any number above: ISO 9283:1998 text (iso.org 403); Biagiotti and Melchiorri 2008 (login wall; double-S closed forms checked by integration instead); Wald 1945 and Page 1954 originals (paywalled); Bender's inflation-factor paper; Tsai and Lenz 1989 accuracy figures (unreadable OCR); Covariant RFM-1 pages (404); Stäubli VALtrack flyer (403); FANUC iRVision visual tracking B-83304EN, KUKA.ConveyorTech 7 and 8, Yaskawa YRC1000 conveyor manuals (not reachable); Carlson and Murphy 2005 field MTBF figures (IEEE page failed).
