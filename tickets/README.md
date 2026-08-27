# Ticket ledger

Tickets are executed in dependency order. Each ticket file contains its own acceptance tests. Status values are `ready`, `in_progress`, `blocked`, `review`, and `done`.

| Ticket | Title | Depends on | Current status |
|---|---|---|---|
| T001 | Engineering baseline and configuration validation | None | done |
| T002 | Domain message contracts | T001 | done |
| T003 | Deterministic clock and event scheduler | T002 | done |
| T004 | Frame graph and calibration math | T002 | done |
| T005 | Conveyor, encoder, and product spawning | T003, T004 | done |
| T006 | Tracking and future-pose prediction | T003, T004, T005 | done |
| T007 | Interception feasibility and plan contract | T006 | done |
| T008 | Grasp, hold, damage, and slip model | T002, T003 | done |
| T009 | Shared cell supervisor and recovery | T007, T008 | done |
| T010 | Solution A state machine | T009 | done |
| T011 | Solution B state machine | T009 | done |
| T012 | Event log, replay, and metrics | T002, T009 | done |
| T013 | Isaac adapter source structure | T002, T003, T004 | done |
| T014 | Integration tests and overnight report | T005 through T013 | done |
| T015 | Physical calibration and OEM asset replacement | T014 | blocked |
| T016 | Connect Scene 2.0 FANUC cell to the complete task pipeline | T014 | review |

The source of truth for scope is `PROBLEM_STATEMENT.md`. The source of truth for architecture is `SYSTEM_DESIGN.md`.

T014 is the durable integrated acceptance gate. It requires work inside Isaac Sim. Proxy-only code cannot satisfy it.

The durable T014 hardening profile has six scenario slots. It covers two nominal deliveries, failed grasp, solution-specific downstream unavailability, emergency stop, and stale observation. The five-seed A and B matrix and its independent artifact audit are recorded in `results/hardening/summary.json`.

The 2026-08-26 learned-vision extension also passed T014 without changing ticket status. YOLO26 segmentation consumed rendered Isaac RGB, produced masks used with rendered depth, and drove complete four-cycle A and B suites. Evidence is under `results/yolo`.

The complete in-simulator FANUC pipeline now passes for Solution A and Solution B. T016 is in review because its simulator acceptance is complete but the separate ROS 2 and MoveIt `FollowJointTrajectory` bridge is not installed or commissioned. T015 remains blocked on physical calibration, production gripper selection, cutter I/O, and real safety evidence.
