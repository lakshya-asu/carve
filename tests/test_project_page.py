from html.parser import HTMLParser
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "PROJECT_PAGE.html"
PRESENTATION_METRICS = ROOT / "assets" / "project_page" / "fanuc_presentation_metrics.json"


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
        "The arm, jaws, workpiece, and release are visible.",
        "It does not yet prove conveyor pickup or the complete YOLO delivery cycle.",
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
    assert parser.video_sources[0] == "assets/project_page/fanuc_presentation.mp4"
    assert video.suffix.lower() == ".mp4"
    assert video.stat().st_size > 100_000


def test_published_gripper_demo_has_contact_hold_and_release_evidence() -> None:
    payload = json.loads(PRESENTATION_METRICS.read_text(encoding="utf-8"))
    grasp = payload["grasp_validation"]
    assert payload["passed"] is True
    assert payload["joint_limit_violations"] == 0
    assert grasp["passed"] is True
    assert grasp["bilateral_contact"] is True
    assert all(force > 0.1 for force in grasp["peak_contact_force_n"])
    assert grasp["gravity_hold_slip_m"] <= 0.005
    assert grasp["release_displacement_m"] >= 0.020
    assert payload["recording"]["source"] == "rendered_presentation_rgb"
    assert payload["recording"]["frame_count"] > 0


def test_project_page_uses_no_forbidden_dash_characters() -> None:
    text, _ = parse_page()
    css = (ROOT / "project_page" / "styles.css").read_text(encoding="utf-8")
    js = (ROOT / "project_page" / "app.js").read_text(encoding="utf-8")
    for forbidden in ("\N{EM DASH}", "\N{EN DASH}"):
        assert forbidden not in text
        assert forbidden not in css
        assert forbidden not in js
