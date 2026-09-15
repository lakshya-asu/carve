"""The pork-leg alignment cell: legs ride a belt to a saw that takes the trotter off at the hock.

    sim          this line in MuJoCo: scene, stepping, sensing, the leg model, the saw and hold-down
    perception   leg segmentation, geometric and learned, and the leg's shape for a grasp policy
    grasping     numpy-only grasp policies: the shank rule and the learned policy
    skills       shank and trotter grasps written against `robotics.core.skill_library`

Everything here may import `robotics`; nothing in `robotics` imports this package. Build order and
the gate for each subsystem are in `library/topics/meat-cell-architecture.md`.
"""
