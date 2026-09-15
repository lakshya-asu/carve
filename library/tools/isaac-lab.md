---
title: Isaac Lab and Isaac Sim
date: 2026-09-05
tags: [tool, simulation, isaac-lab, isaac-sim, nvidia, gpu]
status: draft
source: https://isaac-sim.github.io/IsaacLab/ ; https://docs.isaacsim.omniverse.nvidia.com/
---

# Isaac Lab and Isaac Sim

Isaac Sim is NVIDIA's Omniverse-based simulator (PhysX 5 GPU physics, RTX rendering, USD scenes).
Isaac Lab is the learning framework on top: manager-based and direct RL envs vectorized over
thousands of instances per GPU, actuator models, sensors, randomization, and wrappers for RSL-RL,
rl_games, SKRL and SB3. This is the install and gotcha record; the workflow lives in
[sim-first-workflow](../topics/sim-first-workflow.md).

## Versions (checked 2026-09-05)

| Isaac Lab | Isaac Sim | Python | Linux driver | Status |
|---|---|---|---|---|
| 2.2.x (Aug 2025) | 5.0 (4.5 compat) | 3.11 | 580.65.06 | superseded |
| 2.3.0 (28 Oct 2025), 2.3.1, 2.3.2 (2 Feb 2026) | 5.1.0 (21 Oct 2025) | 3.11 | 580.65.06 | last 2.x GA; pin for production twins |
| 3.0.0-beta (Mar 2026), beta2 (Jun 2026), beta2.patch1 (2 Jul 2026) | 6.0.0 (4 Jun 2026), 6.0.1 (22 Jun 2026) | 3.12 | 595.58.03 | beta; PhysX and Newton backends, pluggable renderer, kit-less mode, quaternion order reported as XYZW (unverified: main still documents wxyz in isaaclab/utils/math.py; check convert_quat on the installed version) |

Sources: [Isaac Lab releases](https://github.com/isaac-sim/IsaacLab/releases), [Isaac Sim releases](https://github.com/isaac-sim/IsaacSim/releases), [5.1 requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html), [6.0 requirements](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html), [3.0 beta 2](https://github.com/isaac-sim/IsaacLab/discussions/6249).

Hardware: RTX GPU with RT cores (A100 and H100 unsupported), 16 GB VRAM minimum (RTX 4080 class),
32 GB RAM, Ubuntu 22.04 or 24.04. pip installs need GLIBC 2.35 or newer, so no Ubuntu 20.04
([pip install](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_python.html)).

## Install (2.3.2 on Isaac Sim 5.1, pip route)

```bash
conda create -n isaaclab python=3.11 && conda activate isaaclab
pip install "isaacsim[all,extscache]==5.1.0" --extra-index-url https://pypi.nvidia.com
git clone -b v2.3.2 https://github.com/isaac-sim/IsaacLab.git && cd IsaacLab
./isaaclab.sh --install
./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/train.py --task Isaac-Cartpole-v0 --headless
./isaaclab.sh --test    # pytest suite; what Isaac Lab's own GPU CI runs
```

Torch is pinned by the installer (2.7.0/cu128 on x86 for 2.3.2)
([pip installation](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/setup/installation/pip_installation.html)).
Do not activate this env in a shell that has sourced `/opt/ros/humble/setup.bash`; the Humble
`PYTHONPATH` leak breaks 3.11 interpreters ([ros2-humble](ros2-humble.md)).

Docker: `./docker/container.py start` builds `isaac-lab-base` on `nvcr.io/nvidia/isaac-sim:5.1.0`;
a prebuilt `nvcr.io/nvidia/isaac-lab:2.3.2` exists. The base image needs `--gpus all`,
`-e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y`, `--network=host` and the cache volume mounts
([Isaac Lab docker](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/deployment/docker.html),
[Isaac Sim container](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_container.html)).
Isaac Lab's CI runs `build.yml` on `[self-hosted, gpu]` per PR and a daily compatibility job at
04:00 ([workflows](https://github.com/isaac-sim/IsaacLab/tree/main/.github/workflows)).

## Headless and streaming

- `--headless` on any Isaac Lab script; `--enable_cameras` when the task renders sensors;
  `--livestream 2` for WebRTC (client on TCP 49100, UDP 47998); `--video`, `--video_length`,
  `--video_interval` record rollouts. Env vars `HEADLESS` and `LIVESTREAM` do the same
  ([RL scripts](https://isaac-sim.github.io/IsaacLab/main/source/overview/reinforcement-learning/rl_existing_scripts.html),
  [livestream](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/manual_livestream_clients.html)).
- The container "supports running our Python apps and standalone examples in headless mode only".
  GUI mode on a server without a monitor aborts at `vkCreateSwapchain`; EGL/Vulkan in a container
  needs `NVIDIA_DRIVER_CAPABILITIES` to include `graphics`
  ([container toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html)).
- Standalone: `SimulationApp({"headless": True})` appends `--no-window` itself.

## ROS 2 bridge

- Extension `isaacsim.ros2.bridge`. Isaac Sim 5.1 ships precompiled Humble and Jazzy libraries
  under `exts/isaacsim.ros2.bridge/{humble,jazzy}/lib`, so no system ROS 2 is required. Set
  `ROS_DISTRO`, `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, add that lib dir to `LD_LIBRARY_PATH`; or
  set `ros_distro = "system_default"` in the extension toml to use the host install
  ([ROS 2 install](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_ros.html)).
  Ubuntu 22.04 with Humble (Jazzy also works), 24.04 with Jazzy; 6.0 adds native Jazzy on 3.12
  ([6.0 announcement](https://github.com/isaac-sim/IsaacSim/discussions/538)).
- Multi-machine or Docker: `--net=host` plus `FASTRTPS_DEFAULT_PROFILES_FILE` pointing at a UDP
  transport profile. Example workspaces with Nav2 and MoveIt: `humble_ws` and `jazzy_ws` in
  [IsaacSim-ros_workspaces](https://github.com/isaac-sim/IsaacSim-ros_workspaces).
- Isaac Lab 2.x has no ROS 2 extension or examples. What exists: `docker/Dockerfile.ros2` (Humble
  via apt, `ros2` compose profile; the 2.3.0 notes say it "is not currently expected to work"
  after the Python 3.11 move) and `*ros_inference_env_cfg.py` for UR10e reach and gear assembly,
  which fix observation order for an Isaac ROS inference node
  ([gear assembly deployment](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/policy_deployment/02_gear_assembly/gear_assembly_policy.html),
  [release notes](https://isaac-sim.github.io/IsaacLab/main/source/refs/release_notes.html)).
  Practical pattern: ROS 2 nodes in `rosdev`, Isaac Sim in its own env with the bundled bridge
  libs, talking over topics.

## Asset import and cameras

- CLI: `scripts/tools/convert_urdf.py`, `convert_mjcf.py`, `convert_mesh.py`
  ([import new asset](https://isaac-sim.github.io/IsaacLab/main/source/how-to/import_new_asset.html)).
- URDF importer defaults that matter: one convex hull per link unless "Convex Decomposition";
  inertia computed from density unless "Import Inertia Tensor" is on; massless links get "Default
  Density"; self-collision off. 5.1 removed the merge-joints flag; 2.3.1 patched around it
  ([URDF importer](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/importer_exporter/ext_isaacsim_asset_importer_urdf.html)).
- Camera from real intrinsics: `Camera.set_opencv_pinhole_properties(cx, cy, fx, fy)`, square
  pixels only ([camera sensor](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/py/source/extensions/isaacsim.sensors.camera/docs/index.html)).
- Randomization (`EventTermCfg`, `isaaclab.envs.mdp.events`) and actuator models are covered in
  [sim-first-workflow](../topics/sim-first-workflow.md#evaluation-in-sim).

## Gotchas

- Determinism holds only for the same hardware and Isaac Sim/PhysX version, rigid bodies and
  articulations; randomize physics materials at setup, not runtime
  ([reproducibility](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/features/reproducibility.html)).
- Version pairs are strict: 2.3.x on 5.1, 3.0 beta on 6.0.
- Newton in 2.x is a separate `feature/newton` branch without PhysX
  ([Newton integration](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/experimental-features/newton-physics-integration/index.html)).
- Isaac Sim's `python.sh` is its own interpreter; never mix it with `rll` or `rosdev`.
- First launch downloads extensions and assets; mount the cache volumes in Docker or every start
  re-downloads. Livestream is not supported on aarch64 (DGX Spark) in 5.1.0.

## Links

- Docs: https://isaac-sim.github.io/IsaacLab/ ; https://docs.isaacsim.omniverse.nvidia.com/
- Repos: https://github.com/isaac-sim/IsaacLab ; https://github.com/isaac-sim/IsaacSim ; https://github.com/isaac-sim/IsaacSim-ros_workspaces ; https://github.com/newton-physics/newton
