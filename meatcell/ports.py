"""Simulator ports. Implementations may use Isaac Sim or a deterministic fake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .contracts import Contract, CutterState, SimTime, Transform


@dataclass(frozen=True)
class CameraSample(Contract):
    camera_id: str
    exposure_time: SimTime
    width_px: int
    height_px: int
    rgb_sha256: str
    depth_sha256: str
    rgb_path: str | None
    depth_path: str | None
    valid_rgb_pixels: int
    valid_depth_pixels: int


@dataclass(frozen=True)
class RobotCommand(Contract):
    timestamp: SimTime
    joint_names: tuple[str, ...]
    position_targets: tuple[float, ...]
    velocity_limits: tuple[float, ...]
    acceleration_limits: tuple[float, ...]

    def __post_init__(self) -> None:
        lengths = {
            len(self.joint_names),
            len(self.position_targets),
            len(self.velocity_limits),
            len(self.acceleration_limits),
        }
        if len(lengths) != 1 or not self.joint_names:
            raise ValueError("Robot command arrays must be nonempty and equal length")


@dataclass(frozen=True)
class RobotState(Contract):
    timestamp: SimTime
    joint_names: tuple[str, ...]
    positions: tuple[float, ...]
    velocities: tuple[float, ...]
    efforts: tuple[float, ...]
    tcp_pose_world: Transform
    controller_ok: bool
    joint_limit_violation_count: int


@dataclass(frozen=True)
class ContactSample(Contract):
    timestamp: SimTime
    body_a: str
    body_b: str
    force_n: float
    contact_count: int
    intentional: bool


@runtime_checkable
class PhysicsPort(Protocol):
    @property
    def simulation_time(self) -> SimTime: ...

    def step_once(self) -> SimTime: ...


@runtime_checkable
class StagePort(Protocol):
    def create_cell(self, solution: str) -> None: ...

    def save_stage(self, path: str) -> str: ...

    def reload_stage(self, path: str) -> str: ...

    def prim_paths(self) -> tuple[str, ...]: ...


@runtime_checkable
class ProductPort(Protocol):
    def create_product(self, product_id: str, pose_world: Transform, mass_kg: float) -> None: ...

    def remove_product(self, product_id: str) -> None: ...

    def get_product_pose(self, product_id: str) -> Transform: ...

    def set_product_pose(self, product_id: str, pose_world: Transform) -> None: ...


@runtime_checkable
class CameraPort(Protocol):
    def capture_rgbd(self, camera_id: str, output_directory: str | None = None) -> CameraSample: ...


@runtime_checkable
class RobotPort(Protocol):
    def command_robot(self, command: RobotCommand) -> None: ...

    def read_robot_state(self) -> RobotState: ...

    def set_gripper_closed(self, closed: bool) -> None: ...


@runtime_checkable
class ContactPort(Protocol):
    def read_contacts(self) -> tuple[ContactSample, ...]: ...

    def attach_grasp(self, product_id: str) -> bool: ...

    def release_grasp(self) -> None: ...


@runtime_checkable
class CutterPort(Protocol):
    def read_cutter_state(self) -> CutterState: ...


@runtime_checkable
class SimulatorAdapter(PhysicsPort, StagePort, ProductPort, CameraPort, RobotPort, ContactPort, CutterPort, Protocol):
    def close(self) -> None: ...
