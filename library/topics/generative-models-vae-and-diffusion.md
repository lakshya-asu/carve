---
title: "Generative models behind learned skills: VAEs, diffusion, flow matching, and composing them"
date: 2026-09-15
tags: [topic, generative-models, vae, cvae, diffusion, flow-matching, score-composition, product-of-experts, skill-architecture, pork-leg]
status: draft
source:
  - https://arxiv.org/abs/1312.6114
  - https://openreview.net/forum?id=Sy2fzU9gl
  - https://arxiv.org/abs/1802.05335
  - https://arxiv.org/abs/2006.11239
  - https://arxiv.org/abs/2011.13456
  - https://arxiv.org/abs/2010.02502
  - https://arxiv.org/abs/2207.12598
  - https://arxiv.org/abs/2210.02747
  - https://arxiv.org/abs/2302.11552
  - worked example computed in the rll env (Python 3.11.16, numpy 2.4.6, scipy 1.17.1) on 2026-09-14
---

# Generative models behind learned skills

What was read in full: Kingma and Welling (arXiv v11), Higgins et al. beta-VAE (ICLR 2017 PDF,
openreview.net blocked scripted download, read from a
[course mirror](https://www.cs.toronto.edu/~bonner/courses/2022s/csc2547/papers/generative/disentangled-representations/beta-vae,-higgins,-iclr2017.pdf)),
Wu and Goodman (v3), Ho et al. DDPM (v2), Song et al. SDE (ICLR 2021), Song et al. DDIM (ICLR 2021),
Ho and Salimans (v1), Lipman et al. (v2), Du et al. (v6). Read in the sections cited: Bowman et al.
2016, Kingma et al. 2016 (Appendix C.8), He et al. 2019, Razavi et al. 2019, Dhariwal and Nichol
2021 (Sec. 4), Pertsch et al. FAST 2025 (Sec. VI-E). Robot numbers come from the paper notes linked
inline, not re-read.

## What it is

A learned skill is a conditional distribution over action chunks, p(a | o), and the model family
decides three things that matter downstream: whether the distribution keeps separate modes, how
many network evaluations one chunk costs, and whether the skill exposes a score or energy that
another skill can be added to. VAEs give a latent variable model trained on a lower bound. Diffusion
and flow models give a learned vector field that is integrated from noise to an action. Energy-based
models give an unnormalised log-density that is optimised or sampled. Token models give a
categorical per token.

## Why it matters in the field

The pork-leg station aligns an 11 kg, 720 mm bone-in leg on a moving belt so the trotter hangs over
the edge ([composition note](../papers/policy-composition-primitives-controllers-diffusion.md),
[arm selection](arm-selection-scara-vs-six-axis.md)). A skill library for it holds skills such as
"rotate the leg" learned from teleoperation, where demonstrators turn it either way (two modes), and
"keep the trotter beyond the edge" written as a cost or a narrow expert. Running both at once means
sampling a product p_1(a) p_2(a). That is only available when each skill exposes grad log p or an
energy, and it changes the mode weights, which a Gaussian action head cannot represent (worked
example below). Composition also multiplies network evaluations. PoCo runs at 5 Hz with two policies
([PoCo in the composition note](../papers/policy-composition-primitives-controllers-diffusion.md)),
and a belt at 300 mm/s moves 30 mm per 100 ms chunk
([conveyor note](conveyor-tracking-and-visual-servoing.md#visual-servoing)). Hard limits stay in
the deterministic layer, not inside a product
([energy products note](../papers/policy-composition-energy-products.md)).

## Methods

### Variational autoencoders

```text
ELBO (Kingma and Welling 2013, Eqs. 1-3)
  log p(x) = log  integral p(x|z) p(z) dz
           = log  E_q(z|x) [ p(x|z) p(z) / q(z|x) ]
          >= E_q(z|x) [ log p(x|z) + log p(z) - log q(z|x) ]       Jensen
           = E_q(z|x) [ log p(x|z) ] - KL( q(z|x) || p(z) )        =: ELBO
  gap:  log p(x) - ELBO = KL( q(z|x) || p(z|x) ) >= 0

Reparameterisation (Sec. 2.4)
  z = mu_phi(x) + sigma_phi(x) * eps,   eps ~ N(0, I)
  grad_phi E_q[ f(z) ] = E_eps[ grad_phi f(mu_phi(x) + sigma_phi(x) * eps) ]
  Gaussian q, N(0, I) prior:  -KL = 1/2 sum_j ( 1 + log sigma_j^2 - mu_j^2 - sigma_j^2 )   (Eq. 10)

beta-VAE (Higgins et al. 2017, Eq. 4)
  L = E_q(z|x) [ log p(x|z) ] - beta * KL( q(z|x) || p(z) )

Conditional VAE for action chunks (ACT)
  decoder p(a_{t:t+k} | z, o),  encoder q(z | a_{t:t+k}, joints),  prior N(0, I),  test time z = 0
```

The naive score-function gradient of E_q[f(z)] has variance too high to use; the reparameterised
estimator works with one sample per datapoint at minibatch 100
([Kingma and Welling 2013](https://arxiv.org/abs/1312.6114), Sec. 2.2 and Algorithm 1).

beta-VAE derives beta as the KKT multiplier of a constraint KL < epsilon. Beta above 1 improved
disentanglement on 2D shapes: metric accuracy 99.23 ± 0.1 % at beta = 4 against 61.58 ± 0.5 % for
beta = 1, with semi-supervised DC-IGN at 99.3 %. The paper reports that disentangled settings "often
result in blurry reconstructions" and that the best beta traces an inverted U against latent size
([Higgins et al. 2017](https://openreview.net/forum?id=Sy2fzU9gl), Sec. 2, Fig. 5). ACT uses
beta = 10 with an L1 reconstruction ([ACT note](../papers/zhao-2023-aloha-act.md)).

Posterior collapse is the local optimum q(z|x) = p(z|x) = p(z) for all x, where a decoder strong
enough to model the data alone ignores z
([He et al. 2019](https://arxiv.org/abs/1901.05534), Sec. 2.2). Fixes that change decisions:
- KL annealing: weight on KL from 0 to 1 over training. Bowman et al. also replace a fraction of
  decoder inputs with UNK (word dropout); without both, their LSTM VAE "reliably" converged to zero
  KL ([Bowman et al. 2016](https://arxiv.org/abs/1511.06349), Sec. 3.1, Sec. 4).
- Free bits: subtract max(lambda, E[KL_j]) per latent group, so spending fewer than lambda nats earns
  nothing; lambda in 0.125 to 2 helped on CIFAR-10
  ([Kingma et al. 2016](https://arxiv.org/abs/1606.04934), Appendix C.8, Eq. 15).
- Aggressive encoder updates: run the encoder to convergence per decoder step until the mutual
  information I_q on validation stops rising, then revert to normal training
  ([He et al. 2019](https://arxiv.org/abs/1901.05534), Algorithm 1, Sec. 4.2).
- Committed rate: pick posterior and prior families whose minimum KL is delta > 0 by construction,
  such as a mean-field posterior against an AR(1) prior
  ([Razavi et al. 2019](https://arxiv.org/abs/1901.03416), Sec. 2, Eq. 1).

For ACT the evidence that the latent is used is the ablation: without the CVAE, success on human
data fell from 35.3 % to 2 %, and on scripted data it made no difference
([ACT note](../papers/zhao-2023-aloha-act.md)).

Products of Gaussian experts in latent space. Wu and Goodman assume modalities x_1..x_N are
conditionally independent given z, which gives p(z | x_1..x_N) proportional to
prod_i p(z | x_i) / p(z)^(N-1). Writing each unimodal posterior as q~(z|x_i) p(z) cancels the
quotient, so the joint posterior is p(z) prod_i q~(z|x_i), with any missing modality dropped. For
Gaussians with precisions T_i = V_i^-1 the product has V = (sum_i T_i)^-1 and
mu = (sum_i mu_i T_i)(sum_i T_i)^-1. The quotient variant needs V_2 > V_1 elementwise, which was
hard in practice. A product does not identify its factors, so training on complete data alone
leaves unimodal encoders untrained; the fix is a subsampled objective with the full ELBO, every
single-modality ELBO, and k random subsets per step
([Wu and Goodman 2018](https://arxiv.org/abs/1802.05335), Secs. 2.1 and 2.2). For skills this means
latent-space products work for encoders trained together, not for skills trained apart. The latent
skill methods are in [latent skills](../papers/policy-composition-latent-skills.md).

### Diffusion and flow models

```text
DDPM (Ho et al. 2020)
  forward:  q(x_t | x_0) = N( sqrt(abar_t) x_0, (1 - abar_t) I ),   abar_t = prod_{s<=t} (1 - beta_s)    (Eq. 4)
  loss:     E_{t, x_0, eps} || eps - eps_theta( sqrt(abar_t) x_0 + sqrt(1 - abar_t) eps, t ) ||^2    (Eq. 14)
  sample:   x_{t-1} = ( x_t - beta_t / sqrt(1 - abar_t) * eps_theta ) / sqrt(1 - beta_t) + sigma_t z   (Alg. 2)

Score view (Song et al. 2021; Ho and Salimans 2022, Sec. 2)
  eps_theta(x_t, t) ~= -sqrt(1 - abar_t) * grad_x log p_t(x_t)
  reverse SDE:          dx = [ f(x,t) - g(t)^2 grad_x log p_t(x) ] dt + g(t) dw_bar            (Eq. 6)
  probability flow ODE: dx = [ f(x,t) - 1/2 g(t)^2 grad_x log p_t(x) ] dt                       (Eq. 13)
  DDPM noise is the discretised VP SDE  dx = -1/2 beta(t) x dt + sqrt(beta(t)) dw               (Eq. 11)

DDIM, eta = 0 (Song, Meng, Ermon 2021)
  x0_hat  = ( x_t - sqrt(1 - abar_t) eps_theta ) / sqrt(abar_t)
  x_{t'}  = sqrt(abar_{t'}) x0_hat + sqrt(1 - abar_{t'}) eps_theta          same trained network, any step subset

Flow matching, OT path (Lipman et al. 2023, Eqs. 20-23; t = 0 noise, t = 1 data)
  x_t = (1 - (1 - sigma_min) t) x_0 + t x_1
  loss: E || v_theta(x_t, t) - ( x_1 - (1 - sigma_min) x_0 ) ||^2
  with sigma_min -> 0 the marginal velocity and score on this path satisfy
  v_t(x) = ( x + (1 - t) grad_x log p_t(x) ) / t      (derived here; checked by hand on x_1 ~ N(0, 1))
```

DDPM fixes T = 1000 and betas linear from 1e-4 to 0.02; learning the reverse variances "leads to
unstable training", and the unweighted eps loss gave the best samples (CIFAR-10 FID 3.17)
([Ho et al. 2020](https://arxiv.org/abs/2006.11239), Sec. 4, Table 2). The eps loss is denoising
score matching over noise levels ([Song et al. 2021](https://arxiv.org/abs/2011.13456), Eq. 7), which
is what makes the composition algebra below apply to any eps-prediction policy.

DDIM changes only the sampler. At 10 steps on CIFAR-10, FID is 13.36 for eta = 0 against 41.07 for
eta = 1 (DDPM); at 100 steps 4.16 against 5.78; the paper claims 10x to 50x faster sampling at
comparable quality ([Song, Meng, Ermon 2021](https://arxiv.org/abs/2010.02502), Table 1). Diffusion
Policy trains with 100 DDPM steps and runs 10 to 16 DDIM steps on the robot
([Diffusion Policy note](../papers/chi-2023-diffusion-policy.md)).

Classifier guidance. Sampling each step from Z p(x_t | x_{t+1}) p_phi(y | x_t) is approximated by
shifting the Gaussian mean by s Sigma grad log p_phi(y | x_t), with a classifier trained on noisy
inputs; scale 10 gave FID 12.0 against 33.0 at scale 1 on one ImageNet class
([Dhariwal and Nichol 2021](https://arxiv.org/abs/2105.05233), Sec. 4.1, Algorithm 1, Fig. 3).

Classifier-free guidance trains one network with the condition replaced by a null token with
probability p_uncond and samples with eps~ = (1 + w) eps(z, c) - w eps(z). p_uncond of 0.1 and 0.2
performed about equally and 0.5 was worse; best FID came at w = 0.1 to 0.3 and best IS at w >= 4,
and every step costs two network evaluations. The guided eps is not the gradient of any classifier,
because unconstrained networks produce non-conservative fields
([Ho and Salimans 2022](https://arxiv.org/abs/2207.12598), Secs. 3.2, 4.1 to 4.3).

Flow matching regresses a velocity field. The conditional loss has the same gradient as the
intractable marginal one (Theorem 2). The OT path gives straight conditional trajectories. On
ImageNet 64x64, with the same U-Net and an adaptive dopri5 solver, FM-OT needed 138 function
evaluations at FID 14.45 against 264 at 17.36 for DDPM training
([Lipman et al. 2023](https://arxiv.org/abs/2210.02747), Secs. 3 and 4.1, Table 1). pi0 trains its
300M action expert with a linear-Gaussian flow path, integrates 10 Euler steps, and measures 73 ms
per 50-step chunk on an RTX 4090 ([pi0 note](../papers/black-2024-pi0.md)).

Action chunking with diffusion. Diffusion Policy denoises a T_p = 16 chunk conditioned on T_o = 2
observations through FiLM, executes T_a = 8, and replans; actions are normalised to [-1, 1] because
DDPM clips there ([Diffusion Policy note](../papers/chi-2023-diffusion-policy.md)).

### Composition

```text
Product (AND):  p(a) = p_1(a) p_2(a) / Z   =>   grad log p = grad log p_1 + grad log p_2      Z drops out
  eps space:    eps = eps_1 + eps_2          (both at the same t)
  flow space:   v = v_1 + v_2 - x/t          (from the velocity-score relation above; derived here)
Energies:       p_i proportional to exp(-E_i)   =>   E = E_1 + E_2       (exact for argmin or MCMC)
Mixture (OR):   p = 1/N sum_i p_i        needs normalised densities; scores alone cannot express it
Negation:       p_0(x) / p_1(x)^alpha    Du et al. use alpha = 0.5

Classifier guidance as a product (Ho and Salimans 2022, Sec. 3.1)
  target  p(x_t | c) p(c | x_t)^w
  eps~ =  eps(x_t, c) - w sigma_t grad log p_phi(c | x_t)
CFG as a product with an implicit classifier p(c | x) proportional to p(x | c) / p(x)
  eps~ = (1 + w) eps(x_t, c) - w eps(x_t)   targets   p(x | c)^(1 + w) / p(x)^w

Why summed scores do not sample the product (Du et al. 2023, Eqs. 11-12)
  reverse diffusion needs   grad log  integral p_1(x_0) p_2(x_0) q(x_t | x_0) dx_0
  summing gives             grad log  integral p_1(x_0) q(x_t | x_0) dx_0
                          + grad log  integral p_2(x_0) q(x_t | x_0) dx_0
  equal only at t = 0. At t = T the summed field is the score of N(0, I/2), not the N(0, I) the sampler starts from.
Fix (Du et al. Alg. 1): at each noise level run K MCMC steps on the summed score,
  ULA:  x <- x + (h/2) s_sum(x, t) + sqrt(h) z
  MALA or HMC with Metropolis correction need an energy, f_theta(x, t) = -|| s_theta(x, t) ||^2   (Sec. 4.2)
```

Du et al. measure the gap. For classifier-guided ImageNet 128x128, class accuracy was 18.64 % with
reverse diffusion, 89.93 % with U-HMC on the score model, and 94.61 % with HMC on the energy model.
For CLEVR with 5 composed cube positions it was 57.4 % reverse, 62.3 % U-HMC, and 72.7 % energy HMC.
The costs: MCMC samplers "can take 5-times longer", and the energy parameterisation needs a second
backward pass, doubling memory and compute
([Du et al. 2023](https://arxiv.org/abs/2302.11552), Tables 2 and 3, Sec. 6). The derivation of
score addition and PoCo's use of it on a Franka are in the
[composition note](../papers/policy-composition-primitives-controllers-diffusion.md); energy sums
and Gaussian products for controllers are in the
[energy products note](../papers/policy-composition-energy-products.md).

## Comparison table for robot policies

Sampling cost numbers are as reported, on different hardware. "Actions/s" in the OpenVLA-OFT table
is chunk length over latency (8 actions at 74 ms gives 108.8 Hz,
[OFT note](../papers/kim-2025-openvla-oft.md)), not the rate at which a new chunk arrives.

| Family | Multimodality | Sampling cost (reported) | Ease of composition | Ease of conditioning | Training stability | Known failure modes |
|---|---|---|---|---|---|---|
| CVAE (ACT) | Through z during training; at test z = 0 decodes one fixed point (worked example) | ACT about 0.01 s per 100-step chunk on RTX 2080 Ti ([ACT](../papers/zhao-2023-aloha-act.md)); 433 actions/s on A100, 3 images ([OFT](../papers/kim-2025-openvla-oft.md)) | Low in action space (no score or energy); Gaussian PoE in latent space only for jointly trained encoders ([Wu and Goodman](https://arxiv.org/abs/1802.05335)) | Observation into decoder and encoder; no guidance mechanism | Posterior collapse needs annealing, free bits, or aggressive encoder steps (sources above); beta tuned per task | CVAE irrelevant on scripted data; a collapsed model returns the mode average |
| Diffusion (DDPM train, DDIM sample) | Yes, samples each mode | Diffusion Policy 0.1 s per chunk, 10 DDIM steps, RTX 3080 ([DP](../papers/chi-2023-diffusion-policy.md)); DP-C 100.5 ms against VQ-BeT 15.1 ms ([VQ-BeT](../papers/lee-2024-vq-bet.md)); 267 actions/s on A100 ([OFT](../papers/kim-2025-openvla-oft.md)) | High: sum eps, add cost gradients, CFG; exact product needs MCMC at up to 5x cost ([Du et al.](https://arxiv.org/abs/2302.11552)) | FiLM or cross-attention; CFG needs condition dropout at training and doubles evaluations ([Ho and Salimans](https://arxiv.org/abs/2207.12598)) | Stable MSE regression; learned variances unstable ([Ho et al.](https://arxiv.org/abs/2006.11239)) | CNN head over-smooths fast action changes; latency; no confidence signal ([DP](../papers/chi-2023-diffusion-policy.md), [PoCo](../papers/policy-composition-primitives-controllers-diffusion.md)) |
| Flow matching (pi0) | Yes | pi0 73 ms per 50-step chunk, 10 Euler steps, RTX 4090 ([pi0](../papers/black-2024-pi0.md)); 292 actions/s on A100 ([OFT](../papers/kim-2025-openvla-oft.md)) | Same algebra as diffusion after converting velocity to score (derived above); no robot composition result found (unverified) | Prefix attention to VLM tokens in pi0 | FM "more stable" than score matching on images ([Lipman et al.](https://arxiv.org/abs/2210.02747)) | Temporal ensembling hurt pi0; diffusion pi0 often ignored language on DROID ([pi0](../papers/black-2024-pi0.md), [FAST](https://arxiv.org/abs/2501.09747)) |
| Autoregressive tokens (OpenVLA, pi0-FAST, VQ-BeT) | Yes, categorical per token | OpenVLA about 6 Hz on RTX 4090 ([OpenVLA](../papers/kim-2024-openvla.md)); pi0-FAST about 750 ms per 1 s chunk against about 100 ms for diffusion pi0, 30 to 60 tokens through a 2B backbone ([FAST](https://arxiv.org/abs/2501.09747), Sec. VI-E); VQ-BeT 15.1 ms, one pass ([VQ-BeT](../papers/lee-2024-vq-bet.md)) | Logit addition composes per-token conditionals, which is not the product of two chunk distributions (my reasoning, unverified) | Natural prefix conditioning on language and images | Cross-entropy; FAST reached high performance with 3x fewer steps than diffusion pi0 on table bussing ([FAST](https://arxiv.org/abs/2501.09747)) | Naive binning fails on high-frequency data; int8 OpenVLA at 1.2 Hz broke a 5 Hz controller ([OpenVLA](../papers/kim-2024-openvla.md)) |
| Energy-based implicit BC (IBC) | Yes, and sharp discontinuities | 7.22 ms on RTX 2080 Ti with 1024 samples, 3 DFO iterations, policy at 5 Hz ([IBC](../papers/florence-2021-implicit-bc.md)) | Highest: energies add exactly, hard -inf constraints possible ([energy products](../papers/policy-composition-energy-products.md)) | Late fusion of image features with the action | Unstable: loss falls while action error does not; success oscillates between checkpoints ([IBC](../papers/florence-2021-implicit-bc.md)) | DFO limited to about 5 action dimensions; autoregressive DFO needs one model per dimension |

## Worked example

Setup, in normalised action units. Skill 1 is a demonstrated leg rotation with two modes,
p_1(a) = 0.5 N(-1, 0.25^2) + 0.5 N(+1, 0.25^2). Expert 2 is a Gaussian preference,
p_2(a) = N(0.5, 0.5^2). Both are illustrative, not fitted to data. Diffusion uses the exact score of
the noised distributions, so any error comes from the head or the sampler, not from learning. VP
schedule with T = 1000 and betas linear from 1e-4 to 0.02 as in DDPM, 20,000 samples per row, numpy
seeds 0 to 5. "Near +1" is |a - 1| < 0.5, "near 0" is |a| < 0.25. W1 is the 1-Wasserstein distance
to 20,000 exact product samples. Computed 2026-09-14, rll env, numpy 2.4.6, scipy 1.17.1.

| Case | Mean | Std | Near -1 | Near 0 | Near +1 | Notes |
|---|---|---|---|---|---|---|
| Unimodal Gaussian head, or VAE with collapsed posterior | 0.000 | 1.031 | | | | density of p_1 at 0 is 0.00067 of its density at +1 |
| Ideal 1-D latent decoder f(z) = F^-1(Phi(z)) | | | | | | f(0) = 0.000, f(0.5) = 0.926, f(+-1) = +-1.119 |
| Skill 1, DDPM 1000 steps | -0.004 | 1.030 | 0.475 | 0.002 | 0.478 | |
| Skill 1, DDIM 10 steps | +0.009 | 0.936 | 0.453 | 0.038 | 0.462 | |
| Exact product p_1 p_2 | 0.837 | 0.385 | 0.032 | 0.003 | 0.920 | weights 0.039 and 0.961 at means -0.700 and +0.900, component std 0.224 |
| Collapsed-VAE Gaussian times expert 2 | 0.405 | 0.450 | | | | one Gaussian between the modes |
| Summed scores, DDPM 1000 steps | 0.544 | 0.610 | 0.141 | 0.008 | 0.758 | P(a > 0) = 0.795 vs 0.961 exact; W1 = 0.292 |
| Summed scores, DDIM 10 steps | 0.819 | 1.9e-6 | 0.000 | 0.000 | 1.000 | every sample at one point; W1 = 0.243 |
| Summed scores, DDIM 1000 steps | 0.739 | 2.3e-3 | | | | still one point; W1 = 0.270 |
| Summed scores, annealed ULA, K = 5 per level | 0.743 | 0.525 | 0.077 | 0.004 | 0.863 | P(a > 0) = 0.903; W1 = 0.093; 6000 score evaluations vs 1000 |

What it shows. ACT's test-time z = 0 decodes the median of the demonstrated distribution, and for a
symmetric bimodal skill that is the low-density point between the modes (f(0) = 0.000). Sampling z
from the prior recovers both modes. A diffusion sampler keeps the modes, and at 10 DDIM steps it
already puts 3.8 % of samples near 0. The exact product moves 96 % of the mass to the right-hand mode
and shifts that mode from 1.0 to 0.9. A Gaussian head composed with the same expert lands at 0.405,
which neither skill would produce. Summed scores under DDPM get the direction right but the weight
wrong (79.5 % vs 96.1 %). Under the deterministic DDIM sampler, summed scores collapsed every sample
to a single point at every step count tried (10, 50, 100, 1000), while skill 1 alone kept a std of
0.94. My reading of the cause, unverified: the deterministic update rescales x0_hat by an eps
whose magnitude assumes a unit-variance marginal, and the summed field is roughly twice that at high
noise, so trajectories contract. Annealed ULA, my implementation of Du et al.'s Algorithm 1 with
h = 0.1 times the level's product variance, cut W1 from 0.292 to 0.093 at 6x the evaluations.

Core of the script (full version in this session's scratchpad, not committed):

```python
T = 1000; betas = np.linspace(1e-4, 0.02, T); alphas = 1 - betas; ab = np.cumprod(alphas)
def score_mix(x, t):                        # exact score of the noised bimodal skill
    m = np.sqrt(ab[t]) * MU1[:, None]; v = ab[t] * S1**2 + 1 - ab[t]
    logp = np.log(W1[:, None]) - 0.5 * (x - m) ** 2 / v
    r = np.exp(logp - logp.max(0)); r /= r.sum(0)
    return (r * (-(x - m) / v)).sum(0)
score_g = lambda x, t: -(x - np.sqrt(ab[t]) * M2) / (ab[t] * S2**2 + 1 - ab[t])
summed = lambda x, t: score_mix(x, t) + score_g(x, t)
def ddim(score, steps, seed):
    g = np.random.default_rng(seed); x = g.normal(size=N)
    ts = np.linspace(T - 1, 0, steps).round().astype(int)
    for i, t in enumerate(ts):
        eps = -np.sqrt(1 - ab[t]) * score(x, t)
        x0 = (x - np.sqrt(1 - ab[t]) * eps) / np.sqrt(ab[t])
        abp = ab[ts[i + 1]] if i + 1 < len(ts) else 1.0
        x = np.sqrt(abp) * x0 + np.sqrt(1 - abp) * eps
    return x
```

## Gotchas

- Normalise diffusion actions to [-1, 1], not zero mean and unit variance, because DDPM clips to
  [-1, 1] ([Diffusion Policy note](../papers/chi-2023-diffusion-policy.md), Appendix A.1).
- ACT sets z = 0 at test time, so the executed chunk is a single decode, not a sample
  ([ACT note](../papers/zhao-2023-aloha-act.md)); on a symmetric bimodal skill that point sits
  between the modes (worked example).
- Classifier-free guidance doubles network evaluations per step; ADM-G at T = 256 is matched in cost
  by CFG at T = 128, where CFG had the worse FID
  ([Ho and Salimans 2022](https://arxiv.org/abs/2207.12598), Sec. 4.3).
- Summing eps from separately trained diffusion policies is not a product sampler
  ([Du et al. 2023](https://arxiv.org/abs/2302.11552), Sec. 4), and with a deterministic DDIM
  sampler it collapsed to one point in the worked example.
- Composed diffusion policies must share action space, normalisation, horizon and frequency; PoCo
  dropped dataset-statistics normalisation for this reason
  ([composition note](../papers/policy-composition-primitives-controllers-diffusion.md)).
- A Gaussian product of latent experts does not train the unimodal encoders unless single-modality
  ELBO terms are in the objective, and the quotient form needs V_2 > V_1
  ([Wu and Goodman 2018](https://arxiv.org/abs/1802.05335), Secs. 2.1 and 2.2).
- Energy-parameterised diffusion enables Metropolis correction and mixtures but doubles memory and
  compute ([Du et al. 2023](https://arxiv.org/abs/2302.11552), Sec. 6).
- Temporal ensembling hurt pi0 and was dropped ([pi0 note](../papers/black-2024-pi0.md)).

## Open questions

- Does naive eps summation fail measurably on 16- to 50-step action chunks for a real task, as it
  does in 2D and image experiments? No robot evidence was found in this pass or the PoCo read.
- Can annealed MCMC composition fit the belt budget? Two policies at 5 Hz (PoCo) times up to 5x
  sampler cost is below 1 Hz, before perception.
- Is the product normaliser Z, or disagreement between component samples, usable as a conflict
  detector for a skill contract's failure signal? For Gaussian experts Z is the overlap integral and
  is cheap; for learned skills it is intractable.
- Does converting pi0-style velocities to scores and summing them behave like diffusion
  composition at 10 Euler steps?
- Can separately trained ACT latents be composed as Gaussian experts, or does it require MVAE-style
  joint training?

## Related

- Paper notes: [Diffusion Policy](../papers/chi-2023-diffusion-policy.md), [pi0](../papers/black-2024-pi0.md), [ACT](../papers/zhao-2023-aloha-act.md), [IBC](../papers/florence-2021-implicit-bc.md), [VQ-BeT](../papers/lee-2024-vq-bet.md), [OpenVLA](../papers/kim-2024-openvla.md), [OpenVLA-OFT](../papers/kim-2025-openvla-oft.md)
- Composition: [primitives, controllers, diffusion (score addition, PoCo)](../papers/policy-composition-primitives-controllers-diffusion.md), [energy products](../papers/policy-composition-energy-products.md), [latent skills](../papers/policy-composition-latent-skills.md)
- Topics: [imitation-learning](imitation-learning.md), [vision-language-action-models](vision-language-action-models.md), [conveyor-tracking-and-visual-servoing](conveyor-tracking-and-visual-servoing.md), [arm-selection-scara-vs-six-axis](arm-selection-scara-vs-six-axis.md)

## Sources

- Kingma and Welling, Auto-Encoding Variational Bayes, arXiv v11: https://arxiv.org/abs/1312.6114 . Secs. 2 to 3, Eqs. 1 to 10, Algorithm 1.
- Higgins et al., beta-VAE, ICLR 2017: https://openreview.net/forum?id=Sy2fzU9gl ; PDF read from https://www.cs.toronto.edu/~bonner/courses/2022s/csc2547/papers/generative/disentangled-representations/beta-vae,-higgins,-iclr2017.pdf . Secs. 2 to 4, Eq. 4, Fig. 5.
- Bowman et al., Generating Sentences from a Continuous Space, 2016: https://arxiv.org/abs/1511.06349 . Secs. 3.1, 4, Table 2.
- Kingma et al., Improved Variational Inference with Inverse Autoregressive Flow, 2016: https://arxiv.org/abs/1606.04934 . Appendix C.8, Eq. 15.
- He et al., Lagging Inference Networks and Posterior Collapse, ICLR 2019: https://arxiv.org/abs/1901.05534 . Secs. 2 to 4, Algorithm 1.
- Razavi et al., Preventing Posterior Collapse with delta-VAEs, ICLR 2019: https://arxiv.org/abs/1901.03416 . Sec. 2, Eq. 1.
- Wu and Goodman, Multimodal Generative Models for Scalable Weakly-Supervised Learning, NeurIPS 2018, arXiv v3: https://arxiv.org/abs/1802.05335 . Secs. 2 to 7, Eqs. 1 to 5.
- Ho, Jain, Abbeel, Denoising Diffusion Probabilistic Models, arXiv v2: https://arxiv.org/abs/2006.11239 . Secs. 2 to 4, Eqs. 4 and 14, Table 2.
- Song et al., Score-Based Generative Modeling through SDEs, ICLR 2021: https://arxiv.org/abs/2011.13456 . Secs. 3 to 4, Eqs. 6, 7, 11, 13.
- Song, Meng, Ermon, Denoising Diffusion Implicit Models, ICLR 2021: https://arxiv.org/abs/2010.02502 . Secs. 4 to 5, Eq. 16, Table 1.
- Dhariwal and Nichol, Diffusion Models Beat GANs on Image Synthesis, 2021: https://arxiv.org/abs/2105.05233 . Sec. 4, Algorithms 1 and 2, Fig. 3.
- Ho and Salimans, Classifier-Free Diffusion Guidance, arXiv v1: https://arxiv.org/abs/2207.12598 . Secs. 2 to 4, Eq. 6, Table 1.
- Lipman et al., Flow Matching for Generative Modeling, ICLR 2023, arXiv v2: https://arxiv.org/abs/2210.02747 . Secs. 3 to 6, Theorems 1 to 3, Eqs. 20 to 23, Table 1.
- Du et al., Reduce, Reuse, Recycle, ICML 2023, arXiv v6: https://arxiv.org/abs/2302.11552 . Secs. 2 to 6, Eqs. 8 to 14, Algorithm 1, Tables 1 to 3.
- Pertsch et al., FAST: Efficient Action Tokenization for VLA Models, 2025: https://arxiv.org/abs/2501.09747 . Sec. VI-D and VI-E, Fig. 9.
