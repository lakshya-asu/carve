from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import hashlib
import json
import math
from pathlib import Path
from typing import Any, ClassVar, Mapping, TypeVar

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return value


def _positive(name: str, value: float) -> float:
    value = _finite(name, value)
    if value <= 0.0:
        raise ValueError(f"{name} must be greater than zero, got {value}")
    return value


def _nonnegative(name: str, value: float) -> float:
    value = _finite(name, value)
    if value < 0.0:
        raise ValueError(f"{name} must be zero or greater, got {value}")
    return value


def _probability(name: str, value: float) -> float:
    value = _finite(name, value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1, got {value}")
    return value


class ConfigSection:
    """Typed section with temporary mapping compatibility for the screening model."""

    def __getitem__(self, key: str) -> Any:
        if key not in {item.name for item in fields(self)}:
            raise KeyError(key)
        return getattr(self, key)


@dataclass(frozen=True)
class SimulationConfig(ConfigSection):
    physics_hz: int = 240
    control_hz: int = 240
    camera_hz: int = 60
    encoder_hz: int = 1000
    max_observation_age_s: float = 0.120
    stage_units_m: float = 1.0

    def __post_init__(self) -> None:
        for name in ("physics_hz", "control_hz", "camera_hz", "encoder_hz"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"simulation.{name} must be a positive integer rate, got {value!r}")
        if self.physics_hz % self.control_hz != 0:
            raise ValueError("simulation.control_hz must be an integer divisor of simulation.physics_hz")
        _positive("simulation.max_observation_age_s", self.max_observation_age_s)
        _positive("simulation.stage_units_m", self.stage_units_m)


@dataclass(frozen=True)
class ConveyorConfig(ConfigSection):
    nominal_speed_mps: float
    speed_sigma_fraction: float
    encoder_sigma_fraction: float
    observation_x_m: float
    pick_x_min_m: float
    pick_x_max_m: float
    candidate_step_m: float

    def __post_init__(self) -> None:
        _positive("conveyor.nominal_speed_mps", self.nominal_speed_mps)
        _nonnegative("conveyor.speed_sigma_fraction", self.speed_sigma_fraction)
        _nonnegative("conveyor.encoder_sigma_fraction", self.encoder_sigma_fraction)
        _finite("conveyor.observation_x_m", self.observation_x_m)
        _finite("conveyor.pick_x_min_m", self.pick_x_min_m)
        _finite("conveyor.pick_x_max_m", self.pick_x_max_m)
        _positive("conveyor.candidate_step_m", self.candidate_step_m)
        if self.pick_x_max_m <= self.pick_x_min_m:
            raise ValueError("conveyor pick window requires pick_x_max_m greater than pick_x_min_m")


@dataclass(frozen=True)
class RobotConfig(ConfigSection):
    max_tcp_speed_mps: float
    max_tcp_accel_mps2: float
    home_to_pick_distance_m: float
    grasp_close_s: float
    command_latency_s: float
    timing_reserve_s: float
    transfer_distance_m: float
    transfer_accel_mps2: float

    def __post_init__(self) -> None:
        for name in ("max_tcp_speed_mps", "max_tcp_accel_mps2", "home_to_pick_distance_m", "grasp_close_s", "transfer_distance_m", "transfer_accel_mps2"):
            _positive(f"robot.{name}", getattr(self, name))
        _nonnegative("robot.command_latency_s", self.command_latency_s)
        _nonnegative("robot.timing_reserve_s", self.timing_reserve_s)


@dataclass(frozen=True)
class PerceptionConfig(ConfigSection):
    latency_mean_s: float
    latency_sigma_s: float
    timestamp_sigma_s: float
    position_sigma_m: float
    angle_sigma_deg: float
    detection_probability: float

    def __post_init__(self) -> None:
        for name in ("latency_mean_s", "latency_sigma_s", "timestamp_sigma_s", "position_sigma_m", "angle_sigma_deg"):
            _nonnegative(f"perception.{name}", getattr(self, name))
        _probability("perception.detection_probability", self.detection_probability)


@dataclass(frozen=True)
class GripperConfig(ConfigSection):
    normal_force_n: float
    contact_count: int
    contact_area_m2: float
    friction_mean: float
    friction_sigma: float
    max_pressure_pa: float
    pick_position_tolerance_m: float
    pick_angle_tolerance_deg: float
    slip_position_sigma_m: float
    slip_angle_sigma_deg: float

    def __post_init__(self) -> None:
        for name in ("normal_force_n", "contact_area_m2", "max_pressure_pa", "pick_position_tolerance_m", "pick_angle_tolerance_deg"):
            _positive(f"gripper.{name}", getattr(self, name))
        if not isinstance(self.contact_count, int) or isinstance(self.contact_count, bool) or self.contact_count <= 0:
            raise ValueError("gripper.contact_count must be a positive integer")
        _nonnegative("gripper.friction_mean", self.friction_mean)
        _nonnegative("gripper.friction_sigma", self.friction_sigma)
        _nonnegative("gripper.slip_position_sigma_m", self.slip_position_sigma_m)
        _nonnegative("gripper.slip_angle_sigma_deg", self.slip_angle_sigma_deg)


@dataclass(frozen=True)
class CuttingConfig(ConfigSection):
    position_tolerance_m: float
    angle_tolerance_deg: float
    timing_tolerance_s: float
    speed_tolerance_mps: float
    readiness_probability: float
    direct_position_sigma_m: float
    direct_angle_sigma_deg: float
    direct_timing_sigma_s: float
    direct_speed_sigma_mps: float

    def __post_init__(self) -> None:
        for name in ("position_tolerance_m", "angle_tolerance_deg", "timing_tolerance_s", "speed_tolerance_mps"):
            _positive(f"cutting.{name}", getattr(self, name))
        _probability("cutting.readiness_probability", self.readiness_probability)
        for name in ("direct_position_sigma_m", "direct_angle_sigma_deg", "direct_timing_sigma_s", "direct_speed_sigma_mps"):
            _nonnegative(f"cutting.{name}", getattr(self, name))


@dataclass(frozen=True)
class BufferConfig(ConfigSection):
    centering_position_factor: float
    centering_angle_factor: float
    feed_position_sigma_m: float
    feed_angle_sigma_deg: float
    feed_timing_sigma_s: float
    feed_speed_sigma_mps: float
    capacity: int
    settle_s: float
    feed_s: float
    max_hold_s: float

    def __post_init__(self) -> None:
        for name in ("centering_position_factor", "centering_angle_factor", "feed_position_sigma_m", "feed_angle_sigma_deg", "feed_timing_sigma_s", "feed_speed_sigma_mps", "settle_s", "feed_s", "max_hold_s"):
            _nonnegative(f"buffer.{name}", getattr(self, name))
        if not isinstance(self.capacity, int) or isinstance(self.capacity, bool) or self.capacity < 0:
            raise ValueError("buffer.capacity must be a nonnegative integer")


@dataclass(frozen=True)
class ScenarioConfig(ConfigSection):
    mass_min_kg: float
    mass_max_kg: float
    yaw_rate_sigma_deg_s: float
    calibration_sigma_m: float
    calibration_sigma_deg: float
    actuation_position_sigma_m: float
    actuation_angle_sigma_deg: float

    def __post_init__(self) -> None:
        _positive("scenario.mass_min_kg", self.mass_min_kg)
        _positive("scenario.mass_max_kg", self.mass_max_kg)
        if self.mass_max_kg < self.mass_min_kg:
            raise ValueError("scenario mass window requires mass_max_kg at least mass_min_kg")
        for name in ("yaw_rate_sigma_deg_s", "calibration_sigma_m", "calibration_sigma_deg", "actuation_position_sigma_m", "actuation_angle_sigma_deg"):
            _nonnegative(f"scenario.{name}", getattr(self, name))


@dataclass(frozen=True)
class CellConfig(ConfigSection):
    name: str
    architecture: str
    conveyor: ConveyorConfig
    robot: RobotConfig
    perception: PerceptionConfig
    gripper: GripperConfig
    cutting: CuttingConfig
    buffer: BufferConfig
    scenario: ScenarioConfig
    simulation: SimulationConfig = SimulationConfig()

    _SECTIONS: ClassVar[Mapping[str, type[ConfigSection]]] = {
        "conveyor": ConveyorConfig,
        "robot": RobotConfig,
        "perception": PerceptionConfig,
        "gripper": GripperConfig,
        "cutting": CuttingConfig,
        "buffer": BufferConfig,
        "scenario": ScenarioConfig,
        "simulation": SimulationConfig,
    }

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if self.architecture not in {"direct", "buffered"}:
            raise ValueError("architecture must be 'direct' or 'buffered'")
        if self.architecture == "buffered" and self.buffer.capacity < 1:
            raise ValueError("buffered architecture requires buffer.capacity of at least 1")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


T = TypeVar("T", bound=ConfigSection)


def _build_section(section_name: str, section_type: type[T], raw: Any) -> T:
    if raw is None and section_type is SimulationConfig:
        return section_type()  # type: ignore[call-arg,return-value]
    if not isinstance(raw, dict):
        raise ValueError(f"{section_name} must be a mapping")
    expected = {item.name for item in fields(section_type)}
    unknown = sorted(set(raw) - expected)
    missing = sorted(name for name in expected if name not in raw and fields(section_type)[list(expected).index(name)].default is fields(section_type)[list(expected).index(name)].default_factory)
    if unknown:
        raise ValueError(f"{section_name} contains unknown fields: {', '.join(unknown)}")
    try:
        return section_type(**raw)
    except TypeError as exc:
        raise ValueError(f"Invalid {section_name} configuration: {exc}") from exc


def config_path(solution: str) -> Path:
    names = {
        "a": "solution_a.yaml",
        "direct": "solution_a.yaml",
        "b": "solution_b.yaml",
        "buffered": "solution_b.yaml",
    }
    try:
        return PROJECT_ROOT / "configs" / names[solution.lower()]
    except KeyError as exc:
        raise ValueError(f"Unknown solution: {solution}") from exc


def config_from_dict(data: Mapping[str, Any]) -> CellConfig:
    expected = {"name", "architecture", *CellConfig._SECTIONS}
    unknown = sorted(set(data) - expected)
    if unknown:
        raise ValueError(f"Configuration contains unknown fields: {', '.join(unknown)}")
    missing = sorted({"name", "architecture", "conveyor", "robot", "perception", "gripper", "cutting", "buffer", "scenario"} - set(data))
    if missing:
        raise ValueError(f"Configuration is missing required fields: {', '.join(missing)}")
    sections = {
        name: _build_section(name, section_type, data.get(name))
        for name, section_type in CellConfig._SECTIONS.items()
    }
    return CellConfig(name=str(data["name"]), architecture=str(data["architecture"]), **sections)


def load_config(path: str | Path) -> CellConfig:
    with Path(path).open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"Configuration must be a mapping: {path}")
    return config_from_dict(data)
