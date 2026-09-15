---
title: Customer daily update and incident message
date: 2026-09-06
tags: [template, field, communication]
status: draft
---

# Customer daily update

Sent before leaving the plant, every day, to the same list. Five lines. Every number carries its
unit and count. No adjectives. Background in [[library/topics/field-engineer-handbook]].

```
Subject: [Site] cell update, YYYY-MM-DD

Done:       <what ran today, one sentence>
Evidence:   <k/n with interval, product, belt speed, condition; stops by cause and minutes;
             log or file name>
Blocked:    <what stopped progress, who can unblock it, since when>
Tomorrow:   <one objective, the window booked, who needs to be there>
Decisions:  <what we need from you, by when, and what happens if we do not get it>
```

Example of the evidence line, with the shape the numbers take:

```
Evidence:   184/200 pieces inside the cutter window (Wilson 95% 87.4 to 95.0%), pork loin,
            250 mm/s, presented-piece station, 09:40 to 11:10. Stops: 2 (jam at infeed 6 min,
            pose reject storm 3 min). Log: 2026-09-06-run03.mcap
```

Rules:

- "Done" is what ran, not what was worked on.
- "Evidence" with no trial count is not evidence; write "no trials today" instead.
- "Blocked" names a person or a thing, never "waiting".
- "Decisions" is empty only when there are none; do not fill it to look busy.
- Copy the five lines into the day's `field-notes/` file.

# Incident message

Sent within 15 minutes of any contact, injury, unexpected motion, dropped safety system, or
hygiene finding, to the production supervisor, the safety officer and your manager. Facts only;
causes are hypotheses until the log is read. The full record goes in
[[sops/incident-log-template]].

```
Subject: [Site] INCIDENT YYYY-MM-DD HH:MM, cell <name>

What happened:      <one paragraph, facts, in time order>
People:             <who was present; injury: state "none" explicitly>
Cell state now:     <stopped / locked out / running; who has the lock>
Immediate action:   <what was done in the first minutes>
Data preserved:     <log files and video from 30 s before to 10 s after, file names>
Suspected cause:    <hypothesis, marked as such, or "not yet known">
Next update:        <time, and who will send it>
Restart requires:   <named person's sign-off; nothing restarts before it>
```

Follow-up within 24 hours: the cause with evidence, what changed in the cell (with the MOC
reference), and what prevents a repeat. Never edit the original message; send a correction.

Changes: 2026-09-06 created.
