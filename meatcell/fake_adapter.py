"""Deterministic fake that satisfies the same ports as the Isaac adapter."""

from __future__ import annotations

import hashlib

from .clock import FixedStepClock
from .contracts import CutterMode, CutterState, SimTime, Transform
from .ports import CameraSample, ContactSample, RobotCommand, RobotState


class FakeSimulatorAdapter:
    def __init__(self, physics_hz: int = 240) -> None:
        self.clock = FixedStepClock(physics_hz)
        self.solution = "a"
        self._products: dict[str, Transform] = {}
        self._joint_names = ("x_axis", "y_axis", "z_axis", "wrist_yaw", "finger_left", "finger_right")
        self._joint_positions = (0.0,) * 6
        self._joint_velocities = (0.0,) * 6
        self._attached: str | None = None
        self._gripper_closed = False
        self._paths: set[str] = set()

    @property
    def simulation_time(self) -> SimTime:
        return self.clock.now

    def step_once(self) -> SimTime:
        return self.clock.step()

    def create_cell(self, solution: str) -> None:
        if solution not in {"a", "b"}:
            raise ValueError("solution must be 'a' or 'b'")
        self.solution = solution
        self._paths = {
            "/World/Conveyor",
            "/World/RobotReference",
            "/World/RobotReference/tool0",
            "/World/RobotReference/GripperReference",
            "/World/Sensors/OverheadCamera",
            "/World/cut_target_frame",
            "/World/CutterFeedStationReference",
            "/World/Guards",
            "/World/RejectBin",
        }
        if solution == "b":
            self._paths.add("/World/BufferReference")

    def save_stage(self, path: str) -> str:
        digest = hashlib.sha256("\n".join(sorted(self._paths)).encode()).hexdigest()
        return digest

    def reload_stage(self, path: str) -> str:
        return self.save_stage(path)

    def prim_paths(self) -> tuple[str, ...]:
        return tuple(sorted(self._paths))

    def create_product(self, product_id: str, pose_world: Transform, mass_kg: float) -> None:
        if mass_kg <= 0.0 or product_id in self._products:
            raise ValueError("Product requires positive mass and unique ID")
        self._products[product_id] = pose_world
        self._paths.add(f"/World/Products/{product_id}")

    def remove_product(self, product_id: str) -> None:
        del self._products[product_id]

    def get_product_pose(self, product_id: str) -> Transform:
        return self._products[product_id]

    def set_product_pose(self, product_id: str, pose_world: Transform) -> None:
        self._products[product_id] = pose_world

    def capture_rgbd(self, camera_id: str, output_directory: str | None = None) -> CameraSample:
        body = f"{camera_id}:{self.simulation_time.nanoseconds}:{sorted(self._products.items())}".encode()
        rgb_hash = hashlib.sha256(b"rgb:" + body).hexdigest()
        depth_hash = hashlib.sha256(b"depth:" + body).hexdigest()
        return CameraSample(camera_id, self.simulation_time, 64, 48, rgb_hash, depth_hash, None, None, 64 * 48, 64 * 48)

    def command_robot(self, command: RobotCommand) -> None:
        if command.joint_names != self._joint_names:
            raise ValueError("Joint order does not match adapter")
        self._joint_velocities = tuple(
            (target - current) * self.clock.physics_hz
            for target, current in zip(command.position_targets, self._joint_positions, strict=True)
        )
        self._joint_positions = command.position_targets

    def read_robot_state(self) -> RobotState:
        return RobotState(
            self.simulation_time,
            self._joint_names,
            self._joint_positions,
            self._joint_velocities,
            (0.0,) * 6,
            Transform.planar(self._joint_positions[0], self._joint_positions[1], self._joint_positions[2], self._joint_positions[3]),
            True,
            0,
        )

    def set_gripper_closed(self, closed: bool) -> None:
        self._gripper_closed = closed

    def read_contacts(self) -> tuple[ContactSample, ...]:
        if self._attached is None:
            return ()
        return (
            ContactSample(self.simulation_time, "finger_left", self._attached, 25.0, 1, True),
            ContactSample(self.simulation_time, "finger_right", self._attached, 25.0, 1, True),
        )

    def attach_grasp(self, product_id: str) -> bool:
        if not self._gripper_closed or product_id not in self._products:
            return False
        self._attached = product_id
        return True

    def release_grasp(self) -> None:
        self._attached = None

    def read_cutter_state(self) -> CutterState:
        return CutterState(self.simulation_time, CutterMode.READY, "cut_target_frame", 0.4, 0.0, "reference-cut", 1)

    def close(self) -> None:
        self._attached = None
