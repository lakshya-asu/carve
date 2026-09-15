r"""Segment pork legs in the real line footage: colour rule against Segment Anything plus the same rule.

The plant clips are phone video with no depth, so the depth-geometry segmenter
cannot run on them. The two methods compared on the same frames:

    colour        deterministic: pixels whose Lab colour is meat, cleaned up,
                  each connected piece one instance
    sam+colour    learned proposals, deterministic decision: Segment Anything
                  (ViT-B) proposes every region in the frame, and the same colour
                  rule decides which regions are meat

The colour rule comes from pixels sampled on two frames on 2026-09-15: meat skin,
fat, lean and cut faces sit at Lab a* 135 to 157 and b* 144 to 157 (OpenCV's
8-bit Lab, 128 is neutral); the white belt at a* 127 to 130, b* 127 to 131; belt
shadow a* 124, b* 138; steel walls a* 130, b* 132 to 136; blue gloves b* 82 to 100;
the yellow sleeve b* 196.

There are no hand-drawn masks for these frames, so the output is overlays for
review by eye, instance counts and time per frame.

    env -u PYTHONPATH PYTHONPATH=src python scripts/segment_real_footage.py \
        --frames <dir of jpg frames> --checkpoint outputs/checkpoints/sam_vit_b_01ec64.pth --out outputs/real-footage
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np
import torch
from segment_anything import SamAutomaticMaskGenerator, sam_model_registry

logger = logging.getLogger("segment_real_footage")

A_MIN, B_MIN, B_MAX, L_MIN = 133, 138, 170, 60
MIN_INSTANCE_FRACTION = 0.004  # of the frame; a small leg end is about 1 percent
MEAT_SHARE_TO_KEEP = 0.6
NESTED_OVERLAP = 0.8
COLOURS = [(66, 135, 245), (245, 170, 66), (90, 200, 90), (220, 80, 200), (60, 210, 210), (240, 90, 90)]


def meat_pixels(bgr: np.ndarray) -> np.ndarray:
    """Boolean mask of pixels whose colour is meat by the sampled Lab rule."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    lightness, a_star, b_star = lab[..., 0], lab[..., 1], lab[..., 2]
    return np.asarray((a_star >= A_MIN) & (b_star >= B_MIN) & (b_star <= B_MAX) & (lightness >= L_MIN))


def colour_instances(bgr: np.ndarray) -> list[np.ndarray]:
    """Deterministic method: meat-coloured pixels, opened and closed, one instance per connected piece."""
    mask = meat_pixels(bgr).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask = cv2.morphologyEx(cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel), cv2.MORPH_CLOSE, kernel)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    minimum = MIN_INSTANCE_FRACTION * mask.size
    return [labels == i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= minimum]


def sam_colour_instances(bgr: np.ndarray, generator: SamAutomaticMaskGenerator) -> list[np.ndarray]:
    """Learned proposals, deterministic decision: SAM regions that are mostly meat-coloured, without nested repeats."""
    meat = meat_pixels(bgr)
    minimum = MIN_INSTANCE_FRACTION * meat.size
    proposals = generator.generate(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    kept: list[np.ndarray] = []
    for proposal in sorted(proposals, key=lambda p: -p["area"]):
        region = proposal["segmentation"]
        if region.sum() < minimum or meat[region].mean() < MEAT_SHARE_TO_KEEP:
            continue
        # SAM proposes a leg and also its parts; a region mostly inside a kept one is a part.
        if any((region & bigger).sum() > NESTED_OVERLAP * region.sum() for bigger in kept):
            continue
        kept.append(region)
    return kept


def overlay(bgr: np.ndarray, instances: list[np.ndarray], title: str) -> np.ndarray:
    """The frame with each instance tinted and outlined in its own colour, and a title bar."""
    out = bgr.copy()
    for index, region in enumerate(instances):
        colour = np.array(COLOURS[index % len(COLOURS)], dtype=np.float32)
        out[region] = (0.55 * out[region] + 0.45 * colour).astype(np.uint8)
        contours, _ = cv2.findContours(region.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out, contours, -1, tuple(int(c) for c in colour), 4, cv2.LINE_AA)
    cv2.rectangle(out, (0, 0), (out.shape[1], 56), (28, 28, 28), cv2.FILLED)
    cv2.putText(out, title, (14, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.95, (240, 240, 240), 2, cv2.LINE_AA)
    return out


def main() -> None:
    """Run both methods on every frame; write overlays, a video and a JSON summary."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--points-per-side", type=int, default=16)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args.out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(0)
    sam = sam_model_registry["vit_b"](checkpoint=str(args.checkpoint))
    sam.eval()
    generator = SamAutomaticMaskGenerator(sam, points_per_side=args.points_per_side)
    writer = imageio.get_writer(
        args.out / "real-footage-segmentation.mp4", fps=2, codec="libx264", pixelformat="yuv420p", macro_block_size=1
    )
    rows = []
    for path in sorted(args.frames.glob("*.jpg")):
        bgr = cv2.imread(str(path))
        started = time.perf_counter()
        colour = colour_instances(bgr)
        colour_ms = 1000 * (time.perf_counter() - started)
        started = time.perf_counter()
        with torch.inference_mode():
            learned = sam_colour_instances(bgr, generator)
        learned_ms = 1000 * (time.perf_counter() - started)
        panel = np.hstack(
            [
                overlay(bgr, [], path.stem),
                overlay(bgr, colour, f"colour rule: {len(colour)} pieces, {colour_ms:.0f} ms"),
                overlay(bgr, learned, f"SAM + colour: {len(learned)} pieces, {learned_ms / 1000:.1f} s"),
            ]
        )
        cv2.imwrite(str(args.out / f"{path.stem}-compare.jpg"), panel, [cv2.IMWRITE_JPEG_QUALITY, 88])
        writer.append_data(
            cv2.cvtColor(cv2.resize(panel, (panel.shape[1] // 2, panel.shape[0] // 2)), cv2.COLOR_BGR2RGB)
        )
        rows.append(
            {
                "frame": path.stem,
                "colour_pieces": len(colour),
                "colour_ms": colour_ms,
                "sam_pieces": len(learned),
                "sam_ms": learned_ms,
            }
        )
        logger.info(
            "%s: colour %d pieces in %.0f ms, SAM+colour %d in %.1f s",
            path.stem,
            len(colour),
            colour_ms,
            len(learned),
            learned_ms / 1000,
        )
    writer.close()
    (args.out / "summary.json").write_text(
        json.dumps(
            {"torch_threads": torch.get_num_threads(), "points_per_side": args.points_per_side, "rows": rows}, indent=1
        )
    )
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
