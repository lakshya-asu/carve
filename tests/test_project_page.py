from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "PROJECT_PAGE.html"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []
        self.ids: set[str] = set()
        self.video_sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"] or "")
        for key in ("href", "src"):
            value = values.get(key)
            if value and not value.startswith(("#", "http://", "https://")):
                self.references.append(value)
        if tag == "source" and values.get("type") == "video/mp4" and values.get("src"):
            self.video_sources.append(values["src"] or "")


def parse_page() -> tuple[str, PageParser]:
    text = PAGE.read_text(encoding="utf-8")
    parser = PageParser()
    parser.feed(text)
    return text, parser


def test_project_page_has_required_views_and_sections() -> None:
    text, parser = parse_page()
    for anchor in {"top", "views", "demo", "system", "results", "run"}:
        assert anchor in parser.ids
    for phrase in {
        "YOLO26",
        "Instance segmentation",
        "Rendered RGB stream",
        "Depth stream",
        "Robot control",
        "Solution A",
        "Solution B",
        "Active integration gap",
    }:
        assert phrase in text


def test_project_page_local_references_exist() -> None:
    _, parser = parse_page()
    missing = []
    for reference in parser.references:
        path = ROOT / reference.split("#", 1)[0]
        if not path.exists():
            missing.append(reference)
    assert missing == []


def test_project_page_embeds_nonempty_recorded_video() -> None:
    _, parser = parse_page()
    assert len(parser.video_sources) == 1
    video = ROOT / parser.video_sources[0]
    assert video.suffix.lower() == ".mp4"
    assert video.stat().st_size > 100_000


def test_project_page_uses_no_forbidden_dash_characters() -> None:
    text, _ = parse_page()
    css = (ROOT / "project_page" / "styles.css").read_text(encoding="utf-8")
    js = (ROOT / "project_page" / "app.js").read_text(encoding="utf-8")
    for forbidden in ("\N{EM DASH}", "\N{EN DASH}"):
        assert forbidden not in text
        assert forbidden not in css
        assert forbidden not in js
