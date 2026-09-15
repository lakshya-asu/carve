"""PostToolUse hook: check a file the moment it is written, not at build time.

Python files under the repo get ruff format and lint. Library notes get a front
matter check, because a note without front matter builds into the manual with a
filename for a title and no status, and that is only noticed much later.

Exit 2 with the findings on stderr so the agent sees them and fixes them in the
same turn. Exit 0 for files this hook does not care about.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUFF = Path("/home/flux/miniconda3/envs/rll/bin/ruff")
NOTE_DIRS = ("library", "sops", "experiments", "field-notes", "retros")
REQUIRED_KEYS = ("title", "status")
SKIP_STEMS = {"README", "TEMPLATE", "MEMORY", "IDENTITY", "CLAUDE", "AGENTS", "GEMINI", "WORKFLOW", "PRODUCT", "DESIGN"}


def check_python(path: Path) -> list[str]:
    """Run ruff format check and lint; return human-readable findings."""
    if not RUFF.exists():
        return []
    findings: list[str] = []
    fmt = subprocess.run(
        [str(RUFF), "format", "--check", str(path)], capture_output=True, text=True, cwd=REPO / "tools"
    )
    if fmt.returncode != 0:
        findings.append(f"ruff format would change {path.name}; run: ruff format {path}")
    lint = subprocess.run([str(RUFF), "check", str(path)], capture_output=True, text=True, cwd=REPO / "tools")
    if lint.returncode != 0:
        findings.append((lint.stdout or lint.stderr).strip())
    return findings


def check_note(path: Path) -> list[str]:
    """Verify a library note carries the front matter the site build needs."""
    if path.stem in SKIP_STEMS or path.stem.startswith("00-"):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    if not text.startswith("---\n"):
        return [f"{path.name} has no YAML front matter; the manual will title it from the filename and mark it draft"]
    end = text.find("\n---", 4)
    head = text[4:end] if end > 0 else ""
    missing = [k for k in REQUIRED_KEYS if f"\n{k}:" not in "\n" + head]
    return [f"{path.name} front matter is missing: {', '.join(missing)}"] if missing else []


def main() -> int:
    """Read the hook payload on stdin and check the file it names."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    raw = (payload.get("tool_input") or {}).get("file_path") or (payload.get("tool_response") or {}).get("filePath")
    if not raw:
        return 0
    path = Path(raw)
    if not path.is_file() or (REPO not in path.parents and path.parent != REPO):
        return 0
    try:
        rel = path.relative_to(REPO)
    except ValueError:
        return 0

    if path.suffix == ".py":
        findings = check_python(path)
    elif path.suffix == ".md" and rel.parts and rel.parts[0] in NOTE_DIRS:
        findings = check_note(path)
    else:
        return 0

    if not findings:
        return 0
    print(f"quality-hook: {rel}", file=sys.stderr)
    for f in findings:
        print(f"  {f}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
