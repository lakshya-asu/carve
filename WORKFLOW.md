# How we work

Two operators, one system. The manual is shared memory; the skills are
the verbs. Everything below runs from this repo on any machine that has
Claude Code, including janus once it is connected.

## Daily
- Morning: `/inbox` for triage and the day's plan. Say "send" on a draft to send it.
- Any question: `/ask <question>`. Answers cite manual addresses.
- Need to show something: `/brief <topic>`. Published to a private artifact.
- Evening or overnight: `/research-pass [priorities]`. Adds notes, rebuilds, republishes, commits.

## Weekly
- Friday: `/retro`. Writes `retros/<date>.md`, updates `retros/capabilities.md`, memory, and rules.

## Before robot time
- `sops/field-deployment-checklist.md`, then `sops/robot-bring-up.md`.
- Everything works in sim first: `library/topics/sim-first-workflow.md`, daily checklist section.

## Scheduling
Session loops end when the terminal closes. For passes that run without a
terminal, push this repo to a private GitHub remote and create cloud
routines with `/schedule` (daily research pass, weekly retro). Until then,
`/loop /research-pass` self-paces inside an open session.

## Tooling on this machine
- Read-only ROS 2 introspection over MCP (`ros2` server in `.mcp.json`). I can see
  topics, rates, nodes, params, and bags. I cannot publish, call, or set anything.
- Permissions in `.claude/settings.json`: actuation verbs are denied outright.
  Move `ros2 launch` and `ros2 run` from `ask` to `deny` before a real robot is
  on the network.
- Hooks check Python and note front matter on every write; a git pre-commit hook
  blocks slop in any harness.
- Subagents: `note-writer`, `paper-reader`, `ros2-reviewer`.
- Full description and the checks to verify it: `library/tools/claude-code-setup.md`.

## Rules that bind both of us
- `CLAUDE.md` here: code and note standards.
- `~/.claude/CLAUDE.md`: no slop, in writing or design.
- `DESIGN.md`: the manual's visual system; `/brief` inherits it.
- No number without a source and its conditions. No send without approval.
