"""Cut the talk together from drawn scenes, footage panels and simulation clips, in spoken order.

The pieces come at different sizes and rates (Manim scenes at 1920x1080 60 fps, the simulation
clips at 960x540 25 fps), so every piece is scaled into a 1920x1080 frame on the talk's ground
and re-timed to 60 fps before joining. A name without a path is looked up among the rendered
Manim scenes.

    env -u PYTHONPATH python scripts/view/stitch_deck.py --out ~/Videos/meat-cell/deck/part.mp4 \
        WhySkills Definition ~/Videos/meat-cell/deck/skill-clips.mp4 Fuse Compose
"""

from __future__ import annotations

import argparse
import logging
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

logger = logging.getLogger("stitch_deck")

SCENES = Path.home() / "Videos" / "meat-cell" / "deck" / "videos" / "deck_leg_cell" / "1080p60"
WIDTH, HEIGHT, FPS = 1920, 1080, 60
PAPER = "0x161616"


DECK = Path.home() / "Videos" / "meat-cell" / "deck"


def resolve(piece: str) -> Path:
    """A rendered scene by class name, a footage card relative to the deck folder, or a path."""
    path = Path(piece).expanduser()
    if not path.suffix:
        return SCENES / f"{piece}.mp4"
    if not path.is_absolute() and (DECK / path).is_file():
        return DECK / path
    return path


def script_targets(script: Path) -> list[float]:
    """Each block's spoken target in seconds, in the order the blocks appear in the script."""
    return [float(m) for m in re.findall(r"Target: ([0-9]+(?:\.[0-9]+)?) s", script.read_text())]


def durations(files: list[Path]) -> list[float]:
    """Each file's length in seconds, read from its container."""
    lengths = []
    for f in files:
        probe = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(f)], capture_output=True, text=True, check=False
        ).stderr
        h, m, sec = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe).groups()
        lengths.append(int(h) * 3600 + int(m) * 60 + float(sec))
    return lengths


def read_order(order: Path) -> list[str]:
    """Pieces from an order file: one per line, blank lines and # comments ignored."""
    return [ln.strip() for ln in order.read_text().splitlines() if ln.strip() and not ln.strip().startswith("#")]


def stitch(pieces: list[str], out: Path, holds: list[float] | None = None) -> None:
    """Join `pieces` in order into one 1920x1080 60 fps file.

    With `holds`, piece i's last frame is held for holds[i] extra seconds, so the cut runs as long
    as the narration over it.
    """
    files = [resolve(p) for p in pieces]
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        raise SystemExit(f"not found: {', '.join(missing)}")
    holds = holds or [0.0] * len(files)
    inputs: list[str] = []
    for f in files:
        inputs += ["-i", str(f)]
    steps = [
        f"[{i}:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color={PAPER},fps={FPS},format=yuv420p,setsar=1"
        f"{f',tpad=stop_mode=clone:stop_duration={holds[i]:.2f}' if holds[i] > 0 else ''}[v{i}]"
        for i in range(len(files))
    ]
    steps.append("".join(f"[v{i}]" for i in range(len(files))) + f"concat=n={len(files)}:v=1:a=0[out]")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-v",
            "error",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(steps),
            "-map",
            "[out]",
            "-c:v",
            "libx264",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            str(out),
        ],
        check=True,
    )
    logger.info("wrote %s from %d pieces", out, len(files))


def main() -> None:
    """Join the named pieces."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--order", type=Path, help="a file listing the pieces, as scripts/view/talk_order.txt")
    parser.add_argument(
        "--pace", type=Path, help="a narration script whose 'Target: N s' lines, one per piece, set how long each holds"
    )
    parser.add_argument("pieces", nargs="*", help="scene class names or video paths, in spoken order")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    pieces = read_order(args.order) if args.order else args.pieces
    if not pieces:
        parser.error("give --order or at least one piece")
    holds = None
    if args.pace:
        targets = script_targets(args.pace)
        if len(targets) != len(pieces):
            raise SystemExit(f"{args.pace} has {len(targets)} targets for {len(pieces)} pieces")
        lengths = durations([resolve(p) for p in pieces])
        holds = [max(0.0, t - d) for t, d in zip(targets, lengths, strict=True)]
        logger.info("paced to the script: %.1f s of picture, %.1f s held", sum(lengths), sum(holds))
    stitch(pieces, args.out, holds)


if __name__ == "__main__":
    main()
