---
title: Capabilities ledger
date: 2026-09-07
tags: [retro, reference]
status: draft
---

# Capabilities ledger

Running list of what each of us needs to be able to do for end-to-end
robotics on production systems, with the current state and the evidence.
Updated at every retro. States: gap, learning, working, proven on site.

## Lakshya

| Capability | State | Evidence | Next step |
|------------|-------|----------|-----------|
| Robot learning methods (IL, RL, VLA) | proven | Stated expert; prior VLM navigation work | Review the draft notes in chapter 2 and mark reviewed or stale |
| ROS 2 in production | learning | Asked to be taught ROS 2 properly (2026-09-05) | Run the reference policy node and the bring-up SOP on one arm |
| Meat cell domain | gap | New assignment (2026-09-06) | Two-week plan in the meat-cutting note; site survey template |
| Customer-site practice | gap | First forward-deployed role | Field engineer handbook; first daily update |

## Claude

| Capability | State | Evidence | Next step |
|------------|-------|----------|-----------|
| Library-grounded answers | working | `/ask` skill; 91 sourced entries | Measure: does every answer cite an address |
| Good-looking UI on request | working | Manual redesign passed a three-round review | `/brief` skill; keep DESIGN.md as the authority |
| DDS and ROS 2 internals | learning | ros2-in-depth note; reference node run on Humble | Test on multi-machine and Zenoh; verify on janus |
| Reliable work on real systems | gap | No real robot touched yet | First bring-up together, with the SOP, at reduced speed |
| Email and calendar management | learning | Gmail tools connected; `/inbox` skill | No calendar tool yet; ask what the meeting source is |
| Daily research passes | working | Five passes in two days | Needs a schedule that survives the session |
| Weekly retrospectives | learning | Template and ledger created | First retro 2026-09-12 |
