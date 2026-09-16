# Architecture

The path of a file says whether it is general robotics or one customer's cell, and which way its
imports may point. The layout follows Neil's principles for the composable skill architecture; the
table at the end maps each principle to the tree.

## Layers

```
src/
  robotics/                         general robotics: names no product and no customer
    core/                           numpy and the standard library only; the ROS 2 nodes import it
      contracts.py                  Frame, Pose2D, Observation: stamped values that cross subsystems
      frames.py                     camera intrinsics and pose, pixel to plane, world to arm base
      camera_frame.py               CameraFrameData: one image, its depth and its camera geometry
      belt_state.py                 encoder readings to belt travel, speed and acceleration
      intercept.py                  when and where an arm meets a point riding the belt
      grasp_action.py               GraspAction: where and how to grip, the same for every arm
      grasp_policy.py               GraspPolicy: perceived product in, GraspAction out
      grasp_execution.py            the timed tool poses for one grasp, before IK
      skill_library/                Contract, run_skill, TaskGraph
    hardware/                       MuJoCo models of hardware any cell can be built from
      arms.py                       UR5e, UR20, FANUC SR-20iA: an ArmSpec and a builder each
      ik.py                         tool pose to joint values; raises UnreachableError
      grippers.py, assets/          pinch, jaw and three-finger grippers, and a wide-jaw placeholder for
                                    a loin-class gripper (its asset says what is assumed and why)
      cameras.py                    Gemini 335L and D455 depth cameras from their datasheets
      image_degradation.py          controlled damage to rendered images, each with its cause
    perception/                     what a depth camera says about whatever is on the belt
      depth_geometry.py             ray per pixel, RANSAC belt plane
      segmentation.py               colour and edge segmenters, mask scoring
      staged_segmenter.py           depth proposes, appearance refines, colour confirms
      pose_estimation.py            mask and depth to a planar pose
      centre_of_gravity.py          outline centre and column centroid
      learned_centre_of_gravity.py  learned offset on top of the column centroid
      tracking.py                   a pose carried forward in belt coordinates
  applications/
    pork_leg_alignment/             this plant's two cells: legs ride a belt to a saw that takes the
                                    trotter off at the hock; loins are set down square for the loin
                                    puller's infeed (the second cell, added 2026-09-16, see known gaps)
      sim/                          this line in MuJoCo: scene.py (CellConfig), cell.py, sensing.py,
                                    product.py (leg and slab), loin.py, saw.py, hold_down.py,
                                    infeed_fixture.py (the loin cell's judge), assets/cell.xml
      perception/                   leg_segmentation.py, learned_leg_segmentation.py, perceive_leg.py
      grasping/                     numpy only: leg_perception.py, shank_grasp_rule.py,
                                    learned_grasp_policy.py
      skills/                       leg_estimate.py, shank_grasp.py, trotter_grasp.py, rotate_on_belt.py;
                                    the loin's estimate, grasp station and alignment target in
                                    loin_estimate.py and loin_infeed.py
tests/                              mirrors src/: tests/robotics/core/test_frames.py tests frames.py
scripts/measure/, train/, view/     entry points, run from the repo root
ros2/src/                           meat_cell_msgs, meat_cell_ros: ROS 2 nodes over core and grasping/
```

`robotics/skills/` does not exist yet. It is the home for a skill that knows no product, created
with the first one. Both skills today read the leg model and the simulated `Cell`, so they are
application code.

## The dependency rule

```
applications.<cell>  ->  robotics.skills | robotics.perception | robotics.hardware  ->  robotics.core
```

1. Imports point down. `hardware`, `perception` and `skills` import `core` and not each other. An
   application imports anything in `robotics`, `robotics` never imports `applications`, and one
   application never imports another. When two siblings need the same thing, it moves into `core`.
2. `robotics/core/` and every `applications/<cell>/grasping/` are numpy-only. The ROS 2 Humble Python
   has numpy but no MuJoCo, OpenCV or torch, and `ros2/src/meat_cell_ros` imports only these modules.
3. Imports are absolute (`from robotics.core.frames import CameraPose`), so an import names the file.

`tests/test_layering.py` enforces all three in the normal test run. It parses every file under `src/`
and `ros2/src/meat_cell_ros/` with `ast`, imports inside functions included. It fails on an import
that points up or sideways; on a numpy-only module whose first-party imports, followed through every
package `__init__` on the way, reach anything but numpy and the standard library; on a relative
import; and on a new package under `robotics/` until it has a rank in `LAYER_RANK` and a line here.

Tests and scripts are not checked. A test sits under the folder of the module it tests, even when it
builds the simulated cell to check that module (`tests/robotics/core/test_frames.py` does).

### Why the simulated cell is application code

`sim/` models this customer's line: the belt and rails in `cell.xml`, the saw that cuts at the hock,
the hold-down chosen for this line on 2026-09-14, and the pork leg. What a second cell reuses sits
below it in `robotics/hardware/`: arms, IK, grippers and depth cameras. This also settles where the
leg model lives. `scene.py` and `saw.py` build the leg into the MuJoCo model and they are application
modules, so no hardware module imports the leg and no leg number enters `robotics/`.

## Adding a skill

1. Decide whether it knows the product. A skill that reads the leg model, leg perception or this
   cell's `Cell` goes in `applications/<cell>/skills/`. One that does not goes in `robotics/skills/`,
   imports only `robotics.core`, and receives the arm, camera or perception result it acts on through
   its contract's input ports.
2. Write a class with `name`, `contract` and `execute(world, args)` returning
   `(outcome, outputs, evidence)`: the `Skill` protocol in `robotics.core.skill_library`. The
   `Contract` declares inputs, preconditions, outputs, success checks and every failure mode.
   `applications/pork_leg_alignment/skills/shank_grasp.py` is a complete example.
3. Test it through `run_skill`, which rejects missing inputs, stops on a failed precondition,
   re-checks a claimed success and raises on an undeclared outcome. The test mirrors the skill's path.
4. Chain it in a `TaskGraph`. The graph will not build unless every outcome of every skill, including
   the runner's `precondition_failed` and `success_not_verified`, has an edge to a skill or a terminal. Those
   edges are the recovery design.

## Adding a robot

1. In `robotics/hardware/arms.py`: an `ArmModel` member, an `ArmSpec` (joint names, home pose,
   attachment site, ratings) and a builder returning an `MjSpec`, registered in `ARM_SPECS`. Each
   number's source goes in `library/hardware/arm-models-for-sim.md`.
2. `ik.py` works from the `ArmSpec` for six-axis and SCARA arms alike, so IK needs no change. Cover
   the model in `tests/robotics/hardware/test_arms.py`.
3. Give it a mount in `DEFAULT_MOUNTS` in `applications/pork_leg_alignment/sim/scene.py` and check its
   reach in `tests/applications/pork_leg_alignment/sim/test_cell_arms.py`.
4. For ROS 2, add `ros2/src/meat_cell_ros/config/<arm>.yaml` and a MoveIt config. Messages, policies
   and the intercept planner do not change.

A depth camera is a `DepthCameraModel` built from its datasheet in `robotics/hardware/cameras.py`,
added to `DEPTH_CAMERAS`.

## Adding a customer cell

1. Create `src/applications/<cell>/` with the subpackages it needs, named as here: `sim/` (its scene
   XML and product model, built from `robotics.hardware`), `perception/` (product-specific choices on
   `robotics.perception`), `grasping/` (its perceived-product type and policies implementing
   `robotics.core.grasp_policy.GraspPolicy`, numpy only) and `skills/`.
2. Import from `robotics`, never from another application. If `pork_leg_alignment` has something the
   new cell needs, that thing is not pork-specific: move it into `robotics/` with its tests, then
   import it from there in both cells.
3. Mirror it under `tests/applications/<cell>/`.

## Neil's principles in the tree

| Principle | Where it shows |
|---|---|
| Hardware, perception, skills, task logic and application configuration separated | `robotics/hardware/` and `robotics/perception/`; the skill contract and `TaskGraph` in `robotics/core/skill_library/` with the skills in `applications/<cell>/skills/`; the cell's configuration in one `CellConfig` (`sim/scene.py`). No line task graph is committed yet. |
| No customer-specific logic in general modules | Every leg, saw and line-geometry module is under `applications/pork_leg_alignment/`; `test_layering.py` fails on any `robotics` to `applications` import. |
| Skills reusable and independently testable | `Contract` and `run_skill` in `core`; each skill is tested alone through `run_skill`. |
| Failure recovery designed in, not added afterwards | Every `Contract` lists its `FailureMode`s; `TaskGraph` refuses an outcome with no edge; `GraspRefusedError`, `NoFeasibleInterceptError` and `UnreachableError` make a refusal an outcome instead of a best effort. |
| Explicit interfaces and readable state | Typed, stamped values in `core` (`contracts.py`, `camera_frame.py`, `grasp_action.py`); `GraspPolicy` as a protocol; `Observation` kept apart from `GroundTruth` in `sim/sensing.py`; task state on a blackboard by name. |
| The application says what; lower layers decide how | The application's policy returns a `GraspAction` (where to grip); `core`'s `intercept.py` and `grasp_execution.py` decide when and where the tool goes; `ik.py` or MoveIt decides the joints. |

Neil's test on a new problem, answered from the tree: existing skills are in `robotics/skills/` and
`applications/*/skills/`; a new one is added as above; chaining and recovery are a `TaskGraph`; and
whatever does not need to know the product becomes reusable infrastructure by moving into `robotics/`.

## Known gaps

- The loin puller infeed lives inside `applications/pork_leg_alignment/` rather than in its own
  `applications/<cell>/`, because it reuses this package's `Cell`, `CellConfig` and grasp and turn
  skills and the dependency rule forbids one application importing another. Section 14 of the plan
  designed the transfer that way (re-parameterise `CellConfig` and the skills, touch nothing under
  `robotics/`), and `experiments/2026-09-16-loin-infeed-transfer.md` counts what it touched. The
  package holds one customer's two cells and wants a customer-level name; renaming it touches the
  ROS 2 packages, every test path and the scripts, so it waits for a quiet moment.
- `sim/sensing.py`: `Sensors` reads cell.xml names (`slab_free`, `belt_encoder`, `g_grip_pos`) and the
  product bodies directly. Passing them in would let it move to `robotics/hardware/`.
- `robotics/hardware/cameras.py` mounts depth cameras on `overhead_cam_mount`, a body in this cell's XML.
- `robotics/core/frames.py` holds `BASE_HEIGHT_M = 0.90`, the UR5e pedestal height in this cell.
- `robotics/core/intercept.py` still says "leg" in docstrings and error messages; its tests match on
  the messages.
- `robotics/perception/learned_centre_of_gravity.py` sizes its grid (96 x 96 cells of 10 mm) and its
  height scale for legs.
- Two empty-belt references do one job: `staged_segmenter.BeltReference` (slab work) and
  `leg_segmentation.EmptyBeltReference`.
- `BELT_TOP_Z_M = 0.90` is defined in `skills/shank_grasp.py`, `sim/saw.py` and `sim/hold_down.py`;
  `BELT_JOINT` and `PRODUCT_JOINT` in both `sim/cell.py` and `sim/saw.py`.
- `sim/scene.py` mixes general assembly (arm on a mount site, gripper on the flange, depth cameras)
  with this cell's XML. The general half could move to `robotics/hardware/`.
- `_noisy` is still copied in `scripts/measure/leg_segmentation.py`,
  `scripts/measure/compare_leg_segmenters.py` and `scripts/view/leg_segmentation.py`.
