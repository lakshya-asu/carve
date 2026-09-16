r"""Run the pre-registered alignment experiment: each approach, arm and tilt on the same 20 legs.

The protocol, the success definition and the reported numbers are fixed in
experiments/2026-09-15-alignment-approaches.md. Each episode places one leg of
the population on the running belt with its centre of gravity at the arrival
point, runs the orient skills from ground-truth pose, returns the arm to its
ready pose, and lets the leg ride through the hold-down belt and the saw. The
saw's `CutResult` is the judge.

One row per episode goes to a CSV under experiments/data, and a summary table
per condition is printed for the record.

Usage:
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/measure/alignment_approaches.py \\
        --approach B --arm ur20 --tilt-deg 0 15 30
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/measure/alignment_approaches.py \\
        --approach B --arm sr20ia --tilt-deg 0
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
from applications.pork_leg_alignment.sim.product import HOCK_FRACTION, LegConfig, leg_population
from applications.pork_leg_alignment.sim.saw import CutOutcome, SawConfig
from applications.pork_leg_alignment.sim.scene import ArmMount, CellConfig
from applications.pork_leg_alignment.sim.sensing import CameraSpec
from applications.pork_leg_alignment.skills import (
    AcquireShank,
    EstimateLegFromCamera,
    EstimateLegFromGroundTruth,
    LegEstimate,
    PickAndPlace,
    RotateOnBelt,
    SelectShankGrasp,
)
from applications.pork_leg_alignment.skills.leg_estimate import estimate_from_ground_truth
from robotics.core.camera_frame import CameraFrameData
from robotics.core.skill_library import SUCCESS, SkillResult, run_skill
from robotics.hardware.arms import ArmModel
from robotics.hardware.cameras import GEMINI_335L, EdgeEffects, sense_depth
from robotics.hardware.grippers import GripperModel
from robotics.hardware.ik import solve_ik
from robotics.perception.learned_centre_of_gravity import LearnedCentreOfGravity

logger = logging.getLogger("alignment_approaches")

DATA_DIR = Path("experiments/data/2026-09-15-alignment-approaches")
LEG_COUNT = 20
LEG_SEED = 0
ARRIVAL_SEED = 20260915
# Arrival: centre of gravity here, y and heading drawn per leg.
ARRIVAL_X_M = -0.30
ARRIVAL_Y_RANGE_M = (0.40, 0.60)
ARRIVAL_YAW_RANGE_RAD = math.radians(35.0)
SQUARE_HEADING_RAD = -math.pi / 2
BELT_SPEED_MPS = 0.30
# Cell layout for the run (amended 2026-09-15, see the record): saw and
# hold-down 1.75 m down the belt from the six-axis mount, the hold-down's
# pressing section 0.5 m long so its lead-in starts at x = 1.11 m, 0.14 m past
# where the open jaws are when they have risen clear of a released leg; SCARA
# mount 0.35 m downstream so its 1.1 m reach covers the pick and the set-down.
SAW_X_M = 1.75
HOLD_DOWN_LENGTH_M = 0.50
SCARA_MOUNT_X_M = 0.35
# Where each arm waits between legs: over the open-edge side of the belt, where
# the legs are thin, tool down and jaws across the belt. A leg arrives with its
# ham on the far side, so an arm that waits here and swings to the shank never
# passes its open jaws over a ham; waiting mid-belt at y = 0.50, the SR-20iA
# swept its jaws through the ham of a 766 mm leg (2026-09-15). The height is
# the top of the SR-20iA's stroke at its mount, used for both arms.
READY_M = np.array([-0.10, 0.25, 0.90 + 0.21])
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
class Arrival:
    """One leg's arrival pose, centre of gravity at `ARRIVAL_X_M`."""

    y_m: float
    heading_rad: float


def arrivals(count: int) -> list[Arrival]:
    """The same arrival draw for every condition."""
    rng = np.random.default_rng(ARRIVAL_SEED)
    return [
        Arrival(
            y_m=float(rng.uniform(*ARRIVAL_Y_RANGE_M)),
            heading_rad=SQUARE_HEADING_RAD + float(rng.uniform(-ARRIVAL_YAW_RANGE_RAD, ARRIVAL_YAW_RANGE_RAD)),
        )
        for _ in range(count)
    ]


def park_ready(cell: Cell) -> None:
    """Move the arm to its ready pose at the allowed joint speeds and let it settle."""
    q = solve_ik(cell.model, cell.data, READY_M, READY_YAW_RAD, arm=cell.arm)
    speeds = np.asarray(cell.arm.max_joint_speed) * SPEED_FRACTION
    cell.move_arm(q, max(MIN_MOVE_S, float(np.max(np.abs(q - cell.arm_qpos) / speeds))))
    cell.step(seconds=0.2)


def place_by_centre_of_gravity(cell: Cell, arrival: Arrival) -> None:
    """Put the leg down so its centre of gravity, not its body origin, is at the arrival point.

    The centre of mass is read from the model at the nominal pose without
    stepping, then the leg is placed once at the corrected pose and settles
    there; placing it twice with a settle in between showed on video as the
    leg jumping back along the belt.
    """
    cell.place_product(ARRIVAL_X_M, arrival.y_m, arrival.heading_rad, settle_s=0.0)
    truth = cell.ground_truth()
    assert truth.centre_of_mass_m is not None
    shift = truth.centre_of_mass_m[:2] - np.array([truth.piece_pose.x_m, truth.piece_pose.y_m])
    cell.place_product(ARRIVAL_X_M - float(shift[0]), arrival.y_m - float(shift[1]), arrival.heading_rad, settle_s=0.0)


def cell_config(arm: ArmModel, leg: LegConfig, gripper: GripperModel, camera: bool = False) -> CellConfig:
    """The run's cell for one arm and one leg, with the depth camera when the pose comes from it."""
    mount = ArmMount(x_m=SCARA_MOUNT_X_M, y_m=1.10, z_m=1.10, yaw_rad=-math.pi / 2) if arm is ArmModel.SR20IA else None
    return CellConfig(
        belt_speed_mps=BELT_SPEED_MPS,
        leg=leg,
        saw=SawConfig(x_m=SAW_X_M),
        hold_down=HoldDownConfig(x_centre_m=SAW_X_M, length_m=HOLD_DOWN_LENGTH_M),
        arm=arm,
        arm_mount=mount,
        gripper=gripper,
        depth_cameras=(GEMINI_335L,) if camera else (),
        depth_camera_yaw_deg=90.0,
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

    condition: str
    approach: str
    pose_source: str
    arm: str
    gripper: str
    tilt_deg: float
    leg: int
    length_mm: float
    mass_kg: float
    arrival_y_m: float
    arrival_heading_deg: float
    estimate: str = ""
    estimate_hock_error_mm: float = math.nan
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
    meet_error_mm: float = math.nan
    opening_mm: float = math.nan
    tool_rise_mm: float = math.nan
    turn_deg: float = math.nan
    slip_mm: float = math.nan
    slip_deg: float = math.nan
    hock_offset_mm: float = math.nan
    heading_error_deg: float = math.nan
    released_at_x_m: float = math.nan
    cycle_s: float = math.nan
    arm_collisions: int = 0
    collision: str = ""
    collision_at_s: float = math.nan
    cut: str = ""
    entry_offset_mm: float = math.nan
    exit_offset_mm: float = math.nan
    cut_angle_deg: float = math.nan
    cut_drift_deg: float = math.nan
    cut_slip_mm: float = math.nan
    success: bool = False
    failure: str = ""
    wall_s: float = math.nan


def _evidence(result: SkillResult, key: str, scale: float = 1.0) -> float:
    return scale * float(result.evidence[key]) if key in result.evidence else math.nan


def estimate_errors(estimate: LegEstimate, truth: LegEstimate) -> dict[str, float]:
    """How far an estimate is from ground truth taken at the same moment, for the record."""
    carried = np.array([truth.belt_travel_m - estimate.belt_travel_m, 0.0, 0.0])
    hock = estimate.point_at(HOCK_FRACTION) + carried - truth.point_at(HOCK_FRACTION)
    centre = estimate.centre_of_gravity_m + carried - truth.centre_of_gravity_m
    return {
        "estimate_hock_error_mm": 1000 * float(np.linalg.norm(hock[:2])),
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
    leg: LegConfig,
    arrival: Arrival,
    pose_source: str = "truth",
    checkpoint: Path | None = None,
    approach: str = "B",
    cell_class: type[Cell] = Cell,
    on_cell: Callable[[Cell, Episode], None] | None = None,
) -> Episode:
    """One leg through approach B: estimate the leg, grasp, rotate on the belt, release, saw."""
    started = time.perf_counter()
    row = Episode(
        condition=f"{approach}-{arm.value}-{gripper.value}-tilt{math.degrees(tilt_rad):.0f}-{pose_source}",
        approach=approach,
        pose_source=pose_source,
        arm=arm.value,
        gripper=gripper.value,
        tilt_deg=math.degrees(tilt_rad),
        leg=leg_index,
        length_mm=1000 * leg.length_m,
        mass_kg=leg.mass_kg,
        arrival_y_m=arrival.y_m,
        arrival_heading_deg=math.degrees(arrival.heading_rad - SQUARE_HEADING_RAD),
    )
    camera = pose_source == "camera"
    cameras = (
        {CAMERA: CameraSpec(CAMERA, GEMINI_335L.width_px, GEMINI_335L.height_px, exposure_s=0.0)} if camera else {}
    )
    with cell_class(cell_config(arm, leg, gripper, camera=camera), cameras) as cell:
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
            if refused:
                row.estimate = refused
            else:
                estimated = run_skill(EstimateLegFromCamera(), cell, perceived)
        else:
            estimated = run_skill(EstimateLegFromGroundTruth(), cell, {})
        if estimated is not None:
            row.estimate = estimated.outcome
            if estimated.outcome == SUCCESS:
                errors = estimate_errors(estimated.outputs["leg_estimate"], estimate_from_ground_truth(cell))
                for key, value in errors.items():
                    setattr(row, key, value)
        selected = (
            run_skill(SelectShankGrasp(tilt_rad=tilt_rad), cell, estimated.outputs)
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
                    perceived, refused = pipeline.perceive(cell)
                    again = run_skill(EstimateLegFromCamera(), cell, perceived) if not refused else None
                    row.re_estimate = again.outcome if again is not None else f"kept first: {refused}"
                else:
                    again = run_skill(EstimateLegFromGroundTruth(), cell, {})
                    row.re_estimate = again.outcome
                planning = again.outputs["leg_estimate"] if again is not None and again.outcome == SUCCESS else before
                truth_now = estimate_from_ground_truth(cell)
                carried = np.array([truth_now.belt_travel_m - before.belt_travel_m, 0.0, 0.0])
                row.grasp_shift_mm = 1000 * float(
                    np.linalg.norm((before.point_at(HOCK_FRACTION) + carried - truth_now.point_at(HOCK_FRACTION))[:2])
                )
                orient_skill = PickAndPlace() if approach == "A" else RotateOnBelt()
                oriented = run_skill(
                    orient_skill, cell, {"leg_estimate": planning, **selected.outputs, **acquired.outputs}
                )
                row.flange_load_n = _evidence(oriented, "flange_load_n")
                row.moment_about_tool_nm = _evidence(oriented, "moment_about_tool_nm")
                row.inertia_about_tool_kgm2 = _evidence(oriented, "inertia_about_tool_kgm2")
                row.airborne = _evidence(oriented, "airborne")
                row.orient = oriented.outcome
                row.turn_deg = math.degrees(_evidence(oriented, "turn_rad"))
                row.slip_mm = _evidence(oriented, "slip_m", 1000)
                row.slip_deg = math.degrees(_evidence(oriented, "slip_rad"))
                row.hock_offset_mm = _evidence(oriented, "hock_offset_m", 1000)
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
        while cell.cut_result is None and cell.time_s < deadline:
            cell.step(seconds=0.02)
        result = cell.cut_result
        if result is None:
            row.cut = "no_result"
        else:
            row.cut = result.outcome.value
            row.entry_offset_mm = 1000 * result.offset_from_hock_m
            row.exit_offset_mm = 1000 * result.offset_at_exit_m
            row.cut_angle_deg = math.degrees(result.angle_rad)
            row.cut_drift_deg = math.degrees(result.yaw_drift_rad)
            row.cut_slip_mm = 1000 * result.slip_m
    row.success, row.failure = judge(row)
    row.wall_s = time.perf_counter() - started
    return row


def judge(row: Episode) -> tuple[bool, str]:
    """The record's success definition, and the first failure mode that applies."""
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
    if row.cut != CutOutcome.CUT.value:
        return False, f"saw: {row.cut}"
    if abs(row.entry_offset_mm) > 1000 * OFFSET_TOLERANCE_M or abs(row.exit_offset_mm) > 1000 * OFFSET_TOLERANCE_M:
        return False, f"cut offset {row.entry_offset_mm:+.1f} / {row.exit_offset_mm:+.1f} mm"
    if abs(row.cut_angle_deg) > math.degrees(ANGLE_TOLERANCE_RAD):
        return False, f"cut angle {row.cut_angle_deg:+.1f} deg"
    return True, ""


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]


def summarise(rows: list[Episode]) -> str:
    """One markdown row per condition, in the record's format."""
    lines = [
        "| condition | successes / trials | entry offset median, p95 mm | cut angle median, p95 deg | cycle median s | failures |",
        "|---|---|---|---|---|---|",
    ]
    for condition in sorted({row.condition for row in rows}):
        group = [row for row in rows if row.condition == condition]
        cut = [row for row in group if row.cut == CutOutcome.CUT.value]
        offsets = [abs(row.entry_offset_mm) for row in cut]
        angles = [abs(row.cut_angle_deg) for row in cut]
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
    parser.add_argument("--approach", choices=["A", "B"], default="B", help="A carries the leg; B turns it on the belt")
    parser.add_argument("--arm", type=ArmModel, choices=list(ArmModel), required=True)
    parser.add_argument("--gripper", type=GripperModel, default=GripperModel.JAW_GEH6180)
    parser.add_argument("--tilt-deg", type=float, nargs="+", default=[0.0])
    parser.add_argument("--legs", type=int, default=LEG_COUNT, help="how many of the 20 legs, for a quick check")
    parser.add_argument("--only-leg", type=int, nargs="+", default=None, help="run just these leg indices")
    parser.add_argument(
        "--pose-source",
        choices=["truth", "camera"],
        default="truth",
        help="what the skills plan on: the simulator's true leg, or the camera pipeline's",
    )
    parser.add_argument(
        "--cog-checkpoint", type=Path, default=None, help="learned centre-of-gravity corrector for the camera path"
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    legs = leg_population(LEG_COUNT, seed=LEG_SEED)
    draws = arrivals(LEG_COUNT)
    indices = args.only_leg if args.only_leg is not None else list(range(args.legs))
    rows: list[Episode] = []
    print(f"git {sha}, belt {BELT_SPEED_MPS} m/s, saw at x = {SAW_X_M} m, {len(indices)} legs")
    for tilt_deg in args.tilt_deg:
        for index in indices:
            row = run_episode(
                args.arm,
                args.gripper,
                math.radians(tilt_deg),
                index,
                legs[index],
                draws[index],
                pose_source=args.pose_source,
                checkpoint=args.cog_checkpoint,
                approach=args.approach,
            )
            rows.append(row)
            print(
                f"{row.condition} leg {index:2d} ({row.length_mm:.0f} mm, {row.mass_kg:.1f} kg, "
                f"{row.arrival_heading_deg:+.0f} deg): {'ok' if row.success else row.failure}; "
                + (
                    f"camera: hock {row.estimate_hock_error_mm:.0f} mm, heading {row.estimate_heading_error_deg:+.1f} deg, "
                    f"cog {row.estimate_cog_error_mm:.0f} mm off; "
                    if row.pose_source == "camera"
                    else ""
                )
                + f"grasp {row.acquire} (moved the hock {row.grasp_shift_mm:.0f} mm; re-estimate {row.re_estimate}), "
                + f"orient {row.orient}, hock {row.hock_offset_mm:+.1f} mm, "
                f"cut {row.cut} {row.entry_offset_mm:+.1f} mm {row.cut_angle_deg:+.1f} deg, "
                f"released x {row.released_at_x_m:.2f}"
                + (f", touched {row.collision} at {row.collision_at_s:.2f} s" if row.arm_collisions else "")
                + f", {row.wall_s:.1f} s",
                flush=True,
            )
    out = args.out or DATA_DIR / f"{args.approach}-{args.arm.value}-{args.gripper.value}-{args.pose_source}-{sha}.csv"
    write_rows(out, rows)
    print(f"\nwrote {out}\n")
    print(summarise(rows))


if __name__ == "__main__":
    main()
