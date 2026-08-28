"""Auditable learned ranking for geometry-safe grasp proposals.

The model in this module only ranks proposals created by the geometric mask
selector. It never creates a target or commands motion.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import ObjectObservation, VisionGraspProposal


MODEL_SCHEMA_VERSION = 1
MODEL_FAMILY = "carve_grasp_affordance_ridge_v1"
FEATURE_NAMES = (
    "local_x_abs_m",
    "local_y_abs_m",
    "boundary_clearance_m",
    "capture_margin_m",
    "estimated_width_m",
    "proposal_quality",
    "proposal_confidence",
    "observation_confidence",
)
OUTCOME_NAMES = (
    "contact_probability",
    "retained_lift_probability",
    "slip_probability",
    "excessive_contact_probability",
    "delivery_probability",
)


def _finite(name: str, value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def candidate_features(
    proposal: VisionGraspProposal,
    observation_confidence: float,
) -> dict[str, float]:
    """Return the fixed feature vector used by training and inference."""
    features = {
        "local_x_abs_m": abs(proposal.grasp_in_product.translation.x_m),
        "local_y_abs_m": abs(proposal.grasp_in_product.translation.y_m),
        "boundary_clearance_m": proposal.boundary_clearance_m,
        "capture_margin_m": proposal.capture_margin_m,
        "estimated_width_m": proposal.estimated_width_m,
        "proposal_quality": proposal.quality,
        "proposal_confidence": proposal.confidence,
        "observation_confidence": observation_confidence,
    }
    return {name: _finite(name, features[name]) for name in FEATURE_NAMES}


@dataclass(frozen=True)
class CandidateAffordanceScore:
    proposal: VisionGraspProposal
    features: Mapping[str, float]
    outcomes: Mapping[str, float]
    score: float
    rank: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal": self.proposal.to_dict(),
            "features": dict(self.features),
            "outcomes": dict(self.outcomes),
            "score": self.score,
            "rank": self.rank,
        }


@dataclass(frozen=True)
class GraspAffordanceDecision:
    selected: VisionGraspProposal
    candidates: tuple[CandidateAffordanceScore, ...]
    model_family: str
    model_sha256: str | None
    mode: str
    fallback_used: bool
    fallback_reason: str | None
    selected_rank: int
    score_margin: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_family": self.model_family,
            "model_sha256": self.model_sha256,
            "mode": self.mode,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "selected_rank": self.selected_rank,
            "score_margin": self.score_margin,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


class GraspAffordanceModel:
    """A fixed-schema multi-outcome ridge model stored as plain JSON."""

    def __init__(self, document: Mapping[str, Any], sha256: str) -> None:
        if int(document.get("schema_version", 0)) != MODEL_SCHEMA_VERSION:
            raise ValueError("Unsupported grasp-affordance model schema")
        if document.get("model_family") != MODEL_FAMILY:
            raise ValueError("Unexpected grasp-affordance model family")
        if tuple(document.get("feature_names", ())) != FEATURE_NAMES:
            raise ValueError("Grasp-affordance feature schema does not match runtime")
        if tuple(document.get("outcome_names", ())) != OUTCOME_NAMES:
            raise ValueError("Grasp-affordance outcome schema does not match runtime")
        normalization = document.get("normalization")
        heads = document.get("heads")
        if not isinstance(normalization, Mapping) or not isinstance(heads, Mapping):
            raise ValueError("Grasp-affordance model is missing normalization or heads")
        means = normalization.get("mean")
        scales = normalization.get("scale")
        if not isinstance(means, list) or not isinstance(scales, list):
            raise ValueError("Grasp-affordance normalization must be arrays")
        if len(means) != len(FEATURE_NAMES) or len(scales) != len(FEATURE_NAMES):
            raise ValueError("Grasp-affordance normalization length is invalid")
        self.means = tuple(_finite("normalization mean", value) for value in means)
        self.scales = tuple(_finite("normalization scale", value) for value in scales)
        if any(value <= 0.0 for value in self.scales):
            raise ValueError("Grasp-affordance normalization scales must be positive")
        parsed_heads: dict[str, tuple[float, tuple[float, ...]]] = {}
        for outcome in OUTCOME_NAMES:
            head = heads.get(outcome)
            if not isinstance(head, Mapping):
                raise ValueError(f"Grasp-affordance model is missing {outcome}")
            weights = head.get("weights")
            if not isinstance(weights, list) or len(weights) != len(FEATURE_NAMES):
                raise ValueError(f"Grasp-affordance head {outcome} has invalid weights")
            parsed_heads[outcome] = (
                _finite(f"{outcome} bias", head.get("bias")),
                tuple(_finite(f"{outcome} weight", value) for value in weights),
            )
        self.heads = parsed_heads
        self.document = dict(document)
        self.sha256 = sha256

    @classmethod
    def load(cls, path: Path) -> "GraspAffordanceModel":
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
        if not isinstance(document, Mapping):
            raise ValueError("Grasp-affordance model root must be an object")
        return cls(document, hashlib.sha256(raw).hexdigest())

    def predict(self, features: Mapping[str, float]) -> dict[str, float]:
        normalized = tuple(
            (_finite(name, features[name]) - mean) / scale
            for name, mean, scale in zip(FEATURE_NAMES, self.means, self.scales, strict=True)
        )
        outputs: dict[str, float] = {}
        for outcome, (bias, weights) in self.heads.items():
            value = bias + sum(weight * feature for weight, feature in zip(weights, normalized, strict=True))
            outputs[outcome] = max(0.0, min(1.0, value))
        return outputs


def composite_affordance_score(outcomes: Mapping[str, float]) -> float:
    return (
        outcomes["contact_probability"]
        * outcomes["retained_lift_probability"]
        * outcomes["delivery_probability"]
        - 0.20 * outcomes["slip_probability"]
        - 0.15 * outcomes["excessive_contact_probability"]
    )


def _fallback(
    proposals: tuple[VisionGraspProposal, ...],
    reason: str,
) -> GraspAffordanceDecision:
    selected = proposals[0]
    return GraspAffordanceDecision(
        selected=selected,
        candidates=(),
        model_family=MODEL_FAMILY,
        model_sha256=None,
        mode="geometric_fallback",
        fallback_used=True,
        fallback_reason=reason,
        selected_rank=0,
        score_margin=0.0,
    )


def rank_grasp_candidates(
    *,
    proposals: Iterable[VisionGraspProposal],
    observation: ObjectObservation,
    model_path: Path,
    minimum_score_margin: float = 0.0,
    allow_fallback: bool = True,
) -> GraspAffordanceDecision:
    """Rank safe proposals, or fail closed to the geometric first proposal."""
    proposal_tuple = tuple(proposals)
    if len(proposal_tuple) < 2:
        raise ValueError("Learned grasp ranking requires at least two safe proposals")
    if minimum_score_margin < 0.0:
        raise ValueError("Minimum score margin must be nonnegative")
    try:
        model = GraspAffordanceModel.load(model_path)
        scored: list[tuple[VisionGraspProposal, dict[str, float], dict[str, float], float]] = []
        for proposal in proposal_tuple:
            features = candidate_features(proposal, observation.confidence)
            outcomes = model.predict(features)
            score = composite_affordance_score(outcomes)
            scored.append((proposal, features, outcomes, score))
        scored.sort(key=lambda item: (-item[3], item[0].proposal_id))
        margin = scored[0][3] - scored[1][3]
        if margin < minimum_score_margin:
            if allow_fallback:
                return _fallback(proposal_tuple, "learned_score_margin_below_threshold")
            raise ValueError("Learned grasp score margin is below the configured threshold")
        ranked = tuple(
            CandidateAffordanceScore(
                proposal=item[0],
                features=item[1],
                outcomes=item[2],
                score=item[3],
                rank=index,
            )
            for index, item in enumerate(scored)
        )
        learned_name = f"{MODEL_FAMILY}@{model.sha256[:12]}"
        selected = replace(ranked[0].proposal, classifier_name=learned_name)
        return GraspAffordanceDecision(
            selected=selected,
            candidates=ranked,
            model_family=MODEL_FAMILY,
            model_sha256=model.sha256,
            mode="learned",
            fallback_used=False,
            fallback_reason=None,
            selected_rank=ranked[0].rank,
            score_margin=margin,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        if not allow_fallback:
            raise
        return _fallback(proposal_tuple, f"{type(exc).__name__}: {exc}")
