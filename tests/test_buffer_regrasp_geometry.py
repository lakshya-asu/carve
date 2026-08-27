import math
from types import SimpleNamespace

import pytest

from isaac_sim.cell_runner import (
    _buffer_closed_finger_targets,
    _buffer_regrasp_target,
    _closed_finger_targets,
    _collision_aware_tcp_check,
    _preshape_finger_targets,
    _project_alignment_target_to_envelope,
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


def test_moving_preshape_retains_more_clearance_than_final_closure() -> None:
    adapter = SimpleNamespace(
        product_profile=load_product_catalog().get("beef_center_cut_tenderloin")
    )

    final = _closed_finger_targets(adapter)
    preshape = _preshape_finger_targets(adapter)

    assert preshape[0] == pytest.approx(final[0] * 0.25)
    assert preshape[1] == pytest.approx(final[1] * 0.25)
    assert abs(preshape[0]) < abs(final[0])


def test_alignment_target_projects_small_workspace_boundary_error() -> None:
    target = Transform.planar(2.480479, 0.0, 0.20, 0.0)

    projected = _project_alignment_target_to_envelope(target)

    assert projected.translation.x_m == pytest.approx(2.48)
    assert projected.translation.y_m == pytest.approx(0.0)
    assert projected.translation.z_m == pytest.approx(0.20)


def test_alignment_target_rejects_large_workspace_projection() -> None:
    target = Transform.planar(2.51, 0.0, 0.20, 0.0)

    with pytest.raises(ValueError, match="infeasible TCP target"):
        _project_alignment_target_to_envelope(target)


def test_collision_check_accepts_only_numerical_boundary_roundoff() -> None:
    names = ("x_axis", "y_axis", "z_axis", "wrist_yaw", "finger_left", "finger_right")
    at_boundary = (2.1300000000000003, 0.0, -0.15, 0.0, 0.0, 0.0)
    beyond_epsilon = (2.13000001, 0.0, -0.15, 0.0, 0.0, 0.0)

    _collision_aware_tcp_check(at_boundary, names)
    with pytest.raises(ValueError, match="leaves validated cell envelope"):
        _collision_aware_tcp_check(beyond_epsilon, names)
