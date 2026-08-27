from html.parser import HTMLParser
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "PROJECT_PAGE.html"
REAL_PICKUP_METRICS = ROOT / "assets" / "project_page" / "fanuc_real_pickup_metrics.json"


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
        "A real pickup, shown without a hidden cut.",
        "Zero workpiece teleports",
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


def test_project_page_publishes_only_the_continuous_pickup_recording() -> None:
    text, parser = parse_page()
    assert parser.video_sources == ["assets/project_page/fanuc_real_pickup.mp4"]
    assert "fanuc_presentation.mp4" not in text


def test_published_pickup_passes_contact_clearance_and_continuity_gates() -> None:
    payload = json.loads(REAL_PICKUP_METRICS.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["moving_conveyor_interception"] is False
    assert payload["product_visible_before_approach"] is True
    assert payload["teleport_calls_after_record_start"] == 0
    assert payload["joint_limit_violations"] == 0
    assert payload["grasp_validation"]["bilateral_contact"] is True
    assert payload["grasp_validation"]["unexpected_contact_pairs"] == []
    assert payload["grasp_validation"]["lift_distance_m"] >= 0.10
    assert payload["grasp_validation"]["maximum_relative_drift_m"] <= 0.020
    assert payload["grasp_validation"]["release_displacement_m"] >= 0.020
    assert payload["clearance_validation"]["minimum_approach_pad_clearance_m"] >= 0.005
    assert payload["continuity_validation"]["maximum_product_step_m"] <= 0.020


def test_project_page_uses_no_forbidden_dash_characters() -> None:
    text, _ = parse_page()
    css = (ROOT / "project_page" / "styles.css").read_text(encoding="utf-8")
    js = (ROOT / "project_page" / "app.js").read_text(encoding="utf-8")
    for forbidden in ("\N{EM DASH}", "\N{EN DASH}"):
        assert forbidden not in text
        assert forbidden not in css
        assert forbidden not in js
