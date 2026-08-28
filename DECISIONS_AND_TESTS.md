# CARVE decision and test ledger

Date: 27 August 2026

This ledger separates decisions, implementation, evidence, and remaining uncertainty. It does not turn simulation assumptions into physical claims.

## Decision ledger

| Decision | Why it was made | What was implemented | Evidence or current limit |
| --- | --- | --- | --- |
| Use a deterministic first cell | The prototype window is one month. Timing, recovery, and safety boundaries must remain inspectable. | Explicit state machines, typed contracts, fixed-step time, rejection rules, and PLC gates. | A and B complete in Isaac. A learned end-to-end policy is not in control. |
| Treat the cutter entrance as a stationary tray | The downstream mechanism was unclear. A stationary handoff isolates the robot task without inventing cutter motion. | `cut_target_frame`, stationary tray, release, near-zero-speed verification, and simulated cutter permissive. | Real cutter geometry, phase, and feed requirements are still unknown. |
| Use planar product pose first | The current cuts move and rotate on the belt. Full flipping would add an unproven 6D problem. | X, Y, Z, and yaw estimates with product-specific rigid meshes. | Roll, pitch, folding, and full deformable shape are not modeled. |
| Use a standard six-axis arm | The user asked for a recognizable standard robot with a realistic kinematic basis. | FANUC M-10iD/12 official-description reference, six controlled revolute joints, meshes, masses, inertias, and limits. | It is not an OEM-certified digital twin or controller model. |
| Keep one fixed overhead RGBD camera in the baseline | It observes the belt without changing viewpoint and avoids unnecessary wrist payload. | Rendered RGB and depth, intrinsics, fixed extrinsics, exposure time, noise, and latency. | A wrist camera remains optional for occlusion or close-up correction. |
| Use YOLO26 instance segmentation | Real-time segmentation provides object identity and boundary geometry in one replaceable interface. | Synthetic dataset generation, YOLO26 training, rendered-image inference, masks, confidence, and overlays. | Synthetic holdout scores do not predict real-camera accuracy. |
| Do not use the box center as the grasp | A bounding box includes belt pixels and can place the fingers near an irregular boundary. | Mask-interior clearance point, principal-axis jaw direction, recipe-aware width, and grasp class. | It is still a geometric score, not a learned contact-success model. |
| Use depth and explicit calibration | Pixel coordinates are not robot coordinates. | RGBD back-projection and named frame transforms. | Real intrinsics, extrinsics, distortion, drift, and calibration repeatability are unmeasured. |
| Use exposure timestamps and one simulation clock | Latency at conveyor speed becomes position error. | Fixed 240 Hz physics and control clock, timestamped camera and encoder data, age checks, and replay. | Cross-process runs are bounded-repeatable, not bit-exact. |
| Fuse vision with conveyor state | The belt supplies a strong motion prior and an independent timing signal. | Timestamped encoder interpolation, photoeye, track velocity, and future-pose prediction. | Real encoder noise, slip, and transport dynamics need measurement. |
| Plan interception in space and time | A reachable location can still be too late. | Candidate pick window, robot travel estimate, timing reserve, freshness, uncertainty, and clearance gates. | The simulated tested speed range is below the original 2.24 m/s requirement. |
| Use Lula IK and bounded joint trajectories | The actual articulation needs six-joint commands with explicit limits. | Lula IK, quintic interpolation, position, velocity, acceleration, workspace, and clearance preflight. | External live MoveIt `FollowJointTrajectory` execution is not commissioned. |
| Require bilateral product contact | A jaw command alone does not establish physical pickup. | Left and right contact sensors, recent-contact gate, finite-effort jaw drives, hold and release evidence. | Contact, friction, and force values are uncalibrated proxies. |
| Use a compact two-finger compliant reference gripper | The first oversized tool collided with the conveyor and obscured the pickup. | 220 mm opening reference, 140 mm pads, recipe-aware closure, soft contact, and 8 mm per-pad compliance proxy. | It is a project reference, not a food-grade production mechanism. |
| Keep the same rigid body through pickup and delivery | Earlier visual shortcuts could make an object appear in the gripper. | The workpiece remains one simulated rigid body. No product pose writes occur after grasp confirmation. | Rigid-body retention is not deformable tissue behavior. |
| Compare a direct and buffered route | The trade is cycle time versus a second observation and correction opportunity. | Solution A direct delivery. Solution B buffer release, re-observation, corrected regrasp, and delivery. | Current A/B evidence is in simulation only. |
| Give the PLC ownership of machine permissives | Cutter readiness and emergency behavior must not be inferred by perception. | Conveyor speed, recipe, cutter state, permissives, faults, emergency stop, result acknowledgement, and trace. | It is a simulated interface, not a connected safety PLC. |
| Fail closed on stale, late, unreachable, or uncertain targets | A missed product is preferable to an unsafe or false pick. | Reject reasons, retreat, reject routing, safe stop, buffer timeout, and fault traces. | Production policy for skip, stop, divert, or operator intervention is unresolved. |
| Use ground truth only as an oracle | Hidden state would make the demonstration misleading if used for control. | Post-run scoring for camera, tracking, intercept, timing, and delivery error. | Oracle fields are not control inputs. |
| Preserve a pure Python domain layer | Logic must be unit-testable without waiting for Isaac startup. | Contracts, clock, frames, tracking, interception, trajectories, supervisors, metrics, and tests outside simulator adapters. | Simulator claims still require integrated Isaac evidence. |
| Publish evidence and limitations together | A polished video alone does not explain whether contact, limits, and delivery actually passed. | Public technical report, videos, overlays, depth, metrics, trace checks, and source links. | The public page is an engineering record, not a production qualification report. |

## What was built

- A saved, visible USD cell with conveyor, workpieces, FANUC reference articulation, compliant gripper reference, cameras, guards, reject area, buffer, cutter-entry tray, and named frames.
- Rendered RGB and depth inputs from physical camera prims.
- A replaceable YOLO26 instance-segmentation interface.
- Metric pose recovery, grasp selection, tracking, motion prediction, and intercept reservation.
- Six-axis Lula inverse kinematics and fixed-step Isaac articulation control.
- Bilateral contact confirmation, retention checks, slip injection, slip correction, and grasp-loss recovery.
- Direct and buffered delivery routes aligned to `cut_target_frame`.
- PLC-style inputs, outputs, permissives, faults, emergency stop, and cycle traces.
- Deterministic scenario seeds, media capture, structured metrics, post-run ground-truth scoring, and fail-closed artifact audits.
- ROS 2 message contracts, live sensor and `JointTrajectory` publication, a `FollowJointTrajectory` adapter, and a MoveIt package. Live external MoveIt execution remains uncommissioned.

## A/B tests and results

### A versus B architecture test

Question: does a buffer and second observation improve delivery enough to justify extra motion and handling?

| Measure | Solution A direct | Solution B buffered | Interpretation |
| --- | ---: | ---: | --- |
| Core camera position error, mean | 5.08 mm | 4.30 mm | B started with slightly lower simulated perception error in its sampled cases. |
| Core tracking position error, mean | 5.08 mm | 4.30 mm | Tracking preserved the camera-position error closely. |
| Core intercept position error, mean | 5.50 mm | 4.76 mm | Both were below the internal 15 mm intercept gate. |
| Core delivery position error, mean | 12.70 mm | 15.98 mm | A was better in this small simulated core matrix. |
| Core timing error, mean | 9.29 ms | 8.19 ms | B was slightly better in these sampled runs. |
| Core full-gate result | 6 of 6 | 4 of 4 | Both passed every normal-envelope case. |

Decision: keep both. The current evidence does not show that B is universally more accurate. It shows that B adds a recovery and re-observation path. Real workpiece slip and cutter tolerance data must decide whether that value justifies its cycle-time and handling cost.

### Detection versus segmentation decision

Question: is a box enough, or does grasping need shape?

Result: the implemented route uses instance segmentation because the mask supplies the visible boundary, major axis, and clearance field. YOLO26 synthetic holdout metrics were box mAP50 0.9276, mask mAP50 0.9176, mask precision 0.8733, and mask recall 0.8615.

Decision: retain segmentation as the primary interface. Keep detection as a latency baseline during real-data commissioning. These synthetic scores do not establish real performance.

### Fixed grasp point versus mask-aware grasp point

Question: should the robot grasp a fixed box center or select a point from the visible product shape?

Result: the current selector places the grasp inside the instance mask with boundary clearance and selects longitudinal, diagonal-left, diagonal-right, or transverse jaw orientation. The same proposal drives the overlay and the robot command. Six speed-and-pose demonstrations from 0.06 to 0.22 m/s passed contact, retention, motion, and delivery gates.

Decision: use geometry-aware selection as the deterministic baseline. Add a learned affordance score only after collecting contact outcomes.

### Gripper size and pickup integrity test

Question: does a large generic gripper create avoidable collision and visual ambiguity?

Result: the earlier oversized reference was replaced with a compact 220 mm opening tool. The stationary pickup test passed with 66.2 mm minimum approach clearance, 159.65 mm lift, 0.387 mm maximum tool-relative drift, zero unexpected contact pairs, and no workpiece teleport.

Decision: keep the compact reference and treat final pad shape, compliance, force, and cleanability as physical design work.

### Speed and orientation matrix

Question: does the pipeline work beyond one centered, slow workpiece?

Result: six video cases passed from 0.06 to 0.22 m/s, lateral starts from -60 to 50 mm, and yaw from -72 to 68 degrees. A larger 15-case accuracy matrix covered 0.06 to 0.30 m/s. All 10 core cases passed. Two of five stress cases passed the full accuracy gate. Two noisy stress cases delivered successfully but exceeded yaw-error limits. The 0.30 m/s, 80 mm offset, 85 degree case was rejected as too late before a false grasp.

Decision: keep the current core release gate and treat high-noise yaw estimation plus late extreme poses as the next algorithmic boundary.

### Replay test

Question: is a repeated seed stable enough for regression testing?

Result: exact cross-process equality did not hold. Both A and B passed bounded replay. The largest repeated placement difference was 0.067 mm. Solution B timing differed by 3.43 ms.

Decision: require bounded numerical replay, stage-hash agreement where applicable, and evidence consistency. Do not claim bit-for-bit determinism across independent Kit processes.

### Recovery tests

Question: does the system expose failures instead of hiding them?

Result: failed grasp, cutter unavailable, stale observation, emergency stop, buffer timeout, and forced slip-correction paths produced their expected terminal states and evidence.

Decision: keep recovery outcomes as first-class acceptance gates. A deliberate reject can be a correct result.

## Current result summary

- Ordinary Python suite: 226 tests passed in the last recorded complete run.
- Scene 2 accuracy matrix: 10 of 10 core cases passed.
- Stress matrix: 2 of 5 passed the full accuracy gate.
- Functional stress outcome: 4 of 5 delivered. One extreme case was rejected before grasp.
- Motion violations in the reported matrices: zero joint, velocity, and acceleration violations.
- Integrated A and B nominal cycles: contact-confirmed pickup, lift, reorientation, delivery, release, and verification passed.
- Remaining integrated blocker: live external MoveIt `FollowJointTrajectory` execution in an authorized ROS 2 and MoveIt runtime.
- Remaining physical blockers: real calibration, workpiece mechanics, gripper testing, cutter I/O, OEM limits, and safety engineering.

## Learned extension decisions, 2026-08-28

### C: rank safe candidates, do not replace safety geometry

Question: can executed Scene 2 outcomes improve grasp choice without giving a model control authority?

Result: six full A and B baseline, learned, and replay cycles passed. Success rate was 1.0. Both bounded replay gates passed. The stronger matched record used 15 fit and 10 held-out executed-candidate rows across five seed groups. Its two held-out groups had zero regret and zero selected-candidate safety violations.

Decision: accept C as an integrated simulator vertical slice. Keep the model below geometry, timing, motion, contact, PLC, verification, recovery, and audit gates. Treat the dataset and degenerate simulator outcome heads as insufficient for a broad generalization claim.

### D: refresh one committed target until no-return

Question: does bounded reactive correction improve interception under belt ramp, encoder bias, latency spike, and pose disturbance?

Result: six of eight paired comparisons improved position error. Mean intercept position improvement was 20.016 mm. Latency failed closed. A and B replay delivery deltas were 0.163 and 0.252 mm against the unchanged 0.300 mm gate.

Decision: accept D inside the simulator boundary. Retain same-track and same-grasp identity, correction caps, quantization, no-return, PLC, emergency-stop, IK, collision, and motion gates.

### E: shadow the contact segment until physical data exists

Question: can a small behavior clone be integrated without fabricating learned-contact success?

Result: five complete Scene 2 shadow cases passed. All five phases were observed. The B slip case delivered. Emergency stop rejected the release proposal. Bounded replay passed. Learned action count stayed zero.

Decision: keep E shadow-only. Do not enable bounded learned execution until representative synchronized physical force, tactile, slip, tissue-damage, and recovery data support the action and intervention envelopes.

### Hybrid ablation: compare C and D inside both A and B

Question: do C, D, or C plus D improve the complete cell when the flow, seed, product pose, belt speed, and disturbance are held constant?

Result: all eight required S0 through S3 cases passed. C alone preserved success but did not improve intercept position in the matched seed. D improved intercept position by 11.230 mm for A and 11.232 mm for B. C plus D improved it by 11.261 mm for A and 11.239 mm for B. Cycle time was unchanged within each flow. S4 was not run because E execution is blocked.

Decision: release C and D as independently gated simulator capabilities. Prefer the C plus D hybrid when the learned scorer does not abstain. Keep deterministic fallback available. Keep E outside execution.

## How future decisions will be recorded

Every new method must add four entries:

1. The failure mode it is intended to solve.
2. The smallest baseline it must beat.
3. The test distribution and frozen acceptance metrics.
4. The result, including regressions, rejected cases, and unresolved parameters.

No method moves into the active control path because it looks more sophisticated. It moves only when end-to-end evidence shows a useful improvement.
