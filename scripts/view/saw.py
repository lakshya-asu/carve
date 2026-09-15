"""Record legs riding into the trotter saw, one pass per alignment case.

Three passes: a leg square to the blade with its hock on the blade plane, the
same leg 40 mm too far onto the belt, and a leg 20 degrees off square. Each
frame carries the cut result once the blade has decided, so the video shows
both the event and the number it is scored on.

Usage:
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/view/saw.py
"""

from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path

import cv2
import imageio.v2 as imageio
import mujoco
import numpy as np

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.hold_down import HoldDownConfig
from applications.pork_leg_alignment.sim.product import LegConfig
from applications.pork_leg_alignment.sim.saw import CutOutcome, SawConfig
from applications.pork_leg_alignment.sim.scene import CellConfig

logger = logging.getLogger("view_saw")

WIDTH_PX, HEIGHT_PX, FPS = 960, 540, 30
PASS_SECONDS = 4.5
START_BEFORE_BLADE_M = 0.6
CASES = [
    ("square, hock on the blade", 0.0, 0.0),
    ("40 mm too far onto the belt", 0.040, 0.0),
    ("20 degrees off square", 0.0, 20.0),
]


def _label(frame: np.ndarray, lines: list[str]) -> None:
    for row, text in enumerate(lines):
        y = 32 + 30 * row
        cv2.putText(frame, text, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, text, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)


def main() -> None:
    """Run the three passes and write one video with the cut results burned in."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path.home() / "Videos" / "meat-cell" / "saw-cut.mp4")
    parser.add_argument("--belt-speed", type=float, default=0.30)
    parser.add_argument("--feed", type=float, default=60.0, help="blade feed resistance, newtons (unmeasured)")
    parser.add_argument("--no-hold-down", action="store_true", help="run without the hold-down belt")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    config = CellConfig(
        belt_speed_mps=args.belt_speed,
        leg=LegConfig(),
        saw=SawConfig(feed_resistance_n=args.feed),
        hold_down=None if args.no_hold_down else HoldDownConfig(),
    )
    # H.264 in yuv420p: OpenCV's mp4v (MPEG-4 Part 2) files do not play in browsers,
    # and the videos are published on the plan page.
    writer = imageio.get_writer(args.out, fps=FPS, codec="libx264", pixelformat="yuv420p", macro_block_size=1)
    with Cell(config) as cell, mujoco.Renderer(cell.model, HEIGHT_PX, WIDTH_PX) as renderer:
        assert cell.saw is not None and config.leg is not None and config.saw is not None
        camera = mujoco.MjvCamera()
        camera.lookat[:] = [config.saw.x_m - 0.15, 0.30, 0.93]
        camera.distance = 1.7
        camera.azimuth = 125.0
        camera.elevation = -28.0
        steps_per_frame = round(1.0 / (FPS * cell.model.opt.timestep))

        for name, inboard_m, yaw_deg in CASES:
            cell.reset()
            cell.place_product(
                config.saw.x_m - START_BEFORE_BLADE_M,
                cell.saw.blade_y_m + config.leg.hock_offset_m + inboard_m,
                -math.pi / 2 + math.radians(yaw_deg),
            )
            for _ in range(round(PASS_SECONDS * FPS)):
                cell.step(steps_per_frame)
                renderer.update_scene(cell.data, camera)
                frame = cv2.cvtColor(renderer.render(), cv2.COLOR_RGB2BGR)
                result = cell.cut_result
                hold = "no hold-down" if args.no_hold_down else "hold-down belt on"
                lines = [
                    name,
                    f"belt {args.belt_speed:.2f} m/s, saw push {args.feed:.0f} N, {hold}   t = {cell.time_s:.2f} s",
                ]
                if result is not None and result.outcome is CutOutcome.CUT:
                    lines.append(
                        f"CUT entered {1000 * result.offset_from_hock_m:+.1f} mm from hock, "
                        f"{math.degrees(result.angle_rad):+.1f} deg off square"
                    )
                    lines.append(
                        f"leg turned {math.degrees(result.yaw_drift_rad):+.1f} deg, "
                        f"slid {1000 * result.slip_m:.0f} mm while cutting"
                    )
                elif result is not None:
                    lines.append(f"{result.outcome.value}")
                elif cell.saw.cutting:
                    lines.append("blade in the leg")
                _label(frame, lines)
                writer.append_data(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            result = cell.cut_result
            logger.info("%s: %s", name, result)
    writer.close()
    logger.info("wrote %s", args.out)


if __name__ == "__main__":
    main()
