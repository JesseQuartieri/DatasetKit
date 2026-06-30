"""
DatasetKit - Prepare image datasets for LoRA training.
Rename images in order and optionally create caption .txt files.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from grok_caption import (
    CAPTION_FOCUS_OPTIONS,
    GROK_VISION_MAX_EDGE_OPTIONS,
    KREA2_LORA_TYPE_OPTIONS,
    MAX_CAPTION_RETRIES,
    TRAINING_TARGET_OPTIONS,
    GrokCaptionError,
    apply_trigger_prefix,
    estimate_batch_cost,
    format_actual_cost,
    format_cost_estimate,
    generate_caption_with_retries,
    is_flux_krea2_target,
    krea2_hint_for_type,
    label_for_max_long_edge,
    max_long_edge_from_label,
    model_from_mode,
    test_connection,
)
from settings_store import load_settings, save_settings

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except ImportError:
    TkinterDnD = None
    DND_FILES = None

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".tiff", ".tif", ".ico", ".heic", ".heif", ".avif",
}

WINDOW_MIN_WIDTH = 680
WINDOW_MIN_HEIGHT = 900
WINDOW_DEFAULT_WIDTH = 740
WINDOW_DEFAULT_HEIGHT = 1120

UI_THEME = {
    "bg": "#000000",
    "surface": "#0a0a0a",
    "surface_raised": "#111111",
    "border": "#262626",
    "border_active": "#ffffff",
    "text": "#ffffff",
    "text_secondary": "#b8b8b8",
    "text_muted": "#6b6b6b",
    "btn_secondary": "#141414",
    "btn_secondary_active": "#222222",
    "btn_primary": "#ffffff",
    "btn_primary_text": "#000000",
    "btn_primary_active": "#e5e5e5",
    "select_bg": "#2a2a2a",
    "status_ok": "#ffffff",
    "status_warn": "#b8b8b8",
    "status_error": "#d4d4d4",
    "font": "Segoe UI",
}


def _normalize_path(raw) -> str:
    if isinstance(raw, bytes):
        for encoding in ("utf-8", "mbcs", "gbk"):
            try:
                return raw.decode(encoding).strip().strip('"').strip("'")
            except UnicodeDecodeError:
                continue
        raw = raw.decode("utf-8", errors="replace")
    elif not isinstance(raw, str):
        raw = str(raw)
    return os.path.normpath(raw.strip().strip('"').strip("'").strip("{}"))


def _path_key(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path.absolute())


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class DatasetKitApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("DatasetKit")
        self.theme = UI_THEME
        self.root.configure(bg=self.theme["bg"])

        self.files: list[Path] = []
        self.last_output_folder: Path | None = None
        self._busy = False
        self._settings = load_settings()

        self._configure_styles()
        self._build_ui()
        self._setup_drag_drop()
        self._fit_window()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        t = self.theme
        style.configure(
            "Modern.Vertical.TScrollbar",
            background=t["surface_raised"],
            troughcolor=t["bg"],
            bordercolor=t["border"],
            arrowcolor=t["text_secondary"],
            relief="flat",
        )
        style.map(
            "Modern.Vertical.TScrollbar",
            background=[("active", t["select_bg"]), ("pressed", t["border"])],
        )
        style.configure(
            "Dark.TCombobox",
            fieldbackground=t["surface"],
            background=t["btn_secondary"],
            foreground=t["text"],
            arrowcolor=t["text_secondary"],
            bordercolor=t["border"],
            relief="flat",
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", t["surface"])],
            foreground=[("readonly", t["text"])],
        )
        style.configure(
            "Dark.Horizontal.TProgressbar",
            troughcolor=t["surface"],
            background=t["text"],
            bordercolor=t["border"],
            lightcolor=t["text"],
            darkcolor=t["text"],
        )

    def _widget_bg(self, parent: tk.Misc) -> str:
        try:
            return parent.cget("bg")
        except tk.TclError:
            return self.theme["bg"]

    def _section_label(self, parent: tk.Misc, text: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text.upper(),
            font=(self.theme["font"], 8, "bold"),
            fg=self.theme["text_muted"],
            bg=self._widget_bg(parent),
        )

    def _body_label(
        self, parent: tk.Misc, text: str, *, muted: bool = False, bold: bool = False
    ) -> tk.Label:
        font = (self.theme["font"], 10, "bold" if bold else "normal")
        fg = self.theme["text_muted"] if muted else self.theme["text_secondary"]
        if bold:
            fg = self.theme["text"]
        return tk.Label(
            parent, text=text, font=font, fg=fg, bg=self._widget_bg(parent)
        )

    def _surface_frame(self, parent: tk.Misc, **kwargs) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=self.theme["surface_raised"],
            highlightbackground=self.theme["border"],
            highlightthickness=1,
            **kwargs,
        )

    def _secondary_button(self, parent: tk.Misc, text: str, command) -> tk.Button:
        t = self.theme
        return tk.Button(
            parent,
            text=text,
            font=(t["font"], 10),
            bg=t["btn_secondary"],
            fg=t["text"],
            activebackground=t["btn_secondary_active"],
            activeforeground=t["text"],
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=7,
            cursor="hand2",
            command=command,
        )

    def _entry_field(self, parent: tk.Misc, **kwargs) -> tk.Entry:
        t = self.theme
        return tk.Entry(
            parent,
            font=(t["font"], 11),
            bg=t["surface"],
            fg=t["text"],
            insertbackground=t["text"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=t["border"],
            highlightcolor=t["border_active"],
            **kwargs,
        )

    def _build_ui(self):
        t = self.theme
        shell = tk.Frame(self.root, bg=t["bg"], padx=28, pady=24)
        self.shell = shell
        shell.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(shell, bg=t["bg"])
        header.pack(fill=tk.X, pady=(0, 20))

        title = tk.Label(
            header,
            text="DatasetKit",
            font=(t["font"], 26, "bold"),
            fg=t["text"],
            bg=t["bg"],
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            header,
            text="LoRA dataset prep  ·  rename, caption files, Grok Vision AI",
            font=(t["font"], 10),
            fg=t["text_secondary"],
            bg=t["bg"],
        )
        subtitle.pack(anchor="w", pady=(6, 0))

        tk.Frame(header, bg=t["border"], height=1).pack(fill=tk.X, pady=(16, 0))

        self._section_label(shell, "Images").pack(anchor="w", pady=(0, 8))

        self.drop_zone = self._surface_frame(shell, height=80)
        self.drop_zone.pack(fill=tk.X, pady=(0, 12))
        self.drop_zone.pack_propagate(False)

        self.drop_label = tk.Label(
            self.drop_zone,
            text="Drop images here",
            font=(t["font"], 12),
            fg=t["text_secondary"],
            bg=t["surface_raised"],
        )
        self.drop_label.pack(expand=True)

        self.drop_hint = tk.Label(
            self.drop_zone,
            text="or use Browse / Folder below",
            font=(t["font"], 9),
            fg=t["text_muted"],
            bg=t["surface_raised"],
        )
        self.drop_hint.pack()

        btn_row = tk.Frame(shell, bg=t["bg"])
        btn_row.pack(fill=tk.X, pady=(0, 12))

        self.browse_btn = self._secondary_button(btn_row, "Browse", self._browse_files)
        self.browse_btn.pack(side=tk.LEFT)

        self.folder_btn = self._secondary_button(btn_row, "Folder", self._browse_folder)
        self.folder_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.clear_btn = self._secondary_button(btn_row, "Clear", self._clear_files)
        self.clear_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.count_label = tk.Label(
            btn_row,
            text="0 images",
            font=(t["font"], 10),
            fg=t["text_muted"],
            bg=t["bg"],
        )
        self.count_label.pack(side=tk.RIGHT)

        list_shell = self._surface_frame(shell)
        list_shell.pack(fill=tk.X, pady=(0, 14))

        list_frame = tk.Frame(list_shell, bg=t["surface_raised"])
        list_frame.pack(fill=tk.X, padx=1, pady=1)

        scrollbar = ttk.Scrollbar(list_frame, style="Modern.Vertical.TScrollbar")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox = tk.Listbox(
            list_frame,
            font=("Consolas", 9),
            bg=t["surface"],
            fg=t["text"],
            selectbackground=t["select_bg"],
            selectforeground=t["text"],
            relief=tk.FLAT,
            highlightthickness=0,
            bd=0,
            height=4,
            yscrollcommand=scrollbar.set,
        )
        self.file_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        scrollbar.config(command=self.file_listbox.yview)

        settings_card = self._surface_frame(shell)
        settings_card.pack(fill=tk.X, pady=(0, 12))

        settings_inner = tk.Frame(settings_card, bg=t["surface_raised"], padx=14, pady=14)
        settings_inner.pack(fill=tk.X)

        self._section_label(settings_inner, "Naming").pack(anchor="w", pady=(0, 8))

        name_label = self._body_label(settings_inner, "File Base name", bold=True)
        name_label.pack(anchor="w")

        self.name_entry = self._entry_field(settings_inner)
        self.name_entry.pack(fill=tk.X, pady=(8, 0), ipady=8)

        example = self._body_label(
            settings_inner,
            "Example: Sara_droidV02_001, Sara_droidV02_002, ...",
            muted=True,
        )
        example.pack(anchor="w", pady=(6, 0))

        api_card = self._surface_frame(shell)
        api_card.pack(fill=tk.X, pady=(0, 12))

        api_inner = tk.Frame(api_card, bg=t["surface_raised"], padx=14, pady=14)
        api_inner.pack(fill=tk.X)

        self._section_label(api_inner, "Grok API").pack(anchor="w", pady=(0, 8))

        api_key_label = self._body_label(api_inner, "xAI API key", bold=True)
        api_key_label.pack(anchor="w")

        api_key_row = tk.Frame(api_inner, bg=t["surface_raised"])
        api_key_row.pack(fill=tk.X, pady=(8, 0))

        self.api_key_entry = self._entry_field(api_key_row, show="•")
        self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=7)
        self.api_key_entry.insert(0, self._settings.get("api_key", ""))

        self.test_api_btn = self._secondary_button(api_key_row, "Test", self._test_api_connection)
        self.test_api_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.api_key_hint = self._body_label(
            api_inner,
            "Saved on this PC only. Never included in the GitHub repo.",
            muted=True,
        )
        self.api_key_hint.pack(anchor="w", pady=(6, 0))

        model_label = self._body_label(api_inner, "Model", bold=True)
        model_label.pack(anchor="w", pady=(12, 0))

        model_row = tk.Frame(api_inner, bg=t["surface_raised"])
        model_row.pack(anchor="w", pady=(8, 0))

        self.model_mode_var = tk.StringVar(
            value=self._settings.get("model_mode", "reasoning")
        )
        self.model_reasoning_rb = tk.Radiobutton(
            model_row,
            text="grok-4.20-0309-reasoning",
            variable=self.model_mode_var,
            value="reasoning",
            font=(t["font"], 9),
            fg=t["text_secondary"],
            bg=t["surface_raised"],
            activebackground=t["surface_raised"],
            activeforeground=t["text"],
            selectcolor=t["surface"],
            highlightthickness=0,
            cursor="hand2",
        )
        self.model_reasoning_rb.pack(anchor="w")
        self.model_fast_rb = tk.Radiobutton(
            model_row,
            text="grok-4.20-0309-non-reasoning",
            variable=self.model_mode_var,
            value="non_reasoning",
            font=(t["font"], 9),
            fg=t["text_secondary"],
            bg=t["surface_raised"],
            activebackground=t["surface_raised"],
            activeforeground=t["text"],
            selectcolor=t["surface"],
            highlightthickness=0,
            cursor="hand2",
        )
        self.model_fast_rb.pack(anchor="w", pady=(4, 0))

        vision_size_label = self._body_label(api_inner, "Vision max size", bold=True)
        vision_size_label.pack(anchor="w", pady=(12, 0))

        vision_edge_labels = [label for _, label in GROK_VISION_MAX_EDGE_OPTIONS]
        saved_vision_edge = self._settings.get("grok_max_long_edge", 1536)
        self.vision_max_edge_var = tk.StringVar(
            value=label_for_max_long_edge(saved_vision_edge)
        )
        self.vision_max_edge_combo = ttk.Combobox(
            api_inner,
            textvariable=self.vision_max_edge_var,
            values=vision_edge_labels,
            state="readonly",
            style="Dark.TCombobox",
            font=(t["font"], 10),
        )
        self.vision_max_edge_combo.pack(fill=tk.X, pady=(8, 0))

        self.vision_max_edge_hint = self._body_label(
            api_inner,
            "Large images are scaled down before upload. Smaller images are never enlarged.",
            muted=True,
        )
        self.vision_max_edge_hint.pack(anchor="w", pady=(6, 0))

        caption_card = self._surface_frame(shell)
        caption_card.pack(fill=tk.X, pady=(0, 16))

        caption_inner = tk.Frame(caption_card, bg=t["surface_raised"], padx=14, pady=14)
        caption_inner.pack(fill=tk.X)

        self._section_label(caption_inner, "Captions").pack(anchor="w", pady=(0, 8))

        mode_label = self._body_label(caption_inner, "After rename", bold=True)
        mode_label.pack(anchor="w", pady=(4, 0))

        self.caption_mode_var = tk.StringVar(
            value=self._settings.get("caption_mode", "none")
        )
        mode_row = tk.Frame(caption_inner, bg=t["surface_raised"])
        mode_row.pack(anchor="w", pady=(8, 0))

        for value, text in (
            ("none", "Rename only"),
            ("empty", "Create empty .txt files"),
            ("grok", "Full captioning with Grok Vision"),
        ):
            tk.Radiobutton(
                mode_row,
                text=text,
                variable=self.caption_mode_var,
                value=value,
                font=(t["font"], 10),
                fg=t["text_secondary"],
                bg=t["surface_raised"],
                activebackground=t["surface_raised"],
                activeforeground=t["text"],
                selectcolor=t["surface"],
                highlightthickness=0,
                cursor="hand2",
                command=self._on_caption_mode_change,
            ).pack(anchor="w", pady=(0 if value == "none" else 4, 0))

        self.mode_hint = self._body_label(caption_inner, "", muted=True)
        self.mode_hint.pack(anchor="w", pady=(8, 0))

        self.trigger_section = tk.Frame(caption_inner, bg=t["surface_raised"])
        self.trigger_section.pack(fill=tk.X, pady=(12, 0))

        trigger_label = self._body_label(self.trigger_section, "Trigger word", bold=True)
        trigger_label.pack(anchor="w")

        self.trigger_entry = self._entry_field(self.trigger_section)
        self.trigger_entry.pack(fill=tk.X, pady=(8, 0), ipady=7)

        self.trigger_hint = self._body_label(self.trigger_section, "", muted=True)
        self.trigger_hint.pack(anchor="w", pady=(6, 0))

        self.grok_options_section = tk.Frame(caption_inner, bg=t["surface_raised"])
        self.grok_options_section.pack(fill=tk.X, pady=(14, 0))

        tk.Frame(self.grok_options_section, bg=t["border"], height=1).pack(
            fill=tk.X, pady=(0, 12)
        )

        self.focus_section = tk.Frame(self.grok_options_section, bg=t["surface_raised"])
        self.focus_section.pack(fill=tk.X)

        focus_label = self._body_label(self.focus_section, "Caption focus", bold=True)
        focus_label.pack(anchor="w", pady=(10, 0))

        focus_labels = [label for _, label in CAPTION_FOCUS_OPTIONS]
        focus_map = {key: label for key, label in CAPTION_FOCUS_OPTIONS}
        saved_focus = self._settings.get("caption_focus", "mixed")
        self.focus_key_var = tk.StringVar(
            value=focus_map.get(saved_focus, focus_labels[0])
        )
        self.focus_combo = ttk.Combobox(
            self.focus_section,
            textvariable=self.focus_key_var,
            values=focus_labels,
            state="disabled",
            style="Dark.TCombobox",
            font=(t["font"], 10),
        )
        self.focus_combo.pack(fill=tk.X, pady=(8, 0))

        self.krea2_section = tk.Frame(self.grok_options_section, bg=t["surface_raised"])

        krea2_type_label = self._body_label(self.krea2_section, "LoRA type", bold=True)
        krea2_type_label.pack(anchor="w", pady=(10, 0))

        krea2_labels = [label for _, label in KREA2_LORA_TYPE_OPTIONS]
        krea2_map = {key: label for key, label in KREA2_LORA_TYPE_OPTIONS}
        saved_krea2_type = self._settings.get("krea2_lora_type", "character")
        self.krea2_type_var = tk.StringVar(
            value=krea2_map.get(saved_krea2_type, krea2_labels[0])
        )
        self.krea2_type_combo = ttk.Combobox(
            self.krea2_section,
            textvariable=self.krea2_type_var,
            values=krea2_labels,
            state="disabled",
            style="Dark.TCombobox",
            font=(t["font"], 10),
        )
        self.krea2_type_combo.pack(fill=tk.X, pady=(8, 0))
        self.krea2_type_combo.bind(
            "<<ComboboxSelected>>", lambda _event: self._on_krea2_type_change()
        )

        self.target_label = self._body_label(
            self.grok_options_section, "Training target", bold=True
        )
        self.target_label.pack(anchor="w", pady=(10, 0))

        target_labels = [label for _, label in TRAINING_TARGET_OPTIONS]
        target_map = {key: label for key, label in TRAINING_TARGET_OPTIONS}
        saved_target = self._settings.get("training_target", "flux")
        self.target_key_var = tk.StringVar(
            value=target_map.get(saved_target, target_labels[0])
        )
        self.target_combo = ttk.Combobox(
            self.grok_options_section,
            textvariable=self.target_key_var,
            values=target_labels,
            state="disabled",
            style="Dark.TCombobox",
            font=(t["font"], 10),
        )
        self.target_combo.pack(fill=tk.X, pady=(8, 0))
        self.target_combo.bind("<<ComboboxSelected>>", lambda _event: self._on_target_change())

        self.krea2_hint = self._body_label(self.grok_options_section, "", muted=True)
        self.krea2_hint.pack(anchor="w", pady=(6, 0))

        self.start_btn = tk.Button(
            shell,
            text="START RENAME",
            font=(t["font"], 11, "bold"),
            bg=t["btn_primary"],
            fg=t["btn_primary_text"],
            activebackground=t["btn_primary_active"],
            activeforeground=t["btn_primary_text"],
            relief=tk.FLAT,
            bd=0,
            padx=24,
            pady=12,
            cursor="hand2",
            command=self._start_rename,
        )
        self.start_btn.pack(fill=tk.X)

        action_row = tk.Frame(shell, bg=t["bg"])
        action_row.pack(fill=tk.X, pady=(10, 0))

        self.open_folder_btn = tk.Button(
            action_row,
            text="Open folder",
            font=(t["font"], 10),
            bg=t["bg"],
            fg=t["text_muted"],
            activebackground=t["btn_secondary"],
            activeforeground=t["text"],
            relief=tk.FLAT,
            bd=0,
            padx=2,
            pady=4,
            cursor="hand2",
            state=tk.DISABLED,
            command=self._open_output_folder,
        )
        self.open_folder_btn.pack(side=tk.LEFT)

        self.progress_frame = tk.Frame(shell, bg=t["bg"])
        self.progress_frame.pack(fill=tk.X, pady=(10, 0))
        self.progress_frame.pack_forget()

        self.grok_progress_label = tk.Label(
            self.progress_frame,
            text="",
            font=(t["font"], 9),
            fg=t["text_muted"],
            bg=t["bg"],
        )
        self.grok_progress_label.pack(anchor="w")

        self.grok_progress = ttk.Progressbar(
            self.progress_frame,
            style="Dark.Horizontal.TProgressbar",
            mode="determinate",
            maximum=100,
        )
        self.grok_progress.pack(fill=tk.X, pady=(6, 0))

        self.status_label = tk.Label(
            shell,
            text="",
            font=(t["font"], 9),
            fg=t["status_ok"],
            bg=t["bg"],
        )
        self.status_label.pack(anchor="w", pady=(10, 0))

        self._shell_max_height = self._measure_max_shell_height()

    def _combo_key_from_label(self, label: str, options: list[tuple[str, str]]) -> str:
        for key, option_label in options:
            if option_label == label:
                return key
        return options[0][0]

    def _caption_mode(self) -> str:
        return self.caption_mode_var.get()

    def _grok_enabled(self) -> bool:
        return self._caption_mode() == "grok"

    def _empty_captions_enabled(self) -> bool:
        return self._caption_mode() == "empty"

    def _on_caption_mode_change(self) -> None:
        self._apply_caption_mode_ui()

    def _apply_caption_mode_ui(self) -> None:
        mode = self._caption_mode()
        hints = {
            "none": "Just rename images. Add captions later if you want.",
            "empty": "Creates one .txt per image. You fill in the captions yourself.",
            "grok": "AI writes captions. Set your API key in Grok API above.",
        }
        trigger_hints = {
            "empty": "Prefills each .txt as: yourword, ",
            "grok": "Added to the start of every AI caption.",
        }
        self.mode_hint.config(text=hints.get(mode, ""))

        if mode in ("empty", "grok"):
            self.trigger_section.pack(fill=tk.X, pady=(12, 0))
            self.trigger_hint.config(text=trigger_hints.get(mode, ""))
        else:
            self.trigger_section.pack_forget()

        if mode == "grok":
            self.grok_options_section.pack(fill=tk.X, pady=(14, 0))
        else:
            self.grok_options_section.pack_forget()

        self._on_target_change()

    def _on_krea2_type_change(self) -> None:
        lora_type_key = self._combo_key_from_label(
            self.krea2_type_var.get(), KREA2_LORA_TYPE_OPTIONS
        )
        self.krea2_hint.config(text=krea2_hint_for_type(lora_type_key))

    def _on_target_change(self) -> None:
        target_key = self._combo_key_from_label(
            self.target_key_var.get(), TRAINING_TARGET_OPTIONS
        )
        grok_enabled = self._grok_enabled()
        combo_state = "readonly" if grok_enabled else "disabled"
        self.target_combo.config(state=combo_state)

        if is_flux_krea2_target(target_key):
            self.focus_section.pack_forget()
            self.krea2_section.pack(fill=tk.X, before=self.target_label)
            self.krea2_type_combo.config(state=combo_state)
            self._on_krea2_type_change()
        else:
            self.krea2_section.pack_forget()
            self.focus_section.pack(fill=tk.X, before=self.target_label)
            self.focus_combo.config(state=combo_state)
            self.krea2_hint.config(text="")

    def _on_close(self) -> None:
        self._persist_settings()
        self.root.destroy()

    def _persist_settings(self) -> None:
        save_settings({
            "api_key": self.api_key_entry.get().strip(),
            "model_mode": self.model_mode_var.get(),
            "caption_focus": self._combo_key_from_label(
                self.focus_key_var.get(), CAPTION_FOCUS_OPTIONS
            ),
            "training_target": self._combo_key_from_label(
                self.target_key_var.get(), TRAINING_TARGET_OPTIONS
            ),
            "krea2_lora_type": self._combo_key_from_label(
                self.krea2_type_var.get(), KREA2_LORA_TYPE_OPTIONS
            ),
            "caption_mode": self._caption_mode(),
            "grok_max_long_edge": max_long_edge_from_label(
                self.vision_max_edge_var.get()
            ),
        })

    def _get_api_key(self) -> str:
        return self.api_key_entry.get().strip()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.start_btn.config(state=state)
        self.browse_btn.config(state=state)
        self.folder_btn.config(state=state)
        self.clear_btn.config(state=state)
        self.test_api_btn.config(state=state)

    def _update_status(self, text: str, *, tone: str = "ok") -> None:
        colors = {
            "ok": self.theme["status_ok"],
            "warn": self.theme["status_warn"],
            "error": self.theme["status_error"],
            "muted": self.theme["text_muted"],
        }
        self.status_label.config(text=text, fg=colors.get(tone, self.theme["status_ok"]))

    def _show_grok_progress(self, current: int, total: int, detail: str = "") -> None:
        if not self.progress_frame.winfo_ismapped():
            self.progress_frame.pack(fill=tk.X, pady=(10, 0), before=self.status_label)
        percent = 0 if total <= 0 else int((current / total) * 100)
        self.grok_progress["value"] = percent
        label = f"Captioning {current}/{total}"
        if detail:
            label = f"{label}  ·  {detail}"
        self.grok_progress_label.config(text=label)

    def _hide_grok_progress(self) -> None:
        self.grok_progress["value"] = 0
        self.grok_progress_label.config(text="")
        if self.progress_frame.winfo_ismapped():
            self.progress_frame.pack_forget()

    def _test_api_connection(self) -> None:
        api_key = self._get_api_key()
        if not api_key:
            messagebox.showwarning("DatasetKit", "Enter your xAI API key first.")
            return

        self._persist_settings()
        self._set_busy(True)
        self._update_status("Testing API connection...", tone="muted")

        def worker() -> None:
            try:
                reply = test_connection(api_key, self.model_mode_var.get())
                self.root.after(
                    0,
                    lambda: self._on_test_api_success(reply),
                )
            except GrokCaptionError as exc:
                self.root.after(0, lambda: self._on_test_api_failure(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_api_success(self, reply: str) -> None:
        self._set_busy(False)
        self._update_status("API connection OK", tone="ok")
        messagebox.showinfo("DatasetKit", f"Connection successful.\nModel replied: {reply}")

    def _on_test_api_failure(self, error: str) -> None:
        self._set_busy(False)
        self._update_status("API connection failed", tone="error")
        messagebox.showerror("DatasetKit", f"Connection failed:\n{error}")

    def _run_grok_captions_async(self, image_paths: list[Path]) -> None:
        api_key = self._get_api_key()
        if not api_key:
            messagebox.showerror("DatasetKit", "Enter your xAI API key to use Grok Vision.")
            return

        self._persist_settings()
        self._set_busy(True)

        focus_key = self._combo_key_from_label(
            self.focus_key_var.get(), CAPTION_FOCUS_OPTIONS
        )
        target_key = self._combo_key_from_label(
            self.target_key_var.get(), TRAINING_TARGET_OPTIONS
        )
        krea2_lora_type = self._combo_key_from_label(
            self.krea2_type_var.get(), KREA2_LORA_TYPE_OPTIONS
        )
        trigger = self.trigger_entry.get().strip()
        model_mode = self.model_mode_var.get()
        max_long_edge = max_long_edge_from_label(self.vision_max_edge_var.get())
        total = len(image_paths)

        def worker() -> None:
            captioned = 0
            failed: list[str] = []
            retried = 0
            usage_totals = {"prompt_tokens": 0, "completion_tokens": 0}

            for index, image_path in enumerate(image_paths, start=1):
                self.root.after(
                    0,
                    lambda i=index, t=total: self._show_grok_progress(i, t),
                )
                self.root.after(
                    0,
                    lambda i=index, t=total: self._update_status(
                        f"Grok captioning {i}/{t}...", tone="muted"
                    ),
                )
                try:
                    caption, usage, attempts = generate_caption_with_retries(
                        api_key,
                        model_mode,
                        image_path,
                        focus_key,
                        target_key,
                        krea2_lora_type,
                        max_long_edge,
                    )
                    usage_totals["prompt_tokens"] += int(usage.get("prompt_tokens", 0) or 0)
                    usage_totals["completion_tokens"] += int(
                        usage.get("completion_tokens", 0) or 0
                    )
                    if attempts > 1:
                        retried += 1
                    caption = apply_trigger_prefix(caption, trigger)
                    image_path.with_suffix(".txt").write_text(caption, encoding="utf-8")
                    captioned += 1
                except Exception as exc:
                    failed.append(f"{image_path.name}: {exc}")

            self.root.after(
                0,
                lambda: self._on_grok_caption_done(
                    captioned, failed, total, usage_totals, retried
                ),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _on_grok_caption_done(
        self,
        captioned: int,
        failed: list[str],
        total: int,
        usage_totals: dict,
        retried: int,
    ) -> None:
        self._set_busy(False)
        self._hide_grok_progress()

        cost_line = format_actual_cost(
            usage_totals.get("prompt_tokens", 0),
            usage_totals.get("completion_tokens", 0),
        )
        summary = f"Grok captions: {captioned}/{total} written (overwritten)"
        if retried:
            summary += f" | {retried} retried"
        summary += f" | {cost_line}"

        dialog_lines = [summary, f"Retries: up to {MAX_CAPTION_RETRIES} per image"]
        if failed:
            summary += f" | {len(failed)} failed"
            preview = "\n".join(failed[:5])
            if len(failed) > 5:
                preview += f"\n... and {len(failed) - 5} more"
            dialog_lines.extend(["", "Failures:", preview])
            messagebox.showwarning("DatasetKit", "\n".join(dialog_lines))
            self._update_status(summary, tone="warn")
        else:
            messagebox.showinfo("DatasetKit", "\n".join(dialog_lines))
            self._update_status(summary, tone="ok")

        if self.last_output_folder is not None:
            self.open_folder_btn.config(state=tk.NORMAL, fg=self.theme["text"])

        self.files.clear()
        self._update_list()

    def _measure_max_shell_height(self) -> int:
        """Measure shell height with the tallest caption-mode layout (once at build)."""
        saved_mode = self._caption_mode()
        saved_target = self._combo_key_from_label(
            self.target_key_var.get(), TRAINING_TARGET_OPTIONS
        )
        target_map = {key: label for key, label in TRAINING_TARGET_OPTIONS}

        self.caption_mode_var.set("grok")
        self.target_key_var.set(target_map.get("krea2", target_map["flux"]))
        self._apply_caption_mode_ui()

        self.root.update_idletasks()
        max_height = self.shell.winfo_reqheight()

        self.caption_mode_var.set(saved_mode)
        self.target_key_var.set(target_map.get(saved_target, target_map["flux"]))
        self._apply_caption_mode_ui()

        return max_height

    def _fit_window(self) -> None:
        """Size and center the window so all controls are visible on launch."""
        self.root.update_idletasks()

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        content_w = self.shell.winfo_reqwidth() + 56
        content_h = max(self.shell.winfo_reqheight(), self._shell_max_height) + 40

        width = min(max(content_w, WINDOW_DEFAULT_WIDTH, WINDOW_MIN_WIDTH), screen_w - 32)
        height = min(
            max(content_h, WINDOW_DEFAULT_HEIGHT, WINDOW_MIN_HEIGHT),
            screen_h - 32,
        )

        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _setup_drag_drop(self):
        if TkinterDnD is None or DND_FILES is None:
            self.status_label.config(
                text="Drag & drop unavailable (install tkinterdnd2)",
                fg=self.theme["status_warn"],
            )
            return

        def on_drop(event):
            try:
                paths = self.root.tk.splitlist(event.data)
                self._handle_drop(paths)
            except Exception as exc:
                self.status_label.config(
                    text=f"Error loading: {exc}", fg=self.theme["status_error"]
                )

        for widget in [self.root, self.drop_zone, self.drop_label, self.drop_hint]:
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", on_drop)
            except Exception:
                pass

    def _handle_drop(self, paths):
        try:
            expanded = self._expand_paths(paths)
            added = self._add_paths(expanded)
            if added:
                self._update_list()
                self.status_label.config(
                    text=f"Added {added} image(s)",
                    fg=self.theme["status_ok"],
                )
            else:
                self.status_label.config(
                    text="No valid images found in dropped items",
                    fg=self.theme["status_warn"],
                )
        except Exception as exc:
            self.status_label.config(
                text=f"Error loading: {exc}", fg=self.theme["status_error"]
            )

    def _expand_paths(self, paths) -> list[str]:
        """If a folder is dropped, include images inside."""
        result: list[str] = []
        for raw in paths:
            path = Path(_normalize_path(raw))
            if path.is_dir():
                for child in sorted(path.iterdir()):
                    if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS:
                        result.append(str(child))
            else:
                result.append(str(path))
        return result

    def _browse_files(self):
        paths = filedialog.askopenfilenames(
            title="Select images",
            filetypes=[
                (
                    "Images",
                    "*.jpg *.jpeg *.png *.gif *.bmp *.webp *.tiff *.tif *.ico *.heic *.heif *.avif",
                ),
                ("All files", "*.*"),
            ],
        )
        if paths:
            self._handle_drop(paths)

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder with images")
        if folder:
            self._handle_drop([folder])

    def _add_paths(self, paths) -> int:
        added = 0
        existing = {_path_key(f) for f in self.files}

        for raw in paths:
            try:
                path = Path(_normalize_path(raw))
            except (TypeError, ValueError):
                continue
            if not path.is_file():
                continue
            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            key = _path_key(path)
            if key not in existing:
                self.files.append(path)
                existing.add(key)
                added += 1

        return added

    def _clear_files(self):
        self.files.clear()
        self._update_list()
        self.status_label.config(text="List cleared", fg=self.theme["text_muted"])

    def _update_list(self):
        self.file_listbox.delete(0, tk.END)
        total = len(self.files)
        show_max = 200

        for i, f in enumerate(self.files[:show_max], start=1):
            self.file_listbox.insert(tk.END, f"{i:03d}. {f.name}")

        if total > show_max:
            self.file_listbox.insert(
                tk.END,
                f"... and {total - show_max} more image(s)",
            )

        self.count_label.config(text=f"{total} image{'s' if total != 1 else ''}")

    def _start_rename(self):
        if self._busy:
            return
        if not self.files:
            messagebox.showwarning("DatasetKit", "No images loaded.")
            return

        base_name = self.name_entry.get().strip()
        if not base_name:
            messagebox.showwarning("DatasetKit", "Enter a base name.")
            return

        invalid_chars = '<>:"/\\|?*'
        if any(c in base_name for c in invalid_chars):
            messagebox.showerror(
                "DatasetKit",
                f"Base name cannot contain: {invalid_chars}",
            )
            return

        create_captions = self._empty_captions_enabled()
        grok_captions = self._grok_enabled()
        if grok_captions and not self._get_api_key():
            messagebox.showwarning("DatasetKit", "Enter your xAI API key for Grok Vision.")
            return

        total = len(self.files)
        pad_width = max(3, len(str(total)))

        preview_first = f"{base_name}{str(1).zfill(pad_width)}"
        preview_last = f"{base_name}{str(total).zfill(pad_width)}"

        confirm_lines = [
            f"{total} image(s) will be renamed.",
            "",
            f"First: {preview_first}.ext",
            f"Last:  {preview_last}.ext",
        ]
        if create_captions:
            trigger = self.trigger_entry.get().strip()
            confirm_lines.extend(["", "Empty caption .txt files will be created."])
            if trigger:
                confirm_lines.append(f'Trigger word: "{trigger}, "')
            confirm_lines.append("Existing .txt files will be skipped.")
        if grok_captions:
            trigger = self.trigger_entry.get().strip()
            max_long_edge = max_long_edge_from_label(self.vision_max_edge_var.get())
            cost_estimate = estimate_batch_cost(total, max_long_edge)
            confirm_lines.extend([
                "",
                "Grok Vision will caption each image and overwrite .txt files.",
                f"Target: {self.target_key_var.get()}",
                f"Model: {model_from_mode(self.model_mode_var.get())}",
                f"Vision max size: {self.vision_max_edge_var.get()}",
                format_cost_estimate(cost_estimate),
                f"Retries: up to {MAX_CAPTION_RETRIES} per image on transient errors",
            ])
            if is_flux_krea2_target(
                self._combo_key_from_label(
                    self.target_key_var.get(), TRAINING_TARGET_OPTIONS
                )
            ):
                confirm_lines.append(f"LoRA type: {self.krea2_type_var.get()}")
            else:
                confirm_lines.append(f"Focus: {self.focus_key_var.get()}")
            if trigger:
                confirm_lines.append(f'Trigger prefix: "{trigger}, "')
        confirm_lines.extend(["", "Continue?"])

        if not messagebox.askyesno("Confirm rename", "\n".join(confirm_lines)):
            return

        try:
            renamed_paths = self._rename_files(base_name, pad_width)
            renamed_count = len(renamed_paths)
            self.last_output_folder = renamed_paths[0].parent if renamed_paths else None
            self._persist_settings()

            if create_captions and not grok_captions:
                created, skipped = self._create_caption_files(renamed_paths)
                summary = (
                    f"Done: {renamed_count} renamed | "
                    f"{created} empty caption(s), {skipped} skipped"
                )
                self._update_status(summary, tone="ok")
                messagebox.showinfo("DatasetKit", summary)
                if self.last_output_folder is not None:
                    self.open_folder_btn.config(state=tk.NORMAL, fg=self.theme["text"])
                self.files.clear()
                self._update_list()
                return

            if grok_captions:
                max_long_edge = max_long_edge_from_label(self.vision_max_edge_var.get())
                estimate = estimate_batch_cost(len(renamed_paths), max_long_edge)
                self._update_status(
                    f"Done: {renamed_count} renamed. Starting Grok captioning... "
                    f"{format_cost_estimate(estimate)}",
                    tone="ok",
                )
                self._show_grok_progress(0, len(renamed_paths))
                self._run_grok_captions_async(renamed_paths)
                return

            self._update_status(f"Done: {renamed_count} image(s) renamed", tone="ok")
            messagebox.showinfo(
                "DatasetKit", f"Successfully renamed {renamed_count} image(s)."
            )
            if self.last_output_folder is not None:
                self.open_folder_btn.config(state=tk.NORMAL, fg=self.theme["text"])
            self.files.clear()
            self._update_list()
        except Exception as exc:
            messagebox.showerror("Error", f"Could not complete rename:\n{exc}")
            self._update_status("Error renaming", tone="error")

    def _default_caption_text(self) -> str:
        trigger = self.trigger_entry.get().strip()
        if not trigger:
            return ""
        return f"{trigger}, "

    def _create_caption_files(self, image_paths: list[Path]) -> tuple[int, int]:
        """Create caption .txt files for renamed images. Returns (created, skipped)."""
        default_caption = self._default_caption_text()
        created = 0
        skipped = 0

        for image_path in image_paths:
            txt_path = image_path.with_suffix(".txt")
            if txt_path.exists():
                skipped += 1
                continue
            txt_path.write_text(default_caption, encoding="utf-8")
            created += 1

        return created, skipped

    def _open_output_folder(self) -> None:
        if self.last_output_folder is None or not self.last_output_folder.exists():
            messagebox.showwarning("DatasetKit", "No output folder available yet.")
            return
        os.startfile(self.last_output_folder)

    def _rename_files(self, base_name: str, pad_width: int) -> list[Path]:
        """Rename using temporary names to avoid collisions."""
        operations: list[tuple[Path, Path]] = []

        for index, src in enumerate(self.files, start=1):
            new_name = f"{base_name}{str(index).zfill(pad_width)}{src.suffix.lower()}"
            dst = src.parent / new_name
            operations.append((src, dst))

        temp_ops: list[tuple[Path, Path]] = []
        for i, (src, dst) in enumerate(operations):
            temp = src.parent / f"__datasetkit_temp_{i:06d}{src.suffix.lower()}"
            if temp.exists():
                raise FileExistsError(f"Could not create temp file: {temp}")
            src.rename(temp)
            temp_ops.append((temp, dst))

        renamed_paths: list[Path] = []
        for temp, dst in temp_ops:
            if dst.exists():
                raise FileExistsError(f"A file with that name already exists: {dst.name}")
            temp.rename(dst)
            renamed_paths.append(dst)

        return renamed_paths


def _ensure_tkdnd():
    global TkinterDnD, DND_FILES
    if TkinterDnD is not None:
        return
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "tkinterdnd2", "-q"])
    from tkinterdnd2 import TkinterDnD as _TkinterDnD, DND_FILES as _DND_FILES
    TkinterDnD = _TkinterDnD
    DND_FILES = _DND_FILES


def _ensure_pillow() -> None:
    try:
        import PIL  # noqa: F401
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow", "-q"])


def main():
    _enable_dpi_awareness()
    _ensure_tkdnd()
    _ensure_pillow()
    root = TkinterDnD.Tk()
    DatasetKitApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()