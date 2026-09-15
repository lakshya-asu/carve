r"""Measure the centre-of-gravity estimators on the 20-leg population, as pre-registered.

`experiments/2026-09-15-centre-of-gravity.md`: the leg-segmentation experiment's cell, camera,
legs, poses and noise seed. Each frame is estimated eight ways, silhouette or column centroid, on
the true silhouette or the geometric segmenter's mask, with datasheet noise or noise plus edge
effects, and scored against the simulator's centre of mass on the belt plane.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/measure_centre_of_gravity.py

Writes `experiments/data/2026-09-15-centre-of-gravity.json` and prints tables.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path

import mujoco
import numpy as np

from meat_cell_sim.arms import ArmModel
from meat_cell_sim.cameras import GEMINI_335L, EdgeEffects, sense_depth
from meat_cell_sim.cell import Cell
from meat_cell_sim.centre_of_gravity import column_centroid, silhouette_centroid
from meat_cell_sim.gripper import GripperModel
from meat_cell_sim.leg_segmentation import EmptyBeltReference, LegSegmenter
from meat_cell_sim.product import PRODUCT_BODY, LegConfig, leg_half_width_m, leg_population
from meat_cell_sim.scene import CellConfig
from meat_cell_sim.sensing import CameraFrameData, CameraSpec

CAM = GEMINI_335L.name
UNDER_CAMERA_X_M = -0.40
OUT_OF_VIEW_X_M = 1.3
FAR_RAIL_INNER_Y_M = 0.857
RAIL_GAPS_M = (0.020, 0.070, 0.120)
ARRIVAL_YAW_DEG = (-35.0, 0.0, 35.0)
REFERENCE_FRAMES = 10
NOISE_SEED = 20260915
METHODS = {"silhouette": silhouette_centroid, "column": column_centroid}
OUT = Path("experiments/data/2026-09-15-centre-of-gravity.json")


def _with_depth(frame: CameraFrameData, depth_m: np.ndarray) -> CameraFrameData:
    return CameraFrameData(frame.stamp_s, frame.rgb, depth_m, frame.intrinsics, frame.camera)


def _centre_y_for_gap(leg: LegConfig, yaw_deg: float, gap_m: float) -> float:
    """Outline-centre y that leaves `gap_m` between the leg's far end and the rail."""
    widest = float(leg_half_width_m(leg, np.linspace(0.0, 1.0, 101)).max())
    reach = 0.5 * leg.length_m * math.cos(math.radians(yaw_deg)) + widest * abs(math.sin(math.radians(yaw_deg)))
    return FAR_RAIL_INNER_Y_M - gap_m - reach


def main() -> None:
    """Run every leg, pose and input; write the raw rows and print the summary."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--legs", type=int, default=20)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    rng = np.random.default_rng(NOISE_SEED)
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
                for _ in range(REFERENCE_FRAMES):
                    _, empty = cell.observe(CAM)
                    assert empty is not None
                    empties.append(_with_depth(empty, sense_depth(empty.depth_m, GEMINI_335L, rng, edges=edges)))
                segmenters[camera] = LegSegmenter(EmptyBeltReference.from_frames(empties))
            for gap_m in RAIL_GAPS_M:
                for yaw_deg in ARRIVAL_YAW_DEG:
                    heading = -math.pi / 2 + math.radians(yaw_deg)
                    cell.reset()
                    cell.place_product(
                        UNDER_CAMERA_X_M - leg.outline_centre_m * math.cos(heading),
                        _centre_y_for_gap(leg, yaw_deg, gap_m) - leg.outline_centre_m * math.sin(heading),
                        heading,
                        settle_s=0.2,
                    )
                    _, frame = cell.observe(CAM)
                    truth = cell.ground_truth(CAM)
                    assert frame is not None and truth.piece_mask is not None and truth.centre_of_mass_m is not None
                    # The ham body's x axis runs from the butt toward the trotter.
                    toward_trotter = cell.data.xmat[ham_body].reshape(3, 3)[:2, 0]
                    toward_trotter = toward_trotter / np.linalg.norm(toward_trotter)
                    across = np.array([-toward_trotter[1], toward_trotter[0]])
                    for camera, edges in cameras.items():
                        segmenter = segmenters[camera]
                        noisy = _with_depth(frame, sense_depth(frame.depth_m, GEMINI_335L, rng, edges=edges))
                        segmented = segmenter.segment(noisy)
                        masks = {"truth": truth.piece_mask, "segmented": segmented.mask if segmented.accepted else None}
                        for mask_name, mask in masks.items():
                            for method_name, method in METHODS.items():
                                row: dict[str, object] = {
                                    "leg": leg_index,
                                    "gap_m": gap_m,
                                    "yaw_deg": yaw_deg,
                                    "camera": camera,
                                    "mask": mask_name,
                                    "method": method_name,
                                    "refused": None if mask is not None else segmented.refused,
                                }
                                if mask is not None:
                                    estimate = method(noisy, mask, segmenter.reference.plane)
                                    error = estimate.position_m - truth.centre_of_mass_m
                                    row |= {
                                        "error_mm": 1000 * float(np.hypot(*error[:2])),
                                        "along_mm": 1000 * float(error[:2] @ toward_trotter),
                                        "across_mm": 1000 * float(error[:2] @ across),
                                        "height_error_mm": 1000 * float(error[2]),
                                        "volume_l": 1000 * estimate.volume_m3,
                                        "ms": estimate.elapsed_ms,
                                    }
                                rows.append(row)
        print(f"leg {leg_index + 1}/{args.legs} done", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1))
    print(f"\nwrote {OUT} ({len(rows)} rows)\n")

    def med(subset: list[dict[str, object]], key: str) -> str:
        values = np.array([float(r[key]) for r in subset])  # type: ignore[arg-type]
        return f"{np.median(values):.1f}"

    print(
        "| Camera | Mask | Method | Frames | Error mm median (worst) | Along, toward trotter | Across | Height | Volume l | ms |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|")
    for camera in cameras:
        for mask_name in ("truth", "segmented"):
            for method_name in METHODS:
                subset = [
                    r
                    for r in rows
                    if (r["camera"], r["mask"], r["method"]) == (camera, mask_name, method_name) and "error_mm" in r
                ]
                if not subset:
                    continue
                worst = max(float(r["error_mm"]) for r in subset)  # type: ignore[arg-type]
                print(
                    f"| {camera} | {mask_name} | {method_name} | {len(subset)} | {med(subset, 'error_mm')} ({worst:.1f}) | "
                    f"{med(subset, 'along_mm')} | {med(subset, 'across_mm')} | {med(subset, 'height_error_mm')} | "
                    f"{med(subset, 'volume_l')} | {med(subset, 'ms')} |"
                )
    print("\nColumn centroid, true silhouette, datasheet noise, by pose:")
    for key, values in (("yaw_deg", ARRIVAL_YAW_DEG), ("gap_m", RAIL_GAPS_M)):
        for value in values:
            subset = [
                r
                for r in rows
                if (r["camera"], r["mask"], r["method"]) == ("noise", "truth", "column") and r[key] == value
            ]
            print(f"  {key} {value}: error {med(subset, 'error_mm')} mm, along {med(subset, 'along_mm')} mm")


if __name__ == "__main__":
    main()
