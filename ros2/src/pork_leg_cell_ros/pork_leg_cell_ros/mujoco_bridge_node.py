"""The simulated cell as ROS 2 sees a real one: clock, joint states, camera-derived leg, trajectory and gripper actions.

Runs `applications.pork_leg_alignment.sim.cell.Cell` with a leg, one arm, the jaw gripper and the Gemini 335L model, and
stands in for the robot driver, the belt encoder and the perception computer:

- publishes `/clock` (simulation time, so every node plans on the simulator's clock) and
  `joint_states` with the arm joints under their URDF names and the belt joint `belt_x`, whose
  position is encoder travel;
- when a leg is under the camera, segments the depth frame (geometric segmenter, camera edge
  effects on) and publishes one `leg/perception` for that leg;
- serves `<arm>_arm_controller/follow_joint_trajectory` by interpolating the trajectory on
  simulation time into the arm's position servos, and `gripper_controller/gripper_cmd`;
- scores what happened, because it is the only node that knows the truth: at the trajectory's
  meeting point it reports how far the tool centre point was from the leg's true shank point, and
  after the jaws close, the measured opening against the true shank width, on `sim/grasp_report`.

Runs in the `ros_moveit` environment, which has rclpy, MuJoCo and the repository's src/ packages together.
QoS: `/clock` and `joint_states` best effort keep-last 10; perception and reports reliable.
"""

from __future__ import annotations

import json
import math
import threading
import time

import mujoco
import numpy as np
import rclpy
from builtin_interfaces.msg import Time
from control_msgs.action import FollowJointTrajectory, GripperCommand
from meat_cell_msgs.msg import LegPerception
from meat_cell_ros.conversions import leg_perception_to_msg
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile, qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import JointState
from std_msgs.msg import String

from applications.pork_leg_alignment.grasping.shank_grasp_rule import SHANK_FRACTION
from applications.pork_leg_alignment.perception.leg_segmentation import EmptyBeltReference, LegSegmenter
from applications.pork_leg_alignment.perception.perceive_leg import perceive_leg
from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import (
    ORIGIN_FRACTION,
    PRODUCT_BODY,
    LegConfig,
    leg_centreline,
    leg_half_width_m,
    product_geom_ids,
)
from applications.pork_leg_alignment.sim.scene import CellConfig
from applications.pork_leg_alignment.sim.sensing import CameraSpec
from robotics.core.camera_frame import CameraFrameData
from robotics.hardware.arms import ARM_SPECS, ArmModel
from robotics.hardware.cameras import GEMINI_335L, EdgeEffects, sense_depth
from robotics.hardware.grippers import TCP_SITE, GripperModel

CAM = GEMINI_335L.name
STEPS_PER_TICK = 5  # 10 ms of simulation per tick at the 2 ms timestep
SPAWN_X_M = -1.05
OUT_OF_VIEW_X_M = 1.3
PERCEIVE_EVERY_S = 0.3
# The jaw gripper's pads (assets/jaw_gripper.xml): 120 mm long along the tool x axis, prefixed g_ in the cell.
PAD_GEOMS = ("g_finger_left_pad", "g_finger_right_pad")
PAD_HALF_LENGTH_M = 0.060
# A leg is perceived once its outline centre is inside this stretch under the camera.
PERCEIVE_BAND_X_M = (-0.65, -0.25)


def _stamp(t_s: float) -> Time:
    return Time(sec=int(t_s), nanosec=int((t_s - int(t_s)) * 1e9))


class MujocoBridgeNode(Node):
    """Steps the simulated cell in real time and exposes it through ROS 2 interfaces."""

    def __init__(self) -> None:
        """Build the cell, record the empty belt, place the leg, and start the loop."""
        super().__init__("mujoco_bridge")

        def parameter(name: str, default: object, description: str) -> object:
            return self.declare_parameter(name, default, ParameterDescriptor(description=description)).value

        arm_name = str(parameter("arm", "ur20", "ur20 or sr20ia"))
        self.arm = ARM_SPECS[{"ur20": ArmModel.UR20, "sr20ia": ArmModel.SR20IA}[arm_name]]
        belt_speed = float(parameter("belt_speed_mps", 0.30, "Belt speed, m/s"))
        self.yaw_deg = float(parameter("arrival_yaw_deg", 0.0, "Leg yaw about square, deg"))
        self.leg_y_m = float(parameter("leg_y_m", 0.45, "Leg outline centre across the belt, m"))
        self.real_time = bool(parameter("real_time", True, "Pace the simulation to the wall clock"))
        self.leg = LegConfig()
        config = CellConfig(
            belt_speed_mps=belt_speed,
            leg=self.leg,
            arm=self.arm.model,
            gripper=GripperModel.JAW_GEH6180,
            depth_cameras=(GEMINI_335L,),
            depth_camera_yaw_deg=90.0,
        )
        self.config = config
        self.ready = threading.Event()

        self.lock = threading.Lock()
        self.trajectory: tuple[float, list[float], list[list[float]], list[float]] | None = None
        self.perceived = False
        self.next_perception_s = 0.0
        self.pending_checks: list[tuple[float, str]] = []
        callbacks = ReentrantCallbackGroup()
        self.clock = self.create_publisher(Clock, "/clock", 10)
        self.joints = self.create_publisher(JointState, "joint_states", qos_profile_sensor_data)
        self.perception = self.create_publisher(LegPerception, "leg/perception", QoSProfile(depth=10))
        self.report = self.create_publisher(String, "sim/grasp_report", QoSProfile(depth=10))
        prefix = f"{arm_name}_arm_controller"
        self.trajectory_server = ActionServer(
            self,
            FollowJointTrajectory,
            f"{prefix}/follow_joint_trajectory",
            self.on_trajectory,
            callback_group=callbacks,
        )
        self.gripper_server = ActionServer(
            self, GripperCommand, "gripper_controller/gripper_cmd", self.on_gripper, callback_group=callbacks
        )
        self.stop = threading.Event()
        self.loop = threading.Thread(target=self.run, daemon=True)
        self.loop.start()
        self.get_logger().info(f"simulated cell up: {arm_name}, belt {belt_speed} m/s, leg yaw {self.yaw_deg:+.0f} deg")

    def _build(self) -> None:
        """Build the cell, record the empty belt and place the leg, in the thread that renders.

        MuJoCo's renderers hold an EGL context, which only the thread that created it may use.
        """
        config = self.config
        self.cell = Cell(config, {CAM: CameraSpec(CAM, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)})
        model = self.cell.model
        self.qpos = [
            model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)] for n in self.arm.joint_names
        ]
        self.actuators = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, n) for n in self.arm.actuator_names]
        self.tcp = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, TCP_SITE)
        self.body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
        self.pad_geoms = {mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name): name for name in PAD_GEOMS}
        self.rng = np.random.default_rng(20260915)
        self.edges = EdgeEffects()

        self.cell.reset()
        self.cell.place_product(OUT_OF_VIEW_X_M, 0.5, -math.pi / 2)
        empties = [self._noisy(self.cell.observe(CAM)[1]) for _ in range(10)]
        self.segmenter = LegSegmenter(EmptyBeltReference.from_frames(empties))
        heading = -math.pi / 2 + math.radians(self.yaw_deg)
        self.cell.reset()
        self.cell.place_product(
            SPAWN_X_M - self.leg.outline_centre_m * math.cos(heading),
            self.leg_y_m - self.leg.outline_centre_m * math.sin(heading),
            heading,
            settle_s=0.2,
        )

        self.ready.set()

    def _noisy(self, frame: CameraFrameData) -> CameraFrameData:
        depth = sense_depth(frame.depth_m, GEMINI_335L, self.rng, edges=self.edges)
        return CameraFrameData(frame.stamp_s, frame.rgb, depth, frame.intrinsics, frame.camera)

    def run(self) -> None:
        """Step, command the arm, publish state, perceive and score, until shutdown."""
        self._build()
        tick_s = STEPS_PER_TICK * self.cell.model.opt.timestep
        while not self.stop.is_set():
            started = time.monotonic()
            with self.lock:
                now = self.cell.time_s
                if self.trajectory is not None:
                    self.cell.data.ctrl[self.actuators] = self._trajectory_command(now)
                self.cell.step(STEPS_PER_TICK)
                now = self.cell.time_s
                self._publish_state(now)
                if not self.perceived and now >= self.next_perception_s:
                    self._perceive(now)
                self._run_checks(now)
            if self.real_time:
                time.sleep(max(0.0, tick_s - (time.monotonic() - started)))

    def _trajectory_command(self, now: float) -> np.ndarray:
        start_s, times, positions, first = self.trajectory
        elapsed = now - start_s
        knots = [0.0, *times]
        values = [first, *positions]
        if elapsed >= knots[-1]:
            return np.asarray(values[-1])
        k = int(np.searchsorted(knots, elapsed, side="right")) - 1
        blend = (elapsed - knots[k]) / max(knots[k + 1] - knots[k], 1e-9)
        return np.asarray(values[k]) + blend * (np.asarray(values[k + 1]) - np.asarray(values[k]))

    def _publish_state(self, now: float) -> None:
        self.clock.publish(Clock(clock=_stamp(now)))
        msg = JointState(name=[*self.arm.joints, "belt_x"])
        msg.header.stamp = _stamp(now)
        msg.position = [*(float(self.cell.data.qpos[i]) for i in self.qpos), self.cell.belt_travel_m]
        self.joints.publish(msg)

    def _perceive(self, now: float) -> None:
        self.next_perception_s = now + PERCEIVE_EVERY_S
        truth = self.cell.ground_truth()
        heading = -math.pi / 2 + math.radians(self.yaw_deg)
        centre_x = truth.piece_pose.x_m + self.leg.outline_centre_m * math.cos(heading)
        if not PERCEIVE_BAND_X_M[0] <= centre_x <= PERCEIVE_BAND_X_M[1]:
            return
        observation, frame = self.cell.observe(CAM)
        noisy = self._noisy(frame)
        result = self.segmenter.segment(noisy)
        if not result.accepted:
            self.get_logger().warning(f"segmenter refused the leg: {result.refused}")
            return
        leg = perceive_leg(noisy, result.mask, self.segmenter.reference.plane, observation.belt_travel_m)
        self.perception.publish(leg_perception_to_msg(leg))
        self.perceived = True
        self.get_logger().info(f"leg perceived at t = {now:.2f} s, segmenter {result.elapsed_ms:.0f} ms")

    def _true_shank_point(self) -> np.ndarray:
        position = self.cell.data.xpos[self.body]
        rotation = self.cell.data.xmat[self.body].reshape(3, 3)
        return np.asarray(position + rotation @ leg_centreline(self.leg, np.array([SHANK_FRACTION]))[0])

    def _widest_under_pads_m(self) -> float:
        """Widest leg section between the jaw pads, which are 120 mm long along the leg, at the tool's position now."""
        position = self.cell.data.xpos[self.body]
        axis = self.cell.data.xmat[self.body].reshape(3, 3)[:, 0]
        along_m = float((self.cell.data.site_xpos[self.tcp] - position) @ axis)
        centre = ORIGIN_FRACTION + along_m / self.leg.length_m
        span = PAD_HALF_LENGTH_M / self.leg.length_m
        fractions = np.clip(np.linspace(centre - span, centre + span, 101), 0.0, 1.0)
        return float(2 * leg_half_width_m(self.leg, fractions).max())

    def _pads_touching_leg(self) -> list[str]:
        """Names of the jaw pads in contact with any part of the leg right now."""
        leg_geoms = set(int(g) for g in product_geom_ids(self.cell.model))
        touching = set()
        for contact in self.cell.data.contact[: self.cell.data.ncon]:
            for pad, other in ((contact.geom1, contact.geom2), (contact.geom2, contact.geom1)):
                if pad in self.pad_geoms and other in leg_geoms:
                    touching.add(self.pad_geoms[pad])
        return sorted(touching)

    def _run_checks(self, now: float) -> None:
        due = [check for check in self.pending_checks if check[0] <= now]
        self.pending_checks = [check for check in self.pending_checks if check[0] > now]
        for _, kind in due:
            if kind == "meet":
                miss = self.cell.data.site_xpos[self.tcp] - self._true_shank_point()
                commanded = np.asarray(self.cell.data.ctrl[self.actuators])
                actual = np.asarray([self.cell.data.qpos[i] for i in self.qpos])
                report = {
                    "joint_tracking_error": [round(float(v), 4) for v in actual - commanded],
                    "tcp_mm": [round(1000 * float(v), 1) for v in self.cell.data.site_xpos[self.tcp]],
                    "true_shank_point_mm": [round(1000 * float(v), 1) for v in self._true_shank_point()],
                    "event": "meet",
                    "t_s": now,
                    "miss_mm": 1000 * float(np.linalg.norm(miss)),
                    "miss_xyz_mm": [round(1000 * float(v), 1) for v in miss],
                }
            else:
                width = 2 * float(leg_half_width_m(self.leg, np.array([SHANK_FRACTION]))[0])
                report = {
                    "event": "closed",
                    "t_s": round(now, 3),
                    "opening_mm": round(1000 * self.cell.gripper_opening_m, 1),
                    "shank_width_mm": round(1000 * width, 1),
                    "widest_under_pads_mm": round(1000 * self._widest_under_pads_m(), 1),
                    "pads_touching_leg": self._pads_touching_leg(),
                }
            self.report.publish(String(data=json.dumps(report)))
            self.get_logger().info(f"grasp report: {report}")

    def on_trajectory(self, goal_handle) -> FollowJointTrajectory.Result:  # noqa: ANN001 - rclpy goal handle
        """Follow a joint trajectory on simulation time; succeed once its last point is due."""
        self.ready.wait()
        trajectory = goal_handle.request.trajectory
        order = [trajectory.joint_names.index(name) for name in self.arm.joints]
        times = [point.time_from_start.sec + 1e-9 * point.time_from_start.nanosec for point in trajectory.points]
        positions = [[point.positions[i] for i in order] for point in trajectory.points]
        stamp_s = trajectory.header.stamp.sec + 1e-9 * trajectory.header.stamp.nanosec
        with self.lock:
            # A stamped trajectory is timed from its stamp, as ros2_control's controller does; 0 means now.
            start_s = stamp_s if stamp_s > 0.0 else self.cell.time_s
            first = [float(v) for v in self.cell.data.ctrl[self.actuators]]
            self.trajectory = (start_s, times, positions, first)
            if len(times) >= 3:
                self.pending_checks += [(start_s + times[1], "meet")]
                # The opening at three times after closing tells a slow close from a close on something wider.
                self.pending_checks += [(start_s + times[2] + after, "closed") for after in (0.3, 0.6, 1.0)]
        while self.cell.time_s < start_s + times[-1] and not self.stop.is_set():
            time.sleep(0.01)
        goal_handle.succeed()
        return FollowJointTrajectory.Result(error_code=FollowJointTrajectory.Result.SUCCESSFUL)

    def on_gripper(self, goal_handle) -> GripperCommand.Result:  # noqa: ANN001 - rclpy goal handle
        """Open to the requested width, or close when it is zero."""
        self.ready.wait()
        opening = float(goal_handle.request.command.position)
        action = f"open to {1000 * opening:.0f} mm" if opening > 1e-3 else "close"
        self.get_logger().info(f"gripper command at t = {self.cell.time_s:.3f} s: {action}")
        with self.lock:
            if opening > 1e-3:
                self.cell.open_gripper(opening)
            else:
                self.cell.close_gripper()
        goal_handle.succeed()
        return GripperCommand.Result(position=opening)

    def destroy_node(self) -> None:
        """Stop the loop and release the renderers."""
        self.stop.set()
        self.loop.join(timeout=1.0)
        if self.ready.is_set():
            self.cell.sensors.close()
        super().destroy_node()


def main() -> None:
    """Run the bridge with a multithreaded executor so actions do not block each other."""
    rclpy.init()
    node = MujocoBridgeNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass  # Ctrl-C or launch shutdown is a normal stop, not an error to print
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
