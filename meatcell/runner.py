from __future__ import annotations

from typing import Any

from .metrics import summarize
from .models import EpisodeResult, Scenario
from .policies import evaluate


def run(config: dict[str, Any], scenarios: list[Scenario]) -> tuple[list[EpisodeResult], dict[str, Any]]:
    results = [evaluate(config, scenario) for scenario in scenarios]
    return results, summarize(results)
