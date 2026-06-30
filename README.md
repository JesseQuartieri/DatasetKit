# DatasetKit

A desktop tool to prepare image datasets for LoRA training. Rename images in numbered order and optionally create or AI-generate caption `.txt` files (Kohya / sd-scripts compatible).

## Features

### Rename

- Drag and drop images into the app
- Browse files or select an entire folder
- Rename with a numbered sequence (e.g. `Sara_droidV02_001`, `Sara_droidV02_002`, …)
- Safe rename via temporary files (no data loss on failure)
- **Open folder** when done
- Formats: JPG, PNG, GIF, BMP, WebP, TIFF, ICO, HEIC, HEIF, AVIF

### Captions

**After rename** — choose one:

| Mode | What it does |
|------|----------------|
| **Rename only** | Images only |
| **Create empty .txt files** | One `.txt` per image; optional trigger prefill (`yourword, `); skips existing files |
| **Full captioning with Grok Vision** | xAI writes captions and overwrites `.txt` files |

### Grok Vision

- xAI API key + connection test
- Models: `grok-4.20-0309-reasoning` / `grok-4.20-0309-non-reasoning`
- **Vision max size** — limit longest side before upload to save tokens:
  - `1024 px` — save tokens
  - `1536 px` — balanced (default)
  - `2048 px` — max detail
  - Large images (e.g. 4K) are scaled **down**; small images (e.g. 512×1024) are **never enlarged**
- **Training target:** Flux, Krea-2, SDXL, SD 1.5, Pony
- **Krea-2:** LoRA type presets (Character, Style, Concept, Lighting) with tailored prompts
- Cost estimate before batch, actual usage after
- Progress bar + automatic retries

## Requirements

- Python 3.8+
- Windows (primary; `.bat` launcher included)
- [tkinterdnd2](https://pypi.org/project/tkinterdnd2/)
- [Pillow](https://pypi.org/project/pillow/) (image resize for Grok)
- xAI API key (Grok Vision mode only)

## Installation

```bash
git clone https://github.com/JesseQuartieri/DatasetKit.git
cd DatasetKit
pip install -r requirements.txt
```

## Usage

**Windows:** double-click `StartDatasetKit.bat`

**Or:**

```bash
python filenamer.py
```

1. Load images (drag & drop, **Browse**, or **Folder**)
2. Set **File Base name** (e.g. `Sara_droidV02_`)
3. Choose **After rename** mode
4. For Grok: enter API key, pick model, vision max size, training target / focus
5. Click **START RENAME** and confirm

Your preferences and API key are saved locally in `datasetkit_settings.json` on your machine. That file is **gitignored** — it stays on your PC and is **never pushed to GitHub**. Each person who clones the repo gets their own private copy. See `datasetkit_settings.example.json` for the format.

## Project docs

| File | Description |
|------|-------------|
| [CHANGELOG.md](CHANGELOG.md) | Version history and roadmap |
| [AGENTS.md](AGENTS.md) | Context for AI coding assistants |
| [PENDING_JOYCAPTION_INTEGRATION.md](PENDING_JOYCAPTION_INTEGRATION.md) | Planned local JoyCaption integration |

## License

MIT