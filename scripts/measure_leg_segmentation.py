r"""Measure the geometric leg segmenter on the 20-leg population, as pre-registered.

`experiments/2026-09-15-leg-segmentation.md`: Gemini 335L model 950 mm above the
belt, long side across it; belt at 0.30 m/s; every leg at three yaw angles and
three distances from the far rail, placed so no leg touches the rail. Each mask
is scored against the simulator's silhouette of the same frame.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/measure_leg_segmentation.py

Writes `experiments/data/2026-09-15-leg-segmentation.json` and prints tables.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path

import numpy as np

from meat_cell_sim.arms import ArmModel
from meat_cell_sim.cameras import GEMINI_335L, EdgeEffects, sense_depth
from meat_cell_sim.cell import Cell
from meat_cell_sim.evidence import ray_directions
from meat_cell_sim.gripper import GripperModel
from meat_cell_sim.leg_segmentation import EmptyBeltReference, LegSegmenter
from meat_cell_sim.product import LegConfig, leg_half_width_m, leg_population
from meat_cell_sim.scene import CellConfig
from meat_cell_sim.segmentation import score_mask
from meat_cell_sim.sensing import CameraFrameData, CameraSpec

CAM = GEMINI_335L.name
UNDER_CAMERA_X_M = -0.40
OUT_OF_VIEW_X_M = 1.3
FAR_RAIL_INNER_Y_M = 0.857
RAIL_GAPS_M = (0.020, 0.070, 0.120)
ARRIVAL_YAW_DEG = (-35.0, 0.0, 35.0)
REFERENCE_FRAMES = 10
NOISE_SEED = 20260915
OUT = Path("experiments/data/2026-09-15-leg-segmentation.json")


def _noisy(frame: CameraFrameData, rng: np.random.Generator, edges: EdgeEffects | None) -> CameraFrameData:
    return CameraFrameData(
        frame.stamp_s,
        frame.rgb,
        sense_depth(frame.depth_m, GEMINI_335L, rng, edges=edges),
        frame.intrinsics,
        frame.camera,
    )


def _centre_y_for_gap(leg: LegConfig, yaw_deg: float, gap_m: float) -> float:
    """Outline-centre y that leaves `gap_m` between the leg's far end and the rail."""
    widest = float(leg_half_width_m(leg, np.linspace(0.0, 1.0, 101)).max())
    reach = 0.5 * leg.length_m * math.cos(math.radians(yaw_deg)) + widest * abs(math.sin(math.radians(yaw_deg)))
    return FAR_RAIL_INNER_Y_M - gap_m - reach


def _centroid_m(mask: np.ndarray, frame: CameraFrameData) -> np.ndarray:
    """Mean belt-plane position of the masked pixels, from the noiseless depth."""
    directions = ray_directions(frame)[mask]
    points = frame.camera.position_m + directions * frame.depth_m[mask][:, None]
    return np.asarray(points[:, :2].mean(axis=0))


def main() -> None:
    """Run every leg and pose; write the raw rows and print the summary."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--legs", type=int, default=20)
    parser.add_argument("--edge-effects", action="store_true", help="add the camera's edge and steep-surface artefacts")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    rng = np.random.default_rng(NOISE_SEED)
    edges = EdgeEffects() if args.edge_effects else None
    out = OUT.with_name(f"{OUT.stem}-edges.json") if args.edge_effects else OUT
    spec = {CAM: CameraSpec(CAM, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)}
    rows: list[dict[str, float | str | None]] = []
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
            empties = [_noisy(cell.observe(CAM)[1], rng, edges) for _ in range(REFERENCE_FRAMES)]
            segmenter = LegSegmenter(EmptyBeltReference.from_frames(empties))
            for gap_m in RAIL_GAPS_M:
                for yaw_deg in ARRIVAL_YAW_DEG:
                    heading = -math.pi / 2 + math.radians(yaw_deg)
                    centre_y = _centre_y_for_gap(leg, yaw_deg, gap_m)
                    cell.reset()
                    cell.place_product(
                        UNDER_CAMERA_X_M - leg.outline_centre_m * math.cos(heading),
                        centre_y - leg.outline_centre_m * math.sin(heading),
                        heading,
                        settle_s=0.2,
                    )
                    _, frame = cell.observe(CAM)
                    truth = cell.ground_truth(CAM).piece_mask
                    assert frame is not None and truth is not None
                    result = segmenter.segment(_noisy(frame, rng, edges))
                    row: dict[str, float | str | None] = {
                        "leg": leg_index,
                        "gap_m": gap_m,
                        "yaw_deg": yaw_deg,
                        "refused": result.refused,
                        "ms": result.elapsed_ms,
                        "truth_touches_border": float(
                            truth[0].any() or truth[-1].any() or truth[:, 0].any() or truth[:, -1].any()
                        ),
                    }
                    if result.accepted:
                        score = score_mask(result.mask, truth)
                        error = _centroid_m(result.mask, frame) - _centroid_m(truth, frame)
                        row |= {
                            "iou": score.iou,
                            "boundary_f1": score.boundary_f1,
                            "precision": score.precision,
                            "recall": score.recall,
                            "area_ratio": result.mask.sum() / truth.sum(),
                            "centroid_mm": 1000 * float(np.hypot(*error)),
                        }
                    rows.append(row)
        print(f"leg {leg_index + 1}/{args.legs} done", flush=True)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1))
    accepted = [r for r in rows if r["refused"] is None]
    print(f"\nwrote {out} ({len(rows)} frames, {len(accepted)} accepted)")
    for reason in sorted({str(r["refused"]) for r in rows if r["refused"] is not None}):
        print(f"refused ({sum(1 for r in rows if str(r['refused']) == reason)}): {reason}")

    def stat(subset: list[dict[str, float | str | None]], key: str) -> str:
        values = np.array([float(r[key]) for r in subset if r.get(key) is not None])  # type: ignore[arg-type]
        if values.size == 0:
            return "n/a"
        worst = values.max() if key in ("centroid_mm", "ms") else values.min()
        return f"{np.median(values):.3f} ({worst:.3f})"

    print(
        "\n| Group | Frames | Accepted | IoU median (worst) | Boundary F1 | Precision | Recall | Centroid mm median (worst) | ms |"
    )
    print("|---|---|---|---|---|---|---|---|---|")
    groups = [("all", rows)] + [(f"yaw {y:+.0f}", [r for r in rows if r["yaw_deg"] == y]) for y in ARRIVAL_YAW_DEG]
    groups += [(f"rail gap {1000 * g:.0f} mm", [r for r in rows if r["gap_m"] == g]) for g in RAIL_GAPS_M]
    for name, subset in groups:
        ok = [r for r in subset if r["refused"] is None]
        print(
            f"| {name} | {len(subset)} | {len(ok)} | {stat(ok, 'iou')} | {stat(ok, 'boundary_f1')} | "
            f"{stat(ok, 'precision')} | {stat(ok, 'recall')} | {stat(ok, 'centroid_mm')} | {stat(ok, 'ms')} |"
        )


if __name__ == "__main__":
    main()
