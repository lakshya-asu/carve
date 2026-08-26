import pytest

from meatcell.physics import latency_travel_m, trapezoidal_motion_time_s


def test_ten_ms_at_nominal_speed_is_22_4_mm() -> None:
    assert latency_travel_m(2.24, 0.010) == pytest.approx(0.0224)


def test_short_move_is_triangular() -> None:
    assert trapezoidal_motion_time_s(0.5, 10.0, 80.0) == pytest.approx(2.0 * (0.5 / 80.0) ** 0.5)


def test_invalid_motion_limit_is_rejected() -> None:
    with pytest.raises(ValueError):
        trapezoidal_motion_time_s(1.0, 0.0, 1.0)
