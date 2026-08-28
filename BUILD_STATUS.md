# Build status

## C, D, and E validated simulator status, 2026-08-28

Solutions C and D now pass their dependency-ordered complete-cell gates. Solution E has a passing shadow-only vertical slice. Bounded learned contact execution remains blocked on representative physical force, tactile, slip, tissue-damage, and recovery data.

The validated release was published from commit `b62dd35`. GitHub Pages deployment run `33190784537` passed, and the public report, hybrid summary, and C training summary returned HTTP 200. `PRODUCT_RECIPES.md` was not included in the commit.

T017 is done. Its learned grasp-affordance scorer passed six full A and B baseline, learned, and replay cycles. A stronger matched dataset contains 25 separately executed candidates, split into 15 fit and 10 held-out rows. The two held-out seed groups had zero selection regret and zero selected-candidate safety violations, but several outcome heads remain degenerate simulator proxies. T018 is done. Its eight paired disturbance comparisons improved mean intercept position error by 20.016 mm, with six of eight positive pairs and both frozen replay gates passing. T019 remains blocked for execution, but its five-run integrated shadow matrix passed with zero learned commands and a fail-closed emergency-stop proposal.

Fresh evidence is under `results/solution_c/matched_training/20260828_verified_v2`, `results/solution_c/comparison/20260827_deterministic`, `results/solution_d/comparison/20260827_recovery`, `results/solution_e/comparison/20260828_shadow_v1`, and `results/hybrid_comparison/20260828_final_clean`. The final hybrid matrix passed all eight required A/B S0 through S3 cases. S4 is explicitly not run because E execution is blocked. The final ordinary suite and documented release gate passed 226 tests at `results/full_suite/20260828_122846985`.

The comparison plan treats A and B as cell-flow choices and C, D, and E as control capabilities. It defines deterministic, C-only, D-only, C-plus-D, and C-plus-D-plus-E stacks. In the final matched pose-disturbance seed, C preserved delivery but did not improve interception. D improved intercept position by 11.230 mm for A and 11.232 mm for B. C plus D improved it by 11.261 mm for A and 11.239 mm for B. The recommended hybrid retains YOLO26, geometric safety filters, deterministic motion and PLC supervision, learned grasp ranking, and bounded reactive correction. E remains outside execution until its physical-data gate is met.

## Solution map, learning research, and report revision, 2026-08-27

At this 2026-08-27 checkpoint, the project page opened with a five-route branch diagram and treated C, D, and E as research proposals. The 2026-08-28 status above supersedes that implementation state.

Three durable documents were added. `END_TO_END_CHAIN.md` defines every stage, input, output, handoff, check, and recovery boundary. `DECISIONS_AND_TESTS.md` records the main design decisions, why they were made, what was built, and the measured A/B evidence. `GENERALIZED_SOLUTION_RESEARCH.md` compares the current deterministic routes with three learning-based extensions and cites the primary or official sources used.

The recovery evidence videos now use two wide columns on desktop and one column on narrow screens. This replaces the compressed four-video row while retaining all four fault cases. The Pages workflow includes the three new documents.

`DEMO_COMMANDS.md` initially kept the visible Scene 2 command, final A and B runs, speed and orientation matrix, recovery scenarios, and full regression command in one copy-ready place. The 2026-08-28 update adds C, D, and E shadow launchers.

The complete ordinary Python suite passed 188 tests after these changes.

GitHub Pages run `33124349285` passed. The deployed recovery section was reviewed at a 1280-pixel desktop viewport and a 390 by 844 narrow viewport. Desktop recovery videos rendered at about 597 pixels wide in two columns. Narrow recovery videos rendered at 347 pixels wide in one column. Neither viewport had horizontal overflow.

The private Synphony Cue pack now includes `CARVE-PROJECT-BRIEF.md`. It contains short and long project explanations, the exact method chain, measured results, likely technical questions, claim boundaries, and a one-line message for Neil. Cue was opened and left ready. This private interview material is not part of the public repository.

## ROS 2, MoveIt, responsive report, and Pages, 2026-08-27

The detailed report now clips page overflow, lets every image, video, SVG, table, code block, and grid shrink to the viewport, and converts wide tables to labeled mobile rows. The focused responsive regression passes. Recipe images were moved into the published asset tree so the public report has no ignored result-file dependencies.

The standard `FollowJointTrajectory` action adapter is implemented over the existing Isaac simulation-clock sampler. It validates measured start, path, goal, and goal-time tolerances and supports cancellation. The `ros2_ws` workspace adds the FANUC model and SRDF, KDL, OMPL RRTConnect, conservative limits, fixed cell collision objects, MoveIt controller mapping, launch file, and timed pose client. Twenty focused ROS and MoveIt contract tests pass.

The complete `run_tests.ps1` gate passed with 180 Python tests. Fresh evidence is `results/full_suite/20260827_133350136`. The headless ROS gate accepted and completed one standard JointTrajectory with 0.000842 rad final error. Solution A delivered at 10.84 mm position error and 37.50 ms timing error. Solution B delivered at 21.56 mm position error and 8.33 ms timing error, with 6.00 mm buffer sensor-to-oracle error. Both reported zero joint, velocity, or acceleration violations. No Isaac or Kit process remained after the suite.

The live MoveIt build was attempted with `validate_moveit.ps1`. It stopped before building because the existing WSL environment has no ROS 2 Humble installation or colcon. The Isaac bundled ROS library also lacks `control_msgs` and MoveIt. No package was installed. The existing JointTrajectory DDS path remains the executed ROS evidence. Live MoveIt execution remains the exact external gate.

The GitHub Pages workflow publishes `TECHNICAL_REPORT.html` as the site index with all report media. Deployment run `33099467297` passed. The public report and a sample MP4 both returned HTTP 200. The repository homepage and README point to `https://lakshya-asu.github.io/carve/`.

## Technical report redesign, 2026-08-27

`TECHNICAL_REPORT.html` now uses a single graphite and muted-amber theme with square geometry. The prior rounded cards, colored side-border warnings, top-border metric cards, blue palette, gradients, and glows were removed. The communication section is now a closed-loop physical and data-flow SVG. The workpiece cycle, perception transformation, speed envelope, motion feedback, cutter boundary, and PLC handshake each use a purpose-built visualization. The report embeds 13 simulator recordings.

`REPORT_DESIGN_STANDARD.md` records the durable report rules and research basis. `tests/test_technical_report.py` prevents the rejected visual patterns from returning and checks diagram IDs, headings, local media, evidence sections, research links, and the design-standard link. The dependency-enabled Python run passed 165 tests. The language audit reports a seven-word median sentence and no sentence over 25 words. In-app visual automation could not open the local `file:` URL because of browser security policy, so the remaining visual confirmation is a manual refresh of the existing local report tab.

## Variable-speed and orientation pass, 2026-08-27

The current Scene 2 implementation has now passed a five-case Solution A matrix from 0.06 to 0.22 m/s with lateral starts from -60 to 50 mm and yaw from -72 to 68 degrees. The classifier produced longitudinal, diagonal-left, diagonal-right, and transverse grasp classes. All five cases used rendered RGBD, YOLO26 proposals, calibrated conveyor-volume filtering, a mask-interior grasp, timed articulation control, bilateral PhysX contact, dynamic lift, cutter-frame alignment, tray release, and verification. Placement error was 10.4 to 19.8 mm and intercept timing error was 4.4 to 18.3 ms. Every case recorded zero joint, velocity, and acceleration violations.

Solution B also passed at 0.16 m/s and 28 degrees with rendered buffer re-observation and forced slip correction. Its placement error was 20.7 mm. Fresh failed-grasp, cutter-unavailable, stale-observation, and emergency-stop cases reached their expected recovery states without reporting delivery.

The geometric grasp selector is version `mask_pca_clearance_v2`. It fixes the unstable first-pixel choice on broad clearance plateaus by choosing the most central point among near-maximum-clearance candidates. Delivery motion compensates for the resulting product-relative grasp offset. YOLO remains the proposal source. A calibrated product-height filter removes robot-geometry masks without using the simulator product pose. The 68 degree case exposed low YOLO confidence at 0.0156, so transverse-angle real and synthetic retraining remains a priority.

The ROS bridge now accepts standard JointTrajectory messages. The live `FollowJointTrajectory` action and external MoveIt planner remain untested because the required packages are not installed. This is simulation evidence only.

The final clean suite is `results/full_suite/20260827_114303264`. It passed 161 Python tests, setup, stage reload, compliant-gripper, ROS sensor, direct command, standard JointTrajectory, Solution A, Solution B, and artifact-audit gates. The one-command speed matrix also passed at `results/speed_pose_matrix/release_20260827`. No Isaac or Kit process remained after either command.

## Final integrated FANUC Scene 2 gate, 2026-08-27

The complete simulator vertical slice now runs on the FANUC M-10iD/12 official-description reference articulation in Scene 2. Solution A and Solution B both passed from rendered RGBD and YOLO26 perception through tracking, prediction, timed moving-conveyor interception, bilateral PhysX contact, dynamic rigid-body lift, Cartesian transport, reorientation, `cut_target_frame` alignment, stationary cutter-entry tray release, verification, PLC acknowledgment, retract, and trace audit.

The final Solution A release evidence is `results/scene2_release/solution_a_seed2601_v2`. It passed with 201 rendered frames, 1,999 articulation-controller commands, 10.31 mm cutter position error, 0.119 degree angle error, 25.00 ms delivery timing error, 177.92 mm physical lift, 70.09 mm maximum product-to-TCP distance, zero unexpected gripper contacts, and zero joint, velocity, or acceleration violations.

The final Solution B release evidence is `results/scene2_release/solution_b_seed2601`. It passed with 353 rendered frames, 3,521 articulation-controller commands, 20.93 mm cutter position error, 0.481 degree angle error, 16.67 ms delivery timing error, 6.52 mm buffer RGBD oracle position error, 177.96 mm physical lift, 79.51 mm maximum product-to-TCP distance, zero unexpected gripper contacts, and zero joint, velocity, or acceleration violations.

Solution A also passed seeds 2602 and 2603. The integrated recovery runs passed failed grasp, cutter unavailable, emergency stop, stale observation, Solution B buffer timeout, and forced slip correction. Workpiece control uses a fixed-step conveyor fixture before bilateral contact. After grasp confirmation the product is a dynamic PhysX body and the program performs zero product pose writes.

The exported USDA files contain the conveyor, moving workpiece, FANUC articulation, compact compliant gripper reference, overhead and buffer cameras, camera mounts, cutter station, stationary tray, centering buffer, guards, reject bin, PLC attributes, and named frames. Each final run reopens the saved stage and verifies required prims before it can pass. The fail-closed audit also checks video and stage hashes, sensor output, YOLO identity, track count, controller commands, limits, contact, lift, retention, state order, delivery tolerance, and the terminal event trace.

The final page-ready videos, contact sheets, RGBD views, metrics, audits, and USDA stages are under `assets/project_page`. `PROJECT_PAGE.html` is the visual overview and `TECHNICAL_REPORT.html` is the detailed implementation report.

The external ROS 2 and MoveIt `FollowJointTrajectory` process was not installed or commissioned. The final integrated runner uses Isaac Sim Lula inverse kinematics and the real Isaac articulation controller. External MoveIt execution remains a review item in T016, not a claimed result. T015 remains blocked on real camera, conveyor, product, gripper, cutter, OEM controller, hygienic design, and safety data.

The final `run_tests.ps1` command passed from a clean process state. Evidence is `results/full_suite/20260827_045748119`. It reported 147 Python tests passed, setup validation passed, the focused Scene 2 ROS and compliant-gripper gate passed, and both final integrated artifact audits passed. No Isaac Sim or Kit process remained afterward.

## Continuous pickup correction, 2026-08-27

The previous page video is rejected as pickup evidence. It moved a test workpiece to the grasp pose after a camera cut and allowed the oversized pads to intersect the conveyor. The file remains only as historical screening evidence. It is no longer linked or presented on the project page.

The Scene 2 reference tool is now compact. Its clear opening is 220 mm, pad depth is 140 mm, pad coverage is 100 mm, and the grasp center is 350 mm from the flange. The 220 mm opening covers the current 200 mm maximum recipe width with 20 mm total clearance. Larger future cuts require another removable pad set or another tool. The project no longer uses one oversized jaw geometry for every possible product.

`record_real_pickup.ps1` now runs a continuous stationary-belt pickup proof. Lula inverse kinematics generates pregrasp, grasp, lift, transport, release, and retract poses for the FANUC articulation. The workpiece is visible before the approach. It stays kinematic on the stationary belt until both pad contacts are confirmed, then becomes dynamic for the lift, transport, and release. No product pose is set after recording starts.

The passing run is `results/scene2_real_pickup_v7`. It recorded 161 rendered frames over 13.42 seconds and sent 3,312 articulation commands at a 240 Hz fixed physics step. Minimum pad clearance above the belt was 66.2 mm. Bilateral contact peaks were 56.42 N and 55.99 N. The same rigid body lifted 159.65 mm with 0.387 mm maximum tool-relative drift. Release displacement was 23.69 mm. Maximum one-step product motion was 5.90 mm. There were zero unexpected contact pairs, zero workpiece teleports, and zero joint-limit violations. The `record_real_pickup.ps1` wrapper passed on a valid run and returned exit code 1 for an intentional invalid-frame-rate probe.

The complete `run_tests.ps1` regression passed after this correction. Fresh evidence is `results/full_suite/20260827_020951506`. Ordinary Python reported 137 passed and 1 skipped. Solution A and Solution B completed eight cycles with four nominal successes, four expected recovery outcomes, eight deterministic replay passes, zero unexpected collisions, and zero joint-limit violations. The Scene 2 ROS probe and compact gripper gate also passed.

This proves a stationary-belt physics pickup. It does not prove moving conveyor interception, YOLO-driven FANUC control, cutter delivery, or physical gripping performance. Those items remain in T016.

## Guided gripper redesign, 2026-08-27

Historical rejected iteration. The current correction and accepted evidence are documented above.

The previous Scene 2 tool looked like a detached blue cross and its presentation video only moved empty jaws. The static housing used a rotated transform while the moving fingers were separate flange children. The mechanism test also inserted a workpiece at the tool center without showing it in the recording.

At this point the Scene 2 tool was a coherent wide parallel-jaw reference. It had a wrist adapter, enclosed linear-drive housing, two guide rails, two articulated carriages, slim finger arms, rigid pad backings, and broad rounded soft-pad collision surfaces. Its open inner gap was 270 mm. This geometry was later rejected as oversized. The saved stage included a named `grasp_tcp` frame. It was still a project reference, not a selected or validated food-grade gripper.

The fresh Isaac Sim mechanism run under `results/scene2_gripper_redesign` passed. Both jaw contact sensors detected the 2.75 kg pork reference. Hold slip was 0.094 mm. Release displacement was 1.317 m. The run reported no unexpected contact pair and no joint-limit violation.

The replacement recording under `results/scene2_gripper_demo_final` also passed. It contains 201 rendered frames over 16.75 seconds and 4,020 articulation-controller commands. Both sensors detected the offset workpiece. The force proxies were 63.91 N and 63.42 N. Gravity-hold slip was 0.17 mm. Opening the jaws produced 1.249 m of workpiece displacement. The page media now uses this run. The workpiece is placed at the grasp test pose, so this evidence does not complete T016 or claim conveyor pickup.

## Visual project page, 2026-08-27

Historical page iteration. The presentation video described in this section has been withdrawn from the current page.

`PROJECT_PAGE.html` is now the main visual entry point for the repository. It shows the saved YOLO26 segmentation output, rendered overhead RGB and depth, Scene 2 FANUC articulation and compliant gripper, a clear 13.75 second standard-arm presentation, a link to the older 31.42 second complete-pipeline recording, the communication path, inputs and outputs, control states, A and B behavior, validation metrics, commands, and limitations.

The main presentation was corrected after review. The old overhead Scene 1 video is no longer the primary demo because that sensor angle is hard to read and does not contain the selected FANUC arm. The new main video is `assets/project_page/fanuc_presentation.mp4`. It is rendered from a virtual three-quarter presentation camera inside the guard envelope and shows the standard arm, conveyor, product path, compliant jaws, and cutter entrance in one frame. The calibrated overhead view remains in the perception section where it belongs.

The corrected recording is 13.75 seconds at 1280 by 720 and 12 FPS. It contains 165 rendered frames and 3,300 actual articulation-controller commands with zero joint-limit violations. It is labeled as a Scene 2 articulation and jaw-motion presentation, not as the unfinished YOLO-to-FANUC delivery cycle. The first recording attempt was rejected after 763 joint-limit violations exposed a command-state bug. The script now maintains one continuous commanded state for all eight joints. The passing evidence is under `results/scene2_presentation_final`. The failed attempt remains under `results/scene2_presentation_demo`.

Selected page media is now copied into `assets/project_page` so the public repository carries the page visuals and videos. The earlier page depended on ignored `results` paths and therefore did not package its media correctly.

The page draws only from checked-in implementation documents and executed artifacts. It states the current integration boundary directly. Scene 1 is the complete camera-to-delivery vertical slice. Scene 2 validates the standard articulated arm, ROS 2 boundary, RGBD publication, and compliant gripper, but the complete YOLO-to-FANUC interception loop remains T016.

The one-command page entry point is `open_project_page.ps1`. The focused page tests validate required views, internal anchors, every local media and documentation reference, the nonempty embedded MP4, the published grasp evidence, and the prohibited dash-character rule. The complete ordinary-Python suite now reports 136 passed and 1 skipped. The existing skip is the NumPy-dependent perception test in the plain interpreter.

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

## Scene 2 accuracy matrix, 2026-08-27

The current Scene 2 pipeline now reports camera pose error, tracked pose error, intercept grasp-point error, intercept timing error, and final delivery error against a simulator oracle that is isolated from control. Perception latency, position noise, and yaw noise are explicit launcher inputs.

The 15-case headless matrix completed sequentially at `results/accuracy_matrix/20260827_175301428`. All 10 core cases passed. Core Solution A covered six runs and Solution B covered four runs. Core speeds ranged from 0.06 to 0.22 m/s, lateral starts from -60 to 50 mm, and yaw from -72 to 68 degrees.

Core Solution A mean errors were 5.08 mm at the camera, 5.08 mm after tracking, 5.50 mm at the intercept grasp point, and 12.70 mm at delivery. Solution B means were 4.30 mm, 4.30 mm, 4.76 mm, and 15.98 mm. Intercept timing error averaged 9.29 ms for A and 8.19 ms for B. All core runs had valid evidence, bilateral contact, verified delivery, and zero joint, velocity, or acceleration violations.

Two of five stress cases passed the full accuracy gate. Two more completed delivery but exceeded the internal 2 degree camera and tracking yaw limit and 3 degree intercept yaw limit under high injected yaw noise. The 0.30 m/s, 80 mm offset, 85 degree case was rejected as too late and recovered to idle without contact or false delivery.

Repeated nominal seeds for A and B were not bitwise identical across separate RTX processes. Both passed the documented bounded replay tolerances. The maximum repeated placement delta was 0.067 mm. The largest timing delta was 3.43 ms. Exact equality is reported as false.

The current one-command entry point is `run_accuracy_matrix.ps1`. It writes `accuracy_summary.json`, `accuracy_cases.csv`, a readable report, and complete per-case Isaac artifacts. This is simulation regression evidence only.
