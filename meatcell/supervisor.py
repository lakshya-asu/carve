"""Deterministic cell state transitions and recovery boundary."""

from __future__ import annotations

from enum import Enum

from .contracts import CellEvent, SimTime, TerminalPath


class CellState(str, Enum):
    IDLE = "idle"
    ACQUIRE = "acquire"
    TRACK = "track"
    PLAN = "plan"
    WAIT_COMMIT = "wait_commit"
    INTERCEPT = "intercept"
    VERIFY_GRASP = "verify_grasp"
    TRANSFER_DIRECT = "transfer_direct"
    WAIT_CUTTER_PERMISSIVE = "wait_cutter_permissive"
    ALIGN_DIRECT = "align_direct"
    FEED_DIRECT = "feed_direct"
    TRANSFER_BUFFER = "transfer_buffer"
    RELEASE_BUFFER = "release_buffer"
    SETTLE = "settle"
    REOBSERVE_BUFFER = "reobserve_buffer"
    ALIGN_BUFFER = "align_buffer"
    FEED_BUFFER = "feed_buffer"
    VERIFY_DELIVERY = "verify_delivery"
    RETRACT = "retract"
    REJECT = "reject"
    RECOVER = "recover"
    SAFE_STOP = "safe_stop"


class TransitionError(RuntimeError):
    pass


_FAILURE_INJECTION_TARGETS = {
    "stale_target": CellState.REJECT,
    "invalid_plan": CellState.REJECT,
    "failed_grasp": CellState.RECOVER,
    "controller_timeout": CellState.SAFE_STOP,
}


_ALLOWED: dict[CellState, set[CellState]] = {
    CellState.IDLE: {CellState.ACQUIRE},
    CellState.ACQUIRE: {CellState.TRACK, CellState.REJECT, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.TRACK: {CellState.PLAN, CellState.REJECT, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.PLAN: {CellState.WAIT_COMMIT, CellState.REJECT, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.WAIT_COMMIT: {CellState.INTERCEPT, CellState.REJECT, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.INTERCEPT: {CellState.VERIFY_GRASP, CellState.REJECT, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.VERIFY_GRASP: {
        CellState.TRANSFER_DIRECT,
        CellState.TRANSFER_BUFFER,
        CellState.REJECT,
        CellState.RECOVER,
        CellState.SAFE_STOP,
    },
    CellState.TRANSFER_DIRECT: {CellState.WAIT_CUTTER_PERMISSIVE, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.WAIT_CUTTER_PERMISSIVE: {
        CellState.ALIGN_DIRECT,
        CellState.FEED_BUFFER,
        CellState.REJECT,
        CellState.RECOVER,
        CellState.SAFE_STOP,
    },
    CellState.ALIGN_DIRECT: {CellState.FEED_DIRECT, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.FEED_DIRECT: {CellState.VERIFY_DELIVERY, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.TRANSFER_BUFFER: {CellState.RELEASE_BUFFER, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.RELEASE_BUFFER: {CellState.SETTLE, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.SETTLE: {CellState.REOBSERVE_BUFFER, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.REOBSERVE_BUFFER: {CellState.ALIGN_BUFFER, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.ALIGN_BUFFER: {CellState.WAIT_CUTTER_PERMISSIVE, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.FEED_BUFFER: {CellState.VERIFY_DELIVERY, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.VERIFY_DELIVERY: {CellState.RETRACT, CellState.RECOVER, CellState.SAFE_STOP},
    CellState.RETRACT: {CellState.RECOVER, CellState.IDLE, CellState.SAFE_STOP},
    CellState.REJECT: {CellState.RECOVER, CellState.IDLE, CellState.SAFE_STOP},
    CellState.RECOVER: {CellState.IDLE, CellState.SAFE_STOP},
    CellState.SAFE_STOP: {CellState.IDLE},
}


class CellSupervisor:
    def __init__(self) -> None:
        self.state = CellState.IDLE
        self.episode_id: str | None = None
        self.events: list[CellEvent] = []
        self.terminal_path = TerminalPath.PARTIAL
        self._last_timestamp = SimTime(0)

    @property
    def known_safe(self) -> bool:
        return self.state in {CellState.IDLE, CellState.SAFE_STOP}

    def start_episode(self, episode_id: str, timestamp: SimTime) -> CellEvent:
        if self.state is not CellState.IDLE:
            raise TransitionError(f"New episode requires IDLE, current state is {self.state.value}")
        if not episode_id.strip():
            raise ValueError("episode_id must not be blank")
        self.episode_id = episode_id
        self.terminal_path = TerminalPath.PARTIAL
        return self.transition(CellState.ACQUIRE, timestamp, "episode_started")

    def transition(
        self,
        target: CellState,
        timestamp: SimTime,
        reason: str,
        data: dict[str, str | int | float | bool | None] | None = None,
    ) -> CellEvent:
        if target not in _ALLOWED[self.state]:
            raise TransitionError(f"Illegal transition {self.state.value} -> {target.value}")
        if self.episode_id is None:
            raise TransitionError("Cannot transition without an active episode")
        if timestamp < self._last_timestamp:
            raise TransitionError("Transition timestamps must not move backward")
        if not reason.strip():
            raise ValueError("Transition reason must not be blank")
        source = self.state
        self.state = target
        self._last_timestamp = timestamp
        event = CellEvent(
            timestamp=timestamp,
            episode_id=self.episode_id,
            event_type="state_transition",
            state=target.value,
            reason=reason,
            data=tuple(sorted({"from": source.value, **(data or {})}.items())),
        )
        self.events.append(event)
        if target is CellState.REJECT:
            self.terminal_path = TerminalPath.REJECT
        elif target is CellState.RECOVER:
            self.terminal_path = TerminalPath.RECOVERED
        elif target is CellState.SAFE_STOP:
            self.terminal_path = TerminalPath.SAFE_STOP
        return event

    def reject(self, timestamp: SimTime, reason: str) -> CellEvent:
        return self.transition(CellState.REJECT, timestamp, reason)

    def recover(self, timestamp: SimTime, reason: str) -> CellEvent:
        return self.transition(CellState.RECOVER, timestamp, reason)

    def safe_stop(self, timestamp: SimTime, reason: str) -> CellEvent:
        return self.transition(CellState.SAFE_STOP, timestamp, reason)

    def inject_failure(self, failure: str, timestamp: SimTime) -> CellEvent:
        try:
            target = _FAILURE_INJECTION_TARGETS[failure]
        except KeyError as exc:
            raise ValueError(f"Unknown failure injection: {failure}") from exc
        return self.transition(target, timestamp, f"injected_{failure}")

    def return_to_idle(self, timestamp: SimTime, reason: str = "known_safe_confirmed") -> CellEvent:
        if self.state not in {CellState.REJECT, CellState.RECOVER, CellState.RETRACT, CellState.SAFE_STOP}:
            raise TransitionError(f"Cannot return to IDLE from {self.state.value}")
        completed = self.state is CellState.RETRACT
        event = self.transition(CellState.IDLE, timestamp, reason)
        if completed:
            self.terminal_path = TerminalPath.SUCCESS
        self.episode_id = None
        return event
