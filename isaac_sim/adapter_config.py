"""Prim and frame names shared by Isaac stage adapters."""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class IsaacCellPaths:
    world: str = "/World"
    physics_scene: str = "/World/PhysicsScene"
    conveyor: str = "/World/Conveyor"
    belt_surface: str = "/World/Conveyor/belt_surface"
    products: str = "/World/Products"
    robot: str = "/World/RobotReference"
    robot_base: str = "/World/RobotReference/base"
    tool0: str = "/World/RobotReference/wrist/tool0"
    gripper: str = "/World/RobotReference/wrist/GripperReference"
    finger_left: str = "/World/RobotReference/finger_left"
    finger_right: str = "/World/RobotReference/finger_right"
    sensors: str = "/World/Sensors"
    overhead_camera: str = "/World/Sensors/OverheadCamera"
    wrist_camera: str = "/World/RobotReference/wrist/WristCamera"
    camera_calibration_target: str = "/World/camera_calibration_target"
    cut_target_frame: str = "/World/cut_target_frame"
    cutter_station: str = "/World/CutterFeedStationReference"
    cutter_feed_frame: str = "/World/CutterFeedStationReference/cutter_feed_frame"
    guards: str = "/World/Guards"
    reject_bin: str = "/World/RejectBin"
    buffer: str = "/World/BufferReference"
    plc: str = "/World/PLCReference"

    def __post_init__(self) -> None:
        values = [getattr(self, item.name) for item in fields(self)]
        if any(not value.startswith("/World") for value in values):
            raise ValueError("Every Isaac cell prim must be rooted below /World")
        if len(values) != len(set(values)):
            raise ValueError("Isaac cell prim paths must be unique")

    def required_for_solution(self, solution: str) -> tuple[str, ...]:
        if solution not in {"a", "b"}:
            raise ValueError("solution must be 'a' or 'b'")
        excluded = {self.buffer} if solution == "a" else set()
        return tuple(value for value in (getattr(self, item.name) for item in fields(self)) if value not in excluded)


REQUIRED_FRAME_NAMES = (
    "world",
    "robot_base",
    "conveyor",
    "belt_surface",
    "camera",
    "camera_calibration_target",
    "tool0",
    "cut_target_frame",
    "cutter_feed_frame",
    "reject_frame",
)
