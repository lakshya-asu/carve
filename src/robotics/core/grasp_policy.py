"""The interface every grasp policy implements: a perceived product in, a grasp action out.

What a policy reads depends on the product, so the application supplies that type (a pork leg's
cross-section profile is `applications.pork_leg_alignment.grasping.LegPerception`) and this module
names none. What it returns is always a `GraspAction`, which the intercept planner and every arm's
executor already understand. Numpy only, so a policy runs in the simulator and inside a ROS 2 node.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from robotics.core.grasp_action import GraspAction

PerceptionT_contra = TypeVar("PerceptionT_contra", contravariant=True)


class GraspRefusedError(ValueError):
    """The policy will not grasp this product; the message says why."""


class GraspPolicy(Protocol[PerceptionT_contra]):
    """Anything that decides a grasp from a perceived product: a deterministic rule or a learned model."""

    name: str

    def decide(self, perceived: PerceptionT_contra, /) -> GraspAction:
        """Return the grasp, or raise `GraspRefusedError`."""
        ...
