"""Segmentation and its scoring.

The test that carries the finding is the last one: a mask that is uniformly a
little too small scores badly on both IoU and boundary F1 and yet gives exactly
the right pose. Mask-quality metrics do not rank methods for this task.
"""

import cv2
import numpy as np
import pytest

from robotics.hardware.image_degradation import (
    background_toward_product,
    lighting_gradient,
    purge_patches,
    sensor_noise,
    specular_blobs,
)
from robotics.perception.segmentation import METHODS, MIN_COMPONENT_PIXELS, boundary_f1, largest_component, score_mask

HEIGHT, WIDTH = 240, 320


def _rect_mask(w: int, h: int, cx: int = WIDTH // 2, cy: int = HEIGHT // 2) -> np.ndarray:
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    mask[cy - h // 2 : cy + h // 2, cx - w // 2 : cx + w // 2] = True
    return mask


def _scene(mask: np.ndarray) -> np.ndarray:
    """Dark belt, red product, matching the cell's materials."""
    image = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    image[:] = (36, 41, 46)
    image[mask] = (184, 71, 77)
    return image


def test_largest_component_keeps_the_product_and_drops_specks() -> None:
    """A threshold on a real belt picks up purge and reflections too."""
    mask = _rect_mask(80, 60)
    mask[10:14, 10:14] = True
    kept = largest_component(mask)
    assert kept.sum() == 80 * 60
    assert not kept[10:14, 10:14].any()


def test_largest_component_rejects_everything_when_nothing_is_product_sized() -> None:
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    mask[10:15, 10:15] = True
    assert mask.sum() < MIN_COMPONENT_PIXELS
    assert not largest_component(mask).any()


def test_iou_and_precision_recall_are_the_textbook_values() -> None:
    truth = _rect_mask(100, 100)
    predicted = _rect_mask(100, 100, cx=WIDTH // 2 + 50)
    score = score_mask(predicted, truth)
    # Two 100x100 squares overlapping by half.
    assert score.iou == pytest.approx(5000 / 15000, abs=1e-6)
    assert score.precision == pytest.approx(0.5, abs=1e-6)
    assert score.recall == pytest.approx(0.5, abs=1e-6)


def test_boundary_f1_is_one_for_an_exact_match_and_zero_for_no_overlap() -> None:
    truth = _rect_mask(100, 80)
    assert boundary_f1(truth, truth) == pytest.approx(1.0)
    far = _rect_mask(20, 20, cx=20, cy=20)
    assert boundary_f1(far, truth) == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("name", sorted(METHODS))
def test_every_method_finds_a_plain_product_on_a_plain_belt(name: str) -> None:
    truth = _rect_mask(140, 70)
    found = METHODS[name](_scene(truth))
    assert found.any(), f"{name} found nothing on a trivial scene"
    assert score_mask(found, truth).iou > 0.6


def test_edges_survive_a_lighting_ramp_that_defeats_a_fixed_colour_cut() -> None:
    """Measured on the cell: at 60 percent falloff the colour threshold is
    10.3 mm out and the edge method is unmoved at 0.050 mm."""
    truth = _rect_mask(140, 70)
    dimmed = lighting_gradient(_scene(truth), 0.6)
    assert score_mask(METHODS["edge_contour"](dimmed), truth).iou > 0.6


def test_degradations_change_the_image_without_changing_its_shape() -> None:
    truth = _rect_mask(140, 70)
    scene = _scene(truth)
    rng = np.random.default_rng(0)
    for degraded in (
        sensor_noise(scene, 20.0, rng),
        lighting_gradient(scene, 0.5),
        specular_blobs(scene, 4, 30, rng),
        background_toward_product(scene, truth, 0.5),
        purge_patches(scene, truth, 6, 20, rng),
    ):
        assert degraded.shape == scene.shape
        assert degraded.dtype == np.uint8
        assert not np.array_equal(degraded, scene)


def test_background_drift_really_closes_the_colour_gap() -> None:
    truth = _rect_mask(140, 70)
    scene = _scene(truth)
    drifted = background_toward_product(scene, truth, 1.0)
    assert drifted[truth].mean(axis=0) == pytest.approx(drifted[~truth].mean(axis=0), abs=1.0)


def test_a_uniformly_shrunken_mask_scores_badly_and_gives_the_right_pose() -> None:
    """Why mask-quality metrics must not be used to rank methods here.

    `edge_contour` scored a lower IoU and a lower boundary F1 than the colour
    threshold and still gave half its pose error, because Canny-and-fill shrinks
    the mask roughly evenly and a symmetric boundary offset does not move the
    centroid. What predicts pose error is whether the mask error is symmetric,
    which neither metric measures.
    """
    truth = _rect_mask(140, 70)
    shrunk = cv2.erode(truth.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    score = score_mask(shrunk, truth)
    # Eroding a 140x70 rectangle by 3 px: IoU falls to 0.875 and the boundary
    # F1 collapses to 0.0, because not one predicted boundary pixel lands within
    # tolerance of the true boundary. Both metrics call this mask bad.
    assert score.iou == pytest.approx(0.875, abs=0.01)
    assert score.boundary_f1 == pytest.approx(0.0, abs=1e-9)
    assert score.precision == pytest.approx(1.0), "nothing outside the product was claimed"

    def centroid(mask: np.ndarray) -> tuple[float, float]:
        rows, cols = np.nonzero(mask)
        return float(cols.mean()), float(rows.mean())

    assert centroid(shrunk) == pytest.approx(centroid(truth), abs=1e-9)
