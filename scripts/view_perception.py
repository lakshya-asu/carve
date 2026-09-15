r"""Record the ingestion chain running, drawn on the camera it is reading.

Two panes. On the left the cell, for context. On the right the overhead camera
with what perception concludes drawn on it: the mask it is given, the centroid
and long axis it estimates, the finger axis a parallel gripper would need, and
where the tracker says the product will be half a second later. Ground truth is
drawn alongside so the error is visible rather than tabulated.

The camera pane carries a display gain, set to unity now that the belt is white.
It was 1.7 while the belt was dark, and any gain is applied after the image
reaches perception, so nothing downstream ever sees it.

Record to a file:

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl \
        python scripts/view_perception.py --out perception.mp4 --seconds 20

Or watch it live in a window, which needs a display:

    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl DISPLAY=:0 \
        python scripts/view_perception.py --live --seconds 120

Live mode paces itself to real time and quits on q or escape. Rendering the
overhead camera at full resolution costs more than the simulation does, so a
slow machine will fall behind real time rather than skip: the clock in the
readout is simulation time and is the one to trust.
"""

from __future__ import annotations

import argparse
import logging
import math
import time
from pathlib import Path

import cv2
import imageio
import mujoco
import numpy as np

from meat_cell_sim.cell import Cell
from meat_cell_sim.contracts import axis_error_rad
from meat_cell_sim.frames import CameraPose, Intrinsics, world_to_pixel
from meat_cell_sim.perception import PerceptionRejectedError, estimate_from_depth, grip_axis_rad
from meat_cell_sim.product import LegConfig
from meat_cell_sim.scene import CellConfig
from meat_cell_sim.sensing import CameraSpec
from meat_cell_sim.tracking import BeltTracker

logger = logging.getLogger(__name__)

CAMERA = "overhead"
FRAME_RATE_HZ = 30.0
LEAD_TIME_S = 0.5
SPAWN_X_M = -0.85
# Past this the product has left the camera and would ride to the end of the
# belt, so a fresh one is placed upstream. A real line either picks it or sends
# it to a reject chute; neither is built yet.
RECYCLE_PAST_X_M = 0.30

# Colours are BGR: OpenCV draws in BGR and the frame is converted once at the end.
# The comment on each line is the colour it actually appears as, because reading
# a BGR triple as RGB is how the legend and the drawing ended up disagreeing.
TRUTH = (255, 255, 255)  # white
ESTIMATE = (60, 180, 245)  # amber
FINGERS = (245, 220, 110)  # cyan
PREDICTION = (120, 240, 140)  # green
REJECT = (90, 90, 245)  # red
PANEL = (24, 24, 24)
DISPLAY_GAIN = 1.0
DISPLAY_LIFT = 0
PANE_W, PANE_H = 800, 600
# ffmpeg wants both dimensions divisible by 16, so the readout strip is sized to
# make the composed frame land on it exactly rather than be silently resized.
STRIP_H = 120
TEXT = (235, 235, 235)
FONT = cv2.FONT_HERSHEY_DUPLEX


def _spawn(model: mujoco.MjModel, data: mujoco.MjData, rng: np.random.Generator, thickness_m: float) -> None:
    adr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "slab_free")]
    dof = model.jnt_dofadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "slab_free")]
    yaw = rng.uniform(-math.pi / 2, math.pi / 2)
    data.qpos[adr : adr + 7] = [
        SPAWN_X_M,
        0.50 + rng.uniform(-0.04, 0.04),
        0.90 + thickness_m,
        math.cos(yaw / 2),
        0.0,
        0.0,
        math.sin(yaw / 2),
    ]
    data.qvel[dof : dof + 6] = 0.0


def _axis_endpoints(x_m: float, y_m: float, yaw_rad: float, half_length_m: float) -> tuple[np.ndarray, np.ndarray]:
    direction = np.array([math.cos(yaw_rad), math.sin(yaw_rad)]) * half_length_m
    centre = np.array([x_m, y_m])
    return centre - direction, centre + direction


Colour = tuple[int, int, int]


def _to_pixel(intr: Intrinsics, cam: CameraPose, xy_m: np.ndarray, z_m: float) -> tuple[int, int] | None:
    try:
        pixel = world_to_pixel(intr, cam, np.array([xy_m[0], xy_m[1], z_m]))
    except ValueError:
        return None
    return round(float(pixel[0])), round(float(pixel[1]))


def _draw_cross(image: np.ndarray, point: tuple[int, int] | None, colour: Colour, size: int = 14) -> None:
    if point is None:
        return
    x, y = point
    cv2.line(image, (x - size, y), (x + size, y), colour, 2, cv2.LINE_AA)
    cv2.line(image, (x, y - size), (x, y + size), colour, 2, cv2.LINE_AA)


def _draw_segment(
    image: np.ndarray, a: tuple[int, int] | None, b: tuple[int, int] | None, colour: Colour, width: int
) -> None:
    if a is not None and b is not None:
        cv2.line(image, a, b, colour, width, cv2.LINE_AA)


def _readout(lines: list[tuple[str, str, Colour]], width: int, height: int) -> np.ndarray:
    """Readout strip under the panes. Labels dim, values bright, so the eye finds the numbers."""
    strip = np.full((height, width, 3), PANEL, dtype=np.uint8)
    columns = 4
    per_column = max(1, -(-len(lines) // columns))
    for i, (label, value, colour) in enumerate(lines):
        x = 22 + (i // per_column) * (width // columns)
        y = 30 + (i % per_column) * 26
        cv2.putText(strip, label, (x, y), FONT, 0.44, (145, 145, 145), 1, cv2.LINE_AA)
        cv2.putText(strip, value, (x + 118, y), FONT, 0.48, colour, 1, cv2.LINE_AA)
    return strip


def _brighten(image: np.ndarray) -> np.ndarray:
    """Display-only gain, applied after perception has already read the frame."""
    return cv2.convertScaleAbs(image, alpha=DISPLAY_GAIN, beta=DISPLAY_LIFT)


def _label(image: np.ndarray, text: str) -> None:
    cv2.putText(image, text, (16, 30), FONT, 0.55, (235, 235, 235), 1, cv2.LINE_AA)


# How far off the belt axis a hand-placed leg arrives. Operators lay them
# roughly along the belt: a 722 mm leg square across a 700 mm belt would hang
# off both edges and fall, which is not a case the line produces.
SPAWN_YAW_LIMIT_RAD = math.radians(35.0)


def _spawn(cell: Cell, rng: np.random.Generator, outline_offset_m: float) -> None:
    """Put a fresh product at the top of the belt, positioned by its outline."""
    yaw = rng.uniform(-SPAWN_YAW_LIMIT_RAD, SPAWN_YAW_LIMIT_RAD)
    cell.place_product(
        SPAWN_X_M - outline_offset_m * math.cos(yaw),
        0.50 + rng.uniform(-0.05, 0.05) - outline_offset_m * math.sin(yaw),
        yaw,
    )


def _require_gui() -> None:
    """Fail early and usefully if this OpenCV build cannot open a window.

    The project pins `opencv-python-headless` on purpose, so that the same
    environment runs on a machine with no display. That build has no GUI at all
    and `namedWindow` raises a rebuild-the-library error that says nothing about
    the real choice. Recording and playing back is the supported path.
    """
    if not hasattr(cv2, "namedWindow"):  # pragma: no cover - depends on the build
        raise RuntimeError("this OpenCV build has no GUI")
    try:
        cv2.namedWindow("__probe__", cv2.WINDOW_NORMAL)
        cv2.destroyWindow("__probe__")
    except cv2.error as missing_gui:
        raise RuntimeError(
            "opencv-python-headless cannot open a window, and it is pinned that way so this "
            "environment also runs where there is no display. Record instead and play the file:\n"
            "  python scripts/view_perception.py --out perception.mp4 --seconds 30\n"
            "To get a live window, swap the dependency for the GUI build:\n"
            "  pip uninstall -y opencv-python-headless && pip install opencv-python"
        ) from missing_gui


def run(out: Path | None, seconds: float, belt_speed_mps: float, seed: int, live: bool, leg: bool) -> int:
    """Record or show the overhead camera with the perception and tracking overlay."""
    config = CellConfig(belt_speed_mps=belt_speed_mps, leg=LegConfig() if leg else None)
    rng = np.random.default_rng(seed)
    # A leg's body origin sits in the ham, so spawning "at x" would leave its
    # trotter half a metre downstream. Spawn by the outline instead.
    outline_offset = config.leg.outline_centre_m if config.leg is not None else 0.0

    writer = None if out is None else imageio.get_writer(out, fps=int(FRAME_RATE_HZ), macro_block_size=None)
    window = "meat cell perception"
    if live:
        _require_gui()
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window, 1600, 720)
    written = 0
    frame_period_s = 1.0 / FRAME_RATE_HZ
    next_due = time.monotonic()

    scene_renderer = None
    with Cell(config, {CAMERA: CameraSpec(CAMERA, 1280, 960, exposure_s=0.004)}) as cell:
        cell.reset()
        _spawn(cell, rng, outline_offset)
        model, data = cell.model, cell.data
        intr = cell.sensors.intrinsics(CAMERA)
        steps_per_frame = max(1, round(1.0 / (FRAME_RATE_HZ * model.opt.timestep)))
        tracker = BeltTracker()

        scene_renderer = mujoco.Renderer(model, PANE_H, PANE_W)
        scene_camera = mujoco.MjvCamera()
        mujoco.mjv_defaultFreeCamera(model, scene_camera)
        scene_camera.lookat[:] = [-0.25, 0.35, 0.95]
        scene_camera.distance, scene_camera.azimuth, scene_camera.elevation = 2.0, 145, -26

        for _ in range(int(seconds * FRAME_RATE_HZ)):
            observation, frame = cell.observe(CAMERA)
            assert frame is not None
            truth = cell.ground_truth(CAMERA, stamp_s=frame.stamp_s)
            image = _brighten(cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR))
            top_z = truth.piece_top_z_m
            lines: list[tuple[str, str, Colour]] = [
                ("time", f"{observation.stamp_s:6.2f} s", TEXT),
                ("belt", f"{observation.belt_speed_mps * 1000:6.1f} mm/s", TEXT),
                ("encoder", f"{observation.belt_travel_m:6.3f} m", TEXT),
            ]

            if truth.piece_mask is not None and truth.piece_mask.any():
                contours, _ = cv2.findContours(
                    truth.piece_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                cv2.drawContours(image, contours, -1, TRUTH, 2, cv2.LINE_AA)
                _draw_cross(image, _to_pixel(intr, frame.camera, truth.piece_pose.xy_m, top_z), TRUTH, 12)

            rejected_reason = ""
            estimate = None
            if truth.piece_mask is not None and truth.piece_mask.any():
                try:
                    estimate = estimate_from_depth(truth.piece_mask, frame)
                except PerceptionRejectedError as rejected:
                    rejected_reason = str(rejected).split(";")[0]
                    lines.append(("perception", "rejected", REJECT))

            if estimate is not None:
                tracker.update(estimate, observation)
                pose = estimate.pose
                a, b = _axis_endpoints(pose.x_m, pose.y_m, pose.yaw_rad, estimate.length_m / 2)
                _draw_segment(
                    image, _to_pixel(intr, frame.camera, a, top_z), _to_pixel(intr, frame.camera, b, top_z), ESTIMATE, 3
                )
                grip = grip_axis_rad(estimate)
                ga, gb = _axis_endpoints(pose.x_m, pose.y_m, grip, estimate.width_m / 2 + 0.035)
                _draw_segment(
                    image,
                    _to_pixel(intr, frame.camera, ga, top_z),
                    _to_pixel(intr, frame.camera, gb, top_z),
                    FINGERS,
                    3,
                )
                _draw_cross(image, _to_pixel(intr, frame.camera, pose.xy_m, top_z), ESTIMATE, 18)

                error_mm = 1000 * math.hypot(pose.x_m - truth.piece_pose.x_m, pose.y_m - truth.piece_pose.y_m)
                axis_deg = math.degrees(axis_error_rad(pose.yaw_rad, truth.piece_pose.yaw_rad))
                lines += [
                    ("position", f"{pose.x_m:+.3f} {pose.y_m:+.3f} m", ESTIMATE),
                    ("heading", f"{math.degrees(pose.yaw_rad):+6.1f} deg", ESTIMATE),
                    ("confidence", f"{estimate.confidence:6.3f}", ESTIMATE),
                    ("error", f"{error_mm:6.3f} mm", TEXT),
                    ("axis error", f"{axis_deg:6.3f} deg", TEXT),
                ]

                state = tracker.state
                if state.samples >= 4:
                    predicted = tracker.predict(state.last_stamp_s + LEAD_TIME_S)
                    point = _to_pixel(intr, frame.camera, predicted.xy_m, top_z)
                    if point is not None:
                        cv2.circle(image, point, 22, PREDICTION, 3, cv2.LINE_AA)
                        cv2.putText(
                            image,
                            f"+{LEAD_TIME_S:.1f}s",
                            (point[0] + 28, point[1] + 7),
                            FONT,
                            0.55,
                            PREDICTION,
                            1,
                            cv2.LINE_AA,
                        )
                    lines += [
                        ("slip", f"{state.slip_mps * 1000:+6.2f} mm/s", TEXT),
                        ("frames", f"{state.samples:6d}", TEXT),
                    ]

            camera_pane = cv2.resize(image, (PANE_W, PANE_H), interpolation=cv2.INTER_AREA)
            _label(camera_pane, "overhead camera, 1280 x 960")
            if rejected_reason:
                cv2.rectangle(camera_pane, (0, 0), (PANE_W - 1, PANE_H - 1), REJECT, 3)
                cv2.putText(
                    camera_pane, f"REJECTED  {rejected_reason}", (16, PANE_H - 18), FONT, 0.5, REJECT, 1, cv2.LINE_AA
                )

            scene_renderer.update_scene(data, scene_camera)
            scene_pane = cv2.cvtColor(scene_renderer.render(), cv2.COLOR_RGB2BGR)
            _label(scene_pane, "the cell")

            legend = (
                "white truth    amber estimated centroid and long axis    "
                "cyan finger axis    green predicted position in 0.5 s"
            )
            strip = _readout(lines, PANE_W * 2, STRIP_H)
            cv2.putText(strip, legend, (22, STRIP_H - 14), FONT, 0.45, (150, 150, 150), 1, cv2.LINE_AA)
            composed = np.vstack([np.hstack([scene_pane, camera_pane]), strip])
            if writer is not None:
                writer.append_data(cv2.cvtColor(composed, cv2.COLOR_BGR2RGB))
            written += 1
            if live:
                cv2.imshow(window, composed)
                next_due += frame_period_s
                wait_ms = max(1, int(1000 * (next_due - time.monotonic())))
                if cv2.waitKey(wait_ms) in (ord("q"), 27):
                    break

            cell.step(steps_per_frame)
            if cell.product_x_m > RECYCLE_PAST_X_M:
                _spawn(cell, rng, outline_offset)
                tracker.reset()

    if scene_renderer is not None:
        scene_renderer.close()
    if writer is not None:
        writer.close()
        logger.info("wrote %s (%d frames, %.1f s)", out, written, written / FRAME_RATE_HZ)
    if live:
        cv2.destroyWindow(window)
    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=None, help="write an mp4 here")
    parser.add_argument("--live", action="store_true", help="show a window instead of, or as well as, writing")
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--belt-speed", type=float, default=0.30, help="metres per second")
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--leg", action="store_true", help="run whole pork legs instead of the rigid slab")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.out is None and not args.live:
        parser.error("nothing to do: pass --out to record, --live to watch, or both")
    return run(args.out, args.seconds, args.belt_speed, args.seed, args.live, args.leg)


if __name__ == "__main__":
    raise SystemExit(main())
