"""Conveyor kinematics, encoder interface, and seeded product spawning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import random

from .contracts import Contract, ContractEnum, SimTime, Transform


@dataclass(frozen=True)
class BeltState(Contract):
    timestamp: SimTime
    position_m: float
    speed_mps: float
    acceleration_mps2: float

    def __post_init__(self) -> None:
        for name in ("position_m", "speed_mps", "acceleration_mps2"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"BeltState.{name} must be finite")
        if self.speed_mps < 0.0:
            raise ValueError("BeltState.speed_mps must be nonnegative")


class BeltKinematics:
    def __init__(
        self,
        initial_speed_mps: float,
        *,
        acceleration_mps2: float = 0.0,
        initial_position_m: float = 0.0,
    ) -> None:
        for name, value in (
            ("initial_speed_mps", initial_speed_mps),
            ("acceleration_mps2", acceleration_mps2),
            ("initial_position_m", initial_position_m),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if initial_speed_mps < 0.0:
            raise ValueError("initial_speed_mps must be nonnegative")
        self.initial_speed_mps = initial_speed_mps
        self.acceleration_mps2 = acceleration_mps2
        self.initial_position_m = initial_position_m

    def at(self, timestamp: SimTime) -> BeltState:
        seconds = timestamp.seconds
        speed = self.initial_speed_mps + self.acceleration_mps2 * seconds
        if speed < 0.0:
            stop_time = self.initial_speed_mps / -self.acceleration_mps2
            position = self.initial_position_m + self.initial_speed_mps * stop_time + 0.5 * self.acceleration_mps2 * stop_time**2
            return BeltState(timestamp, position, 0.0, 0.0)
        position = self.initial_position_m + self.initial_speed_mps * seconds + 0.5 * self.acceleration_mps2 * seconds**2
        return BeltState(timestamp, position, speed, self.acceleration_mps2)


@dataclass(frozen=True)
class EncoderSample(Contract):
    sample_time: SimTime
    delivery_time: SimTime
    position_m: float
    speed_mps: float

    def __post_init__(self) -> None:
        if self.delivery_time < self.sample_time:
            raise ValueError("Encoder delivery cannot precede sample time")
        if not math.isfinite(self.position_m) or not math.isfinite(self.speed_mps):
            raise ValueError("Encoder values must be finite")


class EncoderModel:
    def __init__(
        self,
        kinematics: BeltKinematics,
        *,
        seed: int,
        position_noise_sigma_m: float = 0.0,
        speed_noise_sigma_mps: float = 0.0,
        delay_s: float = 0.0,
        dropout_probability: float = 0.0,
    ) -> None:
        for name, value in (
            ("position_noise_sigma_m", position_noise_sigma_m),
            ("speed_noise_sigma_mps", speed_noise_sigma_mps),
            ("delay_s", delay_s),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if not 0.0 <= dropout_probability <= 1.0:
            raise ValueError("dropout_probability must be between 0 and 1")
        self.kinematics = kinematics
        self._rng = random.Random(seed)
        self.position_noise_sigma_m = position_noise_sigma_m
        self.speed_noise_sigma_mps = speed_noise_sigma_mps
        self.delay_s = delay_s
        self.dropout_probability = dropout_probability

    def sample(self, timestamp: SimTime) -> EncoderSample | None:
        if self._rng.random() < self.dropout_probability:
            return None
        state = self.kinematics.at(timestamp)
        return EncoderSample(
            sample_time=timestamp,
            delivery_time=timestamp.plus_seconds(self.delay_s),
            position_m=state.position_m + self._rng.gauss(0.0, self.position_noise_sigma_m),
            speed_mps=max(0.0, state.speed_mps + self._rng.gauss(0.0, self.speed_noise_sigma_mps)),
        )

    @staticmethod
    def interpolate(samples: tuple[EncoderSample, ...], timestamp: SimTime) -> EncoderSample:
        ordered = sorted(samples, key=lambda item: item.sample_time.nanoseconds)
        if len(ordered) < 2:
            raise ValueError("At least two encoder samples are required for interpolation")
        before = next((item for item in reversed(ordered) if item.sample_time <= timestamp), None)
        after = next((item for item in ordered if item.sample_time >= timestamp), None)
        if before is None or after is None:
            raise ValueError("Interpolation timestamp lies outside the encoder sample range")
        if before.sample_time == after.sample_time:
            return EncoderSample(timestamp, max(before.delivery_time, timestamp), before.position_m, before.speed_mps)
        fraction = (timestamp.nanoseconds - before.sample_time.nanoseconds) / (
            after.sample_time.nanoseconds - before.sample_time.nanoseconds
        )
        return EncoderSample(
            sample_time=timestamp,
            delivery_time=max(before.delivery_time, after.delivery_time),
            position_m=before.position_m + fraction * (after.position_m - before.position_m),
            speed_mps=before.speed_mps + fraction * (after.speed_mps - before.speed_mps),
        )


class SpacingPolicy(ContractEnum):
    REJECT = "reject"
    LOG = "log"


@dataclass(frozen=True)
class ProductRecipe(Contract):
    recipe_id: str
    length_min_m: float
    length_max_m: float
    width_min_m: float
    width_max_m: float
    height_min_m: float
    height_max_m: float
    mass_min_kg: float
    mass_max_kg: float
    compliance_min: float
    compliance_max: float

    def __post_init__(self) -> None:
        if not self.recipe_id.strip():
            raise ValueError("recipe_id must not be blank")
        for prefix in ("length", "width", "height", "mass", "compliance"):
            low = getattr(self, f"{prefix}_min_m", None)
            high = getattr(self, f"{prefix}_max_m", None)
            if prefix in {"mass", "compliance"}:
                low = getattr(self, f"{prefix}_min_kg", None) if prefix == "mass" else self.compliance_min
                high = getattr(self, f"{prefix}_max_kg", None) if prefix == "mass" else self.compliance_max
            assert low is not None and high is not None
            if not math.isfinite(low) or not math.isfinite(high) or low <= 0.0 or high < low:
                raise ValueError(f"Invalid {prefix} range")


@dataclass(frozen=True)
class SpawnedProduct(Contract):
    product_id: str
    spawn_time: SimTime
    initial_pose_belt: Transform
    length_m: float
    width_m: float
    height_m: float
    mass_kg: float
    compliance: float


@dataclass(frozen=True)
class EpisodeParameters(Contract):
    family: str
    family_version: int
    seed: int
    belt_speed_mps: float
    belt_acceleration_mps2: float
    camera_latency_s: float
    encoder_delay_s: float
    products: tuple[SpawnedProduct, ...]
    spacing_policy: SpacingPolicy
    warnings: tuple[str, ...]


class ScenarioGenerator:
    def __init__(self, family: str, family_version: int, recipe: ProductRecipe) -> None:
        if not family.strip() or family_version <= 0:
            raise ValueError("Scenario family must be named and version positive")
        self.family = family
        self.family_version = family_version
        self.recipe = recipe

    def generate(
        self,
        *,
        seed: int,
        product_count: int,
        nominal_speed_mps: float,
        speed_sigma_mps: float,
        acceleration_range_mps2: tuple[float, float],
        arrival_spacing_range_s: tuple[float, float],
        minimum_spacing_m: float,
        spacing_policy: SpacingPolicy = SpacingPolicy.REJECT,
    ) -> EpisodeParameters:
        if product_count <= 0 or minimum_spacing_m <= 0.0:
            raise ValueError("product_count and minimum_spacing_m must be positive")
        if arrival_spacing_range_s[0] <= 0.0 or arrival_spacing_range_s[1] < arrival_spacing_range_s[0]:
            raise ValueError("Invalid arrival spacing range")
        rng = random.Random(seed)
        speed = max(0.01, rng.gauss(nominal_speed_mps, speed_sigma_mps))
        acceleration = rng.uniform(*acceleration_range_mps2)
        products = []
        warnings = []
        spawn_seconds = 0.0
        previous_distance = None
        for index in range(product_count):
            if index:
                spawn_seconds += rng.uniform(*arrival_spacing_range_s)
            distance = spawn_seconds * speed
            if previous_distance is not None and distance - previous_distance < minimum_spacing_m:
                message = f"product {index} spacing {distance - previous_distance:.6f} m is below {minimum_spacing_m:.6f} m"
                if spacing_policy is SpacingPolicy.REJECT:
                    raise ValueError(message)
                warnings.append(message)
            previous_distance = distance
            products.append(
                SpawnedProduct(
                    product_id=f"product-{index:03d}",
                    spawn_time=SimTime.from_seconds(spawn_seconds),
                    initial_pose_belt=Transform.planar(
                        0.0,
                        rng.uniform(-0.25, 0.25),
                        0.05,
                        rng.uniform(-math.pi, math.pi),
                    ),
                    length_m=rng.uniform(self.recipe.length_min_m, self.recipe.length_max_m),
                    width_m=rng.uniform(self.recipe.width_min_m, self.recipe.width_max_m),
                    height_m=rng.uniform(self.recipe.height_min_m, self.recipe.height_max_m),
                    mass_kg=rng.uniform(self.recipe.mass_min_kg, self.recipe.mass_max_kg),
                    compliance=rng.uniform(self.recipe.compliance_min, self.recipe.compliance_max),
                )
            )
        return EpisodeParameters(
            family=self.family,
            family_version=self.family_version,
            seed=seed,
            belt_speed_mps=speed,
            belt_acceleration_mps2=acceleration,
            camera_latency_s=rng.uniform(0.015, 0.055),
            encoder_delay_s=rng.uniform(0.0, 0.005),
            products=tuple(products),
            spacing_policy=spacing_policy,
            warnings=tuple(warnings),
        )
