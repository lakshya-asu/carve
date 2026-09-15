"""A small learned leg segmenter, measured against the depth-geometry one.

The comparison asked for at every pipeline step: what does learning buy over
geometry, and what does it cost to run. This model takes the camera's colour and
depth, shrunk to 320 x 200, and predicts a leg probability per pixel. It returns
the same `LegSegmentation` as `leg_segmentation.LegSegmenter`, so the two swap in
one line or run together, one checking the other.

Post-processing is the same as the geometric method (largest piece, refuse when
empty or touching the image border), so a difference between the two comes from
the model, not from what happens after it.
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn

from meat_cell_sim.leg_segmentation import LegSegmentation
from meat_cell_sim.segmentation import largest_component
from meat_cell_sim.sensing import CameraFrameData

INPUT_W_PX, INPUT_H_PX = 320, 200
# Depth is divided by this so the belt at 0.95 m sits near 0.5, alongside colour in [0, 1].
DEPTH_SCALE_M = 2.0
MIN_LEG_PIXELS = 5000


def frame_to_input(frame: CameraFrameData) -> np.ndarray:
    """Model input for one frame: (4, 200, 320) float32, colour in [0, 1] then scaled depth."""
    size = (INPUT_W_PX, INPUT_H_PX)
    rgb = cv2.resize(frame.rgb, size, interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    depth_m = frame.depth_m.astype(np.float32)
    # Area averages keep every input and the target centred on the same pixels; zero depth is a
    # dropout, so it is left out of the average rather than pulling it toward the camera.
    depth_mean = cv2.resize(depth_m, size, interpolation=cv2.INTER_AREA)
    valid_share = cv2.resize((depth_m > 0).astype(np.float32), size, interpolation=cv2.INTER_AREA)
    depth = np.divide(depth_mean, valid_share, out=np.zeros_like(depth_mean), where=valid_share > 0)
    return np.concatenate([rgb.transpose(2, 0, 1), (depth / DEPTH_SCALE_M)[None]], axis=0).astype(np.float32)


def mask_to_target(mask: np.ndarray) -> np.ndarray:
    """Training target for one mask: (200, 320) float32 in {0, 1}, a pixel is leg if most of its block is."""
    # Nearest-neighbour shrinking samples each 4 x 4 block's top-left pixel, which moved every label
    # 1.5 px up and left, about 3 mm on the belt (experiments/2026-09-15-leg-segmentation.md).
    share = cv2.resize(mask.astype(np.float32), (INPUT_W_PX, INPUT_H_PX), interpolation=cv2.INTER_AREA)
    return (share >= 0.5).astype(np.float32)


class _DoubleConv(nn.Module):
    def __init__(self, channels_in: int, channels_out: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(channels_in, channels_out, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels_out),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels_out, channels_out, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels_out),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)  # type: ignore[no-any-return]


class LegUNet(nn.Module):
    """U-Net with four scales, 16 to 128 channels. Input (B, 4, 200, 320), output logits (B, 1, 200, 320)."""

    def __init__(self, width: int = 16) -> None:
        """Build the network; `width` is the channel count at full resolution."""
        super().__init__()
        widths = [width, 2 * width, 4 * width, 8 * width]
        self.down = nn.ModuleList()
        channels = 4
        for w in widths:
            self.down.append(_DoubleConv(channels, w))
            channels = w
        self.pool = nn.MaxPool2d(2)
        self.up = nn.ModuleList()
        self.merge = nn.ModuleList()
        for w in reversed(widths[:-1]):
            self.up.append(nn.ConvTranspose2d(channels, w, 2, stride=2))
            self.merge.append(_DoubleConv(2 * w, w))
            channels = w
        self.head = nn.Conv2d(channels, 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Leg logits for a batch: (B, 4, 200, 320) float32 in, (B, 1, 200, 320) out."""
        skips = []
        for index, block in enumerate(self.down):
            x = block(x)
            if index < len(self.down) - 1:
                skips.append(x)
                x = self.pool(x)
        for up, merge, skip in zip(self.up, self.merge, reversed(skips), strict=True):
            x = up(x)
            # 200 and 320 are not powers of two, so the upsampled map can be a pixel short.
            x = nn.functional.pad(x, [0, skip.shape[3] - x.shape[3], 0, skip.shape[2] - x.shape[2]])
            x = merge(torch.cat([x, skip], dim=1))
        return self.head(x)  # type: ignore[no-any-return]


class LearnedLegSegmenter:
    """Run a trained `LegUNet` on full-size camera frames."""

    name = "learned-unet-leg"

    def __init__(self, checkpoint: Path, threshold: float = 0.5, threads: int | None = None) -> None:
        """Load weights for CPU inference.

        Args:
            checkpoint: File saved by `scripts/train_leg_segmenter.py`.
            threshold: Probability above which a pixel is leg.
            threads: CPU threads for inference; None keeps torch's default.
        """
        saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
        self.model = LegUNet(width=int(saved["width"]))
        self.model.load_state_dict(saved["state_dict"])
        self.model.eval()
        self.threshold = threshold
        if threads is not None:
            torch.set_num_threads(threads)

    def segment(self, frame: CameraFrameData) -> LegSegmentation:
        """Find the leg in one frame, or refuse and say why."""
        started = time.perf_counter()
        with torch.inference_mode():
            logits = self.model(torch.from_numpy(frame_to_input(frame))[None])
        probability = torch.sigmoid(logits)[0, 0].numpy()
        height, width = frame.depth_m.shape
        full = cv2.resize(probability, (width, height), interpolation=cv2.INTER_LINEAR) > self.threshold
        mask = largest_component(full) if full.any() else full
        pixels = int(mask.sum())
        diagnostics = {"mask_pixels": float(pixels), "mean_probability": float(probability.mean())}

        def finish(refused: str | None) -> LegSegmentation:
            kept = mask if refused is None else np.zeros_like(mask)
            return LegSegmentation(kept, refused, 1000.0 * (time.perf_counter() - started), diagnostics)

        if pixels == 0:
            return finish("model found no leg")
        if pixels < MIN_LEG_PIXELS:
            return finish(f"largest piece is {pixels} px, under {MIN_LEG_PIXELS}")
        if mask[0, :].any() or mask[-1, :].any() or mask[:, 0].any() or mask[:, -1].any():
            return finish("leg runs off the image edge")
        return finish(None)
