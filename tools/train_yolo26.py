"""Fine-tune the official YOLO26n segmentation checkpoint on Isaac frames."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="results/yolo/dataset_v2/dataset.yaml")
    parser.add_argument("--base", default="models/yolo26n-seg.pt")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=2601)
    parser.add_argument("--name", default="yolo26_meat_reference")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from isaac_sim.yolo_runtime import load_yolo_class, ultralytics_version

    dataset = (PROJECT_ROOT / args.dataset).resolve()
    base = (PROJECT_ROOT / args.base).resolve()
    if not dataset.is_file() or not base.is_file():
        raise FileNotFoundError("YOLO dataset or base checkpoint is missing")
    yolo = load_yolo_class()
    model = yolo(str(base), task="segment")
    output_root = PROJECT_ROOT / "models"
    gpu_nms_workaround_used = False
    if not args.validate_only:
        try:
            model.train(
                data=str(dataset),
                epochs=args.epochs,
                imgsz=640,
                batch=8,
                workers=0,
                device=0,
                project=str(output_root),
                name=args.name,
                exist_ok=True,
                seed=args.seed,
                deterministic=True,
                pretrained=True,
                single_cls=True,
                cache=False,
                close_mosaic=5,
                plots=True,
                verbose=True,
            )
        except NotImplementedError as error:
            if "torchvision::nms" not in str(error) or "CUDA" not in str(error):
                raise
            # Isaac Sim 6.0.1 bundles a CPU-only TorchVision NMS operator. The
            # checkpoint is already saved before Ultralytics performs final_eval.
            # Validate it below on CPU without modifying Isaac's environment.
            gpu_nms_workaround_used = True
            print("Isaac TorchVision has no CUDA NMS kernel. Continuing with CPU validation.")
    best = output_root / args.name / "weights" / "best.pt"
    if not best.is_file():
        raise RuntimeError("YOLO training did not produce best.pt")
    validation = yolo(str(best), task="segment").val(
        data=str(dataset),
        split="val",
        imgsz=640,
        batch=8,
        workers=0,
        device="cpu",
        project=str(PROJECT_ROOT / "results" / "yolo"),
        name="validation",
        exist_ok=True,
        plots=True,
        verbose=True,
    )
    example = sorted((dataset.parent / "images" / "val").glob("*.png"))[0]
    prediction = yolo(str(best), task="segment").predict(
        source=str(example), imgsz=640, conf=0.20, device="cpu", verbose=False
    )[0]
    prediction.save(filename=str(PROJECT_ROOT / "results" / "yolo" / "example_prediction.jpg"))
    result_values = {}
    for key, value in validation.results_dict.items():
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, (int, float)):
            result_values[str(key)] = float(value)
    payload = {
        "passed": bool(prediction.masks is not None and len(prediction) > 0),
        "schema_version": 1,
        "ultralytics_version": ultralytics_version(),
        "base_checkpoint": str(base),
        "base_sha256": hashlib.sha256(base.read_bytes()).hexdigest(),
        "trained_checkpoint": str(best.resolve()),
        "trained_sha256": hashlib.sha256(best.read_bytes()).hexdigest(),
        "dataset": str(dataset),
        "epochs": args.epochs,
        "seed": args.seed,
        "validate_only": args.validate_only,
        "gpu_nms_workaround_used": gpu_nms_workaround_used,
        "validation_device": "cpu",
        "validation": result_values,
        "example_image": str(example.resolve()),
        "example_prediction": str((PROJECT_ROOT / "results" / "yolo" / "example_prediction.jpg").resolve()),
        "example_detections": len(prediction),
        "training_data_notice": "Synthetic Isaac reference geometry only. No real meat images were used.",
    }
    report = PROJECT_ROOT / "results" / "yolo" / "training_summary.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
