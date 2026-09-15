"""The pork-leg line in MuJoCo: its belt, rails, saw, hold-down and product.

`scene` builds the model from a `CellConfig`, `cell` steps it (endless belt, saw checked every step),
`sensing` turns it into timestamped sensor records with ground truth kept apart, `product` models the
leg and the control slab, and `saw` and `hold_down` are the equipment at the cut. Arms, grippers and
depth cameras come from `robotics.hardware`.
"""
