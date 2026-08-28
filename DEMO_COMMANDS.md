# CARVE live demo commands

Run these commands from:

```powershell
cd C:\Users\jainl\meat-conveyor-robot-simulation
```

## Fastest visual walkthrough

Open the final Scene 2 workcell in visible Isaac Sim. The window stays open for ten minutes.

```powershell
.\run_scene2.ps1
```

This is the quickest way to point out the FANUC reference arm, compact gripper, conveyor, overhead RGBD camera, buffer camera, guards, cutter-entry tray, reject bin, and named frames. It runs articulation, sensor, and gripper self-check motion. It is not the complete interception cycle.

## Final Solution A evidence

Run one headless direct cycle with a moderate belt speed and a clear diagonal product pose.

```powershell
.\run_solution_a.ps1 -Seed 2601 -Scenario nominal -BeltSpeedMps 0.16 -StartYM 0.03 -StartYawDeg 28 -OutputRoot results\live_demo\solution_a
```

The command prints the evidence directory. Open its `scene2_integrated.mp4`, `yolo_overlay.png`, `rgb.png`, `depth.npy`, `cycle_trace.jsonl`, `robot_joint_trajectory.json`, and `scene2_integrated_metrics.json` files to show the full chain.

## Final Solution B evidence

Run the buffered route with an injected slip correction.

```powershell
.\run_solution_b.ps1 -Seed 3110 -Scenario slip_correction -BeltSpeedMps 0.16 -StartYM 0.03 -StartYawDeg 28 -OutputRoot results\live_demo\solution_b_slip
```

This run shows the first grasp, buffer placement, rendered re-observation, corrected regrasp, cutter delivery, and traceable recovery logic.

## Speed and orientation examples

Run five Solution A cases plus the Solution B slip case.

```powershell
.\run_speed_pose_matrix.ps1 -IncludeSolutionB -OutputRoot results\live_demo\speed_pose_matrix
```

This is the best prepared command for showing different belt speeds, lateral starts, product orientations, grasp classes, and pass or fail evidence.

## Deliberate recovery examples

```powershell
.\run_solution_a.ps1 -Scenario failed_grasp -OutputRoot results\live_demo\failed_grasp
.\run_solution_a.ps1 -Scenario cutter_unavailable -OutputRoot results\live_demo\cutter_unavailable
.\run_solution_a.ps1 -Scenario stale_observation -OutputRoot results\live_demo\stale_observation
.\run_solution_a.ps1 -Scenario emergency_stop -OutputRoot results\live_demo\emergency_stop
```

Each case passes only when it detects the injected condition, avoids a false delivery, reaches the expected recovery state, and records matching evidence.

## Full regression

```powershell
.\run_tests.ps1
```

This is the release gate. It is not the quickest live demonstration.

## Solution C learned grasp ranking

Train the scorer, then run the paired A and B baseline, learned, and replay matrix:

```powershell
.\run_solution_c.ps1
```

## Solution D reactive interception

Run predict-once and reactive A/B pairs for belt ramp, encoder bias, latency spike, and pose disturbance:

```powershell
.\run_solution_d.ps1
```

## Solution E shadow evaluation

Fit the five-phase behavior clone and run nominal A, replay A, nominal B, B slip correction, and A emergency stop. Learned outputs are recorded but never executed:

```powershell
.\run_solution_e.ps1
```

## Final hybrid ablation

Run matched A and B cases for the deterministic baseline, C only, D only, C plus D, and the explicitly blocked S4 entry:

```powershell
.\run_hybrid_comparison.ps1 -OutputRoot results\hybrid_comparison\demo
```

The manifest records S4 as `not_run`. The command does not execute learned contact actions.

## Close Isaac Sim after a manual visible session

Close the Isaac window normally. The automated Solution A and B launchers stop the simulator processes they own after each run.

## Current boundary

Solutions A and B remain the executed regression baselines. C and D are integrated simulator capabilities with one-command launchers. E is integrated in shadow-only mode. Bounded learned E execution is disabled until representative physical force, tactile, slip, tissue-damage, and recovery data exist.
