"""Timestamped frame graph and dependency-free rigid transform math."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

from .contracts import Quaternion, SimTime, Transform, Vector3


class FrameGraphError(ValueError):
    pass


class MissingFrameError(FrameGraphError):
    pass


class CyclicFrameError(FrameGraphError):
    pass


class DisconnectedFrameError(FrameGraphError):
    pass


class StaleTransformError(FrameGraphError):
    pass


def quaternion_multiply(left: Quaternion, right: Quaternion) -> Quaternion:
    return Quaternion(
        left.w * right.w - left.x * right.x - left.y * right.y - left.z * right.z,
        left.w * right.x + left.x * right.w + left.y * right.z - left.z * right.y,
        left.w * right.y - left.x * right.z + left.y * right.w + left.z * right.x,
        left.w * right.z + left.x * right.y - left.y * right.x + left.z * right.w,
    )


def quaternion_inverse(value: Quaternion) -> Quaternion:
    return Quaternion(value.w, -value.x, -value.y, -value.z)


def rotate_vector(rotation: Quaternion, vector: Vector3) -> Vector3:
    ux, uy, uz = rotation.x, rotation.y, rotation.z
    vx, vy, vz = vector.x_m, vector.y_m, vector.z_m
    dot_uv = ux * vx + uy * vy + uz * vz
    dot_uu = ux * ux + uy * uy + uz * uz
    cross_x = uy * vz - uz * vy
    cross_y = uz * vx - ux * vz
    cross_z = ux * vy - uy * vx
    scale = rotation.w * rotation.w - dot_uu
    return Vector3(
        2.0 * dot_uv * ux + scale * vx + 2.0 * rotation.w * cross_x,
        2.0 * dot_uv * uy + scale * vy + 2.0 * rotation.w * cross_y,
        2.0 * dot_uv * uz + scale * vz + 2.0 * rotation.w * cross_z,
    )


def compose(parent_from_middle: Transform, middle_from_child: Transform) -> Transform:
    rotated = rotate_vector(parent_from_middle.rotation, middle_from_child.translation)
    return Transform(
        Vector3(
            parent_from_middle.translation.x_m + rotated.x_m,
            parent_from_middle.translation.y_m + rotated.y_m,
            parent_from_middle.translation.z_m + rotated.z_m,
        ),
        quaternion_multiply(parent_from_middle.rotation, middle_from_child.rotation),
    )


def inverse(parent_from_child: Transform) -> Transform:
    rotation = quaternion_inverse(parent_from_child.rotation)
    negated = Vector3(
        -parent_from_child.translation.x_m,
        -parent_from_child.translation.y_m,
        -parent_from_child.translation.z_m,
    )
    return Transform(rotate_vector(rotation, negated), rotation)


@dataclass(frozen=True)
class PlanarPose:
    """Planar view that retains the exact source transform."""

    source: Transform

    @property
    def x_m(self) -> float:
        return self.source.translation.x_m

    @property
    def y_m(self) -> float:
        return self.source.translation.y_m

    @property
    def z_m(self) -> float:
        return self.source.translation.z_m

    @property
    def yaw_rad(self) -> float:
        return self.source.yaw_rad

    def yaw_only_transform(self) -> Transform:
        return Transform.planar(self.x_m, self.y_m, self.z_m, self.yaw_rad)


@dataclass(frozen=True)
class _StampedEdge:
    timestamp: SimTime
    parent_from_child: Transform


class FrameGraph:
    def __init__(self, required_frames: tuple[str, ...] = ()) -> None:
        if len(required_frames) != len(set(required_frames)):
            raise ValueError("required frame names must be unique")
        for frame in required_frames:
            self._validate_name(frame)
        self._required = set(required_frames)
        self._frames = set(required_frames)
        self._parents: dict[str, str] = {}
        self._history: dict[tuple[str, str], list[_StampedEdge]] = {}

    @staticmethod
    def _validate_name(frame: str) -> None:
        if not isinstance(frame, str) or not frame.strip() or any(char.isspace() for char in frame):
            raise ValueError(f"Invalid frame name: {frame!r}")

    def add_frame(self, frame: str) -> None:
        self._validate_name(frame)
        self._frames.add(frame)

    def set_transform(self, parent: str, child: str, parent_from_child: Transform, timestamp: SimTime) -> None:
        self._validate_name(parent)
        self._validate_name(child)
        if parent == child:
            raise CyclicFrameError(f"Frame {parent!r} cannot parent itself")
        existing_parent = self._parents.get(child)
        if existing_parent is not None and existing_parent != parent:
            raise FrameGraphError(f"Frame {child!r} already has parent {existing_parent!r}")
        cursor = parent
        while cursor in self._parents:
            if cursor == child:
                raise CyclicFrameError(f"Adding {parent} -> {child} creates a cycle")
            cursor = self._parents[cursor]
        if cursor == child:
            raise CyclicFrameError(f"Adding {parent} -> {child} creates a cycle")
        self._frames.update((parent, child))
        self._parents[child] = parent
        history = self._history.setdefault((parent, child), [])
        if history and timestamp <= history[-1].timestamp:
            raise FrameGraphError("Transform timestamps must increase for each edge")
        history.append(_StampedEdge(timestamp, parent_from_child))

    def validate_required(self) -> None:
        missing = sorted(self._required - self._frames)
        if missing:
            raise MissingFrameError(f"Missing required frames: {', '.join(missing)}")

    def _edge_at(
        self,
        parent: str,
        child: str,
        at_time: SimTime,
        max_age: SimTime | None,
    ) -> Transform:
        history = self._history[(parent, child)]
        selected = next((entry for entry in reversed(history) if entry.timestamp <= at_time), None)
        if selected is None:
            raise StaleTransformError(f"No transform for {parent} -> {child} at {at_time.seconds:.6f} s")
        if max_age is not None and at_time.nanoseconds - selected.timestamp.nanoseconds > max_age.nanoseconds:
            raise StaleTransformError(
                f"Transform {parent} -> {child} is older than {max_age.seconds:.6f} s"
            )
        return selected.parent_from_child

    def lookup(
        self,
        source: str,
        target: str,
        at_time: SimTime,
        max_age: SimTime | None = None,
    ) -> Transform:
        for frame in (source, target):
            if frame not in self._frames:
                raise MissingFrameError(f"Unknown frame: {frame}")
        if source == target:
            return Transform.identity()

        queue: deque[tuple[str, Transform]] = deque([(source, Transform.identity())])
        visited = {source}
        while queue:
            current, current_from_source = queue.popleft()
            for (parent, child) in self._history:
                if current == child:
                    neighbor = parent
                    neighbor_from_current = self._edge_at(parent, child, at_time, max_age)
                elif current == parent:
                    neighbor = child
                    neighbor_from_current = inverse(self._edge_at(parent, child, at_time, max_age))
                else:
                    continue
                if neighbor in visited:
                    continue
                neighbor_from_source = compose(neighbor_from_current, current_from_source)
                if neighbor == target:
                    return neighbor_from_source
                visited.add(neighbor)
                queue.append((neighbor, neighbor_from_source))
        raise DisconnectedFrameError(f"Frames {source!r} and {target!r} are disconnected")
