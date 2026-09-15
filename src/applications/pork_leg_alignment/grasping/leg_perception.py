"""What a pork-leg grasp policy reads: one leg as the camera and encoder saw it.

Built by `perception/perceive_leg.py` from a leg mask and a depth frame, carried over ROS 2 as
`meat_cell_msgs/LegPerception`, and read by every policy in `grasping/`. Numpy only.

Belt coordinates: x along the belt minus the belt's travel at the time of the reading, so a point
on a leg that does not slip keeps its belt x; y and z are world y and z.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LegPerception:
    """One leg as the camera and encoder saw it, in belt coordinates.

    Attributes:
        stamp_s: Exposure time of the frame.
        belt_travel_m: Encoder travel at `stamp_s`; world x = belt x + travel.
        belt_surface_z_m: Height of the belt surface under the leg, world z.
        centre_of_gravity_belt_m: (3,) column centroid, or whichever estimate the cell uses.
        outline_centre_belt_m: (2,) centre of the leg's outline on the belt.
        axis_rad: World yaw of the leg's long axis, pointing from the ham toward the trotter.
        length_m: Extent along the axis.
        volume_m3: Volume under the seen surface.
        stations_m: (K,) distance along the axis from the ham end, one per cross section.
        centreline_belt_m: (K, 2) middle of each cross section on the belt.
        widths_m: (K,) width of each cross section across the axis.
        top_heights_m: (K,) highest seen surface in each cross section, above the belt.
        method: Which segmenter and centre-of-gravity estimate produced this.
    """

    stamp_s: float
    belt_travel_m: float
    belt_surface_z_m: float
    centre_of_gravity_belt_m: np.ndarray
    outline_centre_belt_m: np.ndarray
    axis_rad: float
    length_m: float
    volume_m3: float
    stations_m: np.ndarray
    centreline_belt_m: np.ndarray
    widths_m: np.ndarray
    top_heights_m: np.ndarray
    method: str

    def __post_init__(self) -> None:
        stations = self.stations_m.shape[0]
        shapes = (self.centreline_belt_m.shape, self.widths_m.shape, self.top_heights_m.shape)
        if shapes != ((stations, 2), (stations,), (stations,)):
            raise ValueError(f"cross-section arrays disagree in length: {stations} stations, shapes {shapes}")
        if self.centre_of_gravity_belt_m.shape != (3,) or self.outline_centre_belt_m.shape != (2,):
            raise ValueError("centre of gravity must be (3,) and outline centre (2,)")
        if self.length_m <= 0.0:
            raise ValueError(f"length must be positive, got {self.length_m}")
