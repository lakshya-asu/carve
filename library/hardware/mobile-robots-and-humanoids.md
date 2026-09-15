---
title: Mobile robots and humanoids (mobile manipulators, quadrupeds, humanoids, bimanual platforms)
date: 2026-09-06
tags: [hardware, mobile-manipulator, quadruped, humanoid, bimanual, ros2, teleop, sdk]
status: draft
source: vendor documentation and papers (links inline)
---

# mobile robots and humanoids

Everything a field engineer meets in 2026 that is not a fixed arm. Specs are quoted from vendor pages, manuals, SDK READMEs or papers fetched on 2026-09-06; anything not read on
such a page is "(unverified)". Prices appear only where a vendor or store page showed one on that date. Arms and grippers that bolt onto these bases are in `robot-arms.md` and
`grippers-and-end-effectors.md`; how the leg controller works and how to put a policy on it is in `library/topics/whole-body-and-locomotion-control.md`; base localization and Nav2
in `library/topics/state-estimation-and-localization.md`. Fill "units on hand" as robots arrive.

## Quick chooser

| Platform | Class | DOF | Payload | Battery, runtime | Compute | ROS 2 | Learned-policy work | Price (sourced only) |
|---|---|---|---|---|---|---|---|---|
| Hello Robot Stretch 3 (legacy) / Stretch 4 | mobile manipulator | 10 / 2 base + lift + arm + 3 wrist + gripper + head | 2 kg / 4 kg retracted | 5 h light CPU / 8 h light CPU | NUC 12 / NUC + Jetson Orin NX 16 GB | Humble and Jazzy / Jazzy | Dobb-E, RUMs, OK-Robot, SPOC, HomeRobot | $24,950 / $29,950 |
| PAL TIAGo / TIAGo Pro | mobile manipulator | 7-DOF arm / 2x7 SEA arms, lift | 2 to 3 kg / 3 kg per arm | 720 or 1,440 Wh, 4 to 10 h / 8 to 10 h | i5 or i7, optional Jetson, PREEMPT-RT | Humble (PAL OS 25.01) | none verified | no price found; "more than $200k" per Mobile ALOHA paper |
| Fetch (legacy) | mobile manipulator | 7-DOF arm, torso lift | (unverified) | (unverified) | (unverified) | ROS 1 only; discontinued 2024 | RoboNet | n/a |
| ROBOTIS AI Worker FFW-SG2 | mobile bimanual | 25 | 3 kg per arm, 5 kg peak | 25 V 80 Ah, 2,040 Wh; runtime not stated | Jetson AGX Orin 32 GB | Jazzy (Docker), ros2_control at 100 Hz | ACT via LeRobot; GR00T N1.5/N1.6 fine-tunes on HF | no price shown; 8 week lead |
| Clearpath Husky A300 / A200 / Ridgeback | base for arms | base only | 75 to 101 kg / 75 kg / 100 kg | 1 to 3 kWh, 8 to 24 h / 3 h / 15 h | i3 or i7 Mini-ITX, optional GPU | Jazzy | none verified | no price found |
| MiR250 / MiR600 | AMR base | base only | 250 / 600 kg | 13 to 17.5 h / 8.5 to 11 h | closed | community `mir_robot`, ROS 1 only in practice | none | no price found |
| AgileX Scout 2.0 / Scout Mini / Ranger Mini 3.0 / Tracer 2.0 | UGV base | base only | (unverified) / 10 / 120 / 150 kg | 8 h / 8 h / 7 h / 8 h | none | `scout_ros2`, `ranger_ros2`, `tracer_ros2` (Humble) | Mobile ALOHA on Tracer | no price found |
| Unitree Go2 / Go2-W / B2 | quadruped | 12 | 7 to 12 kg / 8 to 12 kg / 40 kg walking | 1 to 4 h / 1.5 to 3 h / 4 to 6 h | 8-core CPU, optional Orin / i5 plus i7 | Humble via `unitree_ros2` | Walk These Ways (Go1), Extreme Parkour, UMI on Legs | Air $1,600, Pro $2,800, X $4,500 |
| Boston Dynamics Spot with Arm | quadruped | 12 plus 6 | 14 kg; arm lifts 11 kg | 564 to 605 Wh, ~90 min | CORE I/O Xavier NX; RL kit AGX Orin | Humble via `spot_ros2` | BD RL layer, RAI 5.2 m/s, Spot-Compose | no price found |
| ANYbotics ANYmal | quadruped | 12 | 10 kg | 90 min | 2x Intel i7 | ROS (research community only) | Hwangbo, Lee, Rudin, Miki | no price found |
| Unitree G1 / H1 / H2 | humanoid | 23 to 43 / 13 or 27 / 31 | ~2 to 3 kg arms / 7 kg rated (H1-2) / 7 kg rated | ~2 h / 0.864 kWh / 0.972 kWh, ~3 h | 8-core plus Orin (EDU) / i5 plus i7 / i5 or i7 | Humble via `unitree_ros2` | TWIST, AMO, ASAP, HOMIE, HumanPlus, OmniH2O | $13,500 / $90,000 listed / $29,900 |
| Booster T1 / T2 / K1 | humanoid | 23 / 31 / 22 | (unverified) / 10 kg dual-arm / (unverified) | 2 h walking | AGX Orin / Jetson Thor (Pro) / 48 to 200 TOPS | Humble via `booster_deploy` | TWIST on T1; BeyondMimic tracking in `booster_train` | K1 from $5,999 |
| Fourier GR-3 | humanoid | 55 | (unverified) | (unverified) | (unverified) | Aurora SDK, Zenoh on N1 | GR00T N1 on GR-1, HOMIE on GR-1 | no price found |
| PND Adam / Adam-U | humanoid / upper body | 25 to 43 / 31 | (unverified) | 1,172 Wh | NUC12 i7 plus Orin NX 16 GB | Humble (`pnd_ros2`) | vendor `pnd_rl_gym`, `pnd_teleoperation` | no price found |
| Galbot G1 | wheeled humanoid | 21 | 5 kg per arm | 48 V 30 Ah, 8 h | AGX Orin 64 GB | (unverified) | GraspVLA (evaluated on Franka) | via JD.com, no price read |
| Galaxea R1 Pro / R1 Lite | wheeled bimanual | 26 / 23 | 3.5 / 3 kg per arm | (unverified) | AGX Orin 32 GB / i9-12900HK | (unverified) | Galaxea Open-World Dataset, G0 | $69,999 / $39,999 |
| AgiBot G1 / A2 | wheeled bimanual / humanoid | 26 / 40+ | 3 kg per arm / (unverified) | over 4 h / 700 Wh, 2 h | AGX Orin 64 GB / (unverified) | (unverified) | AgiBot World, GO-1 | G1 unpriced; A2 Lite $44,560 |
| ALOHA 2 / Mobile ALOHA / Trossen AI | bimanual | 2x6 plus base | 750 g per arm (ViperX) / 1.5 kg (WidowX AI) | n/a / 1.26 kWh / SLATE 24 V 18 Ah | workstation / RTX 3070 Ti laptop / RTX 5090 option | ROS 2 / ROS 1 / Humble and Jazzy | ACT, ALOHA Unleashed, pi0 | ~$20k / $32k / $23,995.95 to $40,025.80 |
| Figure 03, Digit, Apollo, NEO, Optimus | humanoid, reported | see table below | | | | none public | Helix; Radosavovic on Digit ([arXiv:2303.03381](https://arxiv.org/abs/2303.03381), robot not named in the abstract) | NEO $20,000 or $499/month |

## Mobile manipulators

### Hello Robot Stretch 3 and Stretch 4

**Stretch 3** (legacy; hello-robot.com now sells Stretch 4 at $29,950, Stretch 3 sits on a legacy site at $24,950 and its old docs URLs 404,
[hello-robot.com](https://hello-robot.com/), [Stretch 3 legacy](https://hello-stretch3.com/stretch-3-product)): 24.5 kg, 2 kg payload, "5 hour runtime (light CPU) / 2 hour runtime
(high CPU)"; RealSense RGB-D in the gripper and on the pan-tilt head, RP-Lidar A1, 4-mic array; Intel NUC 12; battery Wh and reach (unverified). **Stretch 4**
([overview](https://docs.hello-robot.com/stretch-4-quick-start-guide/robot-overview.md), [hardware
guide](https://docs.hello-robot.com/stretch4-hardware-guide/stretch-4-hardware-guide.md)): three-omniwheel holonomic base, lift to 47 in, telescoping arm with 55 cm reach, 3-DOF
Feetech wrist; 4 kg retracted or 2.5 kg extended; 46 kg; "8 hours (Light CPU load)"; two Hesai JT128 LiDARs on the head, OAK-FFC-3P head cameras, two OAK-D-SR at the gripper, cliff
sensors; NUC running `stretch_body_server` at 100 Hz plus a Jetson Orin NX 16 GB over Ethernet; Ubuntu 22.04, ROS 2 Jazzy; homing takes about 30 s at every power-on.

**Control and ROS 2.** Stretch 1 to 3: `stretch_body` Python (`pip3 install hello-robot-stretch-body`), Dynamixel status at 15 Hz and the rest at 25 Hz
([stretch_body](https://github.com/hello-robot/stretch_body)); `stretch_ros2` with `humble` and `jazzy` branches ([stretch_ros2](https://github.com/hello-robot/stretch_ros2)).
Stretch 4: `stretch4_body` `RobotClient` over ZeroMQ, server at 100 Hz, user loop 10 to 50 Hz recommended, status carries joint position, velocity, effort, base odometry and
battery ([primer](https://docs.hello-robot.com/stretch4-body-repo/core-framework/primer_robot_client.md)); `stretch4_ros2` on Jazzy with `stretch_core`, `stretch_nav2`,
`stretch_simulation` (MuJoCo) ([stretch4_ros2](https://docs.hello-robot.com/stretch4-ros2-repo/readme.md)). Runstop on the head: tap disables motion (1 Hz flash), hold over 2 s
enables; enabled at startup; actuators drop to firmware Safety Mode; "not equivalent to an Emergency Stop found on industrial equipment" ([safety
guide](https://docs.hello-robot.com/stretch-4-safety-guide/stretch-4-safety-guide.md)).

**Teleop and learning.** Browser teleop over WebRTC with Nav2, one browser at a time ([stretch_web_teleop](https://github.com/hello-robot/stretch_web_teleop)); Dex Teleop with a
webcam and an AR-marker tool ([stretch_dex_teleop](https://github.com/hello-robot/stretch_dex_teleop)); `stretch_ai` (Apache-2.0) bundles data collection, a LeRobot fork for ACT,
DynaMem and an OK-Robot derived bridge ([stretch_ai](https://github.com/hello-robot/stretch_ai)). Papers on Stretch: Dobb-E ([arXiv:2311.16098](https://arxiv.org/abs/2311.16098)),
Robot Utility Models ([arXiv:2409.05865](https://arxiv.org/abs/2409.05865)), OK-Robot ([arXiv:2401.12202](https://arxiv.org/abs/2401.12202)), SPOC
([arXiv:2312.02976](https://arxiv.org/abs/2312.02976)), HomeRobot ([arXiv:2306.11565](https://arxiv.org/abs/2306.11565)).

### PAL Robotics TIAGo and TIAGo Pro

**TIAGo Pro** ([product](https://pal-robotics.com/robot/tiago-pro/), [hardware](https://docs.pal-robotics.com/25.01/hardware/tiagopro/hardware-overview.html)): two 7-DOF
series-elastic arms, 3 kg each, 96 cm reach, torque sensing per actuator, "1KHz EtherCAT", optional wrist F/T; mecanum base at 1 m/s, 35 cm torso lift; two 360 deg lasers, IMU,
RealSense D435 head; i5 16 GB or i7 32 GB, optional Jetson, PREEMPT-RT; two 36 V 20 Ah packs, "8-10 hours". **TIAGo**
([hardware](https://docs.pal-robotics.com/25.01/hardware/tiago/hardware-overview.html)): one 7-DOF arm (2 kg in docs, "3 Kg without end-effector" on the product page), 87 cm,
differential base, 72 kg, laser, sonars, IMU, RGB-D head, optional ATI mini45; 720 Wh per pack, 4 to 5 h, 8 to 10 h with two.

**Boot, e-stop, teleop, ROS 2.** Key clockwise, hold power 1 s until green; three e-stops (torso, base, wireless), a lost or dead wireless button counts as pressed ([power
management](https://docs.pal-robotics.com/25.01/general/tiagopro/power-management.html)); on e-stop "motors are stopped and disconnected"
([handbook](https://docs.pal-robotics.com/tiago-single/handbook.html)). Gamepad, web UI, SSH ([TIAGo Pro docs](https://docs.pal-robotics.com/25.01/tiagopro)). PAL OS 25.01 is
Humble on Cyclone DDS with multicast discovery off and a peer list ([communication](https://docs.pal-robotics.com/25.01/development/robot-communication-ros2.html)); `tiago_robot`,
`tiago_pro_robot`, `tiago_simulation` (Gazebo, Nav2, MoveIt 2) on `humble-devel` ([pal-robotics](https://github.com/pal-robotics/tiago_pro_robot)). Learned-policy papers on TIAGo
(unverified; none fetched).

### Fetch (legacy)

"No longer supported or sold by Zebra Technologies as of 2024" ([docs banner](https://fetchrobotics.github.io/docs/)). SICK TIM571 laser, Primesense Carmine head RGB-D, IMU;
Ethernet to a mainboard, RS-485 to per-joint boards at a 17.5 kHz effort loop; runstop drops the base, arm and gripper breakers
([hardware](https://fetchrobotics.github.io/docs/robot_hardware.html)). `fetch_ros` is ROS 1 with ROS 2 "in planning", last push 2024-08
([fetch_ros](https://github.com/fetchrobotics/fetch_ros)). Fetch data is in RoboNet ([arXiv:1910.11215](https://arxiv.org/abs/1910.11215)). Keep one only for its existing ROS 1
stack.

### ROBOTIS AI Worker (FFW-SG2, FFW-BG2, FFW-LG2)

Known to this team from prior Nav2 demo work (`hardware/README.md`). **Hardware** ([hardware page](https://ai.robotis.com/ai_worker/hardware_ai_worker.html)): FFW-SG2 mobile, 25
DOF (two 7-DOF arms, two grippers, 2-DOF head, lift, 6 for the swerve base), 90 kg, 1.5 m/s, 3 kg per arm nominal and 5 kg peak, 641 mm reach to the wrist; arm joints 1 to 6 are
DYNAMIXEL-Y (YM080-230, YM070-210), joint 7 DYNAMIXEL-P, RS-485 at 4 Mbps; ZED Mini head plus two RealSense D405 wrist cameras, two LakiBeam 1 LiDARs (270 deg, 25 m); Jetson AGX
Orin 32 GB; 25 V 80 Ah (2,040 Wh), runtime not stated. FFW-BG2 is the stationary 19-DOF twin on a 1,920 W supply; FFW-LG2 is the 22-DOF worn leader; FFW-LH5 (60 DOF with hands) is
in development. YM080-230: 230 W, 19-bit encoder, 99:1 ([e-manual](https://emanual.robotis.com/docs/en/dxl/y/ym080-230-r099-rh/)).

**Software** ([software page](https://ai.robotis.com/ai_worker/software_ai_worker.html)): ROS 2 Jazzy in Docker on JetPack 6.2; `ros2_control` with a "100Hz joint control loop";
`/joint_states`, `/cmd_vel`, `/leader/joint_trajectory_command_broadcaster_{left,right}`; `ffw_bringup`. Repos: [ai_worker](https://github.com/ROBOTIS-GIT/ai_worker) (Apache-2.0,
`jazzy` branch) and [physical_ai_tools](https://github.com/ROBOTIS-GIT/physical_ai_tools) (LeRobot as a submodule).

**Boot, e-stop, teleop, data** ([setup](https://ai.robotis.com/ai_worker/setup_guide_hardware_ai_worker.html),
[teleop](https://ai.robotis.com/ai_worker/operation_teleoperation_ai_worker.html), [recording](https://ai.robotis.com/ai_worker/dataset_preparation_recording_ai_worker.html)):
supply switch on, key to 12 o'clock, hold power 3 s until the beep. Remote E-STOP mushroom; release by rotating clockwise then pressing A; the robot starts torque-off until A.
Teleop by wearing the FFW-LG2 leader, `ros2 launch ffw_bringup ffw_bg2_ai.launch.py`, both triggers over 2 s to start or pause; a VR page exists. Recording through the Physical AI
Tools web UI at `http://ffw-{serial}.local`, recommended 15 fps, LeRobot format, optional rosbag2; training with the LeRobot CLI (`--policy.type=act`). ROBOTIS publishes seven
LeRobot datasets and six GR00T N1.5/N1.6 fine-tunes ([HF ROBOTIS](https://huggingface.co/ROBOTIS)). Price not shown, "8 week lead time"
([robotis.us](https://www.robotis.us/ai-worker/)).

### Clearpath Husky A300, A200, Ridgeback

**Husky A300** ([manual](https://docs.clearpathrobotics.com/docs_robots/outdoor_robots/husky/a300/user_manual_husky)): LiFePO4 25.6 V in 40, 80 or 120 Ah (1,024 to 3,072 Wh), 8 to
24 h, 78.5 to 105 kg with 75 to 101.5 kg allowable payload, 2.0 m/s, IP54; i3-13100TE or i7-13700TE Mini-ITX, optional GPU, IMU; front and rear e-stops "PLc per ISO 13849", open
debug door is an e-stop, resistive brake on stop, Safety Restart button, optional wireless e-stop. Boot: breaker on, hold power 1 s, wait one minute, Safety Restart, PS button on
the joystick. ROS 2 Jazzy on Ubuntu 24.04 ([installation](https://docs.clearpathrobotics.com/docs/ros/installation/robot)); an FR3 plus MoveIt 2 arm package is listed
([product](https://clearpathrobotics.com/husky-a300-unmanned-ground-vehicle-robot/)). **A200**
([manual](https://docs.clearpathrobotics.com/docs_robots/outdoor_robots/husky/a200/user_manual_husky)): 50 kg, 75 kg payload, 1 m/s, 24 V 20 Ah SLA, 3 h. **Ridgeback**
([manual](https://docs.clearpathrobotics.com/docs_robots/indoor_robots/ridgeback/user_manual_ridgeback)): omnidirectional, 100 kg payload, 1.1 m/s, 24 V 100 Ah AGM, 15 h, four
mushroom stops plus Stop Reset, PS4 with L1 deadman; Jazzy after a USB firmware flash. Config in `/etc/clearpath/robot.yaml`, drivers in
[clearpath_robot](https://github.com/clearpathrobotics/clearpath_robot).

### MiR and Omron AMRs as bases

**MiR250** ([spec](https://mobile-industrial-robots.com/products/robots/mir250/specifications)): 250 kg, 2.0 m/s, 94 kg, 13 to 17.5 h, "10 min charging gives 2 h 40 min", two SICK
nanoScan3, two 3D cameras, ISO 3691-4 with 12 ISO 13849-1 safety functions, one auxiliary e-stop input, 4 DI and 4 DO. **MiR600**
([spec](https://mobile-industrial-robots.com/products/robots/mir600/specifications)): 600 kg, 240 kg, 8.5 to 11 h, TÜV, 13 safety functions. MiR100 is off the current site
(discontinued, unverified). The control surface is the on-robot REST API and rosbridge; the community [mir_robot](https://github.com/DFKI-NI/mir_robot) driver (DFKI, "not
affiliated") bridges rosbridge on port 9090, confirmed on MiR100/200/500 with software 2.8.3.1 only; its `humble` branch last moved in 2021-06 and still uses `roslaunch`, so treat
it as ROS 1. An arm on a MiR treats the base as a black box: Nav2 stays on the MiR, the policy sends missions or REST calls (from field, unverified). Omron LD and MD pages are
JS-rendered and did not fetch (all specs unverified).

### AgileX Scout, Ranger, Tracer

From the vendor manuals ([download page](https://global.agilex.ai/pages/download-manual)): CAN 2.0B at 500 kbit/s, feedback frames every 20 ms, e-stops on both sides that "shut
down power immediately", key switch to boot after releasing them:

| Base | Drive | Size, mass | Battery, runtime | Speed | Payload | IP |
|---|---|---|---|---|---|---|
| Scout 2.0 | 4x 400 W skid | 930x699x349 mm, 67 kg | 24 V 30 Ah, 8 h / 15 km | 1.5 (manual) or 1.67 m/s (page) | (unverified) | IP22 |
| Scout Mini | 4x 250 W skid | 612x580x245 mm, 23 kg | 24 V 15 Ah, 8 h / 10 km | 3 m/s | 10 kg | IP22 |
| Ranger Mini 3.0 | 4 drive plus 4 steer, spin/Ackermann/omni | 720x500x345 mm, 75 kg | 48 V 24 Ah LiFePO4, 7 h / 35 km | 2 m/s (7.2 km/h) | 120 kg | IP54 |
| Tracer 2.0 | 2x 400 W differential | 702x610x169 mm, 54 to 56 kg | 24 V 30 Ah LiFePO4 (60 Ah option), 8 h / 27 km | 2.0 m/s | 150 kg | IP22 |

SDK: [ugv_sdk](https://github.com/agilexrobotics/ugv_sdk) (C++, `ip link set can0 up type can bitrate 500000`); ROS 2 Humble packages
[scout_ros2](https://github.com/agilexrobotics/scout_ros2), [ranger_ros2](https://github.com/agilexrobotics/ranger_ros2),
[tracer_ros2](https://github.com/agilexrobotics/tracer_ros2); topic rates not in the READMEs. No obstacle sensors on board (Ranger manual). Mobile ALOHA reads Tracer wheel
velocities over CAN and logs them as the base action ([arXiv:2401.02117](https://arxiv.org/abs/2401.02117)).
## Quadrupeds

### Unitree Go2, Go2-W, B2

**Specs** ([Go2](https://www.unitree.com/go2), [shop](https://shop.unitree.com/products/unitree-go2), [Go2-W](https://www.unitree.com/go2-w), [B2](https://www.unitree.com/b2)).
Go2: 4D LiDAR L2 (360 x 96 deg, 0.05 m minimum), HD wide-angle camera, foot force sensors on EDU only; "8-core high-performance CPU" on Pro/X/EDU with an optional Orin module
(whether EDU ships a Jetson Orin NX is unverified); 8,000 mAh standard or 15,000 mAh EDU at 28.8 V nominal, "about 1-2 h" or "2-4 h"; ~15 kg; 3.7 m/s (~5 m/s X/EDU); 7 to 8 kg
payload, 12 kg max. Prices on 2026-09-06: Air $1,600, Pro $2,800, X $4,500, EDU contact sales. Go2-W adds in-wheel motors, 15,000 mAh, 1.5 to 3 h, ~18 kg. B2: 3D LiDAR, two depth
plus two optical cameras, i5 platform plus i7 user PC, 2,250 Wh at 58 V, 4 to 6 h, 40 kg walking payload, over 6 m/s, IP67, ~60 kg.

**Control, SDK, ROS 2.** `unitree_sdk2` (C++, CycloneDDS) and `unitree_sdk2_python` (`cyclonedds==0.10.2`). High level: `SportClient` (`StandUp`, `Damp`, `Move`, `RecoveryStand`,
`BodyHeight`) with state on `rt/sportmodestate`. Low level: `rt/lowcmd` and `rt/lowstate`, example loop at 2 ms ("0.001~0.01" allowed), per-motor `q, dq, tau, kp, kd`; the sport
service must be disabled first with `ServiceSwitch("sport_mode", 0)` "to prevent command conflicts". Host at 192.168.123.99/24 on the wired port
([go2_low_level.cpp](https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2/main/example/go2/go2_low_level.cpp),
[go2_sport_client.cpp](https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2/main/example/go2/go2_sport_client.cpp),
[go2_robot_state_client.cpp](https://github.com/unitreerobotics/unitree_sdk2/blob/main/example/go2/go2_robot_state_client.cpp),
[unitree_sdk2_python](https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2_python/master/README.md)).
[unitree_ros2](https://raw.githubusercontent.com/unitreerobotics/unitree_ros2/master/README.md): Humble recommended, `rmw_cyclonedds_cpp` with CycloneDDS 0.10.2 rebuilt from
source, `CYCLONEDDS_URI` naming the NIC; topics `/sportmodestate`, `/lowstate`, `/lowcmd`, `/wirelesscontroller`, `/utlidar/cloud`; the example publishes `/lowcmd` at 5 ms with a
CRC.

**Boot, e-stop, teleop, data.** The developer docs are JS-rendered and did not fetch on 2026-09-06, so the power-on sequence and remote combos are (unverified). What the code
shows: `Damp` is the safe state, `L2+R2` enters debug mode, and the RL deploy script exits through a damping command ([deploy_real
README](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/README.md)). No hardware e-stop on the body (unverified). Teleop through the
shipped remote, the app, `/wirelesscontroller`, or `SportClient.Move`. Loggable: `lowstate` (q, dq, tau, IMU, foot force on EDU), `/utlidar/cloud`, the front camera via
`go2_video_client`; record with `rosbag2`.

**Learned policies.** Walk These Ways on Go1 EDU over the legacy SDK ([arXiv:2212.03238](https://arxiv.org/abs/2212.03238)); Extreme Parkour from one depth camera
([arXiv:2309.14341](https://arxiv.org/abs/2309.14341)); UMI on Legs on a Go2 with an arm ([arXiv:2407.10353](https://arxiv.org/abs/2407.10353)). unitree_rl_gym trains Go2 but ships
real-robot deploy configs only for G1, H1, H1_2 ([unitree_rl_gym](https://github.com/unitreerobotics/unitree_rl_gym)); Go2 and B2 are in
[unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco) for sim2sim.

### Boston Dynamics Spot with Spot Arm

**Specs** ([Spot](https://bostondynamics.com/products/spot/), [about Spot](https://dev.bostondynamics.com/docs/concepts/about_spot), [Spot
Arm](https://bostondynamics.com/products/spot/arm/)): 33.8 kg, 1.6 m/s, 14 kg payload, 300 mm steps, IP54; five stereo pairs, 360 deg, 4 m range; battery 564 Wh on the product page
and 605 Wh in the SDK docs, "average runtime 90 mins", 60 min recharge; two DB25 payload ports at 35 to 58.8 V, 150 W each. Arm: 6 DOF, "almost one meter reach", 11 kg lift, 25 kg
drag, 4K gripper camera with ToF and IMU. No price shown. Compute: CORE I/O with a Jetson Xavier NX running Docker "Spot Extensions" ([CORE
I/O](https://dev.bostondynamics.com/docs/payload/coreio_documentation)); the RL Researcher Kit adds an AGX Orin payload and the joint-level licence ([BD
blog](https://bostondynamics.com/blog/starting-on-the-right-foot-with-reinforcement-learning/)), price (unverified).

**Control, SDK, ROS 2.** `spot-sdk` 5.1.9, Python and protos over gRPC with TLS ([spot-sdk](https://github.com/boston-dynamics/spot-sdk)). Arm: joint, Cartesian trajectory with
optional force, gaze, stow, door, constrained manipulation, impedance ([arm docs](https://dev.bostondynamics.com/docs/concepts/arm/readme)); the arm "has no proximity awareness of
its own" and the body walks to follow a Cartesian target under `FollowArmCommand` ([arm concepts](https://dev.bostondynamics.com/docs/concepts/arm/arm_concepts)). Joint Control
API: beta, 100 to 333 Hz, special licence, every command carries `end_time` ([Joint Control](https://dev.bostondynamics.com/docs/concepts/joint_control/readme)). One lease owner
per resource ([lease](https://dev.bostondynamics.com/docs/concepts/lease_service)); time sync before any command. [spot_ros2](https://github.com/RAI-Opensource/spot_ros2) (MASKOR
and RAI Institute): 22.04 and Humble only, spot-sdk 5.0.1, `spot_hardware_interface` for ros2_control; publish rates (unverified).

**Boot, e-stop, teleop, data.** Motors power on only when every registered E-Stop endpoint has checked in at level `NONE` within its timeout; `SETTLE_THEN_CUT` sits first; from 3.3
the service is optional ([E-Stop service](https://dev.bostondynamics.com/docs/concepts/estop_service)). Teleop by tablet or Orbit
([Orbit](https://bostondynamics.com/products/orbit/)). Data Acquisition stores images, robot state and plugin sensors as ZIP or BDDF, an indexed time-series container readable with
`bosdyn.bddf` ([data acquisition](https://dev.bostondynamics.com/docs/concepts/data_acquisition_overview), [BDDF](https://dev.bostondynamics.com/docs/concepts/bddf)); robot state
carries battery, E-Stop state, foot contacts, faults and per-joint position, velocity, acceleration and load.

**Learned policies.** Production RL step-and-posture layer over MPC ([BD blog](https://bostondynamics.com/blog/starting-on-the-right-foot-with-reinforcement-learning/)); RL
locomotion "over 5.2 m/s" on the Researcher Kit ([arXiv:2504.17857](https://arxiv.org/abs/2504.17857)); model-based RL loco-manipulation with the arm
([arXiv:2501.10499](https://arxiv.org/abs/2501.10499)); Spot-Compose retrieval 51%, drawer opening 82% ([arXiv:2404.12440](https://arxiv.org/abs/2404.12440)).

### ANYbotics ANYmal

**Specs** ([ANYmal](https://www.anybotics.com/robotics/anymal/), [ANYmal X](https://www.anybotics.com/robotics/anymal-x/)): 20x zoom, thermal, 360 deg LiDAR, six depth and two
teleop cameras, ultrasonic microphone; two Intel i7 (8th gen); 90 min runtime, 3 h charge; 0.75 m/s, 2 km per charge, 10 kg payload, IP67; hardware e-stop, warning light, safety
handles. ANYmal X is the ATEX Zone 1 variant with 2026 specs "coming soon". Battery Wh, mass, and whether research units are purchasable in 2026 (unverified; research and partner
pages 404). ETH lists "less than 30 kg", over 2 h ([ETH RSL](https://rsl.ethz.ch/robots-media/anymal.html)).

**Control and ROS.** The ANYmal Research community gets "full access to ANYmal's control software, simulation, documentation" on a ROS stack; distro and rates not public
([anymal-research.org](https://www.anymal-research.org/)). Public repos hold only simple URDFs ([anymal_c](https://github.com/ANYbotics/anymal_c_simple_description)); the research
docs portal failed TLS on 2026-09-06.

**Learned policies.** The platform behind [Hwangbo 2019](https://arxiv.org/abs/1901.08652), [Lee 2020](https://arxiv.org/abs/2010.11251), [Rudin
2021](https://arxiv.org/abs/2109.11978), [Miki 2022](https://arxiv.org/abs/2201.08117); arm door opening at 95% ([arXiv:2409.04882](https://arxiv.org/abs/2409.04882)); Isaac Lab
ships its ANYDrive 3 LSTM actuator net ([anymal.py](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_assets/isaaclab_assets/robots/anymal.py)).

## Bimanual research platforms

### ALOHA, ALOHA 2, Mobile ALOHA

**ALOHA** ([ACT, arXiv:2304.13705](https://arxiv.org/html/2304.13705), [repo](https://github.com/tonyzhaozh/aloha)): two ViperX 300 followers, two WidowX 250 leaders, "less than
$20k"; four Logitech C922x at 480x640; teleop and recording at 50 Hz; 14-dim action; ROS 1 Noetic, HDF5; teleop starts when the leader gripper closes; `sleep.py` before shutdown.
**ALOHA 2** ([arXiv:2405.02292](https://arxiv.org/html/2405.02292)): low-friction rail grippers (leader force 14.68 N down to 0.84 N), hanging retractors for gravity compensation,
four RealSense D405 (848x480, global shutter), ROS 2; system-identified MuJoCo model in [mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie/tree/main/aloha);
cost and compute (unverified). **Mobile ALOHA** ([arXiv:2401.02117](https://arxiv.org/pdf/2401.02117), [repo](https://github.com/MarkFzp/mobile-aloha)): AgileX Tracer base
($7,000), $32k total, 1.26 kWh 14 kg battery, 75 kg, ~1.42 m/s, laptop with RTX 3070 Ti; three C922x at 50 Hz; the operator tethered at the waist back-drives the base; ROS 1, base
over CAN-to-USB, HDF5 with a 2-dim base action; 50 demos per task co-trained with 825 static episodes; no e-stop documented (unverified). Policies: ACT, ALOHA Unleashed on ALOHA 2
([arXiv:2410.13126](https://arxiv.org/abs/2410.13126)), pi0 ([arXiv:2410.24164](https://arxiv.org/abs/2410.24164)).

### Trossen AI (WidowX AI) and the legacy Interbotix ALOHA

**Lineup 2026-09-06** ([trossenrobotics.com/ai](https://www.trossenrobotics.com/ai), [Stationary AI](https://www.trossenrobotics.com/stationary-ai), [Mobile
AI](https://www.trossenrobotics.com/mobile-ai)): WidowX AI arm $4,545.95 base, $4,685.95 leader, $4,995.95 follower with D405; Solo AI $11,385.95 to $23,995.95; Stationary AI (two
leader-follower pairs, four D405, desktop) $23,995.95, TOTL workstation with RTX 5090 +$10,995.95; Mobile AI (two pairs, three D405, SLATE base) $33,695.95, $40,025.80 with laptop.
WidowX AI: 6 DOF, 1.5 kg, 0.769 m, 4 kg, 24 V / 15 A, Ethernet, "500Hz control frequency" on the marketing page
([spec](https://docs.trossenrobotics.com/trossen_arm/main/specifications/wxai.html)). SLATE base: 40 kg, 70 kg payload, 1.0 m/s, 24 V 18 Ah, e-stop switch
([SLATE](https://docs.trossenrobotics.com/slate_docs/specifications.html)).

**SDK, ROS 2, teleop** ([concepts](https://docs.trossenrobotics.com/trossen_arm/main/programming_guide/concepts.html)): `pip install trossen-arm`, Python 3.10 to 3.13; modes Idle
(braked), Position, Velocity, External Effort (gravity and friction compensated, back-drivable for teleop), Effort; UDP for real-time command; on error the controller halts to Idle
until `clear_error`. ROS 2 Humble and Jazzy with MoveIt ([ROS 2](https://docs.trossenrobotics.com/trossen_arm/main/tutorials/ros2.html)); LeRobot via the `lerobot_trossen` plugin;
Meta Quest teleop with a grip-trigger deadman ([trossen_vr](https://github.com/TrossenRobotics/trossen_vr)). Legacy ALOHA kit on Humble: `ros2 launch aloha aloha_bringup.launch.py
robot:=aloha_stationary|aloha_solo|aloha_mobile`; "Terminating bringup while the arms are not in their sleep configurations will cause them to collapse!"; `record_episodes.py`
writes HDF5 with 480x640 images and 14-dim qpos and action ([bringup](https://docs.trossenrobotics.com/aloha_docs/2.0/operation/bringup_shutdown.html), [data
collection](https://docs.trossenrobotics.com/aloha_docs/2.0/operation/data_collection.html)).

### Galaxea R1 Pro and R1 Lite

**R1 Pro** ([page](https://galaxea-dynamics.com/products/galaxea-r1-pro-universal-humanoid-robot)): 26 DOF (7-DOF arms, 4-DOF torso, omnidirectional chassis at 1.5 m/s), 1.70 m,
126 kg, 3.5 kg rated per arm, 86 cm reach, 150 N gripper, two 1920x1536 head cameras, LiDAR plus IMU, Jetson AGX Orin 32 GB, VR teleop plus RC transmitter, $69,999. **R1 Lite**
([page](https://galaxea-dynamics.com/products/6-dof-general-mobile-manipulation-platform)): 23 DOF (6-DOF arms, 3-DOF torso), 96 kg, i9-12900HK, stereo head plus mono wrist
cameras, single-button e-stop controller, $39,999. Battery, runtime, ROS version and boot (unverified; docs sub-pages did not render; SDK V2.4.0 per [docs
home](https://docs.galaxea-dynamics.com/home/)). Galaxea Open-World Dataset and the G0 VLA were collected on R1 Lite ([arXiv:2509.00576](https://arxiv.org/abs/2509.00576)); GMR
retargets to R1 Pro ([GMR](https://github.com/YanjieZe/GMR)).

### AgiBot G1, A2, X2 and AgileX Cobot Magic

**AgiBot G1** ([page](https://www.agibot.com/products/G1)): 1.30 to 1.80 m, 150 kg, 26 DOF, 6-DOF arms with 3 kg continuous, wheeled chassis, three RGB-D plus five fisheye cameras,
six-axis F/T on both wrists, chassis RGB-D and LiDAR, Jetson AGX Orin 64 GB, over 4 h; "designed for data collection and model inference". **A2**: 1.69 m, 69 kg, "40+ active DoF",
700 Wh, 2 h ([A2](https://www.agibot.com/products/A2)). Store: A2 Lite $44,560, X2 $24,240; G1 and G2 unpriced ([store](https://store.agibot.com/)). Third-party SDK for G1 and G2
(unverified); X1 hardware and training code are open ([AgibotTech](https://github.com/AgibotTech)). AgiBot World: "over 1 million trajectories across 217 tasks", GO-1 latent-action
model ([arXiv:2503.06669](https://arxiv.org/abs/2503.06669)), Beta release 1,003,672 trajectories, 43.8 TB, converts to LeRobot
([AgiBot-World](https://github.com/OpenDriveLab/AgiBot-World)); Genie Sim 3.2.0 on Isaac Sim 5.1 ([genie_sim](https://github.com/AgibotTech/genie_sim)). **Cobot Magic**: four arms
on a Tracer base, "uses Mobile ALOHA", price on request, arm model (unverified) ([Cobot Magic](https://global.agilex.ai/products/cobot-magic)).
## Humanoids

Two groups. Unitree, Booster, Fourier, PND and Galbot sell to third parties and publish SDKs. Figure, Agility, Apptronik, 1X and Tesla are partner or consumer programmes with no
public SDK found on 2026-09-06; their rows are reported from vendor blogs or press.

### Unitree G1, H1, H1-2, H2

**Specs** ([G1](https://www.unitree.com/g1), [H1](https://www.unitree.com/h1), [H2](https://www.unitree.com/H2)):

| | G1 / G1 EDU | H1 / H1-2 | H2 / H2 EDU |
|---|---|---|---|
| DOF | 23 / 23 to 43 (Dex3-1 adds 7 per hand) | 13 / 27 | 31 |
| Height, mass | 1.32 m, ~35 kg | ~1.80 m, ~47 kg / ~1.78 m, ~70 kg | 1.82 m, ~70 kg |
| Battery, runtime | 9,000 mAh quick-release, ~2 h (Wh unverified) | 15 Ah 0.864 kWh at 67.2 V max | 15 Ah 0.972 kWh at 75.6 V, ~3 h |
| Compute | 8-core CPU; Orin module on EDU (Jetson Orin NX per [ExBody2](https://arxiv.org/html/2412.13196)) | Intel i5 platform plus i7 user PC | i5 / i7 EDU, "2070 TOPS chip" |
| Sensors | depth camera plus 3D LiDAR (models not named on the page), 4-mic array | 3D LiDAR plus depth camera | binocular camera, mic array |
| Price 2026-09-06 | US$13,500; EDU contact sales; "secondary development" EDU only | H1 listed $90,000 "contact us for the real price" | $29,900; EDU contact sales |

Dex3-1 hand: 7 DOF, 33 pressure sensors, 710 g, 500 g load, 1 kHz bus ([Dex3-1](https://www.unitree.com/Dex3-1)). The 29-DOF G1 used in TWIST, AMO and ASAP is the EDU build
([TWIST](https://arxiv.org/html/2505.02833)).

**Control, SDK, ROS 2.** Same `unitree_sdk2` and `unitree_ros2` stack as the quadrupeds; G1 and H1-2 use the `unitree_hg` IDL, H1 `unitree_go`; the G1 low-level example runs at 2
ms on `rt/lowcmd`, `rt/lowstate`, `rt/secondary_imu` with 29 motors
([g1_ankle_swing_example.cpp](https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2/main/example/g1/low_level/g1_ankle_swing_example.cpp)). The unitree_ros2 README lists
Go2, B2, H1 but not G1 (unverified whether it works unchanged). `unitree_sim_isaaclab` gives G1 29-DOF and H1-2 in Isaac Lab on the same DDS
([unitree_sim_isaaclab](https://github.com/unitreerobotics/unitree_sim_isaaclab)).

**Boot, e-stop, modes.** From the RL deploy README: hang the robot, power on into zero-torque mode, `L2+R2` for debugging mode, `start` for default pose, `A` to step, `select` for
damping mode and exit ([deploy_real README](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/deploy/deploy_real/README.md)). The official quick-start page did
not render; other combos and the e-stop procedure are (unverified). Damping is the safe state.

**Teleop and data.** `xr_teleoperate` drives G1, H1 and H2 arms from Apple Vision Pro, Quest 3 or PICO 4 Ultra with Dex1, Dex3, Inspire or BrainCo hands
([xr_teleoperate](https://github.com/unitreerobotics/xr_teleoperate)); `unitree_IL_lerobot` records JSON episodes (images, depth, audio, state, action), converts to LeRobot v3.0
and trains ACT, Diffusion, pi0/pi0.5 and GR00T ([unitree_IL_lerobot](https://github.com/unitreerobotics/unitree_IL_lerobot)); LeRobot has an in-tree `unitree_g1` class with a
Homunculus exoskeleton teleoperator ([LeRobot G1 docs](https://huggingface.co/docs/lerobot/unitree_g1)).

**Learned policies.** H1: H2O, OmniH2O, ExBody, Open-TeleVision, HOVER, HumanPlus (33-DOF custom build). G1: ExBody2, TWIST, TWIST2, HOMIE, AMO, ASAP, BeyondMimic. Sources in
`library/topics/whole-body-and-locomotion-control.md`. GR00T N1.7 ships `UNITREE_G1` and `UNITREE_G1_SONIC` embodiments ([Isaac-GR00T](https://github.com/NVIDIA/Isaac-GR00T)).

### Booster T1, T2, K1

Sold openly; "38 of 59 teams competed on Booster robots" at RoboCup 2026 (vendor claim, [booster.tech](https://www.booster.tech/)). **T1**
([T1](https://www.booster.tech/booster-t1)): 1.18 m, ~30 kg, 23 DOF (41 with hands), AGX Orin 200 TOPS plus i7-1370P on Standard, depth camera, 9-axis IMU, 10.5 Ah, 2 h walking or
4 h standing, 130 N m peak. **T2** ([T2](https://www.booster.tech/booster-t2)): ~1.4 m, ~42 kg, 31 DOF, 3 m/s, 10 kg dual-arm payload, 48 V 10 Ah, 2 h walking; Pro has Jetson Thor
T5000. **K1** ([K1](https://www.booster.tech/booster-k1)): 0.95 m, 19.5 kg, 22 DOF, from $5,999. T1 and T2 prices (unverified).

**SDK, ROS 2, safety.** C++ and Python over Fast DDS on Ubuntu 22.04 ([booster_robotics_sdk](https://github.com/BoosterRobotics/booster_robotics_sdk)); `booster_deploy` on Humble
with `/low_state` and `/low_cmd`, MuJoCo and Webots sim2sim ([booster_deploy](https://github.com/BoosterRobotics/booster_deploy)); `booster_gym` (Isaac Gym) and `booster_train`
(Isaac Lab 2.2, BeyondMimic tracking) ([BoosterRobotics](https://github.com/BoosterRobotics)). The robot "automatically switches to DAMP mode" on loss of control; soft e-stop from
joystick, app or back-panel button ([K1 overview](https://docs.booster.tech/docs/product-manual/k1/getting-started/overview/)). Control rate (unverified). TWIST also ran on a T1
([TWIST](https://arxiv.org/html/2505.02833)).

### Fourier GR-1, GR-2, GR-3, N1

GR-3: 55 DOF, 1.65 m, 71 kg ([GR-3 docs](https://support.fftai.com/gr3/)); GR-1 and GR-2 specs, battery, price and availability (unverified; fftai.com pages are JS-only). Aurora
SDK 1.3.0 covers GR-1P, GR-2, GR-3 and N1 with `fourier_aurora_client` on pip ([fourier_aurora_sdk](https://github.com/FFTAI/fourier_aurora_sdk)); N1 speaks Zenoh on Ubuntu 22.04
([N1 docs](https://fftai.github.io/fourier-grx-N1/)); `Wiki-GRx-Gym` and `Wiki-GRx-Deploy` (v4.0.0 changed degrees to radians) plus Vision Pro or Quest 3 teleop with DAQ recording
([FFTAI](https://github.com/FFTAI), [teleoperation](https://github.com/FFTAI/teleoperation)). GR00T N1 was evaluated on a GR-1
([arXiv:2503.14734](https://arxiv.org/abs/2503.14734)); HOMIE and Open-TeleVision also used GR-1.

### PND Robotics Adam and Adam-U

Adam: 1.67 m, 60 to 63 kg, 25 to 43 DOF by tier, QDD joints, 1,172 Wh, NUC12 i7 for motion plus Jetson Orin NX 16 GB, RealSense D455 or ZED Mini, WBC plus MPC on board
([wiki](https://wiki.pndbotics.com/robot/humanoid_robot/)); Adam-U is the upper body on a lift base, 31 DOF, 26 kg, ROS 2 Humble
([Adam-U](https://wiki.pndbotics.com/half_robot/half_robot/)). Repos: `pnd_sdk_python` and `pnd_ros2` on CycloneDDS 0.10.2, `pnd_rl_gym`, `pnd_isaac_lab`, `pnd_teleoperation`
(mocap retargeting); `adam_u_deploy` uses `rt/lowcmd`, `rt/lowstate`, `rt/handcmd`, `rt/handstate` with Zero, UserControl, Func and Stop modes and an Xbox "safe exit"
([pndbotics](https://github.com/pndbotics), [adam_u_deploy](https://github.com/pndbotics/adam_u_deploy)). Control rate, runtime and price (unverified).

### Galbot G1 (wheeled)

21 DOF (two 7-DOF arms, 3-DOF waist, 2-DOF leg lift, 2-DOF neck) on a four-wheel omnidirectional base, 1.73 m max, 5 kg per arm, 48 V 30 Ah, 8 h, AGX Orin 64 GB, four RGB plus two
depth cameras, two six-axis F/T sensors, 3D LiDAR, sold through JD.com ([G1](http://www.galbot.com/g1/)). GalbotSDK exposes perception, planning, control and navigation for G1
Lite, G1 and S1 ([developer](https://developer.galbot.com/)). GraspVLA came from Galbot but was evaluated on a Franka ([arXiv:2505.03233](https://arxiv.org/html/2505.03233)). Price
and ROS support (unverified).

### Reported only: Figure, Agility Digit, Apptronik Apollo, 1X NEO, Tesla Optimus

| Platform | What the vendor or press states | Source |
|---|---|---|
| Figure 03 with Helix 02 | Helix: 7B VLM at 7 to 9 Hz over an 80M visuomotor policy at 200 Hz, 35-DOF action space; Helix 02 adds a 10M whole-body controller at 1 kHz trained in "200k+ parallel envs"; F.03 has palm cameras, fingertip tactile, 2 kW inductive foot charging; height, mass, DOF, price not disclosed | [Helix](https://www.figure.ai/news/helix), [Helix 02](https://www.figure.ai/news/helix-02), [Figure 03](https://www.figure.ai/news/introducing-figure-03) |
| Agility Digit | 35 lb payload, 4 h battery, Arc cloud fleet manager; deployed at GXO, Schaeffler, Amazon; FCC and NRTL certified 2025; SPAC announced 2026-06-24; no spec sheet or developer API found | [solutions](https://www.agilityrobotics.com/solutions), [company](https://www.agilityrobotics.com/company), [investors](https://www.agilityrobotics.com/investors) |
| Apptronik Apollo | 172 cm, 72.5 kg, 25 kg lift, ~4 h swappable battery (press); partners Google DeepMind, NVIDIA, Mercedes-Benz, GXO, Jabil; no SDK | [Robot Report](https://www.therobotreport.com/apptronik-unveils-apollo-humanoid-robot/), [apptronik.com](https://apptronik.com/), [Gemini Robotics](https://deepmind.google/discover/blog/gemini-robotics-brings-ai-into-the-physical-world/) |
| 1X NEO | 1.68 m, 30 kg, 842 Wh, 4 h, tendon-driven, walk 1.4 m/s, 22 dB; $20,000 or $499/month, US deliveries 2026; VR and app teleop with "Expert Mode" remote supervision; 25-DOF hands | [NEO](https://www.1x.tech/neo), [order](https://www.1x.tech/order), [hands](https://www.1x.tech/discover/neos-hands) |
| Tesla Optimus | Gen 3 "finalized", external sales "as early as" H2 2027, production described as slow, teleoperation visible in demos (all press) | [Electrek 2026-08-20](https://electrek.co/2026/08/20/tesla-jpmorgan-fremont-fsd-v15-hw4-optimus-2027/), [Electrek guide](https://electrek.co/guides/tesla-optimus/) |

## Cross-family notes

- DDS on the wire. Unitree, Booster and PND expose the robot's own DDS traffic (CycloneDDS 0.10.2 or Fast DDS); PAL pins Cyclone with multicast off and a peer list. Isolate the
  robot NIC from the site LAN and set the domain deliberately, or two robots see each other's `lowcmd`
  ([unitree_ros2](https://raw.githubusercontent.com/unitreerobotics/unitree_ros2/master/README.md),
  [PAL](https://docs.pal-robotics.com/25.01/development/robot-communication-ros2.html)).
- ROS 2 distro spread on 2026-09-06: Humble (Unitree, Spot, PAL, Booster, PND, AgileX, Trossen legacy ALOHA), Jazzy (Stretch 4, ROBOTIS AI Worker, Clearpath, Trossen AI), ROS 1
  only (Fetch, MiR bridge, original ALOHA and Mobile ALOHA). Plan one container per robot.
- Safe states differ by class: damping mode on Unitree and Booster, `SETTLE_THEN_CUT` on Spot, breaker drop on Fetch and Clearpath, torque-off until A on the AI Worker,
  Idle-with-brakes on Trossen AI arms, and "arms collapse" if the legacy ALOHA bringup dies outside sleep pose.
- Every platform above that records for learning lands in LeRobot format or HDF5 that converts to it (Stretch AI, AI Worker, Unitree IL, Trossen, AgiBot World, Galaxea). Pick the
  dataset schema before the first episode; see `library/tools/lerobot.md`.
- Record controller firmware, SDK, ROS driver and DDS versions on arrival, with serial and vendor contact, in `hardware/README.md`.

## Contacts / field log

- Who to contact per vendor, units on hand, serials, firmware: ROBOTIS AI Worker (details to fill); others as they arrive.

## Sources

Mobile manipulators: [Stretch 4](https://docs.hello-robot.com/stretch-4-quick-start-guide/robot-overview.md), [Stretch 3 legacy](https://hello-stretch3.com/stretch-3-product),
[stretch_ai](https://github.com/hello-robot/stretch_ai), [TIAGo Pro hardware](https://docs.pal-robotics.com/25.01/hardware/tiagopro/hardware-overview.html), [TIAGo
hardware](https://docs.pal-robotics.com/25.01/hardware/tiago/hardware-overview.html), [Fetch docs](https://fetchrobotics.github.io/docs/), [AI Worker
hardware](https://ai.robotis.com/ai_worker/hardware_ai_worker.html), [AI Worker software](https://ai.robotis.com/ai_worker/software_ai_worker.html), [Husky A300
manual](https://docs.clearpathrobotics.com/docs_robots/outdoor_robots/husky/a300/user_manual_husky), [Ridgeback
manual](https://docs.clearpathrobotics.com/docs_robots/indoor_robots/ridgeback/user_manual_ridgeback),
[MiR250](https://mobile-industrial-robots.com/products/robots/mir250/specifications), [mir_robot](https://github.com/DFKI-NI/mir_robot), [AgileX
manuals](https://global.agilex.ai/pages/download-manual), [ugv_sdk](https://github.com/agilexrobotics/ugv_sdk). Quadrupeds: [Go2](https://www.unitree.com/go2),
[B2](https://www.unitree.com/b2), [unitree_sdk2](https://github.com/unitreerobotics/unitree_sdk2), [unitree_ros2](https://github.com/unitreerobotics/unitree_ros2),
[Spot](https://bostondynamics.com/products/spot/), [Spot SDK concepts](https://dev.bostondynamics.com/docs/concepts/README),
[spot_ros2](https://github.com/RAI-Opensource/spot_ros2), [ANYmal](https://www.anybotics.com/robotics/anymal/), [anymal-research](https://www.anymal-research.org/). Humanoids:
[G1](https://www.unitree.com/g1), [H1](https://www.unitree.com/h1), [H2](https://www.unitree.com/H2), [xr_teleoperate](https://github.com/unitreerobotics/xr_teleoperate),
[unitree_IL_lerobot](https://github.com/unitreerobotics/unitree_IL_lerobot), [Booster T1](https://www.booster.tech/booster-t1),
[booster_robotics_sdk](https://github.com/BoosterRobotics/booster_robotics_sdk), [Fourier GR-3](https://support.fftai.com/gr3/), [FFTAI](https://github.com/FFTAI), [PND
wiki](https://wiki.pndbotics.com/robot/humanoid_robot/), [pndbotics](https://github.com/pndbotics), [Galbot G1](http://www.galbot.com/g1/), [Figure Helix
02](https://www.figure.ai/news/helix-02), [Agility](https://www.agilityrobotics.com/solutions), [Apptronik](https://apptronik.com/), [1X NEO](https://www.1x.tech/neo), [Electrek
Optimus](https://electrek.co/guides/tesla-optimus/). Bimanual: [ACT](https://arxiv.org/abs/2304.13705), [ALOHA 2](https://arxiv.org/abs/2405.02292), [Mobile
ALOHA](https://arxiv.org/abs/2401.02117), [Trossen AI](https://www.trossenrobotics.com/ai), [WidowX AI
spec](https://docs.trossenrobotics.com/trossen_arm/main/specifications/wxai.html), [ALOHA docs 2.0](https://docs.trossenrobotics.com/aloha_docs/2.0/specifications.html), [Galaxea
R1 Pro](https://galaxea-dynamics.com/products/galaxea-r1-pro-universal-humanoid-robot), [Galaxea dataset](https://arxiv.org/abs/2509.00576), [AgiBot
G1](https://www.agibot.com/products/G1), [AgiBot World](https://arxiv.org/abs/2503.06669), [Cobot Magic](https://global.agilex.ai/products/cobot-magic), [LeRobot
robots](https://github.com/huggingface/lerobot/tree/main/src/lerobot/robots).
