"""Build the meat cell MuJoCo model: cell, arm, gripper, product.

The cell, the gripper, and the product are ours; the UR5e comes from MuJoCo
Menagerie and is attached at build time rather than edited, so the pinned
third-party checkout stays clean.

Every dimension the experiment sweeps lives in `CellConfig`, not in the XML, so
a run is reproducible from one config object. See
`experiments/2026-09-08-meat-cell-sim-baseline.md` for what each value is for
and which of them are assumptions waiting on the customer.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

import mujoco

from meat_cell_sim.arms import ARM_SPECS, ArmModel, build_arm
from meat_cell_sim.cameras import DepthCameraModel, add_depth_camera
from meat_cell_sim.gripper import GRIPPER_SPECS, GripperModel
from meat_cell_sim.holddown import HoldDownConfig, add_hold_down
from meat_cell_sim.product import TROTTER_BODY, LegConfig, add_leg_geoms
from meat_cell_sim.saw import SawConfig, add_saw

logger = logging.getLogger(__name__)

ASSETS = Path(__file__).parent / "assets"
MENAGERIE = Path(__file__).resolve().parents[2] / "third_party" / "mujoco_menagerie"
UR5E_XML = MENAGERIE / "universal_robots_ur5e" / "ur5e.xml"
UR5E_PIN = "8161bba"  # git SHA of the Menagerie checkout this was built against

GRIP_PREFIX = "g_"


@dataclass(frozen=True)
class ArmMount:
    """Where the arm's base stands.

    Attributes:
        x_m: Pedestal centre along the belt, world frame.
        y_m: Pedestal centre across the belt, world frame.
        z_m: Height of the arm base above the floor.
        yaw_rad: Rotation of the base about vertical; zero points the base's x
            axis along belt travel.
    """

    x_m: float
    y_m: float
    z_m: float
    yaw_rad: float = 0.0

    def __post_init__(self) -> None:
        if self.z_m <= 0:
            raise ValueError(f"mount height must be positive, got {self.z_m}")


# The UR5e stands where every earlier experiment put it. The 20 kg arms stand
# behind the far rail (rail inner face at y = 0.857), chosen by Lakshya on
# 2026-09-14 so the open edge stays clear for overhanging trotters and the saw,
# with the base turned to face the belt. The SCARA base is raised so its 300 mm
# stroke runs from above a ham (about 175 mm tall) down to a grasp at shank height.
DEFAULT_MOUNTS = {
    ArmModel.UR5E: ArmMount(x_m=0.0, y_m=0.0, z_m=0.90),
    ArmModel.UR20: ArmMount(x_m=0.0, y_m=1.10, z_m=0.90, yaw_rad=-math.pi / 2),
    ArmModel.SR20IA: ArmMount(x_m=0.0, y_m=1.10, z_m=1.10, yaw_rad=-math.pi / 2),
}


@dataclass(frozen=True)
class SlabConfig:
    """The rigid slab product. Defaults are assumptions pending customer numbers.

    Kept as the control arm of every experiment: a symmetric box is the shape for
    which the silhouette centroid, the mass centroid and the principal axis all
    coincide, so it isolates tracking and control error from shape error. The
    product the customer actually runs is a `LegConfig`.
    """

    half_extents_m: tuple[float, float, float] = (0.090, 0.045, 0.015)
    mass_kg: float = 0.5
    friction_slide: float = 0.35
    deformable: bool = False

    def __post_init__(self) -> None:
        if any(h <= 0 for h in self.half_extents_m):
            raise ValueError(f"half extents must be positive, got {self.half_extents_m}")
        if self.mass_kg <= 0:
            raise ValueError(f"mass must be positive, got {self.mass_kg}")
        if self.deformable:
            raise NotImplementedError("flex slab lands in the deformable conditions; rigid box only for now")


@dataclass(frozen=True)
class CellConfig:
    """One cell configuration: belt, product, and the physics knobs a run sweeps."""

    belt_speed_mps: float = 0.15
    belt_friction_slide: float = 0.55
    slab: SlabConfig = field(default_factory=SlabConfig)
    leg: LegConfig | None = None
    saw: SawConfig | None = None
    hold_down: HoldDownConfig | None = None
    arm: ArmModel = ArmModel.UR5E
    arm_mount: ArmMount | None = None
    gripper: GripperModel = GripperModel.PINCH
    timestep_s: float = 0.002
    # Datasheet depth cameras mounted with the overhead camera, for the camera
    # comparison (experiments/2026-09-15-depth-camera-comparison.md). Empty by
    # default so every earlier experiment builds the cell it was run on.
    depth_cameras: tuple[DepthCameraModel, ...] = ()
    # 0: image width along the belt; 90: across it.
    depth_camera_yaw_deg: float = 0.0

    @property
    def mount(self) -> ArmMount:
        """The arm mount in use: the configured one, or the default for the arm."""
        return self.arm_mount if self.arm_mount is not None else DEFAULT_MOUNTS[self.arm]

    @property
    def product_rest_height_m(self) -> float:
        """Height of the product body origin above the belt when it is at rest."""
        return self.leg.rest_height_m if self.leg is not None else self.slab.half_extents_m[2]

    def __post_init__(self) -> None:
        if not 0.0 <= self.belt_speed_mps <= 1.0:
            raise ValueError(f"belt speed must be within the actuator range 0 to 1 m/s, got {self.belt_speed_mps}")
        if self.timestep_s <= 0:
            raise ValueError(f"timestep must be positive, got {self.timestep_s}")
        if self.saw is not None and self.leg is None:
            raise ValueError("the saw cuts a trotter off a leg; a slab has none")


def _apply_config(spec: mujoco.MjSpec, config: CellConfig) -> None:
    """Push config values into the spec before compilation."""
    spec.option.timestep = config.timestep_s
    belt = spec.geom("belt_surface")
    belt.friction[0] = config.belt_friction_slide
    if config.leg is not None:
        add_leg_geoms(spec, config.leg)
    else:
        slab = spec.geom("slab_geom")
        slab.size[:3] = config.slab.half_extents_m
        slab.mass = config.slab.mass_kg
        slab.friction[0] = config.slab.friction_slide
    # Rest the product on the belt: belt top is at 0.90, so the body origin sits
    # its resting half height above it. Keeping this derived means a size sweep
    # cannot leave the product intersecting the belt at reset.
    spec.body("slab").pos[2] = 0.90 + config.product_rest_height_m
    if config.leg is not None:
        # The weld holds the trotter at an identity pose relative to the ham, so
        # the two bodies must start in the same frame.
        spec.body(TROTTER_BODY).pos[:] = spec.body("slab").pos
    if config.saw is not None:
        add_saw(spec, config.saw)


def build_spec(config: CellConfig | None = None) -> mujoco.MjSpec:
    """Assemble the full cell spec: cell, UR5e on the pedestal, gripper on the wrist.

    Args:
        config: Cell configuration; defaults are the baseline experiment's values.

    Returns:
        An uncompiled MjSpec with the arm and gripper attached.

    Raises:
        FileNotFoundError: If the Menagerie checkout is missing.
    """
    config = config or CellConfig()
    if config.arm is ArmModel.UR5E and not UR5E_XML.exists():
        raise FileNotFoundError(
            f"UR5e model not found at {UR5E_XML}. Fetch it with:\n"
            "  git clone --depth 1 --filter=blob:none --sparse "
            "https://github.com/google-deepmind/mujoco_menagerie.git third_party/mujoco_menagerie\n"
            "  cd third_party/mujoco_menagerie && git sparse-checkout set universal_robots_ur5e"
        )
    spec = mujoco.MjSpec.from_file(str(ASSETS / "cell.xml"))
    _apply_config(spec, config)
    for camera in config.depth_cameras:
        add_depth_camera(spec, camera, yaw_deg=config.depth_camera_yaw_deg)

    arm = ARM_SPECS[config.arm]
    mount = config.mount
    spec.body("pedestal").pos[:] = [mount.x_m, mount.y_m, 0.0]
    column = spec.geom("pedestal_col")
    column.size[1] = mount.z_m / 2
    column.pos[2] = mount.z_m / 2
    mount_site = spec.site("arm_mount")
    mount_site.pos[2] = mount.z_m
    mount_site.quat[:] = [math.cos(mount.yaw_rad / 2), 0.0, 0.0, math.sin(mount.yaw_rad / 2)]
    spec.attach(build_arm(config.arm), prefix=arm.prefix, site=mount_site)

    gripper = mujoco.MjSpec.from_file(str(ASSETS / GRIPPER_SPECS[config.gripper].asset))
    spec.attach(gripper, prefix=GRIP_PREFIX, site=spec.site(arm.site_name))
    # After the arm and gripper, so its actuators come after theirs.
    if config.hold_down is not None:
        add_hold_down(spec, config.hold_down)
    return spec


def build_model(config: CellConfig | None = None) -> tuple[mujoco.MjModel, mujoco.MjData]:
    """Compile the cell and return a model and a fresh data object."""
    model = build_spec(config).compile()
    data = mujoco.MjData(model)
    logger.info(
        "cell built: nq=%d nu=%d nbody=%d timestep=%.4f",
        model.nq,
        model.nu,
        model.nbody,
        model.opt.timestep,
    )
    return model, data


def save_xml(path: Path, config: CellConfig | None = None) -> Path:
    """Write the assembled model to XML, for inspection or for a ROS 2 launch.

    The written XML refers to the UR5e meshes by filename, relative to the
    Menagerie assets directory. It will not load from a bare string or from a
    directory that lacks those meshes; point `meshdir` at
    `third_party/mujoco_menagerie/universal_robots_ur5e/assets` when loading it.
    """
    xml = build_spec(config).to_xml()
    path.write_text(xml, encoding="utf-8")
    return path
