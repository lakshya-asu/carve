"""Versioned product profiles for cutter-loading scenarios.

The catalog separates physical quantities from the dimensionless compliance
index used by the current rigid-body sensitivity model. None of the profiles
claim calibrated meat mechanics.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Mapping

import yaml

from .conveyor import ProductRecipe


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "configs" / "product_recipes.yaml"


def _mapping(name: str, value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value.strip()


def _finite(name: str, value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{name} must be finite")
    return parsed


@dataclass(frozen=True)
class NumericRange:
    minimum: float
    nominal: float
    maximum: float

    @classmethod
    def from_mapping(cls, name: str, raw: Any, *, positive: bool = True) -> "NumericRange":
        values = _mapping(name, raw)
        expected = {"min", "nominal", "max"}
        if set(values) != expected:
            raise ValueError(f"{name} must contain exactly min, nominal, and max")
        result = cls(
            _finite(f"{name}.min", values["min"]),
            _finite(f"{name}.nominal", values["nominal"]),
            _finite(f"{name}.max", values["max"]),
        )
        if positive and result.minimum <= 0.0:
            raise ValueError(f"{name}.min must be greater than zero")
        if not result.minimum <= result.nominal <= result.maximum:
            raise ValueError(f"{name} must satisfy min <= nominal <= max")
        return result


@dataclass(frozen=True)
class ProductGeometry:
    length_m: NumericRange
    width_m: NumericRange
    height_m: NumericRange
    shape_family: str
    taper_ratio: NumericRange
    maximum_curvature_ratio: float
    maximum_asymmetry_ratio: float

    @classmethod
    def from_mapping(cls, name: str, raw: Any) -> "ProductGeometry":
        values = _mapping(name, raw)
        result = cls(
            length_m=NumericRange.from_mapping(f"{name}.length_m", values.get("length_m")),
            width_m=NumericRange.from_mapping(f"{name}.width_m", values.get("width_m")),
            height_m=NumericRange.from_mapping(f"{name}.height_m", values.get("height_m")),
            shape_family=_text(f"{name}.shape_family", values.get("shape_family")),
            taper_ratio=NumericRange.from_mapping(f"{name}.taper_ratio", values.get("taper_ratio")),
            maximum_curvature_ratio=_finite(
                f"{name}.maximum_curvature_ratio", values.get("maximum_curvature_ratio")
            ),
            maximum_asymmetry_ratio=_finite(
                f"{name}.maximum_asymmetry_ratio", values.get("maximum_asymmetry_ratio")
            ),
        )
        for field_name, value in (
            ("maximum_curvature_ratio", result.maximum_curvature_ratio),
            ("maximum_asymmetry_ratio", result.maximum_asymmetry_ratio),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name}.{field_name} must be between zero and one")
        return result


@dataclass(frozen=True)
class ProductMechanics:
    handling_compliance: str
    compliance_index: NumericRange
    effective_compression_modulus_kpa: NumericRange
    friction_coefficient: NumericRange
    surface_condition: str
    calibrated: bool

    @classmethod
    def from_mapping(cls, name: str, raw: Any) -> "ProductMechanics":
        values = _mapping(name, raw)
        result = cls(
            handling_compliance=_text(f"{name}.handling_compliance", values.get("handling_compliance")),
            compliance_index=NumericRange.from_mapping(
                f"{name}.compliance_index", values.get("compliance_index"), positive=False
            ),
            effective_compression_modulus_kpa=NumericRange.from_mapping(
                f"{name}.effective_compression_modulus_kpa",
                values.get("effective_compression_modulus_kpa"),
            ),
            friction_coefficient=NumericRange.from_mapping(
                f"{name}.friction_coefficient", values.get("friction_coefficient")
            ),
            surface_condition=_text(f"{name}.surface_condition", values.get("surface_condition")),
            calibrated=values.get("calibrated"),
        )
        if result.handling_compliance not in {"low", "medium", "high"}:
            raise ValueError(f"{name}.handling_compliance must be low, medium, or high")
        if not 0.0 <= result.compliance_index.minimum <= result.compliance_index.maximum <= 1.0:
            raise ValueError(f"{name}.compliance_index must remain between zero and one")
        if not isinstance(result.calibrated, bool):
            raise ValueError(f"{name}.calibrated must be true or false")
        return result


@dataclass(frozen=True)
class ProductProfile:
    recipe_id: str
    display_name: str
    species: str
    cut: str
    process_state: str
    geometry: ProductGeometry
    mass_kg: NumericRange
    mechanics: ProductMechanics
    required_tray_orientation: str
    evidence: tuple[str, ...]
    assumptions: tuple[str, ...]

    @classmethod
    def from_mapping(cls, recipe_id: str, raw: Any) -> "ProductProfile":
        values = _mapping(f"recipes.{recipe_id}", raw)
        evidence = values.get("evidence")
        assumptions = values.get("assumptions")
        if not isinstance(evidence, list) or not all(isinstance(item, str) and item.strip() for item in evidence):
            raise ValueError(f"recipes.{recipe_id}.evidence must be a list of nonempty strings")
        if not isinstance(assumptions, list) or not all(
            isinstance(item, str) and item.strip() for item in assumptions
        ):
            raise ValueError(f"recipes.{recipe_id}.assumptions must be a list of nonempty strings")
        return cls(
            recipe_id=_text("recipe_id", recipe_id),
            display_name=_text(f"recipes.{recipe_id}.display_name", values.get("display_name")),
            species=_text(f"recipes.{recipe_id}.species", values.get("species")),
            cut=_text(f"recipes.{recipe_id}.cut", values.get("cut")),
            process_state=_text(f"recipes.{recipe_id}.process_state", values.get("process_state")),
            geometry=ProductGeometry.from_mapping(f"recipes.{recipe_id}.geometry", values.get("geometry")),
            mass_kg=NumericRange.from_mapping(f"recipes.{recipe_id}.mass_kg", values.get("mass_kg")),
            mechanics=ProductMechanics.from_mapping(f"recipes.{recipe_id}.mechanics", values.get("mechanics")),
            required_tray_orientation=_text(
                f"recipes.{recipe_id}.required_tray_orientation", values.get("required_tray_orientation")
            ),
            evidence=tuple(item.strip() for item in evidence),
            assumptions=tuple(item.strip() for item in assumptions),
        )

    def to_spawn_recipe(self) -> ProductRecipe:
        """Convert the catalog profile into the existing scenario recipe contract."""

        return ProductRecipe(
            recipe_id=self.recipe_id,
            length_min_m=self.geometry.length_m.minimum,
            length_max_m=self.geometry.length_m.maximum,
            width_min_m=self.geometry.width_m.minimum,
            width_max_m=self.geometry.width_m.maximum,
            height_min_m=self.geometry.height_m.minimum,
            height_max_m=self.geometry.height_m.maximum,
            mass_min_kg=self.mass_kg.minimum,
            mass_max_kg=self.mass_kg.maximum,
            compliance_min=self.mechanics.compliance_index.minimum,
            compliance_max=self.mechanics.compliance_index.maximum,
        )


@dataclass(frozen=True)
class ProductCatalog:
    version: int
    profiles: Mapping[str, ProductProfile]

    def get(self, recipe_id: str) -> ProductProfile:
        try:
            return self.profiles[recipe_id]
        except KeyError as exc:
            available = ", ".join(sorted(self.profiles))
            raise ValueError(f"Unknown product recipe {recipe_id!r}. Available recipes: {available}") from exc


def load_product_catalog(path: str | Path = DEFAULT_CATALOG_PATH) -> ProductCatalog:
    with Path(path).open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    root = _mapping("catalog", raw)
    version = root.get("catalog_version")
    if not isinstance(version, int) or isinstance(version, bool) or version <= 0:
        raise ValueError("catalog_version must be a positive integer")
    recipes = _mapping("recipes", root.get("recipes"))
    if not recipes:
        raise ValueError("recipes must not be empty")
    profiles = {str(recipe_id): ProductProfile.from_mapping(str(recipe_id), value) for recipe_id, value in recipes.items()}
    return ProductCatalog(version=version, profiles=profiles)
