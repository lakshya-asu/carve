r"""Measure what each candidate depth camera delivers on the 20-leg population.

The run pre-registered in `experiments/2026-09-15-depth-camera-comparison.md`:
both cameras at the overhead mount, 950 mm above the belt; every leg of
`leg_population(20, seed=0)` placed under the camera at three cross-belt
positions and three arrival angles with the belt running; per frame, the
camera's reported depth is scored against the simulator's noiseless depth.

No perception runs here. This measures the input perception will get.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/measure/depth_cameras.py

Writes `experiments/data/2026-09-15-depth-cameras.json` and prints a table.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path

import mujoco
import numpy as np

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import (
    HOCK_FRACTION,
    ORIGIN_FRACTION,
    PRODUCT_BODY,
    LegConfig,
    leg_population,
)
from applications.pork_leg_alignment.sim.scene import CellConfig
from applications.pork_leg_alignment.sim.sensing import CameraSpec
from robotics.core.camera_frame import CameraFrameData
from robotics.hardware.cameras import DEPTH_CAMERAS, DepthCameraModel, sense_depth

logger = logging.getLogger("measure_depth_cameras")

BELT_DEPTH_M = 0.95
UNDER_CAMERA_X_M = -0.40
CROSS_BELT_Y_M = (0.40, 0.50, 0.60)
ARRIVAL_YAW_DEG = (-35.0, 0.0, 35.0)
SHANK_START_FRACTION = 0.55
NOISE_SEED = 20260915
OUT = Path("experiments/data/2026-09-15-depth-cameras.json")


def _along_leg_fraction(cell: Cell, frame: CameraFrameData, mask: np.ndarray, leg: LegConfig) -> np.ndarray:
    """Where each masked pixel lies along the leg, 0 at the ham butt and 1 at the trotter tip.

    Pixels are back-projected with the true depth and moved into the leg's body
    frame, whose x axis runs along the leg from its origin in the ham.
    """
    rows, cols = np.nonzero(mask)
    z = frame.depth_m[rows, cols].astype(np.float64)
    intr = frame.intrinsics
    in_camera = np.stack([(cols - intr.cx) / intr.fx * z, -(rows - intr.cy) / intr.fy * z, -z], axis=1)
    world = in_camera @ frame.camera.rotation.T + frame.camera.position_m
    body = mujoco.mj_name2id(cell.model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
    in_body = (world - cell.data.xpos[body]) @ cell.data.xmat[body].reshape(3, 3)
    return np.asarray(in_body[:, 0] / leg.length_m + ORIGIN_FRACTION)


def _frame_metrics(
    camera: DepthCameraModel,
    cell: Cell,
    frame: CameraFrameData,
    mask: np.ndarray,
    border: bool,
    leg: LegConfig,
    rng: np.random.Generator,
) -> dict[str, float]:
    truth = frame.depth_m
    reported = sense_depth(truth, camera, rng, rgb=frame.rgb)
    valid = reported > 0
    belt = ~mask & (np.abs(truth - BELT_DEPTH_M) < 0.005) & valid
    leg_valid = mask & valid
    leg_error = (reported[leg_valid] - truth[leg_valid]) * 1000
    belt_error = (reported[belt] - truth[belt]) * 1000
    fraction = _along_leg_fraction(cell, frame, mask, leg)
    shank = (fraction >= SHANK_START_FRACTION) & (fraction <= HOCK_FRACTION)
    return {
        "in_view": 0.0 if border else 1.0,
        "leg_px": float(mask.sum()),
        "shank_px": float(shank.sum()),
        "valid_on_leg": float(leg_valid.sum()) / max(1, int(mask.sum())),
        "belt_rms_mm": float(np.sqrt(np.mean(np.square(belt_error)))) if belt_error.size else math.nan,
        "leg_rms_mm": float(np.sqrt(np.mean(np.square(leg_error)))) if leg_error.size else math.nan,
        "leg_p95_mm": float(np.percentile(np.abs(leg_error), 95)) if leg_error.size else math.nan,
    }


def main() -> None:
    """Run every leg and pose under both cameras; write the raw rows and print the summary."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--legs", type=int, default=20)
    parser.add_argument("--belt-speed", type=float, default=0.30)
    parser.add_argument("--mount-yaw-deg", type=float, default=0.0, help="90 puts the image width across the belt")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    rng = np.random.default_rng(NOISE_SEED)
    specs = {c.name: CameraSpec(c.name, c.width_px, c.height_px, exposure_s=0.0) for c in DEPTH_CAMERAS}
    rows: list[dict[str, float | str]] = []
    for leg_index, leg in enumerate(leg_population(args.legs, seed=0)):
        config = CellConfig(
            belt_speed_mps=args.belt_speed,
            leg=leg,
            depth_cameras=DEPTH_CAMERAS,
            depth_camera_yaw_deg=args.mount_yaw_deg,
        )
        with Cell(config, specs) as cell:
            for y_m in CROSS_BELT_Y_M:
                for yaw_deg in ARRIVAL_YAW_DEG:
                    cell.reset()
                    heading = -math.pi / 2 + math.radians(yaw_deg)
                    # The body origin sits in the ham, `outline_centre_m` along the leg from the
                    # outline's centre, so the offset follows the leg's heading. Applying it
                    # along x put every leg 160 mm toward the open edge in the first smoke run.
                    cell.place_product(
                        UNDER_CAMERA_X_M - leg.outline_centre_m * math.cos(heading),
                        y_m - leg.outline_centre_m * math.sin(heading),
                        heading,
                        settle_s=0.2,
                    )
                    for camera in DEPTH_CAMERAS:
                        _, frame = cell.observe(camera.name)
                        truth = cell.ground_truth(camera.name)
                        assert frame is not None and truth.piece_mask is not None
                        metrics = _frame_metrics(
                            camera, cell, frame, truth.piece_mask, truth.mask_touches_border, leg, rng
                        )
                        rows.append(
                            {"camera": camera.name, "leg": leg_index, "y_m": y_m, "yaw_deg": yaw_deg, **metrics}
                        )
        print(f"leg {leg_index + 1}/{args.legs} done", flush=True)

    out = OUT if args.mount_yaw_deg == 0.0 else OUT.with_name(f"{OUT.stem}-mount-yaw-{args.mount_yaw_deg:.0f}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1))
    print(f"\nwrote {out} ({len(rows)} rows)\n")
    print(
        "| Camera | Legs fully in view | Belt depth RMS mm | Leg depth RMS mm (median, p95 of frames) | "
        "Leg depth p95 mm (median) | Valid on leg (median) | Leg px (median) | Shank px (median) | mm/px at belt |"
    )
    print("|---|---|---|---|---|---|---|---|---|")
    for camera in DEPTH_CAMERAS:
        mine = [r for r in rows if r["camera"] == camera.name]

        def col(key: str, subset: list[dict[str, float | str]] = mine) -> np.ndarray:
            return np.array([float(r[key]) for r in subset])

        print(
            f"| {camera.label} | {int(col('in_view').sum())}/{len(mine)} | {np.nanmedian(col('belt_rms_mm')):.2f} | "
            f"{np.nanmedian(col('leg_rms_mm')):.2f}, {np.nanpercentile(col('leg_rms_mm'), 95):.2f} | "
            f"{np.nanmedian(col('leg_p95_mm')):.2f} | {100 * np.median(col('valid_on_leg')):.1f}% | "
            f"{np.median(col('leg_px')):.0f} | {np.median(col('shank_px')):.0f} | "
            f"{camera.ground_sample_m(BELT_DEPTH_M) * 1000:.2f} |"
        )


if __name__ == "__main__":
    main()
