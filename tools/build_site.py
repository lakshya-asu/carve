"""Build the living-documentation site from the Markdown library.

Walks the knowledge base, parses YAML front matter, renders Markdown to HTML,
and writes a single self-contained page laid out as an equipment technical
manual: chapters, numbered notes and paragraphs, ruled tables and figures,
change bars beside unverified claims, and a contents column with search.

Usage:
    python tools/build_site.py                  # writes site/index.html
    python tools/build_site.py --artifact       # omit Mermaid script (host renders it)
    python tools/build_site.py --out other.html
"""

from __future__ import annotations

import argparse
import html
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import markdown
import yaml

logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent
MANUAL_TITLE = "Robot Learning Lab"
SECTIONS: tuple[tuple[str, str], ...] = (
    ("sops", "Standard operating procedures"),
    ("library/topics", "Topics"),
    ("library/papers", "Papers"),
    ("library/tools", "Tools"),
    ("library/hardware", "Hardware"),
    ("experiments", "Experiments"),
    ("field-notes", "Field notes"),
)
FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
UNVERIFIED_RE = re.compile(r"\((?:from field, )?unverified\)", re.IGNORECASE)
LINK_RE = re.compile(r"https?://[^\s)\]>\"']+")
MERMAID_RE = re.compile(r'<pre><code class="language-mermaid">(.*?)</code></pre>', re.DOTALL)
HEADING_RE = re.compile(r'<h([23])(?: id="[^"]*")?>(.*?)</h\1>', re.DOTALL)
TASK_RE = re.compile(r"<li>\[( |x|X)\] ")
BLOCK_TAGS = ("p", "li", "tr")
STATUS_LABEL = {"draft": "Draft", "reviewed": "Reviewed", "stale": "Stale"}


@dataclass
class Note:
    """One Markdown note with metadata, numbering, and rendered body."""

    path: Path
    section: str
    title: str
    date: str
    status: str
    tags: list[str]
    source: str
    body_md: str
    lines: int
    n_sources: int
    n_unverified: int
    number: str = ""  # e.g. "2-3"
    body_html: str = ""
    paragraphs: list[tuple[str, str, str]] = field(default_factory=list)  # (number, id, text)

    @property
    def anchor(self) -> str:
        """Element id for the note: n<chapter>-<index>."""
        return "n" + self.number


def parse_front_matter(text: str) -> tuple[dict[str, object], str]:
    """Split a Markdown document into (front matter dict, body).

    Args:
        text: Full file contents.

    Returns:
        Parsed YAML mapping (empty if absent) and the remaining body text.
    """
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    loaded = yaml.safe_load(match.group(1)) or {}
    if not isinstance(loaded, dict):
        raise ValueError("front matter must be a mapping")
    return loaded, text[match.end() :]


def count_unverified(body: str) -> int:
    """Count claims marked "(unverified)" or "(from field, unverified)" in a note body."""
    return len(UNVERIFIED_RE.findall(body))


def count_sources(body: str) -> int:
    """Count distinct http(s) links in a note body."""
    return len(set(LINK_RE.findall(body)))


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def load_note(path: Path, section: str) -> Note:
    """Load one Markdown file without rendering (numbering happens later)."""
    text = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(text)
    title = str(meta.get("title") or path.stem.replace("-", " ").capitalize())
    tags_raw = meta.get("tags") or []
    tags = [str(t) for t in tags_raw] if isinstance(tags_raw, list) else [str(tags_raw)]
    return Note(
        path=path,
        section=section,
        title=title,
        date=str(meta.get("date") or ""),
        status=str(meta.get("status") or "draft"),
        tags=tags,
        source=str(meta.get("source") or ""),
        body_md=body,
        lines=text.count("\n") + 1,
        n_sources=count_sources(body),
        n_unverified=count_unverified(body),
    )


def collect_notes(repo: Path) -> list[Note]:
    """Load every note in the configured sections, skip templates, assign numbers."""
    notes: list[Note] = []
    for chapter, (rel, _label) in enumerate(SECTIONS, start=1):
        folder = repo / rel
        if not folder.is_dir():
            continue
        index = 0
        for path in sorted(folder.glob("*.md")):
            if path.stem.upper() in {"TEMPLATE", "README"}:
                continue
            try:
                note = load_note(path, rel)
            except (ValueError, yaml.YAMLError) as exc:
                raise ValueError(f"{path}: {exc}") from exc
            index += 1
            note.number = f"{chapter}-{index}"
            notes.append(note)
    return notes


# ----------------------------------------------------------------------------
# Rendering one note
# ----------------------------------------------------------------------------


def _letter(k: int) -> str:
    return chr(ord("a") + (k - 1) % 26)


def render_note(note: Note) -> None:
    """Render Markdown to HTML with manual numbering, boxes, figures, change bars."""
    md = markdown.Markdown(extensions=["tables", "fenced_code", "attr_list", "sane_lists"])
    body = md.convert(re.sub(r"^([ \t]*)>(?=\S)", r"\1\\>", note.body_md, flags=re.MULTILINE))
    # Drop the leading h1: the note header carries the title.
    body = re.sub(r"\A\s*<h1>.*?</h1>", "", body, count=1, flags=re.DOTALL)

    # Numbered paragraphs: h2 -> N-M.k, h3 -> N-M.k<letter>.
    paragraphs: list[tuple[str, str, str]] = []
    k = 0
    sub = 0

    def number_heading(m: re.Match[str]) -> str:
        nonlocal k, sub
        level, text = m.group(1), m.group(2)
        if level == "2":
            k += 1
            sub = 0
            num = f"{note.number}.{k}"
        else:
            sub += 1
            num = f"{note.number}.{max(k, 1)}{_letter(sub)}"
        hid = "p" + num
        paragraphs.append((num, hid, _strip_tags(text)))
        return f'<h{level} id="{hid}"><span class="pnum">{num}</span>{text}</h{level}>'

    body = HEADING_RE.sub(number_heading, body)

    # Figures (Mermaid) and tables get manual-style labels.
    fig_n = 0

    def figure(m: re.Match[str]) -> str:
        nonlocal fig_n
        fig_n += 1
        code = html.unescape(m.group(1))
        # Diagram classes become the manual's two emphasis marks; page CSS colours them.
        names: dict[str, str] = {}

        def classdef(cd: re.Match[str]) -> str:
            mark = names.setdefault(cd.group(2), f"mk{min(len(names) + 1, 3)}")
            return f"{cd.group(1)}classDef {mark} stroke-width:1px"

        code = re.sub(r"^(\s*)classDef (\w+) [^\n]+", classdef, code, flags=re.MULTILINE)
        for old, new in names.items():
            code = re.sub(rf"^(\s*class [\w,]+ ){old}\s*$", rf"\g<1>{new}", code, flags=re.MULTILINE)
            code = code.replace(f":::{old}", f":::{new}")
        return (
            f'<figure class="fig"><pre class="mermaid">{code}</pre>'
            f"<figcaption>Figure {note.number}-{fig_n}</figcaption></figure>"
        )

    body = MERMAID_RE.sub(figure, body)
    tbl_n = 0

    def table_open(_m: re.Match[str]) -> str:
        nonlocal tbl_n
        tbl_n += 1
        return f'<figure class="tbl"><figcaption>Table {note.number}-{tbl_n}</figcaption><div class="tablewrap"><table>'

    body = re.sub(r"<table>", table_open, body)
    body = body.replace("</table>", "</table></div></figure>")

    # Blockquotes become ruled NOTE / WARNING / CAUTION boxes.
    def box(m: re.Match[str]) -> str:
        inner = m.group(1)
        plain = _strip_tags(inner).strip().lower()
        label = "NOTE"
        for word in ("warning", "danger", "caution"):
            if plain.startswith(word):
                label = word.upper()
                break
        return f'<div class="box" role="note"><span class="boxlabel">{label}</span>{inner}</div>'

    body = re.sub(r"<blockquote>(.*?)</blockquote>", box, body, flags=re.DOTALL)

    # Task list items become real checkboxes, persisted per note in the browser.
    task_n = 0

    def task(m: re.Match[str]) -> str:
        nonlocal task_n
        task_n += 1
        checked = " checked" if m.group(1).lower() == "x" else ""
        key = f"{note.anchor}-t{task_n}"
        return f'<li class="task"><label><input type="checkbox" data-key="{key}"{checked}><span>'

    body = TASK_RE.sub(task, body)
    body = re.sub(
        r'(<li class="task"><label><input[^>]*><span>)(.*?)</li>', r"\1\2</span></label></li>", body, flags=re.DOTALL
    )

    # Unverified claims: mark the phrase and add a change bar to the block.
    body = re.sub(
        r"\((?:from field, )?unverified\)",
        lambda m: f'<span class="unv">{m.group(0)[1:-1]}</span>',
        body,
        flags=re.IGNORECASE,
    )
    for tag in BLOCK_TAGS:
        body = re.sub(
            rf"<{tag}(?![^>]*class=)([^>]*)>((?:(?!</{tag}>).)*?<span class=\"unv\">)",
            rf'<{tag} class="chg"\1>\2',
            body,
            flags=re.DOTALL,
        )
    body = re.sub(r'(?<![="\'>/\w])(https?://[^\s<]*[^\s<.,;:)\]])', r'<a href="\1" class="url">\1</a>', body)
    note.body_html = body
    note.paragraphs = paragraphs


# ----------------------------------------------------------------------------
# Page assembly
# ----------------------------------------------------------------------------

CSS = r"""
:root{
  --paper:#F6F5F1; --ink:#161616; --ink-2:#4A4A47; --ink-3:#65645F; --rule:#9C9B95; --rule-2:#D3D2CB;
  --blue:#1D4CA0; --blue-soft:#DCE4F4; --field:#FCFBF9; --code:#EBEAE4; --sel:#C9D6F0;
  --gutter:2.25rem; --contents-w:17.5rem; --bar:3px;
  color-scheme:light;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --paper:#161616; --ink:#E5E4E0; --ink-2:#B3B2AC; --ink-3:#84837D; --rule:#5D5C58; --rule-2:#333330;
    --blue:#8FB0EC; --blue-soft:#1C2740; --field:#1D1D1C; --code:#232322; --sel:#2C3D62;
    color-scheme:dark;
  }
}
:root[data-theme="dark"]{
  --paper:#161616; --ink:#E5E4E0; --ink-2:#B3B2AC; --ink-3:#84837D; --rule:#5D5C58; --rule-2:#333330;
  --blue:#8FB0EC; --blue-soft:#1C2740; --field:#1D1D1C; --code:#232322; --sel:#2C3D62;
  color-scheme:dark;
}
*{box-sizing:border-box}
[hidden]{display:none!important}
html{scroll-behavior:smooth;scroll-padding-top:4.5rem}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 "B612","Helvetica Neue",Arial,sans-serif;caret-color:var(--blue);-webkit-font-smoothing:antialiased}
::selection{background:var(--sel);color:var(--ink)}
a{color:var(--blue);text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:.18em;text-decoration-color:color-mix(in srgb,var(--blue) 45%,transparent)}
a:hover{text-decoration-color:currentColor}
a.url,.body code{overflow-wrap:anywhere}
a.dead{color:var(--ink-2);text-decoration-style:dotted}
:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
*{scrollbar-width:thin;scrollbar-color:var(--rule) transparent}
.mono,.pnum,.num,figcaption,.meta,.boxlabel,.hdr-right,.contents h2,.tag,code,kbd{font-family:"B612 Mono",ui-monospace,"SF Mono",Menlo,monospace}

/* Running header */
.hdr{position:sticky;top:0;z-index:5;background:var(--paper);border-bottom:1px solid var(--ink);display:grid;grid-template-columns:var(--contents-w) minmax(0,1fr) auto;align-items:center;gap:1rem;padding:.55rem 1.25rem;min-height:3.4rem}
.hdr-left{display:flex;flex-direction:column;line-height:1.15}
.hdr-left .t{font-weight:700;font-size:13px;letter-spacing:.12em;text-transform:uppercase}
.hdr-left .s{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-2);white-space:nowrap}
.nowrap{white-space:nowrap}
.search{width:100%;max-width:34rem;justify-self:center;display:flex;align-items:center;gap:.5rem;border-bottom:1px solid var(--rule);padding:.15rem 0}
.search label{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-2);white-space:nowrap}
.search input{flex:1;border:0;background:transparent;color:var(--ink);font:14px "B612","Helvetica Neue",Arial,sans-serif;padding:.25rem 0;min-width:0}
.search input::placeholder{color:var(--ink-3)}
.search input:focus{outline:none}
.search kbd{font-size:10px;color:var(--ink-3);border:1px solid var(--rule-2);border-radius:2px;padding:0 .3em}
.hdr-right{text-align:right;font-size:12px;line-height:1.3;color:var(--ink-2);display:flex;flex-direction:column;align-items:flex-end;gap:.15rem}
.hdr-right #cur{color:var(--ink);font-weight:700;max-width:26rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hdr-right #resume[hidden]{display:none}
.contents-toggle{display:none}

/* Page grid */
.page{display:grid;grid-template-columns:var(--contents-w) minmax(0,1fr);max-width:1240px;margin:0 auto;padding:0 1.25rem}
.contents{position:sticky;top:3.4rem;align-self:start;max-height:calc(100vh - 3.4rem);overflow-y:auto;padding:1.25rem 1.25rem 3rem 0;border-right:1px solid var(--rule-2);font-size:13.5px}
.contents h2{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--ink);margin:1.3rem 0 .35rem;padding-bottom:.25rem;border-bottom:1px solid var(--rule)}
.contents h2:first-child{margin-top:0}
.contents h2 .rsv{font-weight:400;color:var(--ink-3);margin-left:.5em}
.contents ol{list-style:none;margin:0;padding:0}
.contents li{margin:0}
.contents li.hidden{display:none}
.contents li>a{display:grid;grid-template-columns:2.9rem minmax(0,1fr) auto;gap:.5rem;padding:.22rem 0;color:var(--ink);text-decoration:none;line-height:1.3}
.contents li>a:hover .t{text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:.18em}
.contents li.active>a{font-weight:700}
.contents .num{color:var(--ink-2);font-size:12px;padding-top:.1em}
.contents .cnt{font-size:11px;color:var(--ink-3);padding-top:.15em}
.contents ol.paras{display:none;margin:.1rem 0 .5rem;border-left:1px solid var(--rule-2);padding-left:.6rem}
.contents li.active ol.paras,.contents li.searching ol.paras{display:block}
.contents ol.paras a{grid-template-columns:3.6rem minmax(0,1fr);font-size:12.5px;color:var(--ink-2);padding:.12rem 0}
.contents ol.paras a .num{font-size:11px}
.contents .empty{color:var(--ink-3);font-size:12px;padding:.2rem 0}

/* Manual body */
.manual{padding:1.5rem 0 6rem 2.25rem;min-width:0}
.chapter{margin:0 0 .5rem}
.chapter-h{margin:3.5rem 0 1.5rem;padding-bottom:.4rem;border-bottom:2px solid var(--ink);display:flex;align-items:baseline;gap:1rem}
.chapter-h:first-child{margin-top:0}
.chapter-h .chnum{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-2);white-space:nowrap}
.chapter-h h2{margin:0;font-size:20px;font-weight:700;letter-spacing:.02em;text-transform:uppercase}
.chapter .reserved{color:var(--ink-3);font-size:13px;margin:0 0 2rem}

article.note{position:relative;max-width:70ch;padding-right:var(--gutter);margin:0 0 4rem}
article.note.hidden{display:none}
.note-h{margin:0 0 1.2rem;padding-bottom:.6rem;border-bottom:1px solid var(--ink)}
.note-h h2{margin:0;font-size:22px;line-height:1.2;font-weight:700;text-wrap:balance}
.note-h h2 .pnum{margin-right:.6em;font-weight:400;font-size:18px;color:var(--ink-2)}
.meta{display:flex;flex-wrap:wrap;gap:0 1.25rem;margin-top:.45rem;font-size:11.5px;letter-spacing:.04em;text-transform:uppercase;color:var(--ink-2)}
.meta .st{color:var(--ink)}
.meta .st.reviewed::before{content:"";display:inline-block;width:.55em;height:.55em;background:var(--ink);margin-right:.45em;vertical-align:baseline}
.meta .st.draft::before{content:"";display:inline-block;width:.5em;height:.5em;border:1px solid var(--ink);margin-right:.45em;vertical-align:baseline}
.meta .st.stale{text-decoration:line-through}
.meta .path{color:var(--ink-3);text-transform:none;letter-spacing:0}
.tags{display:flex;flex-wrap:wrap;gap:.25rem .8rem;margin:.35rem 0 0;font-size:11.5px;color:var(--ink-3)}

.body h2{font-size:15px;font-weight:700;margin:2rem 0 .5rem;line-height:1.35;text-transform:uppercase;letter-spacing:.02em}
.body h3{font-size:15px;font-weight:700;margin:1.4rem 0 .35rem;line-height:1.35}
.body h4{font-size:14px;font-weight:700;margin:1.1rem 0 .3rem;color:var(--ink-2)}
.pnum{display:inline-block;min-width:3.2em;margin-right:.6em;font-weight:400;color:var(--ink-2);font-size:.92em}
.body h3 .pnum{min-width:3.6em}
.body p{margin:.55rem 0}
.body ul,.body ol{margin:.5rem 0;padding-left:1.4rem}
.body li{margin:.2rem 0}
.body li.task{list-style:none;margin-left:-1.4rem}
.body li.task label{display:grid;grid-template-columns:1.1rem 1fr;gap:.55rem;align-items:start;cursor:pointer}
.body li.task input{appearance:none;width:.95rem;height:.95rem;margin:.28em 0 0;border:1px solid var(--ink);background:var(--field);border-radius:0;display:grid;place-content:center}
.body li.task input:checked::before{content:"";width:.5rem;height:.5rem;background:var(--ink)}
.body li.task input:checked+span{color:var(--ink-2);text-decoration:line-through}
.body hr{border:0;border-top:1px solid var(--rule);margin:1.5rem 0}
.body code{font-size:13px;background:var(--code);padding:.05em .35em;border-radius:2px}
.body pre{background:var(--code);border-left:1px solid var(--rule);padding:.8rem 1rem;overflow-x:auto;font-size:12.5px;line-height:1.5;margin:.8rem 0}
.body pre code{background:none;padding:0;font-size:inherit}
.body img{max-width:100%}
.body strong{font-weight:700}

.box{border:1px solid var(--ink);padding:.7rem .9rem .6rem;margin:1rem 0;position:relative}
.box .boxlabel{position:absolute;top:-.6em;left:.7rem;background:var(--paper);padding:0 .4em;font-size:11px;font-weight:700;letter-spacing:.14em}
.box p{margin:.3rem 0}
.box p:first-of-type{margin-top:0}

figure{margin:1.1rem 0}
figcaption{font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-2);margin:0 0 .3rem}
figure.fig{border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:.6rem 0 .4rem}
figure.fig figcaption{margin:.5rem 0 0}
figure.fig pre.mermaid{margin:0;background:transparent;border:0;padding:0;text-align:center;overflow-x:auto}
figure.fig svg g.mk1>rect,figure.fig svg g.mk1>polygon,figure.fig svg g.mk1>circle,figure.fig svg g.mk1>path{fill:var(--blue-soft)!important;stroke:var(--blue)!important}
figure.fig svg g.mk2>rect,figure.fig svg g.mk2>polygon,figure.fig svg g.mk2>circle,figure.fig svg g.mk2>path{fill:var(--paper)!important;stroke:var(--ink)!important;stroke-width:2px!important}
figure.fig svg g.mk3>rect,figure.fig svg g.mk3>polygon,figure.fig svg g.mk3>circle,figure.fig svg g.mk3>path{fill:var(--code)!important;stroke:var(--rule)!important}
figure.fig svg .nodeLabel,figure.fig svg .edgeLabel{color:var(--ink)!important;font-family:"B612",Arial,sans-serif!important}
.tablewrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;border-top:1px solid var(--ink);border-bottom:1px solid var(--ink);font-size:13.5px;line-height:1.4;font-variant-numeric:tabular-nums}
th{text-align:left;font-weight:700;padding:.4rem .6rem .35rem;border-bottom:1px solid var(--ink);vertical-align:bottom}
td{padding:.35rem .6rem;border-bottom:1px solid var(--rule-2);vertical-align:top}
tr:last-child td{border-bottom:0}
th:first-child,td:first-child{padding-left:.2rem}
th:last-child,td:last-child{padding-right:.2rem}

/* Change bars and unverified marks */
.unv{font-size:.82em;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-2);white-space:nowrap}
.unv::before{content:"†";margin-right:.2em}
.chg{position:relative}
p.chg::before,li.chg::before,figure.tbl .rowbar{content:"";position:absolute;top:.2em;bottom:.2em;right:calc(-1 * var(--gutter) + .6rem);width:var(--bar);background:var(--ink)}
figure.tbl{position:relative}
figure.tbl .rowbar{top:auto;bottom:auto;display:block}
.chg-key{font-size:12px;color:var(--ink-2);margin:0 0 1rem;display:flex;align-items:center;gap:.6rem}
.chg-key i{display:inline-block;width:var(--bar);height:1.1em;background:var(--ink)}

/* Jump moment: the numbered heading you arrived at underlines, then fades. */
.body .hit .pnum{text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:.2em}
.body .hidden{display:none}
:target .pnum{text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:.2em;text-decoration-color:var(--ink);animation:arrive 2.4s cubic-bezier(.16,1,.3,1) forwards}
@keyframes arrive{0%,60%{text-decoration-color:var(--ink)}100%{text-decoration-color:transparent}}
@media (prefers-reduced-motion:reduce){.body .hit .pnum{text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:.2em}
.body .hidden{display:none}
:target .pnum{animation:none}}

.index-note{font-size:13px;color:var(--ink-2);max-width:70ch}
.index{columns:3;column-gap:2.5rem;font-size:13px;line-height:1.45;margin:1rem 0 0}
.index dt{font-weight:700;break-after:avoid}
.index dd{margin:0 0 .35rem;font-family:"B612 Mono",ui-monospace,monospace;font-size:12px;color:var(--ink-2)}
.index dd a{color:var(--blue);text-decoration:none}
.index dd a:hover{text-decoration:underline}
@media (max-width:1100px){.index{columns:2}}
@media (max-width:700px){.index{columns:1}}
.colophon{margin-top:4rem;padding-top:.6rem;border-top:1px solid var(--ink);font-size:12px;color:var(--ink-2);display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}
.nomatch{display:none;color:var(--ink-2);font-size:14px;margin:2rem 0}
.nomatch.show{display:block}

@media (max-width:920px){
  .hdr{grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"left right" "search search";padding:.5rem .9rem;gap:.4rem .8rem}
  .hdr>*{min-width:0}
  .hdr-left .s{white-space:normal}
  .search kbd{display:none}
  .hdr-right #cur{display:none}
  .hdr-left{grid-area:left}.hdr-right{grid-area:right}.search{grid-area:search;max-width:none}
  .contents-toggle{display:inline-block;background:none;border:1px solid var(--ink);color:var(--ink);font:11px "B612 Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;padding:.3rem .55rem;cursor:pointer;border-radius:0}
  .contents-toggle[aria-expanded="true"]{background:var(--ink);color:var(--paper)}
  .page{grid-template-columns:1fr;padding:0 .9rem}
  .contents{display:none;position:static;max-height:none;border-right:0;border-bottom:1px solid var(--rule);padding:1rem 0}
  .contents.open{display:block}
  .manual{padding:1.2rem 0 4rem}
  article.note{padding-right:0;padding-left:.9rem;max-width:none}
  p.chg::before,li.chg::before{right:auto;left:-.9rem}
  li.chg::before{left:-2.3rem}
  figure.tbl .rowbar{right:auto;left:-.9rem}
  .note-h h2{font-size:19px}
  html{scroll-padding-top:7rem}
  .chapter-h{flex-direction:column;gap:.15rem;align-items:flex-start}
}
"""

JS = r"""
(function(){
  var q=document.getElementById('q');
  var notes=[].slice.call(document.querySelectorAll('article.note'));
  var rows=[].slice.call(document.querySelectorAll('.contents li[data-search]'));
  var nomatch=document.getElementById('nomatch');
  var cur=document.getElementById('cur');
  var resume=document.getElementById('resume');
  var toggle=document.getElementById('contents-toggle');
  var contents=document.getElementById('contents');
  function store(k,v){try{localStorage.setItem(k,v)}catch(e){}}
  function load(k){try{return localStorage.getItem(k)}catch(e){return null}}

  // Index each note body by paragraph: every element belongs to the numbered heading above it.
  var paras=[];  // {note, id, num, els:[], text}
  notes.forEach(function(a){
    var body=a.querySelector('.body'); var cur=null;
    [].slice.call(body.children).forEach(function(el){
      if(/^H[23]$/.test(el.tagName)&&el.id){cur={note:a,id:el.id,num:el.querySelector('.pnum').textContent,head:el,els:[el],text:''};paras.push(cur);}
      else if(cur){cur.els.push(el);}
      else{cur={note:a,id:null,num:'',head:null,els:[el],text:''};paras.push(cur);}
    });
  });
  paras.forEach(function(pg){pg.text=pg.els.map(function(e){return e.textContent;}).join(' ').toLowerCase();});
  var paraRows={}; [].slice.call(document.querySelectorAll('.contents ol.paras li')).forEach(function(li){var h=li.querySelector('a').getAttribute('href').slice(1);paraRows[h]=li;});

  // Search: notes and paragraphs filter together; the first hit is jumped to; hits mark their numbers.
  var typed=false;
  function apply(){
    var s=q.value.trim().toLowerCase(), shown=0, first=null;
    notes.forEach(function(a){a.dataset.hits='0';});
    paras.forEach(function(pg){
      var hit=!s||pg.text.indexOf(s)>=0;
      pg.els.forEach(function(e){e.classList.toggle('hidden',!hit);});
      if(pg.head)pg.head.classList.toggle('hit',!!s&&hit);
      if(hit){pg.note.dataset.hits=String(+pg.note.dataset.hits+1);if(s&&pg.head&&!first)first=pg.head;}
      if(pg.id&&paraRows[pg.id])paraRows[pg.id].classList.toggle('hidden',!hit);
    });
    notes.forEach(function(a){var hit=!s||+a.dataset.hits>0;a.classList.toggle('hidden',!hit);});
    rows.forEach(function(li){var note=document.getElementById(li.dataset.note);var hit=!note.classList.contains('hidden');li.classList.toggle('hidden',!hit);li.classList.toggle('searching',!!s&&hit);if(hit)shown++;});
    nomatch.classList.toggle('show',!!s&&shown===0);
    [].slice.call(document.querySelectorAll('.contents h2[data-chapter]')).forEach(function(h){
      var ol=h.nextElementSibling; var any=!s||(ol&&ol.tagName==='OL'&&[].slice.call(ol.children).some(function(li){return !li.classList.contains('hidden');}));
      h.hidden=!any; if(ol&&ol.tagName==='OL')ol.hidden=!any;
    });
    [].slice.call(document.querySelectorAll('section.chapter')).forEach(function(sec){
      var any=!s||[].slice.call(sec.querySelectorAll('article.note')).some(function(a){return !a.classList.contains('hidden');});
      sec.hidden=!any;
    });
    store('rll-q',q.value);
    if(typed&&first){var hh=document.querySelector('.hdr').offsetHeight+10;var y=first.getBoundingClientRect().top+window.scrollY-hh;window.scrollTo({top:y,behavior:'auto'});}
    else if(typed&&!s){window.scrollTo({top:0,behavior:'auto'});}
  }
  q.addEventListener('input',function(){typed=true;apply();});
  var saved=load('rll-q'); if(saved){q.value=saved;} apply();
  document.addEventListener('keydown',function(e){if(e.key==='/'&&document.activeElement!==q){e.preventDefault();q.focus();q.select();}if(e.key==='Escape'&&document.activeElement===q){q.value='';typed=true;apply();q.blur();}});

  // Contents toggle on narrow screens.
  if(toggle){toggle.addEventListener('click',function(){var open=contents.classList.toggle('open');toggle.setAttribute('aria-expanded',open?'true':'false');});
    contents.addEventListener('click',function(e){if(e.target.closest('a')&&window.innerWidth<=920){contents.classList.remove('open');toggle.setAttribute('aria-expanded','false');}});}

  // Running header follows the note in view; contents expands the active note.
  var byId={}; rows.forEach(function(li){byId[li.dataset.note]=li;});
  var active=null;
  function setActive(a){
    if(!a||a===active)return; active=a;
    rows.forEach(function(li){li.classList.toggle('active',li.dataset.note===a.id);});
    cur.textContent=a.dataset.number+'  '+a.dataset.title;
  }
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(entries){
      var best=null; entries.forEach(function(en){if(en.isIntersecting&&(!best||en.boundingClientRect.top<best.boundingClientRect.top))best=en;});
      if(best)setActive(best.target);
    },{rootMargin:'-56px 0px -70% 0px',threshold:0});
    notes.forEach(function(a){io.observe(a);});
  }

  // Remember the paragraph you last read; offer it on return.
  var heads=[].slice.call(document.querySelectorAll('.body h2[id], .body h3[id]'));
  var last=load('rll-last');
  if(last){var el=document.getElementById(last);if(el){resume.href='#'+last;resume.textContent='Resume at '+el.querySelector('.pnum').textContent;resume.hidden=false;}}
  var t=null;
  window.addEventListener('scroll',function(){
    if(t)return; t=setTimeout(function(){t=null;var y=60,pick=null;for(var i=0;i<heads.length;i++){var r=heads[i].getBoundingClientRect();if(r.top<=y)pick=heads[i];else break;}if(pick)store('rll-last',pick.id);},400);
  },{passive:true});

  // Table-row change bars are drawn from the figure so a wide, scrolling table cannot hide them.
  function placeRowBars(){
    [].slice.call(document.querySelectorAll('figure.tbl')).forEach(function(fig){
      [].slice.call(fig.querySelectorAll('.rowbar')).forEach(function(b){b.remove();});
      var fr=fig.getBoundingClientRect();
      [].slice.call(fig.querySelectorAll('tr.chg')).forEach(function(tr){
        var r=tr.getBoundingClientRect(); if(!r.height)return;
        var bar=document.createElement('i'); bar.className='rowbar'; bar.style.top=(r.top-fr.top+3)+'px'; bar.style.height=Math.max(r.height-6,4)+'px'; fig.appendChild(bar);
      });
    });
  }
  placeRowBars();
  if(document.fonts&&document.fonts.ready)document.fonts.ready.then(placeRowBars);
  var rt=null; window.addEventListener('resize',function(){if(rt)return;rt=setTimeout(function(){rt=null;placeRowBars();},150);});
  q.addEventListener('input',function(){setTimeout(placeRowBars,0);});

  // Checklists persist per box.
  [].slice.call(document.querySelectorAll('input[type=checkbox][data-key]')).forEach(function(cb){
    var v=load('rll-cb-'+cb.dataset.key); if(v==='1')cb.checked=true; if(v==='0')cb.checked=false;
    cb.addEventListener('change',function(){store('rll-cb-'+cb.dataset.key,cb.checked?'1':'0');});
  });
})();
"""


def build_contents(notes: list[Note]) -> str:
    """Contents column: chapters, numbered notes, expandable paragraph lists."""
    out: list[str] = []
    for chapter, (rel, label) in enumerate(SECTIONS, start=1):
        sec = [n for n in notes if n.section == rel]
        if not sec:
            out.append(
                f'<h2 data-chapter="{chapter}" data-reserved="1">Chapter {chapter} <span class="rsv">{_esc(label)} (reserved)</span></h2>'
            )
            continue
        out.append(f'<h2>Chapter {chapter} <span class="rsv">{_esc(label)}</span></h2><ol>')
        for n in sec:
            search = " ".join([n.number, n.title, *n.tags, n.status, _strip_tags(n.body_html)]).lower()[:6000]
            cnt = f'<span class="cnt">†{n.n_unverified}</span>' if n.n_unverified else "<span></span>"
            paras = "".join(
                f'<li><a href="#{hid}"><span class="num">{_esc(num)}</span><span class="t">{_esc(text)}</span></a></li>'
                for num, hid, text in n.paragraphs
                if "." in num and not num[-1].isalpha()
            )
            out.append(
                f'<li data-note="{n.anchor}" data-search="{_esc(search)}">'
                f'<a href="#{n.anchor}"><span class="num">{n.number}</span><span class="t">{_esc(n.title)}</span>{cnt}</a>'
                f'<ol class="paras">{paras}</ol></li>'
            )
        out.append("</ol>")
    out.append(
        '<h2>Index</h2><ol><li data-search="index terms" data-note="index"><a href="#index"><span class="num">A-Z</span><span class="t">Terms and paragraph addresses</span><span></span></a></li></ol>'
    )
    return "".join(out)


def build_note(n: Note) -> str:
    """One note as a numbered manual entry."""
    rel = n.path.relative_to(REPO)
    search = " ".join([n.number, n.title, *n.tags, n.status, _strip_tags(n.body_html)]).lower()
    meta = [
        f'<span class="st {n.status}">{STATUS_LABEL.get(n.status, n.status)}</span>',
        f"<span>Rev {_esc(n.date)}</span>" if n.date else "",
        f"<span>{n.n_sources} sources</span>",
        f"<span>†{n.n_unverified} unverified</span>" if n.n_unverified else "",
        f'<span class="path">{_esc(str(rel))}</span>',
    ]
    tags = " ".join(f'<span class="tag">{_esc(t)}</span>' for t in n.tags)
    return (
        f'<article class="note" id="{n.anchor}" data-number="{n.number}" data-title="{_esc(n.title)}" data-search="{_esc(search[:6000])}">'
        f'<header class="note-h"><h2><span class="pnum">{n.number}</span>{_esc(n.title)}</h2>'
        f'<div class="meta">{"".join(m for m in meta if m)}</div>'
        + (f'<div class="tags">{tags}</div>' if tags else "")
        + f'</header><div class="body">{n.body_html}</div></article>'
    )


def resolve_note_links(notes: list[Note]) -> None:
    """Rewrite relative Markdown links between notes into in-page anchors."""
    by_path = {n.path.resolve(): n for n in notes}

    def rewrite(note: Note) -> None:
        def repl(m: re.Match[str]) -> str:
            href = html.unescape(m.group(1))
            base = href.partition("#")[0]
            if not base.endswith(".md") or base.startswith(("http://", "https://")):
                return m.group(0)
            target = by_path.get((note.path.parent / base).resolve())
            if target is None:
                return f'<a href="{m.group(1)}" class="dead" title="Not in this manual">'
            return f'<a href="#{target.anchor}">'

        note.body_html = re.sub(r'<a href="([^"]+)">', repl, note.body_html)

        def xref(m: re.Match[str]) -> str:
            target = by_path.get((REPO / m.group(1)).resolve())
            if target is None:
                return m.group(0)
            return f'<a href="#{target.anchor}">{target.number} {_esc(target.title)}</a>'

        note.body_html = re.sub(
            r"<code>((?:sops|library|experiments|field-notes)/[\w./-]+\.md)</code>", xref, note.body_html
        )

    for n in notes:
        rewrite(n)


TERM_RE = re.compile(
    r"(?<![\w/.-])(?:[A-Z][A-Za-z0-9]*[A-Z0-9][A-Za-z0-9]*|[a-z]+_[a-z0-9_]+|[A-Z]{2,}(?:[ -]?[0-9][A-Za-z0-9.]*)?|π0(?:\.5)?)(?![\w/])"
)
TERM_STOP = {
    "OK",
    "NOTE",
    "WARNING",
    "TODO",
    "PDF",
    "URL",
    "HTML",
    "CSV",
    "JSON",
    "YAML",
    "GitHub",
    "II",
    "III",
    "IV",
    "AND",
    "OR",
    "THE",
}
INDEX_MAX_REFS = 10


def _address_key(hid: str) -> tuple[int, int, int, str]:
    """Sort key for a paragraph id like p2-3.1a: chapter, entry, paragraph, letter."""
    m = re.match(r"p(\d+)-(\d+)(?:\.(\d+)([a-z]*))?", hid)
    if not m:
        return (999, 0, 0, hid)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0), m.group(4) or "")


def build_index(notes: list[Note]) -> str:
    """Back-of-book index: term to paragraph addresses, derived from the note bodies."""
    hits: dict[str, dict[str, int]] = {}
    for n in notes:
        chunks = re.split(r'(?=<h[23] id=")', n.body_html)
        for chunk in chunks:
            m = re.match(r'<h[23] id="([^"]+)">', chunk)
            if not m:
                continue
            hid = m.group(1)
            text = _strip_tags(re.sub(r"<pre.*?</pre>|<code>.*?</code>", " ", chunk, flags=re.DOTALL))
            text = re.sub(r"https?://\S+", " ", text)
            for t in set(TERM_RE.findall(text)):
                if t in TERM_STOP or len(t) < 3 or t.endswith("_"):
                    continue
                hits.setdefault(t, {})[hid] = hits.setdefault(t, {}).get(hid, 0) + 1
    entries: list[tuple[str, list[str]]] = []
    for term, refs in hits.items():
        if len(refs) < 2:
            continue
        ordered = sorted(refs, key=lambda h: (-refs[h], h))[:INDEX_MAX_REFS]
        entries.append((term, sorted(ordered, key=_address_key)))
    entries.sort(key=lambda e: e[0].lower())
    out = [
        '<section class="chapter" id="index"><div class="chapter-h"><span class="chnum">Index</span><h2>Terms and paragraph addresses</h2></div>',
        f'<p class="index-note">{len(entries)} terms that appear in two or more paragraphs, listed with up to {INDEX_MAX_REFS} addresses each, most frequent first within a note. Built from the text; not hand-curated.</p>',
        '<dl class="index">',
    ]
    for term, addrs in entries:
        links = ", ".join(f'<a href="#{h}">{_esc(h[1:])}</a>' for h in addrs)
        out.append(f"<dt>{_esc(term)}</dt><dd>{links}</dd>")
    out.append("</dl></section>")
    return "".join(out)


def build_page(notes: list[Note], *, artifact: bool, built: str) -> str:
    """Assemble the complete HTML document."""
    for n in notes:
        if not n.body_html:
            render_note(n)
    resolve_note_links(notes)
    chapters: list[str] = []
    for chapter, (rel, label) in enumerate(SECTIONS, start=1):
        sec = [n for n in notes if n.section == rel]
        chapters.append(
            f'<section class="chapter" id="ch{chapter}"><div class="chapter-h">'
            f'<span class="chnum">Chapter {chapter}</span><h2>{_esc(label)}</h2></div>'
        )
        if sec:
            chapters.extend(build_note(n) for n in sec)
        else:
            chapters.append('<p class="reserved">Reserved. No entries yet.</p>')
        chapters.append("</section>")
    n_unv = sum(n.n_unverified for n in notes)
    mermaid = (
        ""
        if artifact
        else '<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/11.12.0/mermaid.min.js"></script>'
        "<script>var _t=document.documentElement.dataset.theme;mermaid.initialize({startOnLoad:true,theme:(_t==='dark'||(!_t&&matchMedia('(prefers-color-scheme: dark)').matches))?'dark':'neutral',"
        "themeVariables:{fontFamily:'B612, Arial, sans-serif'}});</script>"
    )
    return f"""<title>{_esc(MANUAL_TITLE)}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=B612:ital,wght@0,400;0,700;1,400&family=B612+Mono:wght@400;700&display=swap">
<style>{CSS}</style>
<header class="hdr">
  <div class="hdr-left"><span class="t">{_esc(MANUAL_TITLE)}</span><span class="s">Technical manual · <span class="nowrap">Change {_esc(built)}</span></span></div>
  <form class="search" role="search" onsubmit="return false"><label for="q">Index</label><input id="q" type="search" placeholder="Search paragraphs" autocomplete="off"><kbd>/</kbd></form>
  <div class="hdr-right"><span id="cur">{notes[0].number if notes else ""}  {_esc(notes[0].title) if notes else ""}</span><a id="resume" href="#" hidden>Resume</a><button class="contents-toggle" id="contents-toggle" aria-expanded="false" aria-controls="contents">Contents</button></div>
</header>
<div class="page">
<nav class="contents" id="contents" aria-label="Contents">{build_contents(notes)}</nav>
<main class="manual">
<p class="chg-key"><i></i>Change bar in the margin marks a claim tagged unverified. {n_unv} marked in this change.</p>
<p class="nomatch" id="nomatch">No paragraph matches. Clear the index field with Escape.</p>
{"".join(chapters)}
{build_index(notes)}
<footer class="colophon"><span>Built {_esc(built)} from {len(notes)} notes by tools/build_site.py.</span><span>Reviewed entries carry a filled mark; draft entries an open one.</span></footer>
</main>
</div>
<script>{JS}</script>
{mermaid}
"""


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=REPO / "site" / "index.html")
    parser.add_argument("--artifact", action="store_true", help="omit the Mermaid script tag (host renders diagrams)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    notes = collect_notes(REPO)
    built = date.today().isoformat()
    page = build_page(notes, artifact=args.artifact, built=built)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    logger.info("wrote %s (%d notes, %d bytes)", args.out, len(notes), len(page.encode()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
