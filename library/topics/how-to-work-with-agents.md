---
title: How to work with coding agents
date: 2026-09-07
tags: [tutorial, agentic-coding]
status: draft
source: synthesis
---

# How to work with coding agents

A course in eight lessons for an engineer who already knows robot learning and is now pairing
with a coding agent every day. Every lesson has the idea, a worked example on this repository or
on a robotics task, the exact text to type, what a good result looks like, and the mistake most
people make first. External practice is cited to Anthropic's Claude Code documentation
([Best practices](https://code.claude.com/docs/en/best-practices), accessed 2026-09-07, undated)
or to dated engineering posts. Advice with no source is written as a checklist item or tagged
"(from practice, unverified)".

The one constraint behind most of the advice: the agent's context window fills fast and its
quality drops as it fills. The docs call the context window "the most important resource to
manage" ([Best practices](https://code.claude.com/docs/en/best-practices)). Contracts, plans,
hooks, subagents and skills are all ways to spend that resource on the task instead of on
re-explaining the task.

## Lesson 1. The contract

`CLAUDE.md` is read at the start of every session. In this repo it carries the code standards,
the ROS 2 rules, the experiment rules and the rule to read the matching `sops/` file before a
kind of work. `~/.claude/CLAUDE.md` carries the writing and design rules. Together with the SOPs
they are the contract: the agent is bound by them without being told, and you are bound by them
when you review. The docs' test for each line is "would removing this cause Claude to make
mistakes?"; a bloated file gets ignored in parts
([Best practices](https://code.claude.com/docs/en/best-practices)). The repo file is 56 lines.
Keep it there.

A task prompt is the second half of the contract. The agent cannot read your mind, and it will
narrow a vague task to the part it understands or widen it to the part it finds interesting. The
`~/.claude/CLAUDE.md` process rule says "do the work asked, fully. Do not narrow, widen, or
transform the scope." That rule only works if the scope is written down: the files in, the files
out, the check that proves it done, and the reply shape you want back. The `/ask` skill fixes
the reply shape as answer first, then evidence, then what is uncertain. Demand the same shape
for engineering replies; it makes a wrong answer visible in the first sentence.

Worked example: adding a parameter to the template ROS 2 node.

```text
Read CLAUDE.md and sops/code-review-checklist.md. In templates/ros2-node/policy_node.py add a
declared parameter max_joint_vel_rad_s (default 0.5, with a description) and clamp the action in
_tick before publishing. Scope: that one file plus a pytest in templates/ros2-node/tests/ that
runs without a ROS graph (import rclpy, no spin). Do not touch the QoS, the watchdog, or the
launch pattern. Run the test in the rosdev env and paste the output. Reply: what changed in two
sentences, then the test output, then anything you were unsure about.
```

Good output starts with the two sentences, shows `1 passed` from the actual pytest run, and ends
with a real uncertainty, for example "the clamp is per joint; a norm clamp may be what you want
for Cartesian policies". Bad output starts with a restatement of the task, refactors the watchdog
"while it was there", or says the test passed without showing the run.

Common mistake: writing the task in the chat the way you would say it to a colleague who shares
your head. "Add velocity limiting to the policy node" gives the agent three legitimate readings.
Write the file list and the check every time; it costs one minute.

Checklist for a task prompt:

- [ ] Files or packages in scope, and at least one thing explicitly out of scope.
- [ ] The SOP or checklist to read first, by path.
- [ ] The command that proves it done, and the environment to run it in (`rll` or `rosdev`,
      `env -u PYTHONPATH` in `rll`).
- [ ] The reply shape: answer, evidence, uncertainty.

## Lesson 2. Plan before code

The docs recommend four phases, explore, plan, implement, commit, with plan mode (`Shift+Tab`
until the status bar shows plan mode, or `claude --permission-mode plan`) for the first two so the
agent reads and proposes without editing ([Best practices](https://code.claude.com/docs/en/best-practices)).
For this repo the plan has a fixed shape already: `sops/experiment-protocol.md` says the
hypothesis and the decision it informs are written before anything runs, and `CLAUDE.md` says
every experiment gets a record in `experiments/` first. A plan for code is the same document
with tests in place of trials: name the tests before the implementation, and the implementation
is done when they pass.

The same docs say when to skip it: "if you could describe the diff in one sentence, skip the
plan". A typo, a log line, a renamed parameter, a one-line clamp: ask for it directly. Planning
pays when the change spans files, when you do not know the code, or when the approach is open.
A LeRobot training run is always the second kind, because the expensive part is GPU hours, not
typing.

Worked example: a training run on the meat-cell sim data.

```text
Plan mode. Read sops/experiment-protocol.md, experiments/TEMPLATE.md and library/tools/lerobot.md.
I want to test whether ACT with chunk_size=100 beats the chunk_size=50 baseline on the
so101 intercept task. Draft experiments/2026-09-09-act-chunk-100.md with hypothesis, the decision
it informs, the exact lerobot-train command, seed, trial count and success definition for the sim
eval, and the stop rule. Name the two checks you will run before training starts (dataset
checksum, config diff against the baseline). Do not run anything.
```

Good output is a filled experiment record where the hypothesis names a number ("success rate on
the fixed 50-init list rises from 31/50 to at least 38/50, else the chunk change is rejected"),
the train command carries `--seed`, `--output_dir` and `--job_name` in the checkpoint naming
convention, and the two checks are commands, not intentions. Then you press `Shift+Tab`, approve,
and say "run the two checks, then start training in the background and report the first 200
steps of loss".

Common mistake: letting the agent plan and implement in one turn. The plan then describes what
was already done, and the tests get written to pass the code instead of the other way around.

## Lesson 3. Tests and hooks as the agent's reviewer

An agent stops when the work looks done. The docs put it plainly: without a check it can run,
"looks done" is the only signal, and you become the verification loop
([Best practices](https://code.claude.com/docs/en/best-practices)). The template package answers
this with one line, `ruff format . && ruff check . && mypy src && pytest`
(`templates/python-package/README.md`). A hook makes the check run without being asked. Hooks
are "deterministic and guarantee the action happens", unlike `CLAUDE.md` lines which are advisory
([Hooks guide](https://code.claude.com/docs/en/hooks-guide)). Exit code 2 from a hook blocks the
action and feeds stderr back to the agent.

This setup already has one: `~/.claude/settings.json` runs `~/.claude/hooks/slop-check.py` after
every `Write` or `Edit`. It scans prose and code for em-dashes, banned words and filler, and
exits 2 with the line numbers, so the agent has to fix them before moving on. The same mechanism
carries formatting and typing. Add a `PostToolUse` hook on `Edit|Write` that runs `ruff format`
and `ruff check --fix` on the edited file when it is Python, and a `Stop` hook that runs the
package's test line and blocks the turn until it passes. A `PreToolUse` hook on `Bash` that
exits 2 on `git push.*master` is the local substitute for a protected branch until the repo has
a remote; once it does, protect `master` on GitHub and require the checks in a pull request.

Worked example: run the existing hook by hand on a file, the way the agent sees it.

```bash
echo '{"tool_input":{"file_path":"library/topics/how-to-work-with-agents.md"}}' \
  | python3 ~/.claude/hooks/slop-check.py; echo "exit $?"
```

Good output is `exit 0` and nothing else. A hit looks like
`library/topics/x.md:41: em-dash: ...` on stderr and `exit 2`. Then the formatter hook, written
into `.claude/settings.json` in the repo:

```json
{"hooks": {"PostToolUse": [{"matcher": "Edit|Write", "hooks": [{"type": "command",
  "command": "f=$(jq -r .tool_input.file_path); case \"$f\" in *.py) ruff format \"$f\" && ruff check --fix \"$f\";; esac"}]}]}}
```

The rule that is not negotiable: never merge what the agent did not run. A diff whose reply says
"tests should pass" was not tested. Ask for the command and its output, verbatim, and read the
counts. `CLAUDE.md` says "report failures verbatim"; hold the agent to it and hold yourself to
reading them.

Common mistake: a `CLAUDE.md` rule for something a hook should own. If you find yourself adding
"always run ruff" to the contract, delete the line and write the hook. The docs say the same:
convert a rule the agent keeps following anyway into a hook and prune the file.

## Lesson 4. Sim first, hardware last

`WORKFLOW.md` says everything works in sim first, and `library/topics/sim-first-workflow.md` gives
the daily checklist before robot time: twin matches calibration, the named checkpoint passes the
nominal and perturbed evals with k/n recorded, the policy node runs against
`mock_components/GenericSystem` at the real control rate, observation parity holds between twin
and bag, the safety envelope is verified in sim and copied into the field checklist. A coding
agent fits this loop on the sim side and only on the sim side. It can build the twin, write the
node, run the evals and fill the experiment record. It does not command a real robot.

The safety note gives the structure that makes this a rule you can enforce rather than a habit
you hope for. The shield pattern puts a deterministic software layer between any action source
and the controller: joint limits tighter than the URDF, a workspace box, a force threshold with
hold and retreat, a stale-action watchdog that holds then stops and never replays the last
action, a deadman, and monitor-triggered hold; outside it sits the PL-rated safety controller
that the policy PC "has no wire into" (`library/topics/safety-for-learned-policies.md`, shield
section). An agent is an action source. It sits upstream of the shield like the policy does, and
during commissioning it sits upstream of a human holding the enable.

The rule: an agent never sends a motion command to a real robot without a human in the loop.
"In the loop" means a person holding the deadman, watching the arm, with the pendant e-stop in
reach, and the agent's command going through the same shield as the policy's. Three mechanisms
back it:

- [ ] Read-only ROS access for the agent. The
      [ros-mcp-server](https://github.com/robotmcp/ros-mcp-server) exposes topics, services and
      actions over rosbridge for ROS 2 Humble; it can publish as well as subscribe, so the
      restriction is yours to configure. In `.claude/settings.json` deny the publishing tools and
      allow the reading ones; deny rules win over allow rules, and a bare tool name in deny
      removes the tool from the agent's context entirely
      ([Permissions](https://code.claude.com/docs/en/permissions)). On the robot PC, run the
      bridge only against the sim namespace and never on the network segment that reaches the
      real controller (from practice, unverified).
- [ ] Simulation-only tool access. Any script the agent may run that talks to a controller takes
      a `--dry-run` flag that logs the command it would send and exits, and the agent's Bash
      allowlist contains the dry-run form only.
- [ ] The bring-up SOP. `sops/robot-bring-up.md` puts the shield probe (out-of-box target, 10x
      velocity, silence, corrupt chunk) in scripted test clients that are tested in sim before
      travel, and states that no motion happens before the safety chain section is complete.
      The agent writes and runs those clients in sim; you run them on site.

Worked example: a read-only inspection during a sim session.

```json
{"permissions": {
  "allow": ["mcp__ros__get_topics", "mcp__ros__get_topic_type", "mcp__ros__subscribe_once",
            "mcp__ros__get_services", "Bash(ros2 topic list*)", "Bash(ros2 topic echo*)",
            "Bash(ros2 topic hz*)", "Bash(python -m intercept.send_target --dry-run*)"],
  "deny":  ["mcp__ros__publish", "mcp__ros__call_service", "mcp__ros__send_action_goal",
            "Bash(ros2 topic pub*)", "Bash(ros2 action send_goal*)", "Bash(ros2 service call*)"]}}
```

Tool names follow the server's own naming; check `claude mcp list` and the server's tool list
before copying these. Then the prompt:

```text
The twin is up in MuJoCo with mujoco_ros2_control. Measure the loop period of policy_node at
20 Hz for 60 s with ros2 topic hz on /policy_action, and report the histogram of periods as a
table with p50, p95 and max in ms. If p95 exceeds 55 ms, say which callback you suspect and why;
do not change any code in this turn.
```

Good output is the table with three numbers, the sample count, and the suspect named with a line
reference. A reply that "tried publishing a test target to check the pipeline" is the failure
mode the deny list exists for, and if you see it in sim you fix the permissions before the next
office day, not after.

Common mistake: treating "it is only the sim" as a reason to give the agent full tool access,
then reusing the same `settings.json` on the robot PC. Keep one permission file per machine role
and diff them before travel.

## Lesson 5. Parallel work

One session has one context window. Research that reads forty papers, a batch of paper entries,
or three independent ROS packages will fill it. Subagents run in their own context and report a
summary back, which is why the docs recommend them for anything that reads many files
([Best practices](https://code.claude.com/docs/en/best-practices)). For work that edits files,
worktrees keep parallel sessions from colliding: `claude --worktree <name>` creates
`.claude/worktrees/<name>/` on branch `worktree-<name>`, and a subagent with `isolation: worktree`
in its frontmatter gets the same ([Worktrees](https://code.claude.com/docs/en/worktrees)). The
`/research-pass` skill in this repo is the local instance: three to six `general-purpose` agents,
one per note or paper batch, validated by the parent afterwards.

Cost is real. Anthropic's account of its multi-agent research system reports that agents use
about 4x the tokens of a chat and multi-agent systems about 15x, and that the lead agent gives
each subagent "an objective, an output format, guidance on the tools and sources to use, and
clear task boundaries"
([How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system),
2025-06-13). The same post sizes effort to the question: one agent with 3 to 10 tool calls for a
fact, 2 to 4 subagents for a comparison, more than 10 for open research. The research-pass skill
adds the rate-limit reality: "if an agent dies on a rate limit, check its files on disk before
relaunching; partial files are usually complete."

Worked example: a batch of three paper entries for the conveyor tracking backlog.

```text
Launch 3 general-purpose agents in parallel, one per paper: [arXiv ids]. Each prompt: read
CLAUDE.md, library/README.md and library/papers/black-2024-pi0.md for format; writing rules from
~/.claude/CLAUDE.md; read the full paper, not the abstract; every number carries hardware, trial
count and date; unsupported claims are tagged (unverified); write library/papers/<author>-<year>-<slug>.md;
run the slop-check hook on the file; report a 5-line summary plus a list of unverified items. Do
not rebuild or publish. When all three report, run the build, check
grep -c 'class="dead"' site/index.html is 0, and give me the three summaries.
```

A subagent prompt has four parts, and the skill file spells them out: format (the files to read as
examples and the rules to obey), sources (full papers, primary docs, no abstracts), a validation
step the agent runs on its own output (the hook, a build, a test), and the report shape (line
count, unverified list, no publishing). Good output from the parent is three summaries, a dead-link
count of 0, and a list of what each agent could not verify. An agent that reports "done" with no
unverified list either read nothing hard or is hiding it.

Sizing waves (from practice, unverified): three to six agents per wave; one wave at a time; each
agent owns files no other agent touches; retry a dead agent once after checking the disk. Spend
subagents on reading, not on judgement calls that need your context.

Common mistake: parallelising work that shares a file. Two agents editing
`library/topics/00-study-path.md` produce a merge you resolve by hand. Give the shared file to the
parent and let it apply the rows the agents report.

## Lesson 6. Skills and memory

A task you have given the agent three times with the same instructions is a skill. A skill is a
`SKILL.md` under `.claude/skills/<name>/` with a name, a description and the procedure; the agent
loads it on demand instead of carrying it in every session, which is the docs' argument for
moving anything situational out of `CLAUDE.md` and into a skill
([Best practices](https://code.claude.com/docs/en/best-practices)). This repo has five: `/ask`,
`/brief`, `/inbox`, `/research-pass`, `/retro`. Each is short, names its inputs, gives a numbered
procedure, fixes the report shape, and ends with a pointer to the writing rules. Copy that shape.

Memory is the other store, and the line between the two is simple. The repo holds anything a
colleague or a future you needs: notes, SOPs, experiment records, skills. Memory holds what the
agent needs to work with you specifically and that would be odd in a repo: your role, your
quality bar, the artifact URL, the PYTHONPATH gotcha on this machine. `/retro` is the loop that
feeds both. It reads `git log`, field notes and experiment records for the week, names strengths
and weaknesses with evidence for both operators, builds or proposes the fix for each missing
capability in the same turn, and updates `retros/capabilities.md`, the ledger of what each of you
can do with states gap, learning, working, proven on site. The ledger is where "the agent should
be able to X" turns into a row with evidence and a next step.

Worked example: turning the bring-up test clients into a skill.

```text
Create .claude/skills/shield-probe/SKILL.md, user-invocable, argument-hint "<twin launch file>".
Procedure: launch the twin with the given file in the rosdev env; run the four scripted shield
probes from sops/robot-bring-up.md (out-of-box target, 10x velocity, 2 s silence, corrupt chunk)
against policy_node; for each, record whether the shield held, the latency from probe to hold in
ms, and the log line; write the table into the open experiment record under Results; report the
table and any probe that did not hold, verbatim. Keep it under 40 lines. Model it on
.claude/skills/research-pass/SKILL.md.
```

Good output is a skill file that a stranger could run, with the four probes as commands and the
report shape fixed. Test it: `/shield-probe launch/twin.launch.py` should produce the table
without a follow-up question.

Common mistake: putting project facts in memory. "The intercept task uses a 50-init list" belongs
in the experiment record or the task note; memory that duplicates the repo drifts from it, and the
agent then has two sources that disagree.

## Lesson 7. Review and ship

Reading an agent's diff is a different skill from reading a colleague's. A colleague's diff has one
author's intent behind it; an agent's diff can be locally correct in every hunk and still not do
the task, because the task was narrowed in step one. Read the diff against the prompt first: does
it touch the files in scope and no others, is the named test present, does the reply show the
run. Then read it with `sops/code-review-checklist.md`: units and frames explicit, shapes at
boundaries, seeds logged, limits in code not config, a dry-run mode that was exercised, ruff and
mypy clean, one logical change, message explains why. `/code-review` runs the same checklist in a
fresh subagent; the docs' point about a fresh reviewer is that it is not biased toward code it
just wrote, and its caution is that a reviewer told to find gaps will find some, so ask for gaps
that affect correctness and treat the rest as optional
([Best practices](https://code.claude.com/docs/en/best-practices)).

The finish review pattern this repo used for the manual's redesign is the same idea with the
verdict made explicit. A separate reviewer agent (`.claude/agents/impeccable-finish-reviewer.md`)
edits nothing, checks evidence exists before judging anything, returns one disposition word from
a fixed vocabulary (recapture, rebuild, fix, ship) plus an ordered list of material fixes, and on
the second pass scores each fix as resolved, partial or unresolved against new evidence only; "a
claimed fix you cannot see in the recaptures is unresolved". Applied to code: reviewer runs in a
fresh context, sees the diff, the plan and the test output, returns a disposition and ordered
fixes, and the second pass re-runs the tests rather than reading the author's claim that they
pass. The redesign passed a three-round review of this kind (`retros/capabilities.md`).

Worked example: the review and the PR for the clamp from lesson 1.

```text
Use a subagent to review the diff on worktree-vel-clamp against the task in
experiments/2026-09-09-vel-clamp.md and sops/code-review-checklist.md. Return: disposition
(fix or ship), then material fixes in order, only those that affect correctness or the stated
scope. Do not edit.
```

After fixes, the commit and PR:

```text
Commit with subject "Clamp policy actions to max_joint_vel_rad_s" and a body that says why (the
shield note's rule that limits live in code, not config), referencing the experiment file. Open a
PR whose description has: the test command and its output pasted, the loop-period table from the
twin run, and the trial count for the sim eval (k/n). Screenshots only if a UI changed.
```

Good output: a subject under 72 characters in the imperative, a body with the reason and the file
reference, a PR with numbers that carry n, and no "improved" or "enhanced" anywhere. The `git`
section of `CLAUDE.md` is the standard; the extra rule for agent-authored PRs is that the evidence
is pasted, not described.

Common mistake: approving because the tests are green. Green tests prove the code does what the
tests say; they do not prove the tests say what the task said. Read the test names against the
plan before the diff.

## Lesson 8. A day and a week

The daily rhythm is in `WORKFLOW.md`. Morning: `/inbox` for triage and the day's plan; drafts are
created, nothing is sent without "send". Through the day: `/ask <question>` for anything grounded
in the library, with manual addresses in the answer; `/brief <topic>` when something has to be
shown. Evening or overnight: `/research-pass [priorities]`, which adds notes, rebuilds, republishes
and commits. Friday: `/retro`. Before an office day, the sim-first checklist and the field
deployment checklist, in that order. A session ends when the terminal closes, so until the repo
has a private remote and `/schedule` routines, `/loop /research-pass` self-paces in an open session.

The weekend project pattern is the week's rhythm compressed. Pick one project that is small
enough to ship in two days and real enough that shipping it matters. Write the contract: an
experiment record or a task note with scope, checks, and reply shape (lesson 1). Run passes:
plan, implement against named tests, review in a fresh context, fix (lessons 2, 3, 7). Ship: a
PR with evidence, a rebuilt manual, a retro entry with what the agent did well and badly and one
process change (lessons 6, 7). The project for the weekend of 2026-09-12 is open; the shield probe
skill, a MuJoCo twin of the intercept cell, or the policy node with a real clamp and watchdog test
each fit the size.

Checklist for the first weekend project together:

- [ ] Saturday 09:00: project chosen, contract written in `experiments/` or a task note, out-of-scope
      list has at least two items, done-check is a command.
- [ ] Plan mode session: plan with named tests, approved by you before any edit.
- [ ] `.claude/settings.json` has the ruff hook and the deny list from lesson 4; slop-check runs
      on every write.
- [ ] Each implementation pass ends with pasted test output; no "should pass".
- [ ] Every real-data or sim number in the record carries n and conditions.
- [ ] One fresh-context review with a disposition word; fixes scored on the second pass.
- [ ] Sunday 18:00: commit with a why, manual rebuilt and republished, `retros/capabilities.md` row
      added for the capability the project exercised, one process change written down.

The common mistake at the week scale is running passes without a contract, so that the agent
works all night and Monday's review has nothing to check the output against. Write the contract
first, even for a weekend.

## What to practise this week

1. Write five task prompts using the lesson 1 checklist; count how many needed a follow-up
   clarification from the agent. Target: at most one.
2. Add the ruff `PostToolUse` hook and the `git push` guard to `.claude/settings.json`; confirm
   each fires by triggering it on purpose once. Target: two hooks, two observed blocks or fixes.
3. Run one experiment through the full record: hypothesis with a number, plan in plan mode, train
   in the background, result with k/n, decision line filled. Target: one record with every
   section non-empty.
4. Launch one research wave of three subagents with the four-part prompt; record tokens used and
   time to completion in the pass log. Target: dead-link count 0 after build, all three summaries
   received.
5. Review two agent diffs with `/code-review` in a fresh context and record the disposition and
   fix count for each in Friday's retro. Target: both PRs carry pasted test output before merge.
