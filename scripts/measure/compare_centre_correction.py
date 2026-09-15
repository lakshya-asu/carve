r"""Column centroid against column centroid plus the learned offset, on the same 180 test frames.

The pre-registered comparison in `experiments/2026-09-15-centre-of-gravity.md`: the measurement's
legs, poses and noise seed, the geometric segmenter's mask, datasheet noise and noise plus edge
effects, with time per frame for both.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/measure/compare_centre_correction.py --checkpoint outputs/checkpoints/<file>.pt

Writes `experiments/data/2026-09-15-centre-correction-<checkpoint>.json` and prints a table.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from dataclasses import replace
from pathlib import Path

import mujoco
import numpy as np
import torch

from applications.pork_leg_alignment.perception.leg_segmentation import EmptyBeltReference, LegSegmenter
from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import PRODUCT_BODY, leg_population
from applications.pork_leg_alignment.sim.scene import CellConfig, leg_centre_y_for_rail_gap
from applications.pork_leg_alignment.sim.sensing import CameraSpec
from robotics.hardware.arms import ArmModel
from robotics.hardware.cameras import GEMINI_335L, EdgeEffects, sense_depth
from robotics.hardware.grippers import GripperModel
from robotics.perception.centre_of_gravity import column_centroid
from robotics.perception.learned_centre_of_gravity import LearnedCentreOfGravity

CAM = GEMINI_335L.name
UNDER_CAMERA_X_M = -0.40
OUT_OF_VIEW_X_M = 1.3
RAIL_GAPS_M = (0.020, 0.070, 0.120)
ARRIVAL_YAW_DEG = (-35.0, 0.0, 35.0)
NOISE_SEED = 20260915
OUT = Path("experiments/data/2026-09-15-centre-correction.json")


def main() -> None:
    """Run both estimators on every frame; write rows and print the summary."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--legs", type=int, default=20)
    parser.add_argument("--threads", type=int, default=None, help="CPU threads for the learned model")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    rng = np.random.default_rng(NOISE_SEED)
    learned = LearnedCentreOfGravity(args.checkpoint, threads=args.threads)
    cameras = {"noise": None, "edges": EdgeEffects()}
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
            ham_body = mujoco.mj_name2id(cell.model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
            cell.reset()
            cell.place_product(OUT_OF_VIEW_X_M, 0.5, -math.pi / 2)
            segmenters = {}
            for camera, edges in cameras.items():
                empties = []
                for _ in range(10):
                    _, empty = cell.observe(CAM)
                    assert empty is not None
                    empties.append(replace(empty, depth_m=sense_depth(empty.depth_m, GEMINI_335L, rng, edges=edges)))
                segmenters[camera] = LegSegmenter(EmptyBeltReference.from_frames(empties))
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
                    truth = cell.ground_truth(CAM)
                    assert frame is not None and truth.centre_of_mass_m is not None
                    toward_trotter = cell.data.xmat[ham_body].reshape(3, 3)[:2, 0]
                    toward_trotter = toward_trotter / np.linalg.norm(toward_trotter)
                    for camera, edges in cameras.items():
                        segmenter = segmenters[camera]
                        noisy = replace(frame, depth_m=sense_depth(frame.depth_m, GEMINI_335L, rng, edges=edges))
                        segmented = segmenter.segment(noisy)
                        row: dict[str, object] = {
                            "leg": leg_index,
                            "gap_m": gap_m,
                            "yaw_deg": yaw_deg,
                            "camera": camera,
                        }
                        if not segmented.accepted:
                            row["refused"] = segmented.refused
                            rows.append(row)
                            continue
                        plane = segmenter.reference.plane
                        for name, estimate in (
                            ("column", column_centroid(noisy, segmented.mask, plane)),
                            ("learned", learned.estimate(noisy, segmented.mask, plane)),
                        ):
                            error = estimate.position_m - truth.centre_of_mass_m
                            row |= {
                                f"{name}_error_mm": 1000 * float(np.hypot(*error[:2])),
                                f"{name}_along_mm": 1000 * float(error[:2] @ toward_trotter),
                                f"{name}_ms": estimate.elapsed_ms,
                            }
                        rows.append(row)
        print(f"leg {leg_index + 1}/{args.legs} done", flush=True)

    out = OUT.with_name(f"{OUT.stem}-{args.checkpoint.stem}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {"checkpoint": str(args.checkpoint), "torch_threads": torch.get_num_threads(), "rows": rows}, indent=1
        )
    )
    print(f"\nwrote {out}, learned model on {torch.get_num_threads()} CPU threads\n")
    print("| Camera | Method | Frames | Error mm median (worst) | Along, toward trotter | ms median |")
    print("|---|---|---|---|---|---|")
    for camera in cameras:
        subset = [r for r in rows if r["camera"] == camera and "column_error_mm" in r]
        for name in ("column", "learned"):
            error = np.array([float(r[f"{name}_error_mm"]) for r in subset])  # type: ignore[arg-type]
            along = np.array([float(r[f"{name}_along_mm"]) for r in subset])  # type: ignore[arg-type]
            ms = np.array([float(r[f"{name}_ms"]) for r in subset])  # type: ignore[arg-type]
            print(
                f"| {camera} | {name} | {len(subset)} | {np.median(error):.1f} ({error.max():.1f}) | "
                f"{np.median(along):+.1f} | {np.median(ms):.1f} |"
            )


if __name__ == "__main__":
    main()
