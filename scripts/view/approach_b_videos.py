"""Film approach B end to end on the moving belt: every condition, every leg, saw-judged.

Runs the same episodes as `scripts/measure/alignment_approaches.py` (ground-truth pose, the
pre-registered arrivals) through a cell that writes a frame every 1/25 s of simulated time, so what
is on screen is exactly what the results table counts. One video per condition holds all 20 legs
back to back with a live caption: which leg, what the cell is doing, and the saw's verdict. A
close-up video per condition follows three legs with a camera that tracks the leg.

Usage:
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/view/approach_b_videos.py \\
        --out-dir ~/Videos/meat-cell/2026-09-15
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from collections.abc import Callable
from pathlib import Path

import cv2
import imageio.v2 as imageio
import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "measure"))
from alignment_approaches import (
    ARRIVAL_YAW_RANGE_RAD,
    BELT_SPEED_MPS,
    LEG_COUNT,
    LEG_SEED,
    Episode,
    arrivals,
    run_episode,
)

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import leg_population
from robotics.hardware.arms import ArmModel
from robotics.hardware.grippers import GripperModel

logger = logging.getLogger("approach_b_videos")

WIDTH_PX, HEIGHT_PX, FPS = 960, 540, 25
HOLD_AFTER_S = 1.2
CLOSE_UP_LEGS = (0, 9, 15)
CONDITIONS = (
    (ArmModel.SR20IA, 0.0),
    (ArmModel.UR20, 0.0),
    (ArmModel.UR20, 15.0),
    (ArmModel.UR20, 30.0),
)


def _camera(lookat: list[float], distance: float, azimuth: float, elevation: float) -> mujoco.MjvCamera:
    camera = mujoco.MjvCamera()
    camera.lookat[:] = lookat
    camera.distance = distance
    camera.azimuth = azimuth
    camera.elevation = elevation
    return camera


class Film:
    """One video file: a renderer, a camera and a caption burned into every frame."""

    def __init__(self, model: mujoco.MjModel, path: Path, camera: mujoco.MjvCamera) -> None:
        """Open the renderer and the H.264 writer (browsers play it; the plan page embeds it)."""
        self.renderer = mujoco.Renderer(model, HEIGHT_PX, WIDTH_PX)
        self.writer = imageio.get_writer(path, fps=FPS, codec="libx264", pixelformat="yuv420p", macro_block_size=1)
        self.camera = camera
        self.caption: list[str] = []
        self.path = path

    def frame(self, data: mujoco.MjData) -> None:
        """Render and write one frame with the current caption."""
        self.renderer.update_scene(data, self.camera)
        image = cv2.cvtColor(self.renderer.render(), cv2.COLOR_RGB2BGR)
        for row, text in enumerate(self.caption):
            y = 26 + 24 * row
            cv2.putText(image, text, (14, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(image, text, (14, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1, cv2.LINE_AA)
        self.writer.append_data(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    def hold(self, data: mujoco.MjData, seconds: float) -> None:
        """Write the same scene for `seconds`, so a verdict can be read."""
        for _ in range(round(seconds * FPS)):
            self.frame(data)

    def close(self) -> None:
        """Finish the file."""
        self.writer.close()
        self.renderer.close()
        logger.info("wrote %s", self.path)


class FilmedCell(Cell):
    """A cell that writes a frame every 1/FPS of simulated time while anything steps it.

    The renderer is owned by the film, which outlives the cell: one film holds
    every leg of a condition, each leg in its own cell.
    """

    film: Film | None = None
    caption_fn: Callable[[], list[str]] | None = None
    track: Callable[[], np.ndarray] | None = None
    _steps_since_frame = 0

    def step(self, steps: int = 1, seconds: float | None = None) -> None:
        """Step as `Cell.step` does, filming as it goes."""
        if seconds is not None:
            steps = max(1, round(seconds / self.model.opt.timestep))
        per_frame = max(1, round(1.0 / (FPS * self.model.opt.timestep)))
        for _ in range(steps):
            super().step(1)
            self._steps_since_frame += 1
            if self.film is not None and self._steps_since_frame >= per_frame:
                self._steps_since_frame = 0
                self._frame()

    def _frame(self) -> None:
        assert self.film is not None
        if self.caption_fn is not None:
            self.film.caption = self.caption_fn()
        if self.track is not None:
            self.film.camera.lookat[:] = self.track()
        self.film.frame(self.data)

    def __exit__(self, *exc: object) -> None:
        """Hold the last frame so the verdict can be read, then release the sensors."""
        if self.film is not None:
            self._frame()
            self.film.hold(self.data, HOLD_AFTER_S)
        super().__exit__(*exc)


def _verdict(row: Episode) -> str:
    if row.cut:
        if row.success:
            return f"PASS: cut {row.entry_offset_mm:+.1f} mm from the hock, {row.cut_angle_deg:+.1f} deg off square"
        return f"FAIL: {row.failure}"
    if row.orient:
        return f"released at x = {row.released_at_x_m:.2f} m, hock {row.hock_offset_mm:+.1f} mm from the blade plane; riding to the saw"
    if row.acquire:
        return f"grip {row.acquire}; moving the leg to the aligned pose"
    if row.select:
        return "intercepting the shank on the moving belt and closing the jaws"
    return "reading the leg's pose"


def _caption(row: Episode, arm: ArmModel, tilt_deg: float, index: int, approach: str = "B") -> list[str]:
    tilt = "tool vertical" if tilt_deg == 0.0 else f"tool leaned {tilt_deg:.0f} deg"
    what = "grasp and rotate on the belt" if approach == "B" else "pick up, carry, place"
    return [
        f"APPROACH {approach}, {what}: {arm.value}, jaw on the shank, {tilt}, belt {BELT_SPEED_MPS:.2f} m/s",
        f"leg {index + 1} of {LEG_COUNT}: {row.length_mm:.0f} mm, {row.mass_kg:.1f} kg, arrives {row.arrival_heading_deg:+.0f} deg off square "
        f"(drawn within +/-{math.degrees(ARRIVAL_YAW_RANGE_RAD):.0f})",
        f"PASS = the saw cuts within 10 mm of the hock and 5 deg of square | {_verdict(row)}",
    ]


def film_condition(
    arm: ArmModel, tilt_deg: float, out_dir: Path, close_up: bool, approach: str = "B"
) -> list[Episode]:
    """All 20 legs (or the close-up legs) of one condition into one video."""
    legs = leg_population(LEG_COUNT, seed=LEG_SEED)
    draws = arrivals(LEG_COUNT)
    indices = CLOSE_UP_LEGS if close_up else tuple(range(LEG_COUNT))
    name = f"approach-{approach.lower()}-{'closeup-' if close_up else ''}{arm.value}-tilt{tilt_deg:.0f}.mp4"
    film: Film | None = None
    rows: list[Episode] = []
    for index in indices:

        def attach(cell: Cell, row: Episode, index: int = index) -> None:
            nonlocal film
            if film is None:
                camera = (
                    _camera([0.0, 0.45, 0.95], 1.7, 120.0, -32.0)
                    if close_up
                    else _camera([0.75, 0.45, 0.95], 3.0, 100.0, -30.0)
                )
                film = Film(cell.model, out_dir / name, camera)
            filmed = cell
            assert isinstance(filmed, FilmedCell)
            filmed.film = film
            filmed.caption_fn = lambda: _caption(row, arm, tilt_deg, index, approach)
            if close_up:
                body = cell.model.body("slab").id

                def track() -> np.ndarray:
                    position = np.asarray(cell.data.xpos[body], dtype=float)
                    return np.array([float(np.clip(position[0], -0.2, 1.7)), 0.4, 0.95])

                filmed.track = track

        row = run_episode(
            arm,
            GripperModel.JAW_GEH6180,
            math.radians(tilt_deg),
            index,
            legs[index],
            draws[index],
            approach=approach,
            cell_class=FilmedCell,
            on_cell=attach,
        )
        rows.append(row)
        logger.info("%s leg %d: %s", name, index, "PASS" if row.success else row.failure)
    if film is not None:
        film.close()
    return rows


def main() -> None:
    """Film every condition, full runs and close-ups."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=Path.home() / "Videos" / "meat-cell" / "2026-09-15")
    parser.add_argument("--only", choices=["full", "closeup"], default=None)
    parser.add_argument("--arm", type=ArmModel, choices=list(ArmModel), default=None, help="one arm only")
    parser.add_argument("--tilt-deg", type=float, default=None, help="one tilt only")
    parser.add_argument("--approach", choices=["A", "B"], default="B", help="A carries the leg; B turns it on the belt")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    for name in ("applications.pork_leg_alignment.sim.scene", "applications.pork_leg_alignment.sim.product"):
        logging.getLogger(name).setLevel(logging.WARNING)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for arm, tilt_deg in CONDITIONS:
        if (args.arm is not None and arm is not args.arm) or (args.tilt_deg is not None and tilt_deg != args.tilt_deg):
            continue
        for close_up in (False, True):
            if (args.only == "full" and close_up) or (args.only == "closeup" and not close_up):
                continue
            rows = film_condition(arm, tilt_deg, args.out_dir, close_up, args.approach)
            print(
                f"{arm.value} tilt {tilt_deg:.0f} {'close-up' if close_up else 'full'}: {sum(r.success for r in rows)} / {len(rows)}"
            )


if __name__ == "__main__":
    main()
