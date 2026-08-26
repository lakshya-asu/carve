from dataclasses import replace
import json

import pytest

from meatcell.config import config_from_dict, config_path, load_config


def raw_config() -> dict:
    return load_config(config_path("a")).to_dict()


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        ("conveyor", "nominal_speed_mps", 0.0, "nominal_speed_mps"),
        ("simulation", "physics_hz", 0, "positive integer rate"),
        ("cutting", "timing_tolerance_s", -0.1, "timing_tolerance_s"),
        ("gripper", "normal_force_n", 0.0, "normal_force_n"),
        ("scenario", "mass_min_kg", -1.0, "mass_min_kg"),
        ("conveyor", "pick_x_max_m", 0.1, "pick window"),
    ],
)
def test_invalid_engineering_values_fail_actionably(section: str, field: str, value: object, message: str) -> None:
    data = raw_config()
    data[section][field] = value
    with pytest.raises(ValueError, match=message):
        config_from_dict(data)


def test_unknown_and_malformed_sections_fail_actionably() -> None:
    data = raw_config()
    data["robot"]["mystery_limit"] = 3
    with pytest.raises(ValueError, match="unknown fields: mystery_limit"):
        config_from_dict(data)
    data = raw_config()
    data["gripper"] = "invalid"
    with pytest.raises(ValueError, match="gripper must be a mapping"):
        config_from_dict(data)


def test_serialization_is_deterministic_and_hash_sensitive() -> None:
    first = load_config(config_path("a"))
    second = config_from_dict(json.loads(first.to_json()))
    assert first == second
    assert first.to_json() == second.to_json()
    assert first.sha256 == second.sha256
    changed = replace(first, conveyor=replace(first.conveyor, nominal_speed_mps=2.25))
    assert changed.sha256 != first.sha256


def test_existing_mapping_access_remains_available_during_migration() -> None:
    config = load_config(config_path("a"))
    assert config["conveyor"]["nominal_speed_mps"] == 2.24
