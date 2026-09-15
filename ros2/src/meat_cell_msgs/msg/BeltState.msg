# The belt at one instant, fitted from encoder readings (robotics.core.belt_state.BeltState).
# header.stamp: time of the newest encoder reading used. header.frame_id: "world".
# The belt runs along world +x; travel never decreases.

std_msgs/Header header
float64 travel_m
float64 speed_mps
float64 acceleration_mps2
