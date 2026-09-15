---
title: Depth cameras (RealSense, ZED, Orbbec, Luxonis OAK)
date: 2026-09-05
tags: [hardware, depth-camera, rgb-d, ros2]
status: draft
source: vendor documentation (links inline)
---

# depth cameras

One section per camera family. Specs are quoted from vendor pages fetched on
2026-09-05; anything not verifiable is marked "(unverified)" or omitted.
Concepts, failure modes, and the calibration procedure live in
`library/topics/perception-3d-sensing.md`. Fill in "who to contact" and
firmware fields as units arrive in the field.

## Quick chooser

| Need | Pick | Why |
|---|---|---|
| Tabletop grasping, 10-50 cm from wrist | RealSense D405 | 18 mm baseline, ideal 7-50 cm |
| General manipulation, 0.3-3 m, cheap, huge community | RealSense D435i / D455 | Global-shutter depth, IMU, mature ROS 2 driver |
| Outdoor / long range / textureless, GPU available | ZED 2i (USB) or ZED X (GMSL2, Jetson) | Passive stereo + neural depth, 120 mm baseline |
| Azure Kinect replacement, body tracking, wide FOV ToF | Orbbec Femto Bolt | Same ToF module lineage as Azure Kinect DK |
| Active stereo with hardware sync and IP65 | Orbbec Gemini 335L | 95 mm baseline, global shutter, sync connectors |
| Edge inference on the camera, no host GPU | Luxonis OAK-D Pro (W/PoE) | RVC2 runs NNs on-device, 940 nm projector |

## RealSense D4xx (active IR stereo)

**Vendor status.** RealSense left Intel and completed its spin-out as an
independent company on 2025-07-11 with $50M Series A (Intel Capital, MediaTek
Innovation Fund) ([press release](https://www.realsenseai.com/news-insights/news/realsense-completes-spin-out-from-intel-raises-50-million-to-accelerate-ai-powered-vision-for-robotics-and-biometrics/)).
Docs moved from `intelrealsense.com` to `realsenseai.com` /
`dev.realsenseai.com`; old links may time out. Newer parts: D421 entry-level
module (2024-09) and D555 PoE camera on the in-house "Vision SoC V5" with 5 TOPS
on-board ([Robot Report](https://www.therobotreport.com/after-intel-exit-realsense-maps-its-own-future-in-3d-vision/)).

**Principle.** Two IR imagers + IR texture projector; depth computed on the
camera ASIC. Works without the projector on textured scenes, which is why it
survives outdoors better than structured light.
"f" variants add a 750 nm IR pass filter to boost projector contrast and
suppress visible reflections ([RealSense IR filter](https://www.intelrealsense.com/stereo-depth-with-ir/)).

| Model | Depth FOV | Ideal range | Baseline | Depth res/fps | RGB | IMU | Notes |
|---|---|---|---|---|---|---|---|
| [D435i](https://www.realsenseai.com/products/depth-camera-d435i/) | 87 x 58 deg | 0.3-3 m; MinZ ~28 cm | (unverified) | up to 1280x720 @ 90 | 1920x1080 @ 30, rolling shutter | yes | Depth global shutter; USB-C 3.1 Gen1 |
| [D455](https://www.automate.org/products/realsense/realsense-d455-depth-camera) | 87 x 58 deg | 0.6-6 m | 95 mm | (unverified) | global shutter | yes | Twice D435 range; RGB and depth both global shutter |
| [D405](https://www.therobotreport.com/intel-adds-short-range-realsense-d405-depth-camera/) | 87 x 58 deg | 7-50 cm; +/-1.4% at 20 cm | 18 mm | up to 1280x800 | from depth imagers via ISP | no | 42x42x23 mm, 60 g; wrist camera |
| [D415](https://www.realsenseai.com/products/stereo-depth-camera-d415/) | 65 x 40 deg | 0.5-3 m | 55 mm | rolling shutter depth ([product brief](https://www.mouser.com/pdfdocs/Intel_D415_ProductBrief.pdf)) | rolling | no | Narrow FOV, denser depth per degree; avoid with fast motion |

Intel's spec page lists a 0.105 m minimum depth for D435i
([Intel spec](https://www.intel.com/content/www/us/en/products/sku/190004/intel-realsense-depth-camera-d435i/specifications.html))
versus ~28 cm on the RealSense page; MinZ depends on resolution and disparity
shift, so verify on your profile.

**SDK / ROS.**
- librealsense: https://github.com/IntelRealSense/librealsense (viewer
  `realsense-viewer` is the fastest way to inspect depth quality live).
- ROS 2 wrapper: https://github.com/IntelRealSense/realsense-ros. Supports
  Rolling, Kilted, Jazzy, Iron, Humble, Foxy. Key params: `align_depth.enable`
  (publishes `/camera/camera/aligned_depth_to_color/image_raw`),
  `pointcloud.enable`, `enable_sync`, `unite_imu_method` (0 none, 1 copy,
  2 linear interpolation), `depth_module.depth_profile` as `WxHxFPS`.
  Topics: `/camera/camera/depth/image_rect_raw`, `/camera/camera/color/image_raw`,
  `/camera/camera/depth/color/points`. TF: `camera_link` at the left IR
  sensor plus `*_optical_frame` for each stream.

**Multi-camera and sync** ([dev.realsenseai.com](https://dev.realsenseai.com/docs/multiple-depth-cameras-configuration/)).
- D4xx overlapping FOV "do not suffer from any significant cross-talk".
- HW sync: `inter_cam_sync_mode` 0 default, 1 master, 2 slave; wire pin 5
  (SYNC) and pin 9 (GND) between units (JST ASSHSSH28K152 connectors).
  External trigger wants a 100 us positive pulse at the frame rate
  ([D457 sync note](https://realsenseai.com/wp-content/uploads/2025/08/RealSense-D457-Hardware-Synchronization-V0.11.pdf)).
- Validation quirk: "If you see NO DRIFT, then there is NO HW sync."
- USB: stay "well below" 1200 MB/s aggregate; four D415 at 1280x720 exceed
  it, 640x360 works; cables preferably under 1 m.

**Known quirks (field-relevant).**
- Depth encoding is `16UC1` in millimetres; holes are `0`.
- RGB on D435/D435i is rolling shutter: motion blur during fast arm moves.
- Firmware and librealsense versions are coupled; pin both in the deployment
  image and record them in the hardware log.
- Auto-exposure on the depth imagers can flicker under LED lighting; fix
  exposure once the cell lighting is set (from field, unverified).

## RealSense L515 (MEMS LiDAR camera) - end of life

- Intel issued the EOL notice 2021-08-31; last order 2022-02-28, last ship
  2022-03-31; recommended replacements D455 / D435i
  ([Robot Report](https://www.therobotreport.com/intel-issues-end-of-life-notice-realsense-lidar/)).
- Specs for legacy units: indoor only, 0.25-9 m, 70 x 55 deg FOV, 1024x768
  depth at 30 fps, 860 nm laser on a MEMS mirror, 1080p RGB
  ([Intel spec](https://www.intel.com/content/www/us/en/products/sku/201775/intel-realsense-lidar-camera-l515/specifications.html),
  [TechInsights](https://www.techinsights.com/blog/inside-intel-realsense-l515-lidar-camera)).
- Multiple L515s interfere with each other; Intel published a separate
  multi-camera note ([L515 multi-camera](https://www.realsenseai.com/wp-content/uploads/2020/08/L515_Multiple_Camera_WhitePaper_rev1.1.pdf)).
- Do not build new systems on it. Still supported in librealsense (unverified
  for the newest releases).

## Stereolabs ZED 2i (USB passive stereo + neural depth)

- Baseline 120 mm; depth range quoted 0.2-20 m
  ([Stereolabs FAQ](https://support.stereolabs.com/hc/en-us/articles/1500008533841-For-the-depth-sensing-what-is-the-range-for-the-ZED-cameras-in-terms-of-measuring-distances-and-the-accuracy-of-the-detection)).
- IP66 aluminium enclosure, rolling shutter, up to 120 deg diagonal FOV, IMU,
  USB 3.1, "Neural Depth Engine 2"
  ([ZED 2i store page](https://www.stereolabs.com/store/products/zed-2i)).
  Lens options (2.1 mm / 4 mm) and a polarizer variant exist on the store
  page (exact FOV numbers unverified).
- Video modes and fps per mode: (unverified; the docs page returned 404 at
  time of writing).
- Independent accuracy study of the ZED 2i indoors:
  [Robotics and Autonomous Systems, 2024](https://www.sciencedirect.com/science/article/pii/S0921889024001374).

**SDK / ROS.**
- ZED SDK requires an NVIDIA GPU with CUDA. Depth modes in SDK 5.x:
  `NEURAL_LIGHT` ("fastest ... best for multi-camera setup", smallest ideal
  range), `NEURAL` (balanced), `NEURAL_PLUS` ("highest object details",
  slowest, "may not be suited for multi-camera")
  ([depth modes](https://docs.stereolabs.com/docs/depth-sensing/depth-modes.md)).
  Classical modes are not listed on that page (unverified whether removed).
- ROS 2 wrapper: https://github.com/stereolabs/zed-ros2-wrapper. Humble, Jazzy,
  Rolling (Foxy legacy); needs ZED SDK v5.2; publishes rectified/unrectified
  images, depth, coloured cloud, pose/odom (optional GNSS fusion), IMU,
  objects, skeletons; starts a `robot_state_publisher` with the camera URDF.
  Multi-camera launch tutorial uses intra-process communication.
- Depth published as `32FC1` metres (unverified for the current wrapper).

**Quirks.** Neural depth fills holes plausibly, including on glass, which
looks good and can be wrong; check confidence maps before trusting edges
(from field, unverified). First launch downloads/optimizes AI models; budget
minutes on Jetson ([Stereolabs help](https://support.stereolabs.com/hc/en-us/articles/9747407795223-How-can-I-optimize-the-ZED-SDK-AI-models-manually)).
Known on this team's ROBOTIS AI Worker (see `hardware/README.md`).

## Stereolabs ZED X family (GMSL2 global shutter)

- ZED X: dual 1920x1200 global-shutter colour sensors, 120 mm baseline, IP67,
  IMU; lens options 2 mm (wide) or 4 mm; depth 0.3-20 m (wide) / 1-35 m
  (4 mm); GMSL2 up to 15 m cable, low latency, EMI-robust
  ([Mouser summary](https://www.mouser.com/en/new/stereolabs/stereolabs-zed-x-stereo-camera/),
  [datasheet PDF](https://static.generation-robots.com/media/zed-x-datasheet-v1.2.pdf)).
- "The ZED X, ZED X Mini, and ZED X Nano cameras use a GMSL2 connection,
  which is not compatible with USB." ZED X Nano has no IP rating (indoor)
  ([ZED X docs](https://docs.stereolabs.com/docs/products/cameras/zedx)).
- Needs an NVIDIA Jetson (Orin) plus a ZED Link capture card or ZED Box; the
  ZED Link Quad takes up to 4 GMSL2 inputs
  ([ZED Link](https://docs.stereolabs.com/docs/products/embedded/zed-link-capture-card)).
- Hardware sync across cameras "at frame-level within 100 microseconds" over
  GMSL2 ([ZED X One stereo](https://docs.stereolabs.com/docs/products/cameras/zedxone/dual-camera-stereo-vision)).
- Same SDK/ROS 2 wrapper as ZED 2i. Quirk: the GMSL2 driver is a kernel
  module tied to the JetPack version; upgrading JetPack breaks the camera
  until Stereolabs ships a matching driver (from field, unverified).

## Orbbec Gemini (active IR stereo)

| Model | Depth | Range | FOV (depth) | Baseline | RGB | Other |
|---|---|---|---|---|---|---|
| [Gemini 2](https://www.orbbec.com/products/stereo-vision-camera/gemini-2/) | active stereo IR, up to 1280x800 @ 30 | 0.15-10 m, <=2% at 2 m | H91 x V66 deg | (unverified) | up to 1920x1080 @ 30, H86 x V55 | IMU; USB 3.0 Type-C |
| [Gemini 335L](https://www.orbbec.com/products/stereo-vision-camera/gemini-335l/) | stereo, global shutter, up to 1280x800 @ 30 | 0.17-20 m+, optimal 0.25-6 m | H90 x V65 deg | 95 mm | up to 1280x800 @ 60, H94 x V68 | IMU; IP65; USB 3.0 Type-C; multi-device sync with unified HW timestamps |

Gemini 335 (non-L) is the same generation with a shorter baseline
(exact value unverified). The 330 series is what Orbbec marks "recommended
for new designs" in its ROS 2 driver.

**SDK / ROS.**
- OrbbecSDK v2 (open source, cross-platform): https://github.com/orbbec/OrbbecSDK_v2 ;
  supports Gemini 330/335/336, Gemini 2, Femto Bolt/Mega, Astra 2, Pulsar LiDAR.
- ROS 2: https://github.com/orbbec/OrbbecSDK_ROS2 - use branch `v2-main` for
  Gemini 330/335/336/2 and Femto; legacy `main` (OpenNI) for Astra. Foxy,
  Humble, Jazzy on Ubuntu 20.04-24.04. Supports depth-to-colour alignment,
  point clouds, multi-camera synchronization and hardware timestamp alignment.
  Install udev rules or the device will not open without root.

**Quirks.** Two-branch driver confusion is the number one support issue;
check which branch a colleague's launch file assumes. Devices outside the
"recommended" list get "maintenance-level patches" only.

## Orbbec Femto Bolt / Femto Mega (iToF, Azure Kinect lineage)

- Femto Bolt: ToF at 850 nm, range 0.25-5.46 m by mode; depth modes WFOV
  1024x1024 @ 15 or 512x512 @ 5/15/25/30, NFOV 640x576 @ 5/15/25/30 or
  320x288; passive IR 1024x1024 @ 30; RGB up to 3840x2160 @ 30 with HDR;
  6-DoF IMU; USB 3.2 Gen1 Type-C; 8-pin sync connector (SYNC_IN pin 3,
  SYNC_OUT pin 6) with RJ45 adaptor; 115 x 40 x 65 mm, 348 g
  ([Femto Bolt](https://www.orbbec.com/products/tof-camera/femto-bolt/)).
- Positioned by Microsoft and Orbbec as the Azure Kinect DK replacement;
  "identical operating modes and performance" for the depth module; Orbbec
  ships a K4A wrapper so Azure Kinect SDK apps port over
  ([comparison](https://www.orbbec.com/documentation/comparison-with-azure-kinect-dk/),
  [JetsonHacks review](https://jetsonhacks.com/2024/07/07/orbbec-femto-bolt-a-microsoft-azure-kinect-replacement/)).
- Femto Mega: same ToF module with on-board compute and Ethernet/PoE output
  (specs unverified here).
- ROS 2: same `OrbbecSDK_ROS2` `v2-main` branch.

**Quirks.** ToF needs the sensor to warm up for stable absolute depth
(unverified magnitude). Flying pixels at object edges and multipath in
corners are inherent; filter by depth gradient. Sunlight saturates the 850 nm
return; indoor sensor in practice. 1024x1024 WFOV is limited to 15 fps.

## Luxonis OAK-D Pro family (active stereo + on-camera NN)

- OAK-D Pro ([Luxonis docs](https://docs.luxonis.com/hardware/products/OAK-D%20Pro)):
  stereo pair OV9282 1280x800 mono global shutter, baseline 7.5 cm
  ([Luxonis shop](https://checkout.luxonis.com/products/oak-d-pro)); colour
  IMX378 4056x3040 rolling shutter (AF variant); IR dot projector (up to 1 W)
  plus flood IR LED (up to 1 W) behind 940 nm notch filters for night vision;
  RVC2 SoC, 4 TOPS (1.4 TOPS for AI); USB 2/3; BNO086 9-axis IMU.
- Depth range: MinZ ~20 cm (400P extended) to ~70 cm (800P); ideal range
  quoted "~80cm - 12m" on the product docs and ~10 m elsewhere in Luxonis docs
  ([stereo depth accuracy](https://docs.luxonis.com/projects/hardware/en/latest/pages/guides/depth_accuracy/)).
  Treat >6 m as coarse.
- OAK-D Pro W / Pro W PoE: 150 deg diagonal FOV stereo pair, 120 or 150 deg
  colour, IP66, PoE variant for long cable runs
  ([OAK-D Pro W](https://shop.luxonis.com/products/oak-d-pro-w),
  [Pro W PoE docs](https://docs.luxonis.com/hardware/products/OAK-D%20Pro%20W%20PoE)).
- Newer RVC4-based "OAK4" generation: (unverified; not confirmed in fetched
  docs, check luxonis.com).

**SDK / ROS.**
- DepthAI SDK v3: https://docs.luxonis.com/software-v3/ ; runs neural nets on
  the camera ("get the inference results straight from camera").
- ROS 2: https://github.com/luxonis/depthai-ros , docs at
  https://docs.luxonis.com/software-v3/depthai/ros/ . Humble/Jazzy package is
  `depthai_ros_driver_v3`; Kilted+ uses `depthai_ros_driver` (v3 default).
  apt binaries for Humble/Jazzy come from the ROS testing repo. Publishes
  RGB, stereo depth, point cloud (via filters), IMU.

**Quirks.** Short 7.5 cm baseline means depth noise grows fast beyond 2-3 m;
good for close-range and edge inference, not for long-range mapping. The
ROS driver collects anonymized telemetry; disable via environment variable
per the repo README. Rolling-shutter colour vs global-shutter mono means
RGB and depth are not exposure-matched during fast motion.

## Cross-family notes

- IR wavelengths in the same cell: RealSense projectors and Femto Bolt ToF
  are both near-IR around 850 nm (Femto Bolt confirmed 850 nm; RealSense
  projector wavelength unverified), OAK-D Pro uses 940 nm. Mixed active
  sensors with overlapping FOV need a test before deployment.
- Only ZED X (GMSL2), Gemini 335L, Femto Bolt, and RealSense (sync cable)
  document hardware multi-camera sync; ZED 2i and OAK USB units rely on
  software timestamps (unverified for OAK).
- Every family publishes `sensor_msgs/CameraInfo`; always read `K` and the
  image size from the topic rather than the datasheet.
- Firmware, SDK, and ROS wrapper versions are coupled for every vendor.
  Record all three in the hardware log when a unit arrives.

## Contacts / field log

- Who to contact per vendor: (to fill in the field)
- Units on hand, serials, firmware: (to fill in the field)

## Sources

RealSense: [D435i](https://www.realsenseai.com/products/depth-camera-d435i/), [Intel D435i spec](https://www.intel.com/content/www/us/en/products/sku/190004/intel-realsense-depth-camera-d435i/specifications.html), [D455](https://www.automate.org/products/realsense/realsense-d455-depth-camera), [D405](https://www.therobotreport.com/intel-adds-short-range-realsense-d405-depth-camera/), [D400 datasheet](https://www.mouser.com/pdfdocs/Intel_D400_Series_Datasheet.pdf), [multi-camera](https://dev.realsenseai.com/docs/multiple-depth-cameras-configuration/), [D457 sync](https://realsenseai.com/wp-content/uploads/2025/08/RealSense-D457-Hardware-Synchronization-V0.11.pdf), [IR filter](https://www.intelrealsense.com/stereo-depth-with-ir/), [realsense-ros](https://github.com/IntelRealSense/realsense-ros), [spin-out](https://www.realsenseai.com/news-insights/news/realsense-completes-spin-out-from-intel-raises-50-million-to-accelerate-ai-powered-vision-for-robotics-and-biometrics/), [post-Intel roadmap](https://www.therobotreport.com/after-intel-exit-realsense-maps-its-own-future-in-3d-vision/), [L515 spec](https://www.intel.com/content/www/us/en/products/sku/201775/intel-realsense-lidar-camera-l515/specifications.html), [L515 EOL](https://www.therobotreport.com/intel-issues-end-of-life-notice-realsense-lidar/).
Stereolabs: [ZED 2i](https://www.stereolabs.com/store/products/zed-2i), [range FAQ](https://support.stereolabs.com/hc/en-us/articles/1500008533841), [ZED X docs](https://docs.stereolabs.com/docs/products/cameras/zedx), [ZED X datasheet](https://static.generation-robots.com/media/zed-x-datasheet-v1.2.pdf), [ZED Link](https://docs.stereolabs.com/docs/products/embedded/zed-link-capture-card), [GMSL2 sync](https://docs.stereolabs.com/docs/products/cameras/zedxone/dual-camera-stereo-vision), [depth modes](https://docs.stereolabs.com/docs/depth-sensing/depth-modes.md), [zed-ros2-wrapper](https://github.com/stereolabs/zed-ros2-wrapper), [ZED 2i accuracy study](https://www.sciencedirect.com/science/article/pii/S0921889024001374).
Orbbec: [Gemini 2](https://www.orbbec.com/products/stereo-vision-camera/gemini-2/), [Gemini 335L](https://www.orbbec.com/products/stereo-vision-camera/gemini-335l/), [Femto Bolt](https://www.orbbec.com/products/tof-camera/femto-bolt/), [vs Azure Kinect](https://www.orbbec.com/documentation/comparison-with-azure-kinect-dk/), [OrbbecSDK_ROS2](https://github.com/orbbec/OrbbecSDK_ROS2).
Luxonis: [OAK-D Pro](https://docs.luxonis.com/hardware/products/OAK-D%20Pro), [OAK-D Pro shop](https://checkout.luxonis.com/products/oak-d-pro), [depth accuracy](https://docs.luxonis.com/projects/hardware/en/latest/pages/guides/depth_accuracy/), [OAK-D Pro W](https://shop.luxonis.com/products/oak-d-pro-w), [ROS docs](https://docs.luxonis.com/software-v3/depthai/ros/), [depthai-ros](https://github.com/luxonis/depthai-ros).
