# DatasetKit

A desktop tool to prepare image datasets for LoRA training. Rename images in numbered order and optionally generate caption `.txt` files with trigger word support.

## Features

- Drag and drop images into the app
- Browse files or select an entire folder
- Rename with a numbered sequence (e.g. `Sara_droidV02_001`, `Sara_droidV02_002`, ...)
- Create matching caption `.txt` files for each image (Kohya / sd-scripts compatible)
- Optional trigger word prefill with `, ` suffix for easy caption pasting
- Skips existing `.txt` files to protect your work
- Open output folder when done
- Supports common image formats: JPG, PNG, GIF, BMP, WebP, TIFF, ICO, HEIC, HEIF, AVIF

## Requirements

- Python 3.8+
- [tkinterdnd2](https://pypi.org/project/tkinterdnd2/) (installed automatically on first run)

## Installation

1. Clone this repository:

```bash
git clone https://github.com/JesseQuartieri/DatasetKit.git
cd DatasetKit
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

**Windows:** double-click `StartDatasetKit.bat`

**Or run manually:**

```bash
python filenamer.py
```

1. Load images by dragging them in, or use **Browse** / **Folder**
2. Enter a **Base name** (e.g. `Sara_droidV02_`)
3. Optionally enable **Create caption .txt files** and set a **Trigger word**
4. Click **START RENAME** and confirm

## License

MIT