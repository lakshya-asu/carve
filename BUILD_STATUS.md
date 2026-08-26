# Build status

## Scene 2.0 FANUC implementation, 2026-08-26

The proposed robot and cell are now present in a new Isaac Sim stage. The implementation imports the official FANUC `m10_12_14d` description as a FANUC M-10iD/12 reference. It retains six revolute joints, official description joint limits, visual meshes, collision meshes, masses, and inertias. The source commit is `fb40c9803a826ba68c7c8e28ba904a25efa7fcd2`.

The new stage contains the FANUC arm, pedestal, specialized compliant gripper reference, guarded conveyor, three pork-loin reference workpieces, camera gantry, overhead RGBD sensor, photoeye, stationary cutter-entry tray, cutter housing, reject bin, PLC attributes, lighting, floor drains, and named coordinate frames. Cell equipment and the gripper remain clearly labeled project reference models.

`validate_scene2.ps1` passed in Isaac Sim 6.0.1. Isaac initialized the six-axis articulation and executed three bounded controller motion segments at 240 Hz. The run reported zero joint-limit violations, nonempty 1280 by 720 RGB and depth, 194 authored cell prims, two cameras, six revolute joints, and a matching save and reload manifest. Evidence is in `results/scene2/scene2_validation.json`.

`validate_scene2_ros.ps1` also passed twice. It used the ROS 2 Humble libraries bundled with Isaac Sim and real in-process DDS endpoints. Each run published 720 fixed-time clock messages, 180 measured joint states, and 45 sets of RGB, depth, and camera calibration messages. The probe received every stream type. Isaac rejected one partial command and accepted one complete six-joint command. The accepted command moved the FANUC articulation through its controller with a maximum final error of 0.000836 rad. The replay had the same stage hash and identical ROS metrics.

The visible launcher is `run_scene2.ps1`. It opens the same tested stage and holds the Isaac Sim window for inspection. The full YOLO, interception, contact grasp, and delivery pipeline still uses the existing generic Scene 1 articulation. The external MoveIt process is not installed or tested. Connecting those functions to the FANUC Scene 2.0 articulation is T016 and remains in progress.

The current complete `run_tests.ps1` entry point is not green. Its fresh Solution A batch passed. Its fresh Solution B batch failed both nominal cycles at `buffer_regrasp_contact_failure`, matching the existing known regression. Ordinary Python reported 111 passed and 1 skipped. The skip is the NumPy-dependent perception test in the plain interpreter.

## Report language review, 2026-08-26

Both HTML reports have been rewritten in a direct engineering voice. The openings now state the current result, the Scene 2.0 robot decision, the known limitations, and the next action. Slogan-like headings, vague presentation language, and several long list sentences were removed. Technical terms, exact metrics, failed tests, and simulation limits were kept.

`WRITING_STYLE_RESEARCH.md` records the research and the project writing rules. `tools/audit_report_language.py` is a narrow style lint, not an AI detector. The two reports contain no configured canned phrases, no prohibited dash characters, no encoding replacement characters, and no prose sentence over 25 words. The full ordinary-Python suite reports 102 passed and 1 skipped because NumPy is not installed in that interpreter.

Fresh desktop and mobile renders are under `results/report_validation/human_language`. They were rendered with isolated Playwright Chromium and inspected for layout problems. No Isaac Sim code, configuration, or metrics changed in this pass, so the simulator was not rerun.

## Scene 2.0 design gate, 2026-08-26

The next implementation gate is the production-oriented scene rebuild documented in `SCENE_DESIGN_V2.md`. The proposed baseline is a FANUC M-10iD/12 Food Grade six-axis robot, imported from the official FANUC description package and clearly labeled as a simulation reference. The current generic Cartesian robot remains in place until the new articulation passes joint, reach, collision, controller, save, reload, and deterministic replay tests.

`SCENE_DESIGN_REPORT.html` now presents the decision as a responsive engineering report. It includes a scaled interactive cell layout, robot comparison, payload budget, sensor cross-section, communication architecture, I/O contracts, timing chart, control state machine, fidelity matrix, current Isaac evidence, assumptions register, and staged build gates. `open_scene_report.ps1` validates and opens it.

The new scene baseline uses a stationary cutter-entry tray, a fixed overhead RGB and depth camera pair, conveyor encoder, photoeye, wrist force and torque reference, bilateral jaw sensing, and PLC-style machine I/O. The current 175 mm gripper opening is known to be insufficient for the 200 mm pork width envelope. The replacement reference gripper therefore requires at least 240 mm clear opening.

No Scene 2.0 implementation milestone is complete yet. This section records the selected direction and the gates that must be passed before YOLO training continues.

The latest Scene 1 regression is mixed. Solution A still passes with the recipe-shaped workpieces. Solution B currently fails its two nominal cycles at `buffer_regrasp_contact_failure`. This is current evidence that the generic Cartesian arm, narrow gripper, and old regrasp geometry should not be tuned further as if they were the final cell. Earlier successful Solution B results below are retained as historical screening evidence from the former rectangular workpiece geometry.

## Recorded demonstration and technical report, 2026-08-26

The integrated runner can now record the actual rendered overhead RGB stream into H.264 while the fixed-step Isaac simulation runs. `record_yolo_demo.ps1` completed a four-cycle YOLO26 Solution B suite and wrote a 31.42 second, 640 by 480, 12 FPS recording with 377 frames. The recording gate passed with 6,603 articulation commands, eight learned observations, two nominal deliveries, failed-grasp recovery, buffer-timeout recovery, four deterministic replay passes, zero unexpected collisions, and zero joint-limit violations.

`TECHNICAL_REPORT.html` documents the complete implementation with the embedded recording, architecture and communication visuals, component boundaries, inputs and outputs, message contracts, state machines, PLC I/O, YOLO26 pipeline, metrics, failure recovery, source map, commands, assumptions, and remaining physical blockers.

## Current stage

Integrated Isaac Sim reference milestone complete under documented simulation assumptions.

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

T014 is complete. The exact next ticket is T015, physical calibration and OEM asset replacement. It is blocked on selected assets and real camera, conveyor, cutter, gripper, and meat trial data. Accuracy optimization against real data is intentionally deferred.
