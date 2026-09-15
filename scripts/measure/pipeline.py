r"""Compare the depth-first pipeline against the appearance-based baselines.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/measure/pipeline.py --samples 30

Four methods over the same frames and the same degradations: three
appearance-only segmenters as baselines, and the depth-first evidence pipeline.
Everything is scored on the pose that comes out, because the earlier sweep
established that mask-quality metrics do not rank methods for this task.

The specular condition degrades **both** channels. A highlight is not only a
bright patch in the picture, it is also where active stereo fails to find a
correspondence and returns nothing. Blowing out the colour while leaving a
perfect depth buffer would hand the depth-first design a win it has not earned,
so `specular_blobs` and `depth_dropout_where_specular` are applied together.

Two depth-only axes are included for the same reason: a design that leans on
depth has to be measured when depth is the thing that is failing.
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

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.scene import CellConfig
from applications.pork_leg_alignment.sim.sensing import CameraSpec
from robotics.core.camera_frame import CameraFrameData
from robotics.core.contracts import axis_error_rad
from robotics.hardware.image_degradation import (
    background_toward_product,
    depth_axial_noise,
    depth_dropout,
    depth_dropout_where_specular,
    lighting_gradient,
    purge_patches,
    sensor_noise,
    specular_blobs,
)
from robotics.perception.pose_estimation import PerceptionRejectedError, estimate_from_depth
from robotics.perception.segmentation import METHODS
from robotics.perception.staged_segmenter import (
    ColourConfirmation,
    DepthHeightProposal,
    EdgeSnapRefinement,
    HeightWatershedSplit,
    Segmenter,
)

logger = logging.getLogger(__name__)

CAMERA = "overhead"
PLACEMENT_BOUND_MM = 2.0
# Measured from the rendered product in this scene, and the value the cell would
# be commissioned with rather than one learned at runtime.
PRODUCT_RGB = np.array([247.0, 139.0, 146.0])

Degradation = Callable[[np.ndarray, np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]]


@dataclass
class Sample:
    """One rendered view with the truth to score against."""

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
                    frame, truth.piece_mask.copy(), truth.piece_pose.x_m, truth.piece_pose.y_m, truth.piece_pose.yaw_rad
                )
            )
    return samples


def _unchanged(rgb: np.ndarray, depth: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return rgb, depth


def _noise(sigma: float, rng: np.random.Generator) -> Degradation:
    def apply(rgb: np.ndarray, depth: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return sensor_noise(rgb, sigma, rng), depth

    return apply


def _lighting(strength: float) -> Degradation:
    def apply(rgb: np.ndarray, depth: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return lighting_gradient(rgb, strength), depth

    return apply


def _specular(count: int, rng: np.random.Generator) -> Degradation:
    def apply(rgb: np.ndarray, depth: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        lit = specular_blobs(rgb, count, 60, rng)
        return lit, depth_dropout_where_specular(depth, lit)

    return apply


def _background(fraction: float) -> Degradation:
    def apply(rgb: np.ndarray, depth: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return background_toward_product(rgb, mask, fraction), depth

    return apply


def _purge(count: int, rng: np.random.Generator) -> Degradation:
    def apply(rgb: np.ndarray, depth: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return purge_patches(rgb, mask, count, 40, rng), depth

    return apply


def _depth_noise(sigma_at_1m: float, rng: np.random.Generator) -> Degradation:
    def apply(rgb: np.ndarray, depth: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return rgb, depth_axial_noise(depth, sigma_at_1m, rng)

    return apply


def _depth_holes(fraction: float, rng: np.random.Generator) -> Degradation:
    def apply(rgb: np.ndarray, depth: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return rgb, depth_dropout(depth, fraction, 30, rng)

    return apply


def degradations(rng: np.random.Generator) -> dict[str, list[tuple[str, Degradation]]]:
    """Axes to sweep. The specular axis degrades colour and depth together."""
    return {
        "clean": [("none", _unchanged)],
        "colour noise": [(f"sigma {s}", _noise(s, rng)) for s in (15, 30)],
        "uneven lighting": [(f"{int(100 * v)} pct down", _lighting(v)) for v in (0.3, 0.6)],
        "specular, colour AND depth": [(f"{n} blobs", _specular(n, rng)) for n in (3, 8, 20)],
        "belt colour toward product": [(f"{int(100 * f)} pct", _background(f)) for f in (0.5, 0.9, 1.0)],
        "purge on the belt": [(f"{n} patches", _purge(n, rng)) for n in (15, 40)],
        "depth noise": [(f"{int(1000 * s)} mm at 1 m", _depth_noise(s, rng)) for s in (0.002, 0.006, 0.012)],
        "depth dropout": [(f"{int(100 * f)} pct lost", _depth_holes(f, rng)) for f in (0.1, 0.3, 0.5)],
    }


def build_pipeline() -> Segmenter:
    """The depth-first pipeline as designed."""
    return Segmenter(
        proposals=[DepthHeightProposal(seed=7)],
        refinements=[EdgeSnapRefinement()],
        confirmation=ColourConfirmation(PRODUCT_RGB),
        splitter=HeightWatershedSplit(seed=7),
    )


def _degraded_frame(sample: Sample, degrade: Degradation) -> CameraFrameData:
    rgb, depth = degrade(sample.frame.rgb, sample.frame.depth_m, sample.truth_mask)
    return CameraFrameData(
        stamp_s=sample.frame.stamp_s,
        rgb=rgb,
        depth_m=depth.astype(np.float32),
        intrinsics=sample.frame.intrinsics,
        camera=sample.frame.camera,
    )


def evaluate(samples: list[Sample], degrade: Degradation, method: str, pipeline: Segmenter) -> dict[str, float]:
    """Score one method over every sample under one degradation."""
    errors, axes = [], []
    refused, failed = 0, 0
    for sample in samples:
        frame = _degraded_frame(sample, degrade)
        if method == "depth-first":
            result = pipeline.segment(frame)
            if not result.accepted:
                refused += 1
                continue
            mask = result.mask
        else:
            mask = METHODS[method](frame.rgb)
            if not mask.any():
                failed += 1
                continue
        try:
            estimate = estimate_from_depth(mask, sample.frame)
        except PerceptionRejectedError:
            failed += 1
            continue
        errors.append(1000 * math.hypot(estimate.pose.x_m - sample.truth_x_m, estimate.pose.y_m - sample.truth_y_m))
        axes.append(math.degrees(axis_error_rad(estimate.pose.yaw_rad, sample.truth_yaw_rad)))
    return {
        "centroid_mm": float(np.mean(errors)) if errors else float("nan"),
        "worst_mm": float(np.max(errors)) if errors else float("nan"),
        "axis_deg": float(np.mean(axes)) if axes else float("nan"),
        "refused": refused,
        "failed": failed,
        "scored": len(errors),
    }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260911)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    samples = collect_samples(args.samples, args.seed)
    pipeline = build_pipeline()
    rng = np.random.default_rng(args.seed)
    methods = ["depth-first", "threshold_hsv", "edge_contour", "adaptive_gray"]
    rows: list[dict[str, object]] = []

    for axis, levels in degradations(rng).items():
        print(f"\n{axis}")
        print(
            f"  {'level':<16}{'method':<16}{'centroid mm':>12}{'worst mm':>10}{'axis deg':>10}{'refused':>9}{'failed':>8}"
        )
        for level_name, degrade in levels:
            for method in methods:
                result = evaluate(samples, degrade, method, pipeline)
                rows.append({"axis": axis, "level": level_name, "method": method, **result})
                holds = (
                    ""
                    if math.isnan(result["worst_mm"])
                    else ("  ok" if result["worst_mm"] <= PLACEMENT_BOUND_MM else "  <")
                )
                centroid = "     nan" if math.isnan(result["centroid_mm"]) else f"{result['centroid_mm']:12.3f}"
                worst = "   nan" if math.isnan(result["worst_mm"]) else f"{result['worst_mm']:10.3f}"
                axis_v = "   nan" if math.isnan(result["axis_deg"]) else f"{result['axis_deg']:10.3f}"
                print(
                    f"  {level_name:<16}{method:<16}{centroid}{worst}{axis_v}"
                    f"{result['refused']:>9}{result['failed']:>8}{holds}"
                )

    print(f"\n{args.samples} poses per cell. 'ok' means the worst centroid error held the")
    print(f"{PLACEMENT_BOUND_MM:.0f} mm bound. 'refused' is the pipeline declining a frame, which is a")
    print("working safety behaviour; 'failed' is a method returning a wrong or unusable answer.")
    if args.json:
        args.json.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
