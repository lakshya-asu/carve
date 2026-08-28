from dataclasses import replace
import math
from pathlib import Path

from meatcell.contracts import (
    GraspCandidate,
    InterceptionPlan,
    ObjectTrack,
    SimTime,
    TrackLifecycle,
    Transform,
    Twist,
    Vector3,
)
from meatcell.reactive_interception import ReactiveInterceptionConfig, ReactiveUpdateReason, propose_reactive_update


def test_integrated_perturbation_records_do_not_reuse_trace_kind_keyword() -> None:
    source = (Path(__file__).parents[1] / "isaac_sim" / "run_scene2_integrated.py").read_text(encoding="utf-8")
    assert '"kind": "pose_disturbance"' not in source
    assert '"kind": "belt_ramp"' not in source
    assert "<= calibration.belt_surface_z_world_m + 0.16" in source
    assert "min(0.00025, pose_disturbance_remaining_m)" in source
    assert 'args.interception_perturbation == "belt_ramp"' in source
    assert "x_m=active_belt_speed_mps" in source
    assert 'and "lost" in str(exc).lower()' in source


def _plan() -> InterceptionPlan:
    grasp = GraspCandidate("grasp-1", "track-1", Transform.identity(), 0.8, 0.03, 0.04)
    return InterceptionPlan(
        "plan-1",
        "track-1",
        SimTime.from_seconds(0.0),
        SimTime.from_seconds(0.1),
        SimTime.from_seconds(2.0),
        SimTime.from_seconds(1.5),
        SimTime.from_seconds(1.5),
        SimTime.from_seconds(1.5),
        grasp,
        Transform.planar(0.30, 0.0, 0.88, 0.0),
        Twist(Vector3(0.1, 0.0, 0.0), Vector3(0.0, 0.0, 0.0)),
        0.02,
        0.5,
    )


def _track(**overrides) -> ObjectTrack:
    payload = dict(
        track_id="track-1",
        lifecycle=TrackLifecycle.CONFIRMED,
        last_exposure_time=SimTime.from_seconds(0.9),
        state_time=SimTime.from_seconds(1.0),
        pose_belt=Transform.planar(0.19, 0.015, 0.88, math.radians(2.0)),
        twist_belt=Twist(Vector3(0.12, 0.0, 0.0), Vector3(0.0, 0.0, 0.0)),
        position_variance_m2=Vector3(0.0001, 0.0001, 0.0001),
        yaw_variance_rad2=0.001,
        hit_count=3,
        missed_count=0,
    )
    payload.update(overrides)
    return ObjectTrack(**payload)


def _update(track=None, now_s=1.0, **kwargs):
    return propose_reactive_update(
        plan=_plan(),
        track=track or _track(),
        now=SimTime.from_seconds(now_s),
        current_target_world=Transform.planar(0.30, 0.0, 0.88, 0.0),
        sequence=kwargs.pop("sequence", 1),
        last_sequence=kwargs.pop("last_sequence", 0),
        applied_count=kwargs.pop("applied_count", 0),
        previous_applied_correction_m=kwargs.pop("previous", None),
        plc_ready=kwargs.pop("plc_ready", True),
        emergency_stop=kwargs.pop("emergency_stop", False),
        **kwargs,
    )


def test_applies_only_bounded_same_identity_correction() -> None:
    decision = _update()
    assert decision.accepted is True
    assert decision.reason is ReactiveUpdateReason.APPLIED
    correction = decision.applied_correction_m
    norm = math.sqrt(correction.x_m**2 + correction.y_m**2 + correction.z_m**2)
    assert norm <= 0.025 + 1e-12
    config = ReactiveInterceptionConfig()
    for component in (correction.x_m, correction.y_m, correction.z_m):
        assert math.isclose(component / config.correction_quantum_m, round(component / config.correction_quantum_m))
    assert math.isclose(
        decision.applied_yaw_correction_rad / config.yaw_correction_quantum_rad,
        round(decision.applied_yaw_correction_rad / config.yaw_correction_quantum_rad),
    )


def test_sub_quantum_update_is_ignored_as_measurement_noise() -> None:
    track = replace(
        _track(),
        pose_belt=Transform.planar(0.199, 0.0008, 0.88, math.radians(0.1)),
        twist_belt=Twist(Vector3(0.1, 0.0, 0.0), Vector3(0.0, 0.0, 0.0)),
    )
    decision = _update(track)
    assert decision.accepted is False
    assert decision.reason is ReactiveUpdateReason.BELOW_DEADBAND


def test_rejects_identity_switch_stale_sequence_and_no_return() -> None:
    assert _update(replace(_track(), track_id="track-other")).reason is ReactiveUpdateReason.IDENTITY_MISMATCH
    assert _update(replace(_track(), last_exposure_time=SimTime.from_seconds(0.5))).reason is ReactiveUpdateReason.STALE
    assert _update(sequence=2, last_sequence=2).reason is ReactiveUpdateReason.SEQUENCE_REJECTED
    assert _update(now_s=1.75).reason is ReactiveUpdateReason.NO_RETURN


def test_rejects_oscillation_update_cap_and_total_limit() -> None:
    assert _update(previous=Vector3(0.0, -0.010, 0.0)).reason is ReactiveUpdateReason.OSCILLATION
    assert _update(applied_count=3).reason is ReactiveUpdateReason.UPDATE_LIMIT
    far = replace(_track(), pose_belt=Transform.planar(0.19, 0.09, 0.88, 0.0))
    assert _update(far).reason is ReactiveUpdateReason.TOTAL_CORRECTION_LIMIT


def test_plc_and_emergency_stop_fail_closed() -> None:
    assert _update(plc_ready=False).reason is ReactiveUpdateReason.PLC_BLOCKED
    assert _update(emergency_stop=True).reason is ReactiveUpdateReason.EMERGENCY_STOP
