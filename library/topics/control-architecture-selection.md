---
title: Control architecture selection for a pick-and-align cell with a blade downstream
date: 2026-09-08
tags: [topic, selection, control-architecture, conveyor-tracking, visual-servoing, mpc, learned-policy, error-budget, meat, assignment]
status: draft
source: synthesis (primary links inline and in Sources); error budget computed 2026-09-08 from the constants tabulated below
---

# Control architecture selection for a pick-and-align cell with a blade downstream

## What this decides

One question: which control loop runs the arm that intercepts a piece on a moving belt and puts
it into a cutter infeed fixture. Seven candidates, one set of criteria, one error budget, one
staged path, and the measurement that closes each stage.

This note does not re-derive the belt frame, the meeting-time quadratic or the four intercept
phases ([kinematics-dynamics-and-rotations](kinematics-dynamics-and-rotations.md)), the latency
chain and vendor tracking features
([conveyor-tracking-and-visual-servoing](conveyor-tracking-and-visual-servoing.md)), driver rates
and how to measure end-to-end delay ([connecting-to-real-robots](connecting-to-real-robots.md)),
or the shield and standards map ([safety-for-learned-policies](safety-for-learned-policies.md)).
It uses all four and adds the arithmetic they stop short of: which term in the budget each
architecture actually removes, what that is worth in millimetres, and at what belt speed each one
runs out.

## The cell and the numbers that bind

The cell is the one standing up in `../../src/meat_cell_sim/`: UR5e class arm on a pedestal, a
belt 1.5 m long carrying a slab past a photo-eye 400 mm upstream of the pick zone, an overhead
camera 720 mm above the belt surface, a cutter lane with a datum edge as the placement reference
([cell.xml](../../src/meat_cell_sim/assets/cell.xml)). Belt speeds under test are 0, 100, 200 and
300 mm/s; the 300 mm/s ceiling sits below ABB's 500 mm/s degradation point and inside the I-Cut
130's published 20 to 500 mm/s belt range
([meat-cutting-automation](meat-cutting-automation.md)).

Four constraints decide the architecture, and only the first is about millimetres.

- **Placement**: lane offset and yaw at the infeed, measured at the 95th percentile, not the mean.
  Two bounds are used throughout: 5 mm, the success threshold already pre-registered in
  [the sim baseline](../../experiments/2026-09-08-meat-cell-sim-baseline.md), and 2 mm, the
  stretch bound that a tighter cutter window would impose. The customer's actual window is
  unverified; the meat note has no figure for it.
- **Window**: the piece is available between the start window and the maximum tracking distance.
  A 600 mm window at 300 mm/s is 2 s for connect, approach, dwell and retreat, and an object that
  leaves the start window before the robot connects is skipped
  ([ABB manual 3HAC050991-001](https://search.abb.com/library/Download.aspx?DocumentID=3HAC050991-001&LanguageCode=en&DocumentPartId=&Action=Launch),
  section 1.4).
- **Throughput**: 60 / T_c picks per minute per arm. Every architecture that adds a settle, a
  second look or a re-grasp spends window and cycle time.
- **The blade**: the cutter downstream is guarded and interlocked. The arm never enters its
  envelope, but the cutter's start request is gated on the placed pose, so the control
  architecture is inside the argument the integrator has to sign.

## Candidates: what each one needs

| # | Architecture | Calibration it depends on | Latency budget it must hold | Rate |
|---|---|---|---|---|
| 1 | Open-loop trigger and move | Camera-to-belt, hand-eye, TCP, counts per metre. All of it, once, with no recovery from drift | Every stage compensated by the encoder count at the shutter; the whole flight is dead reckoned, so belt speed error integrates over `L/v` | Trigger to plan under 10 ms; execution at the driver rate |
| 2 | Encoder-synchronised tracking | Same set, plus the belt frame published from live counts | Only the command lag and one target-update period live on the clock (UR RTDE 2 ms, ABB EGM 10 to 20 ms) | Belt frame at the driver rate (250 to 500 Hz); target updates 10 to 100 Hz with an interpolator between |
| 3 | Position-based visual servoing | Second camera's intrinsics, hand-eye and belt-frame extrinsics. Errors in the second calibration enter the corrected pose directly | Loop delay sets the closed-loop bandwidth; a 20 Hz camera with 50 ms of processing gives roughly 2 to 3 Hz of usable bandwidth | Vision 20 to 30 Hz; correction blended into the belt-frame target at the driver rate |
| 4 | Image-based visual servoing | Tolerant of extrinsic error by construction ([Chaumette and Hutchinson 2006](https://doi.org/10.1109/mra.2006.250573)); still needs depth Z for the interaction matrix and the eye-to-hand Jacobians | Same loop delay, and the gain λ is bounded by it; convergence must finish inside the approach | Same as 3 |
| 5 | MPC over the intercept | Same as 2 or 3, plus a kinematic and limit model that is right | Solve time inside the control period, with the tail bounded, not the mean | 20 to 100 Hz replan over a 0.5 to 2 s horizon |
| 6 | Learned visuomotor policy | Camera pose is baked into the weights; the belt frame must be an explicit input or the policy learns belt speed from pixels | Inference plus chunk execution: 108 to 139 ms end to end for a pi0-class policy ([Physical Intelligence, RTC](https://www.pi.website/research/real_time_chunking)), 55 to 71 ms inference and 3 ± 2 control steps at 30 Hz ([Chef Robotics](https://www.chefrobotics.ai/post/latency-aware-vision-language-action-models-vlas-with-system-identification-for-real-time-robot-control)) | 10 to 50 Hz policy, interpolated to the driver rate |
| 7 | Hybrid: scripted approach, learned correction near contact, inside a deterministic shield | Union of 2 and 3, and the shield's limits come from the training distribution, not the URDF | 2's budget for the approach; the correction runs where the target is nearly stationary in the belt frame | 2's rates plus a 10 to 30 Hz correction over the last 100 to 200 mm |

## Candidates: where the error comes from and how it degrades

| # | Dominant error source | Degrades with belt speed as | Degrades with piece variation as | Characteristic failure |
|---|---|---|---|---|
| 1 | Gripper closure while the piece keeps moving: the piece translates `v · T_dwell` through the jaws, 15 mm at 100 mm/s and 45 mm at 300 mm/s for a 150 ms closure | Linearly, and hard. Also a belt speed change during flight is fully uncompensated: a 10 percent ramp for 0.5 s at 300 mm/s is 15 mm | Only through the grasp point; the plan cannot react to a piece that is not the size it assumed | Grasps the trailing edge, or misses. On a stop-and-go belt it misses every time |
| 2 | Servo tracking lag plus the pose estimate. ABB publishes plus or minus 2 mm at 150 mm/s, degrading above 500 mm/s (manual section 1.2) | Linearly through tracking lag, exposure and velocity-match residual; roughly 7 µm per mm/s of belt speed on the ABB figure | Not at all in the tracking, entirely in the pose estimator and the grasp | Encoder glitch or belt slip puts the target where the piece is not; ABB error 50163 when the external adjustment exceeds 0.2 m |
| 3 | The second pose estimate, and everything faster than the loop bandwidth | Weakly in the correction, strongly in what the loop no longer has time to converge on | Same estimator problem as 2, measured closer and with a smaller field of view, so better | Chases a segmentation flicker; oscillates if λ is raised to compensate for loop delay |
| 4 | Feature localisation in pixels times the metric scale: 1.46 mm per pixel at the sim's overhead camera (720 mm, fovy 52 deg, 480 rows) | Through the convergence residual: the error left when the approach runs out. At λ = 2 /s over a 200 mm approach, 0.09 mm at 100 mm/s, 1.3 mm at 300, 2.3 mm at 500 | Badly. A deformable piece has no stable point features, so the "features" become derived axes from the same segmentation, and the calibration-tolerance argument goes with them | Diverges when depth Z is wrong by enough to flip the sign of a Jacobian term; commands a Cartesian path that leaves the workspace |
| 5 | Whatever feeds it. MPC does not reduce a measurement error | Same as its feed, plus solve-time jitter times belt speed | Same as its feed | Solve overruns the period and the last solution is replayed stale; a model mismatch makes an infeasible plan look feasible |
| 6 | Not decomposable. Must be measured end to end | Through the uncompensated latency: at 33 ms of jitter (one control step at 30 Hz) and 300 mm/s that is 10 mm of scatter, and an 8-step chunk at 10 Hz is 240 mm of open-loop belt travel | This is the one place learning can win: in-hand shift and grasp point on a piece the script has no rule for | Silent, out-of-distribution, and correlated across a whole shift when lighting or product changes |
| 7 | 2's budget for the approach, the learned part's for contact | 2's speed dependence | The learned correction absorbs the piece variation the script cannot encode | The correction fires when it should not; the shield clamps and the cycle is lost |

## Error budget

### Terms

Every term is a one-sigma value in millimetres unless marked p95. `v` is belt speed in mm/s,
`L_dr = 400 mm` the dead-reckoning distance from photo-eye to pick, `L_servo = 200 mm` the
approach a servo loop can act over, `T_dwell = 0.15 s` the gripper closure the conveyor note uses.
Two product cases run throughout: **R**, a rigid dummy on a dry belt, which is what the bench and
the sim's rigid box actually measure, and **M**, wet meat, whose four worst terms are assumptions
with no published source.

| Symbol | What it is | Value | Source or assumption |
|---|---|---|---|
| `e_exp` | Uncertainty in the effective exposure instant, times speed | `v · 1 ms` | 10 ms exposure (Photoneo MotionCam-3D M) stamped mid-exposure; the 1 ms is an assumption. A 5-acquisition Zivid HDR at 100 to 500 ms makes this 30 ms and 9 mm at 300 mm/s unless each sub-acquisition is stamped |
| `e_stamp` | Timestamp jitter times speed | `v · 0.1 ms` hardware sync; `v · 9.5 ms` for a software stamp on a 30 Hz camera | ABB DSQC2000 sync input, UR 40 kHz decode; the software figure is a 33 ms frame read as uniform. USB skew of 5 to 30 ms is measured ([Chef Robotics](https://www.chefrobotics.ai/post/latency-aware-vision-language-action-models-vlas-with-system-identification-for-real-time-robot-control)) |
| `e_pose` | Pose estimate on the piece from the upstream frame | R 0.5, M 3.0 | Assumption. Baseline experiment adds depth noise sigma 2 mm; the PCA centroid averages that down, and what is left is segmentation boundary error, which meat has and a box does not |
| `e_pose2` | Pose estimate from the second, closer camera | R 0.8, M 2.0 | Assumption, smaller field of view |
| `e_feat` | Feature localisation for IBVS | R 1.46, M 3.0 | 1 px at 720 mm with fovy 52 deg over 480 rows is 1.46 mm, computed from `cell.xml`. On meat the feature is a derived axis, so it inherits `e_pose` |
| `e_cal` | Hand-eye plus belt-frame calibration residual | 1.0 | Assumption. Tsai-Lenz residual grows as rotation error times lever arm ([OpenCV calibrateHandEye](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#gaebfc1c9f7434196a374c382abf43439b)) |
| `e_enc` | Encoder quantisation | 0.058 | 5,000 counts per metre is 0.2 mm per count, uniform over half a count. ABB recommends 5,000 to 10,000 after 4x decoding |
| `e_pred` | Belt speed estimate error times the horizon it is extrapolated over | closed loop `4 mm/s · 50 ms = 0.2`; open loop `1 mm/s · L_dr/v` | 4 mm/s is the verified `BeltEstimator` figure (2 mm over a 0.5 s prediction, `snippets/conveyor_tracking.py`); the 1 mm/s long-horizon average is an assumption |
| `e_slip` (p95) | Belt stretch and product slip between encoder and piece over `L_dr` | R 0.5, M 2.0 | Assumption. ABB warns the belt "will stretch or flex" (section 3.2.1); no vendor quantifies product slip on a wet belt |
| `e_drift` (p95) | Piece moving relative to the belt after the image | R 0.3, M 2.0, scaled by the fraction of `L_dr` still dead reckoned | Assumption. Open question in the conveyor note; not Gaussian on meat |
| `e_track` | Servo tracking lag times speed | `v · 6.67 ms` | ABB's plus or minus 2 mm at 150 mm/s read as a 95 percent bound gives 1.0 mm sigma, hence 6.67 ms of equivalent lag. Linear extrapolation is mine; ABB says accuracy degrades above 500 mm/s |
| `e_cmd` | Command lag not compensated by belt-velocity feedforward | `v · 10 ms`, open loop only | ABB EGM 10 to 20 ms; UR RTDE 2 ms |
| `e_interp` | Target-update staircase | `v · 2 ms / sqrt(12)` | Ruckig-filtered to 500 Hz. Without an interpolator a 100 Hz target update at 300 mm/s moves the goal 3 mm per tick |
| `e_solve` | MPC solve-time jitter times speed | `v · 2 ms` | Assumption; must be measured as a tail, not a mean |
| `e_lat` | Policy latency jitter times speed | base frame `v · 33 ms`; belt frame `v · 5 ms` | One control step at 30 Hz, from the measured 3 ± 2 steps ([Chef Robotics](https://www.chefrobotics.ai/post/latency-aware-vision-language-action-models-vlas-with-system-identification-for-real-time-robot-control)). The belt-frame figure assumes the encoder-to-action path is stamped |
| `e_conv` | IBVS convergence residual | `5 mm · exp(-λ · L_servo/v)`, λ = 2 /s | Exponential decoupled decrease is the classical law's own guarantee ([Chaumette and Hutchinson 2006](https://doi.org/10.1109/mra.2006.250573)); λ = 2 is a design choice bounded by the 50 ms loop delay |
| `e_dwell` | Piece motion during gripper closure | tracked `0.02 · v · T_dwell`; open loop `v · T_dwell / sqrt(12)` | The 2 percent velocity-match residual is an assumption. The open-loop form is the full smear read as uniform |
| `e_grasp` (p95) | In-hand shift at closure | R 1.0, M 6.0 | Assumption. The conveyor note lists the in-hand motion distribution for wet meat on vacuum as an open question with no published data |
| `e_inhand` | Settling in transport under the 2 m/s² Cartesian cap | R 0.3, M 1.0 | Assumption |
| `e_arm` | Local absolute accuracy after TCP calibration | 0.5 | Assumption; repeatability on an industrial arm is tens of micrometres, absolute accuracy is millimetres without kinematic calibration |
| `e_release` | Shift on opening from 5 mm above the lane | R 0.3, M 1.5 | Assumption |
| `e_verify` | In-hand pose estimate from the verification camera | R 1.0, M 2.0 | Assumption |
| `e_settle` (p95) | Piece settling after release, before the cutter start request | R 0.2, M 1.0 | Assumption; "the piece keeps settling under its own weight" is field practice on other soft products, unverified for meat |

### How they sum

Gaussian terms combine in quadrature; `e_slip`, `e_drift`, `e_grasp` and `e_settle` do not, so they
are added at their 95th percentile on top:

```
p95_placement = 1.645 · sqrt( Σ σ_i² )  +  Σ p95_j
```

Adding the non-Gaussian terms linearly instead of in quadrature is deliberately conservative. It
is the right shape for meat, where the in-hand terms are one-sided and heavy-tailed, and the wrong
shape for a rigid dummy, where they are small enough not to matter.

Correction, 2026-09-15: placement error can fall on either side of the target, so a two-sided
p95 needs 1.96, not 1.645, in front of the square root, here and in the verification-loop formula
below. The tables in this note were computed with 1.645, so their Gaussian part reads about 16
percent optimistic; they have not been recomputed. The Monte Carlo budget in
[pipeline-error-budget-and-continuous-evaluation](pipeline-error-budget-and-continuous-evaluation.md)
supersedes them.

### Where each architecture stops meeting the bound

Placement p95 in millimetres, computed on 2026-09-08 from the constants above. **No fixture-side
correction**: the piece is released where the pick model says it is.

| Architecture | 0 | 100 | 200 | 300 | 500 mm/s | Meets 5 mm up to | Meets 2 mm up to |
|---|---|---|---|---|---|---|---|
| 1 open-loop (case R) | 3.9 | 11.9 | 16.9 | 24.0 | 38.5 | never on a moving belt | never |
| 2 encoder-synchronised (R) | 4.0 | 4.3 | 5.1 | 6.0 | 8.3 | 193 mm/s | never |
| 3 PBVS (R) | 3.6 | 3.9 | 4.6 | 5.6 | 7.7 | 244 mm/s | never |
| 4 IBVS (R) | 3.8 | 4.1 | 4.9 | 6.2 | 8.8 | 208 mm/s | never |
| 5 MPC (R) | 4.0 | 4.3 | 5.1 | 6.2 | 8.5 | 187 mm/s | never |
| 6 learned, base frame (R) | 3.2 | 7.5 | 13.0 | 18.5 | 29.7 | 52 mm/s | never |
| 6 learned, belt frame (R) | 3.0 | 3.7 | 4.9 | 6.3 | 9.1 | 208 mm/s | never |
| 7 hybrid (R) | 3.1 | 3.4 | 4.1 | 5.1 | 7.2 | 295 mm/s | never |
| 2 encoder-synchronised (M) | 16.1 | 16.2 | 16.5 | 17.1 | 18.6 | never | never |
| 3 PBVS (M) | 11.8 | 12.0 | 12.4 | 13.1 | 14.8 | never | never |
| 7 hybrid (M) | 8.8 | 9.0 | 9.4 | 10.1 | 11.8 | never | never |

Three readings, in the order they matter.

**Open-loop is not a candidate on a moving belt**, and its binding term is not accuracy, it is
`e_dwell`: the piece slides `v · T_dwell` through the jaws while they close, 15 mm at 100 mm/s and
45 mm at 300 mm/s. A 180 mm slab survives that geometrically and arrives rotated. Open-loop is the
right architecture for a stopped or indexed belt and for nothing else.

**On meat, no belt-side architecture meets 5 mm at any speed**, because the assumed `e_grasp` of 6 mm p95
exceeds the bound on its own. That is not an artefact of pessimistic numbers, it is the structure
of the problem: the pose that reaches the cutter is not the pose that was measured, and no amount
of tracking accuracy touches the difference.

**The differences between architectures 2 to 5 are second order**: between the best and the worst
of them the 5 mm crossing moves from 187 to 244 mm/s, about 30 percent, on a rigid dummy. The
same table's spread from `e_cal` alone is larger: dropping the calibration residual from 1.0 to
0.5 mm moves encoder-synchronised tracking from 193 to 226 mm/s. Calibration and the grasp are
worth more than the control loop.

### What the budget says that the candidate list does not

Add the fixture-side loop the conveyor note describes but does not cost: a camera over the transfer
path measures the piece **in the gripper**, the place pose is corrected by the measured offset and
rotation, and a push-to-datum primitive finishes the alignment against the lane's datum edge. That
loop measures downstream of every upstream error, so it absorbs them. What survives is its own
estimator, the arm's local accuracy, the release, and the settle:

```
p95_placement = 1.645 · sqrt( e_verify² + e_arm² + e_release² ) + e_settle
```

| Case | `e_verify` | p95 placement | Speed dependence |
|---|---|---|---|
| R rigid dummy | 1.0 | **2.10 mm** | none |
| M meat | 2.0 | **5.19 mm** | none |
| M with a better in-hand estimator | 1.5 | 4.59 mm | none |
| M, requirement for 5 mm | 1.84 or better | 5.00 mm | none |

The 2 mm bound on meat is out of reach through this loop at any `e_verify`: release scatter at
1.5 mm sigma and 1.0 mm of settling give 3.6 mm p95 with a perfect in-hand measurement. Reaching
2 mm on a deformable piece requires changing the release, not the controller: place with the jaws
still supporting, push to the datum, then open from zero height, and re-verify.

That reframes the selection. **The belt-side architecture does not set the placement error once
the fixture-side loop exists**; it sets pick success and cycle time. On the pick-point error alone,
against a 15 mm grasp-landing tolerance for a 180 by 90 mm slab in 140 mm jaws, every closed-loop
candidate clears 700 mm/s on case M; the two that do not are open-loop (which fails immediately on
the dwell smear) and a base-frame learned policy (176 mm/s, killed by `e_lat`).

## Certifiability with a blade downstream

The blade is guarded and interlocked; the arm never enters its envelope. What the architecture
touches is the cutter's start request, which the PLC gates on the verified placed pose, and the
argument the integrator has to sign under an ISO 12100 risk assessment
([safety-for-learned-policies](safety-for-learned-policies.md)).

| # | Enumerable trajectory | What the integrator can credit | The blocker |
|---|---|---|---|
| 1, 2, 5 | Yes. A workspace box is a proof by construction, and vendor conveyor tracking is an ordinary robot program | The whole motion, as a conventional program under ISO 10218-2:2025 | None. MPC needs a bounded solve tail, or the fallback on overrun becomes the thing being certified |
| 3, 4 | Yes, if the correction is clamped. An unclamped servo law is not | The scripted approach plus a bounded correction | An IBVS law that can command a large Cartesian excursion when depth is wrong; clamp the correction magnitude and the clamp is what gets credited |
| 6 | No. The output cannot be enumerated in advance | Nothing about the policy. Only the shield and the PL-rated functions around it | Regulation (EU) 2023/1230, applying from 20 January 2027, lists safety components with self-evolving machine-learning behaviour in Annex I Part A, which forces third-party conformity assessment ([EUR-Lex](https://eur-lex.europa.eu/eli/reg/2023/1230/oj)). IEC 61508-3 has no route for a trained network to be a safety function at any SIL |
| 7 | Yes, at the shield boundary | The shield's clamps, the watchdog and the workspace box, all deterministic and testable against the scripted protocol | The shield is unrated software. It reduces demand on the safety function; it is not one. A Python watchdog is PL nothing ([ISO 13849-1:2023](https://www.iso.org/standard/73481.html)) |

Two rules survive every candidate. The policy PC has no wire into the safety chain; it can request
a hold, it cannot inhibit a stop. And with zero observed unsafe events, the upper bound on the rate
is about 3/n at 95 percent confidence, so 1,000 clean placements bound it near 0.3 percent per
placement ([Hanley and Lippman-Hand 1983](https://doi.org/10.1001/jama.1983.03330370053031)). Say
that number before anyone asks for it.

## The selection

**Run the cell on encoder-synchronised tracking with a fixture-side correction loop**, and add
layers only where a measurement shows they pay. That is candidate 2 plus the in-hand
measurement, which is where the millimetres actually are. Candidate 7 is the destination if and
only if the learned part earns its place on the numbers below.

Reasons, in order of weight. The fixture-side loop is worth 11 mm of p95 on case M and every
belt-side choice is worth about 1 mm. Encoder-synchronised tracking is shipped, tuned and
documented by the arm vendor, and ABB is the only vendor that publishes an accuracy figure to hold
it to. It degrades gracefully: a belt stop is a state, not a fault, and the controller keeps
tracking at zero speed. And it is the only candidate whose failure modes already have written
detections and recoveries (conveyor note, failure table).

### Staged path with measurement gates

| Stage | What it adds | The measurement that justifies adding it | The measurement that retires it |
|---|---|---|---|
| 0 | Encoder-synchronised tracking, one overhead frame, PCA pose, scripted grasp and place, verification frame for logging only | Baseline. Already the scripted controller in [the sim baseline](../../experiments/2026-09-08-meat-cell-sim-baseline.md) | Tracking error against a rigid dummy exceeds ABB's 2 mm at 150 mm/s. That is a bug, not an architecture decision |
| 1 | Fixture-side correction: in-hand pose from the verification camera, corrected place pose, push to datum | In-hand motion distribution: post-grasp pose minus pre-grasp pose, 200 pieces. If its 95th percentile exceeds the cutter window, stage 1 is mandatory | Never; this is the stage that makes 5 mm reachable on meat |
| 2 | Second-camera measurement update in the belt frame (a PBVS correction, not a full servo loop) | Predicted minus re-observed position over `L_dr`, 200 pieces. If the 95th percentile exceeds the window, the piece is not riding the belt and dead reckoning is not enough | The 95th percentile of that difference stays inside the window. Then the second camera stays a verification camera and nothing is added |
| 3 | MPC over the intercept | Window utilisation: the fraction of triggered objects skipped because the plan could not fit connect, approach and dwell inside the window, and the fraction rejected for a singularity or joint-limit violation at the meet pose. MPC buys feasibility, not millimetres | Skip and infeasibility rates are already under the throughput target with Ruckig and the fixed-point intercept planner |
| 4 | Learned segmentation, side classification, grasp-point scoring | Failure-mode counts from the checker: no-pose, wrong side, grasp that tore or folded. These need labelled frames, not demonstrations | Classical segmentation and PCA already produce a pose on more than 99 percent of triggered objects with the side right |
| 5 | Learned correction near contact, inside the shield (candidate 7) | The pre-registered outcome in [learned-vs-scripted](../../experiments/2026-09-15-meat-cell-learned-vs-scripted.md) | Same record, other branch |
| 6 | Full learned visuomotor intercept (candidate 6) | Nothing measured so far justifies reaching this stage | Stage 5's result |

### What would justify a learned policy over the scripted one

The pre-registered answer already exists and this note does not get to change it. A learned policy
gets real-robot days only if, on the randomized split of
[`experiments/2026-09-15-meat-cell-learned-vs-scripted.md`](../../experiments/2026-09-15-meat-cell-learned-vs-scripted.md),
it is significantly better than the scripted controller by McNemar at alpha 0.025 over 200 paired
initial conditions, **and** its lane-offset 95th percentile is no worse. A win on the nominal split
alone is overfitting to the training distribution and buys a widened demonstration distribution,
not robot time.

The budget adds one thing to that record: it says which term the learned policy has to move.
`e_pose`, `e_cal`, `e_track` and `e_interp` are all better handled classically, and a policy that
does not get the belt frame makes `e_lat` worse by 10 mm at 300 mm/s. The only terms a learned
policy is structurally better placed to reduce are `e_grasp` and `e_inhand`, the in-hand terms,
which are also the largest and the least sourced. So the secondary endpoint that decides whether
the win is real is the in-hand motion distribution, not the success rate. A learned policy that
raises success without shrinking in-hand motion won on grasp selection, which stage 4 buys more
cheaply with labelled frames.

The published evidence points the same way. The best learned result on raw meat is 40.6 percent at
38 s per pick on a stationary carcass
([ChicGrasp 2025](https://arxiv.org/abs/2505.08986)). A 2025 PPO framework grasping cans and
cartons from a conveyor runs it at a constant 30 to 70 mm/s
([Machines 13(10) 973](https://www.mdpi.com/2075-1702/13/10/973); the MDPI page returned HTTP 403
on 2026-09-08, so the speed range comes from the indexed abstract and the success rate is
unverified). No fetched paper reports a learned end-to-end policy grasping from a belt at 300 mm/s.
The classical line, by contrast, has reachability-aware dynamic grasping on a real arm
([Akinola et al. 2021](https://arxiv.org/abs/2103.10562); the abstract states no belt speed or
success rate and the full paper was not read this session, unverified), and vendor tracking with a
published tolerance.

One piece of evidence points toward learning near contact rather than away from it: RGB-D depth
stops being valid in the last centimetres of a grasp, which is exactly why Haviland, Dayoub and
Corke hand the final phase to an RGB-only IBVS loop
([arXiv:2001.05650](https://arxiv.org/abs/2001.05650)). Whatever runs in that final phase, learned
or servoed, is running on different information from the approach. That is the seam where stage 5
belongs.

## How to settle this by measurement

The head-to-head runs in the existing MuJoCo cell at `../../src/meat_cell_sim/`, which already has
the belt as a friction-driven body with a `belt_encoder` joint sensor, the UR5e, the parallel
gripper, the overhead camera and the cutter lane with its datum edge. Written before the run, per
[experiment-protocol](../../sops/experiment-protocol.md); it becomes its own record in
`experiments/`, not an addendum to this note.

**Arms.** Six controllers over the same simulator, the same initial-condition list and the same
checker: (1) open-loop trigger and move; (2) encoder-synchronised tracking; (2b) encoder-
synchronised tracking plus the fixture-side correction loop; (3) PBVS, a second belt-frame
measurement update over the last 200 mm; (4) IBVS on the segmented principal axes; (5) MPC over
the intercept. Candidates 6 and 7 are not in this experiment; they are the subject of the
learned-versus-scripted record and only run after 2b has a number.

**Initial conditions.** The baseline's list, extended: belt speed in {0, 100, 200, 300, 400,
500} mm/s so the crossings above can be located rather than assumed; slab size, mass and start
yaw from the baseline's sampling scheme; overhead camera pose perturbed by plus or minus 2 cm and
plus or minus 2 deg per episode. 200 paired initial conditions per speed, every arm on the same
list, interleaved within an initial condition so simulator drift is shared.

**Metrics.** Six, and the first two decide it.

- Placement p95: lane offset and yaw at the datum from the verification frame. This is the curve
  against belt speed that the budget above predicts.
- Pick-point error: TCP position minus true slab centroid at the instant the jaws first touch, from
  privileged state. This is the term the belt-side architectures actually control, and it separates
  a tracking failure from a grasp failure.
- In-hand motion: post-grasp minus pre-grasp pose, per episode. The term that decides whether
  learning has anything to do here.
- Success k/n with a Wilson 95 percent interval, on the baseline's definition (inside the lane
  polygon, offset within 5 mm, yaw within 5 deg, no tear proxy, no fold, under 8 s).
- Window utilisation: fraction of triggered objects skipped for infeasibility, and cycle time
  median over successes. This is where MPC has to earn its place.
- Wall-clock cost per episode, because the follow-on needs thousands.

**Pass criteria, pre-registered.**

- The budget is validated if the measured placement p95 for arms 2, 3 and 5 on the rigid box lands
  within a factor of 1.5 of the table above at 100, 200 and 300 mm/s. Outside that, the budget's
  constants are wrong and get corrected here before any architecture decision is taken.
- The fixture-side loop is mandatory if arm 2b beats arm 2 on placement p95 at 200 mm/s by more
  than 3 mm, paired Wilcoxon over jointly successful episodes. The budget predicts 4 mm on the
  rigid box and 11 mm on the deformable slab.
- The second camera earns a tracking role, rather than staying a verification camera, only if the
  95th percentile of predicted minus re-observed slab position over the 400 mm dead-reckoning
  distance exceeds the cutter window. Below that, arm 3 is dropped.
- IBVS is dropped unless it beats arm 2 on placement p95 at 300 mm/s with no additional
  calibration, which is its only claimed advantage. The budget says it will not, because on a
  deformable piece its features come from the same segmentation.
- MPC is dropped unless it reduces the skip rate at 300 mm/s, or its 99th percentile solve time
  is above the control period, in which case it is dropped for a different reason.
- The arm that wins carries into the learned-versus-scripted record as the scripted baseline. If
  no arm meets 5 mm at 200 mm/s even with the fixture-side loop, the belt speed target is the
  thing that moves, and that goes to the customer as a line-rate question, not to the controller.

## Practical gotchas

- **The candidate list is a distraction if the fixture-side loop is missing.** Ranking belt-side
  loops against a placement bound they cannot reach is how a cell ends up with a beautiful tracker
  and a 12 mm placement distribution.
- **Latency compensated by the encoder is free; latency on the clock is not.** Every architecture
  above pays only for the stages after the pose is expressed in the belt frame. Getting that
  boundary wrong is a 75 mm error at 300 mm/s and it looks like a control problem
  (conveyor note, snippet check 2).
- **MPC's cost is its tail, not its mean.** A solver whose median is 3 ms and whose 99th percentile
  is 40 ms fails at 100 Hz one cycle in a hundred, and the fallback on overrun is what the
  integrator will ask about. Measure the tail with the control loop under camera and inference
  load, the way `cyclictest` is run in [connecting-to-real-robots](connecting-to-real-robots.md).
- **A servo gain chosen without the loop delay is an oscillation waiting for a fast belt.** The
  exponential decrease in the classical law assumes no delay; with 50 ms of loop delay, λ above
  roughly 10 /s is where the phase margin goes.
- **Velocity-controlled policies degrade faster with latency than position-controlled ones**
  ([Chi et al. 2023](https://arxiv.org/abs/2303.04137), section 4.3). Any learned layer here
  outputs positions in the belt frame.
- **The shield's limits come from the training distribution, not the URDF.** A velocity clamp set
  from the robot's own limits clamps nothing.

## What a forward-deployed engineer must be able to do

- Write this budget for a customer's cell in an afternoon, with their camera, their arm, their belt
  speed and their cutter window, and say which three terms dominate.
- State, before building anything, which term each proposed layer removes and what it costs in
  cycle time.
- Defend the choice of encoder-synchronised tracking to a customer who has been told they need a
  learned policy, using their own placement distribution.
- Run the head-to-head above and report it with trial counts and intervals, including the arms
  that lost.
- Explain to a safety officer which parts of the architecture are enumerable, which are not, and
  what that means for the cutter's start gate under the 2027 Machinery Regulation date.

## Open questions

- The cutter's acceptance window. Every threshold in this note is a placeholder until the
  customer's manual supplies it.
- `e_grasp` on wet meat: the in-hand motion distribution during a velocity-matched lift at 100 to
  300 mm/s. It is the largest term in the budget and it has no source anywhere.
- `e_slip` on a wet belt: product slip relative to the encoder over 400 mm, at three speeds.
- Whether a second-camera measurement update in the belt frame beats a full IBVS loop on placement
  error for the same camera, which is stage 2 versus arm 4 above and is what the head-to-head
  answers.
- The 99th percentile solve time of an acados-class NMPC over this intercept on the cell PC, under
  camera and inference load ([acados](https://github.com/acados/acados),
  [Verschueren et al. 2019](https://arxiv.org/abs/1910.13753)). No published figure applies to this
  problem.
- Whether the release sequence can be changed (place supported, push to datum, open from zero
  height) enough to bring the 2 mm bound within reach on a deformable piece.

## Related entries

- [conveyor-tracking-and-visual-servoing](conveyor-tracking-and-visual-servoing.md) (latency chain, vendor tracking, alignment stage, failure table)
- [kinematics-dynamics-and-rotations](kinematics-dynamics-and-rotations.md) (belt frame, intercept quadratic, singularities, Ruckig)
- [connecting-to-real-robots](connecting-to-real-robots.md) (driver rates, MoveIt Servo, latency measurement, real-time loop)
- [safety-for-learned-policies](safety-for-learned-policies.md) (shield pattern, standards map, evidence folder)
- [meat-cutting-automation](meat-cutting-automation.md) (the cell, cutters, latency table), [deformable-object-manipulation](deformable-object-manipulation.md), [policy-evaluation](policy-evaluation.md), [imitation-learning](imitation-learning.md)
- Experiments: [2026-09-08-meat-cell-sim-baseline](../../experiments/2026-09-08-meat-cell-sim-baseline.md), [2026-09-15-meat-cell-learned-vs-scripted](../../experiments/2026-09-15-meat-cell-learned-vs-scripted.md)
- Code: `../../src/meat_cell_sim/`, `snippets/conveyor_tracking.py`, `snippets/kinematics.py`

## Sources

- ABB, Application manual Conveyor tracking, 3HAC050991-001 rev. Y: https://search.abb.com/library/Download.aspx?DocumentID=3HAC050991-001&LanguageCode=en&DocumentPartId=&Action=Launch (sections 1.2, 1.4, 3.2, 3.2.1, 5.12, 7.4)
- Chaumette and Hutchinson, Visual servo control part I, IEEE RAM 2006: https://doi.org/10.1109/mra.2006.250573 ; part II, 2007: https://doi.org/10.1109/mra.2007.339609
- Haviland, Dayoub and Corke, Control of the Final-Phase of Closed-Loop Visual Grasping using Image-Based Visual Servoing, 2020: https://arxiv.org/abs/2001.05650
- Akinola et al., Dynamic grasping with reachability and motion awareness, 2021: https://arxiv.org/abs/2103.10562
- Verschueren et al., acados: a modular open-source framework for fast embedded optimal control, 2019: https://arxiv.org/abs/1910.13753 ; repository: https://github.com/acados/acados ; Ruckig: https://github.com/pantor/ruckig
- Chi et al., Diffusion Policy, 2023: https://arxiv.org/abs/2303.04137 ; Zhao et al., ACT, 2023: https://arxiv.org/abs/2304.13705
- Physical Intelligence, Real-Time Chunking: https://www.pi.website/research/real_time_chunking ; Chef Robotics, latency-aware VLAs: https://www.chefrobotics.ai/post/latency-aware-vision-language-action-models-vlas-with-system-identification-for-real-time-robot-control
- Davar et al., ChicGrasp, 2025: https://arxiv.org/abs/2505.08986 ; Vision-Based Reinforcement Learning for Robotic Grasping of Moving Objects on a Conveyor, Machines 13(10) 973, 2025: https://www.mdpi.com/2075-1702/13/10/973 (page returned HTTP 403 on 2026-09-08)
- Regulation (EU) 2023/1230: https://eur-lex.europa.eu/eli/reg/2023/1230/oj ; ISO 13849-1:2023: https://www.iso.org/standard/73481.html ; ISO 10218-2:2025: https://www.iso.org/standard/73934.html ; ISO 12100:2010: https://www.iso.org/standard/51528.html
- Hanley and Lippman-Hand, If nothing goes wrong, is everything all right?, JAMA 249(13), 1983: https://doi.org/10.1001/jama.1983.03330370053031
- OpenCV calibrateHandEye: https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#gaebfc1c9f7434196a374c382abf43439b
- JBT Marel I-Cut 130 (belt 20 to 500 mm/s): https://jbtmarel.com/en/products/i-cut-130/meat/
