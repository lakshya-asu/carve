# Where and how to take hold of a leg, from any policy, for any arm
# (meat_cell_sim.grasp_action.GraspAction). No joint values: each arm's executor turns this into
# motion with its own IK, or refuses.
# header.stamp: exposure time of the perception it was decided from. header.frame_id: "belt".

std_msgs/Header header

# Which policy decided it, for the A/B record: "shank-at-fraction", "learned-<checkpoint>", ...
string policy

# Encoder travel at header.stamp; world x of the grasp point = grasp_point.x + belt_travel_m.
float64 belt_travel_m

# Point midway between the closed jaws, belt coordinates (x along the belt minus travel, y and z world), metres.
geometry_msgs/Point grasp_point

# World yaw of the line the jaws close along.
float64 finger_axis_rad

# Lean of the tool from pointing straight down, about the finger axis. 0 is vertical; an arm whose
# tool cannot lean refuses anything else.
float64 tool_tilt_rad

float64 opening_m
float64 approach_height_m
# Time for the jaws to close while the tool follows the belt.
float64 close_s
