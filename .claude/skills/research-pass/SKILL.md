---
name: research-pass
description: Run one research pass on the library: pick the highest-value gaps, research them with parallel agents from primary sources, write or extend notes, validate, rebuild and republish the manual, commit. Use daily or whenever the user names new topics.
user-invocable: true
argument-hint: "[topics or gaps to prioritise]"
---

Run one pass. `$ARGUMENTS` names priorities; otherwise choose from the backlog.

Procedure:
1. Read `library/topics/00-study-path.md` (pass log and any backlog rows), `library/papers/00-reading-list.md` (rows still marked todo), and the memory file `meat-cutting-project.md` for standing priorities. List the gaps; rank by value to the current assignment and to production reliability.
2. Launch 3 to 6 `general-purpose` agents in parallel, one per note or paper batch. Each prompt must include: read `CLAUDE.md` and `library/README.md` and one finished note for format; writing rules from `~/.claude/CLAUDE.md` (no em-dashes, no filler words, no emoji); every claim links a primary source or is tagged "(unverified)"; read full papers not abstracts; run `~/.claude/hooks/slop-check.py` on the file before finishing; report a 5-line summary and unverified items; do not rebuild or publish.
3. When agents report, validate: front matter present, slop-check clean, no dead relative links (`grep -c 'class="dead"' site/index.html` after a build must be 0), titles capitalised. Fix contradictions agents flag between notes; downgrade unsupported claims to unverified rather than deleting.
4. Add study-path rows and a pass-log line. Update the reading list.
5. Build both variants with `tools/build_site.py` in the `rll` env with `env -u PYTHONPATH`, run the Playwright render check (figures rendered equals figures present, row bars equal marked rows), publish to the existing artifact URL from memory, commit with a body that says why.
6. Report: what landed, the two or three findings that change what the user should do, and what is still unverified. If an agent dies on a rate limit, check its files on disk before relaunching; partial files are usually complete.
