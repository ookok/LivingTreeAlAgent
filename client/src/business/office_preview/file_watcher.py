"""
office_preview/file_watcher.py - 文件追踪系统

借鉴 AionUi 的自动文件追踪机制：
- 文件变更检测（mtime + content hash）
- 防抖优化（防止频繁更新）
- 变更高亮（未保存指示）
- 工作区同步
"""

import os
import time
import hashlib
import threading
from typing import Dict, Callable, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class WatchedFile:
    """监视的文件"""
    path: str
    mtime: float
    size: int
    content_hash: str = ''
    is_modified: bool = False        # 外部修改
    is_dirty: bool = False           # 编辑器内未保存
    last_checked: float = 0.0
    error_count: int = 0


class FileWatcher:
    """
    文件监视器 - 追踪文件变化并通知订阅者

    借鉴 AionUi 设计：
    - 防抖机制：合并短时间内的多次变更
    - 哈希比对：内容级别变化检测
    - 多路订阅：支持多个文件同时监视
    """

    def __init__(self, debounce_delay: float = 0.5):
        self._watched: Dict[str, WatchedFile] = {}
        self._subscribers: Dict[str, Set[Callable]] = defaultdict(set)
        self._debounce_delay = debounce_delay
        self._debounce_timers: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._poll_thread: Optional[threading.Thread] = None
        self._running = False

    def watch(self, file_path: str, subscriber: Optional[Callable] = None) -> bool:
        """
        开始监视文件

        Args:
            file_path: 要监视的文件路径
            subscriber: 可选的回调函数 (file_path: str, event: str)
                       event: 'changed' | 'deleted' | 'created' | 'error'

        Returns:
            是否成功开始监视
        """
        if not os.path.exists(file_path):
            return False

        abs_path = os.path.abspath(file_path)

        with self._lock:
            # 初始化监视记录
            if abs_path not in self._watched:
                stat = os.stat(abs_path)
                self._watched[abs_path] = WatchedFile(
                    path=abs_path,
                    mtime=stat.st_mtime,
                    size=stat.st_size,
                    content_hash=self._hash_file(abs_path),
                    last_checked=time.time()
                )

            # 注册订阅者
            if subscriber:
                self._subscribers[abs_path].add(subscriber)

        # 启动轮询线程
        self._start_polling()

        return True

    def unwatch(self, file_path: str, subscriber: Optional[Callable] = None):
        """
        停止监视文件

        Args:
            file_path: 文件路径
            subscriber: 可选的指定订阅者（不传则移除所有订阅者）
        """
        abs_path = os.path.abspath(file_path)

        with self._lock:
            if subscriber:
                self._subscribers[abs_path].discard(subscriber)
                if not self._subscribers[abs_path]:
                    self._watched.pop(abs_path, None)
            else:
                self._subscribers.pop(abs_path, None)
                self._watched.pop(abs_path, None)

        # 停止轮询（如果没有文件了）
        if not self._watched:
            self._stop_polling()

    def notify_change(self, file_path: str):
        """
        通知编辑器内容已变化（用于内部状态管理）

        Args:
            file_path: 文件路径
        """
        abs_path = os.path.abspath(file_path)

        with self._lock:
            if abs_path in self._watched:
                self._watched[abs_path].is_dirty = True

    def mark_saved(self, file_path: str):
        """
        标记文件为已保存

        Args:
            file_path: 文件路径
        """
        abs_path = os.path.abspath(file_path)

        with self._lock:
            if abs_path in self._watched:
                self._watched[abs_path].is_dirty = False
                # 更新内容哈希
                self._watched[abs_path].content_hash = self._hash_file(abs_path)

    def is_modified_externally(self, file_path: str) -> bool:
        """检查文件是否被外部程序修改"""
        abs_path = os.path.abspath(file_path)

        with self._lock:
            if abs_path not in self._watched:
                return False
            return self._watched[abs_path].is_modified

    def acknowledge_change(self, file_path: str):
        """确认文件变化（重置修改标志）"""
        abs_path = os.path.abspath(file_path)

        with self._lock:
            if abs_path in self._watched:
                self._watched[abs_path].is_modified = False

    def _start_polling(self):
        """启动轮询线程"""
        if self._poll_thread and self._poll_thread.is_alive():
            return

        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _stop_polling(self):
        """停止轮询"""
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=2)
            self._poll_thread = None

    def _poll_loop(self):
        """轮询循环"""
        while self._running:
            time.sleep(0.5)  # 每 500ms 检查一次

            with self._lock:
                paths_to_check = list(self._watched.keys())

            for path in paths_to_check:
                self._check_file(path)

    def _check_file(self, file_path: str):
        """检查单个文件"""
        try:
            if not os.path.exists(file_path):
                self._emit(file_path, 'deleted')
                with self._lock:
                    self._watched.pop(file_path, None)
                return

            stat = os.stat(file_path)
            current_mtime = stat.st_mtime
            current_size = stat.st_size

            with self._lock:
                if file_path not in self._watched:
                    return

                watched = self._watched[file_path]
                now = time.time()

                # 跳过 debounce 期间的文件
                if file_path in self._debounce_timers:
                    if now - self._debounce_timers[file_path] < self._debounce_delay:
                        return

                # 检查修改时间
                if current_mtime != watched.mtime:
                    # 内容哈希比对确认
                    new_hash = self._hash_file(file_path)
                    if new_hash != watched.content_hash:
                        watched.mtime = current_mtime
                        watched.size = current_size
                        watched.content_hash = new_hash
                        watched.is_modified = True
                        watched.last_checked = now
                        self._emit(file_path, 'changed')
                    else:
                        # 仅 mtime 变化，内容未变
                        watched.mtime = current_mtime
                        watched.size = current_size

                # 检查大小异常
                elif current_size != watched.size:
                    new_hash = self._hash_file(file_path)
                    if new_hash != watched.content_hash:
                        watched.size = current_size
                        watched.content_hash = new_hash
                        watched.is_modified = True
                        watched.last_checked = now
                        self._emit(file_path, 'changed')

        except Exception as e:
            with self._lock:
                if file_path in self._watched:
                    self._watched[file_path].error_count += 1
                    if self._watched[file_path].error_count >= 3:
                        self._emit(file_path, 'error')
                        self._watched.pop(file_path, None)

    def _emit(self, file_path: str, event: str):
        """发送事件到所有订阅者"""
        # 防抖
        self._debounce_timers[file_path] = time.time()

        for callback in list(self._subscribers.get(file_path, [])):
            try:
                callback(file_path, event)
            except Exception:
                pass

    def _hash_file(self, file_path: str) -> str:
        """计算文件内容哈希"""
        try:
            with open(file_path, 'rb') as f:
                # 只读取前 64KB 进行快速哈希
                data = f.read(65536)
                return hashlib.md5(data).hexdigest()
        except Exception:
            return ''

    def get_watched_files(self) -> Set[str]:
        """获取所有被监视的文件路径"""
        with self._lock:
            return set(self._watched.keys())

    def get_file_state(self, file_path: str) -> Optional[WatchedFile]:
        """获取文件状态"""
        abs_path = os.path.abspath(file_path)
        with self._lock:
            return self._watched.get(abs_path)

    def __del__(self):
        self._stop_polling()


# 全局单例
_global_watcher: Optional[FileWatcher] = None


def get_file_watcher() -> FileWatcher:
    """获取全局文件监视器单例"""
    global _global_watcher
    if _global_watcher is None:
        _global_watcher = FileWatcher()
    return _global_watcher
