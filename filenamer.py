"""
FileNamer - Rename images in order with a base name.
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


class FileNamerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("FileNamer")
        self.root.configure(bg="#1e1e2e")

        self.files: list[Path] = []

        self._build_ui()
        self._setup_drag_drop()
        self._fit_window()

    def _build_ui(self):
        style_frame = tk.Frame(self.root, bg="#1e1e2e", padx=24, pady=20)
        style_frame.pack(fill=tk.BOTH, expand=True)

        title = tk.Label(
            style_frame,
            text="FileNamer",
            font=("Segoe UI", 22, "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e",
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            style_frame,
            text="Drag images or use Browse to load them",
            font=("Segoe UI", 10),
            fg="#a6adc8",
            bg="#1e1e2e",
        )
        subtitle.pack(anchor="w", pady=(4, 16))

        self.drop_zone = tk.Frame(
            style_frame,
            bg="#313244",
            highlightbackground="#89b4fa",
            highlightthickness=2,
            height=100,
        )
        self.drop_zone.pack(fill=tk.X, pady=(0, 12))
        self.drop_zone.pack_propagate(False)

        self.drop_label = tk.Label(
            self.drop_zone,
            text="Drag and drop images here",
            font=("Segoe UI", 12),
            fg="#bac2de",
            bg="#313244",
        )
        self.drop_label.pack(expand=True)

        btn_row = tk.Frame(style_frame, bg="#1e1e2e")
        btn_row.pack(fill=tk.X, pady=(0, 16))

        self.browse_btn = tk.Button(
            btn_row,
            text="Browse...",
            font=("Segoe UI", 10),
            bg="#45475a",
            fg="#cdd6f4",
            activebackground="#585b70",
            activeforeground="#cdd6f4",
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._browse_files,
        )
        self.browse_btn.pack(side=tk.LEFT)

        self.folder_btn = tk.Button(
            btn_row,
            text="Folder...",
            font=("Segoe UI", 10),
            bg="#45475a",
            fg="#cdd6f4",
            activebackground="#585b70",
            activeforeground="#cdd6f4",
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._browse_folder,
        )
        self.folder_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.clear_btn = tk.Button(
            btn_row,
            text="Clear list",
            font=("Segoe UI", 10),
            bg="#45475a",
            fg="#cdd6f4",
            activebackground="#585b70",
            activeforeground="#cdd6f4",
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._clear_files,
        )
        self.clear_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.count_label = tk.Label(
            btn_row,
            text="0 images",
            font=("Segoe UI", 10),
            fg="#a6adc8",
            bg="#1e1e2e",
        )
        self.count_label.pack(side=tk.RIGHT)

        list_frame = tk.Frame(style_frame, bg="#1e1e2e")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 16))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox = tk.Listbox(
            list_frame,
            font=("Consolas", 9),
            bg="#181825",
            fg="#cdd6f4",
            selectbackground="#45475a",
            selectforeground="#cdd6f4",
            relief=tk.FLAT,
            highlightthickness=0,
            height=6,
            yscrollcommand=scrollbar.set,
        )
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)

        name_frame = tk.Frame(style_frame, bg="#1e1e2e")
        name_frame.pack(fill=tk.X, pady=(0, 12))

        name_label = tk.Label(
            name_frame,
            text="Base name:",
            font=("Segoe UI", 10),
            fg="#cdd6f4",
            bg="#1e1e2e",
        )
        name_label.pack(anchor="w")

        self.name_entry = tk.Entry(
            name_frame,
            font=("Segoe UI", 12),
            bg="#313244",
            fg="#cdd6f4",
            insertbackground="#cdd6f4",
            relief=tk.FLAT,
        )
        self.name_entry.pack(fill=tk.X, pady=(6, 0), ipady=8)
        self.name_entry.insert(0, "Sara_droidV02_")

        example = tk.Label(
            name_frame,
            text="Example: Sara_droidV02_001, Sara_droidV02_002, ...",
            font=("Segoe UI", 9),
            fg="#6c7086",
            bg="#1e1e2e",
        )
        example.pack(anchor="w", pady=(4, 0))

        self.start_btn = tk.Button(
            style_frame,
            text="Start",
            font=("Segoe UI", 12, "bold"),
            bg="#89b4fa",
            fg="#1e1e2e",
            activebackground="#b4befe",
            activeforeground="#1e1e2e",
            relief=tk.FLAT,
            padx=24,
            pady=10,
            cursor="hand2",
            command=self._start_rename,
        )
        self.start_btn.pack(fill=tk.X)

        self.status_label = tk.Label(
            style_frame,
            text="",
            font=("Segoe UI", 9),
            fg="#a6e3a1",
            bg="#1e1e2e",
        )
        self.status_label.pack(anchor="w", pady=(8, 0))

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
                fg="#f9e2af",
            )
            return

        def on_drop(event):
            try:
                paths = self.root.tk.splitlist(event.data)
                self._handle_drop(paths)
            except Exception as exc:
                self.status_label.config(text=f"Error loading: {exc}", fg="#f38ba8")

        for widget in [self.root, self.drop_zone, self.drop_label]:
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
                    fg="#a6e3a1",
                )
            else:
                self.status_label.config(
                    text="No valid images found in dropped items",
                    fg="#f9e2af",
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
        self.status_label.config(text="List cleared", fg="#a6adc8")

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
            messagebox.showwarning("FileNamer", "No images loaded.")
            return

        base_name = self.name_entry.get().strip()
        if not base_name:
            messagebox.showwarning("FileNamer", "Enter a base name.")
            return

        invalid_chars = '<>:"/\\|?*'
        if any(c in base_name for c in invalid_chars):
            messagebox.showerror(
                "FileNamer",
                f"Base name cannot contain: {invalid_chars}",
            )
            return

        total = len(self.files)
        pad_width = max(3, len(str(total)))

        preview_first = f"{base_name}{str(1).zfill(pad_width)}"
        preview_last = f"{base_name}{str(total).zfill(pad_width)}"

        confirm = messagebox.askyesno(
            "Confirm rename",
            f"{total} image(s) will be renamed.\n\n"
            f"First: {preview_first}.ext\n"
            f"Last:  {preview_last}.ext\n\n"
            f"Continue?",
        )
        if not confirm:
            return

        try:
            renamed = self._rename_files(base_name, pad_width)
            self.status_label.config(
                text=f"Done: {renamed} image(s) renamed",
                fg="#a6e3a1",
            )
            messagebox.showinfo(
                "FileNamer",
                f"Successfully renamed {renamed} image(s).",
            )
            self.files.clear()
            self._update_list()
        except Exception as exc:
            messagebox.showerror("Error", f"Could not complete rename:\n{exc}")
            self.status_label.config(text="Error renaming", fg="#f38ba8")

    def _rename_files(self, base_name: str, pad_width: int) -> int:
        """Rename using temporary names to avoid collisions."""
        operations: list[tuple[Path, Path]] = []

        for index, src in enumerate(self.files, start=1):
            new_name = f"{base_name}{str(index).zfill(pad_width)}{src.suffix.lower()}"
            dst = src.parent / new_name
            operations.append((src, dst))

        temp_ops: list[tuple[Path, Path]] = []
        for i, (src, dst) in enumerate(operations):
            temp = src.parent / f"__filenamer_temp_{i:06d}{src.suffix.lower()}"
            if temp.exists():
                raise FileExistsError(f"Could not create temp file: {temp}")
            src.rename(temp)
            temp_ops.append((temp, dst))

        renamed = 0
        for temp, dst in temp_ops:
            if dst.exists():
                raise FileExistsError(f"A file with that name already exists: {dst.name}")
            temp.rename(dst)
            renamed += 1

        return renamed


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
    FileNamerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()