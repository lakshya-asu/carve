from pathlib import Path
import xml.etree.ElementTree as ET

import yaml


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "ros2_ws" / "src" / "carve_moveit_config"
DEMO_PACKAGE = ROOT / "ros2_ws" / "src" / "carve_moveit_demo"
JOINTS = ["J1", "J2", "J3", "J4", "J5", "J6"]


def test_moveit_package_has_required_runtime_files() -> None:
    required = [
        "package.xml",
        "CMakeLists.txt",
        "robot/carve_m10id12.urdf.xacro",
        "config/carve_m10id12.srdf",
        "config/kinematics.yaml",
        "config/ompl_planning.yaml",
        "config/joint_limits.yaml",
        "config/moveit_controllers.yaml",
        "config/cell_collision_objects.yaml",
        "launch/isaac_moveit.launch.py",
        "scripts/publish_cell_scene.py",
    ]
    assert all((PACKAGE / item).is_file() for item in required)


def test_srdf_uses_the_fanuc_chain_and_six_joint_home_state() -> None:
    root = ET.parse(PACKAGE / "config" / "carve_m10id12.srdf").getroot()
    chain = root.find("./group[@name='manipulator']/chain")
    assert chain is not None
    assert chain.attrib == {"base_link": "base_link", "tip_link": "flange"}
    state = root.find("./group_state[@name='home']")
    assert state is not None
    assert [item.attrib["name"] for item in state.findall("joint")] == JOINTS


def test_robot_model_includes_conservative_gripper_collision_envelope() -> None:
    root = ET.parse(PACKAGE / "robot" / "carve_m10id12.urdf.xacro").getroot()
    link = root.find("./link[@name='gripper_collision_envelope']")
    assert link is not None
    box = link.find("./collision/geometry/box")
    assert box is not None and box.attrib["size"] == "0.35 0.22 0.14"


def test_controller_maps_moveit_to_the_isaac_action() -> None:
    values = yaml.safe_load((PACKAGE / "config" / "moveit_controllers.yaml").read_text(encoding="utf-8"))
    manager = values["moveit_simple_controller_manager"]
    assert manager["controller_names"] == ["carve_arm_controller"]
    controller = manager["carve_arm_controller"]
    assert controller["type"] == "FollowJointTrajectory"
    assert controller["action_ns"] == "/carve/arm_controller/follow_joint_trajectory"
    assert controller["joints"] == JOINTS


def test_planning_and_kinematics_plugins_are_deliberately_small() -> None:
    kinematics = yaml.safe_load((PACKAGE / "config" / "kinematics.yaml").read_text(encoding="utf-8"))
    planning = yaml.safe_load((PACKAGE / "config" / "ompl_planning.yaml").read_text(encoding="utf-8"))
    assert kinematics["manipulator"]["kinematics_solver"] == "kdl_kinematics_plugin/KDLKinematicsPlugin"
    assert planning["planning_plugin"] == "ompl_interface/OMPLPlanner"
    assert planning["manipulator"]["planner_configs"] == ["RRTConnect"]


def test_planning_scene_matches_named_isaac_cell_obstacles() -> None:
    scene = yaml.safe_load((PACKAGE / "config" / "cell_collision_objects.yaml").read_text(encoding="utf-8"))
    identifiers = {item["id"] for item in scene["objects"]}
    assert scene["frame_id"] == "world"
    assert {"conveyor_belt", "robot_pedestal", "cutter_base", "cutter_tray", "reject_bin"} <= identifiers
    for item in scene["objects"]:
        assert len(item["size"]) == 3 and all(value > 0 for value in item["size"])
        assert len(item["position"]) == 3


def test_launch_uses_sim_time_and_measured_isaac_joint_state() -> None:
    text = (PACKAGE / "launch" / "isaac_moveit.launch.py").read_text(encoding="utf-8")
    assert '"use_sim_time": True' in text
    assert '("/joint_states", "/carve/joint_states")' in text
    assert 'package="moveit_ros_move_group"' in text


def test_demo_client_plans_with_rrtconnect_and_executes_timed_trajectory() -> None:
    source = (DEMO_PACKAGE / "src" / "plan_to_pose.cpp").read_text(encoding="utf-8")
    assert (DEMO_PACKAGE / "package.xml").is_file()
    assert (DEMO_PACKAGE / "CMakeLists.txt").is_file()
    assert 'setPlannerId("RRTConnect")' in source
    assert "move_group.plan(plan)" in source
    assert "stretch_trajectory" in source
    assert "move_group.execute(plan)" in source
