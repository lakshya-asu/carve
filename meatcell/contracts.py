"""Immutable simulator-independent message contracts.

All timestamps use integer nanoseconds on the simulation clock. Metric units are
included in field names. This module deliberately imports no simulator, ROS,
NumPy, or wall-clock package.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import json
import math
from typing import Any, ClassVar, Generic, TypeVar


_CONTRACT_TYPES: dict[str, type[Contract]] = {}
_ENUM_TYPES: dict[str, type[Enum]] = {}


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


def _not_blank(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be blank")


class Contract:
    """Base for lossless tagged JSON serialization."""

    schema_version: ClassVar[int] = 1

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        _CONTRACT_TYPES[cls.__name__] = cls

    def to_dict(self) -> dict[str, Any]:
        encoded = _encode(self)
        assert isinstance(encoded, dict)
        return encoded

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Contract:
        decoded = _decode(value)
        if not isinstance(decoded, cls):
            raise ValueError(f"Expected {cls.__name__}, got {type(decoded).__name__}")
        return decoded

    @classmethod
    def from_json(cls, value: str) -> Contract:
        decoded = json.loads(value)
        if not isinstance(decoded, dict):
            raise ValueError("Contract JSON must contain an object")
        return cls.from_dict(decoded)


class ContractEnum(str, Enum):
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        _ENUM_TYPES[cls.__name__] = cls


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return {"__enum__": type(value).__name__, "value": value.value}
    if is_dataclass(value):
        result = {"__type__": type(value).__name__, "schema_version": getattr(value, "schema_version", 1)}
        result.update({item.name: _encode(getattr(value, item.name)) for item in fields(value)})
        return result
    if isinstance(value, tuple):
        return {"__tuple__": [_encode(item) for item in value]}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _encode(item) for key, item in value.items()}
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "__enum__" in value:
        enum_type = _ENUM_TYPES.get(value["__enum__"])
        if enum_type is None:
            raise ValueError(f"Unknown contract enum: {value['__enum__']}")
        return enum_type(value["value"])
    if "__tuple__" in value:
        return tuple(_decode(item) for item in value["__tuple__"])
    if "__type__" in value:
        contract_type = _CONTRACT_TYPES.get(value["__type__"])
        if contract_type is None:
            raise ValueError(f"Unknown contract type: {value['__type__']}")
        if value.get("schema_version") != contract_type.schema_version:
            raise ValueError(
                f"Unsupported {contract_type.__name__} schema version: {value.get('schema_version')}"
            )
        kwargs = {
            key: _decode(item)
            for key, item in value.items()
            if key not in {"__type__", "schema_version"}
        }
        return contract_type(**kwargs)
    return {key: _decode(item) for key, item in value.items()}


@dataclass(frozen=True, order=True)
class SimTime(Contract):
    nanoseconds: int

    def __post_init__(self) -> None:
        if not isinstance(self.nanoseconds, int) or isinstance(self.nanoseconds, bool) or self.nanoseconds < 0:
            raise ValueError("SimTime.nanoseconds must be a nonnegative integer")

    @classmethod
    def from_seconds(cls, seconds: float) -> SimTime:
        _finite("seconds", seconds)
        if seconds < 0.0:
            raise ValueError("seconds must be nonnegative")
        return cls(round(seconds * 1_000_000_000))

    @property
    def seconds(self) -> float:
        return self.nanoseconds / 1_000_000_000

    def plus_seconds(self, seconds: float) -> SimTime:
        return SimTime(self.nanoseconds + SimTime.from_seconds(seconds).nanoseconds)


@dataclass(frozen=True)
class Vector3(Contract):
    x_m: float
    y_m: float
    z_m: float

    def __post_init__(self) -> None:
        for name in ("x_m", "y_m", "z_m"):
            _finite(f"Vector3.{name}", getattr(self, name))


@dataclass(frozen=True)
class Quaternion(Contract):
    w: float
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        values = (self.w, self.x, self.y, self.z)
        for name, value in zip(("w", "x", "y", "z"), values, strict=True):
            _finite(f"Quaternion.{name}", value)
        norm = math.sqrt(sum(value * value for value in values))
        if norm <= 1e-12:
            raise ValueError("Quaternion norm must be greater than zero")
        object.__setattr__(self, "w", self.w / norm)
        object.__setattr__(self, "x", self.x / norm)
        object.__setattr__(self, "y", self.y / norm)
        object.__setattr__(self, "z", self.z / norm)

    @classmethod
    def identity(cls) -> Quaternion:
        return cls(1.0, 0.0, 0.0, 0.0)

    @classmethod
    def from_yaw_rad(cls, yaw_rad: float) -> Quaternion:
        _finite("yaw_rad", yaw_rad)
        return cls(math.cos(yaw_rad / 2.0), 0.0, 0.0, math.sin(yaw_rad / 2.0))

    @property
    def yaw_rad(self) -> float:
        return math.atan2(
            2.0 * (self.w * self.z + self.x * self.y),
            1.0 - 2.0 * (self.y * self.y + self.z * self.z),
        )


@dataclass(frozen=True)
class Transform(Contract):
    translation: Vector3
    rotation: Quaternion

    @classmethod
    def identity(cls) -> Transform:
        return cls(Vector3(0.0, 0.0, 0.0), Quaternion.identity())

    @classmethod
    def planar(cls, x_m: float, y_m: float, z_m: float, yaw_rad: float) -> Transform:
        return cls(Vector3(x_m, y_m, z_m), Quaternion.from_yaw_rad(yaw_rad))

    @property
    def yaw_rad(self) -> float:
        return self.rotation.yaw_rad


@dataclass(frozen=True)
class Twist(Contract):
    linear_mps: Vector3
    angular_radps: Vector3


T = TypeVar("T")


@dataclass(frozen=True)
class Stamped(Contract, Generic[T]):
    timestamp: SimTime
    frame_id: str
    value: T

    def __post_init__(self) -> None:
        _not_blank("Stamped.frame_id", self.frame_id)


@dataclass(frozen=True)
class BoundingBox(Contract):
    x_min_px: float
    y_min_px: float
    x_max_px: float
    y_max_px: float

    def __post_init__(self) -> None:
        for name in ("x_min_px", "y_min_px", "x_max_px", "y_max_px"):
            value = getattr(self, name)
            _finite(f"BoundingBox.{name}", value)
            if value < 0.0:
                raise ValueError(f"BoundingBox.{name} must be nonnegative")
        if self.x_max_px <= self.x_min_px or self.y_max_px <= self.y_min_px:
            raise ValueError("BoundingBox maximum coordinates must exceed minimum coordinates")


class ObservationSource(ContractEnum):
    GROUND_TRUTH = "ground_truth"
    DETECTION = "detection"
    SEGMENTATION = "segmentation"
    REPLAY = "replay"


class TrackLifecycle(ContractEnum):
    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    LOST = "lost"
    EXPIRED = "expired"


class GraspClass(ContractEnum):
    LONGITUDINAL = "longitudinal"
    DIAGONAL_LEFT = "diagonal_left"
    DIAGONAL_RIGHT = "diagonal_right"
    TRANSVERSE = "transverse"


class CutterMode(ContractEnum):
    BLOCKED = "blocked"
    READY = "ready"
    FAULT = "fault"
    EMERGENCY_STOP = "emergency_stop"


class TerminalPath(ContractEnum):
    SUCCESS = "success"
    REJECT = "reject"
    RECOVERED = "recovered"
    SAFE_STOP = "safe_stop"
    PARTIAL = "partial"


@dataclass(frozen=True)
class ObjectObservation(Contract):
    detection_id: str
    exposure_time: SimTime
    delivery_time: SimTime
    class_name: str
    confidence: float
    bbox: BoundingBox
    instance_mask_rle: str | None
    pose_belt: Transform
    position_variance_m2: Vector3
    yaw_variance_rad2: float
    visible_fraction: float
    geometry_quality: float
    source: ObservationSource

    def __post_init__(self) -> None:
        _not_blank("ObjectObservation.detection_id", self.detection_id)
        _not_blank("ObjectObservation.class_name", self.class_name)
        if self.delivery_time < self.exposure_time:
            raise ValueError("ObjectObservation delivery_time cannot precede exposure_time")
        for name in ("confidence", "visible_fraction", "geometry_quality"):
            value = getattr(self, name)
            _finite(f"ObjectObservation.{name}", value)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"ObjectObservation.{name} must be between 0 and 1")
        _finite("ObjectObservation.yaw_variance_rad2", self.yaw_variance_rad2)
        if self.yaw_variance_rad2 < 0.0:
            raise ValueError("ObjectObservation.yaw_variance_rad2 must be nonnegative")


@dataclass(frozen=True)
class ObjectTrack(Contract):
    track_id: str
    lifecycle: TrackLifecycle
    last_exposure_time: SimTime
    state_time: SimTime
    pose_belt: Transform
    twist_belt: Twist
    position_variance_m2: Vector3
    yaw_variance_rad2: float
    hit_count: int
    missed_count: int

    def __post_init__(self) -> None:
        _not_blank("ObjectTrack.track_id", self.track_id)
        if self.state_time < self.last_exposure_time:
            raise ValueError("ObjectTrack state_time cannot precede last exposure")
        if self.hit_count < 1 or self.missed_count < 0:
            raise ValueError("ObjectTrack hit_count must be positive and missed_count nonnegative")


@dataclass(frozen=True)
class GraspCandidate(Contract):
    candidate_id: str
    track_id: str
    grasp_in_product: Transform
    quality: float
    boundary_clearance_m: float
    capture_margin_m: float

    def __post_init__(self) -> None:
        _not_blank("GraspCandidate.candidate_id", self.candidate_id)
        _not_blank("GraspCandidate.track_id", self.track_id)
        _finite("GraspCandidate.quality", self.quality)
        if not 0.0 <= self.quality <= 1.0:
            raise ValueError("GraspCandidate.quality must be between 0 and 1")
        _finite("GraspCandidate.boundary_clearance_m", self.boundary_clearance_m)
        _finite("GraspCandidate.capture_margin_m", self.capture_margin_m)


@dataclass(frozen=True)
class VisionGraspProposal(Contract):
    proposal_id: str
    track_id: str
    classifier_name: str
    grasp_class: GraspClass
    grasp_point_u_px: float
    grasp_point_v_px: float
    grasp_pose_belt: Transform
    grasp_in_product: Transform
    jaw_yaw_rad: float
    approach_vector_belt: Vector3
    estimated_width_m: float
    boundary_clearance_m: float
    capture_margin_m: float
    quality: float
    confidence: float

    def __post_init__(self) -> None:
        for name in ("proposal_id", "track_id", "classifier_name"):
            _not_blank(f"VisionGraspProposal.{name}", getattr(self, name))
        for name in (
            "grasp_point_u_px",
            "grasp_point_v_px",
            "jaw_yaw_rad",
            "estimated_width_m",
            "boundary_clearance_m",
            "capture_margin_m",
            "quality",
            "confidence",
        ):
            _finite(f"VisionGraspProposal.{name}", getattr(self, name))
        if self.grasp_point_u_px < 0.0 or self.grasp_point_v_px < 0.0:
            raise ValueError("VisionGraspProposal image coordinates must be nonnegative")
        if self.estimated_width_m <= 0.0:
            raise ValueError("VisionGraspProposal estimated width must be positive")
        if self.boundary_clearance_m <= 0.0 or self.capture_margin_m <= 0.0:
            raise ValueError("VisionGraspProposal margins must be positive")
        if not 0.0 <= self.quality <= 1.0 or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("VisionGraspProposal quality and confidence must be between 0 and 1")

    def as_candidate(self) -> GraspCandidate:
        return GraspCandidate(
            self.proposal_id,
            self.track_id,
            self.grasp_in_product,
            self.quality,
            self.boundary_clearance_m,
            self.capture_margin_m,
        )


@dataclass(frozen=True)
class InterceptionPlan(Contract):
    plan_id: str
    track_id: str
    source_exposure_time: SimTime
    created_at: SimTime
    intercept_at: SimTime
    commit_at: SimTime
    abort_deadline: SimTime
    valid_until: SimTime
    grasp: GraspCandidate
    interception_pose_world: Transform
    required_tcp_twist_world: Twist
    uncertainty_margin_m: float
    reachability_margin_s: float

    def __post_init__(self) -> None:
        _not_blank("InterceptionPlan.plan_id", self.plan_id)
        _not_blank("InterceptionPlan.track_id", self.track_id)
        if self.grasp.track_id != self.track_id:
            raise ValueError("InterceptionPlan grasp track ID must match plan track ID")
        if not self.source_exposure_time <= self.created_at <= self.commit_at <= self.intercept_at:
            raise ValueError("InterceptionPlan timestamps must follow source, create, commit, intercept order")
        if self.abort_deadline > self.intercept_at:
            raise ValueError("InterceptionPlan abort_deadline cannot exceed intercept time")
        if self.valid_until < self.created_at:
            raise ValueError("InterceptionPlan valid_until cannot precede creation")
        _finite("InterceptionPlan.uncertainty_margin_m", self.uncertainty_margin_m)
        _finite("InterceptionPlan.reachability_margin_s", self.reachability_margin_s)


@dataclass(frozen=True)
class CutterState(Contract):
    timestamp: SimTime
    mode: CutterMode
    target_frame: str
    feed_speed_mps: float
    phase_rad: float
    recipe_id: str
    permissive_sequence: int
    fault_reason: str | None = None

    def __post_init__(self) -> None:
        _not_blank("CutterState.target_frame", self.target_frame)
        _not_blank("CutterState.recipe_id", self.recipe_id)
        _finite("CutterState.feed_speed_mps", self.feed_speed_mps)
        _finite("CutterState.phase_rad", self.phase_rad)
        if self.feed_speed_mps < 0.0 or self.permissive_sequence < 0:
            raise ValueError("CutterState speed and permissive sequence must be nonnegative")


@dataclass(frozen=True)
class CellEvent(Contract):
    timestamp: SimTime
    episode_id: str
    event_type: str
    state: str
    reason: str
    data: tuple[tuple[str, str | int | float | bool | None], ...] = ()

    def __post_init__(self) -> None:
        for name in ("episode_id", "event_type", "state", "reason"):
            _not_blank(f"CellEvent.{name}", getattr(self, name))
        keys = [item[0] for item in self.data]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ValueError("CellEvent.data keys must be unique and sorted")
        for key, value in self.data:
            _not_blank("CellEvent.data key", key)
            if isinstance(value, float):
                _finite(f"CellEvent.data[{key}]", value)


@dataclass(frozen=True)
class CellResult(Contract):
    episode_id: str
    solution: str
    terminal_path: TerminalPath
    terminal_reason: str
    started_at: SimTime
    finished_at: SimTime
    perceived: bool
    tracked: bool
    grasped: bool
    delivered: bool
    slip_detected: bool
    placement_position_error_m: float | None
    placement_angle_error_rad: float | None
    timing_error_s: float | None
    transfer_speed_error_mps: float | None
    collision_count: int
    joint_limit_violation_count: int

    def __post_init__(self) -> None:
        _not_blank("CellResult.episode_id", self.episode_id)
        if self.solution not in {"a", "b"}:
            raise ValueError("CellResult.solution must be 'a' or 'b'")
        _not_blank("CellResult.terminal_reason", self.terminal_reason)
        if self.finished_at < self.started_at:
            raise ValueError("CellResult finished_at cannot precede started_at")
        for name in (
            "placement_position_error_m",
            "placement_angle_error_rad",
            "timing_error_s",
            "transfer_speed_error_mps",
        ):
            value = getattr(self, name)
            if value is not None:
                _finite(f"CellResult.{name}", value)
                if value < 0.0:
                    raise ValueError(f"CellResult.{name} must be nonnegative")
        if self.collision_count < 0 or self.joint_limit_violation_count < 0:
            raise ValueError("CellResult violation counts must be nonnegative")


def contract_from_json(value: str) -> Contract:
    decoded = json.loads(value)
    result = _decode(decoded)
    if not isinstance(result, Contract):
        raise ValueError("JSON does not contain a domain contract")
    return result
