---
title: Field deployment checklist
date: 2026-09-05
tags: [sop, field, safety]
status: draft
---

# Field deployment checklist

## T-1 day: preparation

- [ ] Objective for the day written in one sentence in a new `field-notes/` file.
- [ ] Success criteria defined. What must be true by end of day.
- [ ] Software pinned: git SHA of every repo to be run, container image tags, model checkpoint hashes.
- [ ] Offline fallback: everything runs without internet (weights, pip wheels, docs cached).
- [ ] Hardware kit checked: laptop charged, spare battery, USB hubs, Ethernet cable, e-stop tested, cables labelled.
- [ ] Storage: at least 2x expected data volume free. External SSD formatted and tested.
- [ ] Contact and access: site contact, badge, network credentials, robot admin password location.
- [ ] Safety brief read for the site and robot. Know the e-stop location and the workspace boundary.

## On arrival

- [ ] Walk the workspace. Photograph it. Note lighting, floor, obstacles, people flow.
- [ ] Confirm e-stop works before any motion.
- [ ] Time sync all machines (`chrony` or `ntp`). Log clock offsets.
- [ ] Record robot firmware and driver versions.
- [ ] Run the smoke test: sensors publishing, joints readable, one small safe motion.
- [ ] Baseline data: 60 seconds of idle sensor logs for later drift checks.

## During

- [ ] Log every run: timestamp, git SHA, config, outcome, one-line observation.
- [ ] Any anomaly goes in the field note immediately, not from memory later.
- [ ] Back up data to the external SSD at least every 2 hours.
- [ ] Stop and log an incident on any contact, unexpected motion, or dropped safety system.

## Before leaving

- [ ] All data backed up in two places. Checksums recorded.
- [ ] Robot returned to safe state and documented.
- [ ] Field note has: what worked, what did not, open questions, next steps.
- [ ] Customer-facing summary drafted (3 to 5 bullets) while details are fresh.

## Within 24 hours

- [ ] Field note converted into `library/` entries and `experiments/` records.
- [ ] Bugs found in the field filed as issues with reproduction steps.
- [ ] Checklist updated if something was missing.
