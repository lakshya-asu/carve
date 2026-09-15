"""A library of robot skills with contracts, composed into task graphs.

Nothing here knows about MuJoCo, a particular arm, or pork. A skill declares
what it needs, what must be true before it starts, what it produces, how its
success is checked and every way it can fail; a task is a graph from each of
those outcomes to the next skill. Deterministic controllers, learned policies
and perception modules implement the same interface, which is what lets them be
swapped, reused on another platform, and composed into new skills.
"""

from robotics.core.skill_library.contract import (
    NOT_VERIFIED,
    PRECONDITION_FAILED,
    SUCCESS,
    Check,
    CheckResult,
    Contract,
    ContractError,
    FailureMode,
    Port,
    Skill,
    SkillResult,
    run_skill,
)
from robotics.core.skill_library.graph import STEP_LIMIT, TaskGraph, TaskTrace

__all__ = [
    "NOT_VERIFIED",
    "PRECONDITION_FAILED",
    "STEP_LIMIT",
    "SUCCESS",
    "Check",
    "CheckResult",
    "Contract",
    "ContractError",
    "FailureMode",
    "Port",
    "Skill",
    "SkillResult",
    "TaskGraph",
    "TaskTrace",
    "run_skill",
]
