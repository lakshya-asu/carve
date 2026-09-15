"""What is actually on the belt.

The cell was built around a 180 x 90 x 30 mm rigid slab weighing half a
kilogram. Footage from the customer's line shows something else entirely: whole
bone-in pork legs, ham at one end tapering through a hock to a trotter, placed
by hand on a white conveyor. That difference is not cosmetic. It breaks three
assumptions the earlier work rested on.

**The silhouette centroid is not the mass centroid.** On a slab they coincide by
symmetry. On a leg the mass sits in the ham while the outline runs far down a
thin hock, so the two are tens of millimetres apart. Anything that treated the
image centroid as a balance point was relying on the slab's symmetry without
saying so.

**The principal axis is dominated by the shape, not by the meat.** Principal
component analysis on a leg's silhouette is pulled along the hock, which carries
little of the mass and none of the value.

**There is a rigid handle.** The hock is bone-in, so unlike the rest of the
piece it does not deform under a gripper. A grasp plan for a leg wants to find
that handle, which is a different problem from finding the middle of a slab.

The leg is two bodies welded at the hock joint: the ham and shank, and the
trotter. The station exists so a saw can take the trotter off at that joint, and
a single rigid body cannot lose its foot. Cutting is switching the weld off.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass

import mujoco
import numpy as np

logger = logging.getLogger(__name__)

PRODUCT_BODY = "slab"
PRODUCT_GEOM = "slab_geom"
TROTTER_BODY = "trotter"
TROTTER_JOINT = "trotter_free"
TROTTER_GEOM = "trotter_geom"
TROTTER_WELD = "trotter_weld"
LEG_SKIN_GEOM = "leg_skin"
LEG_RGB = (0.87, 0.71, 0.68)  # the slab_mat colour in cell.xml


@dataclass(frozen=True)
class LegConfig:
    """A whole bone-in pork leg: ham, hock, trotter, lying on its side.

    Defaults are read off the customer's footage and from published carcass
    data, and every one is an assumption until the customer measures their own
    product. See `library/topics/pork-processing-line.md`.

    Attributes:
        length_m: Overall length, ham butt to trotter tip.
        width_scale: Multiplies the profile's half widths, for a broader or
            narrower leg.
        height_scale: Multiplies the profile's half heights.
        flatten_fraction: How much of each cross section is cut away by the belt
            plane. Zero gives a rounded underside that rolls; the default gives
            a flat contact patch roughly 60 percent of the piece's width, which
            is what a soft piece conforming under its own weight looks like.
        mass_kg: Total mass, ham and trotter together. Split between the two
            bodies by volume.
        friction_slide: Sliding friction against the belt.
    """

    length_m: float = 0.722
    width_scale: float = 1.0
    height_scale: float = 1.0
    flatten_fraction: float = 0.30
    mass_kg: float = 11.0
    friction_slide: float = 0.45
    bend_m: float = 0.0
    ham_bulge: float = 1.0
    hock_slenderness: float = 1.0
    left_leg: bool = False
    name: str = "pork_leg"

    def __post_init__(self) -> None:
        if self.length_m <= 0:
            raise ValueError(f"length must be positive, got {self.length_m}")
        if self.mass_kg <= 0:
            raise ValueError(f"mass must be positive, got {self.mass_kg}")
        if not 0.0 <= self.flatten_fraction < 1.0:
            raise ValueError(f"flatten fraction must be in [0, 1), got {self.flatten_fraction}")
        if not 0.5 <= self.ham_bulge <= 1.6:
            raise ValueError(f"ham bulge must be in [0.5, 1.6], got {self.ham_bulge}")
        if not 0.5 <= self.hock_slenderness <= 1.6:
            raise ValueError(f"hock slenderness must be in [0.5, 1.6], got {self.hock_slenderness}")

    @property
    def rest_height_m(self) -> float:
        """Height of the body origin above the belt at rest.

        Zero: the mesh is built with its underside on its own origin plane, so
        the body origin sits exactly on the belt surface.
        """
        return 0.0

    @property
    def outline_centre_m(self) -> float:
        """Midpoint of the outline along x, in the body frame.

        Not the body origin and not the centre of mass. The origin sits in the
        ham, so placing the product "at x" puts its origin there and leaves the
        trotter half a metre downstream, which is how a leg ended up with its
        foot outside the camera's field.
        """
        return (0.5 - ORIGIN_FRACTION) * self.length_m

    @property
    def trotter_offset_m(self) -> float:
        """Distance from the body origin to the trotter tip, along +x.

        The station's whole job is putting this end off the side of the belt, so
        it is the number the task is defined against.
        """
        return (1.0 - ORIGIN_FRACTION) * self.length_m

    @property
    def hock_offset_m(self) -> float:
        """Distance from the body origin to the hock joint, along +x.

        Where the saw should cut. Every cut is scored against this point.
        """
        return (HOCK_FRACTION - ORIGIN_FRACTION) * self.length_m


# Cross sections along the leg: (fraction of the length, half width, half
# height) in metres. Read off the customer's footage: a bulky ham, a waist, a
# slender hock and a small trotter. Not anatomy, but the right silhouette and
# the right mass distribution.
LEG_PROFILE = np.array(
    [
        [0.00, 0.085, 0.070],
        [0.10, 0.120, 0.095],
        [0.28, 0.125, 0.098],
        [0.45, 0.092, 0.082],
        [0.55, 0.058, 0.058],
        [0.70, 0.048, 0.048],
        [0.85, 0.040, 0.042],
        [0.93, 0.038, 0.040],
        [1.00, 0.012, 0.014],
    ]
)

# Where along the leg the body origin sits. Placed in the ham so the origin is
# near the centre of mass rather than the centre of the outline.
ORIGIN_FRACTION = 0.28

# Where along the leg the hock joint sits, and so where the trotter comes off.
# Read off the customer's footage, where the foot below the hock is roughly a
# quarter of the leg: 173 mm on the default 722 mm leg. Unmeasured; replace with
# calipered legs from the line.
HOCK_FRACTION = 0.76

# The ham body collides as a chain of short convex sections, not one mesh.
# MuJoCo collides a mesh by its convex hull, and a single hull from the butt to
# the hock bridges the waist: at the shank grasp point it was 148.6 mm wide
# against a 101.3 mm shank, and a jaw closed on that invisible hull, never
# touching the leg. Short sections hug the outline; they are densest where the
# profile narrows fastest, through the waist.
HAM_SECTION_FRACTIONS = (0.0, 0.14, 0.28, 0.40, 0.50, 0.58, 0.66, HOCK_FRACTION)
HAM_GEOMS = (PRODUCT_GEOM, *(f"ham_section_{i}" for i in range(1, len(HAM_SECTION_FRACTIONS) - 1)))
LEG_COLLISION_GEOMS = (*HAM_GEOMS, TROTTER_GEOM)


def _sections(config: LegConfig, fraction: np.ndarray) -> tuple[np.ndarray, ...]:
    """Cross-section geometry at each fraction of the length, in the body frame.

    Returns:
        (x, lateral, half_width, half_height, centre_z), each shaped like
        `fraction`. `lateral` is the centreline's sideways swing from the bend,
        `centre_z` the height of the section's centre above the belt.
    """
    # The ham and the hock vary independently between animals: a heavy pig can
    # carry a much bulkier ham on a hock of ordinary thickness. Blend the two
    # scalings across the waist rather than scaling the whole piece.
    toward_hock = np.clip((fraction - 0.35) / 0.25, 0.0, 1.0)
    part_scale = config.ham_bulge * (1.0 - toward_hock) + config.hock_slenderness * toward_hock
    half_width = np.interp(fraction, LEG_PROFILE[:, 0], LEG_PROFILE[:, 1]) * config.width_scale * part_scale
    half_height = np.interp(fraction, LEG_PROFILE[:, 0], LEG_PROFILE[:, 2]) * config.height_scale * part_scale
    flatten = config.flatten_fraction * np.clip((0.92 - fraction) / 0.92, 0.0, 1.0)
    centre_z = half_height * (1.0 - flatten)
    x = (fraction - ORIGIN_FRACTION) * config.length_m

    # A real leg is not straight: the hock swings out from the line of the ham,
    # and which way it swings is what makes a leg a left or a right. The bend
    # starts at the waist and grows toward the trotter.
    swing = np.clip((fraction - 0.40) / 0.60, 0.0, 1.0) ** 1.6
    lateral = config.bend_m * swing * (-1.0 if config.left_leg else 1.0)
    return x, lateral, half_width, half_height, centre_z


def leg_centreline(config: LegConfig, fraction: np.ndarray) -> np.ndarray:
    """Points on the leg's centreline, in the body frame.

    The saw scores its cut against this line, so it has to follow the bend: on a
    bent leg the hock is not on the body's x axis.

    Returns:
        (N, 3) array of (x, y, z) in metres for N fractions.
    """
    x, lateral, _, _, centre_z = _sections(config, np.asarray(fraction, dtype=float))
    return np.stack([x, lateral, centre_z], axis=-1)


def leg_half_width_m(config: LegConfig, fraction: np.ndarray) -> np.ndarray:
    """Half the leg's width across its long axis at each fraction of its length.

    The saw uses it for how much leg the blade has to travel through.
    """
    return _sections(config, np.asarray(fraction, dtype=float))[2]


def leg_mesh(
    config: LegConfig,
    stations: int = 56,
    around: int = 40,
    start_fraction: float = 0.0,
    end_fraction: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Build the leg, or one part of it, as a lofted surface with a flat underside.

    The underside is the whole point. An ellipsoid rests on a curved surface, so
    it rolls: the first leg model wobbled down the belt and the tracker read
    108 mm/s of slip against a 250 mm/s belt. Real meat does not do that,
    because it is soft and conforms to the belt under its own weight, giving a
    broad flat contact patch, and because skin and bone hold the piece together
    so it travels as one body.

    Each cross section is an ellipse whose centre sits below its own half
    height, so the bottom of the ellipse falls through the belt plane and is
    clipped flat. `flatten_fraction` sets how deep that cut is, and it tapers
    out toward the trotter, which is round and lifts clear of the belt.

    Args:
        config: The leg.
        stations: Cross sections along the part.
        around: Vertices around each cross section.
        start_fraction: Where the part starts along the leg, 0 at the ham butt.
        end_fraction: Where the part ends, 1 at the trotter tip.

    Returns:
        (vertices (N, 3) in metres, triangle indices (M, 3)). The mesh sits with
        its underside on z = 0 and its origin `ORIGIN_FRACTION` along the whole
        leg, whichever part is built, so the parts line up in one body frame.
    """
    if not 0.0 <= start_fraction < end_fraction <= 1.0:
        raise ValueError(f"need 0 <= start < end <= 1, got {start_fraction} and {end_fraction}")
    fraction = np.linspace(start_fraction, end_fraction, stations)
    x, lateral, half_width, half_height, centre_z = _sections(config, fraction)
    theta = np.linspace(0.0, 2.0 * np.pi, around, endpoint=False)

    ring = np.empty((stations, around, 3))
    ring[:, :, 0] = x[:, None]
    ring[:, :, 1] = lateral[:, None] + half_width[:, None] * np.cos(theta)[None, :]
    ring[:, :, 2] = np.maximum(centre_z[:, None] + half_height[:, None] * np.sin(theta)[None, :], 0.0)

    faces: list[list[int]] = []
    for i in range(stations - 1):
        for k in range(around):
            a, b = i * around + k, i * around + (k + 1) % around
            c, d = (i + 1) * around + (k + 1) % around, (i + 1) * around + k
            faces.append([a, b, c])
            faces.append([a, c, d])

    vertices = ring.reshape(-1, 3)
    back_centre = len(vertices)
    vertices = np.vstack([vertices, ring[0].mean(axis=0)])
    front_centre = len(vertices)
    vertices = np.vstack([vertices, ring[-1].mean(axis=0)])
    for k in range(around):
        faces.append([back_centre, (k + 1) % around, k])
        last = (stations - 1) * around
        faces.append([front_centre, last + k, last + (k + 1) % around])
    return vertices, np.array(faces, dtype=np.int32)


def _mesh_volume_m3(vertices: np.ndarray, faces: np.ndarray) -> float:
    """Enclosed volume of a closed triangle mesh, by the divergence theorem."""
    a, b, c = vertices[faces[:, 0]], vertices[faces[:, 1]], vertices[faces[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)


def add_leg_geoms(spec: mujoco.MjSpec, config: LegConfig) -> None:
    """Turn the product body into a leg: ham body plus a trotter welded at the hock.

    The ham keeps the product body, its free joint and its name, so every
    contract, test and sensor that refers to the product keeps working. The
    trotter is a second free body in the same frame, held by a weld with an
    identity relative pose. Contact between the two is excluded: they share a
    face at the hock, and contact there would fight the weld.

    The ham collides as the short convex sections in `HAM_SECTION_FRACTIONS`,
    each a mesh geom on the ham body, so the collision outline follows the
    drawn one through the waist instead of bridging it. Every section's hull is
    still flat-bottomed, which is what makes the piece sit still. Mass is shared
    between the sections and the trotter by volume.
    """
    sections = []
    for index, (start, end) in enumerate(itertools.pairwise(HAM_SECTION_FRACTIONS)):
        stations = max(4, round(56 * (end - start)) + 2)
        sections.append(
            (HAM_GEOMS[index], *leg_mesh(config, stations=stations, start_fraction=start, end_fraction=end))
        )
    trotter_vertices, trotter_faces = leg_mesh(config, stations=16, start_fraction=HOCK_FRACTION)
    volumes = [_mesh_volume_m3(vertices, faces) for _, vertices, faces in sections]
    trotter_volume = _mesh_volume_m3(trotter_vertices, trotter_faces)
    total_volume = sum(volumes) + trotter_volume
    trotter_mass = config.mass_kg * trotter_volume / total_volume

    skin_vertices, skin_faces = leg_mesh(config)
    for mesh_name, vertices, faces in (
        *((f"{config.name}_{name}", vertices, faces) for name, vertices, faces in sections),
        (f"{config.name}_trotter", trotter_vertices, trotter_faces),
        (f"{config.name}_skin", skin_vertices, skin_faces),
    ):
        mesh = spec.add_mesh()
        mesh.name = mesh_name
        mesh.uservert = vertices.flatten().tolist()
        mesh.userface = faces.flatten().tolist()

    # Until the saw cuts, the camera and the video see one unbroken leg: the skin
    # is drawn and the collision parts are not. Parts meeting at the hock draw a
    # visible seam, which reads as a leg cut before it reaches the blade. The saw
    # swaps the visibility when it cuts. Colours are set per geom rather than
    # through a material so they can be switched at run time.
    product = spec.body(PRODUCT_BODY)
    ham = spec.geom(PRODUCT_GEOM)
    for (name, _, _), volume in zip(sections, volumes, strict=True):
        geom = ham if name == PRODUCT_GEOM else product.add_geom(name=name)
        geom.type = mujoco.mjtGeom.mjGEOM_MESH
        geom.meshname = f"{config.name}_{name}"
        geom.pos[:3] = [0.0, 0.0, 0.0]
        geom.mass = config.mass_kg * volume / total_volume
        geom.friction[0] = config.friction_slide
        geom.condim = 4
        geom.material = ""
        geom.rgba[:] = [*LEG_RGB, 0.0]
        if geom is not ham:
            geom.solref[:] = ham.solref
            geom.solimp[:] = ham.solimp

    skin = product.add_geom(name=LEG_SKIN_GEOM, type=mujoco.mjtGeom.mjGEOM_MESH, meshname=f"{config.name}_skin")
    skin.contype = 0
    skin.conaffinity = 0
    skin.density = 0.0
    skin.rgba[:] = [*LEG_RGB, 1.0]

    trotter_body = spec.worldbody.add_body(name=TROTTER_BODY, pos=list(product.pos))
    trotter_body.add_freejoint(name=TROTTER_JOINT)
    trotter = trotter_body.add_geom(
        name=TROTTER_GEOM, type=mujoco.mjtGeom.mjGEOM_MESH, meshname=f"{config.name}_trotter"
    )
    trotter.mass = trotter_mass
    trotter.rgba[:] = [*LEG_RGB, 0.0]
    trotter.friction[:] = ham.friction
    trotter.condim = 4
    trotter.solref[:] = ham.solref
    trotter.solimp[:] = ham.solimp

    weld = spec.add_equality(name=TROTTER_WELD)
    weld.type = mujoco.mjtEq.mjEQ_WELD
    weld.objtype = mujoco.mjtObj.mjOBJ_BODY
    weld.name1 = PRODUCT_BODY
    weld.name2 = TROTTER_BODY
    # anchor (3), relative position (3), relative quaternion (4), torque scale.
    weld.data[:11] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    # Stiff, because the trotter is bone. At MuJoCo's default softness a trotter
    # overhanging the belt edge sagged about the body origin, 433 mm back in the
    # ham: its tip hung 116.7 mm (12.86 deg) below where a rigid joint holds it,
    # below the belt surface, and a gripper closing on the drawn trotter closed
    # on air. With these values the tip sits 0.1 mm (0.01 deg) off after 2 s
    # (measured 2026-09-14). The time constant is the smallest stable at a 2 ms
    # step.
    weld.solref[:2] = [0.004, 1.0]
    weld.solimp[:3] = [0.99, 0.999, 0.0001]

    exclude = spec.add_exclude()
    exclude.bodyname1 = PRODUCT_BODY
    exclude.bodyname2 = TROTTER_BODY

    logger.info(
        "leg: %.0f mm long, %.1f kg, trotter %.0f mm and %.2f kg welded at the hock",
        1000 * config.length_m,
        config.mass_kg,
        1000 * (1.0 - HOCK_FRACTION) * config.length_m,
        trotter_mass,
    )


def product_geom_ids(model: mujoco.MjModel) -> np.ndarray:
    """Every geom belonging to the product: the slab, or the ham and the trotter.

    A segmentation mask of the product is the union over these. Nothing may
    assume a single id.
    """
    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
    if body < 0:
        raise ValueError(f"no body named {PRODUCT_BODY!r}")
    bodies = [body]
    trotter = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, TROTTER_BODY)
    if trotter >= 0:
        bodies.append(trotter)
    return np.concatenate(
        [np.arange(int(model.body_geomadr[b]), int(model.body_geomadr[b]) + int(model.body_geomnum[b])) for b in bodies]
    )


# Fresh leg mass at a curing plant runs 11.8 to 18.0 kg under the Parma PDO
# specification, which is the most precise public description of a fresh pork
# leg that exists. The customer's plant is unmeasured, so this range is set a
# little wider and a little lighter to cover ordinary fresh trade as well.
# Replace it with 50 weighed legs from the line.
MASS_RANGE_KG = (9.0, 15.5)
LENGTH_RANGE_M = (0.655, 0.815)


def random_leg(rng: np.random.Generator, index: int = 0) -> LegConfig:
    """Sample one leg from the population the line produces.

    Every dimension varies between animals and none of them varies
    independently: a heavy pig grows a long leg with a bulky ham, so length,
    mass and ham bulge are drawn from one underlying size draw and then given
    their own scatter on top. Treating them as independent would generate
    pieces that do not occur, like a 15 kg leg on a slender 660 mm frame.

    Handedness is a real and useful axis: a carcass yields one left and one
    right leg, they are mirror images, and a gripper or a fixture that works on
    one may not work on the other. Mayekawa's ham boning machine handles the two
    separately for exactly this reason.

    Args:
        rng: Seeded generator.
        index: Used only to name the mesh, so several legs can share a model.
    """
    size = float(rng.normal(0.0, 1.0))  # one underlying "how big is this pig"
    length = float(np.clip(np.mean(LENGTH_RANGE_M) + 0.045 * size + rng.normal(0.0, 0.012), *LENGTH_RANGE_M))
    mass = float(np.clip(12.0 + 1.7 * size + rng.normal(0.0, 0.7), *MASS_RANGE_KG))
    return LegConfig(
        length_m=length,
        width_scale=float(np.clip(1.0 + 0.06 * size + rng.normal(0.0, 0.05), 0.85, 1.20)),
        height_scale=float(np.clip(1.0 + 0.05 * size + rng.normal(0.0, 0.05), 0.85, 1.18)),
        mass_kg=mass,
        # How far the hock swings off the line of the ham. Measured on nothing;
        # read off the customer's footage, where the foot clearly sits off axis.
        bend_m=float(abs(rng.normal(0.0, 0.030))),
        ham_bulge=float(np.clip(1.0 + 0.07 * size + rng.normal(0.0, 0.07), 0.80, 1.30)),
        hock_slenderness=float(np.clip(rng.normal(1.0, 0.09), 0.75, 1.30)),
        left_leg=bool(rng.random() < 0.5),
        name=f"pork_leg_{index}",
    )


def leg_population(count: int, seed: int = 0) -> list[LegConfig]:
    """A batch of legs, reproducible from the seed alone."""
    rng = np.random.default_rng(seed)
    return [random_leg(rng, index) for index in range(count)]
