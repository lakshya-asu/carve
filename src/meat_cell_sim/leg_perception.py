"""From a segmented leg to its shape in belt coordinates, for any grasp policy to read.

`perceive_leg` turns a mask, a depth frame, the belt plane and the encoder reading into a
`LegPerception`: the leg's long axis, which end is the trotter, and a width and height profile
along it. Nothing here reads the simulator's true pose; the existing grasp skills do, which is why
they cannot run from the camera.

Which end is the trotter: the centre of gravity sits in the ham, and the outline's centre is pulled
toward the thin end by about 40 mm on every leg measured (`experiments/2026-09-15-centre-of-gravity.md`),
so the axis points from the centre of gravity toward the outline centre.

Kept apart from `grasp_policy.py` because this needs the camera stack, and the policies must run in
a ROS 2 node that has only numpy.
"""

from __future__ import annotations

import math

import numpy as np

from meat_cell_sim.centre_of_gravity import column_centroid, silhouette_centroid
from meat_cell_sim.evidence import MIN_VALID_DEPTH_M, Plane, ray_directions
from meat_cell_sim.grasp_action import LegPerception
from meat_cell_sim.sensing import CameraFrameData

STATIONS = 40
# Outline extent from these percentiles of each cross section, not min and max, so a few edge
# pixels with wrong depth do not widen the leg.
EDGE_PERCENTILES = (2.0, 98.0)


def perceive_leg(
    frame: CameraFrameData, mask: np.ndarray, plane: Plane, belt_travel_m: float, stations: int = STATIONS
) -> LegPerception:
    """Describe the segmented leg in belt coordinates.

    Raises:
        ValueError: If the mask has no usable depth or does not stand above the belt.
    """
    columns = column_centroid(frame, mask, plane)
    outline = silhouette_centroid(frame, mask, plane)
    directions = ray_directions(frame)[mask].astype(np.float64)
    depth_m = frame.depth_m[mask].astype(np.float64)
    usable = depth_m > MIN_VALID_DEPTH_M
    points = frame.camera.position_m + directions[usable] * depth_m[usable, None]
    height_m = np.clip(plane.height_of(points), 0.0, None)
    feet = (points - height_m[:, None] * plane.normal)[:, :2]

    cog_xy = columns.position_m[:2]
    centred = feet - cog_xy
    _, _, right = np.linalg.svd(centred - centred.mean(axis=0), full_matrices=False)
    axis = right[0]
    if (outline.position_m[:2] - cog_xy) @ axis < 0.0:
        axis = -axis
    across = np.array([-axis[1], axis[0]])
    along_m, across_m = centred @ axis, centred @ across

    ham_end_m, trotter_end_m = float(along_m.min()), float(along_m.max())
    edges = np.linspace(ham_end_m, trotter_end_m, stations + 1)
    which = np.clip(np.digitize(along_m, edges) - 1, 0, stations - 1)
    centres_m = 0.5 * (edges[:-1] + edges[1:])
    widths, middles, tops = np.zeros(stations), np.zeros(stations), np.zeros(stations)
    for k in range(stations):
        in_section = which == k
        if in_section.sum() < 2:
            continue
        low, high = np.percentile(across_m[in_section], EDGE_PERCENTILES)
        widths[k], middles[k] = high - low, 0.5 * (low + high)
        tops[k] = np.percentile(height_m[in_section], EDGE_PERCENTILES[1])
    centreline_world = cog_xy + centres_m[:, None] * axis + middles[:, None] * across
    belt_shift = np.array([belt_travel_m, 0.0])
    cog_belt = columns.position_m - np.array([belt_travel_m, 0.0, 0.0])
    below_cog = columns.position_m - float(plane.height_of(columns.position_m)) * plane.normal
    return LegPerception(
        stamp_s=frame.stamp_s,
        belt_travel_m=belt_travel_m,
        belt_surface_z_m=float(below_cog[2]),
        centre_of_gravity_belt_m=cog_belt,
        outline_centre_belt_m=outline.position_m[:2] - belt_shift,
        axis_rad=math.atan2(axis[1], axis[0]),
        length_m=trotter_end_m - ham_end_m,
        volume_m3=columns.volume_m3,
        stations_m=centres_m - ham_end_m,
        centreline_belt_m=centreline_world - belt_shift,
        widths_m=widths,
        top_heights_m=tops,
        method="depth-height segmenter, column centroid",
    )
