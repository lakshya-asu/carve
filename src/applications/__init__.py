"""One package per customer cell: what that cell is trying to do, built from `robotics`.

An application owns everything specific to its line: the product model, the simulated cell it runs
in, the perception choices and grasp rules tuned to that product, and its skills. `robotics` never
imports from here, and one application never imports another.
"""
