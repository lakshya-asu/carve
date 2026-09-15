"""Where the product will be when the gripper gets there.

The model
---------
A product carried on a belt is not a free body doing something a filter has to
guess at. It is stuck to a surface whose displacement is measured directly by an
encoder. Writing the state in belt coordinates rather than world coordinates
makes that structure explicit:

    x_belt(t) = x_world(t) - s(t)

where s is belt travel from the encoder. If the product does not slip, x_belt is
a **constant**, and every observation is an independent measurement of the same
number. Averaging n of them drops the position variance by n, and prediction to
any future time is exact bookkeeping rather than extrapolation:

    x_world(t_future) = x_belt + s(t_last) + v_belt * (t_future - t_last)

Slip does not break the model, it becomes a term in it. Fitting a line to
x_belt against time gives a slope that is zero for a carried product and
non-zero for a sliding one, so the same fit both predicts and diagnoses. That
slope is reported as `slip_mps` and is worth watching in the field: on a wet
belt it is the first thing to move.

Why not differentiate the vision
--------------------------------
Two poses and a subtraction gives a velocity with standard deviation
sqrt(2) * sigma_position / dt. With the measured 0.12 mm position error and 30
frames per second that is 5.1 mm/s, and over the 0.5 s of belt travel between
the camera and the pick that alone is 2.5 mm of prediction error, against a 2 mm
bound. The encoder measures the same quantity without differentiating anything.
Vision supplies position, the encoder supplies velocity, and neither substitutes
for the other. `finite_difference_velocity` and `optical_flow_velocity` are here
so that claim stays measured rather than asserted.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from robotics.core.contracts import Frame, Observation, PieceEstimate, Pose2D, wrap_axis_angle
from robotics.core.frames import CameraPose, Intrinsics, pixel_to_plane

logger = logging.getLogger(__name__)

# Observations kept for the belt-frame fit. At 30 frames per second this is 0.4
# seconds of history, which is long enough for the slip slope to be meaningful
# and short enough that a real slip event is not averaged away by old data.
TRACK_HISTORY = 12

# Below this many observations the slip slope is not estimated: two points fit a
# line exactly and would report the measurement noise as slip.
MIN_SAMPLES_FOR_SLIP = 4


@dataclass(frozen=True)
class TrackState:
    """What the tracker believes about one product.

    Attributes:
        x_belt_m: Position along the belt axis in belt coordinates, metres.
        y_m: Cross-belt position, metres. The belt does not move in y.
        yaw_rad: Product heading, folded to (-pi/2, pi/2].
        slip_mps: Fitted drift of the product relative to the belt. Zero for a
            carried product; a persistent non-zero value means it is sliding.
        last_stamp_s: Simulation time of the most recent observation.
        last_travel_m: Belt encoder reading at that time.
        belt_speed_mps: Belt speed at that time.
        samples: How many observations back the estimate.
        residual_m: Root mean square of the fit residual along the belt axis, a
            direct measure of how well the constant-in-belt-frame model holds.
    """

    x_belt_m: float
    y_m: float
    yaw_rad: float
    slip_mps: float
    last_stamp_s: float
    last_travel_m: float
    belt_speed_mps: float
    samples: int
    residual_m: float


@dataclass
class BeltTracker:
    """Fuses vision position with encoder velocity in belt coordinates.

    Feed it a `PieceEstimate` and the `Observation` it came from. Ask it where
    the product will be at any time with `predict`.
    """

    history: int = TRACK_HISTORY
    _stamps: deque[float] = field(default_factory=lambda: deque(maxlen=TRACK_HISTORY), repr=False)
    _x_belt: deque[float] = field(default_factory=lambda: deque(maxlen=TRACK_HISTORY), repr=False)
    _y: deque[float] = field(default_factory=lambda: deque(maxlen=TRACK_HISTORY), repr=False)
    _yaw: deque[float] = field(default_factory=lambda: deque(maxlen=TRACK_HISTORY), repr=False)
    _last: Observation | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.history < MIN_SAMPLES_FOR_SLIP:
            raise ValueError(f"history must hold at least {MIN_SAMPLES_FOR_SLIP} samples, got {self.history}")
        # Rebuilt rather than cleared: a deque's maxlen is fixed at construction,
        # and the field defaults are built from the module constant before
        # `history` is known.
        self._stamps = deque(maxlen=self.history)
        self._x_belt = deque(maxlen=self.history)
        self._y = deque(maxlen=self.history)
        self._yaw = deque(maxlen=self.history)

    def reset(self) -> None:
        """Forget everything. Call between products, never within one."""
        self.__post_init__()
        self._last = None

    def update(self, estimate: PieceEstimate, observation: Observation) -> None:
        """Fold one vision estimate into the track.

        Args:
            estimate: Product pose in the world frame.
            observation: The sensor record the estimate was computed from. Its
                encoder reading must belong to the same instant as the image,
                which is why both carry a stamp and the stamps are checked.

        Raises:
            ValueError: If the pose is not in the world frame, or if the pose
                and the observation describe different instants. A pose paired
                with an encoder reading from a different moment is the seam
                defect this check exists to catch: at 300 mm/s one frame of
                skew is 10 mm.
        """
        estimate.pose.in_frame(Frame.WORLD)
        if abs(estimate.pose.stamp_s - observation.stamp_s) > 1e-9:
            raise ValueError(
                f"pose is stamped {estimate.pose.stamp_s} s and the observation {observation.stamp_s} s; "
                "they must describe the same instant"
            )
        self._stamps.append(observation.stamp_s)
        self._x_belt.append(estimate.pose.x_m - observation.belt_travel_m)
        self._y.append(estimate.pose.y_m)
        self._yaw.append(estimate.pose.yaw_rad)
        self._last = observation

    @property
    def state(self) -> TrackState:
        """Current belief, refitted from the history.

        Raises:
            RuntimeError: If no observation has been folded in yet.
        """
        if self._last is None or not self._stamps:
            raise RuntimeError("tracker has no observations")
        stamps = np.fromiter(self._stamps, dtype=float)
        x_belt = np.fromiter(self._x_belt, dtype=float)
        slip = 0.0
        residual = 0.0
        if stamps.size >= MIN_SAMPLES_FOR_SLIP and np.ptp(stamps) > 0:
            centred_t = stamps - stamps.mean()
            slip = float(centred_t @ (x_belt - x_belt.mean()) / (centred_t @ centred_t))
            fitted = x_belt.mean() + slip * centred_t
            residual = float(np.sqrt(np.mean((x_belt - fitted) ** 2)))
            x_at_last = float(x_belt.mean() + slip * (stamps[-1] - stamps.mean()))
        else:
            x_at_last = float(x_belt.mean())
        return TrackState(
            x_belt_m=x_at_last,
            y_m=float(np.mean(self._y)),
            yaw_rad=_circular_axis_mean(np.fromiter(self._yaw, dtype=float)),
            slip_mps=slip,
            last_stamp_s=float(stamps[-1]),
            last_travel_m=self._last.belt_travel_m,
            belt_speed_mps=self._last.belt_speed_mps,
            samples=int(stamps.size),
            residual_m=residual,
        )

    def predict(self, at_time_s: float) -> Pose2D:
        """Where the product will be at `at_time_s`, in the world frame.

        The belt is assumed to hold its current speed over the horizon, which is
        true for a line running at setpoint and false during a start or a stop.
        `TrackState.belt_speed_mps` is the number to guard that assumption with.
        """
        state = self.state
        horizon = at_time_s - state.last_stamp_s
        travel = state.last_travel_m + state.belt_speed_mps * horizon
        return Pose2D(
            x_m=state.x_belt_m + state.slip_mps * horizon + travel,
            y_m=state.y_m,
            yaw_rad=state.yaw_rad,
            frame=Frame.WORLD,
            stamp_s=at_time_s,
        )


def _circular_axis_mean(angles_rad: np.ndarray) -> float:
    """Mean of undirected axis angles.

    Averaging +89 and -89 degrees arithmetically gives 0, which is square to
    both. Doubling the angles maps the half-turn period onto a full turn, where
    the vector mean is well defined, and halving the result brings it back.
    """
    doubled = 2.0 * angles_rad
    return wrap_axis_angle(0.5 * float(np.arctan2(np.sin(doubled).mean(), np.cos(doubled).mean())))


def finite_difference_velocity(earlier: PieceEstimate, later: PieceEstimate) -> tuple[np.ndarray, float]:
    """Product velocity from two vision estimates, and the horizon it spans.

    The baseline the encoder is measured against. Its noise is
    sqrt(2) * sigma_position / dt, so it improves with a longer baseline and a
    longer baseline is exactly what a moving product does not give you.

    Returns:
        ((vx, vy) in metres per second, the time between the estimates).

    Raises:
        ValueError: If the two estimates share a timestamp.
    """
    dt = later.pose.stamp_s - earlier.pose.stamp_s
    if dt <= 0:
        raise ValueError(f"estimates must be ordered in time, got dt={dt}")
    return (later.pose.xy_m - earlier.pose.xy_m) / dt, dt


def optical_flow_velocity(
    earlier_rgb: np.ndarray,
    later_rgb: np.ndarray,
    mask: np.ndarray,
    dt_s: float,
    intrinsics: Intrinsics,
    camera: CameraPose,
    surface_z_m: float,
) -> np.ndarray:
    """Product velocity from dense optical flow over the masked region.

    Flow is measured in pixels and converted to metres by moving each pixel by
    its flow vector and back-projecting both ends onto the product's surface
    plane. Doing the conversion per pixel rather than with one scale factor
    matters off-axis, where a pixel spans more ground on one side of the product
    than the other.

    Unlike a centroid difference this uses the product's surface texture, so it
    still reports motion when the silhouette is ambiguous, which is the case a
    near-square product creates. It cannot beat the encoder on a carried
    product, because it is still a difference of two noisy positions over one
    frame interval, but it measures the product rather than the belt and so it
    sees slip that the encoder cannot.

    Args:
        earlier_rgb: (H, W, 3) uint8 frame at t.
        later_rgb: (H, W, 3) uint8 frame at t + dt.
        mask: Product silhouette in the earlier frame.
        dt_s: Interval between the frames.
        intrinsics: Camera model for both frames.
        camera: Camera pose for both frames.
        surface_z_m: World height of the surface the flow is happening on.

    Returns:
        (vx, vy) in metres per second, in the world frame.

    Raises:
        ValueError: If dt is not positive or the mask holds no pixels.
    """
    import cv2

    if dt_s <= 0:
        raise ValueError(f"dt must be positive, got {dt_s}")
    if not mask.any():
        raise ValueError("mask is empty")
    # Farneback parameters, positionally as OpenCV declares them: pyramid scale
    # 0.5, 3 levels, 21 px window, 3 iterations, 5 px polynomial neighbourhood,
    # sigma 1.2, no flags. The 21 px window is a little over one product
    # thickness at this cell's scale, which is the span over which the surface
    # texture stays coherent between frames.
    flow = cv2.calcOpticalFlowFarneback(  # type: ignore[call-overload]
        cv2.cvtColor(earlier_rgb, cv2.COLOR_RGB2GRAY),
        cv2.cvtColor(later_rgb, cv2.COLOR_RGB2GRAY),
        None,
        0.5,
        3,
        21,
        3,
        5,
        1.2,
        0,
    )
    rows, cols = np.nonzero(mask)
    start = np.array(
        [
            pixel_to_plane(intrinsics, camera, float(u), float(v), surface_z_m)[:2]
            for u, v in zip(cols, rows, strict=True)
        ]
    )
    moved = np.array(
        [
            pixel_to_plane(intrinsics, camera, float(u + flow[v, u, 0]), float(v + flow[v, u, 1]), surface_z_m)[:2]
            for u, v in zip(cols, rows, strict=True)
        ]
    )
    return np.asarray((moved - start).mean(axis=0) / dt_s, dtype=float)


def prediction_error_m(predicted: Pose2D, truth: Pose2D) -> float:
    """Planar distance between a predicted pose and the truth, in metres."""
    predicted.in_frame(truth.frame)
    return float(math.hypot(predicted.x_m - truth.x_m, predicted.y_m - truth.y_m))
