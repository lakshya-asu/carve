"""Lay three drill clips side by side, in the talk's palette and typeface.

Three recordings of football drills stand for three skills learned apart: a first touch, a
dribble through cones, and running with the ball. The panel is the only part of the talk built
from footage rather than drawn, so it is composed here with ffmpeg and styled to match the Manim
scenes around it.

    env -u PYTHONPATH python scripts/view/skill_clips_panel.py --out ~/Videos/meat-cell/deck/skill-clips.mp4
"""

from __future__ import annotations

import argparse
import logging
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("skill_clips_panel")

# The talk's dark theme, from deck_leg_cell.py.
PAPER = "0x161616"
INK = (229, 228, 224)
INK_2 = (179, 178, 172)
BLUE = (143, 176, 236)
FONT = Path.home() / ".local/share/fonts/B612-Regular.ttf"

WIDTH, HEIGHT = 1920, 1080
PANEL_W, PANEL_H = 592, 720
PANEL_Y = 196
PANEL_X = (40, 664, 1288)
SECONDS = 8.0

# Each clip, where to start it, and what skill it stands for.
CLIPS = (
    ("Screencast from 09-16-2026 03:05:39 AM.webm", 2.0, "first touch"),
    ("Screencast from 09-16-2026 03:10:48 AM.webm", 2.0, "close control"),
    ("Screencast from 09-16-2026 03:12:07 AM.webm", 3.0, "carrying at speed"),
)


def caption_overlay(target: Path) -> None:
    """Draw the panel's words once, as a transparent layer to lay over the clips.

    The bundled ffmpeg has no text filter, so the type is drawn here instead, in
    the same face the drawn scenes use.
    """
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    pen = ImageDraw.Draw(canvas)
    title_face = ImageFont.truetype(str(FONT), 46)
    caption_face = ImageFont.truetype(str(FONT), 30)
    closing_face = ImageFont.truetype(str(FONT), 34)

    def centred(text: str, face: ImageFont.FreeTypeFont, centre_x: int, y: int, colour: tuple[int, int, int]) -> None:
        left, top, right, _ = pen.textbbox((0, 0), text, font=face)
        pen.text((centre_x - (right - left) / 2 - left, y - top), text, font=face, fill=(*colour, 255))

    centred("Three drills. Three skills.", title_face, WIDTH // 2, 74, INK)
    for index, (_, _, what) in enumerate(CLIPS):
        centred(what, caption_face, PANEL_X[index] + PANEL_W // 2, PANEL_Y + PANEL_H + 26, INK_2)
    centred("Learned apart, at different times.", closing_face, WIDTH // 2, 1016, BLUE)
    canvas.save(target)


def build(source_dir: Path, out: Path) -> None:
    """Compose the three clips into one 1920x1080 panel with captions."""
    if not FONT.is_file():
        raise SystemExit(f"the talk's typeface is not installed at {FONT}")
    missing = [name for name, _, _ in CLIPS if not (source_dir / name).is_file()]
    if missing:
        raise SystemExit(f"not found in {source_dir}: {', '.join(missing)}")

    out.parent.mkdir(parents=True, exist_ok=True)
    overlay = out.with_name(out.stem + "-captions.png")
    caption_overlay(overlay)

    inputs: list[str] = []
    for name, start_s, _ in CLIPS:
        inputs += ["-ss", str(start_s), "-t", str(SECONDS), "-i", str(source_dir / name)]
    inputs += ["-i", str(overlay)]

    steps = [f"color=c={PAPER}:s={WIDTH}x{HEIGHT}:d={SECONDS}[bg]"]
    for index in range(len(CLIPS)):
        steps.append(
            f"[{index}:v]scale={PANEL_W}:{PANEL_H}:force_original_aspect_ratio=decrease,"
            f"pad={PANEL_W}:{PANEL_H}:(ow-iw)/2:(oh-ih)/2:color={PAPER},setsar=1[p{index}]"
        )
    stage = "bg"
    for index, x in enumerate(PANEL_X):
        nxt = f"s{index}"
        steps.append(f"[{stage}][p{index}]overlay={x}:{PANEL_Y}[{nxt}]")
        stage = nxt
    steps.append(f"[{stage}][{len(CLIPS)}:v]overlay=0:0[out]")

    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-v",
        "error",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(steps),
        "-map",
        "[out]",
        "-r",
        "60",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "20",
        "-movflags",
        "+faststart",
        "-an",
        str(out),
    ]
    subprocess.run(command, check=True)
    logger.info("wrote %s", out)


def main() -> None:
    """Compose the panel from the recorded drills."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.home() / "Videos" / "Screencasts")
    parser.add_argument("--out", type=Path, default=Path.home() / "Videos" / "meat-cell" / "deck" / "skill-clips.mp4")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    build(args.source, args.out)


if __name__ == "__main__":
    main()
