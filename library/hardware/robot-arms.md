---
title: Robot arms (UR, Franka, Kinova, xArm, KUKA, ABB, Piper, Trossen, SO-101, Unitree)
date: 2026-09-05
tags: [hardware, robot-arm, manipulator, ros2, teleop]
status: draft
source: vendor documentation (links inline)
---

# robot arms

One section per arm family a field engineer is likely to meet in 2026. Specs are quoted from
vendor pages, datasheets, or driver READMEs fetched on 2026-09-05; anything not read on such a
page is marked "(unverified)". Prices appear only where a vendor or distributor page showed one,
with URL and date. Teleop hardware trade-offs (leader-follower, GELLO, VR, UMI) live in
`library/topics/teleoperation-and-data-collection.md`; LeRobot driver usage in
`library/tools/lerobot.md`. Fill "units on hand" as arms arrive.

## Quick chooser

| Arm | DOF | Payload | Reach | External control rate | ROS 2 driver | Price (sourced only) |
|---|---|---|---|---|---|---|
| UR3e / UR7e / UR12e / UR16e | 6 (unverified on fetched page) | 3 / 7.5 / 12.5 / 16 kg | 500 / 850 / 1300 / 900 mm | RTDE 500 Hz | `Universal_Robots_ROS2_Driver` (vendor, Humble to Rolling) | no price found |
| UR15 / UR20 / UR30 (UR Series) | 6 (unverified) | 17.5 / 25 / 35 kg | 1300 / 1750 / 1300 mm | RTDE 500 Hz | same driver | no price found |
| Franka FR3 | 7 | 3 kg | 855 mm | FCI 1 kHz torque | `franka_ros2` (vendor, Jazzy) | no price found |
| Franka Panda (legacy, FER) | 7 | 3 kg | 855 mm | FCI 1 kHz | `franka_ros2` (FER support unverified) | no price found |
| Kinova Gen3 6/7 DOF | 6 / 7 | 2 kg full range, 4 kg mid range | 891 / 902 mm | Kortex 1 kHz low level | `ros2_kortex` (vendor, Humble/Jazzy) | no price found |
| Kinova Gen3 lite | 6 (unverified) | 0.5 kg (unverified) | 760 mm (unverified) | Kortex API | `ros2_kortex` | no price found |
| UFactory xArm 6 / 7 / Lite 6 | 6 / 7 / 6 | 5 / 3.5 / 0.6 kg | 700 / 700 / 440 mm | Ethernet SDK (rate unverified) | `xarm_ros2` (vendor, Humble/Jazzy) | xArm 6 US$5,299 to 5,494 |
| KUKA LBR iiwa 7 R800 / 14 R820 | 7 | 7 / 14 kg | 800 / 820 mm | FRI, 1 to 4 ms cycle (unverified) | `lbr_fri_ros2_stack` (KCL, Jazzy) | no price found |
| KUKA LBR iisy 3 to 15 | 6 | 3 to 15 kg | 760 to 1300 mm | (unverified) | (unverified) | no price found |
| ABB GoFa CRB 15000 5 / 10 / 12 | 6 | 5 / 10 / 12 kg | 950 / 1520 / 1270 mm | EGM ~250 Hz (unverified) | `abb_ros2` (PickNik; GoFa support unverified) | no price found |
| AgileX PiPER | 6 | 1.5 kg | 626 mm | CAN 1 Mbit/s, ~200 Hz example loop | `piper_ros` humble branch | USD 1,999 |
| Trossen ViperX 300 S / WidowX 250 S | 6 | 750 / 250 g | 750 / 650 mm | Dynamixel bus 1 Mbps | `interbotix_ros_manipulators` (Humble) | no price found |
| Trossen WidowX AI (ALOHA successor) | 6 | 1.5 kg | 769 mm | Ethernet (rate unverified) | (unverified) | no price found |
| SO-100 / SO-101 | 6 incl. gripper (unverified) | (unverified) | (unverified) | Feetech serial bus | LeRobot (no ROS 2 driver from vendor) | BOM US$121.94 follower, US$229.88 pair |
| Koch v1.1 | 6 (unverified) | (unverified) | (unverified) | Dynamixel bus | LeRobot | no price found |
| Unitree Z1 Air / Pro | 6 | 2 / 3 kg | 740 mm | 1 kHz joint control; SDK UDP 500 Hz (unverified) | (unverified) | no price found |
| Unitree D1-T | 6 + gripper | 0.5 kg | 550 mm | (unverified) | (unverified) | dual-arm teleop kit "under $8,500" |

## Universal Robots e-Series and UR Series

**Lineup in 2026.** The e-Series page lists UR3e, UR7e, UR12e, UR16e; the UR Series lists UR8 Long,
UR15, UR18, UR20, UR30 ([e-Series](https://www.universal-robots.com/products/e-series/),
[UR Series](https://www.universal-robots.com/products/ur-series/)). UR5e and UR10e are referenced but
no longer carry spec tables, so quote their specs from the unit's own manual. Whether UR7e/UR12e are
renamed UR5e/UR10e with a payload bump is (unverified). Payload and reach per model are in the
chooser; weights are 11.2 / 20.6 / 33.5 / 33.1 kg (UR3e/7e/12e/16e) and 40.7 / 64 / 63.5 kg
(UR15/20/30); footprints 128 to 245 mm (same two product pages).
Repeatability is stated series-wide as +/-0.03 to +/-0.05 mm; the per-model figure is (unverified).
UR Series payload headlines apply "in top-down-only configurations"
([UR FAQ](https://www.universal-robots.com/insights/faq/)).

**Control interface.** RTDE streams joint position/velocity/current, TCP pose/speed/force, safety
mode and I/O "at a frequency as high as the real-time control loop frequency (500 Hz on e-Series and
UR-Series robots)"; the client picks 1 to 500 Hz and gets floor(500 / f)
([RTDE guide](https://docs.universal-robots.com/tutorials/communication-protocol-tutorials/rtde-guide.html)).
Servo-style streaming goes through URScript `servoj` / `speedj` (unverified on the fetched page).

**ROS 2.** [Universal_Robots_ROS2_Driver](https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver),
maintained by UR. Branches humble, jazzy, kilted, rolling; Foxy/Galactic/Iron EOL. ros2_control
hardware interface plus MoveIt 2 configs. Needs the External Control URCap installed and Play pressed
on the pendant (or headless mode). "Trajectory control currently only supports position commands."
The pendant speed slider scales the streamed trajectory.

**Teach / teleop.** Teach pendant standard; 3PE pendant optional on e-Series (UR FAQ). Freedrive
button on the wrist (unverified on fetched pages). GELLO ships a UR leader design
([gello_software](https://github.com/wuphilipp/gello_software)).

**Quirks.**
- Protective stops are visible through RTDE: C153/C159 when `joint_position_deviation_ratio`
  reaches 1.0, C157/C158 when `collision_detection_ratio` reaches 1.0 (RTDE guide). A policy that
  commands a jump in joint space trips C153 before it damages anything; log the ratio with actions.
- The ROS 2 driver stops when the pendant program stops. Any pendant popup (protective stop
  acknowledgement) ends external control until a human touches the pendant (from field, unverified).
- Tool-flange RS-485 for Robotiq grippers has to be enabled in the driver; see the grippers note.

## Franka FR3 and Panda (FER)

**FR3** ([franka.de/research](https://franka.de/research)): 7 DOF, 3 kg payload, 855 mm reach,
repeatability under +/-0.1 mm, torque sensors in all 7 joints (hand guiding), 1 kHz control. FR3
weight (unverified). GELLO has FR3 and FER configs
([gello_software](https://github.com/wuphilipp/gello_software)). Limits from the
[robot specifications](https://frankarobotics.github.io/docs/robot_specifications.html): q4 in
[-3.0770, -0.1169] rad, q6 in [0.4398, 4.6216] rad; max joint velocity 2.62 rad/s (J1 to J4), 5.26
(J5, J7), 4.18 (J6); torque limits 87 N m (J1 to J4), 12 N m (J5 to J7); torque rate 1000 N m/s.

**Panda (FER, legacy)**: 7 DOF, 3 kg, 855 mm, pose repeatability under +/-0.1 mm (ISO 9283), weight
~17.8 kg, joint velocity limits 150 deg/s (A1 to A4) and 180 deg/s (A5 to A7), IP30, force resolution
under 0.05 N ([Franka datasheet, April 2020](https://download.franka.de/Datasheet-EN.pdf)). Access
tiers on both: Desk (web UI), RIDE, FCI.

**FCI requirements**
([system requirements](https://frankarobotics.github.io/docs/doc/libfranka/docs/system_requirements.html)):
Linux with PREEMPT_RT kernel; direct cable from the workstation NIC to the Control unit, no switch;
round trip plus control loop plus robot processing under 1 ms; late packets are dropped and after 20
consecutive drops the robot stops with `communication_constraints_violation`. Disable CPU frequency
scaling. libfranka version must match the robot system version.

**ROS 2.** [franka_ros2](https://github.com/frankarobotics/franka_ros2), vendor maintained, Jazzy
branch primary (Humble unverified). ros2_control via `franka_hardware`, MoveIt 2 via
`franka_fr3_moveit_config`, example Cartesian/joint impedance and Cartesian velocity controllers.
Docker workflow documented; the RT kernel on the host is still required. README: "under
development, expect breaking changes".

**Quirks** ([troubleshooting](https://frankarobotics.github.io/docs/troubleshooting.html)):
- `joint_motion_generator_velocity_discontinuity`: the command jumped. A policy that outputs
  absolute joint targets at 10 Hz must be interpolated to 1 kHz before it reaches libfranka.
- "Connection timeout": FCI not enabled in Desk (system 4.2.0+) or feature file missing.
  "UDP receive: Timeout": firewall.
- CPU governor must be `performance`; Secure Boot off for the RT kernel; no allocation, printing,
  or sleeping inside the 1 kHz callback.
- The Franka Hand is not part of the real-time loop (see grippers note).

## Kinova Gen3 and Gen3 lite

**Gen3** ([one-pager 2026](https://www.kinovarobotics.com/uploads/Kinova_Onepager_Gen3_2026_EN.pdf)):
6 DOF version 7.2 kg, 891 mm reach; 7 DOF version 8.2 kg, 902 mm. Payload 2.0 kg continuous full
range, 4.0 kg mid range. Max Cartesian speed 50 cm/s, infinite joint rotation, 24 VDC, IP33. Per-joint
torque, position, current, voltage, temperature, accelerometer, gyro. "Closed-loop, low-level control
at 1 kHz" with position, velocity, current, and torque modes; high-level Cartesian/joint position and
velocity plus wrench. Optional RealSense vision module in the wrist. Repeatability (unverified; not in
the one-pager or user guide).

**Networking** ([user guide R07](https://www.kinovarobotics.com/uploads/User-Guide-Gen3-R07.pdf)):
base Ethernet at 192.168.1.10/24; Wi-Fi works for the Web App and API but "not recommended for 1 kHz
(low-level) control ... a wired connection must be used". High-level servoing: send one command, the
base runs the loop. Low-level servoing: your process closes the 1 kHz loop over actuator commands.
Low-level torque control is "for advanced users only"; high-level force control is "experimental".
Xbox gamepad (wired USB only) ships with twist/joint/wrench maps; wrist bracelet buttons enable
Cartesian or joint admittance for kinesthetic teaching.

**ROS 2.** [ros2_kortex](https://github.com/Kinovarobotics/ros2_kortex), vendor maintained, branches
humble, jazzy, main. ros2_control and MoveIt 2 configs for Gen3 6/7 DOF (with Robotiq 2F-85/140) and
Gen3 lite; joint trajectory and twist controllers. Gen3 lite (0.5 kg, 760 mm, 5.4 kg, IP22, all
unverified; its product page is JS-rendered) can also be reached over USB at 192.168.2.10. README documents a gripper mimic-joint workaround and a protobuf version mismatch.
Kortex API versions: Gen3 2.8.0, Gen3 lite 2.3.0 ([kortex](https://github.com/Kinovarobotics/kortex)).

## UFactory xArm 5/6/7, Lite 6, 850

| Model | DOF | Payload | Reach | Repeatability | Weight |
|---|---|---|---|---|---|
| xArm 5 | 5 | 3 kg | 700 mm | +/-0.1 mm | 11.3 kg |
| xArm 6 | 6 | 5 kg | 700 mm | +/-0.1 mm | 12.5 kg |
| xArm 7 | 7 | 3.5 kg | 700 mm | +/-0.1 mm | 14.3 kg |
| Lite 6 | 6 (unverified) | 600 g | 440 mm | +/-0.5 mm | (unverified) |
| 850 | (unverified) | 5 kg | 850 mm | +/-0.02 mm | (unverified) |

All from the [xArm product page](https://www.ufactory.cc/xarm-collaborative-robot/), which also
lists Ethernet as the interface and 180 deg/s joint speed on xArm 5/6/7. Price: xArm 6 "US$5,299.00
to US$5,494.00" on that page, 2026-09-05. The SDK streaming (servo mode) rate is (unverified); the
[Python SDK](https://github.com/xArm-Developer/xArm-Python-SDK) exposes `set_servo_angle_j` (mode 1
servo), `set_servo_cartesian`, modes 6/7 online trajectory planning, and `set_teach_sensitivity` for
manual (drag) mode. GELLO has an xArm config ([gello_software](https://github.com/wuphilipp/gello_software)).

**ROS 2.** [xarm_ros2](https://github.com/xArm-Developer/xarm_ros2), vendor maintained, branches foxy
through jazzy and rolling; MoveIt 2 planning, dual-arm configs, Gazebo, MoveIt Servo jogging; covers
xArm 5/6/7, Lite 6, 850. Bundles the C++ SDK as a submodule; firmware/SDK coupling is (unverified)
but pin both anyway.

## KUKA LBR iiwa and LBR iisy

**iiwa** ([KUKA page](https://www.kuka.com/en-de/products/robot-systems/industrial-robots/lbr-iiwa)):
7 axes; 7 R800 = 7 kg / 800 mm; 14 R820 = 14 kg / 820 mm; joint torque sensors in all axes, +/-2% of
max torque; hand guiding; Sunrise Cabinet controller. Repeatability +/-0.1 mm and weight (unverified;
spec PDF returned 403). FRI (Fast Robot Interface) runs over UDP with 1, 2, or 4 ms cycle
(unverified; manual not fetched).

**iisy** ([KUKA page](https://www.kuka.com/en-us/products/robotics-systems/industrial-robots/lbr-iisy-cobot)):
6 axes, five variants: 3 R760 (3 kg / 760 mm), 6 R1300, 8 R930, 11 R1300, 15 R930; KR C5 micro-2
controller, iiQKA.OS2, hand guiding via joint torque sensors. Repeatability and weight (unverified).
FRI is a Sunrise product; whether iisy on iiQKA.OS exposes an equivalent is (unverified).

**ROS 2.** [lbr_fri_ros2_stack](https://lbr-stack.readthedocs.io/en/latest/lbr_fri_ros2_stack/lbr_fri_ros2_stack/doc/lbr_fri_ros2_stack.html)
(King's College London, not KUKA): Jazzy on 24.04 documented, Humble (unverified); FRI client
versions 1.11 to 2.7; iiwa7, iiwa14, med7, med14; ros2_control with impedance and gravity
compensation controllers. MoveIt 2 (unverified). An alternative `kuka_sunrise_fri_driver` is on the
ROS index (unverified).

## ABB GoFa CRB 15000

From the [ABB datasheet](https://ventionavatars.s3.amazonaws.com/uploads/part_document/file/721/ABB_CRB_15000_GoFa_Datasheet.pdf)
(distributor-hosted copy):

| | GoFa 5 | GoFa 10 | GoFa 12 |
|---|---|---|---|
| Payload | 5 kg | 10 kg | 12 kg |
| Reach (wrist / flange) | 950 / 1050 mm | 1520 / 1620 mm | 1270 / 1370 mm |
| Pose repeatability | 0.02 mm | 0.02 mm | 0.02 mm |
| Weight | 28 kg | 51 kg | 48 kg |
| Max TCP speed | 2.2 m/s | 2 m/s | 2 m/s |
| IP | IP54 | IP67 | IP67 |

Six axes, torque sensors in every joint, OmniCore C30 controller, SafeMove Collaborative (Cat 3
PL d), lead-through anywhere on the arm, Wizard blocks on the FlexPendant. Externally Guided Motion
(EGM) streams UDP/protobuf at about 250 Hz and needs RobotWare option 689-1 (unverified; from the
`abb_libegm` README, not fetched).

**ROS 2.** [abb_ros2](https://github.com/PickNikRobotics/abb_ros2) (PickNik): `abb_hardware_interface`
for ros2_control over EGM plus an RWS client. GoFa description, supported distros, and MoveIt 2
status (unverified).

## AgileX PiPER

6 DOF, 1.5 kg payload, 626 mm reach, 0.1 mm repeatability, 4.2 kg; Python API, ROS 1 and ROS 2;
USD 1,999.00 ([product page](https://global.agilex.ai/products/piper), 2026-09-05).

**Interface** ([piper_sdk](https://github.com/agilexrobotics/piper_sdk)): CAN at a fixed
1,000,000 bit/s; built-in USB-CAN module supported, third-party adapters need `judge_flag=False`;
example loop sleeps 5 ms (200 Hz). SDK 0.0.x for firmware before V1.5-2, newer SDK for S-V1.6-3+ (DH
parameters changed). Joint feedback is only available in slave mode. The per-joint MIT protocol "can
damage the arm"; stay on the position interface unless you have a reason.

**ROS.** [piper_ros](https://github.com/agilexrobotics/piper_ros): noetic branch with MoveIt and
`can_activate.sh`; a `humble` branch exists (MoveIt 2 support unverified). Master/slave
(leader/follower) modes are in the SDK; the teleop kit price is not on the product page.

## Trossen Interbotix X-Series, ALOHA, and WidowX AI

**ViperX 300 S** ([spec](https://docs.trossenrobotics.com/interbotix_xsarms_docs/specifications/vx300s.html)):
6 DOF, 750 g payload at 50% extension, 750 mm reach, 1 mm repeatability, 5 to 8 mm accuracy; 9
servos (7x XM540-W270, 2x XM430-W350) on a 1 Mbps Dynamixel bus through a U2D2.
**WidowX 250 S** ([spec](https://docs.trossenrobotics.com/interbotix_xsarms_docs/specifications/wx250s.html)):
6 DOF, 250 g payload, 650 mm reach, 1 mm repeatability; 7x XM430-W350 plus 2x XL430-W250. Weights
(unverified).

**ROS.** [interbotix_ros_manipulators](https://github.com/Interbotix/interbotix_ros_manipulators):
ROS 1 Noetic; ROS 2 Galactic, Humble, Rolling; `interbotix_xsarm_moveit` packages. Control-loop rate
(unverified).

**ALOHA (Stationary / Mobile)** ([spec](https://docs.trossenrobotics.com/aloha_docs/2.0/specifications.html)):
leaders are "WidowX 250 S - Aloha Version", followers "ViperX 300 S - Aloha Version"; Stationary
has 4x RealSense D405 and gravity compensators; Mobile adds a SLATE base, System76 laptop, 122 kg,
1 m/s, 1.4 kWh. The [Stationary ALOHA store page](https://www.trossenrobotics.com/aloha-stationary)
marks the product discontinued and redirects to "Trossen AI / Aloha Evolved".

**WidowX AI** ([spec](https://docs.trossenrobotics.com/trossen_arm/main/specifications/wxai.html)):
6 DOF, 1.5 kg payload, 0.769 m reach, 4 kg, Ethernet, 24 V / 15 A peak, joint effort 7 to 27 N m,
integrated gripper 100 N with 40 mm finger travel. Repeatability, control rate, leader variant, and
ROS 2 driver (unverified).

**Quirks.** Dynamixel overload or thermal shutdown on sustained holds is a known failure class on
X-Series arms (from field, unverified; no issue URL captured). Leaders and followers are matched
kinematically; swap one and the joint mapping breaks.

## SO-100 / SO-101 and Koch v1.1 (LeRobot arms)

**SO-101** ([SO-ARM100 repo](https://github.com/TheRobotStudio/SO-ARM100),
[LeRobot docs](https://huggingface.co/docs/lerobot/so101)): follower uses 6x Feetech STS3215 at 1/345
gearing; the leader mixes 1/191, 1/345, and 1/147 gears so it back-drives freely. 7.4 V servos
(16.5 kg cm at 6 V) or 12 V variant (30 kg cm, needs a 12 V 5 A+ supply). SO-101 improved wiring and
removed the gear-removal step; SO-100 docs are deprecated. BOM on the repo: US$121.94 single
follower, US$229.88 leader plus follower (2026-09-05). LeRobot tooling: `lerobot-find-port`,
`lerobot-setup-motors`, `lerobot-calibrate`; Waveshare bus board jumpers on "B". Reach, weight,
repeatability, bus baud rate (unverified).

**Koch v1.1** ([LeRobot docs](https://huggingface.co/docs/lerobot/koch),
[hardware](https://github.com/jess-moss/koch-v1-1)): Dynamixel SDK path, 5 V supply for the follower
board, same find-port/setup/calibrate flow. Servo models and cost (unverified on fetched pages).

**HopeJR** ([LeRobot docs](https://huggingface.co/docs/lerobot/en/hope_jr)): 7-joint Feetech arm plus
a tendon hand driven from an exoskeleton and glove at 30 fps; record/train marked experimental.

**Quirks.** Reported in LeRobot issues but not read on the issue pages (unverified): 7.4 V servos
raise an overvoltage alarm on 12 V boards ([#526](https://github.com/huggingface/lerobot/issues/526));
firmware 3.9 vs required 3.10 ([#1010](https://github.com/huggingface/lerobot/issues/1010)). A
third-party bench test reports STS3215 overload protection dropping to ~20% torque under sustained
load with no thermal cutoff at 71 C
([robonine](https://robonine.com/testing-of-feetech-sts3215-servomotor-backlash-repeatability-and-torque/),
unverified). Calibrate every arm after any servo swap; offsets are per unit.

## Unitree Z1 and D1

**Z1** ([product page](https://www.unitree.com/z1)): 6 DOF, 740 mm reach, ~0.1 mm repeatability; Z1
Air 4.3 kg / 2 kg payload, Z1 Pro 4.5 kg / 3 kg; Ethernet; 24 V over 20 A, 500 W; 33 N m joints with
harmonic reducers, 15-bit encoders, 1 kHz joint control, force control and collision detection. SDK:
[z1_sdk](https://github.com/unitreerobotics/z1_sdk); UDP `sendRecv` to `z1_controller` at 500 Hz
(unverified; the developer docs page did not render). ROS 2 driver (unverified).

**D1-T** ([product page](https://www.unitree.com/mobile/D1-T/)): 6 axes plus gripper, 500 g payload,
550 mm reach (670 mm with gripper), ~2.37 kg, RJ45 plus Type-C debug, 24 V ~60 W,
position/velocity/force modes. Dual-arm teleop kit "under $8,500", quad-arm "under $16,000" (USD, ex
tax and freight, same page, 2026-09-05). Repeatability and control rate (unverified).

## Bimanual and humanoid platforms

Covered in `mobile-robots-and-humanoids.md` (2026-09-06 pass): Unitree G1 with Dex3-1 hands, Galaxea
R1 Pro and R1 Lite, AgileX Cobot Magic, Fourier GR-3, Hello Robot Stretch 3 and 4, ALOHA 2, Mobile
ALOHA, Trossen AI kits, AgiBot G1, ROBOTIS AI Worker.

## Cross-family notes

- External control rates: 1 kHz torque (Franka FCI, Kinova low-level, Unitree Z1 joints), 500 Hz
  (UR RTDE), ~250 Hz (ABB EGM, unverified), 200 Hz example (Piper CAN), 30 to 50 Hz for
  Feetech/Dynamixel bus arms in LeRobot practice. A policy at 10 to 30 Hz needs an interpolator in
  front of every 500 Hz+ interface or it trips a discontinuity fault.
- Franka, Kinova Gen3, iiwa, iisy, and GoFa carry joint torque sensors; UR e-Series has a
  tool-flange force/torque sensor (unverified on fetched pages); bus-servo arms give load only.
- Vendor-maintained ROS 2 drivers: UR, Franka, Kinova, xArm, AgileX, Trossen. Community: KUKA (KCL),
  ABB (PickNik). None for SO-101/Koch; LeRobot talks to the bus directly.
- Every arm couples controller firmware, SDK, and ROS driver versions. Record all three on arrival,
  with vendor contact and serial, in `hardware/README.md`.
