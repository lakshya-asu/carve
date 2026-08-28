"""Shared experiment contracts for deterministic and hybrid Scene 2 stacks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = 1
FLOW_IDS = ("a", "b")
STACK_IDS = ("S0", "S1", "S2", "S3", "S4")
RUN_STATUSES = ("planned", "passed", "failed", "blocked", "not_run")


@dataclass(frozen=True)
class StackDefinition:
    stack_id: str
    label: str
    grasp_selector: str
    interception_controller: str
    contact_policy: str
    implemented: bool


STACK_DEFINITIONS: Mapping[str, StackDefinition] = {
    "S0": StackDefinition("S0", "deterministic", "geometric", "predict_once", "deterministic", True),
    "S1": StackDefinition("S1", "learned grasp ranking", "learned", "predict_once", "deterministic", True),
    "S2": StackDefinition("S2", "reactive interception", "geometric", "reactive", "deterministic", True),
    "S3": StackDefinition("S3", "grasp ranking plus reactive interception", "learned", "reactive", "deterministic", True),
    "S4": StackDefinition("S4", "bounded learned contact hybrid", "learned", "reactive", "learned_bounded", False),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def case_id(flow: str, stack_id: str, seed: int, perturbation: str) -> str:
    if flow not in FLOW_IDS:
        raise ValueError(f"Unknown flow {flow!r}")
    if stack_id not in STACK_IDS:
        raise ValueError(f"Unknown stack {stack_id!r}")
    if seed < 0:
        raise ValueError("Seed must be nonnegative")
    if not perturbation:
        raise ValueError("Perturbation must be nonempty")
    return f"{flow.lower()}_{stack_id.lower()}_seed{seed}_{perturbation}"


def make_case(
    *,
    flow: str,
    stack_id: str,
    seed: int,
    perturbation: str,
    belt_speed_mps: float,
    start_y_m: float,
    start_yaw_deg: float,
    recipe_id: str = "pork_boneless_loin",
) -> dict[str, Any]:
    stack = STACK_DEFINITIONS[stack_id]
    status = "planned" if stack.implemented else "not_run"
    return {
        "case_id": case_id(flow, stack_id, seed, perturbation),
        "flow": flow,
        "stack_id": stack_id,
        "seed": seed,
        "scenario": "nominal",
        "recipe_id": recipe_id,
        "belt_speed_mps": float(belt_speed_mps),
        "start_y_m": float(start_y_m),
        "start_yaw_deg": float(start_yaw_deg),
        "interception_perturbation": perturbation,
        "grasp_selector": stack.grasp_selector,
        "interception_controller": stack.interception_controller,
        "contact_policy": stack.contact_policy,
        "required_for_gate": stack.implemented,
        "status": status,
        "result_directory": case_id(flow, stack_id, seed, perturbation),
    }


def build_manifest(
    *,
    experiment_id: str,
    flows: Iterable[str],
    stacks: Iterable[str],
    seed: int,
    perturbation: str,
    belt_speed_mps: float,
    start_y_m: float,
    start_yaw_deg: float,
    model_hashes: Mapping[str, str | None],
) -> dict[str, Any]:
    flow_values = tuple(dict.fromkeys(value.lower() for value in flows))
    stack_values = tuple(dict.fromkeys(value.upper() for value in stacks))
    if not flow_values or not stack_values:
        raise ValueError("At least one flow and stack are required")
    cases = [
        make_case(
            flow=flow,
            stack_id=stack_id,
            seed=seed,
            perturbation=perturbation,
            belt_speed_mps=belt_speed_mps,
            start_y_m=start_y_m,
            start_yaw_deg=start_yaw_deg,
        )
        for flow in flow_values
        for stack_id in stack_values
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "claim_boundary": "Complete Isaac Sim Scene 2 evidence only. No physical or production validation.",
        "reset_policy": "Each case launches a new Isaac process and rebuilds the same seeded stage.",
        "model_hashes": dict(model_hashes),
        "stack_definitions": {key: asdict(value) for key, value in STACK_DEFINITIONS.items()},
        "cases": cases,
    }


def validate_manifest(document: Mapping[str, Any]) -> None:
    if int(document.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError("Unsupported experiment manifest schema")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Experiment manifest must contain cases")
    identifiers: set[str] = set()
    for entry in cases:
        if not isinstance(entry, Mapping):
            raise ValueError("Experiment cases must be objects")
        identifier = str(entry.get("case_id", ""))
        if not identifier or identifier in identifiers:
            raise ValueError("Experiment case IDs must be nonempty and unique")
        identifiers.add(identifier)
        stack_id = str(entry.get("stack_id", ""))
        stack = STACK_DEFINITIONS.get(stack_id)
        if stack is None:
            raise ValueError(f"Unknown stack in manifest: {stack_id!r}")
        if entry.get("flow") not in FLOW_IDS:
            raise ValueError("Experiment flow must be A or B")
        if entry.get("grasp_selector") != stack.grasp_selector:
            raise ValueError(f"{identifier} grasp selector does not match {stack_id}")
        if entry.get("interception_controller") != stack.interception_controller:
            raise ValueError(f"{identifier} interception controller does not match {stack_id}")
        if entry.get("contact_policy") != stack.contact_policy:
            raise ValueError(f"{identifier} contact policy does not match {stack_id}")
        if entry.get("status") not in RUN_STATUSES:
            raise ValueError(f"{identifier} has an invalid status")
        if not stack.implemented and entry.get("status") != "not_run":
            raise ValueError(f"{identifier} cannot run because {stack_id} is not implemented")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
