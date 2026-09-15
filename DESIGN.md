---
name: Robot Learning Lab
description: A ring-bound equipment manual rendered from the Markdown library; every fact has a paragraph number, a source, and a change bar.
colors:
  paper: "#F6F5F1"
  ink: "#161616"
  ink-2: "#4A4A47"
  ink-3: "#65645F"
  rule: "#9C9B95"
  rule-2: "#D3D2CB"
  blue: "#1D4CA0"
  blue-soft: "#DCE4F4"
  field: "#FCFBF9"
  code: "#EBEAE4"
  sel: "#C9D6F0"
typography:
  body:
    fontFamily: "B612, Helvetica Neue, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  entry-title:
    fontFamily: "B612, Helvetica Neue, Arial, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "normal"
  chapter-title:
    fontFamily: "B612, Helvetica Neue, Arial, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.02em"
  paragraph-heading:
    fontFamily: "B612, Helvetica Neue, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "0.02em"
  sub-heading:
    fontFamily: "B612, Helvetica Neue, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "normal"
  address:
    fontFamily: "B612 Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "0.92em"
    fontWeight: 400
    lineHeight: 1.35
    letterSpacing: "normal"
  label:
    fontFamily: "B612 Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "0.12em"
  meta:
    fontFamily: "B612 Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "11.5px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "0.04em"
  caption:
    fontFamily: "B612 Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "11.5px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "0.06em"
  table:
    fontFamily: "B612, Helvetica Neue, Arial, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
  contents:
    fontFamily: "B612, Helvetica Neue, Arial, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.3
    letterSpacing: "normal"
  code:
    fontFamily: "B612 Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  none: "0"
  hairline: "2px"
spacing:
  bar: "3px"
  para: "0.55rem"
  figure: "1.1rem"
  box: "1rem"
  heading: "2rem"
  gutter: "2.25rem"
  chapter: "3.5rem"
  entry: "4rem"
  contents-w: "17.5rem"
  header-h: "3.4rem"
  page-max: "1240px"
  measure: "70ch"
components:
  running-header:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    padding: "0.55rem 1.25rem"
    height: "{spacing.header-h}"
  search-input:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "0.25rem 0"
  contents-link:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.contents}"
    padding: "0.22rem 0"
  contents-link-active:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.contents}"
    padding: "0.22rem 0"
  contents-toggle:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.3rem 0.55rem"
  contents-toggle-expanded:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.3rem 0.55rem"
  entry-header:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.entry-title}"
    padding: "0 0 0.6rem"
  box:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "0.7rem 0.9rem 0.6rem"
  box-label:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    padding: "0 0.4em"
  table:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.table}"
    width: "100%"
  table-cell:
    padding: "0.35rem 0.6rem"
  table-head:
    padding: "0.4rem 0.6rem 0.35rem"
  figure:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    padding: "0.6rem 0 0.4rem"
  task-checkbox:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    size: "0.95rem"
  code-inline:
    backgroundColor: "{colors.code}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    rounded: "{rounded.hairline}"
    padding: "0.05em 0.35em"
  code-block:
    backgroundColor: "{colors.code}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    rounded: "{rounded.none}"
    padding: "0.8rem 1rem"
  kbd:
    backgroundColor: "transparent"
    textColor: "{colors.ink-3}"
    rounded: "{rounded.hairline}"
    padding: "0 0.3em"
  change-bar:
    backgroundColor: "{colors.ink}"
    width: "{spacing.bar}"
  colophon:
    textColor: "{colors.ink-2}"
    padding: "0.6rem 0 0"
---

# Design System: Robot Learning Lab

<!-- Recorded from the shipped build (site/index.html, change 2026-09-05), generated by tools/build_site.py.
     The generator's CSS and JS string constants are the source of truth; anything it does not emit does not exist on the page. -->

## Overview

**Creative North Star: "The Ring-Bound Equipment Manual"**

The site is one HTML file laid out as an equipment technical manual, and it refuses the docs-site arrangement it replaced: no top bar with product tabs, no left nav of icons, no right-hand TOC, no admonition cards, no KPI tiles, no shadowed panels, no coloured pills. Every heading carries a paragraph number, so every fact has an address (`2-4.4`) that can be typed, linked, searched, and remembered. The reader lands on the contents page, types or scans to a number, reads the fact with its source link and its change bar, and leaves knowing whether it was verified.

The material is uncoated stock and ink. One warm off-white paper, one near-black ink with two greys of ink for secondary and tertiary text, two greys for rules, and a single blueprint blue reserved for links and the diagram's primary emphasis fill. There is no shadow, no gradient, no radius beyond a 2px softening on inline code. Structure is carried entirely by hairline rules: a 1px rule under the running header and under every entry header, a 2px rule under each chapter title, a hairline top-and-bottom on tables and figures, and a 3px ink bar in the outer margin beside any block that contains an unverified claim. Density is that of a reference book: 15px body on a 70ch measure, headings that step in weight and case rather than size, and a mono address column that keeps numbers aligned.

State is a mark, never a colour. Draft entries carry an open square, reviewed ones a filled square, stale ones a strikethrough; unverified claims carry a dagger and pull a change bar into the margin. The same marks recur in the contents column (†N beside an entry), the entry meta line, and the colophon key, so the reader learns the notation once. The whole page is generated from Markdown and front matter, so nothing here is hand-tuned; a rule that cannot be derived from the notes does not exist.

**Key Characteristics:**
- One typeface family: B612 for prose, B612 Mono for addresses, labels, meta, captions, and code.
- Single hairline ruling grid in ink and two greys; no shadows, no fills except code and field surfaces.
- Every heading numbered `chapter-entry.paragraph[letter]`; every table and figure labelled with the entry number.
- One blue, used for links, the search caret, selection, and the mk1 diagram fill; nothing else is coloured.
- State as marks: open square, filled square, strikethrough, dagger, and a 3px marginal change bar.
- Sticky running header with manual title, current entry, revision date, and a centred index search.
- Three-state theme contract: bare root light, `prefers-color-scheme: dark` guarded, `data-theme` stamps win.
- Phone: single column, contents behind a bordered toggle, change bars move to the left margin.

## Colors

Paper, ink, three rules, and one blue; the dark theme keeps the same roles and swaps the material to ink-on-black.

### Primary
- **Blueprint Blue** (`{colors.blue}`, dark `#8FB0EC`): links (underlined 1px, underline colour blue at 45% alpha, full blue on hover), the search caret, and the stroke of `mk1` diagram nodes. It is the only chromatic ink on the page.
- **Blueprint Wash** (`{colors.blue-soft}`, dark `#1C2740`): the fill of `mk1` diagram nodes only. It never fills a panel, a button, or a tag.

### Neutral
- **Paper** (`{colors.paper}`, dark `#161616`): the page ground, the running header, and the label patch that interrupts a box border.
- **Ink** (`{colors.ink}`, dark `#E5E4E0`): body text, all headings, the header rule, chapter and entry rules, table top/bottom/head rules, box borders, change bars, the checkbox border and its filled check, the focus ring, and the expanded contents toggle's fill.
- **Ink 2** (`{colors.ink-2}`, dark `#B3B2AC`): secondary ink for paragraph numbers, meta lines, captions, the chapter kicker, contents numbers, unverified marks, the change-bar key, colophon, dead links, and checked-off task text.
- **Ink 3** (`{colors.ink-3}`, dark `#84837D`): tertiary ink for tags, the file path, the contents †count, reserved-chapter notes, the search placeholder, and the `/` keycap.
- **Rule** (`{colors.rule}`, dark `#5D5C58`): the search underline, contents chapter underlines, the code block's left rule, horizontal rules, figure top/bottom rules, `mk3` diagram strokes, and the scrollbar thumb.
- **Rule 2** (`{colors.rule-2}`, dark `#333330`): the faint rule between table rows, the contents column's right edge, the paragraph list's left edge, and the keycap border.
- **Field** (`{colors.field}`, dark `#1D1D1C`): the unchecked checkbox interior.
- **Code** (`{colors.code}`, dark `#232322`): inline code, code blocks, and the `mk3` diagram fill.
- **Selection** (`{colors.sel}`, dark `#2C3D62`): `::selection` background with ink text.

### Dark theme
The dark palette is the same eleven tokens redefined, not a second palette: paper `#161616`, ink `#E5E4E0`, ink-2 `#B3B2AC`, ink-3 `#84837D`, rule `#5D5C58`, rule-2 `#333330`, blue `#8FB0EC`, blue-soft `#1C2740`, field `#1D1D1C`, code `#232322`, sel `#2C3D62`, with `color-scheme: dark`. It is declared twice with identical values: once under `@media (prefers-color-scheme: dark)` scoped to `:root:not([data-theme="light"])`, and once under `:root[data-theme="dark"]`. Every colour has its light definition on bare `:root`; no colour is defined only inside a media or `[data-theme]` block. The local (non-artifact) build also picks Mermaid's `dark` or `neutral` theme by the same test at load.

### Named Rules
**The One Ink Rule.** Colour on this page is ink at three strengths, two rule greys, and one blue. The blue appears only on links, the caret, selection, and the `mk1` diagram fill. Nothing else is coloured, and no state is ever conveyed by colour.

**The Three-State Theme Rule.** Light lives on bare `:root`; dark is redefined under `prefers-color-scheme: dark` guarded by `:root:not([data-theme="light"])` and again under `:root[data-theme="dark"]`, with identical values, so the host's stamp wins in both directions.

## Typography

**Display Font:** none. Titles use the body face at heavier weight.
**Body Font:** B612 (with Helvetica Neue, Arial, sans-serif), weights 400 and 700, italic 400, from fonts.googleapis.com.
**Label/Mono Font:** B612 Mono (with ui-monospace, SF Mono, Menlo, monospace), weights 400 and 700.

**Character:** B612 is the cockpit-display face designed for legibility on instruments, and it is the only family on the page. The mono cut is not a code face here; it is the address and label face. Every paragraph number, contents number, meta line, caption, box label, header status, tag, keycap, and code span sets in B612 Mono so the reader can tell an address from prose at a glance. Hierarchy is carried by weight, case, and tracking; size barely moves.

### Hierarchy
- **Entry title** (700, 22px, 1.2, `text-wrap: balance`): the note's title in its `note-h` header, preceded by its address in mono at 18px / 400 / ink-2. On phones 19px.
- **Chapter title** (700, 20px, uppercase, 0.02em): the chapter label after a mono kicker `CHAPTER N` (11px, 0.12em, uppercase, ink-2), the pair sitting on a 2px ink rule.
- **Paragraph heading** (700, 15px, 1.35, uppercase, 0.02em): every `##` in a note, rendered as `h2` with address `N-M.k`. Same size as body; case and weight do the work.
- **Sub-heading** (700, 15px, 1.35, mixed case): every `###`, address `N-M.k<letter>`. `h4` (700, 14px, ink-2) exists in the stylesheet and is emitted only if a note uses `####`; the current build has none.
- **Body** (400, 15px, 1.55): prose, lists, and box text, on a 70ch measure. Bold is 700; `strong` carries no colour.
- **Address** (mono, 400, 0.92em, ink-2, `min-width: 3.2em`, 3.6em on sub-headings): the `pnum` span at the start of every numbered heading. Contents addresses are 12px (11px in paragraph lists).
- **Label** (mono, 700, 11px, 0.12em, uppercase): contents chapter headings, box labels (0.14em), the contents toggle (0.1em), the running-header title (this one in B612 sans, 13px, 0.12em, uppercase, 700) and its sub-line (11px, 0.1em, uppercase, ink-2).
- **Meta** (mono, 400, 11.5px, 0.04em, uppercase, ink-2): the status, revision date, source count, unverified count, and file path line under each entry title. Tags share the size in ink-3 without case change.
- **Caption** (mono, 400, 11.5px, 0.06em, uppercase, ink-2): `TABLE N-M-t` above a table, `FIGURE N-M-f` below a diagram.
- **Unverified mark** (sans, 0.82em, 0.06em, uppercase, ink-2, `†` prefix, no-wrap): the inline `† UNVERIFIED` phrase.
- **Table** (400, 13.5px, 1.4, `font-variant-numeric: tabular-nums`): headers 700.
- **Contents** (400, 13.5px, 1.3): entry links; paragraph links 12.5px in ink-2. The active entry is 700.
- **Code** (mono, 13px inline; 12.5px / 1.5 in blocks).
- **Running header current entry** (mono, 700, 12px, ink): `N-M Title`, truncated with an ellipsis at 26rem.

### Named Rules
**The One Family Rule.** B612 and B612 Mono are the only faces. Mono is the address and label face, not a code face; anything that is a number, a status, a caption, or a key sets in mono.

**The Flat Scale Rule.** Body, paragraph headings, and sub-headings are all 15px. Level is signalled by weight, case, tracking, and the address, not by size. Only entry titles (22px) and chapter titles (20px) rise above the text.

## Layout

The page is a two-column spread under a sticky running header, capped at 1240px and centred with 1.25rem side padding. Column one is the contents at a fixed `17.5rem`, sticky below the header (`top: 3.4rem`), scrolling inside its own `max-height: calc(100vh - 3.4rem)`, closed on the right by a 1px `rule-2`. Column two is the manual body, indented 2.25rem from the contents rule, with each entry constrained to a 70ch measure plus a 2.25rem right gutter that exists only to hold change bars.

The running header is a three-column grid `17.5rem | 1fr | auto`, min-height 3.4rem, on paper with a 1px ink bottom rule: manual title and `TECHNICAL MANUAL · CHANGE <date>` at left; the index search centred and capped at 34rem, drawn as a single 1px `rule` underline with an `INDEX` label and a `/` keycap; at right the current entry address and title, a `Resume at N-M.k` link when a last-read paragraph is stored, and (narrow only) the Contents toggle. `scroll-padding-top` is 4.5rem so anchored headings land below it.

Vertical rhythm is set in rems off the 15px body: paragraphs 0.55rem apart, list items 0.2rem, figures and tables 1.1rem, boxes 1rem, paragraph headings 2rem above and 0.5rem below, sub-headings 1.4rem/0.35rem, entries 4rem apart, chapters 3.5rem above their rule and 1.5rem below. The manual body ends with a 6rem tail and a colophon on a 1px ink rule.

**Numbering.** Chapters are the seven configured sections in order (SOPs, Topics, Papers, Tools, Hardware, Experiments, Field notes); an empty chapter still appears, marked `(reserved)` in the contents and `Reserved. No entries yet.` in the body. Entries are `N-M` (`id="nN-M"`). Paragraphs are `N-M.k` for `##` and `N-M.k<letter>` for `###` (`id="pN-M.k"`, `id="pN-M.ka"`). Tables are `Table N-M-t`, figures `Figure N-M-f`, numbered per entry in document order. Checklist items are keyed `nN-M-t<n>`.

**Contents column.** Chapter headings are mono labels on a 1px `rule` underline; entries are a three-column grid (`2.9rem` address, title, `†N` count). The active entry (set by an IntersectionObserver with `rootMargin: -56px 0 -70%`) goes bold and unfolds its paragraph list, a `rule-2` left-ruled indented list of `N-M.k` links (letter sub-headings are not listed). Lists also unfold for every entry while a search is active.

**Under 920px.** The header becomes two rows (`left right` / `search search`) with the keycap and the current-entry title hidden and the Contents toggle shown. The page is a single column with 0.9rem side padding; the contents column is static, hidden until the toggle opens it, closed by a 1px `rule` bottom edge, and closes itself when a link is tapped. Entries drop the right gutter and take a 0.9rem left indent so change bars sit in the left margin (`left: -0.9rem`; list items `-2.3rem`). The entry title drops to 19px, the chapter kicker stacks above its title, and `scroll-padding-top` grows to 7rem for the taller header. Wide tables scroll inside `.tablewrap`; the page never scrolls sideways.

### Named Rules
**The Outer Margin Rule.** Change bars live in the gutter outside the text block: the right gutter on the spread, the left margin on the phone. They are never drawn inside the measure.

**The Address Column Rule.** Every numbered thing starts with its address in mono at a fixed minimum width, so numbers align down the page and titles start on a common line.

## Elevation & Depth

There are no shadows anywhere in the stylesheet. Depth is conveyed by paper and ink alone: the sticky header and contents column are the same paper as the page, separated by 1px rules, and the box label sits on a patch of paper that interrupts the box border. The only surfaces that differ from paper are the `code` tint behind code and the `field` tint inside an unchecked checkbox. Diagram nodes are outlined, not lifted.

### Named Rules
**The No-Shadow Rule.** Nothing casts a shadow. Separation is a 1px rule in `rule`, `rule-2`, or ink; hierarchy is the weight of the rule (1px, 2px for chapters, 3px for change bars).

## Shapes

Square. Every box, checkbox, button, table, figure, and code block has `border-radius: 0`; inline code and the `/` keycap soften to 2px so the tint patch does not look cut with a knife. Borders are single hairlines in ink for structural edges (header, entry header, box, table top and bottom, checkbox, contents toggle) and in a rule grey for internal divisions (table rows, figure edges, code block left edge, horizontal rules, contents edges). Rules are horizontal except the contents column's right edge, the paragraph list's left edge, the code block's left edge, and the vertical change bar. The checked state of a checkbox is a solid ink square inside the ink-bordered square. The status marks are squares too: an open 0.5em square for draft, a filled 0.55em square for reviewed.

## Components

### Running header
- **Character:** the manual's running head, always in view.
- **Style:** sticky, paper background, 1px ink bottom rule, `z-index: 5`; grid `17.5rem | 1fr | auto`.
- **Left:** `ROBOT LEARNING LAB` (700, 13px, 0.12em, uppercase) over `TECHNICAL MANUAL · CHANGE 2026-09-05` (11px, 0.1em, uppercase, ink-2; the date never wraps).
- **Right:** `#cur` shows `N-M  Title` of the entry in view (mono 700 12px, ellipsis at 26rem); `#resume` is a hidden link that reads `Resume at N-M.k` when `rll-last` exists; `Contents` toggle is display:none above 920px.

### Index search
- **Style:** a single 1px `rule` underline, no box, no radius; `INDEX` label in 11px uppercase ink-2 at left, a `/` keycap (10px, 1px `rule-2` border, 2px radius, ink-3) at right. Input is 14px B612 on transparent with ink-3 placeholder `Search paragraphs`; focus has no outline (the underline is the affordance).
- **Behaviour:** `/` anywhere focuses and selects; `Escape` inside clears, re-applies, and blurs. The query is matched case-insensitively against each paragraph unit (a numbered heading and every sibling until the next `h2`/`h3`, text joined and lower-cased). Non-matching units are hidden with `.hidden`; a heading whose unit matches gets `.hit`, which underlines its address 2px. Entries with no hits hide; chapters with no visible entries hide; contents rows filter to match and take `.searching` so their paragraph lists unfold. On the first keystroke the page scrolls so the first hit sits 10px under the header; clearing scrolls to top. With no hits the `nomatch` line shows: `No paragraph matches. Clear the index field with Escape.` The query persists in `localStorage` as `rll-q` and is re-applied on load without scrolling.

### Contents
- **Style:** see Layout. Links are ink, no underline; hover underlines the title 1px at 0.18em offset. Active entry 700. Paragraph lists are indented 0.6rem behind a 1px `rule-2` left rule.
- **Count mark:** `†N` in 11px ink-3 at the row's right edge, only for entries with unverified claims.
- **Mobile:** hidden behind the `Contents` toggle (see below); tapping any link closes it.

### Contents toggle (narrow only)
- **Shape:** square, 1px ink border, no fill.
- **Type:** 11px B612 Mono, 0.1em, uppercase, padding 0.3rem 0.55rem.
- **Expanded:** `aria-expanded="true"` inverts to ink fill with paper text.

### Chapter head
- **Style:** flex baseline row with `CHAPTER N` kicker (mono 11px 0.12em uppercase ink-2) and the chapter title (700 20px uppercase 0.02em) on a 2px ink rule; 3.5rem above, 1.5rem below (0 above for the first). Stacks vertically under 920px.
- **Reserved:** an empty chapter shows `Reserved. No entries yet.` in 13px ink-3.

### Entry header
- **Style:** `h2` with mono address (18px, 400, ink-2, 0.6em gap) and title (22px, 700, balanced), closed by a 1px ink rule 0.6rem below.
- **Meta line** (0.45rem below): status mark and word, `REV <date>`, `<n> SOURCES`, `†<n> UNVERIFIED` (only when non-zero), and the repo path in ink-3 without case change; 1.25rem column gap, wrapping.
- **Tags** (0.35rem below): plain mono words in ink-3, 0.8rem apart. No border, no fill, no pill.

### State marks
- **Draft:** an open square (0.5em, 1px ink border) before `DRAFT`.
- **Reviewed:** a filled ink square (0.55em) before `REVIEWED`.
- **Stale:** `STALE` struck through.
- **Unverified:** the phrase `(unverified)` or `(from field, unverified)` in a note becomes `† UNVERIFIED` (0.82em, uppercase, ink-2, no-wrap), and its containing `p`, `li`, or `tr` takes `.chg`, which draws the change bar.
- In the 2026-09-05 build all 21 entries are `draft`; the reviewed and stale marks are defined by the generator and appear only when front matter sets them.

### Change bars
- **Style:** a 3px ink bar (`--bar`) drawn by `::before` on `p.chg` and `li.chg`, spanning the block from 0.2em below its top to 0.2em above its bottom, positioned at `right: calc(-1 * var(--gutter) + .6rem)` so it sits in the outer gutter; left margin under 920px.
- **Table rows:** `tr.chg` cannot position a pseudo-element reliably inside a scrolling wrapper, so the script measures each marked row and appends an `<i class="rowbar">` to the enclosing `figure.tbl`, at the row's offset with 3px inset top and bottom, so a wide table scrolling sideways cannot hide the bar. Bars are re-laid on font load, resize (150ms debounce), and every search keystroke.
- **Key:** the manual body opens with `Change bar in the margin marks a claim tagged unverified. <n> marked in this change.`, led by a 3px x 1.1em ink swatch, in 12px ink-2.

### NOTE / WARNING box
- **Style:** a 1px ink border, no radius, no fill, padding 0.7rem 0.9rem 0.6rem, 1rem above and below, `role="note"`. The label (`NOTE`, or `WARNING` / `DANGER` / `CAUTION` when the quote's text starts with that word) sits on the top border in mono 11px 700 0.14em on a patch of paper. Paragraphs inside are 0.3rem apart.
- **Source:** any Markdown blockquote. No note in the 2026-09-05 build contains one, so the current page carries zero boxes; the rule is the generator's and applies the moment a note uses `>`.

### Tables
- **Style:** `Table N-M-t` caption above in mono uppercase; the table is full width, 13.5px, tabular figures, 1px ink rules top and bottom and under the header row, 1px `rule-2` between body rows, none under the last. Header cells are 700, bottom-aligned; body cells top-aligned, padding 0.35rem 0.6rem with 0.2rem at the outer edges so text aligns with the rules. No zebra, no fills.
- **Wide tables:** wrapped in `.tablewrap { overflow-x: auto }` so they scroll in place; the caption and the change bars stay put outside the scroll.

### Figures (Mermaid)
- **Style:** `figure.fig` with 1px `rule` top and bottom, padding 0.6rem 0 0.4rem, diagram centred, `Figure N-M-f` caption below. The diagram's labels are forced to B612 in ink.
- **Emphasis classes:** the generator rewrites every `classDef` in a diagram, in order of appearance, to `mk1`, `mk2`, `mk3` (all further classes collapse into `mk3`) with `stroke-width: 1px`, and the page CSS colours them: `mk1` blue-soft fill with blue stroke (the primary emphasis); `mk2` paper fill with a 2px ink stroke (the secondary, outlined emphasis); `mk3` code fill with rule stroke (the subdued class). Unclassed nodes take Mermaid's neutral or dark theme. The current build uses `mk1` in eight diagrams and `mk2` in one; `mk3` is defined and unused.
- **Loading:** the artifact host renders `<pre class="mermaid">` natively; the local build loads Mermaid 11.12.0 from cdnjs and initialises it with the theme test from the Colors section and `fontFamily: B612`.

### Checklists
- **Style:** a Markdown task item becomes a real `<input type="checkbox">` inside a label on a `1.1rem | 1fr` grid, list marker removed. The box is 0.95rem, square, 1px ink border on `field`; checked fills a 0.5rem ink square inside and strikes the label text through in ink-2.
- **Persistence:** each box is keyed `nN-M-t<n>`; its state is stored in `localStorage` as `rll-cb-<key>` = `1` or `0` and restored on load, overriding the Markdown's `[x]`.

### Links
- **Style:** blue, 1px underline at 0.18em offset, underline colour blue at 45% alpha, full blue on hover; `a.url` (bare URLs auto-linked) and inline code may break anywhere. Cross-note links (`../x.md`, or a code span holding a repo path) become in-page anchors rendered as `N-M Title`; a link to a Markdown file not in the manual becomes `a.dead` in ink-2 with a dotted underline and the title `Not in this manual`.
- **Focus:** `:focus-visible` is a 2px ink outline at 2px offset, everywhere.

### Arrival mark
- **Behaviour:** navigating to a heading id (`:target`) underlines its address 2px in ink and fades the underline to transparent over 2.4s on `cubic-bezier(.16,1,.3,1)` (held solid for the first 60%). Search hits (`.hit`) keep a steady 2px underline while the query stands. Under `prefers-reduced-motion: reduce` the animation is off, the underline stays, and page scrolling is instant instead of smooth.

### Last-read paragraph
- **Behaviour:** on scroll (400ms throttle) the script finds the last numbered heading whose top is at or above 60px and stores its id as `rll-last`. On the next load the header's `Resume` link is unhidden with the text `Resume at N-M.k` pointing to that id.

### Colophon
- **Style:** 4rem above the page end, a 1px ink top rule, 12px ink-2, two spans justified apart: `Built <date> from <n> notes by tools/build_site.py.` and `Reviewed entries carry a filled mark; draft entries an open one.`

## Do's and Don'ts

### Do:
- **Do** give every heading an address and set it in B612 Mono at 0.92em, 400, ink-2, with `min-width: 3.2em` (3.6em for letter sub-headings) before the title.
- **Do** separate with 1px rules: `rule` for edges (search, figures, code), `rule-2` for internal divisions (table rows, contents edges), ink for structural edges (header, entry header, box, table top/bottom/head).
- **Do** reserve 2px rules for chapter titles and 3px ink bars for change bars; these are the only weights above hairline.
- **Do** use `mk1` (blue-soft fill, blue stroke) for the one thing a diagram is about, `mk2` (paper, 2px ink) for its counterpart, `mk3` (code fill, rule stroke) for the rest; never a fourth class.
- **Do** mark state with the four marks (open square, filled square, strikethrough, dagger) and reuse them wherever that state appears: meta line, contents count, colophon key.
- **Do** define every colour on bare `:root`, then redefine the same tokens under both dark blocks with identical values.
- **Do** keep the measure at 70ch with a 2.25rem outer gutter that exists only for change bars; under 920px move the bars to a 0.9rem left margin.
- **Do** derive every element from Markdown and front matter through `tools/build_site.py`; if the generator does not emit it, it is not on the page.
- **Do** persist reader state in `localStorage` under the `rll-` prefix (`rll-q`, `rll-last`, `rll-cb-<key>`) inside try/catch, and render correctly when storage is empty or throws.

### Don't:
- **Don't** add shadows, gradients, or filled panels; the only tints are `code` behind code and `field` inside a checkbox.
- **Don't** round corners beyond the 2px on inline code and the keycap; boxes, buttons, checkboxes, tables, and figures are square.
- **Don't** use colour for state, status, or emphasis; blue is for links, the caret, selection, and the `mk1` fill only.
- **Don't** render tags, statuses, or counts as pills, chips, or badges; they are plain mono words and marks.
- **Don't** introduce a third typeface, or a display size above the 22px entry title; body, paragraph headings, and sub-headings all stay at 15px.
- **Don't** put a top bar of tabs, a left icon rail, a right-hand table of contents, or admonition cards on the page; the manual has one running header, one contents column, and ruled boxes.
- **Don't** chart the notes themselves (lines per note, counts over time); the only figures are the notes' own Mermaid diagrams of sensors, methods, and pipelines.
- **Don't** let a wide table widen the page; it scrolls inside `.tablewrap` and its change bars are drawn from the figure, not the row.
- **Don't** hand-edit `site/index.html`; edit the CSS and JS constants in `tools/build_site.py` and rebuild.
