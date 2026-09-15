"""Check MoveIt's IK for the UR20 against the cell description's forward kinematics.

Run with move_group up (`ros2 launch cell_moveit_config move_group.launch.py arm:=ur20`) and a
`/clock` or `use_sim_time:=false`. Asks `compute_ik` for the tcp at three grasp-like poses over the
belt, then walks `applications.pork_leg_alignment.sim.robot_description`'s chain with the answer and reports how far the
tool lands from the request. Exits non-zero if any request fails or misses by more than 1 mm.
"""

from __future__ import annotations

import math
import sys

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from meat_cell_ros.conversions import quaternion
from moveit_msgs.msg import MoveItErrorCodes, PositionIKRequest, RobotState
from moveit_msgs.srv import GetPositionIK
from rclpy.duration import Duration
from sensor_msgs.msg import JointState

from applications.pork_leg_alignment.sim.robot_description import arm_chain, forward_kinematics
from robotics.core.grasp_action import tool_rotation
from robotics.hardware.arms import UR20_SPEC, ArmModel

TARGETS = [((0.0, 0.45, 1.00), 0.3, 0.0), ((-0.3, 0.55, 1.05), -1.2, 0.0), ((0.2, 0.40, 1.00), 1.5, math.radians(30.0))]


def main() -> int:
    """Request IK for each target and check where the answer puts the tool."""
    rclpy.init()
    node = rclpy.create_node("check_moveit_ik")
    client = node.create_client(GetPositionIK, "compute_ik")
    if not client.wait_for_service(timeout_sec=30.0):
        print("FAIL compute_ik did not appear within 30 s")
        return 1
    chain = arm_chain(ArmModel.UR20)
    seed = JointState(name=list(UR20_SPEC.joints), position=list(UR20_SPEC.home_qpos))
    failures = 0
    for point, finger_axis, tilt in TARGETS:
        rotation = tool_rotation(finger_axis, tilt)
        pose = PoseStamped()
        pose.header.frame_id = "world"
        pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = point
        pose.pose.orientation = quaternion(rotation)
        request = GetPositionIK.Request()
        request.ik_request = PositionIKRequest(
            group_name="ur_manipulator",
            robot_state=RobotState(joint_state=seed),
            ik_link_name="tcp",
            pose_stamped=pose,
            avoid_collisions=False,
            timeout=Duration(seconds=0.5).to_msg(),
        )
        future = client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
        response = future.result()
        if response is None or response.error_code.val != MoveItErrorCodes.SUCCESS:
            code = None if response is None else response.error_code.val
            print(f"FAIL {point} tilt {math.degrees(tilt):.0f} deg: error code {code}")
            failures += 1
            continue
        joints = dict(zip(response.solution.joint_state.name, response.solution.joint_state.position, strict=False))
        fk = forward_kinematics(chain, joints)
        miss_mm = 1000 * float(np.linalg.norm(fk[:3, 3] - np.array(point)))
        turn_deg = math.degrees(math.acos(min(1.0, (np.trace(fk[:3, :3].T @ rotation) - 1) / 2)))
        ok = miss_mm < 1.0 and turn_deg < 0.5
        failures += not ok
        print(
            f"{'ok  ' if ok else 'FAIL'} {point} tilt {math.degrees(tilt):.0f} deg: tool lands {miss_mm:.3f} mm, {turn_deg:.3f} deg off"
        )
    node.destroy_node()
    rclpy.try_shutdown()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
