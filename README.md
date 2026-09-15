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

## Meat cell simulation

A MuJoCo 3.12 simulation of the pork-leg alignment cell (`src/meat_cell_sim/`) and the skill
library it runs on (`src/skill_library/`). The technical plan is `plan/leg-cell-plan.html`.

Every command runs from the repo root in the `rll` env:

```bash
env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl python -m pytest -q     # 184 tests, about 15 s
```

| Script | What it measures or films |
|---|---|
| `scripts/measure_perception.py --episodes 40` | Sensing, frames, perception and tracking gates on slabs |
| `scripts/measure_segmentation.py --samples 12` | Segmentation methods against the truth mask under image damage |
| `scripts/measure_pipeline.py --samples 30` | Depth-first pipeline against colour-only baselines, scored on pose |
| `scripts/measure_grasp_shift.py --trials 12` | How far the product moves in the gripper as the jaws close |
| `scripts/measure_hold_down.py` | Leg turn and slip during the saw cut, with and without the hold-down |
| `scripts/measure_arm_reach.py` | UR20 and SR-20iA reach over the belt, tool pointing down |
| `scripts/measure_shank_grasp.py` | Each arm and gripper grasping a leg, with contract outcomes |
| `scripts/record_test_videos.py` | One captioned video per arm, gripper and grasp test |
| `scripts/view_saw.py --out saw.mp4` | The saw cutting a leg, with or without the hold-down |
| `scripts/view_perception.py --out perception.mp4 --seconds 20` | Perception and tracking drawn on the overhead camera |
| `scripts/view_cell.py --record cell.mp4 --seconds 12` | The cell running |
| `scripts/show_leg_variants.py --count 20 --out legs.png` | The generated leg population |

Prefix each with `env -u PYTHONPATH PYTHONPATH=src MUJOCO_GL=egl`. Experiment records, written
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
