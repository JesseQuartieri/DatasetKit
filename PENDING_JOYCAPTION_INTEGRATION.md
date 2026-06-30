# Pending: JoyCaption local integration (Python subprocess)

**Status:** Planned — not implemented  
**Target app:** DatasetKit (`filenamer.py`)  
**Approach:** Long-lived Python worker subprocess (not embedded in Tkinter, not HTTP server)  
**Author context:** User has RTX 5090 — VRAM is not a constraint; prefer quality (`bf16`) over quantization.

---

## Goal

Add JoyCaption as an **alternative local caption engine** alongside the existing Grok Vision flow. User selects it under **After rename**, renames images as today, then captions are generated offline without API cost.

```
After rename:
  ○ Rename only
  ○ Create empty .txt files
  ○ Full captioning with Grok Vision        ← cloud (current)
  ○ Full captioning with JoyCaption (local) ← pending
```

Grok remains the default for strict custom rules (e.g. Krea-2 Character minimal captions). JoyCaption covers free/local batch captioning with JoyCaption-native prompt modes.

---

## Why subprocess (not in-process)

| Approach | Verdict |
|----------|---------|
| Load `transformers` inside `filenamer.py` | **Reject** — blocks UI, huge RAM/VRAM footprint in same process, fragile on Windows |
| HTTP server (Gradio / vLLM) | Viable, but extra port/lifecycle management |
| **Dedicated worker subprocess** | **Chosen** — model loads once, DatasetKit stays lightweight, UI stays responsive |

DatasetKit orchestrates; the worker owns the GPU and the model.

---

## Reference projects

| Resource | URL |
|----------|-----|
| Official repo | https://github.com/fpgaminer/joycaption |
| Gradio app (batch reference) | https://github.com/fpgaminer/joycaption/tree/main/gradio-app |
| Model (latest) | https://huggingface.co/fancyfeast/llama-joycaption-beta-one-hf-llava |
| Alpha Two (legacy name “JoyCaption2”) | https://huggingface.co/fancyfeast/llama-joycaption-alpha-two-hf-llava |

**Recommendation for 5090:** Start with **JoyCaption Beta One** in `bfloat16`. Alpha Two only if a specific workflow requires it.

---

## Architecture

```
┌─────────────────────────────────────┐
│  DatasetKit (filenamer.py)          │
│  Tkinter UI + rename + threading    │
└──────────────┬──────────────────────┘
               │ spawn / reuse
               ▼
┌─────────────────────────────────────┐
│  joycaption_worker.py               │
│  - loads model once at startup      │
│  - reads JSON lines from stdin      │
│  - writes JSON lines to stdout      │
│  - optional progress on stderr      │
└──────────────┬──────────────────────┘
               │
               ▼
         CUDA / RTX 5090
```

### Worker lifecycle

1. **First JoyCaption batch** (or explicit “Test JoyCaption”): DatasetKit spawns `python joycaption_worker.py`.
2. Worker prints `{"event":"ready"}` after model load (may take 30–90s first run).
3. DatasetKit sends one JSON job per image on stdin; worker replies with caption or error.
4. Worker stays alive for the session to avoid reload cost between images.
5. On app exit (or worker crash): terminate subprocess.

Alternative for v1: **one subprocess per batch** (simpler, slower). Prefer **persistent worker** given 5090 and large batches.

---

## IPC protocol (draft)

Newline-delimited JSON on stdin/stdout. One request → one response.

### Request (DatasetKit → worker)

```json
{
  "id": "job-001",
  "image_path": "C:/datasets/img_001.png",
  "prompt": "Write a straightforward caption for this image within 12 words.",
  "max_new_tokens": 128,
  "temperature": 0.6,
  "top_p": 0.9
}
```

### Response (worker → DatasetKit)

```json
{
  "id": "job-001",
  "ok": true,
  "caption": "low angle side view of a kneeling figure on a platform"
}
```

### Error response

```json
{
  "id": "job-001",
  "ok": false,
  "error": "CUDA out of memory"
}
```

### Control messages

```json
{"cmd": "ping"}
{"cmd": "shutdown"}
```

Worker events on stderr (logging only, not parsed by UI):

```
{"event":"loading","detail":"Downloading model..."}
{"event":"ready","model":"fancyfeast/llama-joycaption-beta-one-hf-llava"}
```

---

## New files (planned)

| File | Purpose |
|------|---------|
| `joycaption_worker.py` | Subprocess entrypoint; loads model, caption loop |
| `joycaption_client.py` | Spawn worker, send jobs, parse responses, retries |
| `joycaption_prompts.py` | Prompt presets + Krea-2 minimal custom prompt |
| `joycaption_requirements.txt` | Optional deps (`torch`, `transformers`, etc.) — **not** merged into main `requirements.txt` by default |

Keep `grok_caption.py` unchanged; parallel module layout.

---

## Integration points in `filenamer.py`

Mirror the existing Grok path:

| Grok (today) | JoyCaption (planned) |
|--------------|----------------------|
| `_run_grok_captions_async()` | `_run_joycaption_async()` |
| `_on_grok_caption_done()` | `_on_joycaption_done()` |
| `_show_grok_progress()` | Reuse or rename to `_show_caption_progress()` |
| `caption_mode == "grok"` | `caption_mode == "joycaption"` |
| `grok_options_section` UI | `joycaption_options_section` UI |

Flow after rename (same as Grok):

1. Rename images → get final `image_paths`
2. If mode is `joycaption`, call async worker loop
3. `apply_trigger_prefix(caption, trigger)` — reuse from `grok_caption.py`
4. Write/overwrite `.txt` next to each image
5. Show summary in status + dialog

Threading: worker I/O in background thread; UI updates via `root.after(0, ...)`.

---

## UI additions (planned)

### Caption mode

- New radio: **Full captioning with JoyCaption (local)**

### JoyCaption options section (shown when mode = joycaption)

| Control | Notes |
|---------|-------|
| **Caption type** | Straightforward, Descriptive, SD prompt, Booru-like tags, Custom |
| **Custom prompt** | Text area; enabled when type = Custom |
| **Word limit** | Optional spinbox (maps to JoyCaption `{word_count}` prompts) |
| **Extra options** | Checkboxes mirroring JoyCaption extras (camera angle, lighting, etc.) |
| **Preset: Krea-2 Character minimal** | Applies same rules as `grok_caption.py` Character LoRA prompt |
| **Quantization** | `bf16` (default on 5090), `8-bit`, `nf4` |
| **Test JoyCaption** | Loads worker, runs ping + single test image |
| **Worker status** | Idle / Loading model / Ready / Error |

### Grok API section

- Hide or collapse when JoyCaption is selected (no API key needed).

### Settings (`settings_store.py`)

```json
{
  "joycaption_model": "beta_one",
  "joycaption_quant": "bf16",
  "joycaption_caption_type": "straightforward",
  "joycaption_custom_prompt": "",
  "joycaption_word_limit": 12,
  "joycaption_extras": []
}
```

---

## Prompt presets

### Built-in (from JoyCaption docs)

- **Straightforward** — good general LoRA captions
- **Descriptive** — longer prose
- **Stable Diffusion prompt** — tag-like / natural mix
- **Booru-like tag list** — anime-oriented

### Custom: Krea-2 Character minimal

Reuse the same rules already in `grok_caption.py` (`_KREA2_INSTRUCTIONS["character"]`) as a JoyCaption custom system-style prompt, e.g.:

```
Describe only camera angle. Pose only if obvious. Omit lighting unless unusual.
5-10 words. Never describe face, body, clothing, or identity.
```

**Note:** JoyCaption is less strict than Grok on instruction following; expect occasional verbosity. User can edit `.txt` files after batch.

---

## Dependencies & setup (planned)

### Isolated environment (recommended)

JoyCaption deps must **not** bloat the minimal DatasetKit install. Options:

1. **Separate venv** — `DatasetKit/venv_joycaption/` + setup script
2. **Pinokio / manual** — user installs once; DatasetKit points to `python` path in settings

### `joycaption_requirements.txt` (draft)

```
torch
transformers
accelerate
pillow
safetensors
```

Optional: `bitsandbytes` (8-bit / 4-bit), `liger-kernel` (speed).

### First-run behavior

- Detect CUDA + GPU name (show “RTX 5090 detected” in Test)
- Hugging Face model download (~several GB) on first caption
- Cache under `%USERPROFILE%\.cache\huggingface`

### `StartDatasetKit.bat`

No change required initially. Optional later: `SetupJoyCaption.bat` to create venv and pip install.

---

## Error handling

| Case | Behavior |
|------|----------|
| Worker not found / wrong Python | Clear error + link to setup doc |
| Model still loading | Disable START, show “Loading JoyCaption model…” |
| Worker crash mid-batch | Retry spawn once; report which images failed |
| CUDA unavailable | Block JoyCaption mode with explanation |
| Per-image failure | Continue batch; list failures like Grok path |

Retries: 2–3 per image on transient errors (OOM unlikely on 5090 with bf16 single-image inference).

---

## Implementation phases

### Phase 1 — Worker proof of concept
- [ ] `joycaption_worker.py` loads Beta One bf16
- [ ] stdin/stdout JSON for single image
- [ ] Manual CLI test: `echo {...} | python joycaption_worker.py`

### Phase 2 — Client module
- [ ] `joycaption_client.py` persistent subprocess
- [ ] ping / shutdown / batch loop
- [ ] Timeout + crash recovery

### Phase 3 — UI wire-up
- [ ] New caption mode radio
- [ ] JoyCaption options section
- [ ] Test button + status line
- [ ] Settings persistence

### Phase 4 — Batch integration
- [ ] `_run_joycaption_async()` after rename
- [ ] Progress bar + summary dialog
- [ ] Trigger prefix reuse

### Phase 5 — Polish
- [ ] Krea-2 minimal preset
- [ ] Optional `SetupJoyCaption.bat`
- [ ] README section
- [ ] AGENTS.md update

---

## Open questions (decide before coding)

1. **Beta One vs Alpha Two** — default Beta One unless user requests legacy.
2. **venv path** — fixed relative path vs user-configurable in settings.
3. **Overwrite policy** — same as Grok (overwrite `.txt` on caption run).
4. **Rename `grok_progress_*` widgets** to generic `caption_progress_*` when both engines share UI.
5. **Ship worker in repo** vs document-only setup — ship `joycaption_worker.py` + optional requirements; model stays Hugging Face download.

---

## Hardware note (RTX 5090)

- `bfloat16` full model: comfortable
- Batch size in worker: start with **1 image at a time** (simplest IPC); optimize later with internal micro-batching if Gradio batch code is ported
- No need for 4-bit/nf4 unless testing laptop portability

---

## Current focus

**Keep testing Grok + Krea-2 Character minimal captions** with the updated prompts in `grok_caption.py`. JoyCaption integration is documented here for when Grok behavior is validated on the Sara_droidV02 dataset.

---

*Last updated: 2026-06-29*