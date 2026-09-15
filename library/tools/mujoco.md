---
title: MuJoCo, MJX and MuJoCo Warp
date: 2026-09-05
tags: [tool, simulation, mujoco, mjx, mujoco-warp, ros2-control]
status: draft
source: https://mujoco.readthedocs.io/ ; https://github.com/google-deepmind/mujoco
---

# MuJoCo, MJX and MuJoCo Warp

MuJoCo is the CPU rigid-body simulator with a soft-contact model that manipulation and
locomotion research defaults to for fidelity. MJX is its JAX API, now with two backends (MJX-JAX
and MJX-Warp). MuJoCo Warp (MJWarp) is the NVIDIA-plus-DeepMind GPU reimplementation and the
engine inside the Newton project. This note covers install, versions, the ROS 2 bridge and
gotchas; the workflow lives in [sim-first-workflow](../topics/sim-first-workflow.md).

## Versions (checked 2026-09-05)

| Package | Version | Date | Note |
|---|---|---|---|
| `mujoco` | 3.12.0 | 20 Aug 2026 | Python 3.10 to 3.14 ([release](https://github.com/google-deepmind/mujoco/releases/tag/3.12.0), [PyPI](https://pypi.org/project/mujoco/)) |
| `mujoco-warp` | 3.12.0 | 20 Aug 2026 | PyPI classifier "Development Status :: 3 - Alpha"; flex experimental ([PyPI](https://pypi.org/project/mujoco-warp/), [repo](https://github.com/google-deepmind/mujoco_warp)) |
| MuJoCo 3.5 | | 13 Feb 2026 | MJWarp "officially released"; actuator and sensor delays via `mjData.history`; sysid toolbox ([3.5 notes](https://github.com/google-deepmind/mujoco/discussions/3094)) |
| `mujoco_ros2_control` | 0.1.1 tag, pre-1.0 | pushed Sep 2026 | Humble, Jazzy, Kilted, Lyrical supported; Rolling in development ([repo](https://github.com/ros-controls/mujoco_ros2_control)) |

Releases are roughly monthly; pin the exact version in `pyproject.toml` and in every experiment record.

## Install

```bash
conda activate rll
pip install "mujoco==3.12.0"                      # CPU, viewer, MJX-JAX
pip install "mujoco-warp==3.12.0"                 # GPU; CPU fallback for debugging
python -m mujoco.viewer --mjcf path/to/scene.xml  # sanity check the model
```

MJX docs steer users to MJX-Warp, which "resolves key performance bottlenecks exhibited in
MJX-JAX around contacts and constraints" but has no autodiff; keep MJX-JAX when you need
gradients ([MJX docs](https://mujoco.readthedocs.io/en/stable/mjx.html)). MuJoCo Playground wraps
MJX environments for locomotion and manipulation on either backend (`--impl warp`); its vision
path is the MJWarp batch renderer, the Madrona renderer from the paper was removed in March 2026
([playground](https://github.com/google-deepmind/mujoco_playground), [paper](https://arxiv.org/abs/2502.08844)).
mjlab reproduces the Isaac Lab manager API on MJWarp under Apache 2.0
([mjlab](https://github.com/mujocolab/mjlab), [paper](https://arxiv.org/abs/2601.22074)).

## Models

- Menagerie: 68 curated robot directories graded A+ to C, each with its own licence (BSD-3,
  Apache, MIT); includes Franka FR3 and Panda, UR5e, xArm7, Unitree Go2 and G1, Robotiq 2F-85,
  LEAP hand, Spot ([mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie)). Start
  every twin from the Menagerie model when one exists and diff limits and masses against the
  vendor URDF.
- URDF loads directly. A `<mujoco>` child of `<robot>` carries compiler options; URDF defaults for
  `strippath`, `fusestatic`, `discardvisual` differ from MJCF and URDF is not schema-checked
  ([URDF extensions](https://mujoco.readthedocs.io/en/stable/modeling.html#urdf-extensions)).
  The `compile` sample converts URDF to MJCF for hand-editing
  ([samples](https://mujoco.readthedocs.io/en/stable/programming/samples.html#compile)).
- `obj2mjcf` splits an OBJ by material and runs CoACD convex decomposition; last release 0.0.25
  (Mar 2024), so expect to patch it ([obj2mjcf](https://github.com/kevinzakka/obj2mjcf)).

## ROS 2 bridge

`mujoco_ros2_control` (ros-controls org, Apache 2.0) is a ros2_control hardware plugin that runs
MuJoCo inside `ros2_control_node`:

```xml
<ros2_control name="MujocoSystem" type="system">
  <hardware>
    <plugin>mujoco_ros2_control/MujocoSystemInterface</plugin>
    <param name="mujoco_model">/abs/path/scene.xml</param>
    <param name="sim_speed_factor">1.0</param>
  </hardware>
  <!-- joints exactly as on the real robot -->
</ros2_control>
```

`ros2 launch mujoco_ros2_control_demos 01_basic_robot.launch.py` starts robot_state_publisher and
the package's `ros2_control_node` with `controllers.yaml`; it can also generate MJCF from the URDF
at runtime via `<mujoco_inputs>` tags
([demo URDF](https://github.com/ros-controls/mujoco_ros2_control/blob/main/mujoco_ros2_control_demos/demo_resources/robot/test_robot.urdf),
[launch](https://github.com/ros-controls/mujoco_ros2_control/blob/main/mujoco_ros2_control_demos/launch/01_basic_robot.launch.py)).
The older `moveit/mujoco_ros2_control` (MIT, last push Nov 2025) is the fork lineage; use the
ros-controls one. Run it from `rosdev` (Humble, Python 3.10), not `rll`.

## Headless rendering

Linux backends are GLX (X11 window), OSMesa (software, headless) and EGL (GPU, headless); select
with `MUJOCO_GL=egl|osmesa|glx|glfw` before `import mujoco`
([visualization](https://mujoco.readthedocs.io/en/stable/programming/visualization.html),
[gl_context.py](https://github.com/google-deepmind/mujoco/blob/main/python/mujoco/rendering/classic/gl_context.py)).
CI: `egl` on the GPU runner, `osmesa` on laptops.

## Gotchas

- MJWarp lacks `noslip`, PGS, plugin actuators and sensors, the `IMPLICITFAST` midpoint
  integrator, and Warp differentiability; flex is experimental. Tune the XML on CPU MuJoCo, then
  confirm MJWarp reproduces the rollout before scaling ([mujoco_warp](https://github.com/google-deepmind/mujoco_warp)).
- `mujoco` and `mujoco-warp` versions must match; both are cut on the same day.
- Contact parameters (`solref`, `solimp`, `condim`, `margin`) are where "works in sim" hides.
  Per-pair friction beats a global default; record every value's provenance.
- Use the built-in actuator and sensor delays (since 3.5) for measured latency instead of
  hand-rolled buffers ([3.5 notes](https://github.com/google-deepmind/mujoco/discussions/3094)).
- Meshes collide on their convex hull unless split; a concave finger becomes a solid block.
- Menagerie models carry their own licences; check before shipping a customer deliverable.

## Links

- Docs https://mujoco.readthedocs.io/ ; changelog https://mujoco.readthedocs.io/en/stable/changelog.html ; MJX https://mujoco.readthedocs.io/en/stable/mjx.html ; MJWarp https://mujoco.readthedocs.io/en/stable/mjwarp/index.html
- Repos https://github.com/google-deepmind/mujoco ; https://github.com/google-deepmind/mujoco_warp ; https://github.com/google-deepmind/mujoco_menagerie ; https://github.com/google-deepmind/mujoco_playground ; https://github.com/ros-controls/mujoco_ros2_control ; https://github.com/mujocolab/mjlab ; https://github.com/newton-physics/newton
