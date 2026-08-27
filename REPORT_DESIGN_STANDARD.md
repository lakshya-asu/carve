# Technical report design standard

This standard applies to `TECHNICAL_REPORT.html` and future engineering reports in this repository.

## Design intent

The report is for an engineer, reviewer, or interviewer who needs to understand what the system does and what the evidence proves. It should feel like an engineering publication, not a product dashboard.

Design dials:

- Design variance: 6. Use several layout forms, but keep the reading order obvious.
- Motion intensity: 2. Media controls and link feedback only.
- Visual density: 7. Show useful evidence without crowding the page.

## Theme

- Use one dark theme throughout.
- Use graphite and warm gray neutrals.
- Use one muted amber accent for emphasis and data marks.
- Do not use blue, cyan, purple, gradients, glows, glass effects, or pure black.
- Use red and green only for real failure and pass states. Pair color with text or shape.
- Use square geometry. Do not use rounded cards, rounded figures, or pills.

## Layout rules

- Do not use cards as the default grouping device.
- Do not use colored side-border warnings.
- Do not use top-bordered metric tiles.
- Group content with spacing, typography, background bands, sparse rules, and alignment.
- Limit prose to about 72 characters per line.
- Use a distinct composition for each major type of information.
- Keep navigation labels, anchor IDs, and evidence links stable when redesigning.

## Visualization rules

- Architecture diagrams must show the physical cell, information flow, control flow, and feedback loop. A row of software boxes is not enough.
- Process diagrams must use concrete nouns and verbs. Do not label stages as generic steps.
- Put labels next to the mark they describe. Avoid separate legends when direct labeling works.
- Do not rely on color alone. Use labels, line styles, symbols, or position as a second encoding.
- Use real simulator images and videos. Do not draw fake screenshots.
- Charts must answer a stated question. Do not add decorative charts.
- Exact values belong in compact tables when the chart is intended to show a pattern.

## Writing rules

- Lead with what happened.
- Use plain language and short sentences.
- Keep technical names only when they identify a real interface, artifact, or measured value.
- Remove slogans, filler, fake precision, and claims not supported by artifacts.
- Use no em dash or en dash characters.
- State simulation limits near the relevant evidence.

## Review checklist

- Read every heading and caption in order. The page should make sense without body text.
- Check every local image, video, and link.
- Inspect the complete page at desktop and narrow widths.
- Check that diagrams remain readable without horizontal clipping.
- Check heading hierarchy, keyboard focus, media alternatives, and color contrast.
- Run `python -m pytest tests/test_technical_report.py -q`.
- Run `python tools/audit_report_language.py --fail-on-style`.

## Research basis

- [W3C design accessibility tips](https://www.w3.org/WAI/tips/designing/) recommend sufficient contrast, headings and spacing for grouping, media alternatives, and layouts that work at different viewport sizes.
- [W3C accessibility principles](https://www.w3.org/WAI/fundamentals/accessibility-principles/) require non-text alternatives, meaningful structure, reflow, and cues beyond color.
- [W3C heading guidance](https://www.w3.org/WAI/tutorials/page-structure/headings/) explains that heading ranks should reflect the organization of the page.
- [GOV.UK layout guidance](https://design-system.service.gov.uk/styles/layout/) recommends constrained text width and mobile-first layouts. It notes that long lines become difficult to read.
- [GOV.UK type-scale guidance](https://design-system.service.gov.uk/styles/type-scale/) uses a consistent type and line-height scale to improve rhythm and scanning.
- [Nielsen Norman Group on technical content](https://www.nngroup.com/articles/writing-domain-experts/) reports that domain experts still prefer factual, concise, and scannable writing.
- [Nielsen Norman Group on the layer-cake pattern](https://www.nngroup.com/articles/layer-cake-pattern-scanning/) shows why descriptive headings and clear visual hierarchy make long pages easier to scan.
- [Carbon data-visualization palettes](https://carbondesignsystem.com/data-visualization/color-palettes/) treat chart color as a controlled accessibility system, not decoration.
