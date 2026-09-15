"""The product is a pork leg, not a slab.

Footage from the customer's line shows whole bone-in legs, ham through hock to
trotter, hand-placed on a white conveyor. These tests pin the three properties
that a symmetric slab does not have, because those are what break code written
against the slab.
"""

import mujoco
import numpy as np
import pytest

from meat_cell_sim.product import (
    LEG_PROFILE,
    LENGTH_RANGE_M,
    MASS_RANGE_KG,
    LegConfig,
    leg_mesh,
    leg_population,
    product_geom_ids,
)
from meat_cell_sim.scene import CellConfig, build_model

BELT_TOP_Z_M = 0.90


@pytest.fixture(scope="module")
def leg_cell():
    config = CellConfig(belt_speed_mps=0.0, leg=LegConfig())
    model, data = build_model(config)
    return model, data, config


def test_the_leg_is_the_size_and_mass_of_a_real_one(leg_cell) -> None:
    model, _, config = leg_cell
    assert config.leg is not None
    assert 0.65 < config.leg.length_m < 0.95, "a whole pork leg runs about 700 to 900 mm"
    ham = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "slab")
    trotter = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trotter")
    assert float(model.body_mass[ham] + model.body_mass[trotter]) == pytest.approx(11.0, abs=0.01)
    assert 0.1 < float(model.body_mass[trotter]) < 1.5, "a trotter is a few hundred grams to a kilogram"


def test_the_product_is_found_by_its_body_not_by_a_geom_name(leg_cell) -> None:
    """The slab is one box and the leg is a mesh. Nothing may assume either."""
    model, _, _ = leg_cell
    ids = product_geom_ids(model)
    assert len(ids) >= 1
    geom = int(ids[0])
    assert model.geom_type[geom] == mujoco.mjtGeom.mjGEOM_MESH


def test_the_mass_centre_is_far_from_the_centre_of_the_outline(leg_cell) -> None:
    """The property a slab cannot have, and the reason a detected centroid is
    not a place to pick the product up.

    On a symmetric box the two coincide exactly. On a leg the mass sits in the
    ham while the outline runs far down a thin hock.
    """
    model, _, config = leg_cell
    assert config.leg is not None
    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "slab")
    mass_centre_x = float(model.body_ipos[body][0])
    outline_centre_x = config.leg.outline_centre_m
    assert abs(outline_centre_x - mass_centre_x) > 0.08, (
        f"mass centre {1000 * mass_centre_x:.0f} mm and outline centre "
        f"{1000 * outline_centre_x:.0f} mm are too close to make the point"
    )


def test_the_slab_keeps_the_two_centres_together(leg_cell) -> None:
    """The control arm. If this ever fails the slab has stopped being a control."""
    model, _ = build_model(CellConfig())
    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "slab")
    assert float(model.body_ipos[body][0]) == pytest.approx(0.0, abs=1e-9)


def test_the_underside_is_flat_so_the_leg_does_not_roll(leg_cell) -> None:
    """The modelling error that made the first leg wobble down the belt.

    An ellipsoid rests on a curved surface and rolls. Real meat conforms under
    its own weight and sits on a broad flat patch, which is why a leg travels as
    one piece. With the ellipsoid the tracker read 108 mm/s of slip against a
    250 mm/s belt.
    """
    _, _, config = leg_cell
    assert config.leg is not None
    vertices, _ = leg_mesh(config.leg)
    on_the_belt = vertices[vertices[:, 2] < 1e-9]
    assert len(on_the_belt) > 100, "the underside is not flat"
    width = float(on_the_belt[:, 1].max() - on_the_belt[:, 1].min())
    assert width > 0.5 * 2 * LEG_PROFILE[:, 1].max(), "the flat patch is too narrow to be stable"


def test_the_collision_shape_follows_the_shank_instead_of_bridging_the_waist(leg_cell) -> None:
    """A single hull from butt to hock was 148.6 mm wide where the shank is 101.3 mm.

    A jaw closed on that invisible hull and never touched the leg. Each ham
    section's hull must now be no wider than the widest drawn cross section it
    spans, plus a millimetre of tessellation.
    """
    from meat_cell_sim.product import HAM_GEOMS, HAM_SECTION_FRACTIONS, leg_half_width_m

    model, _, config = leg_cell
    assert config.leg is not None
    # A fresh state puts the leg at its reference pose, so the leg's own y axis,
    # across the leg, is world y. MuJoCo stores each mesh in its principal-axis
    # frame, so widths are measured on the vertices placed in the world.
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "slab")
    assert data.xmat[body].reshape(3, 3) == pytest.approx(np.eye(3))
    for index, name in enumerate(HAM_GEOMS):
        geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
        mesh = int(model.geom_dataid[geom])
        start, count = int(model.mesh_vertadr[mesh]), int(model.mesh_vertnum[mesh])
        world = data.geom_xpos[geom] + model.mesh_vert[start : start + count] @ data.geom_xmat[geom].reshape(3, 3).T
        across = float(np.ptp(world[:, 1]))
        fractions = np.linspace(HAM_SECTION_FRACTIONS[index], HAM_SECTION_FRACTIONS[index + 1], 50)
        widest = 2.0 * float(leg_half_width_m(config.leg, fractions).max())
        assert across <= widest + 0.001, f"{name} hull is {1000 * across:.1f} mm across, drawn {1000 * widest:.1f}"


def test_a_trotter_hanging_past_the_belt_edge_stays_in_line_with_the_ham() -> None:
    """The trotter is bone. At the weld's default softness it sagged 116.7 mm at the tip.

    Placed square across the belt with the hock 30 mm outside the open edge, the
    trotter has nothing under it, and after 2 s it must still be within 2 mm and
    half a degree of where a rigid leg would put it.
    """
    from meat_cell_sim.product import leg_centreline

    leg = LegConfig()
    model, data = build_model(CellConfig(belt_speed_mps=0.0, leg=leg))
    pose = [0.30, 0.12 + leg.hock_offset_m, BELT_TOP_Z_M, np.cos(-np.pi / 4), 0.0, 0.0, np.sin(-np.pi / 4)]
    for joint in ("slab_free", "trotter_free"):
        adr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint)]
        data.qpos[adr : adr + 7] = pose
    mujoco.mj_forward(model, data)
    for _ in range(int(2.0 / model.opt.timestep)):
        mujoco.mj_step(model, data)
    ham = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "slab")
    trotter = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trotter")
    tip = leg_centreline(leg, np.array([1.0]))[0]
    as_welded = data.xpos[trotter] + data.xmat[trotter].reshape(3, 3) @ tip
    as_rigid = data.xpos[ham] + data.xmat[ham].reshape(3, 3) @ tip
    relative = data.xmat[ham].reshape(3, 3).T @ data.xmat[trotter].reshape(3, 3)
    angle_deg = np.degrees(np.arccos(np.clip((np.trace(relative) - 1.0) / 2.0, -1.0, 1.0)))
    assert float(np.linalg.norm(as_welded - as_rigid)) < 0.002
    assert angle_deg < 0.5


def test_a_rounded_underside_is_refused_as_a_configuration(leg_cell) -> None:
    with pytest.raises(ValueError, match="flatten fraction"):
        LegConfig(flatten_fraction=1.5)


def test_the_leg_lies_flat_rather_than_balancing_on_its_ham(leg_cell) -> None:
    """The hock and trotter were on the body centre line, so they floated 48 mm
    above the belt, the leg tipped, and the camera saw a foreshortened outline."""
    model, data, config = leg_cell
    assert config.leg is not None
    mujoco.mj_resetData(model, data)
    adr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "slab_free")]
    data.qpos[adr : adr + 7] = [-0.40, 0.50, BELT_TOP_Z_M + config.product_rest_height_m, 1, 0, 0, 0]
    mujoco.mj_forward(model, data)
    for _ in range(int(1.0 / model.opt.timestep)):
        mujoco.mj_step(model, data)
    quaternion = data.qpos[adr + 3 : adr + 7]
    tilt_deg = np.degrees(2 * np.arccos(np.clip(abs(quaternion[0]), 0, 1)))
    assert tilt_deg < 12.0, f"the leg settled {tilt_deg:.1f} degrees off flat"

    for geom in product_geom_ids(model):
        lowest = float(data.geom_xpos[geom][2] - model.geom_aabb[geom][5])
        assert lowest < BELT_TOP_Z_M + 0.02, (
            f"{mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(geom))} floats "
            f"{1000 * (lowest - BELT_TOP_Z_M):.0f} mm above the belt"
        )


def test_a_leg_fits_the_camera_at_any_orientation(leg_cell) -> None:
    """The camera was raised from 600 to 950 mm for exactly this."""
    from meat_cell_sim.sensing import CameraSpec, Sensors

    model, data, config = leg_cell
    assert config.leg is not None
    adr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "slab_free")]
    with Sensors(model, {"overhead": CameraSpec("overhead", 640, 480, exposure_s=0.0)}) as sensors:
        for yaw in np.linspace(-np.pi / 2, np.pi / 2, 7):
            offset = config.leg.outline_centre_m
            data.qpos[adr : adr + 7] = [
                -0.40 - offset * np.cos(yaw),
                0.50 - offset * np.sin(yaw),
                BELT_TOP_Z_M + config.product_rest_height_m,
                np.cos(yaw / 2),
                0,
                0,
                np.sin(yaw / 2),
            ]
            mujoco.mj_forward(model, data)
            truth = sensors.ground_truth(data, "overhead")
            assert not truth.mask_touches_border, f"a leg at {np.degrees(yaw):.0f} degrees runs off the frame"


def test_a_population_is_reproducible_from_its_seed() -> None:
    first = leg_population(20, seed=11)
    second = leg_population(20, seed=11)
    assert [leg.length_m for leg in first] == [leg.length_m for leg in second]
    assert [leg.left_leg for leg in first] == [leg.left_leg for leg in second]


def test_a_population_spans_the_range_the_plant_produces() -> None:
    legs = leg_population(60, seed=3)
    lengths = np.array([leg.length_m for leg in legs])
    masses = np.array([leg.mass_kg for leg in legs])
    assert lengths.min() >= LENGTH_RANGE_M[0] - 1e-9
    assert lengths.max() <= LENGTH_RANGE_M[1] + 1e-9
    assert masses.min() >= MASS_RANGE_KG[0] - 1e-9
    assert masses.max() <= MASS_RANGE_KG[1] + 1e-9
    assert np.ptp(lengths) > 0.08, "the population is too uniform to test anything"
    assert 0.25 < np.mean([leg.left_leg for leg in legs]) < 0.75, "handedness should be roughly even"


def test_size_is_correlated_rather_than_drawn_independently() -> None:
    """A 15 kg leg on a 660 mm frame is not a piece the line produces.

    Length, mass and ham bulk all follow from one underlying size draw, so they
    have to come out correlated. Sampling them independently would generate
    animals that do not exist.
    """
    legs = leg_population(120, seed=5)
    lengths = np.array([leg.length_m for leg in legs])
    masses = np.array([leg.mass_kg for leg in legs])
    correlation = float(np.corrcoef(lengths, masses)[0, 1])
    assert correlation > 0.55, f"length and mass correlate at only {correlation:.2f}"


def test_handedness_mirrors_the_bend() -> None:
    """A carcass yields one left and one right leg, and they are mirror images."""
    right = LegConfig(bend_m=0.05, left_leg=False)
    left = LegConfig(bend_m=0.05, left_leg=True)
    right_vertices, _ = leg_mesh(right)
    left_vertices, _ = leg_mesh(left)
    assert right_vertices[:, 1].mean() > 0
    assert left_vertices[:, 1].mean() < 0
    assert right_vertices[:, 1].mean() == pytest.approx(-left_vertices[:, 1].mean(), rel=1e-9)


def test_a_straight_leg_has_no_bend_either_way() -> None:
    vertices, _ = leg_mesh(LegConfig(bend_m=0.0))
    assert vertices[:, 1].mean() == pytest.approx(0.0, abs=1e-9)
