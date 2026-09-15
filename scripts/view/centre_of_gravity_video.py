r"""Record where each method puts the centre of gravity as legs ride under the camera.

Three different legs from `leg_population(20, seed=0)` ride the belt at 0.30 m/s under the Gemini
335L model with datasheet noise and edge effects, segmented by the geometric segmenter, so this is
the chain the cell would run. Two panes per frame, colour and height above the belt, each marked
with the simulator's centre of mass (white cross), the outline centre (orange) and the column
centroid (green), and a readout of each estimate's error on the belt.
Experiment record: `experiments/2026-09-15-centre-of-gravity.md`.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/view/centre_of_gravity_video.py

Writes `~/Videos/meat-cell/2026-09-15/centre-of-gravity.mp4` (H.264).
"""

from __future__ import annotations

import argparse
import logging
import math
from dataclasses import replace
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np

from applications.pork_leg_alignment.perception.leg_segmentation import EmptyBeltReference, LegSegmenter
from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import leg_population
from applications.pork_leg_alignment.sim.scene import CellConfig
from applications.pork_leg_alignment.sim.sensing import CameraSpec
from robotics.core.camera_frame import CameraFrameData
from robotics.core.frames import world_to_pixel
from robotics.hardware.arms import ArmModel
from robotics.hardware.cameras import GEMINI_335L, EdgeEffects, sense_depth
from robotics.hardware.grippers import GripperModel
from robotics.perception.centre_of_gravity import column_centroid, silhouette_centroid
from robotics.perception.depth_geometry import Plane, ray_directions

logger = logging.getLogger("record_centre_of_gravity")

CAM = GEMINI_335L.name
FPS = 30
PANE_W, PANE_H, BAR_H = 960, 600, 36
SPAWN_X_M = -1.05
LEAVE_X_M = 0.20
CENTRE_Y_M = 0.42
OUT_OF_VIEW_X_M = 1.3
RUNS = ((15, -35.0), (3, 0.0), (8, 35.0))  # (leg index, arrival yaw in degrees)
HEIGHT_SCALE_M = 0.20
NOISE_SEED = 20260915
WHITE, ORANGE, GREEN = (255, 255, 255), (40, 140, 245), (90, 210, 90)


def _pixel(point_m: np.ndarray, frame: CameraFrameData, plane: Plane, scale: float) -> tuple[int, int]:
    """Where the camera sees the belt point under `point_m`, in pane pixels."""
    foot = point_m - float(plane.height_of(point_m)) * plane.normal
    u, v = world_to_pixel(frame.intrinsics, frame.camera, foot)
    return round(u * scale), round(v * scale)


def _mark(pane: np.ndarray, marks: list[tuple[tuple[int, int], tuple[int, int, int]]]) -> None:
    for (u, v), colour in marks[1:]:
        cv2.circle(pane, (u, v), 9, colour, 3, cv2.LINE_AA)
    cv2.drawMarker(pane, marks[0][0], WHITE, cv2.MARKER_CROSS, 26, 3, cv2.LINE_AA)


def _bar(texts: list[tuple[int, str, tuple[int, int, int]]]) -> np.ndarray:
    bar = np.full((BAR_H, 2 * PANE_W, 3), 28, dtype=np.uint8)
    for x_px, text, colour in texts:
        cv2.putText(bar, text, (x_px, BAR_H - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.62, colour, 1, cv2.LINE_AA)
    return bar


def main() -> None:
    """Ride three legs under the camera and write one video."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path.home() / "Videos/meat-cell/2026-09-15/centre-of-gravity.mp4")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(NOISE_SEED)
    edges = EdgeEffects()
    legs = leg_population(20, seed=0)
    spec = {CAM: CameraSpec(CAM, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)}
    scale = PANE_W / GEMINI_335L.width_px
    writer = imageio.get_writer(args.out, fps=FPS, codec="libx264", pixelformat="yuv420p", macro_block_size=1)
    legend = _bar(
        [
            (12, "+ simulator's centre of mass", WHITE),
            (330, "o outline centre", ORANGE),
            (560, "o column centroid", GREEN),
            (PANE_W + 12, "height above the belt, 0 to 200 mm; segmented outline white", WHITE),
        ]
    )
    for leg_index, yaw_deg in RUNS:
        leg = legs[leg_index]
        config = CellConfig(
            belt_speed_mps=0.30,
            leg=leg,
            arm=ArmModel.UR20,
            gripper=GripperModel.JAW_GEH6180,
            depth_cameras=(GEMINI_335L,),
            depth_camera_yaw_deg=90.0,
        )
        with Cell(config, spec) as cell:
            steps_per_frame = max(1, round(1.0 / (FPS * cell.model.opt.timestep)))
            cell.reset()
            cell.place_product(OUT_OF_VIEW_X_M, 0.5, -math.pi / 2)
            empties = []
            for _ in range(10):
                _, empty = cell.observe(CAM)
                assert empty is not None
                empties.append(replace(empty, depth_m=sense_depth(empty.depth_m, GEMINI_335L, rng, edges=edges)))
            reference = EmptyBeltReference.from_frames(empties)
            segmenter = LegSegmenter(reference)
            heading = -math.pi / 2 + math.radians(yaw_deg)
            cell.reset()
            cell.place_product(
                SPAWN_X_M - leg.outline_centre_m * math.cos(heading),
                CENTRE_Y_M - leg.outline_centre_m * math.sin(heading),
                heading,
                settle_s=0.2,
            )
            frames = 0
            while True:
                _, frame = cell.observe(CAM)
                truth = cell.ground_truth(CAM)
                assert frame is not None and truth.centre_of_mass_m is not None
                noisy = replace(frame, depth_m=sense_depth(frame.depth_m, GEMINI_335L, rng, edges=edges))
                result = segmenter.segment(noisy)
                colour = cv2.resize(cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR), (PANE_W, PANE_H), cv2.INTER_AREA)
                rays = np.abs(ray_directions(noisy)[..., 2])
                height = np.clip((reference.depth_m - noisy.depth_m) * rays / HEIGHT_SCALE_M, 0.0, 1.0)
                height_pane = cv2.resize(
                    cv2.applyColorMap((height * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS),
                    (PANE_W, PANE_H),
                    cv2.INTER_AREA,
                )
                if result.accepted:
                    outline = silhouette_centroid(noisy, result.mask, reference.plane)
                    columns = column_centroid(noisy, result.mask, reference.plane)
                    small_mask = cv2.resize(result.mask.astype(np.uint8), (PANE_W, PANE_H), cv2.INTER_NEAREST)
                    contours, _ = cv2.findContours(small_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    marks = [
                        (_pixel(truth.centre_of_mass_m, noisy, reference.plane, scale), WHITE),
                        (_pixel(outline.position_m, noisy, reference.plane, scale), ORANGE),
                        (_pixel(columns.position_m, noisy, reference.plane, scale), GREEN),
                    ]
                    for pane in (colour, height_pane):
                        cv2.drawContours(pane, contours, -1, WHITE, 2, cv2.LINE_AA)
                        _mark(pane, marks)
                    outline_mm, columns_mm = (
                        1000 * float(np.hypot(*(estimate.position_m - truth.centre_of_mass_m)[:2]))
                        for estimate in (outline, columns)
                    )
                    readout = [
                        (12, f"leg {leg_index + 1}, arrival yaw {yaw_deg:+.0f} deg, belt 0.30 m/s", WHITE),
                        (560, f"outline centre {outline_mm:5.1f} mm off", ORANGE),
                        (900, f"column centroid {columns_mm:5.1f} mm off", GREEN),
                        (1260, f"centroid {columns.elapsed_ms:.0f} ms, segmenter {result.elapsed_ms:.0f} ms", WHITE),
                    ]
                else:
                    readout = [(12, f"leg {leg_index + 1}: segmenter refused: {result.refused}", WHITE)]
                image = np.vstack([legend, np.hstack([colour, height_pane]), _bar(readout)])
                writer.append_data(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                frames += 1
                if truth.piece_pose.x_m + leg.outline_centre_m * math.cos(heading) > LEAVE_X_M or frames > 12 * FPS:
                    break
                cell.step(steps_per_frame)
            logger.info("leg %d, yaw %+.0f deg: %d frames", leg_index + 1, yaw_deg, frames)
    writer.close()
    logger.info("wrote %s", args.out)


if __name__ == "__main__":
    main()
