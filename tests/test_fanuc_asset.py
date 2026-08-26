from pathlib import Path
import math
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
URDF = PROJECT_ROOT / "assets" / "robots" / "fanuc_m10id12" / "fanuc_m10id12.urdf"


def test_fanuc_urdf_is_reproducible_and_has_six_axes(tmp_path: Path) -> None:
    from tools.build_fanuc_urdf import build

    rebuilt = build(output=tmp_path / "fanuc.urdf")
    assert rebuilt.read_bytes() == URDF.read_bytes()
    root = ET.parse(rebuilt).getroot()
    revolute = [joint for joint in root.findall("joint") if joint.attrib["type"] == "revolute"]
    assert [joint.attrib["name"] for joint in revolute] == ["J1", "J2", "J3", "J4", "J5", "J6"]
    assert [joint.find("axis").attrib["xyz"] for joint in revolute] == [
        " 0  0  1",
        " 0  1  0",
        " 0 -1  0",
        "-1  0  0",
        " 0 -1  0",
        "-1  0  0",
    ]


def test_fanuc_joint_limits_match_the_official_description() -> None:
    root = ET.parse(URDF).getroot()
    expected_degrees = {
        "J1": (-185, 185, 260),
        "J2": (-90, 145, 240),
        "J3": (-90, 222, 260),
        "J4": (-190, 190, 430),
        "J5": (-180, 180, 450),
        "J6": (-450, 450, 720),
    }
    for joint in root.findall("joint"):
        if joint.attrib["name"] not in expected_degrees:
            continue
        lower, upper, velocity = expected_degrees[joint.attrib["name"]]
        limit = joint.find("limit")
        assert math.isclose(float(limit.attrib["lower"]), math.radians(lower), abs_tol=1e-10)
        assert math.isclose(float(limit.attrib["upper"]), math.radians(upper), abs_tol=1e-10)
        assert math.isclose(float(limit.attrib["velocity"]), math.radians(velocity), abs_tol=1e-10)


def test_fanuc_mesh_inventory_is_complete() -> None:
    mesh_root = (
        PROJECT_ROOT
        / "assets"
        / "vendor"
        / "fanuc_description"
        / "fanuc_m10_description"
        / "meshes"
        / "m10_12_14d"
    )
    assert len(list((mesh_root / "visual").glob("*.dae"))) == 7
    assert len(list((mesh_root / "collision").glob("*.stl"))) == 7
