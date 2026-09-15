"""Grasp policies for pork legs. Numpy only, because the ROS 2 grasp policy node imports them.

`LegPerception` is what a policy reads, `ShankGraspRule` is the deterministic policy, and
`LearnedGraspPolicy` is the learned one A/B tested against it. Both implement
`robotics.core.grasp_policy.GraspPolicy`.
"""
