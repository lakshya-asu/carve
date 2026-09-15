---
title: Deformable object manipulation (meat, dough, produce, cloth, cables)
date: 2026-09-06
tags: [topic, deformable, grasping, simulation, imitation-learning, food-handling, meat-cell, perception]
status: draft
source: synthesis
---

# Deformable object manipulation (meat, dough, produce, cloth, cables)

Companion entries: `library/topics/compliant-mechanisms-and-actuation.md` (the
hardware side: grippers, compliance, soft robotics) and
`library/topics/perception-tactile-and-force.md` (contact sensing and force
control). This entry covers the object: how to represent it, simulate it, grasp
it, move it, and put it down in a known pose.

## What it is

A rigid object has six degrees of freedom and its state is one pose. A slab of
meat, a sheet of dough, or a towel has, for practical purposes, infinitely many:
its shape is a field, and the grasp changes the shape. DefGraspSim states the
problem in one line: "unlike rigid objects, deformable objects have infinite
degrees of freedom and require field quantities (e.g., deformation, stress) to
fully define their state"
([DefGraspSim, arXiv:2203.11274](https://arxiv.org/abs/2203.11274)).

Everything downstream follows from that. Pose estimation becomes shape
estimation, grasp planning has to predict what the grasp does to the object,
and "place at pose X" becomes "place so the final shape matches template X."
The survey by Yin, Varava, and Kragic organises the field into modelling,
perception, learning, and control, and is the right first read
([Yin et al. 2021, Science Robotics](https://doi.org/10.1126/scirobotics.abd8803));
Sanchez et al. cover the industrial and domestic application side
([Sanchez et al. 2018, IJRR](https://doi.org/10.1177/0278364918779698)).

Four state representations are in use, and the choice decides the whole
pipeline.

| Representation | What it stores | Where it fits | Cost | Example |
|---|---|---|---|---|
| Mesh (nodes + connectivity) | Full surface or volume geometry | FEM sim, graph-network dynamics, sim-to-real of thin shells | Needs a mesh of the real object, which a depth camera does not give directly | [MeshGraphNets, arXiv:2010.03409](https://arxiv.org/abs/2010.03409), [VCD, arXiv:2105.10389](https://arxiv.org/abs/2105.10389) |
| Particles (unordered points) | Positions sampled from a point cloud or an MPM/PBD sim | Dough, clay, granular, anything that splits or merges; learned GNN dynamics | Loses topology; needs particle-to-observation matching | [DPI-Net, arXiv:1810.01566](https://arxiv.org/abs/1810.01566), [RoboCraft, arXiv:2205.02909](https://arxiv.org/abs/2205.02909) |
| Keypoints | A few semantic points (corners, edges, centre of mass) | Fast policies, alignment tasks, human-readable goals | Ambiguous on homogeneous objects; occluded points | [kPAM, arXiv:1903.06684](https://arxiv.org/abs/1903.06684), [Dense Object Nets, arXiv:1806.08756](https://arxiv.org/abs/1806.08756) |
| Latent (learned code) | A vector or a set of codes from images or point clouds | End-to-end BC and RL; topology change (cutting, tearing) | Not inspectable; the failure mode is silent | [ACID, arXiv:2203.06856](https://arxiv.org/abs/2203.06856), [DoughNet, arXiv:2404.12524](https://arxiv.org/abs/2404.12524) |

For a meat cell the practical answer is keypoints plus a mask for alignment
(edge, long axis, thickest point) and a latent for the end-to-end policy;
meshes and particles belong in the simulator and the dynamics model, not in
the deployed observation.

## Why it matters (meat cell)

- The cell picks a piece of meat from a belt or bin and places it aligned in a
  fixture for the cut. Each piece differs in size, shape, fat cover, and
  stiffness; Khodabandehloo's review of robotic meat cutting lists this
  variability as the reason "adaptive systems rather than fixed programs" are
  required, and puts a number on yield: at 600 lamb carcasses per hour a 5 mm
  cut-position correction is worth nearly $1M per year
  ([Khodabandehloo 2022, Animal Frontiers](https://doi.org/10.1093/af/vfac012)).
  Alignment accuracy of the pick-and-place is the direct upstream of that 5 mm.
- The review names three handling architectures: robot moves the meat past a
  fixed tool; robot moves the tool past fixtured meat; meat on a moving
  conveyor with a tracking robot
  ([Khodabandehloo 2022](https://doi.org/10.1093/af/vfac012)). Our cell is the
  second, so the pick-and-place must deliver the piece into a known pose.
- Soft wet tissue slips. A gripper built for the meat industry with optical-flow
  slip detection exists precisely because "secure gripping of soft, slippery
  tissues" is the hard part
  ([arXiv:2307.05648](https://arxiv.org/abs/2307.05648)).
- The current published robot meat work is cutting, not handling: a cobot with
  an instrumented knife slicing, trimming, and cubing pork loins, rated
  "adequate" on average by industry experts who "generally preferred the cuts
  performed in collaboration with a human worker"
  ([arXiv:2401.07875](https://arxiv.org/abs/2401.07875)), and a follow-up on
  hand detection, knife force sensing, and an LED uncertainty display for
  human-in-the-loop meat processing
  ([arXiv:2508.14763](https://arxiv.org/abs/2508.14763)). Neither reports
  trial counts in the abstract. The grasp-and-align step is under-published,
  which is an opening for field results.
- Rigid-body tools give wrong answers here. A grasp planner that scores
  antipodal points on a point cloud assumes the object keeps its shape; on a
  slab it predicts a grasp that folds or tears. DefGraspSim was built because
  rigid metrics were "inadequate" for exactly the food-processing case
  ([arXiv:2203.11274](https://arxiv.org/abs/2203.11274)).

## Key methods table

### Modelling and simulation

| Method | Model | Speed / scale | Differentiable | Where to use it | Source |
|---|---|---|---|---|---|
| Finite element method (FEM) | Continuum, tetrahedral mesh, hyperelastic constitutive law | Slow on CPU; GPU corotational FEM in Isaac Gym / PhysX | Not natively | Grasp stress and deformation prediction; ground truth for surrogates | [DefGraspSim](https://arxiv.org/abs/2203.11274), [SOFA](https://www.sofa-framework.org/), [Isaac Gym paper, arXiv:2108.10470](https://arxiv.org/abs/2108.10470) |
| Position-based dynamics (PBD, XPBD) | Constraints on particle positions, no forces | Real time, stable at large steps; stiffness depends on iteration count (XPBD fixes this) | No | Cloth, rope, quick interactive sims; SoftGym's backend (NVIDIA FleX) | [Müller et al. 2007](https://doi.org/10.1016/j.jvcir.2007.01.005), [XPBD, Macklin et al. 2016](https://doi.org/10.1145/2994258.2994272) |
| Mass-spring | Point masses on springs | Fastest, least accurate; volume not preserved | Trivially | Teaching, quick prototypes, thin sheets | MuJoCo `composite`, edge-constraint mode of `flex` ([MuJoCo modeling docs](https://mujoco.readthedocs.io/en/stable/modeling.html)) |
| Material point method (MPM, MLS-MPM) | Particles + background grid; handles plasticity, splitting, merging | GPU real time in Taichi; the engine behind PlasticineLab and Genesis | Yes (Taichi) | Dough, clay, minced or ground meat, anything that fractures | [Jiang et al. 2016 course](https://doi.org/10.1145/2897826.2927348), [MLS-MPM, Hu et al. 2018](https://doi.org/10.1145/3197517.3201293) |
| DiffTaichi | Differentiable programming for physics kernels | Compiles to GPU; gradients through the whole sim | Yes | Writing your own differentiable deformable sim | [DiffTaichi, arXiv:1910.00935](https://arxiv.org/abs/1910.00935) |
| PlasticineLab | MPM soft-body benchmark, gradients through the sim | Gradient methods "rapidly find a solution within tens of iterations" where "RL-based approaches struggle to solve most of the tasks efficiently"; both fail on multi-stage tasks | Yes | Dough and clay shaping research; not a production sim | [arXiv:2104.03311](https://arxiv.org/abs/2104.03311) |
| SoftGym | PBD (FleX) cloth, rope, fluid tasks with a Gym API | RL benchmark; "high intrinsic dimensionality and ... partially observable" is the stated challenge | No | Cloth policy prototyping; baseline comparisons | [arXiv:2011.07215](https://arxiv.org/abs/2011.07215) |
| Isaac Lab `DeformableObject` | PhysX FEM soft bodies, two tetrahedral meshes (simulation, collision); nodal state and kinematic targets exposed | "only supported in GPU simulation" | No | Grasp-in-sim of soft objects in the same stack as the rigid tasks; pinned Isaac Lab 2.3.x per `sim-first-workflow.md` | [Isaac Lab tutorial](https://isaac-sim.github.io/IsaacLab/main/source/tutorials/01_assets/run_deformable_object.html), [API](https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.assets.html) |
| MuJoCo `flex` / `flexcomp` | Bodies joined into capsules (1D), triangles (2D), or tetrahedra (3D); either soft edge constraints or a Saint Venant-Kirchhoff continuum with separate shear and volume stiffness | CPU; contacts "up to 8 bodies" per pair; `flex` still experimental in MuJoCo Warp | Via MJX partially (unverified) | Cables, sheets, a soft slab against a rigid gripper; same model file as the rigid cell | [MuJoCo modeling docs](https://mujoco.readthedocs.io/en/stable/modeling.html), [XML reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html) |
| Genesis | MPM + FEM + PBD coupled, parses URDF/MJCF/USD | GPU; frequent breaking releases (`sim-first-workflow.md`) | Yes | Multi-material scenes; no ROS bridge | [Genesis](https://github.com/Genesis-Embodied-AI/Genesis) |
| Learned dynamics (GNN on particles or mesh) | Message passing over a graph built from the observation | Orders of magnitude faster than FEM once trained; DefGraspNets "up to 1500 times faster than the FEM simulator" | Yes | MPC over dough, cloth smoothing, grasp stress prediction | [DefGraspNets, arXiv:2303.16138](https://arxiv.org/abs/2303.16138), [RoboCraft](https://arxiv.org/abs/2205.02909), [VCD](https://arxiv.org/abs/2105.10389) |

None of these has a calibrated constitutive model of raw muscle out of the box.
Meat is anisotropic (fibre direction), viscoelastic, and its stiffness changes
with temperature and post-mortem time (unverified as a robotics-sim statement;
it is standard meat science). Treat any sim as a place to learn grasp
geometry and trajectory shape, then tune on the real product.

### Grasp planning for deformables

| Strategy | When it works | Failure mode | Evidence | Source |
|---|---|---|---|---|
| FEM-scored pinch grasp | Object is a volume, not a sheet; you can afford offline sim | Sim material mismatch | DefGraspSim: 34 objects, elasticity over 5 orders of magnitude, 6,800 grasps, 1.1M measurements; metrics for stress, deformation, stability, deformation-controllability | [arXiv:2203.11274](https://arxiv.org/abs/2203.11274) |
| GNN surrogate for the above | Need online replanning | Distribution shift from training set | DefGraspNets: gradient-based grasp refinement 1500x faster than FEM | [arXiv:2303.16138](https://arxiv.org/abs/2303.16138) |
| Multi-point or whole-surface support (multiple pinch points, wide pads, cradle) | Slabs, fillets: load spread so no single point exceeds tear stress | Bulky end effector, harder to insert into a bin | Basic mechanics: stress = force / contact area; fewer points means higher local stress (no single source; see DefGraspSim stress metric) | [arXiv:2203.11274](https://arxiv.org/abs/2203.11274) |
| Suction | Non-porous, flat enough surface; sheets and skinned surfaces | Leaks on wet, porous, uneven tissue; marks the surface; hygiene of the cup | Dex-Net 3.0: 350 physical trials on an ABB YuMi, 98% on prismatic and cylindrical objects, 82% on typical, 58% on adversarial (81% after training on adversarial); Dex-Net 4.0 chooses suction vs jaw per object, "300 mean picks per hour" on heaps (Dex-Net 4.0 figure from memory, unverified) | [Dex-Net 3.0, arXiv:1709.06670](https://arxiv.org/abs/1709.06670), [Dex-Net 4.0, Science Robotics 2019](https://doi.org/10.1126/scirobotics.aau4984) |
| Needle gripper | Porous, fibrous, or vacuum-leaky material; textiles, foams | Punctures product; not accepted by many meat customers (from field, unverified); needles retract through the material | Schmalz SNG: 0.8 to 2.0 mm needles, 4 to 24 per gripper, 0 to 25 mm stroke, "for workpieces which are difficult to grip using vacuum as well as highly porous materials" | [Schmalz needle grippers](https://www.schmalz.com/en/vacuum-technology-for-automation/vacuum-components/special-grippers/needle-grippers/) |
| Scoop or spatula (sliding a thin blade under the piece) | Piece rests on a flat surface; no top-surface access acceptable | Needs a low-friction surface; piece may drag rather than lift | Non-prehensile, common in bakery and food lines; no robotics-learning paper found (unverified) | none |
| Fling or dynamic lift | Cloth: unfold with one high-velocity motion | Meat would tear; cloth only | FlingBot unfolds cloth to high coverage with dynamic flinging, learned in sim, transferred to real | [FlingBot, arXiv:2105.03655](https://arxiv.org/abs/2105.03655) |
| Conveyor-assisted regrasp | Place the piece on the belt or a smooth plate, let the belt or a pusher square it, pick again | Doubles cycle time; belt must be food-grade | Standard in meat plants (Khodabandehloo's third architecture) | [Khodabandehloo 2022](https://doi.org/10.1093/af/vfac012) |
| Tactile-verified grasp | Any of the above when slip or under-grip is the failure | Sensor wear on wet tissue | Optical-flow slip detection in a meat-industry gripper; GelSight hardness estimation "from 8 to 87 in Shore 00 scale"; Calandra's regrasp policy raises success on novel objects using touch | [arXiv:2307.05648](https://arxiv.org/abs/2307.05648), [Yuan et al. 2017, arXiv:1704.03955](https://arxiv.org/abs/1704.03955), [Calandra et al. 2018, arXiv:1805.11085](https://arxiv.org/abs/1805.11085) |

Where to grasp a slab so it does not tear or fold: near the centroid of the
mask, across the fibre direction, with a pad width that covers a good fraction
of the short axis, and with the second contact point (or a support plate) such
that the unsupported overhang stays short. Overhang length is the variable;
a long cantilever of soft tissue folds under its own weight and tears at the
grip line when accelerated (from field, unverified; DefGraspSim's
deformation and stress metrics are the quantitative form of this argument).

### Learning approaches

| Method | Object | Representation | Real-robot evidence | Source |
|---|---|---|---|---|
| Goal-conditioned Transporter Networks (DeformableRavens) | Cables (1D), fabrics (2D), bags (3D) | Image, pick-and-place affordance maps | Simulated suite of 1D, 2D, and 3D tasks plus physical experiments (counts not in abstract); goal images without markers at test time | [Seita et al. 2021, arXiv:2012.03385](https://arxiv.org/abs/2012.03385) |
| FabricFlowNet | Cloth folding, bimanual | Optical flow between current and goal depth images, then pick-place pairs | Real bimanual system; trained on one square cloth, transfers to T-shirts and rectangles | [arXiv:2111.05623](https://arxiv.org/abs/2111.05623) |
| Visible Connectivity Dynamics (VCD) | Cloth smoothing | Partial point cloud to particle graph with inferred connectivity; GNN dynamics + planning | Zero-shot sim-to-real on a Franka, several cloth types | [arXiv:2105.10389](https://arxiv.org/abs/2105.10389) |
| SpeedFolding | Garment folding, bimanual | Learned pick-pair prediction from RGB-D | 93% success, under 120 s per garment, 30 to 40 folds per hour, 4,300 annotated and self-supervised actions | [arXiv:2208.10552](https://arxiv.org/abs/2208.10552) |
| Cloth Funnels | Garment canonicalisation and alignment | Self-supervised reward on canonical pose | Real bimanual, unfolds and aligns garments as a preprocessing step for folding | [arXiv:2210.09347](https://arxiv.org/abs/2210.09347) |
| Fabric smoothing via imitation | Fabric | Image, pick-place from an analytic corner-pulling demonstrator | Real da Vinci arm, sim-to-real | [Seita et al. 2020, arXiv:1910.04854](https://arxiv.org/abs/1910.04854) |
| RoboCraft | Elasto-plastic dough | Particles from point cloud, GNN dynamics, MPC | "10 minutes of real-world robotic interaction data"; shapes into novel targets, "comparable to and sometimes better than human subjects" | [arXiv:2205.02909](https://arxiv.org/abs/2205.02909) |
| RoboCook | Dough with tools (roller, cutter, gripper) | Particles + tool-aware GNN + learned skill selection | Real dumpling-making pipeline with tool selection | [arXiv:2306.14447](https://arxiv.org/abs/2306.14447) |
| DiffSkill | Dough, PlasticineLab tasks | Differentiable sim to generate demos, then skill abstraction | Sim only | [arXiv:2203.17275](https://arxiv.org/abs/2203.17275) |
| DoughNet | Dough with topology change (cut, split, merge) | Latent code sets from a denoising autoencoder, autoregressive prediction | Sim and real experiments; predicts splitting and merging that geometry-only models miss | [arXiv:2404.12524](https://arxiv.org/abs/2404.12524) |
| Dense descriptors for rope | Rope | Per-pixel descriptors, correspondence to goal | Real robot, learned in sim | [Sundaresan et al. 2020, arXiv:2003.01835](https://arxiv.org/abs/2003.01835) |
| Tactile-in-the-loop grasping | Soft and rigid household objects | GelSight images + RGB | Regrasp policy improves success on novel objects when touch is added | [Calandra et al. 2018](https://arxiv.org/abs/1805.11085) |
| Meat-industry slip detection gripper | Soft slippery tissue | Optical flow on an in-gripper camera | Meat-cell gripper; no trial counts in the abstract | [arXiv:2307.05648](https://arxiv.org/abs/2307.05648) |
| Fish and fillet handling | Fillets | Vision plus soft or vacuum grippers | Commercial lines exist (Marel, Baader) and SINTEF has published soft-gripper fillet work; no primary source verified here (unverified) | none |

Pattern across the table: the successful real-robot results are pick-and-place
parametrisations (pick point, place point, sometimes a second pair for a
bimanual system) chosen from an image, not continuous torque policies. That
is the action space to start with for the meat cell too.

### Transport without deformation

A piece held at one or two points and accelerated sees an inertial load
`m a` in addition to gravity. Two things cap the acceleration: slip at the
contact (friction cone: the tangential load must stay under `mu` times the
normal force, for a wet surface with `mu` well under 0.3 (unverified, measure
it)) and tearing or folding of the unsupported part, which depends on the
overhang and the tissue's tear strength. Practical consequences:

- Set joint and Cartesian acceleration limits per product class, not per robot.
  A rigid pick-and-place tuned for 2 g will fold a fillet.
- A cradle or plate support (the piece rests on a surface during transport and
  is only pinched to stop sliding) removes the tear constraint and leaves only
  slip. This is why scoop, spatula, and belt-assisted strategies exist.
- Shape the trajectory: ramp acceleration (S-curve or minimum-jerk), keep the
  support surface horizontal, and avoid rotations about the long axis in
  mid-air. Cartesian limits are one line in MoveIt or a joint trajectory
  controller; log peak acceleration per episode as you log peak force.
- For a learned policy, the acceleration cap lives in the controller, not the
  policy, the same way force caps do in `real-world-rl.md`.

### Placement and alignment into a fixture

The place step has to end with the piece flat, in the right orientation, and
with an edge against a datum. Elements that appear across the cloth and
garment literature and transfer directly:

- **Flattening.** Drag or two-point stretch to remove folds; VCD and the
  smoothing papers treat this as a coverage-maximisation task with a learned
  dynamics model or an imitation policy
  ([VCD](https://arxiv.org/abs/2105.10389), [Seita et al. 2020](https://arxiv.org/abs/1910.04854)).
- **Tensioning.** Holding one edge fixed while pulling the other gives a
  predictable shape for cutting; the surgical gauze-cutting work learned a
  tensioning policy for exactly this reason
  ([Thananjeyan et al., ICRA 2017](https://doi.org/10.1109/ICRA.2017.7989275)).
  A fixture with a clamp bar plus a controlled pull from the gripper is the
  meat-cell version.
- **Edge alignment.** Cloth Funnels defines success as matching a canonical
  pose and aligns the garment before folding
  ([arXiv:2210.09347](https://arxiv.org/abs/2210.09347)). For meat: place
  against a hard stop, release, then push the free edge with the closed
  gripper or a pusher. Alignment against a datum is more repeatable than
  alignment by placement accuracy.
- **Vision verification.** Segment the placed piece, fit the long axis and a
  bounding polygon, and compare to the fixture template. Report the residual
  (mm and degrees) per placement and make it the metric the customer sees.
  The 5 mm figure from Khodabandehloo is the reference for what a millimetre
  is worth ([Khodabandehloo 2022](https://doi.org/10.1093/af/vfac012)).

## Practical recipe: first learned grasp-and-place of a soft slab

Assumes a 6-DoF arm, a wrist camera plus an overhead RGB-D camera, a
parallel gripper with wide compliant pads (see the companion entry), and a
fixture with a datum edge. Follow `sops/data-collection-protocol.md` and
`sops/experiment-protocol.md`; the hypothesis goes in `experiments/` first.

1. **Define done.** Piece lies flat in the fixture, long axis within 5 degrees
   of the fixture axis, datum edge within 3 mm of the stop, no visible fold in
   the overhead mask. Write the checker before collecting data; it is also the
   reward classifier if you later fine-tune with RL.
2. **Characterise the product.** For 20 pieces: mass, length, width, thickness,
   and the acceleration at which a hand-held test grasp starts to slip
   (drop-test on a scale or an IMU on the gripper). Log fibre direction
   relative to the long axis. Put the table in `DATASET.md`.
3. **Choose the action space.** Start with a pick pixel and orientation plus a
   place pixel and orientation on the overhead image (the Transporter-style
   parametrisation), with a fixed lift height and a fixed S-curve trajectory
   between them ([Seita et al. 2021](https://arxiv.org/abs/2012.03385)). Add a
   second "push to datum" action as a scripted primitive. Only move to a
   continuous end-effector policy (ACT or Diffusion Policy,
   `imitation-learning.md`) if the discrete version cannot express the
   correction the task needs.
4. **Rigid baseline first.** Run the pipeline on a rigid dummy slab (silicone
   or a plastic plate of similar size) for 20 trials. This separates
   perception and calibration errors from deformation errors.
5. **Collect demonstrations.** 100 to 200 pick-place pairs on real product,
   labelled by a human clicking on the overhead image. Include pieces at the
   extremes of the size table. Log gripper width, the acceleration cap in use,
   and the grasp force setting.
6. **Train and evaluate.** Fully convolutional pick and place heads (Transporter
   or a segmentation backbone from `perception-foundation-models.md`). Evaluate
   with the checker from step 1 on 50 new pieces; report success with n,
   plus alignment residual distributions, plus a tear/fold count.
7. **Add contact feedback where the failures are.** If failures are slip in
   transport: a tactile pad or gripper current signal for regrasp
   (`perception-tactile-and-force.md`). If failures are folds on placement: a
   tensioning primitive and a lower place height. If failures are alignment:
   the push-to-datum primitive with vision verification.
8. **Then, and only then, sim.** If you need to explore grasp locations or
   trajectories beyond what the demos cover, build the slab in MuJoCo `flex`
   (3D tetrahedral, continuum mode) or Isaac Lab `DeformableObject` with
   the mass and stiffness from step 2 and tune until the sim reproduces the
   drop-test slip acceleration and the overhang sag of the real piece.

## Practical gotchas

- **Sim material mismatch dominates.** DefGraspSim spans elasticity over
  five orders of magnitude because the answer changes across it
  ([arXiv:2203.11274](https://arxiv.org/abs/2203.11274)). A sim with a guessed
  Young's modulus gives a confident wrong grasp. Measure sag and slip on the
  real product before trusting any sim number.
- **PBD stiffness is not a material constant.** In plain PBD, stiffness depends
  on the solver iteration count and time step; XPBD exists to fix this
  ([Macklin et al. 2016](https://doi.org/10.1145/2994258.2994272)). Do not
  transfer PBD parameters between engines.
- **Deformable sims are GPU-only or slow.** Isaac Lab's soft bodies are "only
  supported in GPU simulation"
  ([tutorial](https://isaac-sim.github.io/IsaacLab/main/source/tutorials/01_assets/run_deformable_object.html));
  MuJoCo `flex` is CPU and experimental in MuJoCo Warp
  (`sim-first-workflow.md`). Budget for this in the experiment plan.
- **Wet tissue defeats suction and cameras at once.** Specular highlights on
  wet surfaces break depth from structured light and stereo
  (`perception-3d-sensing.md`), and the same wetness leaks suction cups. Plan
  for polarised lighting or time-of-flight, and test suction on the actual
  product, not a dry sample (from field, unverified).
- **Cloth results are not slab results.** FlingBot's dynamic unfolding and the
  garment pipelines rely on cloth's tolerance of high strain; meat tears. Carry
  over the representations and action parametrisations, not the motions.
- **Keypoints on homogeneous product are ambiguous.** A fillet has no corners.
  Use mask geometry (principal axis, extreme points along it) rather than
  learned semantic keypoints unless there is a visible anatomical landmark.
- **Hygiene changes hardware.** Anything that touches product must be
  washdown-rated and food-contact compliant; tactile gels and camera windows
  are the first casualties (companion entry, and
  `perception-tactile-and-force.md` on gel wear).
- **Latent-state policies fail silently.** A latent that has drifted from the
  product distribution (new supplier, colder product) gives no error, only
  wrong actions. Keep the vision checker from step 1 running in deployment
  as an independent monitor (`deployment-engineering.md`).

## What a forward-deployed engineer must be able to do

- [ ] Explain to a customer engineer why a rigid grasp planner fails on their
      product, using the state-representation table.
- [ ] Measure a product class: mass, dimensions, sag under its own weight at a
      given overhang, slip acceleration for the chosen pads. Put it in
      `DATASET.md`.
- [ ] Build a Transporter-style pick-place pipeline with an overhead camera and
      evaluate it with a written checker and trial counts.
- [ ] Set and log Cartesian acceleration limits per product class in the
      controller; show that peak acceleration stays under the measured slip
      threshold.
- [ ] Implement a push-to-datum alignment primitive and the vision residual
      check, and report residuals in millimetres and degrees.
- [ ] Bring up one deformable sim (MuJoCo `flex` or Isaac Lab
      `DeformableObject`), match it to the measured sag and slip, and state
      what it can and cannot predict.
- [ ] Decide suction vs pinch vs support-plate for a given product from a
      short test series (20 picks each) and document the failure modes.

## Open questions to learn hands-on

- On our product, what is the slip acceleration for compliant pads versus
  textured food-grade pads, dry and wet, and how much does chilling change it?
- Does a pick-pixel policy trained on 150 demos beat a scripted
  centroid-and-axis grasp on alignment residual, at 50 trials each? The
  scripted baseline might win; that is a legitimate result.
- What overhang length starts a fold at our transport acceleration, and does
  a support plate let us double the acceleration without tearing?
- Can MuJoCo `flex` in continuum mode reproduce the measured sag within 20%
  after tuning Young's modulus and Poisson's ratio, and does that number stay
  valid across a day of product temperature drift?
- Whether the customer accepts any surface marking from pads or needles;
  this decides the gripper family before any learning starts.

## Related entries

- `library/topics/compliant-mechanisms-and-actuation.md` (grippers and
  compliance for the same cell)
- `library/topics/perception-tactile-and-force.md` (slip, force control)
- `library/topics/perception-3d-sensing.md` (depth on wet surfaces)
- `library/topics/imitation-learning.md` (ACT, Diffusion Policy)
- `library/topics/sim-first-workflow.md` (which simulator, pinned versions)
- `library/topics/sim-to-real.md` (deformables as a sim-gap item)
- `library/topics/real-world-rl.md` (controller-side caps)
- `sops/data-collection-protocol.md`, `sops/experiment-protocol.md`

## Sources

- Surveys and meat: [Yin et al. 2021](https://doi.org/10.1126/scirobotics.abd8803), [Sanchez et al. 2018](https://doi.org/10.1177/0278364918779698), [Khodabandehloo 2022](https://doi.org/10.1093/af/vfac012), [meat-industry slip gripper, arXiv:2307.05648](https://arxiv.org/abs/2307.05648), [cobot meat cutting, arXiv:2401.07875](https://arxiv.org/abs/2401.07875), [human-in-the-loop meat processing, arXiv:2508.14763](https://arxiv.org/abs/2508.14763)
- Modelling and sim: [DefGraspSim](https://arxiv.org/abs/2203.11274), [DefGraspNets](https://arxiv.org/abs/2303.16138), [SOFA](https://www.sofa-framework.org/), [Isaac Gym](https://arxiv.org/abs/2108.10470), [Müller et al. 2007](https://doi.org/10.1016/j.jvcir.2007.01.005), [XPBD](https://doi.org/10.1145/2994258.2994272), [MPM course](https://doi.org/10.1145/2897826.2927348), [MLS-MPM](https://doi.org/10.1145/3197517.3201293), [DiffTaichi](https://arxiv.org/abs/1910.00935), [PlasticineLab](https://arxiv.org/abs/2104.03311), [SoftGym](https://arxiv.org/abs/2011.07215), [Isaac Lab deformable tutorial](https://isaac-sim.github.io/IsaacLab/main/source/tutorials/01_assets/run_deformable_object.html), [Isaac Lab assets API](https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.assets.html), [MuJoCo modeling](https://mujoco.readthedocs.io/en/stable/modeling.html), [MuJoCo XML reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html), [Genesis](https://github.com/Genesis-Embodied-AI/Genesis)
- Representations and dynamics: [MeshGraphNets](https://arxiv.org/abs/2010.03409), [DPI-Net](https://arxiv.org/abs/1810.01566), [kPAM](https://arxiv.org/abs/1903.06684), [Dense Object Nets](https://arxiv.org/abs/1806.08756), [ACID](https://arxiv.org/abs/2203.06856), [DoughNet](https://arxiv.org/abs/2404.12524)
- Grasping: [Dex-Net 3.0](https://arxiv.org/abs/1709.06670), [Dex-Net 4.0](https://doi.org/10.1126/scirobotics.aau4984), [Schmalz needle grippers](https://www.schmalz.com/en/vacuum-technology-for-automation/vacuum-components/special-grippers/needle-grippers/), [Yuan et al. 2017](https://arxiv.org/abs/1704.03955), [Calandra et al. 2018](https://arxiv.org/abs/1805.11085)
- Learning: [Seita et al. 2021](https://arxiv.org/abs/2012.03385), [FabricFlowNet](https://arxiv.org/abs/2111.05623), [VCD](https://arxiv.org/abs/2105.10389), [SpeedFolding](https://arxiv.org/abs/2208.10552), [Cloth Funnels](https://arxiv.org/abs/2210.09347), [FlingBot](https://arxiv.org/abs/2105.03655), [Seita et al. 2020](https://arxiv.org/abs/1910.04854), [RoboCraft](https://arxiv.org/abs/2205.02909), [RoboCook](https://arxiv.org/abs/2306.14447), [DiffSkill](https://arxiv.org/abs/2203.17275), [Sundaresan et al. 2020](https://arxiv.org/abs/2003.01835), [Thananjeyan et al. 2017](https://doi.org/10.1109/ICRA.2017.7989275)
