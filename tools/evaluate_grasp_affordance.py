"""Evaluate a Solution C model on complete matched held-out Isaac trials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from meatcell.grasp_affordance import GraspAffordanceModel, composite_affordance_score


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(rows: list[dict[str, Any]], model: GraspAffordanceModel) -> dict[str, Any]:
    held_out = [row for row in rows if row["split"] == "held_out"]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in held_out:
        groups.setdefault(row["trial_group_id"], []).append(row)
    if not groups:
        raise ValueError("No held-out matched candidate groups were found")
    group_results = []
    for group_id, group_rows in sorted(groups.items()):
        if {int(row["candidate_index"]) for row in group_rows} != set(range(5)):
            raise ValueError(f"Held-out group {group_id} is incomplete")
        scored = []
        for row in group_rows:
            predicted_outcomes = model.predict(row["features"])
            predicted_utility = composite_affordance_score(predicted_outcomes)
            actual_utility = composite_affordance_score(row["outcomes"])
            scored.append(
                {
                    "candidate_index": int(row["candidate_index"]),
                    "predicted_outcomes": predicted_outcomes,
                    "predicted_utility": predicted_utility,
                    "actual_utility": actual_utility,
                    "raw_outcomes": row["raw_outcomes"],
                }
            )
        selected = max(scored, key=lambda item: (item["predicted_utility"], -item["candidate_index"]))
        oracle = max(scored, key=lambda item: (item["actual_utility"], -item["candidate_index"]))
        baseline = next(item for item in scored if item["candidate_index"] == 0)
        selected_safety_passed = all(
            int(selected["raw_outcomes"][name]) == 0
            for name in (
                "collision_violations",
                "joint_limit_violations",
                "velocity_limit_violations",
                "acceleration_limit_violations",
            )
        )
        group_results.append(
            {
                "trial_group_id": group_id,
                "selected_candidate_index": selected["candidate_index"],
                "oracle_candidate_index": oracle["candidate_index"],
                "baseline_candidate_index": 0,
                "selected_actual_utility": selected["actual_utility"],
                "oracle_actual_utility": oracle["actual_utility"],
                "baseline_actual_utility": baseline["actual_utility"],
                "regret": oracle["actual_utility"] - selected["actual_utility"],
                "improvement_over_geometric": selected["actual_utility"] - baseline["actual_utility"],
                "selected_safety_passed": selected_safety_passed,
                "candidates": scored,
            }
        )
    mean_regret = sum(item["regret"] for item in group_results) / len(group_results)
    mean_improvement = sum(item["improvement_over_geometric"] for item in group_results) / len(group_results)
    passed = bool(
        all(item["selected_safety_passed"] for item in group_results)
        and mean_regret <= 0.10
        and mean_improvement >= -0.02
    )
    return {
        "schema_version": 1,
        "passed": passed,
        "held_out_group_count": len(group_results),
        "mean_regret": mean_regret,
        "maximum_regret": max(item["regret"] for item in group_results),
        "mean_improvement_over_geometric": mean_improvement,
        "gates": {
            "maximum_mean_regret": 0.10,
            "minimum_mean_improvement_over_geometric": -0.02,
            "selected_candidate_safety_violations_allowed": 0,
        },
        "groups": group_results,
        "claim_boundary": "Held-out Isaac Sim matched-candidate evidence only. No physical grasp claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    dataset_path = (PROJECT_ROOT / args.dataset).resolve()
    model_path = (PROJECT_ROOT / args.model).resolve()
    output_path = (PROJECT_ROOT / args.output).resolve()
    for path in (dataset_path, model_path, output_path):
        if PROJECT_ROOT not in path.parents:
            raise ValueError("Evaluation paths must stay inside the project")
    summary = evaluate(_read_rows(dataset_path), GraspAffordanceModel.load(model_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
