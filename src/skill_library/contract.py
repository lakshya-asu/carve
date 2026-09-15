"""What every skill promises, and the runner that holds it to the promise.

Neil's six fields, as code: inputs, preconditions, outputs, success conditions,
failure conditions, recovery. The first five live on the skill as a `Contract`.
Recovery lives on the task graph (`graph.py`), because what to do after a
failure depends on the task, not on the skill that failed.

The runner enforces the contract rather than trusting it:

* inputs must be present and of the declared type before the skill runs;
* every precondition is evaluated, and a failing one stops the skill before it
  moves anything;
* a skill may only end in success or in a failure mode it declared; anything
  else is a programming error and raises;
* a claimed success is re-checked against the success conditions, and a success
  the checks do not confirm is reported as its own outcome, never as success.

Every check returns the number it measured, and the result carries all of them,
so a failed episode says why in values, not in prose.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)

SUCCESS = "success"
# Outcomes the runner itself can produce, so every skill has them.
PRECONDITION_FAILED = "precondition_failed"
NOT_VERIFIED = "success_not_verified"
RESERVED_OUTCOMES = frozenset({SUCCESS, PRECONDITION_FAILED, NOT_VERIFIED})


class ContractError(Exception):
    """A skill or a task broke the rules of its own contract. A bug, not an outcome."""


@dataclass(frozen=True)
class Port:
    """One named, typed input or output.

    Attributes:
        name: Key the value travels under between skills.
        kind: Python type the value must be an instance of.
        description: What the value means, including its frame and units.
    """

    name: str
    kind: type
    description: str


@dataclass(frozen=True)
class CheckResult:
    """What a check saw.

    Attributes:
        passed: Whether the condition holds.
        value: The number the decision was made on, in the units the check names.
        detail: One line for a log, naming the threshold.
    """

    passed: bool
    value: float
    detail: str = ""


@dataclass(frozen=True)
class Check:
    """A named condition over the world and the skill's arguments.

    Attributes:
        name: Short identifier, used as the key in a result's evidence.
        description: The condition in words, with its threshold and units.
        evaluate: Measures the world and decides.
    """

    name: str
    description: str
    evaluate: Callable[[Any, Mapping[str, Any]], CheckResult]


@dataclass(frozen=True)
class FailureMode:
    """One declared way a skill can end without success.

    Attributes:
        name: Outcome identifier; a task graph routes on it.
        description: What happened in the world when the skill ends this way.
    """

    name: str
    description: str

    def __post_init__(self) -> None:
        if self.name in RESERVED_OUTCOMES:
            raise ContractError(f"{self.name!r} is reserved for the runner")


@dataclass(frozen=True)
class Contract:
    """Everything a skill promises. Fields are Neil's, minus recovery.

    Attributes:
        inputs: Values the skill reads, by name and type.
        preconditions: Conditions that must hold before the skill may start.
        outputs: Values the skill produces on success.
        success: Conditions that must hold for a claimed success to count.
        failures: Every way the skill can end without success.
    """

    inputs: tuple[Port, ...]
    preconditions: tuple[Check, ...]
    outputs: tuple[Port, ...]
    success: tuple[Check, ...]
    failures: tuple[FailureMode, ...]

    def __post_init__(self) -> None:
        names = [failure.name for failure in self.failures]
        if len(names) != len(set(names)):
            raise ContractError(f"failure modes must be unique, got {names}")

    @property
    def outcomes(self) -> frozenset[str]:
        """Every outcome a run of this skill can end in."""
        return RESERVED_OUTCOMES | {failure.name for failure in self.failures}


class Skill(Protocol):
    """A unit of robot behaviour with a contract.

    Implementations may be classical control, a planner, a learned policy or a
    perception module; the runner treats them all alike.

    `world` is typed `Any` on purpose, here and in the runner and the graph: the
    library only passes it through, and each implementation narrows it to the
    world it acts on (a simulated cell, a robot driver). Typing it `object`
    would make every such implementation an invalid protocol member.
    """

    name: str
    contract: Contract

    def execute(self, world: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:  # noqa: ANN401
        """Do the work. Return an outcome, the outputs, and any numbers worth keeping.

        Called only after inputs and preconditions have passed.
        """
        ...


@dataclass(frozen=True)
class SkillResult:
    """How one run of a skill ended.

    Attributes:
        skill: Skill name.
        outcome: `SUCCESS`, a declared failure mode, `PRECONDITION_FAILED` or
            `NOT_VERIFIED`.
        outputs: The skill's outputs; empty unless the outcome is success.
        evidence: Every number measured by a check or reported by the skill.
        duration_s: Wall time of the run.
    """

    skill: str
    outcome: str
    outputs: Mapping[str, Any] = field(default_factory=dict)
    evidence: Mapping[str, float] = field(default_factory=dict)
    duration_s: float = 0.0

    @property
    def succeeded(self) -> bool:
        """True only for a success the contract's checks confirmed."""
        return self.outcome == SUCCESS


def _evaluate(checks: tuple[Check, ...], world: Any, args: Mapping[str, Any], evidence: dict[str, float]) -> list[str]:  # noqa: ANN401
    failed = []
    for check in checks:
        result = check.evaluate(world, args)
        evidence[check.name] = result.value
        if not result.passed:
            failed.append(f"{check.name}: {result.detail or check.description}")
    return failed


def run_skill(skill: Skill, world: Any, args: Mapping[str, Any]) -> SkillResult:  # noqa: ANN401
    """Run one skill under its contract.

    Args:
        skill: The skill.
        world: Whatever the skill acts on: a simulated cell or a robot interface.
        args: Values available to the skill, by name. Extra keys are ignored.

    Returns:
        The result, with every measured number in `evidence`.

    Raises:
        ContractError: If an input is missing or mistyped, the skill returns an
            undeclared outcome, or it claims success without its declared outputs.
    """
    contract = skill.contract
    for port in contract.inputs:
        if port.name not in args:
            raise ContractError(f"{skill.name}: missing input {port.name!r}")
        if not isinstance(args[port.name], port.kind):
            raise ContractError(
                f"{skill.name}: input {port.name!r} must be {port.kind.__name__}, got {type(args[port.name]).__name__}"
            )

    started = time.perf_counter()
    evidence: dict[str, float] = {}
    failed = _evaluate(contract.preconditions, world, args, evidence)
    if failed:
        logger.info("%s: precondition failed: %s", skill.name, "; ".join(failed))
        return SkillResult(skill.name, PRECONDITION_FAILED, {}, evidence, time.perf_counter() - started)

    outcome, outputs, reported = skill.execute(world, args)
    evidence.update(reported)
    if outcome not in contract.outcomes or outcome in (PRECONDITION_FAILED, NOT_VERIFIED):
        raise ContractError(f"{skill.name}: returned undeclared outcome {outcome!r}")
    if outcome != SUCCESS:
        logger.info("%s: %s", skill.name, outcome)
        return SkillResult(skill.name, outcome, {}, evidence, time.perf_counter() - started)

    for port in contract.outputs:
        if port.name not in outputs or not isinstance(outputs[port.name], port.kind):
            raise ContractError(f"{skill.name}: claimed success without a valid output {port.name!r}")
    failed = _evaluate(contract.success, world, {**args, **outputs}, evidence)
    if failed:
        logger.info("%s: claimed success not confirmed: %s", skill.name, "; ".join(failed))
        return SkillResult(skill.name, NOT_VERIFIED, {}, evidence, time.perf_counter() - started)
    return SkillResult(skill.name, SUCCESS, dict(outputs), evidence, time.perf_counter() - started)
