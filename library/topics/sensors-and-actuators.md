---
title: Sensors and actuators beyond cameras, and how to integrate them
date: 2026-09-06
tags: [topic, actuators, motors, encoders, imu, fieldbus, ethercat, plc, safety, conveyors, ros2_control]
status: draft
source: synthesis   # primary links inline and under Sources; unverified items tagged
---

# Sensors and actuators beyond cameras, and how to integrate them

Companion notes: `connecting-to-real-robots.md` (ros2_control, real-time
loop, vendor arm drivers), `perception-tactile-and-force.md` (F/T and
tactile sensors, force control), `perception-3d-sensing.md` (depth cameras,
LiDAR, time sync for cameras). This note covers what those leave out: the
motor and gearbox behind every joint, the encoders and IMUs that report
state, the plant sensors a food or logistics customer already owns, and the
signal chain that turns any of them into a policy observation.

## What it is

An actuator is a motor, a reduction, a drive that commutates the motor, and
the sensors that close the loop (position, current, sometimes torque and
temperature). A sensor is a transducer plus a signal chain (analog front
end, digitizer, fieldbus, driver, ROS 2 message) with a rate, a latency,
and a clock. A learning engineer needs to know both well enough to read a
datasheet, choose between two options, predict which failure modes will
appear in the data, and get the signal into a `ros2_control` interface or a
topic with a correct timestamp.

## Why it matters in the field

- Learned policies inherit actuator physics. A policy trained on a
  backlash-heavy leader-follower pair learns the hysteresis; a policy
  trained on a quasi-direct-drive arm learns to expect back-drivability.
  Neither transfers to the other hardware (from field, unverified).
- Customers in food and logistics already run PLCs, safety scanners, belt
  encoders, checkweighers, and X-ray. The robot cell has to read from and
  report to that equipment; a policy that cannot see the belt encoder
  cannot pick from a moving belt.
- The integration questions (which bus, which master, which clock, which
  side of the PLC/PC split) are decided in week one of an engagement and
  are expensive to change later.
- Actuator thermal limits, not model quality, cap the duty cycle of a
  deployed pick cell; a demo that runs for ten minutes tells you nothing
  about a shift.

## Actuators

### Motor and reduction families

| Family | Mechanism | Typical use | Learned-policy consequence | Source |
|---|---|---|---|---|
| BLDC / PMSM with FOC | Three-phase permanent-magnet motor; field-oriented control sets the q-axis current so torque is proportional to `I_q` | Every modern joint, gripper, and wheel | Torque command is a current command; torque estimate is `K_t * I_q` before friction and reduction losses | [SimpleFOC theory](https://docs.simplefoc.com/foc_theory) |
| Harmonic (strain wave) | Flexspline deformed by an elliptical wave generator meshes with a rigid circular spline; ratios 30:1 to 160:1 (range unverified); vendor claims zero backlash | Industrial arms (UR, Franka, KUKA), cobots | Compliant, low backlash, high friction; not back-drivable; joint torque from current is poor, hence built-in torque sensors on Franka and KUKA iiwa | [Harmonic Drive principle](https://www.harmonicdrive.net/technology) |
| Cycloidal | Eccentric cam drives a lobed disc against pins; high ratio in one stage, high shock load | Large industrial arms, some legged robots | Low backlash, some torque ripple at the cycloid frequency (unverified) | vendor docs (unverified) |
| Planetary | Sun, planets, ring; 3:1 to 10:1 per stage, stackable | Quasi-direct-drive legs and arms, servos, grippers | Backlash grows with stage count; single stage is back-drivable | [MIT Cheetah actuator, Wensing et al. 2017](https://doi.org/10.1109/TRO.2016.2640183) |
| Quasi-direct-drive (QDD) | Large-diameter outrunner with a single planetary stage under 10:1 | MIT Cheetah, Unitree, T-Motor AK, Piper-class arms | Back-drivable; torque from current is usable; impact-tolerant; lower continuous torque, heat is the limit | [Wensing et al. 2017](https://doi.org/10.1109/TRO.2016.2640183) |
| Series elastic (SEA) | Spring between reduction and load; torque from spring deflection | Legged robots, exoskeletons, Baxter | Accurate torque sensing, lower bandwidth; policies see a soft joint | [Pratt and Williamson 1995](https://doi.org/10.1109/IROS.1995.525827) |
| Hydraulic | Pump, valves, cylinders; very high force density | Atlas (hydraulic generation), heavy machinery | Nonlinear, valve deadband, heat; rare in current learning work | (unverified) |
| Pneumatic | Compressed air cylinders and soft actuators | Grippers, soft robots, food handling (washdown-friendly) | Compressible: position control is poor, force control is coarse; state is often binary (open/closed) | (unverified) |
| Linear: ball screw, belt, rack | Rotary to linear; ball screws are stiff and precise, belts are fast and cheap | Gantries, lifts, linear pickers | Ball screw backlash is small but present; belt stretch shows as position error under load (from field, unverified) | vendor docs (unverified) |

### Servo drives, fieldbus, and motor controllers

The drive runs the current loop (tens of kHz) and usually the velocity and
position loops; the host sends setpoints at the fieldbus cycle. Which layer
the policy commands is a design decision (see the walkthrough).

| Controller | Bus | Modes | Notes | Source |
|---|---|---|---|---|
| Industrial CiA 402 drives (Elmo Gold, Copley Accelnet, Beckhoff, Kollmorgen) | EtherCAT CoE, CANopen | CSP (8), CSV (9), CST (10), homing (6), profile position (1) | The CiA 402 state machine (switch on, enable operation, fault reset) and object dictionary (0x6040 controlword, 0x6041 statusword, 0x6060 mode) are shared across vendors | [ICube CiA402 config](https://icube-robotics.github.io/ethercat_driver_ros2/user_guide/config_cia402_drive.html), [CiA 402 profile](https://www.can-cia.org/can-knowledge/cia-402-series-canopen-device-profile-for-drives-and-motion-control) |
| moteus (mjbots) | CAN-FD | position, velocity, torque; position mode with feedforward torque and per-command kp/kd scaling | Register protocol documented; Python and C++ libs; common on QDD legs and low-cost arms | [moteus reference](https://github.com/mjbots/moteus/blob/main/docs/reference.md) |
| ODrive Pro / S1 | CAN (CANSimple), UART, USB | position, velocity, torque; trapezoidal trajectories | Motor thermistor input and thermal limits configurable in firmware (docs, unverified for exact parameter names) | [ODrive docs](https://docs.odriverobotics.com/) |
| T-Motor AK series | CAN, "MIT mode" packet (position, velocity, kp, kd, torque feedforward) | impedance-style command per packet | Integrated QDD actuator; MIT mode packet format from the Cheetah controller (unverified) | [T-Motor](https://store.tmotor.com/) (unverified) |
| SimpleFOC | Any MCU, no bus standard | FOC library; voltage, current, velocity, angle modes | Education and prototypes; not a fieldbus drive | [SimpleFOC](https://docs.simplefoc.com/) |
| ROBOTIS Dynamixel (X, P series) | RS-485 or TTL, Protocol 2.0 | position, velocity, current, current-based position, PWM | Half-duplex bus shared by all servos; 4 Mbit/s max on X-series (unverified); `dynamixel_hardware_interface` for `ros2_control` | [Protocol 2.0](https://emanual.robotis.com/docs/en/dxl/protocol2/) |
| Feetech STS/SCS | TTL half-duplex, Dynamixel-like register protocol | position, velocity | The SO-101 and LeRobot arms use STS3215; LeRobot's driver is the working reference | [LeRobot feetech.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/feetech/feetech.py) |

### Torque sensing versus current-based torque estimation

Joint torque from motor current is `tau = K_t * I_q * N * eta` with `N`
the ratio and `eta` the efficiency; it ignores static friction, which on a
harmonic drive can exceed the payload torque at low speed. QDD actuators
(low `N`, low friction) make this estimate usable for contact detection and
teleop force feedback; harmonic-drive arms do not, which is why Franka and
KUKA iiwa put torque sensors in each joint (vendor pages via
`hardware/robot-arms.md`; sensing principle unverified). A dedicated F/T sensor at the wrist is the
alternative; see `perception-tactile-and-force.md`. For a policy, log both
the commanded current and the measured joint torque where available; the
difference is the friction the model has to learn (from field, unverified).

### Thermal limits and duty cycle

Continuous torque is set by winding temperature, not by the peak current
the drive can supply. Drives implement an `I^2 t` limit and read a motor
thermistor when wired; without the thermistor the drive protects itself,
not the motor (ODrive and moteus both expose motor temperature limits;
exact parameter names unverified). Practice: run the intended cycle for 30
minutes before quoting a cycle time, log winding or housing temperature,
and derate at ambient above the datasheet condition. Dynamixel and Feetech
servos shut down on overtemperature and drop torque without warning on the
bus; a policy sees a joint that stops following (from field, unverified).

### Backlash and how it shows up in learned policies

Backlash is dead travel on direction reversal; a servo's output encoder
sees it, a motor-side encoder does not. On a leader-follower pair with
motor-side encoders, the recorded "action" is the leader position and the
recorded "state" is the follower motor position, so the dataset contains a
direction-dependent offset the policy learns as if it were task structure.
Symptoms: small oscillation at reversals, failures on fine insertions, and
a policy that performs differently after a gearbox swap. Mitigations: an
output-side absolute encoder as the state source, a backlash term in the
observation, or a dataset from the hardware that will deploy (from field,
unverified).

## Sensors

### Encoders

| Type | Signal | Where | Notes | Source |
|---|---|---|---|---|
| Incremental optical or magnetic | A/B quadrature plus index Z; counts per revolution | Motor shafts, conveyors | Needs homing on power-up; count loss under EMI is silent | (unverified) |
| Absolute single-turn magnetic (AS5047P, MA732) | SPI or ABI; 14-bit typical | Hobby and research actuators, moteus and ODrive boards | Sensitive to magnet placement and axial gap; nonlinearity calibrated in firmware | AS5047P datasheet (ams OSRAM position sensors moved to Infineon in 2025; current URL unverified) |
| Absolute optical (Renishaw RESOLUTE, Heidenhain) | BiSS-C, BiSS Safety, vendor serial protocols (RESOLUTE); EnDat and SSI on others | Industrial joints, output side | Sub-arc-second on large rings; the reference for backlash-free state | [Renishaw RESOLUTE](https://www.renishaw.com/en/resolute-encoder-series--37823) |
| Multi-turn absolute | Battery-backed counter or Wiegand wire, gear train | Industrial servo motors | Survives power loss; battery replacement is a maintenance item | (unverified) |
| Conveyor encoder | Incremental, wheel-on-belt or on the drive shaft | Belt tracking for pick-on-the-fly | Belt slip against the drive roller makes a shaft encoder read wrong; a friction wheel on the belt is preferred (from field, unverified) | |

### IMUs

MEMS IMUs (Bosch BMI088, TDK ICM-42688, Xsens MTi) cost dollars to
thousands and drift by degrees per hour; fibre-optic gyros (KVH, Honeywell)
cost thousands and drift by fractions of a degree per hour (vendor
datasheets, figures unverified). Kalibr's noise model uses four parameters
per axis: gyro and accelerometer white-noise density and random walk, in
`rad/s/sqrt(Hz)`, `m/s^2/sqrt(Hz)`, `rad/s^2/sqrt(Hz)`, `m/s^3/sqrt(Hz)`;
datasheets list the white noise as angular or velocity random walk and
rarely list the bias random walk, which is estimated from an Allan
deviation plot ([kalibr IMU noise model](https://github.com/ethz-asl/kalibr/wiki/IMU-Noise-Model),
[allan_variance_ros](https://github.com/ori-drs/allan_variance_ros)).
Camera-IMU extrinsics and time offset come from Kalibr with an AprilGrid
([kalibr](https://github.com/ethz-asl/kalibr)). On a manipulator an IMU on
the tool is mostly a vibration and impact sensor; on a mobile base it is the
odometry backbone (see `state-estimation-and-localization.md`).

### Force/torque and tactile

See `perception-tactile-and-force.md`.

### Proximity and safety

| Device | Function | Standards and figures | Source |
|---|---|---|---|
| Safety laser scanner (SICK microScan3, nanoScan3; Keyence SZ; Omron OS32C) | Programmable protective and warning fields around a cell or on an AMR | Type 3 per IEC 61496-3, PL d / SIL 2; protective field range up to 9 m on microScan3 (unverified) | [SICK safety laser scanners](https://www.sick.com/us/en/catalog/products/safety/safety-laser-scanners/c/g187132) (link unverified) |
| Light curtain (SICK deTec4, Keyence GL-R) | Detect entry across a plane; muting for product passage | Type 4, PL e; resolution 14 mm finger, 30 mm hand | vendor docs (unverified) |
| Safety mat | Pressure-sensitive floor area | PL d typical; simple, cheap, washdown variants exist | (unverified) |
| Inductive, capacitive, photoelectric proximity | Part-present, gripper-closed, door-closed | IO-Link or discrete 24 V PNP | [IO-Link](https://io-link.com/) |

Safety distance for a scanner or curtain follows ISO 13855: `S = K * T + C`
with `K` the approach speed (1600 mm/s for walking toward a scanner field),
`T` the total stopping time of the system (detection plus robot stop), and
`C` a penetration allowance; the robot's stop time therefore sets the field
size (standard text, figures unverified). Safety functions run on the
safety PLC or the scanner's own outputs, never on the ROS 2 PC; see
`safety-for-learned-policies.md`.

### Industrial vision beyond RGB

| Modality | Measures | Plant use | Representative devices | Source |
|---|---|---|---|---|
| Line laser profiler | Height profile along a line; 3D by belt motion plus encoder | Portion cutting, volume, fill level, presence of bone bumps | Keyence LJ-X, SICK Ranger3, Cognex, Micro-Epsilon | vendor docs (unverified) |
| X-ray (single energy) | Density; foreign body and bone detection | Bone fragments in poultry and fish fillets, metal, glass | Marel SensorX, Eagle, Mettler Toledo Safeline | JBT Marel SensorX ([jbtmarel.com](https://jbtmarel.com/), product URL unverified) |
| DEXA (dual-energy X-ray) | Material composition from two energies | Chemical lean (fat/lean ratio) in bulk meat, bone in trims | Eagle FA3/M: "measures fat precisely to +/-1 CL using DEXA" | [Eagle](https://www.eaglepi.com/) |
| Hyperspectral (VNIR 400 to 1000 nm, SWIR 900 to 1700 nm) | Reflectance spectrum per pixel | Fat vs lean, bruising, plastic contaminants, moisture | Specim FX10 (VNIR 400 to 1000 nm), FX17 (SWIR, range unverified) | [Specim FX10](https://www.specim.com/products/specim-fx10/) |
| Time of flight | Depth per pixel | Bin fill level, pallet dimensioning | Orbbec Femto, Basler blaze | see `perception-3d-sensing.md` |
| Thermal (LWIR) | Surface temperature | Cook-line verification, hot product detection, human presence | FLIR A-series, Optris | vendor docs (unverified) |

The learning-relevant point: X-ray and DEXA machines output a decision and
often an image at the belt rate with a known offset from the camera
position; they are upstream sensors that can be aligned to the robot's belt
encoder and used as labels (bone present or absent) without any annotation
(from field, unverified).

### Load cells and weighing on conveyors

Strain-gauge load cells feed a checkweigher that weighs each item in
motion; the item must settle on the weigh belt for a minimum time, which
sets belt speed and item spacing (OIML R 51 covers automatic catchweighers,
[OIML](https://www.oiml.org/) (link unverified)). Robot cells use the
checkweigher as a downstream verifier (was the pick complete) and, for
portioning, the upstream weight as an observation. A load cell under a
tote gives pick verification in under 100 ms if the tote is mechanically
isolated from the robot's vibration (from field, unverified).

## Integration

### Signal chains

| Chain | Rate and latency | ROS 2 path | Notes |
|---|---|---|---|
| Analog 4 to 20 mA or 0 to 10 V | kHz possible; latency set by the ADC | Beckhoff EL3xxx terminal on EtherCAT via `ethercat_driver_ros2` gpio/analog interfaces | Current loop is EMI tolerant over long cable; voltage is not |
| IO-Link (IEC 61131-9) | 2.3 ms minimum cycle at COM3 (spec, unverified) | IO-Link master on EtherCAT or PROFINET, then PLC or EtherCAT terminal | Point-to-point 3-wire; sensor parameters readable over the link | [IO-Link](https://io-link.com/) |
| Fieldbus to drives | 1 to 4 kHz EtherCAT, 100 Hz to 1 kHz CAN | `ethercat_driver_ros2`, `ros2_canopen` | See `connecting-to-real-robots.md` |
| PLC to PC: OPC UA (IEC 62541) | 10 to 100 ms typical | `open62541` or `opcua-asyncio` in a ROS 2 node | Standard on Siemens, Beckhoff, B&R; the customer's IT knows it | [open62541](https://github.com/open62541/open62541), [opcua-asyncio](https://github.com/FreeOpcUa/opcua-asyncio) |
| PLC to PC: Modbus TCP | 10 to 50 ms polling | `pymodbus` in a ROS 2 node | Register map by agreement; no types, no timestamps | [pymodbus](https://github.com/pymodbus-dev/pymodbus) |
| PLC to PC: vendor (Beckhoff ADS, Siemens S7) | 1 to 10 ms | `pyads`, `python-snap7` | Faster than OPC UA; vendor-locked | [pyads](https://github.com/stlehmann/pyads), [python-snap7](https://github.com/gijzelaerr/python-snap7) |
| Serial servo bus | 50 to 500 Hz | `dynamixel_hardware_interface`, LeRobot motor buses | Shared half-duplex bus; FTDI latency timer to 1 ms | see `connecting-to-real-robots.md` |

### PLC versus PC control split

The PLC owns safety, interlocks, conveyor motion, pneumatics, and anything
that must run when the PC reboots. The PC owns perception, the policy, and
motion planning. The interface is a small set of handshake variables
(cell ready, pick requested, pick done, fault) plus the belt encoder value
and timestamp. Learned policies should never be the only thing between a
safety scanner and the robot; the PLC or safety controller cuts power on
its own (from field, unverified; see `safety-for-learned-policies.md`).

### Time sync

IEEE 1588 PTP on Linux is `linuxptp`: `ptp4l` syncs the NIC hardware clock,
`phc2sys` syncs the system clock to it ([linuxptp](https://linuxptp.sourceforge.net/)).
Ouster LiDARs and many GigE cameras take PTP directly; EtherCAT has its own
distributed clock. Fallback is `chrony` to one master. Every message needs
`header.stamp` from the sensor's clock where it exists (camera exposure
time, LiDAR packet time) and the receive time otherwise; log which.

### EtherCAT masters on Linux

IgH EtherCAT Master ([etherlab](https://gitlab.com/etherlab.org/ethercat),
kernel module, GPL) is what `ethercat_driver_ros2` uses; SOEM
([repo](https://github.com/OpenEtherCATsociety/SOEM)) is userspace; Acontis
EC-Master is the commercial option with vendor support. All need a
dedicated NIC and a PREEMPT_RT kernel for cycle times under 1 ms (see
`connecting-to-real-robots.md`).

### ros2_control hardware interfaces for these

A sensor without an actuator is a `<sensor>` in the `<ros2_control>` URDF
tag exposing state interfaces; a gripper or conveyor is a `<joint>`; digital
IO is a `<gpio>` with command and state interfaces
([hardware components](https://control.ros.org/humble/doc/ros2_control/hardware_interface/doc/hardware_components_userdoc.html)).
A PLC bridge that reads Modbus registers can be written as a `SystemInterface`
so the belt encoder appears as a state interface alongside the joints and is
sampled in the same `read()` call; that is the cleanest way to get one
timestamp for joints and belt (from field, unverified).

### Power, grounding, EMI, and cabling

- Separate 24 V for logic and IO from motor power; single-point (star)
  ground; shields terminated at one end for low-frequency, both ends with
  360-degree clamps for VFD noise (installation practice, unverified).
- Variable-frequency drives on conveyors are the main EMI source; keep
  encoder and camera cables out of the motor cable tray, and use
  differential (RS-422) encoder outputs over single-ended for anything past
  a few metres (from field, unverified).
- Washdown: IP69K per ISO 20653 for high-pressure hot water; M12 connectors
  with stainless couplings; cable jackets rated for the sanitizer in use;
  EHEDG guidelines for hygienic design ([EHEDG](https://www.ehedg.org/))
  (link unverified). Consumer USB cameras and cables do not survive a
  washdown shift (from field, unverified).
- Ground loops between a PC on one outlet and a PLC on another show up as
  analog offsets and USB resets; isolate at the sensor or the NIC.

### Selection table by function

| Function | First choice | Alternative | Why |
|---|---|---|---|
| Joint position (state for the policy) | Output-side absolute encoder | Motor-side encoder plus backlash model | Backlash-free state |
| Joint torque (contact, force feedback) | Joint torque sensor or wrist F/T | `K_t * I_q` on a QDD joint | Friction on high-ratio drives |
| Belt tracking | Friction-wheel incremental encoder on the belt | Drive-shaft encoder | Belt slip |
| Pick verification | Gripper current or position window | Load cell, checkweigher, camera | Zero extra hardware |
| Human presence | Safety laser scanner on the safety PLC | Light curtain, mat | Programmable fields, certified |
| Bone or foreign body | X-ray or DEXA | Hyperspectral, RGB | Density is what matters |
| Fat/lean | DEXA on bulk, hyperspectral or RGB on surfaces | | Depth of measurement |
| Base motion | Wheel odometry plus MEMS IMU plus LiDAR | FOG for GNSS-denied long runs | Cost |
| Fast IO (strobe, trigger, valve) | EtherCAT terminal or camera GPIO | PLC output via OPC UA | Latency |

## Practical recipe: how a sensor becomes a policy observation

Belt encoder on a pick cell, end to end.

1. **Rate.** The encoder gives 1000 pulses per metre through a Beckhoff
   EL5101 counter terminal on EtherCAT at 1 kHz; the camera runs at 30 Hz;
   the policy at 10 Hz. Sample the encoder in the same `read()` as the arm
   joints so both carry one stamp.
2. **Latency.** Measure, do not assume: toggle a strobe from the same
   terminal, capture it in the camera, and compare the image stamp with the
   terminal stamp over 100 frames; record the median and the spread. UMI's
   method for camera and proprio latency applies unchanged
   ([Chi et al. 2024](https://arxiv.org/abs/2402.10329)).
3. **Sync.** Camera stamps come from PTP or from the trigger time; encoder
   stamps from EtherCAT DC. Interpolate the encoder to the image stamp
   (linear is fine at 1 kHz) so each frame gets one belt position.
4. **Normalization.** Convert counts to metres, express the belt position
   relative to the frame's capture instant (so the observation is "belt
   travel since capture", which is zero at capture and grows during
   inference), and scale to the dataset's statistics like any other
   proprio channel. Store the raw count as well.
5. **Action side.** The pick pose the policy outputs is in the belt frame
   at capture time; the controller advances it by the encoder delta at
   execution. Verify on a stopped belt (delta 0) before a moving one.
6. **Dataset check.** LeRobotDataset enforces consecutive timestamps within
   `tolerance_s` ([lerobot source](https://github.com/huggingface/lerobot/blob/main/src/lerobot/datasets/lerobot_dataset.py));
   add a per-episode plot of belt position vs time and reject episodes with
   count jumps.

The same six steps apply to an IMU (rate 200 Hz, bias-corrected, expressed
in the tool frame), a load cell (rate 100 Hz, tared per tote), or a PLC
state word (rate 10 Hz, one-hot).

## Practical gotchas

- A Dynamixel or Feetech bus with one bad cable drops packets for every
  servo after it; the symptom is intermittent position reads, not an error
  (from field, unverified).
- Absolute magnetic encoders read plausibly wrong values when the magnet
  is off-axis; check linearity over a full turn against the motor's
  electrical angle before trusting the state.
- Current-based torque on a harmonic-drive joint reads near zero at rest
  under load because static friction holds it; contact detection from
  current fails there.
- A checkweigher's weight arrives one belt segment after the item was
  imaged; without the encoder offset it is attributed to the wrong item.
- OPC UA subscription rates are set on the server; the default is often
  100 ms or slower and the PLC integrator must change it.
- Two EtherCAT masters on one segment (PLC and PC) is not possible; one
  master owns the bus and the other reads over PLC-to-PC bridge.
- Modbus registers are 16-bit; a 32-bit encoder count spans two registers
  and can tear between reads unless the PLC latches it.
- Servo overtemperature shutdown looks like a policy failure in the log:
  correlate any "joint stopped following" with drive temperature.

## What a forward-deployed engineer must be able to do

1. Read a motor and gearbox datasheet and predict back-drivability, torque
   estimate quality, and continuous duty at the planned cycle.
2. Bring up a CiA 402 drive on EtherCAT with `ethercat_driver_ros2` (CSP
   and CST modes), and a Dynamixel or Feetech bus with `ros2_control`.
3. Calibrate an IMU (Allan deviation) and a camera-IMU pair (Kalibr), and
   state the resulting noise parameters and time offset.
4. Wire a belt encoder, an IO-Link sensor, and a PLC handshake into one
   hardware interface with one timestamp, and prove the sync with a strobe
   test.
5. Configure PTP on the PC and confirm camera, LiDAR, and EtherCAT clocks
   agree within a control period.
6. Specify a safety scanner field from ISO 13855 with the safety engineer
   and explain why the PLC, not the policy, executes the stop.
7. Choose plant sensors (X-ray, DEXA, hyperspectral, checkweigher) as label
   sources or observations and align them to the belt encoder.
8. Diagnose backlash, thermal derating, and EMI from a dataset plot before
   blaming the model.

## Open questions

- How much does an output-side encoder improve fine-insertion success for
  an ACT policy on a SO-101-class arm, at equal demo count?
- Whether adding measured joint torque (or `K_t * I_q` on QDD) as an
  observation helps or hurts under the proprio-shortcut problem.
- Real end-to-end latency of the OPC UA path from a Siemens PLC to a ROS 2
  node under load, and whether ADS or S7 direct is needed for belt tracking.
- Whether X-ray bone decisions are consistent enough to serve as
  segmentation labels for an RGB model.
- A repeatable strobe-based latency test rig that fits in a field kit.

## Related entries

- `library/topics/connecting-to-real-robots.md` (ros2_control, fieldbus table, real-time)
- `library/topics/perception-tactile-and-force.md` (F/T and tactile)
- `library/topics/perception-3d-sensing.md` (depth cameras, LiDAR, camera sync)
- `library/topics/computer-vision-fundamentals.md` (line-scan, encoder-triggered acquisition)
- `library/topics/state-estimation-and-localization.md` (IMU in odometry)
- `library/topics/safety-for-learned-policies.md`
- `library/hardware/robot-arms.md`, `library/hardware/grippers-and-end-effectors.md`

## Sources

- Actuators: [SimpleFOC theory](https://docs.simplefoc.com/foc_theory), [MIT Cheetah actuator (Wensing et al. 2017)](https://doi.org/10.1109/TRO.2016.2640183), [Pratt and Williamson 1995](https://doi.org/10.1109/IROS.1995.525827), [Harmonic Drive](https://www.harmonicdrive.net/technology)
- Controllers and buses: [moteus reference](https://github.com/mjbots/moteus/blob/main/docs/reference.md), [ODrive docs](https://docs.odriverobotics.com/), [SimpleFOC](https://docs.simplefoc.com/), [Dynamixel Protocol 2.0](https://emanual.robotis.com/docs/en/dxl/protocol2/), [LeRobot feetech.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/feetech/feetech.py), [ICube CiA402 config](https://icube-robotics.github.io/ethercat_driver_ros2/user_guide/config_cia402_drive.html), [IgH EtherCAT](https://gitlab.com/etherlab.org/ethercat), [SOEM](https://github.com/OpenEtherCATsociety/SOEM)
- Sensors: [kalibr IMU noise model](https://github.com/ethz-asl/kalibr/wiki/IMU-Noise-Model), [kalibr](https://github.com/ethz-asl/kalibr), [allan_variance_ros](https://github.com/ori-drs/allan_variance_ros), [IO-Link](https://io-link.com/), [EHEDG](https://www.ehedg.org/)
- PLC bridges and time: [open62541](https://github.com/open62541/open62541), [opcua-asyncio](https://github.com/FreeOpcUa/opcua-asyncio), [pymodbus](https://github.com/pymodbus-dev/pymodbus), [pyads](https://github.com/stlehmann/pyads), [python-snap7](https://github.com/gijzelaerr/python-snap7), [linuxptp](https://linuxptp.sourceforge.net/)
- ros2_control: [hardware components](https://control.ros.org/humble/doc/ros2_control/hardware_interface/doc/hardware_components_userdoc.html)
- Observation pipeline: [UMI (Chi et al. 2024)](https://arxiv.org/abs/2402.10329), [LeRobotDataset](https://github.com/huggingface/lerobot/blob/main/src/lerobot/datasets/lerobot_dataset.py)
