"""Isaac Sim 6 proxy scene for architecture A or B.

This script visualizes cell timing and boundaries. It is not a validated robot,
gripper, deformable-meat, or blade model.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path


def smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def lerp(start: tuple[float, float, float], end: tuple[float, float, float], alpha: float) -> tuple[float, float, float]:
    return tuple(a + (b - a) * alpha for a, b in zip(start, end, strict=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", choices=("a", "b"), default="a")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--physics-hz", type=int, default=240)
    parser.add_argument("--duration-s", type=float, default=3.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        from isaacsim import SimulationApp
    except ImportError as exc:
        raise SystemExit(
            "Isaac Sim 6.0.1 is not installed. Follow isaac_sim/README.md and accept the NVIDIA EULA yourself."
        ) from exc

    simulation_app = SimulationApp({"headless": args.headless})

    import omni.timeline
    import omni.usd
    from pxr import Gf, Sdf, UsdGeom, UsdPhysics

    stage = omni.usd.get_context().get_stage()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetTimeCodesPerSecond(args.physics_hz)

    physics = UsdPhysics.Scene.Define(stage, Sdf.Path("/World/PhysicsScene"))
    physics.CreateGravityDirectionAttr(Gf.Vec3f(0.0, 0.0, -1.0))
    physics.CreateGravityMagnitudeAttr(9.80665)

    world = UsdGeom.Xform.Define(stage, Sdf.Path("/World"))
    world.GetPrim().SetMetadata("comment", "Meat interception cell proxy")

    def cube(path: str, scale: tuple[float, float, float], color: tuple[float, float, float]) -> UsdGeom.Cube:
        geom = UsdGeom.Cube.Define(stage, Sdf.Path(path))
        geom.CreateSizeAttr(1.0)
        geom.CreateScaleOp().Set(Gf.Vec3f(*scale))
        geom.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        return geom

    belt = cube("/World/Conveyor", (2.0, 0.45, 0.04), (0.10, 0.12, 0.14))
    belt.CreateTranslateOp().Set(Gf.Vec3d(0.8, 0.0, 0.0))

    cutter_guard = cube("/World/CutterGuard", (0.20, 0.55, 0.40), (0.75, 0.18, 0.10))
    cutter_guard.CreateTranslateOp().Set(Gf.Vec3d(2.65, 0.0, 0.40))

    target = UsdGeom.Xform.Define(stage, Sdf.Path("/World/cut_target_frame"))
    target.AddTranslateOp().Set(Gf.Vec3d(2.35, 0.0, 0.12))
    target_axis = cube("/World/cut_target_frame/marker", (0.08, 0.02, 0.02), (0.10, 0.90, 0.25))
    target_axis.CreateTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 0.0))

    camera = UsdGeom.Camera.Define(stage, Sdf.Path("/World/Camera"))
    camera.CreateFocalLengthAttr(18.0)
    camera.CreateHorizontalApertureAttr(20.955)
    camera.AddTranslateOp().Set(Gf.Vec3d(-0.35, 0.0, 2.2))
    camera.AddRotateXYZOp().Set(Gf.Vec3f(0.0, 0.0, 0.0))

    work_envelope = UsdGeom.Sphere.Define(stage, Sdf.Path("/World/RobotWorkEnvelope"))
    work_envelope.CreateRadiusAttr(0.75)
    work_envelope.CreateDisplayColorAttr([Gf.Vec3f(0.18, 0.35, 0.85)])
    work_envelope.CreatePurposeAttr(UsdGeom.Tokens.guide)
    work_envelope.AddTranslateOp().Set(Gf.Vec3d(1.20, 0.0, 0.65))

    tool = UsdGeom.Sphere.Define(stage, Sdf.Path("/World/RobotTCP"))
    tool.CreateRadiusAttr(0.07)
    tool.CreateDisplayColorAttr([Gf.Vec3f(0.95, 0.72, 0.10)])
    tool_translate = tool.AddTranslateOp()

    meat = cube("/World/MeatPiece", (0.125, 0.060, 0.018), (0.65, 0.08, 0.07))
    meat_translate = meat.CreateTranslateOp()

    if args.solution == "b":
        buffer_geom = cube("/World/CenteringBuffer", (0.25, 0.20, 0.04), (0.15, 0.55, 0.65))
        buffer_geom.CreateTranslateOp().Set(Gf.Vec3d(1.80, -0.60, 0.08))

    timeline = omni.timeline.get_timeline_interface()
    timeline.play()
    dt = 1.0 / args.physics_hz
    intercept_t = 0.72
    pick = (1.05, 0.0, 0.10)
    home = (1.05, 0.0, 0.85)
    buffer_pose = (1.80, -0.60, 0.12)
    cut_pose = (2.35, 0.0, 0.12)

    total_steps = max(1, int(args.duration_s * args.physics_hz))
    for step in range(total_steps):
        now = step * dt
        belt_piece = (-0.56 + 2.24 * now, 0.0, 0.10)

        if now < intercept_t - 0.25:
            tool_pose = home
            meat_pose = belt_piece
        elif now < intercept_t:
            alpha = smoothstep((now - (intercept_t - 0.25)) / 0.25)
            tool_pose = lerp(home, pick, alpha)
            meat_pose = belt_piece
        elif args.solution == "a":
            alpha = smoothstep((now - intercept_t) / 0.55)
            tool_pose = lerp(pick, cut_pose, alpha)
            meat_pose = tool_pose
        elif now < intercept_t + 0.45:
            alpha = smoothstep((now - intercept_t) / 0.45)
            tool_pose = lerp(pick, buffer_pose, alpha)
            meat_pose = tool_pose
        elif now < intercept_t + 0.80:
            tool_pose = home
            meat_pose = buffer_pose
        else:
            alpha = smoothstep((now - (intercept_t + 0.80)) / 0.35)
            tool_pose = home
            meat_pose = lerp(buffer_pose, cut_pose, alpha)

        tool_translate.Set(Gf.Vec3d(*tool_pose))
        meat_translate.Set(Gf.Vec3d(*meat_pose))
        simulation_app.update()

    timeline.stop()
    output = Path(__file__).resolve().parent.parent / "results" / f"isaac_proxy_{args.solution}.usda"
    output.parent.mkdir(parents=True, exist_ok=True)
    omni.usd.get_context().save_as_stage(str(output))
    print(f"Saved {output}")
    simulation_app.close()


if __name__ == "__main__":
    main()
