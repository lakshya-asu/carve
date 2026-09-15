import json
import subprocess
import sys
from pathlib import Path

import pytest

import quality_hook as qh

HOOK = Path(qh.__file__)


def _run(path: Path) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_input": {"file_path": str(path)}})
    return subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, timeout=90)


def test_note_without_front_matter_is_flagged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qh, "REPO", tmp_path)
    note = tmp_path / "library" / "topics" / "thing.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Thing\n\nno front matter here\n")
    assert qh.check_note(note) == [
        "thing.md has no YAML front matter; the manual will title it from the filename and mark it draft"
    ]


def test_note_missing_required_keys_is_flagged(tmp_path: Path) -> None:
    note = tmp_path / "thing.md"
    note.write_text("---\ndate: 2026-09-08\ntags: [x]\n---\n\nbody\n")
    findings = qh.check_note(note)
    assert len(findings) == 1
    assert "title" in findings[0] and "status" in findings[0]


def test_complete_note_passes(tmp_path: Path) -> None:
    note = tmp_path / "thing.md"
    note.write_text("---\ntitle: Thing\ndate: 2026-09-08\ntags: [x]\nstatus: draft\n---\n\nbody\n")
    assert qh.check_note(note) == []


def test_index_and_convention_files_are_skipped(tmp_path: Path) -> None:
    for name in ("README.md", "TEMPLATE.md", "00-study-path.md"):
        f = tmp_path / name
        f.write_text("no front matter\n")
        assert qh.check_note(f) == []


def test_unrelated_files_exit_zero(tmp_path: Path) -> None:
    other = tmp_path / "notes.txt"
    other.write_text("hello")
    assert _run(other).returncode == 0


def test_missing_file_exits_zero() -> None:
    assert _run(Path("/nonexistent/file.py")).returncode == 0


def test_bad_python_is_reported_end_to_end(tmp_path: Path) -> None:
    """A real Python file with an unused import trips ruff through the hook."""
    if not qh.RUFF.exists():
        pytest.skip("ruff not installed at the configured path")
    bad = qh.REPO / "tools" / "_hook_probe.py"
    bad.write_text("import os\n")
    try:
        proc = _run(bad)
        assert proc.returncode == 2
        assert "_hook_probe.py" in proc.stderr
    finally:
        bad.unlink(missing_ok=True)
