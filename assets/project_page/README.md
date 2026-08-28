# Project page media

These files are selected copies of executed Isaac Sim evidence. They are tracked so `PROJECT_PAGE.html` works from a public repository checkout. The full run folders remain under ignored `results` directories.

## Final integrated Scene 2 evidence

- `scene2_solution_a.mp4`: complete Solution A moving-conveyor interception and direct cutter-tray delivery
- `scene2_solution_b.mp4`: complete Solution B buffer re-observation, regrasp, and cutter-tray delivery
- `scene2_solution_a_poster.png` and `scene2_solution_b_poster.png`: presentation-camera frames from the final runs
- `scene2_solution_a_contact_sheet.png` and `scene2_solution_b_contact_sheet.png`: full cycle summaries
- `scene2_yolo26_segmentation.png`: final Scene 2 YOLO26 segmentation output
- `scene2_overhead_depth.png`: aligned overhead depth preview
- `scene2_buffer_rgb.png`: Solution B buffer observation
- `scene2_solution_a_metrics.json` and `scene2_solution_b_metrics.json`: machine-readable final run evidence
- `scene2_solution_a_audit.json` and `scene2_solution_b_audit.json`: fail-closed artifact audit results
- `carve_scene2_a.usda` and `carve_scene2_b.usda`: saved complete cell stages

The final runners use rendered perception, tracking, prediction, a moving conveyor, the FANUC articulation controller, bilateral PhysX contact, physical product retention without pose writes after grasp, reorientation, cutter-frame alignment, PLC-style I/O, release, verification, and recovery.

## Learned-route simulator evidence

- `learning/solution_c_grasp.png`, `solution_c_a.mp4`, and `solution_c_summary.json`: learned ranking among geometry-safe grasp candidates.
- `learning/solution_d_updates.png`, `solution_d_a_belt_ramp.mp4`, and `solution_d_summary.json`: same-target reactive corrections during a belt ramp.
- `learning/solution_e_shadow.png`, `solution_e_b_slip_shadow.mp4`, and `solution_e_summary.json`: five-phase shadow proposals with zero learned commands.
- `learning/solution_c_training_summary.json` and `solution_c_heldout_evaluation.json`: the 15-row fit, 10-row held-out matched C record and held-out candidate evidence.
- `learning/hybrid_experiment_manifest.json` and `hybrid_comparison_summary.json`: the final eight-case A/B S0 through S3 ablation. S4 is recorded as not run.

C and D pass integrated simulator comparison gates. E passes replay and shadow evaluation only. Representative physical force, tactile, slip, tissue-damage, and recovery data are still required before bounded learned execution.

## Historical Scene 2 presentation

- `fanuc_real_pickup.mp4`: 13.42 second continuous stationary-belt pickup recording used by the page
- `fanuc_real_pickup_poster.png`: retained-workpiece frame used by the page
- `fanuc_real_pickup_contact_sheet.png`: approach, contact, lift, transport, release, and retract summary
- `fanuc_real_pickup_metrics.json`: IK, clearance, contact, continuity, lift, drift, release, limit, frame, and file evidence
- `fanuc_presentation.*`: withdrawn fixture-test media retained only as historical screening evidence

The presentation camera is inside the guard envelope. It exists to explain the task and is not a proposed production sensor location. This older recording proves focused Scene 2 articulation, bilateral jaw contact, gravity hold, and physical release. It is retained as development history. The final integrated files above supersede it as the page evidence.

## Historical abstract-cell evidence

- `yolo26_segmentation.jpg`: saved learned segmentation output from Scene 1
- `overhead_rgb.png`: rendered overhead RGB input
- `overhead_depth_preview.png`: aligned depth preview
- `legacy_scene1_end_to_end.mp4`: older complete YOLO-to-delivery recording
- `legacy_scene1_contact_sheet.png`: complete-pipeline sequence summary
- `legacy_scene1_metrics.json`: complete-pipeline recording and cycle evidence

## Standard-arm and suite evidence

- `fanuc_robot_closeup.png`: Scene 2 arm and compliant gripper view
- `scene2_validation.json`: articulation, ROS 2, RGBD, and compliance results
- `full_suite_artifact_audit.json`: latest clean combined artifact audit

All robot, gripper, product, conveyor, cutter, and cell assets remain simulation references. No OEM fidelity, physical accuracy, food-safety validation, machine-safety validation, or production readiness is claimed.
