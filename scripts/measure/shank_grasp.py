"""Grip a leg with every arm and gripper pair and record which hold.

The check for overnight task 4 (plan/overnight-2026-09-14.md). On the default
leg, lying square on a stopped belt, each pair runs `SelectShankGrasp` then
`AcquireShank`; the three-finger gripper also runs its own end-on trotter grasp
on the UR20, chosen by Lakshya, with the leg placed so the trotter overhangs the
open edge. The table reports the outcome with the numbers the contracts
measured. Nothing is tuned between pairs.

A grip counts when the proof lift raises the tool and the part stays with it.
The tool rise column shows how much of the commanded 5 mm the arm achieved under
the leg's load; the arms' servos sag, which is a model limitation recorded in the
daily note, not a grip failure.

Usage:
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/measure/shank_grasp.py
"""

from __future__ import annotations

import argparse
import logging
import math

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import LegConfig
from applications.pork_leg_alignment.sim.scene import CellConfig
from applications.pork_leg_alignment.skills import (
    AcquireShank,
    AcquireTrotterEnd,
    SelectShankGrasp,
    SelectTrotterEndGrasp,
)
from robotics.core.skill_library import SUCCESS, SkillResult, run_skill
from robotics.hardware.arms import ArmModel
from robotics.hardware.grippers import GripperModel

LEG_X_M = 0.30
LEG_Y_M = 0.55
BLADE_PLANE_Y_M = 0.12  # the saw's default blade plane


def _row(arm: str, gripper: str, result: SkillResult, width_m: float) -> str:
    # A failed precondition or an unreachable pose ends before the jaws close,
    # so the opening and the lift may not have been measured.
    evidence = dict(result.evidence)
    ratio = evidence.get("opening_m", math.nan) / width_m
    tool = 1000 * evidence.get("tool_rise_m", math.nan)
    lag = 1000 * evidence.get("part_minus_tool_m", math.nan)
    spare = next((evidence[key] for key in ("jaw_spare_m", "finger_spare_m") if key in evidence), math.nan)
    return (
        f"| {arm} | {gripper} | {result.outcome} | {1000 * spare:.0f} | {ratio:.2f} | {tool:.2f} | {lag:+.2f} | "
        f"{result.duration_s:.1f} |"
    )


def main() -> None:
    """Run each grasp on each pair and print one table."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    leg = LegConfig()
    print(f"default leg ({1000 * leg.length_m:.0f} mm, {leg.mass_kg:.1f} kg), square to the belt, belt stopped")
    print(
        "| arm | gripper and grasp | outcome | spare opening mm | opening / width | tool rise mm | part minus tool mm | skill s |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for arm in (ArmModel.UR20, ArmModel.SR20IA):
        for gripper in (GripperModel.JAW_GEH6180, GripperModel.THREE_FINGER_3FG25):
            config = CellConfig(belt_speed_mps=0.0, leg=leg, arm=arm, gripper=gripper)
            with Cell(config) as cell:
                cell.reset()
                cell.place_product(LEG_X_M, LEG_Y_M, -math.pi / 2, settle_s=0.3)
                selected = run_skill(SelectShankGrasp(), cell, {})
                if selected.outcome != SUCCESS:
                    print(f"| {arm.value} | {gripper.value}, shank | select: {selected.outcome} | | | | | |")
                    continue
                result = run_skill(AcquireShank(), cell, selected.outputs)
            print(_row(arm.value, f"{gripper.value}, shank", result, selected.outputs["shank_grasp"].shank_width_m))

    config = CellConfig(belt_speed_mps=0.0, leg=leg, arm=ArmModel.UR20, gripper=GripperModel.THREE_FINGER_3FG25)
    with Cell(config) as cell:
        cell.reset()
        cell.place_product(LEG_X_M, BLADE_PLANE_Y_M + leg.hock_offset_m, -math.pi / 2, settle_s=0.3)
        selected = run_skill(SelectTrotterEndGrasp(), cell, {})
        result = run_skill(AcquireTrotterEnd(), cell, selected.outputs)
    print(_row("ur20", "three_finger_3fg25, end-on trotter", result, selected.outputs["trotter_grasp"].diameter_m))


if __name__ == "__main__":
    main()
