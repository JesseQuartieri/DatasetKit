# FileNamer

A simple desktop tool to batch-rename image files in order using a custom base name.

## Features

- Drag and drop images into the app
- Browse files or select an entire folder
- Rename with a numbered sequence (e.g. `Sara_droidV02_001`, `Sara_droidV02_002`, ...)
- Supports common image formats: JPG, PNG, GIF, BMP, WebP, TIFF, ICO, HEIC, HEIF, AVIF
- Safe renaming using temporary files to avoid name collisions

## Requirements

- Python 3.8+
- [tkinterdnd2](https://pypi.org/project/tkinterdnd2/) (installed automatically on first run)

## Installation

1. Clone this repository:

```bash
git clone https://github.com/JesseQuartieri/FileNamer.git
cd FileNamer
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

**Windows:** double-click `StartFileNamer.bat`

**Or run manually:**

```bash
python filenamer.py
```

1. Load images by dragging them in, or use **Browse...** / **Folder...**
2. Enter a **Base name** (e.g. `Sara_droidV02_`)
3. Click **Start** and confirm the rename

## License

MIT