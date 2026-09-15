r"""Record the geometric leg segmenter running on the belt.

Legs ride under the Orbbec Gemini 335L model (long side across the belt) at
three arrival angles. Three panes per frame:

    colour     true outline in white, the segmenter's outline in green
    height     height above the empty belt, with the found leg tinted
    difference green: found and true; red: found but not leg; blue: leg but missed

and a readout with overlap, boundary match, centroid error and time per frame.
Experiment record: `experiments/2026-09-15-leg-segmentation.md`.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/view_leg_segmentation.py --out leg-segmentation.mp4
"""

from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np

from meat_cell_sim.arms import ArmModel
from meat_cell_sim.cameras import GEMINI_335L, sense_depth
from meat_cell_sim.cell import Cell
from meat_cell_sim.evidence import ray_directions
from meat_cell_sim.gripper import GripperModel
from meat_cell_sim.leg_segmentation import EmptyBeltReference, LegSegmenter
from meat_cell_sim.product import LegConfig
from meat_cell_sim.scene import CellConfig
from meat_cell_sim.segmentation import score_mask
from meat_cell_sim.sensing import CameraFrameData, CameraSpec

logger = logging.getLogger("view_leg_segmentation")

CAM = GEMINI_335L.name
FPS = 30
PANE_W, PANE_H, STRIP_H, CAPTION_H = 640, 400, 34, 32
SPAWN_X_M = -1.05
LEAVE_X_M = 0.20
CENTRE_Y_M = 0.42
OUT_OF_VIEW_X_M = 1.3
ARRIVAL_YAW_DEG = (-35.0, 0.0, 35.0)
HEIGHT_SCALE_M = 0.20
NOISE_SEED = 20260915


def _noisy(frame: CameraFrameData, rng: np.random.Generator) -> CameraFrameData:
    return CameraFrameData(
        frame.stamp_s, frame.rgb, sense_depth(frame.depth_m, GEMINI_335L, rng), frame.intrinsics, frame.camera
    )


def _fit(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(PANE_W / width, PANE_H / height)
    resized = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
    pane = np.zeros((PANE_H, PANE_W, 3), dtype=np.uint8)
    top, left = (PANE_H - resized.shape[0]) // 2, (PANE_W - resized.shape[1]) // 2
    pane[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
    return pane


def _outline(image: np.ndarray, mask: np.ndarray, colour: tuple[int, int, int]) -> None:
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image, contours, -1, colour, 3, cv2.LINE_AA)


def _centroid_m(mask: np.ndarray, frame: CameraFrameData) -> np.ndarray:
    directions = ray_directions(frame)[mask]
    points = frame.camera.position_m + directions * frame.depth_m[mask][:, None]
    return np.asarray(points[:, :2].mean(axis=0))


def _panes(
    clean: CameraFrameData, noisy: CameraFrameData, reference: EmptyBeltReference, found: np.ndarray, truth: np.ndarray
) -> np.ndarray:
    colour = cv2.cvtColor(clean.rgb, cv2.COLOR_RGB2BGR)
    _outline(colour, truth, (255, 255, 255))
    _outline(colour, found, (90, 220, 90))
    rays = np.abs(ray_directions(noisy)[..., 2])
    height = np.clip((reference.depth_m - noisy.depth_m) * rays / HEIGHT_SCALE_M, 0.0, 1.0)
    height_image = cv2.applyColorMap((height * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS)
    height_image[found] = (0.6 * height_image[found] + 0.4 * np.array([90, 220, 90])).astype(np.uint8)
    difference = np.full((*truth.shape, 3), 30, dtype=np.uint8)
    difference[found & truth] = (90, 200, 90)
    difference[found & ~truth] = (60, 60, 235)
    difference[~found & truth] = (235, 140, 60)
    return np.hstack([_fit(colour), _fit(height_image), _fit(difference)])


def _text_bar(height_px: int, texts: list[tuple[int, str]]) -> np.ndarray:
    bar = np.full((height_px, 3 * PANE_W, 3), 28, dtype=np.uint8)
    for x_px, text in texts:
        cv2.putText(bar, text, (x_px, height_px - 11), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1, cv2.LINE_AA)
    return bar


def main() -> None:
    """Ride three legs under the camera and write one video."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path.home() / "Videos" / "meat-cell" / "leg-segmentation.mp4")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(NOISE_SEED)
    leg = LegConfig()
    config = CellConfig(
        belt_speed_mps=0.30,
        leg=leg,
        arm=ArmModel.UR20,
        gripper=GripperModel.JAW_GEH6180,
        depth_cameras=(GEMINI_335L,),
        depth_camera_yaw_deg=90.0,
    )
    spec = {CAM: CameraSpec(CAM, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)}
    writer = imageio.get_writer(args.out, fps=FPS, codec="libx264", pixelformat="yuv420p", macro_block_size=1)
    caption = _text_bar(
        CAPTION_H,
        [
            (12, "colour: true outline white, found green"),
            (PANE_W + 12, "height above empty belt, found leg tinted"),
            (2 * PANE_W + 12, "green match, red extra, blue missed"),
        ],
    )
    with Cell(config, spec) as cell:
        steps_per_frame = max(1, round(1.0 / (FPS * cell.model.opt.timestep)))
        cell.reset()
        cell.place_product(OUT_OF_VIEW_X_M, 0.5, -math.pi / 2)
        reference = EmptyBeltReference.from_frames([_noisy(cell.observe(CAM)[1], rng) for _ in range(10)])
        segmenter = LegSegmenter(reference)
        for yaw_deg in ARRIVAL_YAW_DEG:
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
                assert frame is not None and truth.piece_mask is not None
                noisy = _noisy(frame, rng)
                result = segmenter.segment(noisy)
                if result.accepted:
                    score = score_mask(result.mask, truth.piece_mask)
                    error_mm = 1000 * float(
                        np.hypot(*(_centroid_m(result.mask, frame) - _centroid_m(truth.piece_mask, frame)))
                    )
                    readout = (
                        f"accepted   IoU {score.iou:.3f}   boundary F1 {score.boundary_f1:.3f}   precision "
                        f"{score.precision:.3f}   recall {score.recall:.3f}   centroid error {error_mm:.2f} mm   "
                        f"{result.elapsed_ms:.0f} ms"
                    )
                else:
                    readout = f"refused: {result.refused}   {result.elapsed_ms:.0f} ms"
                strip = _text_bar(STRIP_H, [(12, f"{GEMINI_335L.label}, arrival yaw {yaw_deg:+.0f} deg   {readout}")])
                image = np.vstack([caption, _panes(frame, noisy, reference, result.mask, truth.piece_mask), strip])
                writer.append_data(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                frames += 1
                if truth.piece_pose.x_m + leg.outline_centre_m * math.cos(heading) > LEAVE_X_M or frames > 12 * FPS:
                    break
                cell.step(steps_per_frame)
            logger.info("arrival yaw %+.0f deg: %d frames", yaw_deg, frames)
    writer.close()
    logger.info("wrote %s", args.out)


if __name__ == "__main__":
    main()
