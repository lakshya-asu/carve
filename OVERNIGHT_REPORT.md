# Overnight build report

## Report language research and rewrite, 2026-08-26

This pass changed the writing, not the simulation. It began with research on generated-text style, detector limits, plain language, and technical writing for expert readers. The Firecrawl command was not installed, so the research used live web retrieval instead. The main sources were peer-reviewed papers, government guidance, and first-party technical style guides.

The research led to one clear rule: this project will not use an AI detector as a writing gate. Published studies show that single words do not prove authorship, people use unreliable cues, automated detectors can be biased, and paraphrasing can defeat many detector methods. The useful editorial checks are accuracy, specificity, evidence, clear actors, readable sentence structure, and honest status language.

Work completed:

- Rewrote the openings and key explanatory sections in `SCENE_DESIGN_REPORT.html` and `TECHNICAL_REPORT.html`.
- Replaced slogan-like headings with headings that describe the section.
- Put the Scene 2.0 decision, current limitation, and next action at the start of each report.
- Kept engineering terms where they carry a precise meaning.
- Kept the failed Solution B result visible.
- Added `WRITING_STYLE_RESEARCH.md` with the evidence review, project rules, examples, sources, limits, and review questions.
- Added `tools/audit_report_language.py` and focused tests.
- Added the language check to `open_scene_report.ps1`.

Exact commands:

```powershell
python tools\audit_report_language.py --fail-on-style --json
python tools\validate_scene_report.py
python -m pytest -q tests\test_scene_design_report.py tests\test_report_language.py
python -m pytest -q
```

Results:

- Scene report: 1,919 visible words, 93 prose sentences, median 10 words, longest 25 words.
- Technical report: 3,502 visible words, 162 prose sentences, median 10 words, longest 24 words.
- Configured canned phrases: zero in both reports.
- Prohibited dash characters: zero.
- Encoding replacement characters: zero.
- HTML structure and local reference validator: passed.
- Focused report tests: 4 passed.
- Full ordinary-Python suite: 102 passed and 1 skipped because NumPy is not installed in that interpreter.

Fresh visual checks:

- `results/report_validation/human_language/scene_report_desktop.png`
- `results/report_validation/human_language/scene_report_mobile.png`
- `results/report_validation/human_language/technical_report_desktop.png`

The three files are nonempty and were inspected. The desktop and mobile openings remain readable, navigation fits the desktop layout, the mobile report reflows cleanly, and the truth labels remain visible. Playwright Chromium closed after rendering. No Isaac Sim or Kit process was running after the pass.

No simulator rerun was needed for the language rewrite itself. Later simulator work superseded the old status recorded here. The FANUC Scene 2.0 robot is now imported and its six-axis articulation and ROS bridge have passed their focused gates. The latest complete Scene 1 suite also passes both solutions.

## Scene 2.0 design gate, 2026-08-26

The next implementation phase is now explicitly scene-first. `SCENE_DESIGN_V2.md` selects the FANUC M-10iD/12 Food Grade as the production-oriented six-axis baseline, subject to import and validation in Isaac Sim. The planned model source is the official FANUC `m10_12-14d` ROS 2 description and mesh package. It will be labeled as a kinematic and visual simulation reference, not as proof of exact OEM food-grade appearance, collision geometry, controller dynamics, washdown performance, or physical safety.

The companion `SCENE_DESIGN_REPORT.html` is a self-contained responsive engineering report with interactive technical drawings and actual Isaac evidence. It distinguishes verified evidence from proposed geometry and unresolved physical work. The validator checks local media links, internal anchors, unique IDs, required landmarks, image alternatives, required truthful status text, and prohibited dash characters. The complete ordinary-Python suite passed with 100 tests and one NumPy-dependent skip after the report was added.

Validation commands:

```powershell
python tools\validate_scene_report.py
python -m pytest -q
```

Results:

- HTML validator: passed
- Ordinary-Python suite: 100 passed, 1 skipped because NumPy is not installed in the ordinary interpreter
- Desktop dark render: `results/report_validation/scene_report_desktop.png`
- Desktop light render: `results/report_validation/scene_report_light.png`
- Responsive 500 px render: `results/report_validation/scene_report_mobile_500.png`
- Long-page visual inspection render: `results/report_validation/scene_report_long.png`

The report was rendered through installed Microsoft Edge in headless mode for visual inspection. Direct navigation of the in-app browser to the local `file:` URL was blocked by that browser's URL security policy. The project launcher remains `open_scene_report.ps1`.

The proposed cell places the robot on a side pedestal between a moving source conveyor and a stationary cutter-entry tray. The baseline sensors are a fixed global-shutter RGB camera, a registered depth stream, conveyor encoder, entry photoeye, robot joint feedback, bilateral jaw contact and position, a wrist force and torque reference, and PLC-style cutter and safety signals. The current 175 mm gripper opening is not compatible with the 200 mm maximum pork width. The replacement reference gripper requires at least 240 mm clear opening.

The recipe-mesh regression was repaired after this design gate. The current complete suite passes both Solution A and Solution B. The Scene 2.0 integrated task milestone is still not claimed because perception, compliant contact grasping, and end-to-end delivery have not yet been connected to the FANUC scene.

Exact next gate: import the official FANUC description, create a project-owned USD, and prove six-axis articulation behavior, joint limits, reach, collision clearance, fixed-step execution, save and reload, and deterministic joint sweeps before adding the rest of the cell.

## Solution B buffer regrasp hardening, 2026-08-26

The buffer regrasp failure was reproduced and fixed without weakening the contact gate. The rendered buffer observation placed the settled product near x 1.781 m and y -0.581 m with about -17 degrees of yaw. The old controller discarded that measured correction and returned to a nominal buffer command pose. It also closed to the maximum width envelope even though the tapered mesh is narrower at its central grasp section.

The fixed controller preserves the observed RGBD pose. It calculates the central mesh width for the stationary regrasp and gives the finite-effort finger drives enough fixed simulation time to close. The moving pick still uses the wider nominal envelope because applying the tighter stationary closure during interception tipped the product.

Focused evidence:

- `results/fixes/buffer_regrasp_full`
- Two nominal Solution B deliveries passed.
- Failed grasp recovery passed.
- Buffer timeout recovery passed.
- Four of four deterministic replay checks passed.
- Position p95 was 47.82 mm.
- Angle p95 was 0.0617 rad.
- Unexpected collisions were zero.
- Joint-limit violations were zero.

Complete-suite evidence:

```powershell
.\run_tests.ps1
```

- Ordinary Python: 118 passed and 1 skipped.
- Solution A: passed four cycles.
- Solution B: passed four cycles.
- Total nominal deliveries: 4.
- Total expected recovery cycles: 4.
- Deterministic replay: 8 of 8.
- Aggregate position p95: 48.56 mm.
- Aggregate angle p95: 0.0623 rad.
- Intercept timing p95: 3.10 ms.
- Perception latency p95: 33.28 ms.
- Unexpected collisions: zero.
- Joint-limit violations: zero.
- Artifact audit: passed.
- Isaac Sim and Kit processes after completion: zero.

The compliance value, force proxy, friction, and rigid product model are still simulation assumptions. The next gate is a visible and actuated compliant gripper mechanism on Scene 2.0, followed by the Scene 2.0 perception and task pipeline.

## Recorded demonstration and implementation report, 2026-08-26

The actual rendered overhead RGB stream is now recorded during the integrated Isaac run. This is not a simulator-independent proxy video. The recorder samples the overhead camera on the 240 Hz fixed simulation clock and streams RGB24 frames to a local H.264 encoder.

Command:

```powershell
.\record_yolo_demo.ps1
```

Result:

- Solution: B
- Vision: trained YOLO26 segmentation checkpoint `cf280497427a...`
- Seed schedule: 2601 through 2604
- Cycles: two nominal, failed grasp, buffer timeout
- Video: `results/yolo/recorded_demo/isaac_b/demo.mp4`
- Video format: H.264, 640 by 480, 12 FPS, 377 frames, 31.42 seconds
- Articulation commands: 6,603
- Rendered learned observations: 8
- Nominal deliveries: 2 of 2
- Recovery cycles: 2 of 2 expected cases
- Deterministic replay: 4 of 4
- Unexpected collisions: 0
- Joint-limit violations: 0
- Overall gates: passed

The run saved the complete USD stage, RGB and depth media, four JSON Lines traces, machine-readable metrics, the MP4, and a contact sheet. Isaac Sim closed cleanly after the batch.

Implementation changes:

- `isaac_sim/video_recorder.py` streams actual RGB24 frames to H.264 and records frame, simulation-time, codec, and file metadata.
- `isaac_sim/adapter.py` samples the rendered overhead camera at a fixed divisor of the physics rate.
- `isaac_sim/run_cell.py` accepts `--record-video` and `--record-fps`.
- `isaac_sim/cell_runner.py` starts and stops recording and enforces a machine-readable video gate.
- `record_yolo_demo.ps1` is the one-command recording entry point.
- `TECHNICAL_REPORT.html` is a complete visual implementation report. It covers system parts, communication, inputs and outputs, message contracts, state machines, PLC I/O, YOLO26, control, evidence, failure handling, code map, commands, assumptions, and the exact next ticket.

Validation commands:

```powershell
py -3.12 -m compileall -q isaac_sim
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,r_frame_rate,nb_frames -of json results\yolo\recorded_demo\isaac_b\demo.mp4
```

The exact next ticket remains T015. It requires OEM selection and physical calibration evidence. No new physical, food-safety, real-cell safety, OEM, or production claim is made.

## Outcome

The integrated Isaac Sim reference milestone is complete under the documented simulation assumptions. T001 through T014 are done. Both Solution A and Solution B pass their four-cycle seeded Isaac suites. Each solution perceived a moving workpiece from rendered RGB and depth, tracked and predicted it, intercepted it through the actual articulation controller, confirmed two-finger contact, held and reoriented it, aligned it to `cut_target_frame`, delivered it, and retracted.

The implementation is reproducible and runnable. It is not an OEM, physical, food-safety, real-cell safety, or production validation.

Run completed at 2026-08-26 01:23 EDT after about 1 hour 27 minutes of runtime checks, implementation, diagnosis, repeated simulation, and reporting.

## Completed tickets

- T001 through T009: typed baseline, contracts, fixed clock, frame graph, conveyor, tracking, prediction, interception planning, grasp and slip models, supervisor, and recovery
- T010: Solution A direct transfer, cutter gating, alignment, feed, verification, retract, and reject
- T011: Solution B buffer transfer, settling, rendered re-observation, slip correction, contact regrasp, feed, verification, and recovery
- T012: JSON Lines event log, metrics, and deterministic replay
- T013: Isaac ports, adapter, and stage structure
- T014: integrated Isaac cell, tests, launchers, media, machine metrics, durable documentation, and report

The exact next ticket is T015, physical calibration and OEM asset replacement. It is blocked on OEM selections and real data.

## What was built

The saved A and B USD stages contain:

- conveyor structure and moving dynamic workpieces
- generic six-joint Cartesian articulation with enforced joint limits
- compliant two-finger gripper reference with finite-effort drives and contact reporting
- overhead and wrist camera mounts with actual rendered RGB and depth
- replaceable rendered color and depth segmentation interface with noise and latency injection
- calibration target and named world, conveyor, belt, robot, tool, buffer, cutter, and cut target frames
- guarded cutter or feed reference, guards, lighting, reject bin, and Solution B centering buffer
- simulated PLC fields for speed, recipe, cutter mode, phase, permissive, fault, emergency stop, and result acknowledgment

The integrated controller executes fixed-step quintic trajectories through Isaac's articulation controller. It checks the TCP envelope, guarded cutter volume, joint positions, commanded velocities, and commanded accelerations before execution. It performs conveyor-speed matching, grasp closure, bounded braking, lift, transport, reorientation, product-frame alignment, downstream handoff, release, retract, and raised recovery paths.

A grasp constraint is created only after both fingers report recent product contact. Solution B physically releases to the buffer, renders a new observation, estimates slip, corrects the target, and requires a second two-finger contact before feeding.

## Exact commands

Environment and compatibility:

```powershell
$env:OMNI_KIT_ACCEPT_EULA='YES'
C:\Users\jainl\is6\Scripts\isaacsim.exe isaacsim.exp.compatibility_check --no-window --/app/quitAfter=300 --/log/file='C:/Users/jainl/meat-conveyor-robot-simulation/results/compatibility_checker.log'
```

Unit and source checks:

```powershell
python -m pytest -q
$files = rg --files -g '*.py'
python -m py_compile $files
```

Setup and final integrated runs:

```powershell
$env:OMNI_KIT_ACCEPT_EULA='YES'
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\validate_setup.py --headless
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\run_cell.py --solution a --cycles 4 --seed 7 --headless
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\run_cell.py --solution b --cycles 4 --seed 7 --headless
```

Final one-command suite verification:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_tests.ps1
```

## One-command entry points

```powershell
.\validate_setup.ps1
.\run_solution_a.ps1
.\run_solution_b.ps1
.\run_tests.ps1
```

## Environment and setup results

- Isaac Sim: 6.0.1
- GPU: NVIDIA GeForce RTX 5080
- Driver: 610.88
- Compatibility checker: passed
- Required stage prims: passed, 121 prims in setup validation
- Fixed clock: passed, 240 steps and 1.0 simulated second
- Articulation: passed, six joints, X target 0.05 m and actual 0.04999993 m
- RGB: passed, 640 by 480 and 307,200 valid pixels
- Depth: passed, 640 by 480 and 307,200 valid pixels
- Rendered perception: passed, primary ground truth flag false
- Save and reload: passed, matching signature `aac2c6489c351e791a90367004f3f077562160b540140dfb8c16b267cb2f0dbc`
- Simulator cleanup: passed, no Isaac or Kit process remained after the final suite

## Test results

- Unit suite: 74 passed and 1 skipped in 0.40 seconds
- The skipped ordinary-Python test requires NumPy. The same perception path ran and passed against real Isaac RGB and depth in setup validation and both integrated suites.
- Python compilation: passed for every Python source file
- Setup validation: passed
- Solution A integrated gates: passed
- Solution B integrated gates: passed
- Deterministic replay: 4 of 4 cycles passed for A and 4 of 4 cycles passed for B
- Final `run_tests.ps1`: exit code 0

## Final metrics

| Metric | Solution A | Solution B |
|---|---:|---:|
| Seeded cycles | 4 | 4 |
| Nominal deliveries | 2 of 2 | 2 of 2 |
| Expected recovery cycles | 2 of 2 | 2 of 2 |
| Aggregate success count | 2 | 2 |
| Placement position p50 | 0.003240 m | 0.003089 m |
| Placement position p95 | 0.003322 m | 0.003196 m |
| Placement angle p95 | 0.005914 rad | 0.019411 rad |
| Timing error p95 | 0.008333 s | 0.008333 s |
| Transfer speed error p95 | 0.023061 m/s | 0.051804 m/s |
| Perception latency p95 | 0.032333 s | 0.032333 s |
| Articulation commands | 4,893 | 5,906 |
| Rendered tracking observations | 8 | 8 |
| Unexpected collisions | 0 | 0 |
| Joint-limit violations | 0 | 0 |
| Replay checks | 4 of 4 | 4 of 4 |

The reported aggregate success rate is 0.5 because two of four cycles intentionally inject failures. It is not an estimated production yield. Both nominal cycles succeeded for each solution.

Solution A failure cycles covered a no-contact grasp and cutter unavailability before commitment. The first recovered to home. The second used a collision-free raised reject path.

Solution B failure cycles covered a no-contact grasp and maximum buffer hold timeout. Both recovered to a known safe state.

The final traces also show PLC result acknowledgment changing from false to true on every successful cycle. Failed grasp and buffer timeout traces set the PLC fault state. The cutter-unavailable A trace records the blocked cutter mode. Emergency-stop state remains available but was not injected in this four-cycle suite.

## Failures found and fixed

1. The initial gripper geometry transform order scaled tool and finger offsets. This prevented true contact. Translation is now authored before scale, which places the physical finger collision shapes at the tool.
2. The original closure completed too near the cutter for a bounded velocity reversal. Closure was shortened and a 12 m/s2 X-axis limit plus explicit braking and lift sequence was added.
3. Direct delivery aimed the TCP at the product target. This caused a 92 mm product-frame error. The controller now measures the live tool-to-product transform and performs closed-loop product-frame correction.
4. Closed fingers continued to constrain the product after the grasp joint was removed. The controller now opens through the articulation before the downstream feed accepts the workpiece.
5. The original Solution B buffer height let fingers touch the buffer. Placement and regrasp clearances were separated and tuned. The final B suite reports zero unexpected collisions.
6. The raised B regrasp initially missed contact. Regrasp height was lowered while preserving 10 mm finger clearance over the buffer.
7. The direct reject trajectory entered the reject volume before it rose. Recovery now brakes, lifts, moves above the bin, lowers, opens, releases, and retracts.
8. The initial delivery feed velocity lagged the articulation. The guarded feed-station reference now accepts the aligned product and applies the simulated 0.40 m/s feed state after physical finger opening.

## Changed files

Core implementation:

- `meatcell/config.py`, `contracts.py`, `clock.py`, `frames.py`, `conveyor.py`, `tracking.py`, `interception.py`, `grasp.py`, `supervisor.py`, `solutions.py`, `eventlog.py`, `ports.py`, `fake_adapter.py`, and `perception.py`
- focused tests in `tests/` for each domain module and interface

Isaac implementation:

- `isaac_sim/adapter_config.py`
- `isaac_sim/stage_builder.py`
- `isaac_sim/adapter.py`
- `isaac_sim/perception_adapter.py`
- `isaac_sim/validate_setup.py`
- `isaac_sim/cell_runner.py`
- `isaac_sim/run_cell.py`
- `isaac_sim/README.md`

Launchers and documentation:

- `validate_setup.ps1`, `run_solution_a.ps1`, `run_solution_b.ps1`, and `run_tests.ps1`
- `README.md`, `SYSTEM_DESIGN.md`, `BUILD_STATUS.md`, and `OVERNIGHT_REPORT.md`
- `tickets/README.md`, T001 through T014 evidence, and blocked next ticket T015

Generated evidence:

- `results/isaac_cell_validation.usda`, `isaac_cell_a.usda`, and `isaac_cell_b.usda`
- `results/setup_validation.json`
- `results/isaac_a/metrics.json` and four traces
- `results/isaac_b/metrics.json` and four traces
- rendered RGB, depth arrays, and depth previews in the A, B, and validation media folders
- `results/compatibility_checker.log`

The historical architecture screen at `results/comparison_10000_seed7.json` was preserved.

## Assumptions and unresolved physical parameters

- The robot is a generic Cartesian articulation. Reach, inertia, drive tuning, cable routing, and controller behavior are not OEM accurate.
- The gripper is a generic two-finger reference. Jaw geometry, pad curvature, compliance, drainage, cleanability, and force control require selection and trials.
- The product is a rigid-body proxy. Deformation, tissue tearing, adhesion, wet friction, pressure distribution, and centroid motion are not physically modeled.
- The active fixed joint approximates a stable hold after two-finger contact. The hardening pass now authors the measured wrist-to-product local transform on the constraint. The former disjoint-body-transform warning and artificial constraint-frame snap are gone. The fixed joint itself remains a simulation approximation.
- The nominal 50 N gripper attribute and finger effort are force proxies. Contact impulses are not calibrated measurements.
- Camera intrinsics, extrinsics, lighting, material color, exposure, noise, and latency are assumed. The rendered segmentation model is a replaceable baseline, not a trained detector.
- Encoder speed is fused into tracking. Real encoder jitter, belt slip, stretch, and synchronization require measurements.
- The 2.24 m/s belt motion is enforced while a free product remains in the belt zone. Belt contact and friction are not a calibrated conveyor model.
- The downstream feed station is guarded reference geometry. It accepts the aligned product and applies a 0.40 m/s simulated feed state. No blade physics is present.
- PLC timing, permissive sequencing, emergency-stop latency, safety-rated behavior, and result acknowledgment are logical simulation contracts only.
- Placement, timing, collision, and replay metrics describe these simulated assumptions. They do not predict real-cell accuracy or throughput.

## Remaining blockers

T015 cannot start truthfully without:

- selected OEM robot, controller, and gripper assets
- real camera calibration and perception recordings
- conveyor speed, acceleration, encoder delay, and slip data
- meat geometry, compliance, friction, adhesion, damage, and slip trials
- cutter PLC I/O timing and guarded feed measurements
- physical safety engineering and validation

## Exact next ticket

T015: Physical calibration and OEM asset replacement. Status: blocked on OEM selections and physical data.

## Hardening pass: 2026-08-26

The results in this section supersede current-state counts earlier in this report where they differ. The earlier section remains as the historical first-pass record.

### Outcome

The second validation and hardening pass completed at 2026-08-26 03:34 EDT. The documented clean setup and full suite passed. The broader hardening matrix also passed for both solutions at all five seeds. The matrix exercised the complete simulator-driven nominal path and the implemented failure and recovery paths without weakening any gate.

T001 through T014 remain done. T015 remains blocked on OEM selections and physical data. No ticket status was changed merely because more tests passed.

### Commands executed

```powershell
.\validate_setup.ps1
.\run_tests.ps1
.\run_hardening.ps1
.\run_hardening.ps1 -Resume
python -m compileall -q isaac_sim meatcell tools tests
python -m pytest -q
C:\Users\jainl\is6\Scripts\python.exe tools\audit_artifacts.py --root results\hardening --mode hardening --expected-seeds 7,31,101,509,1001 --output results\hardening\summary.json
```

`run_hardening.ps1 -Resume` was used after fixing the first seed 31 Solution A emergency-stop attempt. The launcher skipped only matching, passing seed batches and reran the failed batch. Retry logs and the original `failure.json` were preserved.

### Setup and complete suite

- Setup validation: passed
- Current saved setup stage: 101 prims with all required contents present
- Fixed clock: 240 steps and exactly 1.0 simulated second
- Articulation response: target 0.05 m and measured about 0.04999993 m
- RGB: 640 by 480 with 307,200 valid pixels
- Depth: 640 by 480 with 307,200 valid pixels
- Rendered perception: passed with primary ground truth flag false
- Save and reload signature: `aac2c6489c351e791a90367004f3f077562160b540140dfb8c16b267cb2f0dbc`
- Ordinary-Python tests: 77 passed and 1 skipped
- Python source compilation: passed
- Baseline Solution A: passed with 2 of 2 nominal deliveries
- Baseline Solution B: passed with 2 of 2 nominal deliveries
- Baseline independent artifact audit: passed
- Final `.\run_tests.ps1` exit code: 0

The one skipped ordinary-Python test requires NumPy. The Isaac Python environment ran the corresponding image and artifact paths with NumPy against real rendered simulator outputs.

### Hardening seed matrix and counts

Seeds were 7, 31, 101, 509, and 1001. Each seed ran six cycles for Solution A and six cycles for Solution B. Batches were sequential to bound GPU use.

| Count | Solution A | Solution B | Total |
|---|---:|---:|---:|
| Batches passed | 5 of 5 | 5 of 5 | 10 of 10 |
| Cycles audited | 30 | 30 | 60 |
| Nominal deliveries | 10 | 10 | 20 |
| Failed-grasp paths | 5 | 5 | 10 |
| Cutter-unavailable paths | 5 | 0 | 5 |
| Buffer-timeout paths | 0 | 5 | 5 |
| Emergency-stop paths | 5 | 5 | 10 |
| Stale-observation paths | 5 | 5 | 10 |
| Replay checks | 30 of 30 | 30 of 30 | 60 of 60 |
| Unexpected collisions | 0 | 0 | 0 |
| Joint-limit violations | 0 | 0 | 0 |

Terminal paths were 20 success, 15 recovered, 15 reject, and 10 safe stop. These counts reflect explicit scenario injection. They are not a production yield estimate.

### Metric distributions

The placement, timing, and speed distributions below include successful deliveries only. Perception and interception include every applicable cycle. Safe-stop drift includes the 10 emergency-stop cycles.

| Metric | Solution A p50 | Solution A p95 | Solution A max | Solution B p50 | Solution B p95 | Solution B max |
|---|---:|---:|---:|---:|---:|---:|
| Placement position error, m | 0.003198 | 0.003333 | 0.003334 | 0.003318 | 0.003335 | 0.003337 |
| Placement angle error, rad | 0.001117 | 0.003320 | 0.003653 | 0.001196 | 0.003042 | 0.003753 |
| Delivery timing error, s | 0.008333 | 0.008333 | 0.008333 | 0.008333 | 0.008333 | 0.008333 |
| Transfer speed error, m/s | 0.017714 | 0.099342 | 0.161453 | 0.000293 | 0.005420 | 0.009508 |
| Perception latency, s | 0.027936 | 0.032179 | 0.035590 | 0.027936 | 0.032179 | 0.035590 |
| Intercept timing error, s | 0.001351 | 0.003970 | 0.004140 | 0.000980 | 0.003754 | 0.003995 |
| Safe-stop max joint drift | 0.000775 | 0.000900 | 0.000921 | 0.000737 | 0.000898 | 0.000918 |

All values passed the existing configured gates. They describe the generic reference simulation only.

### Artifact, media, trace, and PLC checks

The independent auditor passed 10 USD stages, 10 RGB files, 10 depth arrays, 60 traces, and 10 metrics files. Every RGB and depth output was 640 by 480 with 307,200 valid pixels. Images and arrays were nonempty and nonconstant.

The five A stages had identical file SHA-256 `b57a2b1759577c167c126d98102a53cf411b3ce56c98269d90a0a0da8329801f`. The five B stages had identical file SHA-256 `2f14e5f253cedd22f8e293de0935f7188aa16117dfe7cd11e7ae7222b2c808fe`.

Each trace had monotonic simulator timestamps and matching terminal metrics. The audit required real Isaac dependency metadata, rendered segmentation masks, controller command records, product contact, grasp attachment, alignment correction, delivery verification, PLC acknowledgment, expected fault transitions, collision and limit records, and deterministic replay.

The scenario-specific checks confirmed:

- nominal contact-confirmed delivery and acknowledgment
- failed grasp with no attachment and safe recovery
- cutter unavailable before commitment with raised reject recovery
- buffer timeout with fault and recovery
- Solution B rendered re-observation, slip correction, and contact regrasp
- emergency-stop PLC transition, conveyor stop, articulation hold, bounded drift, reset, and recovery
- stale rendered observation rejected before commitment and recovered

Machine-readable evidence is in `results/artifact_audit.json` and `results/hardening/summary.json`. Per-seed stages, media, traces, metrics, stdout, and stderr are under `results/hardening`.

### Failures investigated and fixes

1. Repeated nominal delivery runs exposed marginal product-frame alignment. Delivery now uses an initial downstream move followed by three measured product-frame corrections. A new nominal-delivery gate requires every scheduled nominal cycle to succeed.
2. The articulation wrist maximum velocity had been written to a PhysX attribute in radians per second even though that USD attribute uses degrees per second. The builder now performs the unit conversion. This removed the major cross-run tracking error.
3. The grasp fixed joint formerly used identity local transforms. It now uses the measured wrist-to-product transform. The former disjoint-body-transform warning and visible constraint-frame snap are gone.
4. The first seed 31 Solution A emergency-stop case caught a tiny contact-driven finger excursion outside the declared position limit. The safe-stop hold target is now clamped to declared joint limits before it is sent through the articulation controller. The failed attempt remains at `results/hardening/seed_0031/isaac_a/failure.json`.
5. Isaac's Python wrapper can terminate through `SystemExit` during application close and can obscure a nonzero result. Every launcher now parses the generated JSON and fails if `passed` is false or the expected metrics are missing.
6. Unused instance-segmentation annotation and duplicate RGB attachment caused shutdown and duplicate-output warnings. They were removed. The primary replaceable model still consumes actual rendered RGB and depth and produces its own mask.
7. Camera aperture was corrected for the 4:3 sensor aspect ratio. The associated camera warning is gone.
8. A standalone artifact auditor and focused tests were added because earlier gates trusted metrics without independently validating every stage, media file, trace sequence, and PLC path.
9. The hardening launcher now starts only from a clean Isaac process state, runs sequential batches, checks results, closes any process started by a failed batch, preserves retry logs, and supports verified resume.

### Remaining warnings and resource state

The final hardening logs contain no traceback, disjoint-body-transform warning, joint-creation failure, articulation acceleration or position-limit violation, camera aperture warning, duplicate RGB warning, or instance-segmentation shutdown warning.

Remaining simulator notices are Isaac Sim environment or renderer messages: synthetic-data deprecation notices, a gamepad notice, Replicator material configuration, an internal 320 by 240 DLSS recommendation, a muted USD diagnostic summary, and `pxr.Semantics` deprecation. They were not hidden. The actual saved 640 by 480 RGB and depth outputs and all independent gates passed.

The final process check found zero Isaac Sim or Kit processes. The RTX 5080 was idle at 0 percent utilization, about 2.7 GB used, about 13.2 GB free, and 44 C after the final batch.

### Files added or materially changed in the hardening pass

- `isaac_sim/cell_runner.py`: hardening scenarios, simulator recovery, alignment corrections, and stronger gates
- `isaac_sim/adapter.py`: constraint frame fix and camera annotation cleanup
- `isaac_sim/stage_builder.py`: camera aperture and PhysX angular velocity unit fixes
- `isaac_sim/run_cell.py`: scenario profile and project-relative output root
- `tools/audit_artifacts.py`: independent stage, media, trace, PLC, metrics, and replay audit
- `tests/test_artifact_audit.py`: focused artifact and scenario schedule tests
- `validate_setup.ps1`, `run_solution_a.ps1`, `run_solution_b.ps1`, and `run_tests.ps1`: machine-metrics validation
- `run_hardening.ps1`: clean, sequential, resumable five-seed launcher
- `README.md`, `isaac_sim/README.md`, `SYSTEM_DESIGN.md`, `BUILD_STATUS.md`, `tickets/README.md`, `tickets/T014.md`, and this report: durable current instructions and evidence

Historical screening results were preserved. The original failed hardening attempt was also preserved as evidence.

### Remaining blockers and exact next ticket

The simulator milestone is runnable and reproducible under its stated assumptions. It is not physically calibrated and does not establish OEM fidelity, food safety, real-cell safety, physical accuracy, or production readiness.

The exact next ticket remains T015, physical calibration and OEM asset replacement. It cannot proceed truthfully without selected OEM assets, real camera calibration and recordings, conveyor and encoder measurements, meat material and grip trials, cutter PLC timing, and physical safety engineering evidence.

## Learned YOLO26 pass: 2026-08-26

### Outcome

The optional learned-vision path is now implemented and exercised inside Isaac Sim. The official Ultralytics YOLO26 nano segmentation checkpoint was installed project-locally, fine-tuned on Isaac-rendered data, validated, and connected to the existing stamped observation interface. Both Solution A and Solution B passed complete four-cycle suites with YOLO masks as the live primary detection source.

T001 through T014 remain done. T015 remains blocked on OEM selections and physical data. Synthetic YOLO training does not remove that blocker.

### Exact commands

```powershell
.\setup_yolo.ps1
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\generate_yolo_dataset.py --samples 240 --seed 2601 --output results\yolo\dataset_v2 --headless
C:\Users\jainl\is6\Scripts\python.exe tools\train_yolo26.py --dataset results\yolo\dataset_v2\dataset.yaml --epochs 30 --seed 2601
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\run_cell.py --solution a --cycles 4 --seed 2601 --vision-model yolo26 --yolo-weights models\yolo26_meat_reference\weights\best.pt --output-root results\yolo\headless_a_v2 --headless
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\run_cell.py --solution b --cycles 4 --seed 2601 --vision-model yolo26 --yolo-weights models\yolo26_meat_reference\weights\best.pt --output-root results\yolo\headless_b_v2 --headless
python -m pytest -q
$pytestRoot = python -c "import pathlib, pytest; print(pathlib.Path(pytest.__file__).resolve().parent.parent)"
$env:PYTHONPATH = "$PWD\third_party\python;$pytestRoot"
C:\Users\jainl\is6\Scripts\python.exe -m pytest tests\test_perception_interface.py -q
```

Project-local one-command entries are now:

```powershell
.\setup_yolo.ps1
.\train_yolo.ps1
.\run_yolo_solution_a.ps1
.\run_yolo_solution_b.ps1
.\run_yolo_tests.ps1
.\run_yolo_demo.ps1
```

### Model and data evidence

- Model family: Ultralytics YOLO26 nano segmentation
- Ultralytics version: 8.4.129
- Official base SHA-256: `361fbfabab285c3237700b6bb91d7ecfa602cd945fffda8dbe1242829b71e73f`
- Trained SHA-256: `cf280497427a8f56fc8ef81e47c32b4a4494435187af0b1916cb03ac09225919`
- Synthetic frames: 240 total, 192 train and 48 validation
- Operating zones: 160 moving-belt views and 80 Solution B buffer views
- Randomized variables: product pose, yaw, color, lighting, height, and robot pose
- Ground-truth use: training-label generation only
- Real meat images: none

Synthetic holdout metrics:

| Metric | Result |
|---|---:|
| Mask precision | 0.8733 |
| Mask recall | 0.8615 |
| Mask mAP50 | 0.9188 |
| Mask mAP50-95 | 0.6923 |
| CPU inference per 640-pixel image | about 25 ms |

`results/yolo/example_prediction.jpg` is a saved held-out prediction. `results/yolo/training_summary.json` is the machine-readable source for model identity and validation metrics.

### Isaac integration results

| Result | Solution A | Solution B |
|---|---:|---:|
| Batch passed | yes | yes |
| Cycles | 4 | 4 |
| Nominal deliveries | 2 of 2 | 2 of 2 |
| Expected failure or recovery cycles | 2 of 2 | 2 of 2 |
| Articulation commands | 5,591 | 6,603 |
| Placement position error p50, m | 0.003226 | 0.003292 |
| Placement position error p95, m | 0.003257 | 0.003320 |
| Placement angle error p95, rad | 0.001016 | 0.000683 |
| Perception latency p95, s | 0.028378 | 0.028378 |
| Replay passes | 4 of 4 | 4 of 4 |
| Unexpected collisions | 0 | 0 |
| Joint-limit violations | 0 | 0 |

Solution A exercised direct delivery, failed grasp, and cutter-unavailable reject. Solution B exercised buffered delivery, rendered buffer reobservation, injected slip correction, contact regrasp, failed grasp, and buffer timeout. RGB, depth, masks, tracking, prediction, articulation control, contact, PLC state, downstream verification, and recovery remained connected to simulator state.

Machine evidence is in `results/yolo/headless_a_v2/isaac_a/metrics.json` and `results/yolo/headless_b_v2/isaac_b/metrics.json`.

### Failures found and fixed

1. The first dataset generator changed a USD attribute on the rigid root instead of the geometry prim. The generator now changes the geometry display color. The original `results/yolo/dataset_v1/failure.json` remains preserved.
2. The first generated frames moved labels but did not synchronize the rigid body before rendering. That invalid training was interrupted. The generator now steps Isaac physics, reads the actual rendered pose, and projects the label from that pose.
3. The first valid dataset covered only the moving belt. The integrated Solution B run detected the belt product but missed the buffer reobservation. The v2 dataset added 80 buffer-zone views and matching robot occlusions. The previously missed frame is now detected at 0.73 confidence.
4. Ultralytics serializes the dedicated single class as `item`. The adapter maps only that class index to the durable `meat_reference` contract.
5. Isaac Sim 6.0.1 bundles TorchVision without CUDA NMS. GPU training saved the checkpoint, then final GPU validation failed. Training now catches only that specific compatibility error and performs final validation and live NMS on CPU. Isaac's installed packages were not changed.
6. Buffer reobservation now writes every detection candidate and captures an RGB and depth failure frame when no valid candidate exists.

### Tests and process state

- Ordinary Python: 77 passed and 1 skipped because ordinary Python has no NumPy
- Isaac Python focused perception interface: 3 passed
- YOLO synthetic validation: passed
- Learned-vision Solution A integrated gates: passed
- Learned-vision Solution B integrated gates: passed
- `.\run_yolo_tests.ps1`: passed model validation plus both complete four-cycle Isaac suites from a clean process state
- `.\run_yolo_demo.ps1`: passed four visible Solution B cycles and the 90-second inspection hold
- Every headless Isaac process closed after its batch

The visible `.\run_yolo_demo.ps1` run showed the full cell in Isaac Sim. It completed two nominal deliveries, failed-grasp recovery, buffer-timeout recovery, slip correction, 6,603 articulation commands, four replay passes, zero unexpected collisions, and zero joint-limit violations. It held the completed window for 90 seconds, validated `results/yolo/visible_demo/isaac_b/metrics.json`, then closed Isaac cleanly.

### Durable files added or changed

- `isaac_sim/yolo_runtime.py`: isolated Ultralytics loading and configuration
- `isaac_sim/yolo_perception.py`: RGB mask, depth pose, noise, and latency adapter
- `isaac_sim/generate_yolo_dataset.py`: Isaac-rendered v2 dataset generation
- `tools/train_yolo26.py`: GPU training, CPU validation, prediction, and model report
- `requirements-yolo.txt`, `setup_yolo.ps1`, and `train_yolo.ps1`: pinned project-local setup and training
- `run_yolo_solution_a.ps1`, `run_yolo_solution_b.ps1`, `run_yolo_tests.ps1`, and `run_yolo_demo.ps1`: one-command learned-vision entry points
- `models/MODEL_CARD.md`: provenance, metrics, intended use, and limits
- `isaac_sim/run_cell.py` and `isaac_sim/cell_runner.py`: learned backend selection and integrated evidence
- `tests/test_perception_interface.py`: focused mask-to-depth observation test
- `README.md`, `isaac_sim/README.md`, `SYSTEM_DESIGN.md`, `BUILD_STATUS.md`, `tickets/README.md`, `tickets/T014.md`, and this report: durable instructions and evidence

### Remaining blocker and next ticket

The learned model is a synthetic reference. It is not validated on real meat, real cameras, real lighting, real conveyor blur, wet friction, OEM equipment, or the physical cutter interface. It does not support claims of physical accuracy, food safety, real-cell safety, OEM fidelity, or production readiness.

The exact next ticket remains T015. It requires selected OEM assets, camera calibration and recordings, conveyor measurements, meat material and grasp trials, cutter I/O captures, and physical safety engineering evidence.

## Recipe integration pass, 2026-08-26

### Scope and commands

The three catalog recipes were connected to the actual Isaac stage, PLC, perception baseline, controller, traces, and metrics. Both architectures were exercised with these commands:

```powershell
.\run_recipe.ps1 -Recipe beef_center_cut_tenderloin -Solution a -Cycles 4 -Seed 311
.\run_recipe.ps1 -Recipe pork_boneless_loin -Solution a -Cycles 4 -Seed 521
.\run_recipe.ps1 -Recipe chicken_breast_fillet -Solution a -Cycles 4 -Seed 411
.\run_recipe.ps1 -Recipe beef_center_cut_tenderloin -Solution b -Cycles 4 -Seed 611
.\run_recipe.ps1 -Recipe pork_boneless_loin -Solution b -Cycles 4 -Seed 621
.\run_recipe.ps1 -Recipe chicken_breast_fillet -Solution b -Cycles 4 -Seed 635
C:\Users\jainl\is6\Scripts\python.exe tools\audit_artifacts.py --root results\recipes --mode recipes --output results\recipes\artifact_audit.json
python -m pytest -q
python -m compileall -q isaac_sim meatcell tests tools
```

### Results

All six batches passed. The 24 cycles produced 12 nominal tray deliveries, 6 expected failed-grasp recoveries, 3 cutter-unavailable rejects, and 3 buffer-timeout recoveries. All 24 replay checks passed. Aggregate perception latency p95 was 32.61 ms. Intercept timing error p95 was 3.83 ms. Successful delivery position error p95 was 54.08 mm, angle error p95 was 0.0375 rad, timing error was 0, and stationary release speed error p95 was 0.00534 m/s. There were zero unexpected collisions and zero joint-limit violations.

Ordinary Python reported 83 passed and 1 skipped because NumPy is not installed there. Isaac Python reported 6 passed for the focused perception interface, including beef, pork, and chicken rendered-color fixtures. Compilation passed, and no Isaac Sim or Kit process remained after the final batch.

The pork Solution B position result is close to the 55 mm simulation gate. This is a valid pass with little margin, not evidence of physical accuracy.

### Failures and fixes

1. Pork initially exceeded the existing gripper opening. The reference gripper was changed to a fixed 175 mm open gap with recipe-aware closure travel and an 8 mm per-pad compliance proxy.
2. Pork's original color threshold segmented only highlights. The species-specific mask was corrected using the actual rendered RGB distribution while rejecting the orange cutter geometry.
3. Grasp closure attempted an unnecessary vertical correction and exceeded the acceleration preflight. Closure now tracks the measured tool height and lateral position while following conveyor speed.
4. Tray verification still assumed a moving feed handoff. It now releases the fixed grasp before opening, settles at zero commanded speed, and verifies a stationary tray handoff.
5. The first chicken B seed did not reach its intended buffer timeout because interception was rejected earlier. The artifact audit exposed the mismatch. Seed 635 was selected and then demonstrated the complete buffer-timeout recovery.
6. The artifact auditor gained a recipe mode. It requires schema version 2 recipe evidence and both solutions for every recipe.

### Assumptions and next work

The products remain rigid rectangular reference proxies with recipe-specific dimensions, mass, color, and metadata. The gripper compliance, friction, forces, tissue response, and tray tolerances are not physically calibrated. The existing YOLO26 checkpoint is not yet a three-recipe model. The next software step is a multi-recipe Isaac dataset and YOLO26 retraining. The next physical ticket remains T015 and requires representative products, selected hardware, measured camera and conveyor data, cutter I/O, and safety engineering.

## Scene 2.0 FANUC build and visual gate, 2026-08-26

The earlier visible demonstration still used the generic Scene 1 robot. That was not the requested robot upgrade. Scene 2.0 now imports the official FANUC `m10_12_14d` description as a FANUC M-10iD/12 simulation reference and builds a new cell around it.

The new stage includes the FANUC arm and pedestal, six revolute joints, specialized compliant gripper reference, guarded conveyor, three recipe-shaped workpieces, overhead RGBD camera and mounting gantry, photoeye, stationary cutter-entry tray, cutter housing, reject bin, PLC attributes, lights, drains, and named frames.

Commands:

```powershell
python tools\build_fanuc_urdf.py
python -m pytest -q tests\test_fanuc_asset.py
.\validate_scene2.ps1
.\run_scene2.ps1
```

The headless Isaac Sim 6.0.1 gate passed. It initialized joints J1 through J6 and executed three controller motion segments over 1,200 fixed physics steps at 240 Hz. The tested motion stayed inside the imported joint limits. There were zero joint-limit violations. The render contained 921,600 nonempty RGB pixels and nonempty depth. The saved cell contained 194 authored `/World` prims, two cameras, six revolute joints, and one articulation root. Its manifest matched after independent save and reload. Exact current motion and sensor values are in `results/scene2/scene2_validation.json`.

Evidence:

- `results/scene2/meatcell_scene2_fanuc.usda`
- `results/scene2/scene2_fanuc_cell.png`
- `results/scene2/scene2_fanuc_robot_closeup.png`
- `results/scene2/scene2_fanuc_cell_depth.npy`
- `results/scene2/scene2_validation.json`

The full YOLO and interception state machine is not yet connected to the FANUC articulation. T016 records that remaining work. The scene and joint-controller gate is complete. The full Scene 2.0 end-to-end milestone is not complete.

## Scene 2.0 ROS 2 and motion boundary gate, 2026-08-26

The FANUC Scene 2.0 articulation and overhead camera now have a tested ROS 2 boundary. Isaac remains responsible for fixed-step physics, rendering, measured joints, contacts, and articulation execution. The planned external MoveIt process will be responsible for collision-aware path planning and trajectory timing.

Commands:

```powershell
python -m py_compile isaac_sim\scene2_ros_bridge.py isaac_sim\scene2_ros_probe.py isaac_sim\run_scene2.py
python -m pytest -q tests\test_scene2_ros_contract.py
.\validate_scene2_ros.ps1
.\run_tests.ps1
```

The focused unit suite reported 6 passed. The complete ordinary-Python suite reported 111 passed and 1 skipped. The skip is the NumPy-dependent perception test in the plain Python interpreter.

The ROS 2 headless Isaac gate passed twice. Each run published 720 `/clock` messages, 180 `/carve/joint_states` messages, 45 rendered RGB images, 45 rendered depth images, and 45 camera calibration messages. The DDS probe received every stream type. RGB payloads contained 921,600 bytes and depth payloads contained 1,228,800 bytes. Isaac rejected one deliberately partial joint command. It accepted one complete J1 through J6 command and applied it through the FANUC articulation controller. The maximum final joint error was 0.000836 rad. The second run produced the same stage hash and identical ROS metrics.

The full entry point did not pass. Solution A passed. Solution B failed both nominal cycles at `buffer_regrasp_contact_failure`. This matches the known Scene 1 recipe-geometry regression and was not caused by the new Scene 2.0 ROS bridge. No Isaac Sim or Kit process remained after the runs.

The external MoveIt gate remains untested. WSL 2 Ubuntu is present, but ROS 2 and MoveIt are not installed there. No system software was installed. The exact next T016 step is the `FollowJointTrajectory` action bridge and FANUC MoveIt configuration in an authorized existing ROS 2 environment. After that, the planner must drive a timed conveyor interception in Scene 2.0 before perception and full task-state migration can be claimed.
