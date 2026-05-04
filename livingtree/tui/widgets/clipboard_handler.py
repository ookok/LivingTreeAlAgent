"""OS clipboard handler — detect images, files, and text."""
from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Optional


class ClipboardItem:
    """Represents a clipboard item with type detection."""

    def __init__(self, type_: str, data: bytes | str, name: str = ""):
        self.type = type_  # "image", "file", "text"
        self.data = data
        self.name = name

    @property
    def is_image(self) -> bool:
        return self.type == "image"

    @property
    def is_file(self) -> bool:
        return self.type == "file"

    @property
    def is_text(self) -> bool:
        return self.type == "text"


def get_clipboard_image() -> Optional[ClipboardItem]:
    """Try to get an image from the system clipboard. Returns None if no image."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grabclipboard()
        if img is None:
            return None
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return ClipboardItem("image", buf.getvalue(), "clipboard_image.png")
    except ImportError:
        pass
    except Exception:
        pass
    return None


def get_clipboard_files() -> list[ClipboardItem]:
    """Get file paths from clipboard (from Explorer copy)."""
    results = []
    try:
        import ctypes
        from ctypes import wintypes
        import pythoncom
        import win32clipboard

        pythoncom.CoInitialize()
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP):
                data = win32clipboard.GetClipboardData(win32clipboard.CF_HDROP)
                if data:
                    paths = data if isinstance(data, list) else [data]
                    for p in paths:
                        path = Path(p) if isinstance(p, str) else Path(str(p))
                        if path.exists():
                            raw = None
                            try:
                                raw = path.read_bytes()
                            except Exception:
                                pass
                            results.append(
                                ClipboardItem("file", raw or b"", str(path.name))
                            )
        finally:
            win32clipboard.CloseClipboard()
        pythoncom.CoUninitialize()
    except ImportError:
        pass
    except Exception:
        pass
    return results


def clipboard_has_image() -> bool:
    """Quick check if clipboard contains an image."""
    try:
        from PIL import ImageGrab
        return ImageGrab.grabclipboard() is not None
    except Exception:
        return False


def read_clipboard_text() -> str:
    """Read text from OS clipboard."""
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except ImportError:
        pass
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=2,
        )
        return result.stdout or ""
    except Exception:
        pass
    return ""


def write_clipboard_text(text: str) -> bool:
    """Write text to OS clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except ImportError:
        pass
    try:
        import subprocess
        subprocess.run(
            ["powershell", "-Command", f"Set-Clipboard -Value '{text}'"],
            timeout=2, capture_output=True,
        )
        return True
    except Exception:
        pass
    return False
