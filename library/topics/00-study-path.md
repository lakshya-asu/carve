---
title: Study path
date: 2026-09-05
tags: [index, learning]
status: draft
source: curated
---

# Study path

Order in which to walk the topic notes. Each pass: read the note, do the
hands-on exercise, record what the field contradicted, then set the note to
`status: reviewed`.

| # | Topic | Why this order | Hands-on exercise | Status |
|---|-------|----------------|-------------------|--------|
| 1 | [3D sensing](perception-3d-sensing.md) | Every downstream skill depends on trusting the sensor. | Calibrate one camera to one robot, verify with a known object. | pass 1 |
| 2 | [Foundation vision models](perception-foundation-models.md) | Off-the-shelf perception is the fastest path to a demo. | Run detect → segment → track on a live camera at >5 Hz. | pass 1 |
| 3 | [Perception for policy learning](perception-for-policy-learning.md) | Decides camera placement before any data is collected. | Compare wrist vs third-person on 20 demos. | pass 1 |
| 4 | [Teleop and data collection](teleoperation-and-data-collection.md) | Data quality sets the ceiling on everything after. | Record 50 episodes to LeRobot format, replay, and inspect. | pass 1 |
| 5 | [Imitation learning](imitation-learning.md) | The workhorse method for customer tasks. | Train ACT and Diffusion Policy on the same 50 episodes. | pass 1 |
| 6 | [Policy evaluation](policy-evaluation.md) | Numbers reported to customers must be defensible. | Run a 20-trial eval with pre-registered protocol. | pass 1 |
| 7 | [Deployment engineering](deployment-engineering.md) | A policy that runs at 2 Hz with no watchdog is not a deliverable. | Wrap a policy in the ROS 2 node template with watchdog. | pass 1 |
| 8 | [VLA models](vision-language-action-models.md) | Where the field is going; fine-tuning is the realistic lever. | LoRA fine-tune an open VLA on the 50 episodes. | pass 1 |
| 9 | [Sim-to-real](sim-to-real.md) | When real data is too expensive or unsafe. | Stand up one task in Isaac Lab or ManiSkill3 and evaluate. | pass 1 |
| 10 | [Real-world RL](real-world-rl.md) | Improving a BC policy past its data. | Read HIL-SERL recipe; plan an intervention-based fine-tune. | pass 1 |
| 11 | [ROS 2 in depth](ros2-in-depth.md) | The substrate for every robot on site. QoS and executors decide whether a policy runs. | Run the reference policy node against two fake sensors; break it with a wrong QoS and watch. | pass 2 |
| 12 | [Connecting to real robots](connecting-to-real-robots.md) | Day-one bring-up is where customer time is won or lost. | Follow the 12-step bring-up on one arm through the sine-wave test. | pass 2 |
| 13 | [Sim-first workflow](sim-first-workflow.md) | The daily loop: sim every day, robot on office days. | Build one cell twin with ros2_control as the seam; run the pre-robot checklist. | pass 2 |
| 14 | [Tactile and force sensing](perception-tactile-and-force.md) | Contact-rich tasks fail on vision alone. | Log a wrist F/T sensor during an insertion and plot the wrench. | pass 2 |
| 15 | [State estimation and localization](state-estimation-and-localization.md) | Mobile manipulation needs a pose the policy can trust. | Run SLAM Toolbox on a bag; measure ATE with evo. | pass 2 |
| 16 | [Language and VLM task planning](language-and-vlm-task-planning.md) | Your prior ground; the composition pattern with VLAs and Nav2. | Wire a VLM planner to nav2_simple_commander behind a validator. | pass 2 |
| 17 | [Training infrastructure](training-infrastructure.md) | Data loaders and normalization mismatches waste more days than model choice. | Size the decode workers on one dataset; verify train and deploy preprocessing match. | pass 2 |
| 18 | [Safety for learned policies](safety-for-learned-policies.md) | The shield pattern and the evidence customers ask for. | Run the STPA worked example on your first cell. | pass 2 |
| 19 | [Deformable object manipulation](deformable-object-manipulation.md) | The meat cell's object is a field, not a pose; grasp, transport, and alignment all change. | Measure sag and slip acceleration on 20 pieces; run the rigid-dummy baseline. | pass 3 |
| 20 | [Compliant mechanisms and actuation](compliant-mechanisms-and-actuation.md) | Compliance decides how much pose error the policy is allowed. | Size a printed Fin Ray finger with PRBM; 20 picks at 0, 5, 10 mm offset. | pass 3 |
| 21 | [Meat cutting automation](meat-cutting-automation.md) | The assignment: intercept a piece of meat and align it into a cutter. | Reproduce the cell architecture in sim with a conveyor and a deformable slab. | pass 3 |
| 22 | [Kinematics, dynamics, and rotations](kinematics-dynamics-and-rotations.md) | Quaternion conventions and conveyor intercept math bite daily. | Run snippets/kinematics.py; solve one intercept on a moving belt. | pass 3 |
| 23 | [Operating robot arms](operating-robot-arms.md) | First hour with an unfamiliar pendant decides the day. | Do the first-hour checklist on one arm in sim, then on site. | pass 3 |
| 24 | [Computer vision fundamentals](computer-vision-fundamentals.md) | Segmentation and depth on wet reflective meat are the perception core. | Label 200 images with SAM assist and train a small segmenter. | pass 3 |
| 25 | [Sensors and actuators](sensors-and-actuators.md) | Encoders, F/T, PLC signals become policy observations. | Wire a belt encoder into a ros2_control state interface. | pass 3 |
| 26 | [Fleet operations](fleet-operations.md) | Robot number two through ten. | Draft the fleet architecture for the meat cell. | pass 3 |
| 27 | [Whole-body and locomotion control](whole-body-and-locomotion-control.md) | For the days a legged base shows up. | Deploy an Isaac Lab locomotion policy in sim. | pass 3 |
| 28 | [Conveyor tracking and visual servoing](conveyor-tracking-and-visual-servoing.md) | The control core of the meat cell. | Run snippets/conveyor_tracking.py; measure the latency chain on one camera and one encoder. | pass 4 |
| 29 | [ROS 2 field integrations](ros2-field-integrations.md) | PLC handshake, cameras, boot-to-running: the plant wiring diagram. | Bring one Compose stack up from power-on with a PLC heartbeat mocked. | pass 4 |
| 30 | [Field engineer handbook](field-engineer-handbook.md) | How the customer measures you; hygiene and plant vocabulary. | Fill templates/site-survey.md for the first visit. | pass 4 |
| 31 | [How to work with coding agents](how-to-work-with-agents.md) | Eight lessons: contract, plan, hooks, sim first, parallel work, skills, review, the week. | Do lesson 1 and 3 on one real task; five measurable practices listed at the end. | pass 6 |
| 32 | [Our Claude Code setup](../tools/claude-code-setup.md) | The four layers that let an agent see a robot without commanding it. | Run the four checks; move launch and run to deny before robot day. | pass 6 |
| 33 | [Skill composition: action, outcome, input](skill-composition-action-outcome-input.md) | Composing skills is composing distributions, and the three kinds carry different guarantees. | Work the note's action-based and outcome-based examples by hand and confirm they give different answers. | pass 7 |
| 34 | [Latent skill representations](latent-skill-representations.md) | What a learned skill space buys for reuse and transfer, and what it cannot promise in a contract. | Pick the representation for the leg orient skill and write its contract, including the runtime monitor. | pass 7 |
| 35 | [Generative models: VAE, diffusion, flow](generative-models-vae-and-diffusion.md) | Why ACT at z = 0 and summed diffusion scores misbehave, before composing learned skills. | Re-run the worked example; compare DDPM, DDIM and annealed ULA on the summed score by W1. | pass 7 |
| 36 | [Cross-embodiment skill transfer](cross-embodiment-skill-transfer.md) | The Wednesday demo: one orient checkpoint on a SCARA and a UR20. | Build the floating-gripper expert and run E0, E1 and E2 on one leg before anything trains. | pass 7 |
| 37 | [Pork plant as a skill tree](pork-plant-skill-tree.md) | Which cell comes after leg alignment, ranked by skills reused. | Change the scoring input you disagree with most and recompute the ranking. | pass 7 |
| 38 | [Pipeline error budget and continuous evaluation](pipeline-error-budget-and-continuous-evaluation.md) | Which stage's error decides the cut, and how each stage keeps getting better without regressions. | Rerun the Monte Carlo budget with the measured grasp shift and find the 2.4 ms tracking bias. | pass 7b |
| 39 | [Learning the grasp, lift and orient skills](learning-grasp-lift-and-orient-skills.md) | What each skill learns, from what data, and the gate before the next stage. | Write the intercept into `AcquireShank` on a moving belt, then run the scripted baseline the learned stages must beat. | pass 7b |

## Pass log

| Date | Pass | What changed |
|------|------|--------------|
| 2026-09-05 | 1 | Initial notes written from literature and vendor docs, all `draft`. |
| 2026-09-05 | 1 | Ten topic notes plus depth-camera hardware note written by parallel research agents from primary sources. One Mermaid diagram per topic. Site generator added. |
| 2026-09-05 | 2 | ROS 2 in depth, connecting to real robots, sim-first workflow, tactile and force, state estimation; hardware notes for arms, grippers, compute; tool notes for Isaac Lab and MuJoCo. |
| 2026-09-06 | 2b | 22 paper entries from full texts; LeRobot, MoveIt 2, Nav2 tool notes; VLM task planning, training infrastructure, safety topics; robot bring-up SOP. |
| 2026-09-06 | 3 | Deformable object manipulation and compliant mechanisms topics for the meat cell. |
| 2026-09-06 | 3 | Meat cutting automation, deformables, compliant mechanisms, kinematics and rotations, operating arms, fleets, vision fundamentals, sensors and actuators, mobile robots and humanoids, whole-body control. |
| 2026-09-06 | 4 | Conveyor tracking with a tested planner, ROS 2 field integrations, field engineer handbook with site-survey and daily-update templates, two meat-cell experiment records, hardware shortlist. |
| 2026-09-06 | 5 | 15 more paper entries (perception, deformables, food handling), a glossary, and a back-of-book term index generated into the manual. |
| 2026-09-08 | 6 | Claude Code tool note, the agentic-coding playbook; agentic coding in robotics landscape note in progress. Identity made cross-harness. |
| 2026-09-08 | 6b | Read-only ROS 2 MCP server, project permissions with actuation denied, quality hook, three subagents, and the setup note. |
| 2026-09-15 | 7 | Skill composition as operations on distributions (action, outcome and input based, with emergence), latent skill representations, VAE and diffusion machinery with a computed composition example, cross-embodiment transfer with a SCARA and six-axis demo design, and the pork plant as a skill tree. Feeds the Wednesday technical plan. |
| 2026-09-15 | 7b | Pipeline error budget and continuous evaluation (Monte Carlo budget, intercept maths with belt acceleration, regression sample sizes); learning the intercept-grasp, lift-place and orient-on-belt skills. Corrected the p95 factor in control-architecture-selection and the vendor accuracy claim in conveyor-tracking. |
