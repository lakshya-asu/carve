r"""Lay a batch of generated legs out on a board and photograph them.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/view/leg_variants.py --count 20 --out legs.png

Every leg comes from `leg_population`, so the sheet is reproducible from the
seed. Laid out on one plane, all pointing the same way, so the differences that
show are the ones the generator actually produces: overall size, how bulky the
ham is against the hock, how far the hock swings off the line of the ham, and
which side of the animal the leg came from.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import mujoco
import numpy as np

from applications.pork_leg_alignment.sim.product import leg_mesh, leg_population

logger = logging.getLogger(__name__)

COLUMNS = 5
COLUMN_PITCH_M = 0.95
ROW_PITCH_M = 0.50


def build_board(count: int, seed: int) -> tuple[mujoco.MjModel, mujoco.MjData]:
    """A flat white board with `count` legs resting on it in a grid."""
    legs = leg_population(count, seed)
    rows = -(-count // COLUMNS)
    spec = mujoco.MjSpec()
    spec.compiler.degree = False

    spec.add_material(name="board", rgba=[0.90, 0.91, 0.92, 1.0])
    spec.add_material(name="meat", rgba=[0.87, 0.71, 0.68, 1.0])
    spec.worldbody.add_light(pos=[0.0, 0.0, 4.0], dir=[0.0, 0.0, -1.0], type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL)
    spec.worldbody.add_light(pos=[-1.5, -1.5, 2.5], dir=[0.5, 0.5, -1.0])
    spec.worldbody.add_geom(
        type=mujoco.mjtGeom.mjGEOM_PLANE, size=[6.0, 6.0, 0.1], material="board", pos=[0.0, 0.0, 0.0]
    )

    for index, leg in enumerate(legs):
        vertices, faces = leg_mesh(leg)
        mesh = spec.add_mesh()
        mesh.name = leg.name
        mesh.uservert = vertices.flatten().tolist()
        mesh.userface = faces.flatten().tolist()
        column, row = index % COLUMNS, index // COLUMNS
        body = spec.worldbody.add_body()
        body.name = f"leg_{index}"
        body.pos = [
            (column - (COLUMNS - 1) / 2) * COLUMN_PITCH_M,
            ((rows - 1) / 2 - row) * ROW_PITCH_M,
            0.0,
        ]
        geom = body.add_geom()
        geom.name = f"leg_geom_{index}"
        geom.type = mujoco.mjtGeom.mjGEOM_MESH
        geom.meshname = leg.name
        geom.material = "meat"

    # Frame the whole board. The field has to satisfy both axes, and with a wide
    # sensor it is the row of five that drives it, not the four rows: fitting
    # only the rows clipped the last column off every sheet.
    width_px, height_px = 1920, 1080
    aspect = width_px / height_px
    half_across = COLUMNS * COLUMN_PITCH_M / 2
    half_along = rows * ROW_PITCH_M / 2
    half_vertical = max(half_along, half_across / aspect) * 1.12
    camera_height = 6.0
    camera = spec.worldbody.add_camera()
    camera.name = "board"
    camera.pos = [0.0, 0.0, camera_height]
    camera.quat = [1.0, 0.0, 0.0, 0.0]
    camera.fovy = float(np.degrees(2 * np.arctan(half_vertical / camera_height)))

    spec.visual.global_.offwidth = width_px
    spec.visual.global_.offheight = height_px
    model = spec.compile()
    return model, mujoco.MjData(model)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--out", type=Path, default=Path("legs.png"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    model, data = build_board(args.count, args.seed)
    mujoco.mj_forward(model, data)
    with mujoco.Renderer(model, 1080, 1920) as renderer:
        renderer.update_scene(data, camera="board")
        image = renderer.render()
    import imageio.v3 as iio

    iio.imwrite(args.out, image)
    logger.info("wrote %s (%d legs, seed %d)", args.out, args.count, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
