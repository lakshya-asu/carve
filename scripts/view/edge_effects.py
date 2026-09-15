r"""Picture of what the camera's edge effects do to one leg's outline, and to its depth mask.

One leg (leg 15 of `leg_population(20, seed=0)`, square, far end 120 mm from the rail, the
frame run 3 checked by hand) seen by the Gemini 335L model twice: with the datasheet noise only,
and with `EdgeEffects` added. Three zoomed panels of the same outline crop: height above the belt
without edge effects, height with them, and the geometric segmenter's mask on the edge-effect
frame against the simulator's silhouette (extra pixels red, missed pixels blue).

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/view/edge_effects.py

Writes `~/Videos/meat-cell/2026-09-15/edge-effects.png`.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from applications.pork_leg_alignment.perception.leg_segmentation import EmptyBeltReference, LegSegmenter
from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import leg_population
from applications.pork_leg_alignment.sim.scene import FAR_RAIL_INNER_Y_M, CellConfig
from applications.pork_leg_alignment.sim.sensing import CameraSpec
from robotics.hardware.arms import ArmModel
from robotics.hardware.cameras import GEMINI_335L, EdgeEffects, sense_depth
from robotics.hardware.grippers import GripperModel

CAM = GEMINI_335L.name
LEG_INDEX = 15
GAP_M = 0.120
UNDER_CAMERA_X_M = -0.40
OUT_OF_VIEW_X_M = 1.3
SEED = 20260915
CROP_W_PX, CROP_H_PX, ZOOM = 90, 60, 6
HEIGHT_RANGE_MM = 60.0
OUT = Path.home() / "Videos/meat-cell/2026-09-15/edge-effects.png"


def _panel(image: np.ndarray, title: str) -> np.ndarray:
    big = cv2.resize(image, None, fx=ZOOM, fy=ZOOM, interpolation=cv2.INTER_NEAREST)
    bar = np.full((44, big.shape[1], 3), 28, np.uint8)
    cv2.putText(bar, title, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (240, 240, 240), 2, cv2.LINE_AA)
    return np.vstack([bar, big])


def main() -> None:
    """Render the leg with and without edge effects and write the three-panel picture."""
    rng = np.random.default_rng(SEED)
    edges = EdgeEffects()
    leg = leg_population(20, seed=0)[LEG_INDEX]
    config = CellConfig(
        belt_speed_mps=0.30,
        leg=leg,
        arm=ArmModel.UR20,
        gripper=GripperModel.JAW_GEH6180,
        depth_cameras=(GEMINI_335L,),
        depth_camera_yaw_deg=90.0,
    )
    spec = {CAM: CameraSpec(CAM, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)}
    with Cell(config, spec) as cell:
        cell.reset()
        cell.place_product(OUT_OF_VIEW_X_M, 0.5, -math.pi / 2)
        _, empty = cell.observe(CAM)
        assert empty is not None
        references = [
            replace(empty, depth_m=sense_depth(empty.depth_m, GEMINI_335L, rng, edges=edges)) for _ in range(10)
        ]
        segmenter = LegSegmenter(EmptyBeltReference.from_frames(references))
        heading = -math.pi / 2
        centre_y = FAR_RAIL_INNER_Y_M - GAP_M - 0.5 * leg.length_m  # square pose: reach is half the length
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

    plain = sense_depth(frame.depth_m, GEMINI_335L, rng)
    edged = sense_depth(frame.depth_m, GEMINI_335L, rng, edges=edges)
    mask = segmenter.segment(replace(frame, depth_m=edged)).mask

    rows, cols = np.nonzero(truth)
    row = int(np.median(rows))
    col = int(cols[rows == row].min())  # a point on the outline, halfway along the leg
    top, left = row - CROP_H_PX // 2, col - CROP_W_PX // 2
    window = (slice(top, top + CROP_H_PX), slice(left, left + CROP_W_PX))

    def height(depth_m: np.ndarray) -> np.ndarray:
        # Height along the ray is enough for a picture; lost pixels (depth 0) are drawn black.
        mm = np.clip(1000 * (empty.depth_m - depth_m), 0, HEIGHT_RANGE_MM)
        coloured = cv2.applyColorMap((255 * mm / HEIGHT_RANGE_MM).astype(np.uint8), cv2.COLORMAP_VIRIDIS)
        coloured[depth_m == 0] = 0
        return np.asarray(coloured[window])

    verdict = np.full((CROP_H_PX, CROP_W_PX, 3), 235, np.uint8)
    both = (mask & truth)[window]
    extra = (mask & ~truth)[window]
    missed = (~mask & truth)[window]
    verdict[both] = (120, 190, 120)
    verdict[extra] = (60, 60, 220)
    verdict[missed] = (220, 120, 40)

    picture = np.hstack(
        [
            _panel(height(plain), "datasheet noise: height, 0 to 60 mm"),
            _panel(height(edged), "plus edge effects (black: no depth)"),
            _panel(verdict, "mask: green right, red extra, blue missed"),
        ]
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT), picture)
    print(
        f"wrote {OUT}; whole frame: {int((mask & ~truth).sum())} extra px, {int((~mask & truth).sum())} missed px, "
        f"{int(truth.sum())} leg px; lost depth px {int((edged == 0).sum())} with edges vs {int((plain == 0).sum())}"
    )


if __name__ == "__main__":
    main()
