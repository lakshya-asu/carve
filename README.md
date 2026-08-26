# Carve

Carve is a runnable Isaac Sim 6.0.1 project for vision-guided robotic handling of beef, pork, and chicken cuts on a moving conveyor. The current reference cell operates at a nominal conveyor speed of 2.24 m/s and releases aligned products onto a stationary cutter-entry tray.

The saved USD cell includes a conveyor, dynamic meat workpieces, a generic six-joint Cartesian articulation, a compliant two-finger gripper reference, overhead and wrist cameras, calibration frames, guards, a reject bin, `cut_target_frame`, a guarded cutter or feed reference, PLC state, and the Solution B buffer.

All robot motion in the integrated demonstration goes through the Isaac articulation controller. All primary observations come from rendered RGB and depth through a replaceable segmentation interface. Simulator ground truth is not used as the primary perception result.

The robot, gripper, workpiece, buffer, and cutter are abstract reference models. They are not OEM accurate. The model is not physically calibrated, food-safe validated, real-cell safety validated, or production ready.

## One-command entry points

Run setup validation:

```powershell
.\validate_setup.ps1
```

Run four seeded Solution A cycles:

```powershell
.\run_solution_a.ps1
```

Run four seeded Solution B cycles:

```powershell
.\run_solution_b.ps1
```

Run a catalog product recipe without replacing the baseline artifacts:

```powershell
.\run_recipe.ps1 -Recipe beef_center_cut_tenderloin -Solution a
.\run_recipe.ps1 -Recipe pork_boneless_loin -Solution a
.\run_recipe.ps1 -Recipe chicken_breast_fillet -Solution a
.\run_recipe.ps1 -Recipe beef_center_cut_tenderloin -Solution b
.\run_recipe.ps1 -Recipe pork_boneless_loin -Solution b
.\run_recipe.ps1 -Recipe chicken_breast_fillet -Solution b
```

The recipe launcher writes under `results/recipes/<recipe>/solution_<a-or-b>`. Each saved stage and metric file records the recipe ID, species, cut, nominal geometry, mass, shape family, compliance proxy, and physical-calibration status.

Audit all six recipe artifacts, rendered RGB and depth files, traces, expected recovery paths, and metrics:

```powershell
C:\Users\jainl\is6\Scripts\python.exe tools\audit_artifacts.py --root results\recipes --mode recipes --output results\recipes\artifact_audit.json
```

The recipe runs currently use deterministic rendered color and depth segmentation. The existing YOLO26 checkpoint was trained on the earlier generic reference workpiece. It must be retrained and validated on the three recipe appearances before it can be claimed as multi-recipe perception.

Run the unit tests, setup validation, and both integrated suites:

```powershell
.\run_tests.ps1
```

Run the bounded five-seed hardening matrix for both solutions:

```powershell
.\run_hardening.ps1
```

Resume a previously interrupted hardening matrix. Only matching passing batches are skipped:

```powershell
.\run_hardening.ps1 -Resume
```

## Learned YOLO26 segmentation

The optional learned perception path uses the official Ultralytics `yolo26n-seg.pt` base and a project-local Ultralytics 8.4.129 install. As checked on 2026-08-26, YOLO26 is the latest documented Ultralytics model family. The custom checkpoint is trained only on labeled RGB frames rendered by this Isaac cell. It is a synthetic reference model, not a real meat detector.

Set up the isolated project packages and official base checkpoint:

```powershell
.\setup_yolo.ps1
```

Regenerate the 240-frame Isaac dataset and train the reference model:

```powershell
.\train_yolo.ps1
```

Run learned-vision Solution A, Solution B, or the complete learned-vision test suite:

```powershell
.\run_yolo_solution_a.ps1
.\run_yolo_solution_b.ps1
.\run_yolo_tests.ps1
```

Open the complete Solution B example in a visible Isaac Sim window:

```powershell
.\run_yolo_demo.ps1
```

Record the complete four-cycle Solution B example from the actual rendered overhead camera:

```powershell
.\record_yolo_demo.ps1
```

The recording, contact sheet, metrics, media, and traces are written under `results/yolo/recorded_demo`. Open `TECHNICAL_REPORT.html` for the full implementation report, architecture visuals, inputs and outputs, state machines, metrics, assumptions, and embedded video.

The project writing standard is in `WRITING_STYLE_RESEARCH.md`. Check both HTML reports with:

```powershell
python tools\audit_report_language.py --fail-on-style
```

This command is a style lint. It does not claim to detect whether AI wrote a passage.

The live model consumes rendered RGB. Its instance mask is combined with rendered depth and the calibrated camera transform to produce the stamped planar pose used by tracking and interception. Ground-truth geometry is used only to label the synthetic training set, not during live inference.

The scripts use the existing Isaac Sim Python at `C:\Users\jainl\is6\Scripts\python.exe`. The EULA environment flag is set only because the current workstation user explicitly accepted the NVIDIA EULA.

## Results

- `results/isaac_cell_a.usda` and `results/isaac_cell_b.usda` are visible saved stages.
- `results/isaac_a/metrics.json` and `results/isaac_b/metrics.json` contain gate results and aggregate metrics.
- `results/isaac_a/traces` and `results/isaac_b/traces` contain deterministic JSON Lines cycle traces.
- `results/isaac_a/media` and `results/isaac_b/media` contain rendered RGB and depth evidence.
- `results/setup_validation.json` records fixed-step, save and reload, articulation, sensor, and perception checks.
- `results/artifact_audit.json` records the independent baseline artifact audit.
- `results/recipes/artifact_audit.json` records the independent six-batch recipe audit.
- `results/hardening/summary.json` records the five-seed, 60-cycle hardening matrix and artifact audit.
- `results/yolo/training_summary.json` records the learned model hash and validation metrics.
- `results/yolo/headless_a_v2/isaac_a/metrics.json` and `results/yolo/headless_b_v2/isaac_b/metrics.json` record passing learned-vision integration runs.
- `results/yolo/recorded_demo/isaac_b/demo.mp4` is the actual rendered overhead-camera recording from the four-cycle YOLO26 Solution B demonstration.
- `TECHNICAL_REPORT.html` is the complete visual and technical implementation report.

Each four-cycle integrated suite runs two nominal cycles, one intentionally failed contact grasp, and one downstream fault cycle. A pass therefore means both nominal cycles delivered successfully and both injected failures recovered as designed. It does not mean 50 percent expected production yield.

Each hardening batch runs two nominal cycles plus failed-grasp, downstream-unavailable, emergency-stop, and stale-observation cases. The current five-seed matrix passed all 10 A and B batches. It is bounded simulator evidence under the stated assumptions, not an estimated production yield or physical validation.

## Fast screening model

The simulator-independent model remains available for architecture screening and regression tests:

```powershell
python -m meatcell compare --episodes 1000 --seed 7 --output results/comparison.json
python -m pytest -q
```

It is not accepted as evidence for the integrated Isaac milestone.

## Important files

- `PROBLEM_STATEMENT.md`: authoritative customer scope
- `PRODUCT_RECIPES.md`: beef, pork, and chicken geometry, mass, shape, compliance, evidence, and open calibration needs
- `configs/product_recipes.yaml`: versioned machine-readable product catalog
- `SYSTEM_DESIGN.md`: durable architecture and simulation assumptions
- `BUILD_STATUS.md`: current implementation status
- `OVERNIGHT_REPORT.md`: commands, evidence, metrics, fixes, and remaining physical blockers
- `TECHNICAL_REPORT.html`: architecture, I/O, control, perception, PLC, evidence, video, and implementation map
- `SCENE_DESIGN_REPORT.html`: Scene 2.0 robot choice, layout, sensors, communication, evidence, and build order
- `WRITING_STYLE_RESEARCH.md`: research-backed project writing standard and language audit rules
- `isaac_sim/`: stage builder, adapters, perception, validation, and integrated runner
- `meatcell/`: simulator-independent contracts and deterministic control logic
- `tickets/`: ticket status and acceptance evidence
