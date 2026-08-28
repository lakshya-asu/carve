# Generalized manipulation and skill-learning research

Date: 27 August 2026

Status: design research plus simulator implementation record. C and D now pass integrated Scene 2 gates. E passes replay and shadow evaluation only. Bounded learned execution is blocked on representative physical contact data.

## Research question

How should CARVE grow from a deterministic conveyor interception demonstration into a reusable handling system for new product cuts, shapes, orientations, line speeds, and grasp conditions without adding learning where ordinary geometry and control already work?

## Direct answer

The next useful learned component is a grasp-affordance scorer. It should rank several physically feasible grasp candidates from RGBD geometry and measured outcomes. It should not replace tracking, timed interception, collision checks, PLC permissives, or the cycle supervisor.

After that, add closed-loop reactive updates during approach. A full learned manipulation skill should be the third stage, first in shadow mode and then inside a bounded action interface. The first two stages and the E shadow slice were completed on 2026-08-28. A large vision-language-action model is not the first baseline for one repeated product recipe.

## Implemented simulator outcome, 2026-08-28

- C ranks several geometry-safe RGBD grasp candidates with a small auditable model. Six full A and B baseline, learned, and replay cycles passed. A stronger record contains 25 separately executed candidate trials, with 15 fit and 10 held-out rows. Its two held-out groups had zero selection regret, but several outcome heads remain degenerate simulator proxies.
- D keeps the same track and grasp identity while applying capped, quantized corrections until no-return. Eight paired disturbance comparisons passed. Mean intercept position error improved by 20.016 mm.
- E fits a five-phase behavior clone from complete Scene 2 demonstrations and records proposals inside live A and B cycles. It is shadow-only. Five cases passed, including slip correction and emergency stop, with zero learned commands.
- The deterministic freshness, reach, timing, joint, velocity, acceleration, collision, PLC, emergency-stop, verification, recovery, and audit gates remain authoritative for every route.
- Physical workpiece, force, tactile, slip, tissue-damage, and recovery measurements remain the exact gate before E can execute learned actions.
- The final matched hybrid matrix passed all eight required A/B S0 through S3 cases. D and C plus D improved intercept position by about 11.23 mm in both flows. C alone preserved delivery without improving interception in that seed. S4 remained not run.

## What “learning a grasping skill” means here

A grasp skill is not one fixed point. It is a policy that maps the current observation and task context to a set of grasp parameters and a confidence estimate.

For CARVE, a practical skill input is:

- segmented RGBD crop or metric point cloud
- product recipe and expected cut family
- estimated product pose and velocity
- mask boundary, surface normal, local thickness, and belt clearance
- gripper geometry and opening range
- robot reachability, approach clearance, and remaining intercept time
- recent contact, force, and slip history for the same product family

The useful output is:

- several grasp candidates, not only one
- grasp point and approach pose
- jaw axis and opening
- predicted contact quality and slip risk
- uncertainty or abstention score
- a fallback candidate or reject decision

The safety boundary remains deterministic. Candidate grasps are filtered for timing, collision, joint limits, workspace, freshness, recipe limits, and machine permissives before motion.

## Solution C: learned grasp-affordance scoring

### Method

Keep YOLO segmentation, metric depth, tracking, timed interception, Lula or MoveIt planning, the state machine, and PLC gates. Replace the single geometric grasp score with a learned ranking model.

The first version should stay planar because the workpiece is assumed to remain on the belt. Generate 16 to 64 mask-interior candidates. For each candidate, compute a local feature crop and explicit geometry. Predict:

- probability of bilateral contact
- probability of retained lift
- expected slip magnitude
- excessive-force or poor-clearance risk
- expected downstream orientation error

The final score can be written as:

```text
score = P(contact) * P(retain) * P(deliver)
        - lambda_slip * E(slip)
        - lambda_force * P(excessive_contact)
        - lambda_time * intercept_cost
```

The model proposes. The existing planner still filters and executes.

### Suitable model families

- A small RGBD or point-cloud encoder followed by a candidate scorer.
- A GQ-CNN style depth grasp-quality network for planar parallel-jaw grasps.
- A VGN or Contact-GraspNet style 3D proposal model if future workpieces require non-planar approach poses.
- A graspness-style dense map when the main question is which visible regions are graspable.
- AnyGrasp or target-referenced grasp tracking as an experimental benchmark for dynamic 6D scenes.

Dex-Net showed the value of training a grasp-quality model from synthetic depth and analytic grasp metrics. GraspNet-1Billion established dense 6D annotations and a common evaluation scheme. Contact-GraspNet anchors candidates on observed point-cloud contacts. VGN produces grasp quality, orientation, and opening width over a TSDF volume. Graspness explicitly learns which points deserve grasp proposals. AnyGrasp adds temporal consistency and dynamic grasp tracking. These methods address general rigid-object grasping, so their reported results do not transfer directly to raw meat.

### Training data

Use the current deterministic pipeline to generate labeled trials. Each trial records the observation and every candidate, followed by:

- bilateral contact
- lift distance
- maximum product-to-tool displacement
- measured slip
- jaw position and effort proxy
- unexpected contact
- delivery error
- terminal reason

Train first on synthetic data. Then fine-tune and calibrate on physical workpiece trials. Split by product batch, cut family, line, day, and capture session. Adjacent frames from one cycle must stay in one partition.

### Why this is the best next solution

- It targets a measured weakness: grasp quality changes with shape, yaw, boundary clearance, and slip.
- It reuses the current simulator, interfaces, logs, and acceptance gates.
- It needs much less data than an end-to-end manipulation policy.
- It remains interpretable because the chosen candidate, alternatives, score terms, and rejection reason can be displayed.
- It generalizes across cuts by learning local contact geometry while retaining recipe-specific constraints.

### A/B test

Baseline C0: current mask-clearance point and principal-axis jaw direction.

Candidate C1: learned candidate scorer with the same perception, planner, and controller.

Frozen test slices:

- beef, pork, and chicken reference shapes
- held-out shape parameters and textures
- 0.06 to 0.30 m/s simulated belt speed
- longitudinal, diagonal, and transverse yaw
- nominal and high-noise depth
- friction, compliance, and latency perturbations
- occlusion and partial visibility

Primary metrics:

- contact-confirmed pickup rate
- retained-lift rate
- slip rate and magnitude
- excessive-contact proxy rate
- delivery success
- abstention calibration
- p95 inference latency

Promotion gate: improve retained-lift or delivery success on held-out stress slices without increasing motion violations, unsafe commitments, or p95 cycle time beyond the agreed budget.

### Main risks

- Synthetic contact labels can encode the wrong physics.
- A model may learn visual texture shortcuts instead of contact geometry.
- A high score can be poorly calibrated on a new cut.
- A 6D grasp network may add complexity that the planar cell does not need.

Mitigation: retain the geometric baseline, log candidate features, use uncertainty and abstention, and require real trials before replacing the baseline.

## Solution D: closed-loop reactive interception

### Method

The current system predicts a timed intercept, commits, and executes a bounded trajectory. The reactive extension continues to update the target during the approach until a defined no-return time.

At each camera update:

1. Refresh the workpiece or target-grasp track.
2. Predict the pose at the remaining contact time.
3. Compute a small Cartesian correction.
4. Send it through MoveIt Servo, RMPflow, or a receding-horizon trajectory optimizer.
5. Scale or stop motion near collision, joint limits, singularity, stale data, or an excessive correction.

Target-referenced reactive grasping tracks a chosen grasp across observations instead of selecting an unrelated grasp in each frame. MoveIt Servo supports joint and velocity limits, singularity checks, collision checks, and smoothing. NVIDIA cuMotion exposes collision-aware IK, graph planning, trajectory optimization, and reactive RMPflow. These are relevant components, but the selected runtime must be benchmarked on the actual controller and GPU.

### Why it helps

- Corrects encoder drift, product rotation, calibration bias, and latency changes before contact.
- Maintains semantic consistency by following the same product and the same intended contact region.
- Works with either the geometric or learned grasp scorer.
- Generalizes to new conveyor speeds without retraining the entire manipulation task.

### A/B test

Baseline D0: current predict-once trajectory after commit.

Candidate D1: target updates until the no-return boundary, followed by the same contact and delivery logic.

Test perturbations:

- belt speed ramps
- encoder bias and delay
- yaw-rate changes
- camera latency spikes
- small external product disturbances
- moving obstacles outside the guarded pick region

Primary metrics:

- intercept position and timing error
- correction magnitude and count
- stale-update rejection
- collision-margin minimum
- singularity and joint-limit events
- grasp and delivery success
- p95 control latency

Promotion gate: reduce intercept error under dynamic perturbations while preserving minimum clearance, bounded corrections, and deterministic stop behavior.

### Main risks

- Noisy pose updates can cause chasing or oscillation.
- Servo corrections can consume collision margin.
- A slow vision or planning loop can make corrections stale.
- A learned grasp tracker can jump to another visible product.

Mitigation: low-pass state estimates, cap correction rate and magnitude, retain a no-return boundary, enforce grasp identity, and fall back to the current committed trajectory or reject.

## Solution E: bounded learned manipulation skill

### Method

Learn the difficult contact-rich segment from demonstrations while preserving the explicit supervisor. The learned skill receives a short history of RGBD features, robot state, gripper state, product track, and target error. It outputs a short action chunk inside a bounded task-space interface.

The state machine still chooses among explicit skills:

- approach moving grasp
- close and stabilize
- lift and correct slip
- align to target
- place and release
- recover or reject

The low-level controller still enforces joint, velocity, acceleration, workspace, collision, force, freshness, and emergency-stop limits.

### Candidate learning methods

Behavior cloning is the simplest first baseline. Robomimic provides a strong experimental framework for comparing offline demonstration-learning methods. ACT predicts action chunks and reduces the effective decision horizon. Diffusion Policy represents multimodal action sequences and uses receding-horizon execution. DAgger addresses covariate shift by collecting expert labels on states visited by the learned policy. Residual reinforcement learning keeps a conventional controller and learns only the correction needed for contact and friction. A generalist initialization such as Octo or OpenVLA can be tested later if the cell becomes multi-product and language-conditioned.

### Data collection

Record synchronized:

- overhead and optional wrist RGBD
- segmentation and track state
- joint position and velocity
- commanded and measured tool pose
- jaw position, effort, contact, and tactile features
- conveyor encoder and PLC state
- action chunks
- operator interventions
- stage outcome and recovery reason

Collect successful cycles, near failures, corrected slips, rejects, and recovery demonstrations. Use DAgger-like intervention only after the baseline can run safely in shadow or supervised mode.

### Why this is third, not first

- It can learn contact timing and correction that are hard to model.
- It can share a skill across shape families when inputs and action spaces are normalized.
- It requires more representative physical data and more careful failure analysis.
- Its behavior is harder to inspect than a candidate grasp scorer.
- The current simulator does not model real tissue, wet friction, or gripper pressure well enough to justify direct policy transfer.

### A/B test

Baseline E0: deterministic trajectory and contact state machine.

Candidate E1: behavior-cloned action-chunk policy in shadow mode.

Candidate E2: learned policy controls only the close, stabilize, and slip-correction segment.

Candidate E3: residual policy adds bounded corrections to the deterministic controller.

Primary metrics:

- task success with Wilson confidence intervals
- damage or excessive-force proxy
- slip recovery rate
- action smoothness and controller intervention rate
- completion time
- out-of-distribution abstention
- failure category by product, speed, pose, lighting, and mechanics

Promotion sequence:

1. Offline replay parity.
2. Simulation shadow mode.
3. Simulation bounded-action control.
4. Hardware-in-the-loop without product.
5. Supervised low-speed physical trials.
6. Held-out workpiece and speed trials.
7. Bounded production canary only after safety engineering and customer acceptance criteria exist.

### Generalist and VLA option

Octo and OpenVLA show that large policies can be adapted across robot platforms and observation or action spaces. Their value is strongest when the task set, embodiments, or language instructions vary. CARVE currently has one tightly specified physical workflow. A 7B-parameter VLA inside the time-critical path would add latency, data, compute, and validation burden without first proving that it solves the dominant failure.

A reasonable later experiment is to use a generalist model for high-level skill selection or as a pretrained visual representation. It should not command the hard real-time servo loop or own PLC permissives.

## Comparison of all five routes

| Route | Learned scope | Data need | Added runtime complexity | Generalization potential | Current recommendation |
| --- | --- | ---: | ---: | ---: | --- |
| A. Direct deterministic | YOLO segmentation only | Low | Low | Medium within calibrated envelope | Keep as fastest baseline. |
| B. Buffered deterministic | YOLO segmentation only | Low | Medium | Medium with second observation | Keep as correction and recovery route. |
| C. Learned grasp scorer | Contact and grasp quality | Medium | Medium | High across related cuts and grasp conditions | Build next. |
| D. Reactive intercept | Optional learned grasp tracking | Medium | Medium to high | High across changing motion | Build after live MoveIt or reactive controller commissioning. |
| E. Learned manipulation skill | Contact-rich action chunks or residuals | High | High | Potentially high with sufficient data | Research after physical data collection. |

## Recommended balanced architecture

```text
YOLO26 mask and RGBD geometry
        |
        v
learned grasp candidate scorer  <- new first learning step
        |
        v
deterministic tracking and timed reservation
        |
        v
closed-loop target correction   <- second extension
        |
        v
MoveIt or cuMotion limits, collision, and trajectory control
        |
        v
Isaac or robot articulation and compliant gripper
        |
        v
bounded contact skill or residual policy  <- third extension
        |
        v
deterministic PLC gates, verification, recovery, and audit
```

This gives learning responsibility for uncertain contact and adaptation. It keeps known geometry, timing, machine coordination, and safety boundaries explicit.

## Generalization plan

### Product representation

Represent each product by measurable features instead of only a species label:

- length, width, thickness, mass, and aspect ratio
- visible contour and local curvature
- surface normal and depth quality
- estimated compliance class
- wetness or friction proxy when a sensor can measure it
- allowed contact pressure and damage threshold after physical testing
- required final orientation and support geometry

The recipe remains useful, but it becomes a prior rather than a fixed grasp script.

### Data strategy

1. Generate broad synthetic RGBD and geometry variation in Isaac Sim.
2. Train perception and a preliminary grasp score.
3. Collect a small real calibration and workpiece set.
4. Measure the simulation-to-real gap by slice.
5. Tune simulation parameter distributions using real evidence.
6. Fine-tune perception and grasp scoring on real trials.
7. Add demonstrations only for failure segments that geometry does not solve.
8. Keep a frozen cross-batch and cross-day test set.

Domain randomization is useful for appearance, latency, camera noise, product pose, friction, mass, compliance, and actuator response. It does not make an inaccurate physics model true. SimOpt-style parameter adaptation uses real rollouts to update the simulation distribution and is a better later step once physical measurements exist.

### Evaluation strategy

Report model metrics and cell metrics together.

Model level:

- mask precision, recall, mAP, and calibration
- pose and yaw error
- grasp-ranking top-k accuracy
- slip-risk calibration
- p50 and p95 latency

Cell level:

- attempted, rejected, and completed cycles
- contact-confirmed pickup and retained lift
- placement and timing error
- product damage or pressure result after a real measurement exists
- recovery success and time
- throughput and uptime
- performance by product, speed, yaw, position, lighting, and batch

Use multiple seeds in simulation and repeated physical trials. Report confidence intervals. A better offline score does not justify promotion if full-cell success, timing, or recovery becomes worse.

## Research conclusions

1. Yes, grasping can be learned as a reusable skill. The most practical first form is learned candidate ranking, not an end-to-end robot policy.
2. Dynamic interception benefits from closed-loop grasp tracking and bounded target updates. This is a control and perception improvement, not necessarily a large learning problem.
3. Imitation learning and residual RL are credible for contact-rich stabilization and slip correction after synchronized physical demonstrations exist.
4. Generalist policies and VLAs are useful research baselines for broader task sets. They are not the simplest answer for the current one-month cell.
5. The strongest architecture is hybrid: learned perception and contact adaptation above a deterministic motion, machine, verification, and safety boundary.

## Primary sources and official references

### Grasp proposals and affordances

1. [Dex-Net project and GQ-CNN grasp-quality research](https://berkeleyautomation.github.io/dex-net/)
2. [GraspNet-1Billion, CVPR 2020](https://openaccess.thecvf.com/content_CVPR_2020/html/Fang_GraspNet-1Billion_A_Large-Scale_Benchmark_for_General_Object_Grasping_CVPR_2020_paper.html)
3. [6-DOF GraspNet, ICCV 2019](https://openaccess.thecvf.com/content_ICCV_2019/html/Mousavian_6-DOF_GraspNet_Variational_Grasp_Generation_for_Object_Manipulation_ICCV_2019_paper.html)
4. [Contact-GraspNet, NVIDIA Research](https://research.nvidia.com/publication/2021-03_contact-graspnet-efficient-6-dof-grasp-generation-cluttered-scenes)
5. [Volumetric Grasping Network](https://arxiv.org/abs/2101.01132)
6. [Graspness Discovery, ICCV 2021](https://openaccess.thecvf.com/content/ICCV2021/html/Wang_Graspness_Discovery_in_Clutters_for_Fast_and_Accurate_Grasp_Detection_ICCV_2021_paper.html)
7. [AnyGrasp](https://arxiv.org/abs/2212.08333)
8. [Target-Referenced Reactive Grasping, CVPR 2023](https://openaccess.thecvf.com/content/CVPR2023/html/Liu_Target-Referenced_Reactive_Grasping_for_Dynamic_Objects_CVPR_2023_paper.html)
9. [Generalizing 6-DoF Grasp Detection via Domain Prior Knowledge, CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/html/Ma_Generalizing_6-DoF_Grasp_Detection_via_Domain_Prior_Knowledge_CVPR_2024_paper.html)

### Demonstration and policy learning

10. [Robomimic](https://robomimic.github.io/)
11. [Diffusion Policy](https://diffusion-policy.cs.columbia.edu/)
12. [Action Chunking with Transformers paper](https://arxiv.org/abs/2304.13705)
13. [DAgger original paper](https://proceedings.mlr.press/v15/ross11a.html)
14. [Residual Reinforcement Learning for Robot Control](https://arxiv.org/abs/1812.03201)
15. [Learning to Manipulate Deformable Objects without Demonstrations, RSS 2020](https://www.roboticsproceedings.org/rss16/p065.html)
16. [Robotic Handling of Compliant Food Objects by Robust Learning from Demonstration](https://arxiv.org/abs/2309.12856)

### Generalist robot policies

17. [Open X-Embodiment and RT-X](https://robotic-transformer-x.github.io/)
18. [Octo](https://octo-models.github.io/)
19. [OpenVLA](https://openvla.github.io/)
20. [pi0 technical report](https://www.physicalintelligence.company/download/pi0.pdf)

### Simulation, motion, and transfer

21. [Isaac Lab official documentation](https://docs.isaacsim.omniverse.nvidia.com/latest/isaac_lab_tutorials/index.html)
22. [Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World](https://arxiv.org/abs/1703.06907)
23. [SimOpt](https://arxiv.org/abs/1810.05687)
24. [MoveIt Servo](https://moveit.picknik.ai/main/doc/examples/realtime_servo/realtime_servo_tutorial.html)
25. [MoveIt planning and collision concepts](https://moveit.ai/documentation/concepts/)
26. [NVIDIA cuMotion](https://nvidia-isaac.github.io/cumotion/index.html)
27. [Ultralytics YOLO26](https://docs.ultralytics.com/models/yolo26)
28. [Ultralytics instance segmentation](https://docs.ultralytics.com/tasks/segment)

### Food handling and tactile feedback

29. [Challenges and Opportunities in Robotic Food Handling](https://pmc.ncbi.nlm.nih.gov/articles/PMC8794010/)
30. [Low Damage Grasping of Fruit, Vegetable and Meat Raw Materials](https://pmc.ncbi.nlm.nih.gov/articles/PMC10528682/)
31. [Sensor-Enhanced Smart Gripper Development for Automated Meat Processing](https://pmc.ncbi.nlm.nih.gov/articles/PMC11281046/)
32. [Measurement of Shear and Slip with a GelSight Tactile Sensor](https://people.csail.mit.edu/yuan_wz/GelSight1/ICRA15_2740_FI.pdf)
33. [Learning to Detect Slip through Tactile Estimation](https://arxiv.org/abs/2303.00935)

## Rerun inputs

```text
research depth: exhaustive
date: 2026-08-27
queries:
  - learned robot grasp affordance point cloud parallel jaw
  - GraspNet benchmark grasp quality and generalization
  - Contact-GraspNet and VGN closed-loop grasp generation
  - AnyGrasp dynamic grasp tracking
  - reactive grasping moving objects conveyor
  - robot imitation learning action chunking
  - Diffusion Policy receding horizon manipulation
  - DAgger covariate shift robot demonstrations
  - residual reinforcement learning contact control
  - deformable object manipulation learning
  - compliant food handling robot learning
  - tactile slip detection robot grasp
  - Isaac Lab imitation learning and domain randomization
  - sim-to-real domain randomization and SimOpt
  - MoveIt Servo and cuMotion reactive control
  - Octo, OpenVLA, Open X-Embodiment, and pi0
  - YOLO26 instance segmentation and deployment
source rule: primary papers, official project pages, and official documentation
Firecrawl status: command-line client unavailable, web research fallback used
```
