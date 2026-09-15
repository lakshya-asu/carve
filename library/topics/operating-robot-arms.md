---
title: Operating robot arms on site (UR, Franka, Kinova, xArm, KUKA, ABB, FANUC, Stäubli, Denso, Yaskawa)
date: 2026-09-06
tags: [topic, hardware, robot-arm, operations, safety, pendant, field, bring-up]
status: draft
source: vendor manuals and driver docs (links inline), field notes marked
---

# Operating robot arms on site

## What it is

The operator's view of an arm: which button releases the brakes, where the safety limits live,
how to hand-guide, teach and run a native program, hand control to an external PC and take it
back, what the first error message means, where logs and backups are, and how to shut down so
the next person can start. Specs, control rates and ROS 2 drivers are in
[[library/hardware/robot-arms]] and [[library/topics/connecting-to-real-robots]] and are not
repeated. This is what you do at the pendant before and after the policy runs.

## Why it matters in the field

- The integrator commissions the cell and leaves. From then on the forward-deployed engineer
  is the person who clears the protective stop, reads the fault code, and restores the backup.
- External control on every vendor is gated by a native program or a pendant-owned mode (UR
  External Control program, Franka FCI activation, ABB EGM RAPID instructions, KUKA FRI app,
  FANUC RMI or Stream Motion option). If you cannot run the native side you cannot run the policy.
- Safety configuration is the customer's risk assessment made concrete, and its checksum is
  what an auditor compares. Changing a joint limit for convenience changes the checksum and
  invalidates the assessment ([[library/topics/safety-for-learned-policies]]).

## Universal Robots e-Series (PolyScope 5) and PolyScope X

PolyScope 5.26 manual pages below live under
`https://www.universal-robots.com/manuals/EN/HTML/SW5_26/Content/prod-usr-man/software/PolyScope/content/`
(abbreviated `PS5/`); PolyScope X 10.14 under the matching `SW10_14/.../PolyScopeX/` tree (`PSX/`).

**Boot.** Pendant power button; a popup says the robot must be initialized. Initialize screen: ON, wait
for Idle, START releases the brakes (`PS5/introduction_g5/quickstart_en.htm`). PolyScope X: Power On,
then the brake release button (`PSX/polyx-initialize/polyx-initialize.htm`).

**Safety configuration.** Password protected (`PS5/safety_g5/Safety_setting_basics_g5_en.htm`).
Normal is the default limit set; Reduced applies past a Trigger Reduced plane or on a configurable
input; Recovery mode drives out of a violated limit (`Safety_modes_g5_en.htm`). Joint limits are
per-joint speed and position range in Normal and Reduced columns (`Joint_limits_g5_en.htm`); robot
limits cover power, momentum, stopping time and distance, tool and elbow speed and force, and "this
limit considers the payload a part of the robot" (`Robot_limits_g5_en.htm`). Safety inputs include
Reduced, Safeguard (Stop Category 2), Emergency Stop (Category 1), Operational Mode, Freedrive, and
3-Position Enabling Device, which in Manual mode "must be pressed and held in the center-on position"
(`Safety_IO_g5_en.htm`). Payload, CoG and inertia are entered under Installation, not Safety
(`PS5/installation_g5/Payload_en.htm`). The Safety Checksum top right "changes if and only if the
safety configuration is changed" (`PSX/polyx-introduction/polyx-Safety-Overview.htm`).

**Freedrive.** Freedrive button on the pendant, or the 3PE button on a 3PE pendant; verify the
configured payload matches, and enabling Freedrive while already moving the arm "can cause drift and
faults" (`PS5/introduction_g5/Freedrive_ur20_en.htm`).

**Teach, run, external control.** Waypoints are program nodes; Play runs them; the speed slider scales
streamed trajectories too ([[library/hardware/robot-arms]]). PolyScope 5: `externalcontrol-X.Y.Z.urcap`,
External Control node in the program, Play; minimum PolyScope 5.9.4
([robot setup](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/robot_setup.html)).
PolyScope X: `external-control-X.Y.Z.urcapx`, PolyScope 10.8.0 or later
([URCapX](https://github.com/UniversalRobots/Universal_Robots_ExternalControl_URCapX)). Headless mode
sends URScript directly, needs Remote Control mode on e-Series, and a new program stops the running one
([operation modes](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_robot_driver/ur_robot_driver/doc/operation_modes.html)).
Run `ur_calibration` once per unit and keep the yaml with its serial: without it end-effector
positions "might be off in the magnitude of centimeters"
([ur_calibration](https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver/blob/main/ur_calibration/README.md)).

**Errors you will see first** (index `SW5_26/Content/Landingpages/Web/ErrorCodes.htm`, one page per
code under `PS5/prod-err-codes/topics/CODE_<n>.html`). C153 "Position deviates from path": "either
there was a collision, or a setting was incorrect"; A0 to A5 name the joint; check payload, CoG,
acceleration. C157/C158 "Collision detected by joint"; C159 path deviation; C162 payload-mass hint;
C163 after more than 50 protective stops in 8 hours. C4 communication, C4A15 "Communication with
joint 3 lost". The e-stop is the red pendant button, reset by twisting clockwise, and "not a
safeguard" per ISO 12100 (`complianceUR5e/H_g5_sections/safety_g5/emergency_stop.htm`). Log RTDE's
deviation and collision ratios with every action ([[library/hardware/robot-arms]]).

**Backups, logs, shutdown.** Log tab, Support file: a zip to USB, up to 10 minutes, not password
protected; Save Report keeps five reports (`PS5/log_g5/log_tab_en.htm`). File manager Backup copies
programs and installations to USB; `.old0` to `.old9` are rolling copies
(`PS5/filemanager_g5/file_manager_en.htm`). Magic files (unverified; support pages not fetched).
Shutdown: hamburger menu, Shutdown Robot, Power Off (`PS5/hamburger_menu_g5/shut_down_en.htm`).

## Franka FR3 (Desk, FCI, brakes, guiding)

Sources: [Operating Manual, system image 5.8](https://franka.de/hubfs/Operating%20Manual%20Franka%20Research%203_System_Image_5.8_R02216_1.1.1_EN.pdf)
("manual") and [libfranka docs](https://frankarobotics.github.io/docs/doc/libfranka/docs/getting_started.html).

**Boot and Desk.** Power the Control; open `https://robot.franka.de` (X5 network, DHCP) or
`https://<fci-ip>`; Unlock joints releases the brakes. Only the holder of the Single Point of Control
token can change settings, release brakes or run tasks, and the token resets on reboot (manual 5.2).
LEDs (manual 13.6, "not certified safety functions"): white idle or teach, yellow brakes locked or
warning, blue ready with brakes engaged, green executing (fast green: "FCI countdown"), red error,
magenta "conflicting input detected (e.g., manual guidance vs. automation)".

**Safety configuration.** Watchman at `https://robot.franka.de/watchman`; only a Safety Operator user
can edit, validate and integrate it. X3.1 e-stop (PL d, Cat. 3, Category 1 stop), X3.2 and X3.3 safe
inputs, X4 "dedicated to a 3-position External Enabling Device"; open X3.1 or X4 show pink in Desk
(manual). Collision thresholds are set by the client with `setCollisionBehavior`; above the upper
threshold the robot registers a collision and stops
([Robot](https://frankarobotics.github.io/libfranka/0.15.0/classfranka_1_1Robot.html)). FR3 versus
Panda Watchman differences (unverified).

**Guiding and native tasks.** The Pilot-Grip's Guiding-Mode button cycles Translation, Rotation, Free
("all seven joints can be moved") and User, where each Cartesian axis is movable or fixed and the
elbow can be locked (manual). Desk tasks run in Execution mode.

**External control (FCI).** Execution mode, top menu, Activate FCI; ready "when the blue LED is
active" (getting started). libfranka 0.18.0+ for system 5.9.0+, 0.15.0+ for 5.7.2+, 0.14.1+ for
5.7.0+, 0.13.3+ for 5.5.0+, 0.10.0+ for 5.2.0+
([compatibility matrix](https://frankarobotics.github.io/docs/doc/libfranka/docs/compatibility_matrix.html)).
Direct cable to the Control LAN port, PREEMPT_RT ([[library/topics/connecting-to-real-robots]]).

**Errors you will see first**
([Errors](https://frankarobotics.github.io/libfranka/0.15.0/structfranka_1_1Errors.html)):
`communication_constraints_violation`, "minimum network communication quality could not be held
during a motion" (20 late packets, or packet loss); `cartesian_reflex` and `joint_reflex`, your
collision threshold was exceeded; `joint_velocity_violation`; `power_limit_violation`;
`joint_motion_generator_velocity_discontinuity`, the command jumped
([[library/hardware/robot-arms]]). `automaticErrorRecovery()` resets after a collision; a human
confirms the workspace is clear first. Joint position error after a power failure with brakes open
needs the Desk joint recovery procedure (manual).

**Backups, logs, shutdown.** Desk exports tasks and settings; log download path (unverified).
Shutdown from Desk; when the Control's front fans stop, turn off the rear switch (manual 9.1.8);
switching off early, or leaving the switch on after a Desk shutdown, needs 1 to 2 minutes before
restart (9.1.9). Brake behaviour on power loss (unverified).

## Kinova Gen3 (Web App, Kortex API, admittance)

Source: [User Guide R07](https://www.kinovarobotics.com/uploads/User-Guide-Gen3-R07.pdf).

**Boot.** Hold the base power button 3 s; 10 s is a factory reset. Blinking blue power LED while
booting, solid green status LED when ready, within 30 s. Web App at 192.168.1.10, default
`admin`/`admin` (also the [SDK example default](https://github.com/Kinovarobotics/kortex/blob/master/api_python/examples/utilities.py));
change it on day one.

**Safety configuration.** Web App: safety thresholds, protection zones, Cartesian and joint speed
limits (also `ControlConfig` in the API), temperature shutdown thresholds, backups, users. Safeties are
Error (emergency stop) or Warning, grouped by base, actuators, interface module. No enabling device or
safety-rated I/O appears in the guide; the cell's safety function must come from outside the arm.

**Admittance and teach.** Wrist buttons: raised circle for Cartesian admittance, ring for joint
admittance, both for null-space (7 DOF). Actions and sequences are built in the Web App; the wired
Xbox gamepad jogs ([[library/hardware/robot-arms]]).

**External control.** Kortex over Ethernet, 40 Hz high level, 1 kHz low level on a wire
([[library/topics/connecting-to-real-robots]]). No activation step: close the Web App session and
gamepad before the client starts, or they fight for the arm.

**Errors, backups, shutdown.** In a fault the arm is unresponsive until cleared: gamepad left bumper,
or Clear Faults under Safety in the Web App; red base LED means fault or e-stop. Backups: Web App
backup management, API `createConfigurationBackup`, protection zones export XML or JSON, actions Export
All; a system log download (unverified). Shutdown: hold the base power button, with the wrist
supported "otherwise it may fall and cause damage".

## UFactory xArm (UFactory Studio, manual mode)

Sources: [hardware](https://docs.xarm.ufactory.cc/2.hardware_installation.html) and
[electrical](https://docs.xarm.ufactory.cc/3.controller_electrical_interface.html) manuals, UFactory
Studio manual ([settings](https://docs.ufactory.cc/user_manual/ufactoryStudio/7.settings.html),
[errors](https://docs.ufactory.cc/user_manual/ufactoryStudio/12.error_handling.html)),
[SDK API](https://github.com/xArm-Developer/xArm-Python-SDK/blob/master/doc/api/xarm_api.md).

**Boot.** Control box power until CONTROLLER lights; pull the e-stop up until ROBOT PWR lights;
browser to `<ip>:18333` (default 192.168.1.xxx); Live Control, Enable (SDK `motion_enable`).

**Safety configuration.** Reduced Mode limits linear speed, joint speed and joint range, I/O
triggerable; Safety Boundary limits the Cartesian range; CI0 to CI7 and CO0 to CO7 carry Protective
Stop and Reduced Mode. Dedicated inputs EI1/EI2 (e-stop) and SI0/SI1 (protective stop); e-stop removes
arm power within 300 ms. No SIL or PL rating found (unverified). Collision sensitivity is 1 to 5 in
Studio, 0 to 5 in the SDK.

**Manual mode and external control.** Mode 2 is zero-gravity drag teaching, entered from mode 0 with
payload and mounting set; `set_teach_sensitivity` 1 to 5. Streaming is `set_mode(1)` plus
`set_servo_angle_j`; modes 6 and 7 plan online for slow clients ([[library/hardware/robot-arms]]).

**Errors you will see first.** C control box, S servo, A SDK. C21 kinematic; C24 speed exceeds limit;
C31 abnormal current (check TCP payload, lower collision sensitivity); C35 safety boundary; C36 too
many delayed commands queued, the client is outrunning the arm. Clear: release the e-stop, Enable;
SDK `clean_error` then `motion_enable` and `set_state`.

**Backups, logs, shutdown.** Settings Export covers motion parameters, TCP offset and payload, I/O,
safety boundary, mounting, coordinate systems; Download pulls control box, servo and end-effector
error logs. Shutdown: e-stop to remove arm power, control box off, no restart within 5 s.

## KUKA LBR iiwa (smartPAD, Sunrise, FRI) and LBR iisy (iiQKA)

Sources: Sunrise Cabinet Med Instructions for Use V5 (2021) ("cabinet manual", manualslib copy;
kuka.com is login-walled); LBR iisy 3 R760 Assembly Instructions V5; [lbr-stack](https://github.com/lbr-stack/lbr_fri_ros2_stack);
[kroshu/kuka_drivers](https://github.com/kroshu/kuka_drivers).

**Boot, modes, enabling.** Modes T1 (250 mm/s at the flange, and "not subjected to safety-oriented
monitoring" unless added to the safety configuration), T2, AUT, CRR (controlled retraction); mode
change needs the key in the smartPAD; three enabling switches (four on smartPAD-2) with centre and
panic positions (cabinet manual pp. 30 to 34).

**Safety configuration.** `SafetyConfigurations.conf` in the Sunrise Workbench project, activated on
the smartPAD under Safety, Activation, with a password
([hardware setup](https://lbr-stack.readthedocs.io/en/latest/lbr_fri_ros2_stack/lbr_fri_ros2_stack/doc/hardware_setup.html)).
ESM states and a displayed checksum (unverified).

**Hand guiding.** Needs the enabling signal; 250 mm/s is preconfigured and exceeding it is a stop
trigger (cabinet manual pp. 28 to 32).

**External control (FRI).** Session states `MONITORING_WAIT` (insufficient quality),
`MONITORING_READY`, `COMMANDING_WAIT`, `COMMANDING_ACTIVE`; quality `POOR`, `FAIR` ("insufficient for
command mode"), `GOOD`, `EXCELLENT` (`friClientIf.h`, FRI 2.5, in lbr-stack). Send period 1 to 10 ms
set in the Sunrise app ([kroshu FRI](https://github.com/kroshu/kuka_drivers/blob/master/doc/wiki/3_Sunrise_FRI.md)).
Below GOOD the session drops to monitoring and commands are ignored (implied; explicit text
unverified). FRI 1.11 to 1.16 and 2.5 to 2.7 in lbr-stack.

**Mastering.** EMD mastering is documented for KSS; the iiwa procedure and "mastering lost" text
(unverified). iisy mastering pose 0, -90, 90, 0, 0, 0 degrees (assembly instructions p. 33).

**iisy.** KR C5 micro-2, iiQKA.OS2, smartPAD pro only (p. 17); wrist handle with enabling switch
(p. 13). External control for ROS 2 is KUKA ExternalAPI.Control (EAC), a toolbox from KUKA support,
over the KONI port, tested on iisy 3 R760 with iiQKA.OS1 1.2.14 and EAC 1.0.3; release single point
of control on the pendant first ([kroshu EAC](https://github.com/kroshu/kuka_drivers/blob/master/doc/wiki/1_iiQKA_EAC.md)).

**Backups, logs, shutdown.** Support asks for the System Software diagnosis package plus the Sunrise
projects (cabinet manual p. 109); keep the Workbench project in git. smartPAD log export and shutdown
sequence (unverified).

## ABB (FlexPendant, RobotStudio, EGM, RWS, SafeMove)

ABB documents are cited by ID; open with
`https://search.abb.com/library/Download.aspx?DocumentID=<ID>&LanguageCode=en&DocumentPartId=&Action=Launch`.

**Boot and modes.** Main switch, FlexPendant. OmniCore is keyless: option 3044-1 gives Auto, Manual
reduced speed, Manual full speed on the pendant; 3044-2 only Auto and Manual reduced (3HAC065034-001).
Manual reduced is 250 mm/s and needs the three-position enabling device in the FlexPendant
(3HAC077389-001). Motors On precedes motion.

**Safety configuration (SafeMove).** Safety controller "included as standard"; Visual SafeMove in
RobotStudio, safe I/O in the I/O Engineering Tool. Download, synchronise, validate, "Lock the
configuration"; the checksum identifies it and it "shall be validated and locked before the robot is
put into production". Grants: Safety Services, Lock Safety Controller Configuration, Commissioning
mode; a Safety User role. RobotWare 7.19 renamed Basic to Premium and Pro to Premium+ (options
3043-11 to 14, Collaborative 3043-3) (3HAC066559-001 Rev W).

**Lead-through.** GoFa: grab and move; enabled by the axis-5 thumb button, Jog menu or QuickSet, with
pendant write access (3HAC077390-001); listed for IRB 14050, CRB 15000, CRB 1810; Wizard blocks for
GoFa, SWIFTI, YuMi (3HAC065034-001).

**External control (EGM, RWS).** EGM streams UDP protobuf "every 4 ms with a control lag of 10-20 ms";
joint and pose modes via `EGMActJoint`/`EGMRunJoint`, `EGMActPose`/`EGMRunPose`, `EGMSetupUC`
(3HAC073319-001); option 689-1 on RobotWare 6, 3124-1 on OmniCore RobotWare 7 (3HAC073318-001). A
RAPID program running those instructions must be active before the client streams. RWS answers XML
or JSON with digest auth and UAS users ([RWS API](https://developercenter.robotstudio.com/api/rwsApi));
RWS 1.0 (RobotWare 6) and 2.0 (RobotWare 7) are incompatible, so `abb_librws` fails on 7.x
([abb_librws](https://github.com/ros-industrial/abb_librws)).

**Errors you will see first.** The event log is split by type (Operational, System, Motion, I/O,
Functional safety and others; 3HAC032104-001). 50024 corner path failure (3HAC065038-001). Collision detection is option 3107-1: `MotionSup` temporarily, the
Collision Detection Level parameter (default 100 percent) permanently (3HAC066554-001). 50026, 50204
(unverified).

**Backups, calibration, shutdown.** FlexPendant Settings, Backup and Recovery; a backup holds
`BACKINFO`, `HOME`, `RAPID` per task, `SYSPAR` (3HAC032104-001). Revolution counters must be updated
after a discharged battery or resolver error; fine calibration needs ABB tools (IRB 1200 manual,
3HAC046983-001); GoFa has no revolution counters and uses a torque sensor calibration routine
(3HAC077389-001). FlexPendant shutdown step (unverified).

## FANUC (teach pendant, DCS, RMI, ROS driver)

Manuals read from a public mirror ([FANUC-Robot-Manual](https://github.com/zhaomengkang/FANUC-Robot-Manual)).

**Boot and modes.** Main breaker, pendant enable. T1 caps TCP and flange at 250 mm/s; T2 is 100
percent and "not the Manual high speed specified in ISO 10218-1"; in AUTO the pendant cannot run
programs (B-83284EN/09, 5.2.2). Release or squeeze the deadman fully and the robot stops
(B-80687EN/17, 4.6). CRX uses the [Tablet TP](https://www.fanucamerica.com/products/robots/tablet-teach-pendant).

**Safety configuration (DCS).** Position/Speed Check, Joint Position Check, Cartesian Position Check,
Safe I/O Connect. Any edit raises SYST-212 "Need to apply to DCS param" until Apply with the 4-digit
master code (default 1111); the "signature number" is a CRC of the parameters (`$DCS_CRC_OUT[]`),
mismatch is SRVO-364 (B-83184EN/11, 1.3, 2.6). Record the signature at commissioning.

**Teach and run.** `.TP` programs on the pendant (`.LS` ASCII needs the ASCII Upload option).
Collision Guard sensitivity defaults to 100 percent, changed per program or on screen
(B-83284EN-2, 8).

**External control.** RMI (R912): ASCII JSON-like over TCP, `FRC_Connect` to port 16001, then the
returned port; no motion shorter than 40 ms (MAROGRMIM11191E Rev B). Stream Motion (J519) is the 8 ms
UDP path on port 60015, 1 kHz on R-50iA with S647. `fanuc_driver` needs Humble or Jazzy, J519 plus
R912 or S636, firmware V9.40P/81+ on R-30iB Plus
([requirements](https://fanuc-corporation.github.io/fanuc_driver_doc/main/docs/environment/system_requirements.html)).

**Errors you will see first** (MARRUEROR02171E Rev I): SRVO-001 operator panel e-stop, SRVO-002
pendant e-stop, SRVO-003 deadman released, SRVO-037 IMSTP input (external chain), SRVO-050 collision
detect, SRVO-062 BZAL (replace battery, PULSE RESET, remaster), SRVO-075 pulse not established (jog
one motor revolution), MOTN-017 software limit.

**Mastering, backups, shutdown.** Fixture, zero position, quick, quick single axis, single axis;
`$MASTER_ENB` 1 or 2 (B-83284EN/09 App. B). Pulsecoder batteries (four D cells on M-710iC, every 1.5
years; lithium on CRX) changed with power off lose all position data (MAROCM71009061E). File screen,
F4 BACKUP, "All of above"; Image backup saves F-ROM and S-RAM, restored by holding F1 and F2 at power
on (B-83284EN/09, 8.9). Image backup before any option install. Shutdown at the main breaker.

## Stäubli (SP2 pendant, uniVAL, HE arms)

**Pendant, modes, safety.** SP2 (7 inch, IP54) and SP2+ (10.1 inch, IP65) carry a three-position
deadman and e-stop (product range PDF, via Wayback; staubli.com blocks fetches). CS8C manual D28070504A p. 129: keyswitch for local, remote,
manual; manual at 250 mm/s with the enable button in the intermediate position; CS9 wording
(unverified). CS9 "optional SIL3-PLe safety functions": safe speed, stop, tool, zone, over FSoE or
ProfiSafe, configured in Stäubli Robotics Suite with 3D zones. Optional: ask what the unit carries.

**External control.** VAL 3 natively. uniVAL drive presents the arm as CiA 402 over EtherCAT,
POWERLINK, PROFINET or SERCOS with CAT3/PL d safety; uniVAL plc gives PLC function blocks.
[staubli_val3_driver](https://github.com/ros-industrial/staubli_val3_driver) is ROS 1 (CS8/CS9,
VAL 3 s7.7.2+, last push 2021); community ROS 2 port
[staubli_driver_ros2](https://github.com/ICube-Robotics/staubli_driver_ros2), paused Nov 2025.

**HE arms, calibration, backups.** TX2 HE and TS2 HE: NSF H1 oil, encapsulated IP65 with IP67 wrist
(TX2-140/160 IP67), stainless joints, "withstand exposure to water and a range of chemical
solutions"; high-pressure washdown wording not on the page (unverified). Joints must be adjusted after
a motor or encoder swap; offsets in `arm.cfx`; backup to FTP or USB from the Control Panel Bkup menu
(CS8C manual pp. 127, 152).

## Denso and Yaskawa, briefly

**Denso (RC8, RC9).** Pendant with three-position deadman and key for AUTO, MANUAL, TEACHCHECK;
mini-pendant for essentials ([pendants](https://www.densorobotics.com/products/teaching-pendants/)).
WINCAPS III offline programming. Remote control is b-CAP (ORiN2); slave mode streams at 125 Hz
minimum, one target per 8 ms, and needs the b-CAP Slave licence on RC8
([denso_robot_ros2](https://github.com/DENSORobot/denso_robot_ros2), Humble; RC9 "under
construction"). CALSET after a motor swap or dead encoder battery (DENSO support article 60000698513).

**Yaskawa (YRC1000, MotoROS2).** Mode switch REMOTE, PLAY, TEACH; servo power only at the enable
switch's middle position; TEACH caps 250 mm/s (YRC1000 Instructions RE-CTO-A221, motoman.com
178642-1CD.pdf). Smart Pendant for HC and GP up to 80 kg; FSU safe zones and speeds (details
unverified). MotoROS2 runs as a MotoPlus app, no SDK licence to deploy, needs the micro-ROS agent,
Foxy to Jazzy with Fast DDS, "not directly compatible with ros2_control"
([motoros2](https://github.com/Yaskawa-Global/motoros2)). Alarms (RE-CER-A600, 178644-1CD.pdf):
4107 OUT OF RANGE (ABSO DATA), position moved while off, check home marks; 4311 encoder data lost
from low battery; 4312 battery below 2.8 V. Backup: power on holding MAIN MENU, EX. MEMORY, CMOS.BIN
Save to SD or USB (RE-CTO-A221, 9.2).

## Common: daily checks

Before the first policy run of the shift, two minutes at the pendant:

- [ ] E-stop and any guard input tested once; the controller reports the stop
      ([[sops/robot-bring-up]] section 1).
- [ ] Safety configuration checksum matches the one photographed at commissioning.
- [ ] Payload and TCP shown on the pendant match the tool actually mounted.
- [ ] Speed slider or override at the value the run plan calls for.
- [ ] Arm moved to `home` with the pendant; displayed joint angles match the driver's
      `/joint_states` within encoder resolution.
- [ ] Log tab shows no new warnings since yesterday's shutdown; if it does, read them first.
- [ ] Cameras clean, mounts tight, cable dress not rubbing; robot PC disk has room for the
      day's recordings ([[library/topics/fleet-operations]]).

## Common: mastering and calibration loss

Two things get called calibration. Mastering (KUKA), zero-position mastering (FANUC), home
position calibration (Yaskawa), revolution counter update (ABB) and CALSET (Denso) all
re-establish each joint's encoder zero; kinematic calibration is the per-unit link geometry the
factory measured, which on UR the driver must extract (UR section). Lost mastering shows as a
boot alarm naming a battery or encoder, taught points off by a joint offset, or a joint that will
only jog. Recovery needs a reference mark, tool or known pose per the vendor sections. Never
guess an offset; a wrong one shifts every safety zone.

## Common: payload identification

Collision detection compares measured torque or current against a model that includes the
payload; a wrong payload makes freedrive drift, trips protective stops on fast moves, or misses
real contacts. Enter mass, centre of gravity and, where accepted, inertia for every tool state
(empty gripper, heaviest part). Where the vendor ships an identification routine, run it after
every tool change and record the result. If the payload changes mid-task, set it per program
section; the policy client has to do the same through the vendor interface.

## Common: tool changers

Every swap changes TCP and payload. Keep both per tool in the controller's tool table and select
the entry on every change, from the program or the policy client; wire the changer's coupled and
released states to an input so a released tool cannot be moved; re-measure the TCP after mounting
a new tool plate, since a 1 mm TCP error is a 1 mm error at every waypoint.

## Common: cable management and dress packs

Joint 6 on most arms turns more than 360 degrees, and a cable wound around the wrist is the
commonest self-inflicted fault on a fresh cell. Route camera, gripper and air lines through a
dress pack or retractor, leave a service loop per joint, limit joint 6 in the safety
configuration to the range the cable survives, strain-relieve at the flange, and photograph the
routing for the field note.

## Common: first hour with a new arm

This is the pendant-side prelude to [[sops/robot-bring-up]]; that SOP takes over at its
section 1 once the arm moves under the pendant.

- [ ] Read the integrator's safety configuration with them; photograph every safety screen and
      the checksum. Record controller software, safety software, and pendant versions.
- [ ] Take a full backup to a labelled USB before touching anything (section per vendor).
- [ ] Boot, release brakes, note every message the boot produces.
- [ ] Set payload and TCP for the mounted tool; run the payload identification if offered.
- [ ] Jog each joint a few degrees at reduced speed, then freedrive or hand-guide the arm
      through the workspace; note where it drifts or resists.
- [ ] Teach two waypoints and run a native program between them at 10 percent, then 50.
- [ ] Trigger a protective stop on purpose (push the arm in a slow move) and clear it. Note
      the code and the recovery steps.
- [ ] Install or confirm the external-control component (URCap, FCI, EGM option, FRI app,
      RMI option), record its version, then export the log as the diagnostic baseline.
- [ ] Continue with [[sops/robot-bring-up]] section 1.

## Practical gotchas

- Kinova boots in under 30 s but holding the power button 10 s factory-resets it
  ([User Guide R07](https://www.kinovarobotics.com/uploads/User-Guide-Gen3-R07.pdf)).
- Any pendant popup on a UR ends external control until a human touches the pendant
  ([[library/hardware/robot-arms]]). Plan the cell so someone can reach it.
- The safety checksum (UR), signature number (FANUC DCS), locked configuration checksum (ABB
  SafeMove) change when anyone edits a limit. Photograph them at commissioning and compare on
  every visit.

## What a forward-deployed engineer must be able to do

- Boot, release brakes, clear a protective stop, and shut down any arm in this note without
  the manual open.
- Read the safety configuration and say which limit will stop the policy first.
- Enter payload and TCP and prove they are right with a freedrive test.
- Take and restore a full backup, and export the log for the vendor.
- Enable and disable external control from the pendant and confirm which side has authority.

## Open questions to learn hands-on

- Actual FRI and EGM behaviour when the policy PC drops packets, per firmware version.
- How long a full backup and restore takes per vendor, measured, for the fleet reflash plan.

## Related entries

- [[library/hardware/robot-arms]] (specs, control rates, ROS 2 drivers)
- [[library/topics/connecting-to-real-robots]] (vendor and driver table, day-one procedure)
- [[library/topics/safety-for-learned-policies]] (standards, shield, evidence)
- [[library/hardware/grippers-and-end-effectors]], [[library/topics/fleet-operations]]
- [[sops/robot-bring-up]], [[sops/incident-log-template]]

## Sources

- Universal Robots, PolyScope 5.26 and PolyScope X 10.14 user manuals (HTML). https://www.universal-robots.com/manuals/ ; UR ROS 2 driver docs. https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/ ; External Control URCapX. https://github.com/UniversalRobots/Universal_Robots_ExternalControl_URCapX
- Franka Robotics, Operating Manual FR3 System Image 5.8. https://franka.de/hubfs/Operating%20Manual%20Franka%20Research%203_System_Image_5.8_R02216_1.1.1_EN.pdf ; libfranka docs (getting started, compatibility matrix, Errors, Robot). https://frankarobotics.github.io/docs/ ; https://frankarobotics.github.io/libfranka/0.15.0/
- Kinova, Gen3 User Guide R07. https://www.kinovarobotics.com/uploads/User-Guide-Gen3-R07.pdf ; kortex examples. https://github.com/Kinovarobotics/kortex
- UFactory, xArm hardware and UFactory Studio manuals. https://docs.xarm.ufactory.cc/ ; https://docs.ufactory.cc/user_manual/ufactoryStudio/ ; xArm Python SDK API. https://github.com/xArm-Developer/xArm-Python-SDK
- KUKA, Sunrise Cabinet Med Instructions for Use V5 (2021), manualslib copy; LBR iisy 3 R760 Assembly Instructions V5; lbr-stack. https://github.com/lbr-stack/lbr_fri_ros2_stack ; kroshu kuka_drivers wiki. https://github.com/kroshu/kuka_drivers/tree/master/doc/wiki
- ABB library documents 3HAC065034-001, 3HAC077389-001, 3HAC077390-001, 3HAC066559-001, 3HAC073319-001, 3HAC073318-001, 3HAC065038-001, 3HAC066554-001, 3HAC032104-001, 3HAC046983-001. https://search.abb.com/library/ ; RWS API. https://developercenter.robotstudio.com/api/rwsApi ; abb_librws. https://github.com/ros-industrial/abb_librws
- FANUC manuals B-83284EN/09, B-83284EN-2, B-83184EN/11, B-80687EN/17, MARRUEROR02171E, MAROGRMIM11191E, MAROCM71009061E via https://github.com/zhaomengkang/FANUC-Robot-Manual ; fanuc_driver docs. https://fanuc-corporation.github.io/fanuc_driver_doc/ ; Tablet TP. https://www.fanucamerica.com/products/robots/tablet-teach-pendant
- Stäubli CS9, SRS, uniVAL and hygienic pages via the Wayback Machine (staubli.com 403); CS8C manual D28070504A; staubli_val3_driver. https://github.com/ros-industrial/staubli_val3_driver ; ICube staubli_driver_ros2. https://github.com/ICube-Robotics/staubli_driver_ros2
- Denso, pendants. https://www.densorobotics.com/products/teaching-pendants/ ; denso_robot_ros2. https://github.com/DENSORobot/denso_robot_ros2 ; DENSO WAVE b-CAP page and support article 60000698513
- Yaskawa, YRC1000 Instructions RE-CTO-A221 and Alarm Codes RE-CER-A600 (motoman.com PDFs 178642-1CD, 178644-1CD); MotoROS2. https://github.com/Yaskawa-Global/motoros2
