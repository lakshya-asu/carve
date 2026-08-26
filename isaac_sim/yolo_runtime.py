"""Project-local Ultralytics runtime bootstrap.

The project keeps Ultralytics below ``third_party/python`` so the Isaac Sim
environment and the system Python are not modified.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENDOR_ROOT = PROJECT_ROOT / "third_party" / "python"
YOLO_CONFIG_ROOT = PROJECT_ROOT / "results" / "yolo" / "config"


def configure_yolo_runtime() -> None:
    if not VENDOR_ROOT.exists():
        raise RuntimeError(
            "The project-local Ultralytics runtime is missing. Run setup_yolo.ps1 first."
        )
    vendor = str(VENDOR_ROOT)
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    YOLO_CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(YOLO_CONFIG_ROOT))
    os.environ.setdefault("WANDB_DISABLED", "true")


def load_yolo_class() -> Any:
    configure_yolo_runtime()
    from ultralytics import YOLO

    return YOLO


def ultralytics_version() -> str:
    configure_yolo_runtime()
    import ultralytics

    return str(ultralytics.__version__)
