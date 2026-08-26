from pathlib import Path

import pytest
import yaml

from meatcell.product_profiles import load_product_catalog


def test_default_catalog_contains_three_valid_reference_recipes() -> None:
    catalog = load_product_catalog()
    assert catalog.version == 1
    assert set(catalog.profiles) == {
        "beef_center_cut_tenderloin",
        "pork_boneless_loin",
        "chicken_breast_fillet",
    }
    assert catalog.get("beef_center_cut_tenderloin").mass_kg.nominal == pytest.approx(1.8)
    assert catalog.get("pork_boneless_loin").mass_kg.maximum == pytest.approx(3.2)
    assert catalog.get("chicken_breast_fillet").mechanics.handling_compliance == "high"
    assert all(not profile.mechanics.calibrated for profile in catalog.profiles.values())


def test_catalog_profiles_convert_to_seeded_spawn_recipe_contract() -> None:
    profile = load_product_catalog().get("chicken_breast_fillet")
    recipe = profile.to_spawn_recipe()
    assert recipe.recipe_id == profile.recipe_id
    assert recipe.length_min_m == pytest.approx(0.14)
    assert recipe.mass_max_kg == pytest.approx(0.230)
    assert recipe.compliance_min == pytest.approx(0.60)
    assert recipe.compliance_max == pytest.approx(0.90)


def test_unknown_recipe_has_actionable_error() -> None:
    catalog = load_product_catalog()
    with pytest.raises(ValueError, match="Available recipes"):
        catalog.get("beef_everything")


def test_invalid_catalog_range_is_rejected(tmp_path: Path) -> None:
    source = Path("configs/product_recipes.yaml")
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data["recipes"]["chicken_breast_fillet"]["mass_kg"] = {"min": 0.2, "nominal": 0.1, "max": 0.3}
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="min <= nominal <= max"):
        load_product_catalog(path)
