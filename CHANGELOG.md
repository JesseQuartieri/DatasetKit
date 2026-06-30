# DatasetKit — Changelog

All notable changes to this project. Dates use the local development timeline.

---

## [Unreleased] — 2026-06-29

### Added

- **Grok Vision AI captioning** — fourth caption path via xAI API (`grok_caption.py`)
  - Models: `grok-4.20-0309-reasoning` / `grok-4.20-0309-non-reasoning`
  - API key field + **Test** connection button
  - Batch captioning after rename with progress bar
  - Cost estimate before run + actual token/cost summary after
  - Up to 3 retries per image on transient errors
- **After rename** radio group (replaces competing checkboxes):
  - Rename only
  - Create empty `.txt` files
  - Full captioning with Grok Vision
- **Caption focus** dropdown (Flux, SDXL, SD 1.5, Pony targets)
- **Training target** dropdown including **Krea-2**
- **Krea-2 LoRA type** selector: Character / Style / Concept / Lighting
- **Krea-2 Character minimal prompts** — camera angle first, conservative pose, omit lighting unless unusual; 5–10 word target
- **Vision max size** control (Grok API section):
  - `1024 px — save tokens`
  - `1536 px — balanced` (default)
  - `2048 px — max detail`
- **Smart image resize** before Grok upload (`grok_caption.py`):
  - Downscales only when longest side exceeds chosen limit
  - Never upscales (e.g. 512×1024 stays 512×1024)
  - Converts to JPEG for API; original files on disk unchanged
  - EXIF orientation correction
- **Local settings** persistence (`settings_store.py` → `datasetkit_settings.json`, gitignored)
- **Pending design doc:** `PENDING_JOYCAPTION_INTEGRATION.md` (local JoyCaption via Python subprocess)

### Changed

- App branding: **FileNamer** → **DatasetKit**
- UI label: **Base name** → **File Base name**
- Window auto-sizing: one-time max shell height cache (no runtime mode toggling)
- List area fixed height (4 lines)
- Dependencies: added `pillow>=10.0.0` for image processing

### Security

- API key saved locally in `datasetkit_settings.json` (gitignored); `datasetkit_settings.example.json` added for GitHub clones

### Fixed

- **Startup freeze** — infinite loop between `_fit_window()` and `_on_caption_mode_change()` removed
- **Training target dropdown** — now enables to `readonly` when Grok mode is active (was stuck `disabled`)

---

## [0.3.0] — Black UI + basic captions

- Modern black/white theme (`UI_THEME`)
- Windows DPI awareness + auto-fit window on launch
- Optional empty caption `.txt` files with trigger word prefill (`trigger, `)
- Safe rename via `__datasetkit_temp_*` temp files
- **Open folder** after successful rename
- Snapshot: `backupV03/`

---

## [0.2.0] — Caption files (pre-Grok)

- Checkbox for caption `.txt` creation
- Trigger word support
- Skip existing `.txt` files
- Snapshot: `backupV02/`

---

## [0.1.0] — Initial rename tool

- Drag & drop, browse, folder load
- Numbered batch rename
- Snapshot: `backupV01/`

---

## Roadmap

| Item | Status |
|------|--------|
| Grok Vision + Krea-2 minimal captions | Done (testing) |
| Vision max size selector | Done |
| JoyCaption local subprocess integration | Planned — see `PENDING_JOYCAPTION_INTEGRATION.md` |
| Push latest changes to GitHub | Pending user request |

---

## Key modules (current)

| File | Role |
|------|------|
| `filenamer.py` | Tkinter UI, rename flow, Grok batch orchestration |
| `grok_caption.py` | xAI API, prompts, image prep, cost estimates |
| `settings_store.py` | Local JSON settings |
| `StartDatasetKit.bat` | Windows launcher |
| `requirements.txt` | `tkinterdnd2`, `pillow` |