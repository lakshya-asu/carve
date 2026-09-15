r"""Train the learned correction to the column centroid, as pre-registered.

`experiments/2026-09-15-centre-of-gravity.md`, follow-up: training legs from
`leg_population(100, seed=1)`, never the 20 test legs (seed 0); 10 frames per leg at random
feasible poses (yaw within 40 degrees of square, far end 10 to 150 mm from the rail, anywhere
under the camera); each frame through the Gemini 335L model with datasheet noise or noise plus edge
effects (chosen at random), segmented by the geometric segmenter, so the training input is what the
cell would really have. Target: the true centre of mass minus the column centroid on the belt, mm.
Validation on the last 10 training legs.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/train/centre_correction.py

Writes `outputs/checkpoints/centrenet-simlegs100-<git sha>-<step>.pt` and a JSON log beside it;
rendered data is cached in `outputs/`.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch

from applications.pork_leg_alignment.perception.leg_segmentation import EmptyBeltReference, LegSegmenter
from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import leg_half_width_m, leg_population
from applications.pork_leg_alignment.sim.scene import FAR_RAIL_INNER_Y_M, CellConfig
from applications.pork_leg_alignment.sim.sensing import CameraSpec
from robotics.hardware.arms import ArmModel
from robotics.hardware.cameras import GEMINI_335L, EdgeEffects, sense_depth
from robotics.hardware.grippers import GripperModel
from robotics.perception.learned_centre_of_gravity import CentreCorrectionNet, correction_inputs

logger = logging.getLogger("train_centre_correction")

CAM = GEMINI_335L.name
OUT_OF_VIEW_X_M = 1.3
DATA_SEED = 20260917
TRAIN_SEED = 1
OUTPUTS = Path("outputs")


def generate(legs: int, frames_per_leg: int) -> dict[str, np.ndarray]:
    """Render and segment the training frames; arrays grids (N, 96, 96), from_camera (N, 2), offsets (N, 2), owners (N,)."""
    rng = np.random.default_rng(DATA_SEED)
    cameras = {"noise": None, "edges": EdgeEffects()}
    spec = {CAM: CameraSpec(CAM, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)}
    grids, from_cameras, offsets, owners, refused = [], [], [], [], 0
    for leg_index, leg in enumerate(leg_population(legs, seed=1)):
        config = CellConfig(
            belt_speed_mps=0.30,
            leg=leg,
            arm=ArmModel.UR20,
            gripper=GripperModel.JAW_GEH6180,
            depth_cameras=(GEMINI_335L,),
            depth_camera_yaw_deg=90.0,
        )
        widest = float(leg_half_width_m(leg, np.linspace(0.0, 1.0, 101)).max())
        with Cell(config, spec) as cell:
            cell.reset()
            cell.place_product(OUT_OF_VIEW_X_M, 0.5, -math.pi / 2, settle_s=0.05)
            segmenters = {}
            for camera, edges in cameras.items():
                empties = []
                for _ in range(10):
                    _, empty = cell.observe(CAM)
                    assert empty is not None
                    empties.append(replace(empty, depth_m=sense_depth(empty.depth_m, GEMINI_335L, rng, edges=edges)))
                segmenters[camera] = LegSegmenter(EmptyBeltReference.from_frames(empties))
            for _ in range(frames_per_leg):
                yaw = math.radians(rng.uniform(-40.0, 40.0))
                reach = 0.5 * leg.length_m * math.cos(yaw) + widest * abs(math.sin(yaw))
                centre_y = FAR_RAIL_INNER_Y_M - rng.uniform(0.010, 0.150) - reach
                heading = -math.pi / 2 + yaw
                cell.reset()
                cell.place_product(
                    rng.uniform(-0.75, -0.05) - leg.outline_centre_m * math.cos(heading),
                    centre_y - leg.outline_centre_m * math.sin(heading),
                    heading,
                    settle_s=0.2,
                )
                _, frame = cell.observe(CAM)
                truth = cell.ground_truth(CAM)
                assert frame is not None and truth.centre_of_mass_m is not None
                camera = str(rng.choice(list(cameras)))
                noisy = replace(frame, depth_m=sense_depth(frame.depth_m, GEMINI_335L, rng, edges=cameras[camera]))
                segmenter = segmenters[camera]
                segmented = segmenter.segment(noisy)
                if not segmented.accepted:
                    refused += 1
                    continue
                grid, from_camera, column = correction_inputs(noisy, segmented.mask, segmenter.reference.plane)
                grids.append(grid.astype(np.float16))
                from_cameras.append(from_camera)
                offsets.append(1000.0 * (truth.centre_of_mass_m - column.position_m)[:2])
                owners.append(leg_index)
        logger.info("rendered leg %d/%d (%d frames refused so far)", leg_index + 1, legs, refused)
    return {
        "grids": np.stack(grids),
        "from_camera": np.stack(from_cameras).astype(np.float32),
        "offsets_mm": np.stack(offsets).astype(np.float32),
        "owners": np.array(owners),
    }


def main() -> None:
    """Render or load the data, train, and keep the checkpoint with the lowest validation median error."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--legs", type=int, default=100)
    parser.add_argument("--frames-per-leg", type=int, default=10)
    parser.add_argument("--val-legs", type=int, default=10)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--width", type=int, default=16)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    torch.manual_seed(TRAIN_SEED)
    logger.info("seeds: data %d, train %d; torch threads %d", DATA_SEED, TRAIN_SEED, torch.get_num_threads())

    cache = OUTPUTS / f"cog-data-legs{args.legs}-f{args.frames_per_leg}-seed{DATA_SEED}.npz"
    if cache.exists():
        data = dict(np.load(cache))
    else:
        data = generate(args.legs, args.frames_per_leg)
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, **data)
    val = data["owners"] >= args.legs - args.val_legs
    grids = torch.from_numpy(data["grids"].astype(np.float32))[:, None]
    from_camera = torch.from_numpy(data["from_camera"])
    offsets = torch.from_numpy(data["offsets_mm"])
    logger.info(
        "frames: %d train, %d validation; offset to learn, mm: median %.1f, worst %.1f",
        int((~val).sum()),
        int(val.sum()),
        float(np.median(np.hypot(*data["offsets_mm"].T))),
        float(np.hypot(*data["offsets_mm"].T).max()),
    )
    train_index, val_index = torch.from_numpy(np.flatnonzero(~val)), torch.from_numpy(np.flatnonzero(val))

    model = CentreCorrectionNet(width=args.width)
    parameters = sum(p.numel() for p in model.parameters())
    optimiser = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    ckpt_dir = OUTPUTS / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    best_error, best_path, step, history = math.inf, None, 0, []
    for epoch in range(args.epochs):
        model.train()
        losses = []
        for batch in train_index[torch.randperm(len(train_index))].split(args.batch):
            prediction = model(grids[batch], from_camera[batch])
            loss = torch.nn.functional.smooth_l1_loss(prediction, offsets[batch], beta=1.0)
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            losses.append(float(loss))
            step += 1
        model.eval()
        with torch.inference_mode():
            residual = model(grids[val_index], from_camera[val_index]) - offsets[val_index]
        val_error = float(residual.norm(dim=1).median())
        history.append(
            {"epoch": epoch + 1, "step": step, "train_loss": float(np.mean(losses)), "val_median_mm": val_error}
        )
        logger.info("epoch %d: train loss %.3f, validation median error %.2f mm", epoch + 1, np.mean(losses), val_error)
        if val_error < best_error:
            best_error = val_error
            best_path = ckpt_dir / f"centrenet-simlegs{args.legs}-{sha}-{step}.pt"
            torch.save({"width": args.width, "state_dict": model.state_dict()}, best_path)
    log = {
        "checkpoint": str(best_path),
        "best_val_median_mm": best_error,
        "parameters": parameters,
        "train_seconds": time.perf_counter() - started,
        "torch_threads": torch.get_num_threads(),
        "args": vars(args),
        "history": history,
    }
    (ckpt_dir / f"centrenet-simlegs{args.legs}-{sha}.json").write_text(json.dumps(log, indent=1))
    print(json.dumps({k: v for k, v in log.items() if k != "history"}, indent=1))


if __name__ == "__main__":
    main()
