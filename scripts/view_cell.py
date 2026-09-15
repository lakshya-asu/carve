r"""Watch the meat cell run, or record it to a video.

Interactive:
    env -u PYTHONPATH PYTHONPATH=src python scripts/view_cell.py

Record instead of showing (works with no display):
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \\
        python scripts/view_cell.py --record out.mp4 --seconds 12

Pieces recycle to the top of the belt once they pass the pick zone, so the cell
runs continuously. The arm holds its home pose: motion is the next subsystem.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

from meat_cell_sim.scene import CellConfig, build_model

logger = logging.getLogger(__name__)

BELT_START_X_M = -0.75
RECYCLE_PAST_X_M = 0.55
SPAWN_Y_JITTER_M = 0.04
SPAWN_YAW_JITTER_RAD = 0.5


def _joint_qpos_slice(model: mujoco.MjModel, joint: str, size: int) -> slice:
    adr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint)]
    return slice(adr, adr + size)


def _respawn(model: mujoco.MjModel, data: mujoco.MjData, rng: np.random.Generator, thickness_m: float) -> None:
    """Put the piece back at the top of the belt with a fresh pose."""
    free = _joint_qpos_slice(model, "slab_free", 7)
    yaw = rng.uniform(-SPAWN_YAW_JITTER_RAD, SPAWN_YAW_JITTER_RAD)
    data.qpos[free] = [
        BELT_START_X_M,
        0.50 + rng.uniform(-SPAWN_Y_JITTER_M, SPAWN_Y_JITTER_M),
        0.90 + thickness_m + 0.001,
        np.cos(yaw / 2),
        0.0,
        0.0,
        np.sin(yaw / 2),
    ]
    dof = model.jnt_dofadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "slab_free")]
    data.qvel[dof : dof + 6] = 0.0


def run(seconds: float, belt_speed_mps: float, record: Path | None, seed: int) -> int:
    """Run the cell, either in the viewer or into a video file."""
    config = CellConfig(belt_speed_mps=belt_speed_mps)
    model, data = build_model(config)
    rng = np.random.default_rng(seed)
    thickness = config.slab.half_extents_m[2]

    mujoco.mj_resetDataKeyframe(model, data, mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "ur_home"))
    arm = _joint_qpos_slice(model, "ur_shoulder_pan_joint", 6)
    data.ctrl[1:7] = data.qpos[arm]
    data.ctrl[0] = belt_speed_mps
    _respawn(model, data, rng, thickness)

    slab_x = _joint_qpos_slice(model, "slab_free", 1)
    steps = int(seconds / model.opt.timestep)

    def step_once() -> None:
        mujoco.mj_step(model, data)
        if float(data.qpos[slab_x][0]) > RECYCLE_PAST_X_M:
            _respawn(model, data, rng, thickness)

    if record is None:
        with mujoco.viewer.launch_passive(model, data) as viewer:
            viewer.cam.lookat[:] = [0.0, 0.15, 0.95]
            viewer.cam.distance, viewer.cam.azimuth, viewer.cam.elevation = 2.2, 140, -24
            for _ in range(steps):
                if not viewer.is_running():
                    break
                step_once()
                viewer.sync()
        return 0

    import imageio.v3 as iio

    fps = 30
    every = max(1, round(1.0 / (fps * model.opt.timestep)))
    frames = []
    with mujoco.Renderer(model, 720, 1100) as renderer:
        cam = mujoco.MjvCamera()
        mujoco.mjv_defaultFreeCamera(model, cam)
        cam.lookat[:] = [0.0, 0.15, 0.95]
        cam.distance, cam.azimuth, cam.elevation = 2.2, 140, -24
        for i in range(steps):
            step_once()
            if i % every == 0:
                renderer.update_scene(data, cam)
                frames.append(renderer.render())
    iio.imwrite(record, frames, fps=fps)
    logger.info("wrote %s (%d frames, %.1f s)", record, len(frames), len(frames) / fps)
    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--belt-speed", type=float, default=0.15, help="metres per second")
    parser.add_argument("--record", type=Path, default=None, help="write a video here instead of opening a window")
    parser.add_argument("--seed", type=int, default=20260908)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return run(args.seconds, args.belt_speed, args.record, args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
