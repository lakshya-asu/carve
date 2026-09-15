---
title: LeRobot
date: 2026-09-05
tags: [tool, imitation-learning, huggingface, dataset-format, so-101, act, vla]
status: draft
source: https://github.com/huggingface/lerobot ; https://huggingface.co/docs/lerobot/index
---

# LeRobot

Hugging Face's PyTorch library for real-robot learning: a dataset format that has become the
de facto interchange format for teleop episodes, drivers for low-cost arms, training scripts
for ACT, Diffusion Policy and a long list of VLAs, and a deployment CLI. This note is the
install and operations record. Method background is in
[imitation-learning](../topics/imitation-learning.md) and
[vision-language-action-models](../topics/vision-language-action-models.md); collection
protocol is in [teleoperation-and-data-collection](../topics/teleoperation-and-data-collection.md);
the controller side of "policy to motor" is in
[connecting-to-real-robots](../topics/connecting-to-real-robots.md).

## Versions (checked 2026-09-05)

| Release | Date | What changed |
|---|---|---|
| 0.4.0 to 0.4.4 | Nov 2025 to Feb 2026 | Dataset v3.0 on by default; ViperX/WidowX (ALOHA) robot classes removed (last present in v0.3.3) |
| 0.5.0, 0.5.1 | Mar, Apr 2026 | Python 3.12 minimum, transformers v5, `cudnn_deterministic` |
| 0.6.0 | 6 Jul 2026 | Base `pip install lerobot` no longer pulls dataset or training deps; `lerobot-rollout` replaces `lerobot-record --policy.path`; torch 2.7 minimum; `eval_freq` renamed `env_eval_freq`; `sac` policy renamed `gaussian_actor`; GR00T N1.5 replaced by N1.7; `--dataset.vcodec` moved to `--dataset.rgb_encoder.vcodec` |
| 0.6.1 (current PyPI) | 3 Aug 2026 | `lerobot.types` renamed `lerobot.lerobot_types`; bucket streaming; RealSense manual exposure; SO follower P gain configurable |

Sources: [releases](https://github.com/huggingface/lerobot/releases),
[PyPI](https://pypi.org/project/lerobot/),
[v0.3.3 viperx config](https://github.com/huggingface/lerobot/blob/v0.3.3/src/lerobot/robots/viperx/config_viperx.py).
`main` is at `version = "0.6.2"`; pin a release for anything a customer runs.

## Install

`requires-python = ">=3.12"`, `torch>=2.7,<2.12.0`, `numpy>=2.0.0,<2.3.0` (the numpy cap
comes from opencv-python-headless)
([pyproject.toml](https://github.com/huggingface/lerobot/blob/main/pyproject.toml)).

```bash
conda create -y -n lerobot python=3.12 && conda activate lerobot
conda install ffmpeg -c conda-forge          # torchcodec needs it; fall back to ffmpeg=7.1.1 if libsvtav1 is missing
pip install --index-url https://download.pytorch.org/whl/cu128 torch torchvision
pip install 'lerobot[core_scripts,training,feetech]'   # record/replay/calibrate + train + SO-10x motors
```

Extras that matter, all from `pyproject.toml`: `core_scripts` = `dataset` + `hardware` + `viz`;
`training` = `dataset` + `wandb` + `accelerate`; `dataset_viz`; `evaluation`; motors `feetech`
(SO-100/101, LeKiwi, HopeJR) and `dynamixel` (Koch); policies `pi` (π0, π0-FAST, π0.5),
`smolvla`, `diffusion`, `groot`, `xvla`, `wallx`; sims `aloha`, `pusht`, `libero`, `metaworld`;
`async` (grpcio); `hilserl`; `all`. Base `pip install lerobot` gives you a library that cannot
load a dataset ([installation](https://huggingface.co/docs/lerobot/installation)).

CUDA wheels: a source install with `uv` pins torch to the cu128 index (driver floor 570.86);
`pip install lerobot` from PyPI gets the cu130 default wheel (driver floor 580.65), so install
torch first with an explicit index if the box has an older driver
([installation](https://huggingface.co/docs/lerobot/installation)).
System-wide `ffmpeg` (apt, brew) only works with torch 2.10 / torchcodec 0.10 or newer;
older pairs need the conda ffmpeg. Do not source `/opt/ros/humble/setup.bash` in this shell:
the Humble `PYTHONPATH` leak breaks 3.12 interpreters ([ros2-humble](ros2-humble.md)).

## Dataset format v3.0

`CODEBASE_VERSION = "v3.0"`
([dataset_metadata.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/datasets/dataset_metadata.py)).
Many episodes per file; episode boundaries live in metadata, not filenames
([LeRobotDataset v3.0](https://huggingface.co/docs/lerobot/lerobot-dataset-v3)).

```
meta/info.json            codebase_version, fps, features{name: {dtype, shape, names}}, total_episodes,
                          total_frames, total_tasks, chunks_size, data_files_size_in_mb,
                          video_files_size_in_mb, data_path, video_path, robot_type, splits, storage_format
meta/stats.json           per-feature mean/std/min/max/count used by the normalization processors
meta/tasks.parquet        task string -> task_index
meta/episodes/chunk-000/file-000.parquet
                          per episode: episode_index, length, tasks, data/chunk_index, data/file_index,
                          dataset_from_index, dataset_to_index, videos/<key>/chunk_index, /file_index,
                          /from_timestamp, /to_timestamp, plus per-episode stats
data/chunk-000/file-000.parquet
                          one row per frame: timestamp (float32), frame_index, episode_index, index,
                          task_index (int64) plus observation.state, action, ... as arrays
videos/<camera_key>/chunk-000/file-000.mp4
```

Sizing constants: `DEFAULT_CHUNK_SIZE = 1000` files per chunk, `DEFAULT_DATA_FILE_SIZE_IN_MB = 100`,
`DEFAULT_VIDEO_FILE_SIZE_IN_MB = 200`; a new file starts when the running one would exceed the
limit ([utils.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/datasets/utils.py),
[dataset_writer.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/datasets/dataset_writer.py)).
The five always-present columns are `DEFAULT_FEATURES` in
[constants.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/utils/constants.py).
The docs page still says `meta/tasks.jsonl`; the code writes `meta/tasks.parquet`
(`DEFAULT_TASKS_PATH`). Trust the code.

Video: default encoder `libsvtav1`, `pix_fmt yuv420p`, GOP `g=2`, `crf=30`;
`vcodec=auto` picks the first available of `h264_videotoolbox`, `hevc_videotoolbox`,
`h264_nvenc`, `hevc_nvenc`, `h264_vaapi`, `h264_qsv`, else `libsvtav1`; `h264`, `hevc`,
`libaom-av1` are accepted ([configs/video.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/configs/video.py)).
Decoding defaults to torchcodec where a wheel exists (Linux x86_64, macOS arm64; Windows needs
torch 2.8+; Linux aarch64 needs torch 2.11+ and torchcodec 0.11), else `pyav`
([pyproject.toml](https://github.com/huggingface/lerobot/blob/main/pyproject.toml),
[video_utils.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/datasets/video_utils.py)).

Writing: `LeRobotDataset.create(repo_id, fps, features, robot_type=..., use_videos=True)`,
then `add_frame()` per tick, `save_episode()` per episode, and `finalize()` once at the end.
`finalize()` closes the parquet writers and writes their footers; without it the parquet files
are invalid ([lerobot_dataset.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/datasets/lerobot_dataset.py),
[PR #1903](https://github.com/huggingface/lerobot/pull/1903)). `streaming_encoding=True`
encodes frames during capture instead of writing PNGs first; `batch_encoding_size` batches
episodes before encoding. Reading: `LeRobotDataset(repo_id, root=None, episodes=None,
delta_timestamps=None, tolerance_s=1e-4, video_backend=None)`; `delta_timestamps` returns
history and future windows and must be multiples of `1/fps` within `tolerance_s`.
`StreamingLeRobotDataset` iterates from the Hub without a download; `lerobot-train
--dataset.streaming=true` uses it. Downloads land in `$HF_LEROBOT_HOME` (default
`~/.cache/huggingface/lerobot`), calibration files in `$HF_LEROBOT_CALIBRATION`
([constants.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/utils/constants.py)).
v2.1 datasets convert with `python -m lerobot.scripts.convert_dataset_v21_to_v30 --repo-id=...`.
Editing: `lerobot-edit-dataset --operation.type` in `delete_episodes`, `split`, `merge`,
`remove_feature`, `modify_tasks`, `convert_image_to_video`, `reencode_videos`, `info`
([dataset tools](https://huggingface.co/docs/lerobot/using_dataset_tools)).

## Recording and the hardware classes

`lerobot-record` is teleop-only since 0.6.0; policy rollouts moved to `lerobot-rollout`
([lerobot_record.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/scripts/lerobot_record.py)).
`RecordConfig` fields: `robot`, `dataset`, `teleop`, `display_data` (Rerun; `display_mode=foxglove`
serves `ws://127.0.0.1:8765`), `play_sounds`, `resume`. `DatasetRecordConfig`: `repo_id`,
`single_task`, `root`, `fps=30`, `episode_time_s=60`, `reset_time_s=60`, `num_episodes=50`,
`video=True`, `push_to_hub=True`, `private`, `tags`, `num_image_writer_threads_per_camera=4`,
`rgb_encoder.*`, `depth_encoder.*`, `streaming_encoding=False`, `encoder_threads`, `no_stamp`
([configs/dataset.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/configs/dataset.py)).
`repo_id` gets a `_YYYYMMDD_HHMMSS` suffix unless `--dataset.no_stamp=true`. Keys during
recording: right arrow or `n` ends the episode or reset early, left arrow or `r` re-records,
`ESC` or `q` stops and encodes; these work over SSH and Wayland, keyboard *teleop* does not
([il_robots](https://huggingface.co/docs/lerobot/il_robots)). `--resume=true` needs
`--dataset.root` and `num_episodes` then means additional episodes.

Robot `type` names registered in `src/lerobot/robots/`: `so100_follower` and `so101_follower`
(one `SOFollowerRobotConfig`: `port`, `id`, `cameras`, `use_degrees=True`,
`max_relative_target`, `disable_torque_on_disconnect=True`, PID `position_p_coefficient=16`,
`position_d_coefficient=32`), `koch_follower` (Dynamixel, `use_degrees=False`),
`bi_so_follower`, `lekiwi`, `hope_jr`, `omx_follower`, `openarm_follower`, `reachy2`,
`unitree_g1`, `earthrover_mini_plus`, `rebot_b601_follower`. Teleop types: `so100_leader`,
`so101_leader`, `koch_leader`, `bi_so_leader`, `gamepad`, `keyboard`, `phone`, `homunculus`
([robots/](https://github.com/huggingface/lerobot/tree/main/src/lerobot/robots),
[teleoperators/](https://github.com/huggingface/lerobot/tree/main/src/lerobot/teleoperators)).
ALOHA and WidowX are not in-tree any more; use the `lerobot_trossen` plugin
([third-party robots](https://huggingface.co/docs/lerobot/third_party_robots)). Set
`max_relative_target` (degrees per tick, scalar or per joint) on any follower a policy drives;
it is the only software clamp between the model and the servo.

Custom robot: subclass `RobotConfig` with `@RobotConfig.register_subclass("my_arm")`, then
`Robot` with `config_class = MyArmConfig` and the abstract members `observation_features`,
`action_features`, `is_connected`, `connect(calibrate=True)`, `is_calibrated`, `calibrate()`,
`configure()`, `get_observation()`, `send_action(action) -> action_sent`, `disconnect()`
([robot.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/robots/robot.py)).
`Teleoperator` mirrors it with `action_features`, `feedback_features`, `get_action()`,
`send_feedback()` ([teleoperator.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/teleoperators/teleoperator.py)).
Ship it as a package named `lerobot_robot_<x>` or `lerobot_teleoperator_<x>` with the
`XConfig` / `X` naming pair exported from `__init__.py` and the CLIs discover it without
touching lerobot ([bring your own hardware](https://huggingface.co/docs/lerobot/integrate_hardware)).
A ROS 2 arm becomes a `Robot` whose `send_action` publishes to a JTC or forward controller;
the rate and safety concerns are in [connecting-to-real-robots](../topics/connecting-to-real-robots.md).

## Policies and training

Registered `--policy.type` values on main
([policies/](https://github.com/huggingface/lerobot/tree/main/src/lerobot/policies)):
`act`, `diffusion`, `tdmpc`, `vqbet`, `pi0`, `pi0_fast`, `pi05`, `smolvla`, `groot` (N1.7),
`xvla`, `wall_x`, `eo1`, `evo1`, `molmoact2_adamw` / `molmoact2_cosine_with_warmup`,
`multi_task_dit`, `fastwam`, `vla_jepa`, `lingbot_va`, `gaussian_actor` (RL actor, was `sac`).
`rtc` is not a policy but the real-time-chunking inference wrapper. Fields that decide a run:

| Policy | Defaults worth knowing | Config |
|---|---|---|
| `act` | `chunk_size=100`, `n_action_steps=100`, `n_obs_steps=1`, `vision_backbone=resnet18`, `dim_model=512`, `n_encoder_layers=4`, `n_decoder_layers=1`, `use_vae=True`, `kl_weight=10.0`, `temporal_ensemble_coeff=None`, `optimizer_lr=1e-5` | [configuration_act.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/act/configuration_act.py) |
| `diffusion` | `n_obs_steps=2`, `horizon=64`, `n_action_steps=32`, `noise_scheduler_type=DDPM`, `num_train_timesteps=100`, `num_inference_steps=None` (= train steps), `crop_shape`, `use_separate_rgb_encoder_per_camera=True`, `optimizer_lr=1e-4`, `gradient_checkpointing` | [configuration_diffusion.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/diffusion/configuration_diffusion.py) |
| `pi0`, `pi05` | `paligemma_variant=gemma_2b`, `action_expert_variant=gemma_300m`, `chunk_size=50`, `n_action_steps=50`, `max_state_dim=32`, `max_action_dim=32`, `num_inference_steps=10`, `dtype=float32`, `freeze_vision_encoder`, `train_expert_only`, `use_relative_actions`, `rtc_config`; π0.5 adds `use_visual_memory`, `memory_frames=6`, `tokenizer_max_length=200` | [pi0](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/pi0/configuration_pi0.py), [pi05](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/pi05/configuration_pi05.py) |
| `smolvla` | `vlm_model_name=HuggingFaceTB/SmolVLM2-500M-Video-Instruct`, `chunk_size=50`, `num_vlm_layers=16`, `expert_width_multiplier=0.75`, `freeze_vision_encoder=True`, `train_expert_only=True`, `load_vlm_weights=False` (set True when starting from `lerobot/smolvla_base`), `resize_imgs_with_padding=(512, 512)` | [configuration_smolvla.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/smolvla/configuration_smolvla.py) |
| `groot` | base `nvidia/GR00T-N1.7-3B`, `chunk_size=40`, `embodiment_tag=new_embodiment`, `tune_llm=False`, `tune_visual=False`, `tune_projector=True`, `tune_diffusion_model=True`, `lora_rank=0`, `video_backend=decord` (x86 only) | [configuration_groot.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/groot/configuration_groot.py) |

`lerobot-train` takes `TrainPipelineConfig`: `--dataset.repo_id`, `--policy.type` or
`--policy.path`, `--output_dir`, `--job_name`, `--steps=100000`, `--batch_size=8`,
`--num_workers=4`, `--seed=1000`, `--save_freq=20000`, `--log_freq=200`, `--env_eval_freq=20000`
(only with `--env.type`), `--eval_steps`, `--tolerance_s=1e-4`, `--use_policy_training_preset=True`
(per-policy optimizer and scheduler), `--ema.enable`, `--peft.method_type=LORA --peft.r=16`,
`--wandb.enable`, `--policy.repo_id` (push at end), `--save_checkpoint_to_hub`,
`--job.target=a10g-small` (HF Jobs), `--resume=true --config_path=<train_config.json or hub id>`
([configs/train.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/configs/train.py),
[configs/default.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/configs/default.py)).
Checkpoints are `outputs/train/<job>/checkpoints/<step>/pretrained_model/{config.json,
model.safetensors, train_config.json}` plus the pre/post processor pipelines that carry the
normalization stats ([backward compatibility](https://huggingface.co/docs/lerobot/backwardcomp)).

## Evaluation

Sim: `lerobot-eval --policy.path=<ckpt> --env.type=pusht --eval.n_episodes=10
--eval.batch_size=10` with `--env.type` in `aloha` (gym-aloha, `AlohaInsertion-v0`), `pusht`,
`libero`, `libero_plus`, `metaworld`, `robocasa`, `robotwin`, `robomme`, `vlabench`,
`isaaclab_arena`; each needs its extra ([lerobot_eval.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/scripts/lerobot_eval.py),
[envs/configs.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/envs/configs.py)).
Report success over `n_episodes` as [policy-evaluation](../topics/policy-evaluation.md) asks.

Robot: `lerobot-rollout --policy.path=... --robot.type=... --task="..." --duration=60
--strategy.type=<base|sentry|highlight|dagger|episodic>`; `sentry` records everything and
uploads every `--strategy.upload_every_n_episodes=5`, `episodic` adds reset phases (the old
`eval_` dataset flow), `dagger` takes a leader arm for corrections (`space` pause, `tab`
correct, `enter` upload). `--inference.type=rtc --inference.rtc.execution_horizon=10` enables
real-time chunking for slow VLAs; `--interactive=true` accepts `/start`, `/subtask`, `/stop` on
stdin ([policy deployment](https://huggingface.co/docs/lerobot/inference),
[rollout/configs.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/rollout/configs.py)).

## Async inference and the pickle RCE

`python -m lerobot.async_inference.policy_server --host=127.0.0.1 --port=8080 --fps=30
--inference_latency=0.033 --obs_queue_timeout=2` on the GPU box;
`python -m lerobot.async_inference.robot_client --server_address=HOST:8080 --robot.type=...
--policy_type=act --pretrained_name_or_path=<hub id> --policy_device=cuda
--actions_per_chunk=50 --chunk_size_threshold=0.5 --aggregate_fn_name=weighted_average
--task="..." [--debug_visualize_queue_size=true]` on the robot host
([async_inference/configs.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/async_inference/configs.py),
[async inference](https://huggingface.co/docs/lerobot/async)). The client sends a new
observation when the queue drops below `chunk_size_threshold` of a chunk. `SUPPORTED_POLICIES`
is `act, smolvla, diffusion, tdmpc, vqbet, pi0, pi05, groot`; `SUPPORTED_ROBOTS` is
`so100_follower, so101_follower, bi_so_follower, omx_follower`
([constants.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/async_inference/constants.py)).

CVE-2026-25874 (published 23 Apr 2026): the server deserializes `SendPolicyInstructions` and
`SendObservations` payloads, and the client deserializes `GetActions`, with `pickle.loads()`
over an unauthenticated gRPC channel opened by `add_insecure_port`, so anyone who can reach
the port runs code on the box ([OSV](https://osv.dev/vulnerability/CVE-2026-25874),
[write-up](https://chocapikk.com/posts/2026/lerobot-pickle-rce/)). On 2026-09-05 this is
still unpatched: `policy_server.py` on `main` and at `v0.6.1` has `pickle.loads(...)  # nosec`
at the same two call sites and still calls `add_insecure_port`
([policy_server.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/async_inference/policy_server.py));
the fix PR replacing pickle with safetensors plus JSON has been open since 27 Feb 2026
([PR #3048](https://github.com/huggingface/lerobot/pull/3048)). Treat the policy server as
`localhost` only or run it inside an SSH tunnel or WireGuard; never on a customer LAN.

## Visualization and the Hub

`lerobot-dataset-viz --repo-id <id> --episode-index 0` opens Rerun; `--save 1 --output-dir d`
writes an `.rrd`; `--mode distant --grpc-port 9876` streams to a remote viewer;
`--display-mode foxglove` serves a scrubbable timeline
([lerobot_dataset_viz.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/scripts/lerobot_dataset_viz.py)).
Any pushed dataset renders in the Hub space
[lerobot/visualize_dataset](https://huggingface.co/spaces/lerobot/visualize_dataset).
`push_to_hub()` uploads `data/`, `meta/`, `videos/`, writes a dataset card, and tags the repo
with the codebase version; `LeRobotDataset(repo_id, revision=...)` pins a tag or commit.

## Common failures

- **Timestamps out of sync.** `LeRobotDataset` checks consecutive `timestamp` values against
  `1/fps` within `tolerance_s=1e-4` and raises `FrameTimestampError` when a decoded frame is
  farther than that from the query
  ([video_utils.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/datasets/video_utils.py)).
  A camera that dropped frames during recording produces this at train time, not record time.
  Widen `tolerance_s` only to diagnose; fix the capture. See
  [perception-for-policy-learning](../topics/perception-for-policy-learning.md).
- **torchcodec and ffmpeg mismatch.** torchcodec dlopens a specific ffmpeg major; the docs'
  fallback is `conda install ffmpeg=7.1.1 -c conda-forge`. Pass `--dataset.video_backend=pyav`
  to bypass torchcodec at the cost of speed
  ([installation](https://huggingface.co/docs/lerobot/installation)).
- **Encoder missing.** `libsvtav1` absent from `ffmpeg -encoders` fails recording at save
  time; use `--dataset.rgb_encoder.vcodec=h264` or `auto`.
- **Torch and CUDA pins.** `torch>=2.7,<2.12`, `torchcodec<0.12`, `numpy<2.3`; a PyPI torch
  wheel on a driver below 580.65 fails at import, install torch from the cu128 index first.
  `placo` (kinematics extra) is capped `<0.9.16` because newer wheels need urdfdom 4 that
  Ubuntu 24.04 does not ship ([pyproject.toml](https://github.com/huggingface/lerobot/blob/main/pyproject.toml)).
- **Camera key mismatch at rollout.** The policy's `config.json` lists the
  `observation.images.<key>` names it was trained on; `--robot.cameras` keys must match, or use
  `--rename_map`.
- **Old checkpoints.** Models trained before the normalization migration need
  `python -m lerobot.processor.migrate_policy_normalization`
  ([backward compatibility](https://huggingface.co/docs/lerobot/backwardcomp)).

## Recipe: 50 SO-101 episodes to a live ACT rollout

```bash
export HF_USER=$(NO_COLOR=1 hf auth whoami | awk -F': *' 'NR==1 {print $2}')
lerobot-find-port                                   # once per arm, unplug/replug to identify
lerobot-setup-motors --robot.type=so101_follower --robot.port=/dev/ttyACM0   # first assembly only
lerobot-calibrate --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=f1
lerobot-calibrate --teleop.type=so101_leader  --teleop.port=/dev/ttyACM1 --teleop.id=l1
lerobot-find-cameras opencv                         # note the index or /dev/video path

lerobot-record \
  --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=f1 \
  --robot.cameras="{ front: {type: opencv, index_or_path: /dev/video0, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30}}" \
  --teleop.type=so101_leader --teleop.port=/dev/ttyACM1 --teleop.id=l1 \
  --dataset.repo_id=${HF_USER}/so101_pick_cube --dataset.no_stamp=true \
  --dataset.num_episodes=50 --dataset.single_task="Pick up the red cube and place it in the bin" \
  --dataset.episode_time_s=30 --dataset.reset_time_s=15 \
  --dataset.streaming_encoding=true --dataset.encoder_threads=2 --display_data=true

lerobot-dataset-viz --repo-id ${HF_USER}/so101_pick_cube --episode-index 0   # check sync and framing

lerobot-train \
  --dataset.repo_id=${HF_USER}/so101_pick_cube --policy.type=act \
  --output_dir=outputs/train/act_so101_pick_cube --job_name=act_so101_pick_cube \
  --policy.device=cuda --steps=100000 --batch_size=8 --seed=1000 \
  --wandb.enable=true --policy.repo_id=${HF_USER}/act_so101_pick_cube

lerobot-rollout --strategy.type=episodic \
  --policy.path=outputs/train/act_so101_pick_cube/checkpoints/last/pretrained_model \
  --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=f1 --robot.max_relative_target=10 \
  --robot.cameras="{ front: {type: opencv, index_or_path: /dev/video0, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30}}" \
  --dataset.repo_id=${HF_USER}/eval_act_so101_pick_cube --dataset.num_episodes=20 \
  --dataset.single_task="Pick up the red cube and place it in the bin" --display_data=true
```

Commands and flags from [so101](https://huggingface.co/docs/lerobot/so101),
[il_robots](https://huggingface.co/docs/lerobot/il_robots), [act](https://huggingface.co/docs/lerobot/act)
and the config dataclasses linked above. Write `DATASET.md` and the experiment record before
the train step ([data-collection-protocol](../../sops/data-collection-protocol.md),
[experiment-protocol](../../sops/experiment-protocol.md)). The docs say "a few hours for 100k
training steps on a single GPU" without naming the GPU (unverified for any specific card).
`--robot.max_relative_target=10` is a starting clamp in degrees per tick; size it from the
per-step deltas in your own teleop data (from field, unverified).

## Links

- Docs: https://huggingface.co/docs/lerobot/index
- Repo: https://github.com/huggingface/lerobot
- HIL-SERL port: https://huggingface.co/docs/lerobot/hilserl (see [real-world-rl](../topics/real-world-rl.md))
- Dataset visualizer: https://huggingface.co/spaces/lerobot/visualize_dataset
