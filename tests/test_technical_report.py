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


def test_report_has_no_forced_horizontal_scroll() -> None:
    text, _ = parse_report()
    compact = "".join(text.lower().split())
    for rejected in (
        "overflow-x:auto",
        "overflow-x:scroll",
        "overflow:auto",
        "min-width:900px",
        "min-width:880px",
        "width:900px",
    ):
        assert rejected not in compact
    assert "overflow-x:clip" in compact
    assert ".diagramsvg{width:100%;min-width:0;height:auto}" in compact
    assert ".table-wraptd{display:grid" in compact


def test_recovery_videos_are_large_and_responsive() -> None:
    text, _ = parse_report()
    compact = "".join(text.lower().split())
    assert ".failures{display:grid;grid-template-columns:repeat(2,1fr)" in compact
    assert "@media(max-width:640px)" in compact
    assert ".route-grid,.failures,.criteria" in compact
    assert "grid-template-columns:1fr" in compact


def test_report_contains_real_visual_explanations() -> None:
    _, parser = parse_report()
    assert {
        "solution-branches",
        "system-map",
        "cycle-map",
        "speed-chart",
        "learning-map",
        "ab-result-map",
    } <= parser.svg_ids
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
        "solutions",
        "evidence",
        "system",
        "cycle",
        "products",
        "vision",
        "speed",
        "control",
        "routes",
        "learning",
        "decisions",
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


def test_report_distinguishes_baselines_validated_routes_and_shadow() -> None:
    text, parser = parse_report()
    assert "A and B remain the regression baselines" in text
    assert "C and D pass integrated simulator gates" in text
    assert "E passes shadow evaluation only" in text
    assert "Learned grasp score" in text
    assert "Reactive intercept" in text
    assert "Bounded manipulation skill" in text
    assert "What we chose, why, and what the tests said" in parser.headings
    for name in (
        "END_TO_END_CHAIN.md",
        "DECISIONS_AND_TESTS.md",
        "GENERALIZED_SOLUTION_RESEARCH.md",
        "DEMO_COMMANDS.md",
    ):
        assert name in text


def test_report_links_to_the_public_repository() -> None:
    text, _ = parse_report()
    assert 'href="https://github.com/lakshya-asu/carve"' in text
    assert "View the GitHub repository" in text


def test_learning_route_claim_boundaries_are_explicit() -> None:
    text, _ = parse_report()
    assert "C  VALIDATED" in text
    assert "D  VALIDATED" in text
    assert "E  SHADOW" in text
    assert "zero learned commands" in text.lower()
    assert "physical contact data blocks execution" in text.lower()
    for summary in (
        "assets/project_page/learning/solution_c_summary.json",
        "assets/project_page/learning/solution_d_summary.json",
        "assets/project_page/learning/solution_e_summary.json",
    ):
        assert summary in text


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
