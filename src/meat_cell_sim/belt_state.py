"""Belt travel, speed and acceleration from the encoder, and where the belt will be.

The intercept planner (`intercept.py`) needs the belt's travel over the half second or so the arm
takes to arrive. A constant-speed prediction is off by a * dt^2 / 2 when the belt changes speed:
12.5 mm for every 0.1 m/s^2 over a 0.5 s lead (plan section 10.1). This fits travel as a quadratic
in time over a short window of encoder readings, so the prediction carries the acceleration the
encoder has already seen.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BeltState:
    """The belt at one instant, from the encoder.

    Attributes:
        stamp_s: Time of the newest reading the state was fitted to.
        travel_m: Belt travel at `stamp_s`, metres.
        speed_mps: Belt speed at `stamp_s`, metres per second, downstream positive.
        acceleration_mps2: Belt acceleration at `stamp_s`, metres per second squared.
    """

    stamp_s: float
    travel_m: float
    speed_mps: float
    acceleration_mps2: float

    def speed_at(self, t_s: float) -> float:
        """Predicted speed at `t_s`. The belt runs one way, so a braking belt stops at 0."""
        return max(self.speed_mps + self.acceleration_mps2 * (t_s - self.stamp_s), 0.0)

    def travel_at(self, t_s: float) -> float:
        """Predicted travel at `t_s`, holding still once a braking belt has stopped."""
        dt = t_s - self.stamp_s
        if self.acceleration_mps2 < 0.0 and self.speed_mps > 0.0:
            dt = min(dt, self.speed_mps / -self.acceleration_mps2)
        return self.travel_m + self.speed_mps * dt + 0.5 * self.acceleration_mps2 * dt**2

    def without_acceleration(self) -> BeltState:
        """The same state predicting at constant speed, for comparing the two predictions."""
        return BeltState(self.stamp_s, self.travel_m, self.speed_mps, 0.0)


class BeltStateEstimator:
    """Least-squares fit of travel = s + v t + a t^2 / 2 over the last `window_s` of encoder readings."""

    def __init__(self, window_s: float = 0.3, min_readings: int = 10) -> None:
        """Keep readings from the last `window_s`; report a state once `min_readings` are held."""
        if window_s <= 0.0 or min_readings < 3:
            raise ValueError("need a positive window and at least 3 readings to fit an acceleration")
        self.window_s = window_s
        self.min_readings = min_readings
        self._readings: deque[tuple[float, float]] = deque()

    def update(self, stamp_s: float, travel_m: float) -> BeltState | None:
        """Add one encoder reading; returns the fitted state, or None until enough readings are held.

        Raises:
            ValueError: If `stamp_s` is not later than the previous reading.
        """
        if self._readings and stamp_s <= self._readings[-1][0]:
            raise ValueError(f"encoder stamps must increase, got {stamp_s} after {self._readings[-1][0]}")
        self._readings.append((stamp_s, travel_m))
        while stamp_s - self._readings[0][0] > self.window_s:
            self._readings.popleft()
        if len(self._readings) < self.min_readings:
            return None
        readings = np.array(self._readings)
        # Time relative to the newest reading keeps the fit well conditioned and makes the
        # constant term the travel now.
        half_accel, speed, travel = np.polyfit(readings[:, 0] - stamp_s, readings[:, 1], 2)
        return BeltState(stamp_s, float(travel), float(speed), float(2.0 * half_accel))
