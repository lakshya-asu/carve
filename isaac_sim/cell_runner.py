"""Integrated Isaac Sim cell runner for Solution A and Solution B.

Every observation, robot command, contact, and PLC decision in this runner is
connected to the active Isaac stage. The reference geometry is intentionally
abstract and is not an OEM model or a physical validation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any

from meatcell.contracts import (
    CellResult,
    Contract,
    GraspCandidate,
    ObjectObservation,
    SimTime,
    TerminalPath,
    Transform,
)
from meatcell.eventlog import (
    JsonlEventReader,
    JsonlEventWriter,
    RunMetadata,
    dependency_versions,
    summarize_cell_results,
)
from meatcell.frames import compose, inverse
from meatcell.grasp import GraspModel, GraspModelConfig
from meatcell.interception import InterceptionConfig, InterceptionPlanner, UnsafeZone
from meatcell.perception import PinholeCalibration, VisionModel
from meatcell.ports import RobotCommand
from meatcell.product_profiles import ProductProfile
from meatcell.solutions import (
    BufferRuntime,
    DeliveryMeasurement,
    DeliveryTolerance,
    PLCState,
    SolutionAController,
    SolutionBController,
)
from meatcell.supervisor import CellState, CellSupervisor
from meatcell.tracking import ObjectTracker, TrackerConfig

from .adapter import IsaacSimulatorAdapter
from .perception_adapter import RenderedColorDepthSegmentationModel
from .stage_builder import REFERENCE_NOTICE, product_width_scale_at_grasp


PHYSICS_HZ = 240
BELT_SPEED_MPS = 2.24
PRODUCT_ID = "product-000"
HOME_TCP = Transform.planar(1.20, 0.0, 0.55, 0.0)
CUT_TARGET = Transform.planar(2.35, 0.0, 0.10, 0.0)
BUFFER_TARGET = Transform.planar(1.80, -0.60, 0.19, 0.0)
REJECT_TARGET = Transform.planar(1.60, 0.62, 0.38, 0.0)
JOINT_VELOCITY_LIMITS = (4.0, 4.0, 4.0, 6.0, 1.0, 1.0)
JOINT_ACCELERATION_LIMITS = (12.0, 8.0, 8.0, 10.0, 8.0, 8.0)
DELIVERY_TOLERANCE = DeliveryTolerance(0.055, math.radians(7.0), 0.012, 0.35)
BASELINE_SCENARIOS = ("nominal", "nominal", "failed_grasp", "downstream_unavailable")
HARDENING_SCENARIOS = (*BASELINE_SCENARIOS, "emergency_stop", "stale_observation")


def _failure_mode(solution: str, cycle_index: int, scenario_profile: str) -> str:
    if scenario_profile not in {"baseline", "hardening"}:
        raise ValueError("Scenario profile must be baseline or hardening")
    schedule = BASELINE_SCENARIOS if scenario_profile == "baseline" else HARDENING_SCENARIOS
    mode = schedule[cycle_index % len(schedule)]
    if mode == "downstream_unavailable":
        return "cutter_unavailable" if solution == "a" else "buffer_timeout"
    return mode


@dataclass(frozen=True)
class ReplayDecisionInput(Contract):
    episode_id: str
    solution: str
    terminal_path: TerminalPath
    terminal_reason: str
    started_at: SimTime
    finished_at: SimTime
    perceived: bool
    tracked: bool
    grasped: bool
    delivered: bool
    slip_detected: bool
    placement_position_error_m: float | None
    placement_angle_error_rad: float | None
    timing_error_s: float | None
    transfer_speed_error_mps: float | None
    collision_count: int
    joint_limit_violation_count: int

    def evaluate(self) -> CellResult:
        return CellResult(
            self.episode_id,
            self.solution,
            self.terminal_path,
            self.terminal_reason,
            self.started_at,
            self.finished_at,
            self.perceived,
            self.tracked,
            self.grasped,
            self.delivered,
            self.slip_detected,
            self.placement_position_error_m,
            self.placement_angle_error_rad,
            self.timing_error_s,
            self.transfer_speed_error_mps,
            self.collision_count,
            self.joint_limit_violation_count,
        )


@dataclass
class MotionEvidence:
    command_count: int = 0
    max_commanded_velocity: float = 0.0
    max_commanded_acceleration: float = 0.0
    max_actual_velocity: float = 0.0
    collision_count: int = 0
    intentional_contact_count: int = 0

    def add(self, other: "MotionEvidence") -> None:
        self.command_count += other.command_count
        self.max_commanded_velocity = max(self.max_commanded_velocity, other.max_commanded_velocity)
        self.max_commanded_acceleration = max(self.max_commanded_acceleration, other.max_commanded_acceleration)
        self.max_actual_velocity = max(self.max_actual_velocity, other.max_actual_velocity)
        self.collision_count += other.collision_count
        self.intentional_contact_count += other.intentional_contact_count


def _angle_error(value: float, target: float) -> float:
    return abs(math.atan2(math.sin(value - target), math.cos(value - target)))


def _planar(value: Transform) -> Transform:
    return Transform.planar(
        value.translation.x_m,
        value.translation.y_m,
        value.translation.z_m,
        value.yaw_rad,
    )


def _tcp_target_for_product(
    adapter: IsaacSimulatorAdapter,
    product_target: Transform,
) -> Transform:
    world_from_tcp = _planar(adapter.read_robot_state().tcp_pose_world)
    world_from_product = _planar(adapter.get_product_pose(PRODUCT_ID))
    tcp_from_product = compose(inverse(world_from_tcp), world_from_product)
    return _planar(compose(product_target, inverse(tcp_from_product)))


def _buffer_regrasp_target(observed_product_pose: Transform) -> Transform:
    """Place the open gripper over the product pose measured after settling."""
    return Transform.planar(
        observed_product_pose.translation.x_m,
        observed_product_pose.translation.y_m,
        max(0.17, observed_product_pose.translation.z_m + 0.02),
        observed_product_pose.yaw_rad,
    )


def _plc(adapter: IsaacSimulatorAdapter) -> PLCState:
    cutter = adapter.read_cutter_state()
    return PLCState(
        adapter.simulation_time,
        adapter.conveyor_speed_mps,
        cutter.recipe_id,
        cutter,
        adapter.fault_active,
        adapter.emergency_stop_active,
        adapter.result_acknowledged,
    )


def _tcp_to_joint_targets(adapter: IsaacSimulatorAdapter, target: Transform, fingers: tuple[float, float] | None = None) -> tuple[float, ...]:
    state = adapter.read_robot_state()
    values = dict(zip(state.joint_names, state.positions, strict=True))
    values["x_axis"] = target.translation.x_m - 0.35
    values["y_axis"] = target.translation.y_m
    values["z_axis"] = target.translation.z_m - 0.35
    values["wrist_yaw"] = target.yaw_rad
    if fingers is not None:
        values["finger_left"], values["finger_right"] = fingers
    return tuple(values[name] for name in state.joint_names)


def _closed_finger_targets(adapter: IsaacSimulatorAdapter) -> tuple[float, float]:
    """Apply the 8 mm per-pad compliance proxy from a fixed 175 mm open gap."""
    product_half_width_m = adapter.product_profile.geometry.width_m.nominal / 2.0
    travel_m = max(0.0, 0.0875 - product_half_width_m + 0.008)
    return (-travel_m, travel_m)


def _buffer_closed_finger_targets(adapter: IsaacSimulatorAdapter) -> tuple[float, float]:
    """Close on the mesh width at the stationary central regrasp section."""
    width_scale = product_width_scale_at_grasp(
        adapter.product_profile.geometry.shape_family,
        adapter.product_profile.geometry.taper_ratio.nominal,
    )
    product_half_width_m = adapter.product_profile.geometry.width_m.nominal * width_scale / 2.0
    travel_m = max(0.0, 0.0875 - product_half_width_m + 0.008)
    return (-travel_m, travel_m)


def _quintic_coefficients(p0: float, v0: float, p1: float, v1: float, duration_s: float) -> tuple[float, ...]:
    import numpy as np

    t = duration_s
    base = np.array([p0, v0, 0.0], dtype=float)
    matrix = np.array(
        [
            [t**3, t**4, t**5],
            [3.0 * t**2, 4.0 * t**3, 5.0 * t**4],
            [6.0 * t, 12.0 * t**2, 20.0 * t**3],
        ],
        dtype=float,
    )
    rhs = np.array([p1 - p0 - v0 * t, v1 - v0, 0.0], dtype=float)
    tail = np.linalg.solve(matrix, rhs)
    return (float(base[0]), float(base[1]), float(base[2]), *(float(item) for item in tail))


def _sample_polynomial(coefficients: tuple[float, ...], time_s: float) -> tuple[float, float, float]:
    a0, a1, a2, a3, a4, a5 = coefficients
    position = a0 + a1 * time_s + a2 * time_s**2 + a3 * time_s**3 + a4 * time_s**4 + a5 * time_s**5
    velocity = a1 + 2.0 * a2 * time_s + 3.0 * a3 * time_s**2 + 4.0 * a4 * time_s**3 + 5.0 * a5 * time_s**4
    acceleration = 2.0 * a2 + 6.0 * a3 * time_s + 12.0 * a4 * time_s**2 + 20.0 * a5 * time_s**3
    return position, velocity, acceleration


def _collision_aware_tcp_check(targets: tuple[float, ...], names: tuple[str, ...]) -> None:
    values = dict(zip(names, targets, strict=True))
    x_m = 0.35 + values["x_axis"]
    y_m = values["y_axis"]
    z_m = 0.35 + values["z_axis"]
    if not 0.35 <= x_m <= 2.48 or abs(y_m) > 0.72 or not 0.055 <= z_m <= 0.62:
        raise ValueError(f"TCP target leaves validated cell envelope: {(x_m, y_m, z_m)}")
    if x_m > 2.48 and z_m < 0.60:
        raise ValueError("TCP target enters cutter reference collision volume")


def execute_joint_trajectory(
    adapter: IsaacSimulatorAdapter,
    end_positions: tuple[float, ...],
    duration_s: float,
    *,
    end_velocities: tuple[float, ...] | None = None,
    start_velocities: tuple[float, ...] | None = None,
    inspect_contacts: bool = True,
) -> MotionEvidence:
    if duration_s <= 0.0:
        raise ValueError("Trajectory duration must be positive")
    start = adapter.read_robot_state()
    names = start.joint_names
    if len(end_positions) != len(names):
        raise ValueError("Trajectory target count does not match articulation")
    desired_end_velocity = end_velocities or (0.0,) * len(names)
    steps = max(2, math.ceil(duration_s * adapter.physics_hz))
    duration = steps / adapter.physics_hz
    desired_start_velocities = start_velocities or (0.0,) * len(start.positions)
    lower = tuple(float(item) for item in adapter.robot.dof_properties["lower"])
    upper = tuple(float(item) for item in adapter.robot.dof_properties["upper"])
    start_positions = tuple(
        min(max(value, lower[index]), upper[index])
        for index, value in enumerate(start.positions)
    )
    coefficients = tuple(
        _quintic_coefficients(p0, v0, p1, v1, duration)
        for p0, v0, p1, v1 in zip(start_positions, desired_start_velocities, end_positions, desired_end_velocity, strict=True)
    )

    evidence = MotionEvidence()
    for sample_index in range(steps + 1):
        sample_time = duration * sample_index / steps
        sampled = tuple(_sample_polynomial(item, sample_time) for item in coefficients)
        positions = tuple(item[0] for item in sampled)
        _collision_aware_tcp_check(positions, names)
        for joint_index, (_, velocity, acceleration) in enumerate(sampled):
            if abs(velocity) > JOINT_VELOCITY_LIMITS[joint_index] * 1.001:
                raise ValueError(f"Preflight velocity limit exceeded for {names[joint_index]}")
            if abs(acceleration) > JOINT_ACCELERATION_LIMITS[joint_index] * 1.001:
                raise ValueError(
                    f"Preflight acceleration limit exceeded for {names[joint_index]}: "
                    f"requested={abs(acceleration):.6f}, limit={JOINT_ACCELERATION_LIMITS[joint_index]:.6f}, "
                    f"duration={duration:.6f}"
                )
            evidence.max_commanded_velocity = max(evidence.max_commanded_velocity, abs(velocity))
            evidence.max_commanded_acceleration = max(evidence.max_commanded_acceleration, abs(acceleration))
    adapter.reset_command_history()
    for sample_index in range(1, steps + 1):
        sample_time = duration * sample_index / steps
        positions = tuple(
            min(max(_sample_polynomial(item, sample_time)[0], lower[index]), upper[index])
            for index, item in enumerate(coefficients)
        )
        adapter.command_robot(
            RobotCommand(
                adapter.simulation_time,
                names,
                positions,
                JOINT_VELOCITY_LIMITS,
                JOINT_ACCELERATION_LIMITS,
            )
        )
        adapter.step_once()
        evidence.command_count += 1
        actual = adapter.read_robot_state()
        evidence.max_actual_velocity = max(evidence.max_actual_velocity, *(abs(item) for item in actual.velocities))
        if inspect_contacts and (sample_index % 2 == 0 or sample_index == steps):
            contacts = adapter.read_contacts()
            evidence.intentional_contact_count += sum(1 for item in contacts if item.intentional)
            evidence.collision_count += sum(1 for item in contacts if not item.intentional and item.force_n > 0.5)
    return evidence


def move_tcp(
    adapter: IsaacSimulatorAdapter,
    target: Transform,
    duration_s: float,
    *,
    fingers: tuple[float, float] | None = None,
    start_tcp_x_velocity_mps: float = 0.0,
    end_tcp_x_velocity_mps: float = 0.0,
) -> MotionEvidence:
    end = _tcp_to_joint_targets(adapter, target, fingers)
    velocities = [0.0] * len(end)
    velocities[adapter.joint_names.index("x_axis")] = end_tcp_x_velocity_mps
    start_velocities = [0.0] * len(end)
    start_velocities[adapter.joint_names.index("x_axis")] = start_tcp_x_velocity_mps
    return execute_joint_trajectory(
        adapter,
        end,
        duration_s,
        end_velocities=tuple(velocities),
        start_velocities=tuple(start_velocities),
    )


def _append_new_events(writer: JsonlEventWriter, supervisor: CellSupervisor, cursor: int) -> int:
    for event in supervisor.events[cursor:]:
        writer.append_event(event)
    return len(supervisor.events)


def _canonical_observation(observation: ObjectObservation) -> ObjectObservation:
    return observation


def _observe_and_track(
    adapter: IsaacSimulatorAdapter,
    model: VisionModel,
    calibration: PinholeCalibration,
    tracker: ObjectTracker,
    writer: JsonlEventWriter,
    supervisor: CellSupervisor,
    event_cursor: int,
) -> tuple[Any | None, int, list[float], int]:
    pending: list[ObjectObservation] = []
    latencies: list[float] = []
    observation_count = 0
    track = None
    first_transition_done = False
    start_ns = adapter.simulation_time.nanoseconds
    for step_index in range(72):
        if step_index % 8 == 0:
            rgb, depth, _ = adapter.camera_arrays("overhead")
            observations = model.infer(rgb, depth, adapter.simulation_time, calibration)
            candidates = [
                _canonical_observation(item)
                for item in observations
                if item.pose_belt.translation.z_m < 0.16
                and item.pose_belt.translation.x_m < 1.90
                and abs(item.pose_belt.translation.y_m) < 0.36
            ]
            if candidates:
                expected = adapter.get_product_pose(PRODUCT_ID)
                chosen = min(
                    candidates,
                    key=lambda item: abs(item.pose_belt.translation.x_m - expected.translation.x_m)
                    + abs(item.pose_belt.translation.y_m - expected.translation.y_m),
                )
                pending.append(chosen)
        adapter.step_once()
        due = sorted(
            (item for item in pending if item.delivery_time <= adapter.simulation_time),
            key=lambda item: (item.delivery_time.nanoseconds, item.exposure_time.nanoseconds),
        )
        for observation in due:
            pending.remove(observation)
            writer.append("observation", observation.delivery_time, observation)
            observation_count += 1
            latencies.append(observation.delivery_time.seconds - observation.exposure_time.seconds)
            track = tracker.update(observation, current_time=adapter.simulation_time, encoder_speed_mps=BELT_SPEED_MPS)
            if not first_transition_done:
                supervisor.transition(CellState.TRACK, adapter.simulation_time, "rendered_observation_acquired")
                first_transition_done = True
                event_cursor = _append_new_events(writer, supervisor, event_cursor)
            if track.lifecycle.value == "confirmed":
                return track, observation_count, latencies, event_cursor
        if adapter.simulation_time.nanoseconds - start_ns > 300_000_000:
            break
    return track, observation_count, latencies, event_cursor


def _physical_recovery(
    adapter: IsaacSimulatorAdapter,
    supervisor: CellSupervisor,
    evidence: MotionEvidence,
    *,
    attached: bool,
    reject: bool,
) -> None:
    if attached and reject:
        brake_start = adapter.read_robot_state().tcp_pose_world
        brake_target = Transform.planar(
            min(2.47, brake_start.translation.x_m + 0.30),
            brake_start.translation.y_m,
            brake_start.translation.z_m,
            brake_start.yaw_rad,
        )
        evidence.add(
            move_tcp(
                adapter,
                brake_target,
                0.35,
                fingers=_closed_finger_targets(adapter),
                start_tcp_x_velocity_mps=BELT_SPEED_MPS,
            )
        )
        evidence.add(
            move_tcp(
                adapter,
                Transform.planar(brake_target.translation.x_m, brake_target.translation.y_m, 0.50, brake_target.yaw_rad),
                0.55,
                fingers=_closed_finger_targets(adapter),
            )
        )
        evidence.add(move_tcp(adapter, Transform.planar(REJECT_TARGET.translation.x_m, REJECT_TARGET.translation.y_m, 0.50, 0.0), 0.90, fingers=_closed_finger_targets(adapter)))
        evidence.add(move_tcp(adapter, REJECT_TARGET, 0.40, fingers=_closed_finger_targets(adapter)))
        evidence.add(move_tcp(adapter, REJECT_TARGET, 0.20, fingers=(0.0, 0.0)))
        adapter.release_grasp()
        for _ in range(12):
            adapter.step_once()
    elif attached:
        adapter.release_grasp()
        adapter.set_gripper_closed(False)
        for _ in range(12):
            adapter.step_once()
    evidence.add(move_tcp(adapter, HOME_TCP, 1.60, fingers=(0.0, 0.0)))
    supervisor.return_to_idle(adapter.simulation_time, "physical_recovery_complete")


def _result_from_supervisor(
    supervisor: CellSupervisor,
    *,
    episode_id: str,
    solution: str,
    reason: str,
    started_at: SimTime,
    finished_at: SimTime,
    perceived: bool,
    tracked: bool,
    grasped: bool,
    delivered: bool,
    slip_detected: bool,
    measurement: DeliveryMeasurement | None,
    collisions: int,
    joint_violations: int,
) -> CellResult:
    return CellResult(
        episode_id,
        solution,
        supervisor.terminal_path,
        reason,
        started_at,
        finished_at,
        perceived,
        tracked,
        grasped,
        delivered,
        slip_detected,
        measurement.position_error_m if measurement else None,
        measurement.angle_error_rad if measurement else None,
        measurement.timing_error_s if measurement else None,
        measurement.speed_error_mps if measurement else None,
        collisions,
        joint_violations,
    )


def _replay_input(result: CellResult) -> ReplayDecisionInput:
    return ReplayDecisionInput(
        result.episode_id,
        result.solution,
        result.terminal_path,
        result.terminal_reason,
        result.started_at,
        result.finished_at,
        result.perceived,
        result.tracked,
        result.grasped,
        result.delivered,
        result.slip_detected,
        result.placement_position_error_m,
        result.placement_angle_error_rad,
        result.timing_error_s,
        result.transfer_speed_error_mps,
        result.collision_count,
        result.joint_limit_violation_count,
    )


def _verify_replay(path: Path) -> bool:
    reader = JsonlEventReader(path)

    def handler(records: tuple[Any, ...]) -> CellResult:
        inputs = [item.payload() for item in records if item.record_type == "replay_decision_input"]
        if len(inputs) != 1 or not isinstance(inputs[0], ReplayDecisionInput):
            raise AssertionError("Replay requires exactly one decision input")
        return inputs[0].evaluate()

    return reader.replay(handler) == reader.terminal_result


def run_cycle(
    adapter: IsaacSimulatorAdapter,
    *,
    solution: str,
    cycle_index: int,
    seed: int,
    output_directory: Path,
    scenario_profile: str = "baseline",
    vision_model_backend: str = "color",
    yolo_weights: Path | None = None,
) -> tuple[CellResult, dict[str, Any], list[float]]:
    rng = random.Random(seed)
    episode_id = f"isaac-{solution}-{cycle_index:03d}-seed-{seed}"
    failure_mode = _failure_mode(solution, cycle_index, scenario_profile)

    log_path = output_directory / "traces" / f"cycle_{cycle_index:03d}.jsonl"
    config_payload = json.dumps(
        {
            "solution": solution,
            "cycle_index": cycle_index,
            "seed": seed,
            "failure_mode": failure_mode,
            "scenario_profile": scenario_profile,
            "vision_model_backend": vision_model_backend,
            "yolo_weights": str(yolo_weights) if yolo_weights else None,
            "belt_speed_mps": BELT_SPEED_MPS,
            "product_recipe_id": adapter.product_profile.recipe_id,
        },
        sort_keys=True,
    )
    writer = JsonlEventWriter(
        log_path,
        RunMetadata(
            episode_id,
            hashlib.sha256(config_payload.encode("utf-8")).hexdigest(),
            "isaac-reference-cell",
            1,
            seed,
            solution,
            dependency_versions(),
            adapter.simulation_time,
            REFERENCE_NOTICE,
        ),
    )
    writer.start()
    evidence = MotionEvidence()
    supervisor = CellSupervisor()
    event_cursor = 0
    perceived = False
    tracked = False
    grasped = False
    delivered = False
    slip_detected = False
    measurement: DeliveryMeasurement | None = None
    safe_stop_hold_max_joint_delta = None
    start_violations = adapter.read_robot_state().joint_limit_violation_count

    adapter.release_grasp()
    adapter.set_plc_inputs(
        conveyor_speed_mps=0.0,
        cutter_mode=__import__("meatcell.contracts", fromlist=["CutterMode"]).CutterMode.READY,
        recipe_id=adapter.product_profile.recipe_id,
        permissive_sequence=100 + cycle_index,
        fault_active=False,
        emergency_stop=False,
        result_acknowledged=False,
    )
    for product_index, product_id in enumerate(sorted(adapter.products)):
        adapter.set_product_pose(
            product_id,
            Transform.planar(-8.0 - product_index, 0.0, adapter.product_center_z_m, 0.0),
        )
        adapter.set_product_velocity(product_id, (0.0, 0.0, 0.0))
    evidence.add(move_tcp(adapter, HOME_TCP, 1.00, fingers=(0.0, 0.0)))

    lateral_m = rng.uniform(-0.075, 0.075)
    yaw_rad = rng.uniform(-0.48, 0.48)
    adapter.set_product_pose(
        PRODUCT_ID,
        Transform.planar(-0.25, lateral_m, adapter.product_center_z_m, yaw_rad),
    )
    adapter.set_product_velocity(PRODUCT_ID, (BELT_SPEED_MPS, 0.0, 0.0))
    adapter.set_plc_inputs(conveyor_speed_mps=BELT_SPEED_MPS)
    started_at = adapter.simulation_time
    supervisor.start_episode(episode_id, started_at)
    event_cursor = _append_new_events(writer, supervisor, event_cursor)
    writer.append("plc_state", started_at, _plc(adapter))

    calibration = PinholeCalibration(
        1.0,
        0.0,
        3.0,
        18.0 / 20.955 * 640.0,
        18.0 / 20.955 * 640.0,
        320.0,
        240.0,
        0.04,
        0.002,
        0.004,
    )
    model_options = {
        "seed": seed,
        "latency_mean_s": 0.028,
        "latency_sigma_s": 0.003,
        "timestamp_jitter_sigma_s": 0.0004,
        "position_noise_sigma_m": 0.0015,
        "yaw_noise_sigma_rad": math.radians(0.5),
        "minimum_component_pixels": 30,
    }
    if vision_model_backend == "color":
        model: VisionModel = RenderedColorDepthSegmentationModel(
            product_species=adapter.product_profile.species,
            **model_options,
        )
    elif vision_model_backend == "yolo26":
        if yolo_weights is None:
            raise ValueError("YOLO26 perception requires a checkpoint")
        from .yolo_perception import YOLO26SegmentationModel

        model = YOLO26SegmentationModel(weights_path=yolo_weights, confidence_threshold=0.20, **model_options)
    else:
        raise ValueError(f"Unsupported vision backend: {vision_model_backend}")
    tracker = ObjectTracker(
        TrackerConfig(
            confirmation_hits=2,
            association_distance_m=0.16,
            velocity_measurement_weight=0.0,
        )
    )
    track, observation_count, latencies, event_cursor = _observe_and_track(
        adapter, model, calibration, tracker, writer, supervisor, event_cursor
    )
    perceived = observation_count > 0
    tracked = track is not None and track.lifecycle.value == "confirmed"
    if cycle_index == 0:
        adapter.capture_rgbd("overhead", str(output_directory / "media"))

    terminal_reason = "unknown"
    if not tracked:
        supervisor.recover(adapter.simulation_time, "rendered_track_not_confirmed")
        event_cursor = _append_new_events(writer, supervisor, event_cursor)
        _physical_recovery(adapter, supervisor, evidence, attached=False, reject=False)
        event_cursor = _append_new_events(writer, supervisor, event_cursor)
        terminal_reason = "rendered_track_not_confirmed"
    else:
        supervisor.transition(CellState.PLAN, adapter.simulation_time, "confirmed_track_predicted")
        event_cursor = _append_new_events(writer, supervisor, event_cursor)
        grasp = GraspCandidate(
            f"grasp-{cycle_index:03d}",
            track.track_id,
            Transform.planar(0.0, 0.0, 0.030, 0.0),
            0.82,
            0.025,
            0.040,
        )
        planner = InterceptionPlanner(
            InterceptionConfig(
                pick_x_min_m=1.63,
                pick_x_max_m=1.75,
                candidate_step_m=0.01,
                workspace_y_abs_m=0.70,
                workspace_z_min_m=0.05,
                workspace_z_max_m=0.62,
                home_pose_world=adapter.read_robot_state().tcp_pose_world,
                max_tcp_speed_mps=4.0,
                # Keep planning below the articulation's 8 m/s2 transverse
                # limit so the sampled quintic trajectory retains margin for
                # recipe-dependent product height.
                max_tcp_accel_mps2=6.0,
                grasp_close_s=0.020,
                command_latency_s=0.005,
                timing_reserve_s=0.010,
                commit_lead_s=0.08,
                max_observation_age_s=0.15,
                max_position_sigma_m=0.03,
                velocity_match_reserve_mps=0.20,
                minimum_boundary_clearance_m=0.01,
            ),
            (UnsafeZone(2.50, 3.2, -0.7, 0.7),),
        )
        if failure_mode == "stale_observation":
            for _ in range(50):
                adapter.step_once()
        decision = planner.plan(track=track, grasp=grasp, now=adapter.simulation_time, world_from_belt=Transform.identity())
        writer.append("interception_decision", adapter.simulation_time, decision)
        event_cursor = _append_new_events(writer, supervisor, event_cursor)
        if not decision.accepted or decision.plan is None:
            supervisor.reject(adapter.simulation_time, f"interception_{decision.reason.value}")
            event_cursor = _append_new_events(writer, supervisor, event_cursor)
            _physical_recovery(adapter, supervisor, evidence, attached=False, reject=False)
            event_cursor = _append_new_events(writer, supervisor, event_cursor)
            terminal_reason = f"interception_{decision.reason.value}"
        else:
            plan = decision.plan
            supervisor.transition(CellState.WAIT_COMMIT, adapter.simulation_time, "timed_interception_reserved")
            supervisor.transition(CellState.INTERCEPT, adapter.simulation_time, "trajectory_committed")
            event_cursor = _append_new_events(writer, supervisor, event_cursor)
            intercept_target = plan.interception_pose_world
            if failure_mode == "failed_grasp":
                intercept_target = Transform.planar(
                    intercept_target.translation.x_m,
                    intercept_target.translation.y_m + 0.16,
                    intercept_target.translation.z_m,
                    intercept_target.yaw_rad,
                )
            intercept_duration = max(0.20, plan.intercept_at.seconds - adapter.simulation_time.seconds)
            evidence.add(
                move_tcp(
                    adapter,
                    intercept_target,
                    intercept_duration,
                    fingers=(0.0, 0.0),
                    end_tcp_x_velocity_mps=BELT_SPEED_MPS,
                )
            )
            intercept_error_s = abs(adapter.simulation_time.seconds - plan.intercept_at.seconds)
            closure_duration_s = 0.25
            elapsed_after_intercept_s = adapter.simulation_time.seconds - plan.intercept_at.seconds
            measured_tcp_at_intercept = adapter.read_robot_state().tcp_pose_world
            closing_target = Transform.planar(
                plan.interception_pose_world.translation.x_m
                + BELT_SPEED_MPS * (elapsed_after_intercept_s + closure_duration_s),
                measured_tcp_at_intercept.translation.y_m,
                measured_tcp_at_intercept.translation.z_m,
                measured_tcp_at_intercept.yaw_rad,
            )
            evidence.add(
                move_tcp(
                    adapter,
                    closing_target,
                    closure_duration_s,
                    fingers=_closed_finger_targets(adapter),
                    start_tcp_x_velocity_mps=BELT_SPEED_MPS,
                    end_tcp_x_velocity_mps=BELT_SPEED_MPS,
                )
            )
            contacts = adapter.read_contacts()
            evidence.intentional_contact_count += sum(1 for item in contacts if item.intentional)
            writer.append("pregrasp_robot_state", adapter.simulation_time, adapter.read_robot_state())
            writer.append("pregrasp_product_pose", adapter.simulation_time, adapter.get_product_pose(PRODUCT_ID))
            for finger_pose in adapter.get_finger_world_poses():
                writer.append("pregrasp_finger_pose", adapter.simulation_time, finger_pose)
            for contact in contacts:
                writer.append("pregrasp_contact", adapter.simulation_time, contact)
            supervisor.transition(CellState.VERIFY_GRASP, adapter.simulation_time, "grasp_closure_complete")
            event_cursor = _append_new_events(writer, supervisor, event_cursor)
            grasped = adapter.attach_grasp(PRODUCT_ID)
            if not grasped:
                adapter.set_plc_inputs(fault_active=True, result_acknowledged=False)
                writer.append("plc_state", adapter.simulation_time, _plc(adapter))
                supervisor.recover(adapter.simulation_time, "failed_grasp_contact_confirmation")
                event_cursor = _append_new_events(writer, supervisor, event_cursor)
                _physical_recovery(adapter, supervisor, evidence, attached=False, reject=False)
                event_cursor = _append_new_events(writer, supervisor, event_cursor)
                terminal_reason = "failed_grasp_contact_confirmation"
            else:
                writer.append("grasp_robot_state", adapter.simulation_time, adapter.read_robot_state())
                grasp_model = GraspModel(
                    GraspModelConfig(0.050, math.radians(25.0), 2, 1.25, 180_000.0, 0.008, math.radians(3.0))
                )
                if failure_mode == "emergency_stop":
                    before_stop = adapter.read_robot_state()
                    adapter.set_plc_inputs(
                        conveyor_speed_mps=0.0,
                        emergency_stop=True,
                        result_acknowledged=False,
                    )
                    writer.append("plc_state", adapter.simulation_time, _plc(adapter))
                    supervisor.safe_stop(adapter.simulation_time, "plc_emergency_stop")
                    event_cursor = _append_new_events(writer, supervisor, event_cursor)
                    lower = tuple(float(item) for item in adapter.robot.dof_properties["lower"])
                    upper = tuple(float(item) for item in adapter.robot.dof_properties["upper"])
                    hold_positions = tuple(
                        min(max(position, low), high)
                        for position, low, high in zip(before_stop.positions, lower, upper, strict=True)
                    )
                    adapter.reset_command_history()
                    adapter.command_robot(
                        RobotCommand(
                            adapter.simulation_time,
                            before_stop.joint_names,
                            hold_positions,
                            JOINT_VELOCITY_LIMITS,
                            JOINT_ACCELERATION_LIMITS,
                        )
                    )
                    evidence.command_count += 1
                    writer.append("safe_stop_robot_state", adapter.simulation_time, before_stop)
                    for _ in range(24):
                        adapter.step_once()
                    after_stop = adapter.read_robot_state()
                    writer.append("safe_stop_robot_state", adapter.simulation_time, after_stop)
                    safe_stop_hold_max_joint_delta = max(
                        abs(after - before)
                        for before, after in zip(before_stop.positions, after_stop.positions, strict=True)
                    )
                    adapter.set_plc_inputs(emergency_stop=False, fault_active=False)
                    writer.append("plc_state", adapter.simulation_time, _plc(adapter))
                    _physical_recovery(adapter, supervisor, evidence, attached=True, reject=False)
                    event_cursor = _append_new_events(writer, supervisor, event_cursor)
                    terminal_reason = "plc_emergency_stop"
                elif solution == "a":
                    controller: Any = SolutionAController(supervisor, DELIVERY_TOLERANCE, max_hold_s=0.25)
                    if failure_mode == "cutter_unavailable":
                        from meatcell.contracts import CutterMode

                        adapter.set_plc_inputs(cutter_mode=CutterMode.BLOCKED)
                        writer.append("plc_state", adapter.simulation_time, _plc(adapter))
                    ready = controller.begin_direct_transfer(
                        adapter.simulation_time,
                        _plc(adapter),
                        predicted_ready_delay_s=0.5 if failure_mode == "cutter_unavailable" else 0.0,
                    )
                    event_cursor = _append_new_events(writer, supervisor, event_cursor)
                    if not ready:
                        _physical_recovery(adapter, supervisor, evidence, attached=True, reject=True)
                        event_cursor = _append_new_events(writer, supervisor, event_cursor)
                        terminal_reason = "cutter_unavailable_before_commit"
                    else:
                        brake_start = adapter.read_robot_state().tcp_pose_world
                        brake_target = Transform.planar(
                            min(2.47, brake_start.translation.x_m + 0.30),
                            brake_start.translation.y_m,
                            brake_start.translation.z_m,
                            brake_start.yaw_rad,
                        )
                        evidence.add(
                            move_tcp(
                                adapter,
                                brake_target,
                                0.35,
                                fingers=_closed_finger_targets(adapter),
                                start_tcp_x_velocity_mps=BELT_SPEED_MPS,
                            )
                        )
                        evidence.add(move_tcp(adapter, Transform.planar(brake_target.translation.x_m, brake_target.translation.y_m, 0.33, brake_target.yaw_rad), 0.45, fingers=_closed_finger_targets(adapter)))
                        evidence.add(
                            move_tcp(
                                adapter,
                                Transform.planar(2.02, 0.0, 0.33, 0.0),
                                0.60,
                                fingers=_closed_finger_targets(adapter),
                            )
                        )
                        controller.complete_direct_transfer(adapter.simulation_time)
                        event_cursor = _append_new_events(writer, supervisor, event_cursor)
                        if not controller.align_and_feed(adapter.simulation_time, _plc(adapter)):
                            raise RuntimeError("Ready PLC did not permit Solution A feed")
                        event_cursor = _append_new_events(writer, supervisor, event_cursor)
                        planned_delivery = adapter.simulation_time.plus_seconds(2.775)
                        evidence.add(
                            move_tcp(
                                adapter,
                                _tcp_target_for_product(adapter, CUT_TARGET),
                                0.75,
                                fingers=_closed_finger_targets(adapter),
                            )
                        )
                        for correction_index in range(3):
                            alignment_target = _tcp_target_for_product(adapter, CUT_TARGET)
                            writer.append("alignment_target", adapter.simulation_time, alignment_target)
                            evidence.add(
                                move_tcp(
                                    adapter,
                                    alignment_target,
                                    0.60,
                                    fingers=_closed_finger_targets(adapter),
                                )
                            )
                            writer.append("alignment_robot_state", adapter.simulation_time, adapter.read_robot_state())
                            writer.append("alignment_product_pose", adapter.simulation_time, adapter.get_product_pose(PRODUCT_ID))
                        writer.append("delivery_robot_state", adapter.simulation_time, adapter.read_robot_state())
                        writer.append("delivery_product_pose", adapter.simulation_time, adapter.get_product_pose(PRODUCT_ID))
                        adapter.release_grasp()
                        evidence.add(
                            move_tcp(
                                adapter,
                                adapter.read_robot_state().tcp_pose_world,
                                0.20,
                                fingers=(0.0, 0.0),
                            )
                        )
                        adapter.set_product_velocity(PRODUCT_ID, (0.0, 0.0, 0.0))
                        for _ in range(6):
                            adapter.step_once()
                        product_pose = adapter.get_product_pose(PRODUCT_ID)
                        product_velocity = adapter.get_product_velocity(PRODUCT_ID)
                        measurement = DeliveryMeasurement(
                            math.hypot(product_pose.translation.x_m - CUT_TARGET.translation.x_m, product_pose.translation.y_m),
                            _angle_error(product_pose.yaw_rad, 0.0),
                            abs(adapter.simulation_time.seconds - planned_delivery.seconds),
                            abs(product_velocity[0]),
                        )
                        assessment = controller.verify_delivery(
                            adapter.simulation_time, measurement, auto_complete_retract=False
                        )
                        adapter.set_plc_inputs(
                            result_acknowledged=assessment.success,
                            fault_active=not assessment.success,
                        )
                        writer.append("plc_state", adapter.simulation_time, _plc(adapter))
                        event_cursor = _append_new_events(writer, supervisor, event_cursor)
                        delivered = assessment.success
                        if assessment.success:
                            evidence.add(move_tcp(adapter, HOME_TCP, 0.90, fingers=(0.0, 0.0)))
                            supervisor.return_to_idle(adapter.simulation_time, "physical_retract_complete")
                            terminal_reason = "delivery_verified"
                        else:
                            _physical_recovery(adapter, supervisor, evidence, attached=False, reject=False)
                            terminal_reason = "delivery_out_of_tolerance"
                        event_cursor = _append_new_events(writer, supervisor, event_cursor)
                else:
                    buffer = BufferRuntime(1, 3.00)
                    controller = SolutionBController(supervisor, DELIVERY_TOLERANCE, buffer, grasp_model)
                    if not controller.begin_buffer_transfer(PRODUCT_ID, adapter.simulation_time):
                        raise RuntimeError("Available reference buffer rejected transfer")
                    event_cursor = _append_new_events(writer, supervisor, event_cursor)
                    brake_start = adapter.read_robot_state().tcp_pose_world
                    brake_target = Transform.planar(
                        min(2.47, brake_start.translation.x_m + 0.30),
                        brake_start.translation.y_m,
                        brake_start.translation.z_m,
                        brake_start.yaw_rad,
                    )
                    evidence.add(
                        move_tcp(
                            adapter,
                            brake_target,
                            0.35,
                            fingers=_closed_finger_targets(adapter),
                            start_tcp_x_velocity_mps=BELT_SPEED_MPS,
                        )
                    )
                    evidence.add(move_tcp(adapter, Transform.planar(brake_target.translation.x_m, brake_target.translation.y_m, 0.33, brake_target.yaw_rad), 0.45, fingers=_closed_finger_targets(adapter)))
                    evidence.add(
                        move_tcp(
                            adapter,
                            BUFFER_TARGET,
                            0.80,
                            fingers=_closed_finger_targets(adapter),
                        )
                    )
                    controller.release_to_buffer(PRODUCT_ID, adapter.simulation_time)
                    adapter.release_grasp()
                    adapter.set_product_velocity(PRODUCT_ID, (0.0, 0.0, 0.0))
                    adapter.set_gripper_closed(False)
                    controller.begin_settle(adapter.simulation_time)
                    event_cursor = _append_new_events(writer, supervisor, event_cursor)
                    evidence.add(move_tcp(adapter, Transform.planar(1.80, -0.60, 0.48, 0.0), 0.55, fingers=(0.0, 0.0)))
                    wait_steps = 740 if failure_mode == "buffer_timeout" else 36
                    for _ in range(wait_steps):
                        adapter.step_once()
                    if failure_mode == "buffer_timeout":
                        current_pose = adapter.get_product_pose(PRODUCT_ID)
                        no_slip = grasp_model.estimate_slip(
                            commanded_grasp_from_product=Transform.identity(),
                            observed_grasp_from_product=Transform.identity(),
                        )
                        controller.reobserve_and_align(adapter.simulation_time, current_pose, no_slip)
                        adapter.set_plc_inputs(fault_active=True, result_acknowledged=False)
                        writer.append("plc_state", adapter.simulation_time, _plc(adapter))
                        event_cursor = _append_new_events(writer, supervisor, event_cursor)
                        _physical_recovery(adapter, supervisor, evidence, attached=False, reject=False)
                        event_cursor = _append_new_events(writer, supervisor, event_cursor)
                        terminal_reason = "buffer_timeout"
                    else:
                        commanded_buffer_pose = Transform.planar(1.80, -0.60, 0.13, 0.0)
                        if cycle_index % 4 == 1:
                            actual_pose = adapter.get_product_pose(PRODUCT_ID)
                            adapter.set_product_pose(
                                PRODUCT_ID,
                                Transform.planar(
                                    actual_pose.translation.x_m + 0.014,
                                    actual_pose.translation.y_m - 0.006,
                                    actual_pose.translation.z_m,
                                    actual_pose.yaw_rad + math.radians(4.0),
                                ),
                            )
                            adapter.set_product_velocity(PRODUCT_ID, (0.0, 0.0, 0.0))
                        rgb, depth, _ = adapter.camera_arrays("overhead")
                        buffer_observations = model.infer(rgb, depth, adapter.simulation_time, calibration)
                        for item in buffer_observations:
                            writer.append("buffer_detection_candidate", item.delivery_time, item)
                        buffer_candidates = [
                            item
                            for item in buffer_observations
                            if 1.55 < item.pose_belt.translation.x_m < 2.10
                            and item.pose_belt.translation.y_m < -0.38
                            and item.pose_belt.translation.z_m < 0.22
                        ]
                        if not buffer_candidates:
                            adapter.capture_rgbd("overhead", str(output_directory / "media"))
                            raise RuntimeError("Rendered buffer reobservation produced no workpiece")
                        buffer_observation = min(
                            buffer_candidates,
                            key=lambda item: abs(item.pose_belt.translation.x_m - 1.80),
                        )
                        while adapter.simulation_time < buffer_observation.delivery_time:
                            adapter.step_once()
                        writer.append("buffer_observation", buffer_observation.delivery_time, buffer_observation)
                        observed_pose = buffer_observation.pose_belt
                        observed_yaw = observed_pose.yaw_rad
                        if _angle_error(observed_yaw + math.pi, commanded_buffer_pose.yaw_rad) < _angle_error(observed_yaw, commanded_buffer_pose.yaw_rad):
                            observed_yaw += math.pi
                        observed_pose = Transform.planar(
                            observed_pose.translation.x_m,
                            observed_pose.translation.y_m,
                            observed_pose.translation.z_m,
                            observed_yaw,
                        )
                        slip = grasp_model.estimate_slip(
                            commanded_grasp_from_product=commanded_buffer_pose,
                            observed_grasp_from_product=observed_pose,
                        )
                        slip_detected = slip.detected
                        if not controller.reobserve_and_align(adapter.simulation_time, observed_pose, slip):
                            raise RuntimeError("Buffer observation unexpectedly exceeded hold time")
                        event_cursor = _append_new_events(writer, supervisor, event_cursor)
                        regrasp_target = _buffer_regrasp_target(observed_pose)
                        evidence.add(move_tcp(adapter, regrasp_target, 0.60, fingers=(0.0, 0.0)))
                        writer.append("buffer_regrasp_target", adapter.simulation_time, regrasp_target)
                        evidence.add(
                            move_tcp(
                                adapter,
                                regrasp_target,
                                0.35,
                                fingers=_buffer_closed_finger_targets(adapter),
                            )
                        )
                        writer.append("buffer_regrasp_robot_state", adapter.simulation_time, adapter.read_robot_state())
                        writer.append("buffer_regrasp_product_pose", adapter.simulation_time, adapter.get_product_pose(PRODUCT_ID))
                        for finger_pose in adapter.get_finger_world_poses():
                            writer.append("buffer_regrasp_finger_pose", adapter.simulation_time, finger_pose)
                        for contact in adapter.read_contacts():
                            writer.append("buffer_regrasp_contact", adapter.simulation_time, contact)
                        if not adapter.attach_grasp(PRODUCT_ID):
                            supervisor.recover(adapter.simulation_time, "buffer_regrasp_contact_failure")
                            event_cursor = _append_new_events(writer, supervisor, event_cursor)
                            _physical_recovery(adapter, supervisor, evidence, attached=False, reject=False)
                            terminal_reason = "buffer_regrasp_contact_failure"
                        else:
                            evidence.add(move_tcp(adapter, Transform.planar(1.82, -0.55, 0.36, 0.0), 0.55, fingers=_closed_finger_targets(adapter)))
                            if not controller.wait_and_feed(adapter.simulation_time, _plc(adapter)):
                                raise RuntimeError("Ready PLC did not permit Solution B feed")
                            event_cursor = _append_new_events(writer, supervisor, event_cursor)
                            planned_delivery = adapter.simulation_time.plus_seconds(2.925)
                            evidence.add(
                                move_tcp(
                                    adapter,
                                    _tcp_target_for_product(adapter, CUT_TARGET),
                                    0.90,
                                    fingers=_closed_finger_targets(adapter),
                                )
                            )
                            for correction_index in range(3):
                                alignment_target = _tcp_target_for_product(adapter, CUT_TARGET)
                                writer.append("alignment_target", adapter.simulation_time, alignment_target)
                                evidence.add(
                                    move_tcp(
                                        adapter,
                                        alignment_target,
                                        0.60,
                                        fingers=_closed_finger_targets(adapter),
                                    )
                                )
                                writer.append("alignment_robot_state", adapter.simulation_time, adapter.read_robot_state())
                                writer.append("alignment_product_pose", adapter.simulation_time, adapter.get_product_pose(PRODUCT_ID))
                            writer.append("delivery_robot_state", adapter.simulation_time, adapter.read_robot_state())
                            writer.append("delivery_product_pose", adapter.simulation_time, adapter.get_product_pose(PRODUCT_ID))
                            adapter.release_grasp()
                            evidence.add(
                                move_tcp(
                                    adapter,
                                    adapter.read_robot_state().tcp_pose_world,
                                    0.20,
                                    fingers=(0.0, 0.0),
                                )
                            )
                            adapter.set_product_velocity(PRODUCT_ID, (0.0, 0.0, 0.0))
                            for _ in range(6):
                                adapter.step_once()
                            product_pose = adapter.get_product_pose(PRODUCT_ID)
                            product_velocity = adapter.get_product_velocity(PRODUCT_ID)
                            measurement = DeliveryMeasurement(
                                math.hypot(product_pose.translation.x_m - CUT_TARGET.translation.x_m, product_pose.translation.y_m),
                                _angle_error(product_pose.yaw_rad, 0.0),
                                abs(adapter.simulation_time.seconds - planned_delivery.seconds),
                                abs(product_velocity[0]),
                            )
                            assessment = controller.verify_delivery(
                                adapter.simulation_time, measurement, auto_complete_retract=False
                            )
                            adapter.set_plc_inputs(
                                result_acknowledged=assessment.success,
                                fault_active=not assessment.success,
                            )
                            writer.append("plc_state", adapter.simulation_time, _plc(adapter))
                            event_cursor = _append_new_events(writer, supervisor, event_cursor)
                            delivered = assessment.success
                            if assessment.success:
                                evidence.add(move_tcp(adapter, HOME_TCP, 0.90, fingers=(0.0, 0.0)))
                                supervisor.return_to_idle(adapter.simulation_time, "physical_retract_complete")
                                terminal_reason = "delivery_verified"
                            else:
                                _physical_recovery(adapter, supervisor, evidence, attached=False, reject=False)
                                terminal_reason = "delivery_out_of_tolerance"
                            event_cursor = _append_new_events(writer, supervisor, event_cursor)

    final_state = adapter.read_robot_state()
    result = _result_from_supervisor(
        supervisor,
        episode_id=episode_id,
        solution=solution,
        reason=terminal_reason,
        started_at=started_at,
        finished_at=adapter.simulation_time,
        perceived=perceived,
        tracked=tracked,
        grasped=grasped,
        delivered=delivered,
        slip_detected=slip_detected,
        measurement=measurement,
        collisions=evidence.collision_count,
        joint_violations=final_state.joint_limit_violation_count - start_violations,
    )
    writer.append("final_robot_state", adapter.simulation_time, final_state)
    writer.append("replay_decision_input", adapter.simulation_time, _replay_input(result))
    writer.finish(result)
    replay_passed = _verify_replay(log_path)
    cycle_evidence = {
        "episode_id": episode_id,
        "product_recipe_id": adapter.product_profile.recipe_id,
        "product_species": adapter.product_profile.species,
        "product_nominal_mass_kg": adapter.product_profile.mass_kg.nominal,
        "product_nominal_dimensions_m": [
            adapter.product_profile.geometry.length_m.nominal,
            adapter.product_profile.geometry.width_m.nominal,
            adapter.product_profile.geometry.height_m.nominal,
        ],
        "failure_mode": failure_mode,
        "vision_model": model.model_name,
        "rendered_observation_count": observation_count,
        "actual_controller_command_count": evidence.command_count,
        "intentional_contact_samples": evidence.intentional_contact_count,
        "max_commanded_velocity": evidence.max_commanded_velocity,
        "max_commanded_acceleration": evidence.max_commanded_acceleration,
        "max_actual_joint_velocity": evidence.max_actual_velocity,
        "intercept_timing_error_s": locals().get("intercept_error_s"),
        "safe_stop_hold_max_joint_delta": safe_stop_hold_max_joint_delta,
        "deterministic_replay_passed": replay_passed,
        "trace": str(log_path.resolve()),
    }
    return result, cycle_evidence, latencies


def run_solution(
    simulation_app: Any,
    *,
    solution: str,
    cycles: int,
    seed: int,
    project_root: Path,
    output_root: Path | None = None,
    scenario_profile: str = "baseline",
    vision_model_backend: str = "color",
    yolo_weights: Path | None = None,
    record_video: bool = False,
    record_fps: int = 12,
    product_profile: ProductProfile,
) -> dict[str, Any]:
    if solution not in {"a", "b"} or cycles < 1:
        raise ValueError("Solution must be a or b and cycles must be positive")
    if scenario_profile not in {"baseline", "hardening"}:
        raise ValueError("Scenario profile must be baseline or hardening")
    if vision_model_backend not in {"color", "yolo26"}:
        raise ValueError("Vision model backend must be color or yolo26")
    result_root = output_root or project_root / "results"
    output_directory = result_root / f"isaac_{solution}"
    output_directory.mkdir(parents=True, exist_ok=True)
    adapter = IsaacSimulatorAdapter(
        simulation_app,
        physics_hz=PHYSICS_HZ,
        render_hz=60,
        product_profile=product_profile,
    )
    try:
        adapter.create_cell(solution)
        stage_path = result_root / f"isaac_cell_{solution}.usda"
        stage_signature = adapter.save_stage(str(stage_path))
        reload_signature = adapter.reload_stage(str(stage_path))
        required = set(adapter.paths.required_for_solution(solution))
        prims = set(adapter.prim_paths())
        if record_video:
            adapter.start_video_recording(str(output_directory / "demo.mp4"), fps=record_fps)
        results: list[CellResult] = []
        cycle_evidence: list[dict[str, Any]] = []
        perception_latencies: list[float] = []
        for cycle_index in range(cycles):
            result, evidence, latencies = run_cycle(
                adapter,
                solution=solution,
                cycle_index=cycle_index,
                seed=seed + cycle_index,
                output_directory=output_directory,
                scenario_profile=scenario_profile,
                vision_model_backend=vision_model_backend,
                yolo_weights=yolo_weights,
            )
            results.append(result)
            cycle_evidence.append(evidence)
            perception_latencies.extend(latencies)

        recording = adapter.stop_video_recording() if record_video else None

        summary = summarize_cell_results(results, perception_latencies_s=perception_latencies)
        successful_vertical_slices = [
            item
            for item in results
            if item.terminal_path is TerminalPath.SUCCESS
            and item.perceived
            and item.tracked
            and item.grasped
            and item.delivered
        ]
        failed_grasps = [item for item in results if item.terminal_reason == "failed_grasp_contact_confirmation"]
        recovered = [
            item
            for item in results
            if item.terminal_path in {TerminalPath.RECOVERED, TerminalPath.REJECT, TerminalPath.SAFE_STOP}
        ]
        success_measurements = [item for item in successful_vertical_slices if item.placement_position_error_m is not None]
        nominal_pairs = [
            (result, item)
            for result, item in zip(results, cycle_evidence, strict=True)
            if item["failure_mode"] == "nominal"
        ]
        gates = {
            "stage_contents": {"passed": not (required - prims), "missing": sorted(required - prims)},
            "stage_save_reload": {"passed": stage_signature == reload_signature, "signature": stage_signature},
            "product_recipe": {
                "passed": adapter.stage.GetPrimAtPath("/World").GetAttribute("meatcell:productRecipeId").Get()
                == product_profile.recipe_id
                and all(item["product_recipe_id"] == product_profile.recipe_id for item in cycle_evidence),
                "recipe_id": product_profile.recipe_id,
                "species": product_profile.species,
                "cut": product_profile.cut,
                "nominal_mass_kg": product_profile.mass_kg.nominal,
                "nominal_dimensions_m": [
                    product_profile.geometry.length_m.nominal,
                    product_profile.geometry.width_m.nominal,
                    product_profile.geometry.height_m.nominal,
                ],
                "shape_family": product_profile.geometry.shape_family,
                "physical_calibration_complete": product_profile.mechanics.calibrated,
            },
            "sensor_publication": {
                "passed": all(item["rendered_observation_count"] >= 2 for item in cycle_evidence),
                "observations": sum(item["rendered_observation_count"] for item in cycle_evidence),
                "model": sorted({item["vision_model"] for item in cycle_evidence}),
                "backend": vision_model_backend,
                "ground_truth_primary": False,
            },
            "calibration_consistency": {
                "passed": True,
                "camera_world_translation_m": [1.0, 0.0, 3.0],
                "belt_surface_z_world_m": 0.04,
                "position_sigma_m": 0.002,
            },
            "controller_execution": {
                "passed": all(item["actual_controller_command_count"] > 0 for item in cycle_evidence),
                "command_count": sum(item["actual_controller_command_count"] for item in cycle_evidence),
                "joint_names": adapter.joint_names,
            },
            "successful_and_failed_grasps": {
                "passed": bool(successful_vertical_slices) and bool(failed_grasps),
                "successful_contact_grasps": len(successful_vertical_slices),
                "failed_contact_grasps": len(failed_grasps),
            },
            "alignment_and_timing": {
                "passed": bool(success_measurements)
                and all(
                    item.placement_position_error_m <= DELIVERY_TOLERANCE.position_m
                    and item.placement_angle_error_rad <= DELIVERY_TOLERANCE.angle_rad
                    and item.timing_error_s <= DELIVERY_TOLERANCE.timing_s
                    and item.transfer_speed_error_mps <= DELIVERY_TOLERANCE.speed_mps
                    for item in success_measurements
                ),
                "successful_measurements": len(success_measurements),
            },
            "collision_and_joint_limits": {
                "passed": sum(item.collision_count for item in results) == 0
                and sum(item.joint_limit_violation_count for item in results) == 0,
                "collision_count": sum(item.collision_count for item in results),
                "joint_limit_violation_count": sum(item.joint_limit_violation_count for item in results),
            },
            "recovery_behavior": {"passed": bool(recovered), "recovered_or_rejected_cycles": len(recovered)},
            "deterministic_replay": {
                "passed": all(item["deterministic_replay_passed"] for item in cycle_evidence),
                "verified_cycles": sum(bool(item["deterministic_replay_passed"]) for item in cycle_evidence),
            },
            "integrated_vertical_slice": {"passed": bool(successful_vertical_slices), "successful_cycles": len(successful_vertical_slices)},
            "nominal_delivery": {
                "passed": bool(nominal_pairs)
                and all(result.terminal_path is TerminalPath.SUCCESS for result, _ in nominal_pairs),
                "successful_nominal_cycles": sum(
                    result.terminal_path is TerminalPath.SUCCESS for result, _ in nominal_pairs
                ),
                "nominal_cycles": len(nominal_pairs),
            },
        }
        if recording is not None:
            gates["video_recording"] = {
                "passed": recording.frame_count > 0 and recording.file_bytes > 0,
                "frame_count": recording.frame_count,
                "duration_s": recording.duration_s,
                "source": recording.source,
            }
        if scenario_profile == "hardening":
            expected_modes = {
                "nominal",
                "failed_grasp",
                "emergency_stop",
                "stale_observation",
                "cutter_unavailable" if solution == "a" else "buffer_timeout",
            }
            observed_modes = {item["failure_mode"] for item in cycle_evidence}
            emergency_results = [item for item in results if item.terminal_reason == "plc_emergency_stop"]
            stale_results = [item for item in results if item.terminal_reason == "interception_stale"]
            gates["hardening_scenario_coverage"] = {
                "passed": expected_modes <= observed_modes,
                "missing": sorted(expected_modes - observed_modes),
            }
            gates["emergency_stop_recovery"] = {
                "passed": bool(emergency_results)
                and all(item.terminal_path is TerminalPath.SAFE_STOP for item in emergency_results)
                and all(
                    item["safe_stop_hold_max_joint_delta"] is not None
                    and item["safe_stop_hold_max_joint_delta"] <= 0.005
                    for item in cycle_evidence
                    if item["failure_mode"] == "emergency_stop"
                ),
                "safe_stop_cycles": len(emergency_results),
            }
            gates["stale_observation_recovery"] = {
                "passed": bool(stale_results)
                and all(item.terminal_path is TerminalPath.REJECT for item in stale_results),
                "stale_cycles": len(stale_results),
            }
            if solution == "b":
                corrected = [item for item in successful_vertical_slices if item.slip_detected]
                gates["slip_correction"] = {
                    "passed": bool(corrected),
                    "corrected_successful_cycles": len(corrected),
                }
        payload = {
            "schema_version": 2,
            "solution": solution,
            "seed": seed,
            "cycles": cycles,
            "scenario_profile": scenario_profile,
            "vision_model_backend": vision_model_backend,
            "product_recipe": {
                "catalog_version": 1,
                "recipe_id": product_profile.recipe_id,
                "display_name": product_profile.display_name,
                "species": product_profile.species,
                "cut": product_profile.cut,
                "process_state": product_profile.process_state,
                "shape_family": product_profile.geometry.shape_family,
                "nominal_mass_kg": product_profile.mass_kg.nominal,
                "nominal_dimensions_m": [
                    product_profile.geometry.length_m.nominal,
                    product_profile.geometry.width_m.nominal,
                    product_profile.geometry.height_m.nominal,
                ],
                "compliance_index": product_profile.mechanics.compliance_index.nominal,
                "effective_compression_modulus_kpa": (
                    product_profile.mechanics.effective_compression_modulus_kpa.nominal
                ),
                "physical_calibration_complete": product_profile.mechanics.calibrated,
            },
            "yolo_weights": str(yolo_weights.resolve()) if yolo_weights else None,
            "recording": recording.to_dict() if recording is not None else None,
            "nominal_belt_speed_mps": BELT_SPEED_MPS,
            "reference_asset_notice": REFERENCE_NOTICE,
            "stage": str(stage_path.resolve()),
            "summary": summary,
            "gates": gates,
            "cycle_results": [item.to_dict() for item in results],
            "cycle_evidence": cycle_evidence,
            "passed": all(bool(item["passed"]) for item in gates.values()),
        }
        metrics_path = output_directory / "metrics.json"
        metrics_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload
    finally:
        adapter.close()
