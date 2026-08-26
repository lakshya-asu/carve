from dataclasses import replace

import pytest

from meatcell.contracts import (
    GraspCandidate,
    ObjectTrack,
    SimTime,
    TrackLifecycle,
    Transform,
    Twist,
    Vector3,
)
from meatcell.interception import InterceptionConfig, InterceptionPlanner, PlanRejection, UnsafeZone


def track(**changes) -> ObjectTrack:
    value = ObjectTrack(
        track_id="track-1",
        lifecycle=TrackLifecycle.CONFIRMED,
        last_exposure_time=SimTime.from_seconds(0.09),
        state_time=SimTime.from_seconds(0.10),
        pose_belt=Transform.planar(0.224, 0.0, 0.05, 0.0),
        twist_belt=Twist(Vector3(2.24, 0.0, 0.0), Vector3(0.0, 0.0, 0.0)),
        position_variance_m2=Vector3(1e-5, 1e-5, 1e-5),
        yaw_variance_rad2=1e-4,
        hit_count=3,
        missed_count=0,
    )
    return replace(value, **changes)


def grasp(**changes) -> GraspCandidate:
    value = GraspCandidate("grasp-1", "track-1", Transform.identity(), 0.9, 0.03, 0.04)
    return replace(value, **changes)


def test_candidate_ranking_is_deterministic_and_plan_has_validity_contract() -> None:
    planner = InterceptionPlanner(InterceptionConfig())
    first = planner.plan(track=track(), grasp=grasp(), now=SimTime.from_seconds(0.10), world_from_belt=Transform.identity())
    second = planner.plan(track=track(), grasp=grasp(), now=SimTime.from_seconds(0.10), world_from_belt=Transform.identity())
    assert first == second
    assert first.accepted and first.plan is not None
    assert first.plan.source_exposure_time == SimTime.from_seconds(0.09)
    assert first.plan.valid_until == first.plan.abort_deadline == first.plan.commit_at
    assert planner.validate_live(first.plan, first.plan.valid_until)
    assert not planner.validate_live(first.plan, SimTime(first.plan.valid_until.nanoseconds + 1))
    assert first.plan.required_tcp_twist_world.linear_mps.x_m == pytest.approx(2.24)


@pytest.mark.parametrize(
    ("modified_track", "modified_grasp", "config", "zones", "reason"),
    [
        (dict(last_exposure_time=SimTime(0)), {}, InterceptionConfig(max_observation_age_s=0.05), (), PlanRejection.STALE),
        (dict(position_variance_m2=Vector3(0.01, 0.01, 0.01)), {}, InterceptionConfig(), (), PlanRejection.UNCERTAIN),
        ({}, dict(boundary_clearance_m=0.001), InterceptionConfig(), (), PlanRejection.INVALID_GRASP),
        ({}, {}, InterceptionConfig(max_tcp_speed_mps=2.3), (), PlanRejection.VELOCITY_MISMATCH),
        (dict(pose_belt=Transform.planar(0.224, 0.2, 0.05, 0.0)), {}, InterceptionConfig(workspace_y_abs_m=0.1), (), PlanRejection.UNREACHABLE),
        ({}, {}, InterceptionConfig(), (UnsafeZone(0.0, 5.0, -1.0, 1.0),), PlanRejection.UNSAFE),
        (dict(pose_belt=Transform.planar(1.6, 0.0, 0.05, 0.0)), {}, InterceptionConfig(), (), PlanRejection.TOO_LATE),
    ],
)
def test_distinct_rejection_reasons(modified_track, modified_grasp, config, zones, reason) -> None:
    decision = InterceptionPlanner(config, zones).plan(
        track=track(**modified_track),
        grasp=grasp(**modified_grasp),
        now=SimTime.from_seconds(0.10),
        world_from_belt=Transform.identity(),
    )
    assert decision.reason is reason
    assert decision.plan is None


def test_pick_window_edges_are_included() -> None:
    config = InterceptionConfig(pick_x_min_m=0.8, pick_x_max_m=0.8 + 0.025, candidate_step_m=0.025)
    decision = InterceptionPlanner(config).plan(
        track=track(), grasp=grasp(), now=SimTime.from_seconds(0.10), world_from_belt=Transform.identity()
    )
    assert decision.evaluated_candidates == 2
