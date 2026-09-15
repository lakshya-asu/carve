#!/usr/bin/env python3
"""PostToolUse hook: flag AI-slop patterns in files Claude just wrote.

Reads the hook JSON on stdin, scans the written file, and reports hits on
stderr with exit code 2 so the findings are fed back to Claude. Exit 0 when
clean or when the file type is not prose or code.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCAN_SUFFIXES = {".md", ".txt", ".rst", ".html", ".py", ".ts", ".tsx", ".js", ".jsx", ".yaml", ".yml", ".toml"}

# (regex, label). Case-insensitive. Kept to high-precision patterns.
PATTERNS: list[tuple[str, str]] = [
    (r"—", "em-dash"),
    (r"\bdelve\b", "banned word: delve"),
    (r"\bleverag(e|es|ed|ing)\b", "banned word: leverage"),
    (r"\bseamless(ly)?\b", "banned word: seamless"),
    (r"\btapestry\b", "banned word: tapestry"),
    (r"\btestament to\b", "banned phrase: testament to"),
    (r"\bgame[- ]changer\b", "banned phrase: game-changer"),
    (r"\bcutting[- ]edge\b", "banned phrase: cutting-edge"),
    (r"\bholistic\b", "banned word: holistic"),
    (r"\bempower(s|ed|ing)?\b", "banned word: empower"),
    (r"\belevat(e|es|ed|ing)\b", "banned word: elevate"),
    (r"\bunlock(s|ed|ing)?\b", "banned word: unlock"),
    (r"\bstreamlin(e|es|ed|ing)\b", "banned word: streamline"),
    (r"\bit'?s worth noting\b", "filler: it's worth noting"),
    (r"\bin conclusion\b", "filler: in conclusion"),
    (r"\bin summary\b", "filler: in summary"),
    (r"\bat its core\b", "filler: at its core"),
    (r"\blet'?s dive\b", "filler: let's dive"),
    (r"\bi hope this helps\b", "filler: I hope this helps"),
    (r"\bgreat question\b", "sycophancy: great question"),
    (r"\babsolutely!", "sycophancy: Absolutely!"),
    (r"\bnot (just|only|merely) \w[^.\n]{0,50}?, but (also )?\b", "cliché: not just X, but Y"),
    (r"^#{1,6} .*[\U0001F300-\U0001FAFF☀-➿]", "emoji in heading"),
    (r"[\U0001F680✨\U0001F525\U0001F4A1✅\U0001F3AF]", "decorative emoji"),
]
COMPILED = [(re.compile(p, re.IGNORECASE), label) for p, label in PATTERNS]
LINK_LINE = re.compile(r"https?://|\[[^\]]+\]\([^)]+\)")
RULE_FILES = {"slop_check.py", "slop-check.py", "CLAUDE.md", "AGENTS.md", "GEMINI.md", "quality_hook.py"}


def scan(text: str) -> list[tuple[int, str, str]]:
    """Return (line_number, label, excerpt) for every hit."""
    hits: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        in_link = bool(LINK_LINE.search(line))
        for rx, label in COMPILED:
            if label.startswith("banned") and in_link:
                continue  # paper titles and URLs legitimately contain these words
            if rx.search(line):
                hits.append((lineno, label, line.strip()[:90]))
    return hits


def main() -> int:
    """Read the hook payload on stdin, scan the written file, report hits on stderr."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    raw = payload.get("tool_input", {}).get("file_path") or payload.get("tool_response", {}).get("filePath")
    if not raw:
        return 0
    path = Path(raw)
    if path.suffix.lower() not in SCAN_SUFFIXES or not path.is_file():
        return 0
    # Files that define the rules necessarily quote the words they ban.
    if path.name in RULE_FILES or path.parent.name == "agents":
        return 0
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    hits = scan(text)
    if not hits:
        return 0
    print(f"slop-check: {len(hits)} hit(s) in {path}. Fix before moving on.", file=sys.stderr)
    for lineno, label, excerpt in hits[:25]:
        print(f"  {path.name}:{lineno}  {label}  |  {excerpt}", file=sys.stderr)
    if len(hits) > 25:
        print(f"  ... {len(hits) - 25} more", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
