"""
DatasetKit - Prepare image datasets for LoRA training.
Rename images in order and optionally create caption .txt files.
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except ImportError:
    TkinterDnD = None
    DND_FILES = None

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".tiff", ".tif", ".ico", ".heic", ".heif", ".avif",
}

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

        self._configure_styles()
        self._build_ui()
        self._setup_drag_drop()
        self._fit_window()

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
            text="LoRA dataset prep  ·  rename images and generate caption files",
            font=(t["font"], 10),
            fg=t["text_secondary"],
            bg=t["bg"],
        )
        subtitle.pack(anchor="w", pady=(6, 0))

        tk.Frame(header, bg=t["border"], height=1).pack(fill=tk.X, pady=(16, 0))

        self._section_label(shell, "Images").pack(anchor="w", pady=(0, 8))

        self.drop_zone = self._surface_frame(shell, height=96)
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
        list_shell.pack(fill=tk.BOTH, expand=True, pady=(0, 18))

        list_frame = tk.Frame(list_shell, bg=t["surface_raised"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

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
            height=6,
            yscrollcommand=scrollbar.set,
        )
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)

        settings_card = self._surface_frame(shell)
        settings_card.pack(fill=tk.X, pady=(0, 16))

        settings_inner = tk.Frame(settings_card, bg=t["surface_raised"], padx=14, pady=14)
        settings_inner.pack(fill=tk.X)

        self._section_label(settings_inner, "Naming").pack(anchor="w", pady=(0, 8))

        name_label = self._body_label(settings_inner, "Base name", bold=True)
        name_label.pack(anchor="w")

        self.name_entry = self._entry_field(settings_inner)
        self.name_entry.pack(fill=tk.X, pady=(8, 0), ipady=8)

        example = self._body_label(
            settings_inner,
            "Example: Sara_droidV02_001, Sara_droidV02_002, ...",
            muted=True,
        )
        example.pack(anchor="w", pady=(6, 0))

        tk.Frame(settings_inner, bg=t["border"], height=1).pack(fill=tk.X, pady=(14, 12))

        self._section_label(settings_inner, "Captions").pack(anchor="w", pady=(0, 8))

        self.create_captions_var = tk.BooleanVar(value=False)
        self.create_captions_cb = tk.Checkbutton(
            settings_inner,
            text="Create caption .txt files",
            variable=self.create_captions_var,
            font=(t["font"], 10),
            fg=t["text"],
            bg=t["surface_raised"],
            activebackground=t["surface_raised"],
            activeforeground=t["text"],
            selectcolor=t["surface"],
            highlightthickness=0,
            cursor="hand2",
        )
        self.create_captions_cb.pack(anchor="w")

        trigger_label = self._body_label(settings_inner, "Trigger word (optional)", bold=True)
        trigger_label.pack(anchor="w", pady=(10, 0))

        self.trigger_entry = self._entry_field(settings_inner)
        self.trigger_entry.pack(fill=tk.X, pady=(8, 0), ipady=7)

        caption_hint = self._body_label(
            settings_inner,
            "Creates image_name.txt in the same folder. Existing files are not overwritten.",
            muted=True,
        )
        caption_hint.pack(anchor="w", pady=(6, 0))

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

        self.status_label = tk.Label(
            shell,
            text="",
            font=(t["font"], 9),
            fg=t["status_ok"],
            bg=t["bg"],
        )
        self.status_label.pack(anchor="w", pady=(10, 0))

    def _fit_window(self) -> None:
        """Size and center the window so all controls are visible on launch."""
        self.root.update_idletasks()

        req_w = self.root.winfo_reqwidth()
        req_h = self.root.winfo_reqheight()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        width = min(max(req_w + 8, 580), screen_w - 48)
        height = min(max(req_h + 8, 560), screen_h - 48)
        min_w = min(max(req_w, 520), width)
        min_h = min(max(req_h, 500), height)

        self.root.minsize(min_w, min_h)
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
            self.status_label.config(text=f"Error loading: {exc}", fg="#f38ba8")

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

        total = len(self.files)
        pad_width = max(3, len(str(total)))

        preview_first = f"{base_name}{str(1).zfill(pad_width)}"
        preview_last = f"{base_name}{str(total).zfill(pad_width)}"
        create_captions = self.create_captions_var.get()

        confirm_lines = [
            f"{total} image(s) will be renamed.",
            "",
            f"First: {preview_first}.ext",
            f"Last:  {preview_last}.ext",
        ]
        if create_captions:
            trigger = self.trigger_entry.get().strip()
            confirm_lines.extend([
                "",
                "Caption .txt files will be created for each renamed image.",
            ])
            if trigger:
                confirm_lines.append(f'Trigger word: "{trigger}, "')
            confirm_lines.append("Existing .txt files will be skipped.")
        confirm_lines.extend(["", "Continue?"])

        if not messagebox.askyesno("Confirm rename", "\n".join(confirm_lines)):
            return

        try:
            renamed_paths = self._rename_files(base_name, pad_width)
            renamed_count = len(renamed_paths)
            self.last_output_folder = renamed_paths[0].parent if renamed_paths else None

            status_parts = [f"Done: {renamed_count} image(s) renamed"]
            message_parts = [f"Successfully renamed {renamed_count} image(s)."]

            if create_captions:
                created, skipped = self._create_caption_files(renamed_paths)
                caption_summary = (
                    f"{created} caption file(s) created, {skipped} skipped (already existed)"
                )
                status_parts.append(caption_summary)
                message_parts.append(caption_summary)

            self.status_label.config(
                text=" | ".join(status_parts), fg=self.theme["status_ok"]
            )
            messagebox.showinfo("DatasetKit", "\n".join(message_parts))

            if self.last_output_folder is not None:
                self.open_folder_btn.config(
                    state=tk.NORMAL, fg=self.theme["text"]
                )

            self.files.clear()
            self._update_list()
        except Exception as exc:
            messagebox.showerror("Error", f"Could not complete rename:\n{exc}")
            self.status_label.config(
                text="Error renaming", fg=self.theme["status_error"]
            )

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


def main():
    _enable_dpi_awareness()
    _ensure_tkdnd()
    root = TkinterDnD.Tk()
    DatasetKitApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()