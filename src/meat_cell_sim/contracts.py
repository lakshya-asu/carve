"""Typed contracts between the cell's subsystems.

Every quantity that crosses a subsystem boundary carries four things, because
these are what actually get mismatched: the frame it is expressed in, its units,
the simulation time it refers to, and where it came from. A pose with no frame
and no timestamp is not an observation.

The decomposition and the gate for each subsystem are in
`library/topics/meat-cell-architecture.md`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np

# Units appear in field names, never in comments alone: `_m`, `_s`, `_rad`,
# `_mps`. A field without a unit suffix is dimensionless or a count.


class Frame(str, Enum):
    """Coordinate frames in the cell, following REP 103 (x forward, z up).

    A transform is named `T_<to>_<from>` and maps a point in `from` into `to`.
    """

    WORLD = "world"
    BASE = "base"  # robot base, at the top of the pedestal
    CAMERA = "camera"  # overhead camera optical frame
    BELT = "belt"  # rides with the belt surface
    TOOL = "tool"  # gripper TCP
    PIECE = "piece"  # product centroid, long axis along +x


class Outcome(str, Enum):
    """Why an episode ended. Every failure path must map to one of these."""

    PLACED = "placed"
    MISSED_PICK = "missed_pick"
    DROPPED = "dropped"
    PIECE_TORE = "piece_tore"
    PIECE_FOLDED = "piece_folded"
    NO_FEASIBLE_INTERCEPT = "no_feasible_intercept"
    SHIELD_REJECTED = "shield_rejected"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class Pose2D:
    """A planar pose on the belt or in a lane: position and heading.

    The product lies flat, so its pose on the belt is fully described by two
    positions and one angle. Using a planar pose rather than a full SE(3) pose
    keeps the perception contract honest about what an overhead camera can
    actually measure.

    Attributes:
        x_m: Position along the frame's x axis, metres.
        y_m: Position along the frame's y axis, metres.
        yaw_rad: Heading of the piece long axis, radians, in (-pi/2, pi/2].
        frame: The frame these numbers are expressed in.
        stamp_s: Simulation time the pose describes, seconds.
    """

    x_m: float
    y_m: float
    yaw_rad: float
    frame: Frame
    stamp_s: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.x_m) or not math.isfinite(self.y_m):
            raise ValueError(f"pose position must be finite, got ({self.x_m}, {self.y_m})")
        if self.stamp_s < 0:
            raise ValueError(f"stamp must be non-negative, got {self.stamp_s}")

    @property
    def xy_m(self) -> np.ndarray:
        """Position as a 2-vector in metres."""
        return np.array([self.x_m, self.y_m], dtype=float)

    def in_frame(self, frame: Frame) -> Pose2D:
        """Assert this pose is already in `frame`, for use at a seam.

        Raises:
            ValueError: If the pose is in a different frame. This is the guard
                that stops a camera-frame pose being planned against as if it
                were in the base frame.
        """
        if self.frame is not frame:
            raise ValueError(f"expected a pose in {frame.value}, got one in {self.frame.value}")
        return self


def wrap_axis_angle(yaw_rad: float) -> float:
    """Fold a heading into (-pi/2, pi/2].

    A slab has no head or tail: a long axis at +80 degrees and one at -100
    degrees describe the same alignment. Comparing raw angles across that
    boundary reports a 180 degree error where there is none, which would make
    every yaw metric wrong near the wrap.
    """
    folded = (yaw_rad + math.pi / 2) % math.pi - math.pi / 2
    return math.pi / 2 if folded == -math.pi / 2 else folded


def axis_error_rad(measured_rad: float, truth_rad: float) -> float:
    """Smallest angle between two undirected axes, in [0, pi/2]."""
    return abs(wrap_axis_angle(measured_rad - truth_rad))


@dataclass(frozen=True)
class Observation:
    """S2 output: what the cell's sensors reported at one instant.

    Attributes:
        stamp_s: Simulation time of the exposure, not of the function call.
        rgb: Overhead image, (H, W, 3) uint8, or None when not rendered.
        depth_m: Overhead depth in metres, (H, W) float32, or None.
        belt_travel_m: Belt encoder reading as distance travelled, metres.
        belt_speed_mps: Belt speed, metres per second.
        joint_pos_rad: Arm joint positions, (n,) float64, one per arm joint. Radians
            for revolute joints; metres for a SCARA's vertical axis, the one
            prismatic joint any arm in the cell has.
        gripper_width_m: Commanded-to-actual finger opening, metres.
    """

    stamp_s: float
    belt_travel_m: float
    belt_speed_mps: float
    joint_pos_rad: np.ndarray
    gripper_width_m: float
    rgb: np.ndarray | None = None
    depth_m: np.ndarray | None = None

    def __post_init__(self) -> None:
        if self.joint_pos_rad.ndim != 1 or self.joint_pos_rad.size == 0:
            raise ValueError(f"joint_pos_rad must be (n,) with n > 0, got {self.joint_pos_rad.shape}")
        if self.rgb is not None and self.rgb.ndim != 3:
            raise ValueError(f"rgb must be (H, W, 3), got {self.rgb.shape}")
        if self.depth_m is not None and self.depth_m.ndim != 2:
            raise ValueError(f"depth_m must be (H, W), got {self.depth_m.shape}")


@dataclass(frozen=True)
class PieceEstimate:
    """S3 output: where the perception module thinks the piece is.

    Attributes:
        pose: Planar pose of the piece centroid and long axis.
        length_m: Extent along the long axis, metres.
        width_m: Extent along the short axis, metres.
        confidence: In [0, 1]. A technique with no notion of confidence reports 1.
        method: Which technique produced this, for the bake-off record.
    """

    pose: Pose2D
    length_m: float
    width_m: float
    confidence: float
    method: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        if self.length_m <= 0 or self.width_m <= 0:
            raise ValueError(f"extents must be positive, got {self.length_m} by {self.width_m}")
        if self.width_m > self.length_m:
            raise ValueError(f"length {self.length_m} must be the longer extent, width is {self.width_m}")


@dataclass(frozen=True)
class GraspChoice:
    """S6 output: where and how to take hold of the piece.

    Attributes:
        pose: Where the TCP goes, in the base frame. Yaw is the finger axis.
        width_m: Finger opening to close to, metres.
        approach_height_m: Height above the piece to approach from, metres.
        rule: Which selection rule produced this, for the bake-off record.
    """

    pose: Pose2D
    width_m: float
    approach_height_m: float
    rule: str

    def __post_init__(self) -> None:
        self.pose.in_frame(Frame.BASE)
        if self.width_m < 0:
            raise ValueError(f"grasp width must be non-negative, got {self.width_m}")
        if self.approach_height_m <= 0:
            raise ValueError(f"approach height must be positive, got {self.approach_height_m}")


@dataclass(frozen=True)
class PlacementResult:
    """S10 and S12: how one episode ended, in the terms the bound is written in.

    Attributes:
        outcome: Why the episode ended.
        lane_offset_m: Signed distance from lane centreline, metres. None if never placed.
        lane_yaw_rad: Angle between piece long axis and lane axis, radians. None if never placed.
        cycle_time_s: Wall of simulated time from episode start to release.
        seed: The initial-condition index, so the episode replays exactly.
    """

    outcome: Outcome
    cycle_time_s: float
    seed: int
    lane_offset_m: float | None = None
    lane_yaw_rad: float | None = None

    def __post_init__(self) -> None:
        placed = self.outcome is Outcome.PLACED
        if placed and (self.lane_offset_m is None or self.lane_yaw_rad is None):
            raise ValueError("a placed episode must report lane offset and yaw")
        if not placed and self.lane_offset_m is not None:
            raise ValueError(f"{self.outcome.value} episode must not report a placement measurement")

    @property
    def within(self) -> bool:
        """Placed and inside the pre-registered rigid bound of 2 mm and 2 degrees."""
        if self.lane_offset_m is None or self.lane_yaw_rad is None:
            return False
        return abs(self.lane_offset_m) <= 0.002 and abs(self.lane_yaw_rad) <= math.radians(2.0)
