from tools.summarize_solution_d import _bounded_replay


def _run(**overrides):
    payload = {
        "passed": True,
        "intercept_position_error_m": 0.010,
        "intercept_yaw_error_rad": 0.010,
        "delivery_position_error_m": 0.020,
        "delivery_yaw_error_rad": 0.005,
    }
    payload.update(overrides)
    return payload


def test_d_replay_preserves_frozen_delivery_position_limit() -> None:
    result = _bounded_replay(
        _run(),
        _run(delivery_position_error_m=0.020301),
    )

    assert result["passed"] is False
    assert result["metric_tolerances"]["delivery_position_error_m"] == 0.0003
    assert result["metric_absolute_deltas"]["delivery_position_error_m"] > 0.0003


def test_d_replay_passes_when_both_runs_and_every_metric_are_bounded() -> None:
    result = _bounded_replay(
        _run(),
        _run(
            intercept_position_error_m=0.0109,
            intercept_yaw_error_rad=0.018,
            delivery_position_error_m=0.02025,
            delivery_yaw_error_rad=0.008,
        ),
    )

    assert result["passed"] is True
