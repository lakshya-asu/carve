import math

import pytest

from meatcell.contracts import Quaternion, SimTime, Transform, Vector3
from meatcell.frames import (
    CyclicFrameError,
    DisconnectedFrameError,
    FrameGraph,
    MissingFrameError,
    PlanarPose,
    StaleTransformError,
    compose,
    inverse,
)


def assert_transform_close(actual: Transform, expected: Transform) -> None:
    assert actual.translation.x_m == pytest.approx(expected.translation.x_m)
    assert actual.translation.y_m == pytest.approx(expected.translation.y_m)
    assert actual.translation.z_m == pytest.approx(expected.translation.z_m)
    dot = sum(
        a * b
        for a, b in zip(
            (actual.rotation.w, actual.rotation.x, actual.rotation.y, actual.rotation.z),
            (expected.rotation.w, expected.rotation.x, expected.rotation.y, expected.rotation.z),
            strict=True,
        )
    )
    assert abs(dot) == pytest.approx(1.0)


def test_compose_and_inverse_identities() -> None:
    transform = Transform(Vector3(0.4, -0.2, 1.1), Quaternion.from_yaw_rad(0.7))
    assert_transform_close(compose(transform, inverse(transform)), Transform.identity())
    assert_transform_close(compose(inverse(transform), transform), Transform.identity())


def test_camera_belt_world_and_product_grasp_chains() -> None:
    graph = FrameGraph(("world", "belt_surface", "camera", "meat_7", "grasp_7"))
    now = SimTime.from_seconds(1.0)
    graph.set_transform("world", "belt_surface", Transform.planar(0.5, 0.1, 0.8, 0.1), now)
    graph.set_transform("belt_surface", "camera", Transform.planar(-0.3, 0.0, 1.5, -0.1), now)
    graph.set_transform("belt_surface", "meat_7", Transform.planar(1.0, -0.2, 0.04, 0.4), now)
    graph.set_transform("meat_7", "grasp_7", Transform.planar(0.02, 0.0, 0.01, 0.0), now)
    expected = compose(graph.lookup("camera", "belt_surface", now), Transform.identity())
    assert_transform_close(graph.lookup("camera", "belt_surface", now), expected)
    world_from_grasp = graph.lookup("grasp_7", "world", now)
    expected_world_from_grasp = compose(
        Transform.planar(0.5, 0.1, 0.8, 0.1),
        compose(Transform.planar(1.0, -0.2, 0.04, 0.4), Transform.planar(0.02, 0.0, 0.01, 0.0)),
    )
    assert_transform_close(world_from_grasp, expected_world_from_grasp)


def test_missing_cyclic_stale_and_disconnected_fail_explicitly() -> None:
    graph = FrameGraph(("world",))
    graph.add_frame("orphan")
    graph.set_transform("world", "belt", Transform.identity(), SimTime(0))
    with pytest.raises(MissingFrameError, match="Unknown frame"):
        graph.lookup("missing", "world", SimTime(0))
    with pytest.raises(CyclicFrameError, match="cycle"):
        graph.set_transform("belt", "world", Transform.identity(), SimTime(0))
    with pytest.raises(StaleTransformError, match="older"):
        graph.lookup("belt", "world", SimTime.from_seconds(1.0), SimTime.from_seconds(0.1))
    with pytest.raises(DisconnectedFrameError, match="disconnected"):
        graph.lookup("orphan", "world", SimTime(0))


def test_planar_view_keeps_full_source_transform() -> None:
    half = math.sin(0.2)
    full = Transform(Vector3(1.0, 2.0, 3.0), Quaternion(math.cos(0.2), half, 0.0, 0.0))
    planar = PlanarPose(full)
    assert planar.source is full
    assert planar.z_m == 3.0
    assert planar.yaw_only_transform().translation == full.translation
