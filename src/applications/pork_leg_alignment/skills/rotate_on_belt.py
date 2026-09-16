"""Approach B: turn a held leg on the belt until its hock sits on the blade plane, square, and let go.

The leg is already gripped by the shank and lifted a few millimetres
(`AcquireShank`). Its ham still rests on the belt, so the arm never carries the
leg's weight: it swings the shank, the ham pivots on its own contact patch, and
the whole piece keeps riding the belt underneath. Then the shank is set back
down, the jaws open, and the tool lifts clear before the leg reaches the
hold-down belt.

The path is planned on the leg, not on the tool. While the grip holds, the tool
sits at a fixed pose in the leg's frame, captured from the leg estimate and the
measured tool pose when the skill starts; the leg's pose is interpolated from
where the estimate says it is to where the saw needs it (`TARGET_HEADING_RAD`,
hock on the blade plane, centre of gravity kept where it is along the belt),
and the tool pose follows by that fixed offset. The estimate may come from
ground truth or from the camera; the scoring at the end is always ground truth.
Everything is expressed relative to the belt surface and the belt's travel is
added at each tick, so a change of belt speed mid-turn is tracked rather than
planned around.

How far the leg's true pose falls short of the planned one when the turn ends
is reported as evidence: from ground truth it is slip in the jaws and on the
belt; from the camera it also carries the estimate's error. It is named as the
failure when the leg ends out of tolerance because of it.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from applications.pork_leg_alignment.sim.cell import Cell, ToolPath
from applications.pork_leg_alignment.sim.product import HOCK_FRACTION, leg_centreline
from applications.pork_leg_alignment.skills.leg_estimate import LegEstimate
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

# Trotter pointing straight out over the open edge, which is world -y.
TARGET_HEADING_RAD = -math.pi / 2
# How high the shank is carried while turning, above where the jaws closed on
# it. Enough that the hock's underside clears the belt through the turn; the
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
# After rising clear of the shank the tool stops following the belt and backs
# upstream, out of the way of the leg and the hold-down's lead-in: following
# the belt for the whole retreat carried the open jaws 0.18 m downstream into
# the ramp on every leg (2026-09-15).
CLEAR_BACK_M = 0.25
CLEAR_S = 0.3
# After the turn a fresh estimate, when the task graph supplies one, triggers a
# correcting turn if the hock or heading is still off by more than this; at
# most `MAX_CORRECTIONS` of them.
CORRECT_ABOVE_HOCK_M = 0.003
CORRECT_ABOVE_HEADING_RAD = math.radians(1.0)
MAX_CORRECTIONS = 2
# What the skill promises at release, the same numbers the saw is scored
# against (experiments/2026-09-15-alignment-approaches.md). Both assumed; the
# customer has not given a tolerance.
HOCK_TOLERANCE_M = 0.010
HEADING_TOLERANCE_RAD = math.radians(5.0)
# Below this the leg has left the belt surface.
ON_BELT_TOLERANCE_M = 0.03
BELT_TOP_Z_M = 0.90


@dataclass(frozen=True)
class _TurnPlan:
    leg_position: np.ndarray
    leg_rotation: np.ndarray
    tool_in_leg: np.ndarray
    tool_rotation_in_leg: np.ndarray
    target_position: np.ndarray
    target_rotation: np.ndarray
    turn_rad: float
    turn_s: float

    def tool_for_leg(self, position: np.ndarray, rotation: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return position + rotation @ self.tool_in_leg, rotation @ self.tool_rotation_in_leg


@dataclass(frozen=True)
class Alignment:
    """Where the leg ended relative to the saw, world frame.

    Attributes:
        hock_offset_m: Hock y minus the blade plane y; positive is inboard, on
            the belt, negative is out over the edge.
        heading_error_rad: Leg heading minus the target heading, wrapped.
        released_at_x_m: Downstream-most point of the leg when the jaws opened.
        cycle_s: From the start of the turn to the tool clear of the leg.
    """

    hock_offset_m: float
    heading_error_rad: float
    released_at_x_m: float
    cycle_s: float


def _rot_z(angle_rad: float) -> np.ndarray:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _wrap(angle_rad: float) -> float:
    return math.remainder(angle_rad, 2.0 * math.pi)


def _blade_plane_y(cell: Cell) -> float:
    if cell.saw is None:
        raise ValueError("the cell has no saw; there is no blade plane to align the hock to")
    return cell.saw.blade_y_m


def _leg_extent_x(cell: Cell) -> float:
    """Downstream-most point of the leg's centreline, world x."""
    leg = cell.config.leg
    assert leg is not None
    position, rotation = leg_pose(cell)
    points = position + leg_centreline(leg, np.linspace(0.0, 1.0, 73)) @ rotation.T
    return float(points[:, 0].max())


def hock_world(cell: Cell) -> np.ndarray:
    """The hock joint's world position from ground truth, (3,)."""
    leg = cell.config.leg
    assert leg is not None
    position, rotation = leg_pose(cell)
    return position + rotation @ leg_centreline(leg, np.array([HOCK_FRACTION]))[0]


def measure_alignment(cell: Cell, released_at_x_m: float, cycle_s: float) -> Alignment:
    """Score the leg's pose against the saw, from ground truth."""
    _, rotation = leg_pose(cell)
    return Alignment(
        hock_offset_m=float(hock_world(cell)[1]) - _blade_plane_y(cell),
        heading_error_rad=_wrap(leg_heading_rad(rotation) - TARGET_HEADING_RAD),
        released_at_x_m=released_at_x_m,
        cycle_s=cycle_s,
    )


def _has_saw(cell: Any, _args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    return CheckResult(cell.saw is not None, float(cell.saw is not None), "the cell has a saw to align to")


def _aligned(cell: Any, args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    alignment: Alignment = args["alignment"]
    within = (
        abs(alignment.hock_offset_m) <= HOCK_TOLERANCE_M and abs(alignment.heading_error_rad) <= HEADING_TOLERANCE_RAD
    )
    return CheckResult(
        within,
        alignment.hock_offset_m,
        f"hock within {1000 * HOCK_TOLERANCE_M:.0f} mm of the blade plane and heading within "
        f"{math.degrees(HEADING_TOLERANCE_RAD):.0f} deg of square",
    )


def _released_in_time(cell: Any, args: Mapping[str, Any]) -> CheckResult:  # noqa: ANN401
    alignment: Alignment = args["alignment"]
    if cell.hold_down is None:
        return CheckResult(True, alignment.released_at_x_m, "no hold-down belt to be late for")
    entry = cell.hold_down.config.entry_x_m
    return CheckResult(
        alignment.released_at_x_m < entry,
        alignment.released_at_x_m,
        f"jaws open before any part of the leg reaches the hold-down ramp at x = {entry:.2f} m",
    )


UNREACHABLE = FailureMode("unreachable", "no joint solution somewhere on the turn, the set-down or the retreat")
SLIPPED = FailureMode("slipped", "the leg lagged the tool by more than the tolerance during the turn")
MISALIGNED = FailureMode("misaligned", "the leg was set down outside the hock or heading tolerance")
RELEASED_LATE = FailureMode("released_late", "the leg reached the hold-down ramp before the jaws opened")
DROPPED = FailureMode("dropped", "the leg was not on the belt after release")


class RotateOnBelt:
    """Swing the held shank until the hock is on the blade plane and the leg square, then release.

    `carry_lift_m` is how high the shank is carried while the leg moves. Low,
    the ham stays on the belt and pivots (approach B); high enough, the whole
    leg leaves the belt and the arm carries its weight (approach A, in
    `PickAndPlace`). The path is the same either way.

    `turn_acceleration_radps2` caps the peak angular acceleration of the turn,
    which sets how long a turn takes and so how far down the belt the leg is
    set down.
    """

    name = "rotate_on_belt"
    carry_lift_m = TURN_LIFT_M

    def __init__(self, turn_acceleration_radps2: float = TURN_ACCELERATION_RADPS2) -> None:
        """Build the skill with its turn acceleration bound."""
        self.turn_acceleration_radps2 = turn_acceleration_radps2

    contract = Contract(
        inputs=(
            Port("leg_estimate", LegEstimate, "the leg the grasp was planned on"),
            Port("shank_grasp", ShankGrasp, "the grasp the jaws closed on"),
            Port("lift_proof", LiftProof, "tool and shank heights when the jaws closed, to set the shank back down"),
        ),
        preconditions=(
            Check("saw_present", "the cell has a saw", _has_saw),
            Check("grip_opening_m", "the jaws are still closed on the shank", _gripping_the_shank),
        ),
        outputs=(Port("alignment", Alignment, "where the leg ended relative to the saw"),),
        success=(
            Check("hock_offset_m", "the leg is aligned to the saw within tolerance", _aligned),
            Check("released_at_x_m", "the jaws opened before the hold-down ramp", _released_in_time),
        ),
        failures=(UNREACHABLE, SLIPPED, MISALIGNED, RELEASED_LATE, DROPPED),
    )

    def _after_lift(self, cell: Cell, evidence: dict[str, float]) -> str | None:
        """A failure to return once the shank is at carry height, or None to carry on.

        Records whether the leg still touches the belt at carry height: on the
        belt is what this skill intends, and the number says whether the jaws'
        hold on the leg's pitch let the ham stay down.
        """
        evidence["airborne"] = 0.0 if leg_touches_belt(cell) else 1.0
        return None

    def execute(self, world: Any, args: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, float]]:  # noqa: ANN401
        """Turn, set down, open and retreat, reporting where the leg ended."""
        cell: Cell = world
        estimate: LegEstimate = args["leg_estimate"]
        grasp: ShankGrasp = args["shank_grasp"]
        proof: LiftProof = args["lift_proof"]
        evidence: dict[str, float] = {}
        started_s = cell.time_s
        travel_at_start = cell.belt_travel_m

        re_estimate: Callable[[], LegEstimate | None] | None = args.get("re_estimate")

        def belt_shift(t_s: float) -> np.ndarray:
            travel = cell.belt_travel_m + cell.belt_speed_mps * (t_s - cell.time_s) - travel_at_start
            return np.array([travel, 0.0, 0.0])

        def plan(source: LegEstimate, carry_z: float) -> _TurnPlan:
            """The leg's frame now, the tool's pose in it, and the target pose, all at height `carry_z`.

            The frame's origin is the estimated centre of gravity, x along the
            estimated heading. The target keeps the centre of gravity where it
            is along the belt, puts the hock on the blade plane and squares the
            heading.
            """
            # Positions are kept in the frame the belt was in when the skill
            # started, so every path can add the travel since; an estimate
            # taken later is world-now and is brought back by that travel.
            carried = np.array([cell.belt_travel_m - source.belt_travel_m, 0.0, 0.0])
            leg_world = source.centre_of_gravity_m + carried
            leg_world[2] = carry_z
            leg_rotation = _rot_z(source.heading_rad)
            hock_in_leg = leg_rotation.T @ (source.point_at(HOCK_FRACTION) + carried - leg_world)
            tool_in_leg = leg_rotation.T @ (cell.tool_position_m - leg_world)
            tool_rotation_in_leg = leg_rotation.T @ cell.tool_rotation
            leg_position = leg_world - belt_shift(cell.time_s)
            turn_rad = _wrap(TARGET_HEADING_RAD - source.heading_rad)
            target_rotation = _rot_z(turn_rad) @ leg_rotation
            target_position = np.array(
                [float(leg_position[0]), _blade_plane_y(cell) - float((target_rotation @ hock_in_leg)[1]), carry_z]
            )
            travel_m = float(
                np.linalg.norm((target_position - leg_position) + (target_rotation - leg_rotation) @ tool_in_leg)
            )
            # A smoothstep of angle theta over T peaks at 6 theta / T^2.
            turn_s = max(
                MIN_TURN_S,
                abs(turn_rad) / TURN_RATE_RADPS,
                math.sqrt(6.0 * abs(turn_rad) / self.turn_acceleration_radps2),
                travel_m / TOOL_SPEED_MPS,
            )
            return _TurnPlan(
                leg_position,
                leg_rotation,
                tool_in_leg,
                tool_rotation_in_leg,
                target_position,
                target_rotation,
                turn_rad,
                turn_s,
            )

        # The leg pose was captured with the shank already raised by the proof
        # lift; the turn carries it `carry_lift_m` above where the jaws closed,
        # and the set-down returns it exactly there, so the tool never presses
        # the shank into the belt.
        rise_so_far = float(cell.tool_position_m[2]) - proof.tool_z_m
        extra_lift = self.carry_lift_m - rise_so_far
        first = plan(estimate, float(estimate.centre_of_gravity_m[2]))
        evidence["turn_rad"] = first.turn_rad
        evidence["shift_m"] = float(np.linalg.norm(first.target_position[:2] - first.leg_position[:2]))
        lift_start_s = cell.time_s

        def lift(t_s: float) -> tuple[np.ndarray, np.ndarray]:
            rise = smoothstep((t_s - lift_start_s) / LIFT_S) * extra_lift
            return first.tool_for_leg(
                first.leg_position + belt_shift(t_s) + np.array([0.0, 0.0, rise]), first.leg_rotation
            )

        def turn_path(current: _TurnPlan, start_s: float) -> ToolPath:
            def turn(t_s: float) -> tuple[np.ndarray, np.ndarray]:
                fraction = smoothstep((t_s - start_s) / current.turn_s)
                rotation = _rot_z(fraction * current.turn_rad) @ current.leg_rotation
                position = (
                    current.leg_position + fraction * (current.target_position - current.leg_position) + belt_shift(t_s)
                )
                return current.tool_for_leg(position, rotation)

            return turn

        def lower(t_s: float) -> tuple[np.ndarray, np.ndarray]:
            fraction = smoothstep((t_s - lower_start_s) / LOWER_S)
            position = current.target_position + belt_shift(t_s)
            position[2] -= fraction * self.carry_lift_m
            return current.tool_for_leg(position, current.target_rotation)

        def retreat(t_s: float) -> tuple[np.ndarray, np.ndarray]:
            fraction = smoothstep((t_s - retreat_start_s) / RETREAT_S)
            position = current.target_position + belt_shift(t_s)
            position[2] -= self.carry_lift_m
            tool_position, tool_rotation = current.tool_for_leg(position, current.target_rotation)
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
            # After the lift the leg sits at carry height; plan the turn there
            # from the estimate, then check it against a fresh estimate and
            # correct, up to `MAX_CORRECTIONS` times: on a turn of more than
            # about 90 degrees the leg lags the tool by 3 to 5 degrees in the
            # jaws (2026-09-15), and a second, small turn takes that out.
            carry_z = float(first.leg_position[2]) + extra_lift
            current = plan(estimate, carry_z)
            corrections = 0
            while True:
                turn_start_s = cell.time_s
                cell.follow_tool(turn_path(current, turn_start_s), current.turn_s)
                if corrections == 0:
                    # Slip: the leg's true centre of gravity and heading against the plan.
                    truth = cell.ground_truth()
                    assert truth.centre_of_mass_m is not None
                    _, rotation = leg_pose(cell)
                    planned = current.target_position + belt_shift(cell.time_s)
                    evidence["slip_m"] = float(np.linalg.norm(truth.centre_of_mass_m[:2] - planned[:2]))
                    evidence["slip_rad"] = _wrap(leg_heading_rad(rotation) - TARGET_HEADING_RAD)
                if re_estimate is None or corrections >= MAX_CORRECTIONS:
                    break
                fresh = re_estimate()
                if fresh is None:
                    break
                hock_error = float(
                    (fresh.point_at(HOCK_FRACTION) + np.array([cell.belt_travel_m - fresh.belt_travel_m, 0.0, 0.0]))[1]
                ) - _blade_plane_y(cell)
                heading_error = _wrap(fresh.heading_rad - TARGET_HEADING_RAD)
                if abs(hock_error) <= CORRECT_ABOVE_HOCK_M and abs(heading_error) <= CORRECT_ABOVE_HEADING_RAD:
                    break
                current = plan(fresh, carry_z)
                corrections += 1
            evidence["corrections"] = float(corrections)
            lower_start_s = cell.time_s
            cell.follow_tool(lower, LOWER_S)
            cell.open_gripper(min(cell.gripper_geometry.max_opening_m, grasp.widest_under_pads_m + 2 * OPEN_MARGIN_M))
            released_at_x = _leg_extent_x(cell)
            retreat_start_s = cell.time_s
            cell.follow_tool(retreat, OPEN_S + RETREAT_S)
            clear_from, clear_rotation = cell.tool_position_m.copy(), cell.tool_rotation.copy()
            clear_start_s = cell.time_s
            cell.follow_tool(clear, CLEAR_S)
        except UnreachableError as error:
            logger.info("%s: %s", self.name, error)
            cell.open_gripper(cell.gripper_geometry.max_opening_m)
            return UNREACHABLE.name, {}, evidence

        alignment = measure_alignment(cell, released_at_x, cell.time_s - started_s)
        evidence["hock_offset_m"] = alignment.hock_offset_m
        evidence["heading_error_rad"] = alignment.heading_error_rad
        evidence["released_at_x_m"] = alignment.released_at_x_m
        evidence["cycle_s"] = alignment.cycle_s
        leg_height = float(leg_pose(cell)[0][2]) - BELT_TOP_Z_M
        evidence["leg_height_m"] = leg_height
        if abs(leg_height) > ON_BELT_TOLERANCE_M:
            return DROPPED.name, {}, evidence
        if cell.hold_down is not None and released_at_x >= cell.hold_down.config.entry_x_m:
            return RELEASED_LATE.name, {}, evidence
        if abs(alignment.hock_offset_m) > HOCK_TOLERANCE_M or abs(alignment.heading_error_rad) > HEADING_TOLERANCE_RAD:
            slipped = evidence["slip_m"] > HOCK_TOLERANCE_M / 2 or abs(evidence["slip_rad"]) > HEADING_TOLERANCE_RAD / 2
            return (SLIPPED if slipped else MISALIGNED).name, {}, evidence
        return SUCCESS, {"alignment": alignment}, evidence


# Approach A carries the whole leg. The shank rises enough that a leg the jaws
# hold rigidly clears the belt by its full drop; a grip that yields in pitch
# leaves the ham dragging, which is the failure the airborne check names.
CARRY_LIFT_M = 0.10
NOT_LIFTED = FailureMode(
    "not_lifted", "the leg still touched the belt at carry height: the grip did not hold its pitch"
)
GRAVITY_MPS2 = 9.81


class PickAndPlace(RotateOnBelt):
    """Approach A: lift the leg clear of the belt, carry it to the aligned pose, set it down, release.

    Same target and same path as the turn on the belt, with the shank carried
    high enough that the ham leaves the belt, so the arm bears the leg's weight
    and the moment of its centre of gravity about the tool. Both are reported
    as evidence against each arm's rating: the load on the flange, the moment
    about the jaw line, and the leg's inertia about the tool's vertical axis,
    which is what a SCARA's wrist carries when it turns the leg.
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
        """Report the load the arm carries and refuse to carry a leg that is still on the belt."""
        truth = cell.ground_truth()
        assert truth.centre_of_mass_m is not None
        leg_bodies = [cell.model.body("slab").id, cell.model.body("trotter").id]
        mass = float(sum(cell.model.body_mass[b] for b in leg_bodies))
        tool = cell.tool_position_m
        lever = truth.centre_of_mass_m[:2] - tool[:2]
        # Inertia about the tool's vertical axis: each body's own zz inertia
        # plus its mass at its distance from the tool axis.
        inertia = 0.0
        for b in leg_bodies:
            offset = np.asarray(cell.data.xipos[b])[:2] - tool[:2]
            inertia += float(cell.model.body_inertia[b][2]) + float(cell.model.body_mass[b]) * float(offset @ offset)
        evidence["flange_load_n"] = mass * GRAVITY_MPS2
        evidence["moment_about_tool_nm"] = mass * GRAVITY_MPS2 * float(np.linalg.norm(lever))
        evidence["inertia_about_tool_kgm2"] = inertia
        touching = leg_touches_belt(cell)
        evidence["airborne"] = 0.0 if touching else 1.0
        return NOT_LIFTED.name if touching else None


def leg_touches_belt(cell: Cell) -> bool:
    """Whether any part of the leg is in contact with the belt surface now."""
    belt = cell.model.geom("belt_surface").id
    leg_bodies = {cell.model.body("slab").id, cell.model.body("trotter").id}
    for i in range(cell.data.ncon):
        contact = cell.data.contact[i]
        geoms = (int(contact.geom1), int(contact.geom2))
        bodies = {int(cell.model.geom_bodyid[geoms[0]]), int(cell.model.geom_bodyid[geoms[1]])}
        if belt in geoms and bodies & leg_bodies:
            return True
    return False
