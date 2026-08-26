import pytest

from meatcell.contracts import SimTime, TerminalPath
from meatcell.supervisor import CellState, CellSupervisor, TransitionError


def advance_to(supervisor: CellSupervisor, state: CellState, time_ms: int) -> None:
    supervisor.transition(state, SimTime(time_ms * 1_000_000), f"to_{state.value}")


def test_shared_nominal_path_records_every_timestamp_and_reason() -> None:
    supervisor = CellSupervisor()
    supervisor.start_episode("episode-1", SimTime(0))
    for index, state in enumerate(
        (CellState.TRACK, CellState.PLAN, CellState.WAIT_COMMIT, CellState.INTERCEPT, CellState.VERIFY_GRASP),
        start=1,
    ):
        advance_to(supervisor, state, index)
    assert supervisor.state is CellState.VERIFY_GRASP
    assert len(supervisor.events) == 6
    assert all(event.reason and event.timestamp.nanoseconds >= 0 for event in supervisor.events)
    assert [event.timestamp.nanoseconds for event in supervisor.events] == sorted(
        event.timestamp.nanoseconds for event in supervisor.events
    )


def test_illegal_transitions_fail_loudly() -> None:
    supervisor = CellSupervisor()
    supervisor.start_episode("episode", SimTime(0))
    with pytest.raises(TransitionError, match="acquire -> intercept"):
        supervisor.transition(CellState.INTERCEPT, SimTime(1), "skip")
    with pytest.raises(TransitionError, match="requires IDLE"):
        supervisor.start_episode("second", SimTime(1))


@pytest.mark.parametrize(
    ("failure", "start_state", "expected_state", "terminal"),
    [
        ("stale_target", CellState.TRACK, CellState.REJECT, TerminalPath.REJECT),
        ("invalid_plan", CellState.PLAN, CellState.REJECT, TerminalPath.REJECT),
        ("failed_grasp", CellState.VERIFY_GRASP, CellState.RECOVER, TerminalPath.RECOVERED),
        ("controller_timeout", CellState.INTERCEPT, CellState.SAFE_STOP, TerminalPath.SAFE_STOP),
    ],
)
def test_failure_injection_paths(failure, start_state, expected_state, terminal) -> None:
    supervisor = CellSupervisor()
    supervisor.start_episode("episode", SimTime(0))
    path = {
        CellState.TRACK: [CellState.TRACK],
        CellState.PLAN: [CellState.TRACK, CellState.PLAN],
        CellState.INTERCEPT: [CellState.TRACK, CellState.PLAN, CellState.WAIT_COMMIT, CellState.INTERCEPT],
        CellState.VERIFY_GRASP: [CellState.TRACK, CellState.PLAN, CellState.WAIT_COMMIT, CellState.INTERCEPT, CellState.VERIFY_GRASP],
    }[start_state]
    for index, state in enumerate(path, start=1):
        advance_to(supervisor, state, index)
    supervisor.inject_failure(failure, SimTime(10_000_000))
    assert supervisor.state is expected_state
    assert supervisor.terminal_path is terminal


def test_new_episode_only_begins_after_known_safe_recovery() -> None:
    supervisor = CellSupervisor()
    supervisor.start_episode("first", SimTime(0))
    supervisor.reject(SimTime(1), "no_target")
    supervisor.recover(SimTime(2), "retract_to_home")
    supervisor.return_to_idle(SimTime(3))
    assert supervisor.known_safe
    supervisor.start_episode("second", SimTime(4))
    assert supervisor.episode_id == "second"
