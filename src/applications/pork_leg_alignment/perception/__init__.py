"""Perception choices for pork legs, built on `robotics.perception`.

`leg_segmentation` finds a leg by its height above the empty belt inside this cell's belt region,
`learned_leg_segmentation` is the U-Net measured against it, and `perceive_leg` turns a leg mask into
the `LegPerception` a grasp policy reads.
"""
