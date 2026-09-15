r"""Record what the two candidate depth cameras deliver, side by side.

Both cameras from `meat_cell_sim.cameras` are mounted at the overhead position,
950 mm above the belt. Legs ride the belt under them at three arrival angles.
Each row of the video is one camera, with three panes:

    colour         the camera's colour image with the leg's true outline
    depth          what the camera reports, drawn as height above the belt
    depth error    reported minus the simulator's noiseless depth, +-5 mm scale

and a readout under each row: valid depth on the leg, and depth error on the belt
and on the leg for that frame. Experiment record:
`experiments/2026-09-15-depth-camera-comparison.md`.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/view_depth_cameras.py --out depth-cameras.mp4
"""

from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np

from meat_cell_sim.cameras import DEPTH_CAMERAS, DepthCameraModel, sense_depth
from meat_cell_sim.cell import Cell
from meat_cell_sim.product import LegConfig
from meat_cell_sim.scene import CellConfig
from meat_cell_sim.sensing import CameraFrameData, CameraSpec

logger = logging.getLogger("view_depth_cameras")

FPS = 30
PANE_W, PANE_H, STRIP_H = 640, 400, 56
BELT_DEPTH_M = 0.95
HEIGHT_SCALE_M = 0.15
ERROR_SCALE_M = 0.005
SPAWN_X_M = -0.85
LEAVE_X_M = 0.05
ARRIVAL_YAW_DEG = (-35.0, 0.0, 35.0)
NOISE_SEED = 20260915


def _fit(image: np.ndarray) -> np.ndarray:
    """Scale an image into one pane, keeping its aspect ratio, on a black ground."""
    height, width = image.shape[:2]
    scale = min(PANE_W / width, PANE_H / height)
    resized = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
    pane = np.zeros((PANE_H, PANE_W, 3), dtype=np.uint8)
    top, left = (PANE_H - resized.shape[0]) // 2, (PANE_W - resized.shape[1]) // 2
    pane[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
    return pane


def _height_image(depth_m: np.ndarray) -> np.ndarray:
    height = np.clip((BELT_DEPTH_M - depth_m) / HEIGHT_SCALE_M, 0.0, 1.0)
    image = cv2.applyColorMap((height * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    image[depth_m <= 0] = 0
    return image


def _error_image(reported_m: np.ndarray, truth_m: np.ndarray) -> np.ndarray:
    """Blue where the camera reads too near, red too far, grey on the truth, black where it lost depth."""
    error = np.clip((reported_m - truth_m) / ERROR_SCALE_M, -1.0, 1.0)
    image = np.full((*error.shape, 3), 128, dtype=np.float32)
    image[..., 2] += 127 * np.clip(error, 0, 1)  # red channel (BGR)
    image[..., 0] += 127 * np.clip(-error, 0, 1)  # blue channel
    image[..., 1] -= 100 * np.abs(error)
    out = image.astype(np.uint8)
    out[reported_m <= 0] = 0
    return out


def _rms_mm(values_m: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(values_m)))) * 1000 if values_m.size else math.nan


def _row(
    camera: DepthCameraModel, frame: CameraFrameData, mask: np.ndarray, rng: np.random.Generator, specular: bool
) -> np.ndarray:
    truth = frame.depth_m
    # Off by default: MuJoCo's lighting saturates the white belt and the pale leg,
    # and the saturation rule then deletes depth across most of the belt, which is
    # a rendering artefact and not what a stereo camera does on a matte belt.
    reported = sense_depth(truth, camera, rng, rgb=frame.rgb if specular else None)
    colour = cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR)
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(colour, contours, -1, (255, 255, 255), 3, cv2.LINE_AA)

    valid = reported > 0
    belt = ~mask & (np.abs(truth - BELT_DEPTH_M) < 0.005) & valid
    leg = mask & valid
    leg_share = float(leg.sum()) / max(1, int(mask.sum()))
    strip = np.full((STRIP_H, 3 * PANE_W, 3), 24, dtype=np.uint8)
    intr = camera.intrinsics
    header = (
        f"{camera.label}   depth {camera.width_px}x{camera.height_px} @ {camera.frame_rate_hz:.0f} fps   "
        f"{camera.hfov_deg:.0f}x{camera.vfov_deg:.0f} deg   {camera.ground_sample_m(BELT_DEPTH_M) * 1000:.2f} mm/px "
        f"at the belt   washdown {camera.washdown}"
    )
    readout = (
        f"leg pixels {int(mask.sum()):6d}   valid on leg {100 * leg_share:5.1f}%   "
        f"depth error RMS: belt {_rms_mm(reported[belt] - truth[belt]):4.2f} mm, "
        f"leg {_rms_mm(reported[leg] - truth[leg]):4.2f} mm   model at 0.95 m {camera.depth_rms_m(0.95) * 1000:.2f} mm"
    )
    for row, text in enumerate((header, readout)):
        cv2.putText(strip, text, (12, 22 + 24 * row), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (235, 235, 235), 1, cv2.LINE_AA)
    assert (intr.width_px, intr.height_px) == reported.shape[::-1]
    panes = np.hstack([_fit(colour), _fit(_height_image(reported)), _fit(_error_image(reported, truth))])
    return np.vstack([panes, strip])


def _captions() -> np.ndarray:
    bar = np.full((32, 3 * PANE_W, 3), 40, dtype=np.uint8)
    for index, text in enumerate(
        ("colour, true outline", "reported depth: height above belt 0 to 150 mm", "error, +-5 mm, no glare model")
    ):
        cv2.putText(
            bar, text, (12 + index * PANE_W, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1, cv2.LINE_AA
        )
    return bar


def main() -> None:
    """Ride three legs under both cameras and write one video."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path.home() / "Videos" / "meat-cell" / "depth-cameras.mp4")
    parser.add_argument("--belt-speed", type=float, default=0.30)
    parser.add_argument(
        "--specular", action="store_true", help="lose depth where the rendered colour saturates (see _row)"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(NOISE_SEED)
    specs = {
        camera.name: CameraSpec(camera.name, camera.width_px, camera.height_px, exposure_s=0.0)
        for camera in DEPTH_CAMERAS
    }
    writer = imageio.get_writer(args.out, fps=FPS, codec="libx264", pixelformat="yuv420p", macro_block_size=1)
    leg = LegConfig()
    config = CellConfig(belt_speed_mps=args.belt_speed, leg=leg, depth_cameras=DEPTH_CAMERAS)
    with Cell(config, specs) as cell:
        steps_per_frame = max(1, round(1.0 / (FPS * cell.model.opt.timestep)))
        for yaw_deg in ARRIVAL_YAW_DEG:
            cell.reset()
            heading = -math.pi / 2 + math.radians(yaw_deg)
            # The body origin sits in the ham; the outline-centre offset runs along the leg's heading.
            cell.place_product(
                SPAWN_X_M - leg.outline_centre_m * math.cos(heading),
                0.50 - leg.outline_centre_m * math.sin(heading),
                heading,
                settle_s=0.2,
            )
            frames = 0
            while True:
                rows = [_captions()]
                truth = cell.ground_truth(DEPTH_CAMERAS[0].name)
                for camera in DEPTH_CAMERAS:
                    _, frame = cell.observe(camera.name)
                    assert frame is not None
                    mask = cell.ground_truth(camera.name).piece_mask
                    assert mask is not None
                    rows.append(_row(camera, frame, mask, rng, args.specular))
                writer.append_data(cv2.cvtColor(np.vstack(rows), cv2.COLOR_BGR2RGB))
                frames += 1
                if truth.piece_pose.x_m + leg.outline_centre_m * math.cos(heading) > LEAVE_X_M or frames > 10 * FPS:
                    break
                cell.step(steps_per_frame)
            logger.info("arrival yaw %+.0f deg: %d frames", yaw_deg, frames)
    writer.close()
    logger.info("wrote %s", args.out)


if __name__ == "__main__":
    main()
