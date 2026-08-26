"""Separate capture, holding, damage, and slip proxy models."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .contracts import Contract, Transform
from .frames import compose, inverse
from .physics import GRAVITY_MPS2


@dataclass(frozen=True)
class CaptureAssessment(Contract):
    captured: bool
    position_error_m: float
    angle_error_rad: float
    position_margin_m: float
    angle_margin_rad: float


@dataclass(frozen=True)
class HoldingAssessment(Contract):
    held: bool
    available_tangential_force_n: float
    required_tangential_force_n: float
    holding_margin: float


@dataclass(frozen=True)
class DamageAssessment(Contract):
    damaged: bool
    pressure_pa: float
    pressure_margin_pa: float


@dataclass(frozen=True)
class SlipEstimate(Contract):
    detected: bool
    commanded_grasp_from_product: Transform
    observed_grasp_from_product: Transform
    slip_transform: Transform
    position_magnitude_m: float
    angle_magnitude_rad: float


@dataclass(frozen=True)
class GraspAssessment(Contract):
    capture: CaptureAssessment
    holding: HoldingAssessment
    damage: DamageAssessment
    slip: SlipEstimate

    @property
    def grasped(self) -> bool:
        return self.capture.captured and self.holding.held and not self.damage.damaged


@dataclass(frozen=True)
class GraspModelConfig:
    footprint_radius_m: float
    footprint_angle_tolerance_rad: float
    minimum_contact_count: int
    safety_factor: float
    maximum_pressure_pa: float
    slip_position_threshold_m: float
    slip_angle_threshold_rad: float

    def __post_init__(self) -> None:
        for name in (
            "footprint_radius_m",
            "footprint_angle_tolerance_rad",
            "safety_factor",
            "maximum_pressure_pa",
            "slip_position_threshold_m",
            "slip_angle_threshold_rad",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if self.minimum_contact_count <= 0:
            raise ValueError("minimum_contact_count must be positive")


class GraspModel:
    def __init__(self, config: GraspModelConfig) -> None:
        self.config = config

    def assess_capture(
        self,
        *,
        position_error_m: float,
        angle_error_rad: float,
        position_uncertainty_m: float,
        contact_count: int,
    ) -> CaptureAssessment:
        position_margin = self.config.footprint_radius_m - abs(position_error_m) - position_uncertainty_m
        angle_margin = self.config.footprint_angle_tolerance_rad - abs(angle_error_rad)
        captured = position_margin >= 0.0 and angle_margin >= 0.0 and contact_count >= self.config.minimum_contact_count
        return CaptureAssessment(captured, abs(position_error_m), abs(angle_error_rad), position_margin, angle_margin)

    def assess_holding(
        self,
        *,
        mass_kg: float,
        planned_acceleration_mps2: float,
        friction_coefficient: float,
        normal_force_per_contact_n: float,
        contact_count: int,
    ) -> HoldingAssessment:
        values = (mass_kg, planned_acceleration_mps2, friction_coefficient, normal_force_per_contact_n)
        if any(not math.isfinite(value) or value < 0.0 for value in values) or mass_kg <= 0.0:
            raise ValueError("Holding inputs must be finite, nonnegative, and mass positive")
        available = friction_coefficient * normal_force_per_contact_n * contact_count
        required = mass_kg * math.hypot(GRAVITY_MPS2, planned_acceleration_mps2) * self.config.safety_factor
        margin = available / required if required else math.inf
        return HoldingAssessment(contact_count >= self.config.minimum_contact_count and margin >= 1.0, available, required, margin)

    def assess_damage(self, *, normal_force_per_contact_n: float, total_contact_area_m2: float) -> DamageAssessment:
        if normal_force_per_contact_n < 0.0 or total_contact_area_m2 <= 0.0:
            raise ValueError("Damage inputs require nonnegative force and positive contact area")
        pressure = normal_force_per_contact_n / total_contact_area_m2
        margin = self.config.maximum_pressure_pa - pressure
        return DamageAssessment(pressure > self.config.maximum_pressure_pa, pressure, margin)

    def estimate_slip(
        self,
        *,
        commanded_grasp_from_product: Transform,
        observed_grasp_from_product: Transform,
    ) -> SlipEstimate:
        slip = compose(inverse(commanded_grasp_from_product), observed_grasp_from_product)
        translation = slip.translation
        magnitude = math.sqrt(translation.x_m**2 + translation.y_m**2 + translation.z_m**2)
        angle = abs(slip.yaw_rad)
        detected = magnitude > self.config.slip_position_threshold_m or angle > self.config.slip_angle_threshold_rad
        return SlipEstimate(detected, commanded_grasp_from_product, observed_grasp_from_product, slip, magnitude, angle)

    @staticmethod
    def corrected_product_pose(observed_product_pose: Transform, slip: SlipEstimate) -> Transform:
        return compose(observed_product_pose, inverse(slip.slip_transform)) if slip.detected else observed_product_pose

    def assess(
        self,
        *,
        position_error_m: float,
        angle_error_rad: float,
        position_uncertainty_m: float,
        mass_kg: float,
        planned_acceleration_mps2: float,
        friction_coefficient: float,
        normal_force_per_contact_n: float,
        contact_count: int,
        total_contact_area_m2: float,
        commanded_grasp_from_product: Transform,
        observed_grasp_from_product: Transform,
    ) -> GraspAssessment:
        return GraspAssessment(
            self.assess_capture(
                position_error_m=position_error_m,
                angle_error_rad=angle_error_rad,
                position_uncertainty_m=position_uncertainty_m,
                contact_count=contact_count,
            ),
            self.assess_holding(
                mass_kg=mass_kg,
                planned_acceleration_mps2=planned_acceleration_mps2,
                friction_coefficient=friction_coefficient,
                normal_force_per_contact_n=normal_force_per_contact_n,
                contact_count=contact_count,
            ),
            self.assess_damage(
                normal_force_per_contact_n=normal_force_per_contact_n,
                total_contact_area_m2=total_contact_area_m2,
            ),
            self.estimate_slip(
                commanded_grasp_from_product=commanded_grasp_from_product,
                observed_grasp_from_product=observed_grasp_from_product,
            ),
        )
