"""One arm's grasp executor: arm-agnostic grasp action in, timed joint trajectory out.

The only node that knows which robot it drives, and it learns that from parameters alone
(`config/<arm>.yaml`): planning group, tip link, joint names, trajectory controller, whether the
tool can lean, motion limits and pick window. For each `grasp/action` message or `execute_grasp`
goal:

1. refuse a leaning tool on an arm that cannot lean (a SCARA), before anything moves;
2. plan the intercept against the newest `belt/state` (`robotics.core.intercept`);
3. turn it into timed tool waypoints (`robotics.core.grasp_execution`);
4. solve IK for each waypoint with MoveIt's `compute_ik`, seeded from the previous solution;
5. send one FollowJointTrajectory goal timed to the meeting, open the jaws now and close them at the meeting.

QoS: `belt/state` and `grasp/action` reliable keep-last 10; `joint_states` sensor-data. TF: reads
`world` to the tip link; publishes none.
"""

from __future__ import annotations

import time

import numpy as np
import rclpy
from control_msgs.action import FollowJointTrajectory, GripperCommand
from geometry_msgs.msg import PoseStamped
from meat_cell_msgs.action import ExecuteGrasp
from meat_cell_msgs.msg import BeltState as BeltStateMsg
from meat_cell_msgs.msg import GraspAction as GraspActionMsg
from moveit_msgs.msg import MoveItErrorCodes, PositionIKRequest, RobotState
from moveit_msgs.srv import GetPositionIK
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.action import ActionClient, ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile, qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import JointState
from tf2_ros import Buffer, TransformException, TransformListener
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from meat_cell_ros.conversions import belt_state_from_msg, grasp_action_from_msg, quaternion, seconds, stamp
from robotics.core.belt_state import BeltState
from robotics.core.grasp_action import GraspAction
from robotics.core.grasp_execution import ToolWaypoint, grasp_waypoints
from robotics.core.intercept import ArmMotion, InterceptPlan, NoFeasibleInterceptError, PickWindow, plan_intercept

# A belt state older than this is not planned against.
STALE_BELT_S = 0.2
IK_TIMEOUT_S = 0.05


class GraspExecutorNode(Node):
    """Carries out grasp actions on the arm its parameters describe."""

    def __init__(self) -> None:
        """Declare the arm's parameters and wire topics, the IK service and actions."""
        super().__init__("grasp_executor")

        def parameter(name: str, default: object, description: str) -> object:
            return self.declare_parameter(name, default, ParameterDescriptor(description=description)).value

        self.arm_id = str(parameter("arm_id", "ur20", "Which arm this executor drives, for logs and results"))
        self.group = str(parameter("planning_group", "manipulator", "MoveIt planning group"))
        self.tip_link = str(parameter("tip_link", "tool0", "Link whose pose the grasp waypoints set"))
        self.joint_names = [str(n) for n in parameter("joint_names", ["joint_1"], "Arm joints in trajectory order")]
        self.tool_tilts = bool(parameter("tool_tilts", True, "Whether the tool can lean away from vertical"))
        self.motion = ArmMotion(
            max_speed_mps=float(parameter("max_tool_speed_mps", 1.0, "Tool speed the planner may use, m/s")),
            max_acceleration_mps2=float(parameter("max_tool_acceleration_mps2", 2.0, "Tool acceleration, m/s^2")),
            command_latency_s=float(parameter("command_latency_s", 0.05, "Command to motion delay, s")),
        )
        corners = [
            float(v) for v in parameter("pick_window_m", [-0.4, 0.6, 0.15, 0.85], "x_min, x_max, y_min, y_max, m")
        ]
        self.window = PickWindow(*corners)
        self.descend_s = float(parameter("descend_s", 0.4, "Time to come down the approach distance, s"))
        self.auto_execute = bool(parameter("auto_execute", True, "Execute every grasp/action message"))
        trajectory_action = str(
            parameter("trajectory_action", "joint_trajectory_controller/follow_joint_trajectory", "Trajectory action")
        )
        gripper_action = str(parameter("gripper_action", "gripper_controller/gripper_cmd", "GripperCommand action"))

        callbacks = ReentrantCallbackGroup()
        self.belt: BeltState | None = None
        self.joints = JointState()
        self.tf = Buffer()
        self.tf_listener = TransformListener(self.tf, self)
        ik_service = str(parameter("ik_service", "compute_ik", "GetPositionIK service: move_group's, or an arm's own"))
        self.ik = self.create_client(GetPositionIK, ik_service, callback_group=callbacks)
        self.trajectory = ActionClient(self, FollowJointTrajectory, trajectory_action, callback_group=callbacks)
        self.gripper = ActionClient(self, GripperCommand, gripper_action, callback_group=callbacks)
        reliable = QoSProfile(depth=10)
        self.create_subscription(BeltStateMsg, "belt/state", self.on_belt, reliable, callback_group=callbacks)
        self.create_subscription(
            JointState, "joint_states", self.on_joints, qos_profile_sensor_data, callback_group=callbacks
        )
        self.create_subscription(GraspActionMsg, "grasp/action", self.on_grasp, reliable, callback_group=callbacks)
        self.server = ActionServer(self, ExecuteGrasp, "execute_grasp", self.on_goal, callback_group=callbacks)
        self.get_logger().info(
            f"executor for {self.arm_id}: group {self.group}, tip {self.tip_link}, tilt {self.tool_tilts}"
        )

    def on_belt(self, msg: BeltStateMsg) -> None:
        """Keep the newest belt state."""
        self.belt = belt_state_from_msg(msg)

    def on_joints(self, msg: JointState) -> None:
        """Keep the newest joint state, the first IK seed."""
        self.joints = msg

    def on_grasp(self, msg: GraspActionMsg) -> None:
        """Execute a published grasp when auto-execute is on."""
        if self.auto_execute:
            outcome, detail, _ = self.execute(grasp_action_from_msg(msg))
            self.get_logger().info(f"{msg.policy} grasp on {self.arm_id}: {outcome}: {detail}")

    def on_goal(self, goal_handle) -> ExecuteGrasp.Result:  # noqa: ANN001 - rclpy's goal handle is untyped
        """Execute a grasp requested through the action, reporting the planning phase as feedback."""
        goal_handle.publish_feedback(ExecuteGrasp.Feedback(phase="planning"))
        outcome, detail, plan = self.execute(grasp_action_from_msg(goal_handle.request.grasp))
        result = ExecuteGrasp.Result(outcome=outcome, detail=detail)
        if plan is not None:
            result.meet_time = stamp(plan.meet_time_s)
            result.meet_point.x, result.meet_point.y, result.meet_point.z = (float(v) for v in plan.meet_world_m)
        if outcome == "closed":
            goal_handle.succeed()
        else:
            goal_handle.abort()
        return result

    def execute(self, action: GraspAction) -> tuple[str, str, InterceptPlan | None]:
        """Plan, solve and send one grasp; returns the outcome, why, and the plan if one was made."""
        if abs(action.tool_tilt_rad) > 1e-6 and not self.tool_tilts:
            return (
                "tool_cannot_tilt",
                f"{self.arm_id} cannot lean its tool; asked for {action.tool_tilt_rad:.3f} rad",
                None,
            )
        now_s = seconds(self.get_clock().now().to_msg())
        if self.belt is None or now_s - self.belt.stamp_s > STALE_BELT_S:
            return "aborted", "no belt state in the last 0.2 s", None
        try:
            tool = self.tf.lookup_transform("world", self.tip_link, Time()).transform.translation
        except TransformException as error:
            return "aborted", f"no transform from world to {self.tip_link}: {error}", None
        # Belt x in the action is world x minus the encoder's absolute travel, the same travel the
        # belt state reports, so it goes to the planner unchanged.
        try:
            plan = plan_intercept(
                action.grasp_point_belt_m,
                self.belt,
                np.array([tool.x, tool.y, tool.z]),
                now_s,
                self.window,
                self.motion,
                action.close_s,
            )
        except NoFeasibleInterceptError as refusal:
            return "no_feasible_intercept", str(refusal), None
        waypoints = grasp_waypoints(action, plan, self.descend_s)
        positions = self.solve(waypoints)
        if positions is None:
            return "ik_failed", "MoveIt found no joint solution for a grasp waypoint", plan
        if not self.send(waypoints, positions, now_s, action.opening_m):
            return "trajectory_rejected", "the trajectory controller refused or is not running", plan
        return "closed", f"sent; meeting at x = {plan.meet_world_m[0]:.3f} m in {plan.meet_time_s - now_s:.2f} s", plan

    def solve(self, waypoints: list[ToolWaypoint]) -> list[list[float]] | None:
        """Joint positions for each waypoint from `compute_ik`, each seeded from the one before."""
        if not self.ik.wait_for_service(timeout_sec=1.0):
            self.get_logger().error("the IK service is not available; is move_group (or the arm's IK node) running?")
            return None
        # Seed with this arm's joints only: joint_states also carries the belt and gripper, which the
        # arm's MoveIt model does not have.
        known = dict(zip(self.joints.name, self.joints.position, strict=False))
        seed_state = JointState(
            name=list(self.joint_names), position=[float(known.get(n, 0.0)) for n in self.joint_names]
        )
        seed = RobotState(joint_state=seed_state)
        solutions = []
        for waypoint in waypoints:
            pose = PoseStamped()
            pose.header.frame_id = "world"
            pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = (float(v) for v in waypoint.position_m)
            pose.pose.orientation = quaternion(waypoint.rotation)
            request = GetPositionIK.Request()
            request.ik_request = PositionIKRequest(
                group_name=self.group,
                robot_state=seed,
                ik_link_name=self.tip_link,
                pose_stamped=pose,
                avoid_collisions=True,
                timeout=Duration(seconds=IK_TIMEOUT_S).to_msg(),
            )
            response = self.ik.call(request)
            if response.error_code.val != MoveItErrorCodes.SUCCESS:
                self.get_logger().warning(f"IK failed at the {waypoint.phase} waypoint: code {response.error_code.val}")
                return None
            by_name = dict(zip(response.solution.joint_state.name, response.solution.joint_state.position, strict=True))
            solutions.append([by_name[name] for name in self.joint_names])
            seed = response.solution
        return solutions

    def send(self, waypoints: list[ToolWaypoint], positions: list[list[float]], now_s: float, opening_m: float) -> bool:
        """Open the jaws, then send one trajectory stamped with the planning time; close the jaws at the meeting.

        The trajectory's header stamp is the planning time, so a controller that starts it later (after
        the IK calls and transport) still reaches each waypoint at the planned moment, as ros2_control's
        trajectory controller does.
        """
        trajectory = JointTrajectory(joint_names=self.joint_names)
        trajectory.header.stamp = stamp(now_s)
        for waypoint, joints in zip(waypoints, positions, strict=True):
            after = Duration(seconds=max(waypoint.time_s - now_s, 0.0)).to_msg()
            trajectory.points.append(JointTrajectoryPoint(positions=joints, time_from_start=after))
        if not self.trajectory.wait_for_server(timeout_sec=1.0):
            self.get_logger().error("trajectory controller action is not available")
            return False
        if self.gripper.wait_for_server(timeout_sec=0.5):
            opened = GripperCommand.Goal()
            opened.command.position = opening_m
            self.gripper.send_goal_async(opened)
        # send_goal (synchronous) would block until the trajectory finishes; wait only for acceptance.
        accepted = self.trajectory.send_goal_async(FollowJointTrajectory.Goal(trajectory=trajectory))
        deadline = time.monotonic() + 2.0
        while not accepted.done() and time.monotonic() < deadline:
            time.sleep(0.005)
        if not accepted.done() or not accepted.result().accepted:
            return False
        meet_s = next(w.time_s for w in waypoints if w.close_jaws)
        one_shot: list = []

        def close() -> None:
            one_shot[0].cancel()
            self.gripper.send_goal_async(GripperCommand.Goal())

        one_shot.append(self.create_timer(max(meet_s - seconds(self.get_clock().now().to_msg()), 0.001), close))
        return True


def main() -> None:
    """Run the node with a multithreaded executor, so IK calls do not block the subscriptions."""
    rclpy.init()
    node = GraspExecutorNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass  # Ctrl-C or launch shutdown is a normal stop, not an error to print
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
