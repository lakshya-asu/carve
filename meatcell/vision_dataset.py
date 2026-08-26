"""Deterministic scene schedule and contracts for synthetic vision data."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import random
from typing import Iterable


DATASET_SCHEMA_VERSION = 3
DATASET_CLASS_NAMES = ("meat_workpiece",)
DATASET_ZONES = ("moving_belt", "solution_b_buffer")
DATASET_SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class DatasetScene:
    scene_id: str
    scene_seed: int
    recipe_id: str
    zone: str
    split: str
    frame_count: int
    instance_count: int
    negative: bool

    def __post_init__(self) -> None:
        if not self.scene_id or not self.recipe_id:
            raise ValueError("Scene and recipe identifiers must not be blank")
        if self.zone not in DATASET_ZONES or self.split not in DATASET_SPLITS:
            raise ValueError("Scene zone or split is invalid")
        if self.frame_count <= 0 or not 0 <= self.instance_count <= 4:
            raise ValueError("Scene frame and instance counts are invalid")
        if self.negative != (self.instance_count == 0):
            raise ValueError("Negative scenes must contain zero workpieces")


def _stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _split_counts(scene_count: int) -> dict[str, int]:
    if scene_count <= 0:
        return {name: 0 for name in DATASET_SPLITS}
    if scene_count < 3:
        return {"train": scene_count, "val": 0, "test": 0}
    val = max(1, round(scene_count * 0.15))
    test = max(1, round(scene_count * 0.15))
    train = scene_count - val - test
    if train < 1:
        train = 1
        if val >= test and val > 1:
            val -= 1
        else:
            test -= 1
    return {"train": train, "val": val, "test": test}


def build_scene_schedule(
    *,
    samples: int,
    frames_per_scene: int,
    recipe_ids: Iterable[str],
    seed: int,
    negative_fraction: float = 0.15,
) -> tuple[DatasetScene, ...]:
    """Build a grouped and stratified scene schedule.

    Every frame from one scene stays in one split. Recipe and operating zone
    strata are assigned independently so validation and test contain all
    represented conditions when each stratum has at least three scenes.
    """

    recipes = tuple(sorted(set(recipe_ids)))
    if samples <= 0 or frames_per_scene <= 0:
        raise ValueError("Samples and frames per scene must be positive")
    if not recipes or any(not value.strip() for value in recipes):
        raise ValueError("At least one nonempty recipe identifier is required")
    if not 0.0 <= negative_fraction < 1.0:
        raise ValueError("Negative fraction must be in [0, 1)")

    scene_count = math.ceil(samples / frames_per_scene)
    raw: list[dict[str, object]] = []
    remaining = samples
    for scene_index in range(scene_count):
        recipe_id = recipes[scene_index % len(recipes)]
        zone = DATASET_ZONES[(scene_index // len(recipes)) % len(DATASET_ZONES)]
        frame_count = min(frames_per_scene, remaining)
        remaining -= frame_count
        scene_seed = _stable_seed(seed, recipe_id, zone, scene_index)
        raw.append(
            {
                "scene_index": scene_index,
                "scene_id": f"scene-{scene_index:05d}-{recipe_id}-{zone}",
                "scene_seed": scene_seed,
                "recipe_id": recipe_id,
                "zone": zone,
                "frame_count": frame_count,
            }
        )

    split_for_index: dict[int, str] = {}
    for recipe_id in recipes:
        for zone in DATASET_ZONES:
            indexes = [
                int(item["scene_index"])
                for item in raw
                if item["recipe_id"] == recipe_id and item["zone"] == zone
            ]
            random.Random(_stable_seed(seed, recipe_id, zone, "split")).shuffle(indexes)
            counts = _split_counts(len(indexes))
            cursor = 0
            for split in DATASET_SPLITS:
                for index in indexes[cursor : cursor + counts[split]]:
                    split_for_index[index] = split
                cursor += counts[split]

    if scene_count >= len(DATASET_SPLITS):
        for missing_split in DATASET_SPLITS:
            if missing_split in split_for_index.values():
                continue
            donor_counts = {
                split: sum(value == split for value in split_for_index.values())
                for split in DATASET_SPLITS
            }
            donor_split = max(DATASET_SPLITS, key=lambda split: (donor_counts[split], split == "train"))
            candidates = [index for index, split in split_for_index.items() if split == donor_split]
            candidates.sort(key=lambda index: _stable_seed(seed, "global-split-rebalance", missing_split, index))
            split_for_index[candidates[0]] = missing_split

    negative_count = round(scene_count * negative_fraction)
    negative_candidates = list(range(scene_count))
    random.Random(_stable_seed(seed, "negatives")).shuffle(negative_candidates)
    negative_indexes = set(negative_candidates[:negative_count])

    scenes = []
    for item in raw:
        scene_index = int(item["scene_index"])
        negative = scene_index in negative_indexes
        rng = random.Random(int(item["scene_seed"]))
        scenes.append(
            DatasetScene(
                scene_id=str(item["scene_id"]),
                scene_seed=int(item["scene_seed"]),
                recipe_id=str(item["recipe_id"]),
                zone=str(item["zone"]),
                split=split_for_index[scene_index],
                frame_count=int(item["frame_count"]),
                instance_count=0 if negative else rng.randint(1, 4),
                negative=negative,
            )
        )
    return tuple(scenes)


def schedule_summary(scenes: Iterable[DatasetScene]) -> dict[str, object]:
    values = tuple(scenes)
    return {
        "scenes": len(values),
        "frames": sum(item.frame_count for item in values),
        "negative_scenes": sum(item.negative for item in values),
        "split_frames": {
            split: sum(item.frame_count for item in values if item.split == split)
            for split in DATASET_SPLITS
        },
        "recipe_frames": {
            recipe: sum(item.frame_count for item in values if item.recipe_id == recipe)
            for recipe in sorted({item.recipe_id for item in values})
        },
        "zone_frames": {
            zone: sum(item.frame_count for item in values if item.zone == zone)
            for zone in DATASET_ZONES
        },
    }
