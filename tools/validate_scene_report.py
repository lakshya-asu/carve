from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


class ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.references: list[tuple[str, str]] = []
        self.image_alts: list[str | None] = []
        self.landmarks: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag in {"header", "main", "nav", "footer"}:
            self.landmarks.add(tag)
        if tag == "img":
            self.image_alts.append(values.get("alt"))
        for name in ("href", "src"):
            value = values.get(name)
            if value:
                self.references.append((tag, value))


def validate_report(report_path: Path) -> list[str]:
    errors: list[str] = []
    text = report_path.read_text(encoding="utf-8")
    if not text.lstrip().lower().startswith("<!doctype html>"):
        errors.append("missing HTML5 doctype")
    if "\u2013" in text or "\u2014" in text:
        errors.append("contains an en dash or em dash")

    parser = ReportParser()
    parser.feed(text)
    id_set = set(parser.ids)
    duplicate_ids = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
    if duplicate_ids:
        errors.append(f"duplicate ids: {duplicate_ids}")
    missing_landmarks = {"header", "main", "nav", "footer"} - parser.landmarks
    if missing_landmarks:
        errors.append(f"missing landmarks: {sorted(missing_landmarks)}")
    if any(not alt or not alt.strip() for alt in parser.image_alts):
        errors.append("one or more images have empty alt text")

    for tag, reference in parser.references:
        parsed = urlparse(reference)
        if parsed.scheme in {"http", "https", "mailto"}:
            continue
        if reference.startswith("#"):
            target = unquote(reference[1:])
            if target and target not in id_set:
                errors.append(f"missing anchor target: {reference}")
            continue
        local_part = unquote(parsed.path)
        if not local_part:
            continue
        target = (report_path.parent / local_part).resolve()
        if not target.exists():
            errors.append(f"missing local reference from <{tag}>: {reference}")

    required_phrases = [
        "FANUC M-10iD/12 Food Grade",
        "Solution B: failed",
        "Not imported",
        "physical evidence",
        "240 mm",
        "2.24 m/s",
    ]
    for phrase in required_phrases:
        if phrase not in text:
            errors.append(f"missing required truthful phrase: {phrase}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Scene 2.0 HTML report.")
    parser.add_argument(
        "report",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "SCENE_DESIGN_REPORT.html",
    )
    args = parser.parse_args()
    errors = validate_report(args.report.resolve())
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: {args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
