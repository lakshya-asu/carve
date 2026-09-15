"""General robotics code with no product or customer knowledge.

    core         numpy-only types and planning: coordinate frames, the skill contract and task
                 graph, belt state, intercept planning, the grasp action, the grasp policy
                 interface and the timed tool waypoints
    hardware     MuJoCo models of hardware any cell can be built from: arms and IK, grippers,
                 datasheet depth cameras
    perception   depth geometry, segmentation, pose, centre of gravity, tracking

Imports point down only. `hardware` and `perception` import `core` and never each other, and nothing
under `robotics` imports `applications`. `tests/test_layering.py` enforces this; `ARCHITECTURE.md`
at the repo root says what goes where.
"""
