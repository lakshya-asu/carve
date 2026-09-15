"""Smoke check of the grasp pipeline nodes with no MoveIt, controller or simulator running.

    rosdev && cd ~/robot-learning-lab/ros2 && source install/setup.bash
    PYTHONPATH=$PYTHONPATH:~/robot-learning-lab/src python3 src/meat_cell_ros/test/smoke_grasp_pipeline.py

Checks what can be checked without them: a published `leg/perception` comes back as a
`grasp/action` from the policy node with the rule's grasp; the SR-20iA executor refuses a tilted
grasp before planning; an executor with no belt state aborts. Exits non-zero on any failure.
"""

from __future__ import annotations

import math
import sys
import time

import numpy as np
import rclpy
from meat_cell_msgs.msg import GraspAction as GraspActionMsg
from meat_cell_msgs.msg import LegPerception as LegPerceptionMsg
from meat_cell_ros.conversions import grasp_action_from_msg, leg_perception_to_msg
from meat_cell_ros.grasp_executor_node import GraspExecutorNode
from meat_cell_ros.grasp_policy_node import GraspPolicyNode
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter

from applications.pork_leg_alignment.grasping.leg_perception import LegPerception
from applications.pork_leg_alignment.grasping.shank_grasp_rule import ShankGraspRule
from robotics.core.grasp_action import GraspAction


def straight_leg() -> LegPerception:
    """A 740 mm leg along world +x, 240 mm wide at the ham tapering to 80 mm, 40 cross sections."""
    stations = np.linspace(0.0, 0.74, 40)
    widths = np.interp(stations, [0.0, 0.3, 0.45, 0.74], [0.24, 0.24, 0.10, 0.06])
    return LegPerception(
        stamp_s=12.5,
        belt_travel_m=3.0,
        belt_surface_z_m=0.90,
        centre_of_gravity_belt_m=np.array([-3.2, 0.45, 0.97]),
        outline_centre_belt_m=np.array([-3.16, 0.45]),
        axis_rad=0.0,
        length_m=0.74,
        volume_m3=0.011,
        stations_m=stations,
        centreline_belt_m=np.column_stack([-3.4 + stations, np.full(40, 0.45)]),
        widths_m=widths,
        top_heights_m=np.interp(stations, [0.0, 0.3, 0.45, 0.74], [0.18, 0.18, 0.09, 0.06]),
        method="smoke test",
    )


def check(condition: bool, what: str) -> bool:
    """Print one result line and pass the condition through."""
    print(("ok   " if condition else "FAIL ") + what)
    return condition


def main() -> int:
    """Run the checks; 0 if all pass."""
    rclpy.init()
    passed = True
    executor = SingleThreadedExecutor()
    policy = GraspPolicyNode()
    probe = Node("smoke_probe")
    received: list[GraspActionMsg] = []
    probe.create_subscription(GraspActionMsg, "grasp/action", received.append, 10)
    publisher = probe.create_publisher(LegPerceptionMsg, "leg/perception", 10)
    executor.add_node(policy)
    executor.add_node(probe)
    leg = straight_leg()
    deadline = time.monotonic() + 5.0
    while not received and time.monotonic() < deadline:
        publisher.publish(leg_perception_to_msg(leg))
        executor.spin_once(timeout_sec=0.1)
    passed &= check(bool(received), "policy node answered a leg/perception with a grasp/action")
    if received:
        got = grasp_action_from_msg(received[0])
        expected = ShankGraspRule().decide(leg)
        passed &= check(
            np.allclose(got.grasp_point_belt_m, expected.grasp_point_belt_m),
            "grasp point matches the rule run directly",
        )
        passed &= check(
            abs(math.remainder(got.finger_axis_rad - math.pi / 2, math.pi)) < 1e-6,
            "jaws close across a leg lying along x",
        )

    tilted = GraspAction(12.5, "smoke", np.array([-2.95, 0.45, 0.95]), math.pi / 2, math.radians(15.0), 0.12, 0.15, 0.6)
    scara = GraspExecutorNode()
    # Configured as the SR-20iA's config/sr20ia.yaml would: parameters are read at construction, so set both.
    scara.set_parameters([Parameter("tool_tilts", value=False), Parameter("arm_id", value="sr20ia")])
    scara.tool_tilts, scara.arm_id = False, "sr20ia"
    outcome, detail, _ = scara.execute(tilted)
    passed &= check(outcome == "tool_cannot_tilt", f"a SCARA executor refuses a 15 degree tilt ({outcome}: {detail})")
    upright = GraspAction(12.5, "smoke", np.array([-2.95, 0.45, 0.95]), math.pi / 2, 0.0, 0.12, 0.15, 0.6)
    outcome, detail, _ = scara.execute(upright)
    passed &= check(
        outcome == "aborted" and "belt state" in detail, f"no belt state aborts before planning ({outcome}: {detail})"
    )

    for node in (policy, probe, scara):
        node.destroy_node()
    rclpy.try_shutdown()
    print("smoke check passed" if passed else "smoke check FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
