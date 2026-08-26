from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import config_path, load_config
from .runner import run
from .scenarios import generate_scenarios


def _write_or_print(payload: dict[str, Any], output: str | None) -> None:
    rendered = json.dumps(payload, indent=2)
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote {target.resolve()}")
    print(rendered)


def command_run(args: argparse.Namespace) -> None:
    config = load_config(config_path(args.solution))
    scenarios = generate_scenarios(config, args.episodes, args.seed)
    _, summary = run(config, scenarios)
    _write_or_print({"seed": args.seed, "summary": summary}, args.output)


def command_compare(args: argparse.Namespace) -> None:
    config_a = load_config(config_path("a"))
    config_b = load_config(config_path("b"))
    scenarios = generate_scenarios(config_a, args.episodes, args.seed)
    _, summary_a = run(config_a, scenarios)
    _, summary_b = run(config_b, scenarios)
    payload = {
        "seed": args.seed,
        "episodes_per_solution": args.episodes,
        "same_scenarios": True,
        "solution_a": summary_a,
        "solution_b": summary_b,
        "delta_success_rate_b_minus_a": summary_b["success_rate"] - summary_a["success_rate"],
        "warning": "Outputs are architecture-screening estimates, not validated production predictions.",
    }
    _write_or_print(payload, args.output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Meat interception cell architecture simulator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare = subparsers.add_parser("compare", help="Compare solutions A and B on identical scenarios")
    compare.add_argument("--episodes", type=int, default=1000)
    compare.add_argument("--seed", type=int, default=7)
    compare.add_argument("--output")
    compare.set_defaults(handler=command_compare)

    single = subparsers.add_parser("run", help="Run one solution")
    single.add_argument("--solution", choices=("a", "b", "direct", "buffered"), required=True)
    single.add_argument("--episodes", type=int, default=1000)
    single.add_argument("--seed", type=int, default=7)
    single.add_argument("--output")
    single.set_defaults(handler=command_run)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.episodes <= 0:
        parser.error("--episodes must be positive")
    args.handler(args)


if __name__ == "__main__":
    main()
