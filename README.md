# Robot Learning Lab

Personal knowledge base and working library for forward-deployed robot learning
engineering. Everything here is meant to be read by both a human and by Claude
Code, so entries are plain Markdown with consistent front matter.

## Layout

| Directory        | Purpose                                                              |
|------------------|----------------------------------------------------------------------|
| `sops/`          | Standard operating procedures. Followed every time, no exceptions.   |
| `library/papers` | One file per paper: citation, core idea, what it changes in practice. |
| `library/topics` | Synthesized notes per subject (imitation learning, VLAs, sim2real…). |
| `library/tools`  | Notes on frameworks and stacks (LeRobot, ROS 2, Isaac, MuJoCo…).      |
| `library/hardware` | Robots, sensors, grippers, compute encountered in the field.        |
| `field-notes/`   | Dated log per deployment day. Raw, honest, written same day.         |
| `experiments/`   | One file per experiment: hypothesis, setup, result, decision.        |
| `templates/`     | Skeletons for new Python packages and ROS 2 nodes.                   |
| `snippets/`      | Small, tested, reusable code fragments.                              |

## Conventions

- Filenames: `kebab-case.md`. Dated files: `YYYY-MM-DD-slug.md`.
- Every note begins with YAML front matter (`title`, `date`, `tags`, `status`).
- `status` is one of `draft`, `reviewed`, `stale`.
- Never record a claim about a paper or tool without a source link.
- Field notes and experiment logs are append-only after the day ends.

## Workflow

1. Before a deployment: read `sops/field-deployment-checklist.md`.
2. During: keep a `field-notes/` file open and log as you go.
3. After: convert findings into `library/` entries and `experiments/` records.
4. Ask Claude to review any new entry against `CLAUDE.md` standards.

## Environments on this machine

| Env | Python | Use |
|-----|--------|-----|
| `conda activate rll` | 3.11 | Library tooling, pure ML code, running the templates' checks. |
| `conda activate rosdev` | 3.10 | Anything importing `rclpy`. Matches `/opt/ros/humble`. |

Run tests in `rll` with `env -u PYTHONPATH pytest` (see `library/tools/ros2-humble.md`).

## Code layout

`src/robotics/` holds robotics code with no product or customer knowledge, in three layers: `core`
(numpy only: frames, the skill contract and task graph, belt state, intercept, the grasp action),
`hardware` (MuJoCo arms, IK, grippers, depth cameras) and `perception`.
`src/applications/pork_leg_alignment/` is the pork-leg alignment cell built on it, including its
MuJoCo simulation. `ARCHITECTURE.md` says what goes where, the import rule `tests/test_layering.py`
enforces, and how to add a skill, a robot or a customer cell.

## Meat cell simulation

A MuJoCo 3.12 simulation of the pork-leg alignment cell (`src/applications/pork_leg_alignment/sim/`)
and the skill library it runs on (`src/robotics/core/skill_library/`). The technical plan is
`plan/leg-cell-plan.html`.

Every command runs from the repo root in the `rll` env:

```bash
env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python -m pytest -q     # 250 tests, about 21 s
```

| Script | What it measures or films |
|---|---|
| `scripts/measure/perception.py --episodes 40` | Sensing, frames, perception and tracking gates on slabs |
| `scripts/measure/segmentation.py --samples 12` | Segmentation methods against the truth mask under image damage |
| `scripts/measure/pipeline.py --samples 30` | Depth-first pipeline against colour-only baselines, scored on pose |
| `scripts/measure/grasp_shift.py --trials 12` | How far the product moves in the gripper as the jaws close |
| `scripts/measure/hold_down.py` | Leg turn and slip during the saw cut, with and without the hold-down |
| `scripts/measure/arm_reach.py` | UR20 and SR-20iA reach over the belt, tool pointing down |
| `scripts/measure/shank_grasp.py` | Each arm and gripper grasping a leg, with contract outcomes |
| `scripts/view/grasp_test_videos.py` | One captioned video per arm, gripper and grasp test |
| `scripts/view/saw.py --out saw.mp4` | The saw cutting a leg, with or without the hold-down |
| `scripts/view/perception.py --out perception.mp4 --seconds 20` | Perception and tracking drawn on the overhead camera |
| `scripts/view/cell.py --record cell.mp4 --seconds 12` | The cell running |
| `scripts/view/leg_variants.py --count 20 --out legs.png` | The generated leg population |
| `scripts/measure/depth_cameras.py [--mount-yaw-deg 90]` | Gemini 335L against D455 on the 20 legs: depth noise, pixels on the shank, legs in view |
| `scripts/view/depth_cameras.py --out cams.mp4` | Both depth cameras side by side: colour, reported depth, depth error |
| `scripts/measure/leg_segmentation.py [--edge-effects]` | Depth-height leg segmentation on 20 legs × 9 poses against the silhouette |
| `scripts/view/leg_segmentation.py` | Video of the depth-height segmenter on moving legs |
| `scripts/view/edge_effects.py` | Zoomed picture of the camera's edge effects and the mask fringe they cause |
| `scripts/train/leg_segmenter.py [--edge-effects]` | Render simulated frames and train the U-Net leg segmenter on CPU |
| `scripts/measure/compare_leg_segmenters.py --checkpoint <pt> [--edge-effects]` | Geometry, U-Net and both combined on the same 180 frames, with time per frame |
| `scripts/measure/segment_real_footage.py --frames <dir> --checkpoint <sam.pth> --out <dir>` | Real plant frames: colour rule against Segment Anything plus the colour rule |
| `scripts/measure/centre_of_gravity.py` | Outline centre against column centroid on 20 legs × 9 poses, both masks, with and without edge effects |
| `scripts/view/centre_of_gravity.py --leg 15` | Picture of the true centre of mass, outline centre and column centroid on one leg |
| `scripts/view/centre_of_gravity_video.py` | Video of the centre-of-gravity estimates as legs ride the belt |
| `scripts/train/centre_correction.py` | Train the learned offset on top of the column centroid |
| `scripts/measure/compare_centre_correction.py --checkpoint <pt>` | Column centroid against column centroid plus the learned offset |
| `ros2/` (colcon workspace) | `meat_cell_msgs` and `meat_cell_ros`: grasp pipeline over ROS 2 with MoveIt IK; see `ros2/src/meat_cell_ros/README.md` |

Prefix each with `env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python`. `scripts/measure/` holds
measurement runs, `scripts/train/` training runs (checkpoints in `outputs/`), `scripts/view/` pictures
and videos. Experiment records, written
before each run, are in `experiments/`; raw results in `experiments/data/`.

## Living documentation site

`tools/build_site.py` renders every note into `site/index.html` with a
coverage dashboard, search, status badges, and Mermaid diagrams. Rebuild after
editing notes:

```bash
conda activate rll
env -u PYTHONPATH python tools/build_site.py          # local file, opens in any browser
env -u PYTHONPATH python tools/build_site.py --artifact --out /tmp/site.html   # for publishing
```

Tests: `cd tools && env -u PYTHONPATH pytest`.
