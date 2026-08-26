"""Encoder-informed planar tracking and future-pose prediction."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math

from .contracts import (
    ObjectObservation,
    ObjectTrack,
    SimTime,
    TrackLifecycle,
    Transform,
    Twist,
    Vector3,
)


def _angle_delta(current: float, previous: float) -> float:
    return math.atan2(math.sin(current - previous), math.cos(current - previous))


@dataclass(frozen=True)
class TrackerConfig:
    confirmation_hits: int = 2
    max_missed_updates: int = 3
    expiry_s: float = 0.25
    association_distance_m: float = 0.20
    velocity_measurement_weight: float = 0.65
    position_process_variance_m2_per_s: float = 0.0004
    yaw_process_variance_rad2_per_s: float = 0.0025

    def __post_init__(self) -> None:
        if self.confirmation_hits < 1 or self.max_missed_updates < 0:
            raise ValueError("Tracker hit and missed limits are invalid")
        if self.expiry_s <= 0.0 or self.association_distance_m <= 0.0:
            raise ValueError("Tracker expiry and association distance must be positive")
        if not 0.0 <= self.velocity_measurement_weight <= 1.0:
            raise ValueError("velocity_measurement_weight must be between 0 and 1")
        if self.position_process_variance_m2_per_s < 0.0 or self.yaw_process_variance_rad2_per_s < 0.0:
            raise ValueError("Tracker process variances must be nonnegative")


@dataclass
class _TrackState:
    contract: ObjectTrack
    last_observed_pose: Transform


class ObjectTracker:
    def __init__(self, config: TrackerConfig = TrackerConfig()) -> None:
        self.config = config
        self._tracks: dict[str, _TrackState] = {}
        self._detection_to_track: dict[str, str] = {}
        self._next_id = 1

    @property
    def tracks(self) -> tuple[ObjectTrack, ...]:
        return tuple(self._tracks[key].contract for key in sorted(self._tracks))

    def _new_id(self) -> str:
        value = f"track-{self._next_id:04d}"
        self._next_id += 1
        return value

    def _associate(self, observation: ObjectObservation) -> str | None:
        mapped = self._detection_to_track.get(observation.detection_id)
        if mapped in self._tracks and self._tracks[mapped].contract.lifecycle is not TrackLifecycle.EXPIRED:
            return mapped
        candidates: list[tuple[float, str]] = []
        for track_id, state in self._tracks.items():
            track = state.contract
            if track.lifecycle is TrackLifecycle.EXPIRED:
                continue
            predicted = self._predict_contract(track, observation.exposure_time)
            dx = predicted.pose_belt.translation.x_m - observation.pose_belt.translation.x_m
            dy = predicted.pose_belt.translation.y_m - observation.pose_belt.translation.y_m
            distance = math.hypot(dx, dy)
            if distance <= self.config.association_distance_m:
                candidates.append((distance, track_id))
        return min(candidates)[1] if candidates else None

    def update(
        self,
        observation: ObjectObservation,
        *,
        current_time: SimTime,
        encoder_speed_mps: float,
    ) -> ObjectTrack:
        if current_time < observation.delivery_time:
            raise ValueError("Tracker cannot consume an observation before delivery")
        if encoder_speed_mps < 0.0 or not math.isfinite(encoder_speed_mps):
            raise ValueError("encoder_speed_mps must be finite and nonnegative")
        track_id = self._associate(observation)
        if track_id is None:
            track_id = self._new_id()
            velocity = Twist(Vector3(encoder_speed_mps, 0.0, 0.0), Vector3(0.0, 0.0, 0.0))
            lifecycle = TrackLifecycle.CONFIRMED if self.config.confirmation_hits == 1 else TrackLifecycle.TENTATIVE
            at_exposure = ObjectTrack(
                track_id=track_id,
                lifecycle=lifecycle,
                last_exposure_time=observation.exposure_time,
                state_time=observation.exposure_time,
                pose_belt=observation.pose_belt,
                twist_belt=velocity,
                position_variance_m2=observation.position_variance_m2,
                yaw_variance_rad2=observation.yaw_variance_rad2,
                hit_count=1,
                missed_count=0,
            )
            self._tracks[track_id] = _TrackState(at_exposure, observation.pose_belt)
        else:
            state = self._tracks[track_id]
            previous = state.contract
            if observation.exposure_time <= previous.last_exposure_time:
                raise ValueError("Observation exposure timestamps must increase within a track")
            dt = observation.exposure_time.seconds - previous.last_exposure_time.seconds
            measured_vx = (
                observation.pose_belt.translation.x_m - state.last_observed_pose.translation.x_m
            ) / dt
            measured_vy = (
                observation.pose_belt.translation.y_m - state.last_observed_pose.translation.y_m
            ) / dt
            measured_yaw_rate = _angle_delta(observation.pose_belt.yaw_rad, state.last_observed_pose.yaw_rad) / dt
            weight = self.config.velocity_measurement_weight
            velocity = Twist(
                Vector3(
                    weight * measured_vx + (1.0 - weight) * encoder_speed_mps,
                    weight * measured_vy,
                    0.0,
                ),
                Vector3(0.0, 0.0, weight * measured_yaw_rate),
            )
            hits = previous.hit_count + 1
            lifecycle = TrackLifecycle.CONFIRMED if hits >= self.config.confirmation_hits else TrackLifecycle.TENTATIVE
            at_exposure = ObjectTrack(
                track_id=track_id,
                lifecycle=lifecycle,
                last_exposure_time=observation.exposure_time,
                state_time=observation.exposure_time,
                pose_belt=observation.pose_belt,
                twist_belt=velocity,
                position_variance_m2=observation.position_variance_m2,
                yaw_variance_rad2=observation.yaw_variance_rad2,
                hit_count=hits,
                missed_count=0,
            )
            state.contract = at_exposure
            state.last_observed_pose = observation.pose_belt
        self._detection_to_track[observation.detection_id] = track_id
        propagated = self._predict_contract(self._tracks[track_id].contract, current_time)
        self._tracks[track_id].contract = propagated
        return propagated

    def _predict_contract(self, track: ObjectTrack, timestamp: SimTime) -> ObjectTrack:
        if timestamp < track.state_time:
            if timestamp < track.last_exposure_time:
                raise ValueError("Cannot predict before the last exposure")
            base_time = track.last_exposure_time
            base_pose = self._tracks.get(track.track_id, _TrackState(track, track.pose_belt)).last_observed_pose
        else:
            base_time = track.state_time
            base_pose = track.pose_belt
        dt = timestamp.seconds - base_time.seconds
        pose = Transform.planar(
            base_pose.translation.x_m + track.twist_belt.linear_mps.x_m * dt,
            base_pose.translation.y_m + track.twist_belt.linear_mps.y_m * dt,
            base_pose.translation.z_m + track.twist_belt.linear_mps.z_m * dt,
            base_pose.yaw_rad + track.twist_belt.angular_radps.z_m * dt,
        )
        growth = self.config.position_process_variance_m2_per_s * max(0.0, dt)
        return replace(
            track,
            state_time=timestamp,
            pose_belt=pose,
            position_variance_m2=Vector3(
                track.position_variance_m2.x_m + growth,
                track.position_variance_m2.y_m + growth,
                track.position_variance_m2.z_m + growth,
            ),
            yaw_variance_rad2=track.yaw_variance_rad2
            + self.config.yaw_process_variance_rad2_per_s * max(0.0, dt),
        )

    def predict(self, track_id: str, timestamp: SimTime) -> ObjectTrack:
        try:
            track = self._tracks[track_id].contract
        except KeyError as exc:
            raise KeyError(f"Unknown track ID: {track_id}") from exc
        if track.lifecycle is TrackLifecycle.EXPIRED:
            raise ValueError(f"Track {track_id} is expired")
        return self._predict_contract(track, timestamp)

    def mark_missed(self, track_id: str, current_time: SimTime) -> ObjectTrack:
        try:
            state = self._tracks[track_id]
        except KeyError as exc:
            raise KeyError(f"Unknown track ID: {track_id}") from exc
        current = self._predict_contract(state.contract, current_time)
        missed = current.missed_count + 1
        age_s = current_time.seconds - current.last_exposure_time.seconds
        if age_s >= self.config.expiry_s:
            lifecycle = TrackLifecycle.EXPIRED
        elif missed > self.config.max_missed_updates:
            lifecycle = TrackLifecycle.LOST
        else:
            lifecycle = current.lifecycle
        state.contract = replace(current, missed_count=missed, lifecycle=lifecycle)
        return state.contract

    def reset(self) -> None:
        self._tracks.clear()
        self._detection_to_track.clear()
        self._next_id = 1
