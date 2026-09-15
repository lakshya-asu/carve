"""What the depth camera says about whatever is on the belt, with no product knowledge.

    depth_geometry             ray per pixel, RANSAC belt plane, the missing-depth threshold
    segmentation               colour and edge segmenters, and mask scoring
    staged_segmenter           depth proposes, appearance refines, colour confirms
    pose_estimation            a mask and a depth image to a planar pose
    centre_of_gravity          outline centre and volume-weighted column centroid
    learned_centre_of_gravity  a learned offset on top of the column centroid
    tracking                   a pose carried forward in belt coordinates

A module that has to know the product is a pork leg belongs in that application's `perception/`.
"""
