"""Build the Scene 2.0 FANUC reference cell.

The FANUC geometry and kinematics come from the official fanuc_description
package. The gripper, conveyor, cutter, guards, and products remain project
reference models. They are not physically qualified or OEM-accurate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from isaac_sim.stage_builder import product_prism_mesh_data


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FANUC_USD = PROJECT_ROOT / "assets" / "robots" / "fanuc_m10id12" / "usd" / "fanuc_m10id12_reference.usda"
SCENE2_STAGE = PROJECT_ROOT / "results" / "scene2" / "meatcell_scene2_fanuc.usda"
ROBOT_PRIM = "/World/Cell/FANUC_M10iD12"
ARTICULATION_ROOT = f"{ROBOT_PRIM}/Geometry/world/base_link"
FLANGE_PATH = (
    f"{ROBOT_PRIM}/Geometry/world/base_link/J1_link/J2_link/J3_link/"
    "J4_link/J5_link/J6_link/flange/ee_link"
)
JOINT_PATHS = tuple(f"{ROBOT_PRIM}/Physics/J{index}" for index in range(1, 7))

REFERENCE_NOTICE = (
    "FANUC visual and kinematic reference from the official description. "
    "The cell equipment and tool are project reference models. No physical or safety validation is claimed."
)


class Scene2Builder:
    def __init__(self, robot_asset: Path = FANUC_USD) -> None:
        self.robot_asset = robot_asset.resolve()
        self.materials: dict[str, Any] = {}

    @staticmethod
    def _imports() -> tuple[Any, ...]:
        from pxr import Gf, PhysxSchema, Sdf, UsdGeom, UsdLux, UsdPhysics, UsdShade

        return Gf, PhysxSchema, Sdf, UsdGeom, UsdLux, UsdPhysics, UsdShade

    def _material(
        self,
        stage: Any,
        name: str,
        color: tuple[float, float, float],
        *,
        metallic: float = 0.0,
        roughness: float = 0.45,
        opacity: float = 1.0,
        emissive: tuple[float, float, float] | None = None,
    ) -> Any:
        Gf, _, Sdf, _, _, _, UsdShade = self._imports()
        material = UsdShade.Material.Define(stage, f"/World/Looks/{name}")
        shader = UsdShade.Shader.Define(stage, f"/World/Looks/{name}/PreviewSurface")
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(metallic)
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
        shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(opacity)
        if emissive is not None:
            shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*emissive))
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        self.materials[name] = material
        return material

    def _bind(self, prim: Any, material: Any) -> None:
        *_, UsdShade = self._imports()
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(material)

    def _label(self, prim: Any, role: str, status: str = "reference") -> None:
        _, _, Sdf, _, _, _, _ = self._imports()
        prim.CreateAttribute("meatcell:role", Sdf.ValueTypeNames.String).Set(role)
        prim.CreateAttribute("meatcell:status", Sdf.ValueTypeNames.String).Set(status)

    def _cube(
        self,
        stage: Any,
        path: str,
        size: tuple[float, float, float],
        position: tuple[float, float, float],
        material: Any,
        *,
        collision: bool = True,
        rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
        role: str = "cell_geometry",
    ) -> Any:
        Gf, _, _, UsdGeom, _, UsdPhysics, _ = self._imports()
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        cube.AddTranslateOp().Set(Gf.Vec3d(*position))
        cube.AddRotateXYZOp().Set(Gf.Vec3f(*rotation))
        cube.AddScaleOp().Set(Gf.Vec3f(*size))
        self._bind(cube.GetPrim(), material)
        self._label(cube.GetPrim(), role)
        if collision:
            UsdPhysics.CollisionAPI.Apply(cube.GetPrim())
        return cube

    def _cylinder(
        self,
        stage: Any,
        path: str,
        radius: float,
        height: float,
        position: tuple[float, float, float],
        material: Any,
        *,
        axis: str = "Z",
        collision: bool = True,
        role: str = "cell_geometry",
    ) -> Any:
        Gf, _, _, UsdGeom, _, UsdPhysics, _ = self._imports()
        cylinder = UsdGeom.Cylinder.Define(stage, path)
        cylinder.CreateRadiusAttr(radius)
        cylinder.CreateHeightAttr(height)
        cylinder.CreateAxisAttr(axis)
        cylinder.AddTranslateOp().Set(Gf.Vec3d(*position))
        self._bind(cylinder.GetPrim(), material)
        self._label(cylinder.GetPrim(), role)
        if collision:
            UsdPhysics.CollisionAPI.Apply(cylinder.GetPrim())
        return cylinder

    def _frame(self, stage: Any, path: str, name: str, position: tuple[float, float, float]) -> Any:
        Gf, _, Sdf, UsdGeom, _, _, _ = self._imports()
        frame = UsdGeom.Xform.Define(stage, path)
        frame.AddTranslateOp().Set(Gf.Vec3d(*position))
        frame.GetPrim().CreateAttribute("meatcell:frameName", Sdf.ValueTypeNames.String).Set(name)
        self._label(frame.GetPrim(), "named_coordinate_frame", "defined")
        return frame

    def _product(
        self,
        stage: Any,
        path: str,
        position: tuple[float, float, float],
        yaw_deg: float,
        material: Any,
    ) -> Any:
        Gf, _, Sdf, UsdGeom, _, UsdPhysics, _ = self._imports()
        dimensions = (0.46, 0.14, 0.08)
        points, face_counts, indices = product_prism_mesh_data(
            "elongated_rounded_prism", dimensions[0], dimensions[1], dimensions[2], 0.82
        )
        body = UsdGeom.Xform.Define(stage, path)
        body.AddTranslateOp().Set(Gf.Vec3d(*position))
        body.AddRotateZOp().Set(yaw_deg)
        mesh = UsdGeom.Mesh.Define(stage, f"{path}/Geometry")
        mesh.CreatePointsAttr([Gf.Vec3f(*point) for point in points])
        mesh.CreateFaceVertexCountsAttr(face_counts)
        mesh.CreateFaceVertexIndicesAttr(indices)
        mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
        mesh.CreateDoubleSidedAttr(True)
        self._bind(mesh.GetPrim(), material)
        UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
        UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim()).CreateApproximationAttr().Set(UsdPhysics.Tokens.convexHull)
        UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
        UsdPhysics.MassAPI.Apply(body.GetPrim()).CreateMassAttr(2.75)
        self._label(body.GetPrim(), "pork_boneless_loin_reference")
        body.GetPrim().CreateAttribute("meatcell:recipeId", Sdf.ValueTypeNames.String).Set("pork_boneless_loin")
        return body

    def _build_materials(self, stage: Any) -> None:
        self._material(stage, "Floor", (0.32, 0.35, 0.38), roughness=0.78)
        self._material(stage, "Steel", (0.58, 0.62, 0.65), metallic=0.85, roughness=0.22)
        self._material(stage, "DarkSteel", (0.16, 0.19, 0.22), metallic=0.75, roughness=0.3)
        self._material(stage, "Belt", (0.055, 0.085, 0.105), roughness=0.72)
        self._material(stage, "SafetyYellow", (0.96, 0.69, 0.04), metallic=0.12, roughness=0.34)
        self._material(stage, "SafetyOrange", (0.92, 0.29, 0.045), roughness=0.38)
        self._material(stage, "ToolBlue", (0.035, 0.43, 0.64), metallic=0.48, roughness=0.28)
        self._material(stage, "SoftPad", (0.06, 0.16, 0.22), roughness=0.9)
        self._material(stage, "Meat", (0.62, 0.10, 0.11), roughness=0.76)
        self._material(stage, "Glass", (0.42, 0.74, 0.82), roughness=0.08, opacity=0.23)
        self._material(stage, "Sensor", (0.035, 0.04, 0.05), metallic=0.55, roughness=0.22)
        self._material(stage, "SignalGreen", (0.05, 0.32, 0.08), roughness=0.3, emissive=(0.1, 1.0, 0.2))

    def _build_conveyor(self, stage: Any) -> None:
        UsdGeom = self._imports()[3]
        UsdGeom.Xform.Define(stage, "/World/Cell/Conveyor")
        self._cube(stage, "/World/Cell/Conveyor/Belt", (4.4, 0.88, 0.055), (0.0, 0.0, 0.78), self.materials["Belt"], role="moving_conveyor_belt")
        for y in (-0.49, 0.49):
            self._cube(stage, f"/World/Cell/Conveyor/Rail_{'L' if y > 0 else 'R'}", (4.55, 0.065, 0.14), (0.0, y, 0.86), self.materials["Steel"], role="conveyor_side_rail")
        for x in (-1.9, -0.65, 0.65, 1.9):
            self._cylinder(stage, f"/World/Cell/Conveyor/Roller_{str(x).replace('.', '_').replace('-', 'm')}", 0.095, 0.82, (x, 0.0, 0.72), self.materials["DarkSteel"], axis="Y", role="conveyor_roller")
            for y in (-0.36, 0.36):
                self._cube(stage, f"/World/Cell/Conveyor/Leg_{str(x).replace('.', '_').replace('-', 'm')}_{'L' if y > 0 else 'R'}", (0.09, 0.09, 0.72), (x, y, 0.37), self.materials["Steel"], role="conveyor_support")
        self._frame(stage, "/World/Cell/Frames/conveyor", "conveyor", (0.0, 0.0, 0.78))
        self._frame(stage, "/World/Cell/Frames/belt_surface", "belt_surface", (0.0, 0.0, 0.8075))

    def _build_robot(self, stage: Any) -> None:
        Gf, _, Sdf, UsdGeom, _, UsdPhysics, _ = self._imports()
        self._cube(stage, "/World/Cell/RobotPedestal", (0.78, 0.78, 0.52), (0.35, -1.25, 0.26), self.materials["Steel"], role="robot_pedestal")
        self._cube(stage, "/World/Cell/RobotPedestalTop", (0.88, 0.88, 0.065), (0.35, -1.25, 0.55), self.materials["DarkSteel"], role="robot_mounting_plate")
        for dx in (-0.31, 0.31):
            for dy in (-0.31, 0.31):
                dx_name = str(dx).replace("-", "m").replace(".", "_")
                dy_name = str(dy).replace("-", "m").replace(".", "_")
                self._cylinder(stage, f"/World/Cell/RobotBolts/B_{dx_name}_{dy_name}", 0.025, 0.09, (0.35 + dx, -1.25 + dy, 0.605), self.materials["DarkSteel"], role="pedestal_anchor")
        robot = UsdGeom.Xform.Define(stage, ROBOT_PRIM)
        robot.GetPrim().GetReferences().AddReference(self.robot_asset.as_posix())
        robot.AddTranslateOp().Set(Gf.Vec3d(0.35, -1.25, 0.59))
        robot.AddRotateZOp().Set(90.0)
        self._label(robot.GetPrim(), "fanuc_m10id12_official_description_reference", "imported")
        robot.GetPrim().CreateAttribute("meatcell:sourceCommit", Sdf.ValueTypeNames.String).Set(
            "fb40c9803a826ba68c7c8e28ba904a25efa7fcd2"
        )
        robot.GetPrim().CreateAttribute("meatcell:model", Sdf.ValueTypeNames.String).Set("FANUC M-10iD/12")
        for index, joint_path in enumerate(JOINT_PATHS, start=1):
            joint = UsdPhysics.RevoluteJoint.Get(stage, joint_path)
            if not joint:
                raise RuntimeError(f"Imported FANUC joint is missing: {joint_path}")
            drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular")
            drive.CreateTypeAttr("force")
            drive.CreateTargetPositionAttr(0.0)
            drive.CreateStiffnessAttr(18000.0 if index <= 3 else 6000.0)
            drive.CreateDampingAttr(1400.0 if index <= 3 else 450.0)
            effort = float(joint.GetPrim().GetAttribute("urdf:limit:effort").Get() or 100.0)
            drive.CreateMaxForceAttr(effort)
        self._frame(stage, "/World/Cell/Frames/robot_base", "robot_base", (0.35, -1.25, 0.59))
        gripper = UsdGeom.Xform.Define(stage, f"{FLANGE_PATH}/CompliantGripperReference")
        gripper.AddTranslateOp().Set(Gf.Vec3d(0.16, 0.0, 0.0))
        gripper.AddRotateYOp().Set(90.0)
        self._label(gripper.GetPrim(), "specialized_compliant_gripper_reference")
        self._cube(stage, f"{FLANGE_PATH}/CompliantGripperReference/WristAdapter", (0.18, 0.18, 0.12), (0.0, 0.0, 0.0), self.materials["ToolBlue"], collision=False, role="gripper_wrist_adapter")
        self._cube(stage, f"{FLANGE_PATH}/CompliantGripperReference/Crossbar", (0.46, 0.10, 0.10), (0.0, 0.0, -0.10), self.materials["ToolBlue"], collision=False, role="gripper_crossbar")
        for y, side in ((0.22, "Left"), (-0.22, "Right")):
            self._cube(stage, f"{FLANGE_PATH}/CompliantGripperReference/{side}Finger", (0.08, 0.09, 0.34), (0.0, y, -0.25), self.materials["Steel"], collision=False, role="compliant_gripper_finger")
            self._cube(stage, f"{FLANGE_PATH}/CompliantGripperReference/{side}Pad", (0.10, 0.045, 0.25), (0.0, y - (0.045 if y > 0 else -0.045), -0.27), self.materials["SoftPad"], collision=False, role="food_contact_pad_reference")
        self._frame(stage, "/World/Cell/Frames/tool0", "tool0", (0.0, 0.0, 0.0))

    def _build_cutter_and_reject(self, stage: Any) -> None:
        UsdGeom = self._imports()[3]
        UsdGeom.Xform.Define(stage, "/World/Cell/CutterStation")
        self._cube(stage, "/World/Cell/CutterStation/Base", (0.85, 1.15, 0.82), (2.65, 0.0, 0.41), self.materials["Steel"], role="cutter_station_reference")
        self._cube(stage, "/World/Cell/CutterStation/GuardHousing", (0.65, 1.05, 0.72), (2.62, 0.0, 1.08), self.materials["SafetyOrange"], role="guarded_cutter_housing_reference")
        self._cube(stage, "/World/Cell/CutterStation/FeedOpening", (0.24, 0.62, 0.34), (2.27, 0.0, 0.93), self.materials["DarkSteel"], collision=False, role="cutter_feed_opening")
        self._cube(stage, "/World/Cell/CutterStation/Tray", (0.88, 0.52, 0.055), (1.92, 0.0, 0.84), self.materials["Steel"], role="stationary_cutter_entry_tray")
        for y in (-0.28, 0.28):
            self._cube(stage, f"/World/Cell/CutterStation/TrayRail_{'L' if y > 0 else 'R'}", (0.88, 0.035, 0.12), (1.92, y, 0.91), self.materials["Steel"], role="tray_guide")
        self._cylinder(stage, "/World/Cell/CutterStation/ReadyLamp", 0.055, 0.12, (2.61, -0.48, 1.55), self.materials["SignalGreen"], role="cutter_ready_indicator")
        self._frame(stage, "/World/Cell/Frames/cut_target_frame", "cut_target_frame", (1.92, 0.0, 0.88))
        self._frame(stage, "/World/Cell/Frames/cutter_feed_frame", "cutter_feed_frame", (2.28, 0.0, 0.94))
        self._cube(stage, "/World/Cell/RejectBin/Base", (0.68, 0.56, 0.16), (1.45, -1.65, 0.10), self.materials["SafetyOrange"], role="reject_bin")
        for x, y, sx, sy in ((1.12, -1.65, 0.04, 0.56), (1.78, -1.65, 0.04, 0.56), (1.45, -1.92, 0.68, 0.04), (1.45, -1.38, 0.68, 0.04)):
            self._cube(stage, f"/World/Cell/RejectBin/Wall_{len(stage.GetPrimAtPath('/World/Cell/RejectBin').GetChildren())}", (sx, sy, 0.44), (x, y, 0.30), self.materials["SafetyOrange"], role="reject_bin_wall")
        self._frame(stage, "/World/Cell/Frames/reject_frame", "reject_frame", (1.45, -1.65, 0.38))

    def _build_sensors(self, stage: Any) -> None:
        Gf, _, _, UsdGeom, _, _, _ = self._imports()
        UsdGeom.Xform.Define(stage, "/World/Cell/Sensors")
        for y in (-1.0, 1.0):
            self._cube(stage, f"/World/Cell/Sensors/Post_{'L' if y > 0 else 'R'}", (0.09, 0.09, 2.5), (-0.35, y, 1.25), self.materials["Steel"], role="camera_mount_post")
        self._cube(stage, "/World/Cell/Sensors/Crossbar", (0.09, 2.1, 0.09), (-0.35, 0.0, 2.48), self.materials["Steel"], role="camera_mount_crossbar")
        self._cube(stage, "/World/Cell/Sensors/RGBHousing", (0.20, 0.22, 0.13), (-0.42, -0.14, 2.36), self.materials["Sensor"], collision=False, role="rgb_camera_housing")
        self._cube(stage, "/World/Cell/Sensors/DepthHousing", (0.20, 0.22, 0.13), (-0.42, 0.14, 2.36), self.materials["Sensor"], collision=False, role="depth_camera_housing")
        overhead = UsdGeom.Camera.Define(stage, "/World/Cell/Sensors/OverheadCamera")
        overhead.CreateFocalLengthAttr(18.0)
        overhead.CreateHorizontalApertureAttr(20.955)
        overhead.CreateVerticalApertureAttr(15.71625)
        overhead.AddTranslateOp().Set(Gf.Vec3d(-0.35, 0.0, 2.31))
        self._label(overhead.GetPrim(), "calibrated_overhead_rgbd_camera", "simulated_sensor")
        presentation = UsdGeom.Camera.Define(stage, "/World/Cell/Sensors/PresentationCamera")
        presentation.CreateFocalLengthAttr(24.0)
        presentation.CreateHorizontalApertureAttr(20.955)
        presentation.CreateVerticalApertureAttr(11.7871875)
        self._label(presentation.GetPrim(), "cell_demonstration_camera", "simulated_sensor")
        self._frame(stage, "/World/Cell/Frames/camera", "camera", (-0.35, 0.0, 2.31))
        self._frame(stage, "/World/Cell/Frames/camera_calibration_target", "camera_calibration_target", (-0.35, 0.0, 0.82))
        self._cube(stage, "/World/Cell/Sensors/PhotoeyeTx", (0.08, 0.08, 0.17), (-1.45, -0.56, 0.95), self.materials["Sensor"], collision=False, role="conveyor_photoeye_transmitter")
        self._cube(stage, "/World/Cell/Sensors/PhotoeyeRx", (0.08, 0.08, 0.17), (-1.45, 0.56, 0.95), self.materials["Sensor"], collision=False, role="conveyor_photoeye_receiver")
        self._cube(stage, "/World/Cell/Sensors/PhotoeyeBeam", (0.018, 1.0, 0.018), (-1.45, 0.0, 0.95), self.materials["SignalGreen"], collision=False, role="photoeye_beam")

    def _build_guards(self, stage: Any) -> None:
        UsdGeom = self._imports()[3]
        UsdGeom.Xform.Define(stage, "/World/Cell/Guards")
        posts = ((-2.55, -2.15), (-2.55, 2.15), (3.2, -2.15), (3.2, 2.15), (0.3, -2.15), (0.3, 2.15))
        for index, (x, y) in enumerate(posts):
            self._cube(stage, f"/World/Cell/Guards/Post_{index}", (0.075, 0.075, 2.05), (x, y, 1.03), self.materials["SafetyYellow"], role="guard_post")
        self._cube(stage, "/World/Cell/Guards/BackPanel", (5.75, 0.025, 1.65), (0.325, 2.15, 1.05), self.materials["Glass"], collision=False, role="transparent_guard_panel")
        self._cube(stage, "/World/Cell/Guards/FrontLeftPanel", (2.8, 0.025, 1.65), (-1.15, -2.15, 1.05), self.materials["Glass"], collision=False, role="transparent_guard_panel")
        self._cube(stage, "/World/Cell/Guards/FrontRightPanel", (2.25, 0.025, 1.65), (2.05, -2.15, 1.05), self.materials["Glass"], collision=False, role="transparent_guard_panel")
        for y, name in ((-2.15, "Front"), (2.15, "Back")):
            self._cube(stage, f"/World/Cell/Guards/{name}TopRail", (5.75, 0.07, 0.07), (0.325, y, 2.08), self.materials["SafetyYellow"], role="guard_top_rail")

    def build(self, stage: Any) -> dict[str, Any]:
        Gf, PhysxSchema, Sdf, UsdGeom, UsdLux, UsdPhysics, _ = self._imports()
        if not self.robot_asset.is_file():
            raise FileNotFoundError(self.robot_asset)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        stage.SetTimeCodesPerSecond(240)
        world = UsdGeom.Xform.Define(stage, "/World")
        stage.SetDefaultPrim(world.GetPrim())
        world.GetPrim().CreateAttribute("meatcell:sceneVersion", Sdf.ValueTypeNames.String).Set("2.0")
        world.GetPrim().CreateAttribute("meatcell:referenceAssetNotice", Sdf.ValueTypeNames.String).Set(REFERENCE_NOTICE)
        world.GetPrim().CreateAttribute("meatcell:conveyorSpeedMps", Sdf.ValueTypeNames.Double).Set(2.24)
        UsdGeom.Xform.Define(stage, "/World/Looks")
        UsdGeom.Xform.Define(stage, "/World/Cell")
        UsdGeom.Xform.Define(stage, "/World/Cell/Frames")
        physics = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
        physics.CreateGravityDirectionAttr(Gf.Vec3f(0.0, 0.0, -1.0))
        physics.CreateGravityMagnitudeAttr(9.80665)
        scene_api = PhysxSchema.PhysxSceneAPI.Apply(physics.GetPrim())
        scene_api.CreateEnableCCDAttr(True)
        scene_api.CreateEnableStabilizationAttr(True)
        self._build_materials(stage)
        self._cube(stage, "/World/Cell/Floor", (6.4, 4.8, 0.10), (0.3, 0.0, -0.05), self.materials["Floor"], role="washdown_floor_reference")
        for y in (-1.72, 1.72):
            self._cube(stage, f"/World/Cell/Drain_{'L' if y > 0 else 'R'}", (5.6, 0.11, 0.018), (0.2, y, 0.01), self.materials["DarkSteel"], collision=False, role="floor_drain_reference")
        self._build_conveyor(stage)
        self._build_robot(stage)
        self._build_cutter_and_reject(stage)
        self._build_sensors(stage)
        self._build_guards(stage)
        UsdGeom.Xform.Define(stage, "/World/Cell/Workpieces")
        products = (
            self._product(stage, "/World/Cell/Workpieces/PorkLoin_01", (-1.18, 0.03, 0.875), 7.0, self.materials["Meat"]),
            self._product(stage, "/World/Cell/Workpieces/PorkLoin_02", (-0.48, -0.10, 0.875), -5.0, self.materials["Meat"]),
            self._product(stage, "/World/Cell/Workpieces/PorkLoin_03", (0.30, 0.08, 0.875), 9.0, self.materials["Meat"]),
        )
        plc = UsdGeom.Xform.Define(stage, "/World/Cell/PLC")
        self._label(plc.GetPrim(), "simulated_plc_machine_io", "implemented")
        for name, value_type, value in (
            ("conveyorSpeedMps", Sdf.ValueTypeNames.Double, 2.24),
            ("recipeId", Sdf.ValueTypeNames.String, "pork_boneless_loin"),
            ("cutterReady", Sdf.ValueTypeNames.Bool, True),
            ("trayClear", Sdf.ValueTypeNames.Bool, True),
            ("faultActive", Sdf.ValueTypeNames.Bool, False),
            ("emergencyStop", Sdf.ValueTypeNames.Bool, False),
        ):
            plc.GetPrim().CreateAttribute(f"meatcell:{name}", value_type).Set(value)
        dome = UsdLux.DomeLight.Define(stage, "/World/Lights/Dome")
        dome.CreateIntensityAttr(900.0)
        dome.CreateColorAttr(Gf.Vec3f(0.82, 0.88, 1.0))
        for index, (x, y) in enumerate(((-0.7, -1.1), (1.6, 1.0), (2.3, -1.4))):
            light = UsdLux.RectLight.Define(stage, f"/World/Lights/Panel_{index}")
            light.CreateIntensityAttr(4500.0)
            light.CreateWidthAttr(1.6)
            light.CreateHeightAttr(0.8)
            light.CreateColorAttr(Gf.Vec3f(1.0, 0.94, 0.84))
            light.AddTranslateOp().Set(Gf.Vec3d(x, y, 3.4))
        world.GetPrim().CreateAttribute("meatcell:sceneReady", Sdf.ValueTypeNames.Bool).Set(True)
        return {
            "robot_prim": ROBOT_PRIM,
            "articulation_root": ARTICULATION_ROOT,
            "joint_paths": JOINT_PATHS,
            "product_paths": tuple(str(product.GetPath()) for product in products),
            "camera_path": "/World/Cell/Sensors/OverheadCamera",
            "presentation_camera_path": "/World/Cell/Sensors/PresentationCamera",
            "reference_notice": REFERENCE_NOTICE,
        }


def stage_manifest(stage: Any) -> dict[str, Any]:
    from pxr import UsdGeom, UsdPhysics

    prims = [prim for prim in stage.Traverse() if prim.GetPath().HasPrefix("/World")]
    return {
        "prim_count": len(prims),
        "camera_paths": [str(prim.GetPath()) for prim in prims if prim.IsA(UsdGeom.Camera)],
        "revolute_joint_paths": [str(prim.GetPath()) for prim in prims if prim.IsA(UsdPhysics.RevoluteJoint)],
        "articulation_roots": [
            str(prim.GetPath()) for prim in prims if prim.HasAPI(UsdPhysics.ArticulationRootAPI)
        ],
        "role_count": sum(bool(prim.GetAttribute("meatcell:role")) for prim in prims),
    }
