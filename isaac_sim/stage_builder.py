"""Build the complete visible Isaac USD cell from local reference geometry.

The robot, gripper, workpiece, cutter, and buffer are abstract reference models.
They are not OEM accurate and are not physically calibrated.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from meatcell.product_profiles import ProductProfile, load_product_catalog

from .adapter_config import IsaacCellPaths


REFERENCE_NOTICE = (
    "Abstract reference model for simulation integration only. "
    "Not OEM accurate, physically calibrated, food-safe validated, or production ready."
)


def product_outline(shape_family: str, taper_ratio: float) -> tuple[tuple[float, float], ...]:
    """Return a convex normalized outline for an abstract meat reference cut."""

    taper = min(1.0, max(0.30, taper_ratio))
    if shape_family == "tapered_capsule":
        narrow = 0.50 * taper
        return (
            (-0.50, 0.0),
            (-0.42, -narrow * 0.70),
            (-0.15, -narrow),
            (0.28, -0.50),
            (0.47, -0.32),
            (0.50, 0.0),
            (0.47, 0.32),
            (0.28, 0.50),
            (-0.15, narrow),
            (-0.42, narrow * 0.70),
        )
    if shape_family == "elongated_rounded_prism":
        end = 0.50 * taper
        return (
            (-0.50, -end * 0.55),
            (-0.40, -end),
            (0.35, -0.50),
            (0.50, -0.27),
            (0.50, 0.27),
            (0.35, 0.50),
            (-0.40, end),
            (-0.50, end * 0.55),
        )
    if shape_family == "asymmetric_teardrop_slab":
        tip = 0.50 * taper
        return (
            (-0.50, 0.0),
            (-0.34, -tip * 0.70),
            (-0.05, -tip),
            (0.30, -0.50),
            (0.49, -0.24),
            (0.50, 0.18),
            (0.30, 0.50),
            (-0.04, tip * 0.92),
            (-0.35, tip * 0.58),
        )
    return ((-0.50, -0.50), (0.50, -0.50), (0.50, 0.50), (-0.50, 0.50))


def product_width_scale_at_grasp(shape_family: str, taper_ratio: float) -> float:
    """Return the normalized mesh width at the central grasp section."""
    outline = product_outline(shape_family, taper_ratio)
    intersections: list[float] = []
    for index, (x0, y0) in enumerate(outline):
        x1, y1 = outline[(index + 1) % len(outline)]
        if not min(x0, x1) <= 0.0 <= max(x0, x1):
            continue
        if math.isclose(x0, x1, abs_tol=1e-12):
            intersections.extend((y0, y1))
            continue
        fraction = -x0 / (x1 - x0)
        intersections.append(y0 + fraction * (y1 - y0))
    if len(intersections) < 2:
        raise ValueError(f"Product outline does not cross the central grasp section: {shape_family}")
    width_scale = max(intersections) - min(intersections)
    if not 0.0 < width_scale <= 1.0:
        raise ValueError(f"Invalid central product width scale: {width_scale}")
    return width_scale


def product_prism_mesh_data(
    shape_family: str,
    length_m: float,
    width_m: float,
    height_m: float,
    taper_ratio: float,
) -> tuple[tuple[tuple[float, float, float], ...], tuple[int, ...], tuple[int, ...]]:
    """Build vertices and faces for a convex recipe-shaped prism."""

    if min(length_m, width_m, height_m) <= 0.0:
        raise ValueError("Product mesh dimensions must be positive")
    outline = product_outline(shape_family, taper_ratio)
    half_height = height_m / 2.0
    bottom = tuple((x * length_m, y * width_m, -half_height) for x, y in outline)
    top = tuple((x * length_m, y * width_m, half_height) for x, y in outline)
    points = bottom + top
    count = len(outline)
    face_counts = (count, count) + (4,) * count
    indices = list(reversed(range(count))) + list(range(count, 2 * count))
    for index in range(count):
        following = (index + 1) % count
        indices.extend((index, following, following + count, index + count))
    return points, face_counts, tuple(indices)


class IsaacStageBuilder:
    def __init__(
        self,
        paths: IsaacCellPaths = IsaacCellPaths(),
        product_profile: ProductProfile | None = None,
    ) -> None:
        self.paths = paths
        self.product_profile = product_profile or load_product_catalog().get("beef_center_cut_tenderloin")

    @staticmethod
    def _imports() -> tuple[Any, ...]:
        from pxr import Gf, PhysxSchema, Sdf, UsdGeom, UsdLux, UsdPhysics

        return Gf, PhysxSchema, Sdf, UsdGeom, UsdLux, UsdPhysics

    def _label_reference(self, prim: Any, role: str) -> None:
        _, _, Sdf, _, _, _ = self._imports()
        prim.CreateAttribute("meatcell:referenceRole", Sdf.ValueTypeNames.String).Set(role)
        prim.CreateAttribute("meatcell:referenceAssetNotice", Sdf.ValueTypeNames.String).Set(REFERENCE_NOTICE)

    def _frame(self, stage: Any, path: str, frame_name: str, position: tuple[float, float, float]) -> Any:
        Gf, _, Sdf, UsdGeom, _, _ = self._imports()
        frame = UsdGeom.Xform.Define(stage, path)
        frame.AddTranslateOp().Set(Gf.Vec3d(*position))
        frame.GetPrim().CreateAttribute("meatcell:frameName", Sdf.ValueTypeNames.String).Set(frame_name)
        return frame

    def _cube(
        self,
        stage: Any,
        path: str,
        dimensions_m: tuple[float, float, float],
        position_m: tuple[float, float, float],
        color: tuple[float, float, float],
        *,
        collision: bool = True,
        rigid: bool = False,
        mass_kg: float = 1.0,
        geometry_offset_m: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> Any:
        Gf, _, _, UsdGeom, _, UsdPhysics = self._imports()
        body = UsdGeom.Xform.Define(stage, path)
        body.AddTranslateOp().Set(Gf.Vec3d(*position_m))
        geom = UsdGeom.Cube.Define(stage, f"{path}/geometry")
        geom.CreateSizeAttr(1.0)
        geom.AddTranslateOp().Set(Gf.Vec3d(*geometry_offset_m))
        geom.AddScaleOp().Set(Gf.Vec3f(*dimensions_m))
        geom.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        if collision:
            UsdPhysics.CollisionAPI.Apply(geom.GetPrim())
        if rigid:
            UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
            UsdPhysics.MassAPI.Apply(body.GetPrim()).CreateMassAttr(mass_kg)
        return body

    def _product_mesh(
        self,
        stage: Any,
        path: str,
        dimensions_m: tuple[float, float, float],
        position_m: tuple[float, float, float],
        color: tuple[float, float, float],
        *,
        shape_family: str,
        taper_ratio: float,
        mass_kg: float,
    ) -> Any:
        Gf, _, _, UsdGeom, _, UsdPhysics = self._imports()
        points, face_counts, face_indices = product_prism_mesh_data(
            shape_family,
            dimensions_m[0],
            dimensions_m[1],
            dimensions_m[2],
            taper_ratio,
        )
        body = UsdGeom.Xform.Define(stage, path)
        body.AddTranslateOp().Set(Gf.Vec3d(*position_m))
        geometry = UsdGeom.Mesh.Define(stage, f"{path}/geometry")
        geometry.CreatePointsAttr([Gf.Vec3f(*point) for point in points])
        geometry.CreateFaceVertexCountsAttr(face_counts)
        geometry.CreateFaceVertexIndicesAttr(face_indices)
        geometry.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
        geometry.CreateDoubleSidedAttr(True)
        geometry.CreateExtentAttr(
            [
                Gf.Vec3f(-dimensions_m[0] / 2.0, -dimensions_m[1] / 2.0, -dimensions_m[2] / 2.0),
                Gf.Vec3f(dimensions_m[0] / 2.0, dimensions_m[1] / 2.0, dimensions_m[2] / 2.0),
            ]
        )
        geometry.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        UsdPhysics.CollisionAPI.Apply(geometry.GetPrim())
        UsdPhysics.MeshCollisionAPI.Apply(geometry.GetPrim()).CreateApproximationAttr().Set(
            UsdPhysics.Tokens.convexHull
        )
        UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
        UsdPhysics.MassAPI.Apply(body.GetPrim()).CreateMassAttr(mass_kg)
        return body

    def _drive(self, joint: Any, drive_type: str, target: float, stiffness: float, damping: float, max_force: float) -> None:
        _, PhysxSchema, Sdf, _, _, UsdPhysics = self._imports()
        drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), drive_type)
        drive.CreateTypeAttr("force")
        drive.CreateTargetPositionAttr(target)
        drive.CreateStiffnessAttr(stiffness)
        drive.CreateDampingAttr(damping)
        drive.CreateMaxForceAttr(max_force)
        joint.GetPrim().CreateAttribute("meatcell:accelerationLimit", Sdf.ValueTypeNames.Double).Set(8.0)
        PhysxSchema.PhysxJointAPI.Apply(joint.GetPrim()).CreateMaxJointVelocityAttr(4.0)

    def _prismatic(
        self,
        stage: Any,
        path: str,
        body0: str,
        body1: str,
        axis: str,
        lower: float,
        upper: float,
        target: float = 0.0,
        stiffness: float = 120_000.0,
        damping: float = 2_200.0,
        max_force: float = 120_000.0,
    ) -> Any:
        _, _, Sdf, _, _, UsdPhysics = self._imports()
        joint = UsdPhysics.PrismaticJoint.Define(stage, path)
        joint.CreateBody0Rel().SetTargets([Sdf.Path(body0)])
        joint.CreateBody1Rel().SetTargets([Sdf.Path(body1)])
        joint.CreateAxisAttr(axis)
        joint.CreateLowerLimitAttr(lower)
        joint.CreateUpperLimitAttr(upper)
        self._drive(joint, "linear", target, stiffness, damping, max_force)
        return joint

    def _build_robot(self, stage: Any) -> None:
        Gf, PhysxSchema, Sdf, UsdGeom, _, UsdPhysics = self._imports()
        p = self.paths
        robot = UsdGeom.Xform.Define(stage, p.robot)
        self._label_reference(robot.GetPrim(), "generic_cartesian_articulated_robot")
        UsdPhysics.ArticulationRootAPI.Apply(robot.GetPrim())
        articulation = PhysxSchema.PhysxArticulationAPI.Apply(robot.GetPrim())
        articulation.CreateEnabledSelfCollisionsAttr(False)

        origin = (0.35, 0.0, 1.10)
        base = self._cube(
            stage,
            p.robot_base,
            (0.35, 0.35, 0.25),
            origin,
            (0.18, 0.24, 0.34),
            rigid=True,
            mass_kg=80.0,
            geometry_offset_m=(0.0, 0.64, 0.0),
        )
        self._label_reference(base.GetPrim(), "robot_base")
        root_joint = UsdPhysics.FixedJoint.Define(stage, f"{p.robot}/Joints/root_fixed")
        root_joint.CreateBody1Rel().SetTargets([Sdf.Path(p.robot_base)])

        x_link = f"{p.robot}/x_carriage"
        y_link = f"{p.robot}/y_carriage"
        z_link = f"{p.robot}/z_carriage"
        wrist = f"{p.robot}/wrist"
        self._cube(stage, x_link, (0.60, 0.08, 0.08), origin, (0.22, 0.42, 0.72), collision=False, rigid=True, mass_kg=8.0)
        self._cube(stage, y_link, (0.10, 0.60, 0.08), origin, (0.28, 0.50, 0.82), collision=False, rigid=True, mass_kg=6.0)
        self._cube(stage, z_link, (0.10, 0.10, 0.65), origin, (0.34, 0.58, 0.88), collision=False, rigid=True, mass_kg=5.0, geometry_offset_m=(0.0, 0.0, -0.30))
        self._cube(stage, wrist, (0.14, 0.14, 0.14), origin, (0.86, 0.62, 0.12), collision=False, rigid=True, mass_kg=3.0)

        x_axis = self._prismatic(stage, f"{p.robot}/Joints/x_axis", p.robot_base, x_link, "X", 0.0, 2.20)
        x_axis.GetPrim().GetAttribute("meatcell:accelerationLimit").Set(12.0)
        self._prismatic(stage, f"{p.robot}/Joints/y_axis", x_link, y_link, "Y", -0.75, 0.75)
        self._prismatic(stage, f"{p.robot}/Joints/z_axis", y_link, z_link, "Z", -0.45, 0.20)
        yaw = UsdPhysics.RevoluteJoint.Define(stage, f"{p.robot}/Joints/wrist_yaw")
        yaw.CreateBody0Rel().SetTargets([Sdf.Path(z_link)])
        yaw.CreateBody1Rel().SetTargets([Sdf.Path(wrist)])
        yaw.CreateAxisAttr("Z")
        yaw.CreateLowerLimitAttr(-180.0)
        yaw.CreateUpperLimitAttr(180.0)
        self._drive(yaw, "angular", 0.0, 1_500.0, 180.0, 2_000.0)
        PhysxSchema.PhysxJointAPI.Apply(yaw.GetPrim()).GetMaxJointVelocityAttr().Set(math.degrees(6.0))

        tool = self._frame(stage, p.tool0, "tool0", (0.0, 0.0, -0.75))
        self._label_reference(tool.GetPrim(), "tool_center_point")
        gripper = UsdGeom.Xform.Define(stage, p.gripper)
        gripper.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, -0.70))
        self._label_reference(gripper.GetPrim(), "compliant_gripper_proxy")
        gripper.GetPrim().CreateAttribute("meatcell:normalForceSetpointN", Sdf.ValueTypeNames.Double).Set(50.0)
        gripper.GetPrim().CreateAttribute("meatcell:complianceProxyMPerN", Sdf.ValueTypeNames.Double).Set(0.00016)

        left = self._cube(stage, p.finger_left, (0.05, 0.025, 0.18), origin, (0.12, 0.75, 0.82), rigid=True, mass_kg=0.4, geometry_offset_m=(0.0, 0.10, -0.72))
        right = self._cube(stage, p.finger_right, (0.05, 0.025, 0.18), origin, (0.12, 0.75, 0.82), rigid=True, mass_kg=0.4, geometry_offset_m=(0.0, -0.10, -0.72))
        self._label_reference(left.GetPrim(), "compliant_finger_proxy")
        self._label_reference(right.GetPrim(), "compliant_finger_proxy")
        PhysxSchema.PhysxContactReportAPI.Apply(left.GetPrim()).CreateThresholdAttr(0.0)
        PhysxSchema.PhysxContactReportAPI.Apply(right.GetPrim()).CreateThresholdAttr(0.0)
        self._prismatic(
            stage,
            f"{p.robot}/Joints/finger_left",
            wrist,
            p.finger_left,
            "Y",
            -0.080,
            0.0,
            stiffness=3_000.0,
            damping=150.0,
            max_force=60.0,
        )
        self._prismatic(
            stage,
            f"{p.robot}/Joints/finger_right",
            wrist,
            p.finger_right,
            "Y",
            0.0,
            0.080,
            stiffness=3_000.0,
            damping=150.0,
            max_force=60.0,
        )

        camera = UsdGeom.Camera.Define(stage, p.wrist_camera)
        camera.CreateFocalLengthAttr(18.0)
        camera.CreateHorizontalApertureAttr(20.955)
        camera.CreateVerticalApertureAttr(15.71625)
        camera.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, -0.58))
        self._label_reference(camera.GetPrim(), "wrist_rgbd_camera")

    def _build_product(
        self,
        stage: Any,
        index: int,
        position: tuple[float, float, float],
        *,
        path_override: str | None = None,
    ) -> str:
        _, PhysxSchema, Sdf, _, _, _ = self._imports()
        profile = self.product_profile
        path = path_override or f"{self.paths.products}/MeatReference_{index:03d}"
        colors = {
            "beef": (0.72, 0.055, 0.045),
            "pork": (0.82, 0.19, 0.17),
            "chicken": (0.86, 0.34, 0.22),
        }
        dimensions = (
            profile.geometry.length_m.nominal,
            profile.geometry.width_m.nominal,
            profile.geometry.height_m.nominal,
        )
        product = self._product_mesh(
            stage,
            path,
            dimensions,
            position,
            colors.get(profile.species, (0.72, 0.055, 0.045)),
            shape_family=profile.geometry.shape_family,
            taper_ratio=profile.geometry.taper_ratio.nominal,
            mass_kg=profile.mass_kg.nominal,
        )
        prim = product.GetPrim()
        from pxr import UsdSemantics

        UsdSemantics.LabelsAPI.Apply(prim, "class").CreateLabelsAttr(["meat_workpiece"])
        UsdSemantics.LabelsAPI.Apply(prim, "recipe").CreateLabelsAttr([profile.recipe_id])
        UsdSemantics.LabelsAPI.Apply(prim, "instance").CreateLabelsAttr([path.rsplit("/", 1)[-1]])
        self._label_reference(prim, "meat_workpiece_rigid_compliance_proxy")
        prim.CreateAttribute("meatcell:semanticClass", Sdf.ValueTypeNames.String).Set("meat_reference")
        prim.CreateAttribute("meatcell:recipeId", Sdf.ValueTypeNames.String).Set(profile.recipe_id)
        prim.CreateAttribute("meatcell:species", Sdf.ValueTypeNames.String).Set(profile.species)
        prim.CreateAttribute("meatcell:cut", Sdf.ValueTypeNames.String).Set(profile.cut)
        prim.CreateAttribute("meatcell:shapeFamily", Sdf.ValueTypeNames.String).Set(profile.geometry.shape_family)
        prim.CreateAttribute("meatcell:nominalLengthM", Sdf.ValueTypeNames.Double).Set(dimensions[0])
        prim.CreateAttribute("meatcell:nominalWidthM", Sdf.ValueTypeNames.Double).Set(dimensions[1])
        prim.CreateAttribute("meatcell:nominalHeightM", Sdf.ValueTypeNames.Double).Set(dimensions[2])
        prim.CreateAttribute("meatcell:nominalMassKg", Sdf.ValueTypeNames.Double).Set(profile.mass_kg.nominal)
        prim.CreateAttribute("meatcell:complianceProxy", Sdf.ValueTypeNames.Double).Set(
            profile.mechanics.compliance_index.nominal
        )
        prim.CreateAttribute("meatcell:effectiveCompressionModulusKPa", Sdf.ValueTypeNames.Double).Set(
            profile.mechanics.effective_compression_modulus_kpa.nominal
        )
        prim.CreateAttribute("meatcell:physicalCalibrationComplete", Sdf.ValueTypeNames.Bool).Set(
            profile.mechanics.calibrated
        )
        prim.CreateAttribute("meatcell:requiredTrayOrientation", Sdf.ValueTypeNames.String).Set(
            profile.required_tray_orientation
        )
        PhysxSchema.PhysxContactReportAPI.Apply(prim).CreateThresholdAttr(0.0)
        return path

    def build(self, stage: Any, solution: str) -> dict[str, Any]:
        if solution not in {"a", "b"}:
            raise ValueError("solution must be 'a' or 'b'")
        Gf, PhysxSchema, Sdf, UsdGeom, UsdLux, UsdPhysics = self._imports()
        p = self.paths
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        stage.SetTimeCodesPerSecond(240)
        world = UsdGeom.Xform.Define(stage, p.world)
        world.GetPrim().CreateAttribute("meatcell:solution", Sdf.ValueTypeNames.String).Set(solution)
        world.GetPrim().CreateAttribute("meatcell:productRecipeId", Sdf.ValueTypeNames.String).Set(
            self.product_profile.recipe_id
        )
        world.GetPrim().CreateAttribute("meatcell:referenceAssetNotice", Sdf.ValueTypeNames.String).Set(REFERENCE_NOTICE)

        physics = UsdPhysics.Scene.Define(stage, p.physics_scene)
        physics.CreateGravityDirectionAttr(Gf.Vec3f(0.0, 0.0, -1.0))
        physics.CreateGravityMagnitudeAttr(9.80665)
        scene_api = PhysxSchema.PhysxSceneAPI.Apply(physics.GetPrim())
        scene_api.CreateEnableCCDAttr(True)
        scene_api.CreateEnableStabilizationAttr(True)

        floor = self._cube(stage, "/World/Floor", (5.0, 3.0, 0.04), (1.2, 0.0, -0.10), (0.18, 0.18, 0.20))
        self._label_reference(floor.GetPrim(), "cell_floor")
        conveyor = self._cube(stage, p.conveyor, (3.6, 0.80, 0.08), (1.0, 0.0, 0.0), (0.08, 0.10, 0.12))
        self._label_reference(conveyor.GetPrim(), "conveyor_reference")
        conveyor.GetPrim().CreateAttribute("meatcell:beltSpeedMps", Sdf.ValueTypeNames.Double).Set(2.24)
        self._frame(stage, p.belt_surface, "belt_surface", (0.0, 0.0, 0.04))
        self._frame(stage, f"{p.conveyor}/conveyor_frame", "conveyor", (0.0, 0.0, 0.0))

        UsdGeom.Xform.Define(stage, p.products)
        product_z_m = 0.04 + self.product_profile.geometry.height_m.nominal / 2.0 + 0.002
        products = (
            self._build_product(stage, 0, (-0.55, 0.00, product_z_m)),
            self._build_product(stage, 1, (-1.15, 0.16, product_z_m)),
            self._build_product(stage, 2, (-1.75, -0.14, product_z_m)),
            self._build_product(stage, 3, (-2.35, 0.08, product_z_m)),
        )

        self._build_robot(stage)
        sensors = UsdGeom.Xform.Define(stage, p.sensors)
        self._label_reference(sensors.GetPrim(), "camera_mount_reference")
        overhead = UsdGeom.Camera.Define(stage, p.overhead_camera)
        overhead.CreateFocalLengthAttr(18.0)
        overhead.CreateHorizontalApertureAttr(20.955)
        overhead.CreateVerticalApertureAttr(15.71625)
        overhead.AddTranslateOp().Set(Gf.Vec3d(1.0, 0.0, 3.0))
        self._label_reference(overhead.GetPrim(), "overhead_rgbd_camera")
        calibration = self._frame(stage, p.camera_calibration_target, "camera_calibration_target", (0.0, -0.32, 0.05))
        self._label_reference(calibration.GetPrim(), "camera_calibration_target")
        target = self._frame(stage, p.cut_target_frame, "cut_target_frame", (2.35, 0.0, 0.10))
        self._label_reference(target.GetPrim(), "downstream_alignment_reference")

        cutter = self._cube(stage, p.cutter_station, (0.38, 0.90, 0.55), (2.72, 0.0, 0.30), (0.70, 0.22, 0.06))
        self._label_reference(cutter.GetPrim(), "guarded_cutter_feed_station_reference")
        self._frame(stage, p.cutter_feed_frame, "cutter_feed_frame", (-0.37, 0.0, -0.20))
        guards = UsdGeom.Xform.Define(stage, p.guards)
        self._label_reference(guards.GetPrim(), "guard_reference_geometry")
        self._cube(stage, f"{p.guards}/LeftFence", (1.5, 0.04, 0.55), (2.1, 0.92, 0.30), (0.95, 0.74, 0.05))
        self._cube(stage, f"{p.guards}/RightFence", (1.5, 0.04, 0.55), (2.1, -0.92, 0.30), (0.95, 0.74, 0.05))
        reject = self._cube(stage, p.reject_bin, (0.55, 0.45, 0.28), (1.60, 0.62, 0.10), (0.25, 0.30, 0.36))
        self._label_reference(reject.GetPrim(), "reject_location_reference")
        self._frame(stage, f"{p.reject_bin}/reject_frame", "reject_frame", (0.0, 0.0, 0.20))
        if solution == "b":
            buffer = self._cube(stage, p.buffer, (0.48, 0.40, 0.08), (1.80, -0.55, 0.06), (0.06, 0.52, 0.66))
            self._label_reference(buffer.GetPrim(), "centering_buffer_reference")
            self._frame(stage, f"{p.buffer}/buffer_frame", "buffer_frame", (0.0, 0.0, 0.08))

        plc = UsdGeom.Xform.Define(stage, p.plc)
        self._label_reference(plc.GetPrim(), "simulated_plc_machine_io")
        plc.GetPrim().CreateAttribute("meatcell:conveyorSpeedMps", Sdf.ValueTypeNames.Double).Set(2.24)
        plc.GetPrim().CreateAttribute("meatcell:recipeId", Sdf.ValueTypeNames.String).Set(
            self.product_profile.recipe_id
        )
        plc.GetPrim().CreateAttribute("meatcell:cutterReady", Sdf.ValueTypeNames.Bool).Set(True)
        plc.GetPrim().CreateAttribute("meatcell:cutterPhaseRad", Sdf.ValueTypeNames.Double).Set(0.0)
        plc.GetPrim().CreateAttribute("meatcell:permissiveSequence", Sdf.ValueTypeNames.Int).Set(1)
        plc.GetPrim().CreateAttribute("meatcell:faultActive", Sdf.ValueTypeNames.Bool).Set(False)
        plc.GetPrim().CreateAttribute("meatcell:emergencyStop", Sdf.ValueTypeNames.Bool).Set(False)
        plc.GetPrim().CreateAttribute("meatcell:resultAcknowledged", Sdf.ValueTypeNames.Bool).Set(False)

        dome = UsdLux.DomeLight.Define(stage, "/World/Lights/Dome")
        dome.CreateIntensityAttr(650.0)
        key = UsdLux.RectLight.Define(stage, "/World/Lights/Key")
        key.CreateIntensityAttr(3_000.0)
        key.CreateWidthAttr(2.0)
        key.CreateHeightAttr(1.0)
        key.AddTranslateOp().Set(Gf.Vec3d(1.0, -1.0, 2.5))
        key.AddRotateXYZOp().Set(Gf.Vec3f(20.0, 0.0, 25.0))
        return {
            "solution": solution,
            "product_profile": self.product_profile,
            "product_paths": products,
            "required_paths": p.required_for_solution(solution),
        }

    @staticmethod
    def manifest(stage: Any) -> dict[str, Any]:
        from pxr import UsdPhysics

        prims = sorted(
            (prim.GetPath().pathString, prim.GetTypeName())
            for prim in stage.Traverse()
            if prim.GetPath().pathString == "/World" or prim.GetPath().pathString.startswith("/World/")
        )
        joints = [path for path, type_name in prims if "Joint" in type_name]
        cameras = [path for path, type_name in prims if type_name == "Camera"]
        rigid_bodies = [
            path
            for path, _ in prims
            if stage.GetPrimAtPath(path).HasAPI(UsdPhysics.RigidBodyAPI)
        ]
        world = stage.GetPrimAtPath("/World")
        product = stage.GetPrimAtPath("/World/Products/MeatReference_000")
        recipe_id = world.GetAttribute("meatcell:productRecipeId").Get() if world.IsValid() else None
        product_properties = {}
        if product.IsValid():
            for key in (
                "species",
                "cut",
                "shapeFamily",
                "nominalLengthM",
                "nominalWidthM",
                "nominalHeightM",
                "nominalMassKg",
                "complianceProxy",
            ):
                product_properties[key] = product.GetAttribute(f"meatcell:{key}").Get()
        return {
            "meters_per_unit": stage.GetMetadata("metersPerUnit"),
            "time_codes_per_second": stage.GetTimeCodesPerSecond(),
            "product_recipe_id": recipe_id,
            "product_properties": product_properties,
            "prims": prims,
            "joints": joints,
            "cameras": cameras,
            "rigid_bodies": rigid_bodies,
        }

    @classmethod
    def signature(cls, stage: Any) -> str:
        payload = json.dumps(cls.manifest(stage), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
