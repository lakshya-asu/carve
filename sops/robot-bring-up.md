---
title: Robot bring-up
date: 2026-09-05
tags: [sop, bring-up, safety, ros2_control, field]
status: draft
---

# Robot bring-up

Bringing a new or unfamiliar robot into service with a learned policy in the loop. Derived from
the day-one procedure in [[library/topics/connecting-to-real-robots]]; the shield and evidence
requirements come from [[library/topics/safety-for-learned-policies]]. Budget: one working day
with the integrator present for the morning. Every step goes in the day's `field-notes/` file
with a timestamp. A failed step stops the procedure; log it verbatim and do not skip ahead.

## Prerequisites (before travel)

- [ ] Arm, controller and e-stop chain installed and accepted by the integrator. Written confirmation.
- [ ] Integrator's risk assessment and safety configuration obtained, or a meeting booked to read them on site.
- [ ] Vendor driver, ROS 2 distro and firmware pairing pinned from the vendor table in [[library/topics/connecting-to-real-robots]]. Container images built and exported.
- [ ] Policy PC has the real-time kernel installed and `cyclictest` passing in the lab with cameras streaming.
- [ ] Shield config drafted: joint limits, workspace box, F/T threshold, watchdog timeout, deadman device. Values marked "draft" until step 6.
- [ ] Scripted test clients ready and tested in sim: sine wave, gripper cycle, shield probe (out-of-box, 10x velocity, silence, corrupt chunk).
- [ ] Field deployment checklist T-1 items done ([[sops/field-deployment-checklist]]).
- [ ] Experiment record opened for the bring-up ([[sops/experiment-protocol]]).

## 1. Safety chain verification

With the integrator. No motion, including pendant motion, before this section is complete.

- [ ] Press every e-stop (pendant, cell, remote). Robot controller reports the stop each time.
- [ ] Open every guard and break every light curtain. Controller reports a protective stop each time.
- [ ] Record the stop category (0, 1, 2) each input triggers, from the safety configuration screen.
- [ ] Photograph the safety configuration screen and the pendant speed slider.
- [ ] Confirm the policy PC has no wire into the safety chain and no ability to inhibit a stop.
- [ ] Confirm reduced-speed mode and its limit value. Set the slider to 25 percent.
- [ ] Note which collaborative mode (monitored stop, SSM, PFL) the cell is assessed for, and the configured limits.

## 2. Network and driver bring-up

1. Dedicated NIC to the robot with a static IP. Franka: straight into the Control LAN port, no switch. Unitree: `CYCLONEDDS_URI` bound to that NIC.
2. `ping -c 1000 -i 0.002 <robot>`; record max RTT. Above 1 ms on a 1 kHz interface is a stop.
3. Set `ROS_DOMAIN_ID` so the customer's other ROS machines cannot see the cell. Confirm no Wi-Fi interface carries DDS.
4. `chrony` between robot PC and inference host. Record the offset. Monotonic client timestamp travels with every observation regardless.
5. Launch the vendor driver with the robot inactive.
6. `ros2 control list_hardware_interfaces` shows the expected joints. `ros2 topic hz /joint_states` matches `update_rate`. `ros2 control list_controllers` shows only broadcasters active.
7. Vendor-specific: UR External Control program running and reverse interface connected; Franka FCI light blue.

- [ ] Robot firmware, driver version, git SHAs and image tags recorded in the field note.

## 3. Kernel and real-time check

1. `uname -a` shows `PREEMPT_RT`. If not, stop; install per the enable guide linked in the topic note.
2. User in the `realtime` group; `ulimit -r` and `ulimit -l` show the configured `rtprio` and `memlock`. In Docker: `--cap-add=sys_nice --ulimit rtprio=99 --ulimit memlock=-1 --net host`.
3. CPU frequency scaling off. Check the governor is `performance` on every core.
4. With cameras streaming and the inference server loaded: `sudo cyclictest --mlockall --smp --priority=80 --interval=200 --distance=0` for at least 10 minutes.
5. Record max latency per core. Pass criterion: under 10 percent of the control period (100 us at 1 kHz).
6. Confirm the controller manager thread runs `SCHED_FIFO` (`chrt -p <pid>`).

## 4. Joint limits and home pose

- [ ] Diff URDF joint limits against the pendant's configured limits and the customer's workspace. Set `<command_interface>` `min`/`max` to the tighter of the two.
- [ ] Set shield joint velocity and acceleration limits from training-data statistics, not from the URDF. Record the percentile used.
- [ ] Define `home` and `policy_start` as named joint vectors in the config. Check both against the workspace box.
- [ ] Move to `home` once with the pendant, not the PC. Compare reported joint state with the pendant display; any offset above encoder resolution stops the procedure.

## 5. Scripted sine-wave test

Pendant slider at 25 percent. One hand on the e-stop. Cameras recording.

1. Activate `joint_trajectory_controller` with `--strict`. Read `list_hardware_interfaces`; every command interface shows `[claimed]` by JTC.
2. Each joint in turn: sine of 5 degrees amplitude at 0.2 Hz for 20 s. Record commanded and measured position.
3. Compute per-joint tracking lag and overshoot. Lag above two control periods or any controller error stops the procedure.
4. All joints together at 0.2 Hz, then at 0.5 Hz. Repeat the computation.
5. Return to `home`.

- [ ] Lag and overshoot per joint written in the experiment record.

## 6. Gripper and camera checks

Gripper:
1. Separate bus and separate controller from the arm. Confirm a gripper fault cannot stall the arm loop by killing the gripper node during a sine run.
2. Open, close, grasp on a reference object. Read the status word. Time command-to-motion delay.
3. Confirm the gripper firmware force limit and record it.

Cameras:
1. Frame rate holds during the sine test. Image timestamps within budget of joint-state timestamps (USB skew of 5 to 30 ms is the known failure).
2. One camera per USB root hub. Device ids recorded; they change across reboots.
3. Lock exposure and white balance. Record the values.
4. Save one frame per camera to the field note for later drift comparison.

## 7. Latency calibration

UMI method, see [[library/topics/connecting-to-real-robots]].

- [ ] Camera latency: rolling QR code of system time on a monitor; `l_camera = t_recv - t_display - l_display`.
- [ ] Proprioception latency from robot-stamped packets where the vendor provides them.
- [ ] Execution latency: teleoperate, time-shift to align commanded and measured end-effector pose.
- [ ] Model p50/p99 latency on the target GPU with a dummy client; then end-to-end with the real client.
- [ ] All numbers in the experiment record. Set `actions_per_chunk` so a chunk covers at least 2x p99 end-to-end latency at the control rate. Set the watchdog timeout from these numbers and record it.

## 8. Shield test

Scripted client only. No policy. Slider at 25 percent.

| Probe | Expected shield action | Expected log entry |
|---|---|---|
| Target outside the workspace box | Clamp to box boundary | clamp, workspace |
| Target at 10x velocity limit | Clamp to limit | clamp, velocity |
| Push against a compliant fixture past the F/T threshold | Hold, then retreat | hold, force |
| Client goes silent | Hold at T_wd, decelerate to stop | hold, watchdog |
| Corrupt or stale chunk | Reject, no motion | reject, stale |
| Deadman released mid-motion | Hold at T_wd | hold, watchdog |

- [ ] All six rows observed and logged with timestamp and executed joint state.
- [ ] Shield config values promoted from "draft" to "commissioned" with the date and git SHA.
- [ ] Log file attached to the experiment record as evidence.

## 9. First policy-in-loop run

- [ ] Slider at 25 percent. Operator on the deadman. Second person on the e-stop if available.
- [ ] Rollout logger confirmed writing: observations, chunks, clamps, monitor scores, model version, latencies.
- [ ] One trial from `policy_start` on a nominal initial condition. Watch the action queue size; it must not reach zero.
- [ ] Review the log before trial two: clamp count, hold count, p99 latency, queue-empty events.
- [ ] Five trials at 25 percent. Then raise the slider in steps (50, 75, 100 percent) with five trials at each. Any hold or clamp on a nominal condition returns the slider one step.
- [ ] Runtime monitor thresholds recalibrated on these episodes; the lab thresholds are not valid on site.
- [ ] Any contact, unexpected motion or dropped safety system: stop, fill [[sops/incident-log-template]].
- [ ] Evaluation protocol from [[sops/experiment-protocol]] starts only after this section is signed.

## 10. Sign-off record

Copy into the field note and the experiment record. Every line filled or the cell is not in service.

```
Date, site, robot serial:
Integrator present (name):
Safety chain: inputs tested / stop categories / photo filename:
Network: max RTT / ROS_DOMAIN_ID / chrony offset:
Kernel: uname / cyclictest max per core / duration:
Limits: URDF vs pendant diff resolved / shield limits source:
Sine test: per-joint lag and overshoot (attach):
Gripper: command-to-motion delay / firmware force limit:
Cameras: ids / exposure and WB values / timestamp skew:
Latency: camera / proprioception / execution / model p50 p99 / end-to-end p99:
Chunking: actions_per_chunk / threshold / watchdog T_wd:
Shield test: six rows passed (attach log):
Policy run: trials per speed step / clamps / holds / interventions:
Checkpoint hash / git SHAs / image tags / config hash:
Open issues:
Signed (engineer) / signed (integrator or customer safety officer):
```

Changes: 2026-09-05 created from the day-one procedure in connecting-to-real-robots.
