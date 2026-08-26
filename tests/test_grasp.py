import math

import pytest

from meatcell.contracts import Transform
from meatcell.grasp import GraspModel, GraspModelConfig


def model() -> GraspModel:
    return GraspModel(
        GraspModelConfig(
            footprint_radius_m=0.04,
            footprint_angle_tolerance_rad=math.radians(12.0),
            minimum_contact_count=2,
            safety_factor=1.2,
            maximum_pressure_pa=25_000.0,
            slip_position_threshold_m=0.005,
            slip_angle_threshold_rad=math.radians(1.5),
        )
    )


def test_capture_failure_is_separate_from_hold_failure() -> None:
    grasp = model()
    capture = grasp.assess_capture(position_error_m=0.06, angle_error_rad=0.0, position_uncertainty_m=0.0, contact_count=2)
    hold = grasp.assess_holding(
        mass_kg=0.5, planned_acceleration_mps2=1.0, friction_coefficient=1.0, normal_force_per_contact_n=50.0, contact_count=2
    )
    assert not capture.captured
    assert hold.held


def test_holding_margin_is_monotonic() -> None:
    grasp = model()
    base = dict(mass_kg=1.0, planned_acceleration_mps2=4.0, friction_coefficient=0.4, normal_force_per_contact_n=40.0, contact_count=2)
    nominal = grasp.assess_holding(**base).holding_margin
    assert grasp.assess_holding(**{**base, "friction_coefficient": 0.5}).holding_margin >= nominal
    assert grasp.assess_holding(**{**base, "normal_force_per_contact_n": 50.0}).holding_margin >= nominal
    assert grasp.assess_holding(**{**base, "planned_acceleration_mps2": 8.0}).holding_margin <= nominal
    assert grasp.assess_holding(**{**base, "mass_kg": 1.2}).holding_margin <= nominal


def test_contact_area_cannot_increase_pressure() -> None:
    grasp = model()
    small = grasp.assess_damage(normal_force_per_contact_n=50.0, total_contact_area_m2=0.002)
    large = grasp.assess_damage(normal_force_per_contact_n=50.0, total_contact_area_m2=0.004)
    assert large.pressure_pa <= small.pressure_pa


def test_slip_is_a_transform_and_can_be_corrected() -> None:
    grasp = model()
    commanded = Transform.identity()
    observed = Transform.planar(0.008, 0.0, 0.0, math.radians(2.0))
    slip = grasp.estimate_slip(commanded_grasp_from_product=commanded, observed_grasp_from_product=observed)
    assert slip.detected
    assert slip.slip_transform == observed
    corrected = grasp.corrected_product_pose(observed, slip)
    assert corrected.translation.x_m == pytest.approx(0.0, abs=1e-12)
    assert corrected.yaw_rad == pytest.approx(0.0, abs=1e-12)


def test_pressure_damage_and_complete_assessment() -> None:
    assessment = model().assess(
        position_error_m=0.005,
        angle_error_rad=0.01,
        position_uncertainty_m=0.002,
        mass_kg=0.5,
        planned_acceleration_mps2=2.0,
        friction_coefficient=0.5,
        normal_force_per_contact_n=50.0,
        contact_count=2,
        total_contact_area_m2=0.001,
        commanded_grasp_from_product=Transform.identity(),
        observed_grasp_from_product=Transform.identity(),
    )
    assert assessment.capture.captured
    assert assessment.holding.held
    assert assessment.damage.damaged
    assert not assessment.grasped
