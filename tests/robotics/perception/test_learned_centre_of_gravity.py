"""Learned centre-of-gravity correction: the height grid it reads, and that it only moves the column centroid."""

from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from robotics.core.camera_frame import CameraFrameData  # noqa: E402
from robotics.core.frames import CameraPose, Intrinsics  # noqa: E402
from robotics.perception.centre_of_gravity import column_centroid  # noqa: E402
from robotics.perception.depth_geometry import Plane  # noqa: E402
from robotics.perception.learned_centre_of_gravity import (  # noqa: E402
    CELL_M,
    GRID_CELLS,
    HEIGHT_SCALE_M,
    CentreCorrectionNet,
    LearnedCentreOfGravity,
    belt_height_grid,
)

CAMERA_HEIGHT_M = 0.95
BELT = Plane(normal=np.array([0.0, 0.0, 1.0]), offset_m=0.0, inlier_fraction=1.0, rms_residual_m=0.0)


def _block_frame(x0: float, x1: float, y0: float, y1: float, top_m: float) -> tuple[CameraFrameData, np.ndarray]:
    """A camera looking straight down at one flat-topped block on the belt."""
    intr = Intrinsics(600.0, 600.0, 319.5, 239.5, 640, 480)
    cols, rows = np.meshgrid(np.arange(640), np.arange(480))
    z = CAMERA_HEIGHT_M - top_m
    x, y = (cols - intr.cx) / intr.fx * z, -(rows - intr.cy) / intr.fy * z
    mask = (x >= x0) & (x < x1) & (y >= y0) & (y < y1)
    depth = np.where(mask, z, CAMERA_HEIGHT_M).astype(np.float32)
    camera = CameraPose(np.array([0.0, 0.0, CAMERA_HEIGHT_M]), np.eye(3))
    return CameraFrameData(0.0, np.zeros((480, 640, 3), np.uint8), depth, intr, camera), mask


def test_grid_puts_the_surface_in_the_cells_under_it() -> None:
    frame, mask = _block_frame(0.02, 0.12, -0.03, 0.03, 0.08)
    grid = belt_height_grid(frame, mask, BELT, centre_m=np.zeros(3))
    rows, cols = np.nonzero(grid)
    centre = GRID_CELLS // 2
    assert cols.min() == centre + round(0.02 / CELL_M) and cols.max() == centre + round(0.12 / CELL_M) - 1
    assert rows.min() == centre - round(0.03 / CELL_M) and rows.max() == centre + round(0.03 / CELL_M) - 1
    assert grid.max() == pytest.approx(0.08 / HEIGHT_SCALE_M, rel=1e-4)


def test_network_returns_one_offset_per_leg() -> None:
    offsets = CentreCorrectionNet(width=4)(torch.zeros(3, 1, GRID_CELLS, GRID_CELLS), torch.zeros(3, 2))
    assert offsets.shape == (3, 2)


def test_a_zero_correction_returns_the_column_centroid(tmp_path: Path) -> None:
    model = CentreCorrectionNet(width=4)
    torch.nn.init.zeros_(model.head[-1].weight)
    torch.nn.init.zeros_(model.head[-1].bias)
    checkpoint = tmp_path / "zero.pt"
    torch.save({"width": 4, "state_dict": model.state_dict()}, checkpoint)
    frame, mask = _block_frame(-0.10, 0.10, -0.05, 0.05, 0.10)
    learned = LearnedCentreOfGravity(checkpoint).estimate(frame, mask, BELT)
    assert np.allclose(learned.position_m, column_centroid(frame, mask, BELT).position_m)
    assert learned.elapsed_ms > 0
