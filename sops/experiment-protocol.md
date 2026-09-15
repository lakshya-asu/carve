---
title: Experiment protocol
date: 2026-09-05
tags: [sop, experiments, evaluation]
status: draft
---

# Experiment protocol

## Before running

1. Copy `experiments/TEMPLATE.md` to `experiments/YYYY-MM-DD-slug.md`.
2. Write the hypothesis and the decision it informs. If no decision depends on it, reconsider running it.
3. Fix the evaluation protocol: number of trials, initial condition sampling, success definition, who judges.
4. Record: git SHA, config file, dataset checksum, seed, hardware, software versions.
5. Estimate cost in time and compute. Get the baseline number first.

## During

- One variable at a time unless it is an explicit ablation grid.
- Log to a persistent tracker (W&B, MLflow, or a plain CSV committed to the run directory).
- Save checkpoints on a fixed schedule. Never overwrite.

## After

- Fill in results with the number of trials, not just a percentage.
- State the decision taken and why.
- Mark failed experiments as such. A failed experiment with a clear write-up is a valid output.
- Link the record from the relevant `library/topics/` note.

## Reporting to others

- Lead with the decision, then the evidence, then the caveats.
- Report confidence intervals or at least trial counts.
- Include one figure or table that carries the whole point.
