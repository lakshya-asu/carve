"""The learned grasp policy: same input and output as the deterministic rule, numpy inference.

Pre-registered in `experiments/2026-09-15-intercept-grasp.md` (policy B). It does not start from
nothing: it takes the deterministic shank grasp (`ShankGraspRule`) as its base and predicts only
how far to move it along and across the leg, how far to turn the jaw line, and which tool tilt to
use. With a zero output it is the deterministic rule exactly, so a badly trained model degrades
toward the baseline rather than toward anywhere.

Its input is only what `LegPerception` carries, the 40-section width, height and centreline profile
plus the leg's scalars and the belt's speed and acceleration, so the ROS 2 message is enough to run
it. Inference is a small multilayer perceptron in numpy, loaded from an `.npz` exported after
training, because the ROS 2 Python has no torch.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from applications.pork_leg_alignment.grasping.leg_perception import LegPerception
from applications.pork_leg_alignment.grasping.shank_grasp_rule import SPARE_OPENING_M, ShankGraspRule
from robotics.core.belt_state import BeltState
from robotics.core.grasp_action import GraspAction

TILT_CLASSES_RAD = (0.0, math.radians(15.0), math.radians(30.0))
PROFILE_STATIONS = 40
FEATURES = 3 * PROFILE_STATIONS + 6
# Scales that bring each feature near 1.
WIDTH_SCALE_M, HEIGHT_SCALE_M, LATERAL_SCALE_M = 0.25, 0.25, 0.05


def grasp_features(leg: LegPerception, belt: BeltState | None) -> np.ndarray:
    """The policy's input vector (126,): per-section width, top height and centreline offset, then six scalars.

    Raises:
        ValueError: If the perception does not have `PROFILE_STATIONS` cross sections.
    """
    if leg.stations_m.size != PROFILE_STATIONS:
        raise ValueError(f"the policy reads {PROFILE_STATIONS} cross sections, got {leg.stations_m.size}")
    axis = np.array([math.cos(leg.axis_rad), math.sin(leg.axis_rad)])
    across = np.array([-axis[1], axis[0]])
    cog = leg.centre_of_gravity_belt_m[:2]
    lateral = (leg.centreline_belt_m - cog) @ across
    ham_end = leg.centreline_belt_m[0] - leg.stations_m[0] * axis
    scalars = [
        leg.length_m,
        1000.0 * leg.volume_m3 / 10.0,
        float((cog - ham_end) @ axis) / leg.length_m,
        float((leg.outline_centre_belt_m - cog) @ axis) / LATERAL_SCALE_M,
        belt.speed_mps if belt is not None else 0.0,
        belt.acceleration_mps2 if belt is not None else 0.0,
    ]
    return np.concatenate(
        [leg.widths_m / WIDTH_SCALE_M, leg.top_heights_m / HEIGHT_SCALE_M, lateral / LATERAL_SCALE_M, scalars]
    ).astype(np.float32)


class LearnedGraspPolicy:
    """Deterministic shank grasp moved by a learned offset, with a learned tool tilt."""

    def __init__(self, weights: Path, can_tilt: bool = True, base: ShankGraspRule | None = None) -> None:
        """Load exported weights: arrays w0, b0, w1, b1, ... applied as relu layers, the last one linear.

        Args:
            weights: `.npz` written by the training script.
            can_tilt: False for an arm that cannot lean its tool; the tilt output is then ignored.
            base: The rule whose grasp the offsets move; the default rule if None.
        """
        with np.load(weights) as saved:
            count = len([key for key in saved.files if key.startswith("w")])
            self.layers = [(saved[f"w{i}"], saved[f"b{i}"]) for i in range(count)]
        if self.layers[0][0].shape[1] != FEATURES or self.layers[-1][0].shape[0] != 3 + len(TILT_CLASSES_RAD):
            raise ValueError("weights do not match the policy's input or output size")
        self.name = f"learned-{weights.stem}"
        self.can_tilt = can_tilt
        self.base = base or ShankGraspRule()
        self.belt: BeltState | None = None

    def decide(self, leg: LegPerception) -> GraspAction:
        """The grasp for this leg, using the belt state last given in `self.belt`.

        Raises:
            GraspRefusedError: If the base rule refuses the leg.
        """
        base = self.base.decide(leg)
        hidden = grasp_features(leg, self.belt)
        for index, (weight, bias) in enumerate(self.layers):
            hidden = weight @ hidden + bias
            if index < len(self.layers) - 1:
                hidden = np.maximum(hidden, 0.0)
        along_m, across_m, turn_rad = (float(v) for v in hidden[:3])
        tilt_rad = TILT_CLASSES_RAD[int(np.argmax(hidden[3:]))] if self.can_tilt else 0.0

        axis = np.array([math.cos(leg.axis_rad), math.sin(leg.axis_rad)])
        across = np.array([-axis[1], axis[0]])
        point = base.grasp_point_belt_m.copy()
        point[:2] += along_m * axis + across_m * across
        station_m = float((point[:2] - (leg.centreline_belt_m[0] - leg.stations_m[0] * axis)) @ axis)
        width_m = float(np.interp(station_m, leg.stations_m, leg.widths_m))
        return GraspAction(
            stamp_s=leg.stamp_s,
            policy=self.name,
            grasp_point_belt_m=point,
            finger_axis_rad=base.finger_axis_rad + turn_rad,
            tool_tilt_rad=tilt_rad,
            opening_m=width_m + SPARE_OPENING_M,
            approach_height_m=base.approach_height_m,
            close_s=base.close_s,
        )
