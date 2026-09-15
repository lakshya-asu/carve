---
title: ROS 2 in depth for a robot learning engineer
date: 2026-09-05
tags: [topic, ros2, dds, qos, executors, tf2, rosbag2, launch, networking, humble, jazzy, kilted]
status: draft
source: synthesis (primary links inline and in Sources)
---

# ROS 2 in depth for a robot learning engineer

## What it is

ROS 2 is two client libraries (`rclcpp`, `rclpy`) over an abstract middleware interface (`rmw`) whose default implementations are DDS vendors. Discovery is peer-to-peer over multicast UDP, transport is UDP or shared memory, and every topic carries a Quality of Service contract that both ends must satisfy or nothing flows ([ROS on DDS](https://design.ros2.org/articles/ros_on_dds.html), [QoS](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html)). In September 2026 the distro picture is: Humble (installed here, Ubuntu 22.04) ends May 2027; Jazzy (24.04) runs to May 2029; Kilted is a short release ending December 2026; Lyrical Luth shipped May 22, 2026 as the new LTS to May 2031 ([Distributions](https://docs.ros.org/en/rolling/Releases.html)). New customer installs go on Jazzy or Lyrical; Humble stays only where a vendor driver pins it.

## Why it matters in the field

A learned policy is one node in a graph the customer already runs. Whether it receives images at 30 Hz, whether its commands reach the arm before the watchdog trips, and whether a recorded bag replays a failure faithfully all depend on QoS, executor, and network choices that are silent when wrong. An incompatible durability pair gives "no communication" and no console error ([QoS compatibility](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html#qos-compatibilities)); a node whose callbacks all share the default group "essentially acts as if it was handled by a Single-Threaded Executor, even if a multi-threaded one is specified" ([callback groups](https://docs.ros.org/en/humble/How-To-Guides/Using-callback-groups.html)); a bag recorded with `use_sim_time` before `/clock` arrives is "essentially unplayable" ([rosbag2 README](https://github.com/ros2/rosbag2/blob/humble/README.md)). Each of these costs a field day when met unprepared.

## Key concepts and methods

### Distros, Python, and support windows (2026)

| Distro | Ubuntu / system Python | Support ends | Middleware (REP 2000 tiers) |
|---|---|---|---|
| Humble | 22.04 / 3.10 | May 2027 | Fast DDS default, Cyclone Tier 1, no Zenoh row |
| Jazzy | 24.04 / 3.12 | May 2029 | Fast DDS default, Cyclone Tier 1, `rmw_zenoh_cpp` binaries exist but no REP 2000 row |
| Kilted | 24.04 / 3.12 | December 2026 | Fast DDS default, Cyclone and `rmw_zenoh_cpp` Tier 1 |
| Lyrical | 24.04 LTS | May 2031 | Adds `EventsCBGExecutor` (10 to 15% less CPU than the single/multi-threaded executors) and `rclpy` `AsyncNode` |

Sources: [REP 2000](https://www.ros.org/reps/rep-2000.html), [Kilted notes](https://docs.ros.org/en/rolling/Releases/Release-Kilted-Kaiju.html), [Lyrical notes](https://docs.ros.org/en/rolling/Releases/Release-Lyrical-Luth.html). Two changes after Humble bite control code: Iron deprecated `ROS_LOCALHOST_ONLY` in favor of `ROS_AUTOMATIC_DISCOVERY_RANGE` and `ROS_STATIC_PEERS` ([Iron notes](https://docs.ros.org/en/jazzy/Releases/Release-Iron-Irwini.html)), and Jazzy's executors moved to a static wait set after which "callbacks in the executor are no longer ordered consistently, even within the same entity" ([Jazzy notes](https://docs.ros.org/en/jazzy/Releases/Release-Jazzy-Jalisco.html), [rclcpp#2532](https://github.com/ros2/rclcpp/issues/2532)). Never rely on callback order between two subscriptions.

### Architecture: rmw and DDS vendors

`RMW_IMPLEMENTATION` selects the middleware per process; every process on a robot must use the same one, since cross-vendor interop "is not guaranteed" ([vendors](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Different-Middleware-Vendors.html)). Fast DDS (`rmw_fastrtps_cpp`) is the default everywhere and the only rmw installed on this machine. Its switches are environment variables: `RMW_FASTRTPS_PUBLICATION_MODE` (SYNCHRONOUS by default, so `publish()` blocks until data is on the wire) and `RMW_FASTRTPS_USE_QOS_FROM_XML=1` with `FASTRTPS_DEFAULT_PROFILES_FILE` for history memory policy and transports ([rmw_fastrtps README](https://github.com/ros2/rmw_fastrtps/blob/humble/README.md)). It also enables shared memory between participants it judges to be on one host, which matters for Docker (below). Cyclone DDS (`ros-humble-rmw-cyclonedds-cpp`) takes one XML string in `CYCLONEDDS_URI`, including static peers when multicast is unavailable ([rmw_cyclonedds README](https://github.com/ros2/rmw_cyclonedds)), and wants `net.core.rmem_max` raised for large messages ([DDS tuning](https://docs.ros.org/en/humble/How-To-Guides/DDS-tuning.html)). `rmw_zenoh_cpp` drops DDS: nodes do not multicast, they connect to a router started with `ros2 run rmw_zenoh_cpp rmw_zenohd`, and `ZENOH_CONFIG_OVERRIDE='connect/endpoints=["tcp/192.168.0.3:7447"]'` links routers across sites ([rmw_zenoh README](https://github.com/ros2/rmw_zenoh)). It is Tier 1 in Kilted; the DDS discovery variables do not apply to it ([Improved dynamic discovery](https://docs.ros.org/en/jazzy/Tutorials/Advanced/Improved-Dynamic-Discovery.html)). Rule: stay on Fast DDS until a documented problem (WiFi discovery storms, cross-subnet fleets) points at Zenoh, then move the whole robot at once.

### Discovery, domain IDs, multicast, discovery server

DDS derives UDP ports from `ROS_DOMAIN_ID`; on Linux choose 0 to 101 to stay clear of the ephemeral range, and expect port collisions past 120 processes per domain per host since each participant takes two ports ([Domain ID](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Domain-ID.html)). Default discovery is multicast to the subnet. `ROS_LOCALHOST_ONLY=1` (Humble) or `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` (Iron+) confines it to the machine; `ROS_STATIC_PEERS=10.0.0.5;10.0.0.6` adds unicast peers ([Improved dynamic discovery](https://docs.ros.org/en/jazzy/Tutorials/Advanced/Improved-Dynamic-Discovery.html)). On WiFi multicast "may not work reliably", and the Fast DDS discovery server replaces it: `fastdds discovery --server-id 0 --udp-address <ip> --udp-port 11811` on one host, `ROS_DISCOVERY_SERVER=<ip>:11811` on every client. CLI tools then only see topics they hold endpoints for unless the daemon runs as a SUPER_CLIENT through an XML profile ([Discovery server](https://docs.ros.org/en/humble/Tutorials/Advanced/Discovery-Server/Discovery-Server.html)). `ros2 daemon stop` is the first move whenever `ros2 topic list` disagrees with reality; the daemon caches the graph.

### QoS in practice

Compatibility is request-versus-offer: the subscription requests a minimum, the publisher offers a maximum, and the pair connects only if every policy is satisfied. The combinations that fail silently ([QoS](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html#qos-compatibilities)):

| Publisher | Subscription | Result |
|---|---|---|
| Best effort | Reliable | no connection |
| Volatile | Transient local | no connection |
| Deadline default | Deadline x | no connection |
| Deadline x | Deadline y < x | no connection |
| Liveliness automatic | Manual by topic | no connection |

The reverse of each row connects. Camera and joint-state drivers publish `SENSOR_DATA` (keep last 5, best effort, volatile, [qos_profiles.h](https://github.com/ros2/rmw/blob/humble/rmw/include/rmw/qos_profiles.h)), so a subscription created with the default profile (reliable, depth 10) never connects: subscribe to sensors with `QoSPresetProfiles.SENSOR_DATA`. Commands and heartbeats are reliable, volatile, depth 1 to 10. Latched state (robot description, calibration, `/tf_static`) is transient local on both ends. Deadline and liveliness are the only policies that turn "the publisher stopped" into a callback (`requested_deadline_missed`, `liveliness_changed`) instead of silence; use them on a policy's command topic. Inspect a live pair with `ros2 topic info -v /topic`, which prints each endpoint's QoS. `KEEP_ALL` history on an image topic is a memory leak waiting for a slow consumer.

### Executors and callback groups

A callback runs only when an executor thread takes it from the wait set; messages stay in the middleware until then and there is no client-library queue ([Executors](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Executors.html)). Everything created without a group lands in the node's default group, which is mutually exclusive. Three consequences:

1. Single-threaded executor plus a 30 Hz image callback that takes 40 ms: the control timer fires late every cycle because the one thread is inside the image callback. The executor works "in a round-robin fashion" without priorities and "callbacks may suffer from priority inversion" ([scheduling semantics](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Executors.html#scheduling-semantics)).
2. Multi-threaded executor with everything in the default group: identical behavior, because one exclusive group serializes all of it ([callback groups](https://docs.ros.org/en/humble/How-To-Guides/Using-callback-groups.html)).
3. A synchronous service or action call inside a callback whose client shares that group "will always cause a deadlock" ([avoiding deadlocks](https://docs.ros.org/en/humble/How-To-Guides/Using-callback-groups.html#avoiding-deadlocks)).

The fix is structural: control timer in its own `MutuallyExclusiveCallbackGroup`, sensor subscriptions in a `ReentrantCallbackGroup` (with a lock) or one exclusive group each, service clients in a third, and `MultiThreadedExecutor(num_threads=...)`, whose default is `multiprocessing.cpu_count()` ([rclpy executors.py](https://github.com/ros2/rclpy/blob/humble/rclpy/rclpy/executors.py)).

### rclpy vs rclcpp for control loops

Python is fine for the policy node at 10 to 50 Hz and wrong for anything that touches the servo loop. Reported numbers: publishing a 10 MB point cloud took 2.8 ms in `rclcpp` and 92 ms in `rclpy` ([ROS Answers 375827](https://answers.ros.org/question/375827/ros2-performance-rclpy-is-30x-100x-slower-than-rclcpp/), conditions unverified); a RoboCup team found the standard executor saturating a core on `/joint_states` at 500 Hz ([Hamburg Bit-Bots 2022](https://robocup.informatik.uni-hamburg.de/en/2022/07/experiences-with-ros-2-on-our-robots/)); `rclpy`'s `MultiThreadedExecutor` had a CPU issue on Jazzy ([rclpy#1452](https://github.com/ros2/rclpy/issues/1452), closed 2025-04). The GIL means Python threads overlap only while native code (a torch forward pass, a DDS wait) releases it. Keep the tick to "copy latest observation, run inference, publish chunk" and leave interpolation, limits, and the 500 Hz to 1 kHz joint loop to `ros2_control` or the vendor SDK ([deployment-engineering](deployment-engineering.md)). Kilted's experimental `rclpy` `EventsExecutor` and Lyrical's `AsyncNode` cut executor overhead but not the GIL.

### Lifecycle nodes and managed startup

A managed node moves through Unconfigured, Inactive, Active, Finalized by `configure`, `activate`, `deactivate`, `cleanup`, `shutdown`; while Inactive, "any data that arrives on managed topics will not be read and or processed" ([node lifecycle](https://design.ros2.org/articles/node_lifecycle.html)). Drive it with `ros2 lifecycle set /policy_node configure` then `activate`; check with `ros2 lifecycle get`. For a policy node: load weights and allocate GPU memory in `on_configure`, start the control timer in `on_activate`, stop publishing in `on_deactivate`. `rclpy.lifecycle.LifecycleNode` exists on Humble; its lifecycle publishers are inert until Active, so a deactivated node cannot command by accident.

### Parameters and dynamic reconfigure

Parameters must be declared before use unless the node sets `allow_undeclared_parameters`; type changes at runtime fail unless declared with `dynamic_typing=True` ([Parameters](https://docs.ros.org/en/humble/Concepts/Basic/About-Parameters.html)). ROS 1's dynamic_reconfigure becomes `add_on_set_parameters_callback`, which validates and must "have no side-effects" because a later callback in the chain may still reject the change; read the accepted value in the timer or an "on parameter event" callback. Override with `--ros-args -p control_rate_hz:=30.0` or `--params-file cell.yaml` ([Node arguments](https://docs.ros.org/en/humble/How-To-Guides/Node-arguments.html)); snapshot a running node with `ros2 param dump /policy_node`.

### Actions for long-running tasks

An action is "a combination of services and topics": goal and result services, a feedback topic, cancel, and status ([actions design](https://design.ros2.org/articles/actions.html)). Use one for "run episode", "home the arm", "collect N demos": anything that lasts seconds, reports progress, and must be cancelable from a dashboard. A service has no cancel and blocks the caller. Since Kilted, rosbag2 records and replays actions ([Kilted notes](https://docs.ros.org/en/rolling/Releases/Release-Kilted-Kaiju.html)).

### Composition and intra-process communication

Loading nodes as components into one `component_container` (or `_mt`, `_isolated`) puts them in one process ([Composition](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Composition.html)). With `use_intra_process_comms(true)` and `std::unique_ptr` messages the subscriber receives the publisher's pointer; `shared_ptr` or `const &` still copies, and one-to-many fan-out copies for all readers but one ([intra-process demo](https://docs.ros.org/en/humble/Tutorials/Demos/Intra-Process-Communication.html)). This is C++ only. A camera-to-policy path that must avoid image copies means a C++ preprocessing component publishing a small tensor topic to Python.

### tf2

`/tf_static` is latched (transient local) and sent once; dynamic frames are re-sent at rate. The listener buffer keeps 10 s by default (`BUFFER_CORE_DEFAULT_CACHE_TIME`, [buffer_core.hpp](https://github.com/ros2/geometry2/blob/humble/tf2/include/tf2/buffer_core.hpp)). Time 0 means "latest available"; asking for `now()` raises "Lookup would require extrapolation into the future" because the newest transform is always slightly old ([tf2 and time](https://docs.ros.org/en/humble/Tutorials/Intermediate/Tf2/Learning-About-Tf2-And-Time-Cpp.html)). The three messages in [cache.cpp](https://github.com/ros2/geometry2/blob/humble/tf2/src/cache.cpp) map to three causes: "into the future" (asked for now, or the publisher's clock runs ahead), "into the past" (stamp older than the 10 s cache, or a bag replayed without `--clock`), and "extrapolation at time" with one sample (a frame published once but not on `/tf_static`). In the policy node pass `timeout=Duration(seconds=0.05)` to `lookup_transform`, and use the six-argument form with a fixed frame to move an observation stamped at t1 into the base frame at t2 ([time travel](https://docs.ros.org/en/humble/Tutorials/Intermediate/Tf2/Time-Travel-With-Tf2-Cpp.html)). Frames follow REP 103 and REP 105 (`CLAUDE.md`).

### Time

Three clocks: system, steady (for hardware timeouts), and ROS time, which equals system time until a `/clock` publisher exists and the node has `use_sim_time=true`; then "if time has not been set it will return zero", and zero "should be considered an error" ([clock and time](https://design.ros2.org/articles/clock_and_time.html)). Every node in a sim or replay session needs `use_sim_time`, including the policy node, or its watchdog compares a bag stamp with wall time and trips. Measure loop jitter with `time.monotonic_ns()`, never with ROS time under sim.

### rosbag2 with MCAP

Humble binaries default to `sqlite3`; `ros-humble-rosbag2-storage-mcap` adds `-s mcap` and is not installed here (2026-09-05, `ros2 bag record --help` lists only `sqlite3`). Iron made MCAP the default ([Iron notes](https://docs.ros.org/en/jazzy/Releases/Release-Iron-Irwini.html)). A data-collection recording:

```bash
ros2 bag record -s mcap -o run_$(date +%Y%m%d_%H%M) --max-bag-duration 300 \
  --storage-preset-profile zstd_fast --max-cache-size 1073741824 \
  /camera/color/image_raw /joint_states /tf /tf_static /policy_action
```

Splitting is by size (`-b`, bytes) or duration (`-d`, seconds), whichever comes first; zstd is the only compression format and file-mode compression is meant to be paired with splitting ([rosbag2 README](https://github.com/ros2/rosbag2/blob/humble/README.md)). MCAP writer options (`chunkSize`, `compression`, `compressionLevel`) go in a YAML for `--storage-config-file`; the `fastwrite` preset skips the index and is not for long-term storage ([rosbag2_storage_mcap](https://github.com/ros2/rosbag2/tree/humble/rosbag2_storage_mcap)). rosbag2 does not throttle: to record a 30 Hz camera at 10 Hz, run `ros2 run topic_tools throttle messages /camera/color/image_raw 10` and record the throttled topic ([topic_tools](https://github.com/ros-tooling/topic_tools)). Replay for a policy test: `ros2 bag play run --clock 100 --rate 1.0 --topics /camera/color/image_raw /joint_states --qos-profile-overrides-path qos.yaml`, every consumer on `use_sim_time`. Recorded QoS follows the publishers at record time, so sensor topics replay best effort; override with the YAML when a reliable subscriber downstream must receive them.

### Launch files in Python

`DeclareLaunchArgument` plus `LaunchConfiguration` parameterize a graph; `PathJoinSubstitution([FindPackageShare("pkg"), "config", "cell.yaml"])` replaces hardcoded paths; `IfCondition(PythonExpression([...]))` gates nodes ([substitutions](https://docs.ros.org/en/humble/Tutorials/Intermediate/Launch/Using-Substitutions.html)). `RegisterEventHandler` with `OnProcessStart`, `OnProcessIO`, `OnExecutionComplete`, `OnProcessExit`, `OnShutdown` sequences startup: the driver starts, `OnProcessStart` launches the policy, `OnProcessExit` of the driver emits `Shutdown()` so nothing keeps commanding a dead arm ([event handlers](https://docs.ros.org/en/humble/Tutorials/Intermediate/Launch/Using-Event-Handlers.html)). For managed nodes, `launch_ros.actions.LifecycleNode` with `OnStateTransition` handlers gives ordered configure and activate.

### Multi-machine networking

Same `ROS_DOMAIN_ID`, same rmw, same distro on every host. Multicast must pass: wired LANs do, WiFi and routed subnets usually do not, and the fix is the discovery server or `ROS_STATIC_PEERS`, never a VPN alone. Tailscale and other WireGuard meshes carry unicast only (open request: [tailscale#11972](https://github.com/tailscale/tailscale/issues/11972)); the working recipe is Fast DDS initial peers with multicast disabled ([Fast DDS: disabling multicast](https://fast-dds.docs.eprosima.com/en/latest/fastdds/use_cases/wifi/disable_multicast.html)) or one Zenoh router per site. Firewalls: open the UDP range the Domain ID doc's port formula gives for your domain and participant count, or only the discovery-server port plus unicast. Docker: `--network=host --ipc=host` together; with only the first, Fast DDS treats containers as one host but "they will not be able to communicate" through separate shared-memory segments ([Fast DDS SHM in Docker](https://fast-dds.docs.eprosima.com/en/latest/docker/shm_docker.html)). Large messages fragment over UDP; if a link drops fragments, raise `net.ipv4.ipfrag_high_thresh` and lower `ipfrag_time` ([DDS tuning](https://docs.ros.org/en/humble/How-To-Guides/DDS-tuning.html)).

### Security (SROS2)

`ros2 security create_keystore ks`, `ros2 security create_enclave ks /ns/node`, then `ROS_SECURITY_KEYSTORE`, `ROS_SECURITY_ENABLE=true`, `ROS_SECURITY_STRATEGY=Enforce` enable DDS authentication, access control, and encryption ([SROS2](https://docs.ros.org/en/humble/Tutorials/Advanced/Security/Introducing-ros2-security.html)). Bother when the robot shares a customer's plant network or crosses the internet, not for a bench cell on an isolated switch. Encryption costs CPU per message on image topics (magnitude unverified here).

### Performance tooling

`ros2 topic hz -w 100 /t`, `ros2 topic bw /t`, and `ros2 topic delay /t` (header stamp to receipt, needs a `std_msgs/Header`) are the first three numbers to write down. `ros2_tracing` gives callback-level timing through LTTng; Humble binaries report "Tracing disabled" (`ros2 run tracetools status`, checked locally) and need `tracetools` rebuilt from source, while Iron and later ship the instrumentation ([ros2_tracing](https://github.com/ros2/ros2_tracing), [Iron notes](https://docs.ros.org/en/jazzy/Releases/Release-Iron-Irwini.html)). `rqt_graph` and `rqt_plot` are installed here; PlotJuggler ([repo](https://github.com/facontidavide/PlotJuggler)) overlays commanded against measured joint traces; Foxglove connects through `foxglove_bridge` ([repo](https://github.com/foxglove/ros-foxglove-bridge)) and reads MCAP directly, the main reason to record MCAP.

### Python environment pitfalls

Binaries are built against the system interpreter (3.10 on Humble); the docs say that with conda "it is very likely that the interpreter will not match" ([Using Python packages](https://docs.ros.org/en/humble/How-To-Guides/Using-Python-Packages.html)). Here `~/.bashrc` sources `/opt/ros/humble/setup.bash`, which exports `PYTHONPATH=/opt/ros/humble/lib/python3.10/site-packages:...`; the 3.11 `rll` env then imports Humble's `launch` through a pytest plugin and fails (from field, 2026-09-05; [ros2-humble](../tools/ros2-humble.md)). Rules: ROS work in `rosdev` (system 3.10, conda deactivated); ML work in `rll` with `env -u PYTHONPATH`; a venv for ROS is created from the system interpreter with `--system-site-packages`. RoboStack ([robostack.github.io](https://robostack.github.io/)) is the only supported way to have ROS and a non-system Python in one conda env.

## A reference node pattern for a learned-policy controller

Sensors arrive in a reentrant group and only store state; one exclusive timer group runs inference and publishes; a watchdog refuses to command on stale observations; a deadline on the command topic lets the downstream controller detect a hung policy without a separate heartbeat.

```python
"""Policy node: multi-threaded executor, callback groups, watchdog, deliberate QoS."""

from __future__ import annotations

import threading
import time

import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSPresetProfiles, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image, JointState
from std_msgs.msg import Float64MultiArray


class PolicyNode(Node):
    """Runs a policy at control_rate_hz; stops commanding when observations go stale."""

    def __init__(self) -> None:
        super().__init__("policy_node")
        self.declare_parameter("control_rate_hz", 20.0)
        self.declare_parameter("obs_timeout_s", 0.2)
        rate_hz = self.get_parameter("control_rate_hz").value
        self._obs_timeout_s = self.get_parameter("obs_timeout_s").value
        self._lock = threading.Lock()
        self._joints: JointState | None = None
        self._image: Image | None = None
        self._rx_ns = dict.fromkeys(("joints", "image"), time.monotonic_ns())  # steady clock: survives sim-time jumps

        sensor_qos = QoSPresetProfiles.SENSOR_DATA.value  # best effort, keep last 5: what drivers offer
        cmd_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                             deadline=Duration(seconds=2.0 / rate_hz))  # consumer detects a hung policy
        sensors = ReentrantCallbackGroup()  # store-only callbacks may overlap
        control = MutuallyExclusiveCallbackGroup()  # inference never overlaps itself
        self.create_subscription(JointState, "joint_states", self._on_joints, sensor_qos, callback_group=sensors)
        self.create_subscription(Image, "camera/color/image_raw", self._on_image, sensor_qos, callback_group=sensors)
        self._cmd_pub = self.create_publisher(Float64MultiArray, "policy_action", cmd_qos)
        self.create_timer(1.0 / rate_hz, self._tick, callback_group=control)

    def _on_joints(self, msg: JointState) -> None:
        with self._lock:
            self._joints, self._rx_ns["joints"] = msg, time.monotonic_ns()

    def _on_image(self, msg: Image) -> None:
        with self._lock:
            self._image, self._rx_ns["image"] = msg, time.monotonic_ns()

    def _tick(self) -> None:
        with self._lock:
            joints, image = self._joints, self._image
            age_s = (time.monotonic_ns() - min(self._rx_ns.values())) * 1e-9
        if joints is None or image is None or age_s > self._obs_timeout_s:
            self.get_logger().warn(f"stale obs ({age_s:.3f} s), not commanding", throttle_duration_sec=1.0)
            return  # silence lets the deadline QoS report us as missing
        self._cmd_pub.publish(Float64MultiArray(data=self._policy(joints, image)))

    def _policy(self, joints: JointState, image: Image) -> list[float]:
        """Replace with the model; output must already be inside joint limits."""
        return list(joints.position)


def main() -> None:
    rclpy.init()
    node = PolicyNode()
    executor = MultiThreadedExecutor(num_threads=3)  # two sensors may overlap while the timer keeps a thread
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.try_shutdown()  # the signal handler may already have shut the context down


if __name__ == "__main__":
    main()
```

`SENSOR_DATA` on the subscriptions because a reliable request against a best-effort driver never connects; reliable depth 1 on the command because the controller should hold the last value rather than miss one; a deadline of two periods so the consumer, not the policy, defines "hung"; `time.monotonic_ns()` for the watchdog because ROS time under `use_sim_time` jumps. `templates/ros2-node/policy_node.py` is the single-threaded version of the same idea.

## Debugging checklists

"My topic isn't showing up":

1. `ros2 daemon stop && ros2 topic list`. The daemon cache is stale more often than the graph is wrong.
2. `echo $ROS_DOMAIN_ID $RMW_IMPLEMENTATION $ROS_LOCALHOST_ONLY` on both hosts; any mismatch ends the search. Humble's `ROS_LOCALHOST_ONLY=1` also blocks Docker-to-host.
3. `ros2 topic info -v /topic`: is there a publisher, and do reliability and durability satisfy the table above. A best-effort publisher with a default subscription is the most common answer.
4. Same message definition on both ends (`ros2 interface show`); a rebuilt `.msg` with the same name and different fields fails to match, and on Humble the failure is silent (from field, unverified on the exact pair).
5. `ros2 multicast receive` on one host, `ros2 multicast send` on the other. If it fails: `ROS_STATIC_PEERS` (Iron+), the discovery server, or Cyclone peers. Firewalls drop UDP silently.
6. Docker without `--network=host`; two containers without `--ipc=host`.
7. Discovery server in use and the CLI is not a super client: give the daemon the SUPER_CLIENT XML.
8. `ros2 doctor --report` for a dump to paste into the incident log.

"My control loop jitters":

1. Measure first: `ros2 topic hz -w 200 /policy_action`, `ros2 topic delay /joint_states`, and tick duration from `time.monotonic_ns()` inside the timer.
2. Everything in the default callback group: give the timer its own exclusive group and use a multi-threaded executor.
3. A sensor callback doing work (decode, resize, normalize) instead of storing. Move it into the tick or a C++ component.
4. Inference longer than half the period: smaller model or image, or chunked actions with inference every N ticks.
5. Logging at rate: `throttle_duration_sec` on warnings, no `print`, no f-string of a large array inside the tick.
6. Synchronous Fast DDS publish stalls behind a slow subscriber: try `RMW_FASTRTPS_PUBLICATION_MODE=ASYNCHRONOUS` and measure again.
7. Reliable QoS on lossy WiFi retransmits and stalls: best effort for observations, reliable for commands, policy on the wired segment.
8. CPU contention: `chrt -f 50` for the controller, pinned cores, laptop on mains; in Docker `--cap-add=SYS_NICE --ulimit rtprio=99` (from field, unverified on this hardware).
9. Under sim time a timer runs at the `/clock` rate; `ros2 bag play --clock 10` makes a 20 Hz timer impossible.

## Practical gotchas

- A `rclpy` subscription with the default QoS never receives images from a best-effort driver, and nothing is printed unless the incompatible-QoS event callback is registered (from field; mechanism in the compatibility table).
- `ros2 bag record --use-sim-time` writes nothing until `/clock` arrives, and a bag mixing time-0 and real stamps is "essentially unplayable" ([rosbag2 README](https://github.com/ros2/rosbag2/blob/humble/README.md)).
- `-s mcap` fails on this Humble install until `ros-humble-rosbag2-storage-mcap` is installed (checked 2026-09-05).
- Jazzy dropped consistent callback ordering; code that assumed "the image callback ran before the joint callback" breaks on upgrade ([Jazzy notes](https://docs.ros.org/en/jazzy/Releases/Release-Jazzy-Jalisco.html)).
- `tf2` lookups at `now()` without a timeout throw on every tick; with a timeout inside an exclusive group they block that whole group for the timeout.
- Many stale `ros2 topic echo` shells on a dev laptop push a host past 120 participants and into the next domain's ports ([Domain ID](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Domain-ID.html)).

## What a forward-deployed engineer must be able to do

- Bring two machines onto one domain over the customer's network within an hour, including the discovery-server fallback when multicast is blocked.
- Read `ros2 topic info -v` and name the QoS pair that blocks a connection without consulting the table.
- Write a policy node with the group layout above, prove the timer holds its period under a 30 Hz image stream with `ros2 topic hz`, and show the watchdog stopping commands when the camera is unplugged.
- Record a day of demos to split, compressed MCAP with the right topics, and replay a failure with `--clock` and `use_sim_time` so the policy sees the same inputs.
- Explain sim, system, and steady time to a customer engineer whose watchdog trips during replay.
- Work both checklists in under fifteen minutes each and log the result in `sops/incident-log-template.md`.
- Choose Humble, Jazzy, or Lyrical for a new cell from the support table and the customer's driver constraints.

## Open questions to learn hands-on

- Tick-time distribution of the reference node on this laptop with a real ACT forward pass at 640x480 and 20 Hz: does the multi-threaded layout beat the single-threaded template, or does the GIL erase the difference.
- Whether `RMW_FASTRTPS_PUBLICATION_MODE=ASYNCHRONOUS` lowers p99 tick time when Foxglove subscribes over WiFi.
- `rmw_zenoh_cpp` on Jazzy across a Tailscale mesh: does one router per site replace the discovery server, and what is image latency.
- CPU cost of MCAP `zstd_fast` at 30 Hz 640x480 RGB plus depth on the recording laptop, and whether frames drop.
- Whether a deadline QoS on `/policy_action` is honored end to end by `ros2_control` controllers or needs an explicit heartbeat topic.

## Related entries

- [deployment-engineering](deployment-engineering.md)
- [teleoperation-and-data-collection](teleoperation-and-data-collection.md)
- [imitation-learning](imitation-learning.md)
- Tools: [ros2-humble](../tools/ros2-humble.md) (local install specifics)
- Templates: `templates/ros2-node/policy_node.py`
- SOPs: `sops/field-deployment-checklist.md`, `sops/incident-log-template.md`

## Sources

- Distributions and release notes: https://docs.ros.org/en/rolling/Releases.html ; REP 2000 https://www.ros.org/reps/rep-2000.html ; Iron https://docs.ros.org/en/jazzy/Releases/Release-Iron-Irwini.html ; Jazzy https://docs.ros.org/en/jazzy/Releases/Release-Jazzy-Jalisco.html ; Kilted https://docs.ros.org/en/rolling/Releases/Release-Kilted-Kaiju.html ; Lyrical https://docs.ros.org/en/rolling/Releases/Release-Lyrical-Luth.html
- Design articles: ROS on DDS https://design.ros2.org/articles/ros_on_dds.html ; node lifecycle https://design.ros2.org/articles/node_lifecycle.html ; clock and time https://design.ros2.org/articles/clock_and_time.html ; actions https://design.ros2.org/articles/actions.html
- Middleware: vendors https://docs.ros.org/en/humble/Concepts/Intermediate/About-Different-Middleware-Vendors.html ; rmw_fastrtps https://github.com/ros2/rmw_fastrtps/blob/humble/README.md ; rmw_cyclonedds https://github.com/ros2/rmw_cyclonedds ; rmw_zenoh https://github.com/ros2/rmw_zenoh ; DDS tuning https://docs.ros.org/en/humble/How-To-Guides/DDS-tuning.html
- Discovery and networking: domain ID https://docs.ros.org/en/humble/Concepts/Intermediate/About-Domain-ID.html ; discovery server https://docs.ros.org/en/humble/Tutorials/Advanced/Discovery-Server/Discovery-Server.html ; improved dynamic discovery https://docs.ros.org/en/jazzy/Tutorials/Advanced/Improved-Dynamic-Discovery.html ; Fast DDS disabling multicast https://fast-dds.docs.eprosima.com/en/latest/fastdds/use_cases/wifi/disable_multicast.html ; Fast DDS SHM in Docker https://fast-dds.docs.eprosima.com/en/latest/docker/shm_docker.html ; Tailscale request https://github.com/tailscale/tailscale/issues/11972
- QoS: https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html ; profile constants https://github.com/ros2/rmw/blob/humble/rmw/include/rmw/qos_profiles.h
- Executors and callback groups: https://docs.ros.org/en/humble/Concepts/Intermediate/About-Executors.html ; https://docs.ros.org/en/humble/How-To-Guides/Using-callback-groups.html ; rclpy executors https://github.com/ros2/rclpy/blob/humble/rclpy/rclpy/executors.py ; rclpy#1452 https://github.com/ros2/rclpy/issues/1452 ; rclcpp#2532 https://github.com/ros2/rclcpp/issues/2532
- Performance reports: Hamburg Bit-Bots 2022 https://robocup.informatik.uni-hamburg.de/en/2022/07/experiences-with-ros-2-on-our-robots/ ; ROS Answers 375827 https://answers.ros.org/question/375827/ros2-performance-rclpy-is-30x-100x-slower-than-rclcpp/
- Parameters and node arguments: https://docs.ros.org/en/humble/Concepts/Basic/About-Parameters.html ; https://docs.ros.org/en/humble/How-To-Guides/Node-arguments.html
- Composition and intra-process: https://docs.ros.org/en/humble/Concepts/Intermediate/About-Composition.html ; https://docs.ros.org/en/humble/Tutorials/Demos/Intra-Process-Communication.html
- tf2: https://docs.ros.org/en/humble/Tutorials/Intermediate/Tf2/Learning-About-Tf2-And-Time-Cpp.html ; https://docs.ros.org/en/humble/Tutorials/Intermediate/Tf2/Time-Travel-With-Tf2-Cpp.html ; https://github.com/ros2/geometry2/blob/humble/tf2/include/tf2/buffer_core.hpp ; https://github.com/ros2/geometry2/blob/humble/tf2/src/cache.cpp
- rosbag2: https://github.com/ros2/rosbag2/blob/humble/README.md ; MCAP plugin https://github.com/ros2/rosbag2/tree/humble/rosbag2_storage_mcap ; topic_tools https://github.com/ros-tooling/topic_tools
- Launch: https://docs.ros.org/en/humble/Tutorials/Intermediate/Launch/Using-Substitutions.html ; https://docs.ros.org/en/humble/Tutorials/Intermediate/Launch/Using-Event-Handlers.html
- Security and tooling: SROS2 https://docs.ros.org/en/humble/Tutorials/Advanced/Security/Introducing-ros2-security.html ; ros2_tracing https://github.com/ros2/ros2_tracing ; PlotJuggler https://github.com/facontidavide/PlotJuggler ; foxglove_bridge https://github.com/foxglove/ros-foxglove-bridge
- Python environments: https://docs.ros.org/en/humble/How-To-Guides/Using-Python-Packages.html ; RoboStack https://robostack.github.io/
