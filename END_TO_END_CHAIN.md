# CARVE end-to-end chain

Date: 27 August 2026

## The problem in one sentence

CARVE must see a product moving on a conveyor, estimate where it will be, grasp it without relying on hidden simulator state, turn it to the required orientation, and release it on a stationary cutter-entry tray only when the downstream machine allows the transfer.

## How one cycle finishes the work

### 1. The recipe defines the expected product

The simulated PLC selects a recipe. The recipe supplies the product family, nominal size and mass, allowed variation, target tray orientation, grasp opening, and process limits.

Input: `recipe_id`, product parameters, internal regression limits.

Output: one active configuration bundle used by perception, grasp selection, motion, and verification.

Why this matters: a beef tenderloin, pork loin, and chicken breast do not present the same geometry. The controller must not hide product-specific assumptions inside code.

### 2. The conveyor creates motion and timing

Isaac Sim moves the workpiece on the source belt. A timestamped encoder signal reports belt position and speed. An entry photoeye provides an independent presence event.

Input: commanded conveyor speed and a seeded workpiece pose.

Output: moving rigid-body state, encoder samples, and a photoeye transition.

Why this matters: at the original 2.24 m/s problem speed, 10 ms of unmodeled delay equals about 22 mm of travel. Position alone is not enough. The plan needs position and time.

### 3. The camera produces observations

The fixed overhead camera renders RGB and metric depth. Each frame carries an exposure timestamp, intrinsics, and the camera-to-world calibration.

Input: visible simulator geometry, light, material, camera model, and simulation time.

Output: `RGBDFrame` with RGB, depth, calibration, and exposure time.

Why this matters: the primary demonstration starts from rendered pixels. Simulator ground truth is reserved for scoring after the run.

### 4. YOLO separates the workpiece from the belt

The YOLO26 segmentation interface produces an instance mask, box, class, and confidence. The interface can be replaced without changing the tracker or controller.

Input: rendered RGB.

Output: mask, box, class, confidence, and inference latency.

Why this matters: the mask provides boundary geometry that a box center cannot provide. The current model is trained and tested on synthetic data, so it does not establish real-camera accuracy.

### 5. Geometry converts pixels into a grasp proposal

Depth and calibration back-project the mask into the belt frame. The grasp selector finds a central point with clearance from the mask boundary. Principal-axis geometry estimates the jaw direction. The recipe sets a feasible jaw opening.

Input: mask, depth, calibration, gripper footprint, and product recipe.

Output: `VisionGraspProposal` with position, yaw, width, class, and quality.

Why this matters: the same typed proposal drives the visible overlay, intercept planner, tool yaw, jaw opening, and placement compensation. The visualization and robot do not use separate answers.

### 6. Tracking estimates motion

The tracker associates observations by identity and combines recent measurements with conveyor state. It estimates position, yaw, velocity, uncertainty, and observation age.

Input: `VisionObservation`, encoder state at the exposure timestamp, and prior track state.

Output: `ObjectTrack` with a future-pose function.

Why this matters: using the frame arrival time instead of the exposure time would turn perception latency into a position error.

### 7. The intercept planner reserves a reachable meeting point

The planner scans the allowed pick window. For each candidate time, it predicts the workpiece pose and estimates the robot travel time. It accepts the earliest candidate that satisfies timing reserve, reach, uncertainty, clearance, and freshness limits.

Input: track prediction, current robot state, tool geometry, pick window, limits, and current simulation time.

Output: `InterceptPlan` with grasp pose, intercept time, commit time, and reject reason if no plan is safe.

Why this matters: an attractive grasp point is useless if the arm cannot reach it before the workpiece leaves the window.

### 8. Motion planning converts the meeting point into joint motion

Lula inverse kinematics maps the top-down Cartesian approach and grasp poses to six FANUC joint targets. Quintic interpolation creates position, velocity, and acceleration samples. A preflight gate checks joint limits, speed, acceleration, workspace, and cutter clearance.

Input: timed Cartesian poses and measured joint state.

Output: sampled six-joint trajectory or a rejected motion request.

Why this matters: learned perception never bypasses the deterministic motion boundary.

### 9. The Isaac articulation executes the intercept

The trajectory sampler sends commands to the actual Isaac articulation controller at 240 Hz. The workpiece continues to move until physical finger contact constrains it.

Input: six-joint trajectory samples and jaw commands.

Output: measured joint state, jaw state, contact events, and wrist-load proxy.

Why this matters: the robot does not teleport to the target. The controller has to meet the moving rigid body.

### 10. Contact confirms or rejects the grasp

Both fingers must report recent contact with the workpiece. Finite-effort jaw drives and soft contact parameters approximate compliance. Relative workpiece-to-tool motion provides a slip signal.

Input: bilateral contact, jaw position, effort proxy, wrist-load proxy, and relative pose.

Output: confirmed grasp, slip correction request, grasp loss, or excessive-contact rejection.

Why this matters: a closed gripper command is not proof of a grasp. The current compliance and force values are uncalibrated simulation proxies.

### 11. The supervisor chooses the route

Solution A transports the confirmed grasp directly to the cutter-entry tray. Solution B moves through a buffer, releases, re-observes the product, and performs a corrected second grasp before delivery.

Input: confirmed grasp, route selection, cutter readiness, tray state, and current faults.

Output: the next state and its motion request.

Why this matters: both routes use the same contracts. The A/B difference is isolated to whether a second observation and regrasp are worth the added cycle time.

### 12. The robot aligns to `cut_target_frame`

The planner rotates and translates the held workpiece to the recipe target. Solution B can compensate for measured pose change at the buffer.

Input: target frame, measured or estimated product-to-tool transform, and route state.

Output: a collision-checked delivery trajectory.

Why this matters: the downstream goal is product alignment, not merely moving the gripper to a tray coordinate.

### 13. PLC permissives authorize release

The supervisor checks emergency stop, guards, tray clear, cutter ready, cutter phase, and sequence numbers. It releases only under the simulated machine handshake.

Input: PLC-style I/O and delivery readiness.

Output: release command, wait, reject, or safe stop.

Why this matters: the robot cell does not own blade safety. The downstream machine owns its guarded feed permissive.

### 14. Release and verification close the cycle

The gripper opens, the grasp constraint is removed, and the same rigid body settles on the stationary tray. Verification checks position, yaw, timing, product speed, contact history, and absence of motion-limit violations.

Input: released workpiece state, target frame, timestamps, and full cycle evidence.

Output: pass, fail, or a structured recovery reason.

Why this matters: a cycle does not pass merely because the arm reached the tray.

### 15. Evidence makes the result reproducible

Each run saves the USD stage, RGB and depth images, segmentation overlay, event trace, metrics JSON, video, and an independent artifact audit. Seeded replay checks bounded repeatability.

Input: all timestamped subsystem outputs.

Output: an auditable run directory and machine-readable verdict.

Why this matters: the report is secondary evidence. If it disagrees with a run artifact, the artifact wins.

## The control loop in compact form

```text
recipe and PLC state
    -> moving simulated product
    -> rendered RGB and depth
    -> YOLO instance mask
    -> metric pose and grasp proposal
    -> track and future pose
    -> timed intercept reservation
    -> collision and limit checked joint trajectory
    -> Isaac articulation and jaw contact
    -> direct delivery or buffer correction
    -> cut_target_frame alignment
    -> PLC-authorized release
    -> verification, trace, and recovery
```

## Current evidence boundary

This chain has executed in Isaac Sim for Solution A and Solution B. It uses a FANUC description reference, project gripper geometry, synthetic YOLO training data, rigid workpieces, and uncalibrated contact parameters. It is not evidence of OEM controller behavior, real meat mechanics, real perception accuracy, sanitary design, machinery safety, or production readiness.
