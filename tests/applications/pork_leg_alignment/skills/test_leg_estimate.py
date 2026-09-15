"""The leg estimate is what every planning skill reads, so its two sources must agree with the world.

From ground truth the estimate must reproduce the leg's true centreline, hock and centre of mass;
from the camera it must land within the perception pipeline's measured accuracy of the same
points on the same leg. The skills that consume it are tested on their own.
"""

import math

import numpy as np
import pytest

from applications.pork_leg_alignment.perception.leg_segmentation import EmptyBeltReference, LegSegmenter
from applications.pork_leg_alignment.perception.perceive_leg import perceive_leg
from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import HOCK_FRACTION, LegConfig, leg_centreline
from applications.pork_leg_alignment.sim.scene import CellConfig
from applications.pork_leg_alignment.sim.sensing import CameraSpec
from applications.pork_leg_alignment.skills import EstimateLegFromCamera, EstimateLegFromGroundTruth
from applications.pork_leg_alignment.skills.leg_estimate import LegEstimate, estimate_from_ground_truth
from robotics.core.camera_frame import CameraFrameData
from robotics.core.skill_library import SUCCESS, run_skill
from robotics.hardware.arms import ArmModel
from robotics.hardware.cameras import GEMINI_335L, sense_depth
from robotics.hardware.grippers import GripperModel

CAM = GEMINI_335L.name
LEG = LegConfig()


def test_the_ground_truth_estimate_reproduces_the_true_hock_and_centre_of_mass() -> None:
    config = CellConfig(leg=LEG, arm=ArmModel.UR20, gripper=GripperModel.JAW_GEH6180)
    with Cell(config) as cell:
        cell.reset()
        cell.place_product(0.30, 0.55, -math.pi / 2 + math.radians(20), settle_s=0.2)
        result = run_skill(EstimateLegFromGroundTruth(), cell, {})
        assert result.outcome == SUCCESS
        estimate: LegEstimate = result.outputs["leg_estimate"]
        body = cell.model.body("slab").id
        position, rotation = cell.data.xpos[body], cell.data.xmat[body].reshape(3, 3)
        true_hock = position + rotation @ leg_centreline(LEG, np.array([HOCK_FRACTION]))[0]
        assert np.linalg.norm(estimate.point_at(HOCK_FRACTION) - true_hock) < 0.002
        assert estimate.length_m == pytest.approx(LEG.length_m, abs=0.002)
        truth = cell.ground_truth()
        assert truth.centre_of_mass_m is not None
        assert np.allclose(estimate.centre_of_gravity_m, truth.centre_of_mass_m)
        assert estimate.heading_rad == pytest.approx(-math.pi / 2 + math.radians(20), abs=1e-3)
        assert estimate.source == "ground_truth"


def test_the_camera_estimate_lands_near_the_true_leg() -> None:
    """Clean depth: the pipeline's hock, heading and centre of gravity within its measured accuracy."""
    config = CellConfig(
        leg=LEG,
        arm=ArmModel.UR20,
        gripper=GripperModel.JAW_GEH6180,
        depth_cameras=(GEMINI_335L,),
        depth_camera_yaw_deg=90.0,
    )
    rng = np.random.default_rng(3)

    def noisy(frame: CameraFrameData) -> CameraFrameData:
        return CameraFrameData(
            frame.stamp_s,
            frame.rgb,
            sense_depth(frame.depth_m, GEMINI_335L, rng, edges=None),
            frame.intrinsics,
            frame.camera,
        )

    with Cell(config, {CAM: CameraSpec(CAM, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)}) as cell:
        cell.reset()
        cell.place_product(1.3, 0.5, -math.pi / 2)
        segmenter = LegSegmenter(EmptyBeltReference.from_frames([noisy(cell.observe(CAM)[1]) for _ in range(10)]))
        cell.reset()
        cell.place_product(-0.40 - LEG.outline_centre_m * math.cos(-math.pi / 2), 0.42, -math.pi / 2, settle_s=0.2)
        observation, frame = cell.observe(CAM)
        frame = noisy(frame)
        result = segmenter.segment(frame)
        assert result.accepted
        leg = perceive_leg(frame, result.mask, segmenter.reference.plane, observation.belt_travel_m)
        estimated = run_skill(EstimateLegFromCamera(), cell, {"leg_perception": leg})
        assert estimated.outcome == SUCCESS
        estimate: LegEstimate = estimated.outputs["leg_estimate"]
        truth = estimate_from_ground_truth(cell)
        carried = np.array([truth.belt_travel_m - estimate.belt_travel_m, 0.0, 0.0])
        hock_error = np.linalg.norm((estimate.point_at(HOCK_FRACTION) + carried - truth.point_at(HOCK_FRACTION))[:2])
        centre_error = np.linalg.norm((estimate.centre_of_gravity_m + carried - truth.centre_of_gravity_m)[:2])
        assert hock_error < 0.030, f"hock {1000 * hock_error:.0f} mm off"
        assert centre_error < 0.020, f"centre of gravity {1000 * centre_error:.0f} mm off"
        assert abs(math.remainder(estimate.heading_rad - truth.heading_rad, 2 * math.pi)) < math.radians(3.0)
        assert estimate.source.startswith("camera")
