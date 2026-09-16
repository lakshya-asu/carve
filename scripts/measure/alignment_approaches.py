r"""Run the pre-registered alignment experiment: each approach, arm and tilt on the same 20 pieces.

The protocol, the success definition and the reported numbers are fixed in
experiments/2026-09-15-alignment-approaches.md (legs) and
experiments/2026-09-16-loin-infeed-transfer.md (loins). Each episode places one
piece of the population on the running belt with its centre of gravity at the
arrival point, runs the orient skills from ground-truth pose, returns the arm
to its ready pose, and lets the piece ride to the judge: the hold-down belt
and the saw for a leg, the infeed fixture for a loin.

`--product` selects the population, the estimate skills, the grasp station,
the alignment target and the judge (`PRODUCTS`). Nothing else in the runner
knows which product it is running.

One row per episode goes to a CSV under experiments/data, and a summary table
per condition is printed for the record.

Usage:
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/measure/alignment_approaches.py \\
        --approach B --arm ur20 --tilt-deg 0 15 30
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/measure/alignment_approaches.py \\
        --product loin --approach B --arm sr20ia --tilt-deg 0
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
import statistics
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from applications.pork_leg_alignment.perception.leg_segmentation import EmptyBeltReference, LegSegmenter
from applications.pork_leg_alignment.perception.perceive_leg import perceive_leg
from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.hold_down import HoldDownConfig
from applications.pork_leg_alignment.sim.infeed_fixture import InfeedFixtureConfig, InfeedOutcome, target_heading_rad
from applications.pork_leg_alignment.sim.loin import OVERHEAD_CAMERA_MOUNT_M, LoinConfig, loin_population
from applications.pork_leg_alignment.sim.product import LegConfig, leg_population
from applications.pork_leg_alignment.sim.saw import CutOutcome, SawConfig
from applications.pork_leg_alignment.sim.scene import ArmMount, CellConfig
from applications.pork_leg_alignment.sim.sensing import CameraSpec
from applications.pork_leg_alignment.skills import (
    INFEED_TARGET,
    SAW_TARGET,
    AcquireShank,
    AlignmentTarget,
    EstimateLegFromCamera,
    EstimateLegFromGroundTruth,
    EstimateLoinFromGroundTruth,
    LegEstimate,
    PickAndPlace,
    RotateOnBelt,
    SelectShankGrasp,
    centre_of_gravity_station,
    shank_station,
)
from applications.pork_leg_alignment.skills.rotate_on_belt import TURN_ACCELERATION_RADPS2
from robotics.core.camera_frame import CameraFrameData
from robotics.core.skill_library import SUCCESS, Skill, SkillResult, run_skill
from robotics.hardware.arms import ArmModel
from robotics.hardware.cameras import GEMINI_335L, EdgeEffects, sense_depth
from robotics.hardware.grippers import GripperModel
from robotics.hardware.ik import UnreachableError, solve_ik
from robotics.perception.learned_centre_of_gravity import LearnedCentreOfGravity

logger = logging.getLogger("alignment_approaches")

LEG_COUNT = 20
LEG_SEED = 0
ARRIVAL_SEED = 20260915
# Arrival: centre of gravity here, y and heading drawn per piece.
ARRIVAL_X_M = -0.30
ARRIVAL_Y_RANGE_M = (0.40, 0.60)
ARRIVAL_YAW_RANGE_RAD = math.radians(35.0)
# The leg's target heading: trotter straight out over the open edge. A loin's
# is along the belt, chosen per piece by its bone side (`Product.square_heading`).
SQUARE_HEADING_RAD = -math.pi / 2
# The belt body's y in cell.xml; which side of it the loin's datum stands on
# decides the loin's target heading.
BELT_CENTRE_Y_M = 0.50
BELT_SPEED_MPS = 0.30
# Cell layout for the run (amended 2026-09-15, see the record): saw and
# hold-down 1.75 m down the belt from the six-axis mount, the hold-down's
# pressing section 0.5 m long so its lead-in starts at x = 1.11 m, 0.14 m past
# where the open jaws are when they have risen clear of a released leg; SCARA
# mount 0.35 m downstream so its 1.1 m reach covers the pick and the set-down.
SAW_X_M = 1.75
HOLD_DOWN_LENGTH_M = 0.50
# Two arrival sets. "square": the pre-registered draw, within 35 degrees of
# square with the trotter toward the open edge, saw at 1.95 m on a 5 m belt
# (1.75 m on 4 m until the correcting turn of 2026-09-15 added 0.4 s, after
# which the UR20's fingers met the hold-down ramp on their way up on 7 to 13
# legs of 20). "any": the leg
# at any heading at all, ham kept on the belt, trotter wherever the heading
# puts it, including upstream, downstream and toward the rail; a leg that
# arrives trotter-first needs a turn of up to 180 degrees, which is more belt,
# so the saw stands at 2.30 m on a 6 m belt. Added 2026-09-15 at Lakshya's
# request, before any run of it.
# Per set: heading range, saw x, belt half length, and each arm's mount x. A
# 180 degree turn takes 2.5 s plus a correcting pass, so a leg arriving
# trotter-upstream is set down 1.5 to 1.8 m past the pick; the saw stands at
# 2.6 m on a 6 m belt and each arm stands midway between the pick and its
# furthest set-down, as far downstream as its reach to the pick allows.
ARRIVAL_KINDS = {
    "square": (ARRIVAL_YAW_RANGE_RAD, 1.95, 2.5, {ArmModel.UR20: 0.0, ArmModel.SR20IA: 0.45}),
    "any": (math.pi, 2.60, 3.0, {ArmModel.UR20: 0.85, ArmModel.SR20IA: 0.60}),
}
# The ham end must stay this far inside either belt edge; the trotter may
# overhang the open edge, as it does on the line, but not the rail.
BELT_EDGE_Y_M = (0.15, 0.85)
EDGE_MARGIN_M = 0.03
# Where each arm waits between legs: over the open-edge side of the belt, where
# the legs are thin, tool down and jaws across the belt. A leg arrives with its
# ham on the far side, so an arm that waits here and swings to the shank never
# passes its open jaws over a ham; waiting mid-belt at y = 0.50, the SR-20iA
# swept its jaws through the ham of a 766 mm leg (2026-09-15). The height is
# the top of the SR-20iA's stroke at its mount, used for both arms.
# The ready pose sits 0.45 m upstream of the arm's mount, over the thin side of the belt.
READY_UPSTREAM_OF_MOUNT_M = 0.45
READY_Y_M = 0.25
READY_Z_M = 0.90 + 0.21
READY_YAW_RAD = SQUARE_HEADING_RAD
SPEED_FRACTION = 0.5
MIN_MOVE_S = 0.4
# Success bars, from the record. Assumed; the customer has given no tolerance.
OFFSET_TOLERANCE_M = 0.010
ANGLE_TOLERANCE_RAD = math.radians(5.0)
SETTLE_S = 0.3
PASS_TIMEOUT_S = 15.0
# The camera path: the Gemini 335L model over the belt, long side across it, with edge
# effects on, the depth-height segmenter, `perceive_leg`, and the learned centre-of-gravity
# corrector when a checkpoint is given. The same pipeline the ROS 2 bridge runs.
CAMERA = GEMINI_335L.name
EMPTY_BELT_FRAMES = 10
OUT_OF_VIEW_X_M = 1.3
CAMERA_SEED = 20260915


@dataclass(frozen=True)
class Verdict:
    """The judge's reading of one piece, whichever judge: the saw's cut or the fixture's crossing."""

    outcome: str
    entry_offset_m: float
    exit_offset_m: float
    angle_rad: float
    drift_rad: float
    slip_m: float


@dataclass(frozen=True)
class Product:
    """What `--product` selects. Nothing else in the runner knows the product.

    Attributes:
        name: The flag's value and the CSV's `product` column.
        data_dir: Where this product's CSVs go.
        population: (count, seed) to the pieces, in the order the episodes run.
        ground_truth_skill: The estimate skill from the simulator's own pose.
        camera_skill: The estimate skill from the camera pipeline, or None
            when the product has no perception yet.
        ground_truth: The true piece, for the record's error columns.
        station: The grasp rule's station, as `SelectShankGrasp` takes it.
        target: What aligned means, as `RotateOnBelt` takes it.
        fixtures: `CellConfig` fields for the judge standing at a given x.
        camera_mount_m: Where the cell hangs its overhead camera, or None for
            the XML's position.
        verdict: The judge's reading once the piece has passed it, or None.
        judge_name: How the judge is named in a failure.
        passed: The verdict outcome that counts as the judge passing the piece.
        square_heading: The heading "square" arrivals are drawn about, per piece.
        centre_of_gravity_fraction: Where along the piece its centre of gravity
            sits, for keeping the ends of an "any" arrival on the belt.
    """

    name: str
    data_dir: Path
    population: Callable[[int, int], list[Any]]
    ground_truth_skill: Callable[[], Skill]
    camera_skill: Callable[[], Skill] | None
    ground_truth: Callable[[Cell], LegEstimate]
    station: Callable[[LegEstimate], float]
    target: AlignmentTarget
    fixtures: Callable[[float], dict[str, Any]]
    camera_mount_m: tuple[float, float, float] | None
    verdict: Callable[[Cell], Verdict | None]
    judge_name: str
    passed: str
    square_heading: Callable[[Any], float]
    centre_of_gravity_fraction: float


def _saw_verdict(cell: Cell) -> Verdict | None:
    result = cell.cut_result
    if result is None:
        return None
    return Verdict(
        result.outcome.value,
        result.offset_from_hock_m,
        result.offset_at_exit_m,
        result.angle_rad,
        result.yaw_drift_rad,
        result.slip_m,
    )


def _fixture_verdict(cell: Cell) -> Verdict | None:
    result = cell.infeed_result
    if result is None:
        return None
    return Verdict(
        result.outcome.value,
        result.offset_m,
        result.offset_at_exit_m,
        result.angle_rad,
        result.yaw_drift_rad,
        result.slip_m,
    )


def _leg_fixtures(x_m: float) -> dict[str, Any]:
    return {"saw": SawConfig(x_m=x_m), "hold_down": HoldDownConfig(x_centre_m=x_m, length_m=HOLD_DOWN_LENGTH_M)}


def _loin_fixtures(x_m: float) -> dict[str, Any]:
    return {"infeed_fixture": InfeedFixtureConfig(x_m=x_m)}


LOIN_DATUM_SIDE = math.copysign(1.0, InfeedFixtureConfig().datum_y_m - BELT_CENTRE_Y_M)

PRODUCTS = {
    "leg": Product(
        name="leg",
        data_dir=Path("experiments/data/2026-09-15-alignment-approaches"),
        population=leg_population,
        ground_truth_skill=EstimateLegFromGroundTruth,
        camera_skill=EstimateLegFromCamera,
        ground_truth=SAW_TARGET.ground_truth,
        station=shank_station,
        target=SAW_TARGET,
        fixtures=_leg_fixtures,
        camera_mount_m=None,
        verdict=_saw_verdict,
        judge_name="saw",
        passed=CutOutcome.CUT.value,
        square_heading=lambda leg: SQUARE_HEADING_RAD,
        # The leg's centre of gravity sits about 0.35 of the length from the butt.
        centre_of_gravity_fraction=0.35,
    ),
    "loin": Product(
        name="loin",
        data_dir=Path("experiments/data/2026-09-16-loin-infeed-transfer"),
        population=loin_population,
        ground_truth_skill=EstimateLoinFromGroundTruth,
        camera_skill=None,
        ground_truth=INFEED_TARGET.ground_truth,
        station=centre_of_gravity_station,
        target=INFEED_TARGET,
        fixtures=_loin_fixtures,
        camera_mount_m=OVERHEAD_CAMERA_MOUNT_M,
        verdict=_fixture_verdict,
        judge_name="fixture",
        passed=InfeedOutcome.CROSSED.value,
        square_heading=lambda loin: target_heading_rad(loin.bone_side, LOIN_DATUM_SIDE),
        centre_of_gravity_fraction=0.5,
    ),
}
DATA_DIR = PRODUCTS["leg"].data_dir


@dataclass(frozen=True)
class Arrival:
    """One piece's arrival pose, centre of gravity at `ARRIVAL_X_M`."""

    y_m: float
    heading_rad: float


def arrivals(
    count: int,
    kind: str = "square",
    legs: list[LegConfig] | list[LoinConfig] | None = None,
    product: Product = PRODUCTS["leg"],
) -> list[Arrival]:
    """The same arrival draw for every condition of one kind, about each piece's own target heading.

    For "any", the drawn y is shifted the least that keeps the row-0 end (a
    leg's ham) and, when it points at the rail, the other end inside the belt.
    """
    yaw_range = ARRIVAL_KINDS[kind][0]
    rng = np.random.default_rng(ARRIVAL_SEED)
    draws = []
    for index in range(count):
        y = float(rng.uniform(*ARRIVAL_Y_RANGE_M))
        offset = float(rng.uniform(-yaw_range, yaw_range))
        heading = (product.square_heading(legs[index]) if legs is not None else SQUARE_HEADING_RAD) + offset
        if kind == "any" and legs is not None:
            leg = legs[index]
            along = math.sin(heading)
            butt_y = y - product.centre_of_gravity_fraction * leg.length_m * along
            tip_y = y + (1.0 - product.centre_of_gravity_fraction) * leg.length_m * along
            low, high = BELT_EDGE_Y_M[0] + EDGE_MARGIN_M, BELT_EDGE_Y_M[1] - EDGE_MARGIN_M
            shift = 0.0
            for end_y, keep_off_open_edge in ((butt_y, True), (tip_y, False)):
                if end_y > high:
                    shift = min(shift, high - end_y)
                if keep_off_open_edge and end_y < low:
                    shift = max(shift, low - end_y)
            y += shift
        draws.append(Arrival(y_m=y, heading_rad=heading))
    return draws


def park_ready(cell: Cell) -> None:
    """Move the arm to its ready pose at the allowed joint speeds and let it settle.

    The ready pose is solved from the arm's current joints first, so a parked
    arm stays on its branch; after a big turn the UR20's wrist can be left where
    that seed converges 130 degrees off in orientation (loin 10 of the any set,
    2026-09-16), so the solve is retried from the home pose, which every
    episode's first park solves from.
    """
    ready = np.array([cell.config.mount.x_m - READY_UPSTREAM_OF_MOUNT_M, READY_Y_M, READY_Z_M])
    try:
        q = solve_ik(cell.model, cell.data, ready, READY_YAW_RAD, arm=cell.arm)
    except UnreachableError:
        q = solve_ik(cell.model, cell.data, ready, READY_YAW_RAD, seed_qpos=np.array(cell.arm.home_qpos), arm=cell.arm)
    speeds = np.asarray(cell.arm.max_joint_speed) * SPEED_FRACTION
    cell.move_arm(q, max(MIN_MOVE_S, float(np.max(np.abs(q - cell.arm_qpos) / speeds))))
    cell.step(seconds=0.2)


def place_by_centre_of_gravity(cell: Cell, arrival: Arrival) -> None:
    """Put the piece down so its centre of gravity, not its body origin, is at the arrival point.

    The centre of mass is read from the model at the nominal pose without
    stepping, then the piece is placed once at the corrected pose and settles
    there; placing it twice with a settle in between showed on video as the
    leg jumping back along the belt.
    """
    cell.place_product(ARRIVAL_X_M, arrival.y_m, arrival.heading_rad, settle_s=0.0)
    truth = cell.ground_truth()
    assert truth.centre_of_mass_m is not None
    shift = truth.centre_of_mass_m[:2] - np.array([truth.piece_pose.x_m, truth.piece_pose.y_m])
    cell.place_product(ARRIVAL_X_M - float(shift[0]), arrival.y_m - float(shift[1]), arrival.heading_rad, settle_s=0.0)


def cell_config(
    arm: ArmModel,
    leg: LegConfig | LoinConfig,
    gripper: GripperModel,
    camera: bool = False,
    kind: str = "square",
    product: Product = PRODUCTS["leg"],
) -> CellConfig:
    """The run's cell for one arm and one piece, with the depth camera when the pose comes from it."""
    # Mounts per arrival set. Square: the UR20 at x = 0, where it stood for
    # every earlier run (at 0.35 its retreat after release met the hold-down
    # ramp on 7 to 13 legs of 20, 2026-09-15); the SR-20iA at 0.45, because
    # the correcting turn sets the leg down 0.12 m further along and from
    # 0.35 the retreat at x = 0.92 was 1 mm past its reach on 7 legs. Any: a
    # leg arriving trotter-upstream is set down 1.1 to 1.3 m downstream after
    # a 180 degree turn, beyond the UR20's reach from x = 0 with the tool down.
    _, saw_x, half_length, mounts = ARRIVAL_KINDS[kind]
    mount = ArmMount(x_m=mounts[arm], y_m=1.10, z_m=1.10 if arm is ArmModel.SR20IA else 0.90, yaw_rad=-math.pi / 2)
    return CellConfig(
        belt_speed_mps=BELT_SPEED_MPS,
        belt_half_length_m=half_length,
        arm=arm,
        arm_mount=mount,
        gripper=gripper,
        depth_cameras=(GEMINI_335L,) if camera else (),
        depth_camera_yaw_deg=90.0,
        overhead_camera_mount_m=product.camera_mount_m,
        **{product.name: leg},
        **product.fixtures(saw_x),
    )


class CameraPipeline:
    """Empty-belt reference, segmentation, perception and centre of gravity, as the bridge runs them."""

    def __init__(self, cell: Cell, checkpoint: Path | None) -> None:
        """Record the empty belt with the leg parked out of view, then build the segmenter."""
        self.rng = np.random.default_rng(CAMERA_SEED)
        self.edges = EdgeEffects()
        self.learned = LearnedCentreOfGravity(checkpoint) if checkpoint is not None else None
        cell.reset()
        cell.place_product(OUT_OF_VIEW_X_M, 0.5, -math.pi / 2)
        empties = [self.noisy(cell.observe(CAMERA)[1]) for _ in range(EMPTY_BELT_FRAMES)]
        self.segmenter = LegSegmenter(EmptyBeltReference.from_frames(empties))

    def noisy(self, frame: CameraFrameData) -> CameraFrameData:
        """The Gemini's depth errors, edge effects included."""
        depth = sense_depth(frame.depth_m, GEMINI_335L, self.rng, edges=self.edges)
        return CameraFrameData(frame.stamp_s, frame.rgb, depth, frame.intrinsics, frame.camera)

    def perceive(self, cell: Cell) -> tuple[dict[str, Any], str]:
        """One frame of the leg now, as skill arguments; or why it could not be perceived."""
        observation, frame = cell.observe(CAMERA)
        noisy = self.noisy(frame)
        result = self.segmenter.segment(noisy)
        if not result.accepted:
            return {}, f"segmenter refused: {result.refused}"
        plane = self.segmenter.reference.plane
        leg = perceive_leg(noisy, result.mask, plane, observation.belt_travel_m)
        args: dict[str, Any] = {"leg_perception": leg}
        if self.learned is not None:
            args["centre_of_gravity_m"] = self.learned.estimate(noisy, result.mask, plane).position_m
        return args, ""


@dataclass
class Episode:
    """One row of the results table."""

    product: str
    condition: str
    approach: str
    pose_source: str
    arm: str
    gripper: str
    tilt_deg: float
    piece: int
    length_mm: float
    mass_kg: float
    arrival_y_m: float
    arrival_heading_deg: float
    estimate: str = ""
    estimate_datum_error_mm: float = math.nan
    estimate_heading_error_deg: float = math.nan
    estimate_cog_error_mm: float = math.nan
    estimate_length_error_mm: float = math.nan
    select: str = ""
    acquire: str = ""
    re_estimate: str = ""
    grasp_shift_mm: float = math.nan
    orient: str = ""
    flange_load_n: float = math.nan
    moment_about_tool_nm: float = math.nan
    inertia_about_tool_kgm2: float = math.nan
    airborne: float = math.nan
    corrections: float = math.nan
    meet_error_mm: float = math.nan
    opening_mm: float = math.nan
    tool_rise_mm: float = math.nan
    turn_deg: float = math.nan
    slip_mm: float = math.nan
    slip_deg: float = math.nan
    datum_offset_mm: float = math.nan
    heading_error_deg: float = math.nan
    released_at_x_m: float = math.nan
    cycle_s: float = math.nan
    arm_collisions: int = 0
    collision: str = ""
    collision_at_s: float = math.nan
    judge: str = ""
    entry_offset_mm: float = math.nan
    exit_offset_mm: float = math.nan
    angle_deg: float = math.nan
    drift_deg: float = math.nan
    judge_slip_mm: float = math.nan
    success: bool = False
    failure: str = ""
    wall_s: float = math.nan


def _evidence(result: SkillResult, key: str, scale: float = 1.0) -> float:
    return scale * float(result.evidence[key]) if key in result.evidence else math.nan


def estimate_errors(estimate: LegEstimate, truth: LegEstimate, target: AlignmentTarget) -> dict[str, float]:
    """How far an estimate is from ground truth taken at the same moment, for the record."""
    carried = np.array([truth.belt_travel_m - estimate.belt_travel_m, 0.0, 0.0])
    datum = target.datum_point(estimate) + carried - target.datum_point(truth)
    centre = estimate.centre_of_gravity_m + carried - truth.centre_of_gravity_m
    return {
        "estimate_datum_error_mm": 1000 * float(np.linalg.norm(datum[:2])),
        "estimate_heading_error_deg": math.degrees(
            math.remainder(estimate.heading_rad - truth.heading_rad, 2 * math.pi)
        ),
        "estimate_cog_error_mm": 1000 * float(np.linalg.norm(centre[:2])),
        "estimate_length_error_mm": 1000 * (estimate.length_m - truth.length_m),
    }


def run_episode(
    arm: ArmModel,
    gripper: GripperModel,
    tilt_rad: float,
    leg_index: int,
    leg: LegConfig | LoinConfig,
    arrival: Arrival,
    pose_source: str = "truth",
    checkpoint: Path | None = None,
    approach: str = "B",
    kind: str = "square",
    turn_acceleration_radps2: float = TURN_ACCELERATION_RADPS2,
    cell_class: type[Cell] = Cell,
    on_cell: Callable[[Cell, Episode], None] | None = None,
    product: Product = PRODUCTS["leg"],
) -> Episode:
    """One piece through approach B: estimate the piece, grasp, rotate on the belt, release, judge."""
    started = time.perf_counter()
    row = Episode(
        product=product.name,
        condition=f"{approach}-{arm.value}-{gripper.value}-tilt{math.degrees(tilt_rad):.0f}-{pose_source}-{kind}",
        approach=approach,
        pose_source=pose_source,
        arm=arm.value,
        gripper=gripper.value,
        tilt_deg=math.degrees(tilt_rad),
        piece=leg_index,
        length_mm=1000 * leg.length_m,
        mass_kg=leg.mass_kg,
        arrival_y_m=arrival.y_m,
        arrival_heading_deg=math.degrees(arrival.heading_rad - product.square_heading(leg)),
    )
    camera = pose_source == "camera"
    if camera and product.camera_skill is None:
        raise ValueError(f"the {product.name} has no camera pipeline yet; run it from ground truth")
    cameras = (
        {CAMERA: CameraSpec(CAMERA, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)} if camera else {}
    )
    with cell_class(cell_config(arm, leg, gripper, camera=camera, kind=kind, product=product), cameras) as cell:
        if on_cell is not None:
            on_cell(cell, row)
        pipeline = CameraPipeline(cell, checkpoint) if camera else None
        cell.reset()
        park_ready(cell)
        place_by_centre_of_gravity(cell, arrival)
        cell.arm_collisions = 0
        cycle_start_s = cell.time_s

        # The camera sees the leg as it arrives, before it settles and rides
        # on: 0.3 s later its ham has left the image's downstream edge, which
        # says the camera sits too close to the pick zone (11.6).
        estimated: SkillResult | None = None
        perceived: dict[str, Any] = {}
        refused = ""
        if pipeline is not None:
            perceived, refused = pipeline.perceive(cell)
        cell.step(seconds=SETTLE_S)
        if pipeline is not None:
            assert product.camera_skill is not None
            if refused:
                row.estimate = refused
            else:
                estimated = run_skill(product.camera_skill(), cell, perceived)
        else:
            estimated = run_skill(product.ground_truth_skill(), cell, {})
        if estimated is not None:
            row.estimate = estimated.outcome
            if estimated.outcome == SUCCESS:
                errors = estimate_errors(estimated.outputs["leg_estimate"], product.ground_truth(cell), product.target)
                for key, value in errors.items():
                    setattr(row, key, value)
        selected = (
            run_skill(SelectShankGrasp(tilt_rad=tilt_rad, station=product.station), cell, estimated.outputs)
            if estimated is not None and estimated.outcome == SUCCESS
            else None
        )
        row.select = selected.outcome if selected is not None else ""
        if selected is not None and selected.outcome == SUCCESS:
            acquired = run_skill(AcquireShank(), cell, selected.outputs)
            row.acquire = acquired.outcome
            row.meet_error_mm = _evidence(acquired, "meet_error_m", 1000)
            row.opening_mm = _evidence(acquired, "opening_m", 1000)
            row.tool_rise_mm = _evidence(acquired, "tool_rise_m", 1000)
            if acquired.outcome == SUCCESS:
                assert estimated is not None
                # Closing the jaws moves the leg (about 20 mm along its axis on
                # the default leg, 2026-09-15), so the turn is planned on a
                # fresh estimate: ground truth again, or a second camera look
                # when the leg is still in view; otherwise the first estimate,
                # carried by the belt, and the record says so.
                before = estimated.outputs["leg_estimate"]
                if pipeline is not None:
                    assert product.camera_skill is not None
                    perceived, refused = pipeline.perceive(cell)
                    again = run_skill(product.camera_skill(), cell, perceived) if not refused else None
                    row.re_estimate = again.outcome if again is not None else f"kept first: {refused}"
                else:
                    again = run_skill(product.ground_truth_skill(), cell, {})
                    row.re_estimate = again.outcome
                planning = again.outputs["leg_estimate"] if again is not None and again.outcome == SUCCESS else before
                truth_now = product.ground_truth(cell)
                carried = np.array([truth_now.belt_travel_m - before.belt_travel_m, 0.0, 0.0])
                row.grasp_shift_mm = 1000 * float(
                    np.linalg.norm(
                        (product.target.datum_point(before) + carried - product.target.datum_point(truth_now))[:2]
                    )
                )
                orient_skill = (PickAndPlace if approach == "A" else RotateOnBelt)(
                    turn_acceleration_radps2, target=product.target
                )

                def re_estimate() -> LegEstimate | None:
                    """A fresh look at the piece mid-turn: the truth, or the camera when it can see it."""
                    if pipeline is None:
                        return product.ground_truth(cell)
                    assert product.camera_skill is not None
                    seen, why = pipeline.perceive(cell)
                    if why:
                        return None
                    return run_skill(product.camera_skill(), cell, seen).outputs.get("leg_estimate")

                oriented = run_skill(
                    orient_skill,
                    cell,
                    {"leg_estimate": planning, "re_estimate": re_estimate, **selected.outputs, **acquired.outputs},
                )
                row.corrections = _evidence(oriented, "corrections")
                row.flange_load_n = _evidence(oriented, "flange_load_n")
                row.moment_about_tool_nm = _evidence(oriented, "moment_about_tool_nm")
                row.inertia_about_tool_kgm2 = _evidence(oriented, "inertia_about_tool_kgm2")
                row.airborne = _evidence(oriented, "airborne")
                row.orient = oriented.outcome
                row.turn_deg = math.degrees(_evidence(oriented, "turn_rad"))
                row.slip_mm = _evidence(oriented, "slip_m", 1000)
                row.slip_deg = math.degrees(_evidence(oriented, "slip_rad"))
                row.datum_offset_mm = _evidence(oriented, "datum_offset_m", 1000)
                row.heading_error_deg = math.degrees(_evidence(oriented, "heading_error_rad"))
                row.released_at_x_m = _evidence(oriented, "released_at_x_m")
                row.cycle_s = cell.time_s - cycle_start_s
        # Whatever happened, let go and get out of the way, as the cycle would.
        cell.open_gripper(cell.gripper_geometry.max_opening_m)
        cell.step(seconds=0.2)
        park_ready(cell)
        row.arm_collisions = cell.arm_collisions
        row.collision = "; ".join(f"{a}/{b}" for a, b in sorted(cell.arm_collision_pairs))
        row.collision_at_s = cell.arm_collision_first_s - cycle_start_s

        deadline = cell.time_s + PASS_TIMEOUT_S
        while product.verdict(cell) is None and cell.time_s < deadline:
            cell.step(seconds=0.02)
        verdict = product.verdict(cell)
        if verdict is None:
            row.judge = "no_result"
        else:
            row.judge = verdict.outcome
            row.entry_offset_mm = 1000 * verdict.entry_offset_m
            row.exit_offset_mm = 1000 * verdict.exit_offset_m
            row.angle_deg = math.degrees(verdict.angle_rad)
            row.drift_deg = math.degrees(verdict.drift_rad)
            row.judge_slip_mm = 1000 * verdict.slip_m
    row.success, row.failure = judge(row)
    row.wall_s = time.perf_counter() - started
    return row


def judge(row: Episode) -> tuple[bool, str]:
    """The record's success definition, and the first failure mode that applies."""
    product = PRODUCTS[row.product]
    if row.estimate != SUCCESS:
        return False, f"estimate: {row.estimate}"
    if row.select != SUCCESS:
        return False, f"select: {row.select}"
    if row.acquire != SUCCESS:
        return False, f"grasp: {row.acquire}"
    if row.orient != SUCCESS:
        return False, f"orient: {row.orient}"
    if row.arm_collisions > 0:
        return False, "arm collision"
    if row.judge != product.passed:
        return False, f"{product.judge_name}: {row.judge}"
    if abs(row.entry_offset_mm) > 1000 * OFFSET_TOLERANCE_M or abs(row.exit_offset_mm) > 1000 * OFFSET_TOLERANCE_M:
        return False, f"{product.judge_name} offset {row.entry_offset_mm:+.1f} / {row.exit_offset_mm:+.1f} mm"
    if abs(row.angle_deg) > math.degrees(ANGLE_TOLERANCE_RAD):
        return False, f"{product.judge_name} angle {row.angle_deg:+.1f} deg"
    return True, ""


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]


def summarise(rows: list[Episode]) -> str:
    """One markdown row per condition, in the record's format."""
    lines = [
        "| condition | successes / trials | entry offset median, p95 mm | angle median, p95 deg | cycle median s | failures |",
        "|---|---|---|---|---|---|",
    ]
    for condition in sorted({row.condition for row in rows}):
        group = [row for row in rows if row.condition == condition]
        cut = [row for row in group if row.judge == PRODUCTS[row.product].passed]
        offsets = [abs(row.entry_offset_mm) for row in cut]
        angles = [abs(row.angle_deg) for row in cut]
        cycles = [row.cycle_s for row in group if not math.isnan(row.cycle_s)]
        failures: dict[str, int] = {}
        for row in group:
            if not row.success:
                failures[row.failure] = failures.get(row.failure, 0) + 1
        failure_text = "; ".join(f"{name} x{count}" for name, count in sorted(failures.items())) or "none"
        lines.append(
            f"| {condition} | {sum(row.success for row in group)} / {len(group)} | "
            f"{statistics.median(offsets) if offsets else math.nan:.1f}, {_percentile(offsets, 0.95):.1f} | "
            f"{statistics.median(angles) if angles else math.nan:.2f}, {_percentile(angles, 0.95):.2f} | "
            f"{statistics.median(cycles) if cycles else math.nan:.2f} | {failure_text} |"
        )
    return "\n".join(lines)


def write_rows(path: Path, rows: list[Episode]) -> None:
    """Every episode as one CSV row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def main() -> None:
    """Run the requested conditions and print the summary table."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--product", choices=list(PRODUCTS), default="leg", help="the piece and its cell")
    parser.add_argument(
        "--approach", choices=["A", "B"], default="B", help="A carries the piece; B turns it on the belt"
    )
    parser.add_argument("--arrivals", choices=list(ARRIVAL_KINDS), default="square", help="the arrival draw")
    parser.add_argument("--arm", type=ArmModel, choices=list(ArmModel), required=True)
    parser.add_argument("--gripper", type=GripperModel, default=GripperModel.JAW_GEH6180)
    parser.add_argument("--tilt-deg", type=float, nargs="+", default=[0.0])
    parser.add_argument("--pieces", type=int, default=LEG_COUNT, help="how many of the 20 pieces, for a quick check")
    parser.add_argument(
        "--turn-acceleration",
        type=float,
        default=TURN_ACCELERATION_RADPS2,
        help="peak angular acceleration of the turn, rad/s^2; the file name carries it when it is not the default",
    )
    parser.add_argument("--only-piece", type=int, nargs="+", default=None, help="run just these piece indices")
    parser.add_argument(
        "--pose-source",
        choices=["truth", "camera"],
        default="truth",
        help="what the skills plan on: the simulator's true piece, or the camera pipeline's",
    )
    parser.add_argument(
        "--cog-checkpoint", type=Path, default=None, help="learned centre-of-gravity corrector for the camera path"
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    product = PRODUCTS[args.product]
    if args.pose_source == "camera" and product.camera_skill is None:
        parser.error(
            f"the {product.name} has no camera pipeline yet (Section 14.3 of the plan); use --pose-source truth"
        )

    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    pieces = product.population(LEG_COUNT, LEG_SEED)
    draws = arrivals(LEG_COUNT, args.arrivals, pieces, product)
    indices = args.only_piece if args.only_piece is not None else list(range(args.pieces))
    rows: list[Episode] = []
    print(
        f"git {sha}, {product.name}, belt {BELT_SPEED_MPS} m/s, arrivals {args.arrivals}, "
        f"{product.judge_name} at x = {ARRIVAL_KINDS[args.arrivals][1]} m, {len(indices)} pieces"
    )
    for tilt_deg in args.tilt_deg:
        for index in indices:
            row = run_episode(
                args.arm,
                args.gripper,
                math.radians(tilt_deg),
                index,
                pieces[index],
                draws[index],
                pose_source=args.pose_source,
                checkpoint=args.cog_checkpoint,
                approach=args.approach,
                kind=args.arrivals,
                turn_acceleration_radps2=args.turn_acceleration,
                product=product,
            )
            rows.append(row)
            print(
                f"{row.condition} {product.name} {index:2d} ({row.length_mm:.0f} mm, {row.mass_kg:.1f} kg, "
                f"{row.arrival_heading_deg:+.0f} deg): {'ok' if row.success else row.failure}; "
                + (
                    f"camera: datum {row.estimate_datum_error_mm:.0f} mm, heading {row.estimate_heading_error_deg:+.1f} deg, "
                    f"cog {row.estimate_cog_error_mm:.0f} mm off; "
                    if row.pose_source == "camera"
                    else ""
                )
                + f"grasp {row.acquire} (moved the datum point {row.grasp_shift_mm:.0f} mm; re-estimate {row.re_estimate}), "
                + f"orient {row.orient}, datum {row.datum_offset_mm:+.1f} mm, "
                f"{product.judge_name} {row.judge} {row.entry_offset_mm:+.1f} mm {row.angle_deg:+.1f} deg, "
                f"released x {row.released_at_x_m:.2f}"
                + (f", touched {row.collision} at {row.collision_at_s:.2f} s" if row.arm_collisions else "")
                + f", {row.wall_s:.1f} s",
                flush=True,
            )
    out = args.out or product.data_dir / (
        f"{args.approach}-{args.arm.value}-{args.gripper.value}-{args.pose_source}-{args.arrivals}"
        + ("" if args.turn_acceleration == TURN_ACCELERATION_RADPS2 else f"-accel{args.turn_acceleration:g}")
        + f"-{sha}.csv"
    )
    write_rows(out, rows)
    print(f"\nwrote {out}\n")
    print(summarise(rows))


if __name__ == "__main__":
    main()
