import pytest

from meatcell.contracts import SimTime, contract_from_json
from meatcell.conveyor import (
    BeltKinematics,
    EncoderModel,
    EpisodeParameters,
    ProductRecipe,
    ScenarioGenerator,
    SpacingPolicy,
)


def recipe() -> ProductRecipe:
    return ProductRecipe("reference-cut", 0.18, 0.30, 0.08, 0.15, 0.025, 0.06, 0.4, 1.2, 0.1, 0.7)


def test_nominal_ten_ms_travel_and_acceleration() -> None:
    constant = BeltKinematics(2.24)
    assert constant.at(SimTime.from_seconds(0.010)).position_m == pytest.approx(0.0224)
    accelerating = BeltKinematics(2.0, acceleration_mps2=1.0)
    state = accelerating.at(SimTime.from_seconds(0.5))
    assert state.position_m == pytest.approx(1.125)
    assert state.speed_mps == pytest.approx(2.5)


def test_encoder_interpolation_uses_sample_timestamps() -> None:
    model = EncoderModel(BeltKinematics(2.0), seed=1, delay_s=0.01)
    samples = (model.sample(SimTime(0)), model.sample(SimTime.from_seconds(0.1)))
    assert all(item is not None for item in samples)
    interpolated = EncoderModel.interpolate(tuple(item for item in samples if item), SimTime.from_seconds(0.025))
    assert interpolated.position_m == pytest.approx(0.05)
    assert interpolated.sample_time == SimTime.from_seconds(0.025)


def test_encoder_noise_delay_and_dropout_are_seeded_and_configurable() -> None:
    kwargs = dict(seed=9, position_noise_sigma_m=0.01, speed_noise_sigma_mps=0.02, delay_s=0.005)
    first = EncoderModel(BeltKinematics(2.24, acceleration_mps2=0.1), **kwargs)
    second = EncoderModel(BeltKinematics(2.24, acceleration_mps2=0.1), **kwargs)
    assert first.sample(SimTime.from_seconds(0.2)) == second.sample(SimTime.from_seconds(0.2))
    dropped = EncoderModel(BeltKinematics(2.24), seed=1, dropout_probability=1.0)
    assert dropped.sample(SimTime(0)) is None


def test_scenario_is_seeded_versioned_and_losslessly_serializable() -> None:
    generator = ScenarioGenerator("nominal", 2, recipe())
    kwargs = dict(
        seed=17,
        product_count=3,
        nominal_speed_mps=2.24,
        speed_sigma_mps=0.05,
        acceleration_range_mps2=(-0.1, 0.1),
        arrival_spacing_range_s=(0.4, 0.6),
        minimum_spacing_m=0.5,
    )
    first = generator.generate(**kwargs)
    assert first == generator.generate(**kwargs)
    restored = contract_from_json(first.to_json())
    assert isinstance(restored, EpisodeParameters)
    assert restored == first


def test_invalid_spacing_is_rejected_or_logged_by_policy() -> None:
    generator = ScenarioGenerator("close-spacing", 1, recipe())
    kwargs = dict(
        seed=1,
        product_count=2,
        nominal_speed_mps=2.24,
        speed_sigma_mps=0.0,
        acceleration_range_mps2=(0.0, 0.0),
        arrival_spacing_range_s=(0.01, 0.01),
        minimum_spacing_m=0.5,
    )
    with pytest.raises(ValueError, match="spacing"):
        generator.generate(**kwargs, spacing_policy=SpacingPolicy.REJECT)
    logged = generator.generate(**kwargs, spacing_policy=SpacingPolicy.LOG)
    assert len(logged.warnings) == 1
