"""Simulation of the meat cell: belt, arm, gripper, product, and its perception.

Build order and the gate for each subsystem are in
`library/topics/meat-cell-architecture.md`. Modules are added in that order and
nothing advances until its gate passes with committed tests.

    scene       the cell, the arm, the gripper, the product
    contracts   the typed values that cross subsystem boundaries
    sensing     timestamped sensor records, and the oracle kept apart from them
    frames      camera geometry: pixels to metres, and metres between frames
    perception  a mask and a depth image to a pose
    tracking    that pose forward to the instant the gripper arrives
"""
