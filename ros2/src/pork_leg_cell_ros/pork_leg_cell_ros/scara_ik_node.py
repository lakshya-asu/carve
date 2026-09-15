"""Closed-form IK for the SR-20iA, served on MoveIt's GetPositionIK interface.

The grasp executor asks every arm for joint positions the same way, a `GetPositionIK` request for
the `tcp` link in `world`. For the UR20 MoveIt's move_group answers with KDL; a four-joint SCARA
cannot meet KDL's six-number pose goals, so this node answers instead with
`applications.pork_leg_alignment.sim.scara_kinematics.scara_ik`, on `scara/compute_ik` by default. A tilted tool or an
unreachable point comes back as NO_IK_SOLUTION with the reason logged.

Parameters give the arm's mount; the defaults are the cell's (`scene.DEFAULT_MOUNTS`).
"""

from __future__ import annotations

import numpy as np
import rclpy
from moveit_msgs.msg import MoveItErrorCodes
from moveit_msgs.srv import GetPositionIK
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from applications.pork_leg_alignment.sim.scara_kinematics import ScaraUnreachableError, scara_ik
from applications.pork_leg_alignment.sim.scene import DEFAULT_MOUNTS, ArmMount
from robotics.hardware.arms import SR20IA_SPEC, ArmModel


def _rotation(q) -> np.ndarray:  # noqa: ANN001 - geometry_msgs Quaternion
    w, x, y, z = q.w, q.x, q.y, q.z
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


class ScaraIkNode(Node):
    """Answers GetPositionIK for the SR-20iA's tool centre point."""

    def __init__(self) -> None:
        """Declare the mount parameters and start the service."""
        super().__init__("scara_ik")
        default = DEFAULT_MOUNTS[ArmModel.SR20IA]

        def parameter(name: str, value: float, description: str) -> float:
            return float(self.declare_parameter(name, value, ParameterDescriptor(description=description)).value)

        self.mount = ArmMount(
            x_m=parameter("mount_x_m", default.x_m, "Pedestal x, world, m"),
            y_m=parameter("mount_y_m", default.y_m, "Pedestal y, world, m"),
            z_m=parameter("mount_z_m", default.z_m, "Mount height, world, m"),
            yaw_rad=parameter("mount_yaw_rad", default.yaw_rad, "Mount yaw, rad"),
        )
        service = str(self.declare_parameter("service", "scara/compute_ik").value)
        self.create_service(GetPositionIK, service, self.on_request)
        self.get_logger().info(f"SR-20iA closed-form IK on {service}")

    def on_request(self, request: GetPositionIK.Request, response: GetPositionIK.Response) -> GetPositionIK.Response:
        """Solve for the requested tcp pose, seeded from the request's robot state."""
        ik = request.ik_request
        if ik.pose_stamped.header.frame_id not in ("world", ""):
            response.error_code.val = MoveItErrorCodes.FRAME_TRANSFORM_FAILURE
            return response
        by_name = dict(zip(ik.robot_state.joint_state.name, ik.robot_state.joint_state.position, strict=False))
        seed = tuple(float(by_name.get(name, 0.0)) for name in SR20IA_SPEC.joints)
        pose = ik.pose_stamped.pose
        try:
            joints = scara_ik(
                np.array([pose.position.x, pose.position.y, pose.position.z]),
                _rotation(pose.orientation),
                self.mount,
                seed=seed,  # type: ignore[arg-type]
            )
        except ScaraUnreachableError as refusal:
            self.get_logger().warning(f"no SR-20iA solution: {refusal}")
            response.error_code.val = MoveItErrorCodes.NO_IK_SOLUTION
            return response
        response.solution.joint_state.name = list(SR20IA_SPEC.joints)
        response.solution.joint_state.position = [float(v) for v in joints]
        response.error_code.val = MoveItErrorCodes.SUCCESS
        return response


def main() -> None:
    """Run the node until shutdown."""
    rclpy.init()
    node = ScaraIkNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass  # Ctrl-C or launch shutdown is a normal stop, not an error to print
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
