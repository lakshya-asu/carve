"""The belt must behave like a conveyor, not like a plank that runs out.

The defect these cover: modelling the belt as a body on a slide joint means it
physically translates. It reaches its joint limit, stops, and takes the whole
scene with it, and before that it slides out from under the camera so product
falls through where the belt used to be. Measured on the original model at
0.30 m/s: the belt stopped dead at t = 10.0 s and the product froze at
x = 2.405 m.
"""

import mujoco
import numpy as np
import pytest

from meat_cell_sim.cell import Cell
from meat_cell_sim.scene import CellConfig

BELT_TOP_Z_M = 0.90


@pytest.fixture(scope="module")
def running_cell():
    with Cell(CellConfig(belt_speed_mps=0.30)) as cell:
        yield cell


def test_belt_carries_product_far_past_the_old_joint_limit(running_cell) -> None:
    """Three metres of belt travel used to be the end of the world."""
    cell = running_cell
    cell.reset()
    cell.place_product(-0.60, 0.50, 0.0, settle_s=0.5)
    start_travel = cell.belt_travel_m
    cell.step(seconds=40.0)
    travelled = cell.belt_travel_m - start_travel
    assert travelled == pytest.approx(0.30 * 40.0, rel=0.01)
    assert cell.belt_speed_mps == pytest.approx(0.30, abs=0.005), "the belt stopped"


def test_the_belt_surface_stays_put(running_cell) -> None:
    """The joint is rewound every step, so the geometry never moves."""
    cell = running_cell
    cell.reset()
    cell.place_product(-0.60, 0.50, 0.0, settle_s=0.3)
    cell.step(seconds=20.0)
    belt_joint = cell.model.jnt_qposadr[mujoco.mj_name2id(cell.model, mujoco.mjtObj.mjOBJ_JOINT, "belt_x")]
    assert abs(float(cell.data.qpos[belt_joint])) < 1e-3


def test_product_rides_the_belt_rather_than_falling_through_it(running_cell) -> None:
    cell = running_cell
    cell.reset()
    cell.place_product(-0.70, 0.50, 0.4, settle_s=0.3)
    resting_z = float(cell.data.qpos[cell._product_qadr + 2])
    cell.step(seconds=6.0)
    assert float(cell.data.qpos[cell._product_qadr + 2]) == pytest.approx(resting_z, abs=1e-3)


def test_encoder_and_product_agree_to_the_slip(running_cell) -> None:
    """The belt-frame model the tracker rests on: carried product does not slip."""
    cell = running_cell
    cell.reset()
    cell.place_product(-0.70, 0.50, 0.0, settle_s=0.6)
    start_x, start_travel = cell.product_x_m, cell.belt_travel_m
    cell.step(seconds=3.0)
    carried = cell.product_x_m - start_x
    travelled = cell.belt_travel_m - start_travel
    assert abs(travelled - carried) < 0.002, f"slipped {1000 * (travelled - carried):.1f} mm in 3 s"


def test_encoder_is_continuous_across_the_rewind(running_cell) -> None:
    """A jump in the encoder would break the tracker's belt-frame subtraction."""
    cell = running_cell
    cell.reset()
    cell.place_product(-0.60, 0.50, 0.0, settle_s=0.3)
    readings = []
    for _ in range(200):
        cell.step(1)
        readings.append(cell.belt_travel_m)
    steps = np.diff(readings)
    assert steps.min() > 0, "the encoder went backwards"
    assert steps.max() < 2 * 0.30 * cell.model.opt.timestep, "the encoder jumped"


def test_reset_zeroes_the_encoder_and_rehomes_the_arm(running_cell) -> None:
    cell = running_cell
    cell.place_product(-0.60, 0.50, 0.0)
    cell.step(seconds=2.0)
    assert cell.belt_travel_m > 0.5
    cell.reset()
    assert cell.belt_travel_m == pytest.approx(0.0, abs=1e-12)
    assert cell.time_s == pytest.approx(0.0, abs=1e-12)
