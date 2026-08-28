"""Shadow-only learned proposals for the bounded contact segment."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any


FEATURE_ORDER = (
    "bias",
    "solution_b",
    "abs_yaw_rad",
    "product_width_m",
    "contact_force_imbalance",
    "slip_flag",
)


@dataclass(frozen=True)
class ContactSkillObservation:
    solution_b: bool
    yaw_rad: float
    product_width_m: float
    contact_force_imbalance: float
    slip_detected: bool
    age_s: float
    supervisor_state: str
    plc_ready: bool
    emergency_stop: bool

    def features(self) -> tuple[float, ...]:
        values = (
            1.0,
            float(self.solution_b),
            abs(self.yaw_rad),
            self.product_width_m,
            self.contact_force_imbalance,
            float(self.slip_detected),
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Contact-skill features must be finite")
        return values


@dataclass(frozen=True)
class ContactSkillProposal:
    phase: str
    value: float
    unit: str
    uncertainty: float
    accepted_by_shadow_gate: bool
    fallback_reason: str | None
    executed: bool = False


class ContactSkillModel:
    def __init__(self, payload: dict[str, Any], source_path: Path) -> None:
        if tuple(payload.get("feature_order", ())) != FEATURE_ORDER:
            raise ValueError("Contact-skill feature order does not match the runtime contract")
        if payload.get("execution_policy") != "shadow_only":
            raise ValueError("Only shadow-only contact-skill models are permitted")
        self.payload = payload
        self.source_path = source_path
        self.sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()

    @classmethod
    def load(cls, path: str | Path) -> "ContactSkillModel":
        source = Path(path).resolve()
        return cls(json.loads(source.read_text(encoding="utf-8-sig")), source)

    def propose(
        self,
        phase: str,
        observation: ContactSkillObservation,
        *,
        maximum_age_s: float = 0.15,
        maximum_uncertainty: float = 0.05,
    ) -> ContactSkillProposal:
        spec = self.payload.get("phases", {}).get(phase)
        if not isinstance(spec, dict):
            raise ValueError(f"Unknown contact-skill phase: {phase}")
        features = observation.features()
        weights = tuple(float(value) for value in spec["weights"])
        if len(weights) != len(features):
            raise ValueError("Contact-skill weight count does not match its feature contract")
        raw = sum(weight * feature for weight, feature in zip(weights, features, strict=True))
        lower = float(spec["minimum"])
        upper = float(spec["maximum"])
        value = max(lower, min(upper, raw))
        uncertainty = float(spec["held_out_mae"])
        allowed_states = set(spec["allowed_states"])
        reason = None
        if observation.emergency_stop:
            reason = "emergency_stop"
        elif not observation.plc_ready:
            reason = "plc_blocked"
        elif observation.age_s < 0.0 or observation.age_s > maximum_age_s:
            reason = "stale"
        elif observation.supervisor_state not in allowed_states:
            reason = "state_blocked"
        elif not math.isfinite(uncertainty) or uncertainty > maximum_uncertainty:
            reason = "uncertain"
        elif not math.isfinite(raw) or not lower <= raw <= upper:
            reason = "outside_action_envelope"
        return ContactSkillProposal(
            phase,
            value,
            str(spec["unit"]),
            uncertainty,
            reason is None,
            reason,
            False,
        )
