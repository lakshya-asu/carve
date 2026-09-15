---
title: Safety and assurance for learned robot policies
date: 2026-09-05
tags: [topic, safety, standards, deployment, vla, monitoring, hazard-analysis, assurance]
status: draft
source: synthesis (primary links inline and in Sources)
---

# Safety and assurance for learned robot policies in customer deployments

## What it is

A learned policy is a component whose output cannot be enumerated in advance. Machinery safety
standards were written for components whose behaviour can. The engineering that reconciles the
two has three parts: a deterministic shield that bounds what the policy is allowed to command,
runtime monitors that notice when the policy is about to fail, and evidence (hazard analysis,
test protocols, logs) that lets an integrator and a customer sign the cell off. None of the
standards below certify a neural network. They certify the wiring around it, and they define
what the integrator's risk assessment must cover. The learning engineer's job is to make the
policy fit inside that wiring and to produce the evidence the risk assessment needs.

## Why it matters in the field

- The customer's cell is approved per installation under ISO 10218-2, by the integrator, on the
  basis of an ISO 12100 risk assessment. A new policy checkpoint is a change to the cell. If the
  risk assessment does not already cover "the policy commands something unexpected", the change
  is not approved ([ISO 12100:2010](https://www.iso.org/standard/51528.html),
  [ISO 10218-2:2025](https://www.iso.org/standard/73934.html)).
- The EU Machinery Regulation (EU) 2023/1230 applies from 20 January 2027 and lists
  "safety components with fully or partially self-evolving behaviour using machine learning
  approaches" among the high-risk machinery products in Annex I Part A, which forces third-party
  conformity assessment ([EUR-Lex](https://eur-lex.europa.eu/eli/reg/2023/1230/oj)). Keeping the
  learned policy out of the safety function is what keeps it out of that annex (interpretation,
  unverified with a notified body).
- Policies fail in ways integrators have not seen. A universal adversarial patch on the gripper
  breaks essentially all originally solvable LIBERO tasks on pi0 and pi0.5
  ([DRIFT, arXiv:2608.03207](https://arxiv.org/abs/2608.03207)); a single adversarial texture
  cuts mean task success from 90.0% to 48.4% across manipulation tasks
  ([UniTexture, arXiv:2608.13453](https://arxiv.org/abs/2608.13453)); prompt jailbreaks reached
  100% attack success on a commercial Unitree Go2
  ([RoboPAIR, arXiv:2410.13691](https://arxiv.org/abs/2410.13691)).
- Latency is a safety parameter. The ISO speed and separation monitoring formula puts the whole
  system reaction time, inference included, inside the protective distance; NIST measured a
  113 ms robot reaction time and a 220 ms position-reporting delay on their testbed
  ([Marvel and Norcross, NIST](https://pmc.ncbi.nlm.nih.gov/articles/PMC5117641/)).
- The first serious incident on a customer site ends the deployment. The evidence in this note is
  what lets you say, before that day, what the cell can and cannot do.

## Standards map

Status checked 2026-09-05 where a link is given. ISO catalogue pages were not reachable from this
machine on that date, so edition details marked (unverified) come from secondary sources or memory.

| Standard | Covers | What the learning engineer must know | Whose job |
|---|---|---|---|
| ISO 10218-1:2025 | Industrial robot (the arm and controller) safety requirements. Replaced the 2011 edition, absorbed ISO/TS 15066's collaborative content as normative text, added functional safety and cybersecurity clauses and new robot classes ([arXiv:2602.17822](https://arxiv.org/abs/2602.17822); [ISO catalogue](https://www.iso.org/standard/73933.html)) | Which safety functions the controller offers (safety-rated monitored stop, speed and separation monitoring, power and force limiting, joint and Cartesian limits) and their configured values. The 2011 edition required safety functions at PL d Category 3 unless the risk assessment said otherwise; carry-over into 2025 (unverified) | Robot manufacturer |
| ISO 10218-2:2025 | Robot systems and integration, including collaborative applications, in the cell ([ISO catalogue](https://www.iso.org/standard/73934.html)) | The integrator's risk assessment names the hazards the shield must bound. Get a copy. Your monitors and test evidence feed it | Integrator |
| ISO/TS 15066:2016 | Collaborative operation: four modes, body-region force and pressure limits for power and force limiting ([ISO catalogue](https://www.iso.org/standard/62996.html)) | Content is now normative in 10218:2025 ([arXiv:2602.17822](https://arxiv.org/abs/2602.17822)). Withdrawal status of the TS itself (unverified). The body-region limits (quasi-static 65 to 220 N by region, transient 2x) are what a force threshold in the shield must be set against (values unverified against the text this session) | Integrator sets, you respect |
| ISO 13482:2014 | Personal care robots: mobile servant, physical assistant, person carrier; excludes industrial robots ([ISO catalogue](https://www.iso.org/standard/53820.html)) | Applies to home and service deployments, not the factory cell. Different hazard list (person carrying, pinch, tipping) | Manufacturer |
| ISO 3691-4:2023 | Driverless industrial trucks and their systems, i.e. AMRs and AGVs in the workplace ([ISO catalogue](https://www.iso.org/standard/83545.html)) | A learned navigation or loco-manipulation policy on a mobile base sits under this, not 10218. Personnel detection zones, speed limits by zone, emergency and protective stops | Truck manufacturer and integrator |
| IEC 61508 (parts 1 to 7) | Generic functional safety of E/E/PE systems. SIL 1 to 4; high-demand PFH bands SIL 2: 1e-7 to 1e-6 per hour, SIL 3: 1e-8 to 1e-7 ([IEC 61508 overview](https://en.wikipedia.org/wiki/IEC_61508)) | Parent of everything below. Part 3 (software) has no route for a trained network to be a safety function at any SIL; ISO/IEC TR 5469:2024 discusses AI in functional safety and says the same in longer form ([ISO catalogue](https://www.iso.org/standard/81283.html), content unverified) | Safety engineer |
| IEC 62061:2021 | Machinery-sector application of IEC 61508 for safety-related control systems ([IEC webstore](https://webstore.iec.ch/publication/59927)) | SIL-based alternative to ISO 13849 for the cell's safety PLC and safety I/O | Integrator |
| ISO 13849-1:2023 (4th ed.) | Safety-related parts of control systems. PL a to e as PFHd bands, PL a below 1e-4 down to PL e at or above 1e-8 per hour; categories B, 1, 2, 3, 4 with Category 3 = redundant with cross-monitoring ([ISO 13849 overview](https://en.wikipedia.org/wiki/ISO_13849); [ISO catalogue](https://www.iso.org/standard/73481.html)) | Any stop, limit or monitor you want the risk assessment to credit must be implemented in a PL-rated channel (safety PLC, robot safety controller). A Python watchdog on a Linux box is PL nothing. It reduces demand on the safety function; it is not one | Integrator |
| IEC 60204-1:2016 | Electrical equipment of machines. Stop category 0 (immediate power removal), 1 (controlled stop, then power off), 2 (controlled stop, power on) ([IEC webstore](https://webstore.iec.ch/publication/26037), clause numbers unverified) | Which category each e-stop, guard and protective stop input triggers; read it off the robot's safety configuration with the integrator | Integrator |
| ISO 13855:2010 | Positioning of safeguards; approach speeds 1600 mm/s (separation over 500 mm) and 2000 mm/s ([NIST](https://pmc.ncbi.nlm.nih.gov/articles/PMC5117641/)) | Feeds the protective distance formula below | Integrator |
| ISO 12100:2010 | Risk assessment and risk reduction method for machinery ([ISO catalogue](https://www.iso.org/standard/51528.html)) | The hazard analysis in this note is input to a 12100 assessment, not a replacement | Integrator |
| ANSI/A3 R15.06 | US national adoption of ISO 10218 ([A3 standards page](https://www.automate.org/robotics/standards)); a 2025 revision adopting 10218:2025 (unverified) | Same content as 10218 for US sites | Integrator |
| UL 4600 | Safety evaluation of autonomous products, organised around a safety case ([UL](https://www.shopulstandards.com/ProductDetail.aspx?productId=UL4600)); edition and year (unverified) | The only standard in this table that expects a machine-learning component and asks for a structured argument with evidence. Use its safety-case shape for the evidence section below even if nobody asks for UL 4600 compliance | Product manufacturer |
| ISO/PAS 8800:2024 | Road vehicles, safety and AI ([ISO catalogue](https://www.iso.org/standard/83303.html), content unverified) | Automotive, but the vocabulary (AI safety lifecycle, data-related safety requirements, out-of-distribution) is what customers with automotive backgrounds will use | Reference |

Division of labour in one sentence: the integrator owns the risk assessment and the PL-rated safety
functions; the learning engineer owns the shield configuration, the monitors, the test evidence,
and the honest statement of what the policy has and has not been tested on.

## The shield pattern

Two independent layers bound a non-deterministic policy. The outer one is the robot's own safety
controller plus the cell's safety PLC, PL-rated, configured by the integrator. The inner one is
software you write, unrated, whose purpose is to make sure the outer layer almost never has to act.

```
policy action ──► software shield (unrated, yours) ──► controller ──► robot safety controller (PL d) ──► drives
                  clamps, workspace box, F/T hold,                     joint/speed/torque limits,
                  stale-action watchdog, deadman,                      safety-rated monitored stop,
                  monitor-triggered hold                               SSM zones, PFL, e-stop chain
                  catches: policy is wrong                             catches: everything upstream is wrong
```

Inner layer, in the order actions pass through it:

1. **Joint position, velocity, acceleration limits.** Tighter than the URDF and tighter than the
   pendant; the tighter of the customer's workspace and the training distribution. Clamp, log the
   clamp, count clamps per episode.
2. **Workspace bounds.** A Cartesian box or mesh around the task; approach and retreat moves may
   leave it under scripted control only. MoveIt Servo gives joint and singularity scaling for free
   if the policy speaks end-effector space (see [[library/topics/connecting-to-real-robots]]).
3. **Force and torque threshold.** External wrench estimate or F/T sensor; above threshold hold,
   then retreat along the last approach direction. Threshold set below the TS 15066 body-region
   limit the integrator chose, with margin for sensor bias measured at bring-up.
4. **Stale-action watchdog.** No fresh, valid action within T_wd (a few control ticks) means hold,
   then decelerate to stop. Never replay the last action. The forward command controllers in
   ros2_control have no timeout of their own
   ([forward_command_controller](https://control.ros.org/humble/doc/ros2_controllers/forward_command_controller/doc/userdoc.html)).
5. **Deadman and operator hold.** An operator-held enable during commissioning and canary runs;
   release stops the client from publishing, and the watchdog does the rest.
6. **Monitor-triggered hold.** Any runtime monitor below can request the same hold.

Outer layer, configured by the integrator and read back by you:

- **Safety-rated monitored stop**: robot stands still with drives powered while a person is in the
  collaborative space; motion resumes when they leave. Cheap and the default for a cell with
  occasional entry.
- **Speed and separation monitoring**: the protective distance
  `S(t0) >= int vH over (TR+TS) + int vR over TR + int vS over TS + C + ZS + ZR`, with TR the whole
  system reaction time and TS the stopping time
  ([NIST](https://pmc.ncbi.nlm.nih.gov/articles/PMC5117641/)). Every millisecond between "person
  detected" and "drives decelerating" is in TR, so a monitor that must run before a hold is issued
  lengthens S.
- **Power and force limiting**: the robot's own collision detection against body-region limits.
  Only credible on arms designed for it, and only for the payload and tooling in the assessment.
- **Protective stop categories**: category 1 for guard and light-curtain inputs is common so the
  arm brakes under control; category 0 for e-stop buttons on some controllers. Read the mapping
  off the safety configuration and record it (from field, unverified as a general rule).

The rule that keeps both layers honest: the policy PC has no wire into the safety chain. It can
request a hold through the controller; it cannot inhibit a stop.

## Runtime monitoring

Monitors do not make the cell safe. They reduce how often the shield acts and they give the
operator time. Four kinds are in use, with different maturity.

**Out-of-distribution and failure detection on policy internals.** SAFE trains a small head on
VLA hidden features to output a scalar failure likelihood and thresholds it with conformal
prediction; tested on OpenVLA, pi0 and pi0-FAST, sim and real
([Gu et al., NeurIPS 2025](https://arxiv.org/abs/2506.09937)). FAIL-Detect treats failure detection
as sequential OOD detection trained on successful episodes only, with conformal thresholds
([Xu et al., RSS 2025](https://arxiv.org/abs/2503.08558)). The 2026 wave adds perturbation-based
epistemic uncertainty ([PFD, arXiv:2606.20754](https://arxiv.org/abs/2606.20754)), action-space
probes for early detection ([ActProbe, arXiv:2606.08508](https://arxiv.org/abs/2606.08508)),
contrast-set training with calibration ([SAFECAST, arXiv:2608.04246](https://arxiv.org/abs/2608.04246)),
and gradient-ablation risk scores for diffusion VLAs
([GUARD, arXiv:2608.04510](https://arxiv.org/abs/2608.04510)). All report AUROC on benchmark
suites; none reports false-alarm rate per hour on a production cell, which is the number you need.

**Action anomaly detection.** Cheaper and older: statistics of the commanded action stream
(jerk, clamp rate, distance from the training action distribution, disagreement across ensemble
members or across denoising samples). Sinha et al. run a fast embedding-space binary classifier
in the loop and defer to a slow LLM reasoner only when it fires, keeping fallback plans feasible
while waiting ([RSS 2024](https://arxiv.org/abs/2407.08735)). Anomaly detectors on force and
proprioception reach AUROC above 0.96 on cabling and screwing tasks
([arXiv:2509.26308](https://arxiv.org/abs/2509.26308)).

**Confidence that is actually calibrated.** Raw softmax or likelihood from a large network is
overconfident; temperature scaling fixes most of it on classification
([Guo et al., ICML 2017](https://arxiv.org/abs/1706.04599)). For policies, the usable tool is
conformal prediction: KnowNo calibrates an LLM planner's option set so the robot asks for help
with a statistical guarantee ([Ren et al., CoRL 2023](https://arxiv.org/abs/2307.01928));
FabriVLA and ReconVLA apply conformal bounds to action chunks
([arXiv:2607.08575](https://arxiv.org/abs/2607.08575), [arXiv:2604.16677](https://arxiv.org/abs/2604.16677)).
A confidence score you cannot show a reliability diagram for is decoration.

**VLM-based failure detection.** A separate vision-language model watches the scene and judges
progress or failure. Code-as-Monitor compiles constraints into visual programs
([arXiv:2412.04455](https://arxiv.org/abs/2412.04455)); Guardian detects planning and execution
errors with a VLM ([arXiv:2512.01946](https://arxiv.org/abs/2512.01946)); ARMADA's FLOAT detector
reports about 95% accuracy and hands control to a human on detection
([arXiv:2510.02298](https://arxiv.org/abs/2510.02298)). These run at 1 Hz or slower on a second
GPU; they are a supervisory layer, never inside the control loop.

**Human intervention as the safety layer.** An operator with a deadman and a teleop takeover is the
monitor with the best precision and the worst latency (hundreds of ms). HIL-SERL and Sirius
make the takeover a training signal as well as a stop
([arXiv:2410.21845](https://arxiv.org/abs/2410.21845), [arXiv:2211.08416](https://arxiv.org/abs/2211.08416)).
Log every intervention with its trigger.

**Safe exploration when the policy learns on site.** Constrained RL (SafeVLA, CMDP formulation,
83.58% fewer safety violations and 3.85% higher task success than its baselines in simulation
[arXiv:2503.03480](https://arxiv.org/abs/2503.03480)); recovery policies that take over near a
constraint boundary (Recovery RL, 2 to 20x better violation-to-success trade-off in sim, about 3x
on a physical robot [arXiv:2010.15920](https://arxiv.org/abs/2010.15920)); control barrier
functions inside the flow-matching sampler
([arXiv:2607.29569](https://arxiv.org/abs/2607.29569)); language-conditioned latent safety
filters ([arXiv:2608.00315](https://arxiv.org/abs/2608.00315)). Reset-free learning and the rest
of the real-world RL safety toolbox are in [[library/topics/real-world-rl]]. On a customer site
the shield settings for an exploring policy are the same as for a frozen one; the difference is
that clamp and hold counts become part of the reward log.

## Hazard analysis worked example

STPA, because it treats the policy as a controller with unsafe control actions rather than as a
component with a failure rate ([Leveson and Thomas, STPA Handbook, March 2018](https://psas.scripts.mit.edu/home/get_file.php?name=STPA_handbook.pdf)).
HAZOP ([IEC 61882:2016](https://webstore.iec.ch/publication/24321)) works too, with guidewords
applied to each interface; STPA's four unsafe-control-action types are HAZOP guidewords for
controllers. Cell: single arm, parallel gripper, two cameras, tabletop pick-and-place of small
parts into a tray, operator loads parts from the front, light curtain across the front.

**Step 1: losses and hazards.** L1 injury to operator. L2 damage to parts, tooling, camera.
L3 loss of customer trust from an uncontrolled motion, even without contact. H1 robot moves while
a person is inside the reach envelope with the curtain bypassed or muted. H2 robot applies
force above threshold to a fixed object. H3 robot leaves the task workspace. H4 robot moves
with a stale or invalid command.

**Step 2: control structure.** Operator -> pendant and e-stop -> safety controller -> drives.
Policy -> shield -> controller -> drives. Cameras and joint states -> policy; joint states and
F/T -> shield; curtain and guards -> safety controller.

**Step 3: unsafe control actions for the policy's one control action, "command joint target".**

| UCA type | Instance | Hazard | Constraint (who enforces) |
|---|---|---|---|
| Provided, causes hazard | Target outside the tray-and-bin box | H3 | Workspace clamp (shield); joint limits (safety controller) |
| Provided, causes hazard | Target reachable only through the part fixture | H2 | F/T hold at threshold (shield); PFL if credited (safety controller) |
| Provided, causes hazard | Target commands a joint speed the training data never had, e.g. after an adversarial texture on the tray | H1, H3 | Velocity clamp (shield); SSM or monitored stop (safety controller) |
| Not provided | Policy server unreachable, no chunk | H4 | Watchdog hold then stop (shield) |
| Too early, too late, wrong order | Chunk arrives after its timestamps, is executed anyway | H4, H3 | Discard past actions; hold if the chunk is fully stale (client) |
| Stopped too soon, applied too long | Gripper close held while arm retracts with a jammed part | H2 | Gripper force limit (gripper firmware); F/T hold (shield) |

**Step 4: causal scenarios**, one per row, e.g. for row 3: lighting change or a new SKU shifts
the observation out of distribution; the policy's action becomes erratic; no monitor fires
because the OOD detector was calibrated on the lab dataset. Constraint added: OOD detector
recalibrated on the first 50 on-site episodes; the shield's velocity clamp is set from training
statistics, not the URDF. Each scenario turns into a test in the section below and a row in the
integrator's ISO 12100 assessment.

## Evidence customers ask for

Shape the folder like a safety case: claim, argument, evidence, one page per claim
(UL 4600's structure, cited above).

- **Configuration record.** Safety controller settings (photographed), shield limits, watchdog
  timeout, checkpoint hash, git SHA, dataset checksum, camera calibration hash. Everything that
  changes the behaviour of the cell, versioned together.
- **Shield test protocol.** Scripted client sends: out-of-box target, 10x velocity, F/T threshold
  exceeded against a compliant fixture, silence, a corrupted chunk. Expected: clamp, clamp, hold,
  hold, reject. Each logged with timestamp and executed joint state. Repeat after every driver,
  kernel or shield change.
- **Trial counts with intervals.** Success k/n with a Wilson interval, never a bare percentage
  ([[library/topics/policy-evaluation]]). For a safety claim, the useful statistic is the
  upper bound on the failure rate given zero observed failures: about 3/n at 95% confidence,
  so 100 clean trials bound the unsafe-event rate near 3% per trial, and 1000 near 0.3%
  ([Hanley and Lippman-Hand, JAMA 1983](https://doi.org/10.1001/jama.1983.03330370053031)).
  Say this number out loud before promising anything.
- **Coverage of initial conditions.** A written sampling scheme over part positions, orientations,
  counts, lighting and distractors, with the list of conditions actually run. Include the
  conditions the policy was not trained on and label them as such.
- **Regression suite.** The same initial-condition list, re-run on every new checkpoint, shadow
  first (new model logs actions, old model drives), then canary at reduced speed
  ([[library/topics/deployment-engineering]]).
- **Monitor evidence.** Reliability diagram or conformal coverage plot for any confidence score
  used; false-alarm count per shift and missed-failure count from the intervention log.
- **Adversarial and OOD evidence.** Which perturbations were tried (lighting, camera nudge, new
  SKU, printed patterns near the workspace) and what the shield and monitors did. Cite the
  attacks you did not test.
- **Incident log and the data kept.** For every clamp, hold, intervention, stop and contact:
  30 s of observations before and 10 s after, commanded and executed joints, shield decision,
  monitor scores, model version, operator id, outcome label. Kept in the dataset format so it is
  training data as well as evidence. The incident narrative goes in
  [[sops/incident-log-template]] within 15 minutes. US sites record recordable injuries under
  OSHA 29 CFR 1904 within 7 calendar days ([OSHA](https://www.osha.gov/recordkeeping)).

## Practical gotchas

- A `switch_controllers` call can return `ok=True` on a resource conflict, leaving the old
  controller driving ([ros2_control #1179](https://github.com/ros-controls/ros2_control/issues/1179)).
  A shield that assumes it owns the command interface does not. Read `list_hardware_interfaces`.
- Software stop categories are not hardware stop categories. A "hold" from the shield is a
  category 2 stop at best, drives powered, with the software still in the loop. It does not
  satisfy a protective-stop requirement (from field, unverified as a general rule).
- OOD detectors calibrated in the lab fire constantly on site (new lighting, new table) or never
  (threshold too loose). Recalibrate on the first on-site episodes and write down the threshold
  (from field).
- Force thresholds drift with tool weight, cable drag and temperature; a threshold that was 15 N
  above baseline at 09:00 is 5 N above it at 15:00. Re-zero on a schedule and log the baseline
  (from field, unverified as a general number).
- VLM monitors agree with the policy. Agreement bias in multimodal verifiers is documented and
  a two-step self-grounded verification improves failure detection by 25 percentage points on
  their benchmark ([arXiv:2507.11662](https://arxiv.org/abs/2507.11662)). Do not use the same
  model family as a judge of itself.
- Adversarial patches are cheap to print. Anyone with camera view of the cell and a printer can
  test the attacks above. Treat printed patterns near the workspace as a hazard in the
  assessment, and treat a camera nudge as a change to the cell.
- The stale-observation filter and the watchdog both depend on clock agreement between robot PC
  and inference host; without `chrony` or PTP, one of them is always wrong
  ([[library/topics/connecting-to-real-robots]]).
- LeRobot's policy server called `pickle.loads` on network input (CVE-2026-25874). The
  cybersecurity clauses in 10218-1:2025 are aimed at exactly this; an attacker who owns the
  policy PC owns the inner layer, which is why the outer one exists
  ([disclosure](https://chocapikk.com/posts/2026/lerobot-pickle-rce/)).

## What a forward-deployed engineer must be able to do

- Read the integrator's risk assessment and safety configuration and restate, in one page, which
  hazards the PL-rated functions cover and which the shield must cover.
- Configure and test the software shield against the scripted protocol above and produce the
  log as evidence, in under an hour on a new cell.
- Compute the protective distance for the cell with measured, not datasheet, reaction time.
- Run an STPA pass on a new task in an afternoon and turn each unsafe control action into a
  test case and a shield constraint.
- Calibrate one runtime monitor on site, show its reliability diagram or conformal coverage, and
  state its false-alarm rate per shift.
- Report success and failure rates with trial counts and intervals, and state the zero-failure
  upper bound before anyone else does.
- Fill the incident log within 15 minutes and preserve the surrounding data.
- Explain to a customer's safety officer why the neural network is not a safety function and
  what is.

## Open questions to learn hands-on

- False-alarm rate per 8-hour shift for SAFE-style and FAIL-Detect-style monitors on our arm
  and task; nothing published reports this.
- What velocity and force limits the customer's 10218-2:2025 assessment actually asks for on a
  Class II arm, and whether our training data stays inside them without retraining.
- Whether a printed adversarial texture from the 2026 papers transfers to our checkpoint and our
  cameras; one afternoon with a printer answers it.
- How the integrator treats a checkpoint update: re-assessment, delta assessment, or none; this
  decides the regression-suite cost per release.
- Whether the Machinery Regulation's "self-evolving" wording will be read to cover a frozen
  policy that is periodically retrained off-site.

## Related entries

- [[library/topics/deployment-engineering]] (shield, watchdog, rollout and rollback)
- [[library/topics/connecting-to-real-robots]] (stop categories, SSM formula, bring-up)
- [[library/topics/policy-evaluation]] (Wilson intervals, trial counts)
- [[library/topics/real-world-rl]] (safe exploration, recovery policies, reset-free learning)
- [[library/topics/vision-language-action-models]]
- [[sops/robot-bring-up]]
- [[sops/incident-log-template]]
- [[sops/experiment-protocol]]

## Sources

- Standards: ISO 10218-1:2025 https://www.iso.org/standard/73933.html ; ISO 10218-2:2025 https://www.iso.org/standard/73934.html ; ISO/TS 15066:2016 https://www.iso.org/standard/62996.html ; ISO 13482:2014 https://www.iso.org/standard/53820.html ; ISO 3691-4:2023 https://www.iso.org/standard/83545.html ; ISO 13849-1:2023 https://www.iso.org/standard/73481.html ; IEC 62061:2021 https://webstore.iec.ch/publication/59927 ; IEC 60204-1:2016 https://webstore.iec.ch/publication/26037 ; ISO 12100:2010 https://www.iso.org/standard/51528.html ; IEC 61882:2016 https://webstore.iec.ch/publication/24321 ; ISO/IEC TR 5469:2024 https://www.iso.org/standard/81283.html ; ISO/PAS 8800:2024 https://www.iso.org/standard/83303.html ; UL 4600 https://www.shopulstandards.com/ProductDetail.aspx?productId=UL4600 ; A3 standards https://www.automate.org/robotics/standards ; Regulation (EU) 2023/1230 https://eur-lex.europa.eu/eli/reg/2023/1230/oj ; OSHA recordkeeping https://www.osha.gov/recordkeeping
- Hartmann et al., "Evolution of Safety Requirements in Industrial Robotics: Comparative Analysis of ISO 10218-1/2 (2011 vs. 2025) and Integration of ISO/TS 15066" (2026). https://arxiv.org/abs/2602.17822
- Marvel and Norcross, "Implementing speed and separation monitoring in collaborative robot workcells" (NIST, 2017). https://pmc.ncbi.nlm.nih.gov/articles/PMC5117641/
- IEC 61508 and ISO 13849 overviews (secondary). https://en.wikipedia.org/wiki/IEC_61508 ; https://en.wikipedia.org/wiki/ISO_13849
- Leveson and Thomas, "STPA Handbook" (March 2018). https://psas.scripts.mit.edu/home/get_file.php?name=STPA_handbook.pdf
- Hanley and Lippman-Hand, "If nothing goes wrong, is everything all right?" JAMA 249(13), 1983. https://doi.org/10.1001/jama.1983.03330370053031
- Failure detection and monitoring: Gu et al., "SAFE: Multitask Failure Detection for Vision-Language-Action Models" (NeurIPS 2025) https://arxiv.org/abs/2506.09937 ; Xu et al., "Can We Detect Failures Without Failure Data?" (RSS 2025) https://arxiv.org/abs/2503.08558 ; Sinha et al., "Real-Time Anomaly Detection and Reactive Planning with Large Language Models" (RSS 2024) https://arxiv.org/abs/2407.08735 ; Ren et al., "Robots That Ask For Help" (KnowNo, CoRL 2023) https://arxiv.org/abs/2307.01928 ; Guo et al., "On Calibration of Modern Neural Networks" (ICML 2017) https://arxiv.org/abs/1706.04599 ; Code-as-Monitor https://arxiv.org/abs/2412.04455 ; Guardian https://arxiv.org/abs/2512.01946 ; ARMADA https://arxiv.org/abs/2510.02298 ; PFD https://arxiv.org/abs/2606.20754 ; ActProbe https://arxiv.org/abs/2606.08508 ; SAFECAST https://arxiv.org/abs/2608.04246 ; GUARD https://arxiv.org/abs/2608.04510 ; FabriVLA https://arxiv.org/abs/2607.08575 ; ReconVLA https://arxiv.org/abs/2604.16677 ; assembly anomaly detection https://arxiv.org/abs/2509.26308 ; self-grounded verification https://arxiv.org/abs/2507.11662
- Adversarial and VLA safety: Wang et al., "Exploring the Adversarial Vulnerabilities of Vision-Language-Action Models in Robotics" (2024, rev. 2025) https://arxiv.org/abs/2411.13587 ; Robey et al., "Jailbreaking LLM-Controlled Robots" (RoboPAIR, 2024) https://arxiv.org/abs/2410.13691 ; Zhang et al., "BadRobot" (ICLR 2025) https://arxiv.org/abs/2407.20242 ; DRIFT https://arxiv.org/abs/2608.03207 ; UniTexture https://arxiv.org/abs/2608.13453 ; VLAGuard https://arxiv.org/abs/2608.01028 ; SARF https://arxiv.org/abs/2608.03231 ; DURA https://arxiv.org/abs/2608.10393 ; LIBERO-Safety https://arxiv.org/abs/2606.23686 ; ForesightSafety-VLA https://arxiv.org/abs/2606.27079 ; LIBERO-VIFO https://arxiv.org/abs/2608.17600 ; OopsieVerse https://arxiv.org/abs/2606.31993
- Safe learning: Zhang et al., "SafeVLA" (NeurIPS 2025) https://arxiv.org/abs/2503.03480 ; Thananjeyan et al., "Recovery RL" (RA-L 2021) https://arxiv.org/abs/2010.15920 ; barrier-enhanced flow matching https://arxiv.org/abs/2607.29569 ; language-conditioned latent safety filters https://arxiv.org/abs/2608.00315 ; Logic-VLA https://arxiv.org/abs/2608.20556 ; HIL-SERL https://arxiv.org/abs/2410.21845 ; Sirius https://arxiv.org/abs/2211.08416
- Software: ros2_control forward_command_controller https://control.ros.org/humble/doc/ros2_controllers/forward_command_controller/doc/userdoc.html ; ros2_control #1179 https://github.com/ros-controls/ros2_control/issues/1179 ; CVE-2026-25874 disclosure https://chocapikk.com/posts/2026/lerobot-pickle-rce/
