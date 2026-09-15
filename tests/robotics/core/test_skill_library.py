"""The contract runner and the task graph must enforce what the skills declare.

These use toy skills on a dictionary world, because the rules being tested are
about the library, not about any robot: a failing precondition stops a skill
before it acts, a skill cannot end in an outcome it never declared, a claimed
success is re-checked, values flow between skills by name, recovery edges are
followed, and a task with an unrouted outcome cannot be built at all.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import pytest

from robotics.core.skill_library import (
    NOT_VERIFIED,
    PRECONDITION_FAILED,
    STEP_LIMIT,
    SUCCESS,
    Check,
    CheckResult,
    Contract,
    ContractError,
    FailureMode,
    Port,
    TaskGraph,
    run_skill,
)


@dataclass
class ToySkill:
    name: str
    contract: Contract
    behaviour: Callable[[Any, Mapping[str, Any]], tuple[str, dict[str, Any], dict[str, float]]]

    def execute(self, world: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:
        return self.behaviour(world, args)


def _flag_check(name: str, key: str) -> Check:
    return Check(name, f"world[{key!r}] is true", lambda world, _args: CheckResult(bool(world[key]), float(world[key])))


SLIPPED = FailureMode("slipped", "the object left the jaws")


def _contract(**overrides: Any) -> Contract:
    fields: dict[str, Any] = {"inputs": (), "preconditions": (), "outputs": (), "success": (), "failures": ()}
    fields.update(overrides)
    return Contract(**fields)


def test_a_failing_precondition_stops_the_skill_before_it_acts() -> None:
    world = {"gripper_empty": False, "moved": False}

    def move(w: Any, _args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:
        w["moved"] = True
        return SUCCESS, {}, {}

    skill = ToySkill("acquire", _contract(preconditions=(_flag_check("gripper_empty", "gripper_empty"),)), move)
    result = run_skill(skill, world, {})
    assert result.outcome == PRECONDITION_FAILED
    assert world["moved"] is False
    assert result.evidence == {"gripper_empty": 0.0}


def test_an_undeclared_outcome_is_a_bug_not_a_result() -> None:
    skill = ToySkill("acquire", _contract(failures=(SLIPPED,)), lambda _w, _a: ("exploded", {}, {}))
    with pytest.raises(ContractError, match="undeclared outcome"):
        run_skill(skill, {}, {})


def test_a_skill_cannot_claim_a_runner_outcome_itself() -> None:
    skill = ToySkill("acquire", _contract(), lambda _w, _a: (NOT_VERIFIED, {}, {}))
    with pytest.raises(ContractError, match="undeclared outcome"):
        run_skill(skill, {}, {})


def test_a_claimed_success_the_checks_do_not_confirm_is_not_success() -> None:
    world = {"object_in_jaws": False}
    skill = ToySkill(
        "acquire",
        _contract(
            outputs=(Port("grip_width_m", float, "pad separation after closing"),),
            success=(_flag_check("object_in_jaws", "object_in_jaws"),),
        ),
        lambda _w, _a: (SUCCESS, {"grip_width_m": 0.09}, {"close_time_s": 0.4}),
    )
    result = run_skill(skill, world, {})
    assert result.outcome == NOT_VERIFIED
    assert not result.succeeded
    assert result.outputs == {}
    assert result.evidence == {"close_time_s": 0.4, "object_in_jaws": 0.0}


def test_missing_or_mistyped_inputs_are_refused_before_anything_runs() -> None:
    skill = ToySkill(
        "orient",
        _contract(inputs=(Port("target_yaw_rad", float, "leg heading to reach"),)),
        lambda *_: (SUCCESS, {}, {}),
    )
    with pytest.raises(ContractError, match="missing input"):
        run_skill(skill, {}, {})
    with pytest.raises(ContractError, match="must be float"):
        run_skill(skill, {}, {"target_yaw_rad": "north"})


def test_success_without_its_declared_outputs_is_refused() -> None:
    skill = ToySkill(
        "observe", _contract(outputs=(Port("leg_pose", tuple, "x, y, yaw"),)), lambda *_: (SUCCESS, {}, {})
    )
    with pytest.raises(ContractError, match="without a valid output"):
        run_skill(skill, {}, {})


def test_failure_modes_cannot_take_a_reserved_name() -> None:
    with pytest.raises(ContractError, match="reserved"):
        FailureMode(PRECONDITION_FAILED, "clashes with the runner")


def _two_step_task(acquire_outcomes: list[str], edges_override: dict[tuple[str, str], str] | None = None) -> TaskGraph:
    select = ToySkill(
        "select_grasp",
        _contract(outputs=(Port("grasp_point_m", float, "distance along the leg"),)),
        lambda _w, _a: (SUCCESS, {"grasp_point_m": 0.35}, {}),
    )
    remaining = list(acquire_outcomes)

    def acquire(_w: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:
        outcome = remaining.pop(0) if remaining else SUCCESS
        return outcome, {}, {"grasp_point_m": args["grasp_point_m"]}

    grasp = ToySkill(
        "acquire",
        _contract(inputs=(Port("grasp_point_m", float, "where to grip"),), failures=(SLIPPED,)),
        acquire,
    )
    edges = {
        ("select_grasp", SUCCESS): "acquire",
        ("select_grasp", PRECONDITION_FAILED): "abandon",
        ("select_grasp", NOT_VERIFIED): "abandon",
        ("acquire", SUCCESS): "gripped",
        ("acquire", "slipped"): "select_grasp",
        ("acquire", PRECONDITION_FAILED): "abandon",
        ("acquire", NOT_VERIFIED): "select_grasp",
    }
    edges.update(edges_override or {})
    return TaskGraph(
        name="grip_leg",
        start="select_grasp",
        skills={"select_grasp": select, "acquire": grasp},
        edges=edges,
        terminals=frozenset({"gripped", "abandon"}),
        max_steps=6,
    )


def test_outputs_flow_to_the_next_skill_by_name() -> None:
    trace = _two_step_task([]).run({}, {})
    assert trace.terminal == "gripped"
    assert trace.path == ("select_grasp:success", "acquire:success")
    assert trace.results[1].evidence["grasp_point_m"] == 0.35


def test_a_failure_follows_its_recovery_edge() -> None:
    trace = _two_step_task(["slipped"]).run({}, {})
    assert trace.path == ("select_grasp:success", "acquire:slipped", "select_grasp:success", "acquire:success")
    assert trace.terminal == "gripped"


def test_a_task_that_keeps_failing_stops_at_the_step_limit() -> None:
    trace = _two_step_task(["slipped"] * 10).run({}, {})
    assert trace.terminal == STEP_LIMIT
    assert len(trace.results) == 6


def test_a_task_with_an_unrouted_outcome_cannot_be_built() -> None:
    select = ToySkill("select_grasp", _contract(), lambda *_: (SUCCESS, {}, {}))
    grasp = ToySkill("acquire", _contract(failures=(SLIPPED,)), lambda *_: (SUCCESS, {}, {}))
    with pytest.raises(ContractError, match=r"no edge.*acquire:slipped"):
        TaskGraph(
            name="grip_leg",
            start="select_grasp",
            skills={"select_grasp": select, "acquire": grasp},
            edges={
                ("select_grasp", SUCCESS): "acquire",
                ("select_grasp", PRECONDITION_FAILED): "abandon",
                ("select_grasp", NOT_VERIFIED): "abandon",
                ("acquire", SUCCESS): "gripped",
                ("acquire", PRECONDITION_FAILED): "abandon",
                ("acquire", NOT_VERIFIED): "abandon",
            },
            terminals=frozenset({"gripped", "abandon"}),
        )


def test_an_edge_to_nowhere_cannot_be_built() -> None:
    with pytest.raises(ContractError, match="unknown"):
        _two_step_task([], edges_override={("acquire", SUCCESS): "celebrate"})
