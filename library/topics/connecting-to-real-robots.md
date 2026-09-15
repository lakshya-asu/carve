---
title: Connecting to real robots
date: 2026-09-05
tags: [topic, ros2, ros2_control, drivers, fieldbus, real-time, safety, bring-up]
status: draft
source: synthesis (primary links inline and in Sources)
---

# Connecting to real robots: drivers, control interfaces, and ros2_control

## What it is

The plumbing between a learned policy and a motor. A policy emits a target (joint positions,
end-effector pose, gripper width) at 10 to 50 Hz. Something has to turn that into a setpoint the
drive electronics accept every 1 to 8 ms, keep doing so when the policy is late, and stop the
robot when anything upstream dies. On ROS 2 that something is usually `ros2_control` plus a vendor
hardware interface; off ROS it is the vendor SDK called from a real-time loop. Below that sits a
fieldbus (EtherCAT, CANopen, vendor Ethernet, serial) and the drive itself.

```
policy (10-50 Hz) -> action client / shield -> controller (JTC, forward, custom)
  -> controller_manager update loop (100 Hz - 1 kHz) -> hardware_interface read()/write()
  -> fieldbus or vendor SDK (EtherCAT, RTDE, FRI, EGM, CAN, serial) -> drive firmware -> motor
```

Each arrow is a rate boundary and a place to lose time or samples. The rest of this note is
about what lives at each boundary and how to check it on a customer site.

## Why it matters in the field

- A policy that evaluates well in sim or on the lab arm meets a different driver, rate and
  latency at every customer. The UMI authors put hardware latency at "single-digit to hundreds of
  milliseconds" across deployments and calibrated it per robot
  ([arXiv:2402.10329](https://arxiv.org/abs/2402.10329), Sec. PD1).
- The controller boundary is where a policy bug becomes a collision. A `switch_controllers`
  call that hits a resource conflict logs "Command interface ... is already claimed" but the
  service still returned `ok=True` in the reported case, so the old controller keeps driving
  while your client believes the new one is live
  ([ros2_control #1179](https://github.com/ros-controls/ros2_control/issues/1179)).
- Vendor interfaces have hard timing rules. Franka drops any 1 kHz cycle whose round trip
  exceeds 1 ms and stops the arm after 20 consecutive drops
  ([libfranka requirements](https://frankarobotics.github.io/docs/doc/libfranka/docs/system_requirements.html)).
  A laptop on a generic kernel will hit that within minutes.
- Day one on site is usually the only day with the customer's integrator in the room. Network,
  driver, limits and a scripted motion test must be done before lunch or the policy never runs.
- Safety approval is per installation. The learned policy is not a safety function; the wiring
  around it is (ISO 10218-1/-2:2025, see [[library/topics/deployment-engineering]]).

## Key concepts and methods

### ros2_control architecture

`ros2_control` is a plugin framework with three moving parts
([control.ros.org](https://control.ros.org/humble/doc/ros2_control/doc/index.html)):

- **Hardware components** (`System`, `Actuator`, `Sensor`) wrap the robot. They expose
  **state interfaces** (read-only: position, velocity, effort, sensor values) and
  **command interfaces** (setpoints the hardware accepts). The set is declared in the URDF
  `<ros2_control>` tag with `<joint>`, `<sensor>` and `<gpio>` children and per-interface
  `min`/`max` params ([interface types](https://control.ros.org/humble/doc/ros2_control/hardware_interface/doc/hardware_interface_types_userdoc.html)).
- **Controllers** are plugins that read state interfaces and write command interfaces. A command
  interface is claimed by one controller at a time; a second claim is refused with
  "Resource conflict for controller" ([#1400](https://github.com/ros-controls/ros2_control/issues/1400)).
- **controller_manager** owns the loop. `update_rate` (Hz, default 100 in current docs) sets the
  period in which it calls `read()` on every hardware component, `update()` on every active
  controller, then `write()`. `ros2_control_node` tries `SCHED_FIFO` priority 50 for that thread
  (`thread_priority`), can pin it (`cpu_affinity`) and lock memory (`lock_memory`)
  ([controller_manager](https://control.ros.org/rolling/doc/ros2_control/controller_manager/doc/userdoc.html)).

Hardware component lifecycle
([docs](https://control.ros.org/rolling/doc/ros2_control/hardware_interface/doc/lifecycle_of_a_hardware_component.html)):
`on_init` -> UNCONFIGURED (no communication); `on_configure` opens communication -> INACTIVE
(`read()` allowed, `write()` not); `on_activate` enables power -> ACTIVE (`read()` and `write()`);
`on_deactivate`, `on_cleanup`, `on_shutdown` walk back down. If `read()` or `write()` returns
`ERROR`, `on_error(previous_state)` runs; success lands in UNCONFIGURED, failure in FINALIZED,
from which the only recovery is reloading the plugin
([hardware components](https://control.ros.org/humble/doc/ros2_control/hardware_interface/doc/hardware_components_userdoc.html)).
In practice a fieldbus timeout inside `read()` takes the whole robot to UNCONFIGURED, every
controller loses its interfaces, and you re-run the spawners. Design the hardware interface so a
single missed cycle sets a stale flag and only N consecutive misses return `ERROR` (from field,
unverified).

Switching: `SwitchController.srv` defines `BEST_EFFORT=1` and `STRICT=2`; "STRICT means that
switching will fail if anything goes wrong"
([srv](https://github.com/ros-controls/ros2_control/blob/master/controller_manager_msgs/srv/SwitchController.srv)).
CLI ([ros2controlcli](https://control.ros.org/humble/doc/ros2_control/ros2controlcli/doc/userdoc.html)):
`ros2 control list_hardware_interfaces` (shows `[claimed]` per command interface),
`ros2 control switch_controllers --activate A --deactivate B --strict --switch-timeout 5`,
`ros2 control set_hardware_component_state <name> active`. Always switch with `--strict` on a
real robot and check the claimed list afterwards, because the service response alone does not
tell you (#1179 above).

### Which controller for a learned policy

| Controller | Input | Use with a policy when | Caveat |
|---|---|---|---|
| `joint_trajectory_controller` (JTC) | `FollowJointTrajectory` action or `joint_trajectory` topic; command interfaces `position`, `position+velocity`, `position+velocity+acceleration`, `velocity`, or `effort` ([docs](https://control.ros.org/humble/doc/ros2_controllers/joint_trajectory_controller/doc/userdoc.html)) | You send action chunks with timestamps and want interpolation, path and goal tolerances, and a hold on timeout | Each new trajectory replaces the old one; splicing chunks every 100 ms needs the topic interface and a `time_from_start` that begins in the future, or the arm stutters (from field) |
| `forward_command_controller` family (`position_controllers`, `velocity_controllers`, `effort_controllers`) | `~/commands` `Float64MultiArray`, one value per joint, applied on the next update ([docs](https://control.ros.org/humble/doc/ros2_controllers/forward_command_controller/doc/userdoc.html)) | You already interpolate in the policy client and stream at the control rate | No limits, no smoothing, no timeout: a stalled publisher leaves the last command in place forever |
| Custom effort / impedance controller | State interfaces plus your own `update()` | Contact-rich tasks, compliant tracking, torque-level RL policies | Runs in the real-time thread: no allocation, no locks, no logging; needs an `effort` command interface. Franka exposes one; UR lists a `forward_effort_controller` ([UR docs](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_robot_driver/ur_robot_driver/doc/usage/controllers.html)), whether it works on the customer's PolyScope version is unverified |
| MoveIt Servo | `TwistStamped`, `JointJog`, `PoseStamped` | End-effector-space policies; you want singularity and collision scaling for free | Adds a hop and its own smoothing; output goes to JTC or a forward controller |

For most imitation-learning deployments the pattern is: policy client publishes
`JointTrajectory` messages of 10 to 50 points to JTC over the topic interface, with
`allow_partial_joints_goal: false` and `open_loop_control: false` unless the vendor interface
has no reliable state feedback. Use `goal_time` and per-joint `trajectory` tolerances on the
action interface when you want the controller, not the policy, to abort on tracking error.

### The real-time loop and what breaks it

The controller manager's `read()`-`update()`-`write()` chain must finish inside one period,
every period. What breaks it, in the order it usually happens on site:

- Wrong permissions: without `rtprio`/`memlock` limits for the user, `SCHED_FIFO` silently
  fails and the loop runs as a normal thread. Add a `realtime` group and
  `@realtime soft/hard rtprio 99`, `memlock unlimited` to `/etc/security/limits.conf`; in
  Docker run `--cap-add=sys_nice --ulimit rtprio=99 --ulimit memlock=-1 --net host`
  ([controller_manager](https://control.ros.org/rolling/doc/ros2_control/controller_manager/doc/userdoc.html)).
- Generic kernel: Ubuntu's own measurement on one machine shows per-core `cyclictest` max of
  26 to 129 us on the generic kernel against 22 to 39 us on the real-time kernel
  ([Ubuntu docs](https://ubuntu.com/real-time/docs/latest/how-to/measure-maximum-latency/)).
  Under camera and GPU load the generic-kernel tail grows into milliseconds (from field).
- Blocking work inside `read()`, `write()` or `update()`: a `std::cout`, a ROS publish without
  `realtime_tools::RealtimePublisher`, a mutex the non-RT thread holds, a growing `std::vector`
  ([realtime_tools](https://control.ros.org/rolling/doc/realtime_tools/doc/index.html)).
- Fieldbus hiccup: an EtherCAT working-counter mismatch or a lost CAN frame becomes a missed
  `read()`; see the lifecycle note above.
- Power management: Franka's requirements page tells you to disable CPU frequency scaling
  ([libfranka](https://frankarobotics.github.io/docs/doc/libfranka/docs/system_requirements.html));
  C-states and turbo do the same damage. `cyclictest` shows it.

### PREEMPT_RT and cyclictest

`PREEMPT_RT` landed in mainline Linux 6.12 (November 2024,
[kernelnewbies](https://kernelnewbies.org/Linux_6.12)). Ubuntu ships a real-time kernel for
22.04 (5.15, HWE 6.8) and 24.04 (6.8) behind Ubuntu Pro: `sudo pro attach` then
`sudo pro enable realtime-kernel` (variants `--variant=intel-iotg`, `--variant=raspi`); Pro is
free for up to 5 machines. On 26.04 it is in the main archive: `sudo apt install ubuntu-realtime`
([enable guide](https://ubuntu.com/pro-client/docs/en/latest/howtoguides/enable_realtime_kernel/),
[26.04 how-to](https://ubuntu.com/real-time/docs/latest/how-to/enable-real-time-ubuntu/)).
Check the machine, not the label: `uname -a` must show `PREEMPT_RT`. Then, with cameras, driver
and inference running, measure with Ubuntu's invocation
`sudo cyclictest --mlockall --smp --priority=80 --interval=200 --distance=0`
([measure guide](https://ubuntu.com/real-time/docs/latest/how-to/measure-maximum-latency/))
and read the `Max` column per core. OSADL's reference runs use
`cyclictest -l100000000 -m -Sp90 -i200 -h400 -q` for 5.5 hours and show worst cases around
55 us on well-tuned boxes ([OSADL](https://www.osadl.org/Latency-plots.latency-plots.0.html)).
Rule of thumb: max latency must be under 10 percent of the control period for the rate you
intend to run (100 us at 1 kHz), and a run shorter than an hour has not seen the tail (from
field, unverified).

### Fieldbuses and links

| Link | Typical rate | ROS 2 path | Notes |
|---|---|---|---|
| EtherCAT | 1 to 4 kHz cyclic | [`ethercat_driver_ros2`](https://github.com/ICube-Robotics/ethercat_driver_ros2) (ICube): `ros2_control` hardware plugin on the IgH EtherCAT master; `EcCiA402Drive` plugin covers CiA402 cyclic position (8), velocity (9), effort (10), homing (6) ([config](https://icube-robotics.github.io/ethercat_driver_ros2/user_guide/config_cia402_drive.html)) | [SOEM](https://github.com/OpenEtherCATsociety/SOEM) is the userspace alternative, now GPLv3 or commercial. Dedicated NIC plus RT kernel |
| CANopen (CiA402 over CAN) | 100 Hz to 1 kHz | [`ros2_canopen`](https://github.com/ros-industrial/ros2_canopen): Lely master, `Cia402Driver`, `canopen_ros2_control/CIA402System`, socketcan; Humble branch plus master for Jazzy and newer | README: "not yet ready for production use". 1 Mbit/s bus saturates with many nodes and PDOs (from field) |
| Vendor Ethernet (UDP/TCP) | 125 Hz to 1 kHz | Vendor driver: UR RTDE, Franka FCI, KUKA FRI or RSI, ABB EGM, Kinova Kortex, FANUC Stream Motion | Rates and jitter tolerance set by the vendor, see table below |
| Modbus RTU (RS-485) | 200 Hz max | Gripper drivers (Robotiq 2F-85 at 115200 8N1, slave ID 9, 5 ms minimum between commands, [manual](https://assets.robotiq.com/website-assets/support_documents/document/online/2F-85_2F-140_TM_InstructionManual_HTML5_20190503.zip/2F-85_2F-140_TM_InstructionManual_HTML5/Content/4.%20Control.htm)) | Polling protocol; keep it off the arm's real-time thread |
| Serial / USB (TTL, RS-485) | 50 Hz to a few hundred Hz | Feetech and Dynamixel SDKs at 1 Mbit/s ([LeRobot feetech.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/feetech/feetech.py)); ROBOTIS `dynamixel_hardware_interface` for `ros2_control` (the community `dynamixel_hardware` is being archived, [README](https://github.com/dynamixel-community/dynamixel_hardware)) | Bus shared by all servos; FTDI `latency_timer` defaults to 16 ms, set it to 1 ([ROBOTIS FAQ](https://emanual.robotis.com/docs/en/software/dynamixel/dynamixel_sdk/faq/)) |
| Wi-Fi | n/a for control | Telemetry and teleop only | See gotchas: never in the control path |

### MoveIt 2 for planning and Servo for streaming

MoveIt 2 plans collision-free trajectories to a goal and hands them to JTC through `MoveGroup`;
use it for scripted approach and retreat moves around the policy segment. MoveIt Servo is the
streaming path: `ServoNode` (or the `Servo` C++ class, which skips ROS transport) takes
`JointJog`, `TwistStamped` or `PoseStamped` (switched with the `ServoCommandType` service),
applies joint position and velocity limits, scales velocity down near singularities
(`lower_singularity_threshold: 17.0`, `hard_stop_singularity_threshold: 30.0`, condition number)
and collisions (`check_collisions: true`, `collision_check_rate: 10.0` Hz,
`self_collision_proximity_threshold: 0.01` m, `scene_collision_proximity_threshold: 0.02` m),
runs at `publish_period: 0.01` and drops input older than `incoming_command_timeout: 0.1` s
([servo_parameters.yaml](https://github.com/moveit/moveit2/blob/main/moveit_ros/moveit_servo/config/servo_parameters.yaml)).
Output is `JointTrajectory` or `Float64MultiArray` by `command_out_type`, so it drives JTC or a
forward controller; with an RT kernel it tries `SCHED_FIFO` priority 40
([tutorial](https://moveit.picknik.ai/main/doc/examples/realtime_servo/realtime_servo_tutorial.html)).
Every command needs a fresh header stamp. For an end-effector-space policy this is the cheapest
way to get workspace and singularity guards without writing a controller.

### Safety wiring around the controller

- ISO 10218-1/-2:2025 replaced the 2011 editions and made ISO/TS 15066's collaborative content
  normative, with expanded functional safety and cybersecurity clauses
  ([arXiv:2602.17822](https://arxiv.org/abs/2602.17822)). The customer's risk assessment,
  not the vendor's brochure, decides what the cell needs.
- The e-stop chain is hardwired: pendant and cell buttons, fence and light-curtain contacts,
  and the safety PLC's outputs go to the robot controller's safety inputs, never through the
  policy PC. Which stop category each input triggers (0 uncontrolled, 1 controlled then power
  off, 2 controlled with power on, per IEC 60204-1) is set on the robot controller and must be
  read back with the integrator (stop-category mapping from field, unverified).
- Speed and separation monitoring: the protective distance is
  `S = int(vH) over (TR+TS) + int(vR) over TR + int(vS) over TS + C + ZS + ZR`, where TR is
  the system reaction time (sensor latency, network, controller cycle included) and TS the
  stopping time; ISO 13855 uses 1600 or 2000 mm/s for vH
  ([NIST, Marvel and Norcross](https://pmc.ncbi.nlm.nih.gov/articles/PMC5117641/)). Every
  millisecond of policy-side latency that can delay a stop is part of TR.
- Reduced modes: UR's `scaled_joint_trajectory_controller` follows the pendant speed slider
  and pauses on safeguard stop, which is why it is the driver default
  ([UR controllers](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_robot_driver/ur_robot_driver/doc/usage/controllers.html)).
  Run the first policy trials with the slider at 25 percent.

### Measuring end-to-end latency

The number that matters is camera exposure to motor motion, and it has to be measured, not
summed from datasheets. UMI's method: point the camera at a monitor showing a rolling QR code
of the system timestamp; `l_camera = t_recv - t_display - l_display`. Proprioception latency
comes from robot-stamped packets when the vendor provides them (Franka does); execution
latency is the time shift that best aligns commanded and measured end-effector pose
sequences, obtained by teleoperating rather than running the policy
([arXiv:2402.10329](https://arxiv.org/abs/2402.10329), Appendix A). Their Fig. 5 illustrates
100 ms arm and 120 ms gripper execution latency; they discard the actions in each chunk whose
timestamp is already past and send the rest ahead of time.

Typical numbers with source: Physical Intelligence measured 97 ms model time and 108 to 139 ms
end to end for pi-0-class policies ([RTC](https://www.pi.website/research/real_time_chunking));
Chef Robotics reports 55 to 71 ms inference for 3 to 4 images on an RTX 5090, about 67 ms
leader-follower mechanical lag, and 5 to 30 ms camera-to-camera timestamp skew from USB
scheduling, for a total of "3 +/- 2 control steps" at 30 Hz
([Chef Robotics](https://www.chefrobotics.ai/post/latency-aware-vision-language-action-models-vlas-with-system-identification-for-real-time-robot-control)).
A wired loop under 150 ms camera-to-motion is normal; over 250 ms, dynamic tasks fail and the
policy needs delay-aware training or RTC (see [[library/topics/deployment-engineering]]).

## Vendor and driver table

Status checked 2026-09-05 against the linked repos and vendor docs. "Rate" is the vendor
interface cycle, which is the ceiling for `update_rate`.

| Robot | Interface | ROS 2 driver | Rate | Notes | Link |
|---|---|---|---|---|---|
| Universal Robots (CB3, e-Series, PolyScope X) | RTDE + reverse interface over TCP; External Control URCap (CB3, PolyScope 5) or `.urcapx` node (PolyScope X) must be in the running program | `ur_robot_driver`: Humble, Jazzy, Kilted, Lyrical, Rolling; `scaled_joint_trajectory_controller`, `passthrough_trajectory_controller`, forward position/velocity/effort, `force_mode`, `freedrive_mode`, `tool_contact` | 500 Hz e-Series, 125 Hz CB3 (`URE_MAX_FREQUENCY`, `CB3_MAX_FREQUENCY` in the client library) | Program stop, protective stop or e-stop drops the reverse interface; `headless_mode` plus `/io_and_status_controller/resend_robot_program` recovers. Min PolyScope 3.14.3 / 5.9.4 / 10.7.0. Off-ROS: `ur_rtde` `servoJ` at 2 ms | [driver](https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver), [setup](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/robot_setup.html), [rtde_client.h](https://github.com/UniversalRobots/Universal_Robots_Client_Library/blob/master/include/ur_client_library/rtde/rtde_client.h), [ur_rtde](https://sdurobotics.gitlab.io/ur_rtde/pages/examples/high_frequency_servoing/servoj_example.html) |
| Franka FR3 (and Panda) | FCI over UDP, `libfranka` >= 0.19.0 for current branches | `franka_ros2`: Humble and Jazzy branches; joint position, velocity, effort, Cartesian pose and velocity interfaces; example impedance controllers; `franka_gripper` with `Grasp`, `Move`, `Homing` actions | 1 kHz, round trip plus your loop under 1 ms; 20 dropped packets stop the arm | PREEMPT_RT required; connect the PC straight to the Control LAN port, no switch; "avoid Docker Desktop" | [franka_ros2](https://github.com/frankarobotics/franka_ros2), [requirements](https://frankarobotics.github.io/docs/doc/libfranka/docs/system_requirements.html) |
| Kinova Gen3 | Kortex API over 100 Mbit Ethernet | `ros2_kortex`: Humble, Jazzy, Rolling; Robotiq 2F-85/140 through the arm's internal bus (`use_internal_bus_gripper_comm`), action `/robotiq_gripper_controller/gripper_cmd` | 1 kHz low-level servoing, 40 Hz high level | Gripper shares the arm link, so no second cable | [ros2_kortex](https://github.com/Kinovarobotics/ros2_kortex), [servoing modes](https://github.com/Kinovarobotics/Kinova-kortex2_Gen3_G3L/blob/master/linked_md/python_servoing_modes.md) |
| UFactory xArm 5/6/7, Lite 6 | xArm SDK over TCP; servo mode `set_mode(1)` + `set_servo_angle_j` | `xarm_ros2`: foxy through jazzy branches; `xarm_controller` hardware interface with `update_rate: 150` in the shipped config | 150 Hz in the ROS 2 config; SDK servo rate limit unverified | Cheap and common in labs; check firmware vs SDK version pairing | [xarm_ros2](https://github.com/xArm-Developer/xarm_ros2), [SDK API](https://github.com/xArm-Developer/xArm-Python-SDK/blob/master/doc/api/xarm_api.md) |
| KUKA LBR iiwa 7/14, Med 7/14 | FRI (UDP) from a Sunrise Java app (`LBRServer`) | `lbr_fri_ros2_stack`: Jazzy on 24.04, FRI client 1.11 to 2.7; default `update_rate: 100` matched to a 10 ms FRI send period | FRI send period set on the smartPAD; 1 to 10 ms range unverified in these docs | Needs Sunrise Workbench (Windows) to install the server app; `kroshu/kuka_drivers` covers Sunrise 1.x, KSS via RSI (4 or 12 ms cycle), iiQKA | [lbr-stack](https://github.com/lbr-stack/lbr_fri_ros2_stack), [hardware setup](https://lbr-stack.readthedocs.io/en/latest/lbr_fri_ros2_stack/lbr_fri_ros2_stack/doc/hardware_setup.html), [kuka_drivers](https://github.com/kroshu/kuka_drivers) |
| ABB (IRB, OmniCore) | RWS for state and program control, EGM (UDP, protobuf) for streaming; RobotWare option 689-1, >= 6.07.01 | `abb_ros2` (PickNik): `abb_hardware_interface` on `abb_libegm`; branches foxy, humble, iron, rolling; only IRB1200 description shipped | EGM every 4 ms (250 Hz) with 10 to 20 ms control lag | Description and config for other models are yours to write | [abb_ros2](https://github.com/PickNikRobotics/abb_ros2), [EGM manual](https://search.abb.com/library/Download.aspx?DocumentID=3HAC073318-001&LanguageCode=en&DocumentPartId=&Action=Launch), [abb_libegm](https://github.com/ros-industrial/abb_libegm) |
| FANUC (R-30iB Plus, R-50iA) | Stream Motion (option J519 plus R912, or S636) | `fanuc_driver` (FANUC official, 2025): `ros2_control` streaming driver, Jazzy main plus Humble branch; PREEMPT_RT optional | "1 ms" per FANUC America page; not stated in the GitHub docs | `ros-industrial/fanuc` is ROS 1 only; `ros2_fanuc_interface` (CRX, EtherNet/IP) has ~0.2 s delay | [fanuc_driver](https://github.com/FANUC-CORPORATION/fanuc_driver), [requirements](https://fanuc-corporation.github.io/fanuc_driver_doc/main/docs/environment/system_requirements.html), [ros2_fanuc_interface](https://github.com/paolofrance/ros2_fanuc_interface) |
| Agile Robots Diana 7 | Vendor announced FCI compatibility (1 kHz, libfranka-style) in Feb 2025 | No public ROS 2 driver found; `franka_ros2` issue #117 asking for support is open | 1 kHz claimed | Unverified beyond the press release | [press release](https://www.agile-robots.com/en/news/detail/agile-robots-released-new-features-on-diana-7-to-fully-support-franka-control-interface/), [#117](https://github.com/frankarobotics/franka_ros2/issues/117) |
| AgileX Piper | Built-in CAN at 1 Mbit/s via USB-CAN adapter; `piper_sdk` (python-can) | `piper_ros` humble branch: Python node on `/joint_ctrl_single`, no real `ros2_control` hardware interface (the MoveIt config uses `mock_components`) | SDK example loops at 200 Hz; no spec | LeRobot support only via community plugin or open PR #1481 | [piper_sdk](https://github.com/agilexrobotics/piper_sdk), [piper_ros](https://github.com/agilexrobotics/piper_ros/tree/humble) |
| SO-101 (LeRobot) | Feetech STS3215 on a Waveshare serial bus board, USB CDC-ACM, 1 Mbit/s | LeRobot `so101_follower` (no ROS); `lerobot-find-port`, `lerobot-setup-motors`, `lerobot-calibrate` | Teleop default `fps: 60` in `lerobot_teleoperate.py`; record at `--dataset.fps` | Position-only servos; expect 30 to 100 ms bus and servo lag (from field, unverified) | [SO-101 docs](https://huggingface.co/docs/lerobot/so101), [teleoperate](https://github.com/huggingface/lerobot/blob/main/src/lerobot/scripts/lerobot_teleoperate.py) |
| Koch v1.1 (LeRobot) | Dynamixel XL430-W250 and XL330-M288, Protocol 2.0, 1 Mbit/s | LeRobot `koch_follower` (no ROS); `dynamixel_hardware_interface` (ROBOTIS) for `ros2_control` | Same as SO-101 | Set FTDI `latency_timer` to 1 ms | [koch docs](https://huggingface.co/docs/lerobot/koch), [XL330 baud table](https://emanual.robotis.com/docs/en/dxl/x/xl330-m288/) |
| Unitree Go2, B2, H1, G1 | `unitree_sdk2` on CycloneDDS 0.10.2, Ethernet | `unitree_ros2`: Humble recommended, Foxy with rebuilt CycloneDDS; `rmw_cyclonedds_cpp`; `/lowcmd` `LowCmd` with torque, position, velocity fields | Low-level example runs at 2 ms with "0.001~0.01" allowed | Interface bound via `CYCLONEDDS_URI`; the robot's own DDS domain is on the wire, so isolate it from the site LAN | [unitree_ros2](https://github.com/unitreerobotics/unitree_ros2), [go2_low_level.cpp](https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2/main/example/go2/go2_low_level.cpp) |
| Boston Dynamics Spot (+Arm) | gRPC over TLS; Joint Control API is beta and needs a special license | `spot_ros2` (now RAI-Opensource): Ubuntu 22.04 and Humble only, spot-sdk 5.0.1; `spot_hardware_interface` streams joint states at 333 Hz | Joint streaming 100 to 333 Hz | Body and arm share one 12 or 19 element joint vector | [spot_ros2](https://github.com/RAI-Opensource/spot_ros2), [joint control](https://dev.bostondynamics.com/docs/concepts/joint_control/README.html) |
| Mobile bases (Nav2) | Whatever the base driver speaks; Nav2 needs `map -> odom -> base_link` TF, `nav_msgs/Odometry`, and consumes `cmd_vel` | Nav2: Jazzy and Lyrical active, Humble and Kilted maintained; `cmd_vel` is `Twist` up to Jazzy, `TwistStamped` by default from Kilted | Base-dependent | The odometry and TF are the driver's job, not Nav2's | [transforms](https://docs.nav2.org/setup_guides/transformation/setup_transforms.html), [odometry](https://docs.nav2.org/setup_guides/odom/setup_odom.html), [velocity smoother](https://docs.nav2.org/configuration/packages/configuring-velocity-smoother.html) |
| Robotiq 2F-85 / 2F-140 | Modbus RTU, RS-485, 115200 8N1, ID 9; direct via ACC-ADT-USB-RS485, or through the arm (UR tool RS-485, Kinova internal bus) | `ros2_robotiq_gripper` (PickNik, not vendor-maintained): plugin `robotiq_driver/RobotiqGripperHardwareInterface`, `COM_port` default `/dev/ttyUSB0`, `position` command interface; Humble, Iron, Rolling | 200 Hz bus max, 5 ms between commands | On UR: tool I/O must be "Communication interface" and the Robotiq URCap removed, the driver forwards RS-485 to `/tmp/ttyUR` | [ros2_robotiq_gripper](https://github.com/PickNikRobotics/ros2_robotiq_gripper), [UR tool comm](https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver/blob/main/ur_robot_driver/doc/setup_tool_communication.rst) |

## Day-one bring-up procedure

Assumes the arm, its controller and the e-stop chain were installed and accepted by the
integrator; you bring the PC, the policy and this list. Log every step in the field note.

1. **Walk the safety chain with the integrator.** Press every e-stop and open every guard;
   confirm the robot controller reports the stop and what category it is. Photograph the
   safety configuration screen and the pendant's speed slider. No motion before this.
2. **Network.** Static IPs on a dedicated NIC to the robot (Franka: straight into the Control
   LAN port; UR: `robot_ip`; Unitree: `CYCLONEDDS_URI` bound to that NIC). `ping -c 1000 -i 0.002`
   and record max RTT. Set `ROS_DOMAIN_ID` so the customer's other ROS machines cannot see the
   cell. Confirm no Wi-Fi interface carries DDS.
3. **Kernel and permissions.** `uname -a` shows `PREEMPT_RT`; user in the `realtime` group with
   `rtprio` and `memlock` limits; CPU frequency scaling off. Run `cyclictest` for at least 10 min
   with cameras streaming; write down the max per core.
4. **Time sync.** `chrony` between robot PC and inference host; log the offset. A monotonic
   client timestamp travels with every observation regardless.
5. **Driver up, robot inactive.** Launch the vendor driver. `ros2 control list_hardware_interfaces`
   shows the expected joints; `ros2 topic hz /joint_states` matches `update_rate`; `ros2 control
   list_controllers` shows only broadcasters active. For UR, start the External Control program
   and confirm the reverse interface connects; for Franka, check the FCI light is blue.
6. **Joint limits and home.** Diff the URDF limits against the pendant's configured limits and
   the customer's workspace; set `<command_interface>` `min`/`max` to the tighter of the two.
   Define the home pose and the policy start pose as named joint vectors in the config, and
   move to home once with the pendant, not the PC.
7. **Scripted sine-wave test.** Activate JTC with `--strict`. Command each joint in turn with a
   sine of 5 degrees amplitude at 0.2 Hz for 20 s, pendant slider at 25 percent, a hand on the
   e-stop. Record commanded and measured position; compute per-joint tracking lag and overshoot.
   Repeat all joints together, then at 0.5 Hz. Any lag above two control periods or a
   controller error goes in the field note before continuing.
8. **Gripper alone.** Separate bus, separate controller. Open, close, grasp on an object,
   read the status word; time the command-to-motion delay.
9. **Cameras with the arm moving.** Confirm frame rate holds during the sine test and that
   image timestamps stay within budget of joint-state timestamps (the 5 to 30 ms USB skew above
   is what you are looking for). Lock exposure and white balance.
10. **Latency calibration.** QR-code camera latency, robot-stamped proprioception latency,
    teleoperated execution latency (UMI method). Write the three numbers into the experiment
    record; they set `actions_per_chunk` and the watchdog timeout.
11. **Safety shield with a scripted client.** Out-of-box target, 10x velocity, then silence.
    Expect clamp, clamp, watchdog hold. Confirm all three are logged
    ([[library/topics/deployment-engineering]]).
12. **Policy in the loop, slider at 25 percent.** Operator on the deadman, one trial, log
    everything. Only then raise speed in steps and start the evaluation protocol from
    [[sops/experiment-protocol]].

## Practical gotchas

- **Wi-Fi in the control path.** ROS 2's DDS tuning guide: dropped IP fragments on lossy links
  can saturate kernel buffers and hang for 30 s; fixes are best-effort QoS for sensor streams,
  `net.ipv4.ipfrag_time=3`, `net.ipv4.ipfrag_high_thresh=134217728`, and larger
  `net.core.rmem_max` ([DDS tuning](https://docs.ros.org/en/humble/How-To-Guides/DDS-tuning.html)).
  RTC's Wi-Fi network cost was 3x wired ([RTC](https://www.pi.website/research/real_time_chunking)).
  Wire the cell.
- **USB bandwidth.** Two or three UVC cameras on one host controller drop frames and skew
  timestamps by 5 to 30 ms ([Chef Robotics](https://www.chefrobotics.ai/post/latency-aware-vision-language-action-models-vlas-with-system-identification-for-real-time-robot-control)).
  One camera per root hub, MJPEG rather than raw, and `lerobot-find-cameras` ids change across
  reboots ([LeRobot cameras](https://huggingface.co/docs/lerobot/en/cameras)).
- **Serial latency timer.** FTDI adapters buffer for 16 ms by default; `echo 1 >
  /sys/bus/usb-serial/devices/ttyUSB0/latency_timer` ([ROBOTIS FAQ](https://emanual.robotis.com/docs/en/software/dynamixel/dynamixel_sdk/faq/)).
  Without it a 6-servo bus cannot reach 60 Hz (from field, unverified).
- **Clock drift.** Stale-observation filtering and chunk splicing compare timestamps from two
  machines; without `chrony` or PTP the filter either drops everything or nothing (from field).
- **Controller switching.** The service can return `ok=True` on a resource conflict; use
  `--strict` and read `list_hardware_interfaces` after every switch
  ([#1179](https://github.com/ros-controls/ros2_control/issues/1179)). Chainable controllers
  cannot always be activated in one call ([#1400](https://github.com/ros-controls/ros2_control/issues/1400)).
- **UR program stops silently from the driver's point of view.** A protective stop or someone
  pressing stop on the pendant drops the reverse interface; controllers stay "active" but
  nothing moves. Watch `/io_and_status_controller` state and use `resend_robot_program` in
  headless mode ([UR startup](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_robot_driver/ur_robot_driver/doc/usage/startup.html)).
- **Franka communication_constraints_violation.** 20 cycles over 1 ms and the arm stops. Culprits
  in order: no RT kernel, Docker Desktop, a switch between PC and Control, CPU frequency scaling
  ([libfranka](https://frankarobotics.github.io/docs/doc/libfranka/docs/system_requirements.html)).
- **Gripper on the arm's bus.** Robotiq through the UR tool port and the Robotiq URCap cannot
  both own the RS-485 line ([UR tool comm](https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver/blob/main/ur_robot_driver/doc/setup_tool_communication.rst)).
- **Hardware interface errors are terminal.** `ERROR` from `read()` drops to UNCONFIGURED; a
  failed `on_error` drops to FINALIZED and needs a plugin reload
  ([lifecycle](https://control.ros.org/humble/doc/ros2_control/hardware_interface/doc/hardware_components_userdoc.html)).
- **Forward controllers have no timeout.** A crashed policy client leaves the last velocity
  command applied. Put the watchdog in the client or in a custom controller, never rely on the
  forward controller.
- **Distro drift.** `spot_ros2` is Humble-only, `franka_ros2` has Humble and Jazzy, `abb_ros2`
  has no Jazzy branch, Nav2 changed `cmd_vel` to `TwistStamped` in Kilted. Pin the distro per
  robot before the trip.

## What a forward-deployed engineer must be able to do

- Read a vendor's control interface spec and say, before touching the robot, at what rate and
  with what jitter tolerance it accepts setpoints, and whether position, velocity or torque.
- Write or adapt a `ros2_control` hardware interface: URDF `<ros2_control>` block, lifecycle
  callbacks, `read()`/`write()` with no blocking calls, an error policy for missed cycles.
- Configure JTC and a forward controller, switch between them with `--strict`, and prove which
  interfaces are claimed with `list_hardware_interfaces`.
- Verify the kernel and scheduler with `cyclictest` and `chrt`, and fix limits, affinity and
  power management until the loop's max latency is inside budget.
- Measure camera, proprioception and execution latency with the QR-code and alignment methods
  and write the numbers into the experiment record.
- Bring up a gripper on a separate bus and a separate controller so a gripper fault cannot
  stall the arm loop.
- Walk the e-stop chain with the integrator and confirm which stop category each button and
  fence triggers.
- Run the day-one procedure end to end from a checklist and log every step.

## Open questions to learn hands-on

- On our UR and Franka cells, what JTC `time_from_start` offset per chunk gives clean splices
  at 10 Hz policy rate without the arm pausing (measure jerk).
- Whether `ethercat_driver_ros2` or a vendor SDK is the better base for an in-house arm we may
  have to integrate: measure cycle jitter on both.
- Actual `cyclictest` max on Jetson AGX Orin and Thor with the RT kernel while cameras and
  inference share the box.
- Which vendor rates in the table are hard limits and which are default configuration (xArm
  servo mode, Unitree low-level, KUKA FRI period).
- Whether UR's `forward_effort_controller` is usable for a torque-level policy on PolyScope 5
  and PolyScope X hardware.

## Related entries

- [Safety for learned policies](safety-for-learned-policies.md): the shield pattern, standards map, runtime monitors.
- [[library/topics/deployment-engineering]] (latency budget, async inference, safety shield)
- [[library/topics/teleoperation-and-data-collection]] (leader arms use the same buses)
- [[library/topics/real-world-rl]] (torque-level controllers for RL)
- [[library/tools/ros2-humble]]
- [[library/tools/lerobot]]
- [[sops/field-deployment-checklist]]
- [[sops/experiment-protocol]]

## Sources

- ros2_control: controller_manager https://control.ros.org/rolling/doc/ros2_control/controller_manager/doc/userdoc.html ; hardware component lifecycle https://control.ros.org/rolling/doc/ros2_control/hardware_interface/doc/lifecycle_of_a_hardware_component.html and https://control.ros.org/humble/doc/ros2_control/hardware_interface/doc/hardware_components_userdoc.html ; interface types https://control.ros.org/humble/doc/ros2_control/hardware_interface/doc/hardware_interface_types_userdoc.html ; CLI https://control.ros.org/humble/doc/ros2_control/ros2controlcli/doc/userdoc.html ; SwitchController.srv https://github.com/ros-controls/ros2_control/blob/master/controller_manager_msgs/srv/SwitchController.srv ; issues #1179 https://github.com/ros-controls/ros2_control/issues/1179 and #1400 https://github.com/ros-controls/ros2_control/issues/1400 ; realtime_tools https://control.ros.org/rolling/doc/realtime_tools/doc/index.html
- ros2_controllers: joint_trajectory_controller https://control.ros.org/humble/doc/ros2_controllers/joint_trajectory_controller/doc/userdoc.html ; forward_command_controller https://control.ros.org/humble/doc/ros2_controllers/forward_command_controller/doc/userdoc.html
- MoveIt Servo tutorial https://moveit.picknik.ai/main/doc/examples/realtime_servo/realtime_servo_tutorial.html ; servo_parameters.yaml https://github.com/moveit/moveit2/blob/main/moveit_ros/moveit_servo/config/servo_parameters.yaml
- Real-time Linux: kernelnewbies 6.12 https://kernelnewbies.org/Linux_6.12 ; Ubuntu enable guide https://ubuntu.com/pro-client/docs/en/latest/howtoguides/enable_realtime_kernel/ ; Ubuntu measure guide https://ubuntu.com/real-time/docs/latest/how-to/measure-maximum-latency/ ; OSADL latency plots https://www.osadl.org/Latency-plots.latency-plots.0.html
- Fieldbus: ethercat_driver_ros2 https://github.com/ICube-Robotics/ethercat_driver_ros2 and CiA402 guide https://icube-robotics.github.io/ethercat_driver_ros2/user_guide/config_cia402_drive.html ; SOEM https://github.com/OpenEtherCATsociety/SOEM ; ros2_canopen https://github.com/ros-industrial/ros2_canopen ; ROS 2 DDS tuning https://docs.ros.org/en/humble/How-To-Guides/DDS-tuning.html
- Universal Robots: ROS 2 driver https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver ; robot setup https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/robot_setup.html ; controllers https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_robot_driver/ur_robot_driver/doc/usage/controllers.html ; startup https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_robot_driver/ur_robot_driver/doc/usage/startup.html ; tool communication https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver/blob/main/ur_robot_driver/doc/setup_tool_communication.rst ; rtde_client.h https://github.com/UniversalRobots/Universal_Robots_Client_Library/blob/master/include/ur_client_library/rtde/rtde_client.h ; ur_rtde ServoJ https://sdurobotics.gitlab.io/ur_rtde/pages/examples/high_frequency_servoing/servoj_example.html
- Franka: franka_ros2 https://github.com/frankarobotics/franka_ros2 ; libfranka system requirements https://frankarobotics.github.io/docs/doc/libfranka/docs/system_requirements.html ; issue #117 (Diana 7) https://github.com/frankarobotics/franka_ros2/issues/117
- Kinova: ros2_kortex https://github.com/Kinovarobotics/ros2_kortex ; servoing modes https://github.com/Kinovarobotics/Kinova-kortex2_Gen3_G3L/blob/master/linked_md/python_servoing_modes.md
- UFactory: xarm_ros2 https://github.com/xArm-Developer/xarm_ros2 ; SDK API https://github.com/xArm-Developer/xArm-Python-SDK/blob/master/doc/api/xarm_api.md
- KUKA: lbr_fri_ros2_stack https://github.com/lbr-stack/lbr_fri_ros2_stack ; hardware setup https://lbr-stack.readthedocs.io/en/latest/lbr_fri_ros2_stack/lbr_fri_ros2_stack/doc/hardware_setup.html ; kuka_drivers https://github.com/kroshu/kuka_drivers and RSI wiki https://github.com/kroshu/kuka_drivers/wiki/2_RSI
- ABB: abb_ros2 https://github.com/PickNikRobotics/abb_ros2 ; abb_libegm https://github.com/ros-industrial/abb_libegm ; EGM application manual 3HAC073318 https://search.abb.com/library/Download.aspx?DocumentID=3HAC073318-001&LanguageCode=en&DocumentPartId=&Action=Launch
- FANUC: fanuc_driver https://github.com/FANUC-CORPORATION/fanuc_driver ; system requirements https://fanuc-corporation.github.io/fanuc_driver_doc/main/docs/environment/system_requirements.html ; FANUC America ROS 2 page https://www.fanucamerica.com/solutions/ros-2-driver ; ros2_fanuc_interface https://github.com/paolofrance/ros2_fanuc_interface
- Agile Robots Diana 7 FCI press release https://www.agile-robots.com/en/news/detail/agile-robots-released-new-features-on-diana-7-to-fully-support-franka-control-interface/
- AgileX: piper_sdk https://github.com/agilexrobotics/piper_sdk ; piper_ros https://github.com/agilexrobotics/piper_ros/tree/humble ; LeRobot PR #1481 https://github.com/huggingface/lerobot/pull/1481
- LeRobot: SO-101 https://huggingface.co/docs/lerobot/so101 ; Koch https://huggingface.co/docs/lerobot/koch ; cameras https://huggingface.co/docs/lerobot/en/cameras ; feetech.py https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/feetech/feetech.py ; lerobot_teleoperate.py https://github.com/huggingface/lerobot/blob/main/src/lerobot/scripts/lerobot_teleoperate.py
- Dynamixel: dynamixel_hardware (archiving notice) https://github.com/dynamixel-community/dynamixel_hardware ; XL330-M288 https://emanual.robotis.com/docs/en/dxl/x/xl330-m288/ ; SDK FAQ latency timer https://emanual.robotis.com/docs/en/software/dynamixel/dynamixel_sdk/faq/
- Unitree: unitree_ros2 https://github.com/unitreerobotics/unitree_ros2 ; unitree_sdk2 https://github.com/unitreerobotics/unitree_sdk2 ; go2_low_level.cpp https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2/main/example/go2/go2_low_level.cpp
- Boston Dynamics: spot_ros2 https://github.com/RAI-Opensource/spot_ros2 ; spot_ros2_control README https://github.com/bdaiinstitute/spot_ros2/blob/main/spot_ros2_control/README.md ; Joint Control API https://dev.bostondynamics.com/docs/concepts/joint_control/README.html ; networking https://dev.bostondynamics.com/docs/concepts/networking
- Nav2: transforms https://docs.nav2.org/setup_guides/transformation/setup_transforms.html ; odometry https://docs.nav2.org/setup_guides/odom/setup_odom.html ; velocity smoother https://docs.nav2.org/configuration/packages/configuring-velocity-smoother.html
- Robotiq: 2F-85/140 manual, Control section https://assets.robotiq.com/website-assets/support_documents/document/online/2F-85_2F-140_TM_InstructionManual_HTML5_20190503.zip/2F-85_2F-140_TM_InstructionManual_HTML5/Content/4.%20Control.htm ; ros2_robotiq_gripper https://github.com/PickNikRobotics/ros2_robotiq_gripper
- Safety: Marvel and Norcross, "Implementing speed and separation monitoring in collaborative robot workcells" (NIST, 2017) https://pmc.ncbi.nlm.nih.gov/articles/PMC5117641/ ; ISO 10218:2025 comparison (arXiv preprint) https://arxiv.org/abs/2602.17822
- Latency: Chi et al., "Universal Manipulation Interface" (2024) https://arxiv.org/abs/2402.10329 ; Physical Intelligence, Real-Time Chunking https://www.pi.website/research/real_time_chunking ; Chef Robotics, "Latency-Aware VLAs" https://www.chefrobotics.ai/post/latency-aware-vision-language-action-models-vlas-with-system-identification-for-real-time-robot-control
