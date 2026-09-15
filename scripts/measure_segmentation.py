r"""Score real segmentation against the truth mask, and see where each method breaks.

Answers a question the rest of the pipeline had been dodging: every perception
number measured so far used the renderer's ground-truth silhouette, so none of
them said anything about finding the product in an image.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/measure_segmentation.py --samples 12

Three methods are scored: a colour threshold, an intensity threshold with no
colour at all, and Canny edges filled into a contour. Each is scored on the
clean render and then under one degradation at a time.

Read the clean row as a control, not a result. The rendered product is red on a
near-black belt with no noise, so every method scores near 1.0 and that only
says the code works. The useful output is the shape of each curve as the
appearance degrades, and in particular the contrast level at which a method
stops holding the 2 mm placement bound. That number is a specification the cell
can hand to the customer: how much the belt must differ from the product.

Depth is left clean throughout. This is a test of segmentation, and on an RGB-D
sensor the depth comes from a different modality than the colour. Real depth on
wet product degrades too, and that is a separate test.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from meat_cell_sim.appearance import (
    background_toward_product,
    lighting_gradient,
    purge_patches,
    sensor_noise,
    specular_blobs,
)
from meat_cell_sim.cell import Cell
from meat_cell_sim.contracts import axis_error_rad
from meat_cell_sim.perception import PerceptionRejectedError, estimate_from_depth
from meat_cell_sim.scene import CellConfig
from meat_cell_sim.segmentation import METHODS, score_mask
from meat_cell_sim.sensing import CameraFrameData, CameraSpec

logger = logging.getLogger(__name__)

CAMERA = "overhead"
PLACEMENT_BOUND_MM = 2.0


@dataclass
class Sample:
    """One rendered view of the product, with the truth to score against."""

    frame: CameraFrameData
    truth_mask: np.ndarray
    truth_x_m: float
    truth_y_m: float
    truth_yaw_rad: float


def collect_samples(count: int, seed: int) -> list[Sample]:
    """Render the product at a spread of poses inside the camera's view."""
    rng = np.random.default_rng(seed)
    samples: list[Sample] = []
    with Cell(CellConfig(belt_speed_mps=0.0), {CAMERA: CameraSpec(CAMERA, 1280, 960, exposure_s=0.0)}) as cell:
        cell.reset(belt_speed_mps=0.0)
        while len(samples) < count:
            x = rng.uniform(-0.62, -0.20)
            y = 0.50 + rng.uniform(-0.04, 0.04)
            yaw = rng.uniform(-math.pi / 2, math.pi / 2)
            cell.place_product(x, y, yaw, settle_s=0.15)
            _, frame = cell.observe(CAMERA)
            truth = cell.ground_truth(CAMERA)
            if frame is None or truth.piece_mask is None or truth.mask_touches_border:
                continue
            samples.append(
                Sample(
                    frame=frame,
                    truth_mask=truth.piece_mask.copy(),
                    truth_x_m=truth.piece_pose.x_m,
                    truth_y_m=truth.piece_pose.y_m,
                    truth_yaw_rad=truth.piece_pose.yaw_rad,
                )
            )
    return samples


Degradation = Callable[[np.ndarray, np.ndarray], np.ndarray]


def _noise(sigma: float, rng: np.random.Generator) -> Degradation:
    def apply(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        return sensor_noise(rgb, sigma, rng)

    return apply


def _lighting(strength: float) -> Degradation:
    def apply(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        return lighting_gradient(rgb, strength)

    return apply


def _specular(count: int, rng: np.random.Generator) -> Degradation:
    def apply(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        return specular_blobs(rgb, count, 60, rng)

    return apply


def _background(fraction: float) -> Degradation:
    def apply(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        return background_toward_product(rgb, mask, fraction)

    return apply


def _purge(count: int, rng: np.random.Generator) -> Degradation:
    def apply(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        return purge_patches(rgb, mask, count, 40, rng)

    return apply


def _unchanged(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    return rgb


def degradations(rng: np.random.Generator) -> dict[str, list[tuple[str, Degradation]]]:
    """The axes to sweep, each standing in for a named thing that happens on a line."""
    return {
        "clean": [("none", _unchanged)],
        "sensor noise (grey levels)": [(f"sigma {s}", _noise(s, rng)) for s in (5, 15, 30, 50)],
        "uneven lighting (dark end)": [(f"{int(100 * v)} pct down", _lighting(v)) for v in (0.3, 0.6, 0.8)],
        "specular highlights": [(f"{n} blobs", _specular(n, rng)) for n in (3, 8, 20)],
        "belt colour toward product": [(f"{int(100 * f)} pct", _background(f)) for f in (0.5, 0.75, 0.9, 0.97, 1.0)],
        "purge on the belt": [(f"{n} x 40 px", _purge(n, rng)) for n in (5, 15, 40)],
    }


def evaluate(
    samples: list[Sample], degrade: Degradation, method: Callable[[np.ndarray], np.ndarray]
) -> dict[str, float]:
    """Run one method over every sample under one degradation."""
    ious, boundaries, centroids, axes = [], [], [], []
    failures = 0
    for sample in samples:
        image = degrade(sample.frame.rgb, sample.truth_mask)
        mask = method(image)
        if not mask.any():
            failures += 1
            continue
        score = score_mask(mask, sample.truth_mask)
        ious.append(score.iou)
        boundaries.append(score.boundary_f1)
        try:
            estimate = estimate_from_depth(mask, sample.frame)
        except PerceptionRejectedError:
            failures += 1
            continue
        centroids.append(1000 * math.hypot(estimate.pose.x_m - sample.truth_x_m, estimate.pose.y_m - sample.truth_y_m))
        axes.append(math.degrees(axis_error_rad(estimate.pose.yaw_rad, sample.truth_yaw_rad)))
    return {
        "iou": float(np.mean(ious)) if ious else 0.0,
        "boundary_f1": float(np.mean(boundaries)) if boundaries else 0.0,
        "centroid_mm": float(np.mean(centroids)) if centroids else float("nan"),
        "centroid_max_mm": float(np.max(centroids)) if centroids else float("nan"),
        "axis_deg": float(np.mean(axes)) if axes else float("nan"),
        "failures": failures,
        "n": len(samples),
    }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260911)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    samples = collect_samples(args.samples, args.seed)
    rng = np.random.default_rng(args.seed)
    rows: list[dict[str, object]] = []

    for axis, levels in degradations(rng).items():
        print(f"\n{axis}")
        print(
            f"  {'level':<14}{'method':<16}{'IoU':>7}{'bF1':>7}{'centroid mm':>13}"
            f"{'worst mm':>10}{'axis deg':>10}{'fail':>6}"
        )
        for level_name, degrade in levels:
            for method_name, method in METHODS.items():
                result = evaluate(samples, degrade, method)
                rows.append({"axis": axis, "level": level_name, "method": method_name, **result})
                holds = (
                    ""
                    if math.isnan(result["centroid_max_mm"])
                    else ("  " if result["centroid_max_mm"] <= PLACEMENT_BOUND_MM else " <")
                )
                print(
                    f"  {level_name:<14}{method_name:<16}{result['iou']:7.3f}{result['boundary_f1']:7.3f}"
                    f"{result['centroid_mm']:13.3f}{result['centroid_max_mm']:10.3f}"
                    f"{result['axis_deg']:10.3f}{result['failures']:6d}{holds}"
                )

    print(f"\n{args.samples} product poses per cell. '<' marks a cell whose worst centroid error")
    print(f"exceeds the {PLACEMENT_BOUND_MM:.0f} mm placement bound before the arm has moved.")
    if args.json:
        args.json.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
