"""
文件监控器
使用 watchdog 监控项目目录文件变更
"""

import time
from pathlib import Path
from typing import Callable
from dataclasses import dataclass

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None


@dataclass
class FileChange:
    type: str   # created | modified | deleted | moved
    path: str
    is_dir: bool


class ProjectFileWatcher:
    """
    项目目录文件监控
    - 监控 docs/ 目录下的 .md 文件变更
    - 通过 watchdog 实现（跨平台）
    """

    def __init__(self, project_path: str, on_change: Callable[[list[FileChange]], None]):
        self.project_path = Path(project_path)
        self.on_change = on_change
        self._changes: list[FileChange] = []
        self._last_flush = time.time()
        self._flush_interval = 0.5  # 批量合并变更

        if WATCHDOG_AVAILABLE:
            self._handler = _WatchdogHandler(self)
            self._observer = Observer()
        else:
            self._handler = None
            self._observer = None

    def start(self):
        if WATCHDOG_AVAILABLE and self._observer:
            watch_path = self.project_path / "docs"
            if watch_path.exists():
                self._observer.schedule(self._handler, str(watch_path), recursive=True)
                self._observer.schedule(self._handler, str(self.project_path / "assets"), recursive=True)
            self._observer.start()

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=3)

    def record(self, change: FileChange):
        """记录变更，批量触发回调"""
        self._changes.append(change)
        if time.time() - self._last_flush > self._flush_interval:
            self.flush()

    def flush(self):
        if self._changes and self.on_change:
            changes = self._changes.copy()
            self._changes.clear()
            self._last_flush = time.time()
            self.on_change(changes)


if WATCHDOG_AVAILABLE:
    class _WatchdogHandler(FileSystemEventHandler):
        def __init__(self, watcher: ProjectFileWatcher):
            self.watcher = watcher

        def on_any_event(self, event: FileSystemEvent):
            if event.is_directory:
                return
            # 只监控 .md 和图片
            ext = Path(event.src_path).suffix.lower()
            if ext not in (".md", ".png", ".jpg", ".jpeg", ".gif", ".webp"):
                return

            event_map = {
                "created": "created",
                "modified": "modified",
                "deleted": "deleted",
                "moved": "moved",
            }
            change = FileChange(
                type=event_map.get(event.event_type, "modified"),
                path=event.src_path,
                is_dir=event.is_directory,
            )
            self.watcher.record(change)
