---
title: Grippers, dexterous hands, and tactile sensors
date: 2026-09-05
tags: [hardware, gripper, end-effector, dexterous-hand, tactile, ros2]
status: draft
source: vendor documentation (links inline)
---

# grippers and end effectors

One section per end-effector family. Specs are quoted from vendor pages, datasheets, or driver
READMEs fetched on 2026-09-05; anything not read on such a page is marked "(unverified)". Prices
appear only where a vendor or distributor page showed one, with URL and date. Arms are in
`robot-arms.md`; the "what the policy sees" column below is what matters for learning: whether the
device reports finger position, a grasp/object-detected flag, or measured force, and at what rate.

## Quick chooser

| Device | Stroke / DOF | Force | Weight | Interface | ROS 2 | What the policy sees | Price (sourced only) |
|---|---|---|---|---|---|---|---|
| Robotiq 2F-85 | 85 mm | 20 to 235 N | 0.9 kg | Modbus RTU, RS-485 | PickNik `ros2_robotiq_gripper` (community) | position, object-detected flag | no price found |
| Robotiq 2F-140 | 140 mm | 10 to 125 N | 1.0 kg | Modbus RTU, RS-485 | same | position, object-detected flag | no price found |
| Robotiq Hand-E | 50 mm (or 100 mm) | 20 to 185 N | 1.0 kg | Modbus RTU (unverified) | Hand-E support (unverified) | "object detection, position, speed, and force" | no price found |
| Franka Hand | 80 mm | 30 to 70 N continuous | 0.73 kg | arm flange, outside the 1 kHz loop | `franka_gripper` in `franka_ros2` | width via joint_states; force is commanded | no price found |
| OnRobot RG2 (2015 UR version) | 0 to 110 mm | 3 to 40 N | 0.65 kg | UR tool I/O; Compute Box on current units | `OnRobot_ROS2_Driver` (community, RG2/RG6) | finger width; force/width reached flags | no price found |
| OnRobot RG6 | 0 to 160 mm (unverified) | 25 to 120 N (unverified) | (unverified) | Compute Box Modbus TCP or UR tool serial | same | finger width | no price found |
| Schunk EGU 50 | 51 mm per jaw | 150 to 300 N | 1.44 kg | Modbus RTU / EtherCAT / PROFINET / EtherNet/IP by variant | `schunk_egu_egk_gripper` (vendor, Humble/Jazzy) | actual position and force | no price found |
| Weiss WSG 50-110 | 110 mm | 5 to 80 N | 1.2 kg | Ethernet TCP/IP (GCL), PROFINET option | community only | position, grip state; optional force fingers | no price found |
| ROBOTIS RH-P12-RN(A) | 0 to 106 mm | 170 N max | 0.5 kg | RS-485 Dynamixel Protocol 2.0 | via `dynamixel_sdk` (unverified package) | position 0.088 deg, present current | RH-P12-RN US$3,663.90 |
| Interbotix X-Series gripper | 30 to 74 mm (unverified) | (unverified) | (unverified) | Dynamixel XM430 on arm bus | `interbotix_ros_manipulators` | position, servo load | no price found |
| SO-101 / Koch gripper | (unverified) | (unverified) | (unverified) | Feetech / Dynamixel on arm bus | LeRobot | servo position and load | in arm BOM |
| Soft Robotics mGrip | (unverified) | (unverified) | (unverified) | pneumatic | none found | none | no price found |
| Festo DHAS Fin Ray fingers | 60 / 80 / 120 mm finger length (unverified) | (unverified) | (unverified) | passive fingers on a parallel gripper | n/a | whatever the host gripper reports | no price found |
| Schmalz ECBPMi | one cup, 1.6 l/min | 60% vacuum | (unverified) | 24 V, IO-Link and RS-485, M12 8-pole | none found | vacuum level via IO-Link (unverified) | no price found |
| piab piCOBOT | (unverified) | up to 7 kg payload (unverified) | (unverified) | UR-certified vacuum ejector unit | none found | (unverified) | no price found |
| Allegro Hand V4 | 16 DOF | 5 kg payload | 1.08 kg | CAN, 333 Hz | ROS package (ROS 2 unverified) | joint positions | contact for pricing |
| LEAP Hand | 16 DOF (unverified) | (unverified) | (unverified) | Dynamixel XC330 over U2D2 USB, up to 500 Hz | ROS 2 API folder | position, velocity, current | "under $2,000" BOM |
| Shadow Dexterous Hand | 20 actuated, 24 joints | (unverified) | 4.3 kg | EtherCAT, 1 kHz | ROS 1 driver; ROS 2 (unverified) | joints, 40 tendon loads, fingertip tactile | no price found |
| Inspire RH56 | 6 DOF, 12 joints | 10 to 30 N fingertip by model | 0.54 to 0.79 kg | RS-485; CAN / Modbus TCP on E2 | (unverified) | position and force, 0.5 N resolution | RH56E2 US$8,900 |
| Tesollo DG-5F | 20 DOF | 12 to 20 kg payload | 0.88 to 1.76 kg | (unverified) | (unverified) | (unverified) | no price found |
| Sharpa Wave | 22 active DOF | 20 N fingertip, 40 kg payload | (unverified) | (unverified) | "ROS" (vendor) | 1000+ taxels per fingertip, up to 180 Hz | no price found |
| GelSight Mini | camera on gel | n/a | (unverified) | USB camera | ROS 2 Foxy listed | tactile image, 25 fps | US$560 robotics package |
| Meta DIGIT | camera on gel | n/a | ~20 g | USB, 640x480 at 60 fps | (unverified) | tactile image | ~$15 BOM at 1000 units |
| XELA uSPa 44 | 4x4 taxels | 1500 gf per taxel | (unverified) | CAN to USB, 500 Hz | "ROS and ROS2" via websocket | 3-axis force per taxel | no price found |
| Contactile PapillArray | 3x3 pillars | 15 N per pillar (Fz) | (unverified) | controller box, USB virtual COM, 1000 Hz | ROS 1 node; ROS 2 (unverified) | 3D force, slip, friction | no price found |

## Robotiq 2F-85, 2F-140, Hand-E

From the [product sheet, May 2025](https://robotiq.com/hubfs/Product-sheets/Adaptive%20Grippers/Product-sheet-Adaptive-Grippers-EN.pdf):
2F-85 stroke 85 mm, grip force 20 to 235 N, 5 kg form-fit and friction payload, 0.9 kg, fingertip
position resolution 0.4 mm, closing speed 20 to 150 mm/s. 2F-140: 140 mm, 10 to 125 N, 2.5 kg, 1 kg,
0.6 mm, 30 to 250 mm/s. Both Modbus RTU over RS-485, IP40, "built-in part detection for grasp
confirmation". The sheet says the user manual is authoritative. Hand-E
([adaptive grippers page](https://robotiq.com/products/adaptive-grippers)): 50 mm stroke (100 mm
variant), 7 kg payload, 20 to 185 N, 150 mm/s, 1 kg, repeatability 0.025 mm, IP67, 24 V 2 A,
feedback "object detection, position, speed, and force". Supply voltage for the 2F units and the
Modbus register map (unverified; manual not fetched).

**ROS 2.** [ros2_robotiq_gripper](https://github.com/PickNikRobotics/ros2_robotiq_gripper), PickNik,
"initially only 2F-85"; ros2_control hardware interface, controllers, description; main targets
Humble/Iron/Rolling. Robotiq itself publishes no ROS 2 package (forum statement, unverified).
Kinova's `ros2_kortex` bundles its own 2F-85/140 description for Gen3.

**For learning.** Gripper position is a clean 1-D observation and action; the object-detected bit
(fingers stopped before the target) is the cheapest "grasp succeeded" signal available and belongs
in the dataset. Force is a commanded setpoint, not a measurement (unverified whether current is
exposed). Modbus round trips over the UR tool port are slow relative to arm state; timestamp gripper
state separately rather than assuming it is synchronous with joint states (from field, unverified).

**Quirks** (search results, issue pages not read; unverified): the UR tool-port RS-485 path has to be
enabled in `ur_robot_driver`
([driver issue 202](https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver/issues/202));
the driver may need several respawns with Modbus exceptions before the gripper LED turns blue;
activation is reset then activate, and a gripper that lost power re-activates by sweeping its full
stroke, so keep it clear of the workpiece.

## Franka Hand

[franka.de/franka-hand](https://franka.de/franka-hand) and the
[product manual v1.2](https://download.franka.de/documents/220010_Product%20Manual_Franka%20Hand_1.2_EN.pdf):
730 g, 63 x 205 x 127 mm, continuous grasping force adjustable 30 to 70 N, 80 mm travel, 50 mm/s
per finger; powered and controlled through the arm's DIN ISO 9409-1-A50 flange, no external cable.
Max force 140 N (unverified; distributor datasheet not fetched).

**Quirk that matters.** The manual states "Franka Hand does not work with real time commands
(applies only to research robots with FCI interface)": gripper commands go through a separate,
blocking TCP client (`franka::Gripper`), not the 1 kHz loop. Do not call it from the control
callback; run it in its own thread and treat its latency (tens to hundreds of ms, unverified) as
part of the action pipeline.

**ROS 2.** `franka_gripper` in [franka_ros2](https://github.com/frankaemika/franka_ros2) (Jazzy
primary) exposes Homing, Grasp, Move, Stop, and GripperCommand actions (action names from search
results, unverified). Grasp takes width, speed, force, and an epsilon window; width is reported
through joint_states; force is commanded, not measured.

## OnRobot RG2, RG6, 2FG7

RG2 ([datasheet v1.4, 2015](https://www.universal-robots.com/media/1226143/rg2-datasheet-v14.pdf),
the legacy UR-direct version): total stroke 0 to 110 mm, finger position resolution 0.1 mm typical,
repetition accuracy 0.1 mm typical, gripping force 3 to 40 N (accuracy +/-1 N typical), speed 55 to
184 mm/s, 24 V DC (runs at half speed on 12 V), weight 0.65 kg, force maintained on power loss,
"analog width feedback" on a robot analog input plus I/O flags for force or width reached. RG6:
0 to 160 mm, 25 to 120 N, 6 kg payload; 2FG7: 11 kg payload, 73 mm external range, 20 to 140 N,
IP54 (all unverified; current [RG2 page](https://onrobot.com/en/products/rg2-finger-gripper)
confirms adjustable 110 mm stroke and automatic grip detection only). Current units connect through
the OnRobot Compute Box or Control Box (Modbus TCP) or the UR tool I/O.

**ROS 2.** [OnRobot_ROS2_Driver](https://github.com/tonydle/OnRobot_ROS2_Driver), community,
RG2/RG6 only: `/onrobot/joint_states` with finger width in metres and a JointGroupPositionController
on `/onrobot/finger_width_controller/commands`; no GripperCommand action; target force hard-coded to
half of max (README TODO); no force feedback. Distros not stated. Other community drivers exist
(ABC-iRobotics, Osaka University Harada Lab; unverified).

**For learning.** Width is the observation; there is no measured force. Stroke is generous for a
gripper this light, which is why it shows up on Kinova and UR teleop rigs.

## Schunk EGU (and EGK, EZU)

EGU 50-MB-N-B ([Schunk page](https://schunk.com/us/en/gripping-systems/parallel-gripper/egu/egu-50-mb-n-b/p/000000000001491536)):
stroke 51 mm per jaw, gripping force 150 to 300 N, 1.44 kg, closing time 0.8 s, positioning speed
110 mm/s, gripping repeatability 0.02 mm, positioning accuracy 0.05 mm unidirectional, 24 V, Modbus
RTU ("MB" variant), IP67 electronics. Other variants carry EtherCAT (EC), PROFINET (PN),
EtherNet/IP (EI), IO-Link (unverified list).

**ROS 2.** [schunk_egu_egk_gripper](https://github.com/SCHUNK-SE-Co-KG/schunk_egu_egk_gripper),
maintained by Schunk, for EGU/EGK/EZU over EtherNet/IP, Modbus RTU, PROFINET, EtherCAT (EoE). CI
badges for Humble and Jazzy. Lifecycle node, multi-gripper namespaces, auto-detect, a "twitch"
command to identify which gripper is which, `grip` / `move_to_absolute_position` / `release`
actions, joint_states, and a gripper state message with actual position and force. Feedback rate
(unverified).

**For learning.** The only parallel gripper here with a vendor-maintained ROS 2 driver that reports
measured force. 150 N minimum is too much for soft objects; pick the EGK for lighter work.

## Weiss Robotics WSG 50

[WSG series page](https://weiss-robotics.com/servo-electric/wsg-series/): WSG 50-110 stroke 110 mm,
force 5 to 80 N, 1.2 kg, finger speed up to 420 mm/s, repeatability +/-0.005 mm, 24 V 850 mA,
Ethernet TCP/IP with the text-based GCL protocol, PROFIBUS/PROFINET optional, continuous grip
monitoring and workpiece detection, optional WSG-FMF force-measuring finger on a sensor port. Still
listed with no discontinuation notice; Weiss also sells CRG and GRIPKIT lines (relationship
unverified).

**ROS 2.** Community only: [5GRobot_WSG50](https://github.com/AAU-RoboticsAutomationGroup/5GRobot_WSG50)
(unverified). ROS 1 drivers from nalt, KIT, and IPA exist; KIT's advertises high-rate feedback and
FMF finger support (unverified).

**For learning.** Very fast and precise, common in older lab setups; the FMF fingers give real
force. Budget time for the ROS 2 driver.

## Dynamixel and bus-servo grippers

**ROBOTIS RH-P12-RN(A)** ([e-manual](https://emanual.robotis.com/docs/en/platform/rh_p12_rna/)):
stroke 0 to 106 mm, max grip force 170 N, 500 g, 5 kg recommended payload, 75 mm/s, 24 V, RS-485
Dynamixel Protocol 2.0 at 9,600 bps to 10.5 Mbps; Current Control and Current-based Position
Control modes; 12-bit absolute encoder (0.088 deg, 0 to 1150 pulses); Present Position at address
580 (4 bytes), Present Current at 574 (2 bytes, mA). Price: RH-P12-RN US$3,663.90
([robotis.us](https://www.robotis.us/robotis-hand-rh-p12-rn/), 2026-09-05; the (A) variant not
listed there).

**Interbotix X-Series gripper**: XM430-W350 on the arm bus, grip width 30 to 74 mm (unverified);
position and load through `interbotix_ros_manipulators`.

**SO-101 / Koch gripper**: one STS3215 (SO-101, 1/345 gear) or Dynamixel (Koch) driving a printed jaw;
LeRobot reads position and load on the same bus as the arm; no force sensing.

**For learning.** Current-based position control gives a usable force cap: set the current limit
and the servo stalls on contact, so present position vs. goal position becomes the grasp signal and
present current a proxy for force. On the 12 V STS3215 the overload protection cuts torque to ~20%
under sustained load with no thermal cutoff (third-party bench test, unverified; see
`robot-arms.md`), so long holds in a dataset are also a hardware risk.

## Soft grippers

**Soft Robotics mGrip**: Soft Robotics sold the mGrip finger-gripper business to Schmalz in August
2024 and rebranded as Oxipital AI (press coverage, unverified; Schmalz page not fetched). Specs
(unverified). Pneumatic, no position or force feedback; the policy sees only the valve command.

**Festo DHAS Fin Ray fingers**: passive adaptive fingers in 60 / 80 / 120 mm lengths (unverified;
Festo datasheet returned 403). Mount on any parallel gripper; observation stays whatever the host
gripper reports, but the finger shape changes the position-to-contact mapping, so re-collect data
after swapping fingertips.

## Suction

**Schmalz ECBPMi** ([product page](https://www.schmalz.com/en/products/automation-743270/vacuum-generators-307617/electric-vacuum-generators-738973/electric-vacuum-generators-end-of-arm-739374/vacuum-generators-ecbpmi-308305)):
electric, no compressed air; up to 1.6 l/min, 60% max vacuum, 24 V DC 0.3 A, M12 8-pole, integrated
IO-Link and RS-485, NFC commissioning, 0 to 40 C, one bellows cup included. Weight (unverified).
ECBPi is the larger sibling (12 l/min, 75%, unverified). Vacuum level as IO-Link process data
(unverified). No ROS 2 driver found.

**piab piCOBOT** ([overview](https://www.piab.com/en-us/robot-and-cobot-gripping-solutions/cobots-and-robot-grippers/picobot-vacuum-gripper-unit/picobot-/)):
UR-certified vacuum ejector with integrated controls and mounts for UR/FANUC/ABB; no numeric specs
on that page. Payload up to 7 kg standard, 16 kg for piCOBOT L, an electric variant at -70 kPa
(all unverified). No ROS 2 driver found.

**For learning.** Suction actions are binary; the useful observation is vacuum level (part
present, seal lost). Bring it out through the arm's tool I/O or IO-Link master and log it at the
policy rate; a seal-loss event is the label for a failed pick.

## Dexterous hands

**Shadow Dexterous Hand** ([Shadow page](https://www.shadowrobot.com/dexterous-hand-series/)):
20 actuated plus 4 under-actuated joints (24), 20 DC motors, tendon driven with 40 tendon load
sensors, 4.3 kg, EtherCAT at 1 kHz, Shadow Tactile Fingertips standard on two fingers. Lite / Extra
Lite / Super Lite variants at 2.4 to 1.8 kg. ROS 1 driver
[sr-ros-interface-ethercat](https://github.com/shadow-robot/sr-ros-interface-ethercat); ROS 2
(unverified). **DEX-EE** ([page](https://www.shadowrobot.com/dex-ee/)), built with Google DeepMind:
12 DOF, 3 fingers, 4.1 kg, 350 mm tall, optical fingertip sensors with "hundreds of taxels", torque
and position loops; rate and interface (unverified).

**Wonik Allegro Hand V4** ([spec](https://www.allegrohand.com/sub/product/p.php?idx=1)): 16 active
DOF, DC motors 1:369, 0.70 N m joint torque, 0.11 s per 60 deg, potentiometer feedback at 0.002 deg,
1.08 kg, 5 kg payload, CAN at 333 Hz, 24 V 100 W, no built-in tactile (XELA and Touchlab skins sold
separately). Official ROS package (ROS 2 distros unverified). Knoxlabs lists "Contact for Pricing".
V5 (9 DOF) and V5 Plus (16 DOF) add omnidirectional pressure tactile
([allegrohand.com](https://www.allegrohand.com/)); other V5 specs (unverified, spec page 403).

**LEAP Hand** ([site](https://v1.leaphand.com/), [paper](https://arxiv.org/abs/2309.06440),
[API](https://github.com/leap-hand/LEAP_Hand_API)): open source, "assembled in 4 hours at a cost of
2000 USD", Dynamixel XC330-M288 over a U2D2; position-only or position+velocity+current at up to
500 Hz ("higher rates can slow USB"); current limits ~300 mA Lite / ~550 mA Full; ROS and ROS 2 API
folders. DOF count (16) and weight not read on a fetched page (unverified). A v2 and a
"$200 to $300" simple version are referenced from the v1 site (specs unverified).

**Inspire RH56** ([RH56DFX](https://en.inspire-robots.com/product/rh56dfx),
[RH56E2 at usrobotstore](https://www.usrobotstore.com/products/inspire-robots-5-finger-robotic-dexterous-hand-rh56e2)):
6 DOF, 12 joints; DFX 540 g, fingertip 15 N thumb / 10 N fingers, RS-485, 12 to 48 V, force
resolution 0.5 N, absolute position and force sensors, power-off self-locking; E2 (the Unitree G1
variant) 790 g, 30 N / 28 N, RS-485 / CAN / Modbus TCP, 5 or 17 tactile zones. Price RH56E2
US$8,900.00 (usrobotstore, 2026-09-05). Control rate, register map, ROS 2 driver (unverified).

**Tesollo DG-3F / DG-5F** ([tesollo.com](https://www.tesollo.com/)): DG-3F-M 12 DOF, 15 kg payload,
1.11 kg; DG-5F-M 20 DOF, 20 kg, 1.76 kg; DG-5F-S 20 DOF, 12 kg, 880 g. Interface, rate, ROS
(unverified; datasheet is download-only).

**Sharpa Wave** ([page](https://www.sharpa.com/pages/wave)): 22 active DOF, 20 N fingertip, 40 kg
payload, over 1000 taxels per fingertip at 0 to 30 N, 0.02 N sensitivity, up to 180 Hz sampling,
"ROS, Isaac Sim, MuJoCo", C++/Python SDK. Weight, actuators, interface (unverified; press claims
500 Hz and Gigabit Ethernet).

**Unitree Dex3-1** ([page](https://www.unitree.com/mobile/Dex3-1/)): 7 DOF (thumb 3, index 2, middle
2), 710 g, 500 g load, +/-2 mm fingertip repeatability, USB 2.0 at 1000 Hz with torque, position,
velocity, temperature feedback; tactile version has 33 pressure sensors (10 to 2500 g). ROS 2
(unverified).

**For learning.** Hands multiply the action dimension (16 to 22) and the calibration burden; every
hand above is position-controlled at the joint level, so the policy action is a joint target vector
and the observation is joints plus whatever tactile channel exists. LEAP is the practical default
for research because it is cheap, open, and Dynamixel-native; Allegro has the most published
policies; Inspire is what ships on Unitree G1.

## Tactile sensors

**GelSight Mini** ([page](https://www.gelsight.com/gelsightmini/),
[datasheet](https://www.gelsight.com/wp-content/uploads/2022/09/GelSight_Datasheet_GSMini_9.20.22b.pdf),
[shop](https://www.gelsight.com/product/gelsight-mini-robotics-package/)): camera on an elastomer,
25 fps, USB (Micro-B to USB-C), user-replaceable gel cartridge (4.25 +/- 0.20 mm thick, rated 1000
coin presses), standard and tracking-marker gels, 0 to 25 C preferred, SDK
[gsrobotics](https://github.com/gelsightinc/gsrobotics) with ROS Noetic and ROS 2 Foxy listed
(Humble unverified). Image resolution and body dimensions (unverified). Price: Robotics Package
US$560.00 (vendor, 2026-09-05, 4-week lead). Robotiq 2F-85 fingertip adapters (unverified).

**Meta DIGIT** ([paper](https://arxiv.org/pdf/2005.14679)): 20 x 27 x 18 mm, ~20 g, 19 x 16 mm
sensing field, OVM7692 640x480 at 60 fps, RGB LEDs, USB; ~$15 in components at 1000 units; three
elastomer options. Shown mounted on Allegro fingertips. ROS 2 driver and commercial availability
(unverified). **Digit 360** ([digit.ml](https://digit.ml/), [repo](https://github.com/facebookresearch/digit360)):
finger-shaped multimodal fingertip, ROS 2 package `d360`, research access via call for proposals
only; resolution and rate (unverified).

**XELA uSkin uSPa 44** ([page](https://xelarobotics.com/products/uspa-44/)): 16 magnetic 3-axis
taxels (4x4, ~4 mm pitch) in a 22.6 x 24.6 x 5.5 mm patch, 500 Hz, 1500 gf normal per taxel
(3000 gf overload), 0.1 gf resolution, CAN daisy chain to a CAN2USB, temperature and magnetic
compensation, "ROS and ROS2" over websocket. Curved skins for Allegro V4 exist (unverified).

**Contactile PapillArray v2** ([page](https://contactile.com/),
[spec PDF](https://contactile.com/wp-content/uploads/2021/12/PTS_2.0_SPEC_DEC21.pdf)): 9 silicone
pillars (3x3, 7 mm pitch), per pillar Fx/Fy +/-4 N and Fz 15 N at under 0.05 N resolution, 1000 Hz
16-bit, controller box for two sensors over USB virtual COM computing force, torque, slip, and
friction; 24.0 x 30.6 x 8.6 mm; temperature drift, so re-bias whenever the sensor is known to be
unloaded; no ingress protection. ROS 1 node shipped; ROS 2 (unverified).

**For learning.** Camera-based sensors (GelSight, DIGIT) give an image the policy encoder can eat
directly, at 25 to 60 fps, and the gel wears; log gel age with the dataset. Taxel sensors (XELA,
Contactile) give low-dimensional force at 500 to 1000 Hz and drift with temperature; re-zero at
episode start. Both need a fingertip mount per gripper, which changes the closed width and the
grasp offsets, so recalibrate the gripper after fitting.

## Cross-family notes

- Interfaces by class: industrial parallel grippers speak Modbus RTU over the arm's tool RS-485 or
  a fieldbus (EtherCAT, PROFINET, EtherNet/IP); research hands speak CAN, EtherCAT, or Dynamixel
  serial; tactile sensors are USB cameras or CAN/USB bridges. Budget one USB port per tactile
  sensor and check hub bandwidth before adding cameras.
- Measured force exists on Schunk EGU/EGK, Weiss with FMF fingers, Inspire RH56, and via current
  on Dynamixel/Feetech servos. Robotiq, Franka Hand, and OnRobot report a commanded force.
- Vendor-maintained ROS 2: Schunk, Franka (gripper inside `franka_ros2`). Everything else is
  community or unverified; plan a driver check on day one.
- Record gripper firmware, driver version, fingertip type, and gel batch in `hardware/README.md`
  when a unit arrives.
