"""Take hold of a leg by its shank, on a stopped or a moving belt.

The shank between the waist and the hock is the leg's rigid handle: bone inside,
little meat, a near-constant width. Both alignment approaches start by holding
it, so this is the first skill in the library.

Two skills, so a task graph can route between them. `SelectShankGrasp` decides
where the tool closes; `AcquireShank` approaches from above, closes, and proves
the grip by lifting 5 mm and measuring that the shank rose with the tool. A grip
that only looks closed, jaws stalled on the belt or on nothing, fails that check.

The grasp point rides the belt. The selection records the encoder reading it was
made at, and every tool pose the acquisition commands adds the belt's travel
since, so the jaws come down on the shank where it is rather than where it was.
With the belt stopped that adds nothing, and the skill is the stopped-belt one
it started as.

The leg comes in as a `LegEstimate` (`skills/leg_estimate.py`), from the
simulator's ground truth or from the camera; which one is the task graph's
choice, not these skills'. The proof lift's measurement of the shank is ground
truth, because it is scoring the grip, not planning it.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import mujoco
import numpy as np

from applications.pork_leg_alignment.sim.cell import TOOL_TICK_S, Cell
from applications.pork_leg_alignment.sim.product import PRODUCT_BODY, leg_centreline
from applications.pork_leg_alignment.skills.leg_estimate import LegEstimate
from robotics.core.grasp_action import tool_rotation
from robotics.core.skill_library import SUCCESS, Check, CheckResult, Contract, FailureMode, Port
from robotics.hardware.ik import UnreachableError, solve_ik_rotation, tool_pose

logger = logging.getLogger(__name__)

BELT_TOP_Z_M = 0.90
# Where along the leg the jaws close: between the waist (about 0.55) and the
# hock (0.76), on bone. Assumed from the leg model's profile, not measured. At
# 0.66 the jaw's 120 mm pads reached 3 mm past the waist, which widens quickly
# there (112 mm at 0.58, 150 mm at 0.50), and a millimetre of placement error
# along the leg had the jaws closing at 135 mm instead of 110; at 0.68 the
# margin was 17 mm and an 8 mm placement error on a 739 mm leg put one pad on
# the waist, where it pinched the taper with 1500 N and the SR-20iA could not
# lift (both 2026-09-15). At 0.70 the pads span 0.62 to 0.78 of the leg, 37 mm
# clear of the waist, and their last 20 mm reach past the hock onto the
# narrower trotter, which does not matter to the grip.
SHANK_GRASP_FRACTION = 0.70
# Half the length of leg the pads can touch, along the leg. At least half the
# longest pad in the cell (the jaw's 120 mm); the opening after closing is set by
# the widest shank under the pads, not by the width at the grasp centre.
PAD_SPAN_HALF_M = 0.08
# Approach heights above the grasp tried in order, along the tool axis. The
# arm travels to the approach point in joint space, so the open jaws sweep
# across the belt at about that height: the first clears the tallest ham in
# the population (256 mm) with the jaw's 30 mm pads below the tool point,
# and at 0.15 m the SR-20iA swept its jaws through the ham of a 766 mm leg and
# shoved it 80 mm sideways (2026-09-15). A SCARA's 300 mm stroke with a long
# gripper cannot always reach the first; the last still clears a shank (about
# 90 mm tall, grasped at its centreline).
APPROACH_CLEARANCES_M = (0.30, 0.25, 0.20, 0.15, 0.10)
# Descent speed from the approach height, so a higher approach takes longer
# rather than arriving faster.
DESCEND_MPS = 0.6
LIFT_CHECK_M = 0.005
# The proof lift must raise the tool at least this much to prove anything. The
# grip is judged against how far the tool actually rose, not against the
# command, so an arm that cannot lift the load reports that rather than a slip.
LIFT_TOOL_MIN_M = 0.0005
# How far the part may lag the tool on that lift and still count as held. A
# grip settles under load before it holds: the three-finger gripper's end-on
# hold on a trotter lagged 1.8 mm on a 5 mm lift and 1.6 mm on a 10 mm lift
# (2026-09-15), the same amount whatever the lift, which is settling of the
# pad contacts and not slip. The jaw on a shank lags under 0.1 mm.
LIFT_FOLLOW_TOLERANCE_M = 0.002
# Fraction of each joint's rated speed a move may use; the rest is margin.
SPEED_FRACTION = 0.5
MIN_MOVE_S = 0.4
# The descent from the approach height onto the shank, tracking the belt, and
# the proof lift. Every fixed wait here is belt travel the alignment has to
# make up downstream: at 0.3 m/s the grasp's waits alone cost half a metre.
MIN_DESCEND_S = 0.3
LIFT_S = 0.3
SETTLE_S = 0.15
CLOSE_S = 0.6
# Each side of the widest shank under the pads when approaching. The arm places
# the tool to about 3 mm (measured on the UR20, 2026-09-14); the rest covers
# pose error once perception, not ground truth, supplies the leg.
OPEN_MARGIN_M = 0.02
# The pad tips stay at least this far above the belt. Grasping above the
# shank's centreline to gain clearance is not free: pads squeezing an ellipse
# above its equator are pushed upward, and 6 mm above the centreline that push
# lifted the SR-20iA's quill 1.5 mm, wound up its servo, and the arm could not
# lift the leg (2026-09-15). The jaw's pads are shaped so the tip sits 35 mm
# below the tool point, a few millimetres above the belt with the tool on the
# centreline of the smallest leg, so this floor only acts on outliers.
PAD_BELT_CLEARANCE_M = 0.003


@dataclass(frozen=True)
class ShankGrasp:
    """Where the tool closes on the shank, world frame, at a known belt position.

    Attributes:
        position_m: Tool centre point target, (3,) metres, where the shank was
            when the encoder read `belt_travel_m`.
        yaw_rad: Tool heading; the tool x axis lies along the leg, so the
            fingers, which close along tool y, close across it.
        shank_width_m: Width of the shank at the grasp centre.
        widest_under_pads_m: Widest the shank gets within `PAD_SPAN_HALF_M` of
            the grasp along the leg.
        fraction: Where along the leg, 0 at the ham butt and 1 at the trotter tip.
        tilt_rad: Lean of the tool from vertical about the finger axis, positive
            leaning the tool body toward the ham. Zero on an arm that cannot tilt.
        belt_travel_m: Encoder reading when the leg's pose was read. The grasp
            point has moved along the belt by the travel since.
    """

    position_m: np.ndarray
    yaw_rad: float
    shank_width_m: float
    widest_under_pads_m: float
    fraction: float
    tilt_rad: float = 0.0
    belt_travel_m: float = 0.0

    @property
    def rotation(self) -> np.ndarray:
        """World-from-tool rotation: tool x along the leg, jaws across it, leaned by the tilt."""
        return tool_rotation(self.yaw_rad - math.pi / 2, self.tilt_rad)


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


def leg_pose(cell: Cell) -> tuple[np.ndarray, np.ndarray]:
    """The leg body's world position (3,) and world-from-body rotation (3, 3), from ground truth."""
    body = mujoco.mj_name2id(cell.model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
    return np.asarray(cell.data.xpos[body], dtype=float).copy(), cell.data.xmat[body].reshape(3, 3).copy()


def leg_heading_rad(rotation: np.ndarray) -> float:
    """Yaw of the leg's long axis, ham toward trotter, about world z."""
    return math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))


def _shank_point_world(cell: Cell, fraction: float) -> tuple[np.ndarray, float]:
    """World position of the leg centreline at `fraction`, and the leg's heading."""
    leg = cell.config.leg
    assert leg is not None
    position, rotation = leg_pose(cell)
    point_body = leg_centreline(leg, np.array([fraction]))[0]
    return position + rotation @ point_body, leg_heading_rad(rotation)


class SelectShankGrasp:
    """Choose where on the shank to close, from the leg estimate, with the tool leaned by `tilt_rad`."""

    name = "select_shank_grasp"
    contract = Contract(
        inputs=(Port("leg_estimate", LegEstimate, "the leg's centreline, widths and heading, world frame"),),
        preconditions=(),
        outputs=(Port("shank_grasp", ShankGrasp, "tool target on the shank, world frame"),),
        success=(),
        failures=(),
    )

    def __init__(self, tilt_rad: float = 0.0) -> None:
        """A tilt other than zero is refused at run time on an arm whose tool cannot leave vertical."""
        self.tilt_rad = tilt_rad
        self.contract = Contract(
            inputs=self.contract.inputs,
            preconditions=(
                *self.contract.preconditions,
                Check("tool_tilts", "the arm can lean its tool, or no lean is asked for", self._tilt_available),
            ),
            outputs=self.contract.outputs,
            success=(),
            failures=(),
        )

    def _tilt_available(self, cell: Any, _args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
        available = self.tilt_rad == 0.0 or bool(cell.arm.tool_tilts)
        return CheckResult(
            available, float(available), f"tilt {math.degrees(self.tilt_rad):.0f} deg on {cell.arm.model.value}"
        )

    def execute(self, world: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:  # noqa: ANN401
        """Place the grasp on the estimated centreline at `SHANK_GRASP_FRACTION`, across its local direction."""
        cell: Cell = world
        estimate: LegEstimate = args["leg_estimate"]
        point = estimate.point_at(SHANK_GRASP_FRACTION)
        # The jaws align with the leg's overall heading, not the centreline's
        # local direction at the shank: on a bent leg the local direction
        # differs by a few degrees, and with it the SR-20iA lost 6 of 20 legs
        # (8 against 14, 2026-09-15) to slips and lifts that stalled.
        heading = estimate.heading_rad
        # A leaned tool swings the pads' downhill end toward the belt: at 15
        # degrees the jaw's pad ends dropped 20 mm and jammed on the belt on
        # every leg (2026-09-15). The tool point rises to keep the lowest pad
        # corner clear, which is part of what a tilt costs on a lying leg.
        tilt = abs(self.tilt_rad)
        lowest_corner = cell.gripper_geometry.pad_reach_m * math.cos(tilt) + PAD_SPAN_HALF_M * math.sin(tilt)
        point[2] = max(point[2], BELT_TOP_Z_M + lowest_corner + PAD_BELT_CLEARANCE_M)
        half_span = PAD_SPAN_HALF_M / estimate.length_m
        grasp = ShankGrasp(
            position_m=point,
            yaw_rad=heading,
            shank_width_m=estimate.width_at(SHANK_GRASP_FRACTION),
            widest_under_pads_m=estimate.widest_between(
                SHANK_GRASP_FRACTION - half_span, SHANK_GRASP_FRACTION + half_span
            ),
            fraction=SHANK_GRASP_FRACTION,
            tilt_rad=self.tilt_rad,
            belt_travel_m=estimate.belt_travel_m,
        )
        evidence = {"shank_width_m": grasp.shank_width_m, "widest_under_pads_m": grasp.widest_under_pads_m}
        return SUCCESS, {"shank_grasp": grasp}, evidence


UNREACHABLE = FailureMode("unreachable", "no joint solution for any approach height, the grasp, or the lift")
CLOSED_ON_NOTHING = FailureMode("closed_on_nothing", "the jaws closed past half the shank's width")
SLIPPED = FailureMode("slipped", "the jaws closed but the shank did not rise with the tool")
LIFT_NOT_ACHIEVED = FailureMode("lift_not_achieved", "the arm could not raise the tool under the part's load")


def _jaws_fit(cell: Any, args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    grasp: ShankGrasp = args["shank_grasp"]
    opening = cell.gripper_geometry.max_opening_m
    if len(cell.gripper.pad_sites) >= 3:
        # A centric gripper's fingers sit at equal angles round the tool axis.
        # Coming down on a shank that runs along the tool's x axis, the finger
        # nearest that axis is only half the open radius from it, so two of
        # three fingers land on any shank wider than half the opening (the
        # 3FG25 at 155 mm on a 78 to 110 mm shank, 2026-09-15). The room that
        # matters is that half opening, not the full one.
        opening = opening / 2
    spare = opening - grasp.widest_under_pads_m
    return CheckResult(
        spare >= 2 * OPEN_MARGIN_M,
        spare,
        f"fingers straddle the shank with at least {1000 * OPEN_MARGIN_M:.0f} mm each side",
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


def smoothstep(fraction: float) -> float:
    """0 to 1 with zero slope at both ends, so a move starts and stops without a velocity step.

    A move that stops dead leaves the servos still catching up: on a 0.2 m
    descent in 0.3 s ending at full speed the UR20's tool overshot 6 mm below
    the grasp point (2026-09-15).
    """
    fraction = min(1.0, max(0.0, fraction))
    return fraction * fraction * (3.0 - 2.0 * fraction)


def grasp_point_at(cell: Cell, grasp: ShankGrasp, t_s: float) -> np.ndarray:
    """Where the grasp point will be at simulation time `t_s`, assuming the belt keeps its speed."""
    travel = cell.belt_travel_m + cell.belt_speed_mps * (t_s - cell.time_s) - grasp.belt_travel_m
    return grasp.position_m + np.array([travel, 0.0, 0.0])


class AcquireShank:
    """Approach from above, close on the shank, and prove the grip with a 5 mm lift, tracking the belt."""

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

    def _approach(self, cell: Cell, grasp: ShankGrasp, evidence: dict[str, float]) -> tuple[np.ndarray, float] | None:
        """Joints above where the grasp point will be when the arm gets there, and the move time.

        The move time depends on the target and the target on the move time,
        because the belt carries the grasp point while the arm travels; two
        passes settle it to well under a tick at any belt speed the cell runs.
        """
        up_the_tool = -grasp.rotation[:, 2]
        for clearance in APPROACH_CLEARANCES_M:
            seconds = MIN_MOVE_S
            try:
                for _ in range(3):
                    above = grasp_point_at(cell, grasp, cell.time_s + seconds) + clearance * up_the_tool
                    q_above = solve_ik_rotation(cell.model, cell.data, above, grasp.rotation, arm=cell.arm)
                    seconds = self._move_seconds(cell, q_above)
            except UnreachableError:
                continue
            evidence["approach_clearance_m"] = clearance
            return q_above, seconds
        return None

    def execute(self, world: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:  # noqa: ANN401
        """Run the grasp and report what the jaws and the shank did."""
        cell: Cell = world
        grasp: ShankGrasp = args["shank_grasp"]
        evidence: dict[str, float] = {}
        approach = self._approach(cell, grasp, evidence)
        if approach is None:
            logger.info("%s: no approach height reachable above %s", self.name, np.round(grasp.position_m, 3).tolist())
            return UNREACHABLE.name, {}, evidence
        q_above, seconds = approach
        clearance = evidence["approach_clearance_m"]
        up_the_tool = -grasp.rotation[:, 2]

        cell.open_gripper(min(cell.gripper_geometry.max_opening_m, grasp.widest_under_pads_m + 2 * OPEN_MARGIN_M))
        cell.move_arm(q_above, seconds)
        descent_start_s = cell.time_s
        descend_s = max(MIN_DESCEND_S, clearance / DESCEND_MPS)

        def descend(t_s: float) -> tuple[np.ndarray, np.ndarray]:
            fraction = smoothstep((t_s - descent_start_s) / descend_s)
            return grasp_point_at(cell, grasp, t_s) + (1.0 - fraction) * clearance * up_the_tool, grasp.rotation

        def hold(t_s: float) -> tuple[np.ndarray, np.ndarray]:
            return grasp_point_at(cell, grasp, t_s), grasp.rotation

        try:
            cell.follow_tool(descend, descend_s)
            cell.follow_tool(hold, SETTLE_S)
            evidence["meet_error_m"] = float(
                np.linalg.norm(cell.tool_position_m - grasp_point_at(cell, grasp, cell.time_s))
            )
            evidence["joint_lag_rad"] = float(np.max(np.abs(cell.arm_target - cell.arm_qpos)))
            # The jaws close on a ramp rather than a step: a step drove the leg
            # 21 mm along its axis in the first 0.1 s of closing (2026-09-15).
            open_from = float(cell.gripper_opening_m)
            close_start_s = cell.time_s
            while cell.time_s < close_start_s + CLOSE_S - 1e-9:
                fraction = min(1.0, (cell.time_s - close_start_s + TOOL_TICK_S) / CLOSE_S)
                cell.open_gripper(
                    max(
                        cell.gripper_geometry.rest_gap_m,
                        open_from + fraction * (cell.gripper_geometry.rest_gap_m - open_from),
                    )
                )
                cell.follow_tool(hold, TOOL_TICK_S)
            cell.close_gripper()
            cell.follow_tool(hold, SETTLE_S)
            opening = float(cell.gripper_opening_m)
            evidence["opening_m"] = opening
            if opening < 0.5 * grasp.shank_width_m:
                return CLOSED_ON_NOTHING.name, {}, evidence

            tool, _ = tool_pose(cell.model, cell.data)
            point, _ = _shank_point_world(cell, grasp.fraction)
            proof = LiftProof(tool_z_m=float(tool[2]), part_z_m=float(point[2]))
            lift_start_s = cell.time_s

            def lift(t_s: float) -> tuple[np.ndarray, np.ndarray]:
                fraction = smoothstep((t_s - lift_start_s) / LIFT_S)
                return grasp_point_at(cell, grasp, t_s) + np.array([0.0, 0.0, fraction * LIFT_CHECK_M]), grasp.rotation

            cell.follow_tool(lift, LIFT_S + SETTLE_S)
        except UnreachableError as error:
            logger.info("%s: %s", self.name, error)
            return UNREACHABLE.name, {}, evidence

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
