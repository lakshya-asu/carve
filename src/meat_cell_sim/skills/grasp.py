"""Take hold of a leg by its shank.

The shank between the waist and the hock is the leg's rigid handle: bone inside,
little meat, a near-constant width. Both alignment approaches start by holding
it, so this is the first skill in the library.

Two skills, so a task graph can route between them. `SelectShankGrasp` decides
where the tool closes; `AcquireShank` approaches from above, closes, and proves
the grip by lifting 5 mm and measuring that the shank rose with the tool. A grip
that only looks closed, jaws stalled on the belt or on nothing, fails that check.

For now the leg's pose is read from the simulator's ground truth, stated as
such in the contract. The perception skill that replaces it is a separate
library entry; swapping it in changes the task graph, not these skills.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import mujoco
import numpy as np

from meat_cell_sim.arm import UnreachableError, solve_ik, tool_pose
from meat_cell_sim.cell import Cell
from meat_cell_sim.product import PRODUCT_BODY, leg_centreline, leg_half_width_m
from skill_library import SUCCESS, Check, CheckResult, Contract, FailureMode, Port

logger = logging.getLogger(__name__)

BELT_TOP_Z_M = 0.90
# Where along the leg the jaws close: between the waist (about 0.55) and the
# hock (0.76), on bone. Assumed from the leg model's profile, not measured.
SHANK_GRASP_FRACTION = 0.66
# Half the length of leg the pads can touch, along the leg. At least half the
# longest pad in the cell (the jaw's 120 mm); the opening after closing is set by
# the widest shank under the pads, not by the width at the grasp centre.
PAD_SPAN_HALF_M = 0.08
# Approach heights above the grasp tried in order. A SCARA's 300 mm stroke with
# a long gripper cannot always reach the first; the last still clears a shank
# (about 90 mm tall, grasped at its centreline) under 30 mm pads.
APPROACH_CLEARANCES_M = (0.20, 0.15, 0.10)
LIFT_CHECK_M = 0.005
# The proof lift must raise the tool at least this much to prove anything. The
# arms' position servos sag under a leg (the UR20 raised its tool 1.6 mm of a
# commanded 5 mm on the default leg, 2026-09-14), so the grip is judged against
# how far the tool actually rose, not against the command.
LIFT_TOOL_MIN_M = 0.0005
# How far the part may lag the tool on that lift and still count as held.
LIFT_FOLLOW_TOLERANCE_M = 0.001
# Fraction of each joint's rated speed a move may use; the rest is margin.
SPEED_FRACTION = 0.5
MIN_MOVE_S = 0.4
SETTLE_S = 0.3
CLOSE_S = 0.6
# Each side of the widest shank under the pads when approaching. The arm places
# the tool to about 3 mm (measured on the UR20, 2026-09-14); the rest covers
# pose error once perception, not ground truth, supplies the leg.
OPEN_MARGIN_M = 0.02


@dataclass(frozen=True)
class ShankGrasp:
    """Where the tool closes on the shank, world frame.

    Attributes:
        position_m: Tool centre point target, (3,) metres.
        yaw_rad: Tool heading; the tool x axis lies along the leg, so the
            fingers, which close along tool y, close across it.
        shank_width_m: Width of the shank at the grasp centre.
        widest_under_pads_m: Widest the shank gets within `PAD_SPAN_HALF_M` of
            the grasp along the leg.
        fraction: Where along the leg, 0 at the ham butt and 1 at the trotter tip.
    """

    position_m: np.ndarray
    yaw_rad: float
    shank_width_m: float
    widest_under_pads_m: float
    fraction: float


@dataclass(frozen=True)
class LiftProof:
    """Heights when the grip closed, so a check can measure the proof lift against them.

    Attributes:
        tool_z_m: Tool centre point height, world frame.
        part_z_m: Height of the gripped point on the leg's centreline, world frame.
    """

    tool_z_m: float
    part_z_m: float


def lift_followed(proof: LiftProof, tool_z_m: float, part_z_m: float) -> CheckResult:
    """Whether the part rose with the tool since `proof` was taken.

    Returns:
        Passed if the tool rose at least `LIFT_TOOL_MIN_M` and the part lagged it
        by no more than `LIFT_FOLLOW_TOLERANCE_M`; the value is part rise minus
        tool rise, metres.
    """
    tool_rise = tool_z_m - proof.tool_z_m
    lag = (part_z_m - proof.part_z_m) - tool_rise
    return CheckResult(
        tool_rise >= LIFT_TOOL_MIN_M and lag >= -LIFT_FOLLOW_TOLERANCE_M,
        lag,
        f"tool rose at least {1000 * LIFT_TOOL_MIN_M:.1f} mm and the part lagged it by at most "
        f"{1000 * LIFT_FOLLOW_TOLERANCE_M:.1f} mm",
    )


def _shank_point_world(cell: Cell, fraction: float) -> tuple[np.ndarray, float]:
    """World position of the leg centreline at `fraction`, and the leg's heading."""
    leg = cell.config.leg
    assert leg is not None
    body = mujoco.mj_name2id(cell.model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
    rotation = cell.data.xmat[body].reshape(3, 3)
    point_body = leg_centreline(leg, np.array([fraction]))[0]
    point_world = cell.data.xpos[body] + rotation @ point_body
    heading = math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))
    return np.asarray(point_world, dtype=float), heading


def _leg_on_belt(cell: Any, _args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    body = mujoco.mj_name2id(cell.model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
    height = float(cell.data.xpos[body][2]) - BELT_TOP_Z_M
    return CheckResult(abs(height) < 0.02, height, "leg origin within 20 mm of the belt surface")


class SelectShankGrasp:
    """Choose where on the shank to close, from the leg's pose."""

    name = "select_shank_grasp"
    contract = Contract(
        inputs=(),
        preconditions=(
            Check("leg_on_belt_m", "the leg rests on the belt, origin within 20 mm of its surface", _leg_on_belt),
        ),
        outputs=(Port("shank_grasp", ShankGrasp, "tool target on the shank, world frame, from ground-truth pose"),),
        success=(),
        failures=(),
    )

    def execute(self, world: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:  # noqa: ANN401
        """Place the grasp on the leg centreline at `SHANK_GRASP_FRACTION`."""
        cell: Cell = world
        leg = cell.config.leg
        assert leg is not None
        point, heading = _shank_point_world(cell, SHANK_GRASP_FRACTION)
        half_span = PAD_SPAN_HALF_M / leg.length_m
        under_pads = np.linspace(SHANK_GRASP_FRACTION - half_span, SHANK_GRASP_FRACTION + half_span, 41)
        grasp = ShankGrasp(
            position_m=point,
            yaw_rad=heading,
            shank_width_m=2.0 * float(leg_half_width_m(leg, np.array([SHANK_GRASP_FRACTION]))[0]),
            widest_under_pads_m=2.0 * float(leg_half_width_m(leg, under_pads).max()),
            fraction=SHANK_GRASP_FRACTION,
        )
        evidence = {"shank_width_m": grasp.shank_width_m, "widest_under_pads_m": grasp.widest_under_pads_m}
        return SUCCESS, {"shank_grasp": grasp}, evidence


UNREACHABLE = FailureMode("unreachable", "no joint solution for any approach height, the grasp, or the lift")
CLOSED_ON_NOTHING = FailureMode("closed_on_nothing", "the jaws closed past half the shank's width")
SLIPPED = FailureMode("slipped", "the jaws closed but the shank did not rise with the tool")
LIFT_NOT_ACHIEVED = FailureMode("lift_not_achieved", "the arm could not raise the tool under the part's load")


def _jaws_fit(cell: Any, args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    grasp: ShankGrasp = args["shank_grasp"]
    spare = cell.gripper_geometry.max_opening_m - grasp.widest_under_pads_m
    return CheckResult(
        spare >= 2 * OPEN_MARGIN_M, spare, f"jaws open at least {2000 * OPEN_MARGIN_M:.0f} mm wider than the shank"
    )


def _shank_followed_tool(cell: Any, args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    grasp: ShankGrasp = args["shank_grasp"]
    point, _ = _shank_point_world(cell, grasp.fraction)
    tool, _ = tool_pose(cell.model, cell.data)
    return lift_followed(args["lift_proof"], float(tool[2]), float(point[2]))


def _gripping_the_shank(cell: Any, args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    grasp: ShankGrasp = args["shank_grasp"]
    opening = float(cell.gripper_opening_m)
    low, high = 0.5 * grasp.shank_width_m, 1.05 * grasp.widest_under_pads_m
    return CheckResult(low <= opening <= high, opening, f"opening between {1000 * low:.0f} and {1000 * high:.0f} mm")


class AcquireShank:
    """Approach from above, close on the shank, and prove the grip with a 5 mm lift."""

    name = "acquire_shank"
    contract = Contract(
        inputs=(Port("shank_grasp", ShankGrasp, "tool target on the shank"),),
        preconditions=(Check("jaw_spare_m", "the jaws open wider than the shank with margin", _jaws_fit),),
        outputs=(
            Port("grip_opening_m", float, "measured opening after closing, metres"),
            Port("lift_proof", LiftProof, "tool and shank heights when the jaws closed"),
        ),
        success=(
            Check(
                "grip_opening_m",
                "opening between half the shank and the widest shank under the pads",
                _gripping_the_shank,
            ),
            Check("part_minus_tool_m", "the shank rose with the tool on the proof lift", _shank_followed_tool),
        ),
        failures=(UNREACHABLE, CLOSED_ON_NOTHING, SLIPPED, LIFT_NOT_ACHIEVED),
    )

    def _move_seconds(self, cell: Cell, target_q: np.ndarray) -> float:
        speeds = np.asarray(cell.arm.max_joint_speed) * SPEED_FRACTION
        return max(MIN_MOVE_S, float(np.max(np.abs(target_q - cell.arm_qpos) / speeds)))

    def execute(self, world: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:  # noqa: ANN401
        """Run the grasp and report what the jaws and the shank did."""
        cell: Cell = world
        grasp: ShankGrasp = args["shank_grasp"]
        target = grasp.position_m
        evidence: dict[str, float] = {}
        q_above = None
        for clearance in APPROACH_CLEARANCES_M:
            try:
                q_above = solve_ik(
                    cell.model, cell.data, target + np.array([0.0, 0.0, clearance]), grasp.yaw_rad, arm=cell.arm
                )
            except UnreachableError:
                continue
            evidence["approach_clearance_m"] = clearance
            break
        if q_above is None:
            logger.info("%s: no approach height reachable above %s", self.name, np.round(target, 3).tolist())
            return UNREACHABLE.name, {}, evidence
        try:
            q_grasp = solve_ik(cell.model, cell.data, target, grasp.yaw_rad, seed_qpos=q_above, arm=cell.arm)
            lifted = target + np.array([0.0, 0.0, LIFT_CHECK_M])
            q_lift = solve_ik(cell.model, cell.data, lifted, grasp.yaw_rad, seed_qpos=q_grasp, arm=cell.arm)
        except UnreachableError as error:
            logger.info("%s: %s", self.name, error)
            return UNREACHABLE.name, {}, evidence

        cell.open_gripper(min(cell.gripper_geometry.max_opening_m, grasp.widest_under_pads_m + 2 * OPEN_MARGIN_M))
        cell.move_arm(q_above, self._move_seconds(cell, q_above))
        cell.move_arm(q_grasp, self._move_seconds(cell, q_grasp))
        cell.step(seconds=SETTLE_S)
        cell.close_gripper()
        cell.step(seconds=CLOSE_S)
        opening = float(cell.gripper_opening_m)
        evidence["opening_m"] = opening
        if opening < 0.5 * grasp.shank_width_m:
            return CLOSED_ON_NOTHING.name, {}, evidence

        tool, _ = tool_pose(cell.model, cell.data)
        point, _ = _shank_point_world(cell, grasp.fraction)
        proof = LiftProof(tool_z_m=float(tool[2]), part_z_m=float(point[2]))
        cell.move_arm(q_lift, max(MIN_MOVE_S, 2 * SETTLE_S))
        cell.step(seconds=SETTLE_S)
        tool, _ = tool_pose(cell.model, cell.data)
        point, _ = _shank_point_world(cell, grasp.fraction)
        evidence["tool_rise_m"] = float(tool[2]) - proof.tool_z_m
        followed = lift_followed(proof, float(tool[2]), float(point[2]))
        evidence["part_minus_tool_m"] = followed.value
        if evidence["tool_rise_m"] < LIFT_TOOL_MIN_M:
            return LIFT_NOT_ACHIEVED.name, {}, evidence
        if not followed.passed:
            return SLIPPED.name, {}, evidence
        return SUCCESS, {"grip_opening_m": opening, "lift_proof": proof}, evidence
