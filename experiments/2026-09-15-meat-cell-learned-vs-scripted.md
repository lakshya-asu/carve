---
title: Meat cell, learned intercept policy versus the scripted controller in sim
date: 2026-09-15
tags: [experiment, meat-cell, simulation, imitation-learning, act, diffusion-policy, conveyor-tracking, evaluation]
status: draft
decision: whether a learned visuomotor intercept policy earns a place in the cell before real data exists
---

# Experiment: meat-cell-learned-vs-scripted

Follow-on to [meat-cell-sim-baseline](2026-09-08-meat-cell-sim-baseline.md), which fixes the
simulator, the slab model, the scripted controller and the checker. This record is written
before the run per the [experiment protocol](../sops/experiment-protocol.md); trial counts,
endpoints and the statistical test are pre-registered below and do not change after the first
episode. No result appears here yet.

## Hypothesis

A Diffusion Policy or an ACT policy, trained on demonstrations from a privileged scripted expert
in the standardized simulator, achieves a higher success rate than the perception-based scripted
controller on a held-out split with randomized slab shape and belt speed, evaluated on the same
initial-condition list.

The mechanism the hypothesis rests on: the scripted controller is look-then-move (one frame,
then dead reckoning on the encoder; [meat note](../library/topics/meat-cutting-automation.md),
conveyor tracking). Its grasp point and approach are fixed heuristics. A closed-loop policy that
sees the slab during approach and grasp can correct for slab shape it has not been programmed
for and for in-hand motion after the grasp. The counter-hypothesis is equally plausible: the
[deformable note](../library/topics/deformable-object-manipulation.md) says outright that "the
scripted baseline might win; that is a legitimate result", and the best published learned meat
grasp is 40.6 percent at 38 s per pick ([ChicGrasp 2025](https://arxiv.org/abs/2505.08986)).

## Decision this informs

Whether to spend real-robot days and customer product on demonstrations for a full visuomotor
intercept policy (item 4 in the meat note's list of where learning earns its place), or to keep
the classical tracker plus PCA pose as the deployed controller and confine learning to
segmentation, side classification and grasp-point scoring (items 1 to 3). A learned policy that
cannot beat the scripted controller in its own simulator, on the simulator's own randomization,
does not get robot time.

## Setup

- Git SHA: fill at run start; separately for this repo (`src/robotics`, `src/applications`) and the LeRobot commit.
- Config: `src/applications/pork_leg_alignment/configs/learned_vs_scripted.yaml` (demo generation, splits, training,
  evaluation, all in one file).
- Dataset and checksum: `datasets/meat-cell-sim-expert-v1/` generated in step 2 below, with
  `DATASET.md` per the [data collection protocol](../sops/data-collection-protocol.md); SHA-256
  of the LeRobot dataset directory recorded here after generation.
- Seed(s): demo generation 20260915; training seeds 1, 2, 3 per policy; evaluation IC lists
  `ic_nominal_v1.json` and `ic_random_v1.json` (seed 20260916), disjoint from the demo seeds and
  from the validation list `ic_val_v1.json` used for checkpoint selection.
- Hardware: rented RTX 4090 for training and evaluation (the laptop's GTX 1050 Ti is rated
  "SmolVLA only" in the [compute note](../library/hardware/compute.md)); MuJoCo episodes can run
  on the laptop CPU if the baseline chose MuJoCo. Log GPU, driver, simulator version.
- Software: whichever simulator the baseline standardized on, at the pinned version;
  LeRobot at a pinned commit for ACT and Diffusion Policy; Python 3.11 in `rll`.

### Three policies under test

| Policy | Inputs | Outputs | Notes |
|---|---|---|---|
| Scripted (baseline) | Overhead depth frame at trigger, encoder count | Same seven-step controller as the baseline experiment | Perception-based, not privileged. Unchanged from 2026-09-08. |
| ACT | Overhead RGB-D 320 x 240 (downsampled from 640 x 480, assumption), joint positions, gripper width, encoder count and belt speed | Joint-position chunk | LeRobot `ACTConfig` defaults from the [imitation learning note](../library/topics/imitation-learning.md): ResNet-18, `dim_model=512`, `use_vae=True`, `kl_weight=10`, `lr=1e-5`; `chunk_size=20` at a 20 Hz policy rate (1 s of open-loop motion, design choice; the note's rule is chunk seconds = k / Hz and a 300 mm/s belt moves 300 mm in that second), temporal ensembling on with `n_action_steps=1`, `m=0.01` |
| Diffusion Policy | Same as ACT | Absolute end-effector pose plus gripper width chunk | CNN head first, per the authors' recommendation (same note); paper settings `To=2, Ta=8, Tp=16`, 100 DDPM training steps, DDIM 10 inference steps; EMA on; random crop. Absolute position control, not velocity ([Chi et al. 2023](https://arxiv.org/abs/2303.04137)) |

Both learned policies get the encoder count and belt speed so the comparison with the scripted
controller, which also gets them, is about the visuomotor loop and not about hidden state.

### Demonstration data

- Expert: the baseline's scripted controller with privileged state (true slab node positions
  instead of the depth-frame PCA), so demonstrations are as clean as the simulator allows. The
  expert and the baseline share code; only the pose source differs.
- 200 episodes on the training distribution (ACT used 50 per task, Diffusion Policy's real tasks
  used 90 to 284; imitation learning note). Successful expert episodes only; the number
  discarded is logged in `DATASET.md`.
- Training distribution (written down, logged per episode): slab length 160 to 200 mm, width 80
  to 100 mm, thickness 25 to 35 mm, mass 0.4 to 0.6 kg, belt speed uniform in {100, 200} mm/s,
  start yaw uniform in plus or minus 45 deg, start lateral position uniform across the belt
  width minus 20 mm margin, nominal material from the baseline (assumptions carried over).
- Recording at 20 Hz policy rate against the simulator's inner loop; no mixed rates.
- Diversity budget per [Lin et al. 2024](https://arxiv.org/abs/2410.18647): variation is in slab
  geometry and belt speed within the 200, not in more episodes of one slab.

### Training

- 3 seeds per policy, fixed step budget: ACT 100k steps, batch 8 (the original README's "at least
  5000 epochs" on real data is the reference; 100k steps over 200 episodes is the design choice
  and will be reported with the loss curves); Diffusion Policy 100k steps, batch 64 (assumption).
- Checkpoint every 10k steps, named `<model>-meat-cell-sim-expert-v1-<git-sha>-<step>.pt`, never
  overwritten.
- Checkpoint selection on `ic_val_v1.json` (50 ICs, training distribution) by success rate; the
  test lists are not touched until selection is frozen and written into this record.
- Tracker: W&B project `meat-cell-sim`, run names carry the seed and the git SHA.

## Evaluation protocol

Written before any policy is evaluated. From [policy evaluation](../library/topics/policy-evaluation.md).

- Trials: 200 initial conditions per split, both splits, every policy on the same list. Two
  splits:
  - nominal: `ic_nominal_v1.json`, drawn from the training distribution;
  - randomized (the hypothesis split): `ic_random_v1.json`, slab length 130 to 240 mm, width 60
    to 120 mm, mass 0.3 to 1.0 kg, belt speed uniform in {50, 150, 250, 300} mm/s (two speeds
    never seen in training), overhead camera pose perturbed by plus or minus 2 cm and plus or
    minus 2 deg per episode (the perturbation split the [sim-first note](../library/topics/sim-first-workflow.md)
    takes from LIBERO-Pro and LIBERO-Plus).
- Design: paired. Every policy sees the identical IC, so per-IC outcomes form pairs and the
  test is McNemar's on the discordant pairs (policy-only versus scripted-only successes), the
  recommended design when ICs are reproducible (policy evaluation note, comparing two policies).
- Trial count justification: the note's power table gives 199 per arm for 80 percent power to
  detect 0.90 versus 0.80 unpaired at two-sided alpha 0.05; pairing needs fewer, so 200 paired
  ICs is the pre-registered count and also the minimum detectable difference we care about
  (about 10 percentage points). Wilson 95 percent width at n = 200 near p = 0.8 is 0.11.
- Primary endpoint: success rate on the randomized split, learned minus scripted, McNemar
  two-sided. Two learned policies against one baseline, so alpha 0.025 per comparison
  (Bonferroni over the two pre-registered comparisons). The hypothesis holds if at least one
  learned policy is significantly better on the randomized split.
- Secondary endpoints, reported and not used for the pass decision: success on the nominal
  split (same test); lane-offset 95th percentile per policy; per-IC lane offset on jointly
  successful pairs, Wilcoxon signed-rank; tear-proxy and fold counts; cycle time median over
  successes; failure mode counts from the checker (no grasp, dropped in transport, outside lane,
  fold, tear proxy, timeout).
- Which seed: the primary comparison uses the seed selected on the validation list; all three
  seeds are reported so the spread is visible. No seed is selected on the test lists.
- Order: interleaved across policies within each IC (scripted, ACT, DP, then next IC), so any
  simulator drift is shared. The judge is the checker from the baseline experiment; there is no
  human judgment to blind.
- No peeking: the test lists are run once, in full. If a sequential design is wanted later it
  gets its own record with a pre-registered stopping rule ([Snyder et al. 2025](https://arxiv.org/abs/2503.10966)).
- Success definition, metrics and checker: unchanged from the baseline (offset 5 mm, yaw 5 deg,
  no tear proxy, no fold, under 8 s).
- Reporting: the note's template, k/n with Wilson interval per policy per split, the difference
  with its interval, McNemar p, and one figure: success against belt speed for the three
  policies on the randomized split.

## Build steps

1. Expert with privileged pose: a `pose_source` switch in the baseline controller; test that
   privileged and perception modes agree within 1 mm and 1 deg on a noise-free frame.
2. Demo generation to LeRobot dataset format at 20 Hz; observation parity test between the
   dataset and a live simulator observation (shapes, dtypes, value ranges); `DATASET.md` before
   anything trains.
3. IC list generation for val, nominal and randomized; commit the JSON files.
4. Training scripts for ACT and Diffusion Policy with the configs above; a smoke run of 100
   steps on 5 episodes must produce a loadable checkpoint before the full run starts.
5. Policy runner in the simulator at 20 Hz with an interpolator to the inner loop (the arms
   note's rule: a policy at 10 to 30 Hz needs an interpolator in front of every 500 Hz interface).
6. Checkpoint selection on the validation list, frozen into this record with the checkpoint
   names.
7. Evaluation run, interleaved, both splits, three policies, 1,200 episodes plus 600 for the
   validation sweeps.
8. Statistics script: Wilson intervals, McNemar, Wilcoxon, tables and the figure, from
   `episodes.csv`; unit-tested on the worked example in the policy evaluation note (17/20 versus
   13/20 reproduces Fisher p = 0.273).

Estimated cost: 2 days of build, about 6 GPU-hours of training (3 seeds x 2 policies, assumption),
1 to 2 GPU-hours of evaluation, under $10 of rented 4090 time at RunPod rates in the compute
note.

## Results

Not run.

| Condition | Successes / trials | Notes |
|-----------|--------------------|-------|

## Decision taken and why

Not yet taken. Pre-registered mapping:

| Outcome on the randomized split | Decision |
|---|---|
| A learned policy is significantly better (McNemar, alpha 0.025) and its lane-offset 95th percentile is no worse | Plan real demonstration collection for the intercept policy on the office arm, with the scripted controller kept as the fallback in the deployment shield ([safety for learned policies](../library/topics/safety-for-learned-policies.md)). The winning policy family and its config carry over. |
| No learned policy is significantly better | Deployed controller stays classical tracker plus PCA pose. Learning effort goes to segmentation, side classification and grasp-point scoring (meat note items 1 to 3), which need labelled frames, not demonstrations. |
| Learned wins on nominal but not randomized | Overfitting to the training distribution. One follow-up record: widen the demo distribution, not the episode count ([Lin et al. 2024](https://arxiv.org/abs/2410.18647)). No robot time. |
| Scripted is significantly better | Same as "no learned policy better", and the failure-mode table goes into the deformable note as the record of why. |
| All three policies under 50 percent on the randomized split | The split is wider than the controller family can handle or the simulator is misbehaving at the extremes; inspect failure modes, narrow the split in a new record with its own pre-registration. This outcome does not count for or against the hypothesis. |

## Caveats

- Everything is in one simulator with an uncalibrated slab. A win here is a reason to collect
  real data, not evidence the policy works on meat.
- The expert and the baseline share code, so the learned policies inherit the expert's grasp
  heuristic; a policy cannot discover a grasp the expert never demonstrated. That limits how much
  "better" is possible and is the reason the primary endpoint is the randomized split.
- Chunk length, policy rate, image resolution, step budgets and batch sizes are design choices
  or assumptions; each is a candidate for a later ablation record, not a change mid-run.
- Encoder count and belt speed are given to all policies as clean scalars; the real cell's
  encoder has jitter and the real camera has exposure time, neither modelled here.
- Two learned policies against one baseline with Bonferroni is conservative; if both are close to
  the threshold, the honest statement is "weak evidence", not a rerun until one passes.
