from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "TECHNICAL_REPORT.html"


class ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.references: list[str] = []
        self.videos: list[str] = []
        self.svg_ids: set[str] = set()
        self.headings: list[str] = []
        self._heading: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        value_id = values.get("id")
        if value_id:
            self.ids.add(value_id)
            if tag == "svg":
                self.svg_ids.add(value_id)
        for key in ("href", "src", "poster"):
            value = values.get(key)
            if value and not value.startswith(("#", "http://", "https://")):
                self.references.append(value)
        if tag == "source" and values.get("type") == "video/mp4":
            source = values.get("src")
            if source:
                self.videos.append(source)
        if tag in {"h1", "h2", "h3"}:
            self._heading = ""

    def handle_data(self, data: str) -> None:
        if self._heading is not None:
            self._heading += data

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h1", "h2", "h3"} and self._heading is not None:
            self.headings.append(" ".join(self._heading.split()))
            self._heading = None


def parse_report() -> tuple[str, ReportParser]:
    text = REPORT.read_text(encoding="utf-8")
    parser = ReportParser()
    parser.feed(text)
    return text, parser


def test_report_uses_the_project_anti_slop_standard() -> None:
    text, _ = parse_report()
    lowered = text.lower()
    for rejected in (
        "border-radius",
        'class="card',
        'class="panel',
        'class="callout',
        'class="notice',
        "#45d8e8",
        "#68a7ff",
        "--blue",
        "--cyan",
        "linear-gradient",
        "radial-gradient",
        "box-shadow",
    ):
        assert rejected not in lowered
    for forbidden in ("\N{EM DASH}", "\N{EN DASH}"):
        assert forbidden not in text


def test_report_contains_real_visual_explanations() -> None:
    _, parser = parse_report()
    assert {"system-map", "cycle-map", "speed-chart"} <= parser.svg_ids
    assert {
        "How the cell communicates",
        "How one workpiece reaches the cutter",
        "Pixels become a robot target",
        "From intercept plan to joint motion",
    } <= set(parser.headings)
    assert len(parser.videos) >= 13


def test_report_keeps_required_sections_and_local_evidence() -> None:
    _, parser = parse_report()
    assert {
        "top",
        "evidence",
        "system",
        "cycle",
        "products",
        "vision",
        "speed",
        "control",
        "routes",
        "io",
        "failures",
        "implementation",
        "limits",
    } <= parser.ids
    missing = []
    for reference in parser.references:
        target = ROOT / reference.split("#", 1)[0]
        if not target.exists():
            missing.append(reference)
    assert missing == []


def test_report_includes_durable_design_rules_and_research_sources() -> None:
    text, _ = parse_report()
    assert "REPORT_DESIGN_STANDARD.md" in text
    for domain in (
        "w3.org/WAI",
        "design-system.service.gov.uk",
        "nngroup.com",
        "carbondesignsystem.com",
    ):
        assert domain in text
