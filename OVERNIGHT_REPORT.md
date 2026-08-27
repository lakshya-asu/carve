# Overnight build report

## Continuous pickup hardening, 2026-08-27

The published presentation recording was withdrawn after review. It was a contact fixture test, not a pickup. The workpiece was moved to the grasp pose after a camera cut, and the tool entered the conveyor envelope. The project page no longer links that recording.

The gripper was resized from a 270 mm opening, 360 mm pad depth, 160 mm pad height, and 500 mm flange reach to a 220 mm opening, 140 mm pad depth, 100 mm pad coverage, and 350 mm flange reach. This is a compact reference tool for the current 200 mm maximum recipe width. Future cuts outside that envelope need a different removable pad set or tool.

Commands run:

```powershell
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\run_scene2.py --headless --output-root results/scene2_compact_gripper
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\probe_scene2_ik.py
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\record_scene2_real_pickup_demo.py --output-root results/scene2_real_pickup_v1 --fps 12
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\record_scene2_real_pickup_demo.py --output-root results/scene2_real_pickup_v2 --fps 12
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\record_scene2_real_pickup_demo.py --output-root results/scene2_real_pickup_v3 --fps 12
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\record_scene2_real_pickup_demo.py --output-root results/scene2_real_pickup_v4 --fps 12
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\record_scene2_real_pickup_demo.py --output-root results/scene2_real_pickup_v5 --fps 12
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\record_scene2_real_pickup_demo.py --output-root results/scene2_real_pickup_v6 --fps 12
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\record_scene2_real_pickup_demo.py --output-root results/scene2_real_pickup_v7 --fps 12
```

The compact mechanism gate passed. The IK probe found reachable top-down pickup poses using the project FANUC URDF and a Lula robot descriptor. Early real-pick runs failed truthfully. V1 rejected a drifted workpiece pose. V2 and V3 rejected conveyor penetration and unexpected contacts. V4 rejected an unreachable lift pose. V5 still detected belt contact during the long overview-to-pregrasp joint interpolation. V6 starts the recording at a verified pregrasp pose and contains only the collision-free vertical pickup sequence.

V7 is the accepted final recording. It passed with 66.2 mm minimum approach clearance, bilateral contact peaks of 56.42 N and 55.99 N, 159.65 mm lift, 0.387 mm maximum relative drift, 23.69 mm release displacement, 5.90 mm maximum one-step product motion, zero unexpected contact pairs, zero product teleports after recording began, and zero joint-limit violations. The video has 161 frames at 1280 by 720 and 12 FPS. The fixed camera keeps the workpiece, gripper, and belt visible through approach, closure, lift, transport, release, and retract. V7 also removes the kinematic reset warning. The PowerShell wrapper returns a failing process exit code when the machine-readable gate fails.

The one-command wrapper was tested in both directions. A valid 12 FPS run passed and printed its evidence path. An intentional 11 FPS run produced `passed: false`, named the invalid frame rate, and returned process exit code 1 from `record_real_pickup.ps1`.

The documented complete entry point passed after the pickup correction:

```powershell
.\run_tests.ps1
```

Fresh complete-suite evidence is `results/full_suite/20260827_020951506`. Ordinary Python reported 137 passed and 1 skipped. The skip is the NumPy-dependent perception test in the plain interpreter. Isaac Python provides NumPy for simulator tests. Solution A and Solution B ran eight total cycles with four nominal successes, four expected recovery outcomes, eight deterministic replay passes, zero unexpected collisions, and zero joint-limit violations. The Scene 2 ROS probe and compact gripper mechanism gate passed in the same command.

The workpiece is held kinematic on the stationary belt until bilateral contact, then becomes dynamic. This is a transparent conveyor fixture approximation. It is not moving interception and is not evidence of real meat handling performance. The exact next ticket remains T016: connect camera perception and prediction to a moving workpiece and execute the same contact pickup on the FANUC articulation.

## Guided gripper correction, 2026-08-27

Historical rejected iteration. The accepted compact-tool pickup evidence is documented above.

The first Scene 2 gripper passed a narrow contact fixture test but looked detached and did not show a workpiece in the presentation recording. The housing and finger transforms were rebuilt as one readable wide parallel-jaw tool. The new reference includes an enclosed drive housing, guide rails, articulated carriages, finger arms, rigid backings, broad rounded soft pads, and a named `grasp_tcp` frame.

Commands run:

```powershell
python -m pytest tests\test_scene2_gripper_model.py tests\test_video_recorder.py tests\test_scene2_camera_options.py -q
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\run_scene2.py --headless --output-root results/scene2_gripper_redesign
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\record_scene2_presentation_demo.py --output-root results/scene2_gripper_demo_final --fps 12
```

The focused Python tests reported 11 passes. The mechanism gate passed with bilateral contact, 0.094 mm hold slip, 1.317 m release displacement, no unexpected contact pair, and no joint-limit violation. The final recorded grasp gate passed with force proxies of 63.91 N and 63.42 N, peak contact estimates of 63.51 N and 64.57 N, 0.17 mm gravity-hold slip, and 1.249 m release displacement. The MP4 contains 201 rendered frames at 1280 by 720 and 12 FPS. Every Isaac process closed after its run.

The workpiece is placed at an offset grasp test pose before closure. This proves the articulated contact, hold, and release mechanism. It does not prove conveyor pickup, YOLO-to-FANUC interception, or downstream delivery. Those functions remain T016.

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

## Scene 2.0 compliant gripper mechanism, 2026-08-26

The FANUC scene now contains a working gripper mechanism, not static display geometry. Two prismatic jaw joints are part of the Isaac articulation. Each jaw has collision pads, contact sensing, finite drive effort, joint travel, velocity limits, and explicit compliance metadata. The clear inner opening is 270 mm, which covers the current 200 mm recipe envelope with margin.

The first load runs exposed two real implementation errors. The product moved before both jaws made contact, and the jaw joint anchors were authored at the flange origin instead of the visible jaw zero poses. After the joint anchors were corrected, the contact trace showed the right pad touching FANUC link J4. The tool had been mounted backwards along the flange axis. The mount orientation and offset were corrected so the jaws extend forward from the wrist.

Final command:

```powershell
.\validate_compliant_gripper.ps1
```

Repeated Isaac evidence:

- Eight articulation joints: FANUC J1 through J6 plus `finger_left` and `finger_right`.
- Bilateral product contact: passed.
- Product mass: 2.75 kg rigid pork-loin reference.
- Jaw targets: -78.88 mm and 78.88 mm.
- Measured jaw positions: -68.85 mm and 68.89 mm.
- Elastic drive deflection: 10.03 mm and 9.99 mm.
- Force proxy: 62.71 N and 62.41 N.
- Configured finite drive limit: 70 N per jaw.
- Raw PhysX contact estimate: 48.04 N and 56.84 N.
- One-second hold slip: zero in the repeated run.
- Deliberate grasp-loss displacement: 1.383 m.
- Open recovery error: below 4 micrometers.
- Unexpected contact pairs in the final gate: zero.
- Stage save and reload manifest: matched.
- Repeat stage hash: identical.
- Repeat compliance measurements: identical.
- Isaac Sim or Kit processes left after the batches: zero.

The ROS bridge was retested after the articulation grew from six to eight joints. The ROS robot contract still exposes only J1 through J6. The gripper remains a separate control and status interface. Live DDS clock, joint state, RGB, depth, and camera calibration passed. One incomplete command was rejected, one complete command was accepted, and maximum final robot joint error was 0.000679 rad.

This is not a final gripper design. The product is rigid. Friction, compliance, raw contact force, pad shape, drainage, cleanability, material suitability, and damage thresholds are not calibrated. The focused result proves that the simulated mechanism actuates, contacts, deflects, holds, loses grasp, and recovers inside Isaac Sim under the stated assumptions.

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

## Final validation and contact hardening, 2026-08-26

### Outcome

The documented complete entry point passed from a clean process state. Fresh evidence is in `results/full_suite/20260826_205915468`. Ordinary Python reported 127 passed and 1 skipped. The skip is the NumPy-dependent perception test in the plain interpreter. Isaac Python supplied NumPy for the simulator gates.

Solution A and Solution B each ran four seeded cycles. Each solution delivered both nominal workpieces and completed its two expected fault paths. All eight replay decisions matched. The independent artifact audit passed. It found zero unexpected collisions, zero joint-limit violations, eight complete traces, two nonempty saved stages, two valid RGB captures, and two valid depth arrays.

The same complete command ran the Scene 2.0 FANUC ROS and compliant-gripper gate. The saved stage contained 200 prims, six revolute robot joints, two prismatic jaw joints, two cameras, and one articulation root. Its save and reload manifests matched. The ROS probe received clock, joint state, RGB, depth, and camera calibration. One partial command was rejected. One complete command moved J1 through J6 with 0.000679 rad maximum final error.

The Scene 2.0 gripper established bilateral Isaac contact on the 2.75 kg pork reference. Elastic jaw deflection was 10.03 mm and 9.99 mm. Force proxies were 62.71 N and 62.41 N against a 70 N limit. Peak contact estimates were 48.04 N and 56.84 N. One-second hold slip was zero. Deliberate release produced 1.383 m displacement. Both jaws recovered to within 2 micrometres of open. This remains an uncalibrated rigid-product and linear-compliance reference.

### Exact commands

```powershell
python -m pytest tests\test_buffer_regrasp_geometry.py -q
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\run_cell.py --solution a --cycles 4 --seed 7 --headless --output-root results/repro_a_settle125_2
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\run_cell.py --solution a --cycles 4 --seed 7 --headless --output-root results/repro_a_settle125_3
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\run_cell.py --solution a --cycles 4 --seed 7 --headless --output-root results/repro_a_settle125_4
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\run_cell.py --solution b --cycles 4 --seed 7 --headless --output-root results/repro_b_final_1
.\run_tests.ps1
python -m compileall -q isaac_sim meatcell tests tools
python tools\audit_report_language.py --fail-on-style
```

### Fresh metrics

| Metric | Solution A | Solution B |
|---|---:|---:|
| Batch passed | yes | yes |
| Cycles | 4 | 4 |
| Nominal deliveries | 2 of 2 | 2 of 2 |
| Expected fault paths | 2 of 2 | 2 of 2 |
| Replay passes | 4 of 4 | 4 of 4 |
| Position error p50, m | 0.046997 | 0.048800 |
| Position error p95, m | 0.047340 | 0.049898 |
| Angle error p95, rad | 0.024225 | 0.053129 |
| Timing error p95, s | 0 | 0 |
| Perception latency p95, s | 0.032333 | 0.032333 |
| Maximum commanded acceleration | 11.885655 | 11.885655 |
| Unexpected collisions | 0 | 0 |
| Joint-limit violations | 0 | 0 |

The combined artifact audit measured intercept timing error p95 of 4.14 ms, placement position error p95 of 49.65 mm, and placement angle error p95 of 0.05087 rad. These are simulation measurements under the current 55 mm and 7 degree gates. They are not physical accuracy claims.

### Failures found and fixed

1. The clean suite found a 0.48 mm TCP request beyond the validated cutter-side workspace. Cutter alignment now uses a bounded workspace projection tied to half of the product-placement tolerance. Larger projections still fail.
2. Repeated contact runs exposed early jaw contact during approach. Moving pre-shape was reduced from 45 percent to 25 percent.
3. The jaw drives sometimes had not finished closing when contact was checked. A 125 ms belt-speed-matched settle now uses measured starting joint velocities and retains the 8 m/s2 jaw acceleration gate.
4. The added settle initially left too little stopping distance. The intercept window moved upstream to 1.37 to 1.49 m. The existing 300 mm brake then remained inside the 12 m/s2 X-axis limit and TCP envelope.
5. The Solution B tray sat near the overhead image edge. The tray and named target moved 50 mm toward camera centre. Low-quality buffer fragments are rejected before motion.
6. Buffer jaws sometimes reached only one side before regrasp confirmation. A 150 ms stationary compliant-drive settle was added. Recent bilateral PhysX contact remains mandatory.
7. The prior full-suite launcher could audit stale shared results. It now creates a timestamped result root and checks fresh failure and metrics files for A, B, and Scene 2. Historical results remain untouched.

Failed exploratory outputs remain under the `results/repro_a_alignment_*`, `results/repro_a_settle_*`, `results/repro_b_settle_*`, and `results/repro_b_buffer_*` folders. They were not deleted or presented as passes.

### Warnings and process state

Isaac reported its known low-resolution DLSS input warning, a render-variable host-copy performance warning, and an RTX transform-history warning during the Scene 2.0 run. These did not make the RGB or depth outputs empty and were not hidden. The transform-history warning may affect long-exposure motion rendering and remains an open sensor-fidelity item.

No Isaac Sim or Kit process remained after the final command. Batches ran sequentially and headless.

### Changed implementation

- `isaac_sim/cell_runner.py`: hardened moving contact acquisition, bounded cutter alignment, tray perception, buffer contact settle, and measured-velocity continuation
- `isaac_sim/stage_builder.py`: recentered stationary Solution B tray and named frame
- `isaac_sim/scene2_builder.py`: articulated two-jaw compliant-gripper reference with collision, friction, limits, and sensors
- `isaac_sim/run_scene2.py`: compliant load, hold, release, and recovery gate
- `isaac_sim/scene2_ros_bridge.py`: six-axis robot contract separated from jaw joints
- `run_tests.ps1`: timestamped fresh artifact roots and integrated Scene 2.0 gate
- `validate_compliant_gripper.ps1`: focused one-command gripper validation
- `tests/test_buffer_regrasp_geometry.py` and `tests/test_scene2_gripper_model.py`: focused geometry, envelope, and gripper tests
- `README.md`, `SYSTEM_DESIGN.md`, `BUILD_STATUS.md`, `tickets/T016.md`, and this report: durable commands, evidence, assumptions, and blockers

### Remaining blocker and exact next ticket

T016 remains the exact next software ticket. Scene 2.0 still needs collision-aware FANUC inverse kinematics, time-parameterized MoveIt trajectories, camera-to-conveyor calibration, YOLO and tracker connection, moving interception, transport, reorientation, stationary tray delivery, fault recovery, and a recorded full delivery. The external MoveIt runtime is not installed in the available WSL environment, and system installation was outside this run's authorization.

T015 remains blocked on representative products, selected production gripper and cutter hardware, real camera calibration, conveyor measurements, tissue and grip trials, cutter I/O captures, and safety engineering. The project does not claim OEM fidelity, food-safety validation, real-cell safety validation, physical accuracy, or production readiness.

## Visual project page, 2026-08-27

### Outcome

A new visual entry point is available at `PROJECT_PAGE.html`. It presents the project as an engineering system rather than a collection of scripts. It includes actual Isaac Sim segmentation, RGB, depth, full-cell, close robot, and recorded-video artifacts. It also documents the problem, subsystem responsibilities, message flow, state machine, Solution A and B, compliance model, PLC inputs and outputs, metrics, commands, assumptions, and the exact Scene 2 integration gap.

The page deliberately separates two bodies of evidence. Scene 1 is the tested end-to-end pipeline using the generic Cartesian articulation. Scene 2 is the standard-arm foundation using the FANUC M-10iD/12 official-description reference, ROS 2, RGBD, and articulated compliant jaws. T016 still owns the work to place the complete vision, prediction, IK, interception, and delivery sequence on the FANUC arm.

### Changed files

- `PROJECT_PAGE.html`: full visual project narrative and embedded MP4
- `project_page/styles.css`: responsive light and dark engineering layout
- `project_page/app.js`: theme control and command-copy feedback
- `open_project_page.ps1`: one-command local page launcher
- `tests/test_project_page.py`: local reference, required content, video, and language gates
- `README.md` and `BUILD_STATUS.md`: durable entry point and current status

### Validation commands and results

```powershell
python -m pytest tests\test_project_page.py -q
python -m pytest -q
```

The focused project-page tests reported 4 passed. The complete ordinary-Python suite reported 131 passed and 1 skipped in 0.99 seconds. The skip remains the NumPy-dependent perception-interface test in the plain interpreter. The page test confirms that every local `href` and `src` exists, the MP4 is nonempty, required subsystem views are present, and no prohibited dash character appears in the HTML, CSS, or JavaScript.

Direct `file:` navigation through the in-app browser automation interface was blocked by its URL policy. No bypass was attempted. The page was opened as a local Codex file artifact for the user. The repository launcher remains available for normal desktop viewing.

### Evidence used

- YOLO26 output: `results/yolo/example_prediction.jpg`
- RGB and depth: `results/yolo/recorded_demo/isaac_b/media`
- Video and contact sheet: `results/yolo/recorded_demo/isaac_b`
- Standard-arm views and metrics: `results/scene2_compliance_ros`
- Complete-suite evidence: `results/full_suite/20260826_205915468`

No simulator implementation or metric changed in this documentation pass, so Isaac Sim was not rerun. The page reports the latest completed simulator suite without recasting historical data as a new run. No Isaac Sim or Kit process was started.

## Presentation-camera correction, 2026-08-27

The first project-page version mixed the current Scene 2 FANUC cell image with an older overhead Scene 1 video. The overhead camera is appropriate for segmentation and pose estimation, but it gives a poor explanation of the robot task. It also made the page appear to switch robot systems without warning.

Four Scene 2 presentation-camera candidates were rendered in one headless Isaac run. The operator and process-side views were rejected because the yellow rail and transparent guard obscured the robot. The selected view is a virtual 18 mm three-quarter camera at eye `[3.65, -2.20, 2.40]` m looking toward `[0.30, 0.00, 0.86]` m. It sits inside the guard envelope for explanation only. It is not presented as a physically mounted sensor.

The first video run failed its own gate. It wrote 165 frames, but the command generator rebuilt partially specified commands from measured joint state. That created 763 joint-limit violations and unrealistic spikes. The recording was rejected. The fixed generator maintains a continuous eight-joint commanded state and changes only the selected joints inside that state.

The repeated run passed with 3,300 articulation commands, 0 joint-limit violations, 165 frames, 1280 by 720 resolution, 12 FPS, H.264 encoding, and 13.75 seconds of video. The output is `results/scene2_presentation_final/scene2_fanuc_demo.mp4`. The page-ready copy is `assets/project_page/fanuc_presentation.mp4`.

The new recording demonstrates the Scene 2 FANUC articulation and jaw motion. It does not show complete vision-guided product delivery, and both the metrics and project page say so directly. The older Scene 1 video remains linked as the complete YOLO-to-delivery evidence until T016 joins that pipeline to the FANUC arm.

Commands used:

```powershell
.\render_scene2_camera_options.ps1
.\record_scene2_demo.ps1
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate -show_entries format=duration,size -of json results\scene2_presentation_final\scene2_fanuc_demo.mp4
python -m pytest tests\test_video_recorder.py tests\test_scene2_camera_options.py tests\test_project_page.py -q
```

Isaac and Kit closed after both passing render batches. Known render-variable host-copy warnings remained visible. No system software, Windows setting, or unrelated project was changed.

## Final integrated FANUC pipeline and hardening, 2026-08-27

### Outcome

The complete Scene 2 simulator milestone now passes for Solution A and Solution B. The final path starts with actual rendered RGB and metric depth. YOLO26 produces the instance mask through a replaceable vision interface. Depth and calibration produce a planar product pose. Two timestamped observations create a track and velocity estimate. The interception planner predicts a future contact pose and time. Lula inverse kinematics and the Isaac articulation controller drive the FANUC M-10iD/12 reference to the moving product.

The compact gripper closes only after a clear vertical approach. Both PhysX pad contacts must be recent before the grasp is accepted. The product uses a fixed-step kinematic conveyor fixture before capture. After grasp confirmation it becomes a dynamic PhysX rigid body. The program performs zero product pose writes during lift, transport, buffer handling, alignment, and release.

Solution A carries the product directly to `cut_target_frame`, aligns it, releases into the stationary cutter-entry tray, verifies the result, acknowledges the PLC, and retracts. Solution B releases on the centering buffer, renders a new RGBD observation, measures the pose change, corrects the regrasp target, makes new bilateral contact, and feeds the same cutter-entry tray.

The cell USD includes the conveyor, moving workpieces, robot pedestal and arm, compact compliant gripper reference, overhead and buffer camera mounts, sensors, photoeye, buffer, cutter housing, stationary tray, guards, reject bin, PLC attributes, lighting, and named frames. Every integrated run exports the stage, reopens it, and verifies the required prim paths before it can pass.

### Final nominal commands

```powershell
.\validate_setup.ps1
.\run_solution_a.ps1 -Seed 2601 -Scenario nominal -OutputRoot results/scene2_release/solution_a_seed2601_v2
.\run_solution_b.ps1 -Seed 2601 -Scenario nominal -OutputRoot results/scene2_release/solution_b_seed2601
python tools/audit_scene2_integrated.py results/scene2_release/solution_a_seed2601_v2/scene2_integrated_metrics.json --solution a --output results/scene2_release/solution_a_seed2601_v2/integrated_audit.json
python tools/audit_scene2_integrated.py results/scene2_release/solution_b_seed2601/scene2_integrated_metrics.json --solution b --output results/scene2_release/solution_b_seed2601/integrated_audit.json
```

Both PowerShell launchers returned exit code 0. Both integrated audits returned `passed: true`.

### Final nominal metrics

| Metric | Solution A | Solution B |
|---|---:|---:|
| Seed | 2601 | 2601 |
| Rendered video frames | 201 | 353 |
| Video bytes | 1,583,538 | 2,834,395 |
| Articulation-controller commands | 1,999 | 3,521 |
| Cutter position error | 10.31 mm | 20.93 mm |
| Cutter angle error | 0.119 deg | 0.481 deg |
| Delivery timing error | 25.00 ms | 16.67 ms |
| Physical lift | 177.92 mm | 177.96 mm |
| Maximum product-to-TCP distance | 70.09 mm | 79.51 mm |
| Buffer RGBD oracle position error | not applicable | 6.52 mm |
| Product pose writes after grasp | 0 | 0 |
| Unexpected gripper contacts | 0 | 0 |
| Joint-limit violations | 0 | 0 |
| Velocity-limit violations | 0 | 0 |
| Acceleration-limit violations | 0 | 0 |

The Solution A delivery gate is 55 mm position, 7 degrees angle, and 0.10 m/s stationary release speed. Solution B uses the same delivery gate and adds a 50 mm buffer RGBD oracle-error gate. These are simulation thresholds, not measured production capability.

### Seed and scenario hardening

| Solution | Seed | Scenario | Result | Evidence |
|---|---:|---|---|---|
| A | 2601 | nominal | passed | `results/scene2_release/solution_a_seed2601_v2` |
| A | 2602 | nominal | passed | `results/scene2_integrated_a_2602_v4` |
| A | 2603 | nominal | passed | integrated seed matrix output |
| B | 2601 | nominal | passed | `results/scene2_release/solution_b_seed2601` |
| B | 2602 | slip correction | passed | `results/scene2_final/solution_b_slip_seed2602` |
| A | 2610 | failed grasp | passed expected recovery | `results/scene2_recovery/a_failed_grasp_seed2610_v3` |
| A | 2611 | cutter unavailable | passed expected reject | `results/scene2_recovery/a_cutter_unavailable_seed2611` |
| A | 2612 | emergency stop | passed expected safe stop | `results/scene2_recovery/a_emergency_stop_seed2612` |
| A | 2613 | stale observation | passed expected recovery | `results/scene2_recovery/a_stale_observation_seed2613` |
| B | 2614 | buffer timeout | passed expected recovery | `results/scene2_recovery/b_buffer_timeout_seed2614` |

The forced-slip run reported `slip_detected: true`, 17.38 mm cutter position error, 0.453 degree angle error, 25.00 ms timing error, 17.50 mm buffer RGBD oracle error, and zero limit violations.

### YOLO26 model

The final checkpoint is `models/yolo26_meat_reference_buffer_v2/weights/best.pt`. Its SHA-256 is `8baaf05e63a5e654215dbdcf58e106ea62c24e75a54ae9f9c45e8c9c1ed9ceab`. It uses Ultralytics 8.4.129. Synthetic validation reported box precision 0.9440, mask precision 0.96267, box recall 0.79033, mask recall 0.80596, box mAP50 0.89715, mask mAP50 0.91762, box mAP50-95 0.70795, and mask mAP50-95 0.75210.

The training data under `results/yolo/dataset_v4_buffer` is synthetic simulator data. Simulator ground truth generated training labels and remains available as a test oracle. Ground truth is not presented as learned perception and does not control the final demonstration. No real meat accuracy claim is made.

### Failures found and fixed

1. The original gripper was visually oversized and collided with the conveyor. It was replaced by a 220 mm clear-opening compact tool with a 140 mm pad depth and a 350 mm flange-to-grasp-center offset.
2. The earlier recording moved a product into the tool after a camera cut. That evidence was rejected. The final runner keeps the product visible, requires bilateral contact, and records zero product pose writes after grasp.
3. Raw depth initially returned the visible top surface while control expected the rigid-body center. A documented 40 mm surface-to-center correction was added and tested.
4. Solution B initially used oracle pose for slip and regrasp control. It now uses the rendered buffer RGBD observation. Oracle state is retained only for the 50 mm camera-error gate.
5. The secondary authored Isaac camera render product remained stale after dynamic PhysX motion. The working capture binds the active Fabric render camera to the authored buffer-camera pose and intrinsics. The metrics record both paths and the reason. This is a documented Isaac limitation, not hidden ground-truth control.
6. A direct diagonal approach swept the open gripper through conveyor geometry. Motion now uses a clearance pose, vertical descent, open-jaw clearance gate, and finger-only closure while holding the measured arm state.
7. Direct joint interpolation during carry caused the product to peel out of the jaws. Lift, carry, reorientation, alignment, and feed now use Cartesian TCP segments with live bilateral contact age and product-to-TCP retention gates.
8. Solution A timing originally used the plan time before controller settling. The reference now starts after measured convergence.
9. Opening exactly onto hard finger limits created avoidable acceleration spikes. The open target now retains a 2 mm margin inside each limit.
10. Startup exported rigid products in the wrong kinematic order and produced PhysX warnings. Products now reset dynamic first, then receive their kinematic fixture state before export.

### Media and artifact checks

The public page assets contain both MP4 files, posters, contact sheets, YOLO26 segmentation, overhead depth, Solution B buffer RGB, metrics, audits, and saved USDA stages. The A video is 1,583,538 bytes and the B video is 2,834,395 bytes. Both contain more than 100 rendered frames. Audit records confirm matching video and stage hashes.

The integrated audit requires the saved stage to contain the FANUC articulation, two gripper prismatic joints, conveyor, workpieces, overhead and buffer cameras, cutter station, buffer station, reject bin, guards, PLC, and frames. The runner independently reopens the USDA and checks the required paths before writing a passing metric.

### Warnings

Final logs contain no Isaac `[Error]` lines and no PhysX errors. Solution B reports one `rtx.scenedb.plugin` transform-history warning because the simulated history request exceeds the configured transform count. Motion blur is disabled. The camera is static and uses one exposure. The RGB and depth arrays are nonempty, and the 6.52 mm nominal and 17.50 mm forced-slip oracle gates pass. The warning is retained because it may matter if long-exposure motion rendering is introduced later.

The renderer also reports low-resolution DLSS, host-copy performance, and initial render-variable warnings. They are performance or startup warnings, not suppressed validation failures.

### Documentation and launchers

- `run_solution_a.ps1`: complete fail-closed Solution A runner and nominal artifact audit
- `run_solution_b.ps1`: complete fail-closed Solution B runner and nominal or slip artifact audit
- `run_scene2_full.ps1`: setup validation followed by A and B
- `run_tests.ps1`: ordinary unit tests, setup validation, historical regression suites, artifact audit, focused Scene 2 ROS and compliant-gripper gate, and final integrated A and B
- `PROJECT_PAGE.html`: visual overview with both final recordings
- `TECHNICAL_REPORT.html`: detailed architecture, data flow, I/O, controls, evidence, limitations, and commands
- `SYSTEM_DESIGN.md`: durable final architecture
- `BUILD_STATUS.md`: current truth plus historical sections
- `tickets/T016.md`: simulator acceptance complete, external MoveIt item in review

### Remaining blockers and exact next work

The complete Isaac Sim pipeline is runnable under documented assumptions. The exact next software integration task is to commission an external ROS 2 and MoveIt `FollowJointTrajectory` environment against the tested core-message bridge. This requires an existing authorized ROS 2 and MoveIt environment. It was not installed during this build.

T015 remains blocked on real inputs: representative workpieces, real annotated camera data, lens calibration, conveyor timing and encoder logs, measured friction and tissue deformation, production gripper tests, cutter PLC traces, OEM controller limits, hygienic design review, machine safety engineering, and physical commissioning. The project does not claim OEM fidelity, physical accuracy, food-safety validation, real-cell safety validation, or production readiness.

### Final clean suite

The final documented release command was:

```powershell
.\run_tests.ps1
```

It passed from a clean process state. Evidence is `results/full_suite/20260827_045748119`. The command reported 147 Python tests passed, setup validation passed, the focused Scene 2 FANUC ROS and compliant-gripper gate passed, the integrated Solution A audit passed, and the integrated Solution B audit passed. The focused gripper gate measured bilateral product-only contact, 0.898 mm hold slip, 62.03 mm release displacement, zero unexpected contact pairs, and zero joint-limit violations. The ROS probe received clock, joint state, RGB, depth, and camera calibration, rejected a partial command, accepted a full six-joint command, and reached 0.000846 rad maximum joint error.

Two issues were exposed during the clean-suite repetitions and fixed without weakening a gate. The historical abstract-cell buffer-timeout cycle could fail its initial contact check before reaching the intended injected timeout. It now receives one typed, physically simulated matched-velocity contact-settle retry for every non-failed-grasp scenario. The superseded abstract-cell physics matrix is no longer part of the release command because it is not the current FANUC implementation. Its files and historical results remain untouched. The focused Scene 2 compliance fixture was also too close to the cutter guard. It now uses a Lula-verified top-down pose at product center `(0.05, 0.0, 1.10)` m and still fails on any non-product contact.

No Isaac Sim or Kit process remained after the command. The final unit tests and both published integrated artifact audits were run once more after shutdown and all passed.
