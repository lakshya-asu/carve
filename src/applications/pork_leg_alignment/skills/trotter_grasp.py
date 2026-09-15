"""Take hold of a leg end-on at the trotter, with a centric three-finger gripper.

Chosen by Lakshya on 2026-09-14 for the three-finger gripper on the UR20. Three
fingers closing around a vertical axis cannot straddle a shank lying on the
belt; turned horizontal and pointed along the leg, they close round the trotter
like a hand round a bottle neck. That needs a tool that tilts, so a SCARA cannot
do it, and it needs the trotter to hang far enough past the belt's open edge
that the lower fingers, which reach below the trotter's centreline, do not hit
the belt. Both are preconditions, so a leg or an arm that cannot take this grasp
says so before anything moves.

The approach comes in along the leg's axis from beyond the trotter tip, from a
waypoint above it so the arm does not sweep through the belt on the way, and the
grip is proven the same way as the shank grasp: lift 5 mm and measure that the
trotter rose with the tool.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import mujoco
import numpy as np

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import PRODUCT_BODY, leg_centreline
from applications.pork_leg_alignment.sim.saw import BELT_BODY, BELT_GEOM
from applications.pork_leg_alignment.skills.leg_estimate import LegEstimate
from applications.pork_leg_alignment.skills.shank_grasp import (
    CLOSE_S,
    LIFT_CHECK_M,
    LIFT_NOT_ACHIEVED,
    LIFT_TOOL_MIN_M,
    MIN_MOVE_S,
    OPEN_MARGIN_M,
    SETTLE_S,
    SPEED_FRACTION,
    LiftProof,
    lift_followed,
)
from robotics.core.skill_library import SUCCESS, Check, CheckResult, Contract, FailureMode, Port
from robotics.hardware.ik import UnreachableError, solve_ik_rotation, tool_pose, tool_rotation_for_approach

logger = logging.getLogger(__name__)

# Where along the leg the fingers close: 64 mm from the tip of the default leg,
# where the trotter is about 78 mm across. Assumed from the leg model's profile.
TROTTER_GRASP_FRACTION = 0.91
# Half the length of leg the three-finger pads touch: the pads are 30 mm wide.
TROTTER_PAD_SPAN_HALF_M = 0.02
# The tool starts this far beyond the grasp along the leg, and the waypoint
# before that is this much higher, so the arm reaches the line of the leg from
# above instead of dragging the gripper across the belt.
APPROACH_BACKOFF_M = 0.15
WAYPOINT_RISE_M = 0.25


@dataclass(frozen=True)
class TrotterGrasp:
    """Where and from which direction the fingers close on the trotter, world frame.

    Attributes:
        position_m: Tool centre point target, (3,) metres.
        approach_dir: Unit vector the tool points along: along the leg from the
            trotter tip toward the ham, horizontal.
        diameter_m: Trotter width at the grasp.
        widest_under_pads_m: Widest the trotter gets within the pads' span.
        fraction: Where along the leg, 0 at the ham butt and 1 at the trotter tip.
    """

    position_m: np.ndarray
    approach_dir: np.ndarray
    diameter_m: float
    widest_under_pads_m: float
    fraction: float


def _belt_open_edge_y_m(cell: Cell) -> float:
    belt = mujoco.mj_name2id(cell.model, mujoco.mjtObj.mjOBJ_BODY, BELT_BODY)
    surface = mujoco.mj_name2id(cell.model, mujoco.mjtObj.mjOBJ_GEOM, BELT_GEOM)
    return float(cell.model.body_pos[belt][1] - cell.model.geom_size[surface][1])


def _trotter_point_world(cell: Cell, fraction: float) -> tuple[np.ndarray, np.ndarray]:
    """World position of the leg centreline at `fraction`, and the horizontal direction from the tip toward the ham."""
    leg = cell.config.leg
    assert leg is not None
    body = mujoco.mj_name2id(cell.model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
    rotation = cell.data.xmat[body].reshape(3, 3)
    point = cell.data.xpos[body] + rotation @ leg_centreline(leg, np.array([fraction]))[0]
    toward_ham = -rotation[:, 0].copy()
    toward_ham[2] = 0.0
    return np.asarray(point, dtype=float), toward_ham / np.linalg.norm(toward_ham)


class SelectTrotterEndGrasp:
    """Choose where the fingers close on the trotter, and the direction to come in from."""

    name = "select_trotter_end_grasp"
    contract = Contract(
        inputs=(Port("leg_estimate", LegEstimate, "the leg's centreline, widths and heading, world frame"),),
        preconditions=(),
        outputs=(Port("trotter_grasp", TrotterGrasp, "tool target and approach on the trotter, world frame"),),
        success=(),
        failures=(),
    )

    def execute(self, world: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:  # noqa: ANN401
        """Place the grasp on the estimated centreline at `TROTTER_GRASP_FRACTION`, approached along the leg."""
        estimate: LegEstimate = args["leg_estimate"]
        point = estimate.point_at(TROTTER_GRASP_FRACTION)
        heading = estimate.direction_at(TROTTER_GRASP_FRACTION)
        toward_ham = -np.array([math.cos(heading), math.sin(heading), 0.0])
        half_span = TROTTER_PAD_SPAN_HALF_M / estimate.length_m
        grasp = TrotterGrasp(
            position_m=point,
            approach_dir=toward_ham,
            diameter_m=estimate.width_at(TROTTER_GRASP_FRACTION),
            widest_under_pads_m=estimate.widest_between(
                TROTTER_GRASP_FRACTION - half_span, min(1.0, TROTTER_GRASP_FRACTION + half_span)
            ),
            fraction=TROTTER_GRASP_FRACTION,
        )
        return SUCCESS, {"trotter_grasp": grasp}, {"trotter_diameter_m": grasp.diameter_m}


UNREACHABLE = FailureMode("unreachable", "no joint solution for the waypoint, approach, grasp or lift pose")
CLOSED_ON_NOTHING = FailureMode("closed_on_nothing", "the fingers closed past half the trotter's width")
SLIPPED = FailureMode("slipped", "the fingers closed but the trotter did not rise with the tool")


def _arm_tilts_tool(cell: Any, _args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    return CheckResult(bool(cell.arm.tool_tilts), float(cell.arm.tool_tilts), "the arm can point its tool horizontally")


def _centric_gripper(cell: Any, _args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    fingers = len(cell.gripper.pad_sites)
    return CheckResult(fingers >= 3, float(fingers), "a gripper whose fingers close on its own axis")


def _fingers_fit(cell: Any, args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    grasp: TrotterGrasp = args["trotter_grasp"]
    spare = cell.gripper_geometry.max_opening_m - grasp.widest_under_pads_m
    return CheckResult(spare >= 2 * OPEN_MARGIN_M, spare, f"opens at least {2000 * OPEN_MARGIN_M:.0f} mm wider")


def _trotter_overhangs(cell: Any, args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    """The grasp must be beyond the open edge by the fingers' open radius, so no finger reaches over the belt."""
    grasp: TrotterGrasp = args["trotter_grasp"]
    overhang = _belt_open_edge_y_m(cell) - float(grasp.position_m[1])
    needed = cell.gripper_geometry.max_opening_m / 2
    return CheckResult(overhang >= needed, overhang, f"grasp at least {1000 * needed:.0f} mm beyond the open edge")


def _trotter_followed_tool(cell: Any, args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    grasp: TrotterGrasp = args["trotter_grasp"]
    point, _ = _trotter_point_world(cell, grasp.fraction)
    tool, _ = tool_pose(cell.model, cell.data)
    return lift_followed(args["lift_proof"], float(tool[2]), float(point[2]))


def _gripping_the_trotter(cell: Any, args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    grasp: TrotterGrasp = args["trotter_grasp"]
    opening = float(cell.gripper_opening_m)
    low, high = 0.5 * grasp.diameter_m, 1.05 * grasp.widest_under_pads_m
    return CheckResult(low <= opening <= high, opening, f"opening between {1000 * low:.0f} and {1000 * high:.0f} mm")


class AcquireTrotterEnd:
    """Come in along the leg from beyond the trotter tip, close round the trotter, prove it with a 5 mm lift."""

    name = "acquire_trotter_end"
    contract = Contract(
        inputs=(Port("trotter_grasp", TrotterGrasp, "tool target and approach on the trotter"),),
        preconditions=(
            Check("arm_tilts_tool", "the arm can point its tool horizontally", _arm_tilts_tool),
            Check("gripper_fingers", "the gripper closes on its own axis", _centric_gripper),
            Check("finger_spare_m", "the fingers open wider than the trotter with margin", _fingers_fit),
            Check(
                "trotter_overhang_m", "the grasp lies beyond the open edge by the fingers' reach", _trotter_overhangs
            ),
        ),
        outputs=(
            Port("grip_opening_m", float, "measured opening after closing, metres"),
            Port("lift_proof", LiftProof, "tool and trotter heights when the fingers closed"),
        ),
        success=(
            Check(
                "grip_opening_m",
                "opening between half the trotter and its widest under the pads",
                _gripping_the_trotter,
            ),
            Check("part_minus_tool_m", "the trotter rose with the tool on the proof lift", _trotter_followed_tool),
        ),
        failures=(UNREACHABLE, CLOSED_ON_NOTHING, SLIPPED, LIFT_NOT_ACHIEVED),
    )

    def _move_seconds(self, cell: Cell, target_q: np.ndarray) -> float:
        speeds = np.asarray(cell.arm.max_joint_speed) * SPEED_FRACTION
        return max(MIN_MOVE_S, float(np.max(np.abs(target_q - cell.arm_qpos) / speeds)))

    def execute(self, world: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:  # noqa: ANN401
        """Run the end-on grasp and report what the fingers and the trotter did."""
        cell: Cell = world
        grasp: TrotterGrasp = args["trotter_grasp"]
        rotation = tool_rotation_for_approach(grasp.approach_dir)
        target = grasp.position_m
        approach = target - APPROACH_BACKOFF_M * grasp.approach_dir
        waypoint = approach + np.array([0.0, 0.0, WAYPOINT_RISE_M])
        lifted = target + np.array([0.0, 0.0, LIFT_CHECK_M])
        try:
            q_waypoint = solve_ik_rotation(cell.model, cell.data, waypoint, rotation, arm=cell.arm)
            q_approach = solve_ik_rotation(
                cell.model, cell.data, approach, rotation, seed_qpos=q_waypoint, arm=cell.arm
            )
            q_grasp = solve_ik_rotation(cell.model, cell.data, target, rotation, seed_qpos=q_approach, arm=cell.arm)
            q_lift = solve_ik_rotation(cell.model, cell.data, lifted, rotation, seed_qpos=q_grasp, arm=cell.arm)
        except UnreachableError as error:
            logger.info("%s: %s", self.name, error)
            return UNREACHABLE.name, {}, {}

        cell.open_gripper(cell.gripper_geometry.max_opening_m)
        for q in (q_waypoint, q_approach, q_grasp):
            cell.move_arm(q, self._move_seconds(cell, q))
        cell.step(seconds=SETTLE_S)
        cell.close_gripper()
        cell.step(seconds=CLOSE_S)
        opening = float(cell.gripper_opening_m)
        evidence = {"opening_m": opening}
        if opening < 0.5 * grasp.diameter_m:
            return CLOSED_ON_NOTHING.name, {}, evidence

        tool, _ = tool_pose(cell.model, cell.data)
        point, _ = _trotter_point_world(cell, grasp.fraction)
        proof = LiftProof(tool_z_m=float(tool[2]), part_z_m=float(point[2]))
        cell.move_arm(q_lift, max(MIN_MOVE_S, 2 * SETTLE_S))
        cell.step(seconds=SETTLE_S)
        tool, _ = tool_pose(cell.model, cell.data)
        point, _ = _trotter_point_world(cell, grasp.fraction)
        evidence["tool_rise_m"] = float(tool[2]) - proof.tool_z_m
        followed = lift_followed(proof, float(tool[2]), float(point[2]))
        evidence["part_minus_tool_m"] = followed.value
        if evidence["tool_rise_m"] < LIFT_TOOL_MIN_M:
            return LIFT_NOT_ACHIEVED.name, {}, evidence
        if not followed.passed:
            return SLIPPED.name, {}, evidence
        return SUCCESS, {"grip_opening_m": opening, "lift_proof": proof}, evidence
