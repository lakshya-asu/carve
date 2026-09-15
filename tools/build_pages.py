r"""Build the GitHub Pages copy of the leg cell plan in `docs/`.

`plan/leg-cell-plan.html` is written for the artifact viewer, which supplies the document head.
GitHub Pages serves files as they are, so this wraps the page in a full document, copies every
video and image it references into `docs/videos/`, and marks `docs/` as plain static files so
Pages does not run Jekyll over it. Carve serves `docs/` at https://lakshya-asu.github.io/carve/.

    python tools/build_pages.py --media <folder holding the page's videos and images>

Without `--media`, media already in `docs/videos/` is kept and anything missing is an error.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "plan" / "leg-cell-plan.html"
DOCS = ROOT / "docs"
BODY_START = '<header class="run">'
DOCUMENT_HEAD = (
    '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
)


def main() -> None:
    """Write docs/index.html and docs/videos/ from the plan page."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--media", type=Path, help="folder to copy the referenced media from")
    args = parser.parse_args()

    html = PAGE.read_text(encoding="utf-8")
    head, body = html.split(BODY_START, 1)
    (DOCS / "videos").mkdir(parents=True, exist_ok=True)
    missing = []
    for reference in sorted(set(re.findall(r'src="(videos/[^"]+)"', html))):
        target = DOCS / reference
        source = args.media / Path(reference).name if args.media else None
        if source is not None and source.is_file():
            shutil.copy2(source, target)
        elif not target.is_file():
            missing.append(reference)
    if missing:
        raise SystemExit(f"referenced by the page but not found: {', '.join(missing)}")
    # Media the page no longer references would stay published and in the repo; remove it.
    referenced = {Path(reference).name for reference in re.findall(r'src="(videos/[^"]+)"', html)}
    for stale in (DOCS / "videos").iterdir():
        if stale.name not in referenced:
            stale.unlink()

    document = f"{DOCUMENT_HEAD}{head.strip()}\n</head>\n<body>\n{BODY_START}{body.rstrip()}\n</body>\n</html>\n"
    (DOCS / "index.html").write_text(document, encoding="utf-8")
    (DOCS / ".nojekyll").touch()
    size_mb = sum(f.stat().st_size for f in DOCS.rglob("*") if f.is_file()) / 1e6
    print(f"wrote {DOCS / 'index.html'} and {len(list((DOCS / 'videos').iterdir()))} media files, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
