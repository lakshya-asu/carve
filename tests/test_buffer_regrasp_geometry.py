import math
from types import SimpleNamespace

import pytest

from isaac_sim.cell_runner import (
    _buffer_closed_finger_targets,
    _buffer_regrasp_target,
    _closed_finger_targets,
)
from meatcell.contracts import Transform
from meatcell.product_profiles import load_product_catalog


def test_buffer_regrasp_uses_observed_planar_pose() -> None:
    observed = Transform.planar(1.781, -0.581, 0.175, math.radians(-17.0))

    target = _buffer_regrasp_target(observed)

    assert target.translation.x_m == pytest.approx(1.781)
    assert target.translation.y_m == pytest.approx(-0.581)
    assert target.translation.z_m == pytest.approx(0.195)
    assert target.yaw_rad == pytest.approx(math.radians(-17.0))


def test_buffer_regrasp_keeps_minimum_safe_height() -> None:
    observed = Transform.planar(1.8, -0.6, 0.13, 0.0)

    target = _buffer_regrasp_target(observed)

    assert target.translation.z_m == pytest.approx(0.17)


def test_buffer_closure_uses_local_mesh_width_without_changing_moving_pick() -> None:
    adapter = SimpleNamespace(
        product_profile=load_product_catalog().get("beef_center_cut_tenderloin")
    )

    moving_pick = _closed_finger_targets(adapter)
    buffer_pick = _buffer_closed_finger_targets(adapter)

    assert moving_pick == pytest.approx((-0.0405, 0.0405))
    assert abs(buffer_pick[0]) > abs(moving_pick[0])
    assert buffer_pick[0] == pytest.approx(-buffer_pick[1])
