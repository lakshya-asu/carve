from pathlib import Path
import re

import pytest

from isaac_sim.run_scene2_integrated import _artifact_manifest


def test_every_integrated_return_to_idle_updates_the_saved_media_label() -> None:
    source = (Path(__file__).parents[1] / "isaac_sim" / "run_scene2_integrated.py").read_text(encoding="utf-8")
    calls = list(re.finditer(r'^\s+supervisor\.return_to_idle\([^\n]+\)$', source, flags=re.MULTILINE))

    assert calls
    for call in calls:
        following_lines = source[call.end() :].splitlines()[1:3]
        assert following_lines[0].strip() == 'set_state("idle")'
        assert following_lines[1].strip() == "flush_events()"


def _write_required_artifacts(root: Path) -> Path:
    for name in (
        "overhead_rgb.png",
        "overhead_depth.png",
        "overhead_depth_m.npy",
        "yolo26_segmentation.png",
        "robot_joint_trajectory.json",
    ):
        (root / name).write_bytes(b"evidence")
    event_path = root / "cycle_trace.jsonl"
    event_path.write_text('{"record_type":"terminal_result"}\n', encoding="utf-8")
    return event_path


def test_solution_b_manifest_omits_buffer_files_before_reobservation(tmp_path: Path) -> None:
    event_path = _write_required_artifacts(tmp_path)

    manifest = _artifact_manifest(tmp_path, event_path, "b")

    assert "buffer_rgb" not in manifest
    assert "buffer_depth_npy" not in manifest


def test_solution_b_manifest_requires_complete_buffer_pair(tmp_path: Path) -> None:
    event_path = _write_required_artifacts(tmp_path)
    (tmp_path / "buffer_rgb.png").write_bytes(b"evidence")

    with pytest.raises(RuntimeError, match="buffer artifact set is incomplete"):
        _artifact_manifest(tmp_path, event_path, "b")


def test_solution_b_manifest_includes_complete_buffer_pair(tmp_path: Path) -> None:
    event_path = _write_required_artifacts(tmp_path)
    (tmp_path / "buffer_rgb.png").write_bytes(b"rgb")
    (tmp_path / "buffer_depth_m.npy").write_bytes(b"depth")

    manifest = _artifact_manifest(tmp_path, event_path, "b")

    assert manifest["buffer_rgb"].endswith("buffer_rgb.png")
    assert manifest["buffer_depth_npy"].endswith("buffer_depth_m.npy")
