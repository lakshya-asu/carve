"""Finding the product in the image, and scoring how well that went.

Everything measured in this project so far handed the pose estimator the
renderer's ground-truth silhouette. That bounds the geometry and the timing and
says nothing at all about segmentation, because there was none. This module is
the part that was missing.

A warning about the numbers it produces. In this scene the product is red
(247, 139, 146) on a near-black belt (59, 64, 69), so every method here scores
close to perfect on a clean render. That measures the implementation, not the
problem. Real product on a real line is wet, specular, sometimes the same colour
as the purge on the belt, and lit by whatever the plant has. The honest use of
this module is the degradation sweep in `scripts/measure/segmentation.py`: hold
the methods fixed, take the appearance apart in controlled ways, and see which
method degrades gracefully and how much contrast margin the cell needs.

The degradations here are stand-ins with a stated physical cause, not calibrated
models of a real camera. Each says what it is standing in for.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Anything smaller than this is not product. Matches the floor used in
# `pose_estimation.py` so the two stages agree on what counts as a detection.
MIN_COMPONENT_PIXELS = 400


@dataclass(frozen=True)
class MaskScore:
    """How close a predicted mask is to the true one.

    Attributes:
        iou: Intersection over union. The usual headline, and the one that
            hides boundary error: a mask can score 0.97 while its edge is
            several pixels out all the way round, and it is the edge that sets
            the pose.
        boundary_f1: F1 of the predicted boundary against the true boundary
            within a tolerance. This is the number that tracks pose error.
        precision: Fraction of predicted product pixels that are product.
        recall: Fraction of product pixels that were found.
        predicted_pixels: Size of the predicted mask.
    """

    iou: float
    boundary_f1: float
    precision: float
    recall: float
    predicted_pixels: int


def largest_component(mask: np.ndarray) -> np.ndarray:
    """Keep only the biggest connected blob.

    A threshold on a real belt picks up purge, reflections and rail edges. The
    product is the largest thing that is not the belt, and everything else is a
    distractor. Returns an empty mask if nothing is big enough.
    """
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if count <= 1:
        return np.zeros_like(mask, dtype=bool)
    areas = stats[1:, cv2.CC_STAT_AREA]
    best = int(np.argmax(areas)) + 1
    if areas[best - 1] < MIN_COMPONENT_PIXELS:
        return np.zeros_like(mask, dtype=bool)
    return np.asarray(labels == best)


def _clean(mask: np.ndarray, closing_px: int = 5) -> np.ndarray:
    """Close small holes, drop specks, keep the largest blob."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (closing_px, closing_px))
    closed = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)
    return largest_component(opened.astype(bool))


def threshold_hsv(rgb: np.ndarray) -> np.ndarray:
    """Colour threshold: product is redder and more saturated than the belt.

    The cheapest thing that works, and the first thing to fail when the belt
    gets covered in product-coloured liquid. Otsu on the saturation channel
    rather than a fixed cut, so it adapts to a lighting change but not to a
    background that has become the same colour as the product.
    """
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    _, saturated = cv2.threshold(hsv[:, :, 1], 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, bright = cv2.threshold(hsv[:, :, 2], 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return _clean((saturated > 0) & (bright > 0))


def adaptive_gray(rgb: np.ndarray) -> np.ndarray:
    """Intensity threshold with Otsu, no colour at all.

    The fallback when colour is unusable, which happens under the monochrome or
    near-infrared cameras some hygienic installations use. Included because it
    isolates how much of the performance is coming from colour.
    """
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return _clean(binary > 0)


def edge_contour(rgb: np.ndarray) -> np.ndarray:
    """Canny edges, closed into a loop, filled.

    Edge methods do not care about absolute colour, only about a discontinuity
    at the boundary, so they should hold where a threshold fails on a background
    that has drifted toward the product's colour. The cost is that they need the
    boundary to be an actual step: a soft or shadowed edge breaks the loop, and
    an unclosed contour fills nothing.
    """
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.4)
    median = float(np.median(blurred))
    low = int(max(0, 0.66 * median))
    high = int(min(255, 1.33 * median))
    edges = cv2.Canny(blurred, low, high)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return np.zeros(gray.shape, dtype=bool)
    filled = np.zeros(gray.shape, dtype=np.uint8)
    cv2.drawContours(filled, [max(contours, key=cv2.contourArea)], -1, 255, thickness=cv2.FILLED)
    return _clean(filled > 0)


METHODS = {
    "threshold_hsv": threshold_hsv,
    "adaptive_gray": adaptive_gray,
    "edge_contour": edge_contour,
}


def boundary_f1(predicted: np.ndarray, truth: np.ndarray, tolerance_px: int = 2) -> float:
    """F1 of the two boundaries, matched within `tolerance_px`.

    IoU is dominated by the interior, which every method gets right. The pose
    comes from the boundary, so this is the metric that moves with pose error.
    """
    predicted_edge = _boundary(predicted)
    truth_edge = _boundary(truth)
    if not predicted_edge.any() or not truth_edge.any():
        return 0.0
    near_truth = cv2.dilate(
        truth_edge.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tolerance_px + 1,) * 2)
    ).astype(bool)
    near_predicted = cv2.dilate(
        predicted_edge.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tolerance_px + 1,) * 2)
    ).astype(bool)
    precision = float((predicted_edge & near_truth).sum()) / float(predicted_edge.sum())
    recall = float((truth_edge & near_predicted).sum()) / float(truth_edge.sum())
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _boundary(mask: np.ndarray) -> np.ndarray:
    eroded = cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8))
    return np.asarray(mask & ~eroded.astype(bool))


def score_mask(predicted: np.ndarray, truth: np.ndarray) -> MaskScore:
    """Compare a predicted mask against the true silhouette."""
    intersection = float((predicted & truth).sum())
    union = float((predicted | truth).sum())
    predicted_count = float(predicted.sum())
    truth_count = float(truth.sum())
    return MaskScore(
        iou=intersection / union if union else 0.0,
        boundary_f1=boundary_f1(predicted, truth),
        precision=intersection / predicted_count if predicted_count else 0.0,
        recall=intersection / truth_count if truth_count else 0.0,
        predicted_pixels=int(predicted_count),
    )
