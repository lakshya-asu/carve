"""Take the rendered image apart in controlled ways.

The rendered scene is far easier than a meat line: the product is red on a
near-black belt with no noise, no reflections and even lighting. Scoring a
segmenter on it measures the code, not the problem. These functions degrade the
image along axes that have a named physical cause on a real line, so that what
gets measured is how each method fails and how much margin the cell needs.

None of these is a calibrated camera model. Each is a stand-in with its cause
stated, and the useful output is the shape of the curve, not the absolute score
at any one setting.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def sensor_noise(rgb: np.ndarray, sigma: float, rng: np.random.Generator) -> np.ndarray:
    """Additive read noise, in grey levels.

    Stands in for a short exposure at high gain, which is what a fast line
    forces: the exposure has to be short to keep motion smear under the
    placement bound, so the gain goes up and the noise with it.
    """
    noisy = rgb.astype(np.float32) + rng.normal(0.0, sigma, rgb.shape).astype(np.float32)
    return np.clip(noisy, 0, 255).astype(np.uint8)


def lighting_gradient(rgb: np.ndarray, strength: float) -> np.ndarray:
    """Multiplicative brightness ramp across the frame.

    Stands in for one luminaire lighting a wide conveyor, which no plant gets
    perfectly even. `strength` is the fractional difference between the bright
    and dark ends, so 0.6 means the dark end is 40 percent of the bright one.
    """
    height, width = rgb.shape[:2]
    ramp = np.linspace(1.0, 1.0 - strength, width, dtype=np.float32)
    field = np.repeat(ramp[None, :], height, axis=0)[:, :, None]
    return np.asarray(np.clip(rgb.astype(np.float32) * field, 0, 255).astype(np.uint8))


def specular_blobs(rgb: np.ndarray, count: int, radius_px: int, rng: np.random.Generator) -> np.ndarray:
    """Blown-out highlights scattered over the frame.

    Stands in for wet product and a wet belt under direct light. Highlights
    destroy both colour and edge information locally, which is why they break
    threshold and edge methods in different ways.
    """
    out = rgb.astype(np.float32).copy()
    height, width = rgb.shape[:2]
    for _ in range(count):
        centre = (int(rng.integers(0, width)), int(rng.integers(0, height)))
        layer = np.zeros((height, width), dtype=np.float32)
        cv2.circle(layer, centre, radius_px, 1.0, thickness=cv2.FILLED)
        blurred = np.asarray(cv2.GaussianBlur(layer, (0, 0), radius_px / 2.0), dtype=np.float32)
        out += 255.0 * blurred[:, :, None]
    return np.asarray(np.clip(out, 0, 255).astype(np.uint8))


def background_toward_product(rgb: np.ndarray, product_mask: np.ndarray, fraction: float) -> np.ndarray:
    """Drag the background's colour toward the product's.

    The single most decision-relevant axis here. On a clean belt the product is
    obvious; as purge, fat smear and product debris accumulate through a shift,
    the belt drifts toward the colour of the thing on it. `fraction` is how far
    the background moves toward the product's mean colour, so 1.0 means the belt
    and the product are the same colour and only geometry separates them.

    This is what sets the lighting and belt-colour specification: the cell needs
    to state how much colour separation it requires to hold its bound.
    """
    if not product_mask.any():
        return rgb
    product_colour = rgb[product_mask].mean(axis=0).astype(np.float32)
    out = rgb.astype(np.float32)
    background = ~product_mask
    out[background] = out[background] * (1.0 - fraction) + product_colour * fraction
    return np.asarray(np.clip(out, 0, 255).astype(np.uint8))


def purge_patches(
    rgb: np.ndarray, product_mask: np.ndarray, count: int, radius_px: int, rng: np.random.Generator
) -> np.ndarray:
    """Product-coloured patches on the belt, away from the product.

    Stands in for exudate and trimmings left on the belt. Unlike a uniform
    colour drift these are product-coloured *blobs*, so they are exactly what a
    largest-component rule is there to survive, and what it fails at once a blob
    is bigger than the product.
    """
    if not product_mask.any():
        return rgb
    product_colour = rgb[product_mask].mean(axis=0)
    out = rgb.copy()
    height, width = rgb.shape[:2]
    for _ in range(count):
        centre = (int(rng.integers(0, width)), int(rng.integers(0, height)))
        patch = np.zeros((height, width), dtype=np.uint8)
        cv2.circle(patch, centre, radius_px, 255, thickness=cv2.FILLED)
        spot = (patch > 0) & ~product_mask
        out[spot] = product_colour
    return np.asarray(out)


def depth_axial_noise(depth_m: np.ndarray, sigma_at_1m: float, rng: np.random.Generator) -> np.ndarray:
    """Range-dependent depth noise.

    Structured-light and active-stereo error grows with the square of range,
    because disparity resolution is fixed and range is inversely proportional to
    disparity. `sigma_at_1m` is the standard deviation in metres at one metre,
    scaled here as sigma(z) = sigma_at_1m * z^2. Missing returns stay missing.
    """
    valid = depth_m > 0
    noisy = depth_m.astype(np.float32).copy()
    sigma = sigma_at_1m * np.square(depth_m[valid])
    noisy[valid] += rng.normal(0.0, 1.0, sigma.shape).astype(np.float32) * sigma.astype(np.float32)
    return np.asarray(noisy)


def depth_dropout(depth_m: np.ndarray, fraction: float, patch_px: int, rng: np.random.Generator) -> np.ndarray:
    """Punch holes in the depth image, as a real sensor does.

    Active stereo returns nothing where it cannot match, and the holes are
    patches rather than isolated pixels. `fraction` is the share of the frame
    lost. Missing depth is written as zero, which is what the sensors report.
    """
    out = depth_m.astype(np.float32).copy()
    height, width = depth_m.shape
    target = int(fraction * height * width)
    lost = 0
    while lost < target:
        centre = (int(rng.integers(0, width)), int(rng.integers(0, height)))
        hole = np.zeros((height, width), dtype=np.uint8)
        cv2.circle(hole, centre, patch_px, 255, thickness=cv2.FILLED)
        spot = hole > 0
        lost += int(spot.sum())
        out[spot] = 0.0
    return np.asarray(out)


def depth_dropout_where_specular(depth_m: np.ndarray, rgb: np.ndarray, threshold: int = 250) -> np.ndarray:
    """Lose depth exactly where the colour image is blown out.

    This is the coupling that makes an honest test. A specular highlight is not
    only a bright patch in the picture: it is also where active stereo fails,
    because a mirror-like surface returns the projected pattern to one direction
    only and the two cameras cannot match it. Degrading colour without
    degrading depth in the same place would rig any comparison between a
    colour-based and a depth-based method.
    """
    # All three channels clipped, not just the brightest one. A real specular
    # highlight is white: the surface is acting as a mirror and returning the
    # source, so every channel saturates together. Testing only the maximum
    # channel flagged the product itself, whose red channel sits at 247 clean,
    # and deleted the whole piece from the depth image the moment any soft
    # highlight brightened it past the cut.
    blown = rgb.min(axis=2) >= threshold
    dilated = cv2.dilate(blown.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    out = depth_m.astype(np.float32).copy()
    out[dilated > 0] = 0.0
    return np.asarray(out)


def depth_systematic_warp(depth_m: np.ndarray, amplitude_m: float) -> np.ndarray:
    """A smooth, fixed spatial distortion of the depth field.

    Not noise: this is the same every frame, so averaging does not remove it and
    a plane fit cannot absorb it because the shape is not planar. It stands in
    for the calibration and lens error every depth camera carries. Measured on a
    RealSense D415 the range of this error was 29.57 mm over a 500 to 1500 mm
    working range (Servi et al. 2021), which at this cell's scale is the size of
    the product itself.

    Modelled as a quadratic bowl in image radius, which is the shape a radial
    calibration error takes.
    """
    height, width = depth_m.shape
    rows, cols = np.mgrid[0:height, 0:width].astype(np.float32)
    radius = np.hypot(cols - (width - 1) / 2, rows - (height - 1) / 2)
    normalised = (radius / radius.max()) ** 2
    out = depth_m.astype(np.float32) + amplitude_m * (normalised - normalised.mean()).astype(np.float32)
    out[depth_m <= 0] = 0.0
    return np.asarray(out)
