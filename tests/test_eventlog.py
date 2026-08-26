from pathlib import Path

from meatcell.contracts import (
    BoundingBox,
    CellEvent,
    CellResult,
    ObjectObservation,
    ObservationSource,
    SimTime,
    TerminalPath,
    Transform,
    Vector3,
)
from meatcell.eventlog import JsonlEventReader, JsonlEventWriter, RunMetadata, summarize_cell_results


def metadata() -> RunMetadata:
    return RunMetadata(
        "run-1",
        "a" * 64,
        "nominal",
        1,
        7,
        "a",
        (("PyYAML", "6.0.3"),),
        SimTime(0),
        "Generic robot and product geometry are reference assets, not OEM accurate.",
    )


def observation() -> ObjectObservation:
    return ObjectObservation(
        "det-1",
        SimTime.from_seconds(0.1),
        SimTime.from_seconds(0.13),
        "meat_reference",
        0.9,
        BoundingBox(1.0, 2.0, 20.0, 12.0),
        "mask",
        Transform.planar(0.224, 0.0, 0.04, 0.0),
        Vector3(1e-5, 1e-5, 1e-5),
        1e-4,
        1.0,
        1.0,
        ObservationSource.SEGMENTATION,
    )


def result(path=TerminalPath.SUCCESS, reason="delivered", delivered=True) -> CellResult:
    return CellResult(
        "episode-1",
        "a",
        path,
        reason,
        SimTime(0),
        SimTime.from_seconds(1.0),
        True,
        True,
        True,
        delivered,
        False,
        0.003,
        0.01,
        0.004,
        0.02,
        0,
        0,
    )


def test_json_lines_metadata_observation_and_terminal_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = JsonlEventWriter(path, metadata())
    writer.start()
    writer.append("observation", observation().delivery_time, observation())
    writer.append_event(CellEvent(SimTime.from_seconds(0.2), "episode-1", "state_transition", "track", "confirmed"))
    writer.finish(result())
    reader = JsonlEventReader(path)
    assert reader.metadata == metadata()
    assert reader.observations() == (observation(),)
    assert reader.terminal_result == result()
    assert len(path.read_text(encoding="utf-8").splitlines()) == 4


def test_replay_produces_same_result_without_renderer(tmp_path: Path) -> None:
    path = tmp_path / "replay.jsonl"
    writer = JsonlEventWriter(path, metadata())
    writer.start()
    writer.append("observation", observation().delivery_time, observation())
    writer.finish(result())
    render_calls = 0

    def replay_handler(records):
        nonlocal render_calls
        assert any(record.record_type == "observation" for record in records)
        assert render_calls == 0
        return result()

    assert JsonlEventReader(path).replay(replay_handler) == result()
    assert render_calls == 0


def test_partial_episodes_are_not_successes_and_metrics_have_percentiles() -> None:
    partial = result(TerminalPath.PARTIAL, "interrupted", False)
    failed = result(TerminalPath.REJECT, "stale_target", False)
    summary = summarize_cell_results([result(), failed, partial], perception_latencies_s=[0.01, 0.02, 0.04])
    assert summary["episodes"] == 3
    assert summary["complete_episodes"] == 2
    assert summary["partial_episodes"] == 1
    assert summary["successes"] == 1
    assert summary["success_rate_complete"] == 0.5
    assert summary["failure_counts"] == {"stale_target": 1}
    assert summary["perception_latency_s"]["p50"] == 0.02
    assert summary["perception_latency_s"]["p95"] is not None
