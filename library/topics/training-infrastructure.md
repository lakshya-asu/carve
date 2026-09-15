---
title: Training infrastructure for robot policies
date: 2026-09-05
tags: [topic, training, data-loading, video-decoding, distributed-training, experiment-tracking, reproducibility, hydra, ci, cost]
status: draft
source: synthesis
---

# Training infrastructure for robot policies (as of 2026-09)

Verification convention: every number links a source in **Sources** or carries "(unverified)".
Memory figures labelled "arithmetic" bound what fits; they do not replace a measurement.

## What it is

Everything between a recorded dataset and a checkpoint you would deploy: the loader that
decodes video fast enough to keep a GPU busy, the sampler that mixes datasets, the parallelism
that fits a 3B to 7B model into memory, the tracker that tells you which run was which, and the
checks that stop a normalization or timestamp bug from reaching the robot. Robot policy training
differs from vision training in that samples are multi-camera video windows, datasets are small
enough that one bad shard matters, and the metric that counts (hardware success rate) cannot be
computed inside the training loop.

## Why it matters in the field

- **Decode, not the GPU, is the small team's bottleneck.** LeRobot stores camera streams as
  AV1 MP4 (`libsvtav1`, `yuv420p`, keyframe interval `g=2`, `crf=30`, preset 12 by default)
  [LeRobot-video-cfg]: small on disk, expensive to decode on CPU. A fine-tune that should take
  a night takes a week when four DataLoader workers feed an H100.
- **Silent mismatches ship.** Normalization stats live in `meta/stats.json` (LeRobot)
  [LeRobot-v3] or `norm_stats.json` (openpi) [openpi], not in the weights; a checkpoint alone is
  not a deployable artifact, and a stats mismatch moves the arm confidently to the wrong place.
- **Compute has a price you can compute.** OpenVLA pretraining took 64 A100s for 15 days
  [OpenVLA-site]; a π0 full fine-tune needs a >70 GB GPU [openpi]. At the rental prices below, a
  fine-tune is tens of dollars and a pretrain is six figures.
- **Reproducibility is a contract item.** When a customer asks why yesterday's checkpoint behaved
  differently, you need the seed, dataset checksum, git SHA and config, or you have nothing.

## Key methods

### Data loaders for video-heavy datasets

| Stack | Storage | Decode path | Notes |
|---|---|---|---|
| LeRobot v3 (`LeRobotDataset`) | Parquet shards for low-dim data, MP4 shards per camera, `meta/` JSON and Parquet; many episodes per file | `torchcodec` by default, `pyav` fallback on platforms without wheels; frames matched to timestamps with `tolerance_s` (default 1e-4 s) [LeRobot-video], [LeRobot-dataset] | `StreamingLeRobotDataset` streams from the Hub or a bucket (`--dataset.streaming=true`); `finalize()` is mandatory before push; `lerobot-lancedb` offers Lance-backed drop-in subclasses with claimed but unquantified speed-ups [LeRobot-v3] |
| RLDS / TFDS (OXE, Octo, OpenVLA) | TFRecord shards, one `tf.data` dataset per source | `tf.data` pipeline; OpenVLA and Octo use `dlimp` for interleaving and augmentation [OpenVLA-repo] | Pretraining-scale; interleaving by weight is native. Requires renaming BridgeData V2 to `bridge_orig` in OpenVLA's tree [OpenVLA-repo] |
| GR00T (LeRobot-compatible + `modality.json`) | LeRobot layout plus a mapping of concatenated state/action arrays to named fields | `torchcodec` only, FFmpeg 4 to 7; H.264 universally supported, "AV1 decoding is unreliable" [GR00T-repo] | Re-encode AV1 datasets to H.264 before GR00T fine-tuning |
| NVIDIA DALI video reader | Any FFmpeg container it can index | NVDEC on GPU; returns `(N, F, H, W, C)` sequences; `sequence_length`, `stride`, `step`, `random_shuffle` | "Only supports constant frame rate videos" [DALI-video]; frees CPU cores, competes with training for GPU memory |
| torchcodec direct | MP4 | CPU or CUDA (NVDEC); `get_frames_at(indices)`, `get_frames_played_at(seconds)`; FFmpeg 4 to 9 [torchcodec] | The primitive under LeRobot and GR00T; use it when writing a custom dataset |
| decord | MP4 | FFmpeg/LibAV, optional NVDEC (`-DUSE_CUDA=ON`) [decord] | Maintenance status unclear from the repo page (unverified); prefer torchcodec for new code |

**The CPU decode bottleneck and how to size workers.** Random access into a video costs one
keyframe plus every inter frame up to the target. LeRobot's `g=2` default makes that at most two
frames per access, which is why the files are large relative to `g=30` and why decode stays
bounded [LeRobot-video-cfg]. Size workers by measurement, not folklore:

1. Time `dataset[i]` for 200 random indices in one process; the mean is `t_sample` (s), and it
   includes every camera's decode, transforms and tensor conversion.
2. Required throughput `r = batch_size / t_step`, with `t_step` the optimizer step time measured
   on synthetic data.
3. Workers: `ceil(r * t_sample * 1.5)`. If that exceeds the physical cores, in order of cost:
   resize at encode time to the policy's input size, cache decoded windows as uint8 on NVMe, or
   move decode to NVDEC (torchcodec CUDA or DALI).
4. `pin_memory=True`, `persistent_workers=True`, `prefetch_factor` covering one full step. Log
   data-wait per step (from `optimizer.step()` returning to the next batch arriving); above 5% of
   the step you are loader-bound.

Illustrative, not a benchmark: batch 64 at 0.5 s per step is r = 128 samples/s; two AV1 cameras
at 640x480 decoding in 25 ms per sample gives ceil(128 x 0.025 x 1.5) = 5 workers.

**Storage layout and caching.** Hot copy on local NVMe, cold copy on object storage or the Hub, and a `DATASET.md` carrying the
Hub revision or the SHA-256 of `meta/info.json` and every shard (`CLAUDE.md`). Streaming
[LeRobot-v3] is for exploration and evaluation, not for a fine-tune you need to reproduce. Keep
one directory per format version: the v2.1 to v3 converter rewrites file names and metadata
[LeRobot-v3], and mixing both under one path is how a loader silently picks the wrong one.
Decoded caches are derived artifacts, named by dataset checksum plus transform parameters and
deleted when either changes. Measure `t_sample` on any network filesystem before training from
it; NFS metadata latency on Parquet shards can double loader time (from field, unverified).

### Mixed datasets and sampling weights

Open X-Embodiment mixes are weighted per source dataset by hand, not by size. Octo's
`OXE_MAGIC_SOUP` (25 entries) uses `fractal20220817_data` 0.541, `kuka` 0.834, `bridge_dataset`
1.0, `taco_play` 2.0, `language_table` 0.1, `nyu_franka_play` 3.0, `furniture_bench` 0.1, `bc_z`
0.2, among others [Octo-mixes]; OpenVLA's `oxe_magic_soup_plus` adds `droid` at 0.06 and `dobbe`
at 0.2 [OpenVLA-mixes]. The largest sources are down-weighted (RT-1, Kuka, DROID) and small clean
ones up-weighted (NYU Franka play at 3.0). Weights are relative sampling rates, so the effective
mix depends on sizes too. For a customer mix (their 200 episodes plus a public slice for language
retention), start the customer data at 1.0 and the slice at 0.1 to 0.3, measure language
following on held-out prompts before moving the dial, and log realized per-dataset counts each
epoch, since configured weight and realized fraction diverge when episode lengths differ.

### Distributed training: what fits where

Mixed-precision AdamW costs 2 (bf16 weights) + 2 (bf16 grads) + 4 (fp32 master) + 8 (fp32 Adam
m and v) = 16 bytes per parameter, plus activations scaling with batch, sequence and image count.

| Model size | States (arithmetic) | One 80 GB GPU | Evidence |
|---|---|---|---|
| 3B (π0 3.3B, GR00T N1.x, SmolVLA scale) | ~48 GB | Full fine-tune fits with gradient checkpointing and a modest batch | openpi: full fine-tune ">70 GB", LoRA ">22.5 GB", inference ">8 GB" [openpi]; GR00T: "40 GB+ VRAM recommended", H100 or L40 [GR00T-repo] |
| 7B (OpenVLA) | ~112 GB | Full fine-tune does not fit; LoRA does | OpenVLA LoRA: "~72 GB" at batch 16 on one A100 80 GB, "~27 GB" minimum with smaller batch; full fine-tune "a full node of 8 A100 GPUs" with FSDP [OpenVLA-repo] |

- **DDP** replicates the model per GPU and all-reduces gradients: simplest and fastest per step
  when the 3B model fits one GPU. `torchrun --nproc_per_node=8` is the launcher GR00T documents
  [GR00T-repo] and OpenVLA uses for single-node runs [OpenVLA-repo].
- **FSDP** shards parameters, gradients and optimizer states (ZeRO-3 style): `FULL_SHARD`,
  `SHARD_GRAD_OP` (grads and optimizer only), `HYBRID_SHARD` (shard within a node, replicate
  across nodes), `NO_SHARD` (DDP-equivalent); mixed precision sets param, reduce and buffer
  dtypes separately; `CPUOffload` moves parameters and the optimizer step to CPU [FSDP]. openpi
  exposes it as `--fsdp-devices`, trading memory per GPU for speed [openpi]. Use it for 7B full
  fine-tunes and for 3B runs where batch size matters more than step time.
- **Gradient checkpointing** recomputes activations in backward, costing roughly one extra
  forward per step by construction; it turns "3B does not fit at batch 32" into "fits".
- **bf16** for weights and activations on Ampere or newer, fp32 master copy and fp32 loss; fp16
  needs loss scaling and buys nothing on H100. **LoRA first**: it fits 7B on one 24 to 80 GB GPU
  and keeps the base checkpoint immutable; go full fine-tune only when LoRA measurably
  underperforms on your evaluation (see the VLA entry's recipe).

### Experiment tracking and what to log

| Tool | Cost and hosting | Fit |
|---|---|---|
| Weights & Biases | Free: 5 GB storage, up to 5 model seats; Pro from $60/month, up to 10 seats; storage overage $0.03/GB [W&B-pricing] | Hosted dashboards, media logging (rollout videos), sweeps. Data leaves the site; check customer policy |
| MLflow | Open source; file or SQL backend (SQLite, PostgreSQL, MySQL), artifacts on local disk, S3 or Azure Blob; standalone tracking server [MLflow] | On-prem tracking when data cannot leave the customer network |
| Plain CSV + Git | Free | One `metrics.csv` per run in the run directory, committed config; enough for a two-week pilot, not for a sweep |

What to log for a policy, regardless of tool:
- Training and validation action loss, as smoke alarms only: action MSE on held-out demos does
  not predict success rate (`library/topics/policy-evaluation.md`); a policy that averages
  between modes has low MSE and fails.
- **Rollouts.** Sim evaluation every N steps with success rate, trial count and videos
  (LeRobot's trainer exposes `eval_freq`, default unverified). Without a simulator, log open-loop
  predicted-vs-recorded action plots for five fixed episodes at every checkpoint.
- Normalization stats hash, dataset checksum, mixture weights and realized per-dataset counts,
  every named seed, git SHA, config diff against the base, learning-rate schedule, gradient
  norm, data-wait time per step, samples per second, GPU memory high-water mark.

**Checkpoints and evaluation cadence.** Name checkpoints `<model>-<dataset>-<git-sha>-<step>.pt`, never overwrite, and store stats,
config and processor next to the weights (`CLAUDE.md`). Save every K steps for 10 to 20
checkpoints per run, sim-evaluate at every save, and hardware-evaluate 3 to 5 chosen checkpoints
rather than "the last one": best validation loss and best success rate are routinely different
checkpoints (from field, unverified). Record the base checkpoint hash.

**Reproducibility.** PyTorch's guidance: `torch.manual_seed`, `random.seed`, `np.random.seed`;
`torch.use_deterministic_algorithms(True)`; `torch.backends.cudnn.benchmark = False`; a
DataLoader `worker_init_fn` deriving NumPy and Python seeds from `torch.initial_seed()` plus a
seeded `torch.Generator`. The same page says results are not guaranteed across PyTorch releases,
commits, platforms, or between CPU and GPU [PyTorch-repro]. Deterministic cuBLAS also needs
`CUBLAS_WORKSPACE_CONFIG` (`:4096:8` or `:16:8`); PyTorch raises an error naming it when missing
(unverified against the current docs page).

Run with determinism on for the smoke test that pins a run, then off for speed, and quantify
run-to-run noise with three seeds. Pin the dataset by checksum and Hub revision, the container by
image digest, and the config by file.

### Cost, configs and CI (prices as fetched, September 2026)

| Resource | Price | Source and date |
|---|---|---|
| AWS p5.48xlarge (8x H100), Capacity Block, us-east-1 | $41.528/h ($5.191 per GPU-hour) | [AWS-CB], page notes a price update scheduled October 2026 |
| Lambda H100 SXM, 8x node | $3.99 per GPU-hour ($31.92/h node); 1x H100 $4.29/h; B200 $6.69 per GPU-hour | [Lambda], no "as of" date on page |
| RunPod H100 SXM 80 GB; A100 80 GB | $2.69/h community, $3.29/h secure; $1.19/h PCIe community to $1.59/h SXM secure | [RunPod], page dated 2026-07-27 |
| RunPod RTX 4090 24 GB; RTX PRO 6000 96 GB | $0.34/h community, $0.74/h secure; $1.69/h community, $2.09/h secure | [RunPod] |

Worked numbers: a π0 LoRA fine-tune on a 4090-class GPU (>22.5 GB [openpi]) for 8 hours is
$3 to $6 rented. An OpenVLA-OFT-style 7B full fine-tune, 8x A100 for 2 days [OFT-in-VLA-entry],
is 8 x 48 h x $1.59 = ~$610 on RunPod secure. OpenVLA pretraining, 64 A100 x 15 days
[OpenVLA-site], is 23,040 GPU-hours: ~$37k at $1.59, ~$120k at the AWS H100 capacity-block rate,
and not a fine-tuning budget. On-prem: a workstation with a 96 GB RTX PRO 6000 at roughly $10k
(unverified) against $2.09/h rented breaks even near 4,800 GPU-hours, about 200 days of
continuous use, before power, cooling and the person who maintains it. Buy when the box also
serves deployment or data collection; rent for bursts.

**Config patterns.** Hydra 1.3 (1.4 pre-release) gives config groups, `defaults` composition, command-line
overrides, `--multirun` sweeps, OmegaConf structured configs and a timestamped output directory
per run [Hydra]; its costs are the working-directory change and the untyped YAML surface. The
robot stacks have converged on dataclass configs: openpi defines `TrainConfig` and data configs
as dataclasses with named presets such as `pi05_libero` [openpi], and LeRobot moved from Hydra
to `draccus` dataclass parsing in early 2025 (unverified PR). Typed configs fail at parse time
instead of at step 10,000. Either way `CLAUDE.md` applies: no magic constants, every random
source seeded from config, resolved config saved next to the checkpoint, and never both parsers
in one repo.

**CI for training code.** CPU unit tests under two minutes: dataset indexing on a 3-episode fixture, normalization
round-trip (`denorm(norm(x)) == x` within tolerance), timestamp alignment, preprocessing shape
and dtype, config parsing for every preset. A nightly `@pytest.mark.gpu` smoke test: 20
optimizer steps on the fixture, loss decreases, checkpoint reloads and emits an action of the
right shape and dtype; plus a determinism test that two seeded 10-step runs match. `ruff format
--check`, `ruff check`, `mypy --strict` on `src/` (`CLAUDE.md`). Checksum verification belongs
in the launcher, not CI.

## Practical recipe: a reference training repo layout

```
policy-train/
  pyproject.toml            # ruff, mypy, pytest config; pinned torch/torchcodec/lerobot
  DATASET.md                # per dataset: source, robot, date, operator, episodes, checksum, issues
  configs/
    base.py                 # dataclasses: DataConfig, ModelConfig, OptimConfig, TrainConfig
    presets/                # named presets: pi05_customer_a.py, smolvla_so101.py
  src/policy_train/
    data/
      dataset.py            # LeRobotDataset wrapper: delta_timestamps, transforms, checksum check
      mixture.py            # weighted interleave; logs realized per-dataset counts
      normalize.py          # stats load/save, norm/denorm with explicit mode (minmax | meanstd | quantile)
      preprocess.py         # resize/crop/pad; the same function the deploy stack imports
    models/                 # thin adapters over openpi / lerobot / gr00t policies
    train.py                # loop; DDP/FSDP switch; grad checkpointing; bf16; logging hooks
    evaluate.py             # sim rollouts + open-loop plots at each checkpoint
    tracking.py, seeding.py # W&B/MLflow/CSV behind one interface; seed_all(cfg) logs every seed
  scripts/
    compute_norm_stats.py
    verify_dataset.py       # checksums + timestamp tolerance scan
    launch.sh               # torchrun wrapper; writes run id, git sha, config to run dir
  tests/
    fixtures/tiny_dataset/  # 3 episodes, 2 cameras, 30 frames each, LeRobot v3 layout
    test_dataset.py test_normalize.py test_preprocess.py test_config.py
    test_train_smoke.py     # @pytest.mark.gpu
  runs/                     # gitignored: <run_id>/{config.json, metrics.csv, ckpt/, rollouts/}
```

The non-negotiable lines are `preprocess.py`, which the deploy stack imports so train and
inference cannot disagree on resize, crop or channel order, and `normalize.py`, whose stats file
carries an explicit mode field.

Steps for a new fine-tune:

1. `verify_dataset.py`: checksums match `DATASET.md`, every episode passes the `tolerance_s`
   scan, camera names and fps match the preset. Then `compute_norm_stats.py` on that exact
   revision and commit the stats hash into the run.
2. Measure `t_sample` and `t_step`, set workers, confirm data-wait under 5% in the first 100 steps.
3. Train 50 steps with determinism flags, save, reload, compare losses; then switch flags off.
4. Save every K steps, sim-evaluate at each save, pick 3 checkpoints for hardware evaluation
   under the written protocol (`sops/experiment-protocol.md`).
5. Package the deploy bundle: weights, stats, resolved config, preprocess version, git SHA.

## Practical gotchas

- **Normalization mismatch between train and deploy.** Stats are a separate file in LeRobot
  (`meta/stats.json`) [LeRobot-v3] and openpi (`norm_stats.json`, quantiles and std) [openpi].
  Rolling back a model without its stats is a documented failure in
  `library/topics/deployment-engineering.md`; the imitation-learning entry records LeRobot's
  Diffusion Policy min-max clipping as a related trap. Hash the stats into the checkpoint
  directory and refuse to load a policy whose hash differs.
- **Timestamp misalignment.** LeRobot checks at init that consecutive timestamps are 1/fps apart
  within `tolerance_s` (1e-4 s default), that `delta_timestamps` are multiples of 1/fps, and that
  decoded video frames land within the tolerance of the requested time [LeRobot-dataset],
  [LeRobot-video]. A drifting camera clock passes recording and fails here; a dataset that only
  loads after loosening the tolerance has an action-observation offset you will train in.
- **Image resize and crop mismatch.** Training resizes in the loader, deployment in the client
  (openpi recommends client-side resize; see the deployment entry). Pad vs stretch,
  interpolation and channel order differ by default between OpenCV, PIL and torchvision. One
  shared function, one test with a known image.
- **AV1 on the wrong stack, `finalize()` forgotten.** LeRobot encodes AV1 by default
  [LeRobot-video-cfg]; GR00T calls AV1 decoding unreliable and pins FFmpeg 4 to 7 [GR00T-repo],
  so re-encode to H.264 for GR00T. Parquet files written without `finalize()` lack footers and
  load as corrupt [LeRobot-v3]; the symptom is a loader error on a dataset that "recorded fine".
- **Loader-bound runs misread as model problems.** Low GPU utilization is a decode problem
  until the data-wait metric says otherwise; `use_deterministic_algorithms(True)` left on is a
  pin the run no longer needs [PyTorch-repro].

## What a forward-deployed engineer must be able to do

1. Size DataLoader workers from measured `t_sample` and `t_step` and show data-wait under 5%
   on the customer's machine before the first long run.
2. Build a weighted mixture of customer data and a public slice, log realized counts, and report
   its effect on language following with trial counts.
3. Choose DDP, FSDP or LoRA for a model and GPU from the memory arithmetic and confirm it with
   the high-water mark.
4. Produce a deploy bundle (weights, stats, config, preprocess version, SHA) that the inference
   node loads with a hash check, and demonstrate the refusal path.
5. Reproduce a run from its record to identical first-50-step losses with determinism on, and
   put a dated, sourced cost estimate in front of a customer.

## Open questions to learn hands-on

- Real `t_sample` for AV1 `g=2` versus H.264 `g=30` on our datasets, CPU vs NVDEC, at 224 and
  native resolution; and whether `StreamingLeRobotDataset` from a local bucket is fast enough to
  skip the NVMe copy at customer sites.
- FSDP `HYBRID_SHARD` vs DDP for a 3B model on 2 to 4 GPUs: step time and memory, measured.
- Run-to-run variance across three seeds in hardware success rate at 20 trials, which sets the
  minimum effect size we can claim.
- Whether Lance-backed `LeRobotLanceVideoDataset` beats plain v3 on random access with our
  camera count, and what GPU smoke test fits the lab's 4 GB GTX 1050 Ti in five minutes.

## Related entries

- `library/topics/vision-language-action-models.md` (fine-tuning recipe, VRAM lines per model)
- `library/topics/teleoperation-and-data-collection.md` (LeRobot v3 and RLDS formats, DATASET.md)
- `library/topics/imitation-learning.md` (normalization clipping trap, ACT and DP baselines)
- `library/topics/policy-evaluation.md` (why action MSE is not success, trial counts)
- `library/topics/deployment-engineering.md` (rollback with stats, client-side resize, serving)
- `library/tools/lerobot.md`, `templates/python-package/`, `sops/experiment-protocol.md`

## Sources

- [LeRobot-v3] LeRobotDataset v3.0 docs: https://huggingface.co/docs/lerobot/lerobot-dataset-v3
- [LeRobot-dataset] `lerobot_dataset.py` (`tolerance_s` default and docstring): https://github.com/huggingface/lerobot/blob/main/src/lerobot/datasets/lerobot_dataset.py
- [LeRobot-video] `video_utils.py` (torchcodec default, pyav fallback, timestamp matching): https://github.com/huggingface/lerobot/blob/main/src/lerobot/datasets/video_utils.py
- [LeRobot-video-cfg] `configs/video.py` (`libsvtav1`, `yuv420p`, `g=2`, `crf=30`, preset 12): https://github.com/huggingface/lerobot/blob/main/src/lerobot/configs/video.py
- [GR00T-repo] Isaac-GR00T README (40 GB+ VRAM, torchrun, `modality.json`, torchcodec and FFmpeg 4 to 7, AV1 note): https://github.com/NVIDIA/Isaac-GR00T
- [torchcodec] https://github.com/pytorch/torchcodec ; docs https://docs.pytorch.org/torchcodec/stable/
- [DALI-video] `nvidia.dali.fn.readers.video`: https://docs.nvidia.com/deeplearning/dali/user-guide/docs/operations/nvidia.dali.fn.readers.video.html
- [decord] https://github.com/dmlc/decord
- [Octo-mixes] `octo/data/oxe/oxe_dataset_mixes.py`: https://github.com/octo-models/octo/blob/main/octo/data/oxe/oxe_dataset_mixes.py
- [OpenVLA-mixes] `prismatic/vla/datasets/rlds/oxe/mixtures.py`: https://github.com/openvla/openvla/blob/main/prismatic/vla/datasets/rlds/oxe/mixtures.py
- [OpenVLA-repo] OpenVLA README (LoRA memory, FSDP node, dlimp, `bridge_orig`): https://github.com/openvla/openvla
- [OpenVLA-site] OpenVLA project page (64 A100 GPUs for 15 days; LoRA 1.4% of parameters): https://openvla.github.io/
- [OFT-in-VLA-entry] OpenVLA-OFT compute (8x A100/H100, 1 to 2 days) as cited in `library/topics/vision-language-action-models.md`: https://arxiv.org/abs/2502.19645
- [openpi] openpi README (memory table, `compute_norm_stats.py`, dataclass configs, `--fsdp-devices`): https://github.com/Physical-Intelligence/openpi
- [FSDP] PyTorch FSDP docs (sharding strategies, mixed precision, CPU offload): https://docs.pytorch.org/docs/stable/fsdp.html
- [PyTorch-repro] PyTorch reproducibility notes: https://docs.pytorch.org/docs/stable/notes/randomness.html
- [Hydra] Hydra docs: https://hydra.cc/docs/intro/
- [MLflow] MLflow Tracking docs: https://mlflow.org/docs/latest/ml/tracking/
- [W&B-pricing] Weights & Biases pricing: https://wandb.ai/site/pricing
- [AWS-CB] EC2 Capacity Blocks pricing: https://aws.amazon.com/ec2/capacityblocks/pricing/
- [Lambda] Lambda GPU cloud pricing: https://lambda.ai/service/gpu-cloud
- [RunPod] RunPod pricing (page dated 2026-07-27): https://www.runpod.io/pricing
