r"""Generate simulated leg frames and train the learned leg segmenter on CPU.

Pre-registered in `experiments/2026-09-15-leg-segmentation.md`: training legs
come from `leg_population(100, seed=1)`, a different population from the 20
test legs (seed 0); 10 frames per leg at random feasible poses plus one
empty-belt frame; the Gemini 335L noise model; validation on the last 10 legs.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/train/leg_segmenter.py

Frames are cached under `outputs/` (gitignored). The checkpoint is written as
`outputs/checkpoints/legunet-simlegs100-<git sha>-<step>.pt` with a JSON log
beside it.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from applications.pork_leg_alignment.perception.learned_leg_segmentation import LegUNet, frame_to_input, mask_to_target
from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import leg_half_width_m, leg_population
from applications.pork_leg_alignment.sim.scene import FAR_RAIL_INNER_Y_M, CellConfig
from applications.pork_leg_alignment.sim.sensing import CameraSpec
from robotics.core.camera_frame import CameraFrameData
from robotics.hardware.arms import ArmModel
from robotics.hardware.cameras import GEMINI_335L, EdgeEffects, sense_depth
from robotics.hardware.grippers import GripperModel

logger = logging.getLogger("train_leg_segmenter")

CAM = GEMINI_335L.name
OUT_OF_VIEW_X_M = 1.3
DATA_SEED = 20260916
TRAIN_SEED = 1
OUTPUTS = Path("outputs")


def _git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def generate(legs: int, frames_per_leg: int, edges: EdgeEffects | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Render training frames. Returns inputs (N, 4, H, W) float16, targets (N, H, W) uint8, leg index (N,)."""
    rng = np.random.default_rng(DATA_SEED)
    spec = {CAM: CameraSpec(CAM, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)}
    inputs, targets, owners = [], [], []
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
            poses: list[tuple[float, float, float] | None] = [None]  # one empty-belt frame
            for _ in range(frames_per_leg):
                yaw = math.radians(rng.uniform(-40.0, 40.0))
                reach = 0.5 * leg.length_m * math.cos(yaw) + widest * abs(math.sin(yaw))
                centre_y = FAR_RAIL_INNER_Y_M - rng.uniform(0.010, 0.150) - reach
                poses.append((rng.uniform(-0.75, -0.05), centre_y, yaw))
            for pose in poses:
                if pose is None:
                    cell.place_product(OUT_OF_VIEW_X_M, 0.5, -math.pi / 2, settle_s=0.05)
                else:
                    x_c, y_c, yaw = pose
                    heading = -math.pi / 2 + yaw
                    cell.place_product(
                        x_c - leg.outline_centre_m * math.cos(heading),
                        y_c - leg.outline_centre_m * math.sin(heading),
                        heading,
                        settle_s=0.2,
                    )
                _, frame = cell.observe(CAM)
                truth = cell.ground_truth(CAM).piece_mask
                assert frame is not None and truth is not None
                noisy = CameraFrameData(
                    frame.stamp_s,
                    frame.rgb,
                    sense_depth(frame.depth_m, GEMINI_335L, rng, edges=edges),
                    frame.intrinsics,
                    frame.camera,
                )
                inputs.append(frame_to_input(noisy).astype(np.float16))
                targets.append(mask_to_target(truth).astype(np.uint8))
                owners.append(leg_index)
        logger.info("rendered leg %d/%d", leg_index + 1, legs)
    return np.stack(inputs), np.stack(targets), np.array(owners)


def _dice_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    probability = torch.sigmoid(logits)
    intersection = (probability * target).sum(dim=(1, 2, 3))
    total = probability.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3))
    return (1.0 - (2.0 * intersection + 1.0) / (total + 1.0)).mean()


def _iou(logits: torch.Tensor, target: torch.Tensor) -> float:
    predicted = logits > 0
    truth = target > 0.5
    union = (predicted | truth).sum().item()
    return float((predicted & truth).sum().item() / union) if union else 1.0


def main() -> None:
    """Render or load the data, train, and save the best checkpoint by validation IoU."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--legs", type=int, default=100)
    parser.add_argument("--frames-per-leg", type=int, default=10)
    parser.add_argument("--val-legs", type=int, default=10)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--width", type=int, default=16)
    parser.add_argument("--edge-effects", action="store_true", help="train on frames with the camera's edge artefacts")
    args = parser.parse_args()
    edges = EdgeEffects() if args.edge_effects else None
    tag = "edges" if args.edge_effects else ""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    torch.manual_seed(TRAIN_SEED)
    np.random.seed(TRAIN_SEED)
    logger.info("seeds: data %d, train %d; torch threads %d", DATA_SEED, TRAIN_SEED, torch.get_num_threads())

    cache = OUTPUTS / f"legseg-data-legs{args.legs}-f{args.frames_per_leg}{tag}-seed{DATA_SEED}.npz"
    if cache.exists():
        loaded = np.load(cache)
        inputs, targets, owners = loaded["inputs"], loaded["targets"], loaded["owners"]
    else:
        cache.parent.mkdir(parents=True, exist_ok=True)
        inputs, targets, owners = generate(args.legs, args.frames_per_leg, edges)
        np.savez(cache, inputs=inputs, targets=targets, owners=owners)
    val = owners >= args.legs - args.val_legs
    train_x = torch.from_numpy(inputs[~val]).float()
    train_y = torch.from_numpy(targets[~val]).float()[:, None]
    val_x = torch.from_numpy(inputs[val]).float()
    val_y = torch.from_numpy(targets[val]).float()[:, None]
    logger.info("frames: %d train, %d validation", len(train_x), len(val_x))

    model = LegUNet(width=args.width)
    parameters = sum(p.numel() for p in model.parameters())
    optimiser = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    bce = nn.BCEWithLogitsLoss()
    sha = _git_sha()
    ckpt_dir = OUTPUTS / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    history, best_iou, best_path, step = [], -1.0, None, 0
    started = time.perf_counter()
    for epoch in range(args.epochs):
        model.train()
        order = torch.randperm(len(train_x))
        losses = []
        for start in range(0, len(order), args.batch):
            batch = order[start : start + args.batch]
            logits = model(train_x[batch])
            loss = bce(logits, train_y[batch]) + _dice_loss(logits, train_y[batch])
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            losses.append(float(loss.item()))
            step += 1
        model.eval()
        with torch.inference_mode():
            ious = [
                _iou(model(val_x[i : i + args.batch]), val_y[i : i + args.batch])
                for i in range(0, len(val_x), args.batch)
            ]
        val_iou = float(np.mean(ious))
        history.append({"epoch": epoch + 1, "step": step, "train_loss": float(np.mean(losses)), "val_iou": val_iou})
        logger.info("epoch %d: train loss %.4f, validation IoU %.4f", epoch + 1, np.mean(losses), val_iou)
        if val_iou > best_iou:
            best_iou = val_iou
            best_path = ckpt_dir / f"legunet-simlegs{args.legs}{tag}-{sha}-{step}.pt"
            torch.save({"width": args.width, "state_dict": model.state_dict()}, best_path)
    log = {
        "checkpoint": str(best_path),
        "best_val_iou": best_iou,
        "parameters": parameters,
        "train_seconds": time.perf_counter() - started,
        "torch_threads": torch.get_num_threads(),
        "args": vars(args),
        "history": history,
    }
    (ckpt_dir / f"legunet-simlegs{args.legs}{tag}-{sha}.json").write_text(json.dumps(log, indent=1))
    print(json.dumps({k: v for k, v in log.items() if k != "history"}, indent=1))


if __name__ == "__main__":
    main()
