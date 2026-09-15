"""The types and planning every layer shares. Numpy and the standard library only.

Nothing here imports MuJoCo, OpenCV or torch, so the ROS 2 nodes in `ros2/` run these modules
unchanged under the system Python, and nothing here names a product or a customer.
`tests/test_layering.py` checks both import rules.
"""
