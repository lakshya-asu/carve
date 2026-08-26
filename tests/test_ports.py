import importlib
import sys

from isaac_sim.adapter_config import IsaacCellPaths, REQUIRED_FRAME_NAMES
from meatcell.contracts import Transform
from meatcell.fake_adapter import FakeSimulatorAdapter
from meatcell.ports import RobotCommand, SimulatorAdapter


def test_fake_adapter_satisfies_all_simulator_ports() -> None:
    adapter = FakeSimulatorAdapter()
    assert isinstance(adapter, SimulatorAdapter)
    adapter.create_cell("b")
    adapter.create_product("piece", Transform.planar(0.0, 0.0, 0.1, 0.0), 0.7)
    camera = adapter.capture_rgbd("overhead")
    assert camera.valid_rgb_pixels == camera.width_px * camera.height_px
    adapter.set_gripper_closed(True)
    assert adapter.attach_grasp("piece")
    assert len(adapter.read_contacts()) == 2
    command = RobotCommand(
        adapter.simulation_time,
        ("x_axis", "y_axis", "z_axis", "wrist_yaw", "finger_left", "finger_right"),
        (1.0, 0.1, 0.2, 0.3, -0.02, 0.02),
        (1.0,) * 6,
        (2.0,) * 6,
    )
    adapter.command_robot(command)
    adapter.step_once()
    assert adapter.read_robot_state().positions == command.position_targets


def test_adapter_configuration_names_every_required_prim_and_frame() -> None:
    paths = IsaacCellPaths()
    required = paths.required_for_solution("b")
    assert paths.robot in required
    assert paths.gripper in required
    assert paths.overhead_camera in required
    assert paths.cut_target_frame in required
    assert paths.plc in required
    assert "cut_target_frame" in REQUIRED_FRAME_NAMES
    assert len(required) == len(set(required))


def test_importing_domain_and_adapter_config_does_not_import_or_start_isaac() -> None:
    before = set(sys.modules)
    importlib.import_module("meatcell")
    importlib.import_module("meatcell.ports")
    importlib.import_module("isaac_sim.adapter_config")
    newly_loaded = set(sys.modules) - before
    assert not any(name == "isaacsim" or name.startswith("omni") or name.startswith("pxr") for name in newly_loaded)
