# Remaining work and research plan

Date: 28 August 2026

## Direct answer

The project has a strong simulator demonstration, but it is not a finished real-world system. Solutions A and B are the released simulation baseline. Solution C has a working learned grasp-ranking prototype. Solution D has a working reactive-interception prototype. Solution E has not been implemented.

The immediate next ticket is T017. Its code is mostly present, but its dataset and validation are not yet strong enough for promotion. T018 should remain blocked until C passes. T019 should remain blocked until D passes.

The best technical direction is deliberately modest:

1. Keep YOLO26 for product masks.
2. Improve and independently test the vision dataset.
3. Learn only the ranking of geometry-safe grasp candidates.
4. Fix and promote bounded reactive interception.
5. Prove the live ROS 2 and MoveIt path in a supported Linux environment.
6. Learn only the short contact segment, first in replay and shadow mode.
7. Use physical measurements before making claims about meat handling, grip force, damage, hygiene, or production performance.

This gives the system more adaptability without putting a large opaque model in charge of the whole cell.

## How the approaches will be compared and combined

A and B are cell-flow choices. C, D, and E are control capabilities. They should not be treated as five mutually exclusive systems.

The comparison therefore has two axes:

| Flow axis | Meaning |
| --- | --- |
| A | Intercept from the main conveyor and deliver directly to the cutter-entry tray |
| B | Intercept, place in the buffer, re-observe, then deliver to the cutter-entry tray |

| Control stack | Grasp choice | Intercept update | Contact behavior | Purpose |
| --- | --- | --- | --- | --- |
| S0 deterministic | geometric | predict once | deterministic | released baseline |
| S1 C only | learned ranking with fallback | predict once | deterministic | isolate grasp-ranking value |
| S2 D only | geometric | bounded reactive | deterministic | isolate reactive-interception value |
| S3 C plus D | learned ranking with fallback | bounded reactive | deterministic | first recommended hybrid |
| S4 C plus D plus E | learned ranking with fallback | bounded reactive | bounded learned contact segment | full research hybrid |

Every stack will run through both A and B where the capability applies. D-only runs are diagnostic ablations. They do not remove the ticket dependency that requires C to pass before D is promoted.

### Recommended hybrid route

The hybrid keeps one clear authority chain:

1. YOLO26 produces the product mask from rendered RGB.
2. Calibrated depth and geometry produce several safe grasp candidates.
3. C ranks those candidates. It falls back to the geometric rank on low confidence, low score margin, invalid data, or model failure.
4. Tracking predicts the contact time and pose.
5. D applies small same-track corrections until the no-return time. It ignores stale or unsafe updates.
6. The deterministic planner and articulation controller enforce reach, timing, joint, velocity, acceleration, singularity, workspace, and collision limits.
7. E may act only after contact is confirmed and only inside close, stabilize, slip-correct, reorient, and release states.
8. The deterministic supervisor owns PLC permissives, emergency stop, verification, reject, safe stop, and audit at all times.

This uses the strongest part of each method without creating one end-to-end black box.

### Fair test design

Each comparison will use identical starting seeds, stage state, recipe, speed, pose, lighting, sensor noise, and machine state. The stage will be reset before each stack runs. Artifacts will retain the stack identity and hashes for every active model.

The main ablations are:

- S0 against S1 under shape, yaw, width, occlusion, and friction variation. This measures C.
- S0 against S2 under belt ramps, encoder bias, latency, and pose disturbances. This measures D.
- S2 against S3 under combined grasp and motion variation. This measures whether C and D help each other.
- S3 against S4 under slip, unstable contact, reorientation, and release disturbances. This measures E.
- S0 against S3 and S4 across the complete held-out matrix. This measures total hybrid value.

The primary result is verified delivery success. Secondary results are grasp confirmation, retained lift, slip, excessive-contact proxy, intercept error, timing error, delivery position and yaw, cycle time, rejection, recovery, intervention, minimum clearance, motion violations, and p95 inference or correction latency.

The hybrid is selected only if it improves the useful outcome or gives a better success, cycle-time, and complexity tradeoff. If a learned component adds no held-out value, it stays out of the released route. A simpler stack is a valid winning result.

## What exists now

| Area | Current evidence | Honest status |
| --- | --- | --- |
| Full Isaac cell | Saved USD, FANUC reference articulation, conveyor, cameras, compliant-gripper approximation, cutter-entry tray, guards, frames, PLC-style I/O, RGBD, contact, videos, traces, and metrics | Implemented for simulation |
| Solution A | Direct conveyor interception and stationary cutter-entry tray delivery | Released simulator baseline |
| Solution B | Buffered handling with re-observation and slip correction | Released simulator baseline |
| YOLO26 | Custom instance-segmentation checkpoint, rendered-camera inference, tracking input, and grasp overlay | Implemented on synthetic data |
| ROS 2 command path | Joint states, sensor messages, standard JointTrajectory input, and FollowJointTrajectory behavior | Executed through the existing simulation bridge |
| Live MoveIt 2 | Configuration files, SRDF, KDL, OMPL, limits, collision objects, and client contracts | Not built or executed because ROS 2 Humble and colcon are absent from WSL |
| Solution C | Candidate generation, learned scorer, model file, launchers, tests, and six comparison runs | Prototype only |
| Solution D | Bounded same-track corrections, launchers, tests, eight paired perturbation comparisons, and two replays | Prototype only. Release gate failed |
| Solution E | Ticket and research design | Not implemented |

## Evidence audit

### Solution C

The useful parts are real. The integrated runner loads the model, ranks mask-interior candidates, records every score, executes the selected candidate through the actual Isaac articulation, and retains the deterministic safety gates. Focused tests pass. The six-run deterministic comparison also passed.

The evidence is still too small:

- The fit set has 10 rows.
- The held-out set has 5 rows.
- Contact RMSE on held-out rows is 0.4472.
- Delivery RMSE is 0.3618.
- Excessive-contact RMSE is 0.6383.
- Retained-lift RMSE is 0.4288.
- Slip RMSE is 0.5043.
- Several predicted probabilities saturate at zero or one.
- The comparison does not establish that the selected candidate is better than plausible alternatives under matched scene conditions.
- The learned A run still reported an uncalibrated peak contact proxy above 2,000 N on one finger. This is not a physical force measurement, but it shows that the proxy is unsuitable as a promotion signal until it is calibrated or bounded more meaningfully.

Conclusion: C proves integration, serialization, fallback structure, and deterministic execution. It does not yet prove a useful learned grasp policy.

### Solution D

All 18 expected artifacts now exist. The matrix contains baseline and reactive runs for belt ramp, encoder bias, latency spike, and pose disturbance in both A and B, plus one reactive replay per solution.

The comparison is encouraging:

- Reactive execution passed all eight perturbation cases.
- Track identity was retained.
- Stale latency updates failed closed in A and B.
- No new collision, joint, velocity, or acceleration violations were reported.
- Intercept position improved in 6 of 8 paired cases.
- Mean intercept position improvement was 16.97 mm.
- Reactive A recovered a belt-ramp case that the predict-once baseline did not deliver.

The release summary still failed. Solution A replay differed from its first run by 0.792 mm in delivery position against a 0.300 mm tolerance. Delivery yaw differed by 0.515 degrees against a 0.200 degree tolerance. Solution B replay passed.

Conclusion: D has a credible vertical slice, but it is not reproducible enough for release. The tolerances must not be widened before the source of the drift is identified.

### Solution E

No E launcher, dataset, policy, integrated result, or focused test exists. The current ticket correctly blocks it behind D.

The larger blocker is physical validity. The workpieces are rigid approximations. Drive effort, contact force, friction, compliance, slip, and tissue damage are not calibrated against representative beef, pork, or chicken. There is no tactile array. A simulator-only E can test software boundaries, replay, shadow behavior, bounded actions, abstention, and recovery. It cannot prove that a learned contact policy will handle real meat without damage or loss.

## Research conclusions

### Perception

Ultralytics identifies YOLO26 as its current model family for new projects. It supports instance segmentation, oriented boxes, tracking, export, and benchmarking. CARVE already uses a YOLO26 segmentation checkpoint, so changing model families now would add churn without addressing the main weakness. The next work should improve data coverage and independent validation, not replace the interface. [Ultralytics YOLO26](https://docs.ultralytics.com/models/yolo26)

The current synthetic validation reports mask mAP50 of 0.9176 and mask mAP50-95 of 0.7521. Those numbers are useful only for the synthetic distribution used to train and validate the checkpoint. Integrated stress runs show much lower confidence at transverse angles and in noisy buffer views. A real validation set is still absent.

Isaac Sim Replicator can vary scene appearance and physics properties such as mass, friction, and restitution. This is useful for controlled stress coverage, but it does not replace real images or measured mechanics. [Isaac Sim scene-based synthetic data generation](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/replicator_tutorials/tutorial_replicator_scene_based_sdg.html) [Isaac Sim 6.0 release notes](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/overview/release_notes.html)

Recommendation: keep the replaceable vision interface and YOLO26. Add held-out synthetic scenes, then a separately labeled real-camera set. Report mask precision, recall, mAP50-95, mask IoU, pose error, track continuity, confidence calibration, missed-intercept rate, and p95 latency. Do not tune thresholds on the final test set.

### Grasp selection

Contact-GraspNet, VGN, Dex-Net, and AnyGrasp show useful patterns for learned grasping. They predict candidate quality from depth or 3D geometry, retain several possible grasps, and evaluate grasp success rather than treating an object box as a grasp. [Contact-GraspNet](https://arxiv.org/abs/2103.14127) [VGN](https://proceedings.mlr.press/v155/breyer21a/breyer21a.pdf) [Dex-Net](https://berkeleyautomation.github.io/dex-net/) [AnyGrasp](https://arxiv.org/abs/2212.08333)

These systems were primarily evaluated on rigid objects. Their reported success rates do not transfer to raw meat. CARVE also has a simpler planar setup than a general cluttered 6D grasp benchmark.

Recommendation: do not add a large 6D grasp network yet. Keep the current planar candidate generator. Train a small regularized classifier or ranker on matched, executed candidate trials. Use a 3D model only if real observations show that product roll, folding, piles, or non-top-down approaches are common.

### Reactive motion

MoveIt Servo provides joint and velocity limit enforcement, collision checking, singularity checking, and smoothing for real-time updates. This matches the safety envelope needed around D. [MoveIt Servo](https://moveit.picknik.ai/main/doc/examples/realtime_servo/realtime_servo_tutorial.html)

NVIDIA cuMotion exposes MoveIt-compatible collision-aware planning and collision-free inverse kinematics. Its supported workflow uses ROS 2 on Linux and requires a URDF and XRDF for a new robot. [Isaac ROS cuMotion](https://nvidia-isaac-ros.github.io/v/release-4.4/repositories_and_packages/isaac_ros_cumotion/isaac_ros_cumotion/index.html)

Recommendation: keep D deterministic first. Use fresh same-track observations to propose small corrections. Keep the no-return boundary, total correction cap, oscillation check, collision margin, PLC gates, and emergency stop authoritative. A learned residual is unnecessary until the deterministic version is stable across replay and broader held-out perturbations.

### Skill learning

Behavior cloning is the smallest suitable baseline for E. Isaac Lab Mimic can expand a small set of object-relative demonstrations and train a behavior-cloning policy through robomimic. NVIDIA's own example uses explicit subtask boundaries and reports that dataset generation success can vary widely. Its current Mimic workflow is Linux-only. [Isaac Lab Mimic](https://isaac-sim.github.io/IsaacLab/develop/source/overview/imitation-learning/teleop_imitation.html)

DAgger addresses the problem that a learned policy visits states that are missing from ordinary expert demonstrations. It does this by adding expert labels on policy-induced states. [DAgger paper](https://proceedings.mlr.press/v15/ross11a.html)

Residual reinforcement learning keeps a conventional controller and learns only a correction for difficult contact and friction effects. That architecture fits CARVE better than replacing the whole controller. [Residual reinforcement learning](https://arxiv.org/abs/1812.03201)

ACT and Diffusion Policy are stronger sequence models for fine or multimodal manipulation. They also add data, inference, debugging, and validation burden. CARVE does not yet have enough representative contact data to justify them. [ACT](https://arxiv.org/abs/2304.13705) [Diffusion Policy](https://arxiv.org/abs/2303.04137)

Recommendation: start E with a small state-based behavior-cloning or residual model for close, stabilize, slip-correct, reorient, and release. Keep it in offline replay and shadow mode first. Consider ACT only if ordinary behavior cloning fails on temporal contact behavior with a sufficiently large dataset. Consider Diffusion Policy only if the same observation genuinely needs several distinct valid action sequences.

### Contact and compliance

NIST separates grasp evaluation into motion and effort. Its proposed measures include grasp cycle time, grasp strength, force tracking, touch sensitivity, slip resistance, object pose estimation, and in-hand manipulation error. It also recommends independent measurement when comparing systems. [NIST grasping metrics](https://www.nist.gov/el/intelligent-systems-division-73500/robotic-grasping-and-manipulation-assembly/grasping)

GelSight research shows that tactile geometry and shear can detect translational, rotational, and incipient slip. It also demonstrates why a jaw-position or drive-effort proxy is not equivalent to tactile evidence. [GelSight geometry and slip](https://arxiv.org/abs/1708.00922) [GelSight shear and incipient slip](https://publications.ri.cmu.edu/measurement-of-shear-and-slip-with-a-gelsight-tactile-sensor)

Recommendation: preserve the simulated compliance model as a software test fixture. Before hardware learning, measure jaw force, contact pressure, slip onset, retained load, deformation, and visible product damage on representative cuts. Select the real gripper and sensor stack only after these tests.

## Dependency-ordered execution plan

### Phase 0: preserve the released baseline

Goal: make sure the partial C and D work has not weakened A or B.

Work:

1. Start from a clean Isaac and Kit process state.
2. Run `run_tests.ps1` with the current working tree.
3. Confirm that A and B still generate nonempty USD, RGB, depth, video, trajectory, PLC trace, contact evidence, and metrics.
4. Confirm that no process remains after the run.
5. Record the new full-suite result root before changing any ticket status.

Gate: the existing A and B thresholds pass unchanged.

### Phase 0.5: create the shared comparison harness

Goal: make every later claim directly comparable.

Work:

1. Add one experiment manifest for flow A or B, stack S0 through S4, recipe, seed, speed, pose, perturbation, and model hashes.
2. Reset the same saved stage before every paired stack run.
3. Reuse one artifact schema for all stacks.
4. Add an aggregate summary with paired deltas and pass or fail reasons.
5. Keep unavailable stacks marked `not_run`. Never treat them as zero or as a pass.

Gate: the harness can reproduce the current S0 A and B baselines and can summarize the existing S1 and S2 prototype evidence without changing the underlying metrics.

### Phase 1: finish T017, Solution C

Goal: determine whether learned ranking adds value over geometric selection.

Work:

1. Replace the 15-row proof dataset with matched candidate trials. Reset the same seeded scene and execute several safe candidates separately. This produces a fair comparison between center, offset, and orientation choices.
2. Cover all three reference recipes, longitudinal through transverse yaw, 0.06 to 0.30 m/s belt speed, lateral offsets, partial occlusion, depth noise, light changes, friction variation, compliance variation, and latency.
3. Split by complete seed and scene family. Never place adjacent observations from one cycle in different partitions.
4. Keep the small regularized model. Add class-balance checks, Brier score, calibration error, ranking regret, top-one success, abstention coverage, and held-out end-to-end success.
5. Add explicit counterexamples where the learned rank differs from geometric rank. Execute both choices from the same reset state.
6. Test missing model, corrupt model, hash mismatch, feature mismatch, low margin, low vision confidence, and out-of-range geometry in full Isaac cycles.
7. Run A and B comparisons across a seed matrix, then run the complete release suite.

Promotion gate:

- Every predicted outcome contains both positive and negative held-out examples.
- No train and held-out scene leakage exists.
- Learned ranking improves or safely matches paired delivery and retained-lift outcomes.
- It does not increase excessive-contact proxy, collision, motion-limit, stale-commit, PLC, or recovery failures.
- Calibration and abstention are reported, not hidden behind one accuracy number.
- Bounded replay and the full release suite pass.

### Phase 2: finish T018, Solution D

Goal: make reactive updates reproducible and useful under changing conveyor conditions.

Work:

1. Reproduce the failed A pose-disturbance replay in isolation.
2. Compare hashes and first divergence for the saved stage, initial transforms, RGB, depth, YOLO mask, track states, correction proposals, articulation commands, contact times, and delivery measurements.
3. Determine whether drift starts in rendering, perception, tracking, physics contact, or trajectory execution.
4. Fix the source. Do not widen replay tolerances as the first response.
5. Rerun the original 18-run matrix.
6. Add held-out seeds and combined perturbations. Important combinations are belt ramp plus latency, encoder bias plus yaw disturbance, and pose disturbance near the no-return boundary.
7. Measure p50, p95, and maximum correction latency, intercept error, minimum clearance, cycle time, grasp, retention, delivery, rejection, and recovery.
8. Run the full release suite after C and D are both green.

Promotion gate: A and B replay pass unchanged, all reactive cases retain identity and deterministic gates, and the improvement holds on held-out seeds rather than only the development matrix.

### Phase 3: prove the live ROS 2 and MoveIt path

Goal: execute a MoveIt-planned trajectory through ROS 2 into the Isaac articulation, not only through the in-process contract adapter.

External prerequisite: a supported ROS 2 Humble environment with colcon and MoveIt 2. The current WSL environment does not have it. Creating or installing that environment needs explicit approval because it changes software outside the project.

Work after approval:

1. Build the existing `ros2_ws` packages.
2. Launch one `move_group` process with the FANUC URDF, SRDF, limits, controller mapping, and static cell collision objects.
3. Plan with OMPL first. Keep cuMotion as an optional later planner.
4. Execute through FollowJointTrajectory and verify measured start, path, goal, cancel, timeout, and emergency-stop behavior.
5. Add the moving target only after static start-to-goal execution passes.
6. Record ROS topics, transforms, action states, planned trajectory, measured joints, collision result, and Isaac metrics.

Gate: one-command build and launch, collision-aware plan, articulation execution, cancellation, stale-command rejection, and clean shutdown all pass.

### Phase 4: implement T019, Solution E

Goal: test whether learning helps only the contact-rich segment.

Work:

1. Define the exact contact-segment observation and bounded action schema.
2. Generate synchronized teacher trajectories from successful deterministic A and B cycles plus slip, failed grasp, unexpected contact, stale input, and emergency-stop recoveries.
3. Start with a small state-based behavior-cloning or residual model.
4. Evaluate offline replay.
5. Run simulation shadow mode. Log model actions without applying them.
6. Promote to bounded execution only when shadow actions satisfy every deterministic gate on held-out seeds.
7. Test nominal close, stabilization, injected slip, reorientation, release, abstention, fallback, recovery, and stop.
8. Compare with the deterministic contact sequence using paired seeds.

Gate: no learned action can leave its state, pose, jaw, velocity, acceleration, collision, contact-proxy, PLC, or emergency-stop envelope. A and B full cycles and replays must stay green.

### Phase 5: physical calibration and transfer

This is the point where real-world work begins.

Required inputs:

- exact conveyor dimensions, speed profile, encoder behavior, belt material, and wet friction
- exact cutter-entry geometry, timing, permissives, and handoff tolerances
- chosen robot controller and measured tool center point
- real gripper geometry, opening, force range, pad material, washdown constraints, and cleanability requirements
- camera model, lens, mounting, lighting, exposure, and calibration captures
- representative beef, pork, and chicken dimensions, mass, temperature, surface condition, compliance, and damage limits
- measured grip force, contact pressure, slip onset, deformation, and damage results
- real cycle-rate and reject-rate requirements

Work:

1. Build a guarded low-speed test rig.
2. Calibrate cameras, robot base, conveyor frame, tool frame, and cutter-entry frame with independent measurement.
3. Validate YOLO26 on labeled real images before using it to command motion.
4. Fit friction and compliance ranges from measurements, then rerun simulation sensitivity tests.
5. Run end-effector tests separately from whole-cell tests, following the NIST separation between gripper effort and system motion.
6. Progress from dry objects to representative product only under the relevant engineering, hygiene, and safety process.

No simulator result can replace this phase.

### Phase 6: release, report, and public page

Work:

1. Reconcile BUILD_STATUS, OVERNIGHT_REPORT, tickets, commands, and the public report with the evidence.
2. Mark C, D, or E complete only after its own gate and the full release suite pass.
3. Add concise visuals for candidate ranking, reactive target updates, replay error, shadow actions, intervention reasons, and paired outcome distributions.
4. Keep C, D, and E labeled as prototypes until promotion.
5. Publish only committed, reproducible artifacts.

## Test matrix that should remain fixed

| Dimension | Core values |
| --- | --- |
| Product | beef, pork, chicken reference recipes |
| Solution path | A and B |
| Belt speed | 0.06, 0.10, 0.14, 0.18, 0.22, 0.26, 0.30 m/s |
| Yaw | 0, 30, 60, 90, 120, 150 degrees with small random offsets |
| Lateral position | center and both workspace edges |
| Perception | nominal, low contrast, partial occlusion, depth noise, latency spike |
| Motion | nominal, belt ramp, encoder bias, pose disturbance, combined disturbance |
| Contact | nominal, low friction, high friction, slip injection, failed bilateral contact |
| Machine state | ready, cutter unavailable, buffer timeout, stale observation, emergency stop |
| Evaluation | baseline, candidate, exact replay, held-out seed |

Every reported distribution should include sample count, median, p95, worst case, failure count, and seed list. Binary success rates should include confidence intervals. Paired comparisons should retain identical starting seeds and scene states.

## What should not be added yet

- A vision-language-action model in the real-time control loop.
- A large 6D grasp network for a planar single-layer conveyor without evidence that planar candidates are insufficient.
- Reinforcement learning over the entire cycle.
- Automatic threshold relaxation to make replay pass.
- Claims based only on simulator ground truth.
- Claims that contact-force proxies represent real force, tissue damage, food safety, or production readiness.
- New public claims before the working tree, tickets, tests, and evidence agree.

## Exact next action

Create the shared S0 through S4 experiment manifest and summary first. Then finish T017 by rebuilding the dataset as matched, executed candidate trials. Keep the current small model and deterministic fallback. Compare S0 with S1 in both A and B. Only after C is green should the A replay drift in T018 be fixed and the S0, S2, and S3 D matrix be rerun.

## Open decisions for the real cell

These questions do not block the next simulator pass, but they block physical design and transfer:

1. Which exact cuts and size ranges are first for commissioning?
2. What is the acceptable visible damage, compression, and drop rate?
3. What is the required throughput and maximum reject rate?
4. What exact signal does the cutter provide for ready, phase, accept, fault, and result?
5. Will the product arrive singly with spacing, or can pieces touch and overlap?
6. Which gripper concept can meet force, opening, cleanability, and washdown needs?
7. Are overhead cameras sufficient, or is a wrist or side view required for folds and occlusion?
8. What hardware and software environment is approved for ROS 2 and MoveIt validation?

## Claim boundary

This plan is based on current CARVE artifacts, primary technical sources, and simulation evidence. It does not establish OEM fidelity, physical accuracy, hygienic design, food-safety compliance, machine safety, or production readiness.
