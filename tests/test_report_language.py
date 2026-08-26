from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_reports_pass_project_language_lint() -> None:
    from tools.audit_report_language import audit

    for name in (
        "SCENE_DESIGN_REPORT.html",
        "TECHNICAL_REPORT.html",
    ):
        result = audit(PROJECT_ROOT / name)
        assert result["style_phrases"] == []
        assert result["prohibited_dash_count"] == 0
        assert result["replacement_character_count"] == 0


def test_writing_standard_rejects_detector_claims() -> None:
    guide = (PROJECT_ROOT / "WRITING_STYLE_RESEARCH.md").read_text(encoding="utf-8")
    assert "will not use an AI detector as a writing gate" in guide
    assert "does not claim to identify who wrote the text" in guide
    assert "\u2013" not in guide
    assert "\u2014" not in guide
    assert "\ufffd" not in guide
