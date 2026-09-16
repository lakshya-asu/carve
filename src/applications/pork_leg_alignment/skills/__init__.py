"""This plant's grasp and alignment skills, written against `robotics.core.skill_library`.

The contracts are the library's. The implementations act on this cell's simulated `Cell` and read
the product models, which is why they live in the application. A skill with no product knowledge
goes in `robotics/skills/`, which is created with the first such skill. The loin puller infeed
reuses the leg's grasp and turn skills with its own estimate, grasp station and alignment target
(`loin_estimate.py`, `loin_infeed.py`).
"""

from applications.pork_leg_alignment.skills.leg_estimate import (
    EstimateLegFromCamera,
    EstimateLegFromGroundTruth,
    LegEstimate,
)
from applications.pork_leg_alignment.skills.loin_estimate import EstimateLoinFromGroundTruth, LoinEstimate
from applications.pork_leg_alignment.skills.loin_infeed import INFEED_TARGET, InfeedTarget, centre_of_gravity_station
from applications.pork_leg_alignment.skills.rotate_on_belt import (
    SAW_TARGET,
    Alignment,
    AlignmentTarget,
    PickAndPlace,
    RotateOnBelt,
    SawTarget,
)
from applications.pork_leg_alignment.skills.shank_grasp import AcquireShank, SelectShankGrasp, ShankGrasp, shank_station
from applications.pork_leg_alignment.skills.trotter_grasp import AcquireTrotterEnd, SelectTrotterEndGrasp, TrotterGrasp

__all__ = [
    "INFEED_TARGET",
    "SAW_TARGET",
    "AcquireShank",
    "AcquireTrotterEnd",
    "Alignment",
    "AlignmentTarget",
    "EstimateLegFromCamera",
    "EstimateLegFromGroundTruth",
    "EstimateLoinFromGroundTruth",
    "InfeedTarget",
    "LegEstimate",
    "LoinEstimate",
    "PickAndPlace",
    "RotateOnBelt",
    "SawTarget",
    "SelectShankGrasp",
    "SelectTrotterEndGrasp",
    "ShankGrasp",
    "TrotterGrasp",
    "centre_of_gravity_station",
    "shank_station",
]
