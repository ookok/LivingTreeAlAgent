"""Attachment Bar — Dropped files/images displayed as removable chips.

Shows files selected via file picker, drag-and-drop, or paste.
Each attachment shows: icon + filename + size + [x] remove button.
"""

from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, Button

ICONS = {
    ".py": "🐍", ".js": "🟨", ".ts": "🔷", ".json": "📋", ".yaml": "📄", ".yml": "📄",
    ".md": "📝", ".txt": "📃", ".pdf": "📕", ".doc": "📘", ".docx": "📘",
    ".png": "🖼", ".jpg": "🖼", ".jpeg": "🖼", ".gif": "🖼", ".webp": "🖼", ".bmp": "🖼", ".svg": "🖼",
    ".zip": "📦", ".tar": "📦", ".gz": "📦", ".7z": "📦",
    ".exe": "⚙", ".dll": "⚙", ".so": "⚙",
    ".mp4": "🎬", ".mp3": "🎵", ".wav": "🎵",
    ".css": "🎨", ".html": "🌐", ".sql": "🗄",
    ".rs": "🦀", ".go": "🔵", ".java": "☕", ".cpp": "⚡", ".c": "⚡",
    ".rb": "💎", ".php": "🐘", ".swift": "🕊",
    ".sh": "💻", ".bat": "💻", ".ps1": "💻",
}


class AttachmentBar(Horizontal):

    def __init__(self, on_remove=None, **kwargs):
        super().__init__(**kwargs)
        self._on_remove = on_remove
        self._files: list[Path] = []

    def add(self, path: str | Path) -> None:
        path = Path(path)
        if not path.exists():
            return
        if path in self._files:
            return
        self._files.append(path)
        self._render()

    def remove(self, index: int) -> None:
        if 0 <= index < len(self._files):
            self._files.pop(index)
            self._render()

    def clear(self) -> None:
        self._files.clear()
        self._render()

    def get_files(self) -> list[Path]:
        return list(self._files)

    def _render(self) -> None:
        self.remove_children()
        if not self._files:
            self.styles.display = "none"
            return
        self.styles.display = "block"
        import time
        uid = str(int(time.time() * 1000))[-6:]
        for i, f in enumerate(self._files):
            ext = f.suffix.lower()
            icon = ICONS.get(ext, "📎")
            size_str = self._format_size(f)
            name = f.name[:25] + ("..." if len(f.name) > 25 else "")
            label = f"{icon} {name} {size_str}"
            self.mount(Static(label, id=f"att-label-{uid}-{i}"))
            btn = Button("[#f85149]✕[/#f85149]", id=f"att-rm-{uid}-{i}")
            btn.can_focus = False
            self.mount(btn)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = str(event.button.id)
        if bid.startswith("att-rm-"):
            try:
                idx = int(bid.split("-")[-1])
                self.remove(idx)
                if self._on_remove:
                    self._on_remove(idx)
            except (ValueError, IndexError):
                pass

    @staticmethod
    def _format_size(path: Path) -> str:
        try:
            size = path.stat().st_size
            if size < 1024:
                return f"({size}B)"
            elif size < 1024 * 1024:
                return f"({size // 1024}KB)"
            else:
                return f"({size // 1024 // 1024}MB)"
        except Exception:
            return ""
