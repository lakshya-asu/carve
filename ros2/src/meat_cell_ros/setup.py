"""Install the grasp pipeline nodes, launch files and per-arm configs."""

from glob import glob

from setuptools import setup

PACKAGE = "meat_cell_ros"

setup(
    name=PACKAGE,
    version="0.1.0",
    packages=[PACKAGE],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{PACKAGE}"]),
        (f"share/{PACKAGE}", ["package.xml", "README.md"]),
        (f"share/{PACKAGE}/launch", glob("launch/*.launch.py")),
        (f"share/{PACKAGE}/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Lakshya Jain",
    maintainer_email="jainlakshya04@gmail.com",
    description="Grasp pipeline nodes for the pork leg cell.",
    license="Proprietary",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "belt_state_node = meat_cell_ros.belt_state_node:main",
            "grasp_policy_node = meat_cell_ros.grasp_policy_node:main",
            "grasp_executor_node = meat_cell_ros.grasp_executor_node:main",
        ],
    },
)
