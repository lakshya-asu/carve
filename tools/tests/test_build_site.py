from pathlib import Path

import pytest

import build_site as bs


def _note(body: str, number: str = "2-3", **meta: str) -> bs.Note:
    n = bs.Note(
        path=bs.REPO / "library" / "topics" / "t.md",
        section="library/topics",
        title=meta.get("title", "T"),
        date=meta.get("date", "2026-09-05"),
        status=meta.get("status", "draft"),
        tags=["x"],
        source="",
        body_md=body,
        lines=body.count("\n") + 1,
        n_sources=bs.count_sources(body),
        n_unverified=bs.count_unverified(body),
        number=number,
    )
    bs.render_note(n)
    return n


def test_parse_front_matter_splits_meta_and_body() -> None:
    meta, body = bs.parse_front_matter("---\ntitle: X\ntags: [a, b]\n---\n# Body\n")
    assert meta == {"title": "X", "tags": ["a", "b"]}
    assert body == "# Body\n"


def test_parse_front_matter_absent() -> None:
    meta, body = bs.parse_front_matter("# Just body\n")
    assert meta == {}
    assert body == "# Just body\n"


def test_parse_front_matter_rejects_non_mapping() -> None:
    with pytest.raises(ValueError, match="mapping"):
        bs.parse_front_matter("---\n- a\n- b\n---\nbody")


def test_count_unverified_and_sources() -> None:
    body = "A (unverified). B (Unverified) https://a.org/x https://a.org/x https://b.org"
    assert bs.count_unverified(body) == 2
    assert bs.count_sources(body) == 2


def test_headings_are_numbered_and_leading_h1_dropped() -> None:
    n = _note("# Title\n\n## Alpha\n\n### Sub one\n\n### Sub two\n\n## Beta\n")
    assert "<h1>" not in n.body_html
    assert [p[0] for p in n.paragraphs] == ["2-3.1", "2-3.1a", "2-3.1b", "2-3.2"]
    assert 'id="p2-3.1"' in n.body_html and '<span class="pnum">2-3.2</span>Beta' in n.body_html


def test_tables_figures_and_boxes_get_manual_labels() -> None:
    n = _note(
        "| a | b |\n|---|---|\n| 1 | 2 |\n\n```mermaid\ngraph TD; A-->B\n```\n\n> Warning: sunlight kills the IR pattern.\n"
    )
    assert "Table 2-3-1" in n.body_html and '<div class="tablewrap"><table>' in n.body_html
    assert "Figure 2-3-1" in n.body_html and '<pre class="mermaid">graph TD; A-->B' in n.body_html
    assert '<span class="boxlabel">WARNING</span>' in n.body_html


def test_unverified_claims_get_change_bars() -> None:
    n = _note("Min range 0.28 m.\n\nBaseline 50 mm (unverified).\n\n- ok\n- fps (from field, unverified)\n")
    assert n.body_html.count('class="chg"') == 2
    assert '<span class="unv">unverified</span>' in n.body_html
    assert '<span class="unv">from field, unverified</span>' in n.body_html


def test_task_items_become_persisted_checkboxes() -> None:
    n = _note("- [ ] E-stop tested\n- [x] Laptop charged\n")
    assert n.body_html.count('type="checkbox"') == 2
    assert 'data-key="n2-3-t1"' in n.body_html and "checked" in n.body_html
    assert "E-stop tested</span></label></li>" in n.body_html


def test_collect_notes_numbers_by_chapter_and_skips_templates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bs, "REPO", tmp_path)
    (tmp_path / "sops").mkdir()
    (tmp_path / "sops" / "a.md").write_text("---\ntitle: A\n---\nx")
    (tmp_path / "sops" / "b.md").write_text("---\ntitle: B\n---\nx")
    d = tmp_path / "experiments"
    d.mkdir()
    (d / "TEMPLATE.md").write_text("---\ntitle: tpl\n---\nx")
    (d / "2026-09-05-real.md").write_text("---\ntitle: real\n---\nx")
    notes = bs.collect_notes(tmp_path)
    assert [(n.number, n.title) for n in notes] == [("1-1", "A"), ("1-2", "B"), ("6-1", "real")]


def test_build_page_has_contents_themes_and_no_mermaid_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bs, "REPO", tmp_path)
    (tmp_path / "sops").mkdir()
    (tmp_path / "sops" / "a.md").write_text("---\ntitle: Alpha\nstatus: reviewed\n---\n# Alpha\n\n## First\n\ntext\n")
    page = bs.build_page(bs.collect_notes(tmp_path), artifact=True, built="2026-09-05")
    assert "Chapter 1" in page and "(reserved)" in page
    assert 'id="n1-1"' in page and 'href="#p1-1.1"' in page
    assert 'data-theme="dark"' in page and "mermaid.min.js" not in page


def test_relative_note_links_resolve_to_anchors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bs, "REPO", tmp_path)
    (tmp_path / "sops").mkdir()
    (tmp_path / "sops" / "a.md").write_text(
        "---\ntitle: A\n---\nsee [B](b.md) and [gone](zzz.md) and [ext](https://x.org/a.md)"
    )
    (tmp_path / "sops" / "b.md").write_text("---\ntitle: B\n---\nx")
    notes = bs.collect_notes(tmp_path)
    bs.build_page(notes, artifact=True, built="2026-09-05")
    assert '<a href="#n1-2">B</a>' in notes[0].body_html
    assert 'class="dead"' in notes[0].body_html
    assert 'href="https://x.org/a.md"' in notes[0].body_html


def test_bare_urls_autolink_and_gt_lines_stay_text() -> None:
    n = _note("See https://x.org/a, then (https://y.org/b).\n\n- 90 m at\n  >90% probability\n\n> Note: real box.\n")
    assert '<a href="https://x.org/a" class="url">https://x.org/a</a>,' in n.body_html
    assert '<a href="https://y.org/b" class="url">https://y.org/b</a>)' in n.body_html
    assert n.body_html.count('class="box"') == 1 and "&gt;90%" in n.body_html


def test_code_paths_become_numbered_cross_references(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bs, "REPO", tmp_path)
    (tmp_path / "sops").mkdir()
    (tmp_path / "sops" / "a.md").write_text("---\ntitle: A\n---\nsee `sops/b.md` and `sops/none.md`")
    (tmp_path / "sops" / "b.md").write_text("---\ntitle: B\n---\nx")
    notes = bs.collect_notes(tmp_path)
    bs.build_page(notes, artifact=True, built="2026-09-05")
    assert '<a href="#n1-2">1-2 B</a>' in notes[0].body_html and "<code>sops/none.md</code>" in notes[0].body_html


def test_mermaid_classdefs_map_to_manual_marks() -> None:
    n = _note(
        "```mermaid\nflowchart LR\n  A-->B\n  classDef fix fill:#D9EEF1,stroke:#0B7C8C,color:#141A22\n  classDef risk fill:#F9DEDC,stroke:#B3261E,color:#141A22\n  class A fix\n```\n"
    )
    assert "#D9EEF1" not in n.body_html and "#B3261E" not in n.body_html
    assert "classDef mk1 stroke-width:1px" in n.body_html and "classDef mk2 stroke-width:1px" in n.body_html
    assert "class A mk1" in n.body_html and "fix" not in n.body_html.split("classDef")[1]


def test_index_lists_terms_seen_in_two_paragraphs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bs, "REPO", tmp_path)
    (tmp_path / "sops").mkdir()
    (tmp_path / "sops" / "a.md").write_text(
        "---\ntitle: A\n---\n## One\n\nThe D435i and ros2_control. Every day.\n\n## Two\n\nD435i again with MoveIt Servo.\n"
    )
    page = bs.build_page(bs.collect_notes(tmp_path), artifact=True, built="2026-09-05")
    assert "<dt>D435i</dt>" in page and 'href="#p1-1.1"' in page and 'href="#p1-1.2"' in page
    assert "<dt>ros2_control</dt>" not in page and "<dt>Every</dt>" not in page
