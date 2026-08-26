"""Audit an Isaac generated YOLO dataset without changing it."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output")
    return parser.parse_args()


def decoded_sha256(value: Any) -> str:
    return hashlib.sha256(value.tobytes()).hexdigest()


def main() -> int:
    import numpy as np
    from PIL import Image

    args = parse_args()
    dataset = Path(args.dataset)
    if not dataset.is_absolute():
        dataset = (PROJECT_ROOT / dataset).resolve()
    if PROJECT_ROOT not in dataset.parents:
        raise ValueError("Dataset must be inside the project")
    output = Path(args.output).resolve() if args.output else dataset / "artifact_audit.json"
    metadata_path = dataset / "dataset_metadata.json"
    manifest_path = dataset / "frames.jsonl"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    records = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line]
    errors: list[str] = []
    scene_splits: dict[str, set[str]] = {}
    file_counts = {kind: 0 for kind in ("image", "label", "mask", "depth")}
    label_rows = 0
    nonempty_masks = 0

    if not metadata.get("passed"):
        errors.append("Generator metadata did not pass")
    if len(records) != metadata.get("samples"):
        errors.append("Manifest frame count does not match metadata")
    if not all(metadata.get("gates", {}).values()):
        errors.append("One or more generator gates failed")

    for record in records:
        scene_splits.setdefault(record["scene_id"], set()).add(record["split"])
        resolved: dict[str, Path] = {}
        for kind, relative in record["files"].items():
            if relative is None:
                continue
            path = dataset / relative
            resolved[kind] = path
            file_counts[kind] += 1
            if not path.is_file():
                errors.append(f"Missing or empty {kind} file for {record['frame_id']}")
            elif path.stat().st_size == 0 and (kind != "label" or not record["negative"]):
                errors.append(f"Unexpected empty {kind} file for {record['frame_id']}")
        if any(kind not in resolved for kind in ("image", "label", "mask", "depth")):
            errors.append(f"Incomplete file set for {record['frame_id']}")
            continue
        rgb = np.asarray(Image.open(resolved["image"]).convert("RGB"))
        mask = np.asarray(Image.open(resolved["mask"]))
        depth = np.load(resolved["depth"])["depth_m"]
        if rgb.shape != (480, 640, 3) or mask.shape != (480, 640) or depth.shape != (480, 640):
            errors.append(f"Unexpected sensor shape for {record['frame_id']}")
        if decoded_sha256(rgb) != record["hashes"]["rgb_sha256"]:
            errors.append(f"RGB hash mismatch for {record['frame_id']}")
        if decoded_sha256(mask) != record["hashes"]["mask_sha256"]:
            errors.append(f"Mask hash mismatch for {record['frame_id']}")
        if decoded_sha256(depth) != record["hashes"]["depth_sha256"]:
            errors.append(f"Depth hash mismatch for {record['frame_id']}")
        if np.isfinite(depth).mean() < 0.99 or (depth > 0.0).mean() < 0.99:
            errors.append(f"Invalid depth coverage for {record['frame_id']}")
        mask_nonempty = bool(np.count_nonzero(mask))
        nonempty_masks += int(mask_nonempty)
        if mask_nonempty != (record["visible_source_instance_count"] > 0):
            errors.append(f"Mask visibility mismatch for {record['frame_id']}")
        rows = [line.split() for line in resolved["label"].read_text(encoding="utf-8").splitlines() if line]
        label_rows += len(rows)
        if len(rows) != record["yolo_labeled_instance_count"]:
            errors.append(f"YOLO row count mismatch for {record['frame_id']}")
        if record["negative"] and rows:
            errors.append(f"Negative frame contains labels for {record['frame_id']}")
        if not record["negative"] and not rows:
            errors.append(f"Positive frame has no labels for {record['frame_id']}")
        for row in rows:
            if len(row) < 7 or row[0] != "0" or len(row[1:]) % 2:
                errors.append(f"Invalid YOLO polygon structure for {record['frame_id']}")
                continue
            if any(not 0.0 <= float(value) <= 1.0 for value in row[1:]):
                errors.append(f"YOLO coordinate outside [0, 1] for {record['frame_id']}")

    if any(len(splits) != 1 for splits in scene_splits.values()):
        errors.append("At least one scene crosses dataset splits")
    stages = sorted((dataset / "stages").glob("*.usda"))
    if len(stages) != 3 or any(path.stat().st_size == 0 for path in stages):
        errors.append("Expected three nonempty recipe stages")
    if not (dataset / "dataset.yaml").is_file():
        errors.append("dataset.yaml is missing")

    payload = {
        "schema_version": 1,
        "passed": not errors,
        "dataset": str(dataset),
        "frames": len(records),
        "file_counts": file_counts,
        "label_rows": label_rows,
        "nonempty_masks": nonempty_masks,
        "recipe_stages": [path.name for path in stages],
        "errors": errors,
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
