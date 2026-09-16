"""Approach B: turn a held piece on the belt until its datum point sits on the datum plane, square, and let go.

The piece is already gripped and lifted a few millimetres (`AcquireShank`).
Its bulk still rests on the belt, so the arm never carries the piece's weight:
it swings the gripped section, the rest pivots on its own contact patch, and
the whole piece keeps riding the belt underneath. Then the gripped section is
set back down, the jaws open, and the tool lifts clear before the piece
reaches whatever stands downstream: the hold-down belt on the leg cell, the
infeed fixture on the loin cell.

The path is planned on the piece, not on the tool. While the grip holds, the
tool sits at a fixed pose in the piece's frame, captured from the estimate and
the measured tool pose when the skill starts; the piece's pose is interpolated
from where the estimate says it is to where the cell needs it, and the tool
pose follows by that fixed offset. Everything is expressed relative to the
belt surface and the belt's travel is added at each tick, so a change of belt
speed mid-turn is tracked rather than planned around.

What "aligned" means is the one thing that differs between cells, and it is
the skill's `AlignmentTarget`: which point on the piece must reach which plane
at which heading, plus the true piece for scoring. The leg's is `SawTarget`,
the hock on the blade plane with the trotter straight out over the edge; the
loin's is in `loin_infeed.py`. The manoeuvre is the same for both (Section
14.3 of the plan).

How far the piece's true pose falls short of the planned one when the turn
ends is reported as evidence: from ground truth it is slip in the jaws and on
the belt; from the camera it also carries the estimate's error. It is named as
the failure when the piece ends out of tolerance because of it.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from applications.pork_leg_alignment.sim.cell import Cell, ToolPath
from applications.pork_leg_alignment.sim.product import HOCK_FRACTION, product_body_ids
from applications.pork_leg_alignment.skills.leg_estimate import LegEstimate, estimate_from_ground_truth
from applications.pork_leg_alignment.skills.shank_grasp import (
    OPEN_MARGIN_M,
    LiftProof,
    ShankGrasp,
    _gripping_the_shank,
    leg_heading_rad,
    leg_pose,
    smoothstep,
)
from robotics.core.skill_library import SUCCESS, Check, CheckResult, Contract, FailureMode, Port
from robotics.hardware.ik import UnreachableError

logger = logging.getLogger(__name__)

# The leg's target heading: trotter pointing straight out over the open edge, which is world -y.
TARGET_HEADING_RAD = -math.pi / 2
# How high the gripped section is carried while turning, above where the jaws
# closed on it. Enough that a leg's hock clears the belt through the turn; the
# ham, 175 mm tall, stays down.
TURN_LIFT_M = 0.020
LIFT_S = 0.3
# Tool speed and turn rate through the turn. Assumed: a 20 kg-class arm swinging
# a 15 kg leg on the belt; neither vendor rates a payload move this way.
# The turn is bounded by speed and by angular acceleration. A turn planned on
# rate alone made short turns violent: a 53 degree turn in 0.44 s peaks at
# 27 rad/s^2 and the leg slid 15 mm in the jaws, a 126 degree turn 29 mm
# (2026-09-15). At 3 rad/s^2 the leg's inertia about the grasp (about
# 1.5 kg m^2) asks the pads for under 5 N m, but a 180 degree turn then takes
# 2.5 s of belt travel and a 35 degree turn 1.1 s, which put the SR-20iA's
# set-down beyond its reach on 12 of 20 square arrivals (2026-09-15). The
# square set had run at up to 10 rad/s^2 before the bound existed (60 deg/s,
# 35 degrees in 0.61 s) with one slip in 20, so 10 is the default and the
# bound is a skill parameter, `turn_acceleration_radps2`. All assumed.
TOOL_SPEED_MPS = 0.8
TURN_RATE_RADPS = math.radians(120.0)
TURN_ACCELERATION_RADPS2 = 10.0
MIN_TURN_S = 0.4
LOWER_S = 0.25
OPEN_S = 0.3
RETREAT_M = 0.15
RETREAT_S = 0.2
# After rising clear of the piece the tool stops following the belt and backs
# upstream, out of the way of the piece and the hold-down's lead-in: following
# the belt for the whole retreat carried the open jaws 0.18 m downstream into
# the ramp on every leg (2026-09-15).
CLEAR_BACK_M = 0.25
CLEAR_S = 0.3
# After the turn a fresh estimate, when the task graph supplies one, triggers a
# correcting turn if the datum point or heading is still off by more than
# this; at most `MAX_CORRECTIONS` of them.
CORRECT_ABOVE_DATUM_M = 0.003
CORRECT_ABOVE_HEADING_RAD = math.radians(1.0)
MAX_CORRECTIONS = 2
# What the skill promises at release, the same numbers the judge is scored
# against (experiments/2026-09-15-alignment-approaches.md). Both assumed; no
# customer or vendor has given a tolerance for either cell.
DATUM_TOLERANCE_M = 0.010
HEADING_TOLERANCE_RAD = math.radians(5.0)
# Below this the piece has left the belt surface.
ON_BELT_TOLERANCE_M = 0.03
BELT_TOP_Z_M = 0.90


class AlignmentTarget(Protocol):
    """What "aligned" means for one product in one cell.

    The skill plans on an estimate and scores on the truth, so the target
    answers both: which point on the piece must reach the datum plane, the
    heading the piece must end at, where the plane is in this cell, how an
    offset from it is signed, and the true piece for scoring.
    """

    name: str

    def datum_point(self, estimate: LegEstimate) -> np.ndarray:
        """The point on the piece that must sit on the datum plane, world frame at the estimate's encoder reading, (3,)."""
        ...

    def heading_rad(self, cell: Cell, estimate: LegEstimate) -> float:
        """The heading the piece must end at, for this piece in this cell."""
        ...

    def datum_y_m(self, cell: Cell) -> float | None:
        """World y of the datum plane, or None when the cell has none to align to."""
        ...

    def datum_offset_m(self, cell: Cell, point_y_m: float) -> float:
        """A point's offset from the datum plane, positive inboard, on the belt; negative past the plane."""
        ...

    def ground_truth(self, cell: Cell) -> LegEstimate:
        """The true piece now, for scoring only."""
        ...


class SawTarget:
    """The leg's alignment: the hock on the blade plane, the trotter straight out over the open edge."""

    name = "saw"

    def datum_point(self, estimate: LegEstimate) -> np.ndarray:
        """The hock joint."""
        return estimate.point_at(HOCK_FRACTION)

    def heading_rad(self, cell: Cell, estimate: LegEstimate) -> float:
        """Square to the blade, whatever the leg."""
        del cell, estimate
        return TARGET_HEADING_RAD

    def datum_y_m(self, cell: Cell) -> float | None:
        """The blade plane, when the cell has a saw."""
        return cell.saw.blade_y_m if cell.saw is not None else None

    def datum_offset_m(self, cell: Cell, point_y_m: float) -> float:
        """Hock y minus the blade plane y: the blade stands at -y, so positive is inboard."""
        datum_y = self.datum_y_m(cell)
        if datum_y is None:
            raise ValueError("the cell has no saw; there is no blade plane to measure from")
        return point_y_m - datum_y

    def ground_truth(self, cell: Cell) -> LegEstimate:
        """The simulator's own leg."""
        return estimate_from_ground_truth(cell)


SAW_TARGET = SawTarget()


@dataclass(frozen=True)
class _TurnPlan:
    piece_position: np.ndarray
    piece_rotation: np.ndarray
    tool_in_piece: np.ndarray
    tool_rotation_in_piece: np.ndarray
    target_position: np.ndarray
    target_rotation: np.ndarray
    target_heading_rad: float
    turn_rad: float
    turn_s: float

    def tool_for_piece(self, position: np.ndarray, rotation: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return position + rotation @ self.tool_in_piece, rotation @ self.tool_rotation_in_piece


@dataclass(frozen=True)
class Alignment:
    """Where the piece ended relative to the cell's datum, world frame.

    Attributes:
        datum_offset_m: The datum point's offset from the datum plane; positive
            is inboard, on the belt, negative is past the plane.
        heading_error_rad: Piece heading minus the target heading, wrapped.
        released_at_x_m: Downstream-most point of the piece when the jaws opened.
        cycle_s: From the start of the turn to the tool clear of the piece.
    """

    datum_offset_m: float
    heading_error_rad: float
    released_at_x_m: float
    cycle_s: float


def _rot_z(angle_rad: float) -> np.ndarray:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _wrap(angle_rad: float) -> float:
    return math.remainder(angle_rad, 2.0 * math.pi)


def _product_extent_x(cell: Cell) -> float:
    """Downstream-most point of the piece's centreline, world x."""
    return float(cell.product_centreline_world(np.linspace(0.0, 1.0, 73))[:, 0].max())


def measure_alignment(cell: Cell, target: AlignmentTarget, released_at_x_m: float, cycle_s: float) -> Alignment:
    """Score the piece's pose against the cell's datum, from ground truth."""
    truth = target.ground_truth(cell)
    return Alignment(
        datum_offset_m=target.datum_offset_m(cell, float(target.datum_point(truth)[1])),
        heading_error_rad=_wrap(truth.heading_rad - target.heading_rad(cell, truth)),
        released_at_x_m=released_at_x_m,
        cycle_s=cycle_s,
    )


def _aligned(cell: Any, args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    del cell
    alignment: Alignment = args["alignment"]
    within = (
        abs(alignment.datum_offset_m) <= DATUM_TOLERANCE_M and abs(alignment.heading_error_rad) <= HEADING_TOLERANCE_RAD
    )
    return CheckResult(
        within,
        alignment.datum_offset_m,
        f"datum point within {1000 * DATUM_TOLERANCE_M:.0f} mm of the datum plane and heading within "
        f"{math.degrees(HEADING_TOLERANCE_RAD):.0f} deg of the target",
    )


def _released_in_time(cell: Any, args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    alignment: Alignment = args["alignment"]
    deadline = cell.release_before_x_m
    if deadline is None:
        return CheckResult(True, alignment.released_at_x_m, "nothing downstream to be late for")
    return CheckResult(
        alignment.released_at_x_m < deadline,
        alignment.released_at_x_m,
        f"jaws open before any part of the piece reaches x = {deadline:.2f} m",
    )


UNREACHABLE = FailureMode("unreachable", "no joint solution somewhere on the turn, the set-down or the retreat")
SLIPPED = FailureMode("slipped", "the piece lagged the tool by more than the tolerance during the turn")
MISALIGNED = FailureMode("misaligned", "the piece was set down outside the datum or heading tolerance")
RELEASED_LATE = FailureMode(
    "released_late", "the piece reached the hold-down ramp or the fixture before the jaws opened"
)
DROPPED = FailureMode("dropped", "the piece was not on the belt after release")


class RotateOnBelt:
    """Swing the held section until the datum point is on the datum plane and the piece square, then release.

    `carry_lift_m` is how high the gripped section is carried while the piece
    moves. Low, the bulk stays on the belt and pivots (approach B); high
    enough, the whole piece leaves the belt and the arm carries its weight
    (approach A, in `PickAndPlace`). The path is the same either way.

    `turn_acceleration_radps2` caps the peak angular acceleration of the turn,
    which sets how long a turn takes and so how far down the belt the piece is
    set down. `target` says what aligned means; the leg's saw by default.
    """

    name = "rotate_on_belt"
    carry_lift_m = TURN_LIFT_M
    contract = Contract(
        inputs=(
            Port("leg_estimate", LegEstimate, "the piece the grasp was planned on"),
            Port("shank_grasp", ShankGrasp, "the grasp the jaws closed on"),
            Port("lift_proof", LiftProof, "tool and part heights when the jaws closed, to set the part back down"),
        ),
        preconditions=(Check("grip_opening_m", "the jaws are still closed on the part", _gripping_the_shank),),
        outputs=(Port("alignment", Alignment, "where the piece ended relative to the datum"),),
        success=(
            Check("datum_offset_m", "the piece is aligned to the datum within tolerance", _aligned),
            Check("released_at_x_m", "the jaws opened before the hold-down ramp or the fixture", _released_in_time),
        ),
        failures=(UNREACHABLE, SLIPPED, MISALIGNED, RELEASED_LATE, DROPPED),
    )

    def __init__(
        self, turn_acceleration_radps2: float = TURN_ACCELERATION_RADPS2, target: AlignmentTarget = SAW_TARGET
    ) -> None:
        """Build the skill with its turn acceleration bound and its alignment target.

        The datum precondition is bound to the target, so it is added per
        instance on top of the class's contract; a subclass's extra failure
        modes come through `type(self).contract`.
        """
        self.turn_acceleration_radps2 = turn_acceleration_radps2
        self.target = target
        base = type(self).contract
        self.contract = Contract(
            inputs=base.inputs,
            preconditions=(
                Check("datum_present", f"the cell has the {target.name} datum to align to", self._has_datum),
                *base.preconditions,
            ),
            outputs=base.outputs,
            success=base.success,
            failures=base.failures,
        )

    def _has_datum(self, cell: Any, _args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
        present = self.target.datum_y_m(cell) is not None
        return CheckResult(present, float(present), f"the cell has the {self.target.name} datum")

    def _after_lift(self, cell: Cell, evidence: dict[str, float]) -> str | None:
        """A failure to return once the gripped section is at carry height, or None to carry on.

        Records whether the piece still touches the belt at carry height: on the
        belt is what this skill intends, and the number says whether the jaws'
        hold on the piece's pitch let its bulk stay down.
        """
        evidence["airborne"] = 0.0 if product_touches_belt(cell) else 1.0
        return None

    def execute(self, world: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:  # noqa: ANN401
        """Turn, set down, open and retreat, reporting where the piece ended."""
        cell: Cell = world
        estimate: LegEstimate = args["leg_estimate"]
        grasp: ShankGrasp = args["shank_grasp"]
        proof: LiftProof = args["lift_proof"]
        evidence: dict[str, float] = {}
        started_s = cell.time_s
        travel_at_start = cell.belt_travel_m
        datum_y = self.target.datum_y_m(cell)
        assert datum_y is not None  # the datum precondition ran

        re_estimate: Callable[[], LegEstimate | None] | None = args.get("re_estimate")

        def belt_shift(t_s: float) -> np.ndarray:
            travel = cell.belt_travel_m + cell.belt_speed_mps * (t_s - cell.time_s) - travel_at_start
            return np.array([travel, 0.0, 0.0])

        def plan(source: LegEstimate, carry_z: float) -> _TurnPlan:
            """The piece's frame now, the tool's pose in it, and the target pose, all at height `carry_z`.

            The frame's origin is the estimated centre of gravity, x along the
            estimated heading. The target keeps the centre of gravity where it
            is along the belt, puts the datum point on the datum plane and
            turns the heading to the target's.
            """
            # Positions are kept in the frame the belt was in when the skill
            # started, so every path can add the travel since; an estimate
            # taken later is world-now and is brought back by that travel.
            carried = np.array([cell.belt_travel_m - source.belt_travel_m, 0.0, 0.0])
            piece_world = source.centre_of_gravity_m + carried
            piece_world[2] = carry_z
            piece_rotation = _rot_z(source.heading_rad)
            datum_in_piece = piece_rotation.T @ (self.target.datum_point(source) + carried - piece_world)
            tool_in_piece = piece_rotation.T @ (cell.tool_position_m - piece_world)
            tool_rotation_in_piece = piece_rotation.T @ cell.tool_rotation
            piece_position = piece_world - belt_shift(cell.time_s)
            target_heading = self.target.heading_rad(cell, source)
            turn_rad = _wrap(target_heading - source.heading_rad)
            target_rotation = _rot_z(turn_rad) @ piece_rotation
            target_position = np.array(
                [float(piece_position[0]), datum_y - float((target_rotation @ datum_in_piece)[1]), carry_z]
            )
            travel_m = float(
                np.linalg.norm((target_position - piece_position) + (target_rotation - piece_rotation) @ tool_in_piece)
            )
            # A smoothstep of angle theta over T peaks at 6 theta / T^2.
            turn_s = max(
                MIN_TURN_S,
                abs(turn_rad) / TURN_RATE_RADPS,
                math.sqrt(6.0 * abs(turn_rad) / self.turn_acceleration_radps2),
                travel_m / TOOL_SPEED_MPS,
            )
            return _TurnPlan(
                piece_position,
                piece_rotation,
                tool_in_piece,
                tool_rotation_in_piece,
                target_position,
                target_rotation,
                target_heading,
                turn_rad,
                turn_s,
            )

        # The piece's pose was captured with the gripped section already raised
        # by the proof lift; the turn carries it `carry_lift_m` above where the
        # jaws closed, and the set-down returns it exactly there, so the tool
        # never presses the part into the belt.
        rise_so_far = float(cell.tool_position_m[2]) - proof.tool_z_m
        extra_lift = self.carry_lift_m - rise_so_far
        first = plan(estimate, float(estimate.centre_of_gravity_m[2]))
        evidence["turn_rad"] = first.turn_rad
        evidence["shift_m"] = float(np.linalg.norm(first.target_position[:2] - first.piece_position[:2]))
        lift_start_s = cell.time_s

        def lift(t_s: float) -> tuple[np.ndarray, np.ndarray]:
            rise = smoothstep((t_s - lift_start_s) / LIFT_S) * extra_lift
            return first.tool_for_piece(
                first.piece_position + belt_shift(t_s) + np.array([0.0, 0.0, rise]), first.piece_rotation
            )

        def turn_path(current: _TurnPlan, start_s: float) -> ToolPath:
            def turn(t_s: float) -> tuple[np.ndarray, np.ndarray]:
                fraction = smoothstep((t_s - start_s) / current.turn_s)
                rotation = _rot_z(fraction * current.turn_rad) @ current.piece_rotation
                position = (
                    current.piece_position
                    + fraction * (current.target_position - current.piece_position)
                    + belt_shift(t_s)
                )
                return current.tool_for_piece(position, rotation)

            return turn

        def lower(t_s: float) -> tuple[np.ndarray, np.ndarray]:
            fraction = smoothstep((t_s - lower_start_s) / LOWER_S)
            position = current.target_position + belt_shift(t_s)
            position[2] -= fraction * self.carry_lift_m
            return current.tool_for_piece(position, current.target_rotation)

        def retreat(t_s: float) -> tuple[np.ndarray, np.ndarray]:
            fraction = smoothstep((t_s - retreat_start_s) / RETREAT_S)
            position = current.target_position + belt_shift(t_s)
            position[2] -= self.carry_lift_m
            tool_position, tool_rotation = current.tool_for_piece(position, current.target_rotation)
            return tool_position + np.array([0.0, 0.0, fraction * RETREAT_M]), tool_rotation

        def clear(t_s: float) -> tuple[np.ndarray, np.ndarray]:
            fraction = smoothstep((t_s - clear_start_s) / CLEAR_S)
            return clear_from + np.array([-fraction * CLEAR_BACK_M, 0.0, 0.0]), clear_rotation

        try:
            cell.follow_tool(lift, LIFT_S)
            lifted = self._after_lift(cell, evidence)
            if lifted is not None:
                cell.open_gripper(cell.gripper_geometry.max_opening_m)
                return lifted, {}, evidence
            # After the lift the piece sits at carry height; plan the turn there
            # from the estimate, then check it against a fresh estimate and
            # correct, up to `MAX_CORRECTIONS` times: on a turn of more than
            # about 90 degrees the leg lags the tool by 3 to 5 degrees in the
            # jaws (2026-09-15), and a second, small turn takes that out.
            carry_z = float(first.piece_position[2]) + extra_lift
            current = plan(estimate, carry_z)
            corrections = 0
            while True:
                turn_start_s = cell.time_s
                cell.follow_tool(turn_path(current, turn_start_s), current.turn_s)
                if corrections == 0:
                    # Slip: the piece's true centre of gravity and heading against the plan.
                    truth = cell.ground_truth()
                    assert truth.centre_of_mass_m is not None
                    _, rotation = leg_pose(cell)
                    planned = current.target_position + belt_shift(cell.time_s)
                    evidence["slip_m"] = float(np.linalg.norm(truth.centre_of_mass_m[:2] - planned[:2]))
                    evidence["slip_rad"] = _wrap(leg_heading_rad(rotation) - current.target_heading_rad)
                if re_estimate is None or corrections >= MAX_CORRECTIONS:
                    break
                fresh = re_estimate()
                if fresh is None:
                    break
                carried_since = np.array([cell.belt_travel_m - fresh.belt_travel_m, 0.0, 0.0])
                datum_error = self.target.datum_offset_m(
                    cell, float((self.target.datum_point(fresh) + carried_since)[1])
                )
                heading_error = _wrap(fresh.heading_rad - self.target.heading_rad(cell, fresh))
                if abs(datum_error) <= CORRECT_ABOVE_DATUM_M and abs(heading_error) <= CORRECT_ABOVE_HEADING_RAD:
                    break
                current = plan(fresh, carry_z)
                corrections += 1
            evidence["corrections"] = float(corrections)
            lower_start_s = cell.time_s
            cell.follow_tool(lower, LOWER_S)
            cell.open_gripper(min(cell.gripper_geometry.max_opening_m, grasp.widest_under_pads_m + 2 * OPEN_MARGIN_M))
            released_at_x = _product_extent_x(cell)
            retreat_start_s = cell.time_s
            cell.follow_tool(retreat, OPEN_S + RETREAT_S)
            clear_from, clear_rotation = cell.tool_position_m.copy(), cell.tool_rotation.copy()
            clear_start_s = cell.time_s
            cell.follow_tool(clear, CLEAR_S)
        except UnreachableError as error:
            logger.info("%s: %s", self.name, error)
            cell.open_gripper(cell.gripper_geometry.max_opening_m)
            return UNREACHABLE.name, {}, evidence

        alignment = measure_alignment(cell, self.target, released_at_x, cell.time_s - started_s)
        evidence["datum_offset_m"] = alignment.datum_offset_m
        evidence["heading_error_rad"] = alignment.heading_error_rad
        evidence["released_at_x_m"] = alignment.released_at_x_m
        evidence["cycle_s"] = alignment.cycle_s
        piece_height = float(leg_pose(cell)[0][2]) - BELT_TOP_Z_M
        evidence["piece_height_m"] = piece_height
        if abs(piece_height) > ON_BELT_TOLERANCE_M:
            return DROPPED.name, {}, evidence
        deadline = cell.release_before_x_m
        if deadline is not None and released_at_x >= deadline:
            return RELEASED_LATE.name, {}, evidence
        if (
            abs(alignment.datum_offset_m) > DATUM_TOLERANCE_M
            or abs(alignment.heading_error_rad) > HEADING_TOLERANCE_RAD
        ):
            slipped = (
                evidence["slip_m"] > DATUM_TOLERANCE_M / 2 or abs(evidence["slip_rad"]) > HEADING_TOLERANCE_RAD / 2
            )
            return (SLIPPED if slipped else MISALIGNED).name, {}, evidence
        return SUCCESS, {"alignment": alignment}, evidence


# Approach A carries the whole piece. The gripped section rises enough that a
# piece the jaws hold rigidly clears the belt by its full drop; a grip that
# yields in pitch leaves the bulk dragging, which is the failure the airborne
# check names.
CARRY_LIFT_M = 0.10
NOT_LIFTED = FailureMode(
    "not_lifted", "the piece still touched the belt at carry height: the grip did not hold its pitch"
)
GRAVITY_MPS2 = 9.81


class PickAndPlace(RotateOnBelt):
    """Approach A: lift the piece clear of the belt, carry it to the aligned pose, set it down, release.

    Same target and same path as the turn on the belt, with the gripped
    section carried high enough that the bulk leaves the belt, so the arm
    bears the piece's weight and the moment of its centre of gravity about
    the tool. Both are reported as evidence against each arm's rating: the
    load on the flange, the moment about the jaw line, and the piece's inertia
    about the tool's vertical axis, which is what a SCARA's wrist carries when
    it turns the piece.
    """

    name = "pick_and_place"
    carry_lift_m = CARRY_LIFT_M
    contract = Contract(
        inputs=RotateOnBelt.contract.inputs,
        preconditions=RotateOnBelt.contract.preconditions,
        outputs=RotateOnBelt.contract.outputs,
        success=RotateOnBelt.contract.success,
        failures=(*RotateOnBelt.contract.failures, NOT_LIFTED),
    )

    def _after_lift(self, cell: Cell, evidence: dict[str, float]) -> str | None:
        """Report the load the arm carries and refuse to carry a piece that is still on the belt."""
        truth = cell.ground_truth()
        assert truth.centre_of_mass_m is not None
        bodies = product_body_ids(cell.model)
        mass = float(sum(cell.model.body_mass[b] for b in bodies))
        tool = cell.tool_position_m
        lever = truth.centre_of_mass_m[:2] - tool[:2]
        # Inertia about the tool's vertical axis: each body's own zz inertia
        # plus its mass at its distance from the tool axis.
        inertia = 0.0
        for b in bodies:
            offset = np.asarray(cell.data.xipos[b])[:2] - tool[:2]
            inertia += float(cell.model.body_inertia[b][2]) + float(cell.model.body_mass[b]) * float(offset @ offset)
        evidence["flange_load_n"] = mass * GRAVITY_MPS2
        evidence["moment_about_tool_nm"] = mass * GRAVITY_MPS2 * float(np.linalg.norm(lever))
        evidence["inertia_about_tool_kgm2"] = inertia
        touching = product_touches_belt(cell)
        evidence["airborne"] = 0.0 if touching else 1.0
        return NOT_LIFTED.name if touching else None


def product_touches_belt(cell: Cell) -> bool:
    """Whether any body of the product is in contact with the belt surface now."""
    belt = cell.model.geom("belt_surface").id
    bodies = set(product_body_ids(cell.model))
    for i in range(cell.data.ncon):
        contact = cell.data.contact[i]
        geoms = (int(contact.geom1), int(contact.geom2))
        touching = {int(cell.model.geom_bodyid[geoms[0]]), int(cell.model.geom_bodyid[geoms[1]])}
        if belt in geoms and touching & bodies:
            return True
    return False
