from html.parser import HTMLParser
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "PROJECT_PAGE.html"
SOLUTION_A_METRICS = ROOT / "assets" / "project_page" / "scene2_solution_a_metrics.json"
SOLUTION_B_METRICS = ROOT / "assets" / "project_page" / "scene2_solution_b_metrics.json"


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
    for anchor in {"top", "views", "demo", "envelope", "system", "results", "run"}:
        assert anchor in parser.ids
    for phrase in {
        "YOLO26",
        "Instance segmentation",
        "Rendered cell view",
        "Depth stream",
        "Robot control",
        "Two complete cycles, with no hidden pickup.",
        "Pose writes after grasp",
        "Solution A",
        "Solution B",
        "External integration boundary",
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


def test_project_page_publishes_both_final_scene2_recordings() -> None:
    text, parser = parse_page()
    assert parser.video_sources[:2] == [
        "assets/project_page/scene2_solution_a.mp4",
        "assets/project_page/scene2_solution_b.mp4",
    ]
    assert len(parser.video_sources) >= 12
    for required in {
        "assets/project_page/speed_pose/slow_diagonal_right.mp4",
        "assets/project_page/speed_pose/fast_transverse.mp4",
        "assets/project_page/speed_pose/high_speed_transverse.mp4",
        "assets/project_page/speed_pose/solution_b_slip.mp4",
        "assets/project_page/speed_pose/failed_grasp.mp4",
        "assets/project_page/speed_pose/emergency_stop.mp4",
    }:
        assert required in parser.video_sources
    assert "fanuc_presentation.mp4" not in text


def test_published_speed_matrix_is_machine_readable_and_honest() -> None:
    path = ROOT / "assets" / "project_page" / "speed_pose" / "matrix_summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["simulation_only"] is True
    assert payload["demonstrated_speed_range_mps"] == [0.06, 0.22]
    assert len(payload["cases"]) == 6
    assert all(item["passed"] for item in payload["cases"])
    assert min(item["detection_confidence"] for item in payload["cases"]) < 0.02


def test_published_cycles_pass_integrated_contact_motion_and_delivery_gates() -> None:
    for path, solution in ((SOLUTION_A_METRICS, "a"), (SOLUTION_B_METRICS, "b")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["passed"] is True
        assert payload["solution"] == solution
        assert payload["product_pose_sets_after_confirmed_grasp"] == 0
        assert payload["perception"]["model_name"].startswith("ultralytics_yolo26")
        assert payload["grasp"]["bilateral_contact"] is True
        assert payload["grasp"]["unexpected_contact_pairs"] == []
        assert payload["grasp"]["lift_distance_m"] >= 0.10
        assert payload["grasp"]["maximum_product_to_tcp_distance_m"] <= payload["grasp"]["retention_limit_m"]
        assert payload["delivery"]["delivered"] is True
        assert payload["motion"]["joint_limit_violations"] == 0
        assert payload["motion"]["velocity_limit_violations"] == 0
        assert payload["motion"]["acceleration_limit_violations"] == 0


def test_project_page_uses_no_forbidden_dash_characters() -> None:
    text, _ = parse_page()
    css = (ROOT / "project_page" / "styles.css").read_text(encoding="utf-8")
    js = (ROOT / "project_page" / "app.js").read_text(encoding="utf-8")
    for forbidden in ("\N{EM DASH}", "\N{EN DASH}"):
        assert forbidden not in text
        assert forbidden not in css
        assert forbidden not in js
