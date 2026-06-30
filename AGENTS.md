# DatasetKit — Project Context

Desktop tool for **LoRA dataset preparation**: batch-rename images in numbered order and optionally create or AI-generate Kohya/sd-scripts-compatible caption `.txt` files.

## Repository

- **GitHub:** https://github.com/JesseQuartieri/DatasetKit
- **Owner:** JesseQuartieri
- **Visibility:** Public
- **Local path:** `C:\Users\Jesse\Downloads\FileNamer` (folder name may still say FileNamer)

## Key Files

| File | Purpose |
|------|---------|
| `filenamer.py` | Main application (`DatasetKitApp` class, Tkinter UI) |
| `grok_caption.py` | xAI Grok Vision API — prompts, image resize, cost estimates |
| `settings_store.py` | Local settings (`datasetkit_settings.json`, gitignored) |
| `StartDatasetKit.bat` | Windows launcher (runs `python filenamer.py`) |
| `requirements.txt` | `tkinterdnd2`, `pillow` |
| `CHANGELOG.md` | Feature history and roadmap |
| `PENDING_JOYCAPTION_INTEGRATION.md` | Planned local JoyCaption subprocess design |
| `README.md` | User-facing docs (English) |

Note: the Python entrypoint is still named `filenamer.py` for compatibility.

## Features

### Core

1. Drag & drop images (via tkinterdnd2)
2. Browse files / select folder
3. Numbered rename with **File Base name** (e.g. `Sara_droidV02_001.png`)
4. Safe rename via temporary files (`__datasetkit_temp_*`)
5. **Open folder** button after successful rename
6. Auto-fit window on launch + Windows DPI awareness
7. List area fixed at 4 lines height

### Caption modes (After rename — radio group)

| Mode | Behavior |
|------|----------|
| `none` | Rename only |
| `empty` | Create empty `.txt` per image; optional trigger prefill `trigger, `; skips existing `.txt` |
| `grok` | Grok Vision AI captions; **overwrites** `.txt` files |

### Grok Vision (`grok` mode)

- **Grok API** section: API key (saved locally in gitignored `datasetkit_settings.json`), Test button, model radio
- **Vision max size:** 1024 / 1536 / 2048 px longest side — downscales before upload, never upscales
- **Training target:** Flux, Krea-2, SDXL, SD 1.5, Pony
- **Krea-2 only:** LoRA type (Character / Style / Concept / Lighting)
- **Non-Krea-2:** Caption focus dropdown
- Character LoRA + Krea-2: minimalist prompts (angle > pose > lighting)
- Progress bar, cost estimate, 3 retries per image, settings persisted

### Settings keys (`datasetkit_settings.json`)

```json
{
  "api_key": "",
  "model_mode": "reasoning",
  "caption_focus": "mixed",
  "training_target": "flux",
  "krea2_lora_type": "character",
  "caption_mode": "none",
  "grok_max_long_edge": 1536
}
```

## UI

- **Theme:** Modern black (`#000000`) background, white text, gray surfaces/borders
- **Primary CTA:** White `START RENAME` button
- **File Base name field:** Starts **empty**
- **UI language:** English

## Architecture notes

- Grok captioning runs in a **background thread**; UI updates via `root.after(0, ...)`
- `_apply_caption_mode_ui()` — show/hide sections; **must not** call `_fit_window()` (freeze bug fix)
- `_measure_max_shell_height()` — cached once at end of `_build_ui()`
- `image_to_data_url()` — always JPEG via Pillow; resize only if `long_edge > grok_max_long_edge`

## Backups (do not modify)

| Folder | Contents |
|--------|----------|
| `backupV01/` | Snapshot before caption features + English UI |
| `backupV02/` | Snapshot before black/white UI redesign |
| `backupV03/` | Snapshot before Grok Vision integration |

## Git Conventions

- **Commit author:** JesseQuartieri
- **Email (local repo):** `160431188+JesseQuartieri@users.noreply.github.com`
- Do **not** use `jesse.a.barrios.e@gmail.com` — maps to wrong GitHub account (JesseBarrios1)
- Do **not push to GitHub** unless the user explicitly asks
- **Never commit** `datasetkit_settings.json` — contains API keys; only `datasetkit_settings.example.json` goes in the repo

## User Preferences

- Communicate with the user in **Spanish** unless they write in English
- Create backup folders before major changes when requested
- Keep changes focused — no drive-by refactors
- UI language: **English**

## Common Tasks

| Task | Where |
|------|-------|
| UI tweaks | `_build_ui()`, `UI_THEME` in `filenamer.py` |
| Grok prompts / image resize | `grok_caption.py` |
| Empty caption files | `_create_caption_files()` |
| Grok batch flow | `_run_grok_captions_async()` |
| Rename logic | `_rename_files()` |
| Settings | `settings_store.py` |
| Test locally | `StartDatasetKit.bat` |

## Tech Stack

- Python 3.8+ / Tkinter / tkinterdnd2 / Pillow
- xAI Grok Vision API (urllib, no extra SDK)
- Windows-focused (`.bat` launcher, `os.startfile`)

## Planned

- **JoyCaption local** — subprocess worker; see `PENDING_JOYCAPTION_INTEGRATION.md`