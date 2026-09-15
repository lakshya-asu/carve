"""Record one captioned video per test run on 2026-09-14, so each can be reviewed by eye.

Every video says on screen what is being tested, what counts as a pass, and what
happened, including tests where a skill refused to move because a condition it
checks first did not hold. The saw videos come from scripts/view/saw.py; this
script records the arm reach, the grippers on their own, and each grasp on a leg.

Usage:
    env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python scripts/view/grasp_test_videos.py
"""

from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path

import cv2
import imageio.v2 as imageio
import mujoco
import numpy as np

from applications.pork_leg_alignment.sim.cell import Cell
from applications.pork_leg_alignment.sim.product import LegConfig
from applications.pork_leg_alignment.sim.scene import CellConfig
from applications.pork_leg_alignment.skills import (
    AcquireShank,
    AcquireTrotterEnd,
    EstimateLegFromGroundTruth,
    SelectShankGrasp,
    SelectTrotterEndGrasp,
)
from robotics.core.skill_library import SUCCESS, Skill, SkillResult, run_skill
from robotics.hardware.arms import ArmModel
from robotics.hardware.grippers import GRIPPER_ASSETS, GRIPPER_SPECS, GripperModel, _finger_joint_addresses
from robotics.hardware.ik import UnreachableError, solve_ik

logger = logging.getLogger("record_test_videos")

WIDTH_PX, HEIGHT_PX, FPS = 960, 540, 30
BELT_TOP_Z_M = 0.90
BLADE_PLANE_Y_M = 0.12
PART_RADIUS_M = 0.045
PAD_FRICTION = 0.5

OUTCOME_MEANING = {
    SUCCESS: "PASS: gripped, and the part rose with the tool",
    "precondition_failed": "REFUSED: a check before moving failed, so the arm never moved",
    "unreachable": "FAIL: the arm has no joint solution for a pose it needs",
    "closed_on_nothing": "FAIL: the fingers closed past the part",
    "slipped": "FAIL: the tool rose but the part stayed behind",
    "lift_not_achieved": "FAIL: the arm could not raise the tool under the load",
    "success_not_verified": "FAIL: the skill thought it worked but its checks disagreed",
}


def _camera(lookat: list[float], distance: float, azimuth: float, elevation: float) -> mujoco.MjvCamera:
    camera = mujoco.MjvCamera()
    camera.lookat[:] = lookat
    camera.distance = distance
    camera.azimuth = azimuth
    camera.elevation = elevation
    return camera


class Film:
    """One video file: a renderer, a camera and the caption burned into every frame."""

    def __init__(self, model: mujoco.MjModel, path: Path, camera: mujoco.MjvCamera) -> None:
        """Open the renderer and the video writer."""
        self.renderer = mujoco.Renderer(model, HEIGHT_PX, WIDTH_PX)
        # H.264 in yuv420p: OpenCV's mp4v (MPEG-4 Part 2) files do not play in browsers,
        # and the videos are published on the plan page.
        self.writer = imageio.get_writer(path, fps=FPS, codec="libx264", pixelformat="yuv420p", macro_block_size=1)
        self.camera = camera
        self.caption: list[str] = []
        self.path = path

    def frame(self, data: mujoco.MjData) -> None:
        """Render and write one frame with the current caption."""
        self.renderer.update_scene(data, self.camera)
        image = cv2.cvtColor(self.renderer.render(), cv2.COLOR_RGB2BGR)
        for row, text in enumerate(self.caption):
            y = 26 + 24 * row
            cv2.putText(image, text, (14, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(image, text, (14, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1, cv2.LINE_AA)
        self.writer.append_data(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    def hold(self, data: mujoco.MjData, seconds: float) -> None:
        """Write the same scene for `seconds`, so a caption can be read."""
        for _ in range(round(seconds * FPS)):
            self.frame(data)

    def close(self) -> None:
        """Finish the file."""
        self.writer.close()
        self.renderer.close()
        logger.info("wrote %s", self.path)


class FilmedCell(Cell):
    """A cell that writes a frame every 1/FPS of simulated time while anything steps it."""

    film: Film | None = None
    _steps_since_frame = 0

    def step(self, steps: int = 1, seconds: float | None = None) -> None:
        """Step as `Cell.step` does, filming as it goes."""
        if seconds is not None:
            steps = max(1, round(seconds / self.model.opt.timestep))
        per_frame = max(1, round(1.0 / (FPS * self.model.opt.timestep)))
        for _ in range(steps):
            super().step(1)
            self._steps_since_frame += 1
            if self.film is not None and self._steps_since_frame >= per_frame:
                self._steps_since_frame = 0
                self.film.frame(self.data)


def film_reach(arm: ArmModel, path: Path) -> None:
    """Move the tool to belt corners and centre at shank height and at clearance height."""
    leg = LegConfig()
    with FilmedCell(CellConfig(belt_speed_mps=0.0, leg=leg, arm=arm)) as cell:
        cell.reset()
        # A leg lies upstream of every test point so the scale of the cell is visible; it is not part of the test.
        heading = -math.pi / 2
        cell.place_product(
            -1.15 - leg.outline_centre_m * math.cos(heading), 0.42 - leg.outline_centre_m * math.sin(heading), heading
        )
        film = Film(cell.model, path, _camera([0.3, 0.6, 1.0], 3.2, 215.0, -30.0))
        cell.film = film
        points = [(-0.4, 0.25), (1.0, 0.25), (1.0, 0.75), (-0.4, 0.75), (0.3, 0.50)]
        for label, height in (("shank height, 50 mm above the belt", 0.05), ("clearance, 350 mm above the belt", 0.35)):
            for index, (x, y) in enumerate(points):
                film.caption = [
                    f"TEST: can the {arm.value} put its tool over the belt, pointing down?",
                    "PASS for a point = a joint solution exists and the arm gets there (the leg upstream is for scale)",
                    f"{label}: point {index + 1} of {len(points)}, x {x:+.2f} m, y {y:.2f} m",
                ]
                try:
                    q = solve_ik(
                        cell.model, cell.data, np.array([x, y, BELT_TOP_Z_M + height]), -math.pi / 2, arm=cell.arm
                    )
                except UnreachableError:
                    film.caption.append("UNREACHABLE: no joint solution, the arm stays put")
                    film.hold(cell.data, 1.5)
                    continue
                film.caption.append("reachable: moving there")
                speeds = 0.5 * np.asarray(cell.arm.max_joint_speed)
                cell.move_arm(q, max(0.8, float(np.max(np.abs(q - cell.arm_qpos) / speeds))))
                cell.step(seconds=0.4)
        film.close()


def film_gripper(gripper: GripperModel, path: Path) -> None:
    """The gripper alone: open, close on a 90 mm part, then pull the part until it slips."""
    spec = mujoco.MjSpec()
    spec.compiler.degree = False
    spec.option.gravity = [0.0, 0.0, 0.0]
    spec.option.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    spec.option.cone = mujoco.mjtCone.mjCONE_ELLIPTIC
    spec.option.noslip_iterations = 3
    spec.visual.global_.offwidth = WIDTH_PX
    spec.visual.global_.offheight = HEIGHT_PX
    mount = spec.worldbody.add_site(name="mount")
    spec.attach(mujoco.MjSpec.from_file(str(GRIPPER_ASSETS / GRIPPER_SPECS[gripper].asset)), prefix="g_", site=mount)
    spec.worldbody.add_light(pos=[0.5, -0.5, 1.0], dir=[-0.5, 0.5, -1.0], diffuse=[0.8, 0.8, 0.8])
    tcp_z = float(spec.site("g_tcp").pos[2])
    along_jaw = gripper is GripperModel.JAW_GEH6180
    part = spec.worldbody.add_body(
        name="part", pos=[0.0, 0.0, tcp_z], quat=[0.7071068, 0.0, 0.7071068, 0.0] if along_jaw else [1, 0, 0, 0]
    )
    part.add_freejoint()
    part.add_geom(
        name="part_geom",
        type=mujoco.mjtGeom.mjGEOM_CAPSULE if along_jaw else mujoco.mjtGeom.mjGEOM_CYLINDER,
        size=[PART_RADIUS_M, 0.05, 0.0],
        mass=1.0,
        condim=4,
        friction=[PAD_FRICTION, 0.05, 0.001],
        rgba=[0.87, 0.71, 0.68, 1.0],
    )
    model = spec.compile()
    data = mujoco.MjData(model)
    grip = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "g_grip")
    high = float(model.jnt_range[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "g_finger_left_joint")][1])
    rated = GRIPPER_SPECS[gripper].rated_force_n
    film = Film(model, path, _camera([0.0, 0.0, tcp_z], 0.7, 35.0, -20.0))
    headline = f"TEST: {gripper.value} alone, on a 90 mm shank-sized part, gravity off"
    per_frame = max(1, round(1.0 / (FPS * model.opt.timestep)))

    def run(seconds: float) -> None:
        for step in range(round(seconds / model.opt.timestep)):
            mujoco.mj_step(model, data)
            if step % per_frame == 0:
                film.frame(data)

    def squeeze_n() -> float:
        geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "part_geom")
        wrench, total = np.zeros(6), 0.0
        for i in range(data.ncon):
            if geom in (data.contact[i].geom1, data.contact[i].geom2):
                mujoco.mj_contactForce(model, data, i, wrench)
                total += float(wrench[0])
        return total

    for address, ratio in _finger_joint_addresses(model):
        data.qpos[address] = ratio * high
    data.ctrl[grip] = high
    film.caption = [headline, "step 1: open fully"]
    run(0.8)
    film.caption = [headline, f"step 2: close. PASS = squeeze within 15% of the rated {rated:.0f} N"]
    data.ctrl[grip] = 0.0
    run(0.8)
    squeeze = squeeze_n()
    film.caption = [headline, f"step 2 result: squeeze {squeeze:.0f} N against {rated:.0f} N rated"]
    film.hold(data, 1.5)

    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "part")
    axis = data.xmat[body].reshape(3, 3)[:, 2].copy()
    start = data.xpos[body].copy()
    expected = PAD_FRICTION * rated
    steps = round(3.0 / model.opt.timestep)
    slipped_at = None
    for step in range(steps):
        force = 2.0 * expected * step / steps
        data.xfrc_applied[body, :3] = force * axis
        mujoco.mj_step(model, data)
        moved = float(np.dot(data.xpos[body] - start, axis))
        if step % per_frame == 0:
            film.caption = [
                headline,
                f"step 3: pull along the part. PASS = holds to 80% of friction x squeeze = {0.8 * expected:.0f} N",
                f"pull {force:5.0f} N, part moved {1000 * moved:5.2f} mm",
            ]
            film.frame(data)
        if moved > 0.002:
            slipped_at = force
            break
    verdict = "PASS" if slipped_at is not None and slipped_at >= 0.8 * expected else "FAIL"
    film.caption = [
        headline,
        f"step 3 result: slipped at {slipped_at:.0f} N against {0.8 * expected:.0f} N needed: {verdict}"
        if slipped_at is not None
        else "step 3 result: never slipped at twice the rated friction",
    ]
    data.xfrc_applied[body] = 0.0
    film.hold(data, 2.0)
    film.close()


def film_grasp(title: str, arm: ArmModel, gripper: GripperModel, trotter_end: bool, path: Path) -> None:
    """One grasp skill on the default leg, from placement through the proof lift or the refusal."""
    leg = LegConfig()
    config = CellConfig(belt_speed_mps=0.0, leg=leg, arm=arm, gripper=gripper)
    leg_y = BLADE_PLANE_Y_M + leg.hock_offset_m if trotter_end else 0.55
    select: Skill = SelectTrotterEndGrasp() if trotter_end else SelectShankGrasp()
    acquire: Skill = AcquireTrotterEnd() if trotter_end else AcquireShank()
    with FilmedCell(config) as cell:
        cell.reset()
        cell.place_product(0.30, leg_y, -math.pi / 2)
        lookat = [0.30, 0.02, 0.95] if trotter_end else [0.30, 0.30, 0.95]
        film = Film(cell.model, path, _camera(lookat, 1.7, 235.0 if trotter_end else 205.0, -22.0))
        cell.film = film
        headline = f"TEST: {title}"
        rule = "PASS = the tool rises on a 5 mm lift and the part stays within 1 mm of it"
        film.caption = [headline, rule, "leg placed square on a stopped belt"]
        cell.step(seconds=0.6)
        estimated = run_skill(EstimateLegFromGroundTruth(), cell, {})
        selected = run_skill(select, cell, estimated.outputs)
        film.caption = [headline, rule, f"skill 1 {select.name}: {selected.outcome}"]
        if selected.outcome != SUCCESS:
            film.hold(cell.data, 3.0)
            film.close()
            return
        film.caption.append(f"skill 2 {acquire.name}: checking conditions, then approach, close, lift")
        result: SkillResult = run_skill(acquire, cell, selected.outputs)
        lines = [headline, rule, f"skill 2 {acquire.name}: {result.outcome}", OUTCOME_MEANING.get(result.outcome, "")]
        if result.outcome == "precondition_failed":
            for check in acquire.contract.preconditions:
                if check.name in result.evidence:
                    value = result.evidence[check.name]
                    shown = f"{1000 * value:.0f} mm" if check.name.endswith("_m") else f"{value:.0f}"
                    lines.append(f"  checked: {check.description}: measured {shown}")
        else:
            evidence = dict(result.evidence)
            if "opening_m" in evidence:
                lines.append(f"  opening after closing {1000 * evidence['opening_m']:.0f} mm")
            if "tool_rise_m" in evidence:
                lines.append(
                    f"  tool rose {1000 * evidence['tool_rise_m']:.2f} mm, part minus tool "
                    f"{1000 * evidence.get('part_minus_tool_m', math.nan):+.2f} mm"
                )
        film.caption = lines
        film.hold(cell.data, 3.5)
        film.close()


def main() -> None:
    """Record the reach, gripper and grasp videos into one folder, numbered in review order."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=Path.home() / "Videos" / "meat-cell" / "tests-2026-09-14")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("robotics", "applications"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    film_reach(ArmModel.UR20, out / "03-reach-ur20.mp4")
    film_reach(ArmModel.SR20IA, out / "04-reach-scara.mp4")
    film_gripper(GripperModel.JAW_GEH6180, out / "05-gripper-jaw-alone.mp4")
    film_gripper(GripperModel.THREE_FINGER_3FG25, out / "06-gripper-three-finger-alone.mp4")
    grasps = [
        ("UR20 + jaw grips the shank from above", ArmModel.UR20, GripperModel.JAW_GEH6180, False, "07"),
        ("SCARA + jaw grips the shank from above", ArmModel.SR20IA, GripperModel.JAW_GEH6180, False, "08"),
        ("UR20 + three-finger tries the shank from above", ArmModel.UR20, GripperModel.THREE_FINGER_3FG25, False, "09"),
        (
            "SCARA + three-finger tries the shank from above",
            ArmModel.SR20IA,
            GripperModel.THREE_FINGER_3FG25,
            False,
            "10",
        ),
        ("UR20 + three-finger grips the trotter end-on", ArmModel.UR20, GripperModel.THREE_FINGER_3FG25, True, "11"),
        ("SCARA + three-finger tries the trotter end-on", ArmModel.SR20IA, GripperModel.THREE_FINGER_3FG25, True, "12"),
    ]
    for title, arm, gripper, trotter_end, number in grasps:
        slug = title.lower().replace(" + ", "-").replace(" ", "-")
        film_grasp(title, arm, gripper, trotter_end, out / f"{number}-{slug}.mp4")


if __name__ == "__main__":
    main()
