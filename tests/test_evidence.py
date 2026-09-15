"""The depth-first pipeline.

Two tests carry findings rather than behaviour. `test_height_band_excludes_the
_guide_rails` pins the defect that made the first version select a rail on every
frame. `test_confirmation_survives_a_lighting_change` pins the one that made it
reject correctly segmented product at the dim end of a lighting gradient.
"""

import numpy as np
import pytest

from meat_cell_sim.appearance import depth_systematic_warp, lighting_gradient
from meat_cell_sim.evidence import (
    BeltReference,
    ColourConfirmation,
    DepthHeightProposal,
    EdgeSnapRefinement,
    HeightWatershedSplit,
    Segmenter,
    fit_plane_ransac,
)
from meat_cell_sim.frames import CameraPose, Intrinsics
from meat_cell_sim.sensing import CameraFrameData

WIDTH, HEIGHT = 320, 240
CAMERA_Z_M = 1.50
BELT_Z_M = 0.90
PRODUCT_RGB = (184, 71, 77)
BELT_RGB = (36, 41, 46)


def _frame(height_field_m: np.ndarray, rgb: np.ndarray | None = None) -> CameraFrameData:
    """A nadir camera over a belt, with product standing at the given heights."""
    intr = Intrinsics.from_fovy(52.0, WIDTH, HEIGHT)
    depth = (CAMERA_Z_M - (BELT_Z_M + height_field_m)).astype(np.float32)
    if rgb is None:
        rgb = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        rgb[:] = BELT_RGB
        rgb[height_field_m > 0.001] = PRODUCT_RGB
    return CameraFrameData(
        stamp_s=1.0,
        rgb=rgb,
        depth_m=depth,
        intrinsics=intr,
        camera=CameraPose(np.array([0.0, 0.0, CAMERA_Z_M]), np.eye(3)),
    )


def _slab(w: int, h: int, cx: int, cy: int, thickness_m: float = 0.030) -> np.ndarray:
    field = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
    field[cy - h // 2 : cy + h // 2, cx - w // 2 : cx + w // 2] = thickness_m
    return field


def test_plane_fit_recovers_a_known_plane_and_reports_its_confidence() -> None:
    rng = np.random.default_rng(0)
    points = np.column_stack([rng.uniform(-1, 1, 4000), rng.uniform(-1, 1, 4000), np.full(4000, 0.9)])
    points[:200, 2] = 0.95  # outliers standing above it
    plane = fit_plane_ransac(points, tolerance_m=0.004, rng=rng)
    assert plane.normal == pytest.approx([0.0, 0.0, 1.0], abs=1e-6)
    assert plane.offset_m == pytest.approx(-0.9, abs=1e-6)
    assert plane.inlier_fraction == pytest.approx(0.95, abs=0.01)
    assert plane.rms_residual_m < 1e-6


def test_plane_normal_always_points_up() -> None:
    """Height above the belt must be positive whichever trio RANSAC drew."""
    rng = np.random.default_rng(3)
    points = np.column_stack([rng.uniform(-1, 1, 2000), rng.uniform(-1, 1, 2000), np.full(2000, 0.9)])
    for seed in range(5):
        assert fit_plane_ransac(points, 0.004, np.random.default_rng(seed)).normal[2] > 0


def test_depth_proposal_finds_the_product() -> None:
    proposal = DepthHeightProposal(seed=1)
    truth = _slab(120, 60, WIDTH // 2, HEIGHT // 2)
    candidate = proposal.propose(_frame(truth))
    assert candidate.mask.sum() == pytest.approx((truth > 0).sum(), rel=0.02)
    assert candidate.confidence > 0.8
    assert candidate.diagnostics["median_height_m"] == pytest.approx(0.030, abs=0.002)


def test_height_band_excludes_the_guide_rails() -> None:
    """Everything standing proud of the belt is not the product.

    The cell's rails stand 90 mm above the belt and are far larger than a slab,
    so a largest-component rule with no ceiling picked a rail on every frame.
    """
    field = _slab(100, 50, WIDTH // 2, HEIGHT // 2)
    field[0:40, :] = 0.090  # a rail across the top, much larger than the product
    candidate = DepthHeightProposal(seed=1).propose(_frame(field))
    assert candidate.mask.any()
    assert not candidate.mask[0:40, :].any(), "the rail was selected as product"
    assert candidate.mask.sum() == pytest.approx(100 * 50, rel=0.05)


def test_missing_depth_is_excluded_rather_than_treated_as_belt() -> None:
    """Active stereo reports zero where it found no correspondence."""
    field = _slab(120, 60, WIDTH // 2, HEIGHT // 2)
    frame = _frame(field)
    depth = frame.depth_m.copy()
    depth[HEIGHT // 2 :, :] = 0.0
    holed = CameraFrameData(frame.stamp_s, frame.rgb, depth, frame.intrinsics, frame.camera)
    candidate = DepthHeightProposal(seed=1).propose(holed)
    assert candidate.diagnostics["depth_returned"] == pytest.approx(0.5, abs=0.01)
    assert not candidate.mask[HEIGHT // 2 :, :].any()


def test_a_frame_with_almost_no_depth_is_refused_not_guessed() -> None:
    field = _slab(120, 60, WIDTH // 2, HEIGHT // 2)
    frame = _frame(field)
    depth = np.zeros_like(frame.depth_m)
    depth[:20, :20] = frame.depth_m[:20, :20]
    dead = CameraFrameData(frame.stamp_s, frame.rgb, depth, frame.intrinsics, frame.camera)
    candidate = DepthHeightProposal(seed=1).propose(dead)
    assert candidate.confidence == 0.0
    assert not candidate.mask.any()


def test_confirmation_survives_a_lighting_change() -> None:
    """Comparing raw RGB rejected correct product at the dim end of a gradient.

    Chromaticity is a ratio between channels, and a lighting change scales all
    three together, so the test does not fail on the axis the design exists to
    be immune to.
    """
    field = _slab(120, 60, WIDTH // 2, HEIGHT // 2)
    mask = field > 0.001
    bright = _frame(field)
    dim = _frame(field, rgb=lighting_gradient(bright.rgb, 0.7))
    confirm = ColourConfirmation(np.array(PRODUCT_RGB, dtype=float))
    assert confirm.agreement(mask, bright) > 0.9
    assert confirm.agreement(mask, dim) > 0.9


def test_confirmation_rejects_a_mask_that_is_on_the_belt() -> None:
    field = _slab(120, 60, WIDTH // 2, HEIGHT // 2)
    frame = _frame(field)
    belt_region = np.zeros((HEIGHT, WIDTH), dtype=bool)
    belt_region[10:40, 10:60] = True
    confirm = ColourConfirmation(np.array(PRODUCT_RGB, dtype=float))
    assert confirm.agreement(belt_region, frame) < 0.25


def test_edge_snap_leaves_a_good_boundary_alone() -> None:
    field = _slab(120, 60, WIDTH // 2, HEIGHT // 2)
    frame = _frame(field)
    mask = field > 0.001
    snapped = EdgeSnapRefinement().refine(mask, frame)
    assert snapped.sum() == pytest.approx(mask.sum(), rel=0.05)


def test_edge_snap_does_not_move_the_boundary_when_there_is_no_edge_to_find() -> None:
    """Product and belt the same colour: the contour must stay where depth put it."""
    field = _slab(120, 60, WIDTH // 2, HEIGHT // 2)
    flat = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    flat[:] = PRODUCT_RGB
    frame = _frame(field, rgb=flat)
    mask = field > 0.001
    snapped = EdgeSnapRefinement().refine(mask, frame)
    assert snapped.sum() == pytest.approx(mask.sum(), rel=0.02)


def test_splitter_leaves_a_single_piece_alone() -> None:
    field = _slab(120, 60, WIDTH // 2, HEIGHT // 2)
    pieces = HeightWatershedSplit(seed=1).split(field > 0.001, _frame(field))
    assert len(pieces) == 1


def _touching_pair() -> np.ndarray:
    """Two slabs meeting at a corner, so their union has a waist.

    Two rectangles butted flush side by side are indistinguishable from one
    wider rectangle and there is nothing to split. What makes a touching pair
    separable is the narrowing where they meet.
    """
    field = _slab(70, 60, 105, HEIGHT // 2) + _slab(70, 60, 215, HEIGHT // 2)
    field[HEIGHT // 2 - 6 : HEIGHT // 2 + 6, 140:180] = 0.030
    return field


def test_splitter_separates_two_touching_pieces() -> None:
    """Two slabs in contact have a valley between them that colour cannot see."""
    field = _touching_pair()
    pieces = HeightWatershedSplit(seed=1).split(field > 0.001, _frame(field))
    assert len(pieces) == 2
    assert all(piece.sum() > 1000 for piece in pieces)


def test_segmenter_reports_which_stage_refused_a_frame() -> None:
    """A rejection has to be attributable, or a bad pose is a mystery."""
    field = _slab(120, 60, WIDTH // 2, HEIGHT // 2)
    frame = _frame(field)
    pipeline = Segmenter(
        proposals=[DepthHeightProposal(seed=1)],
        confirmation=ColourConfirmation(np.array([20.0, 200.0, 20.0])),  # expects green product
    )
    result = pipeline.segment(frame)
    assert not result.accepted
    assert result.rejected_by == "colour-confirm"
    assert "agreement" in str(result.reason)
    assert "depth-height" in result.record


def test_segmenter_runs_the_fusion_seam_even_with_one_channel() -> None:
    """The seam is exercised from the first day so a second channel is not a rewrite."""
    field = _slab(120, 60, WIDTH // 2, HEIGHT // 2)
    pipeline = Segmenter(proposals=[DepthHeightProposal(seed=1)])
    result = pipeline.segment(_frame(field))
    assert result.accepted
    assert result.record["fuse"]["channels"] == 1.0


def test_segmenter_refuses_touching_pieces_rather_than_grasping_two() -> None:
    field = _touching_pair()
    pipeline = Segmenter(proposals=[DepthHeightProposal(seed=1)], splitter=HeightWatershedSplit(seed=1))
    result = pipeline.segment(_frame(field))
    assert not result.accepted
    assert result.instances == 2
    assert "touching" in str(result.reason)


def test_a_pipeline_needs_at_least_one_channel() -> None:
    with pytest.raises(ValueError, match="at least one proposal channel"):
        Segmenter(proposals=[])


def test_height_cut_must_clear_the_plane_tolerance() -> None:
    """Otherwise belt noise is classified as product."""
    with pytest.raises(ValueError, match="must exceed the plane tolerance"):
        DepthHeightProposal(height_cut_m=0.002, plane_tolerance_m=0.004)


def test_belt_reference_cancels_a_distortion_a_plane_fit_cannot() -> None:
    """The finding that made the reference worth building.

    A depth camera's fixed error is smooth but not planar, so fitting a plane
    per frame cannot absorb it. Measured on a RealSense D415 that error ranged
    over 29.57 mm across its working distance, which at this cell's scale is the
    size of the product. Subtracting a reference image of the empty belt removes
    it exactly, because both frames carry it.
    """
    field = _slab(120, 60, WIDTH // 2, HEIGHT // 2)
    empty = _frame(np.zeros((HEIGHT, WIDTH), dtype=np.float32))
    loaded = _frame(field)

    def warp(frame: CameraFrameData, amplitude_m: float) -> CameraFrameData:
        return CameraFrameData(
            frame.stamp_s,
            frame.rgb,
            depth_systematic_warp(frame.depth_m, amplitude_m),
            frame.intrinsics,
            frame.camera,
        )

    amplitude = 0.060
    reference = BeltReference.from_frame(warp(empty, amplitude), seed=3)
    with_reference = DepthHeightProposal(reference=reference, seed=3).propose(warp(loaded, amplitude))
    fitted = DepthHeightProposal(seed=3).propose(warp(loaded, amplitude))

    truth_pixels = int((field > 0.001).sum())
    assert with_reference.mask.sum() == pytest.approx(truth_pixels, rel=0.05)
    assert fitted.mask.sum() != pytest.approx(truth_pixels, rel=0.05), (
        "a plane fit absorbed a non-planar distortion, so this test proves nothing"
    )


def test_belt_reference_agrees_with_a_plane_fit_when_there_is_no_distortion() -> None:
    field = _slab(120, 60, WIDTH // 2, HEIGHT // 2)
    reference = BeltReference.from_frame(_frame(np.zeros((HEIGHT, WIDTH), dtype=np.float32)), seed=3)
    against_reference = DepthHeightProposal(reference=reference, seed=3).propose(_frame(field))
    fitted = DepthHeightProposal(seed=3).propose(_frame(field))
    assert against_reference.mask.sum() == pytest.approx(fitted.mask.sum(), rel=0.02)
    assert against_reference.diagnostics["reference_overlap"] > 0.99


def test_a_reference_taken_from_a_dead_frame_is_refused() -> None:
    empty = _frame(np.zeros((HEIGHT, WIDTH), dtype=np.float32))
    dead = CameraFrameData(empty.stamp_s, empty.rgb, np.zeros_like(empty.depth_m), empty.intrinsics, empty.camera)
    with pytest.raises(ValueError, match="almost no depth"):
        BeltReference.from_frame(dead)
