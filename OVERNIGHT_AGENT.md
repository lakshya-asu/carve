# Overnight coding instructions

## Objective

Build, launch, and test a reproducible end-to-end Isaac Sim implementation of the meat interception cell for both Solution A and Solution B. Advance through the ready tickets in `tickets/` while preserving the authoritative problem scope and architecture.

## Required reading

1. `PROBLEM_STATEMENT.md`
2. `SYSTEM_DESIGN.md`
3. `BUILD_STATUS.md`
4. `tickets/README.md`
5. The ticket file being executed

## Work order

Work in dependency order starting with T001. Complete only as many tickets as can be implemented and tested carefully. Prefer finishing an earlier ticket over partially changing several later tickets.

For each ticket:

1. Confirm dependencies are done.
2. Change the ticket status to `in_progress`.
3. Implement the smallest cohesive design satisfying the acceptance criteria.
4. Add focused tests.
5. Run the relevant tests and the existing test suite.
6. Change status to `done` only when every acceptance item has evidence.
7. Otherwise set `review` or `blocked` and record the reason in the ticket.

## Hard constraints

- Work only under `C:\Users\jainl\meat-conveyor-robot-simulation`.
- The user has accepted the NVIDIA EULA and authorizes the compatibility checker plus headless Isaac Sim startup and testing.
- Use the installed Isaac Sim 6.0.1 environment at `C:\Users\jainl\is6`.
- Keep simulator runs headless when practical and close simulator processes after each test run.
- Run simulator-dependent tests in the Isaac Sim environment. Keep simulator-independent unit tests usable in the normal project environment.
- Do not install software or change the Windows environment.
- Do not delete user files.
- Use clearly labeled reference or abstract assets when required physical or OEM assets are unavailable. Do not claim OEM fidelity.
- Do not claim physical validation, food-safety certification, real-cell safety validation, or production readiness.
- Do not weaken tests to make them pass.
- Preserve the current research and screening results as historical artifacts.
- Use plain human language and no em dash characters in documentation.

## Completion

Create or update `OVERNIGHT_REPORT.md` with completed tickets, changed files, exact commands, simulator results, A and B metrics, failures and fixes, blockers, and the exact next ticket. Leave one-command entry points for environment validation, Solution A, Solution B, and the full test suite. The delivered system must be runnable under documented simulation assumptions.
