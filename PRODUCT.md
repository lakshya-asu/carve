# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

One user: a robot learning expert who started a forward-deployed robot
learning engineer role in September 2026. They know the field; the site is
their working reference, not a tutorial. They read the site on a
laptop at a desk during study passes, on a laptop next to a robot on site
with hands busy, and on a phone. Nobody else reads it.

## Product Purpose

A personal knowledge base for robot learning field work: SOPs, sourced topic
notes, hardware notes, field logs, and experiment records. The site is a
rendered view of the Markdown library in this repo, rebuilt by
`tools/build_site.py`. Success is finding a specific fact fast: a camera spec,
a hyperparameter, a checklist item, a gotcha. Reading a whole topic and
tracking review status are secondary.

## Positioning

Every claim links a primary source or is tagged unverified. Notes carry the
trial counts, hardware, and dates behind their numbers. The site is generated
from the notes, so it is never out of date relative to the repo.

## Operating Context

- Daily loop: make things work in simulation first every day, then on the
  real robot the next time the user is in the office.
- The user has strong opinions on how systems should work and wants to see
  and approve changes before they land.
- Field days follow `sops/field-deployment-checklist.md`; data collection,
  experiments, and code review each have an SOP.
- The user also runs a separate machine with a local assistant and local
  models for building; this site is read there too.
- Notes are Markdown with YAML front matter (`title`, `date`, `tags`,
  `status` in draft, reviewed, stale). Sections are consistent across topic
  notes: What it is, Why it matters in the field, methods, recipe, gotchas,
  skills, open questions, related, sources.
- Mermaid diagrams live in the Markdown. The artifact host renders them
  natively; the local build loads Mermaid from a CDN.

## Capabilities and Constraints

- Single self-contained HTML file. No build framework, no server.
- Must render inside the Claude artifact host and as a local file. External
  scripts only from cdnjs, jsdelivr npm, cdn.tailwindcss.com, code.jquery.com;
  stylesheets only from fonts.googleapis.com.
- Must work in light and dark themes with the three-state theme contract
  (bare root, prefers-color-scheme guarded, data-theme stamps).
- Content volume today: 21 notes, about 3,300 lines, 447 distinct sources,
  around 65 claims tagged unverified. Will grow with every research pass.
- Client-side search over titles, tags, and body text is a hard requirement.
- Phone use means one-handed lookup must work; wide tables scroll in their
  own container.
- Generator is Python 3.11, `markdown` plus `pyyaml`, tested with pytest.

## Brand Commitments

None. No logo, no existing palette. The user has rejected one prior design as
"AI slop": a docs-dashboard template with KPI tiles, cards with shadows on
every block, decorative pills, and charts of meta-metrics such as lines per
note. Treat that as the anti-reference. Global rules in
`~/.claude/CLAUDE.md` ban a list of design defaults.

## Evidence on Hand

- All content is real and in the repo: `sops/`, `library/`, `experiments/`,
  `field-notes/`.
- No images, logos, screenshots, or testimonials exist. Do not fabricate any.

## Product Principles

- Fact retrieval first. Every design decision is tested against "how fast
  can I find the D435i minimum range on a phone."
- Show the subject, never the meta. Visualize sensors, methods, and
  pipelines; never chart the notes themselves.
- Provenance is visible. Source links and unverified tags are first-class in
  the reading experience, not decoration.
- Generated, not hand-tuned. Anything the design needs must be derivable from
  the Markdown and front matter.
