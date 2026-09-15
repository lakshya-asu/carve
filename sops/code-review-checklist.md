---
title: Code review checklist
date: 2026-09-05
tags: [sop, code-quality]
status: draft
---

# Code review checklist

Run this before every push. Claude runs it on request with `/code-review`.

## Correctness

- [ ] Does what the docstring says. Edge cases: empty input, single element, NaN, unit mismatch.
- [ ] Tensor shapes and dtypes asserted or documented at boundaries.
- [ ] Coordinate frames and units explicit. No silent degree/radian or mm/m mixing.
- [ ] Seeds set and logged. Non-determinism sources documented.
- [ ] Failure modes raise, not silently return defaults.

## Safety (anything that moves hardware)

- [ ] Velocity, torque, and workspace limits enforced in code, not only in config.
- [ ] Watchdog or timeout on every command stream.
- [ ] Safe default on loss of communication.
- [ ] Dry-run or simulation mode exists and was exercised.

## Quality

- [ ] `ruff format`, `ruff check`, `mypy` clean.
- [ ] Tests exist and pass. Hardware tests behind a marker.
- [ ] No dead code, no commented-out blocks, no TODOs without an owner.
- [ ] Names carry units and meaning. No single-letter names outside tight math.
- [ ] README or docstring updated if behaviour changed.

## Hygiene

- [ ] No credentials, no absolute personal paths, no weights or data in the diff.
- [ ] Commit message explains why.
- [ ] Diff is one logical change.
