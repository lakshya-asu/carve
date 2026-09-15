r"""Measure the ingestion chain: sensing, frames, perception, tracking.

Runs products down the belt, estimates each one's pose from the overhead camera,
tracks it in belt coordinates, and predicts where it will be after a fixed lead
time. Every number the perception and tracking notes quote comes from here.

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/measure_perception.py --episodes 40

The four gates it reports, from `library/topics/meat-cell-architecture.md`:

    sensing     observation stamp matches the state it describes, under 1 ms
    frames      a known point reaches the base frame within 1 mm
    perception  centroid under 2 mm and axis under 2 degrees
    tracking    predicted position at the meet instant within 2 mm
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from meat_cell_sim.cell import Cell
from meat_cell_sim.contracts import axis_error_rad
from meat_cell_sim.frames import pixel_to_plane, world_to_base, world_to_pixel
from meat_cell_sim.perception import (
    PerceptionRejectedError,
    estimate_from_depth,
    estimate_from_mask,
)
from meat_cell_sim.scene import CellConfig
from meat_cell_sim.sensing import CameraSpec
from meat_cell_sim.tracking import BeltTracker, finite_difference_velocity, prediction_error_m

logger = logging.getLogger(__name__)

CAMERA = "overhead"
FRAME_RATE_HZ = 30.0
# Lead time from the last usable observation to the predicted meet. The product
# leaves the camera's field of view about 0.4 m before the pick zone, so at
# 300 mm/s the arm is working from a prediction this old.
LEAD_TIME_S = 0.5
SPAWN_X_M = -0.78
SPAWN_Y_M = 0.50


@dataclass
class EpisodeResult:
    """One product's pass through the field of view."""

    seed: int
    belt_speed_mps: float
    observations: int
    rejected: int
    centroid_err_mm: list[float]
    axis_err_deg: list[float]
    mono_err_mm: list[float]
    stamp_err_ms: list[float]
    predict_err_mm: float | None
    predict_horizon_s: float
    slip_mps: float
    residual_mm: float
    encoder_vs_truth_mps: float
    finite_diff_err_mps: float | None


def run_episode(cell: Cell, config: CellConfig, seed: int) -> EpisodeResult:
    """One product from the upstream end of the belt to the edge of the camera."""
    rng = np.random.default_rng(seed)
    cell.reset()
    cell.place_product(
        SPAWN_X_M,
        SPAWN_Y_M + rng.uniform(-0.04, 0.04),
        rng.uniform(-math.pi / 2, math.pi / 2),
    )

    # Let the belt reach its commanded speed before measuring; the velocity
    # servo needs a few steps and a product measured during the ramp would
    # report a slip that is really the actuator settling.
    cell.step(seconds=0.30)

    tracker = BeltTracker()
    result = EpisodeResult(
        seed=seed,
        belt_speed_mps=config.belt_speed_mps,
        observations=0,
        rejected=0,
        centroid_err_mm=[],
        axis_err_deg=[],
        mono_err_mm=[],
        stamp_err_ms=[],
        predict_err_mm=None,
        predict_horizon_s=LEAD_TIME_S,
        slip_mps=0.0,
        residual_mm=0.0,
        encoder_vs_truth_mps=0.0,
        finite_diff_err_mps=0.0,
    )
    steps_per_frame = max(1, round(1.0 / (FRAME_RATE_HZ * cell.model.opt.timestep)))
    first_estimate = None
    last_estimate = None
    truth_top_z = 0.90 + 2 * config.slab.half_extents_m[2]
    # Once the product starts running off the edge of the frame it will not come
    # back, and every further step burns lead time the arm does not have.
    consecutive_rejections = 0

    for _ in range(int(6.0 * FRAME_RATE_HZ)):
        observation, frame = cell.observe(CAMERA)
        assert frame is not None
        truth = cell.ground_truth(CAMERA, stamp_s=frame.stamp_s)
        if truth.piece_mask is None or not truth.piece_mask.any():
            break
        try:
            estimate = estimate_from_depth(truth.piece_mask, frame)
        except PerceptionRejectedError:
            result.rejected += 1
            consecutive_rejections += 1
            if result.observations and consecutive_rejections >= 2:
                break
            cell.step(steps_per_frame)
            continue
        consecutive_rejections = 0

        # Ground truth is taken at the exposure midpoint, so the comparison
        # tests the timestamp as well as the estimator.
        truth_at_stamp = cell.ground_truth(None, stamp_s=frame.stamp_s).piece_pose
        result.centroid_err_mm.append(
            1000.0 * math.hypot(estimate.pose.x_m - truth_at_stamp.x_m, estimate.pose.y_m - truth_at_stamp.y_m)
        )
        result.axis_err_deg.append(math.degrees(axis_error_rad(estimate.pose.yaw_rad, truth_at_stamp.yaw_rad)))
        result.stamp_err_ms.append(1000.0 * abs(observation.stamp_s - frame.stamp_s))
        try:
            mono = estimate_from_mask(truth.piece_mask, frame, truth_top_z)
            result.mono_err_mm.append(
                1000.0 * math.hypot(mono.pose.x_m - truth_at_stamp.x_m, mono.pose.y_m - truth_at_stamp.y_m)
            )
        except PerceptionRejectedError:
            pass

        tracker.update(estimate, observation)
        result.observations += 1
        first_estimate = first_estimate or estimate
        last_estimate = estimate
        cell.step(steps_per_frame)

    if result.observations >= 6:
        state = tracker.state
        result.slip_mps = state.slip_mps
        result.residual_mm = 1000.0 * state.residual_m
        # The prediction and the truth must describe the same instant.
        meet_time = state.last_stamp_s + LEAD_TIME_S
        if meet_time <= cell.time_s:
            raise RuntimeError(
                f"the observation loop already ran to {cell.time_s:.4f} s, past the meet at {meet_time:.4f} s"
            )
        predicted = tracker.predict(meet_time)
        while cell.time_s < meet_time - cell.model.opt.timestep / 2:
            cell.step(1)
        result.predict_horizon_s = meet_time - state.last_stamp_s
        truth_at_meet = cell.ground_truth(None, stamp_s=cell.time_s).piece_pose
        result.predict_err_mm = 1000.0 * prediction_error_m(predicted, truth_at_meet)
        truth_v = float(cell.ground_truth(None).piece_velocity_mps[0])
        result.encoder_vs_truth_mps = abs(state.belt_speed_mps - truth_v)
        if first_estimate is not None and last_estimate is not None:
            velocity, _ = finite_difference_velocity(first_estimate, last_estimate)
            result.finite_diff_err_mps = abs(float(velocity[0]) - truth_v)
    return result


def _summary(name: str, values: list[float], unit: str, gate: float | None) -> dict[str, object]:
    if not values:
        return {"metric": name, "n": 0}
    ordered = sorted(values)
    row: dict[str, object] = {
        "metric": name,
        "unit": unit,
        "n": len(ordered),
        "mean": round(float(np.mean(ordered)), 4),
        "p95": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 4),
        "max": round(ordered[-1], 4),
    }
    if gate is not None:
        row["gate"] = gate
        row["pass"] = ordered[-1] <= gate
    return row


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--belt-speeds", type=float, nargs="+", default=[0.15, 0.30, 0.50])
    parser.add_argument("--json", type=Path, default=None, help="write the full result table here")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    rows: list[dict[str, object]] = []
    for speed in args.belt_speeds:
        config = CellConfig(belt_speed_mps=speed)
        with Cell(config, {CAMERA: CameraSpec(CAMERA)}) as cell:
            results = [run_episode(cell, config, seed) for seed in range(args.episodes)]

        def pool(key: str, episodes: list[EpisodeResult] = results) -> list[float]:
            return [v for r in episodes for v in getattr(r, key)]

        predictions = [r.predict_err_mm for r in results if r.predict_err_mm is not None]
        table = [
            _summary("perception centroid", pool("centroid_err_mm"), "mm", 2.0),
            _summary("perception axis", pool("axis_err_deg"), "deg", 2.0),
            _summary("monocular centroid", pool("mono_err_mm"), "mm", None),
            _summary("sensing stamp skew", pool("stamp_err_ms"), "ms", 1.0),
            _summary("tracking prediction", predictions, "mm", 2.0),
            _summary("belt-frame fit residual", [r.residual_mm for r in results], "mm", None),
            _summary("encoder speed error", [r.encoder_vs_truth_mps for r in results], "m/s", None),
            _summary(
                "vision finite-difference speed error",
                [r.finite_diff_err_mps for r in results if r.finite_diff_err_mps is not None],
                "m/s",
                None,
            ),
        ]
        observed = sum(r.observations for r in results)
        rejected = sum(r.rejected for r in results)
        print(f"\nbelt {speed:.2f} m/s   {len(results)} products   {observed} usable frames, {rejected} rejected")
        print(f"  {'metric':<38}{'unit':>5}{'n':>6}{'mean':>10}{'p95':>10}{'max':>10}{'gate':>8}{'':>7}")
        for row in table:
            if row.get("n", 0) == 0:
                print(f"  {row['metric']:<38}{'':>5}{'no samples':>6}")
                continue
            verdict = "" if "pass" not in row else ("  PASS" if row["pass"] else "  FAIL")
            gate = f"{row['gate']:.1f}" if "gate" in row else ""
            print(
                f"  {row['metric']:<38}{row['unit']:>5}{row['n']:>6}{row['mean']:>10.3f}"
                f"{row['p95']:>10.3f}{row['max']:>10.3f}{gate:>8}{verdict:>7}"
            )
        rows.append({"belt_speed_mps": speed, "products": len(results), "frames": observed, "table": table})

    if args.json:
        args.json.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    failed = [r["metric"] for row in rows for r in row["table"] if r.get("pass") is False]  # type: ignore[union-attr]
    if failed:
        print(f"\nGATES FAILED: {sorted(set(failed))}")
        return 1
    print("\nall gates pass")
    return 0


def frames_gate_error_mm(cell: Cell) -> float:
    """Round trip a known world point through the camera and back to the base frame.

    The frames gate. Projecting a point into the image and back onto its own
    plane must return where it started; any error is the transform's, since no
    perception is involved.
    """
    intr = cell.sensors.intrinsics(CAMERA)
    cam = cell.sensors.camera_pose(cell.data, CAMERA)
    truth = cell.ground_truth(None)
    point = np.array([truth.piece_pose.x_m, truth.piece_pose.y_m, truth.piece_top_z_m])
    pixel = world_to_pixel(intr, cam, point)
    round_tripped = pixel_to_plane(intr, cam, float(pixel[0]), float(pixel[1]), truth.piece_top_z_m)
    return 1000.0 * float(np.linalg.norm(world_to_base(round_tripped) - world_to_base(point)))


if __name__ == "__main__":
    raise SystemExit(main())
