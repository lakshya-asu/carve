# System design

## Scene 2.0 selected baseline

`SCENE_DESIGN_V2.md` defines the next physical scene gate. The selected baseline robot is the FANUC M-10iD/12 Food Grade. Its official `m10_12-14d` FANUC description will be imported and validated as a six-axis Isaac Sim articulation before replacing the current generic Cartesian reference.

The rebuilt cell will use a stationary cutter-entry tray and a side-pedestal robot layout. The baseline sensor set is one fixed global-shutter RGB camera, one registered depth stream, a conveyor encoder, an entry photoeye, robot joint feedback, bilateral jaw position and contact, a wrist force and torque reference, and PLC-style cutter and safety I/O. A wrist camera is not required in the baseline.

The official robot description provides a stronger kinematic and visual basis than the current proxy. It does not by itself establish OEM controller dynamics, collision fidelity, the exact food-grade surface package, washdown performance, food safety, or production readiness.

## Purpose

Build a complete simulation and control architecture for detecting, tracking, intercepting, grasping, reorienting, and delivering a deformable meat cut moving at a nominal 2.24 m/s.

The first customer prototype must remain deterministic, observable, testable, and recoverable. Learned components may estimate perception or grasp quality, but they do not own safety, timing, state transitions, or cutter permissives.

## Non-negotiable boundaries

1. A detector result is an observation, not a robot command.
2. All observations use exposure timestamps and a common simulation clock.
3. Conveyor encoder state is interpolated to each observation timestamp.
4. Every interception is planned in space and time.
5. A target is rejected if stale, uncertain, unreachable, unsafe, or too late.
6. The gripper model separates capture, holding, slip, and damage.
7. The cutter owns its guarded feed permissive. The robot never owns blade safety.
8. Every episode produces a structured event log and terminal reason.
9. Solution A and Solution B use the same domain contracts and scenario families.
10. Isaac Sim adapters may not contain business logic that cannot be tested without Isaac Sim.

## Current scope decision

The first simulation assumes planar product pose. The product may translate laterally and rotate in yaw, but it does not roll or flip. Full 6D reorientation remains an extension ticket and is not allowed to distort the initial design.

The first physics model uses a rigid or compliant proxy plus calibrated stochastic slip and centroid shift. It does not claim to predict tissue fracture.

The current downstream handoff is a stationary cutter-entry tray. The robot aligns the product to `cut_target_frame`, releases the grasp constraint, opens the fingers, and verifies position, yaw, timing, and near-zero product speed. Any later feed motion is owned by the cutter model and its PLC permissive.

The active product recipe selects nominal dimensions, mass, species appearance, shape family metadata, compliance metadata, tray orientation, and PLC recipe ID. The current Isaac geometry uses separate rigid meshes for the beef tapered capsule, pork elongated rounded prism, and chicken asymmetric teardrop slab. These meshes improve visual and contact diversity but remain rigid, abstract product references. They do not reproduce tissue deformation or establish physical shape fidelity.

The reference gripper has a 175 mm open gap and recipe-aware closing travel. It uses an 8 mm per-pad compliance deflection proxy. This is an uncalibrated simulation parameter, not a safe force or damage threshold.

## Coordinate frames

All transforms are explicit and timestamped.

- `world`: fixed simulation frame
- `robot_base`: robot manufacturer base frame
- `conveyor`: fixed frame attached to the conveyor structure
- `belt_surface`: belt plane with +X in belt travel direction, +Y across the belt, and +Z upward
- `camera`: optical camera frame
- `camera_calibration_target`: calibration artifact frame
- `meat_<track_id>`: estimated product pose at an observation timestamp
- `grasp_<track_id>`: selected grasp pose on the product
- `tool0`: robot tool-center-point frame
- `buffer_frame`: Solution B centering nest frame
- `cut_target_frame`: required downstream product frame
- `cutter_feed_frame`: guarded feed actuator frame

The domain core stores transforms as translation in meters plus a normalized quaternion. Planar helpers may expose X, Y, Z, and yaw, but must convert through the full transform type.

## Time model

The only authoritative clock is simulation time.

- Physics runs at a fixed configurable step, initially 240 Hz.
- Control runs at 240 Hz or an integer divisor.
- Encoder sampling runs at 1 kHz in the interface model and may be downsampled for publication.
- Camera exposure is initially 60 Hz with configurable phase offset.
- Perception delivery occurs after sampled latency, but the observation retains exposure time.
- Planning uses the current state plus observation age.
- Wall time is recorded only for performance profiling.

No domain function may call the wall clock directly. It receives time through a `Clock` interface.

## Layered architecture

### Layer 1: domain types

Pure Python dataclasses and enums define poses, twists, stamped values, detections, masks, tracks, grasp candidates, trajectories, cutter state, cell commands, events, and terminal results.

### Layer 2: deterministic models

Pure Python modules implement:

- fixed-step clock
- frame graph and transform composition
- conveyor kinematics and encoder interpolation
- scenario spawning and seeded randomization
- tracking and prediction
- interception feasibility
- grasp capture, holding, slip, and damage proxies
- cutter readiness and feed contracts
- Solution A and Solution B state machines
- event logging and metrics

These modules must run under ordinary Python without importing Isaac Sim.

### Layer 3: simulator ports

Protocols define the minimum capabilities required from a simulator:

- create and remove a product
- read and write a rigid-body pose
- apply or release a grasp constraint
- read contact and effort samples
- render or retrieve camera observations
- publish encoder state
- execute robot commands
- read cutter readiness
- step physics exactly once

### Layer 4: Isaac Sim adapter

Isaac Sim code maps USD prims, PhysX state, sensors, and articulation control into the simulator ports. It must not decide which target to pick or when the cutter is safe.

### Layer 5: perception adapters

Adapters provide three interchangeable modes:

1. simulator ground truth
2. replayed detections with recorded latency
3. live detection or segmentation inference

All modes produce the same stamped `ObjectObservation` contract.

### Active YOLO26 reference adapter

The learned reference option uses Ultralytics YOLO26 nano segmentation. The official `yolo26n-seg.pt` checkpoint is the bootstrap model. It is fine-tuned on 240 RGB frames rendered by the complete Isaac cell. The synthetic set contains 160 moving-belt views and 80 Solution B buffer views. Product pose, yaw, color, lighting, height, and robot pose are randomized. Known simulator geometry is projected through the calibrated camera only to create training labels.

Live inference receives rendered RGB only. It produces a learned instance mask and confidence. Rendered depth inside that mask provides range. Camera intrinsics and extrinsics map the mask centroid into the belt frame. Principal-axis analysis estimates planar yaw. Seeded latency, timestamp jitter, position noise, and yaw noise are then applied. Ground truth is not consulted during live inference.

Ultralytics currently serializes the dedicated one-class checkpoint label as `item`. The adapter accepts class index zero from this checkpoint and publishes the durable domain class `meat_reference`. It rejects every other class. The checkpoint SHA-256 is recorded in model identity, metrics, and the model card.

Isaac Sim 6.0.1 bundles TorchVision without CUDA NMS. Training remains on the GPU. Final validation and live NMS run on CPU. Measured synthetic holdout inference was about 25 ms per 640-pixel image on this workstation. This is a compatibility choice, not a physical latency measurement.

## Core message contracts

### Object observation

- track hint or detection identifier
- exposure timestamp
- class and confidence
- bounding box
- optional instance mask reference
- belt-plane pose estimate
- covariance or uncertainty bounds
- visible fraction and geometry quality

### Object track

- stable track ID
- last observation timestamp
- filtered planar pose
- linear and angular velocity
- covariance
- age, hit count, and missed count
- predicted pose function
- lifecycle state

### Interception plan

- track ID and source observation timestamp
- grasp pose relative to product
- interception pose in `world`
- interception time
- required TCP velocity at contact
- pregrasp trajectory
- commit time and abort deadline
- uncertainty and reachability margins
- validation decision and rejection reasons

### Grasp state

- commanded opening
- measured or simulated force
- contact count and locations
- pressure proxy
- friction margin
- attached state
- estimated slip transform
- damage flag

### Cutter contract

- ready state
- guarded state
- target frame
- feed speed
- phase or time window when applicable
- recipe identifier
- permissive sequence number
- fault reason

## Cell state machines

### Shared acquisition states

`IDLE -> ACQUIRE -> TRACK -> PLAN -> WAIT_COMMIT -> INTERCEPT -> VERIFY_GRASP`

Any state may transition to `REJECT`, `RECOVER`, or `SAFE_STOP` through an explicit reason.

### Solution A states

`VERIFY_GRASP -> TRANSFER_DIRECT -> WAIT_CUTTER_PERMISSIVE -> ALIGN_DIRECT -> FEED_DIRECT -> VERIFY_DELIVERY -> RECOVER`

The direct solution has a bounded hold time. It rejects or diverts if cutter readiness cannot be guaranteed before commitment.

### Solution B states

`VERIFY_GRASP -> TRANSFER_BUFFER -> RELEASE_BUFFER -> SETTLE -> REOBSERVE_BUFFER -> ALIGN_BUFFER -> WAIT_CUTTER_PERMISSIVE -> FEED_BUFFER -> VERIFY_DELIVERY -> RECOVER`

The buffer has capacity, occupancy, maximum hold time, and sanitation-state contracts.

## Interception algorithm

1. Transform the latest observation to `belt_surface` at exposure time.
2. Interpolate encoder position and robot state to exposure time.
3. Update the track state and covariance.
4. Sample candidate interception times inside the configured pick window.
5. Predict product pose and uncertainty at each candidate time.
6. Generate mask-aware grasp candidates with boundary clearance.
7. Reject candidates outside position, angle, velocity, uncertainty, collision, or timing limits.
8. Rank the remaining candidates by time margin, grasp margin, robot cost, and downstream feasibility.
9. Publish a plan with a commit time and abort deadline.
10. Continue bounded corrections until the commit boundary.

The initial robot-time estimator is a conservative acceleration-limited bound. It must be replaced or calibrated using the selected OEM robot and controller.

## Grasp model

The first model evaluates four independent conditions.

### Capture

The closing footprint must contain the predicted grasp region after position, angle, and timing uncertainty are applied.

### Holding

Available tangential force must exceed gravity and planned inertial load with a configurable safety factor.

### Damage

Peak force and contact-pressure proxies must remain below recipe limits measured from product trials.

### Slip

Slip is a state estimate, not only a random failure. It produces a transform between the commanded grasp frame and the observed product frame. Solution B may correct this during buffer re-observation.

## Scenario model

Every scenario has a version, family, seed, and parameter record. Scenario families cover:

- nominal operation
- speed and acceleration changes
- close spacing
- lateral and yaw extremes
- camera latency and timestamp jitter
- calibration drift
- encoder noise and delay
- partial visibility and overlap
- wet-friction variation
- gripper-force variation
- post-grasp slip
- cutter unavailability
- robot tracking error
- lighting and appearance changes

Training, validation, and test splits operate on complete scenario families and recordings.

## Safety model

The simulated safety supervisor is deterministic and separate from the task controller. It checks:

- robot and tool workspace limits
- blade exclusion zone
- target age and command age
- trajectory validity period
- speed and acceleration limits
- minimum product spacing
- buffer occupancy
- cutter permissive sequence
- unexpected contact
- controller heartbeat

The simulator may test safety logic, but it cannot certify a physical system.

## Logging and replay

Each run writes:

- immutable run configuration
- scenario family and seed
- dependency versions
- timestamped state transitions
- observations and tracks
- plans and rejection reasons
- gripper force, pressure, and slip estimates
- cutter states and permissives
- terminal result and metrics

Replay must be possible from the logged observations, encoder values, robot states, and cutter signals without rerendering images.

## Acceptance gates

### Stage 1

Isaac compatibility, headless startup, fixed-step clock, and stage-save smoke tests pass.

### Stage 2

All required prims and frames exist, transforms validate, and the stage reloads identically.

### Stage 3

At 2.24 m/s, simulated and encoder-predicted travel agree within configured numerical tolerance over held-out seeds.

### Stage 4

Ground-truth tracking and prediction errors remain within deterministic unit-test bounds, including delayed observations.

### Stage 5

The selected robot reaches the pick window with limits enforced and verified trajectory timing.

### Stage 6

Capture, hold, damage, and slip outcomes respond monotonically to force, friction, acceleration, and error sweeps.

### Stages 7 and 8

Each architecture completes nominal episodes and produces correct failure reasons for every injected failure family.

### Stage 9

Detection and segmentation are compared on held-out recording and scenario families using both model and full-cell metrics.

### Stage 10

The report distinguishes simulated results, calibrated estimates, and unresolved physical risks.

## Integrated Isaac implementation

The integrated acceptance path is `isaac_sim/run_cell.py`. Simulator-independent proxy code remains useful for screening, but it cannot satisfy an integrated milestone.

### Saved cell

The builder creates a visible USD stage with:

- a rigid conveyor and dynamic workpieces
- a generic six-joint Cartesian articulation with X, Y, Z, yaw, and two finger joints
- a two-finger compliant gripper reference with finite drive effort
- overhead and wrist camera mounts with rendered RGB and depth
- calibration target, `world`, `robot_base`, `conveyor`, `belt_surface`, `camera`, `tool0`, `cut_target_frame`, and cutter feed frames
- guards, reject location, lighting, and reference cutter or feed geometry
- a Solution B centering buffer and buffer frame
- simulated PLC attributes for conveyor speed, recipe, cutter state, phase, permissive, faults, emergency stop, and result acknowledgment

The product is selected from the versioned catalog in `configs/product_recipes.yaml`. The initial integrated recipes are beef center-cut tenderloin, pork boneless loin, and chicken breast fillet. Recipe selection changes nominal workpiece dimensions, mass, color, compliance metadata, cutter-entry orientation metadata, PLC recipe ID, traces, and metrics. The current geometry uses distinct rigid recipe meshes. Shape families and compression values remain sensitivity inputs, not calibrated tissue models.

The robot, gripper, meat, buffer, and cutter are labeled reference assets. They are not OEM models.

### Motion and interception

All accepted robot motion is sent through the Isaac articulation controller at a fixed 240 Hz physics rate. Quintic trajectories are sampled before execution. Joint position, velocity, and acceleration limits are checked for every sample. The TCP is checked against the validated cell envelope and guarded cutter volume. The X axis limit is 4 m/s and 12 m/s2. Other prismatic axes use 4 m/s and 8 m/s2. The wrist and finger axes use their documented limits.

The interception trajectory arrives at a predicted product pose and matches the 2.24 m/s belt velocity. Grasp closure continues at belt speed. A bounded braking move stops the conveyor-relative motion before the arm lifts. Recovery uses the same bounded braking behavior before moving above guards or reject geometry.

The hardened moving grasp uses 25 percent jaw pre-shaping during approach. Final closure is followed by a 125 ms belt-speed-matched contact settle that starts from measured Isaac joint velocities. The intercept window is 1.37 to 1.49 m. This leaves enough distance for a monotonic 300 mm braking segment before the cutter envelope. The preflight still checks every trajectory sample against the articulation velocity, acceleration, joint, and TCP-envelope limits.

Product alignment at the cutter uses the measured product-to-TCP transform. A target that falls just beyond the validated TCP envelope may be projected onto the boundary only when the three-dimensional projection is no more than half of the 55 mm product-placement tolerance. A larger request is infeasible and fails before execution. The final product measurement, not the requested TCP pose, determines delivery acceptance.

This is collision-aware envelope checking, not a general motion planner. An OEM deployment must replace it with validated robot geometry and collision models.

### Rendered perception

The primary integrated interface uses actual overhead-camera RGB and depth. The default replaceable color and depth model provides a deterministic baseline. The optional trained YOLO26 adapter produces a learned instance mask from RGB, then uses depth and calibration for pose. Both produce planar pose, confidence, geometry quality, visible fraction, and exposure and delivery timestamps. Configurable noise and latency are injected. The tracker assigns a stable identity, fuses encoder velocity, and publishes a predicted intercept pose and time using calibrated camera-to-world assumptions.

Ground truth is available only as a baseline and test oracle. It is not presented as learned perception and is not the primary integrated result.

### Contact, compliance, and slip

Both finger links use PhysX contact reporting and finite-effort prismatic drives. A grasp is accepted only after both fingers report recent product contact. The active fixed joint then approximates a stable compliant hold. Finger drive effort is the force proxy. Solution B releases onto the physical buffer, renders a new observation, estimates a planar slip transform, corrects the pose, and requires new two-finger contact before transport.

The Solution B tray centre and `buffer_frame` are at `(1.80, -0.55, 0.14)` m. Buffer detections are limited to the calibrated tray region, require confidence and visible fraction of at least 0.10, and are associated by distance to the tray target. A 150 ms stationary compliant-drive settle follows buffer jaw closure. The transport constraint is created only after recent contact is present on both jaws.

The workpiece is a rigid body. Deformation, tissue damage, wet adhesion, and true pressure distribution are not modeled. Contact impulses and the 50 N nominal force attribute are uncalibrated. The fixed joint is an approximation and does not prove that a physical gripper will hold the product.

### Integrated state and I/O sequence

The runner exercises simulator state through observation, acquire, track, predict, reserve, approach, intercept, confirm grasp, lift or stabilize, align to `cut_target_frame`, place or feed, verify, retract, and recover. Solution A checks the cutter permissive before direct transfer. Solution B manages buffer occupancy, hold time, re-observation, correction, regrasp, and feed. Injected failed grasps, cutter unavailability, and buffer timeout produce explicit traces and physical recovery motion.

### Integrated acceptance gate

The integrated milestone is complete only when both A and B have at least one cycle that uses rendered camera data, tracking, timed articulation control, two-finger contact, a simulated hold, reorientation, downstream delivery, and verification. The four-cycle gate also requires a failed contact grasp, downstream recovery, stage contents, RGB and depth publication, calibration consistency, controller commands, alignment and timing limits, zero unexpected collisions, zero joint-limit violations, and deterministic replay.

### Hardening profile and artifact audit

The accepted four-cycle baseline is retained for quick regression. A separate six-cycle hardening profile adds emergency-stop and stale-observation cases to nominal, failed-grasp, and downstream-unavailable coverage. Solution A injects cutter unavailability. Solution B injects maximum buffer hold timeout. Every hardening cycle records its profile, scenario mode, simulator dependency, state transitions, PLC changes, articulation commands, sensor observations, terminal reason, and replay result.

An emergency stop changes the simulated PLC state, stops the conveyor, moves the controller to `SAFE_STOP`, and sends a limit-clamped measured joint hold command through the articulation controller. The runner measures maximum joint drift during the hold, clears the injected condition, and performs physical recovery to the known idle pose. This is a logical and dynamic simulator test. It is not a safety-rated stop validation.

A stale-observation case renders and tracks a workpiece, advances the fixed physics clock until the observation exceeds the configured age, and confirms that the planner rejects it before commitment. The resulting reject or recovery motion still executes through the simulator.

The artifact auditor independently reads each saved USDA, rendered RGB file, depth array, JSON Lines trace, and metrics file. It checks required stage contents, reference-asset labeling, PhysX and articulation APIs, sensor dimensions and nonempty pixels, calibrated transforms, monotonic simulation timestamps, rendered-mask observations, contact and controller evidence, alignment and timing gates, PLC transitions, failure-specific recovery, collision and joint limits, and deterministic replay. The audit is part of both the complete suite and the hardening launcher.

The PhysX angular joint velocity attribute is authored in degrees per second, while the domain limit remains radians per second. The stage builder performs the unit conversion. The active grasp joint uses the measured wrist-to-product transform as its local body transform. This avoids an artificial constraint-frame snap while retaining the documented fixed-joint hold approximation.

Hardening outputs use a caller-selected project-relative output root. This permits several seed batches to coexist without replacing baseline artifacts. The hardening launcher runs A and B sequentially to bound GPU use, verifies a clean Isaac process state, validates each machine-readable result, closes batch-owned orphan processes, and permits resume only for a matching seed, cycle count, profile, and passing metrics file.

## Current authorization and safety boundary

The workstation user accepted the NVIDIA EULA and explicitly authorized headless Isaac Sim startup and testing for this build. This authorization does not permit system software installation, Windows setting changes, unrelated project changes, OEM claims, or physical safety claims.

The simulator may demonstrate software behavior under its assumptions. It cannot validate food safety, real-cell safety, OEM fidelity, physical accuracy, or production readiness.

## Scene 2.0 FANUC cell

Scene 2.0 is built by `isaac_sim/scene2_builder.py` and exercised by `isaac_sim/run_scene2.py`. It references the project-local USD conversion of the official FANUC `m10_12_14d` description. The articulation has joints J1 through J6 under one Isaac articulation root. The cell builder adds the conveyor, recipe-shaped workpieces, gripper reference, fixed RGBD camera, photoeye, cutter-entry tray, reject bin, guards, PLC attributes, lighting, and named frames.

The Scene 2.0 gripper is now an actuated part of the FANUC articulation. It adds two prismatic jaw joints named `finger_left` and `finger_right`. Each jaw has collision geometry, a contact sensor, a 0.25 m/s velocity limit, a 1.5 m/s2 acceleration metadata limit, a 70 N finite drive limit, and a 6,250 N/m series-compliance reference. The clear inner opening is 270 mm. The normal-force setpoint is 50 N per jaw. The 0.16 mm/N compliance and friction values are uncalibrated simulation assumptions.

The compliance gate moves the robot to a clear test pose, places a 2.75 kg pork-loin reference between the jaws, commands both jaws through the Isaac articulation controller, and requires bilateral product contact. It measures jaw target error as elastic deflection and force proxy. It then releases the temporary positioning fixture, checks slip under gravity, opens the jaws to create a grasp-loss event, confirms product displacement, restores the workpiece, and verifies open recovery. No fixed grasp constraint is used during this gate.

The current Scene 2.0 gate proves stage construction, six-axis controller execution, imported limits, bounded velocity and acceleration commands, rendered RGB and depth, stage save, and independent reload. A second gate, `validate_scene2_ros.ps1`, runs the same articulation and overhead RGBD sensor through ROS 2 Humble DDS. Isaac publishes `/clock`, measured J1 through J6 state, RGB, depth, and camera calibration. It subscribes to a strict six-joint command topic and applies accepted positions through the actual articulation controller.

The ROS 2 command and sensor contract is in `configs/ros2_interface.yaml`. The tested bridge is in `isaac_sim/scene2_ros_bridge.py`. MoveIt will run outside Isaac. It will use the FANUC description, KDL inverse kinematics, OMPL RRTConnect, and a standard `FollowJointTrajectory` action. A thin trajectory action bridge will validate and sample the trajectory against simulation time, then publish checked six-joint commands to Isaac. This keeps physics, contacts, rendering, and actuator execution inside Isaac while leaving planning replaceable.

The ROS 2 self-test passed twice with identical ROS metrics and saved-stage hashes. Each run published 720 clock messages, 180 joint states, 45 RGB frames, 45 depth frames, and 45 camera calibration messages. The live probe received every stream type. A partial command was rejected. A valid command moved the FANUC articulation with a maximum final joint error of 0.000836 rad.

This does not yet prove MoveIt planning or the complete task sequence on this arm. ROS 2 and MoveIt are not installed in WSL 2 on this workstation. The existing integrated YOLO and state-machine evidence still belongs to Scene 1. T016 connects camera perception, tracking, prediction, collision-aware inverse kinematics, interception, transport, reorientation, tray delivery, and recovery to the FANUC articulation. The Scene 2.0 compliant contact mechanism is complete as a focused simulation gate, but it is not physically calibrated.
