r"""Measure how far the product moves in the gripper as the jaws close.

This is the number the control architecture analysis rests on and never had.
Its claim: if the product shifts in the hand by more than the placement bound
during closure, then no amount of belt-side tracking can meet that bound,
because the shift happens after tracking has finished. The assumed value was
6 mm at the 95th percentile with no source. This measures it.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/measure_grasp_shift.py --trials 12

Method. The belt is stopped, so what is measured is closure alone and not
conveyor motion. The product is placed at a known pose. The tool is commanded to
a grasp whose lateral offset and yaw error from the true product pose are set by
the sweep, which is what a real perception error would produce. The product's
pose **in the tool frame** is recorded before contact, after the jaws close, and
after the lift. The shift is the change in that frame: how far the product ends
up from where the gripper believed it was when it committed.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import mujoco
import numpy as np

from meat_cell_sim.arm import (
    UnreachableError,
    arm_qpos_indices,
    solve_ik,
    tool_pose,
)
from meat_cell_sim.contracts import wrap_axis_angle
from meat_cell_sim.scene import CellConfig, SlabConfig, build_model

logger = logging.getLogger(__name__)

APPROACH_HEIGHT_M = 0.12
LIFT_HEIGHT_M = 0.12
# Jaw pads are 60 mm tall and the TCP sits at their mid height, so the tool goes
# to half the product thickness above the belt to straddle it rather than press
# on it.
# The gripper actuator commands one finger's joint, and the opening between the
# pads is twice that. Conflating the two is how the jaws ended up commanded to
# 70 mm around a 90 mm product and struck it on the way down.
OPEN_JOINT_M = 0.055  # 110 mm between the pads, clearing a 90 mm product by 10 mm a side
SETTLE_S = 0.4
MOVE_S = 1.2


@dataclass(frozen=True)
class Trial:
    """One grasp attempt and what moved during it."""

    seed: int
    lateral_offset_mm: float
    yaw_error_deg: float
    squeeze_mm: float
    friction: float
    closure_shift_mm: float
    closure_turn_deg: float
    total_shift_mm: float
    total_turn_deg: float
    lifted: bool


def _piece_in_tool(model: mujoco.MjModel, data: mujoco.MjData, piece_qadr: int) -> tuple[np.ndarray, float]:
    """Product position and heading expressed in the tool frame.

    This is the quantity that matters. The product's world pose changes when the
    arm carries it and that is not a shift; only its pose relative to the jaws
    holding it is.
    """
    tool_position, tool_rotation = tool_pose(model, data)
    piece_position = data.qpos[piece_qadr : piece_qadr + 3].copy()
    offset = tool_rotation.T @ (piece_position - tool_position)
    quat = data.qpos[piece_qadr + 3 : piece_qadr + 7]
    piece_yaw = math.atan2(2.0 * (quat[0] * quat[3] + quat[1] * quat[2]), 1.0 - 2.0 * (quat[2] ** 2 + quat[3] ** 2))
    tool_yaw = math.atan2(tool_rotation[1, 0], tool_rotation[0, 0])
    return offset[:2], wrap_axis_angle(piece_yaw - tool_yaw)


def _hold(model: mujoco.MjModel, data: mujoco.MjData, seconds: float) -> None:
    for _ in range(int(seconds / model.opt.timestep)):
        mujoco.mj_step(model, data)


def _move_to(model: mujoco.MjModel, data: mujoco.MjData, target_q: np.ndarray, seconds: float) -> None:
    """Ramp the joint commands from where they are to `target_q`.

    A step change would have the position servos slam the arm, and the product
    would move because of that rather than because of the grasp.
    """
    start = data.ctrl[1:7].copy()
    steps = max(1, int(seconds / model.opt.timestep))
    for step in range(steps):
        blend = (step + 1) / steps
        data.ctrl[1:7] = start + blend * (target_q - start)
        mujoco.mj_step(model, data)


def run_trial(
    config: CellConfig,
    seed: int,
    lateral_offset_m: float,
    yaw_error_rad: float,
    squeeze_m: float,
) -> Trial | None:
    """One placement, approach, close and lift. None if the pose is unreachable."""
    model, data = build_model(config)
    piece_qadr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "slab_free")]
    arm_index = arm_qpos_indices(model)
    rng = np.random.default_rng(seed)

    half = config.slab.half_extents_m
    piece_x = rng.uniform(-0.12, 0.02)
    piece_y = 0.50 + rng.uniform(-0.03, 0.03)
    piece_yaw = rng.uniform(-math.pi / 2, math.pi / 2)

    mujoco.mj_resetDataKeyframe(model, data, mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "ur_home"))
    data.qpos[piece_qadr : piece_qadr + 7] = [
        piece_x,
        piece_y,
        0.90 + half[2],
        math.cos(piece_yaw / 2),
        0.0,
        0.0,
        math.sin(piece_yaw / 2),
    ]
    data.ctrl[0] = 0.0  # belt stopped: this measures closure, not conveyor motion
    data.ctrl[1:7] = data.qpos[arm_index]
    data.ctrl[7] = OPEN_JOINT_M
    mujoco.mj_forward(model, data)
    _hold(model, data, 0.3)

    # The grasp the planner would command, carrying the sweep's error.
    #
    # The fingers slide along the tool's **y** axis, while `tool_down_rotation`
    # names the tool's x axis. The finger axis in the world is therefore at
    # tool yaw minus 90 degrees. Wanting the fingers across the product means
    # tool yaw equals the product's heading, not square to it. Commanding it
    # square closes the jaws along the 180 mm length instead of across the
    # 90 mm width, which looks like a plausible grasp and is not one.
    across = piece_yaw + math.pi / 2
    grasp_x = piece_x + lateral_offset_m * math.cos(across)
    grasp_y = piece_y + lateral_offset_m * math.sin(across)
    tool_yaw = piece_yaw + yaw_error_rad
    grasp_z = 0.90 + half[2]

    try:
        approach_q = solve_ik(model, data, np.array([grasp_x, grasp_y, grasp_z + APPROACH_HEIGHT_M]), tool_yaw)
        grasp_q = solve_ik(model, data, np.array([grasp_x, grasp_y, grasp_z]), tool_yaw, seed_qpos=approach_q)
        lift_q = solve_ik(
            model, data, np.array([grasp_x, grasp_y, grasp_z + LIFT_HEIGHT_M]), tool_yaw, seed_qpos=grasp_q
        )
    except UnreachableError as unreachable:
        logger.warning("seed %d: %s", seed, unreachable)
        return None

    _move_to(model, data, approach_q, MOVE_S)
    _move_to(model, data, grasp_q, MOVE_S)
    _hold(model, data, SETTLE_S)
    before_offset, before_yaw = _piece_in_tool(model, data, piece_qadr)

    data.ctrl[7] = max(0.0, half[1] - squeeze_m)
    _hold(model, data, SETTLE_S + 0.3)
    closed_offset, closed_yaw = _piece_in_tool(model, data, piece_qadr)

    _move_to(model, data, lift_q, MOVE_S)
    _hold(model, data, SETTLE_S)
    lifted_offset, lifted_yaw = _piece_in_tool(model, data, piece_qadr)
    lifted = bool(data.qpos[piece_qadr + 2] > 0.90 + half[2] + 0.03)

    return Trial(
        seed=seed,
        lateral_offset_mm=1000 * lateral_offset_m,
        yaw_error_deg=math.degrees(yaw_error_rad),
        squeeze_mm=1000 * squeeze_m,
        friction=config.slab.friction_slide,
        closure_shift_mm=1000 * float(np.linalg.norm(closed_offset - before_offset)),
        closure_turn_deg=math.degrees(abs(wrap_axis_angle(closed_yaw - before_yaw))),
        total_shift_mm=1000 * float(np.linalg.norm(lifted_offset - before_offset)),
        total_turn_deg=math.degrees(abs(wrap_axis_angle(lifted_yaw - before_yaw))),
        lifted=lifted,
    )


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return float("nan")
    return float(np.percentile(values, 100 * fraction))


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--trials", type=int, default=8, help="seeds per sweep cell")
    parser.add_argument("--offsets-mm", type=float, nargs="+", default=[0.0, 5.0, 10.0])
    parser.add_argument("--yaw-errors-deg", type=float, nargs="+", default=[0.0, 10.0])
    parser.add_argument("--squeeze-mm", type=float, default=4.0)
    parser.add_argument("--frictions", type=float, nargs="+", default=[0.35])
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    trials: list[Trial] = []
    for friction in args.frictions:
        config = CellConfig(belt_speed_mps=0.0, slab=SlabConfig(friction_slide=friction))
        for offset_mm in args.offsets_mm:
            for yaw_deg in args.yaw_errors_deg:
                for seed in range(args.trials):
                    trial = run_trial(
                        config,
                        seed,
                        offset_mm / 1000.0,
                        math.radians(yaw_deg),
                        args.squeeze_mm / 1000.0,
                    )
                    if trial is not None:
                        trials.append(trial)
                held = [t for t in trials if t.lateral_offset_mm == offset_mm and t.yaw_error_deg == yaw_deg]
                shifts = [t.closure_shift_mm for t in held]
                print(
                    f"  offset {offset_mm:4.1f} mm  yaw err {yaw_deg:4.1f} deg  "
                    f"n={len(held):3d}  closure shift mean {np.mean(shifts):6.3f} mm  "
                    f"p95 {_percentile(shifts, 0.95):6.3f}  max {max(shifts):6.3f}  "
                    f"lifted {sum(t.lifted for t in held)}/{len(held)}"
                )

    if not trials:
        print("no trials completed")
        return 1
    closure = [t.closure_shift_mm for t in trials]
    total = [t.total_shift_mm for t in trials]
    print(f"\nall {len(trials)} trials, belt stopped, squeeze {args.squeeze_mm:.1f} mm")
    print(
        f"  closure shift      mean {np.mean(closure):6.3f} mm  p95 {_percentile(closure, 0.95):6.3f}  max {max(closure):6.3f}"
    )
    print(
        f"  through lift       mean {np.mean(total):6.3f} mm  p95 {_percentile(total, 0.95):6.3f}  max {max(total):6.3f}"
    )
    print(f"  turn at closure    p95 {_percentile([t.closure_turn_deg for t in trials], 0.95):6.3f} deg")
    print(f"  lifted             {sum(t.lifted for t in trials)}/{len(trials)}")
    print("\nassumed in the control architecture note: 6.000 mm p95, unsourced")

    if args.csv:
        with args.csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(asdict(trials[0])))
            writer.writeheader()
            writer.writerows(asdict(t) for t in trials)
        print(f"wrote {args.csv}")
    if args.json:
        args.json.write_text(json.dumps([asdict(t) for t in trials], indent=2), encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
