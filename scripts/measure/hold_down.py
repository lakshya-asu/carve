"""How far the blade moves a leg while cutting, with and without the hold-down belt.

For each feed resistance and each hold-down setting, one leg square to the blade
with its hock on the blade plane rides through the saw. The table reports where
the cut entered and left relative to the hock, how far the leg turned and slid
while the blade was in it, and the outcome. Feed resistance is unmeasured, so it
is swept rather than chosen.

Usage:
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/measure/hold_down.py
"""

from __future__ import annotations

import argparse
import logging
import math

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.hold_down import HoldDownConfig
from applications.pork_leg_alignment.sim.product import LegConfig
from applications.pork_leg_alignment.sim.saw import SawConfig
from applications.pork_leg_alignment.sim.scene import CellConfig

START_BEFORE_BLADE_M = 0.80
PASS_TIMEOUT_S = 8.0


def main() -> None:
    """Sweep feed resistance with the hold-down off and on and print one table."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--belt-speed", type=float, default=0.30)
    parser.add_argument("--feeds", type=float, nargs="+", default=[0.0, 30.0, 60.0, 120.0])
    parser.add_argument("--press", type=float, default=HoldDownConfig().press_force_n)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    print(f"belt {args.belt_speed:.2f} m/s, default leg (722 mm, 11 kg), hock placed on the blade plane, square")
    print("| hold-down | feed N | outcome | entry mm | exit mm | turned deg | slid mm |")
    print("|---|---|---|---|---|---|---|")
    for hold in (False, True):
        for feed in args.feeds:
            config = CellConfig(
                belt_speed_mps=args.belt_speed,
                leg=LegConfig(),
                saw=SawConfig(feed_resistance_n=feed),
                hold_down=HoldDownConfig(press_force_n=args.press) if hold else None,
            )
            with Cell(config) as cell:
                assert cell.saw is not None and config.leg is not None
                cell.reset()
                cell.place_product(
                    cell.saw.config.x_m - START_BEFORE_BLADE_M,
                    cell.saw.blade_y_m + config.leg.hock_offset_m,
                    -math.pi / 2,
                )
                deadline = cell.time_s + PASS_TIMEOUT_S
                while cell.cut_result is None and cell.time_s < deadline:
                    cell.step(seconds=0.02)
                result = cell.cut_result
            label = f"{args.press:.0f} N" if hold else "none"
            if result is None:
                print(f"| {label} | {feed:.0f} | undecided after {PASS_TIMEOUT_S:.0f} s | | | | |")
                continue
            print(
                f"| {label} | {feed:.0f} | {result.outcome.value} | {1000 * result.offset_from_hock_m:+.1f} | "
                f"{1000 * result.offset_at_exit_m:+.1f} | {math.degrees(result.yaw_drift_rad):+.2f} | "
                f"{1000 * result.slip_m:.1f} |"
            )


if __name__ == "__main__":
    main()
