---
name: brief
description: Build a good-looking single-page UI (artifact) about a topic, decision, comparison, or dataset, with real visualizations of the subject drawn from the library and sources. Use when the user wants something to look at, present, or share rather than read as prose.
user-invocable: true
argument-hint: "<topic or question> [--for <audience>]"
---

Produce a published artifact about `$ARGUMENTS`.

Rules:
1. Load the `artifact-design` skill, then `dataviz` if any chart is involved. Read `PRODUCT.md` and `DESIGN.md` in this repo: the brief inherits the manual's world (one typeface family, B612; paper, ink, rule, one blue; state as marks; no cards with shadows, no pills, no KPI tiles, no gradient hero) unless the user pins a different look for an external audience.
2. Visualize the subject, never the meta. Charts show sensor ranges, latencies, success rates with trial counts, timelines, architectures, decision tables. A chart of note counts is slop.
3. Every number on the page has a source and its condition (hardware, n, date). Pull from `library/` first; fetch primary sources for anything missing; tag unverified values visibly on the page.
4. Diagrams are inline SVG or Mermaid `<pre class="mermaid">` blocks; the artifact host renders Mermaid natively.
5. Write the HTML to the scratchpad, take one screenshot with the Playwright script pattern used in this repo (`rll` conda env, `env -u PYTHONPATH`), fix what it shows, publish with the Artifact tool. Use a distinctive page name as `<title>`.
6. If the user says "for the team" or "for the customer", load `library/topics/field-engineer-handbook.md` first and write for that reader.

Follow `~/.claude/CLAUDE.md` writing rules.
