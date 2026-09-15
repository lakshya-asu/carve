"""Tasks as graphs of skills, where every outcome has somewhere to go.

A task graph maps (skill, outcome) to the next skill or to a terminal. Values
flow between skills by name: a skill's outputs are added to a shared blackboard,
and the next skill reads its inputs from it.

The graph refuses to be built with an outcome that has no edge. Every skill can
end in success, in each failure mode it declares, and in the two outcomes the
runner produces, and a task that has not decided what happens after each of
those has not designed its recovery. That check is what "recovery designed in,
not added afterwards" means in code.

A graph can also loop (re-grasp after a slip), so a run stops at a step limit
and says so rather than spinning forever.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from skill_library.contract import ContractError, Skill, SkillResult, run_skill

logger = logging.getLogger(__name__)

STEP_LIMIT = "step_limit"


@dataclass(frozen=True)
class TaskTrace:
    """What happened in one run of a task.

    Attributes:
        terminal: The terminal the run ended in, or `STEP_LIMIT`.
        results: Every skill result, in order.
        blackboard: All values at the end of the run.
    """

    terminal: str
    results: tuple[SkillResult, ...]
    blackboard: Mapping[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> tuple[str, ...]:
        """Skill and outcome at each step, for a log line or a test."""
        return tuple(f"{result.skill}:{result.outcome}" for result in self.results)


@dataclass(frozen=True)
class TaskGraph:
    """A task: skills, the edge taken after each of their outcomes, and terminals.

    Attributes:
        name: Task name.
        start: Name of the first skill.
        skills: Every skill in the task, by name.
        edges: (skill name, outcome) to the next skill name or a terminal.
        terminals: Names that end a run, such as "aligned" or "let_pass".
        max_steps: Skill runs allowed before a run stops at `STEP_LIMIT`.
    """

    name: str
    start: str
    skills: Mapping[str, Skill]
    edges: Mapping[tuple[str, str], str]
    terminals: frozenset[str]
    max_steps: int = 50

    def __post_init__(self) -> None:
        if self.start not in self.skills:
            raise ContractError(f"{self.name}: start {self.start!r} is not a skill in the task")
        overlap = self.terminals & set(self.skills)
        if overlap:
            raise ContractError(f"{self.name}: names used as both skill and terminal: {sorted(overlap)}")
        for key, skill in self.skills.items():
            if key != skill.name:
                raise ContractError(f"{self.name}: skill registered as {key!r} is named {skill.name!r}")
        missing = [
            f"{name}:{outcome}"
            for name, skill in self.skills.items()
            for outcome in sorted(skill.contract.outcomes)
            if (name, outcome) not in self.edges
        ]
        if missing:
            raise ContractError(f"{self.name}: outcomes with no edge, so no recovery designed: {missing}")
        for (name, outcome), target in self.edges.items():
            if name not in self.skills:
                raise ContractError(f"{self.name}: edge from unknown skill {name!r}")
            if outcome not in self.skills[name].contract.outcomes:
                raise ContractError(f"{self.name}: edge from {name!r} on undeclared outcome {outcome!r}")
            if target not in self.skills and target not in self.terminals:
                raise ContractError(f"{self.name}: edge {name}:{outcome} goes to unknown {target!r}")

    def run(self, world: Any, blackboard: Mapping[str, Any]) -> TaskTrace:  # noqa: ANN401
        """Run the task from its start skill until a terminal or the step limit."""
        values = dict(blackboard)
        results: list[SkillResult] = []
        current = self.start
        for _ in range(self.max_steps):
            result = run_skill(self.skills[current], world, values)
            results.append(result)
            values.update(result.outputs)
            current = self.edges[(current, result.outcome)]
            if current in self.terminals:
                logger.info("%s ended in %s after %d skills", self.name, current, len(results))
                return TaskTrace(current, tuple(results), values)
        logger.warning("%s stopped at the step limit of %d", self.name, self.max_steps)
        return TaskTrace(STEP_LIMIT, tuple(results), values)
