"""Pork-leg grasp skills, written against `robotics.core.skill_library`.

The contracts are the library's. The implementations act on this cell's simulated `Cell` and read
the leg model, which is why they live in the application. A skill with no product knowledge goes in
`robotics/skills/`, which is created with the first such skill.
"""

from applications.pork_leg_alignment.skills.leg_estimate import (
    EstimateLegFromCamera,
    EstimateLegFromGroundTruth,
    LegEstimate,
)
from applications.pork_leg_alignment.skills.rotate_on_belt import Alignment, PickAndPlace, RotateOnBelt
from applications.pork_leg_alignment.skills.shank_grasp import AcquireShank, SelectShankGrasp, ShankGrasp
from applications.pork_leg_alignment.skills.trotter_grasp import AcquireTrotterEnd, SelectTrotterEndGrasp, TrotterGrasp

__all__ = [
    "AcquireShank",
    "AcquireTrotterEnd",
    "Alignment",
    "EstimateLegFromCamera",
    "EstimateLegFromGroundTruth",
    "LegEstimate",
    "PickAndPlace",
    "RotateOnBelt",
    "SelectShankGrasp",
    "SelectTrotterEndGrasp",
    "ShankGrasp",
    "TrotterGrasp",
]
