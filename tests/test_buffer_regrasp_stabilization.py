import math

import pytest

from meatcell.buffer_regrasp import stabilize_buffer_regrasp_pose
from meatcell.contracts import Transform


def test_nearby_rgbd_observations_share_one_execution_proposal() -> None:
    first = Transform.planar(0.639703, -0.701986, 0.907500, math.radians(-13.44))
    second = Transform.planar(0.637740, -0.703515, 0.907500, math.radians(-13.94))

    assert stabilize_buffer_regrasp_pose(first) == stabilize_buffer_regrasp_pose(second)


def test_stabilized_pose_uses_documented_grid() -> None:
    result = stabilize_buffer_regrasp_pose(
        Transform.planar(0.637740, -0.703515, 0.907500, math.radians(-13.94))
    )

    assert result.translation.x_m == pytest.approx(0.64)
    assert result.translation.y_m == pytest.approx(-0.70)
    assert result.translation.z_m == pytest.approx(0.91)
    assert result.yaw_rad == pytest.approx(math.radians(-14.0))


@pytest.mark.parametrize("translation_quantum,yaw_quantum", [(0.0, 0.1), (0.01, 0.0)])
def test_invalid_grid_fails_closed(translation_quantum: float, yaw_quantum: float) -> None:
    with pytest.raises(ValueError):
        stabilize_buffer_regrasp_pose(
            Transform.identity(),
            translation_quantum_m=translation_quantum,
            yaw_quantum_rad=yaw_quantum,
        )
