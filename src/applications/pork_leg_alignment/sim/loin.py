"""A bone-in pork loin, the piece the loin puller infeed handles.

The loin puller pulls the loin free of its bone rather than cutting it, so the
piece that reaches the machine is the whole bone-in loin: a long, flat-bottomed
primal with the chine and rib ends standing along one long edge and the softer
belly edge along the other. Nothing is cut off it in this cell, so unlike the
leg it is one rigid body with no weld.

Every dimension here is derived or assumed, and each is named in the record
(`experiments/2026-09-16-loin-infeed-transfer.md`). The one public figure is
the mass: the USDA cutout puts the loin primal at 25.17 percent of a 97.5 kg
carcass, 24.5 kg per carcass and 12.3 kg per side
(`library/topics/pork-processing-line.md` 4.1). The length, the cross section
and which edge stands higher are unmeasured; the profile below holds the derived
mass at an assumed 1050 kg/m^3 over an assumed 0.72 m.

What the shape must get right for the skills, in order: a flat underside, so
the piece sits still on the belt as the leg model learned to (`product.py`,
`leg_mesh`); a width at the centre of gravity, because that is where the
starting grasp rule closes the jaws across the piece (Section 14.2 of the
plan); and an asymmetry across the piece, the bone edge taller than the belly
edge, because that is the only feature the plan trusts to sign the piece's
pose. The outline along the length is nearly even on purpose: whether a real
loin's ends differ enough to sign its heading is unverified, and the model
should not hand the perception a cue the plant may not provide.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import mujoco
import numpy as np

from applications.pork_leg_alignment.sim.product import PRODUCT_GEOM, loft_mesh

logger = logging.getLogger(__name__)

# 12.3 kg: the cutout's loin primal for one side, derived as the module docstring says.
NOMINAL_MASS_KG = 12.3
# Plus or minus 20 percent of the nominal, for the spread of carcass weights
# behind one cutout figure. The spread at the plant is unmeasured.
MASS_RANGE_KG = (9.8, 14.8)
# No source gives a loin's length. A market pig's back from the second rib to
# the hip is about this; unverified.
LENGTH_RANGE_M = (0.64, 0.80)
# How much the bone edge stands above the belly edge: the top of each section
# is scaled by (1 + BONE_SKEW * u) with u from -1 at the belly edge to +1 at
# the bone edge, so the ridge sits toward the bone. Assumed.
BONE_SKEW = 0.40
# Where the loin cell hangs its overhead camera: over the pick zone as the leg
# cell does (cell.xml), but 1.20 m above the belt instead of 0.95 m so the
# field's short axis holds the longest piece lying across the belt at either
# edge of the arrival band (y 0.40 to 0.60 m): a 0.80 m piece centred at
# y 0.40 reaches 0.50 m from the camera's axis, and the field is measured at
# the piece's top, 0.10 m nearer the camera than the belt. The leg cell's
# height did not hold its longest leg (Section 14.2 of the plan); checked in
# test_loin.py.
OVERHEAD_CAMERA_MOUNT_M = (-0.40, 0.50, 2.10)


@dataclass(frozen=True)
class LoinConfig:
    """A whole bone-in pork loin lying flat on the belt, bone edge along one side.

    Attributes:
        length_m: Overall length, blade end to sirloin end.
        width_scale: Multiplies the profile's half widths.
        height_scale: Multiplies the profile's half heights.
        flatten_fraction: How much of each cross section the belt plane cuts
            away, as for the leg: zero rolls, the default gives a broad flat
            contact patch.
        mass_kg: Mass of the one body.
        friction_slide: Sliding friction against the belt.
        bone_on_left: Which long edge the bone lies along, looking along the
            body's +x axis: True puts it on the +y side. The two loins of a
            carcass are mirror images, as its two legs are.
        name: Mesh name prefix, so several loins can share one model.
    """

    length_m: float = 0.72
    width_scale: float = 1.0
    height_scale: float = 1.0
    flatten_fraction: float = 0.30
    mass_kg: float = NOMINAL_MASS_KG
    friction_slide: float = 0.45
    bone_on_left: bool = False
    name: str = "pork_loin"

    def __post_init__(self) -> None:
        if self.length_m <= 0:
            raise ValueError(f"length must be positive, got {self.length_m}")
        if self.mass_kg <= 0:
            raise ValueError(f"mass must be positive, got {self.mass_kg}")
        if not 0.0 <= self.flatten_fraction < 1.0:
            raise ValueError(f"flatten fraction must be in [0, 1), got {self.flatten_fraction}")

    @property
    def rest_height_m(self) -> float:
        """Height of the body origin above the belt at rest: zero, the mesh sits on its origin plane."""
        return 0.0

    @property
    def outline_centre_m(self) -> float:
        """Midpoint of the outline along x in the body frame: zero, the origin is the outline centre."""
        return 0.0

    @property
    def bone_side(self) -> float:
        """+1 when the bone edge lies on the body's +y side, -1 on its -y side."""
        return 1.0 if self.bone_on_left else -1.0

    def centreline_m(self, fraction: np.ndarray) -> np.ndarray:
        """Points on the centreline in the body frame, (N, 3): the piece is straight, so y is zero."""
        x, _, centre_z, _ = _sections(self, np.asarray(fraction, dtype=float))
        return np.stack([x, np.zeros_like(x), centre_z], axis=-1)

    def half_width_m(self, fraction: np.ndarray) -> np.ndarray:
        """Half the width across the piece at each fraction, (N,)."""
        return _sections(self, np.asarray(fraction, dtype=float))[3]

    def bone_edge_m(self, fraction: np.ndarray) -> np.ndarray:
        """Points on the bone-side edge at belt height, body frame, (N, 3).

        The edge the fixture's datum is measured against: the centreline moved
        the half width toward the bone side.
        """
        points = self.centreline_m(fraction)
        points[:, 1] += self.bone_side * self.half_width_m(fraction)
        points[:, 2] = 0.0
        return points


# Cross sections along the loin: (fraction of the length, half width, half
# height) in metres, blade end at 0 and sirloin end at 1. Nearly even along the
# length, a little wider at the blade end where the ribs are longest; the
# numbers hold the derived mass and are otherwise assumed (module docstring).
LOIN_PROFILE = np.array(
    [
        [0.00, 0.080, 0.050],
        [0.08, 0.098, 0.058],
        [0.30, 0.100, 0.060],
        [0.60, 0.094, 0.058],
        [0.85, 0.084, 0.054],
        [0.94, 0.074, 0.048],
        [1.00, 0.052, 0.036],
    ]
)


def _sections(config: LoinConfig, fraction: np.ndarray) -> tuple[np.ndarray, ...]:
    """Cross-section geometry at each fraction, body frame: (x, half_height, centre_z, half_width)."""
    half_width = np.interp(fraction, LOIN_PROFILE[:, 0], LOIN_PROFILE[:, 1]) * config.width_scale
    half_height = np.interp(fraction, LOIN_PROFILE[:, 0], LOIN_PROFILE[:, 2]) * config.height_scale
    centre_z = half_height * (1.0 - config.flatten_fraction)
    x = (fraction - 0.5) * config.length_m
    return x, half_height, centre_z, half_width


def loin_mesh(config: LoinConfig, stations: int = 48, around: int = 40) -> tuple[np.ndarray, np.ndarray]:
    """Build the loin as a lofted surface with a flat underside and a ridge toward the bone edge.

    Each cross section starts as the leg's flat-bottomed ellipse, then its
    height is scaled across the section so the bone edge stands higher than the
    belly edge (`BONE_SKEW`). The flat patch is what keeps the piece still on
    the belt; the ridge is what a height profile across the piece reads the
    bone side from.

    Returns:
        (vertices (N, 3) in metres, triangle indices (M, 3)). The underside is
        on z = 0 and the origin is the outline centre.
    """
    fraction = np.linspace(0.0, 1.0, stations)
    x, half_height, centre_z, half_width = _sections(config, fraction)
    theta = np.linspace(0.0, 2.0 * np.pi, around, endpoint=False)
    ring = np.empty((stations, around, 3))
    ring[:, :, 0] = x[:, None]
    ring[:, :, 1] = half_width[:, None] * np.cos(theta)[None, :]
    height = np.maximum(centre_z[:, None] + half_height[:, None] * np.sin(theta)[None, :], 0.0)
    toward_bone = config.bone_side * np.cos(theta)[None, :]
    ring[:, :, 2] = height * (1.0 + BONE_SKEW * toward_bone)
    return loft_mesh(ring)


def add_loin_geoms(spec: mujoco.MjSpec, config: LoinConfig) -> None:
    """Turn the product body into a loin: one mesh geom on the product body, no second body.

    The product body keeps its name and free joint, so every contract, sensor
    and test that refers to the product keeps working. One convex hull is
    enough because the outline has no waist for a hull to bridge, which is what
    forced the leg into short sections.
    """
    vertices, faces = loin_mesh(config)
    mesh = spec.add_mesh()
    mesh.name = f"{config.name}_body"
    mesh.uservert = vertices.flatten().tolist()
    mesh.userface = faces.flatten().tolist()

    geom = spec.geom(PRODUCT_GEOM)
    geom.type = mujoco.mjtGeom.mjGEOM_MESH
    geom.meshname = mesh.name
    geom.pos[:3] = [0.0, 0.0, 0.0]
    geom.mass = config.mass_kg
    geom.friction[0] = config.friction_slide
    geom.condim = 4
    logger.info(
        "loin: %.0f mm long, %.0f mm across at the widest, %.1f kg, bone on the %s",
        1000 * config.length_m,
        2000 * float(config.half_width_m(np.linspace(0.0, 1.0, 101)).max()),
        config.mass_kg,
        "left" if config.bone_on_left else "right",
    )


def random_loin(rng: np.random.Generator, index: int = 0) -> LoinConfig:
    """Sample one loin from the assumed population, as `random_leg` samples legs.

    Length, mass, width and height follow one underlying size draw with their
    own scatter on top, so a heavy piece is also a long one. Which side the
    bone lies on is drawn evenly, as a carcass gives one of each.

    Args:
        rng: Seeded generator.
        index: Used only to name the mesh, so several loins can share a model.
    """
    size = float(rng.normal(0.0, 1.0))
    length = float(np.clip(np.mean(LENGTH_RANGE_M) + 0.040 * size + rng.normal(0.0, 0.012), *LENGTH_RANGE_M))
    mass = float(np.clip(NOMINAL_MASS_KG + 1.25 * size + rng.normal(0.0, 0.5), *MASS_RANGE_KG))
    return LoinConfig(
        length_m=length,
        width_scale=float(np.clip(1.0 + 0.05 * size + rng.normal(0.0, 0.05), 0.85, 1.20)),
        height_scale=float(np.clip(1.0 + 0.05 * size + rng.normal(0.0, 0.05), 0.85, 1.18)),
        mass_kg=mass,
        bone_on_left=bool(rng.random() < 0.5),
        name=f"pork_loin_{index}",
    )


def loin_population(count: int, seed: int = 0) -> list[LoinConfig]:
    """A batch of loins, reproducible from the seed alone."""
    rng = np.random.default_rng(seed)
    return [random_loin(rng, index) for index in range(count)]
