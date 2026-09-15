---
name: inbox
description: Triage the user's Gmail: read unread and recent threads, group by action needed, draft replies for the user to approve, never send without explicit approval. Also extracts meetings and deadlines into a daily plan. Use daily or when the user asks about email.
user-invocable: true
argument-hint: "[days back] [--draft]"
---

Triage with the Gmail tools (load them with ToolSearch: `select:mcp__claude_ai_Gmail__search_threads,mcp__claude_ai_Gmail__get_thread,mcp__claude_ai_Gmail__create_draft`).

Rules:
1. Read-only by default. Creating a draft is allowed; sending, labelling, trashing, or marking spam requires the user's explicit instruction in the current conversation. Never forward.
2. Search `is:unread newer_than:Nd` (N from `$ARGUMENTS`, default 3) plus `newer_than:1d` for anything already read that carries a deadline or meeting.
3. Group into: needs a reply from the user (with a proposed one-line answer), needs an action (with the action and date), meetings and deadlines (date, time, who, link), FYI, noise. Quote nothing sensitive back beyond what is needed to act.
4. With `--draft`, create Gmail drafts for the replies in group one, in the user's voice: short, direct, no filler, no em-dashes. Say which drafts were created.
5. Produce a daily plan at the end: top three things to do today, meetings in order, and anything blocked on someone else.
6. Report under 250 words. Do not store email contents in the repo or in memory; only durable facts about people, projects, and commitments the user confirms.
