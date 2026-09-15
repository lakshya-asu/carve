---
name: retro
description: Weekly retrospective on the user and on Claude as a working pair: what was shipped, what broke, strengths and weaknesses observed with evidence, one improvement each for next week, and updates to memory, CLAUDE.md, and the capabilities ledger. Run weekly or when the user asks.
user-invocable: true
argument-hint: "[week ending YYYY-MM-DD]"
---

Write `retros/YYYY-MM-DD.md` from `retros/TEMPLATE.md` and update `retros/capabilities.md`.

Evidence sources, in order: `git log` for the week, `field-notes/`, `experiments/`, the memory directory, and the conversation. Never invent an observation; every strength or weakness cites a concrete event (a commit, a note, an incident, a decision, a thing the user said). Strengths and weaknesses cover both people: the user, and Claude in this collaboration.

Procedure:
1. Shipped: list with links. Broke or slipped: list with cause.
2. User: two strengths and two weaknesses observed this week, each with evidence and one specific practice for next week. Be direct; the user asked for this. No flattery, no hedging.
3. Claude: same, honestly. Where a weakness is a missing capability (a tool, a hook, a skill, a memory), build or propose the fix in the same turn.
4. One improvement for the pair: a process change, a checklist, an automation.
5. Update `retros/capabilities.md`: the running ledger of skills to grow, with status. Update memory files where a durable fact changed. Update `~/.claude/CLAUDE.md` or the repo `CLAUDE.md` if a rule earned its place.
6. Commit. Report the retro in under 300 words.
