---
title: Robot learning reading list
date: 2026-09-05
tags: [reading-list]
status: draft
source: curated
---

# Reading list

Canonical work a forward-deployed robot learning engineer is expected to know.
Each row becomes its own file in this directory once read. One-line gists only;
details go in the per-paper file with sources.

## Imitation learning and policy architectures

| Work | Year | Gist | Entry |
|------|------|------|-------|
| ALOHA / ACT (Zhao et al.) | 2023 | Low-cost bimanual teleop plus a transformer that predicts action chunks. | [zhao-2023-aloha-act.md](zhao-2023-aloha-act.md) |
| Diffusion Policy (Chi et al.) | 2023 | Model actions as a conditional denoising process. Strong on multimodal demos. | [chi-2023-diffusion-policy.md](chi-2023-diffusion-policy.md) |
| Implicit BC (Florence et al.) | 2021 | Energy-based policies; why explicit regression struggles with multimodality. | [florence-2021-implicit-bc.md](florence-2021-implicit-bc.md) |
| UMI (Chi et al.) | 2024 | Handheld gripper data collection decoupled from the robot. | [chi-2024-umi.md](chi-2024-umi.md) |
| 3D Diffusion Policy (Ze et al.) | 2024 | Diffusion policy on point clouds. | todo |
| VQ-BeT (Lee et al.) | 2024 | Residual VQ action tokens plus a GPT head; one forward pass per action. | [lee-2024-vq-bet.md](lee-2024-vq-bet.md) |
| Data scaling laws in IL (Lin et al.) | 2024 | Generalisation scales as a power law in environments and objects, not demos. | [lin-2024-data-scaling-laws.md](lin-2024-data-scaling-laws.md) |

## Vision-language-action models and large-scale data

| Work | Year | Gist | Entry |
|------|------|------|-------|
| RT-1 (Brohan et al.) | 2022 | Transformer policy on 130k real episodes. | [brohan-2022-rt1.md](brohan-2022-rt1.md) |
| RT-2 (Brohan et al.) | 2023 | VLM fine-tuned to emit actions as tokens. | [brohan-2023-rt2.md](brohan-2023-rt2.md) |
| Open X-Embodiment (2023) | 2023 | Cross-embodiment dataset and RT-X models. | [open-x-embodiment-collaboration-2023-rt-x.md](open-x-embodiment-collaboration-2023-rt-x.md) |
| Octo (2024) | 2024 | Open generalist policy, diffusion head. | [octo-model-team-2024-octo.md](octo-model-team-2024-octo.md) |
| OpenVLA (Kim et al.) | 2024 | 7B open VLA, LoRA fine-tuning recipe. | [kim-2024-openvla.md](kim-2024-openvla.md), [kim-2025-openvla-oft.md](kim-2025-openvla-oft.md) |
| π0 (Physical Intelligence) | 2024 | VLM backbone plus flow-matching action expert. | [black-2024-pi0.md](black-2024-pi0.md), [physical-intelligence-2025-pi05.md](physical-intelligence-2025-pi05.md) |
| DROID (2024) | 2024 | Large diverse in-the-wild manipulation dataset. | [khazatsky-2024-droid.md](khazatsky-2024-droid.md) |

## Reinforcement learning and sim-to-real

| Work | Year | Gist | Entry |
|------|------|------|-------|
| Dreamer v3 (Hafner et al.) | 2023 | World-model RL that works across domains with fixed hyperparameters. | [hafner-2023-dreamerv3.md](hafner-2023-dreamerv3.md) |
| Learning to Walk in Minutes (Rudin et al.) | 2021 | Massively parallel sim RL for legged locomotion. | [rudin-2021-learning-to-walk-in-minutes.md](rudin-2021-learning-to-walk-in-minutes.md) |
| Domain randomization (Tobin et al.) | 2017 | Randomize sim visuals so real looks like another sample. | [tobin-2017-domain-randomization.md](tobin-2017-domain-randomization.md) |
| RLPD (Ball et al.) | 2023 | Off-policy RL with 50/50 offline sampling, LayerNorm critics, high UTD. The learner inside SERL. | [ball-2023-rlpd.md](ball-2023-rlpd.md) |
| SERL (Luo et al.) | 2024 | Sample-efficient real-world RL for manipulation. | [luo-2024-serl.md](luo-2024-serl.md) |
| HIL-SERL (2024) | 2024 | Human-in-the-loop corrections on top of SERL. | [luo-2024-hil-serl.md](luo-2024-hil-serl.md) |

## Perception and representation

| Work | Year | Gist | Entry |
|------|------|------|-------|
| R3M (Nair et al.) | 2022 | ResNet pretrained on Ego4D with time-contrastive and language losses, for frozen policy inputs. | [nair-2022-r3m.md](nair-2022-r3m.md) |
| VC-1 (Majumdar et al.) | 2023 | MAE ViT pretrained on egocentric video, evaluated across embodied tasks. | todo |
| DINOv2 (Oquab et al.) | 2023 | Self-supervised ViT features widely used as frozen policy backbones. | [oquab-2023-dinov2.md](oquab-2023-dinov2.md) |
| Segment Anything (Kirillov et al.) | 2023 | Promptable image segmentation trained with a data engine on 1B masks. | [kirillov-2023-segment-anything.md](kirillov-2023-segment-anything.md) |
| SAM 2 (Ravi et al.) | 2024 | Promptable segmentation extended to video with a streaming memory. | [ravi-2024-sam2.md](ravi-2024-sam2.md) |
| Depth Anything V2 (Yang et al.) | 2024 | Monocular depth trained on synthetic labels and pseudo-labelled real images; metric fine-tunes. | [yang-2024-depth-anything-v2.md](yang-2024-depth-anything-v2.md) |
| FoundationPose (Wen et al.) | 2024 | 6D pose estimation and tracking of novel rigid objects from RGB-D plus a CAD model or reference views. | [wen-2024-foundationpose.md](wen-2024-foundationpose.md) |
| RAFT-Stereo (Lipson et al.) | 2021 | Iterative GRU refinement over a correlation pyramid for stereo disparity. | [lipson-2021-raft-stereo.md](lipson-2021-raft-stereo.md) |
| FoundationStereo (Wen et al.) | 2025 | Zero-shot stereo matching with a monocular depth foundation backbone and a large synthetic dataset. | [wen-2025-foundationstereo.md](wen-2025-foundationstereo.md) |

## Evaluation and deployment

| Work | Year | Gist | Entry |
|------|------|------|-------|
| LIBERO | 2023 | Lifelong manipulation benchmark. | todo |
| SimplerEnv | 2024 | Sim evaluation that correlates with real policy performance. | [li-2024-simplerenv.md](li-2024-simplerenv.md) |
| Evaluating real-world robot policies (Kress-Gazit et al. and others) | 2024 | How to report success rates honestly. | todo |

## Deformable and food handling

| Work | Year | Gist | Entry |
|------|------|------|-------|
| DefGraspSim (Huang et al.) | 2022 | GPU FEM grasp outcomes on 34 deformable objects; 7 metrics, 7 pre-pickup features, tofu and latex pilot. | [huang-2022-defgraspsim.md](huang-2022-defgraspsim.md) |
| Dex-Net 3.0 (Mahler et al.) | 2017 | Analytic suction seal and wrench model labels 2.8M synthetic grasps; GQ-CNN 98/82/58% on basic/typical/adversarial objects. | [mahler-2017-dex-net-3.md](mahler-2017-dex-net-3.md) |
| DeformableRavens (Seita et al.) | 2021 | Goal-image Transporter Networks on 12 cable, fabric, and bag tasks; 7/10 on a real cable. | [seita-2021-deformable-ravens.md](seita-2021-deformable-ravens.md) |
| RoboCraft (Shi et al.) | 2022 | Particles from RGB-D, GNN dynamics from 10 min of real pinches, gradient MPC shapes dough into letters. | [shi-2022-robocraft.md](shi-2022-robocraft.md) |
| SpeedFolding (Avigal et al.) | 2022 | Bimanual pose-pair network plus a learned "smooth enough" classifier; 93% folds at 30 to 40 per hour. | [avigal-2022-speedfolding.md](avigal-2022-speedfolding.md) |
| Optical-flow slip gripper (Takács et al.) | 2023 | In-finger endoscope and Farneback flow for slip in a meat-cell gripper; no reported rates. | [takacs-2023-optical-flow-slip-gripper.md](takacs-2023-optical-flow-slip-gripper.md) |
| ChicGrasp (Davar et al.) | 2025 | Dual-jaw pneumatic gripper plus diffusion policy from 50 demos; 41/101 broiler carcass picks. | [davar-2025-chicgrasp.md](davar-2025-chicgrasp.md) |

## Skill composition, generative machinery and cross-embodiment transfer

Read in full for pass 7 (2026-09-15). No per-paper file yet; each row points to the topic note that uses it.

| Work | Year | Gist | Entry |
|------|------|------|-------|
| Reduce, Reuse, Recycle (Du et al.) | 2023 | Summed diffusion scores do not sample the product distribution; MCMC samplers at each noise level fix it at up to 5x the cost. | [generative models](../topics/generative-models-vae-and-diffusion.md) |
| Classifier-free guidance (Ho and Salimans) | 2022 | Guidance as a product with an implicit classifier, at double the network evaluations per step. | [generative models](../topics/generative-models-vae-and-diffusion.md) |
| Flow matching (Lipman et al.) | 2023 | Regress a velocity field from noise to data; the action generator inside π0. | [generative models](../topics/generative-models-vae-and-diffusion.md) |
| Multimodal VAE (Wu and Goodman) | 2018 | Product of Gaussian experts in latent space, one expert per modality. | [generative models](../topics/generative-models-vae-and-diffusion.md) |
| CrossFormer (Doshi et al.) | 2024 | One transformer policy over 20 embodiments; the authors report no significant positive transfer yet. | [cross-embodiment](../topics/cross-embodiment-skill-transfer.md) |
| HPT (Wang et al.) | 2024 | Shared pretrained trunk with a stem and head per embodiment. | [cross-embodiment](../topics/cross-embodiment-skill-transfer.md) |
| Mirage (Chen et al.) | 2024 | Cross-painting the source robot into target images for zero-shot arm transfer; end-effector actions with a blocking controller. | [cross-embodiment](../topics/cross-embodiment-skill-transfer.md) |
| RoVi-Aug (Chen et al.) | 2024 | Robot and viewpoint augmentation; one policy runs Franka to UR5 and back zero-shot. | [cross-embodiment](../topics/cross-embodiment-skill-transfer.md) |
| Shadow (Lepert et al.) | 2025 | Mask-based embodiment swap; real UR5e success falls from 0.98 to 0.64 under 1 cm, 5 degree calibration noise. | [cross-embodiment](../topics/cross-embodiment-skill-transfer.md) |
| Modular multi-robot policies (Devin et al.) | 2017 | Task modules and robot modules composed through a learned interface; unseen robot-task pairs in simulation. | [cross-embodiment](../topics/cross-embodiment-skill-transfer.md) |

Add rows as the job reveals what matters. Remove rows that turn out to be irrelevant.
