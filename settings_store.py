"""Local settings persistence for DatasetKit.

Settings (including API key) are stored only in datasetkit_settings.json on the user's
machine. That file is gitignored and must never be committed to GitHub.
"""

from __future__ import annotations

import json
from pathlib import Path

SETTINGS_FILE = Path(__file__).resolve().parent / "datasetkit_settings.json"
SETTINGS_EXAMPLE_FILE = Path(__file__).resolve().parent / "datasetkit_settings.example.json"

DEFAULTS = {
    "api_key": "",
    "model_mode": "reasoning",
    "caption_focus": "mixed",
    "training_target": "flux",
    "krea2_lora_type": "character",
    "caption_mode": "none",
    "grok_max_long_edge": 1536,
}


def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return dict(DEFAULTS)
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULTS)
    merged = dict(DEFAULTS)
    merged.update({k: data[k] for k in DEFAULTS if k in data})
    return merged


def save_settings(settings: dict) -> None:
    payload = {key: settings.get(key, DEFAULTS[key]) for key in DEFAULTS}
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")