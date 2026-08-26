"""Deterministic timed-interception feasibility and ranking."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .contracts import (
    Contract,
    ContractEnum,
    GraspCandidate,
    InterceptionPlan,
    ObjectTrack,
    SimTime,
    TrackLifecycle,
    Transform,
    Twist,
    Vector3,
)
from .frames import compose, rotate_vector
from .physics import trapezoidal_motion_time_s


class PlanRejection(ContractEnum):
    NONE = "none"
    TOO_LATE = "too_late"
    STALE = "stale"
    UNCERTAIN = "uncertain"
    UNREACHABLE = "unreachable"
    UNSAFE = "unsafe"
    INVALID_GRASP = "invalid_grasp"
    VELOCITY_MISMATCH = "velocity_mismatch"
    TRACK_NOT_CONFIRMED = "track_not_confirmed"


@dataclass(frozen=True)
class PlanDecision(Contract):
    accepted: bool
    reason: PlanRejection
    plan: InterceptionPlan | None
    evaluated_candidates: int

    def __post_init__(self) -> None:
        if self.accepted != (self.plan is not None):
            raise ValueError("Accepted plan decisions must contain exactly one plan")
        if self.accepted != (self.reason is PlanRejection.NONE):
            raise ValueError("Accepted plan decision must use reason NONE")
        if self.evaluated_candidates < 0:
            raise ValueError("evaluated_candidates must be nonnegative")


@dataclass(frozen=True)
class UnsafeZone:
    x_min_m: float
    x_max_m: float
    y_min_m: float
    y_max_m: float

    def contains(self, x_m: float, y_m: float) -> bool:
        return self.x_min_m <= x_m <= self.x_max_m and self.y_min_m <= y_m <= self.y_max_m


@dataclass(frozen=True)
class InterceptionConfig:
    pick_x_min_m: float = 0.8
    pick_x_max_m: float = 1.55
    candidate_step_m: float = 0.025
    workspace_y_abs_m: float = 0.55
    workspace_z_min_m: float = 0.0
    workspace_z_max_m: float = 1.2
    home_pose_world: Transform = Transform.planar(1.1, 0.0, 0.85, 0.0)
    max_tcp_speed_mps: float = 10.0
    max_tcp_accel_mps2: float = 80.0
    grasp_close_s: float = 0.045
    command_latency_s: float = 0.010
    timing_reserve_s: float = 0.035
    commit_lead_s: float = 0.080
    max_observation_age_s: float = 0.120
    max_position_sigma_m: float = 0.030
    velocity_match_reserve_mps: float = 0.25
    minimum_boundary_clearance_m: float = 0.010

    def __post_init__(self) -> None:
        if self.pick_x_max_m <= self.pick_x_min_m or self.candidate_step_m <= 0.0:
            raise ValueError("Invalid interception pick window")
        if self.workspace_y_abs_m <= 0.0 or self.workspace_z_max_m <= self.workspace_z_min_m:
            raise ValueError("Invalid interception workspace")
        for name in (
            "max_tcp_speed_mps",
            "max_tcp_accel_mps2",
            "grasp_close_s",
            "commit_lead_s",
            "max_observation_age_s",
            "max_position_sigma_m",
        ):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be positive")


class InterceptionPlanner:
    def __init__(self, config: InterceptionConfig, unsafe_zones: tuple[UnsafeZone, ...] = ()) -> None:
        self.config = config
        self.unsafe_zones = unsafe_zones

    def _reject(self, reason: PlanRejection, count: int = 0) -> PlanDecision:
        return PlanDecision(False, reason, None, count)

    def plan(
        self,
        *,
        track: ObjectTrack,
        grasp: GraspCandidate,
        now: SimTime,
        world_from_belt: Transform,
    ) -> PlanDecision:
        if track.lifecycle is not TrackLifecycle.CONFIRMED:
            return self._reject(PlanRejection.TRACK_NOT_CONFIRMED)
        age_s = now.seconds - track.last_exposure_time.seconds
        if age_s < 0.0 or age_s > self.config.max_observation_age_s:
            return self._reject(PlanRejection.STALE)
        sigma_m = math.sqrt(
            max(
                track.position_variance_m2.x_m,
                track.position_variance_m2.y_m,
                track.position_variance_m2.z_m,
            )
        )
        if sigma_m > self.config.max_position_sigma_m:
            return self._reject(PlanRejection.UNCERTAIN)
        if (
            grasp.boundary_clearance_m < self.config.minimum_boundary_clearance_m
            or grasp.capture_margin_m <= sigma_m
        ):
            return self._reject(PlanRejection.INVALID_GRASP)
        belt_speed = track.twist_belt.linear_mps.x_m
        if belt_speed <= 0.0:
            return self._reject(PlanRejection.TOO_LATE)
        if self.config.max_tcp_speed_mps < belt_speed + self.config.velocity_match_reserve_mps:
            return self._reject(PlanRejection.VELOCITY_MISMATCH)

        candidates: list[tuple[float, int, InterceptionPlan]] = []
        unsafe_seen = False
        unreachable_seen = False
        too_late_seen = False
        evaluated = 0
        x_m = self.config.pick_x_min_m
        while x_m <= self.config.pick_x_max_m + 1e-12:
            evaluated += 1
            delay_s = (x_m - track.pose_belt.translation.x_m) / belt_speed
            if delay_s <= 0.0:
                too_late_seen = True
                x_m += self.config.candidate_step_m
                continue
            intercept_at = now.plus_seconds(delay_s)
            yaw = track.pose_belt.yaw_rad + track.twist_belt.angular_radps.z_m * delay_s
            product_belt = Transform.planar(
                x_m,
                track.pose_belt.translation.y_m + track.twist_belt.linear_mps.y_m * delay_s,
                track.pose_belt.translation.z_m,
                yaw,
            )
            grasp_belt = compose(product_belt, grasp.grasp_in_product)
            grasp_world = compose(world_from_belt, grasp_belt)
            point = grasp_world.translation
            if any(zone.contains(point.x_m, point.y_m) for zone in self.unsafe_zones):
                unsafe_seen = True
                x_m += self.config.candidate_step_m
                continue
            if (
                abs(point.y_m) > self.config.workspace_y_abs_m
                or not self.config.workspace_z_min_m <= point.z_m <= self.config.workspace_z_max_m
            ):
                unreachable_seen = True
                x_m += self.config.candidate_step_m
                continue
            dx = point.x_m - self.config.home_pose_world.translation.x_m
            dy = point.y_m - self.config.home_pose_world.translation.y_m
            dz = point.z_m - self.config.home_pose_world.translation.z_m
            motion_time = trapezoidal_motion_time_s(
                math.sqrt(dx * dx + dy * dy + dz * dz),
                self.config.max_tcp_speed_mps,
                self.config.max_tcp_accel_mps2,
            )
            required_s = motion_time + self.config.grasp_close_s + self.config.command_latency_s + self.config.timing_reserve_s
            reachability_margin_s = delay_s - required_s
            if reachability_margin_s < 0.0 or delay_s <= self.config.commit_lead_s:
                too_late_seen = True
                x_m += self.config.candidate_step_m
                continue
            commit_at = SimTime(
                intercept_at.nanoseconds - SimTime.from_seconds(self.config.commit_lead_s).nanoseconds
            )
            velocity_world = rotate_vector(world_from_belt.rotation, track.twist_belt.linear_mps)
            valid_until = commit_at
            plan = InterceptionPlan(
                plan_id=f"{track.track_id}-{intercept_at.nanoseconds}",
                track_id=track.track_id,
                source_exposure_time=track.last_exposure_time,
                created_at=now,
                intercept_at=intercept_at,
                commit_at=commit_at,
                abort_deadline=commit_at,
                valid_until=valid_until,
                grasp=grasp,
                interception_pose_world=grasp_world,
                required_tcp_twist_world=Twist(velocity_world, track.twist_belt.angular_radps),
                uncertainty_margin_m=grasp.capture_margin_m - sigma_m,
                reachability_margin_s=reachability_margin_s,
            )
            robot_cost = motion_time - 0.05 * reachability_margin_s
            candidates.append((robot_cost, intercept_at.nanoseconds, plan))
            x_m += self.config.candidate_step_m

        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1], item[2].plan_id))
            return PlanDecision(True, PlanRejection.NONE, candidates[0][2], evaluated)
        if unsafe_seen:
            return self._reject(PlanRejection.UNSAFE, evaluated)
        if unreachable_seen:
            return self._reject(PlanRejection.UNREACHABLE, evaluated)
        if too_late_seen:
            return self._reject(PlanRejection.TOO_LATE, evaluated)
        return self._reject(PlanRejection.UNREACHABLE, evaluated)

    @staticmethod
    def validate_live(plan: InterceptionPlan, now: SimTime) -> bool:
        return now <= plan.valid_until
