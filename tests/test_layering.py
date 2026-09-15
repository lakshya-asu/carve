"""The import rules in ARCHITECTURE.md, checked on the source so a violation fails a test run.

* Layers import downward only. `robotics.core` imports no other first-party layer.
  `robotics.hardware`, `robotics.perception` and `robotics.skills` import `robotics.core` and not
  each other. Nothing in `robotics` imports `applications`, and one application never imports another.
* `robotics.core` and every application's `grasping` package are numpy-only: following their
  first-party imports, including the `__init__` of every package on the way, reaches nothing but the
  standard library and numpy.
* The ROS 2 package imports only modules that pass that check, because its nodes run under the
  system Python, which has no MuJoCo, OpenCV or torch.

Imports are read with `ast` anywhere in a file, so an import inside a function is checked too.
"""

from __future__ import annotations

import ast
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
ROS_PACKAGE = REPO / "ros2" / "src" / "meat_cell_ros"
FIRST_PARTY = ("robotics", "applications")
# Layers inside `robotics`, lowest first. Every `applications.<cell>` sits above all of them.
LAYER_RANK = {"robotics.core": 0, "robotics.hardware": 1, "robotics.perception": 1, "robotics.skills": 1}
APPLICATION_RANK = 2
ALLOWED_IN_NUMPY_ONLY = set(sys.stdlib_module_names) | {"__future__", "numpy"}


@dataclass(frozen=True)
class SourceTree:
    """First-party modules under a source root and what each imports."""

    modules: dict[str, Path]
    first_party: dict[str, set[str]]
    third_party: dict[str, set[str]]
    problems: list[str]


def scan_imports(path: Path, modules: dict[str, Path]) -> tuple[set[str], set[str], list[str]]:
    """First-party modules, other top-level packages, and unresolvable imports in one file."""
    first: set[str] = set()
    other: set[str] = set()
    problems: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            targets = [(alias.name, ()) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                problems.append(f"{path}:{node.lineno}: relative import; write the absolute module path")
                continue
            targets = [(node.module or "", tuple(alias.name for alias in node.names))]
        else:
            continue
        for module, members in targets:
            if module.split(".")[0] not in FIRST_PARTY:
                other.add(module.split(".")[0])
                continue
            if module not in modules:
                problems.append(f"{path}:{node.lineno}: imports {module}, which is not a module under src/")
                continue
            first.add(module)
            first.update(f"{module}.{member}" for member in members if f"{module}.{member}" in modules)
    return first, other, problems


def load_tree(src: Path) -> SourceTree:
    """Read every first-party module under `src`."""
    modules: dict[str, Path] = {}
    for path in sorted(src.rglob("*.py")):
        parts = path.relative_to(src).with_suffix("").parts
        if parts[0] in FIRST_PARTY:
            modules[".".join(parts[:-1] if parts[-1] == "__init__" else parts)] = path
    first_party, third_party, problems = {}, {}, []
    for name, path in modules.items():
        first_party[name], third_party[name], found = scan_imports(path, modules)
        problems.extend(found)
    return SourceTree(modules, first_party, third_party, problems)


def layer_of(module: str) -> str:
    """`robotics.<layer>` or `applications.<cell>`: the first two parts of the module name."""
    return ".".join(module.split(".")[:2])


def rank_of(layer: str) -> int | None:
    """Height of a layer, or None for a package that is not a known layer."""
    if layer.startswith("applications."):
        return APPLICATION_RANK
    return LAYER_RANK.get(layer)


def layer_violations(tree: SourceTree) -> list[tuple[str, str, str]]:
    """(importer, imported, reason) for every import that does not point to a lower layer."""
    violations = []
    for importer in sorted(tree.first_party):
        for imported in sorted(tree.first_party[importer]):
            importer_layer, imported_layer = layer_of(importer), layer_of(imported)
            importer_rank, imported_rank = rank_of(importer_layer), rank_of(imported_layer)
            if importer_rank is None or imported_rank is None:
                unknown = importer_layer if importer_rank is None else imported_layer
                violations.append(
                    (importer, imported, f"{unknown} is not a layer; add it to LAYER_RANK and ARCHITECTURE.md")
                )
            elif importer_layer != imported_layer and imported_rank >= importer_rank:
                violations.append((importer, imported, f"{importer_layer} may not import {imported_layer}"))
    return violations


def is_numpy_only(module: str) -> bool:
    """Whether the rules require this module to run with numpy and the standard library alone."""
    parts = module.split(".")
    return layer_of(module) == "robotics.core" or (parts[0] == "applications" and parts[2:3] == ["grasping"])


def beyond_numpy(tree: SourceTree, start: str) -> str | None:
    """The first import chain from `start` that reaches a package other than numpy or the standard library."""
    queue = deque([(start, (start,))])
    seen = {start}
    while queue:
        module, chain = queue.popleft()
        heavy = sorted(tree.third_party[module] - ALLOWED_IN_NUMPY_ONLY)
        if heavy:
            return " -> ".join(chain) + " imports " + ", ".join(heavy)
        # Importing a.b.c runs the __init__ of a and a.b first.
        parents = {".".join(module.split(".")[:depth]) for depth in range(1, module.count(".") + 1)}
        for following in sorted((tree.first_party[module] | parents) - seen):
            seen.add(following)
            queue.append((following, (*chain, following)))
    return None


@pytest.fixture(scope="module")
def tree() -> SourceTree:
    return load_tree(SRC)


def test_every_first_party_import_resolves(tree: SourceTree) -> None:
    assert tree.problems == []


def test_layers_import_downward_only(tree: SourceTree) -> None:
    present = {layer_of(module) for module in tree.modules}
    assert {"robotics.core", "robotics.hardware", "robotics.perception", "applications.pork_leg_alignment"} <= present
    violations = layer_violations(tree)
    assert not violations, "\n".join(f"{a} imports {b}: {why}" for a, b, why in violations)


def test_core_and_grasping_are_numpy_only(tree: SourceTree) -> None:
    roots = sorted(module for module in tree.modules if is_numpy_only(module))
    assert any(m.startswith("robotics.core.") for m in roots)
    assert any(m.startswith("applications.") for m in roots)
    failures = [chain for module in roots if (chain := beyond_numpy(tree, module))]
    assert not failures, "\n".join(failures)


def test_ros2_package_imports_only_numpy_only_modules(tree: SourceTree) -> None:
    imported: set[str] = set()
    for path in sorted(ROS_PACKAGE.rglob("*.py")):
        first, _, problems = scan_imports(path, tree.modules)
        assert problems == []
        imported |= first
    assert imported, f"no import of robotics or applications found under {ROS_PACKAGE}"
    failures = [chain for module in sorted(imported) if (chain := beyond_numpy(tree, module))]
    assert not failures, "\n".join(failures)


def _write_module(root: Path, module: str, body: str) -> None:
    path = root / (module.replace(".", "/") + ".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def test_checker_finds_upward_sideways_cross_application_and_heavy_imports(tmp_path: Path) -> None:
    packages = ("robotics", "robotics.core", "robotics.hardware", "robotics.perception")
    for package in (*packages, "applications", "applications.cell_a", "applications.cell_a.grasping"):
        _write_module(tmp_path, f"{package}.__init__", "")
    _write_module(tmp_path, "applications.cell_b.__init__", "")
    _write_module(tmp_path, "robotics.core.types", "import math\nimport numpy\n")
    _write_module(tmp_path, "robotics.core.lazy", "def load():\n    from robotics.hardware.arm import Arm\n")
    _write_module(tmp_path, "robotics.hardware.arm", "import mujoco\nfrom robotics.core.types import T\n")
    _write_module(tmp_path, "robotics.perception.seg", "from robotics.hardware.arm import Arm\n")
    _write_module(tmp_path, "applications.cell_a.grasping.rule", "import cv2\nfrom robotics.core.types import T\n")
    _write_module(tmp_path, "applications.cell_b.skill", "from applications.cell_a.grasping.rule import Rule\n")

    tree = load_tree(tmp_path)

    assert tree.problems == []
    assert {(a, b) for a, b, _ in layer_violations(tree)} == {
        ("robotics.core.lazy", "robotics.hardware.arm"),
        ("robotics.perception.seg", "robotics.hardware.arm"),
        ("applications.cell_b.skill", "applications.cell_a.grasping.rule"),
    }
    assert beyond_numpy(tree, "robotics.core.types") is None
    assert beyond_numpy(tree, "robotics.core.lazy") == "robotics.core.lazy -> robotics.hardware.arm imports mujoco"
    assert beyond_numpy(tree, "applications.cell_a.grasping.rule") == "applications.cell_a.grasping.rule imports cv2"


def test_checker_reports_imports_of_modules_that_do_not_exist(tmp_path: Path) -> None:
    _write_module(tmp_path, "robotics.__init__", "")
    _write_module(tmp_path, "robotics.core.__init__", "from robotics.core.gone import X\n")

    assert len(load_tree(tmp_path).problems) == 1
