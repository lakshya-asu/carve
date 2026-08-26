"""Generate grouped YOLO26 segmentation data from actual Isaac annotations."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import traceback
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from meatcell.product_profiles import ProductProfile, load_product_catalog
from meatcell.vision_dataset import (
    DATASET_CLASS_NAMES,
    DATASET_SCHEMA_VERSION,
    DATASET_SPLITS,
    DATASET_ZONES,
    DatasetScene,
    build_scene_schedule,
    schedule_summary,
)

from isaac_sim.stage_builder import product_prism_mesh_data


MIN_YOLO_POLYGON_IOU = 0.95


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--frames-per-scene", type=int, default=4)
    parser.add_argument("--seed", type=int, default=2601)
    parser.add_argument("--negative-fraction", type=float, default=0.15)
    parser.add_argument("--output", default="results/yolo/dataset_v3_audit")
    parser.add_argument("--preview-count", type=int, default=18)
    parser.add_argument("--save-depth", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def mask_to_polygon(mask: Any) -> tuple[list[tuple[float, float]], float]:
    """Convert one crisp Isaac instance mask to a YOLO polygon and audit IoU."""

    import cv2
    import numpy as np

    binary = np.asarray(mask, dtype=np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [contour for contour in contours if len(contour) >= 3 and cv2.contourArea(contour) >= 1.0]
    if not contours:
        return [], 0.0
    contours.sort(key=cv2.contourArea, reverse=True)
    ordered = [contours.pop(0).reshape(-1, 2)]
    while contours:
        previous = ordered[-1]
        nearest_index = min(
            range(len(contours)),
            key=lambda index: float(
                np.min(((previous[:, None, :] - contours[index].reshape(-1, 2)[None, :, :]) ** 2).sum(-1))
            ),
        )
        ordered.append(contours.pop(nearest_index).reshape(-1, 2))
    if len(ordered) == 1:
        merged = ordered[0]
    else:
        connection_indexes: list[list[int]] = [[] for _ in ordered]
        for index in range(1, len(ordered)):
            distances = ((ordered[index - 1][:, None, :] - ordered[index][None, :, :]) ** 2).sum(-1)
            previous_index, current_index = np.unravel_index(np.argmin(distances), distances.shape)
            connection_indexes[index - 1].append(int(previous_index))
            connection_indexes[index].append(int(current_index))
        parts = []
        for pass_index in range(2):
            if pass_index == 0:
                for index, connections in enumerate(connection_indexes):
                    if len(connections) == 2 and connections[0] > connections[1]:
                        connections = connections[::-1]
                        ordered[index] = ordered[index][::-1, :]
                    ordered[index] = np.roll(ordered[index], -connections[0], axis=0)
                    ordered[index] = np.concatenate([ordered[index], ordered[index][:1]])
                    if index in {0, len(ordered) - 1}:
                        parts.append(ordered[index])
                    else:
                        stop = connections[1] - connections[0]
                        parts.append(ordered[index][: stop + 1])
            else:
                for index in range(len(ordered) - 1, -1, -1):
                    if index not in {0, len(ordered) - 1}:
                        connections = connection_indexes[index]
                        parts.append(ordered[index][abs(connections[1] - connections[0]) :])
        merged = np.concatenate(parts)
    contour = merged.reshape(-1, 1, 2).astype(np.int32)
    height, width = binary.shape
    points = [
        (
            min(1.0, max(0.0, float(point[0][0]) / width)),
            min(1.0, max(0.0, float(point[0][1]) / height)),
        )
        for point in contour
    ]
    polygon_mask = np.zeros_like(binary)
    cv2.fillPoly(polygon_mask, [contour], 1)
    intersection = int(np.count_nonzero((polygon_mask > 0) & (binary > 0)))
    union = int(np.count_nonzero((polygon_mask > 0) | (binary > 0)))
    return points, intersection / union if union else 0.0


def apply_camera_effects(rgb: Any, *, rng: random.Random, belt_speed_mps: float) -> tuple[Any, dict[str, float | int]]:
    """Inject a documented camera exposure and noise approximation."""

    import cv2
    import numpy as np

    rgb8 = np.asarray(rgb)
    if rgb8.dtype != np.uint8:
        scale = 255.0 if rgb8.max(initial=0.0) <= 1.0 else 1.0
        rgb8 = np.clip(rgb8 * scale, 0, 255).astype(np.uint8)
    rgb8 = np.ascontiguousarray(rgb8[..., :3])
    exposure_s = rng.choice((0.00025, 0.0005, 0.001, 0.002, 0.004))
    focal_px = 18.0 / 20.955 * 640.0
    approximate_distance_m = 2.9
    blur_pixels = belt_speed_mps * exposure_s * focal_px / approximate_distance_m
    blur_kernel = max(1, int(round(blur_pixels)))
    if blur_kernel > 1:
        blur_kernel += 1 if blur_kernel % 2 == 0 else 0
        rgb8 = cv2.blur(rgb8, (blur_kernel, 1))
    noise_sigma = rng.uniform(0.0, 4.0)
    if noise_sigma > 0.0:
        noise_rng = np.random.default_rng(rng.getrandbits(64))
        noise = noise_rng.normal(0.0, noise_sigma, rgb8.shape)
        rgb8 = np.clip(rgb8.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    return rgb8, {
        "exposure_time_s": exposure_s,
        "approximated_motion_blur_px": blur_pixels,
        "applied_horizontal_blur_kernel_px": blur_kernel,
        "rgb_noise_sigma_8bit": noise_sigma,
    }


def set_product_geometry(
    adapter: Any,
    product_id: str,
    profile: ProductProfile,
    dimensions_m: tuple[float, float, float],
    taper_ratio: float,
    color: tuple[float, float, float],
    mass_kg: float,
) -> None:
    from pxr import Gf, UsdGeom, UsdPhysics

    path = adapter.product_paths[product_id]
    points, counts, indices = product_prism_mesh_data(
        profile.geometry.shape_family,
        dimensions_m[0],
        dimensions_m[1],
        dimensions_m[2],
        taper_ratio,
    )
    mesh = UsdGeom.Mesh(adapter.stage.GetPrimAtPath(f"{path}/geometry"))
    mesh.GetPointsAttr().Set([Gf.Vec3f(*point) for point in points])
    mesh.GetFaceVertexCountsAttr().Set(counts)
    mesh.GetFaceVertexIndicesAttr().Set(indices)
    mesh.GetExtentAttr().Set(
        [
            Gf.Vec3f(-dimensions_m[0] / 2.0, -dimensions_m[1] / 2.0, -dimensions_m[2] / 2.0),
            Gf.Vec3f(dimensions_m[0] / 2.0, dimensions_m[1] / 2.0, dimensions_m[2] / 2.0),
        ]
    )
    mesh.GetDisplayColorAttr().Set([Gf.Vec3f(*color)])
    body = adapter.stage.GetPrimAtPath(path)
    UsdPhysics.MassAPI.Apply(body).CreateMassAttr(mass_kg)
    body.GetAttribute("meatcell:nominalLengthM").Set(dimensions_m[0])
    body.GetAttribute("meatcell:nominalWidthM").Set(dimensions_m[1])
    body.GetAttribute("meatcell:nominalHeightM").Set(dimensions_m[2])
    body.GetAttribute("meatcell:nominalMassKg").Set(mass_kg)


def semantic_instances(annotation: dict[str, Any]) -> list[tuple[int, dict[str, str]]]:
    result = []
    labels = annotation.get("info", {}).get("idToLabels", {})
    for raw_id, raw_labels in labels.items():
        if not isinstance(raw_labels, dict) or raw_labels.get("class") != DATASET_CLASS_NAMES[0]:
            continue
        result.append((int(raw_id), {str(key): str(value) for key, value in raw_labels.items()}))
    return sorted(result, key=lambda item: (item[1].get("instance", ""), item[0]))


def visible_semantic_instance_count(annotation: dict[str, Any], *, minimum_pixels: int = 24) -> int:
    import numpy as np

    data = np.asarray(annotation.get("data", []))
    if data.ndim == 3 and data.shape[-1] == 1:
        data = data[..., 0]
    return sum(int(np.count_nonzero(data == semantic_id)) >= minimum_pixels for semantic_id, _ in semantic_instances(annotation))


def semantic_visibility_mask(annotation: dict[str, Any]) -> Any:
    import numpy as np

    data = np.asarray(annotation.get("data", []))
    if data.ndim == 3 and data.shape[-1] == 1:
        data = data[..., 0]
    visible = np.zeros(data.shape, dtype=bool)
    for semantic_id, _ in semantic_instances(annotation):
        visible |= data == semantic_id
    return visible


def read_segmentation_with_retry(annotator: Any, rep: Any, *, attempts: int = 12) -> dict[str, Any]:
    """Wait for Isaac's segmentation render variable to become readable."""

    import numpy as np

    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            annotation = annotator.get_data()
            if isinstance(annotation, dict) and np.asarray(annotation.get("data", [])).size:
                return annotation
        except RuntimeError as exc:
            last_error = exc
        rep.orchestrator.step(delta_time=0.0)
    detail = f": {last_error}" if last_error is not None else ""
    raise RuntimeError(f"Isaac segmentation render variable did not become readable{detail}")


def prepare_output(output: Path, *, save_depth: bool) -> None:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Dataset output already exists and is not empty: {output}")
    for split in DATASET_SPLITS:
        for kind in ("images", "labels", "masks"):
            (output / kind / split).mkdir(parents=True, exist_ok=True)
        if save_depth:
            (output / "depth" / split).mkdir(parents=True, exist_ok=True)
    (output / "previews").mkdir(parents=True, exist_ok=True)
    (output / "stages").mkdir(parents=True, exist_ok=True)


def configure_scene(adapter: Any, scene: DatasetScene, profile: ProductProfile) -> dict[str, dict[str, Any]]:
    import numpy as np

    from meatcell.contracts import Transform

    rng = random.Random(scene.scene_seed)
    base_colors = {
        "beef": (0.72, 0.055, 0.045),
        "pork": (0.82, 0.19, 0.17),
        "chicken": (0.86, 0.34, 0.22),
    }
    dome = adapter.stage.GetPrimAtPath("/World/Lights/Dome").GetAttribute("inputs:intensity")
    key = adapter.stage.GetPrimAtPath("/World/Lights/Key").GetAttribute("inputs:intensity")
    dome.Set(rng.uniform(300.0, 1_050.0))
    key.Set(rng.uniform(1_200.0, 5_500.0))
    robot_targets = {
        "x_axis": rng.uniform(0.62, 1.16),
        "y_axis": rng.uniform(0.08, 0.34),
        "z_axis": rng.uniform(0.28, 0.65),
        "wrist_yaw": rng.uniform(-0.70, 0.70),
        "finger_left": rng.uniform(-0.045, 0.0),
        "finger_right": rng.uniform(0.0, 0.045),
    }
    joint_targets = np.asarray([robot_targets.get(name, 0.0) for name in adapter.joint_names], dtype=np.float32)
    adapter.robot.set_joint_positions(joint_targets)
    adapter.robot.set_joint_velocities(np.zeros_like(joint_targets))

    active = sorted(adapter.products)[: scene.instance_count]
    metadata: dict[str, dict[str, Any]] = {}
    for product_index, product_id in enumerate(sorted(adapter.products)):
        if product_id not in active:
            adapter.set_product_pose(product_id, Transform.planar(-9.0 - product_index, 0.0, 0.20, 0.0))
            adapter.set_product_velocity(product_id, (0.0, 0.0, 0.0))
            continue
        length = rng.uniform(profile.geometry.length_m.minimum, profile.geometry.length_m.maximum)
        width = rng.uniform(profile.geometry.width_m.minimum, profile.geometry.width_m.maximum)
        height = rng.uniform(profile.geometry.height_m.minimum, profile.geometry.height_m.maximum)
        mass = rng.uniform(profile.mass_kg.minimum, profile.mass_kg.maximum)
        taper = rng.uniform(profile.geometry.taper_ratio.minimum, profile.geometry.taper_ratio.maximum)
        base = base_colors.get(profile.species, (0.72, 0.055, 0.045))
        color = tuple(min(0.95, max(0.015, channel * rng.uniform(0.75, 1.25))) for channel in base)
        set_product_geometry(adapter, product_id, profile, (length, width, height), taper, color, mass)
        if scene.zone == "moving_belt":
            moving_slots = ((-0.10, 0.18), (0.38, -0.17), (0.84, 0.18), (1.28, -0.17))
            slot_x, slot_y = moving_slots[product_index]
            x_m = slot_x + rng.uniform(-0.06, 0.06)
            y_m = slot_y + rng.uniform(-0.035, 0.035)
            z_m = 0.04 + height / 2.0 + 0.002
            velocity = (2.24, 0.0, 0.0)
        else:
            buffer_slots = ((1.66, -0.46), (1.96, -0.46), (1.66, -0.72), (1.96, -0.72))
            slot_x, slot_y = buffer_slots[product_index]
            x_m = slot_x + rng.uniform(-0.035, 0.035)
            y_m = slot_y + rng.uniform(-0.025, 0.025)
            z_m = 0.10 + height / 2.0 + 0.002
            velocity = (0.0, 0.0, 0.0)
        yaw = rng.uniform(-0.25, 0.25) if product_index == 0 else rng.uniform(-math.pi / 2.0, math.pi / 2.0)
        adapter.set_product_pose(product_id, Transform.planar(x_m, y_m, z_m, yaw))
        adapter.set_product_velocity(product_id, velocity)
        metadata[product_id] = {
            "instance_label": adapter.product_paths[product_id].rsplit("/", 1)[-1],
            "dimensions_m": [length, width, height],
            "mass_kg": mass,
            "taper_ratio": taper,
            "initial_pose_world": {"x_m": x_m, "y_m": y_m, "z_m": z_m, "yaw_rad": yaw},
            "velocity_mps": list(velocity),
            "color_rgb": list(color),
        }
    adapter.set_plc_inputs(conveyor_speed_mps=2.24 if scene.zone == "moving_belt" else 0.0, recipe_id=profile.recipe_id)
    return metadata


def main() -> int:
    args = parse_args()
    if args.samples < 24:
        raise ValueError("At least 24 Isaac frames are required")
    if args.preview_count < 0:
        raise ValueError("Preview count must be nonnegative")
    output = (PROJECT_ROOT / args.output).resolve()
    if Path(args.output).is_absolute() or PROJECT_ROOT not in output.parents:
        raise ValueError("Dataset output must stay inside the project")
    catalog = load_product_catalog()
    scenes = build_scene_schedule(
        samples=args.samples,
        frames_per_scene=args.frames_per_scene,
        recipe_ids=catalog.profiles,
        seed=args.seed,
        negative_fraction=args.negative_fraction,
    )
    payload: dict[str, Any] = {"passed": False}
    app = None
    adapter = None
    frame_records: list[dict[str, Any]] = []
    try:
        prepare_output(output, save_depth=args.save_depth)
        from isaacsim import SimulationApp

        app = SimulationApp({"headless": args.headless, "renderer": "RaytracedLighting", "width": 640, "height": 480})
        import numpy as np
        from PIL import Image, ImageDraw

        from isaac_sim.adapter import IsaacSimulatorAdapter
        from meatcell.contracts import Transform
        import omni.replicator.core as rep

        preview_written = 0
        preview_conditions: set[tuple[str, str, bool]] = set()
        frame_index = 0
        polygon_ious: list[float] = []
        source_polygon_ious: list[float] = []
        mask_pixels: list[int] = []
        depth_valid_fractions: list[float] = []
        positive_without_labels = 0
        negative_with_labels = 0
        recipe_scene_groups: dict[str, list[DatasetScene]] = {}
        for scene in scenes:
            recipe_scene_groups.setdefault(scene.recipe_id, []).append(scene)

        for recipe_id in sorted(recipe_scene_groups):
            profile = catalog.get(recipe_id)
            adapter = IsaacSimulatorAdapter(app, physics_hz=240, render_hz=60, product_profile=profile)
            adapter.create_cell("b")
            if len(adapter.products) != 4:
                raise RuntimeError("Vision dataset stage must contain exactly four workpiece references")
            adapter.save_stage(str(output / "stages" / f"{recipe_id}.usda"))
            render_product = rep.create.render_product(adapter.paths.overhead_camera, (640, 480))
            rgb_annotator = rep.annotators.get("rgb")
            depth_annotator = rep.annotators.get("distance_to_image_plane")
            instance_annotator = rep.annotators.get(
                "semantic_segmentation",
                init_params={
                    "colorize": False,
                    "semanticTypes": ["class", "recipe", "instance"],
                },
            )
            for annotator in (rgb_annotator, depth_annotator, instance_annotator):
                annotator.attach(render_product)
            for _ in range(6):
                rep.orchestrator.step(delta_time=0.0)
                try:
                    rgb_annotator.get_data()
                    depth_annotator.get_data()
                except RuntimeError:
                    pass
                read_segmentation_with_retry(instance_annotator, rep)

            for scene in recipe_scene_groups[recipe_id]:
                product_metadata = configure_scene(adapter, scene, profile)
                rep.orchestrator.step(delta_time=0.0)
                read_segmentation_with_retry(instance_annotator, rep)
                for local_frame in range(scene.frame_count):
                    rep.orchestrator.step(delta_time=1.0 / adapter.render_hz)
                    annotation = read_segmentation_with_retry(instance_annotator, rep)
                    previous_visibility = None
                    stable_reads = 0
                    for _ in range(10):
                        visible_count = visible_semantic_instance_count(annotation)
                        visibility = semantic_visibility_mask(annotation)
                        condition_valid = (scene.negative and visible_count == 0) or (
                            not scene.negative and visible_count > 0
                        )
                        if condition_valid and previous_visibility is not None and np.array_equal(
                            visibility, previous_visibility
                        ):
                            stable_reads += 1
                        else:
                            stable_reads = 1 if condition_valid else 0
                        if stable_reads >= 2:
                            break
                        previous_visibility = visibility.copy() if condition_valid else None
                        rep.orchestrator.step(delta_time=0.0)
                        annotation = read_segmentation_with_retry(instance_annotator, rep)
                    rgb = rgb_annotator.get_data()
                    depth = depth_annotator.get_data()
                    if not isinstance(annotation, dict) or "data" not in annotation:
                        raise RuntimeError("Isaac overhead camera did not publish instance segmentation")
                    instance_data = np.asarray(annotation["data"])
                    if instance_data.ndim == 3 and instance_data.shape[-1] == 1:
                        instance_data = instance_data[..., 0]
                    depth32 = np.asarray(depth, dtype=np.float32)
                    effect_rng = random.Random(scene.scene_seed + local_frame * 1009)
                    rgb8, camera_effects = apply_camera_effects(
                        rgb,
                        rng=effect_rng,
                        belt_speed_mps=2.24 if scene.zone == "moving_belt" else 0.0,
                    )
                    stem = f"isaac_v3_{frame_index:06d}"
                    labels: list[str] = []
                    polygons: list[list[tuple[float, float]]] = []
                    audit_mask = np.zeros(instance_data.shape, dtype=np.uint8)
                    detected_instances = []
                    omitted_yolo_instances = 0
                    for output_id, (semantic_id, semantic_labels) in enumerate(semantic_instances(annotation), start=1):
                        component = instance_data == semantic_id
                        pixel_count = int(np.count_nonzero(component))
                        if pixel_count < 24:
                            continue
                        audit_mask[component] = output_id
                        mask_pixels.append(pixel_count)
                        polygon, polygon_iou = mask_to_polygon(component)
                        source_polygon_ious.append(polygon_iou)
                        emitted_to_yolo = len(polygon) >= 3 and polygon_iou >= MIN_YOLO_POLYGON_IOU
                        detected_instances.append(
                            {
                                "semantic_id": semantic_id,
                                "semantic_labels": semantic_labels,
                                "mask_pixels": pixel_count,
                                "polygon_points": len(polygon),
                                "polygon_mask_iou": polygon_iou,
                                "emitted_to_yolo": emitted_to_yolo,
                            }
                        )
                        if not emitted_to_yolo:
                            omitted_yolo_instances += 1
                            continue
                        if len(polygon) < 3:
                            continue
                        coordinates = " ".join(f"{value:.8f}" for point in polygon for value in point)
                        labels.append(f"0 {coordinates}")
                        polygons.append(polygon)
                        polygon_ious.append(polygon_iou)
                    if scene.negative and labels:
                        negative_with_labels += 1
                    if not scene.negative and not labels:
                        positive_without_labels += 1
                    split = scene.split
                    image_path = output / "images" / split / f"{stem}.png"
                    label_path = output / "labels" / split / f"{stem}.txt"
                    mask_path = output / "masks" / split / f"{stem}.png"
                    Image.fromarray(rgb8).save(image_path)
                    label_path.write_text("\n".join(labels) + ("\n" if labels else ""), encoding="utf-8")
                    Image.fromarray(audit_mask).save(mask_path)
                    depth_path = None
                    if args.save_depth:
                        depth_path = output / "depth" / split / f"{stem}.npz"
                        np.savez_compressed(depth_path, depth_m=depth32)
                    valid_depth = np.isfinite(depth32) & (depth32 > 0.0)
                    depth_valid_fraction = float(np.count_nonzero(valid_depth) / valid_depth.size)
                    depth_valid_fractions.append(depth_valid_fraction)
                    preview_condition = (recipe_id, scene.zone, scene.negative)
                    if preview_written < args.preview_count and preview_condition not in preview_conditions:
                        preview = Image.fromarray(rgb8).copy()
                        draw = ImageDraw.Draw(preview)
                        for polygon in polygons:
                            pixels = [(round(x * rgb8.shape[1]), round(y * rgb8.shape[0])) for x, y in polygon]
                            if pixels:
                                draw.line([*pixels, pixels[0]], fill=(40, 255, 110), width=3)
                        preview.save(output / "previews" / f"{stem}_{recipe_id}_{scene.zone}.png")
                        preview_written += 1
                        preview_conditions.add(preview_condition)
                    frame_record = {
                        "schema_version": DATASET_SCHEMA_VERSION,
                        "frame_index": frame_index,
                        "frame_id": stem,
                        "scene_id": scene.scene_id,
                        "scene_seed": scene.scene_seed,
                        "scene_frame_index": local_frame,
                        "split": split,
                        "recipe_id": recipe_id,
                        "species": profile.species,
                        "shape_family": profile.geometry.shape_family,
                        "zone": scene.zone,
                        "negative": scene.negative,
                        "configured_instance_count": scene.instance_count,
                        "visible_source_instance_count": len(detected_instances),
                        "yolo_labeled_instance_count": len(labels),
                        "visible_labeled_instance_count": len(labels),
                        "omitted_yolo_instance_count": omitted_yolo_instances,
                        "sim_time_ns": int(round(float(adapter.world.current_time) * 1_000_000_000)),
                        "conveyor_speed_mps": adapter.conveyor_speed_mps,
                        "camera_effects": camera_effects,
                        "depth_valid_fraction": depth_valid_fraction,
                        "instances": detected_instances,
                        "configured_products": product_metadata,
                        "files": {
                            "image": str(image_path.relative_to(output)).replace("\\", "/"),
                            "label": str(label_path.relative_to(output)).replace("\\", "/"),
                            "mask": str(mask_path.relative_to(output)).replace("\\", "/"),
                            "depth": str(depth_path.relative_to(output)).replace("\\", "/") if depth_path else None,
                        },
                        "hashes": {
                            "rgb_sha256": hashlib.sha256(rgb8.tobytes()).hexdigest(),
                            "mask_sha256": hashlib.sha256(audit_mask.tobytes()).hexdigest(),
                            "depth_sha256": hashlib.sha256(depth32.tobytes()).hexdigest(),
                        },
                    }
                    frame_records.append(frame_record)
                    frame_index += 1
            for annotator in (rgb_annotator, depth_annotator, instance_annotator):
                annotator.detach()
            render_product.destroy()
            adapter.close()
            adapter = None

        frame_manifest = output / "frames.jsonl"
        frame_manifest.write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in frame_records),
            encoding="utf-8",
        )
        data_yaml = output / "dataset.yaml"
        data_yaml.write_text(
            "\n".join(
                [
                    f"path: {output.as_posix()}",
                    "train: images/train",
                    "val: images/val",
                    "test: images/test",
                    "names:",
                    "  0: meat_workpiece",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        summary = schedule_summary(scenes)
        visible_labels = sum(int(item["visible_labeled_instance_count"]) for item in frame_records)
        visible_source_instances = sum(int(item["visible_source_instance_count"]) for item in frame_records)
        omitted_yolo_instances = sum(int(item["omitted_yolo_instance_count"]) for item in frame_records)
        gates = {
            "exact_frame_count": len(frame_records) == args.samples,
            "all_recipes_present": set(item["recipe_id"] for item in frame_records) == set(catalog.profiles),
            "all_zones_present": set(item["zone"] for item in frame_records) == set(DATASET_ZONES),
            "all_splits_present": set(item["split"] for item in frame_records) == set(DATASET_SPLITS),
            "scene_split_isolation": all(
                len({item["split"] for item in frame_records if item["scene_id"] == scene.scene_id}) == 1
                for scene in scenes
            ),
            "positive_frames_have_labels": positive_without_labels == 0,
            "negative_frames_have_no_labels": negative_with_labels == 0,
            "actual_instance_masks_nonempty": visible_labels > 0 and bool(mask_pixels),
            "polygon_mask_iou_min_0_95": bool(polygon_ious) and min(polygon_ious) >= MIN_YOLO_POLYGON_IOU,
            "rgb_nonempty": all(Path(output / item["files"]["image"]).stat().st_size > 0 for item in frame_records),
            "depth_nonempty": (not args.save_depth)
            or all(Path(output / item["files"]["depth"]).stat().st_size > 0 for item in frame_records),
        }
        payload = {
            "passed": all(gates.values()),
            "schema_version": DATASET_SCHEMA_VERSION,
            "seed": args.seed,
            "samples": args.samples,
            "frames_per_scene": args.frames_per_scene,
            "class_names": list(DATASET_CLASS_NAMES),
            "schedule": summary,
            "visible_labeled_instances": visible_labels,
            "visible_source_instances": visible_source_instances,
            "omitted_yolo_instances_low_polygon_iou": omitted_yolo_instances,
            "positive_frames_without_labels": positive_without_labels,
            "negative_frames_with_labels": negative_with_labels,
            "polygon_mask_iou": {
                "minimum": min(polygon_ious) if polygon_ious else None,
                "p50": percentile(polygon_ious, 0.50),
                "p95": percentile(polygon_ious, 0.95),
            },
            "source_polygon_iou_before_quality_filter": {
                "minimum": min(source_polygon_ious) if source_polygon_ious else None,
                "p50": percentile(source_polygon_ious, 0.50),
                "p95": percentile(source_polygon_ious, 0.95),
            },
            "mask_pixels": {
                "minimum": min(mask_pixels) if mask_pixels else None,
                "p50": percentile([float(value) for value in mask_pixels], 0.50),
                "p95": percentile([float(value) for value in mask_pixels], 0.95),
            },
            "depth_valid_fraction": {
                "minimum": min(depth_valid_fractions) if depth_valid_fractions else None,
                "p50": percentile(depth_valid_fractions, 0.50),
            },
            "label_source": "Isaac Sim semantic segmentation keyed by unique USD instance labels",
            "ground_truth_use": "training labels and test oracle only, never live learned inference",
            "camera_effect_model": "Actual Isaac RGB and depth with documented post-render exposure blur and RGB sensor noise approximation",
            "split_policy": "Grouped by scene and stratified by recipe and operating zone",
            "reference_asset_notice": "Synthetic rigid recipe-shaped meat references. Not real meat data or physical validation.",
            "dataset_yaml": str(data_yaml.resolve()),
            "frame_manifest": str(frame_manifest.resolve()),
            "gates": gates,
        }
        (output / "dataset_metadata.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        payload = {
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        output.mkdir(parents=True, exist_ok=True)
        (output / "failure.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    finally:
        if adapter is not None:
            try:
                adapter.close()
            except Exception:
                pass
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        if app is not None:
            try:
                app.close()
            except SystemExit:
                pass
    return 0 if payload.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
