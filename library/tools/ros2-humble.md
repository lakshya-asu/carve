---
title: ROS 2 Humble (local install)
date: 2026-09-05
tags: [tool, ros2, humble, local-machine]
status: draft
source: field (this machine, checked 2026-09-05)
---

# ROS 2 Humble (local install)

Concepts, QoS, executors, networking, rosbag2, and the debugging checklists live in
[ros2-in-depth](../topics/ros2-in-depth.md). This note holds only what is true of this machine.

## Install

- `/opt/ros/humble`, Ubuntu 22.04, system Python 3.10.12. Packages `ros-humble-desktop 0.10.0` and
  `ros-humble-ros-base 0.10.0` (apt, 2026-08 builds). Support ends May 2027.
- Workspaces: `~/ros2_ws` (tutorial packages: `py_pubsub`, `cpp_pubsub`, `action_tutorials_*`,
  `turtlesim_catch_them_all`, `my_robot_description`), `~/cinema_ws` (vehicle project).
- rmw: only `rmw_fastrtps_cpp` (`ros-humble-rmw-fastrtps-cpp 6.2.10`, Fast DDS 2.6.12). Not installed:
  `rmw_cyclonedds_cpp`, `rmw_zenoh_cpp`.
- rosbag2 0.15.16 with `sqlite3` storage only; `ros-humble-rosbag2-storage-mcap` is not installed, so
  `ros2 bag record -s mcap` fails until `sudo apt install ros-humble-rosbag2-storage-mcap`. zstd compression
  plugin is present.
- Tracing: `ros2 run tracetools status` prints `Tracing disabled` (Humble binaries ship without LTTng
  instrumentation).
- Installed tooling: `rqt_graph`, `rqt_plot`, `tf2_tools`, `sros2`. Not installed: `topic_tools`,
  `foxglove_bridge`, `plotjuggler`, `domain_bridge`.

## Environment

`~/.bashrc` sources `/opt/ros/humble/setup.bash` twice (lines 118 and 146) and sets `ROS_LOCALHOST_ONLY=0`;
`ROS_DOMAIN_ID` is unset (defaults to 0). Aliases: `rosdev` (deactivate conda, source Humble and
`~/ros2_ws/install`), `cb` (clean `colcon build --symlink-install` in `~/ros2_ws`), `build`.

## Gotcha: ROS PYTHONPATH leaks into conda/venv (found 2026-09-05)

Sourcing Humble exports `PYTHONPATH=/opt/ros/humble/lib/python3.10/site-packages:/opt/ros/humble/local/lib/python3.10/dist-packages`.
Any non-3.10 interpreter (the `rll` conda env on 3.11) then imports Humble's `launch` package through a pytest
plugin and fails on a missing `yaml`.

Fix per invocation: `env -u PYTHONPATH pytest`. Fix per env: pure-ML work in an env that never sources ROS, ROS
work in `rosdev` (3.10). Background and the RoboStack alternative: [ros2-in-depth, Python environment pitfalls](../topics/ros2-in-depth.md#python-environment-pitfalls).

## Verified here

- The reference policy node in [ros2-in-depth](../topics/ros2-in-depth.md) was run on 2026-09-05 with
  `ROS_DOMAIN_ID=77 ROS_LOCALHOST_ONLY=1`, two `ros2 topic pub -r 30 --qos-reliability best_effort` sources,
  and `ros2 topic hz -w 40 /policy_action`: 17 to 20 Hz against a 20 Hz timer (two runs, `ros2 topic pub`
  itself is a Python process), reliable/volatile/deadline 100 ms endpoint as designed, watchdog warning at 1 Hz
  and no commands once the sources stopped.
- Fill in from the field: driver quirks per robot.
