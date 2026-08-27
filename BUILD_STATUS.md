# Build status

## Scene 2.0 FANUC implementation, 2026-08-26

The proposed robot and cell are now present in a new Isaac Sim stage. The implementation imports the official FANUC `m10_12_14d` description as a FANUC M-10iD/12 reference. It retains six revolute joints, official description joint limits, visual meshes, collision meshes, masses, and inertias. The source commit is `fb40c9803a826ba68c7c8e28ba904a25efa7fcd2`.

The new stage contains the FANUC arm, pedestal, specialized compliant gripper reference, guarded conveyor, three pork-loin reference workpieces, camera gantry, overhead RGBD sensor, photoeye, stationary cutter-entry tray, cutter housing, reject bin, PLC attributes, lighting, floor drains, and named coordinate frames. Cell equipment and the gripper remain clearly labeled project reference models.

`validate_scene2.ps1` passed in Isaac Sim 6.0.1. Isaac initialized the FANUC arm and its two-joint compliant gripper, then executed three bounded robot motion segments at 240 Hz. The run reported zero robot joint-limit violations, nonempty 1280 by 720 RGB and depth, 200 authored cell prims, two cameras, six revolute robot joints, two prismatic jaw joints, and a matching save and reload manifest.

The Scene 2.0 compliant gripper gate also passed twice with identical stage hashes and measurements. Both articulated jaws contacted the 2.75 kg pork reference. Measured elastic deflection was 10.03 mm and 9.99 mm. The force proxy was 62.71 N and 62.41 N, below the 70 N drive limit. Raw PhysX contact estimates were 48.04 N and 56.84 N. One-second hold slip was zero in the repeated run. Deliberate opening produced 1.383 m of workpiece displacement and both jaws recovered within 4 micrometers of open. No fixed grasp constraint was used during the load check. Evidence is in `results/scene2_compliance_v10/scene2_validation.json` and `results/scene2_compliance_v11/scene2_validation.json`.

`validate_scene2_ros.ps1` passed again after the gripper joints were added. It used the ROS 2 Humble libraries bundled with Isaac Sim and real in-process DDS endpoints. The bridge publishes only J1 through J6 on the robot joint contract and keeps jaw state inside the separate gripper contract. The probe received clock, robot joint state, RGB, depth, and camera calibration. Isaac rejected one partial command and accepted one complete six-joint command. The accepted command moved the FANUC articulation through its controller with a maximum final error of 0.000679 rad. Evidence is in `results/scene2_compliance_ros/scene2_validation.json`.

The visible launcher is `run_scene2.ps1`. It opens the same tested stage and holds the Isaac Sim window for inspection. `validate_compliant_gripper.ps1` is the focused one-command physical mechanism gate. The full YOLO, interception, and delivery pipeline still uses the existing generic Scene 1 articulation. The external MoveIt process is not installed or tested. Connecting those functions to the FANUC Scene 2.0 articulation is T016 and remains in progress.

The current complete `run_tests.ps1` entry point is green. The fresh evidence root is `results/full_suite/20260826_205915468`. Ordinary Python reported 127 passed and 1 skipped. The skip is the NumPy-dependent perception test in the plain interpreter. The complete run produced 8 cycles, 4 nominal deliveries, 4 expected recovery cycles, 8 deterministic replay passes, zero unexpected collisions, and zero joint-limit violations. The same command also passed the Scene 2.0 ROS and compliant-gripper gate.

The Solution B buffer regrasp regression is fixed. The controller now preserves the product pose measured from the rendered buffer RGBD observation. The stationary regrasp closure uses the actual central width of the recipe mesh instead of its maximum width envelope. The moving interception closure remains unchanged because it needs extra capture tolerance. The regrasp trace now records the measured product pose, target pose, robot state, finger poses, and PhysX contacts. The 8 mm per-pad compliance value remains an uncalibrated proxy.

## Report language review, 2026-08-26

Both HTML reports have been rewritten in a direct engineering voice. The openings now state the current result, the Scene 2.0 robot decision, the known limitations, and the next action. Slogan-like headings, vague presentation language, and several long list sentences were removed. Technical terms, exact metrics, failed tests, and simulation limits were kept.

`WRITING_STYLE_RESEARCH.md` records the research and the project writing rules. `tools/audit_report_language.py` is a narrow style lint, not an AI detector. The two reports contain no configured canned phrases, no prohibited dash characters, no encoding replacement characters, and no prose sentence over 25 words. The full ordinary-Python suite reports 102 passed and 1 skipped because NumPy is not installed in that interpreter.

Fresh desktop and mobile renders are under `results/report_validation/human_language`. They were rendered with isolated Playwright Chromium and inspected for layout problems. No Isaac Sim code, configuration, or metrics changed in this pass, so the simulator was not rerun.

## Scene 2.0 design gate, 2026-08-26

The next implementation gate is the production-oriented scene rebuild documented in `SCENE_DESIGN_V2.md`. The proposed baseline is a FANUC M-10iD/12 Food Grade six-axis robot, imported from the official FANUC description package and clearly labeled as a simulation reference. The current generic Cartesian robot remains in place until the new articulation passes joint, reach, collision, controller, save, reload, and deterministic replay tests.

`SCENE_DESIGN_REPORT.html` now presents the decision as a responsive engineering report. It includes a scaled interactive cell layout, robot comparison, payload budget, sensor cross-section, communication architecture, I/O contracts, timing chart, control state machine, fidelity matrix, current Isaac evidence, assumptions register, and staged build gates. `open_scene_report.ps1` validates and opens it.

The new scene baseline uses a stationary cutter-entry tray, a fixed overhead RGB and depth camera pair, conveyor encoder, photoeye, wrist force and torque reference, bilateral jaw sensing, and PLC-style machine I/O. The current 175 mm gripper opening is known to be insufficient for the 200 mm pork width envelope. The replacement reference gripper therefore requires at least 240 mm clear opening.

No Scene 2.0 implementation milestone is complete yet. This section records the selected direction and the gates that must be passed before YOLO training continues.

The latest Scene 1 regression is green. Solution A and Solution B pass with the recipe-shaped workpieces. The generic Cartesian arm and narrow gripper remain development references. They are not the selected final cell hardware.

## Recorded demonstration and technical report, 2026-08-26

The integrated runner can now record the actual rendered overhead RGB stream into H.264 while the fixed-step Isaac simulation runs. `record_yolo_demo.ps1` completed a four-cycle YOLO26 Solution B suite and wrote a 31.42 second, 640 by 480, 12 FPS recording with 377 frames. The recording gate passed with 6,603 articulation commands, eight learned observations, two nominal deliveries, failed-grasp recovery, buffer-timeout recovery, four deterministic replay passes, zero unexpected collisions, and zero joint-limit violations.

`TECHNICAL_REPORT.html` documents the complete implementation with the embedded recording, architecture and communication visuals, component boundaries, inputs and outputs, message contracts, state machines, PLC I/O, YOLO26 pipeline, metrics, failure recovery, source map, commands, assumptions, and remaining physical blockers.

## Current stage

The Scene 1 integrated Isaac Sim reference milestone is complete under documented simulation assumptions. The Scene 2.0 FANUC stage, ROS boundary, controller, sensors, and compliant-gripper gate are complete. Full perception, interception, transport, and delivery with the FANUC articulation remain T016 work.

## 2026-08-26 recipe integration status

The product catalog is now connected to the integrated Isaac runner. Beef center-cut tenderloin, pork boneless loin, and chicken breast fillet each construct a recipe-specific saved USD stage and run through both Solution A and Solution B. The stage, PLC recipe, rendered-perception adapter, event traces, and schema version 2 metrics all carry the selected recipe.

Six four-cycle headless batches passed, for 24 simulator cycles. Each recipe and solution completed two nominal deliveries and its two expected recovery cases. The aggregate recipe audit reports 12 nominal successes, 6 failed-grasp recoveries, 3 cutter-unavailable rejects, 3 buffer-timeout recoveries, 24 of 24 deterministic replay passes, zero unexpected collisions, and zero joint-limit violations.

The gripper reference now has a fixed 175 mm open gap and recipe-aware closure targets. The closure uses an uncalibrated 8 mm compliance deflection per pad. Delivery is a stationary release into the cutter-entry tray. Cutter feed speed represents motion owned by the downstream cutter after acceptance, not robot release velocity.

Machine-readable evidence is in `results/recipes/artifact_audit.json` and the six metric files below `results/recipes`. This evidence uses the rendered color and depth baseline. The existing YOLO26 model was trained on the earlier generic workpiece and has not yet been retrained or validated across all three product recipes.

## Runtime evidence

- Isaac Sim 6.0.1 compatibility checker passed on the local RTX 5080 workstation.
- Headless startup passed and all simulator processes closed after each run.
- The 240 Hz fixed-step clock advanced exactly 240 domain steps in one simulated second.
- USD save and independent reload signatures matched.
- The actual six-joint Isaac articulation responded to controller targets.
- The overhead camera published rendered 640 by 480 RGB and depth.
- The rendered perception interface produced segmentation observations without using ground truth as its primary output.
- Solution A passed its four-cycle seeded suite with two nominal deliveries and two expected recovery paths.
- Solution B passed its four-cycle seeded suite with two nominal buffered deliveries and two expected recovery paths.
- Both integrated suites reported zero collisions and zero joint-limit violations.
- All four replay checks passed for each solution.

Machine-readable evidence is in `results/setup_validation.json`, `results/isaac_a/metrics.json`, and `results/isaac_b/metrics.json`.

## 2026-08-26 hardening status

The documented clean setup and complete suite passed again after the hardening fixes. The current ordinary-Python suite reports 77 passed and 1 skipped. Setup validation reports 101 stage prims, exact 240-step fixed-clock behavior, rendered 640 by 480 RGB and depth, articulation response, perception output, and a matching save and reload signature.

The bounded hardening matrix used seeds 7, 31, 101, 509, and 1001. Each solution ran six simulator cycles per seed. All 10 batches passed, for 60 cycles total. The matrix produced:

- 20 successful nominal deliveries
- 10 expected failed-grasp paths
- 5 expected cutter-unavailable paths
- 5 expected buffer-timeout paths
- 10 expected emergency-stop paths
- 10 expected stale-observation paths
- 60 of 60 deterministic replay passes
- zero unexpected collisions and zero joint-limit violations

The independent artifact audit passed for all saved stages, RGB images, depth arrays, traces, PLC transitions, controller records, scenario outcomes, and metrics. `results/hardening/summary.json` is the machine-readable source of truth for this matrix.

No Isaac Sim or Kit process remained after the final batch. The hardening launcher enforces a clean start, runs batches sequentially, checks machine metrics even if the Isaac wrapper masks an exit status, closes batch-owned orphan processes, supports verified resume, and preserves retry logs.

## 2026-08-26 YOLO26 learned-vision status

The official YOLO26 nano segmentation base is installed project-locally and fine-tuned on 240 actual Isaac-rendered images. The v2 dataset covers the moving belt and the Solution B buffer with robot-pose, object-pose, color, and lighting randomization. No real meat image was used.

The synthetic validation set passed with mask precision 0.8733, mask recall 0.8615, mask mAP50 0.9188, and mask mAP50-95 0.6923. The trained checkpoint SHA-256 is `cf280497427a8f56fc8ef81e47c32b4a4494435187af0b1916cb03ac09225919`.

Learned-vision Solution A and Solution B each passed four seeded cycles in Isaac Sim. Each run completed two nominal deliveries and its two expected recovery cases. Solution A issued 5,591 articulation commands. Solution B issued 6,603. Both reported zero unexpected collisions, zero joint-limit violations, and four of four deterministic replay passes.

Machine evidence is in `results/yolo/training_summary.json`, `results/yolo/headless_a_v2/isaac_a/metrics.json`, and `results/yolo/headless_b_v2/isaac_b/metrics.json`.

## Implementation scope

The reference cell includes conveyor physics, moving workpieces, a generic articulation, a compliant gripper proxy, camera mounts, RGB and depth sensors, named calibration frames, guards, reject handling, cutter or feed reference geometry, Solution B buffer geometry, and simulated PLC state.

The complete simulator-driven state sequence covers observation, acquisition, tracking, prediction, reservation, approach, timed interception, contact confirmation, lift and stabilization, downstream alignment, placement or feed, verification, retract, reject, emergency stop, stale-observation rejection, and recovery.

## Truthful limits

This is a reproducible vertical slice, not a physical validation. The robot, gripper, meat, buffer, and cutter are abstract references. They are not OEM accurate. Rigid-body meat, the fixed grasp constraint, force proxy, friction, latency, lighting, and cutter handshake are simulation assumptions. Food safety, real-cell safety, physical accuracy, and production readiness remain unvalidated.

## Next action

T014 is complete. T016 is the exact next software ticket and remains in progress. Its next gate is the external MoveIt `FollowJointTrajectory` path and collision-aware FANUC interception. T015 remains blocked on selected assets and real camera, conveyor, cutter, gripper, and meat trial data. Accuracy optimization against real data is intentionally deferred.

## Final full-suite hardening, 2026-08-26

The complete timestamped suite passed at `results/full_suite/20260826_205915468`. Solution A and Solution B each completed two nominal deliveries plus their expected failed-grasp and downstream-unavailable paths. All eight cycle replays matched. The independent artifact audit found eight complete traces, two nonempty saved stages, two RGB captures, two depth arrays, zero unexpected collisions, and zero joint-limit violations.

The moving grasp now uses 25 percent jaw pre-shaping, a 125 ms belt-speed-matched contact settle, measured starting joint velocities, and an upstream 1.37 to 1.49 m intercept window. These values keep the jaw and conveyor-axis trajectories inside the stated acceleration limits. Cutter alignment may project a TCP request onto the validated envelope only when the projection is no more than half the 55 mm product-placement tolerance. Larger requests still fail.

The Solution B stationary tray and target moved 50 mm toward the overhead camera centre. Buffer detections require at least 0.10 confidence and 0.10 visible fraction, remain bounded to the calibrated buffer zone, and are associated by distance to `buffer_frame`. The buffer regrasp includes a 150 ms compliant-drive settle and still requires recent bilateral PhysX contact before the fixed transport constraint is created.

Fresh Solution A position error p95 was 47.34 mm. Fresh Solution B position error p95 was 49.90 mm. Both used a 55 mm simulation gate. These margins are simulation results, not physical accuracy claims.
