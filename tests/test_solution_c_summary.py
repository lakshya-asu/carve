from tools.summarize_solution_c import _bounded_replay


def _run(**overrides):
    payload = {
        "passed": True,
        "delivery_position_error_m": 0.01,
        "delivery_yaw_error_rad": 0.01,
        "interception_timing_error_s": 0.01,
        "lift_distance_m": 0.18,
    }
    payload.update(overrides)
    return payload


def test_bounded_replay_reports_the_failed_metric_without_weakening_limits() -> None:
    result = _bounded_replay(
        _run(),
        _run(delivery_yaw_error_rad=0.014, delivery_position_error_m=0.0101),
    )

    assert result["passed"] is False
    assert result["metric_passes"]["delivery_position_error_m"] is True
    assert result["metric_passes"]["delivery_yaw_error_rad"] is False
    assert result["metric_tolerances"]["delivery_yaw_error_rad"] == 0.0034906585
    assert result["metric_absolute_deltas"]["delivery_yaw_error_rad"] == 0.004


def test_bounded_replay_passes_only_when_both_cycles_and_every_metric_pass() -> None:
    result = _bounded_replay(
        _run(),
        _run(
            delivery_position_error_m=0.0101,
            delivery_yaw_error_rad=0.012,
            interception_timing_error_s=0.014,
            lift_distance_m=0.1805,
        ),
    )

    assert result["passed"] is True
    assert result["both_cycles_passed"] is True
    assert all(result["metric_passes"].values())
