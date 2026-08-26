from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    PROJECT_ROOT
    / "assets"
    / "vendor"
    / "fanuc_description"
    / "fanuc_m10_description"
    / "urdf"
    / "m10_12_14d_urdf_macro.xacro"
)
OUTPUT = PROJECT_ROOT / "assets" / "robots" / "fanuc_m10id12" / "fanuc_m10id12.urdf"
XACRO_NS = "http://wiki.ros.org/xacro"


def _resolve_radians(value: str) -> str:
    pattern = re.compile(r"\$\{radians\(\s*([-+]?\d+(?:\.\d+)?)\s*\)\}")
    return pattern.sub(lambda match: f"{math.radians(float(match.group(1))):.12g}", value)


def _clone(element: ET.Element, properties: dict[str, str]) -> ET.Element | None:
    if element.tag == f"{{{XACRO_NS}}}property":
        return None
    if element.tag == f"{{{XACRO_NS}}}insert_block":
        return ET.Element("origin", {"xyz": "0 0 0", "rpy": "0 0 0"})
    tag = element.tag.split("}", 1)[-1]
    cloned = ET.Element(tag)
    for key, raw_value in element.attrib.items():
        value = _resolve_radians(raw_value)
        value = value.replace("${prefix}", "")
        value = value.replace("${parent}", "world").replace("${child}", "ee_link")
        for name, replacement in properties.items():
            value = value.replace(f"${{{name}}}", replacement)
        cloned.set(key.split("}", 1)[-1], value)
    if element.text and element.text.strip():
        cloned.text = element.text
    for child in element:
        copied = _clone(child, properties)
        if copied is not None:
            cloned.append(copied)
    return cloned


def build(source: Path = SOURCE, output: Path = OUTPUT) -> Path:
    tree = ET.parse(source)
    root = tree.getroot()
    macro = root.find(f"{{{XACRO_NS}}}macro")
    if macro is None:
        raise ValueError(f"No xacro macro found in {source}")
    properties = {
        child.attrib["name"]: _resolve_radians(child.attrib["value"])
        for child in macro
        if child.tag == f"{{{XACRO_NS}}}property"
    }
    robot = ET.Element("robot", {"name": "fanuc_m10id12_reference"})
    robot.append(ET.Comment("Derived from FANUC fanuc_description m10_12_14d, Apache-2.0."))
    robot.append(ET.Comment("This is a kinematic and visual simulation reference, not an OEM controller model."))
    robot.append(ET.Element("link", {"name": "world"}))
    robot.append(ET.Element("link", {"name": "ee_link"}))
    for child in macro:
        copied = _clone(child, properties)
        if copied is not None:
            robot.append(copied)
    ET.indent(robot, space="  ")
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(robot).write(output, encoding="utf-8", xml_declaration=True)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Expand the official FANUC M-10iD/12 xacro into plain URDF.")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = build(args.source.resolve(), args.output.resolve())
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
