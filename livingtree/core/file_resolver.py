"""FileResolver — unified file path resolution for all write operations.

Handles:
  1. Project root detection (git root / pyproject.toml)
  2. Smart output directory by file type
  3. Conflict resolution (auto-rename on collision)
  4. User notification of output path

All write operations route through here, replacing scattered hardcoded paths.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ResolvedPath:
    path: Path
    exists: bool = False
    is_new: bool = True
    conflict_resolved: bool = False
    suggested: bool = False


OUTPUT_RULES: dict[str, str] = {
    ".py": "src",
    ".js": "src", ".ts": "src", ".jsx": "src", ".tsx": "src",
    ".go": "src", ".rs": "src", ".java": "src",
    ".docx": "output", ".pdf": "output", ".xlsx": "output",
    ".md": "docs", ".rst": "docs", ".txt": "output",
    ".json": "data", ".yaml": "data", ".yml": "data", ".toml": "data",
    ".csv": "data",
    ".html": "web", ".css": "web",
    ".png": "assets", ".jpg": "assets", ".svg": "assets",
    ".sh": "scripts", ".bat": "scripts", ".ps1": "scripts",
}

PROJECT_MARKERS = [".git", "pyproject.toml", "package.json", "Cargo.toml", "go.mod"]


class FileResolver:
    """Determines where files should be written."""

    def __init__(self, workspace: str | Path = "."):
        self._workspace = Path(workspace).resolve()
        self._project_root = self._detect_root()

    def _detect_root(self) -> Path:
        """Walk up from workspace to find project root."""
        current = self._workspace.resolve()
        for _ in range(5):
            for marker in PROJECT_MARKERS:
                if (current / marker).exists():
                    return current
            parent = current.parent
            if parent == current:
                break
            current = parent
        return self._workspace

    @property
    def project_root(self) -> Path:
        return self._project_root

    def resolve(
        self,
        filename: str,
        directory: str = "",
        content: str = "",
        auto_rename: bool = True,
    ) -> ResolvedPath:
        """Resolve the best path for a file.

        Args:
            filename: Desired filename (e.g. "report.docx")
            directory: Explicit directory (overrides auto-detection)
            content: File content (used for language detection)
            auto_rename: If True, append _N to avoid overwriting

        Returns:
            ResolvedPath with final path and metadata
        """
        name = filename.strip()

        # Determine directory
        if directory:
            base = self._project_root / directory
        else:
            subdir = OUTPUT_RULES.get(Path(name).suffix.lower(), "")
            base = self._project_root / subdir if subdir else self._project_root

        base.mkdir(parents=True, exist_ok=True)
        path = base / name

        # Conflict resolution
        result = ResolvedPath(path=path, exists=path.exists())
        if path.exists() and auto_rename:
            stem, ext = os.path.splitext(name)
            for i in range(1, 10):
                new_name = f"{stem}_{i}{ext}"
                new_path = base / new_name
                if not new_path.exists():
                    result.path = new_path
                    result.conflict_resolved = True
                    result.is_new = True
                    break
        elif not path.exists():
            result.is_new = True

        return result

    def resolve_for_content(self, content: str, prefix: str = "output", ext: str = ".md") -> ResolvedPath:
        """Auto-detect directory from content analysis, generate filename."""
        # Detect language from content
        detected_dir = ""
        if re.search(r'^(import |from |def |class |async def)', content, re.MULTILINE):
            detected_dir = "src"
            ext = ".py"
        elif re.search(r'^#+|## ', content, re.MULTILINE):
            detected_dir = "docs"
            ext = ".md"
        elif re.search(r'^{|\[', content):
            detected_dir = "data"
            ext = ".json"

        # Generate timestamp-based filename
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"{prefix}_{ts}{ext}"

        return self.resolve(name, directory=detected_dir)

    def resolve_existing(self, path_str: str) -> ResolvedPath:
        """Resolve an existing path (for saves/overwrites)."""
        p = Path(path_str)
        if not p.is_absolute():
            p = self._project_root / p
        return ResolvedPath(path=p, exists=p.exists(), is_new=False)

    def get_output_dir(self, category: str = "") -> Path:
        """Get recommended output directory for a category."""
        dirs = {
            "code": self._project_root / "src",
            "docs": self._project_root / "output",
            "data": self._project_root / "data",
            "assets": self._project_root / "assets",
            "scripts": self._project_root / "scripts",
        }
        d = dirs.get(category, self._project_root / "output")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write(
        self,
        path: ResolvedPath,
        content: str | bytes,
        notify: callable = None,
    ) -> str:
        """Write content to resolved path. Returns human-readable path description."""
        path.path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            path.path.write_text(content, encoding="utf-8")
        else:
            path.path.write_bytes(content)

        rel = self._relative(path.path)
        if notify:
            notify(f"已保存: {rel}")
        return rel

    def _relative(self, path: Path) -> str:
        try:
            return str(path.relative_to(self._project_root))
        except ValueError:
            return str(path)


# ═══ Global ═══

_resolver: FileResolver | None = None


def get_resolver(workspace: str | Path = ".") -> FileResolver:
    global _resolver
    if _resolver is None:
        _resolver = FileResolver(workspace)
    return _resolver
