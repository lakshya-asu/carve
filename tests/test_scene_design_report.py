from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_scene_design_report_has_no_broken_local_references() -> None:
    from tools.validate_scene_report import validate_report

    report = PROJECT_ROOT / "SCENE_DESIGN_REPORT.html"
    assert report.is_file()
    assert validate_report(report) == []


def test_technical_report_links_to_scene_design_report() -> None:
    report = (PROJECT_ROOT / "TECHNICAL_REPORT.html").read_text(encoding="utf-8")
    assert 'href="SCENE_DESIGN_REPORT.html"' in report
