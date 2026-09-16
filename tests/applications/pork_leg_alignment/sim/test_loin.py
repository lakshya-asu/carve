"""The loin is the second product, in the same shape as the leg and with what the leg does not have.

These pin what the loin cell's skills rest on: one rigid body with no weld, a
flat underside that sits still, a width at the centre of gravity (the starting
grasp station), a bone edge that stands higher than the belly edge (the one
cue the plan trusts to sign the pose), a population from one seed, and a camera
mount high enough to hold the longest piece at any arrival.
"""

import mujoco
import numpy as np
import pytest

from applications.pork_leg_alignment.sim.loin import (
    LENGTH_RANGE_M,
    LOIN_PROFILE,
    MASS_RANGE_KG,
    NOMINAL_MASS_KG,
    OVERHEAD_CAMERA_MOUNT_M,
    LoinConfig,
    loin_mesh,
    loin_population,
)
from applications.pork_leg_alignment.sim.product import PRODUCT_BODY, TROTTER_BODY, product_body_ids, product_geom_ids
from applications.pork_leg_alignment.sim.scene import CellConfig, build_model

BELT_TOP_Z_M = 0.90


@pytest.fixture(scope="module")
def loin_cell():
    config = CellConfig(belt_speed_mps=0.0, loin=LoinConfig(), overhead_camera_mount_m=OVERHEAD_CAMERA_MOUNT_M)
    model, data = build_model(config)
    return model, data, config


def test_the_loin_is_one_body_of_the_derived_mass_with_no_weld(loin_cell) -> None:
    model, _, config = loin_cell
    assert config.loin is not None
    assert product_body_ids(model) == [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)]
    assert mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, TROTTER_BODY) < 0
    # The gripper couples its fingers with a joint equality; a weld is the leg's trotter.
    assert int((model.eq_type == mujoco.mjtEq.mjEQ_WELD).sum()) == 0, (
        "nothing is cut off a loin, so nothing is welded on"
    )
    body = product_body_ids(model)[0]
    assert float(model.body_mass[body]) == pytest.approx(NOMINAL_MASS_KG, abs=0.01)
    assert len(product_geom_ids(model)) == 1
    assert model.geom_type[product_geom_ids(model)[0]] == mujoco.mjtGeom.mjGEOM_MESH


def test_the_underside_is_flat_so_the_loin_does_not_roll() -> None:
    vertices, _ = loin_mesh(LoinConfig())
    on_the_belt = vertices[vertices[:, 2] < 1e-9]
    assert len(on_the_belt) > 100, "the underside is not flat"
    width = float(on_the_belt[:, 1].max() - on_the_belt[:, 1].min())
    assert width > 0.5 * 2 * LOIN_PROFILE[:, 1].max(), "the flat patch is too narrow to be stable"


def test_the_bone_edge_stands_higher_than_the_belly_edge_and_mirrors_with_the_side() -> None:
    """The asymmetry across the piece is what a height profile reads the bone side from."""
    for bone_on_left in (True, False):
        vertices, _ = loin_mesh(LoinConfig(bone_on_left=bone_on_left))
        near_edge = 0.8 * LOIN_PROFILE[:, 1].max()
        left = vertices[vertices[:, 1] > near_edge][:, 2].max()
        right = vertices[vertices[:, 1] < -near_edge][:, 2].max()
        taller, lower = (left, right) if bone_on_left else (right, left)
        assert taller > 1.5 * lower, f"bone edge {1000 * taller:.0f} mm against belly edge {1000 * lower:.0f} mm"
    left_vertices, _ = loin_mesh(LoinConfig(bone_on_left=True))
    right_vertices, _ = loin_mesh(LoinConfig(bone_on_left=False))
    mirrored = left_vertices.copy()
    mirrored[:, 1] *= -1.0
    assert np.allclose(np.sort(mirrored, axis=0), np.sort(right_vertices, axis=0), atol=1e-9)


def test_the_bone_edge_is_the_outline_edge_on_the_bone_side() -> None:
    loin = LoinConfig(bone_on_left=True)
    fraction = np.array([0.3, 0.5])
    edge = loin.bone_edge_m(fraction)
    assert np.allclose(edge[:, 1], loin.half_width_m(fraction))
    assert np.allclose(edge[:, 2], 0.0)
    assert np.allclose(LoinConfig(bone_on_left=False).bone_edge_m(fraction)[:, 1], -loin.half_width_m(fraction))


def test_the_mass_centre_sits_near_the_outline_centre(loin_cell) -> None:
    """Unlike the leg, the loin's outline is nearly even along its length, on purpose."""
    model, _, _ = loin_cell
    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
    assert abs(float(model.body_ipos[body][0])) < 0.05


def test_the_width_at_the_centre_of_gravity_is_the_piece_the_jaw_has_to_straddle(loin_cell) -> None:
    """The starting grasp rule closes across the piece here, so its width is the number the fit check sees."""
    model, _, config = loin_cell
    assert config.loin is not None
    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
    fraction = float(model.body_ipos[body][0]) / config.loin.length_m + 0.5
    width = 2.0 * float(config.loin.half_width_m(np.array([fraction]))[0])
    assert 0.15 < width < 0.25, f"a bone-in loin is roughly 150 to 250 mm across, got {1000 * width:.0f} mm"


def test_one_hull_is_no_wider_than_the_drawn_outline(loin_cell) -> None:
    """The leg needed short sections because one hull bridged its waist; a loin has no waist."""
    model, _, config = loin_cell
    assert config.loin is not None
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    geom = int(product_geom_ids(model)[0])
    mesh = int(model.geom_dataid[geom])
    start, count = int(model.mesh_vertadr[mesh]), int(model.mesh_vertnum[mesh])
    world = data.geom_xpos[geom] + model.mesh_vert[start : start + count] @ data.geom_xmat[geom].reshape(3, 3).T
    across = float(np.ptp(world[:, 1]))
    widest = 2.0 * float(config.loin.half_width_m(np.linspace(0.0, 1.0, 101)).max())
    assert across <= widest + 0.001


def test_the_loin_lies_flat_and_rests_on_the_belt(loin_cell) -> None:
    model, data, config = loin_cell
    mujoco.mj_resetData(model, data)
    adr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "slab_free")]
    data.qpos[adr : adr + 7] = [-0.40, 0.50, BELT_TOP_Z_M + config.product_rest_height_m, 1, 0, 0, 0]
    mujoco.mj_forward(model, data)
    for _ in range(int(1.0 / model.opt.timestep)):
        mujoco.mj_step(model, data)
    quaternion = data.qpos[adr + 3 : adr + 7]
    tilt_deg = np.degrees(2 * np.arccos(np.clip(abs(quaternion[0]), 0, 1)))
    assert tilt_deg < 5.0, f"the loin settled {tilt_deg:.1f} degrees off flat"
    geom = int(product_geom_ids(model)[0])
    lowest = float(data.geom_xpos[geom][2] - model.geom_aabb[geom][5])
    assert lowest < BELT_TOP_Z_M + 0.02, f"the loin floats {1000 * (lowest - BELT_TOP_Z_M):.0f} mm above the belt"
    assert abs(float(data.qpos[adr]) + 0.40) < 0.005, "the loin moved along the belt while settling"


def test_the_longest_loin_fits_the_overhead_camera_at_any_arrival(loin_cell) -> None:
    """Section 14.2: the camera's field must hold the longest piece at any arrival across the belt."""
    from applications.pork_leg_alignment.sim.sensing import CameraSpec, Sensors

    longest = LoinConfig(length_m=LENGTH_RANGE_M[1], width_scale=1.2)
    config = CellConfig(belt_speed_mps=0.0, loin=longest, overhead_camera_mount_m=OVERHEAD_CAMERA_MOUNT_M)
    model, data = build_model(config)
    mount = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "overhead_cam_mount")
    assert np.allclose(model.body_pos[mount], OVERHEAD_CAMERA_MOUNT_M)
    adr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "slab_free")]
    with Sensors(model, {"overhead": CameraSpec("overhead", 640, 480, exposure_s=0.0)}) as sensors:
        for y in (0.40, 0.60):
            for yaw in np.linspace(-np.pi / 2, np.pi / 2, 7):
                data.qpos[adr : adr + 7] = [-0.40, y, BELT_TOP_Z_M, np.cos(yaw / 2), 0, 0, np.sin(yaw / 2)]
                mujoco.mj_forward(model, data)
                truth = sensors.ground_truth(data, "overhead")
                assert not truth.mask_touches_border, (
                    f"at y {y} and {np.degrees(yaw):.0f} deg the loin runs off the frame"
                )


def test_the_leg_cell_keeps_its_camera_where_the_xml_puts_it() -> None:
    model, _ = build_model(CellConfig())
    mount = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "overhead_cam_mount")
    assert np.allclose(model.body_pos[mount], [-0.40, 0.50, 1.85])


def test_a_leg_and_a_loin_in_one_cell_is_refused() -> None:
    from applications.pork_leg_alignment.sim.product import LegConfig

    with pytest.raises(ValueError, match="one product"):
        CellConfig(leg=LegConfig(), loin=LoinConfig())


def test_a_population_is_reproducible_from_its_seed() -> None:
    first = loin_population(20, seed=11)
    second = loin_population(20, seed=11)
    assert [loin.length_m for loin in first] == [loin.length_m for loin in second]
    assert [loin.bone_on_left for loin in first] == [loin.bone_on_left for loin in second]


def test_a_population_spans_the_assumed_range_and_both_sides() -> None:
    loins = loin_population(60, seed=3)
    lengths = np.array([loin.length_m for loin in loins])
    masses = np.array([loin.mass_kg for loin in loins])
    assert lengths.min() >= LENGTH_RANGE_M[0] - 1e-9
    assert lengths.max() <= LENGTH_RANGE_M[1] + 1e-9
    assert masses.min() >= MASS_RANGE_KG[0] - 1e-9
    assert masses.max() <= MASS_RANGE_KG[1] + 1e-9
    assert np.ptp(lengths) > 0.08, "the population is too uniform to test anything"
    assert 0.25 < np.mean([loin.bone_on_left for loin in loins]) < 0.75, "bone side should be roughly even"


def test_size_is_correlated_rather_than_drawn_independently() -> None:
    loins = loin_population(120, seed=5)
    lengths = np.array([loin.length_m for loin in loins])
    masses = np.array([loin.mass_kg for loin in loins])
    correlation = float(np.corrcoef(lengths, masses)[0, 1])
    assert correlation > 0.55, f"length and mass correlate at only {correlation:.2f}"


def test_a_rounded_underside_is_refused_as_a_configuration() -> None:
    with pytest.raises(ValueError, match="flatten fraction"):
        LoinConfig(flatten_fraction=1.0)
