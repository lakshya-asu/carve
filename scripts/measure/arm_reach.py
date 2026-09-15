"""Which belt positions each arm can put its tool at, pointing down, from its default mount.

A grid over the belt and a little beyond it, at three tool heights: shank
centreline, the top of a ham, and a clearance height for moving over legs. Each
point is an inverse kinematics solve from the home pose; a point counts as
reachable only if the solver converges inside the joint limits. One image per
arm shows it reaching the middle of the belt.

Usage:
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/measure/arm_reach.py
"""

from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path

import cv2
import mujoco
import numpy as np

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.scene import CellConfig
from robotics.hardware.arms import ArmModel
from robotics.hardware.ik import UnreachableError, arm_qpos_indices, solve_ik

BELT_TOP_Z_M = 0.90
HEIGHTS_ABOVE_BELT_M = {"shank centre": 0.05, "ham top": 0.18, "clearance": 0.35}
X_RANGE_M = (-0.4, 1.0)
Y_RANGE_M = (0.15, 0.85)
GRID_STEP_M = 0.10


def main() -> None:
    """Print a reach table per arm and height, and save one image per arm."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=Path.home() / "Videos" / "meat-cell")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    xs = np.arange(X_RANGE_M[0], X_RANGE_M[1] + 1e-9, GRID_STEP_M)
    ys = np.arange(Y_RANGE_M[0], Y_RANGE_M[1] + 1e-9, GRID_STEP_M)
    # The grid steps from the belt edge, so it has no row exactly on the centre line.
    centre_y = float(ys[np.argmin(np.abs(ys - 0.50))])
    print(f"grid x {X_RANGE_M} m, y {Y_RANGE_M} m, step {1000 * GRID_STEP_M:.0f} mm, tool pointing down, yaw -90 deg")
    print(f"| arm | height | reachable | of | x span reached at y = {centre_y:.2f} m |")
    print("|---|---|---|---|---|")
    for arm_model in (ArmModel.UR20, ArmModel.SR20IA):
        with Cell(CellConfig(belt_speed_mps=0.0, arm=arm_model)) as cell:
            cell.reset()
            for label, height in HEIGHTS_ABOVE_BELT_M.items():
                reached = 0
                centre_row = []
                for x in xs:
                    for y in ys:
                        target = np.array([x, y, BELT_TOP_Z_M + height])
                        try:
                            solve_ik(cell.model, cell.data, target, -math.pi / 2, arm=cell.arm)
                        except UnreachableError:
                            continue
                        reached += 1
                        if abs(y - centre_y) < 1e-9:
                            centre_row.append(float(x))
                span = f"{min(centre_row):+.1f} to {max(centre_row):+.1f}" if centre_row else "none"
                print(
                    f"| {arm_model.value} | {label} ({1000 * height:.0f} mm) | {reached} | {xs.size * ys.size} | {span} |"
                )

            target = np.array([0.3, 0.50, BELT_TOP_Z_M + HEIGHTS_ABOVE_BELT_M["shank centre"]])
            q = solve_ik(cell.model, cell.data, target, -math.pi / 2, arm=cell.arm)
            cell.data.qpos[arm_qpos_indices(cell.model, cell.arm)] = q
            mujoco.mj_forward(cell.model, cell.data)
            with mujoco.Renderer(cell.model, 540, 960) as renderer:
                camera = mujoco.MjvCamera()
                camera.lookat[:] = [0.3, 0.6, 0.95]
                camera.distance = 2.6
                camera.azimuth = 215.0
                camera.elevation = -25.0
                renderer.update_scene(cell.data, camera)
                image = cv2.cvtColor(renderer.render(), cv2.COLOR_RGB2BGR)
            path = args.out_dir / f"arm-reach-{arm_model.value}.png"
            cv2.imwrite(str(path), image)
            print(f"image: {path}")


if __name__ == "__main__":
    main()
