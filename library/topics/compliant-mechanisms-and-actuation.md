---
title: Compliant mechanisms, actuators, and control for contact with soft or uncertain objects
date: 2026-09-06
tags: [topic, compliance, grippers, soft-robotics, actuators, mechanism-design, food-handling, meat-cell, force-control]
status: draft
source: synthesis
---

# Compliant mechanisms, actuators, and control for contact with soft or uncertain objects

Companion entries: `library/topics/deformable-object-manipulation.md` (the
object side) and `library/topics/perception-tactile-and-force.md` (sensing
and the impedance/admittance basics, which this entry does not repeat). This
entry is about the hardware and control that let a robot touch something
whose shape and position it does not know exactly, without breaking either.

## What it is

Compliance is the inverse of stiffness: how far the tool moves per unit of
force. A robot can get it three ways, and most deployed cells use two at once.

- **Mechanism compliance.** The structure bends by design. Howell's flexure
  mechanisms replace pin joints with thin bending segments and are analysed
  with the pseudo-rigid-body model (PRBM), which maps a flexible beam to a
  rigid link, a pin, and a torsional spring so that ordinary linkage
  kinematics apply ([Howell and Midha 1994](https://doi.org/10.1115/1.2919359),
  [Howell, Compliant Mechanisms, Wiley 2001](https://www.wiley.com/en-us/Compliant+Mechanisms-p-9780471384786),
  [BYU Compliant Mechanisms Research](https://www.compliantmechanisms.byu.edu/)).
  Living hinges, Fin Ray fingers, lattice grippers, and monolithic 3D-printed
  grippers are all this idea.
- **Actuator compliance.** A spring sits between the motor and the load
  (series elastic actuator, SEA: [Pratt and Williamson 1995](https://doi.org/10.1109/IROS.1995.525827)),
  the spring stiffness itself is adjustable (variable stiffness actuator,
  VSA: [Vanderborght et al. 2013 review](https://doi.org/10.1016/j.robot.2013.06.009)),
  or the gear ratio is so low that the motor's own back-drivability provides
  it (quasi-direct-drive, QDD: [Wensing et al. 2017, MIT Cheetah](https://doi.org/10.1109/TRO.2016.2640183)).
  Pneumatic soft actuators belong here too: the air is the spring.
- **Control compliance.** A stiff arm behaves like a spring because the
  controller makes it so (impedance, admittance; see the tactile entry and
  [Hogan 1985](https://doi.org/10.1115/1.3140702)).

The first two are passive: they act at the speed of physics, need no sensor,
and cannot be switched off by a software fault. The third is active: it can be
tuned per task and per phase, and it fails when the loop is too slow or the
sensor is wrong. Whitney's analysis of the remote centre compliance (RCC)
device is the classic statement of why a passive device with the right
compliance centre inserts a peg that a stiff robot jams
([Whitney 1982](https://doi.org/10.1115/1.3149634)).

## Why it matters (meat cell)

- The piece is soft, wet, and never in exactly the pose the camera says. A
  stiff parallel gripper closing to a commanded width either crushes it or
  misses it; a compliant finger closes until contact and then conforms.
  Underactuated hands "adaptively conform to the surface of objects without
  the explicit need for sensors or complicated feedback systems"
  ([Yale OpenHand](https://www.eng.yale.edu/grablab/openhand/)).
- Learned policies are only as precise as their observations and their
  demonstrations. UMI puts "soft fingers" on both the hand-held and robot
  grippers and states the principle: "Using series-elastic end effectors
  principle, UMI can implicitly record and control grasp forces by regulating
  the deformation of soft fingers through continuous gripper width control"
  ([Chi et al. 2024, UMI](https://arxiv.org/html/2402.10329); see
  `library/papers/chi-2024-umi.md`, 95A TPU fingers). Compliance turns a
  position error into a small force instead of a failure, so the policy's
  tolerance requirement drops.
- RL on real hardware collides. BaRiFlex was built for "issues caused by
  unexpected contact and collisions during robot learning" and mixes Fin Ray
  flexible linkages with rigid ones on a low-inertia back-drivable actuator
  ([arXiv:2312.05323](https://arxiv.org/abs/2312.05323)); SERL's stack runs
  the RL action through a compliant impedance controller (`real-world-rl.md`).
- Alignment into a fixture is an insertion problem in disguise: a soft slab
  against a hard datum. The RCC logic applies to the tool, and the slab's own
  compliance is part of the plant.
- Food contact adds constraints that rule out most research hardware:
  washdown, no crevices, food-contact-grade materials, and no shedding parts.
  Compliance elements are often the first thing that fails those rules
  (exposed springs, porous foams, ungasketed camera windows).

## Key methods table

### Mechanisms

| Mechanism | Principle | Strengths | Limits | Source |
|---|---|---|---|---|
| Flexure / living hinge | Thin section bends; PRBM gives the equivalent pin plus torsional spring | Monolithic, no wear particles, no lubrication, printable | Fatigue life; stiffness set by geometry and material, not tunable later | [Howell and Midha 1994](https://doi.org/10.1115/1.2919359), [BYU CMR](https://www.compliantmechanisms.byu.edu/) |
| Fin Ray effect | Two flexible flanks joined by ribs; pressing the tip makes the finger wrap toward the load instead of away | Self-conforming with one actuator; cheap to print or mould; food-grade versions exist | Low pinch force at the tip; contact point wanders as it wraps | [Crooks et al. 2016](https://doi.org/10.3389/frobt.2016.00070), [Festo Fin Ray](https://www.festo.com/) (DHAS finger family; details unverified), [BaRiFlex](https://arxiv.org/abs/2312.05323) |
| Lattice and metamaterial mechanisms | Cell geometry of a printed lattice gives the motion (shear cells, bistable cells) | Whole mechanism in one print; stiffness tuned by cell design | Anisotropic, hard to model without FEM; porous unless skinned (hygiene) | [Ion et al. 2016, Metamaterial Mechanisms](https://doi.org/10.1145/2984511.2984540) |
| Monolithic 3D-printed compliant gripper | Fingers, hinges, and frame in one part, TPU or nylon | No assembly, no fasteners; UMI's fingers are printed TPU | Print orientation sets strength; TPU absorbs water and staining (from field, unverified) | [UMI](https://arxiv.org/abs/2402.10329) |
| Tendon-driven underactuated fingers | One tendon, several joints, spring return; contacts stop joints in turn | Wraps irregular objects; Yale OpenHand designs are open CAD (CC BY-NC 3.0), made by "resin casting and 3D-printing" | Tendons stretch, wear, and are hard to seal for washdown | [Yale OpenHand](https://www.eng.yale.edu/grablab/openhand/), [Ma and Dollar 2017](https://doi.org/10.1109/MRA.2016.2639034), [Dollar and Howe 2010, SDM hand](https://doi.org/10.1177/0278364909360852) |
| Remote centre compliance (RCC) | Elastomer shear pads place the compliance centre at the part tip; lateral error becomes a small lateral force that guides the part in | Passive, fast, proven for peg-in-hole since the 1970s; ATI and others sell them (specs unverified) | Fixed compliance centre, so one device per part length; not for large errors | [Whitney 1982](https://doi.org/10.1115/1.3149634) |
| Delrin (POM), TPU, silicone compliance elements | Machined POM springs, printed TPU pads, cast silicone pads as the contact surface | Food-contact grades exist for all three; POM is machinable and stiff, TPU printable and mid-stiffness, silicone soft | POM creeps under sustained load; TPU stains; silicone tears at thin sections (from field, unverified) | [FDA 21 CFR 177.2600 (rubber articles for repeated use)](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-177/subpart-C/section-177.2600), [EU 1935/2004](https://eur-lex.europa.eu/eli/reg/2004/1935/oj), [EU 10/2011 (plastics)](https://eur-lex.europa.eu/eli/reg/2011/10/oj) |

### Actuators

| Actuator | Compliance source | Bandwidth and force | Where it fits | Source |
|---|---|---|---|---|
| Series elastic actuator (SEA) | Spring in series with a geared motor; deflection measures force | Force control bandwidth limited by the spring; shock tolerant | Arm joints, gripper drives where force is the controlled quantity | [Pratt and Williamson 1995](https://doi.org/10.1109/IROS.1995.525827) |
| Variable stiffness actuator (VSA) | Two motors or a nonlinear spring set stiffness and position independently | Stiff when precise, soft when touching; more mass and cost | Research arms; rarely in food cells | [Vanderborght et al. 2013](https://doi.org/10.1016/j.robot.2013.06.009) |
| Quasi-direct-drive (QDD) | Low gear ratio (roughly 6:1 to 10:1), high-torque motor; back-drivable, proprioceptive force sensing from current | High bandwidth; force from motor current without a sensor; lower peak torque per mass than high-ratio gearboxes | Legged robots; BaRiFlex-style grippers; low-cost arm joints in many 2024 to 2026 open designs | [Wensing et al. 2017](https://doi.org/10.1109/TRO.2016.2640183), [BaRiFlex](https://arxiv.org/abs/2312.05323) |
| Pneumatic soft actuator (PneuNet, bellows) | Air pressure inflates chambers in an elastomer; the body is the spring | Low bandwidth (valve and tube limited); force set by pressure; inherently gentle | Food grippers; the actuator is also the finger | [Ilievski et al. 2011](https://doi.org/10.1002/anie.201006464), [Shintake et al. 2018 review](https://doi.org/10.1002/adma.201707035) |
| Vacuum-driven soft gripper | Negative pressure collapses a silicone body around the object | Uses the vacuum line already on a food robot; one part, no moving joints | Grip force limited by atmospheric pressure times area | Piab piSOFTGRIP (vendor page not reachable at time of writing, unverified) |
| Electric soft gripper | Motor drives soft fingers; no compressor | "All-electric", 24 V DC, "> 1.5M cycles, maintenance-free", up to 1.5 kg payload across Gentle Duo and Pro | Cells with no clean compressed air | [Ubiros](https://ubiros.com/) |
| Stiff servo gripper plus soft pads | Gripper is rigid; compliance is in the pads | Full stroke and force of an industrial gripper; pads are a consumable | Default for a first learned cell | [Robotiq Hand-E](https://robotiq.com/products/adaptive-grippers): 50 or 100 mm stroke, 20 to 185 N, 7 kg payload, IP67 |

### Soft robotics products for food

| Product | Actuation | Materials and compliance claims | Notes | Source |
|---|---|---|---|---|
| OnRobot Soft Gripper | Electric, "no external air supply needed" | Food-grade silicone cups, dishwasher-safe; "FDA 21 CFR (for non-fatty food items) and EC 1935/2004" | "Up to 2.2 kg payload based on shape, softness and friction"; grip range 11 to 118 mm; star or finger cups; the "non-fatty" caveat matters for meat | [OnRobot](https://onrobot.com/en/products/soft-gripper) |
| Ubiros Gentle Duo / Pro / Flex | All-electric | Soft fingers; certifications not stated on the site | Up to 1.5 kg; 24 V; 1.5M cycles | [Ubiros](https://ubiros.com/) |
| Soft Robotics mGrip | Pneumatic elastomer fingers | Historically marketed as FDA and EC 1935/2004 compliant for food (unverified); the company has since pivoted to vision inspection under the Oxipital AI name and the mGrip line is reported to have moved to Schmalz (unverified) | Check who supports the product before specifying it | [Soft Robotics / Oxipital AI](https://www.softroboticsinc.com/) |
| Festo DHAS Fin Ray fingers and pneumatic soft grippers | Pneumatic | Fin Ray polyurethane fingers; food-grade variants listed by Festo (unverified, vendor page not reachable) | Fits standard parallel grippers | [Festo](https://www.festo.com/) |
| Piab piSOFTGRIP | Vacuum | Silicone, food-grade (unverified) | Vacuum-driven, single part | Piab (unverified) |

### Underactuated hands

| Hand | Fingers and actuators | Compliance | Evidence | Source |
|---|---|---|---|---|
| Yale OpenHand Model O, T42, M2 and others | Tendon-driven, 1 to 4 actuators, printed and cast | Joint springs plus flexure pads | Open CAD; Model O "commercialized by RightHand Robotics" | [Yale OpenHand](https://www.eng.yale.edu/grablab/openhand/) |
| iHY hand (iRobot-Harvard-Yale) | 3 fingers, 5 actuators, flexure joints | "A compliant, underactuated hand for robust manipulation" is the title; DARPA ARM-H entry | Peer-reviewed field evaluation on the ARM tasks | [Odhner et al. 2014, IJRR](https://doi.org/10.1177/0278364913514466) |
| SDM hand | 4 fingers, 1 actuator, shape-deposition-manufactured elastomer joints | Very low stiffness joints; grasps under large positioning error | Reported tolerance to position error in the paper (numbers unverified) | [Dollar and Howe 2010](https://doi.org/10.1177/0278364909360852) |
| Robotiq 2F-85 / 2F-140 adaptive | 2 fingers, 1 motor, linkage; parallel or encompassing grip depending on contact | Mechanism adaptivity, rigid links | 85 or 140 mm stroke, 20 to 235 N / 10 to 125 N, 5 kg / 2.5 kg payload (vendor figures, unverified from the page reachable today) | [Robotiq adaptive grippers](https://robotiq.com/products/adaptive-grippers) |
| BaRiFlex | 2 fingers mixing Fin Ray flexible and rigid linkages, low-inertia back-drivable actuators | Collision-tolerant for RL; pinch and conforming modes | Compared on a Franka Panda against the Franka Hand and a Fin Ray gripper; abstract gives no numbers | [arXiv:2312.05323](https://arxiv.org/abs/2312.05323) |
| Soft-bubble gripper (TRI) | Parallel jaw with inflated latex membranes and a depth camera behind each | Membrane compliance plus dense contact geometry sensing | RoboSoft 2019; later used for perceptive manipulation | [Alspach et al. 2019](https://arxiv.org/abs/1904.02252) |

### Active compliance for alignment (what the tactile entry does not cover)

The tactile entry explains impedance vs admittance and which arms support
which. For alignment of a soft piece against a fixture, the extra decisions
are these.

- **Compliance frame.** Stiffness is a matrix, and it should be expressed in
  the task frame, not the base frame: stiff along the push direction, soft
  across it, and soft in the rotations that the datum constrains. This is
  Raibert and Craig's hybrid position/force selection matrix in modern form
  ([Raibert and Craig 1981](https://doi.org/10.1115/1.3139652)).
- **Per-phase gains.** Approach stiff, contact soft, push at a force setpoint,
  release stiff. The ros2_control `admittance_controller` takes the mass,
  damping, and stiffness diagonals as parameters and the selection per axis
  ([admittance_controller docs](https://control.ros.org/humble/doc/ros2_controllers/admittance_controller/doc/userdoc.html));
  a phase machine outside the policy switches them. Adaptive Compliance
  Policy does this inside the policy (tactile entry).
- **Passive plus active.** Put the passive compliance in the fingers and the
  active compliance in the arm. The finger handles what the loop cannot
  (impact in the first milliseconds); the arm handles what the finger cannot
  (a 20 mm position error). Whitney's RCC argument and Hogan's impedance
  argument are complementary, not competing.
- **Soft plant.** When the piece itself is soft, the effective stiffness seen
  by the controller is the series combination of finger, piece, and fixture.
  A stiffness that is stable on a rigid dummy can be under-damped on product.
  Retune on product and log the gains in `DATASET.md`.

## Design and selection guide: a food handling gripper

Work through it in this order; each step narrows the next.

1. **Product envelope.** Min and max dimension across the grip axis, mass,
   surface (skin, cut face, fat), wetness, temperature. Stroke must cover the
   range plus a clearance for approach; for a 40 to 120 mm slab that means
   140 mm or a two-position finger.
2. **Grip force.** Required holding force is `m (g + a) / mu` for a friction
   grip, where `a` is the transport acceleration and `mu` the wet friction
   coefficient (measure it; do not assume). A 1 kg piece at 5 m/s2 with
   `mu` = 0.2 needs about 75 N total normal force, which is why form-closure
   (wrapping) or support plates beat friction grips on wet product.
3. **Contact type.** Friction pinch (needs high `mu` pads, marks the surface),
   encompassing (Fin Ray or underactuated fingers, spreads load), support
   (scoop, plate, cradle: no pinch stress at all), suction (dry non-porous
   skin only), needle (porous, only where the customer accepts punctures).
   See the decision table below and the deformable entry's grasp table.
4. **Compliance placement.** Passive in the fingers first (pads or Fin Ray),
   sized so that the expected pose error (camera plus calibration, typically
   3 to 10 mm) is absorbed at under the tissue's tear force. Active in the arm
   for alignment. Series elasticity in the gripper drive only if you need
   force-controlled grasping without a tactile sensor (UMI's argument).
5. **Material.** Contact parts from food-contact-grade silicone (FDA 21 CFR
   177.2600, EU 1935/2004), POM, PEEK, or 316 stainless; printed TPU only if a
   food-contact grade is certified for the printer and process, which few are
   (unverified). Avoid open-cell foams, exposed springs, fabric tendons.
6. **Washdown.** IP67 minimum for the actuator, IP69K if the line uses
   high-pressure hot washdown (IP69K per ISO 20653). Cups and pads must be
   removable without tools. No blind holes, no unsealed threads; EHEDG
   hygienic design guidelines cover the geometry rules
   ([EHEDG](https://www.ehedg.org/)).
7. **Sensing.** Motor current or a series spring for grip force; a
   washdown-rated camera for slip if needed; avoid gel-based tactile sensors
   on product contact surfaces (gel wear, tactile entry).
8. **Verify.** 20 picks per product class per candidate gripper, logging
   success, drop, tear, mark, and alignment residual after placement. Choose
   on the failure modes, not the success rate alone.

### Decision table: task feature to gripper strategy

| Task feature | First choice | Why | Avoid |
|---|---|---|---|
| Wet surface | Encompassing soft fingers (Fin Ray, pneumatic) or support plate | Wrapping does not rely on friction; a plate carries the weight | Friction pinch with smooth pads; suction (leaks) |
| Slippery and heavy (over 1 kg) | Support plate or scoop plus a light pinch to stop sliding | Holding force from friction alone becomes large enough to damage tissue (step 2) | Two-point pinch |
| Fragile (tears, bruises) | Wide soft pads, low closing force, low acceleration cap | Stress = force / area; large area and low force | Needles, narrow fingertips, high-`mu` textured pads that shear the surface |
| Irregular shape, varies piece to piece | Underactuated or Fin Ray fingers, or vacuum-driven soft gripper | Conforms without per-piece planning | Rigid form-fit fingers |
| Must not mark the surface | Smooth food-grade silicone, or non-contact support (plate, belt regrasp) | No texture, no puncture, low pressure | Needles, textured pads, suction cups (ring marks) |
| Thin and flat (fillet, sheet) | Scoop or spatula, or suction if dry-skinned | Cannot be pinched without folding | Pinch from above |
| Porous and dry (breaded, fibrous) | Needle gripper (if punctures accepted) or soft fingers | Vacuum leaks through the material | Suction |
| Needs alignment against a datum afterward | Any of the above plus a pusher or the closed gripper as a pusher, arm under admittance control | Alignment by contact is more repeatable than by placement | Releasing and hoping |
| Sub-zero product (frozen or crusted) | Rigid or lightly padded fingers; treat as rigid | It is rigid; compliance adds nothing | Soft pneumatic fingers (stiffen and crack in the cold, unverified) |

## Practical gotchas

- **Passive compliance moves the contact point.** A Fin Ray finger wraps, so
  where it touches depends on how far it has closed. A policy that learned
  "grasp at pixel X" with rigid fingers grasps elsewhere with soft ones.
  Collect demonstrations with the deployed fingers, and record the finger
  model in `DATASET.md` (same argument as controller gains in the tactile
  entry).
- **Soft fingers hide force from the policy.** Without a series spring
  measurement or current sensing, the policy sees gripper width, not force.
  UMI's trick is to make width a proxy for force through known finger
  deformation ([UMI](https://arxiv.org/html/2402.10329)); this only works if
  the fingers are the same ones the data was collected with, and fingers age.
- **Pneumatics are slow and need air quality.** Valve and tube dynamics put
  pneumatic soft grippers well below the rate of an electric gripper, and
  food lines require filtered, oil-free air (from field, unverified). The
  electric soft grippers exist for this reason
  ([OnRobot](https://onrobot.com/en/products/soft-gripper), [Ubiros](https://ubiros.com/)).
- **"Food-grade" has a scope.** OnRobot's cups are stated compliant "for
  non-fatty food items" ([OnRobot](https://onrobot.com/en/products/soft-gripper)).
  Meat is fatty. Ask the vendor for the migration test conditions, not the
  logo.
- **Vendor product lines move.** Soft Robotics Inc. is now Oxipital AI and
  its website no longer lists mGrip specifications
  ([softroboticsinc.com](https://www.softroboticsinc.com/)). Several vendor
  spec pages returned 404 or 403 while writing this entry (Festo, Piab, ATI
  compliance devices, Robotiq 2F pages). Confirm support and spare parts
  before a customer commits.
- **Elastomers fatigue and creep.** Flexure life is finite; PRBM gives
  stiffness, not life. Test a printed finger for the cycle count of one
  shift times the pilot length before the pilot, and count marks on product.
- **QDD actuators are proprioceptive only at low speed.** Current-based force
  sensing includes friction and inertia; the Cheetah design minimises both,
  but a cheap QDD gripper does not ([Wensing et al. 2017](https://doi.org/10.1109/TRO.2016.2640183)).
- **Compliance plus a stiff fixture is a resonator.** Soft finger, soft slab,
  hard datum, admittance loop: the combined system can oscillate on contact
  at a stiffness that was stable on a rigid test part. Add damping, lower the
  approach speed, and test on product (tactile entry, admittance section).
- **The compliance you add is the compliance sim ignores.** Rigid-body
  simulators model rigid fingers; a policy trained in sim with rigid pads and
  deployed on Fin Ray fingers has a different contact model. Either model the
  finger in sim (MuJoCo `flex`, deformable entry) or train on real data.

## What a forward-deployed engineer must be able to do

- [ ] Explain PRBM in two sentences and use it to size a printed flexure
      finger for a target stiffness (N/mm at the tip).
- [ ] State where the compliance is in a given cell (fingers, gripper drive,
      arm controller, fixture) and what pose error each layer absorbs.
- [ ] Run the selection guide for a product class and produce a one-page
      gripper spec: stroke, force, contact type, material, IP rating, pad
      replacement interval.
- [ ] Measure wet friction coefficient and slip acceleration for two pad
      materials and show the holding-force calculation with the numbers.
- [ ] Bring up `admittance_controller` or the arm's native impedance mode with
      per-phase gains for approach, contact, push, release, and log the
      gains and peak forces per episode.
- [ ] Retrain or re-collect when fingers change, and prove the policy did not
      degrade (same trial count, same checker).
- [ ] Get a vendor's food-contact declaration in writing with the test
      conditions (fatty vs aqueous simulant, temperature, duration).

## Open questions to learn hands-on

- On our product, how much pose error does a 95A TPU Fin Ray finger absorb
  before the piece is marked, compared with a flat silicone pad at the same
  grip force? 20 picks each at 0, 5, 10 mm deliberate offset.
- Does a support plate let us raise transport acceleration enough to pay
  back its extra cycle time on the regrasp?
- Whether an electric soft gripper (OnRobot or Ubiros class) survives one
  week of washdown on the customer line without stiffness change; measure
  finger stiffness with a force gauge on days 0, 3, and 7.
- Whether the same ACT or Diffusion Policy checkpoint holds its success rate
  after fingers are replaced with a new print of the same design, at 50
  trials. If not, finger aging is a dataset variable.
- Whether the customer accepts any pad marking at all; the answer selects the
  contact type before anything else in the guide.

## Related entries

- `library/topics/deformable-object-manipulation.md` (grasp planning on the
  object side, transport limits, alignment recipe)
- `library/topics/perception-tactile-and-force.md` (impedance vs admittance,
  sensors, gel wear)
- `library/papers/chi-2024-umi.md` (soft fingers as series elastic elements)
- `library/topics/real-world-rl.md` (compliant controller under RL)
- `library/topics/connecting-to-real-robots.md` (ros2_control effort and
  impedance controllers)
- `library/topics/safety-for-learned-policies.md` (force caps as a safety
  layer)
- `sops/robot-bring-up.md`, `sops/field-deployment-checklist.md`

## Sources

- Mechanisms: [Howell and Midha 1994](https://doi.org/10.1115/1.2919359), [Howell 2001](https://www.wiley.com/en-us/Compliant+Mechanisms-p-9780471384786), [BYU CMR](https://www.compliantmechanisms.byu.edu/), [Crooks et al. 2016 Fin Ray](https://doi.org/10.3389/frobt.2016.00070), [Ion et al. 2016](https://doi.org/10.1145/2984511.2984540), [Whitney 1982](https://doi.org/10.1115/1.3149634)
- Actuators and control: [Pratt and Williamson 1995](https://doi.org/10.1109/IROS.1995.525827), [Vanderborght et al. 2013](https://doi.org/10.1016/j.robot.2013.06.009), [Wensing et al. 2017](https://doi.org/10.1109/TRO.2016.2640183), [Hogan 1985](https://doi.org/10.1115/1.3140702), [Raibert and Craig 1981](https://doi.org/10.1115/1.3139652), [ros2_control admittance_controller](https://control.ros.org/humble/doc/ros2_controllers/admittance_controller/doc/userdoc.html)
- Soft robotics: [Ilievski et al. 2011](https://doi.org/10.1002/anie.201006464), [Shintake et al. 2018](https://doi.org/10.1002/adma.201707035), [Alspach et al. 2019 Soft-bubble](https://arxiv.org/abs/1904.02252), [OnRobot Soft Gripper](https://onrobot.com/en/products/soft-gripper), [Ubiros](https://ubiros.com/), [Soft Robotics / Oxipital AI](https://www.softroboticsinc.com/), [Festo](https://www.festo.com/)
- Hands and grippers: [Yale OpenHand](https://www.eng.yale.edu/grablab/openhand/), [Ma and Dollar 2017](https://doi.org/10.1109/MRA.2016.2639034), [Odhner et al. 2014](https://doi.org/10.1177/0278364913514466), [Dollar and Howe 2010](https://doi.org/10.1177/0278364909360852), [Robotiq adaptive grippers](https://robotiq.com/products/adaptive-grippers), [BaRiFlex](https://arxiv.org/abs/2312.05323), [UMI](https://arxiv.org/abs/2402.10329)
- Food contact and hygiene: [FDA 21 CFR 177.2600](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-177/subpart-C/section-177.2600), [EU 1935/2004](https://eur-lex.europa.eu/eli/reg/2004/1935/oj), [EU 10/2011](https://eur-lex.europa.eu/eli/reg/2011/10/oj), [EHEDG](https://www.ehedg.org/)
