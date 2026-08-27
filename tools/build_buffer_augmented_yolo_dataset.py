"""Build a combined conveyor and buffer-view YOLO26 segmentation dataset.

The buffer source image must be rendered by Isaac Sim. Its label is derived
from the known reference-product material color, then reviewed through saved
overlay images. This is synthetic domain adaptation, not real-data training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dataset", default="results/yolo/dataset_v2")
    parser.add_argument("--buffer-image", default="results/scene2_integrated_b_v10/buffer_rgb.png")
    parser.add_argument("--output", default="results/yolo/dataset_v4_buffer")
    parser.add_argument("--count", type=int, default=80)
    parser.add_argument("--seed", type=int, default=2601)
    return parser.parse_args()


def inside_project(path: Path) -> bool:
    return path == PROJECT_ROOT or PROJECT_ROOT in path.parents


def main() -> int:
    args = parse_args()
    import cv2
    import numpy as np

    base = (PROJECT_ROOT / args.base_dataset).resolve()
    source_path = (PROJECT_ROOT / args.buffer_image).resolve()
    output = (PROJECT_ROOT / args.output).resolve()
    if not all(inside_project(path) for path in (base, source_path, output)):
        raise ValueError("Every dataset path must remain inside the project")
    if not (base / "dataset.yaml").is_file() or not source_path.is_file():
        raise FileNotFoundError("Base dataset or rendered buffer image is missing")
    if args.count < 20:
        raise ValueError("At least 20 buffer variants are required")

    for split in ("train", "val"):
        (output / "images" / split).mkdir(parents=True, exist_ok=True)
        (output / "labels" / split).mkdir(parents=True, exist_ok=True)
        for path in sorted((base / "images" / split).glob("*.png")):
            shutil.copy2(path, output / "images" / split / path.name)
        for path in sorted((base / "labels" / split).glob("*.txt")):
            shutil.copy2(path, output / "labels" / split / path.name)

    source_bgr = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
    if source_bgr is None:
        raise RuntimeError("OpenCV could not read the rendered buffer image")
    source_rgb = cv2.cvtColor(source_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    red, green, blue = source_rgb[..., 0], source_rgb[..., 1], source_rgb[..., 2]
    source_mask = (
        (red > 0.45)
        & (red > green * 1.45)
        & (red > blue * 1.35)
        & (green < 0.55)
        & (blue < 0.60)
    ).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(source_mask, connectivity=8)
    if count <= 1:
        raise RuntimeError("The rendered buffer image contains no labelable product component")
    selected = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    source_mask = (labels == selected).astype(np.uint8) * 255
    if int(np.count_nonzero(source_mask)) < 3000:
        raise RuntimeError("The rendered product mask is unexpectedly small")

    height, width = source_mask.shape
    rng = random.Random(args.seed)
    records = []
    for index in range(args.count):
        angle = rng.uniform(-12.0, 12.0)
        scale = rng.uniform(0.72, 1.05)
        shift_x = rng.uniform(-55.0, 55.0)
        shift_y = rng.uniform(-45.0, 45.0)
        matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), angle, scale)
        matrix[:, 2] += (shift_x, shift_y)
        image = cv2.warpAffine(
            source_bgr,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        mask = cv2.warpAffine(
            source_mask,
            matrix,
            (width, height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        gain = rng.uniform(0.82, 1.18)
        bias = rng.uniform(-12.0, 12.0)
        image = np.clip(image.astype(np.float32) * gain + bias, 0, 255).astype(np.uint8)
        if rng.random() < 0.65:
            image = cv2.GaussianBlur(image, (3, 3), rng.uniform(0.1, 0.8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(contours, key=cv2.contourArea)
        epsilon = 0.003 * cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
        if len(polygon) < 4 or cv2.contourArea(contour) < 2000:
            raise RuntimeError(f"Invalid transformed product mask at variant {index}")
        split = "val" if index % 5 == 0 else "train"
        stem = f"isaac_buffer_{index:04d}"
        cv2.imwrite(str(output / "images" / split / f"{stem}.png"), image)
        values = ["0"]
        for x_value, y_value in polygon:
            values.extend((f"{x_value / width:.8f}", f"{y_value / height:.8f}"))
        (output / "labels" / split / f"{stem}.txt").write_text(" ".join(values) + "\n", encoding="utf-8")
        records.append({"file": f"images/{split}/{stem}.png", "angle_deg": angle, "scale": scale})

    overlay = source_bgr.copy()
    overlay[source_mask.astype(bool)] = (
        0.45 * overlay[source_mask.astype(bool)] + 0.55 * np.asarray((183, 235, 36))
    ).astype(np.uint8)
    cv2.imwrite(str(output / "buffer_label_overlay.png"), overlay)
    (output / "dataset.yaml").write_text(
        f"path: {output.as_posix()}\ntrain: images/train\nval: images/val\nnames:\n  0: meat_reference\n",
        encoding="utf-8",
    )
    metadata = {
        "schema_version": 1,
        "seed": args.seed,
        "base_dataset": str(base),
        "buffer_source": str(source_path),
        "buffer_source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "buffer_variants": args.count,
        "train_images": len(tuple((output / "images" / "train").glob("*.png"))),
        "val_images": len(tuple((output / "images" / "val").glob("*.png"))),
        "notice": "Synthetic Isaac Sim reference geometry only. No real meat images were used.",
        "records": records,
    }
    (output / "dataset_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in metadata.items() if key != "records"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
