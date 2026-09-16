"""The loin estimate is the leg's estimate plus the bone side, and both must agree with the world.

From ground truth it must reproduce the loin's true centreline, widths, centre of mass and bone
side, pass through the leg's port so the grasp and turn skills read it unchanged, and carry the
bone side as the one field whose meaning survives a flipped axis.
"""

import math

import numpy as np
import pytest

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.loin import LoinConfig
from applications.pork_leg_alignment.sim.scene import CellConfig
from applications.pork_leg_alignment.skills import EstimateLoinFromGroundTruth, LegEstimate, LoinEstimate
from applications.pork_leg_alignment.skills.loin_estimate import estimate_loin_from_ground_truth
from robotics.core.skill_library import PRECONDITION_FAILED, SUCCESS, run_skill
from robotics.hardware.arms import ArmModel
from robotics.hardware.grippers import GripperModel


@pytest.fixture(scope="module", params=[False, True], ids=["bone_right", "bone_left"])
def loin_cell(request):
    config = CellConfig(
        loin=LoinConfig(bone_on_left=request.param), arm=ArmModel.UR20, gripper=GripperModel.JAW_GEH6180
    )
    with Cell(config) as cell:
        yield cell


def test_the_ground_truth_estimate_reproduces_the_true_loin(loin_cell) -> None:
    cell = loin_cell
    loin = cell.config.loin
    assert loin is not None
    cell.reset()
    cell.place_product(0.30, 0.55, math.radians(20), settle_s=0.2)
    result = run_skill(EstimateLoinFromGroundTruth(), cell, {})
    assert result.outcome == SUCCESS
    estimate = result.outputs["leg_estimate"]
    assert isinstance(estimate, LoinEstimate) and isinstance(estimate, LegEstimate)
    assert estimate.bone_side == loin.bone_side
    assert estimate.length_m == pytest.approx(loin.length_m, abs=0.002)
    fractions = np.array([0.0, 0.5, 1.0])
    assert np.allclose(estimate.centreline_m[[0, 20, 40]], cell.product_centreline_world(fractions), atol=1e-6)
    assert np.allclose(estimate.widths_m[[0, 20, 40]], 2.0 * loin.half_width_m(fractions))
    truth = cell.ground_truth()
    assert truth.centre_of_mass_m is not None
    assert np.allclose(estimate.centre_of_gravity_m, truth.centre_of_mass_m)
    assert estimate.heading_rad == pytest.approx(math.radians(20), abs=2e-3)
    assert estimate.source == "ground_truth"
    assert result.evidence["bone_side"] == loin.bone_side


def test_the_bone_edge_lies_on_the_bone_side_of_the_heading(loin_cell) -> None:
    """The one field that carries the pose's meaning must point at the taller edge in the world."""
    cell = loin_cell
    loin = cell.config.loin
    assert loin is not None
    cell.reset()
    cell.place_product(0.30, 0.55, math.radians(-35), settle_s=0.2)
    estimate = estimate_loin_from_ground_truth(cell)
    body = cell.model.body("slab").id
    edge_world = cell.data.xpos[body] + cell.data.xmat[body].reshape(3, 3) @ loin.bone_edge_m(np.array([0.5]))[0]
    from_centreline = edge_world - estimate.point_at(0.5)
    assert float(from_centreline[:2] @ estimate.left_normal()[:2]) * estimate.bone_side > 0.05


def test_a_loin_off_the_belt_fails_the_precondition(loin_cell) -> None:
    cell = loin_cell
    cell.reset()
    cell.place_product(0.30, 0.55, 0.0)
    adr = cell.model.jnt_qposadr[cell.model.joint("slab_free").id]
    cell.data.qpos[adr + 2] += 0.10
    cell.step()
    result = run_skill(EstimateLoinFromGroundTruth(), cell, {})
    assert result.outcome == PRECONDITION_FAILED


def test_a_bone_side_other_than_plus_or_minus_one_is_refused() -> None:
    with pytest.raises(ValueError, match="bone side"):
        LoinEstimate(
            centreline_m=np.zeros((3, 3)),
            widths_m=np.ones(3),
            heading_rad=0.0,
            centre_of_gravity_m=np.zeros(3),
            belt_travel_m=0.0,
            source="test",
            bone_side=0.0,
        )
