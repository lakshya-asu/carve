"""Grasp from the camera: the perceived leg and the shank rule against the simulator's true shank."""

import math

import numpy as np
import pytest

from meat_cell_sim.arms import ArmModel
from meat_cell_sim.cameras import GEMINI_335L, sense_depth
from meat_cell_sim.cell import Cell
from meat_cell_sim.grasp_action import GraspAction
from meat_cell_sim.grasp_policy import SHANK_FRACTION, GraspRefusedError, ShankGraspRule
from meat_cell_sim.gripper import GripperModel
from meat_cell_sim.leg_perception import perceive_leg
from meat_cell_sim.leg_segmentation import EmptyBeltReference, LegSegmenter
from meat_cell_sim.product import PRODUCT_BODY, LegConfig, leg_centreline, leg_half_width_m
from meat_cell_sim.scene import CellConfig
from meat_cell_sim.sensing import CameraFrameData, CameraSpec

CAM = GEMINI_335L.name
LEG = LegConfig()


def _noisy(frame: CameraFrameData, rng: np.random.Generator) -> CameraFrameData:
    depth = sense_depth(frame.depth_m, GEMINI_335L, rng)
    return CameraFrameData(frame.stamp_s, frame.rgb, depth, frame.intrinsics, frame.camera)


@pytest.fixture(scope="module", params=[0.0, 35.0], ids=["square", "yaw35"])
def seen_leg(request):
    """A leg under the camera: its perception, and the true shank point and direction at the grasp fraction."""
    config = CellConfig(
        leg=LEG,
        arm=ArmModel.UR20,
        gripper=GripperModel.JAW_GEH6180,
        depth_cameras=(GEMINI_335L,),
        depth_camera_yaw_deg=90.0,
    )
    rng = np.random.default_rng(3)
    with Cell(config, {CAM: CameraSpec(CAM, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)}) as cell:
        cell.reset()
        cell.place_product(1.3, 0.5, -math.pi / 2)
        segmenter = LegSegmenter(EmptyBeltReference.from_frames([_noisy(cell.observe(CAM)[1], rng) for _ in range(10)]))
        heading = -math.pi / 2 + math.radians(request.param)
        cell.reset()
        cell.place_product(
            -0.40 - LEG.outline_centre_m * math.cos(heading),
            0.42 - LEG.outline_centre_m * math.sin(heading),
            heading,
            settle_s=0.2,
        )
        observation, frame = cell.observe(CAM)
        noisy = _noisy(frame, rng)
        result = segmenter.segment(noisy)
        assert result.accepted
        leg = perceive_leg(noisy, result.mask, segmenter.reference.plane, observation.belt_travel_m)
        body = cell.model.body(PRODUCT_BODY).id
        position, rotation = cell.data.xpos[body].copy(), cell.data.xmat[body].reshape(3, 3).copy()
    line = leg_centreline(LEG, np.array([SHANK_FRACTION - 0.01, SHANK_FRACTION, SHANK_FRACTION + 0.01]))
    world = position + line @ rotation.T
    direction = world[2, :2] - world[0, :2]
    return leg, observation.belt_travel_m, world[1], math.atan2(direction[1], direction[0]), rotation[:2, 0]


def test_the_perceived_axis_points_from_the_ham_to_the_trotter(seen_leg) -> None:
    leg, _, _, _, body_x = seen_leg
    axis = np.array([math.cos(leg.axis_rad), math.sin(leg.axis_rad)])
    assert axis @ body_x > math.cos(math.radians(5.0))
    assert leg.length_m == pytest.approx(LEG.length_m, abs=0.03)


def test_the_rule_grips_the_true_shank_across_it(seen_leg) -> None:
    leg, travel_m, true_point, true_direction, _ = seen_leg
    action = ShankGraspRule().decide(leg)
    assert isinstance(action, GraspAction)
    world = action.world_point_m(travel_m)
    assert np.hypot(*(world[:2] - true_point[:2])) < 0.020
    assert abs(world[2] - true_point[2]) < 0.020
    across = abs(math.remainder(action.finger_axis_rad - (true_direction + math.pi / 2), math.pi))
    assert across < math.radians(8.0)
    true_width = 2 * float(leg_half_width_m(LEG, np.array([SHANK_FRACTION]))[0])
    assert action.opening_m == pytest.approx(true_width + 0.040, abs=0.015)


def test_a_shank_too_wide_for_the_gripper_is_refused(seen_leg) -> None:
    with pytest.raises(GraspRefusedError, match=r"too wide|opens"):
        ShankGraspRule(max_opening_m=0.05).decide(seen_leg[0])
