"""Learned leg segmenter: input preparation, model shapes, and the shared result type."""

from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from meat_cell_sim.frames import CameraPose, Intrinsics  # noqa: E402
from meat_cell_sim.learned_segmentation import (  # noqa: E402
    DEPTH_SCALE_M,
    INPUT_H_PX,
    INPUT_W_PX,
    LearnedLegSegmenter,
    LegUNet,
    frame_to_input,
    mask_to_target,
)
from meat_cell_sim.leg_segmentation import LegSegmentation  # noqa: E402
from meat_cell_sim.sensing import CameraFrameData  # noqa: E402


def _frame(height: int = 800, width: int = 1280) -> CameraFrameData:
    rgb = np.full((height, width, 3), 255, dtype=np.uint8)
    depth = np.full((height, width), 0.95, dtype=np.float32)
    intr = Intrinsics(640.0, 628.0, (width - 1) / 2, (height - 1) / 2, width, height)
    return CameraFrameData(0.0, rgb, depth, intr, CameraPose(np.array([0.0, 0.0, 1.85]), np.eye(3)))


def test_input_is_colour_then_scaled_depth_at_model_size() -> None:
    x = frame_to_input(_frame())
    assert x.shape == (4, INPUT_H_PX, INPUT_W_PX)
    assert x.dtype == np.float32
    assert np.allclose(x[:3], 1.0)
    assert np.allclose(x[3], 0.95 / DEPTH_SCALE_M)


def test_target_is_binary_at_model_size() -> None:
    mask = np.zeros((800, 1280), dtype=bool)
    mask[300:500, 400:900] = True
    target = mask_to_target(mask)
    assert target.shape == (INPUT_H_PX, INPUT_W_PX)
    assert set(np.unique(target)) == {0.0, 1.0}


def test_target_shrunk_and_grown_back_keeps_the_mask_in_place() -> None:
    import cv2

    mask = np.zeros((800, 1280), dtype=np.uint8)
    cv2.ellipse(mask, (640, 400), (300, 90), 20, 0, 360, 1, -1)
    grown = cv2.resize(mask_to_target(mask.astype(bool)), (1280, 800), interpolation=cv2.INTER_LINEAR) > 0.5
    rows, cols = np.nonzero(mask)
    grown_rows, grown_cols = np.nonzero(grown)
    # The segmenter grows its output back this way; a label sampled off-centre moves the leg by 1.5 px.
    assert abs(grown_cols.mean() - cols.mean()) < 0.25
    assert abs(grown_rows.mean() - rows.mean()) < 0.25


def test_depth_dropouts_do_not_pull_the_input_depth_toward_the_camera() -> None:
    frame = _frame()
    frame.depth_m[::2, ::2] = 0.0  # a quarter of the pixels lost
    assert np.allclose(frame_to_input(frame)[3], 0.95 / DEPTH_SCALE_M)


def test_unet_keeps_the_input_size_despite_odd_scales() -> None:
    logits = LegUNet(width=4)(torch.zeros(2, 4, INPUT_H_PX, INPUT_W_PX))
    assert logits.shape == (2, 1, INPUT_H_PX, INPUT_W_PX)


def test_segmenter_returns_the_same_result_type_as_the_geometric_one(tmp_path: Path) -> None:
    checkpoint = tmp_path / "untrained.pt"
    torch.save({"width": 4, "state_dict": LegUNet(width=4).state_dict()}, checkpoint)
    result = LearnedLegSegmenter(checkpoint).segment(_frame())
    assert isinstance(result, LegSegmentation)
    assert result.mask.shape == (800, 1280)
    assert result.elapsed_ms > 0
