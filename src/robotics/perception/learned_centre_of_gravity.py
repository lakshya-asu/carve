"""A learned correction on top of the column centroid.

The column centroid (`centre_of_gravity.py`) leaves a bias that is not noise: about 7 mm toward the
trotter, where the columns under the lifted trotter are partly air, and larger when the camera sees
the leg from an angle (`experiments/2026-09-15-centre-of-gravity.md`). This model does not replace
the geometry. It takes the column centroid as given and predicts only how far to move it on the
belt, so a bad prediction is bounded by what the model learned, and the geometric answer is always
there to check it against.

Input: the leg's top surface resampled onto a 96 x 96 grid of 10 mm cells on the belt, centred on
the column centroid, plus where that centroid sits relative to the camera, because the bias depends
on viewing angle. Output: the offset (x, y) on the belt, world axes, millimetres.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from robotics.core.camera_frame import CameraFrameData
from robotics.perception.centre_of_gravity import CentreOfGravityEstimate, column_centroid
from robotics.perception.depth_geometry import MIN_VALID_DEPTH_M, Plane, ray_directions

GRID_CELLS = 96
CELL_M = 0.010
# Heights are divided by this so a ham's top, about 0.2 m, sits near 1.
HEIGHT_SCALE_M = 0.2


def belt_height_grid(frame: CameraFrameData, mask: np.ndarray, plane: Plane, centre_m: np.ndarray) -> np.ndarray:
    """Highest seen surface above each 10 mm cell of belt around `centre_m`: (96, 96) float32, rows along world y.

    Cells no leg pixel falls in are 0. Heights are divided by `HEIGHT_SCALE_M`.
    """
    directions = ray_directions(frame)[mask]
    depth_m = frame.depth_m[mask]
    usable = depth_m > MIN_VALID_DEPTH_M
    points = frame.camera.position_m + directions[usable] * depth_m[usable, None]
    height = np.clip(plane.height_of(points), 0.0, None) / HEIGHT_SCALE_M
    col = np.floor((points[:, 0] - centre_m[0]) / CELL_M + GRID_CELLS / 2).astype(int)
    row = np.floor((points[:, 1] - centre_m[1]) / CELL_M + GRID_CELLS / 2).astype(int)
    inside = (col >= 0) & (col < GRID_CELLS) & (row >= 0) & (row < GRID_CELLS)
    grid = np.zeros((GRID_CELLS, GRID_CELLS), dtype=np.float32)
    np.maximum.at(grid, (row[inside], col[inside]), height[inside].astype(np.float32))
    return grid


def correction_inputs(
    frame: CameraFrameData, mask: np.ndarray, plane: Plane
) -> tuple[np.ndarray, np.ndarray, CentreOfGravityEstimate]:
    """Height grid (96, 96), camera-relative position (2,) in metres, and the column centroid they are centred on."""
    column = column_centroid(frame, mask, plane)
    grid = belt_height_grid(frame, mask, plane, column.position_m)
    from_camera = (column.position_m[:2] - frame.camera.position_m[:2]).astype(np.float32)
    return grid, from_camera, column


class CentreCorrectionNet(nn.Module):
    """Offset from the column centroid to the centre of mass, mm, from the height grid and camera-relative position.

    Convolutions shrink the grid to 6 x 6 and keep where things are, which a global pool would throw
    away: the offset is about where the mass lies relative to the grid's centre.
    """

    def __init__(self, width: int = 16) -> None:
        """Build the network; `width` is the first layer's channel count."""
        super().__init__()

        def block(channels_in: int, channels_out: int) -> nn.Sequential:
            return nn.Sequential(
                nn.Conv2d(channels_in, channels_out, 3, padding=1), nn.ReLU(inplace=True), nn.MaxPool2d(2)
            )

        self.features = nn.Sequential(
            block(1, width), block(width, 2 * width), block(2 * width, 4 * width), block(4 * width, 4 * width)
        )
        self.head = nn.Sequential(nn.Linear(4 * width * 6 * 6 + 2, 64), nn.ReLU(inplace=True), nn.Linear(64, 2))

    def forward(self, grid: torch.Tensor, from_camera: torch.Tensor) -> torch.Tensor:
        """Offsets (B, 2) in mm from grids (B, 1, 96, 96) and camera-relative positions (B, 2) in metres."""
        return self.head(torch.cat([self.features(grid).flatten(1), from_camera], dim=1))  # type: ignore[no-any-return]


class LearnedCentreOfGravity:
    """Column centroid moved by the learned offset; the same result type as the geometric estimators."""

    name = "column-centroid-plus-learned-offset"

    def __init__(self, checkpoint: Path, threads: int | None = None) -> None:
        """Load a checkpoint written by `scripts/train_centre_correction.py`: {"width", "state_dict"}."""
        if threads is not None:
            torch.set_num_threads(threads)
        saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
        self.model = CentreCorrectionNet(width=int(saved["width"]))
        self.model.load_state_dict(saved["state_dict"])
        self.model.eval()

    def estimate(self, frame: CameraFrameData, mask: np.ndarray, plane: Plane) -> CentreOfGravityEstimate:
        """Column centroid plus the predicted offset on the belt; time covers both.

        Raises:
            ValueError: As `column_centroid` does.
        """
        started = time.perf_counter()
        grid, from_camera, column = correction_inputs(frame, mask, plane)
        with torch.inference_mode():
            offset_mm = self.model(torch.from_numpy(grid)[None, None], torch.from_numpy(from_camera)[None])[0].numpy()
        position = column.position_m + np.array([offset_mm[0], offset_mm[1], 0.0]) / 1000.0
        return CentreOfGravityEstimate(
            position, column.volume_m3, column.pixels, 1000.0 * (time.perf_counter() - started)
        )
