"""Between meat_cell_msgs messages and the numpy-only cell types they carry.

The cell logic lives in `robotics.core` (belt state, intercept) and in
`applications.pork_leg_alignment.grasping` (grasp policies), so the nodes stay thin: convert in,
call the library, convert out. Kept free of rclpy so it is testable without a running ROS graph.
"""

from __future__ import annotations

import math

import numpy as np
from builtin_interfaces.msg import Time
from geometry_msgs.msg import Point, Quaternion
from meat_cell_msgs.msg import BeltState as BeltStateMsg
from meat_cell_msgs.msg import GraspAction as GraspActionMsg
from meat_cell_msgs.msg import LegPerception as LegPerceptionMsg

from applications.pork_leg_alignment.grasping.leg_perception import LegPerception
from robotics.core.belt_state import BeltState
from robotics.core.grasp_action import GraspAction


def seconds(stamp: Time) -> float:
    """A ROS time as float seconds."""
    return float(stamp.sec) + 1e-9 * float(stamp.nanosec)


def stamp(t_s: float) -> Time:
    """Float seconds as a ROS time."""
    whole = math.floor(t_s)
    return Time(sec=int(whole), nanosec=round((t_s - whole) * 1e9) % 1_000_000_000)


def belt_state_from_msg(msg: BeltStateMsg) -> BeltState:
    """BeltState message to the planner's type."""
    return BeltState(seconds(msg.header.stamp), msg.travel_m, msg.speed_mps, msg.acceleration_mps2)


def belt_state_to_msg(state: BeltState) -> BeltStateMsg:
    """The planner's belt state as a message, frame "world"."""
    msg = BeltStateMsg(travel_m=state.travel_m, speed_mps=state.speed_mps, acceleration_mps2=state.acceleration_mps2)
    msg.header.stamp = stamp(state.stamp_s)
    msg.header.frame_id = "world"
    return msg


def leg_perception_from_msg(msg: LegPerceptionMsg) -> LegPerception:
    """LegPerception message to the policy input."""
    return LegPerception(
        stamp_s=seconds(msg.header.stamp),
        belt_travel_m=msg.belt_travel_m,
        belt_surface_z_m=msg.belt_surface_z_m,
        centre_of_gravity_belt_m=np.array([msg.centre_of_gravity.x, msg.centre_of_gravity.y, msg.centre_of_gravity.z]),
        outline_centre_belt_m=np.array([msg.outline_centre.x, msg.outline_centre.y]),
        axis_rad=msg.axis_rad,
        length_m=msg.length_m,
        volume_m3=msg.volume_m3,
        stations_m=np.asarray(msg.stations_m, dtype=float),
        centreline_belt_m=np.array([[p.x, p.y] for p in msg.centreline], dtype=float).reshape(-1, 2),
        widths_m=np.asarray(msg.widths_m, dtype=float),
        top_heights_m=np.asarray(msg.top_heights_m, dtype=float),
        method=msg.method,
    )


def leg_perception_to_msg(leg: LegPerception) -> LegPerceptionMsg:
    """A perceived leg as a message, frame "belt"."""
    msg = LegPerceptionMsg(
        belt_travel_m=leg.belt_travel_m,
        belt_surface_z_m=leg.belt_surface_z_m,
        centre_of_gravity=Point(**dict(zip("xyz", map(float, leg.centre_of_gravity_belt_m), strict=True))),
        outline_centre=Point(x=float(leg.outline_centre_belt_m[0]), y=float(leg.outline_centre_belt_m[1])),
        axis_rad=leg.axis_rad,
        length_m=leg.length_m,
        volume_m3=leg.volume_m3,
        stations_m=[float(v) for v in leg.stations_m],
        centreline=[Point(x=float(x), y=float(y)) for x, y in leg.centreline_belt_m],
        widths_m=[float(v) for v in leg.widths_m],
        top_heights_m=[float(v) for v in leg.top_heights_m],
        method=leg.method,
    )
    msg.header.stamp = stamp(leg.stamp_s)
    msg.header.frame_id = "belt"
    return msg


def grasp_action_to_msg(action: GraspAction, belt_travel_m: float) -> GraspActionMsg:
    """A grasp action as a message, frame "belt", with the encoder travel its belt x is relative to."""
    msg = GraspActionMsg(
        policy=action.policy,
        belt_travel_m=belt_travel_m,
        grasp_point=Point(**dict(zip("xyz", map(float, action.grasp_point_belt_m), strict=True))),
        finger_axis_rad=action.finger_axis_rad,
        tool_tilt_rad=action.tool_tilt_rad,
        opening_m=action.opening_m,
        approach_height_m=action.approach_height_m,
        close_s=action.close_s,
    )
    msg.header.stamp = stamp(action.stamp_s)
    msg.header.frame_id = "belt"
    return msg


def grasp_action_from_msg(msg: GraspActionMsg) -> GraspAction:
    """GraspAction message to the executor's type."""
    return GraspAction(
        stamp_s=seconds(msg.header.stamp),
        policy=msg.policy,
        grasp_point_belt_m=np.array([msg.grasp_point.x, msg.grasp_point.y, msg.grasp_point.z]),
        finger_axis_rad=msg.finger_axis_rad,
        tool_tilt_rad=msg.tool_tilt_rad,
        opening_m=msg.opening_m,
        approach_height_m=msg.approach_height_m,
        close_s=msg.close_s,
    )


def quaternion(rotation: np.ndarray) -> Quaternion:
    """Rotation matrix (3, 3) to a unit quaternion message, by the largest-diagonal method."""
    m = rotation
    trace = m[0, 0] + m[1, 1] + m[2, 2]
    if trace > 0.0:
        s = 0.5 / math.sqrt(trace + 1.0)
        w, x, y, z = 0.25 / s, (m[2, 1] - m[1, 2]) * s, (m[0, 2] - m[2, 0]) * s, (m[1, 0] - m[0, 1]) * s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = 2.0 * math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
        w, x, y, z = (m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[1, 0] + m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = 2.0 * math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
        w, x, y, z = (m[0, 2] - m[2, 0]) / s, (m[1, 0] + m[0, 1]) / s, 0.25 * s, (m[2, 1] + m[1, 2]) / s
    else:
        s = 2.0 * math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
        w, x, y, z = (m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[2, 1] + m[1, 2]) / s, 0.25 * s
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    return Quaternion(w=w / norm, x=x / norm, y=y / norm, z=z / norm)
