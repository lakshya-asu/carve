"""Belt state estimator and intercept planner from the conveyor tracking note.

Companion to ``library/topics/conveyor-tracking-and-visual-servoing.md``. One-dimensional
along the belt axis: positions in meters, time in seconds, the belt frame origin at the
trigger line and x increasing downstream. The arm's motion model is a rest-to-rest
trapezoid with a velocity-matching margin, a conservative stand-in for a jerk-limited
profile such as Ruckig's.

Run ``python snippets/conveyor_tracking.py`` or ``pytest snippets/conveyor_tracking.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class BeltEstimator:
    """Kalman filter on belt travel and speed driven by encoder counts.

    State is (s, v): meters travelled past the trigger line and belt speed. The process
    model is constant velocity with acceleration noise ``accel_std``; the measurement is
    the encoder count times ``m_per_count`` with quantisation noise of one count.
    """

    m_per_count: float
    accel_std: float = 0.5  # m/s^2, how fast the belt can change speed between updates
    s: float = 0.0
    v: float = 0.0
    P: np.ndarray | None = None  # (2, 2) covariance
    t: float | None = None

    def update(self, count: int, t: float) -> tuple[float, float]:
        """Fold one encoder reading at controller time ``t`` into the state. Returns (s, v)."""
        z = count * self.m_per_count
        if self.t is None:
            self.s, self.v, self.P, self.t = z, 0.0, np.diag([self.m_per_count**2, 1.0]), t
            return self.s, self.v
        dt = t - self.t
        F = np.array([[1.0, dt], [0.0, 1.0]])
        G = np.array([0.5 * dt**2, dt])
        Q = np.outer(G, G) * self.accel_std**2
        x = F @ np.array([self.s, self.v])
        P = F @ self.P @ F.T + Q
        H = np.array([[1.0, 0.0]])
        R = (self.m_per_count / np.sqrt(12.0)) ** 2  # uniform quantisation over one count
        K = P @ H.T / (H @ P @ H.T + R)
        x = x + (K * (z - x[0])).ravel()
        self.P = (np.eye(2) - K @ H) @ P
        self.s, self.v, self.t = float(x[0]), float(x[1]), t
        return self.s, self.v

    def travel_at(self, t: float) -> float:
        """Belt travel at ``t`` under the constant-velocity model, forwards or backwards in time."""
        if self.t is None:
            raise ValueError("no encoder reading yet")
        return self.s + self.v * (t - self.t)


def stamp_object(belt: BeltEstimator, x_img_m: float, t_exposure: float) -> float:
    """Return the object's fixed belt-frame coordinate from an image taken at ``t_exposure``.

    ``x_img_m`` is the object position in the camera's world-fixed frame along the belt axis.
    Stamping with the belt travel at exposure time, not at the time the pose arrives, is the
    whole of latency compensation for a rigidly carried object.
    """
    return x_img_m - belt.travel_at(t_exposure)


def object_position(belt: BeltEstimator, x_belt_m: float, t: float) -> float:
    """World-fixed position along the belt axis at time ``t`` of an object stamped at ``x_belt_m``."""
    return x_belt_m + belt.travel_at(t)


def move_time(dist_m: float, v_max: float, a_max: float, v_match: float) -> float:
    """Rest-to-rest trapezoid time over ``dist_m`` plus the ramp to match ``v_match``.

    Conservative: a jerk-limited planner that ends at belt speed instead of rest is faster.
    """
    d = abs(dist_m)
    if d <= v_max**2 / a_max:
        t = 2.0 * np.sqrt(d / a_max)
    else:
        t = d / v_max + v_max / a_max
    return float(t + abs(v_match) / a_max)


def plan_intercept(
    belt: BeltEstimator,
    x_belt_m: float,
    x_tcp_m: float,
    t_now: float,
    window_m: tuple[float, float],
    v_max: float,
    a_max: float,
    dwell_s: float,
    latency_s: float = 0.0,
) -> tuple[float, float] | None:
    """Earliest meet time and world position for a tracked object, or None if it cannot be met.

    Fixed-point iteration: the object is where it will be when the arm arrives, and the arm
    takes ``move_time`` to get there after ``latency_s`` of command lag. The pick must start
    inside ``window_m`` and the object must still be inside it after ``dwell_s`` of grasp
    closure, since the arm tracks the belt while the gripper closes.
    """
    t_meet = t_now + latency_s
    for _ in range(50):
        x_meet = object_position(belt, x_belt_m, t_meet)
        t_next = t_now + latency_s + move_time(x_meet - x_tcp_m, v_max, a_max, belt.v)
        if abs(t_next - t_meet) < 1e-6:
            break
        t_meet = t_next
    x_meet = object_position(belt, x_belt_m, t_meet)
    x_release = object_position(belt, x_belt_m, t_meet + dwell_s)
    if x_meet < window_m[0]:  # arm is early: wait at the window entry
        t_meet = t_meet + (window_m[0] - x_meet) / belt.v
        x_meet, x_release = window_m[0], window_m[0] + belt.v * dwell_s
    if x_release > window_m[1]:
        return None
    return t_meet, x_meet


# --- checks ---------------------------------------------------------------------------


def _simulated_belt(v_true: float, m_per_count: float, rate_hz: float, n: int, seed: int = 0) -> BeltEstimator:
    rng = np.random.default_rng(seed)
    belt = BeltEstimator(m_per_count=m_per_count)
    for k in range(n):
        t = k / rate_hz + rng.normal(0.0, 2e-4)  # 0.2 ms timestamp jitter
        belt.update(int(np.floor(v_true * t / m_per_count)), t)
    return belt


def test_estimator_converges_to_belt_speed() -> None:
    """Speed within 5 mm/s and travel within 2 mm after 2 s of 0.1 mm counts at 500 Hz."""
    belt = _simulated_belt(v_true=0.3, m_per_count=1e-4, rate_hz=500.0, n=1000)
    assert abs(belt.v - 0.3) < 0.005
    assert abs(belt.travel_at(2.5) - 0.75) < 0.002


def test_exposure_stamp_beats_arrival_stamp() -> None:
    """Stamping at exposure time keeps 2 mm; stamping at pose arrival loses 75 mm at 0.3 m/s."""
    belt = _simulated_belt(v_true=0.3, m_per_count=1e-4, rate_hz=500.0, n=1000)
    t_exposure, processing_delay = 1.0, 0.25  # the pose arrives 250 ms after the shutter
    x_true_belt = 0.10
    x_img = x_true_belt + 0.3 * t_exposure
    good = stamp_object(belt, x_img, t_exposure)
    naive = stamp_object(belt, x_img, t_exposure + processing_delay)
    assert abs(good - x_true_belt) < 0.002
    assert abs(naive - x_true_belt) > 0.07  # 0.3 m/s times 0.25 s = 75 mm of error


def test_intercept_meets_inside_window_and_fails_when_belt_outruns_arm() -> None:
    """Meet point lands in the window, latency delays it, and a slow arm returns None."""
    belt = _simulated_belt(v_true=0.3, m_per_count=1e-4, rate_hz=500.0, n=1000)
    t_now = belt.t or 0.0
    x_belt = stamp_object(
        belt, object_position(belt, 0.0, t_now) + 0.4, t_now
    )  # belt coordinate 0.4 m: 1.0 m past the trigger line now
    plan = plan_intercept(
        belt, x_belt, x_tcp_m=1.2, t_now=t_now, window_m=(1.0, 1.6), v_max=1.5, a_max=5.0, dwell_s=0.15
    )
    assert plan is not None
    t_meet, x_meet = plan
    assert 1.0 <= x_meet <= 1.6 and t_meet > t_now
    assert abs(object_position(belt, x_belt, t_meet) - x_meet) < 1e-9
    late = plan_intercept(belt, x_belt, 1.2, t_now, (1.0, 1.6), v_max=1.5, a_max=5.0, dwell_s=0.15, latency_s=0.05)
    assert late is not None and late[0] > t_meet
    slow_arm = plan_intercept(belt, x_belt, 1.2, t_now, (1.0, 1.6), v_max=0.2, a_max=0.2, dwell_s=0.15)
    assert slow_arm is None


if __name__ == "__main__":
    test_estimator_converges_to_belt_speed()
    test_exposure_stamp_beats_arrival_stamp()
    test_intercept_meets_inside_window_and_fails_when_belt_outruns_arm()
    print("conveyor_tracking: 3 checks passed")
