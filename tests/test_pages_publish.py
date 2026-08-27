from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class References(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key in {"src", "href"} and value:
                self.values.append(value)


def test_pages_workflow_publishes_the_report_as_the_site_index() -> None:
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    assert "cp TECHNICAL_REPORT.html _site/index.html" in workflow
    assert "cp -R assets/project_page _site/assets/project_page" in workflow
    assert "actions/deploy-pages@v4" in workflow
    assert "actions/configure-pages@v5" in workflow
    assert "actions/upload-pages-artifact@v4" in workflow
    for name in (
        "END_TO_END_CHAIN.md",
        "DECISIONS_AND_TESTS.md",
        "GENERALIZED_SOLUTION_RESEARCH.md",
        "DEMO_COMMANDS.md",
    ):
        assert name in workflow


def test_all_local_report_media_is_inside_the_published_asset_tree() -> None:
    parser = References()
    parser.feed((ROOT / "TECHNICAL_REPORT.html").read_text(encoding="utf-8"))
    media = [value for value in parser.values if value.startswith("assets/")]
    assert media
    assert all(value.startswith("assets/project_page/") for value in media)
    assert all((ROOT / value).is_file() for value in media)
