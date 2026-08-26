"""Integer-step simulation clock and stable event scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from fractions import Fraction
import heapq
from typing import Any

from .contracts import SimTime


class EventPriority(IntEnum):
    """Stable order for events sharing a timestamp."""

    EMERGENCY_STOP = 0
    CUTTER = 10
    ENCODER = 20
    CAMERA_EXPOSURE = 30
    PERCEPTION_DELIVERY = 40
    CONTROLLER = 50
    CUSTOM = 100


@dataclass(frozen=True)
class ScheduledEvent:
    event_id: int
    timestamp: SimTime
    priority: EventPriority
    event_type: str
    payload: Any = None


@dataclass(order=True)
class _QueueEntry:
    timestamp_ns: int
    priority: int
    sequence: int
    event: ScheduledEvent = field(compare=False)


class FixedStepClock:
    """Clock derived from an integer step index without float accumulation."""

    def __init__(self, physics_hz: int = 240) -> None:
        if not isinstance(physics_hz, int) or isinstance(physics_hz, bool) or physics_hz <= 0:
            raise ValueError("physics_hz must be a positive integer")
        self._physics_hz = physics_hz
        self._step_index = 0

    @property
    def physics_hz(self) -> int:
        return self._physics_hz

    @property
    def step_index(self) -> int:
        return self._step_index

    @property
    def exact_seconds(self) -> Fraction:
        return Fraction(self._step_index, self._physics_hz)

    @property
    def now(self) -> SimTime:
        exact_ns = self.exact_seconds * 1_000_000_000
        return SimTime(round(exact_ns))

    @property
    def dt_seconds(self) -> Fraction:
        return Fraction(1, self._physics_hz)

    def step(self, count: int = 1) -> SimTime:
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise ValueError("step count must be a positive integer")
        self._step_index += count
        return self.now

    def reset(self) -> None:
        self._step_index = 0


class EventScheduler:
    def __init__(self) -> None:
        self._queue: list[_QueueEntry] = []
        self._cancelled: set[int] = set()
        self._next_id = 1
        self._next_sequence = 0

    def schedule(
        self,
        event_type: str,
        timestamp: SimTime,
        *,
        priority: EventPriority = EventPriority.CUSTOM,
        payload: Any = None,
    ) -> int:
        if not event_type.strip():
            raise ValueError("event_type must not be blank")
        event_id = self._next_id
        self._next_id += 1
        event = ScheduledEvent(event_id, timestamp, priority, event_type, payload)
        heapq.heappush(
            self._queue,
            _QueueEntry(timestamp.nanoseconds, int(priority), self._next_sequence, event),
        )
        self._next_sequence += 1
        return event_id

    def schedule_periodic(
        self,
        event_type: str,
        *,
        frequency_hz: int,
        count: int,
        phase: SimTime = SimTime(0),
        priority: EventPriority = EventPriority.CUSTOM,
    ) -> tuple[int, ...]:
        if not isinstance(frequency_hz, int) or frequency_hz <= 0:
            raise ValueError("frequency_hz must be a positive integer")
        if not isinstance(count, int) or count < 0:
            raise ValueError("count must be a nonnegative integer")
        ids = []
        for index in range(count):
            offset_ns = round(Fraction(index, frequency_hz) * 1_000_000_000)
            ids.append(
                self.schedule(
                    event_type,
                    SimTime(phase.nanoseconds + offset_ns),
                    priority=priority,
                    payload={"sample_index": index},
                )
            )
        return tuple(ids)

    def schedule_delivery(
        self,
        exposure_event_id: int,
        exposure_time: SimTime,
        latency_s: float,
        payload: Any = None,
    ) -> int:
        if latency_s < 0.0:
            raise ValueError("latency_s must be nonnegative")
        delivery_time = exposure_time.plus_seconds(latency_s)
        body = {"exposure_event_id": exposure_event_id, "exposure_time_ns": exposure_time.nanoseconds, "value": payload}
        return self.schedule(
            "perception_delivery",
            delivery_time,
            priority=EventPriority.PERCEPTION_DELIVERY,
            payload=body,
        )

    def cancel(self, event_id: int) -> bool:
        if event_id <= 0:
            return False
        active = any(entry.event.event_id == event_id for entry in self._queue)
        if active:
            self._cancelled.add(event_id)
        return active

    def pop_due(self, now: SimTime) -> list[ScheduledEvent]:
        result = []
        while self._queue and self._queue[0].timestamp_ns <= now.nanoseconds:
            event = heapq.heappop(self._queue).event
            if event.event_id in self._cancelled:
                self._cancelled.remove(event.event_id)
                continue
            result.append(event)
        return result

    @property
    def pending_count(self) -> int:
        return sum(entry.event.event_id not in self._cancelled for entry in self._queue)

    def reset(self) -> None:
        self._queue.clear()
        self._cancelled.clear()
        self._next_id = 1
        self._next_sequence = 0
