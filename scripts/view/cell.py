r"""Watch the meat cell run, or record it to a video.

Interactive:
    env -u PYTHONPATH PYTHONPATH=src python scripts/view/cell.py

Record instead of showing (works with no display):
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \\
        python scripts/view/cell.py --record out.mp4 --seconds 10

The cell as the current experiments build it: a whole pork leg on the belt, the UR20 with the
jaw gripper at the far mount, and the Gemini 335L depth camera overhead. Legs recycle to the top
of the belt once they pass the pick zone, so the cell runs continuously. The arm holds its home
pose: motion is the next subsystem.
"""

from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import LegConfig
from applications.pork_leg_alignment.sim.scene import CellConfig
from robotics.hardware.arms import ArmModel
from robotics.hardware.cameras import GEMINI_335L
from robotics.hardware.grippers import GripperModel

logger = logging.getLogger(__name__)

BELT_START_X_M = -0.75
RECYCLE_PAST_X_M = 0.55
CENTRE_Y_M = 0.42
SPAWN_Y_JITTER_M = 0.04
SPAWN_YAW_JITTER_RAD = 0.5
FPS = 30
# The reach videos' view: belt, leg and the UR20 behind the far rail in one frame.
VIEW_LOOKAT_M = [0.0, 0.55, 1.0]
VIEW_DISTANCE_M, VIEW_AZIMUTH_DEG, VIEW_ELEVATION_DEG = 3.0, 215.0, -30.0


def run(seconds: float, belt_speed_mps: float, record: Path | None, seed: int) -> int:
    """Run the cell, either in the viewer or into a video file."""
    rng = np.random.default_rng(seed)
    leg = LegConfig()
    config = CellConfig(
        belt_speed_mps=belt_speed_mps,
        leg=leg,
        arm=ArmModel.UR20,
        gripper=GripperModel.JAW_GEH6180,
        depth_cameras=(GEMINI_335L,),
        depth_camera_yaw_deg=90.0,
    )
    with Cell(config, {}) as cell:
        cell.reset()

        def respawn() -> None:
            # The leg's body origin sits in the ham, so place by the outline's centre instead.
            heading = -math.pi / 2 + rng.uniform(-SPAWN_YAW_JITTER_RAD, SPAWN_YAW_JITTER_RAD)
            centre_y = CENTRE_Y_M + rng.uniform(-SPAWN_Y_JITTER_M, SPAWN_Y_JITTER_M)
            cell.place_product(
                BELT_START_X_M - leg.outline_centre_m * math.cos(heading),
                centre_y - leg.outline_centre_m * math.sin(heading),
                heading,
                settle_s=0.1,
            )

        def step_once() -> None:
            cell.step(1)
            if cell.ground_truth().piece_pose.x_m > RECYCLE_PAST_X_M:
                respawn()

        respawn()
        steps = int(seconds / cell.model.opt.timestep)
        if record is None:
            with mujoco.viewer.launch_passive(cell.model, cell.data) as viewer:
                viewer.cam.lookat[:] = VIEW_LOOKAT_M
                viewer.cam.distance, viewer.cam.azimuth, viewer.cam.elevation = (
                    VIEW_DISTANCE_M,
                    VIEW_AZIMUTH_DEG,
                    VIEW_ELEVATION_DEG,
                )
                for _ in range(steps):
                    if not viewer.is_running():
                        break
                    step_once()
                    viewer.sync()
            return 0

        import imageio.v2 as imageio

        every = max(1, round(1.0 / (FPS * cell.model.opt.timestep)))
        writer = imageio.get_writer(record, fps=FPS, codec="libx264", pixelformat="yuv420p", macro_block_size=1)
        frames = 0
        with mujoco.Renderer(cell.model, 720, 1100) as renderer:
            camera = mujoco.MjvCamera()
            mujoco.mjv_defaultFreeCamera(cell.model, camera)
            camera.lookat[:] = VIEW_LOOKAT_M
            camera.distance, camera.azimuth, camera.elevation = VIEW_DISTANCE_M, VIEW_AZIMUTH_DEG, VIEW_ELEVATION_DEG
            for i in range(steps):
                step_once()
                if i % every == 0:
                    renderer.update_scene(cell.data, camera)
                    writer.append_data(renderer.render())
                    frames += 1
        writer.close()
    logger.info("wrote %s (%d frames, %.1f s)", record, frames, frames / FPS)
    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--belt-speed", type=float, default=0.30, help="metres per second")
    parser.add_argument("--record", type=Path, default=None, help="write a video here instead of opening a window")
    parser.add_argument("--seed", type=int, default=20260908)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return run(args.seconds, args.belt_speed, args.record, args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
