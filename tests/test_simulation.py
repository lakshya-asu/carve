from meatcell.config import config_path, load_config
from meatcell.runner import run
from meatcell.scenarios import generate_scenarios


def test_scenarios_are_reproducible() -> None:
    config = load_config(config_path("a"))
    first = generate_scenarios(config, episodes=10, seed=9)
    second = generate_scenarios(config, episodes=10, seed=9)
    assert first == second


def test_same_scenarios_can_be_used_for_both_solutions() -> None:
    config_a = load_config(config_path("a"))
    config_b = load_config(config_path("b"))
    scenarios = generate_scenarios(config_a, episodes=100, seed=4)
    results_a, _ = run(config_a, scenarios)
    results_b, _ = run(config_b, scenarios)
    assert [item.episode for item in results_a] == [item.episode for item in results_b]


def test_buffered_solution_improves_default_success_rate() -> None:
    config_a = load_config(config_path("a"))
    config_b = load_config(config_path("b"))
    scenarios = generate_scenarios(config_a, episodes=2000, seed=7)
    _, summary_a = run(config_a, scenarios)
    _, summary_b = run(config_b, scenarios)
    assert summary_b["success_rate"] > summary_a["success_rate"]


def test_metrics_include_complete_cell_failures() -> None:
    config = load_config(config_path("a"))
    scenarios = generate_scenarios(config, episodes=100, seed=11)
    _, summary = run(config, scenarios)
    assert summary["episodes"] == 100
    assert sum(summary["failure_counts"].values()) + summary["successes"] == 100
