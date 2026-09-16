r"""Trace one loin through the turn: where the datum offset moves, and what the piece and the jaws touch.

Two measurements behind experiments/2026-09-16-loin-infeed-transfer.md, run two. Per phase of
`RotateOnBelt` (lift, turn, lower, retreat, clear): the bone edge's offset from the datum and the
heading error from ground truth before and after, the piece's height, how far its ends reached
toward the far rail, and contact counts between the piece and the rail, the gripper and the rail,
and the gripper and the belt. Then the lower and retreat phases tick by tick: datum offset, jaw
opening, pad forces, the piece's roll and the height of its origin, which is where a piece that
was rolled in the jaws shows itself un-rolling as they open.

Usage:
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/measure/loin_turn_trace.py \\
        --arm ur20 --piece 3 --arrivals any --gripper wide_jaw
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/measure/loin_turn_trace.py \\
        --arm ur20 --piece 0 --gripper jaw_geh6180 --width-scale 0.60 --ticks
"""

from __future__ import annotations

import argparse
import logging
import math
from dataclasses import replace

import mujoco
import numpy as np
from alignment_approaches import PRODUCTS, arrivals, cell_config, park_ready, place_by_centre_of_gravity

from applications.pork_leg_alignment.sim.cell import Cell, ToolPath
from applications.pork_leg_alignment.skills import (
    INFEED_TARGET,
    AcquireShank,
    EstimateLoinFromGroundTruth,
    RotateOnBelt,
    SelectShankGrasp,
    centre_of_gravity_station,
)
from applications.pork_leg_alignment.skills.loin_estimate import estimate_loin_from_ground_truth
from robotics.core.skill_library import run_skill
from robotics.hardware.arms import ArmModel
from robotics.hardware.grippers import GripperModel

logger = logging.getLogger("loin_turn_trace")

BELT_TOP_Z_M = 0.90
TICK_S = 0.02
TICKED_PHASES = ("lower", "retreat")


class Watched(Cell):
    """A cell that counts, per step, contacts of the piece with the rail and of the gripper with the rail or belt."""

    piece_rail = 0
    gripper_rail = 0
    gripper_belt = 0
    end_reach_y_m = 0.0

    def step(self, steps: int = 1, seconds: float | None = None) -> None:
        """Step as `Cell.step` does, counting contacts after every step."""
        if seconds is not None:
            steps = max(1, round(seconds / self.model.opt.timestep))
        rail = self.model.geom("rail_far").id
        belt = self.model.geom("belt_surface").id
        piece = self.model.geom("slab_geom").id
        for _ in range(steps):
            super().step(1)
            for i in range(self.data.ncon):
                pair = {int(self.data.contact[i].geom1), int(self.data.contact[i].geom2)}
                gripper = any(
                    (mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_GEOM, g) or "").startswith("g_") for g in pair
                )
                if pair == {rail, piece}:
                    self.piece_rail += 1
                elif rail in pair and gripper:
                    self.gripper_rail += 1
                elif belt in pair and gripper:
                    self.gripper_belt += 1
            ends = self.product_centreline_world(np.array([0.0, 1.0]))
            self.end_reach_y_m = max(self.end_reach_y_m, float(ends[:, 1].max()))


def datum_and_heading(cell: Cell) -> tuple[float, float]:
    """The bone edge's offset from the datum (mm, positive inboard) and the heading error (deg), from ground truth."""
    truth = estimate_loin_from_ground_truth(cell)
    offset = INFEED_TARGET.datum_offset_m(cell, float(INFEED_TARGET.datum_point(truth)[1]))
    error = math.remainder(truth.heading_rad - INFEED_TARGET.heading_rad(cell, truth), 2.0 * math.pi)
    return 1000 * offset, math.degrees(error)


def roll_deg(cell: Cell) -> float:
    """The piece's roll about its long axis, degrees; zero lying flat."""
    rotation = cell.data.xmat[cell.model.body("slab").id].reshape(3, 3)
    return math.degrees(math.atan2(float(rotation[2, 1]), float(rotation[2, 2])))


def pad_forces_n(cell: Cell) -> tuple[float, float]:
    """Force on each pad's site, newtons."""
    forces = []
    for name in ("g_pad_left_force", "g_pad_right_force"):
        adr = int(cell.model.sensor_adr[cell.model.sensor(name).id])
        forces.append(float(np.linalg.norm(cell.data.sensordata[adr : adr + 3])))
    return forces[0], forces[1]


def trace(cell: Watched, ticks: bool) -> None:
    """Run the chain on the placed piece, printing the trace as the turn's phases go by."""
    estimated = run_skill(EstimateLoinFromGroundTruth(), cell, {})
    selected = run_skill(SelectShankGrasp(station=centre_of_gravity_station), cell, estimated.outputs)
    acquired = run_skill(AcquireShank(), cell, selected.outputs)
    print(f"grasp {acquired.outcome}, opening {1000 * acquired.evidence.get('opening_m', math.nan):.0f} mm")
    if acquired.outcome != "success":
        return
    planning = run_skill(EstimateLoinFromGroundTruth(), cell, {}).outputs["leg_estimate"]
    follow = cell.follow_tool
    body = cell.model.body("slab").id

    def phase(path: ToolPath, seconds: float) -> None:
        name = path.__name__
        before = (cell.piece_rail, cell.gripper_rail, cell.gripper_belt)
        cell.end_reach_y_m = 0.0
        datum_before, heading_before = datum_and_heading(cell)
        if ticks and name in TICKED_PHASES:
            end_s = cell.time_s + seconds
            while cell.time_s < end_s - 1e-9:
                follow(path, min(TICK_S, end_s - cell.time_s))
                datum, _ = datum_and_heading(cell)
                left, right = pad_forces_n(cell)
                print(
                    f"    {name} t+{cell.time_s - (end_s - seconds):.2f} s: datum {datum:+6.1f} mm, opening "
                    f"{1000 * cell.gripper_opening_m:6.1f} mm, pads {left:6.0f} {right:6.0f} N, roll {roll_deg(cell):+6.2f} deg, "
                    f"origin z {1000 * (cell.data.xpos[body][2] - BELT_TOP_Z_M):+5.1f} mm, tool z "
                    f"{1000 * (cell.tool_position_m[2] - BELT_TOP_Z_M):5.1f} mm"
                )
        else:
            follow(path, seconds)
        datum_after, heading_after = datum_and_heading(cell)
        print(
            f"  {name:8s} {seconds:5.2f} s: datum {datum_before:+7.1f} -> {datum_after:+7.1f} mm, heading "
            f"{heading_before:+7.2f} -> {heading_after:+7.2f} deg, piece height {1000 * (cell.data.xpos[body][2] - BELT_TOP_Z_M):+4.0f} mm, "
            f"end reached y {cell.end_reach_y_m:.3f} m (rail face 0.857), contacts piece-rail +{cell.piece_rail - before[0]}, "
            f"gripper-rail +{cell.gripper_rail - before[1]}, gripper-belt +{cell.gripper_belt - before[2]}"
        )

    cell.follow_tool = phase  # type: ignore[method-assign]
    oriented = run_skill(
        RotateOnBelt(target=INFEED_TARGET),
        cell,
        {
            "leg_estimate": planning,
            "re_estimate": lambda: estimate_loin_from_ground_truth(cell),
            **selected.outputs,
            **acquired.outputs,
        },
    )
    cell.follow_tool = follow  # type: ignore[method-assign]
    print(
        f"orient {oriented.outcome}: turn {math.degrees(oriented.evidence.get('turn_rad', math.nan)):+.0f} deg, "
        f"slip {1000 * oriented.evidence.get('slip_m', math.nan):.1f} mm, corrections {oriented.evidence.get('corrections', math.nan):.0f}, "
        f"datum at release {1000 * oriented.evidence.get('datum_offset_m', math.nan):+.1f} mm"
    )


def main() -> None:
    """Trace one piece of the population through the turn."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arm", type=ArmModel, choices=list(ArmModel), default=ArmModel.UR20)
    parser.add_argument("--gripper", type=GripperModel, default=GripperModel.WIDE_JAW)
    parser.add_argument("--piece", type=int, default=0, help="index in loin_population(20, seed=0)")
    parser.add_argument("--arrivals", choices=["square", "any"], default="square")
    parser.add_argument("--width-scale", type=float, default=None, help="override the piece's width scale")
    parser.add_argument("--ticks", action="store_true", help="print the lower and retreat phases tick by tick")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    product = PRODUCTS["loin"]
    pieces = product.population(20, 0)
    piece = (
        pieces[args.piece] if args.width_scale is None else replace(pieces[args.piece], width_scale=args.width_scale)
    )
    draws = arrivals(20, args.arrivals, pieces, product)
    arrival = draws[args.piece]
    print(
        f"{args.arm.value}, {args.gripper.value}, {args.arrivals} set, loin {args.piece}: {1000 * piece.length_m:.0f} mm, "
        f"{piece.mass_kg:.1f} kg, width scale {piece.width_scale:.2f}, bone {'left' if piece.bone_on_left else 'right'}, "
        f"arrives {math.degrees(arrival.heading_rad - product.square_heading(piece)):+.0f} deg off the target"
    )
    with Watched(cell_config(args.arm, piece, args.gripper, kind=args.arrivals, product=product)) as cell:
        cell.reset()
        park_ready(cell)
        place_by_centre_of_gravity(cell, arrival)
        cell.step(seconds=0.3)
        trace(cell, args.ticks)


if __name__ == "__main__":
    main()
