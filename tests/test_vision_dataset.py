import pytest

from meatcell.vision_dataset import DATASET_SCHEMA_VERSION, build_scene_schedule, schedule_summary


RECIPES = (
    "beef_center_cut_tenderloin",
    "pork_boneless_loin",
    "chicken_breast_fillet",
)


def test_audit_schedule_is_deterministic_grouped_and_stratified() -> None:
    first = build_scene_schedule(samples=200, frames_per_scene=4, recipe_ids=RECIPES, seed=2601)
    second = build_scene_schedule(samples=200, frames_per_scene=4, recipe_ids=RECIPES, seed=2601)
    assert first == second
    assert DATASET_SCHEMA_VERSION == 3
    assert len(first) == 50
    assert sum(item.frame_count for item in first) == 200
    assert all(item.frame_count == 4 for item in first)
    assert {item.split for item in first} == {"train", "val", "test"}
    for recipe in RECIPES:
        for zone in {"moving_belt", "solution_b_buffer"}:
            matching = [item for item in first if item.recipe_id == recipe and item.zone == zone]
            assert {item.split for item in matching} == {"train", "val", "test"}


def test_audit_schedule_has_negatives_and_one_to_four_positive_instances() -> None:
    scenes = build_scene_schedule(samples=200, frames_per_scene=4, recipe_ids=RECIPES, seed=2601)
    negatives = [item for item in scenes if item.negative]
    positives = [item for item in scenes if not item.negative]
    assert len(negatives) == 8
    assert all(item.instance_count == 0 for item in negatives)
    assert all(1 <= item.instance_count <= 4 for item in positives)
    assert {item.instance_count for item in positives} == {1, 2, 3, 4}


def test_schedule_summary_accounts_for_every_frame() -> None:
    scenes = build_scene_schedule(samples=201, frames_per_scene=4, recipe_ids=RECIPES, seed=17)
    summary = schedule_summary(scenes)
    assert summary["frames"] == 201
    assert sum(summary["split_frames"].values()) == 201
    assert sum(summary["recipe_frames"].values()) == 201
    assert sum(summary["zone_frames"].values()) == 201


def test_small_smoke_schedule_keeps_all_splits_present() -> None:
    scenes = build_scene_schedule(samples=24, frames_per_scene=4, recipe_ids=RECIPES, seed=2601)
    assert {item.split for item in scenes} == {"train", "val", "test"}


@pytest.mark.parametrize(
    ("samples", "frames_per_scene", "negative_fraction"),
    [(0, 4, 0.15), (20, 0, 0.15), (20, 4, -0.1), (20, 4, 1.0)],
)
def test_invalid_schedule_requests_are_rejected(samples: int, frames_per_scene: int, negative_fraction: float) -> None:
    with pytest.raises(ValueError):
        build_scene_schedule(
            samples=samples,
            frames_per_scene=frames_per_scene,
            recipe_ids=RECIPES,
            seed=1,
            negative_fraction=negative_fraction,
        )
