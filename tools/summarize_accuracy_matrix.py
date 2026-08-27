"""Build JSON, CSV, and readable reports from an Isaac accuracy matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from meatcell.accuracy_benchmark import summarize_matrix


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    summary = summarize_matrix(args.root.resolve())
    print(json.dumps({
        "core_gate_passed": summary["core_gate_passed"],
        "all_cases_passed": summary["all_cases_passed"],
        "core_pass_count": summary["core"]["pass_count"],
        "core_fail_count": summary["core"]["fail_count"],
        "stress_pass_count": summary["stress"]["pass_count"],
        "stress_fail_count": summary["stress"]["fail_count"],
    }, indent=2))
    return 0 if summary["core_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
