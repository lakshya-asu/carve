r"""Picture of where each method puts one leg's centre of gravity, on the camera's height map.

One leg of `leg_population(20, seed=0)` at the experiment's poses, seen by the Gemini 335L model
with datasheet noise: height above the belt inside the leg, the outline, the simulator's centre of
mass (white cross), the outline's centre (orange) and the column centroid (green), each dropped
onto the belt and drawn where the camera sees that belt point.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/view_centre_of_gravity.py --leg 15

Writes `~/Videos/meat-cell/2026-09-15/centre-of-gravity.png`.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2
import numpy as np

from meat_cell_sim.arms import ArmModel
from meat_cell_sim.cameras import GEMINI_335L, sense_depth
from meat_cell_sim.cell import Cell
from meat_cell_sim.centre_of_gravity import column_centroid, silhouette_centroid
from meat_cell_sim.evidence import Plane, ray_directions
from meat_cell_sim.frames import world_to_pixel
from meat_cell_sim.gripper import GripperModel
from meat_cell_sim.leg_segmentation import EmptyBeltReference
from meat_cell_sim.product import LegConfig, leg_half_width_m, leg_population
from meat_cell_sim.scene import CellConfig
from meat_cell_sim.sensing import CameraFrameData, CameraSpec

CAM = GEMINI_335L.name
UNDER_CAMERA_X_M = -0.40
OUT_OF_VIEW_X_M = 1.3
FAR_RAIL_INNER_Y_M = 0.857
GAP_M = 0.070
YAW_DEG = (-35.0, 0.0, 35.0)
SEED = 20260915
HEIGHT_RANGE_MM = 200.0
MARGIN_PX = 40
OUT = Path.home() / "Videos/meat-cell/2026-09-15/centre-of-gravity.png"
ORANGE, GREEN, WHITE = (40, 140, 245), (90, 200, 90), (255, 255, 255)


def _with_depth(frame: CameraFrameData, depth_m: np.ndarray) -> CameraFrameData:
    return CameraFrameData(frame.stamp_s, frame.rgb, depth_m, frame.intrinsics, frame.camera)


def _centre_y_for_gap(leg: LegConfig, yaw_deg: float, gap_m: float) -> float:
    widest = float(leg_half_width_m(leg, np.linspace(0.0, 1.0, 101)).max())
    reach = 0.5 * leg.length_m * math.cos(math.radians(yaw_deg)) + widest * abs(math.sin(math.radians(yaw_deg)))
    return FAR_RAIL_INNER_Y_M - gap_m - reach


def _on_belt(point_m: np.ndarray, plane: Plane) -> np.ndarray:
    """The belt point straight below `point_m`."""
    return np.asarray(point_m - float(plane.height_of(point_m)) * plane.normal)


def main() -> None:
    """Render the leg at three yaws and write one panel per yaw."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--leg", type=int, default=15)
    args = parser.parse_args()
    rng = np.random.default_rng(SEED)
    leg = leg_population(20, seed=0)[args.leg]
    config = CellConfig(
        belt_speed_mps=0.30,
        leg=leg,
        arm=ArmModel.UR20,
        gripper=GripperModel.JAW_GEH6180,
        depth_cameras=(GEMINI_335L,),
        depth_camera_yaw_deg=90.0,
    )
    spec = {CAM: CameraSpec(CAM, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)}
    panels = []
    with Cell(config, spec) as cell:
        cell.reset()
        cell.place_product(OUT_OF_VIEW_X_M, 0.5, -math.pi / 2)
        empties = []
        for _ in range(10):
            _, empty = cell.observe(CAM)
            assert empty is not None
            empties.append(_with_depth(empty, sense_depth(empty.depth_m, GEMINI_335L, rng)))
        plane = EmptyBeltReference.from_frames(empties).plane
        for yaw_deg in YAW_DEG:
            heading = -math.pi / 2 + math.radians(yaw_deg)
            cell.reset()
            cell.place_product(
                UNDER_CAMERA_X_M - leg.outline_centre_m * math.cos(heading),
                _centre_y_for_gap(leg, yaw_deg, GAP_M) - leg.outline_centre_m * math.sin(heading),
                heading,
                settle_s=0.2,
            )
            _, clean = cell.observe(CAM)
            truth = cell.ground_truth(CAM)
            assert clean is not None and truth.piece_mask is not None and truth.centre_of_mass_m is not None
            frame = _with_depth(clean, sense_depth(clean.depth_m, GEMINI_335L, rng))
            mask = truth.piece_mask
            outline = silhouette_centroid(frame, mask, plane)
            columns = column_centroid(frame, mask, plane)

            points = frame.camera.position_m + ray_directions(frame) * frame.depth_m[..., None]
            height_mm = np.clip(1000 * plane.height_of(points.reshape(-1, 3)).reshape(mask.shape), 0, HEIGHT_RANGE_MM)
            image = cv2.applyColorMap((255 * height_mm / HEIGHT_RANGE_MM).astype(np.uint8), cv2.COLORMAP_VIRIDIS)
            image[~mask] = (image[~mask] * 0.25).astype(np.uint8)
            contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            cv2.drawContours(image, contours, -1, WHITE, 2, cv2.LINE_AA)

            truth_px = world_to_pixel(frame.intrinsics, frame.camera, _on_belt(truth.centre_of_mass_m, plane))
            for position, colour in ((outline.position_m, ORANGE), (columns.position_m, GREEN)):
                u, v = world_to_pixel(frame.intrinsics, frame.camera, _on_belt(position, plane))
                cv2.circle(image, (round(u), round(v)), 11, colour, 4, cv2.LINE_AA)
            u, v = round(truth_px[0]), round(truth_px[1])
            cv2.drawMarker(image, (u, v), WHITE, cv2.MARKER_CROSS, 30, 3, cv2.LINE_AA)

            rows, cols = np.nonzero(mask)
            crop = image[
                max(rows.min() - MARGIN_PX, 0) : rows.max() + MARGIN_PX,
                max(cols.min() - MARGIN_PX, 0) : cols.max() + MARGIN_PX,
            ]
            size = 520
            scale = size / max(crop.shape[:2])
            crop = cv2.resize(crop, (round(crop.shape[1] * scale), round(crop.shape[0] * scale)))
            canvas = np.full((size + 70, size, 3), 28, np.uint8)
            top, left = (size - crop.shape[0]) // 2 + 70, (size - crop.shape[1]) // 2
            canvas[top : top + crop.shape[0], left : left + crop.shape[1]] = crop

            outline_mm, columns_mm = (
                1000 * float(np.hypot(*(estimate.position_m - truth.centre_of_mass_m)[:2]))
                for estimate in (outline, columns)
            )
            lines = (
                (f"yaw {yaw_deg:+.0f} deg", WHITE),
                (f"outline centre {outline_mm:.1f} mm off", ORANGE),
                (f"column centroid {columns_mm:.1f} mm off", GREEN),
            )
            for i, (text, colour) in enumerate(lines):
                cv2.putText(canvas, text, (12, 22 + 21 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2, cv2.LINE_AA)
            panels.append(canvas)
            print(f"yaw {yaw_deg:+.0f}: outline {outline_mm:.1f} mm, columns {columns_mm:.1f} mm")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT), np.hstack(panels))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
