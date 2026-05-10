# Automated Image & Video Generation — Implementation Plan (Small Startup)

> Stack goal: Fully automated pipeline. Input a prompt/brief → system generates
> image or video → stores and delivers it. Runs on a schedule or on-demand.
> No manual intervention after setup.

---

## Tool Decision: What to Use for Automation

### The Main Options

| Tool | Type | Best For | Cost |
|---|---|---|---|
| **n8n** | Open-source workflow automation | Visual workflows, webhooks, scheduling, integrations | Free self-hosted |
| **Apache Airflow** | Open-source DAG orchestrator | Complex scheduled pipelines, data-engineering style | Free self-hosted |
| **Prefect** | Open-source workflow orchestrator | Python-native, easier than Airflow, good UI | Free self-hosted / $0 cloud tier |
| **Temporal.io** | Open-source durable execution engine | Long-running tasks, retries, fault tolerance | Free self-hosted |
| **Custom Python + cron** | DIY | Simple schedules, full control, minimal overhead | Free |
| **ComfyUI API directly** | Built-in REST API | When ComfyUI is your generation engine | Free |

### Recommendation for a Small Startup

**Use n8n + ComfyUI API + Python scripts.**

- **n8n** handles triggers, scheduling, routing, and integrations (Slack notifications, Google Sheets input, email delivery, etc.) — no code needed for the workflow layer
- **ComfyUI** exposes a REST API — you call it programmatically with a JSON workflow payload
- **Python** handles anything custom (prompt building, post-processing, uploading)
- This combo is used by dozens of small AI content studios in 2025

Do NOT use Airflow for this — it's over-engineered for a 5–50 items/day use case and has a steep ops burden.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   TRIGGER LAYER                      │
│  Schedule (cron) │ Webhook │ Google Sheet │ API call │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│               ORCHESTRATION (n8n)                    │
│  - Reads input (prompt, style, type: image/video)    │
│  - Calls generation service                          │
│  - Handles retries, notifications, routing           │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│            GENERATION SERVICE (Python API)           │
│  - Wraps ComfyUI REST API                           │
│  - Selects model based on type (image vs video)     │
│  - Queues jobs, polls for completion                 │
│  - Returns file path / URL                          │
└─────────────────────┬───────────────────────────────┘
                      │
        ┌─────────────┴────────────┐
        ▼                          ▼
┌───────────────┐         ┌────────────────┐
│  GPU Worker   │         │  GPU Worker    │
│ (ComfyUI)     │         │ (ComfyUI)      │
│ Image models  │         │ Video models   │
│ FLUX.1 schnell│         │ LTX-Video /    │
│ SDXL          │         │ Wan 2.1 14B    │
└───────┬───────┘         └───────┬────────┘
        └─────────────┬───────────┘
                      ▼
┌─────────────────────────────────────────────────────┐
│                  STORAGE LAYER                       │
│         S3 / Cloudflare R2 / Local NAS               │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                 DELIVERY LAYER                       │
│  Webhook callback │ Slack/Discord │ Dashboard │ CDN  │
└─────────────────────────────────────────────────────┘
```

---

## Phase-by-Phase Implementation Plan

---

### Phase 1 — Core Generation Service (Week 1–2)

**Goal:** Get ComfyUI running and callable via API.

#### Step 1: Set up ComfyUI on RunPod

```bash
# On RunPod, use the official ComfyUI template
# Or SSH in and run:
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
pip install -r requirements.txt
python main.py --listen 0.0.0.0 --port 8188
```

ComfyUI exposes a REST API at `http://<host>:8188`.

#### Step 2: Build your Python generation client

```python
# generation_client.py
import httpx
import json
import uuid
import asyncio

COMFY_URL = "http://your-runpod-ip:8188"

async def generate_image(prompt: str, negative_prompt: str = "") -> str:
    """Submit a Flux.1 Schnell job to ComfyUI, return output filename."""
    workflow = build_flux_workflow(prompt, negative_prompt)
    client_id = str(uuid.uuid4())

    async with httpx.AsyncClient() as client:
        # Queue the prompt
        resp = await client.post(f"{COMFY_URL}/prompt", json={
            "prompt": workflow,
            "client_id": client_id
        })
        prompt_id = resp.json()["prompt_id"]

        # Poll for completion
        while True:
            history = await client.get(f"{COMFY_URL}/history/{prompt_id}")
            data = history.json()
            if prompt_id in data:
                outputs = data[prompt_id]["outputs"]
                # Extract image filename from outputs
                for node_id, node_output in outputs.items():
                    if "images" in node_output:
                        img = node_output["images"][0]
                        return img["filename"]
            await asyncio.sleep(2)

def build_flux_workflow(prompt: str, negative_prompt: str) -> dict:
    # Export your ComfyUI workflow as JSON (via Save (API Format) button)
    # and paste it here, substituting the prompt value dynamically
    with open("workflows/flux_schnell.json") as f:
        workflow = json.load(f)
    # Inject prompt into the CLIPTextEncode node
    workflow["6"]["inputs"]["text"] = prompt
    workflow["7"]["inputs"]["text"] = negative_prompt
    return workflow
```

**Key insight:** Design your ComfyUI workflows visually in the UI, then export them as JSON (`Save (API Format)`). Your Python code just swaps in the dynamic values (prompt, seed, resolution) and submits the JSON.

#### Step 3: Wrap in a FastAPI service

```python
# main.py
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from generation_client import generate_image, generate_video
import boto3

app = FastAPI()

class GenerationRequest(BaseModel):
    type: str          # "image" or "video"
    prompt: str
    negative_prompt: str = ""
    webhook_url: str = ""   # optional: POST result here when done

@app.post("/generate")
async def generate(req: GenerationRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    background_tasks.add_task(run_generation, job_id, req)
    return {"job_id": job_id, "status": "queued"}

@app.get("/status/{job_id}")
async def status(job_id: str):
    # Return job status from DB/Redis
    ...

async def run_generation(job_id: str, req: GenerationRequest):
    if req.type == "image":
        filename = await generate_image(req.prompt, req.negative_prompt)
    else:
        filename = await generate_video(req.prompt)

    # Upload to S3
    url = upload_to_s3(filename)

    # Fire webhook if provided
    if req.webhook_url:
        async with httpx.AsyncClient() as client:
            await client.post(req.webhook_url, json={"job_id": job_id, "url": url})
```

Deploy this FastAPI service on a small VPS (Hetzner, DigitalOcean — $5–10/month). It acts as the **job broker** between n8n and ComfyUI.

---

### Phase 2 — Orchestration with n8n (Week 2–3)

**Goal:** Automate triggers, routing, retries, notifications.

#### Install n8n (self-hosted)

```bash
# Docker (recommended)
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -e N8N_BASIC_AUTH_USER=admin \
  -e N8N_BASIC_AUTH_PASSWORD=yourpassword \
  -v n8n_data:/home/node/.n8n \
  n8nio/n8n
```

Access at `http://localhost:5678`.

#### Core n8n Workflows to Build

**Workflow 1: Scheduled Daily Generation**
```
Schedule Trigger (9am daily)
  → Read Google Sheet (today's prompts/content calendar)
  → Loop over each row
  → HTTP Request → POST /generate (your FastAPI)
  → Wait for webhook callback
  → Upload URL → Update Google Sheet row
  → Send Slack notification with preview
```

**Workflow 2: On-Demand via Webhook**
```
Webhook Trigger (POST /webhook/generate)
  → Validate input
  → HTTP Request → POST /generate
  → Respond immediately with job_id
  → (Async) Wait for completion webhook → notify requester
```

**Workflow 3: Content Calendar from Notion/Airtable**
```
Schedule Trigger (every 6 hours)
  → Notion API → Get pages with status="pending"
  → For each: build prompt from template + page fields
  → POST /generate
  → On completion: update Notion page status="done", attach asset URL
```

**Workflow 4: Retry on Failure**
```
HTTP Request → POST /generate
  → On error: wait 60s → retry up to 3 times
  → On final failure: Slack alert to #ops channel
```

#### n8n is ideal here because:
- Visual, no-code workflow builder
- Built-in HTTP, webhook, Google Sheets, Notion, Slack, Discord nodes
- Cron scheduling built-in
- Self-hosted = no per-task fees
- Easy retry/error handling

---

### Phase 3 — Storage & Delivery (Week 3)

#### Storage: Cloudflare R2 (Recommended)

Cloudflare R2 is S3-compatible, has **zero egress fees**, and costs $0.015/GB/month.

```python
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url="https://<account_id>.r2.cloudflarestorage.com",
    aws_access_key_id="your_r2_key",
    aws_secret_access_key="your_r2_secret",
)

def upload_to_r2(local_path: str, key: str) -> str:
    s3.upload_file(local_path, "your-bucket", key)
    return f"https://your-custom-domain.com/{key}"
```

#### Delivery options

| Use case | Tool |
|---|---|
| Internal dashboard | Simple Next.js or SvelteKit page reading from R2 |
| Client delivery | Signed URL (expires in 7 days) via R2 |
| Social posting | n8n → Buffer API or direct platform API |
| Team notification | n8n → Slack / Discord with thumbnail embed |

---

### Phase 4 — Prompt Management (Week 3–4)

For a startup, prompts should be managed as data, not hardcoded.

#### Option A: Google Sheets (simplest)

| Column | Value |
|---|---|
| Date | 2025-05-15 |
| Type | video |
| Prompt | A serene mountain lake at golden hour, cinematic |
| Style | cinematic, 4K |
| Status | pending |
| Output URL | (filled by automation) |

n8n reads this sheet daily and processes all `pending` rows.

#### Option B: Notion Database (recommended for teams)

- Each page = one generation job
- Properties: Type, Prompt, Style, Status, Output URL, Requester
- n8n polls Notion API every hour for new `pending` entries

#### Option C: Custom Admin UI (if you scale)

Build a simple SvelteKit or Next.js form → submits to your FastAPI `/generate` endpoint → shows job status and output.

---

### Phase 5 — GPU Cost Optimization (Week 4)

Since you're on cloud GPUs, keep costs near zero when idle.

#### Strategy 1: RunPod Serverless

- No pod running when idle — spins up in ~30 seconds on request
- Pay per second of compute
- Ideal for async workflows where a 30-second cold start is acceptable

```python
# Hit RunPod serverless endpoint instead of a fixed pod
RUNPOD_ENDPOINT = "https://api.runpod.ai/v2/your-endpoint-id/run"

async def generate_via_runpod(payload: dict) -> str:
    headers = {"Authorization": f"Bearer {RUNPOD_API_KEY}"}
    resp = httpx.post(RUNPOD_ENDPOINT, json={"input": payload}, headers=headers)
    job_id = resp.json()["id"]

    # Poll for result
    while True:
        result = httpx.get(f"{RUNPOD_ENDPOINT}/status/{job_id}", headers=headers)
        if result.json()["status"] == "COMPLETED":
            return result.json()["output"]["url"]
        await asyncio.sleep(5)
```

#### Strategy 2: Pod auto-shutdown

If using a fixed RunPod pod, add a shutdown timer:

```python
# After all jobs complete, if queue is empty for 10 minutes, stop the pod
import subprocess

def shutdown_if_idle(idle_minutes: int = 10):
    # RunPod pods can be stopped via their API
    if queue_is_empty() and idle_for(idle_minutes):
        requests.post(
            f"https://api.runpod.io/v2/pod/{POD_ID}/stop",
            headers={"Authorization": f"Bearer {API_KEY}"}
        )
```

---

## Full Tech Stack Summary

| Layer | Tool | Why |
|---|---|---|
| Workflow automation | **n8n** (self-hosted) | Visual, free, great integrations |
| Generation API | **FastAPI** (Python) | Thin wrapper over ComfyUI |
| Image generation | **ComfyUI + FLUX.1 schnell** | Fastest, Apache 2.0, API-friendly |
| Video generation | **ComfyUI + LTX-Video / Wan 2.1** | Apache 2.0, runs on 24GB |
| GPU compute | **RunPod Serverless** | Pay-per-second, no idle cost |
| Storage | **Cloudflare R2** | Zero egress, S3-compatible, cheap |
| Prompt management | **Notion** or Google Sheets | Easy for small team |
| Notifications | **Slack / Discord** via n8n | Free, instant |
| VPS (for n8n + FastAPI) | **Hetzner CX21** (~$5/mo) | Cheap, reliable |

---

## Estimated Monthly Cost (5–10 items/day)

| Item | Cost |
|---|---|
| RunPod Serverless (GPU compute) | ~$5–15/month |
| Cloudflare R2 storage | ~$1–2/month |
| Hetzner VPS (n8n + FastAPI) | ~$5/month |
| n8n self-hosted | Free |
| **Total** | **~$11–22/month** |

---

## Phased Timeline

| Week | Milestone |
|---|---|
| Week 1 | ComfyUI running on RunPod, image generation working via API |
| Week 2 | FastAPI generation service deployed, video generation added |
| Week 3 | n8n installed, scheduling workflow live, Notion/Sheets integration |
| Week 4 | R2 storage, delivery webhooks, Slack notifications, idle auto-shutdown |
| Week 5+ | Custom admin UI (optional), prompt templates, batch scheduling |

---

## What NOT to Use

| Tool | Why not |
|---|---|
| **Apache Airflow** | Over-engineered for this scale; heavy to operate |
| **Zapier / Make** | Per-task fees add up; limited AI/GPU integration |
| **AWS Step Functions** | Vendor lock-in; complex for simple needs |
| **LangChain / LlamaIndex** | These are for LLM pipelines, not image/video generation |
| **Celery** | Fine for task queues but adds Redis dependency with more ops overhead than needed |

---

## Key Repos & Docs

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) — generation engine
- [ComfyUI API docs](https://github.com/comfyanonymous/ComfyUI/blob/master/server.py) — REST API reference
- [n8n docs](https://docs.n8n.io) — workflow automation
- [RunPod Serverless](https://docs.runpod.io/serverless/overview) — GPU-on-demand
- [Cloudflare R2](https://developers.cloudflare.com/r2/) — storage
- [Wan2GP](https://github.com/deepbeepmeep/Wan2GP) — video on consumer GPUs
