---
title: Compute (Jetson edge modules, field laptops, training GPUs, real-time and I/O budgets)
date: 2026-09-05
tags: [hardware, compute, jetson, gpu, real-time, ros2, networking, storage]
status: draft
source: vendor documentation (links inline)
---

# compute

Specs quoted from vendor pages fetched on 2026-09-05 unless a line says otherwise; anything not
verifiable is marked "(unverified)". Prices are dated and will drift. Policy memory figures
cross-reference `library/topics/vision-language-action-models.md` (the "VLA note"). The
driver-mismatch procedure at the end is untested on the laptop it describes.

## What it is

Four compute roles appear in every deployment: the on-robot module that runs the policy (Jetson or
an x86 box with a discrete GPU), the field laptop for driving, recording, and debugging, the training
machine (workstation or cloud), and the real-time control PC that closes the joint loop. Their
constraints differ (memory, watts, jitter, I/O) and one part rarely does two jobs well.

## Why it matters in the field

Memory decides where a policy can live: pi0 needs 14 GB at inference, SmolVLA about 2 GB
([LeRobot async docs](https://huggingface.co/docs/lerobot/en/async)), so a 16 GB Orin NX and a
64 GB AGX Orin are different products for a VLA team. Watts decide whether the module rides on the
robot's battery, jitter whether a 1 kHz torque loop is safe, USB and NVMe budgets whether a
three-camera rig records without drops. The current laptop (GTX 1050 Ti, 4 GB, Pascal) runs SmolVLA
and nothing 7B-class; its driver stack is on the last branch that supports the card (see gotchas).

## Edge compute table

Every Jetson shares one DRAM pool between CPU and GPU: "both the CPU (Host) and the iGPU share SoC
DRAM memory" ([CUDA for Tegra](https://docs.nvidia.com/cuda/cuda-for-tegra-appnote/index.html)).
OS, ROS 2, camera buffers, and the model all come out of the same number.

| Module | Memory | AI perf (precision as quoted) | GPU / CPU | Power | Source |
|---|---|---|---|---|---|
| Orin Nano 8GB (Super dev kit) | 8 GB LPDDR5, 102 GB/s | 67 TOPS sparse INT8 | Ampere 1024 CUDA / 6x A78AE 1.7 GHz | 7-25 W | [dev kit](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/) |
| Orin NX 16GB (8GB variant: 117 TOPS) | 16 GB LPDDR5, 102.4 GB/s | 157 TOPS sparse INT8 (GPU 77 sparse / 38 dense + DLA) | Ampere 1792 CUDA / 8x A78AE 2.0 GHz | 10-40 W | [Orin family](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/) |
| AGX Orin 32GB | 32 GB LPDDR5, 204.8 GB/s | 248 TOPS sparse INT8 | Ampere 2048 CUDA / 12x A78AE 2.2 GHz | 15-60 W | same |
| AGX Orin 64GB | 64 GB LPDDR5, 204.8 GB/s | 275 TOPS sparse INT8 (GPU 170 sparse / 85 dense + DLA 105 / 52.5) | same | 15-60 W | same |
| Jetson T5000 (AGX Thor dev kit, $3,499) | 128 GB LPDDR5X, 273 GB/s | 2070 TFLOPS sparse FP4; 1035 dense FP4 = sparse FP8 = sparse INT8; 517 dense FP8 = sparse FP16 | Blackwell 2560 CUDA, MIG / 14x Neoverse-V3AE 2.6 GHz | 40-130 W | [Thor](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-thor/), [Thor blog](https://developer.nvidia.com/blog/introducing-nvidia-jetson-thor-the-ultimate-platform-for-physical-ai/) |
| Jetson T4000 | 64 GB LPDDR5X, 273 GB/s | 1200 TFLOPS sparse FP4; 600 dense FP4 / sparse INT8 | Blackwell 1536 CUDA / 12x Neoverse-V3AE | 40-70 W | same |

Read TOPS with the precision attached: Orin is quoted sparse INT8 including the DLA engines, Thor
sparse FP4. On one basis (dense INT8, GPU only) AGX Orin 64GB is 85 TOPS and Thor about 517, roughly
6x, not the 7.5x in the [launch release](https://nvidianews.nvidia.com/news/nvidia-blackwell-powered-jetson-thor-now-available-accelerating-the-age-of-general-robotics).
"Super" Nano/NX figures need the MAXN SUPER mode from [JetPack 6.2](https://developer.nvidia.com/embedded/jetpack-sdk-62); Orin dev kit prices (unverified).

| JetPack | L4T | Ubuntu / kernel | CUDA | TensorRT | cuDNN | Modules | Native ROS 2 |
|---|---|---|---|---|---|---|---|
| [6.0](https://developer.nvidia.com/embedded/jetpack-sdk-60) | 36.3 | 22.04 / 5.15 | 12.2 | 8.6 | 8.9 | Orin | Humble |
| [6.1](https://developer.nvidia.com/embedded/jetpack-sdk-61) | 36.4 | 22.04 / 5.15 | 12.6 | 10.3 | 9.3 | Orin | Humble |
| [6.2 / 6.2.1](https://developer.nvidia.com/embedded/jetpack-sdk-621) | 36.4.3 / 36.4.4 | 22.04 / 5.15 | 12.6 | 10.3 | 9.3 | Orin, adds Super modes | Humble |
| [7.0](https://developer.nvidia.com/embedded/jetpack/downloads/archive-7.0) | 38.2 | 24.04 / 6.8 | 13.0 | 10.13 | 9.12 | Thor T5000 only | Jazzy |
| [7.1](https://developer.nvidia.com/embedded/jetpack/downloads/archive-7.1) | 38.4 | 24.04 / 6.8 | 13.0 | 10.13 | 9.12 | Thor T5000, T4000 | Jazzy |
| [7.2 / 7.2.1](https://developer.nvidia.com/embedded/jetpack/downloads/archive-7.2) | 39.2 | 24.04 / 6.8 | 13.2 | 10.16 | 9.20 | Thor + Orin family | Jazzy |

JetPack 6 does not boot Thor; 7.0 and 7.1 do not boot Orin; 7.2 (2026-06) covers both but has no
SD-card image for the Nano dev kit ([forum announcement](https://forums.developer.nvidia.com/t/jetpack-7-2-jetson-software-goes-agentic-with-jetson-linux-39-2/372056)).
[Humble](https://www.openrobotics.org/blog/2022/5/23/ros-2-humble-hawksbill-released) is supported
to May 2027, [Jazzy](https://www.openrobotics.org/blog/2024/5/ros-jazzy-jalisco-released) to May 2029.
Isaac ROS [3.2](https://nvidia-isaac-ros.github.io/v/release-3.2/getting_started/index.html) targets
JetPack 6.1 and Humble; [4.0](https://nvidia-isaac-ros.github.io/v/release-4.0/getting_started/index.html)
through 4.5 were Thor-only on Jazzy; [4.6](https://nvidia-isaac-ros.github.io/getting_started/index.html)
(2026-08) adds Orin on JetPack 7.2. For this team's Humble code, JetPack 6.2.1 plus Isaac ROS 3.2
is the safe pairing.

**What runs where.** bf16 weights cost 2 bytes per parameter and a first-order inference total is
1.2x the weights ([EleutherAI Transformer Math](https://blog.eleuther.ai/transformer-math/)): 7B =
14 GB weights, about 17 GB resident; 3B = 6 GB, about 7 GB.

| Board | Fits | Measured or vendor throughput |
|---|---|---|
| Orin Nano 8GB | SmolVLA (~2 GB), ACT, Diffusion Policy (footprint unverified) | Llama 3.1 8B INT4 19 tok/s on Nano Super ([Jetson AI Lab](https://www.jetson-ai-lab.com/archive/benchmarks.html)); no published VLA rate (unverified) |
| Orin NX 16GB | SmolVLA; GR00T N1.5 at 3B bf16 on paper (unverified on NX); pi0 at 14 GB leaves under 2 GB for everything else, so INT8 or smaller | (unverified) |
| AGX Orin 64GB | pi0 / pi0.5, GR00T N1.x, OpenVLA 7B | GR00T N1.5 15.2 tok/s and N1 18.5 tok/s, TensorRT MAXN, precision not stated ([Thor blog table 3](https://developer.nvidia.com/blog/introducing-nvidia-jetson-thor-the-ultimate-platform-for-physical-ai/)); pi0.5 naive PyTorch 1.42 s/step, 6.1 Hz optimized, board variant not stated ([Jetson-PI, arXiv 2607.12659](https://arxiv.org/html/2607.12659)); OpenVLA 7B INT4 about 3 FPS ([LiteVLA-Edge, arXiv 2603.03380](https://arxiv.org/html/2603.03380v1), abstract only, unverified) |
| AGX Thor (T5000) | all of the above with headroom; 70B LLM INT4 | pi0.5 (LIBERO, horizon 10) 132 ms bf16 PyTorch, 54 ms TensorRT FP8, 48.8 ms FP8+NVFP4 (about 20 Hz), JetPack 7.2 MAXN ([openpi on Thor](https://www.jetson-ai-lab.com/tutorials/openpi_on_thor/)); GR00T N1.5 41.5 tok/s (Thor blog); community pi0.5 44 ms, GR00T N1.6 41-45 ms (unverified) |

Plan around 20 Hz for pi0-class models on Thor after TensorRT work, 7-8 Hz in plain PyTorch, and
1-6 Hz on AGX Orin unless the TensorRT export exists.

## Laptop and workstation guidance

VRAM is the spec. Laptop memory and TGP ranges (Dynamic Boost excluded; OEMs advertise up to 175 W)
from the [GeForce laptop comparison](https://www.nvidia.com/en-us/geforce/laptops/compare/):

| Laptop GPU | VRAM | TGP | Holds 7B bf16 (14 GB + activations)? |
|---|---|---|---|
| RTX 5090 Laptop | 24 GB GDDR7, 896 GB/s | 95-150 W | yes, about 7 GB spare |
| RTX 5080 Laptop / 4090 Laptop | 16 GB | 80-150 W | no in bf16; yes at 8-bit (7 GB) |
| RTX 5070 Ti Laptop / 4080 Laptop | 12 GB | 60-150 W | 4-bit only (3.5 GB weights) |
| RTX 5070 / 5060 / 4070 / 4060 Laptop | 8 GB | 35-115 W | 4-bit only; SmolVLA and ACT fine |
| RTX PRO 5000 Blackwell Laptop | 24 GB GDDR7 ECC ([ADLINK MXM spec](https://www.adlinktech.com/products/embedded_graphics/graphics_solutions/egx-mxm-bw5000?lang=en); nvidia.com page 404) | 95-175 W (unverified) | yes |
| RTX 5000 Ada Laptop | 16 GB GDDR6 ECC ([ADLINK](https://shop.adlinktech.com/products/egx-mxm-ad5000)) | 115 W module | no in bf16 |
| GTX 1050 Ti (current laptop) | 4 GB GDDR5 ([videocardz](https://videocardz.com/nvidia/geforce-10/geforce-gtx-1050-ti); nvidia page gone) | 75 W | SmolVLA only |

The arithmetic: 7 x 10^9 params x 2 bytes = 14 GB. EleutherAI's 1.2x heuristic for activations and
KV cache gives about 17 GB, and OpenVLA-OFT with three cameras and FiLM reports about 18 GB in bf16
(VLA note). A 16 GB card cannot hold a 7B VLA in bf16 before counting the CUDA context and the
desktop compositor. 8-bit halves the weights to 7 GB, 4-bit to 3.5 GB, with the usual accuracy checks.

**Pascal end of life.** The 580 branch is "the last to support GPUs based on the Maxwell, Pascal,
and Volta architectures" ([NVIDIA deprecation schedule](https://forums.developer.nvidia.com/t/unix-graphics-feature-deprecation-schedule/60588));
CUDA 13.0 removed offline compilation for them while 12.x toolkits keep working ([CUDA 13.0 notes](https://docs.nvidia.com/cuda/archive/13.0.1/cuda-toolkit-release-notes/index.html)).
PyTorch dropped Pascal from cu128/cu129 wheels in 2.8 ([dev-discuss](https://dev-discuss.pytorch.org/t/cuda-toolkit-version-and-architecture-support-update-maxwell-and-pascal-architecture-support-removed-in-cuda-12-8-and-12-9-builds/3128))
and 2.14 is the last release with any cu126 wheel ([notice, 2026-09-04](https://dev-discuss.pytorch.org/t/notice-cuda-12-6-wheels-will-no-longer-be-published-from-pytorch-2-15-drops-maxwell-pascal-volta/3432)).
On the 1050 Ti: `pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cu126` and
the proprietary `nvidia-driver-580` (the `-open` flavour is Turing+, [driver guide](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/kernel-modules.html)).
Treat the laptop as a ROS 2 and recording machine, not an inference target.

**Small form factor x86 with a real GPU.** Two families: MXM modules (laptop silicon on an 82 x 105
mm mezzanine, 95-115 W class, [ADLINK](https://www.adlinktech.com/en/mxm-gpu-modules)) and boxes
that take desktop PCIe cards. ASUS ROG NUC 2025: RTX 5080 Laptop 16 GB, "175W TGP", 3 L ([ASUS](https://rog.asus.com/desktops/mini-pc/rog-nuc-2025/));
ASUS NUC 13 Extreme: full-length PCIe x16 slot, about 13.8 L ([ASUS](https://www.asus.com/us/displays-desktops/nucs/nuc-kits/nuc-13-extreme-kit/techspec/));
rugged Neousys Nuvo-10208GC: two 350 W desktop cards on 8-48 V DC with ignition control, -25 to 60 C
([Neousys](https://www.neousys-tech.com/en/product/product-lines/edge-ai-gpu-computing/nuvo-10208gc-intel-13th-nvidia-rtx-gpu-computing-platform), page 403, specs from distributor copy).
For a cell that needs 24 GB+ with desktop drivers rather than JetPack, an RTX PRO 4500 Blackwell
(32 GB, 200 W) in a NUC Extreme-class box is the smallest option.

## Training compute

| Card | Memory | Bandwidth | Board power | Fits |
|---|---|---|---|---|
| [RTX 5090](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/) | 32 GB GDDR7 | (not on page) | 575 W, 1000 W PSU | pi0 LoRA (>22.5 GB), 7B inference |
| [RTX 6000 Ada](https://www.nvidia.com/en-us/design-visualization/rtx-6000/) | 48 GB GDDR6 ECC | (not on page) | 300 W | OpenVLA LoRA (27 GB min), GR00T N1.7 fine-tune (40 GB+) |
| [RTX PRO 5000 Blackwell](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-5000/) | 48 or 72 GB GDDR7 ECC | 1,344 GB/s | 300 W | same, more batch |
| [RTX PRO 6000 Blackwell](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000/) ([Max-Q](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000-max-q/)) | 96 GB GDDR7 ECC | 1,792 GB/s | 600 W (Max-Q 300 W) | pi0.5 full fine-tune (>70 GB) on one card |
| [RTX PRO 4500 Blackwell](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-4500/) | 32 GB GDDR7 ECC | 896 GB/s | 200 W | SFF inference box |
| [A100 80GB SXM](https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/a100/pdf/nvidia-a100-datasheet-us-nvidia-1758950-r4-web.pdf) | 80 GB HBM2e | 2,039 GB/s | 400 W | 312 TFLOPS dense BF16 |
| [H100 SXM](https://www.nvidia.com/en-us/data-center/h100/) | 80 GB HBM3 | 3.35 TB/s | up to 700 W | 989 TFLOPS dense BF16 |
| [H200 SXM](https://www.nvidia.com/en-us/data-center/h200/) | 141 GB HBM3e | 4.8 TB/s | up to 700 W | 989 TFLOPS dense BF16 |
| B200 ([DGX B200](https://www.nvidia.com/en-us/data-center/dgx-b200/), [HGX](https://www.nvidia.com/en-us/data-center/hgx/)) | 180 GB HBM3e (1,440 GB per 8) | 8 TB/s | about 1 kW | 2.25 PFLOPS dense BF16, derived from the 8-GPU figure |

NVIDIA datacenter pages quote sparse TFLOPS; dense is half. B300 at about 288 GB per GPU is
third-party only (unverified). Training memory with mixed-precision AdamW is about 16 bytes per
parameter before activations (2 weights + 2 grads + 12 optimizer, EleutherAI), so a 7B full
fine-tune is 112 GB: two 80 GB cards or one B200. That is why OpenVLA's authors used 8x A100 and
everyone else uses LoRA (VLA note).

**Cloud prices, fetched 2026-09-05, US regions.** AWS Capacity Blocks ([official](https://aws.amazon.com/ec2/capacityblocks/pricing/)):
p4d.24xlarge (8x A100 40GB) $11.80/h ($1.48/GPU); p5.48xlarge (8x H100) $41.53/h ($5.19/GPU); p5e
(8x H200) $47.76/h; p6-b200 (8x B200) $98.84/h ($12.36/GPU). AWS on-demand us-east-1 via a price-API
mirror ([vantage p5](https://instances.vantage.sh/aws/ec2/p5.48xlarge)): p4d $21.96/h, p5 $55.04/h,
p6-b200 $113.93/h. AWS Spot Advisor ([data](https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json), 22:33 UTC):
p4d 56%, p5 57%, p5en 67%, p6-b200 79% below on-demand; interruption bucket p5 under 5%, p6-b200
10-15%. Azure ND96isr H100 v5 $98.32/h, spot $18.17/h ([vantage](https://instances.vantage.sh/azure/vm/nd96isrh100-v5)).
GCP a3/a4 and Azure H200 pages are JavaScript-rendered; snippets put a3-highgpu-8g near $88/h (unverified).

| GPU | Lambda on-demand ([pricing](https://lambda.ai/pricing)) | RunPod community / secure ([pricing](https://www.runpod.io/pricing)) | Vast.ai floor ([pricing](https://vast.ai/pricing), JS-rendered, snippet only, unverified) |
|---|---|---|---|
| RTX 4090 24 GB | not offered | $0.34 / $0.74 | from $0.29 |
| RTX 5090 32 GB | not offered | $0.69 / $0.99 | from $0.37 |
| RTX PRO 6000 96 GB | not offered | $1.69 / $2.09 | (unverified) |
| A100 80 GB SXM | $2.79 (8x) | $1.39 / $1.59 | (unverified) |
| H100 80 GB SXM | $3.99 (8x) to $4.29 (1x) | $2.69 / $3.29 | from $1.65 |
| H200 141 GB | not listed | $3.59 / $4.59 | (unverified) |
| B200 180 GB | $6.69 (8x) to $6.99 (1x) | $5.98 / $6.79 | (unverified) |

A LoRA run that fits one 80 GB H100 costs $3-7/h by provider, half that on spot; a RunPod RTX PRO 6000
at $2/h tests a 96 GB fine-tune before buying the card. Buy when fine-tunes run weekly or data cannot leave site.

## Real-time configuration

**Kernel.** PREEMPT_RT merged into mainline in Linux 6.12 ([LWN](https://lwn.net/Articles/989212/)).
On Ubuntu 22.04 the supported route is Ubuntu Pro, free for up to 5 machines ([ubuntu.com/real-time](https://ubuntu.com/real-time)):
`sudo pro attach <token>` then `sudo pro enable realtime-kernel`, or `sudo apt install
linux-realtime-hwe-22.04` for the 6.8 HWE variant, then reboot ([Pro client docs](https://ubuntu.com/pro-client/docs//en/latest/howtoguides/enable_realtime_kernel/)).
Verify `uname -a` shows `PREEMPT_RT` and `/sys/kernel/realtime` reads 1, which is what Franka
checks: libfranka must "run with real-time priority under a PREEMPT_RT kernel" with
`@realtime soft/hard rtprio 99` and `memlock 102400` in `/etc/security/limits.conf` ([Franka RT setup](https://frankarobotics.github.io/docs/doc/libfranka/docs/real_time_kernel.html)).
ros2_control's controller manager asks for SCHED_FIFO priority 50 and the same `realtime` group ([control.ros.org](https://control.ros.org/rolling/doc/ros2_control/controller_manager/doc/userdoc.html)).
NVIDIA drivers "are not officially supported on PREEMPT_RT kernels"; the installer may work with
`IGNORE_PREEMPT_RT_PRESENCE=1` (Franka page), so keep the RT control PC and the GPU box separate.
Jetson Linux 36.4.4 ships an RT kernel as OTA packages (`nvidia-l4t-rt-kernel`, select `real-time`
in `/boot/extlinux/extlinux.conf`), labelled developer-preview ([Jetson RT kernel](https://docs.nvidia.com/jetson/archives/r36.4.4/DeveloperGuide/SD/Kernel/RealTimeKernel.html)).

**Boot parameters** ([kernel-parameters.txt](https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html)):
`isolcpus=domain,managed_irq,2-3` removes CPUs 2-3 from scheduler balancing (irreversible at
runtime); `nohz_full=2-3` stops the tick on them and implies `rcu_nocbs=2-3`; `processor.max_cstate=1`
and `intel_idle.max_cstate=0` cap sleep states so wake-up latency is bounded; `idle=poll` removes it
at the cost of power and heat. The ROS 2 Real-Time WG reference is `nohz_full=1-3 isolcpus=1-3
watchdog=0` with `CONFIG_HZ_1000` and the performance governor ([ros-realtime guide](https://ros-realtime.github.io/Guides/Real-Time-Operating-System-Setup/Real-Time-Linux/build_rt_kernel_using_docker.html)).
Pin the controller with `taskset` and `chrt -f`.

**BIOS.** Disable C-states and package sleep, SpeedStep/turbo, and SMT on the control PC; leave SMI
handling alone because fully disabling SMIs "can result in catastrophic hardware failure" ([Red Hat RT tuning](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux_for_real_time/9/html/optimizing_rhel_9_for_real_time_for_low_latency_operation/setting-bios-parameters-for-system-tuning_optimizing-rhel9-for-real-time-for-low-latency-operation), search snippet).

**Measure.** Canonical runs `sudo cyclictest --mlockall --smp --priority=80 --interval=200 --distance=0`
under `stress-ng` and reports Max 129 us on the generic kernel against 25 us on the RT kernel
([Ubuntu measure guide](https://ubuntu.com/real-time/docslatest/how-to/measure-maximum-latency/)).
The RT WG soak is `taskset -c 0 cyclictest -p 90 -m -t1 -n -D 3h -i 200 -a 1 -h500 -q`; `-m` locks
memory, `-p` SCHED_FIFO priority, `-i` interval in us, `-l` loop count, `-h` histogram ([Red Hat howto](https://people.redhat.com/williams/latency-howto/rt-latency-howto.txt)).
Acceptance for a 1 kHz loop: max under 100 us over the soak with cameras and network running, on the
controller's CPU; log the number and kernel version.

## Bandwidth budgets

| USB generation | Line rate | Encoding | Nominal payload | Practical |
|---|---|---|---|---|
| 3.2 Gen 1x1 (was 3.0) | 5 Gbit/s | 8b/10b | 500 MB/s | 200-460 MB/s |
| 3.2 Gen 2x1 | 10 Gbit/s | 128b/132b | 1,212 MB/s | 800-1,000 MB/s |
| 3.2 Gen 2x2 | 20 Gbit/s | 128b/132b | 2,424 MB/s | 1.6-2 GB/s |

Source: [USB 3.x](https://en.wikipedia.org/wiki/USB_3.0). RealSense quotes 4 Gbit/s raw for USB 3
and says stay "well below" about 30% of it; D415 depth 1280x720 at 30 fps is 442 Mbit/s, depth plus
colour 884 Mbit/s, and four cameras fit one controller only at 640x360 ([multi-camera guide](https://dev.realsenseai.com/docs/multiple-depth-cameras-configuration/)).
Hubs fail because every port behind one shares a single upstream link and one xHCI controller's
isochronous reservation; multi-port PCs often hide "an internal USB hub as opposed to having
multiple independent controllers" (same doc). Check with `lsusb -t` (one tree per root hub) and buy
controllers, not ports: StarTech PEXUSB3S44V has four Gen 1 controllers on PCIe x4 ([StarTech](https://www.startech.com/en-us/cards-adapters/pexusb3s44v));
Sonnet Allegro Pro has four Gen 2 controllers for eight ports on PCIe 3.0 x8 ([Sonnet](https://www.sonnettech.com/product/allegro-pro-usbc-8port/overview.html)).

**PCIe** per lane ([PCI Express](https://en.wikipedia.org/wiki/PCI_Express)): 3.0 0.985 GB/s, 4.0
1.969 GB/s, 5.0 3.938 GB/s. An x4 Gen 4 link is 7.9 GB/s, enough for a Gen 4 NVMe or a
four-controller USB card but not both behind a laptop's single Thunderbolt link. HDMI/SDI capture:
Magewell Pro Capture HDMI 4K Plus, Gen 2 x4 ([Magewell](https://www.magewell.com/tech-specs/pro-capture-hdmi-4k-plus)); DeckLink 8K Pro, Gen 3 x8 ([Blackmagic](https://www.blackmagicdesign.com/products/decklink/techspecs/W-DLK-37)).

**GMSL2 on Jetson.** 6 Gbit/s per link over coax "in excess of 15 m" ([MAX9295](https://www.analog.com/en/products/max9295d.html), snippet).
AGX Orin exposes 16 MIPI CSI-2 lanes, "up to 6 cameras (16 via virtual channels)" ([Orin page](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/)).
Deserializer boards: Connect Tech GMSL2 Plus, 8 cameras ([Connect Tech](https://connecttech.com/product/gmsl2-plus-camera-platform-for-nvidia-jetson-agx-orin-jetson-thor-t5000/));
D3 Embedded 16-channel with hardware sync ([D3](https://www.d3embedded.com/product/designcore-nvidia-jetson-agx-orin-gmsl2-interface-card/));
ZED Link Quad for ZED X ([Stereolabs](https://docs.stereolabs.com/docs/products/embedded/zed-link-capture-card)).
GMSL2 removes the USB budget and adds a kernel-module tie to the exact JetPack (depth camera note, from field).

**Storage for recording.** 1920x1080 RGB8 at 30 fps is 1920 x 1080 x 3 x 30 = 186.6 MB/s; 640x480
16-bit depth at 30 fps is 18.4 MB/s; one RealSense at 1280x720 colour plus depth at 30 fps is 82.9 +
55.3 = 138 MB/s, so three write 415 MB/s, 1.5 TB per hour, and fill a 2 TB drive in 80 minutes. A
USB 3.2 Gen 1 external SSD (200-460 MB/s practical) is already at the edge; record to NVMe. Samsung
990 PRO writes up to 6,900 MB/s ([datasheet](https://download.semiconductor.samsung.com/resources/data-sheet/samsung_nvme_ssd_990_pro_datasheet_rev.2.0.pdf))
and 9100 PRO up to 13,400 MB/s ([spec sheet](https://image-us.samsung.com/SamsungUS/home/pdf/2025_9100PRO_Memory_SpecSheet_022025_FINAL.pdf)),
but only until the SLC cache fills: TechPowerUp measured the 990 PRO 2 TB at about 5 GB/s for the
first 187 GB, then 1.7 GB/s sustained ([review](https://www.techpowerup.com/review/samsung-990-pro-2-tb/6.html)),
still 4x the three-camera rig. Compress at write time with the rosbag2 MCAP plugin
(`--storage-preset-profile zstd_small` for chunked zstd, `fastwrite` for maximum throughput,
[rosbag2_storage_mcap](https://github.com/ros2/rosbag2/blob/rolling/rosbag2_storage_mcap/README.md));
image compression ratios are content-dependent (unverified), as are Jetson NVENC stream counts.

## Networking and power

**Time sync.** Hardware PTP needs a NIC with a PHC: Intel I226-V lists "IEEE 1588: Yes" ([Intel](https://www.intel.com/content/www/us/en/products/sku/210599/intel-ethernet-controller-i226v/specifications.html)).
`ethtool -T eth0` shows the capabilities, the first thing the [linuxptp](https://linuxptp.sourceforge.net/)
homepage demonstrates; then `ptp4l -i eth0 -m` per machine and `phc2sys` to slave the system clock
(man pages, not fetched). Managed industrial switch with hardware 1588v2: Moxa EDS-4012 ([datasheet](https://www.moxa.com/getmedia/d3b9b18f-4832-41d9-bbd2-63f41f7f1945/moxa-eds-4012-series-datasheet-v1.6.pdf))
with BC, E2E_TC, and P2P_TC modes ([Moxa PTP manual](https://www.moxa.com/getmedia/5f267f23-042a-454a-861f-7733c8d047e7/moxa-computer-time-sync-settings-ieee-1588-ptp-manual-v1.0.pdf)).
Unmanaged DIN-rail spare: Moxa EDS-2008-EL, 8x 10/100 only, 9.6-60 VDC, -10 to 60 C ([Moxa](https://www.moxa.com/en/products/industrial-network-infrastructure/ethernet-switches/unmanaged-switches/eds-2008-el-series)),
fine for e-stop and robot control, not camera streams. The field checklist's `chrony` step is the
fallback when no PHC exists.

**Wireless for teleop.** Wi-Fi 6E opened the 6 GHz band; Wi-Fi 7 adds 320 MHz channels there, 4K
QAM, and Multi-Link Operation ([Wi-Fi Alliance](https://www.wi-fi.org/discover-wi-fi/wi-fi-certified-7)).
No vendor latency figure found (unverified); measure `ping -i 0.02` under camera load on site and keep the e-stop wired.

**Remote access.** Tailscale: `tailscale set --advertise-routes=<robot LAN>` with
`net.ipv4.ip_forward=1` makes the field laptop a subnet router for the whole cell
([subnet routers](https://tailscale.com/kb/1019/subnets)); `tailscale set --ssh` replaces key
distribution ([Tailscale SSH](https://tailscale.com/kb/1193/tailscale-ssh)). ROS 2 discovery does
not cross a VPN because default DDS discovery is multicast and the tunnel is point-to-point. Use
`rmw_zenoh` with its router ("without the Zenoh router, nodes will not be able to discover each
other", [rmw_zenoh](https://github.com/ros2/rmw_zenoh)) or the Fast DDS Discovery Server via
`ROS_DISCOVERY_SERVER`, which "does not require Multicasting"
([Fast DDS](https://fast-dds.docs.eprosima.com/en/latest/fastdds/ros2/discovery_server/ros2_discovery_server.html)).

**Power.** AGX Orin and Orin Nano dev kits take a 5.5 x 2.5 mm centre-positive DC jack ([AGX Orin layout](https://docs.nvidia.com/jetson/agx-orin-devkit/user-guide/latest/hardware_layout.html),
[Orin Nano layout](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/hardware_layout.html));
the input range is in the carrier board spec (commonly 9-20 V, unverified). Budget by power mode
plus peripherals: AGX Orin 60 W max, a managed switch about 10 W, three USB depth cameras a few W
each (unverified), laptop charging up to 100 W. A 12.8 V 20 Ah LiFePO4 pack (256 Wh; nominal voltage
unverified) runs a 120 W rig for about two hours. Put a DIN-rail DC UPS between battery and
electronics so an e-stop or battery swap does not reboot the Jetson: Mean Well DRC-40 ([Mean Well](https://www.meanwell.com/webapp/product/search.aspx?prod=DRC-40),
numbers only in the linked PDF, unverified). Network UPS Tools' `upsmon` shuts the Jetson down on
battery-low ([NUT](https://networkupstools.org/)).

## Field kit list

| Item | For |
|---|---|
| Laptop with a 16 GB+ discrete GPU (RTX 5080 Laptop class), or the 1050 Ti plus a remote inference box | driving, recording, small-policy inference, debugging |
| Jetson AGX Orin 64GB dev kit on the pinned JetPack, in a fanned case | on-robot inference matching the customer module |
| Four-controller USB 3 PCIe card (StarTech PEXUSB3S44V) or a dock with two controllers | three or more USB cameras without drops |
| Labelled USB 3 cables under 1 m, one spare per camera | cable faults are the top camera failure |
| Managed PoE switch with 1588, an unmanaged DIN-rail spare, 5 m and 20 m Cat6a cables | robot, cameras, laptop on one wired segment; never site WiFi for control |
| PTP-capable NIC (I226 class) | timestamp alignment across machines |
| WiFi 6E/7 travel router with WAN failover | teleop and the Tailscale uplink |
| 2 TB Gen 4 NVMe in a USB 3.2 Gen 2 enclosure, plus a second for backup | recording target and the SOP's 2x-volume rule |
| DC-DC converter and DIN-rail UPS with a LiFePO4 pack | keeping Jetson and switch alive across e-stops and battery swaps |

## Practical gotchas

**Driver/library mismatch on the current laptop (procedure to verify).** Symptom: `nvidia-smi`
prints "Failed to initialize NVML: Driver/library version mismatch". Usual cause:
unattended-upgrades replaced the userspace libraries (`libnvidia-compute-580`, `nvidia-utils-580`)
while the older kernel module stayed loaded; the kernel log shows `NVRM: API mismatch: the client
has the version X, but this kernel module has the version Y` ([NVIDIA forum](https://forums.developer.nvidia.com/t/nvml-driver-library-mismatch-after-libnvidia-update/126730),
[unattended-upgrades thread](https://forums.developer.nvidia.com/t/ubuntu-unattended-upgrades-leads-to-failed-to-initialize-nvml-driver-library-version-mismatch/250484)).
Second cause: packages from two repos. Ubuntu jammy-updates ships 580.173.02-0ubuntu0.22.04.1
([packages.ubuntu.com](https://packages.ubuntu.com/jammy-updates/nvidia-driver-580)), NVIDIA's
ubuntu2204 repo ships up to 580.178.04-1ubuntu1 ([NVIDIA repo](https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/)),
and apt can take half from each ([partial-upgrade thread](https://forums.developer.nvidia.com/t/ubuntu-20-04-driver-apt-packages-broken-by-unattended-upgrade-after-2-months/219260)).

```
cat /proc/driver/nvidia/version          # loaded kernel module version
modinfo nvidia | grep ^version           # module on disk
dpkg -l | grep -E 'nvidia|libnvidia'     # userspace versions; all must match
dkms status                              # module built for the running kernel?
sudo dmesg | grep -i nvrm                # API mismatch line
apt-cache policy nvidia-driver-580       # which repo won
```

Repair in order of least disruption ([sauerburger](https://frank.sauerburger.io/2024/03/27/nvidia-version-mismatch.html),
[hychiang](https://hychiang.info/blog/2024/nvml_mismatch/)):

```
sudo reboot                                       # fixes cause 1 by itself
# without reboot, from a text console with the display manager stopped:
sudo systemctl stop nvidia-persistenced
sudo rmmod nvidia_uvm nvidia_drm nvidia_modeset nvidia && sudo modprobe nvidia
# cause 2: make every package come from one repo, then rebuild
sudo apt install --reinstall nvidia-driver-580 libnvidia-compute-580
sudo apt install linux-headers-$(uname -r) && sudo dkms autoinstall
# prevent recurrence
sudo apt-mark hold nvidia-driver-580 libnvidia-compute-580 nvidia-utils-580
```

Or blacklist `"nvidia-"; "libnvidia-"; "cuda-";` under `Unattended-Upgrade::Package-Blacklist` in
`/etc/apt/apt.conf.d/50unattended-upgrades` ([example](https://help.ateliere.com/live/docs/installation/base-platform/unattended-upgrades/)).
If both repos are enabled, disable one; NVIDIA's guide says not to mix install methods ([CUDA install guide](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/index.html)).
`ubuntu-drivers install nvidia:580` is the clean reinstall ([ubuntuhandbook](https://ubuntuhandbook.org/index.php/2025/09/ubuntu-added-nvidia-580-driver/)).
Untested on this laptop; run it, then record versions in the hardware log.

**Other gotchas.**
- JetPack upgrades break vendor kernel modules (ZED GMSL2 driver) until the vendor ships a match;
  pin JetPack per robot (depth camera note, from field).
- Isaac ROS 4.0 to 4.5 had no Orin support; do not plan Orin on Jazzy until 4.6 / JetPack 7.2 is
  proven on the target robot.
- Thor's "7.5x Orin" is FP4-sparse against INT8-sparse; NVIDIA's own GR00T N1.5 comparison is
  2.7x (15.2 to 41.5 tok/s), so plan on about 3x for a policy until it is quantized to FP8/FP4.
- A 16 GB Orin NX with a 14 GB model OOM-kills under camera load; module memory is shared with the OS.
- NVIDIA driver plus PREEMPT_RT is unsupported; keep the 1 kHz loop off the GPU box.

## Sources

NVIDIA Jetson: [Orin family](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/), [Orin Nano Super dev kit](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/), [Thor](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-thor/), [Thor blog](https://developer.nvidia.com/blog/introducing-nvidia-jetson-thor-the-ultimate-platform-for-physical-ai/), [Thor release](https://nvidianews.nvidia.com/news/nvidia-blackwell-powered-jetson-thor-now-available-accelerating-the-age-of-general-robotics), [JetPack 6.0](https://developer.nvidia.com/embedded/jetpack-sdk-60), [6.1](https://developer.nvidia.com/embedded/jetpack-sdk-61), [6.2](https://developer.nvidia.com/embedded/jetpack-sdk-62), [6.2.1](https://developer.nvidia.com/embedded/jetpack-sdk-621), [7.0](https://developer.nvidia.com/embedded/jetpack/downloads/archive-7.0), [7.1](https://developer.nvidia.com/embedded/jetpack/downloads/archive-7.1), [7.2](https://developer.nvidia.com/embedded/jetpack/downloads/archive-7.2), [JetPack 7.2 forum](https://forums.developer.nvidia.com/t/jetpack-7-2-jetson-software-goes-agentic-with-jetson-linux-39-2/372056), [CUDA for Tegra](https://docs.nvidia.com/cuda/cuda-for-tegra-appnote/index.html), [Jetson RT kernel](https://docs.nvidia.com/jetson/archives/r36.4.4/DeveloperGuide/SD/Kernel/RealTimeKernel.html), [Jetson AI Lab benchmarks](https://www.jetson-ai-lab.com/archive/benchmarks.html), [openpi on Thor](https://www.jetson-ai-lab.com/tutorials/openpi_on_thor/), [Jetson-PI arXiv 2607.12659](https://arxiv.org/html/2607.12659), [LiteVLA-Edge arXiv 2603.03380](https://arxiv.org/html/2603.03380v1), [AGX Orin dev kit layout](https://docs.nvidia.com/jetson/agx-orin-devkit/user-guide/latest/hardware_layout.html), [Orin Nano dev kit layout](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/hardware_layout.html).
ROS 2 and Isaac ROS: [Humble release](https://www.openrobotics.org/blog/2022/5/23/ros-2-humble-hawksbill-released), [Jazzy release](https://www.openrobotics.org/blog/2024/5/ros-jazzy-jalisco-released), [Isaac ROS 3.2](https://nvidia-isaac-ros.github.io/v/release-3.2/getting_started/index.html), [4.0](https://nvidia-isaac-ros.github.io/v/release-4.0/getting_started/index.html), [current](https://nvidia-isaac-ros.github.io/getting_started/index.html), [LeRobot async](https://huggingface.co/docs/lerobot/en/async), [ros2_control](https://control.ros.org/rolling/doc/ros2_control/controller_manager/doc/userdoc.html), [ROS RT WG](https://ros-realtime.github.io/Guides/Real-Time-Operating-System-Setup/Real-Time-Linux/build_rt_kernel_using_docker.html), [rmw_zenoh](https://github.com/ros2/rmw_zenoh), [Fast DDS discovery server](https://fast-dds.docs.eprosima.com/en/latest/fastdds/ros2/discovery_server/ros2_discovery_server.html), [rosbag2 MCAP](https://github.com/ros2/rosbag2/blob/rolling/rosbag2_storage_mcap/README.md).
GPUs: [GeForce laptop compare](https://www.nvidia.com/en-us/geforce/laptops/compare/), [ADLINK BW5000](https://www.adlinktech.com/products/embedded_graphics/graphics_solutions/egx-mxm-bw5000?lang=en), [ADLINK AD5000](https://shop.adlinktech.com/products/egx-mxm-ad5000), [ADLINK MXM](https://www.adlinktech.com/en/mxm-gpu-modules), [RTX 5090](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/), [RTX 6000 Ada](https://www.nvidia.com/en-us/design-visualization/rtx-6000/), [RTX PRO 6000](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000/), [Max-Q](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000-max-q/), [RTX PRO 5000](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-5000/), [RTX PRO 4500](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-4500/), [A100 datasheet](https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/a100/pdf/nvidia-a100-datasheet-us-nvidia-1758950-r4-web.pdf), [H100](https://www.nvidia.com/en-us/data-center/h100/), [H200](https://www.nvidia.com/en-us/data-center/h200/), [DGX B200](https://www.nvidia.com/en-us/data-center/dgx-b200/), [HGX](https://www.nvidia.com/en-us/data-center/hgx/), [EleutherAI Transformer Math](https://blog.eleuther.ai/transformer-math/), [ROG NUC 2025](https://rog.asus.com/desktops/mini-pc/rog-nuc-2025/), [NUC 13 Extreme](https://www.asus.com/us/displays-desktops/nucs/nuc-kits/nuc-13-extreme-kit/techspec/), [Neousys Nuvo-10208GC](https://www.neousys-tech.com/en/product/product-lines/edge-ai-gpu-computing/nuvo-10208gc-intel-13th-nvidia-rtx-gpu-computing-platform).
Cloud: [AWS Capacity Blocks](https://aws.amazon.com/ec2/capacityblocks/pricing/), [AWS spot advisor data](https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json), [vantage p4d](https://instances.vantage.sh/aws/ec2/p4d.24xlarge), [vantage p5](https://instances.vantage.sh/aws/ec2/p5.48xlarge), [vantage p6-b200](https://instances.vantage.sh/aws/ec2/p6-b200.48xlarge), [vantage Azure ND H100 v5](https://instances.vantage.sh/azure/vm/nd96isrh100-v5), [Lambda](https://lambda.ai/pricing), [RunPod](https://www.runpod.io/pricing), [Vast.ai](https://vast.ai/pricing).
Real-time: [LWN PREEMPT_RT](https://lwn.net/Articles/989212/), [Ubuntu real-time](https://ubuntu.com/real-time), [Pro client RT kernel](https://ubuntu.com/pro-client/docs//en/latest/howtoguides/enable_realtime_kernel/), [Ubuntu latency measurement](https://ubuntu.com/real-time/docslatest/how-to/measure-maximum-latency/), [kernel parameters](https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html), [Red Hat BIOS tuning](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux_for_real_time/9/html/optimizing_rhel_9_for_real_time_for_low_latency_operation/setting-bios-parameters-for-system-tuning_optimizing-rhel9-for-real-time-for-low-latency-operation), [Red Hat latency howto](https://people.redhat.com/williams/latency-howto/rt-latency-howto.txt), [Franka RT kernel](https://frankarobotics.github.io/docs/doc/libfranka/docs/real_time_kernel.html).
I/O, network, power: [USB 3.x](https://en.wikipedia.org/wiki/USB_3.0), [PCI Express](https://en.wikipedia.org/wiki/PCI_Express), [RealSense multi-camera](https://dev.realsenseai.com/docs/multiple-depth-cameras-configuration/), [StarTech PEXUSB3S44V](https://www.startech.com/en-us/cards-adapters/pexusb3s44v), [Sonnet Allegro Pro](https://www.sonnettech.com/product/allegro-pro-usbc-8port/overview.html), [MAX9295](https://www.analog.com/en/products/max9295d.html), [Connect Tech GMSL2 Plus](https://connecttech.com/product/gmsl2-plus-camera-platform-for-nvidia-jetson-agx-orin-jetson-thor-t5000/), [D3 GMSL2 card](https://www.d3embedded.com/product/designcore-nvidia-jetson-agx-orin-gmsl2-interface-card/), [ZED Link](https://docs.stereolabs.com/docs/products/embedded/zed-link-capture-card), [Magewell](https://www.magewell.com/tech-specs/pro-capture-hdmi-4k-plus), [DeckLink 8K Pro](https://www.blackmagicdesign.com/products/decklink/techspecs/W-DLK-37), [990 PRO datasheet](https://download.semiconductor.samsung.com/resources/data-sheet/samsung_nvme_ssd_990_pro_datasheet_rev.2.0.pdf), [9100 PRO spec](https://image-us.samsung.com/SamsungUS/home/pdf/2025_9100PRO_Memory_SpecSheet_022025_FINAL.pdf), [TechPowerUp 990 PRO](https://www.techpowerup.com/review/samsung-990-pro-2-tb/6.html), [Intel I226-V](https://www.intel.com/content/www/us/en/products/sku/210599/intel-ethernet-controller-i226v/specifications.html), [linuxptp](https://linuxptp.sourceforge.net/), [Moxa EDS-4012](https://www.moxa.com/getmedia/d3b9b18f-4832-41d9-bbd2-63f41f7f1945/moxa-eds-4012-series-datasheet-v1.6.pdf), [Moxa PTP manual](https://www.moxa.com/getmedia/5f267f23-042a-454a-861f-7733c8d047e7/moxa-computer-time-sync-settings-ieee-1588-ptp-manual-v1.0.pdf), [Moxa EDS-2008-EL](https://www.moxa.com/en/products/industrial-network-infrastructure/ethernet-switches/unmanaged-switches/eds-2008-el-series), [Wi-Fi 7](https://www.wi-fi.org/discover-wi-fi/wi-fi-certified-7), [Tailscale subnets](https://tailscale.com/kb/1019/subnets), [Tailscale SSH](https://tailscale.com/kb/1193/tailscale-ssh), [Mean Well DRC-40](https://www.meanwell.com/webapp/product/search.aspx?prod=DRC-40), [NUT](https://networkupstools.org/).
Driver fix: [deprecation schedule](https://forums.developer.nvidia.com/t/unix-graphics-feature-deprecation-schedule/60588), [CUDA 13.0 notes](https://docs.nvidia.com/cuda/archive/13.0.1/cuda-toolkit-release-notes/index.html), [driver kernel modules](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/kernel-modules.html), [PyTorch cu128 notice](https://dev-discuss.pytorch.org/t/cuda-toolkit-version-and-architecture-support-update-maxwell-and-pascal-architecture-support-removed-in-cuda-12-8-and-12-9-builds/3128), [PyTorch cu126 end notice](https://dev-discuss.pytorch.org/t/notice-cuda-12-6-wheels-will-no-longer-be-published-from-pytorch-2-15-drops-maxwell-pascal-volta/3432), [NVML mismatch thread](https://forums.developer.nvidia.com/t/nvml-driver-library-mismatch-after-libnvidia-update/126730), [unattended-upgrades thread](https://forums.developer.nvidia.com/t/ubuntu-unattended-upgrades-leads-to-failed-to-initialize-nvml-driver-library-version-mismatch/250484), [partial-upgrade thread](https://forums.developer.nvidia.com/t/ubuntu-20-04-driver-apt-packages-broken-by-unattended-upgrade-after-2-months/219260), [sauerburger](https://frank.sauerburger.io/2024/03/27/nvidia-version-mismatch.html), [hychiang](https://hychiang.info/blog/2024/nvml_mismatch/), [packages.ubuntu.com 580](https://packages.ubuntu.com/jammy-updates/nvidia-driver-580), [NVIDIA ubuntu2204 repo](https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/), [CUDA install guide](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/index.html), [ubuntuhandbook 580](https://ubuntuhandbook.org/index.php/2025/09/ubuntu-added-nvidia-580-driver/), [unattended-upgrades blacklist](https://help.ateliere.com/live/docs/installation/base-platform/unattended-upgrades/).
