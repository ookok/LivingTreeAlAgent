"""Windows native file dialogs — tkinter-based, runs in thread."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable, Optional


def _run_tk_dialog(dialog_type: str, **kwargs) -> Optional[str]:
    """Run a tkinter dialog in a subprocess-friendly way."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    result = None
    try:
        if dialog_type == "open_file":
            result = filedialog.askopenfilename(**kwargs)
        elif dialog_type == "open_files":
            result = filedialog.askopenfilenames(**kwargs)
        elif dialog_type == "save_file":
            result = filedialog.asksaveasfilename(**kwargs)
        elif dialog_type == "open_folder":
            result = filedialog.askdirectory(**kwargs)
    finally:
        root.destroy()

    return result if result else None


async def open_file_dialog(
    title: str = "选择文件",
    filetypes: list[tuple[str, str]] | None = None,
    initialdir: str = ".",
) -> Optional[Path]:
    """Open a native file selection dialog. Returns path or None."""
    if filetypes is None:
        filetypes = [
            ("所有文件", "*.*"),
            ("图片", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
            ("文档", "*.pdf *.docx *.txt *.md *.py *.json *.yaml"),
        ]
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _run_tk_dialog,
        "open_file",
        **{"title": title, "filetypes": filetypes, "initialdir": initialdir},
    )
    return Path(result) if result else None


async def open_files_dialog(
    title: str = "选择文件",
    filetypes: list[tuple[str, str]] | None = None,
    initialdir: str = ".",
) -> list[Path]:
    """Open native multi-file selection. Returns list of paths."""
    if filetypes is None:
        filetypes = [("所有文件", "*.*")]
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _run_tk_dialog,
        "open_files",
        **{"title": title, "filetypes": filetypes, "initialdir": initialdir},
    )
    return [Path(r) for r in result] if result else []


async def save_file_dialog(
    title: str = "保存文件",
    filetypes: list[tuple[str, str]] | None = None,
    initialdir: str = ".",
    defaultextension: str = ".txt",
) -> Optional[Path]:
    """Open native save-as dialog. Returns path or None."""
    if filetypes is None:
        filetypes = [("所有文件", "*.*")]
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _run_tk_dialog,
        "save_file",
        **{
            "title": title,
            "filetypes": filetypes,
            "initialdir": initialdir,
            "defaultextension": defaultextension,
        },
    )
    return Path(result) if result else None


async def open_folder_dialog(
    title: str = "选择文件夹",
    initialdir: str = ".",
) -> Optional[Path]:
    """Open native folder selection dialog. Returns path or None."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _run_tk_dialog,
        "open_folder",
        **{"title": title, "initialdir": initialdir},
    )
    return Path(result) if result else None
