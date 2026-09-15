# One leg as the camera and encoder saw it (meat_cell_sim.grasp_action.LegPerception).
# header.stamp: exposure time of the frame. header.frame_id: "belt".
# Belt coordinates: x along the belt minus belt_travel_m, y and z world, metres.

std_msgs/Header header

# Encoder travel at the exposure; world x = belt x + belt_travel_m.
float64 belt_travel_m
# Height of the belt surface under the leg, world z.
float64 belt_surface_z_m

geometry_msgs/Point centre_of_gravity
# z unused.
geometry_msgs/Point outline_centre

# World yaw of the long axis, pointing from the ham toward the trotter.
float64 axis_rad
float64 length_m
float64 volume_m3

# Cross sections along the axis, all of the same length K.
# Distance of each section from the ham end.
float64[] stations_m
# Middle of each section on the belt; z unused.
geometry_msgs/Point[] centreline
float64[] widths_m
# Highest seen surface in each section, above the belt.
float64[] top_heights_m

# Which segmenter and centre-of-gravity estimate produced this.
string method
