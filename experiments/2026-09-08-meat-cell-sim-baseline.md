---
title: Meat cell sim baseline, scripted pick-and-place of a soft slab from a moving belt
date: 2026-09-08
tags: [experiment, meat-cell, simulation, mujoco, isaac-lab, deformable, conveyor-tracking, baseline]
status: draft
decision: which simulator and slab object model to standardize on for the meat cell
---

# Experiment: meat-cell-sim-baseline

Scope note. This is the planned record, written before the run per
[experiment protocol](../sops/experiment-protocol.md). Nothing below is a result. Every
number is either a design choice (marked as such), a figure from a library note with its link,
or an assumption listed in Caveats. Background for the cell is in
[meat cutting automation](../library/topics/meat-cutting-automation.md); the object side is in
[deformable object manipulation](../library/topics/deformable-object-manipulation.md); the
simulator choice is in [sim-first workflow](../library/topics/sim-first-workflow.md).

## Hypothesis

A scripted look-then-move controller (one overhead depth image, PCA pose, encoder-synchronised
intercept, S-curve lift and place, push to a datum edge) can pick a soft slab from a belt moving
at up to 300 mm/s and place it in a mock cutter lane with placement error inside the bound below,
in both MuJoCo `flex` and Isaac Lab `DeformableObject`, without tearing or folding the slab.

Bound (design choice, pre-registered): over 50 fixed initial conditions per condition,

- rigid dummy slab: 95th percentile lane offset under 2 mm and yaw under 2 deg at every belt
  speed. The 2 mm figure is ABB's published tracking error at 150 mm/s
  ([ABB conveyor tracking manual](https://search.abb.com/library/Download.aspx?DocumentID=3HAC050991-001&LanguageCode=en&DocumentPartId=&Action=Launch)),
  used here as the calibration target for the sim tracking chain, not as a claim about the sim;
- deformable slab: 95th percentile lane offset under 5 mm and yaw under 5 deg, zero tear events,
  fold rate under 5 percent, at every belt speed. The 5 mm and 5 deg come from the alignment
  definition in the deformable note's recipe (step 1) and from the yield figures in the meat
  note (5 mm of cut placement was worth about $300k per line per year in 2003,
  [Khodabandehloo 2022](https://academic.oup.com/af/article/12/2/7/6576396)). The customer's
  cutter window replaces this bound once we have it (open question in the meat note).

If the hypothesis fails on the rigid dummy, the controller or tracking chain is wrong. If it
holds on the rigid dummy and fails on the slab, the failure is deformation and that is the
finding.

## Decision this informs

Which simulator and which slab model become the standard for every later meat-cell experiment,
starting with [learned vs scripted](2026-09-15-meat-cell-learned-vs-scripted.md). The
candidates, with the reasons each is on the list:

| Candidate | For | Against |
|---|---|---|
| MuJoCo 3.12 `flex` (3D tetrahedral, continuum mode) | CPU, so it runs on the laptop (GTX 1050 Ti, 4 GB; [compute note](../library/hardware/compute.md)); one MJCF for the rigid cell and the slab; `mujoco_ros2_control` gives the same-code ROS 2 path ([mujoco tool note](../library/tools/mujoco.md)); Saint Venant-Kirchhoff continuum with separate shear and volume stiffness ([MuJoCo modeling docs](https://mujoco.readthedocs.io/en/stable/modeling.html)) | Flex is experimental in MuJoCo Warp, so no GPU scale-up yet ([mujoco_warp](https://github.com/google-deepmind/mujoco_warp)); contact between flex and rigid limited to 8 bodies per pair (modeling docs); speed on CPU unknown until measured |
| Isaac Lab 2.3.x `DeformableObject` on Isaac Sim 5.1 | PhysX FEM soft body with nodal state exposed ([tutorial](https://isaac-sim.github.io/IsaacLab/main/source/tutorials/01_assets/run_deformable_object.html)); parallel envs and RTX cameras for the follow-on policy experiment | "only supported in GPU simulation" (same tutorial); needs an RTX card with 16 GB, so a rented 4090 at $0.34 to $0.74 per hour ([compute note](../library/hardware/compute.md)); no ros2_control plugin ([sim-first note](../library/topics/sim-first-workflow.md)) |
| Rigid box with randomized mass and friction (control arm) | Fast, runs anywhere, isolates tracking and controller errors from deformation errors (deformable note recipe, step 4) | Cannot show tear or fold, which is the meat-specific failure |

Genesis is excluded for this round: every 1.2 and 1.3 minor release carried a breaking section
and it has no ROS bridge (sim-first note).

## Setup

- Git SHA: fill at run start (`git rev-parse HEAD` of this repo and of the sim package).
- Config: `src/meat_cell_sim/configs/baseline.yaml` (to be created in step 2 below; one file,
  every sweep value in it, no constants in code).
- Dataset and checksum: none consumed. The run produces
  `experiments/runs/2026-09-08-meat-cell-sim-baseline/episodes.csv` plus the initial-condition
  list `ic_list_v1.json`; checksum both in this record after the run.
- Seed(s): 20260908 for the IC list; per-episode seed is the IC index. Log simulator version,
  physics backend and driver per episode (Isaac Lab determinism holds only for the same hardware
  and version, [reproducibility page](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/features/reproducibility.html)).
- Hardware: MuJoCo arm on the laptop CPU (`rll` env, `env -u PYTHONPATH`). Isaac Lab arm on a
  rented RTX 4090 (RunPod, container `nvcr.io/nvidia/isaac-lab:2.3.2`, headless with
  `--enable_cameras`).
- Software: `mujoco==3.12.0`, `mujoco_ros2_control` 0.1.1 (Humble), Isaac Sim 5.1 with Isaac Lab
  2.3.2 (pinned pair, sim-first note), Python 3.11 in `rll`, ROS 2 Humble in `rosdev`.

### Simulator and object models

Three object models, identical outer dimensions and mass in all three:

1. Rigid box, MuJoCo `geom type="box"` and an Isaac Lab `RigidObject`.
2. MuJoCo `flexcomp` type `grid`, 3D tetrahedral, continuum mode (Saint Venant-Kirchhoff),
   `dim="3"`, resolution to be chosen in step 3 so that one episode runs in under 60 s wall time.
3. Isaac Lab `DeformableObjectCfg` with a tetrahedral simulation mesh and a coarser collision
   mesh, the two-mesh scheme the tutorial describes.

### Arm

UR5e from MuJoCo Menagerie for the MuJoCo arm, converted with Isaac Lab's `convert_mjcf.py`
for the Isaac arm ([Menagerie](https://github.com/google-deepmind/mujoco_menagerie),
[import guide](https://isaac-sim.github.io/IsaacLab/main/source/how-to/import_new_asset.html)).
Reasons, from [robot arms](../library/hardware/robot-arms.md): a vendor-maintained ROS 2 driver
(`Universal_Robots_ROS2_Driver`, Humble), RTDE at 500 Hz, and the only conveyor-tracking path
documented for a cobot (`track_conveyor_linear`, encoder on DI0 to DI3 at up to 40 kHz, meat
note). The UR is not the production arm. Production candidates are washdown 6-axis arms (FANUC
LR Mate 200iD/7WP, KUKA KR AGILUS HM, Stäubli TX2 HE) in the
[meat cell shortlist](../library/hardware/meat-cell-shortlist.md); they are the same class
(6 axes, 700 to 900 mm reach), so the controller structure transfers and the kinematic model gets
swapped when the customer names the arm. Joint velocity limits and the Cartesian acceleration cap
below are what carry over, not the URDF.

### Gripper

A parallel jaw modelled as a position-controlled joint with a force limit (sim-first note,
section 6), with the Robotiq 2F-140 stroke (140 mm, 10 to 125 N,
[product sheet](https://robotiq.com/hubfs/Product-sheets/Adaptive%20Grippers/Product-sheet-Adaptive-Grippers-EN.pdf))
and custom flat pads 60 mm wide by 40 mm tall. Reasons: the compliant note's selection guide
says a 40 to 120 mm slab needs about 140 mm of stroke
([compliant mechanisms](../library/topics/compliant-mechanisms-and-actuation.md), step 1), and
wide pads spread load so no point exceeds tear stress (deformable note, grasp table). Pinch is
chosen for the sim because neither simulator models suction on a deformable natively; the
production choice between vacuum, soft fingers and a support plate is a real-product test
(20 picks each, compliant note step 8), not a sim result. Pad friction is a sweep variable.

### Belt

A 1.5 m long, 300 mm wide box on a prismatic joint with a velocity actuator in MuJoCo; a
kinematic rigid body with its linear velocity set each step in Isaac Lab. The slab rests on it
and moves with it through friction. An "encoder" is the belt joint position sampled at the
control rate and quantised to 5,000 counts per metre (the low end of ABB's recommended 5,000 to
10,000 counts per metre after 4x decoding, ABB manual). A photo-eye trigger is a plane 400 mm
upstream of the pick zone: the first control step at which the slab's leading edge crosses it
stamps the object with the encoder count. Belt speeds: 0 (presented piece), 100, 200, 300 mm/s.
The 300 mm/s ceiling is a design choice below ABB's 500 mm/s degradation point and inside the
I-Cut 130's 20 to 500 mm/s belt range (meat note).

### Slab parameters to sweep

Nominal slab 180 x 90 x 30 mm, 0.5 kg (assumption; the customer's piece size and mass range is
an open question in the shortlist). The deformable note states there is no calibrated
constitutive model of raw muscle in any of these simulators and that sag and slip must be
measured on product before a sim number is trusted, so the sweep brackets the unknown rather
than guessing a value:

| Parameter | Values | Why this range |
|---|---|---|
| Young's modulus | 10, 50, 250 kPa | Two decades inside DefGraspSim's five-order span ([Huang 2022](https://arxiv.org/abs/2203.11274)); replaced by the sag measurement on product (deformable note, recipe step 2). Assumption. |
| Poisson's ratio | 0.45 fixed | Near-incompressible tissue; not swept. Assumption. |
| Pad-slab friction | 0.15, 0.3, 0.6 | Wet surfaces "well under 0.3" (deformable note, unverified); the 0.6 point is the dry control |
| Belt-slab friction | 0.3 fixed | Assumption; set from the belt sample once we have one |
| Mass | 0.3, 0.5, 1.0 kg | Brackets the nominal until the customer's range arrives |
| Length x width | 140 x 70, 180 x 90, 220 x 110 mm | Same |

Full grid is 3 x 3 x 3 x 3 = 81 material cells; too many at 50 episodes each. Pre-registered
plan: the belt-speed sweep runs at the nominal material (50 kPa, mu 0.3, 0.5 kg, 180 x 90); the
material sweep runs one factor at a time from that nominal at 200 mm/s (one variable at a time,
experiment protocol). That is 4 speeds plus 8 off-nominal material cells, 12 conditions.

### Cameras

Two pinhole cameras, intrinsics copied from a RealSense D435 `CameraInfo` at 640 x 480 so the
sim and the bench camera see the same model (sim-first note, section 4). Overhead camera 600 mm
above the belt, centred 400 mm upstream of the pick zone, optical axis vertical; that upstream
distance leaves 500 ms of belt travel at 300 mm/s between exposure and pick, the budget the meat
note derives for a Zivid HDR capture. Verification camera 500 mm above the mock lane, same
intrinsics. Depth from the sim renderer is noise-free; a Gaussian depth noise term (sigma 2 mm,
assumption) is on by default so the PCA pose sees noise now and not in September.

### Scripted controller

1. Trigger: photo-eye crossing stamps the encoder count.
2. One overhead depth frame at the stamp; segment by height above belt; oriented bounding box
   by PCA of the segmented points ([Open3D OBB](https://www.open3d.org/docs/release/python_api/open3d.geometry.OrientedBoundingBox.html));
   centroid and yaw in the belt frame; 180-degree ambiguity resolved by the leading-edge rule
   (the end that crossed the photo-eye first is the "tip").
3. Grasp point: mask centroid, jaw axis across the long axis (deformable note: near the centroid,
   across the fibre, short overhang).
4. Intercept: target expressed in the belt frame (encoder count plus offset), arm matches belt
   velocity over the last 100 mm of approach, closes at the force limit, lifts 80 mm.
5. Transport under a Cartesian acceleration cap of 2 m/s2 (design choice; the deformable note
   says a 2 g pick-and-place folds a fillet, and the cap is a controller setting, not a policy
   output) on a minimum-jerk profile, support surface kept horizontal, no rotation about the
   long axis in flight.
6. Place: lower to 5 mm above the lane floor, release, then push the free edge to the datum
   stop with the closed jaw (push-to-datum primitive, deformable note).
7. Verification frame: segment the placed slab, PCA, compute lane offset and yaw against the lane
   template.

Every step logs its timestamp so the cycle-time breakdown matches the latency table in the meat
note.

## Evaluation protocol

- Trials: 50 episodes per condition from one fixed initial-condition list (`ic_list_v1.json`,
  seed 20260908), the 50-per-task convention the sim-first note takes from LIBERO and OpenVLA.
  12 conditions x 3 object models x 2 simulators = 3,600 episodes. The rigid box runs the full
  grid in both simulators first; a deformable condition runs only after its rigid counterpart
  passes the bound.
- Initial condition sampling (written distribution, logged per episode): slab start position
  uniform across the belt width minus 20 mm margin, start yaw uniform in plus or minus 45 deg,
  start 600 mm upstream of the photo-eye, initial "resting" deformation from a 0.5 s settle
  under gravity before the belt starts. Belt speed constant within an episode.
- Success definition (pre-registered): slab released inside the lane polygon, lane offset within
  5 mm and yaw within 5 deg after the push-to-datum step, no tear event, no fold event, cycle
  time under 8 s from trigger to verification frame. Subgoals logged separately: grasp (jaw
  stopped on object, both pads in contact), lift (slab centroid 50 mm above belt with both pads
  in contact), place (inside lane polygon before push).
- Metrics per episode:
  - lane offset (mm) and yaw (deg) from the verification frame; report median and 95th
    percentile per condition, the 95th being the number (meat note, evaluation protocol);
  - tear proxy: maximum edge strain over any flex edge or FEM element during the episode; a
    tear event is strain over 0.5 (assumption; neither simulator tears, so this is a threshold
    on the quantity that would tear, to be replaced by a measured tear strain on product);
  - fold event: placed footprint area under 80 percent of the flat footprint, or maximum
    thickness over 1.5 times nominal, from the verification depth frame (assumption);
  - cycle time (s), trigger to verification, and its breakdown;
  - wall-clock seconds per simulated second per simulator, because the follow-on experiment
    needs thousands of episodes.
- Judge: the checker script, `src/meat_cell_sim/eval/checker.py`, written and unit-tested in
  step 6 before any episode runs.
- Report: k/n per condition with a Wilson 95 percent interval
  ([policy evaluation](../library/topics/policy-evaluation.md)); one table per simulator; one
  figure of lane-offset 95th percentile against belt speed for the three object models.

## Build steps

1. Package `src/meat_cell_sim/` per the CLAUDE.md layout (`pyproject.toml`, `tests/`, ruff and
   mypy strict). `TWIN.md` next to the scene with provenance for every number: measured,
   datasheet, vendor file, or assumption (sim-first note, twin procedure).
2. `configs/baseline.yaml`: every value in the tables above, dataclass-loaded.
3. MuJoCo scene: Menagerie UR5e, belt with prismatic joint and velocity actuator, gripper, slab
   `flexcomp`, two cameras. Check inertia and joint limits against the UR datasheet after load.
   Pick flex resolution: start at 6 x 3 x 2 cells and double until wall time per episode passes
   60 s or the slab's static sag under its own weight stops changing by more than 10 percent
   between resolutions. Record both numbers.
4. Belt-frame tracking: `belt_frame.py` turns the quantised encoder into a moving frame;
   `trigger.py` stamps objects. Unit test: a rigid box at 300 mm/s stays within 0.2 mm of its
   predicted belt-frame position over 2 s (5,000 counts per metre gives 0.2 mm quantisation).
5. Controller `scripted_intercept.py` with the seven steps above; each step is a function that
   returns its timestamp; the acceleration cap is enforced in the trajectory generator and its
   peak is logged per episode.
6. Checker `eval/checker.py` and the IC list generator. Tests: hand-built placements at 4.9 mm
   and 5.1 mm offset return pass and fail; a synthetic folded footprint returns a fold event.
7. Rigid-box runs in MuJoCo, all 12 conditions. Stop and fix if the bound fails.
8. Deformable runs in MuJoCo. Log wall time per episode.
9. Isaac Lab port: `convert_mjcf.py` for the arm, `DeformableObjectCfg` for the slab, the same
   controller against the Isaac Lab articulation API. Observation parity test between the two
   simulators: same shapes, dtypes, frame ids, depth value range on the same IC (sim-first note).
10. Rigid then deformable runs in Isaac Lab on the rented GPU. Record container tag, driver,
    GPU model.
11. Analysis notebook to CSV and the two tables; fill Results; write the decision.

Estimated cost: 3 to 4 working days of build (steps 1 to 6), one laptop-day of MuJoCo runs,
about 6 GPU-hours rented for Isaac Lab (assumption, measure in step 10).

## Results

Not run. Table to be filled from `episodes.csv`.

| Condition | Successes / trials | Notes |
|-----------|--------------------|-------|

## Decision taken and why

Not yet taken. The pre-registered mapping from outcome to decision:

| Outcome | Decision |
|---|---|
| Rigid box fails the bound in either simulator | Controller or tracking bug. Fix, re-run, no simulator decision until it passes. |
| Both deformable models pass at nominal material | Standardize on MuJoCo `flex`: CPU, one MJCF, ros2_control path. Keep the Isaac Lab scene only if the follow-on policy needs rendered RGB at scale. |
| MuJoCo `flex` fails (unstable at low modulus, tear-proxy blowups, or over 60 s per episode) and Isaac Lab passes | Standardize on Isaac Lab `DeformableObject`; accept GPU-only and the missing ros2_control seam; the same-code path becomes topics through the Isaac Sim bridge. |
| Isaac Lab fails and MuJoCo passes | Standardize on MuJoCo `flex`. |
| Rigid passes, both deformables fail at nominal | The object model is the problem, not the controller. Develop the controller and the follow-on policy on the rigid box with randomized mass and friction; move every deformation question to real product per the deformable note (recipe step 8: "then, and only then, sim"). |
| Deformables pass only at the stiffest modulus | Report the modulus at which each fails; the sag measurement on product decides whether that regime is the real one. Standardize on whichever simulator held the lowest modulus. |
| Wall time over 60 s per episode in the chosen simulator | Follow-on demonstrations come from the rigid box; the deformable slab is evaluation-only. |

## Caveats

- Assumptions to replace with customer or bench numbers: slab dimensions and mass, modulus range,
  friction values, depth noise sigma, tear strain threshold, fold thresholds, the 5 mm and 5 deg
  bound, 2 m/s2 acceleration cap, cost estimate.
- The UR5e is a stand-in for the washdown arm; only the controller structure and the limits are
  meant to transfer.
- Pinch pads in sim, not vacuum; the production gripper decision is made on product, not here.
- No simulator here tears or is calibrated to muscle. The pass/fail says whether the controller
  is sound and which simulator is usable, not whether the real slab survives.
- The photo-eye and encoder are ideal apart from quantisation; jitter and camera exposure time
  are added in the follow-on, not here.
- Pick-on-the-fly versus presented piece is still an open question with the customer; the 0 mm/s
  condition covers the presented-piece case.

## Step 1 progress: the cell stands up (2026-09-08)

Not a result for the hypothesis. This records that the apparatus is calibrated,
which the experiment protocol requires before any episode is run.

Built: `src/meat_cell_sim/` with `cell.xml` (belt, rails, product, cutter lane,
overhead camera), `gripper.xml` (parallel jaw, 140 mm stroke, 60 mm pads), and
`scene.py`, which attaches the Menagerie UR5e (pin `8161bba`) and the gripper
with `MjSpec.attach` so the third-party checkout stays unedited. Model compiles
to 16 DoF, 8 actuators, 2 cameras, 8 sensors.

Gate, all passing:

| Check | Requirement | Measured |
|---|---|---|
| Belt speed tracking | within 2 mm/s of command | 0.0 mm/s error at 0.10, 0.15, 0.30 m/s |
| Product carried, not teleported | slip under 5 mm/s | 0.0 mm over 2 s at all three speeds |
| Product rests without sinking | under 1 mm in 1 s | 0.01 mm |
| Pick and lane inside arm reach | under 0.850 m | 0.781 m and 0.541 m |
| Step speed on the laptop CPU | faster than realtime | 86x realtime |

Four calibration errors were found and fixed. Each was silent, and the first two
would have biased every intercept in the experiment:

1. Side rails at y = 0.295 overlapped the belt edge at 0.300 and touched it at
   z = 0.90, jamming the moving belt against the static world. The belt held at
   0.00008 m/s under 60 N of actuator force. Rails moved to leave a 7 mm gap.
2. The belt joint carried 200 N.s/m of damping while its velocity servo had
   kv = 400. A velocity servo settles at v = ctrl.kv/(kv+c), so the belt ran at
   exactly two thirds of every commanded speed. Damping is now zero and kv is
   2000, and a test asserts the tracking error stays under 2 mm/s.
3. Every cell geom was in group 3, which the renderer hides, so the scene
   rendered as an arm floating in a void. Now group 0.
4. The overhead camera carried `quat="0 1 0 0"`, a 180 degree flip about x, so
   it faced the ceiling and rendered black. A MuJoCo camera looks along its own
   negative z, so identity is already straight down.

Interim evidence for the simulator decision: MuJoCo runs this cell at 86x
realtime on the laptop CPU with no GPU, which removes the rented-4090 cost from
the Isaac Lab column for every rigid condition. The deformable conditions are
still open, since that is where MuJoCo `flex` and PhysX FEM actually differ.
