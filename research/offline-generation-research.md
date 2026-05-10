# Offline Image & Video Generation — Research Report (2025)

> Goal: Run local/offline image and video generation with no external APIs.
> Volume: 5–10 items/day. Full control over output.

---

## 1. Best Image Generation Models

| Model | VRAM | License | Notes |
|---|---|---|---|
| **FLUX.1 [schnell]** | 12GB (GGUF) / 16GB (FP8) | Apache 2.0 | Best commercial pick — fast (4 steps), near top quality |
| **FLUX.1 [dev]** | 16GB (FP8) / 24GB (FP16) | Non-commercial | Highest quality; needs paid license for commercial use |
| **SDXL / Juggernaut XL** | 8GB | RAIL-M (commercial OK) | Huge fine-tune ecosystem; solid fallback if VRAM limited |
| **SD 3.5 Large** | 18–24GB | Stability AI (free <$1M/yr) | Good text rendering, secondary tier |

**Recommendation:** Start with **FLUX.1 [schnell]** — Apache 2.0, runs on 16GB FP8, 2–4 sec/image on an RTX 4090.

---

## 2. Best Video Generation Models

| Model | VRAM (optimized) | License | Gen Time (RTX 4090) |
|---|---|---|---|
| **Wan 2.1/2.2 14B** | 8GB (480p GGUF), 24GB (720p FP8) | Apache 2.0 | ~4–5 min / 5-sec clip at 480p |
| **LTX-Video** | 12–16GB | Apache 2.0 | ~90 sec/clip at 720p — fastest |
| **HunyuanVideo 1.5** | 8GB (FP8 + offload) | Tencent Community | ~6 min/clip; best motion quality |
| **CogVideoX-5B** | 16–24GB | Apache 2.0 | Best image-to-video quality |

**Recommendations:**
- **Speed / iteration:** LTX-Video (90 sec, 720p)
- **Best quality:** Wan 2.1 14B — use [Wan2GP](https://github.com/deepbeepmeep/Wan2GP) for low-VRAM optimization

---

## 3. Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| GPU VRAM | 16GB (images only) | 24GB (RTX 3090 / 4090) — runs everything |
| System RAM | 32GB | 64GB (video models offload to RAM) |
| CPU | Any modern 8-core | Doesn't matter much for inference |
| Storage | 100GB SSD | 500GB+ NVMe (models are large) |

**Notes:**
- CPU-only inference is not practical — 10–60 min/image
- FP8/GGUF quantization lets a 24GB card run models that formerly needed 80GB (A100)
- RTX 4090 or RTX 3090 is the sweet spot for Wan 2.1, LTX-Video, and Flux at full quality

---

## 4. Rent vs. Buy — Break-Even Analysis

**Estimated active GPU time:** 5–10 items/day ≈ 30–60 min/day

| Option | Annual Cost |
|---|---|
| Vast.ai RTX 4090 spot | ~$40–75/year |
| RunPod Serverless | ~$40–75/year |
| RunPod on-demand ($0.69/hr) | ~$130/year |
| Own RTX 4090 workstation (new) | ~$875/year (hardware amortized over 4 years) |
| Own used RTX 3090 | ~$300/year (amortized) |

**Break-even for buying an RTX 4090 workstation vs. cloud: 28–56 years at this volume.**

**Verdict: Rent. Decisively.**

The only reasons to buy:
- Strict offline / privacy requirement (no cloud)
- You'd use the GPU for other things (gaming, other AI work)
- You already have a desktop and just need to add a GPU (~$800–1,000 used RTX 3090)

---

## 5. How Content Companies Handle This

| Type | Approach |
|---|---|
| Midjourney, Runway, Pika | Proprietary models on private data centers with thousands of A100/H100s — fully custom inference stacks |
| Small studios / agencies | 1–4 GPU workstations on-prem with ComfyUI; cloud for burst jobs |
| Solo creators / small teams | RunPod or Vast.ai + ComfyUI; pay per use |
| Hybrid | Local GPU for iteration/testing, cloud for final high-quality renders |

### Standard Open-Source Production Stack

| Layer | Tool |
|---|---|
| Pipeline UI | **ComfyUI** — dominant; node-based; fastest; supports images + video natively |
| Alternative GUI | **SD WebUI Forge** — easier for beginners; 30–75% faster than A1111 |
| Video nodes | ComfyUI-WanVideo, AnimateDiff, VideoHelperSuite |
| Low-VRAM video | **Wan2GP** (GitHub) — enables Wan/HunyuanVideo on consumer 24GB cards |
| Managed cloud ComfyUI | RunComfy, Comfy Cloud, ViewComfy |

---

## 6. Practical Recommendation (5–10 Items/Day)

### Option A — Cloud (Recommended)

**RunPod Serverless + ComfyUI + RTX 4090**

1. Create a [RunPod](https://runpod.io) account — use their pre-built ComfyUI template
2. Pick an RTX 4090 pod (Community Cloud: $0.34/hr, or Serverless: pay-per-second)
3. Load **FLUX.1 [schnell]** for images, **LTX-Video** for fast video, **Wan 2.1 14B** for quality video
4. Generate your 5–10 items, shut down the instance
5. Total cost: **~$5–10/month maximum**

### Option B — Fully Offline (Privacy / No Cloud)

1. Buy a **used RTX 3090** (~$800–1,000) — fits any existing desktop
2. Install **ComfyUI** (Windows or Linux)
3. Use **Wan2GP** for running video models optimally on 24GB
4. Models to download: FLUX.1 [schnell] (images), LTX-Video or Wan 2.1 14B GGUF (video)

---

## Quick Reference

| Decision | Answer |
|---|---|
| Best image model (commercial) | FLUX.1 [schnell] (Apache 2.0) |
| Best image model (quality, non-commercial) | FLUX.1 [dev] |
| Best video model (quality) | Wan 2.1/2.2 14B (Apache 2.0) |
| Best video model (speed) | LTX-Video (Apache 2.0) |
| Minimum viable GPU | RTX 3090 or RTX 4090 (24GB VRAM) |
| Best pipeline UI | ComfyUI |
| Buy vs. rent at 5–10 items/day | **Rent** — cloud is 10–20x cheaper at this volume |
| Cheapest cloud option | Vast.ai spot or RunPod Serverless (~$40–75/year) |
| Break-even for buying | 28–56 years at this usage volume |

---

## Key Resources

- [Wan2GP — GPU-poor video generation tool](https://github.com/deepbeepmeep/Wan2GP)
- [RunPod](https://runpod.io) — GPU cloud with ComfyUI templates
- [Vast.ai](https://vast.ai) — cheapest GPU marketplace
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) — open-source pipeline UI
- [FLUX.1 models — Black Forest Labs](https://huggingface.co/black-forest-labs)
- [Wan 2.1 — Alibaba](https://github.com/Wan-Video/Wan2.1)
- [LTX-Video — Lightricks](https://huggingface.co/Lightricks/LTX-Video)
