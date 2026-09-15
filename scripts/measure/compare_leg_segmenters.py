r"""Geometry, learned, and both together, on the same 180 leg frames.

The pre-registered comparison in `experiments/2026-09-15-leg-segmentation.md`:
the same legs, poses, camera model and noise seed as
`scripts/measure/leg_segmentation.py`, run through

    geometry       LegSegmenter (height above the empty belt)
    learned        LearnedLegSegmenter (small U-Net on colour and depth)
    both, AND      pixels both call leg: the learned mask checked by geometry
    both, OR       pixels either calls leg

with each method's time per frame on this CPU.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/measure/compare_leg_segmenters.py --checkpoint outputs/checkpoints/<file>.pt

Writes `experiments/data/2026-09-15-leg-segmenter-comparison-<checkpoint>[-edges].json` and
prints a table.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path

import numpy as np
import torch

from applications.pork_leg_alignment.perception.learned_leg_segmentation import LearnedLegSegmenter
from applications.pork_leg_alignment.perception.leg_segmentation import EmptyBeltReference, LegSegmenter
from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import leg_population
from applications.pork_leg_alignment.sim.scene import CellConfig, leg_centre_y_for_rail_gap
from applications.pork_leg_alignment.sim.sensing import CameraSpec
from robotics.core.camera_frame import CameraFrameData
from robotics.hardware.arms import ArmModel
from robotics.hardware.cameras import GEMINI_335L, EdgeEffects, sense_depth
from robotics.hardware.grippers import GripperModel
from robotics.perception.depth_geometry import ray_directions
from robotics.perception.segmentation import largest_component, score_mask

CAM = GEMINI_335L.name
UNDER_CAMERA_X_M = -0.40
OUT_OF_VIEW_X_M = 1.3
RAIL_GAPS_M = (0.020, 0.070, 0.120)
ARRIVAL_YAW_DEG = (-35.0, 0.0, 35.0)
NOISE_SEED = 20260915
METHODS = ("geometry", "learned", "both_and", "both_or")
OUT = Path("experiments/data/2026-09-15-leg-segmenter-comparison.json")


def _noisy(frame: CameraFrameData, rng: np.random.Generator, edges: EdgeEffects | None) -> CameraFrameData:
    return CameraFrameData(
        frame.stamp_s,
        frame.rgb,
        sense_depth(frame.depth_m, GEMINI_335L, rng, edges=edges),
        frame.intrinsics,
        frame.camera,
    )


def _centroid_m(mask: np.ndarray, frame: CameraFrameData) -> np.ndarray:
    directions = ray_directions(frame)[mask]
    points = frame.camera.position_m + directions * frame.depth_m[mask][:, None]
    return np.asarray(points[:, :2].mean(axis=0))


def _score(mask: np.ndarray, truth: np.ndarray, frame: CameraFrameData) -> dict[str, float]:
    score = score_mask(mask, truth)
    error = _centroid_m(mask, frame) - _centroid_m(truth, frame)
    return {
        "iou": score.iou,
        "boundary_f1": score.boundary_f1,
        "precision": score.precision,
        "recall": score.recall,
        "centroid_mm": 1000 * float(np.hypot(*error)),
    }


def main() -> None:
    """Run all methods on every frame; write rows and print the summary."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--legs", type=int, default=20)
    parser.add_argument("--threads", type=int, default=None, help="CPU threads for the learned model")
    parser.add_argument("--edge-effects", action="store_true", help="add the camera's edge and steep-surface artefacts")
    args = parser.parse_args()
    edges = EdgeEffects() if args.edge_effects else None
    # One file per checkpoint and camera model, so runs never overwrite each other.
    out = OUT.with_name(f"{OUT.stem}-{args.checkpoint.stem}{'-edges' if args.edge_effects else ''}.json")
    logging.basicConfig(level=logging.WARNING)
    rng = np.random.default_rng(NOISE_SEED)
    learned = LearnedLegSegmenter(args.checkpoint, threads=args.threads)
    spec = {CAM: CameraSpec(CAM, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)}
    rows: list[dict[str, object]] = []
    for leg_index, leg in enumerate(leg_population(args.legs, seed=0)):
        config = CellConfig(
            belt_speed_mps=0.30,
            leg=leg,
            arm=ArmModel.UR20,
            gripper=GripperModel.JAW_GEH6180,
            depth_cameras=(GEMINI_335L,),
            depth_camera_yaw_deg=90.0,
        )
        with Cell(config, spec) as cell:
            cell.reset()
            cell.place_product(OUT_OF_VIEW_X_M, 0.5, -math.pi / 2)
            geometry = LegSegmenter(
                EmptyBeltReference.from_frames([_noisy(cell.observe(CAM)[1], rng, edges) for _ in range(10)])
            )
            for gap_m in RAIL_GAPS_M:
                for yaw_deg in ARRIVAL_YAW_DEG:
                    heading = -math.pi / 2 + math.radians(yaw_deg)
                    cell.reset()
                    cell.place_product(
                        UNDER_CAMERA_X_M - leg.outline_centre_m * math.cos(heading),
                        leg_centre_y_for_rail_gap(leg, yaw_deg, gap_m) - leg.outline_centre_m * math.sin(heading),
                        heading,
                        settle_s=0.2,
                    )
                    _, frame = cell.observe(CAM)
                    truth = cell.ground_truth(CAM).piece_mask
                    assert frame is not None and truth is not None
                    noisy = _noisy(frame, rng, edges)
                    results = {"geometry": geometry.segment(noisy), "learned": learned.segment(noisy)}
                    row: dict[str, object] = {"leg": leg_index, "gap_m": gap_m, "yaw_deg": yaw_deg}
                    for name, result in results.items():
                        row[f"{name}_ms"] = result.elapsed_ms
                        row[f"{name}_refused"] = result.refused
                        if result.accepted:
                            row |= {f"{name}_{k}": v for k, v in _score(result.mask, truth, frame).items()}
                    if results["geometry"].accepted and results["learned"].accepted:
                        g, lm = results["geometry"].mask, results["learned"].mask
                        for name, combined in (("both_and", g & lm), ("both_or", largest_component(g | lm))):
                            if combined.any():
                                row |= {f"{name}_{k}": v for k, v in _score(combined, truth, frame).items()}
                    rows.append(row)
        print(f"leg {leg_index + 1}/{args.legs} done", flush=True)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {"checkpoint": str(args.checkpoint), "torch_threads": torch.get_num_threads(), "rows": rows}, indent=1
        )
    )
    print(f"\nwrote {out} ({len(rows)} frames), learned model on {torch.get_num_threads()} CPU threads\n")
    print(
        "| Method | Accepted | IoU median (worst) | Boundary F1 median | Recall median | Centroid mm median (worst) | ms median |"
    )
    print("|---|---|---|---|---|---|---|")
    for method in METHODS:
        ious = np.array([float(r[f"{method}_iou"]) for r in rows if f"{method}_iou" in r])  # type: ignore[arg-type]
        f1 = np.array([float(r[f"{method}_boundary_f1"]) for r in rows if f"{method}_boundary_f1" in r])  # type: ignore[arg-type]
        recall = np.array([float(r[f"{method}_recall"]) for r in rows if f"{method}_recall" in r])  # type: ignore[arg-type]
        centroid = np.array([float(r[f"{method}_centroid_mm"]) for r in rows if f"{method}_centroid_mm" in r])  # type: ignore[arg-type]
        base = method if method in ("geometry", "learned") else None
        ms = np.array([float(r[f"{base}_ms"]) for r in rows]) if base else None  # type: ignore[arg-type]
        if ious.size == 0:
            print(f"| {method} | 0/{len(rows)} | n/a | n/a | n/a | n/a | n/a |")
            continue
        timing = f"{np.median(ms):.1f}" if ms is not None else "sum of both"
        print(
            f"| {method} | {ious.size}/{len(rows)} | {np.median(ious):.3f} ({ious.min():.3f}) | {np.median(f1):.3f} | "
            f"{np.median(recall):.3f} | {np.median(centroid):.2f} ({centroid.max():.2f}) | {timing} |"
        )


if __name__ == "__main__":
    main()
