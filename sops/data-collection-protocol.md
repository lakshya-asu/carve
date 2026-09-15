---
title: Data collection protocol
date: 2026-09-05
tags: [sop, data, imitation-learning]
status: draft
---

# Data collection protocol

Applies to teleoperated demonstrations, autonomous rollouts saved for training,
and sensor logs.

## Before recording

1. Define the task in writing: initial state distribution, success condition, allowed variations.
2. Decide the observation and action spaces and write them down with shapes, dtypes, units, and frame ids.
3. Set the control frequency and confirm the recorder captures it without drops.
4. Verify camera intrinsics and extrinsics are saved with the dataset.
5. Create `DATASET.md` with: robot, gripper, cameras, operator, date, site, task, intended use.
6. Record 3 test episodes. Replay them. Check for timestamp gaps, dropped frames, action clipping.

## During recording

- Vary initial conditions deliberately and log the variation scheme.
- Mark failed or corrupted episodes immediately. Do not delete them, tag them.
- Every 25 episodes: spot check one episode end to end.
- Operators take breaks. Fatigued demonstrations degrade policies.

## After recording

- Compute and store dataset statistics: episode count, mean length, action mean/std per dimension.
- Checksum the dataset. Store checksums in `DATASET.md`.
- Two copies in two physical locations before the day ends.
- Note known issues honestly in `DATASET.md`. A future you will train on this.

## Quality rules

- No dataset is used for training without a `DATASET.md`.
- Never mix control frequencies within a dataset without an explicit resampling step.
- Never modify raw data in place. Derived versions get a new directory and a provenance note.

## Additions from research pass 1 (2026-09-05)

Source: `library/topics/teleoperation-and-data-collection.md`. Each item cites the
evidence behind it there.

### Before recording (additions)

7. Choose the teleop interface by task class and write the choice into `DATASET.md`:
   leader-follower for fine or bimanual work, VR controller for portable single-arm
   Cartesian control, handheld UMI-style device when the robot is unavailable or many
   scenes are needed. Spacemouse and keyboard are for debugging only (RoboTurk and GELLO
   user studies).
8. Budget diversity before count: list target scenes and objects, then demos per
   (scene, object). Generalization scales with the number of environments and objects
   and plateaus in demos per environment (Lin et al. 2024). Move scene roughly every
   100 trajectories or 20 minutes (DROID practice).
9. Write a one-page operator protocol (task instructions, allowed grasps, forbidden
   shortcuts, reset procedure) and have every operator read it before their first
   independent episode (ALOHA Unleashed practice). Prefer one or two proficient
   operators for fine tasks; mixed-skill pools degrade offline learning (robomimic).
10. Record camera poses as dataset features, not only in calibration files. Camera pose
    is a first-order axis for both diversity and later retrieval (MimicLabs).
11. Decide the annotation schema now: language instruction, success flag, failure
    reason with timestamp, optional sub-task boundaries. Capture success and failure
    reason live; language variants and segments can be added in post if episode ids are
    stable.
12. Plan staffing on wall-clock, not recorded time. Resets and mistakes make wall-clock
    roughly 3x recorded time (ALOHA: 10-20 min of data took 30-60 min).
13. If any public dataset will be mixed in, record its license in `DATASET.md` and
    confirm it permits the intended use (AgiBot World and most of RH20T are
    non-commercial; DROID and BridgeData V2 are CC BY 4.0).

### During recording (additions)

- Log operator id on every episode and keep per-operator counts and reject rates.
- Reject or tag episodes with end-effector pose jumps (VR tracking loss) or SLAM
  tracking loss (handheld devices) at capture time, not in post.
- Keep failed and recovery episodes with a label and failure reason; do not delete
  (DROID kept ~16k not-successful episodes; AgiBot World labels recovery episodes).

### After recording (additions)

- For LeRobot v3 datasets call `dataset.finalize()` before `push_to_hub()`; then load
  the Hub copy with `StreamingLeRobotDataset` as the verification step.
- Add to the statistics list: per-operator episode count and reject rate, pose-jump
  rate, dropped-frame rate, scene and object inventory counts.
- Smoke-test the pipeline by training a small policy (ACT or Diffusion Policy) on the
  first 10 episodes before the collection day ends; a training failure here is cheaper
  than after 500 episodes.
