"""Install this cell's ROS 2 adapters: the simulated cell bridge, SR-20iA IK, and the simulation launch."""

from glob import glob

from setuptools import setup

PACKAGE = "pork_leg_cell_ros"

setup(
    name=PACKAGE,
    version="0.1.0",
    packages=[PACKAGE],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{PACKAGE}"]),
        (f"share/{PACKAGE}", ["package.xml"]),
        (f"share/{PACKAGE}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Lakshya Jain",
    maintainer_email="jainlakshya04@gmail.com",
    description="ROS 2 adapters for the pork leg alignment cell.",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "mujoco_bridge_node = pork_leg_cell_ros.mujoco_bridge_node:main",
            "scara_ik_node = pork_leg_cell_ros.scara_ik_node:main",
        ],
    },
)
