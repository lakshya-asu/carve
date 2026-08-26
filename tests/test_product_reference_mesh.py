import pytest

from isaac_sim.stage_builder import (
    product_outline,
    product_prism_mesh_data,
    product_width_scale_at_grasp,
)


@pytest.mark.parametrize(
    "shape_family",
    ["tapered_capsule", "elongated_rounded_prism", "asymmetric_teardrop_slab"],
)
def test_recipe_outline_is_bounded_and_has_visible_area(shape_family: str) -> None:
    outline = product_outline(shape_family, 0.65)
    assert len(outline) >= 8
    assert all(-0.5 <= x <= 0.5 and -0.5 <= y <= 0.5 for x, y in outline)
    signed_double_area = sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(outline, (*outline[1:], outline[0]), strict=True)
    )
    assert abs(signed_double_area) > 0.2


def test_product_prism_has_closed_face_topology() -> None:
    points, counts, indices = product_prism_mesh_data(
        "tapered_capsule",
        length_m=0.45,
        width_m=0.11,
        height_m=0.075,
        taper_ratio=0.75,
    )
    outline_count = len(product_outline("tapered_capsule", 0.75))
    assert len(points) == outline_count * 2
    assert len(counts) == outline_count + 2
    assert sum(counts) == len(indices)
    assert min(index for index in indices) == 0
    assert max(index for index in indices) == len(points) - 1
    assert max(abs(point[0]) for point in points) <= 0.45 / 2.0
    assert max(abs(point[1]) for point in points) <= 0.11 / 2.0
    assert sorted({point[2] for point in points}) == pytest.approx([-0.075 / 2.0, 0.075 / 2.0])


def test_unknown_shape_uses_rectangular_fallback() -> None:
    outline = product_outline("future_cut", 0.8)
    assert outline == ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))


@pytest.mark.parametrize(
    ("shape_family", "taper_ratio", "expected_range"),
    [
        ("tapered_capsule", 0.75, (0.78, 0.84)),
        ("elongated_rounded_prism", 0.85, (0.90, 1.00)),
        ("asymmetric_teardrop_slab", 0.55, (0.55, 0.65)),
        ("future_cut", 0.8, (0.99, 1.00)),
    ],
)
def test_central_grasp_width_matches_reference_outline(
    shape_family: str,
    taper_ratio: float,
    expected_range: tuple[float, float],
) -> None:
    scale = product_width_scale_at_grasp(shape_family, taper_ratio)
    assert expected_range[0] <= scale <= expected_range[1]


@pytest.mark.parametrize("dimensions", [(0.0, 0.1, 0.1), (0.1, -0.1, 0.1)])
def test_product_prism_rejects_invalid_dimensions(dimensions: tuple[float, float, float]) -> None:
    with pytest.raises(ValueError, match="positive"):
        product_prism_mesh_data("tapered_capsule", *dimensions, taper_ratio=0.8)
