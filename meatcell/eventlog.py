"""Versioned JSON Lines event log, observation replay, and cell metrics."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import importlib.metadata
import json
from pathlib import Path
from typing import Callable, Iterable

from .contracts import CellEvent, CellResult, Contract, ObjectObservation, SimTime, TerminalPath, contract_from_json
from .metrics import percentile


LOG_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class RunMetadata(Contract):
    run_id: str
    configuration_sha256: str
    scenario_family: str
    scenario_version: int
    seed: int
    solution: str
    dependency_versions: tuple[tuple[str, str], ...]
    started_at_sim_time: SimTime
    reference_asset_notice: str

    def __post_init__(self) -> None:
        if not self.run_id.strip() or len(self.configuration_sha256) != 64:
            raise ValueError("Run metadata requires a run ID and SHA-256 configuration hash")
        if not self.scenario_family.strip() or self.scenario_version <= 0:
            raise ValueError("Run metadata requires a versioned scenario family")
        if self.solution not in {"a", "b"}:
            raise ValueError("Run metadata solution must be 'a' or 'b'")
        if tuple(sorted(self.dependency_versions)) != self.dependency_versions:
            raise ValueError("Dependency versions must be sorted")
        if not self.reference_asset_notice.strip():
            raise ValueError("Reference asset notice must not be blank")


@dataclass(frozen=True)
class ReplayRecord(Contract):
    timestamp: SimTime
    record_type: str
    payload_json: str

    def __post_init__(self) -> None:
        if not self.record_type.strip():
            raise ValueError("Replay record type must not be blank")
        json.loads(self.payload_json)

    def payload(self) -> Contract:
        return contract_from_json(self.payload_json)


def dependency_versions(names: tuple[str, ...] = ("PyYAML", "numpy", "torch", "isaacsim")) -> tuple[tuple[str, str], ...]:
    result = []
    for name in names:
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            version = "not-installed"
        result.append((name, version))
    return tuple(sorted(result))


class JsonlEventWriter:
    def __init__(self, path: str | Path, metadata: RunMetadata) -> None:
        self.path = Path(path)
        self.metadata = metadata
        self._started = False
        self._finished = False

    def start(self) -> None:
        if self._started:
            raise RuntimeError("Run metadata is immutable and has already been written")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = {
            "schema_version": LOG_SCHEMA_VERSION,
            "record_type": "run_metadata",
            "payload": self.metadata.to_dict(),
        }
        self.path.write_text(json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        self._started = True

    def append(self, record_type: str, timestamp: SimTime, payload: Contract) -> None:
        if not self._started or self._finished:
            raise RuntimeError("Event writer must be active")
        line = {
            "schema_version": LOG_SCHEMA_VERSION,
            "record_type": record_type,
            "timestamp_ns": timestamp.nanoseconds,
            "payload": payload.to_dict(),
        }
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n")

    def append_event(self, event: CellEvent) -> None:
        self.append("cell_event", event.timestamp, event)

    def finish(self, result: CellResult) -> None:
        self.append("terminal_result", result.finished_at, result)
        self._finished = True


class JsonlEventReader:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.metadata: RunMetadata | None = None
        self.records: list[ReplayRecord] = []
        self.terminal_result: CellResult | None = None
        self._read()

    def _read(self) -> None:
        previous_timestamp = -1
        for index, line in enumerate(self.path.read_text(encoding="utf-8").splitlines()):
            body = json.loads(line)
            if body.get("schema_version") != LOG_SCHEMA_VERSION:
                raise ValueError(f"Unsupported log schema on line {index + 1}")
            payload = contract_from_json(json.dumps(body["payload"]))
            if index == 0:
                if body.get("record_type") != "run_metadata" or not isinstance(payload, RunMetadata):
                    raise ValueError("First JSON Lines record must be run_metadata")
                self.metadata = payload
                continue
            timestamp = SimTime(body["timestamp_ns"])
            if timestamp.nanoseconds < previous_timestamp:
                raise ValueError("Replay records must be ordered by simulation timestamp")
            previous_timestamp = timestamp.nanoseconds
            record = ReplayRecord(timestamp, body["record_type"], payload.to_json())
            self.records.append(record)
            if record.record_type == "terminal_result":
                if not isinstance(payload, CellResult):
                    raise ValueError("terminal_result record must contain CellResult")
                self.terminal_result = payload
        if self.metadata is None:
            raise ValueError("Log has no metadata")

    def observations(self) -> tuple[ObjectObservation, ...]:
        result = []
        for record in self.records:
            if record.record_type == "observation":
                payload = record.payload()
                if not isinstance(payload, ObjectObservation):
                    raise ValueError("observation record contains the wrong contract")
                result.append(payload)
        return tuple(result)

    def replay(self, handler: Callable[[tuple[ReplayRecord, ...]], CellResult]) -> CellResult:
        if self.terminal_result is None:
            raise ValueError("Partial log has no terminal result and cannot verify deterministic replay")
        inputs = tuple(record for record in self.records if record.record_type != "terminal_result")
        replayed = handler(inputs)
        if replayed != self.terminal_result:
            raise AssertionError("Deterministic replay result differs from recorded terminal result")
        return replayed


def summarize_cell_results(
    results: Iterable[CellResult],
    *,
    perception_latencies_s: Iterable[float] = (),
) -> dict[str, object]:
    values = list(results)
    latencies = list(perception_latencies_s)
    complete = [item for item in values if item.terminal_path is not TerminalPath.PARTIAL]
    successes = [item for item in complete if item.terminal_path is TerminalPath.SUCCESS and item.delivered]
    partial = [item for item in values if item.terminal_path is TerminalPath.PARTIAL]
    failures = Counter(item.terminal_reason for item in complete if item not in successes)

    def metric(name: str) -> dict[str, float | None]:
        data = [getattr(item, name) for item in complete if getattr(item, name) is not None]
        return {"p50": percentile(data, 0.50), "p95": percentile(data, 0.95)}

    return {
        "schema_version": 1,
        "episodes": len(values),
        "complete_episodes": len(complete),
        "partial_episodes": len(partial),
        "successes": len(successes),
        "success_rate_complete": len(successes) / len(complete) if complete else 0.0,
        "failure_counts": dict(sorted(failures.items())),
        "perception_latency_s": {"p50": percentile(latencies, 0.50), "p95": percentile(latencies, 0.95)},
        "placement_position_error_m": metric("placement_position_error_m"),
        "placement_angle_error_rad": metric("placement_angle_error_rad"),
        "timing_error_s": metric("timing_error_s"),
        "transfer_speed_error_mps": metric("transfer_speed_error_mps"),
        "collision_count": sum(item.collision_count for item in complete),
        "joint_limit_violation_count": sum(item.joint_limit_violation_count for item in complete),
    }
