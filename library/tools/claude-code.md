---
title: Claude Code
date: 2026-09-07
tags: [tool, agentic-coding]
status: draft
source: https://code.claude.com/docs/en/overview.md
---

# Claude Code: Production Robotics Reference

Claude Code is an AI agent that reads, modifies, and runs code while respecting safety constraints via permission modes, hooks, and sandboxing.

## Configuration Hierarchy

Settings cascade from most to least specific: Local > Project > User > Managed Policy. Load order for CLAUDE.md: managed policy, user (`~/.claude/CLAUDE.md`), project (`./CLAUDE.md` or `./.claude/CLAUDE.md`), local (`./CLAUDE.local.md`). All ancestor files concatenate. ([Memory docs](https://code.claude.com/docs/en/memory.md))

### Core Config Files
- `~/.claude/settings.json` (user)
- `.claude/settings.json` (project, checked in)
- `.claude/settings.local.json` (local overrides, .gitignore)
- `.claude/rules/` (path-scoped instructions with `paths:` frontmatter)

Target CLAUDE.md under 200 lines; use rules for organization by path pattern.

## Permissions and Safety

Set permission mode in `/config` or `"permissionMode"` setting: **Manual** (prompt each action), **Auto** (classifier), **Plan** (read-only), **Accept Edits** (auto-approve writes), **Bypass** (none; dangerous). For robots, use Manual or Plan. ([Permissions docs](https://code.claude.com/docs/en/permission-modes.md))

Deny risky commands in settings:
```json
{
  "permissions": {
    "deny": [
      "Bash(ros2 service call *)",
      "Bash(rostopic pub *)",
      "Bash(sudo *)",
      "Bash(/dev/* *)"
    ]
  }
}
```

Rule syntax: `ToolName(pattern)` with glob matching. Patterns with trailing ` *` (space before asterisk) enable prefix matching. Common: `Read`, `Edit`, `Bash`, `Write`, `Glob`, `Grep`, `WebFetch`. ([Permissions docs](https://code.claude.com/docs/en/permissions.md#permission-rule-syntax))

## Hooks: Automation

Run shell commands at fixed lifecycle points. Store in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{"type": "command", "command": "~/.claude/hooks/block-hardware.sh"}]
    }],
    "PostToolUse": [{
      "matcher": "Bash",
      "matchers": {"command": "pytest *"},
      "hooks": [{"type": "command", "command": "~/.claude/hooks/format-output.sh"}]
    }]
  }
}
```

Events: **SessionStart** (once per session), **PreToolUse** (before each call; can modify input), **PostToolUse** (after success; receives exit code), **PermissionRequest** (before prompt). Matchers filter by tool name and pattern. Pre/Post hooks receive JSON on stdin; PreToolUse output must return modified input JSON. ([Hooks guide](https://code.claude.com/docs/en/hooks-guide.md))

## Skills and Plugins

Create skills at `~/.claude/skills/name/SKILL.md` or `.claude/skills/name/SKILL.md`:

```yaml
---
name: fix-lint
description: Fix linting errors in TypeScript
arguments: [severity]
allowed-tools: Bash(npm run lint *) Edit(src/**/*.ts)
---

Fix all $severity linting errors in src.
```

Invoke with `/fix-lint high`. Use `allowed-tools` to pre-approve tools for that turn. Set `context: fork` to run in isolated subagent. ([Skills docs](https://code.claude.com/docs/en/skills.md))

## Subagents and Parallelism

Create in `.claude/agents/name.md`:

```yaml
---
name: reviewer
description: Code review
tools: Read, Grep, Glob, Bash
model: sonnet
permissionMode: plan
isolation: worktree
---

You are a code reviewer. Analyze and provide feedback.
```

Isolation via worktree prevents file collision. Use for verbose operations or parallel work. ([Subagents docs](https://code.claude.com/docs/en/sub-agents.md))

## MCP Servers

Define in `.mcp.json` at repo root for custom integrations:

```json
{
  "mcpServers": {
    "ros2": {
      "type": "stdio",
      "command": "python",
      "args": ["./ros2_mcp_bridge.py"],
      "env": {"ROS_DOMAIN_ID": "${ROS_DOMAIN_ID:-0}"}
    }
  }
}
```

Transport types: **HTTP** (remote with auth headers), **Stdio** (local process), **WebSocket** (persistent). Env vars expand at runtime. ([MCP docs](https://code.claude.com/docs/en/mcp.md))

## Headless and CI

Run non-interactively:
```bash
claude -p "Find bugs" --allowedTools "Read,Edit,Bash"
claude -p "Task" --permission-mode dontAsk --output-format json
claude -p "Task" --bare  # Skip hooks/skills/MCP
```

Output formats: `text` (default), `json` (structured), `stream-json` (real-time events). Exit codes: 0 (success), 1 (fail), 2 (partial; cost ceiling). ([Headless docs](https://code.claude.com/docs/en/headless.md))

GitHub Actions: Use `anthropics/claude-code-action@v1` with workflows in `.github/workflows/`. ([GitHub Actions docs](https://code.claude.com/docs/en/github-actions.md))

## Memory and Context

Auto memory saves to `~/.claude/projects/<project>/memory/MEMORY.md` (first 200 lines loaded each session). Toggle with `/memory`. Custom location: `"autoMemoryDirectory"` in settings (absolute or `~/`). Clear between tasks with `/clear`. Track usage with `/usage`. ([Memory docs](https://code.claude.com/docs/en/memory.md))

## Worktrees

Isolate sessions in separate git checkouts:
```bash
claude --worktree feature-auth    # New worktree
claude --worktree "#1234"         # Branch from PR
git worktree list                 # Inspect
```

Add `.gitignore`:
```
.claude/worktrees/
```

Copy untracked files with `.worktreeinclude`:
```
.env
.env.local
config/secrets.json
```

Worktree isolation blocks edits to main checkout and git redirects outside isolation. ([Worktrees docs](https://code.claude.com/docs/en/worktrees.md))

## Agent SDK

Build custom agents in Python or TypeScript. Includes same tools, loop, and context as Claude Code. You host it.

```python
from anthropic.agent_sdk import Agent
agent = Agent()
result = agent.run_sync("Find and fix bugs in auth.py")
```

Built-in tools: Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch. Features: sessions, permissions, hooks, subagents, MCP, skills, auto memory. ([Agent SDK docs](https://code.claude.com/docs/en/agent-sdk/overview.md))

## Sandboxing

Isolates Bash at OS level (macOS Seatbelt, Linux seccomp). Configure filesystem allowlist:

```json
{
  "sandbox": {
    "enabled": true,
    "filesystem": {"allowlist": ["${CLAUDE_PROJECT_DIR}", "/tmp"]}
  }
}
```

Blocks filesystem and network access outside allowlist. Does not prevent ROS topics or hardware `/dev/` access; use permission rules and hooks. ~100ms overhead per command. ([Sandboxing docs](https://code.claude.com/docs/en/sandboxing.md))

## Costs and Models

Model is set in settings (`"model"`) or with `/model`. This machine is pinned to `claude-fable-5-1` (see `~/.claude/settings.json`). Current line-up as of September 2026: Fable 5.1 (`claude-fable-5-1`, most capable), Opus 5 (`claude-opus-5`), Sonnet 5 (`claude-sonnet-5`), Haiku 4.5 (`claude-haiku-4-5-20251001`, fast and cheap). The docs page fetched for this note listed older 4.x IDs; check the models page before pinning (unverified which IDs the docs currently list). Effort levels control thinking budget: `/effort low` (fast), `/effort high` (deep). Check cost with `/usage`. Average per-developer: $13-30/day; $150-250/month. Reduce costs: clear between tasks, use a smaller model for routine edits, offload to subagents, use PreToolUse hooks to filter logs. ([Costs docs](https://code.claude.com/docs/en/costs.md))

## Robotics Team Checklist

- Deny robot control in settings: `"deny": ["Bash(ros2 service call *)", "Bash(rostopic pub *)", "Bash(sudo *)"]`
- Add linting/testing hooks: PreToolUse on Edit, PostToolUse on Bash(pytest *)
- Create CLAUDE.md: build commands, git workflow, ROS safety rules, code style
- Implement ROS 2 MCP server (python stdio) for safe topic inspection
- GitHub Actions: Use `claude-code-action@v1` with cost ceiling and permission mode `dontAsk`
- Skills: `/lint-fix`, `/test-suite`, `/inspect-ros-topic` with pre-approved tools
- Add `.claude/worktrees/` to .gitignore

## Resources

- [Official docs](https://code.claude.com/docs/en/overview.md)
- [Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview.md)
- [GitHub Action](https://github.com/anthropics/claude-code-action)
- [Security guide](https://code.claude.com/docs/en/security-guidance.md)

Version: Claude Code >= 2.1.198. Run `claude --version` and update with `claude update`.

## Could Not Verify

- ROS 2 topic MCP bridge latency under high message rates (domain-specific)
- Sandbox seccomp performance on systems with custom filter policies
- Exact behavior with non-standard git filter drivers (LFS, custom drivers in repo config)
- Compatibility matrix for older Ubuntu/RHEL versions (tested on 20.04+, 8+)

