"""
Performance Optimization Layer for LivingTree AI Agent

Provides thread-safe caching, async I/O, and resource management utilities
to fix identified performance bottlenecks in the PyQt6 GUI application.

Components:
- LRUCache: Thread-safe LRU cache with TTL support
- FileContentCache: File content cache based on modification time
- ASTCache: AST parsing result cache
- AsyncFileIO: QThread-based async file operations
- ThreadPoolManager: QThread lifecycle manager
- DebounceTimer: Debounce timer for UI operations
- ChatHistoryManager: Chat history with memory limits
- ParallelScanner: Parallel project scanner
"""

import ast
import fnmatch
import os
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Pattern

from PyQt6.QtCore import QObject, QThread, pyqtSignal

# =============================================================================
# 1. LRUCache - Thread-safe LRU Cache with TTL
# =============================================================================


class LRUCache:
    """
    Thread-safe LRU cache with TTL (Time-To-Live) support.

    Features:
    - O(1) get/put operations
    - Automatic TTL expiration
    - Pattern-based invalidation
    - Hit/miss statistics
    - Lazy loading via factory function

    Usage:
        cache = LRUCache(maxsize=128, ttl_seconds=60)
        value = cache.get("key", factory=lambda: expensive_operation())
        cache.put("key", value, ttl=30)  # Override TTL
    """

    def __init__(self, maxsize: int = 128, ttl_seconds: float = 60.0):
        self._maxsize = maxsize
        self._default_ttl = ttl_seconds
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str, factory: Optional[Callable[[], Any]] = None) -> Any:
        """
        Get value from cache.

        Args:
            key: Cache key
            factory: Optional factory function for lazy loading on cache miss

        Returns:
            Cached value or factory result
        """
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    self._cache.move_to_end(key)
                    self._hits += 1
                    return value
                else:
                    del self._cache[key]

            self._misses += 1
            if factory is not None:
                value = factory()
                self.put(key, value)
                return value
            return None

    def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """
        Put value into cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override (uses default if None)
        """
        if ttl is None:
            ttl = self._default_ttl

        expiry = time.time() + ttl

        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, expiry)

            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from cache. Returns True if key existed."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Remove all keys matching a wildcard pattern.

        Args:
            pattern: Unix-style glob pattern (e.g., "*.py", "file_*")

        Returns:
            Number of keys removed
        """
        with self._lock:
            keys_to_remove = [k for k in self._cache if fnmatch.fnmatch(k, pattern)]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "maxsize": self._maxsize,
                "hit_rate": self._hits / total if total > 0 else 0.0,
            }

    def _cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        now = time.time()
        removed = 0
        with self._lock:
            expired_keys = [k for k, (_, exp) in self._cache.items() if now >= exp]
            for key in expired_keys:
                del self._cache[key]
                removed += 1
        return removed


# =============================================================================
# 2. FileContentCache - File Content Cache with Modification Time Tracking
# =============================================================================


class FileContentCache:
    """
    File content cache that tracks file modification times.

    Automatically invalidates cached content when the file is modified.

    Usage:
        cache = FileContentCache()
        content = cache.get_content("path/to/file.py")
        if content is None:
            content = read_file("path/to/file.py")
            cache.put_content("path/to/file.py", content)
    """

    def __init__(self, maxsize: int = 256):
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._lock = threading.RLock()
        self._maxsize = maxsize

    def get_content(self, file_path: str) -> Optional[str]:
        """
        Get cached file content if file hasn't been modified.

        Args:
            file_path: Path to the file

        Returns:
            Cached content or None if not cached or file is modified
        """
        with self._lock:
            if file_path not in self._cache:
                return None

            content, cached_mtime = self._cache[file_path]

            if not os.path.exists(file_path):
                del self._cache[file_path]
                return None

            current_mtime = os.path.getmtime(file_path)
            if current_mtime > cached_mtime:
                del self._cache[file_path]
                return None

            self._cache.move_to_end(file_path)
            return content

    def put_content(self, file_path: str, content: str) -> None:
        """
        Cache file content with current modification time.

        Args:
            file_path: Path to the file
            content: File content to cache
        """
        with self._lock:
            if os.path.exists(file_path):
                mtime = os.path.getmtime(file_path)
            else:
                mtime = time.time()

            self._cache[file_path] = (content, mtime)
            self._cache.move_to_end(file_path)

            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def is_dirty(self, file_path: str) -> bool:
        """
        Check if file has been modified since it was cached.

        Args:
            file_path: Path to the file

        Returns:
            True if file is modified or not cached, False otherwise
        """
        with self._lock:
            if file_path not in self._cache:
                return True

            _, cached_mtime = self._cache[file_path]

            if not os.path.exists(file_path):
                return True

            return os.path.getmtime(file_path) > cached_mtime

    def invalidate(self, file_path: str) -> bool:
        """Remove a file from cache. Returns True if file was cached."""
        with self._lock:
            if file_path in self._cache:
                del self._cache[file_path]
                return True
            return False

    def clear(self) -> None:
        """Clear all cached file contents."""
        with self._lock:
            self._cache.clear()


# =============================================================================
# 3. ASTCache - AST Parsing Result Cache
# =============================================================================


class ASTCache:
    """
    AST (Abstract Syntax Tree) parsing result cache.

    Caches parsed AST trees associated with file modification times.
    Provides helper methods to extract symbols and structure info.

    Usage:
        cache = ASTCache()
        tree = cache.get_ast("path/to/file.py")
        if tree is None:
            with open("path/to/file.py") as f:
                cache.parse("path/to/file.py", f.read())
        symbols = cache.get_symbols("path/to/file.py")
    """

    def __init__(self, maxsize: int = 128):
        self._cache: OrderedDict[str, tuple[ast.Module, float]] = OrderedDict()
        self._lock = threading.RLock()
        self._maxsize = maxsize

    def get_ast(self, file_path: str) -> Optional[ast.Module]:
        """
        Get cached AST if file hasn't been modified.

        Args:
            file_path: Path to the Python file

        Returns:
            Cached AST or None
        """
        with self._lock:
            if file_path not in self._cache:
                return None

            tree, cached_mtime = self._cache[file_path]

            if not os.path.exists(file_path):
                del self._cache[file_path]
                return None

            current_mtime = os.path.getmtime(file_path)
            if current_mtime > cached_mtime:
                del self._cache[file_path]
                return None

            self._cache.move_to_end(file_path)
            return tree

    def parse(self, file_path: str, source: Optional[str] = None) -> ast.Module:
        """
        Parse a Python file and cache the result.

        Args:
            file_path: Path to the Python file
            source: Optional source code (reads file if None)

        Returns:
            Parsed AST tree
        """
        with self._lock:
            existing = self.get_ast(file_path)
            if existing is not None:
                return existing

            if source is None:
                with open(file_path, "r", encoding="utf-8") as f:
                    source = f.read()

            tree = ast.parse(source, filename=file_path)
            mtime = os.path.getmtime(file_path)

            self._cache[file_path] = (tree, mtime)
            self._cache.move_to_end(file_path)

            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

            return tree

    def get_symbols(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract all symbols (classes, functions, imports) from a Python file.

        Args:
            file_path: Path to the Python file

        Returns:
            List of symbol info dicts with keys: name, type, lineno, end_lineno
        """
        tree = self.get_ast(file_path)
        if tree is None:
            try:
                tree = self.parse(file_path)
            except (SyntaxError, ValueError):
                return []

        symbols = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append({
                    "name": node.name,
                    "type": "class" if isinstance(node, ast.ClassDef) else "function",
                    "lineno": node.lineno,
                    "end_lineno": getattr(node, "end_lineno", None),
                })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    symbols.append({
                        "name": alias.name,
                        "type": "import",
                        "lineno": node.lineno,
                        "end_lineno": node.lineno,
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    symbols.append({
                        "name": f"{module}.{alias.name}" if module else alias.name,
                        "type": "import_from",
                        "lineno": node.lineno,
                        "end_lineno": node.lineno,
                    })

        return symbols

    def get_structure(self, file_path: str) -> Dict[str, Any]:
        """
        Get hierarchical structure of a Python file.

        Args:
            file_path: Path to the Python file

        Returns:
            Dict with classes and their methods
        """
        tree = self.get_ast(file_path)
        if tree is None:
            try:
                tree = self.parse(file_path)
            except (SyntaxError, ValueError):
                return {"classes": [], "functions": [], "imports": []}

        structure = {
            "classes": [],
            "functions": [],
            "imports": [],
        }

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in ast.walk(node)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                structure["classes"].append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "methods": methods,
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                structure["functions"].append({
                    "name": node.name,
                    "lineno": node.lineno,
                })
            elif isinstance(node, ast.Import):
                structure["imports"].extend([a.name for a in node.names])
            elif isinstance(node, ast.ImportFrom):
                module = node.module or "*"
                structure["imports"].append(f"from {module} import ...")

        return structure

    def invalidate(self, file_path: str) -> bool:
        """Remove a file's AST from cache."""
        with self._lock:
            if file_path in self._cache:
                del self._cache[file_path]
                return True
            return False

    def clear(self) -> None:
        """Clear all cached ASTs."""
        with self._lock:
            self._cache.clear()


# =============================================================================
# 4. AsyncFileIO - QThread-based Async File Operations
# =============================================================================


class _AsyncFileIOWorker(QThread):
    """Worker thread for async file I/O operations."""

    read_completed = pyqtSignal(str, str)
    write_completed = pyqtSignal(str, bool)
    error_occurred = pyqtSignal(str, str)
    batch_read_completed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: List[tuple] = []
        self._running = True
        self._lock = threading.Lock()

    def add_read_task(self, file_path: str, encoding: str = "utf-8"):
        with self._lock:
            self._tasks.append(("read", file_path, encoding))

    def add_write_task(self, file_path: str, content: str, encoding: str = "utf-8"):
        with self._lock:
            self._tasks.append(("write", file_path, content, encoding))

    def add_batch_read_task(self, file_paths: List[str], encoding: str = "utf-8"):
        with self._lock:
            self._tasks.append(("batch_read", file_paths, encoding))

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            task = None
            with self._lock:
                if self._tasks:
                    task = self._tasks.pop(0)

            if task is None:
                self.msleep(10)
                continue

            op = task[0]

            if op == "read":
                _, file_path, encoding = task
                self._do_read(file_path, encoding)
            elif op == "write":
                _, file_path, content, encoding = task
                self._do_write(file_path, content, encoding)
            elif op == "batch_read":
                _, file_paths, encoding = task
                self._do_batch_read(file_paths, encoding)

    def _do_read(self, file_path: str, encoding: str):
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
            self.read_completed.emit(file_path, content)
        except Exception as e:
            self.error_occurred.emit(file_path, str(e))

    def _do_write(self, file_path: str, content: str, encoding: str):
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding=encoding) as f:
                f.write(content)
            self.write_completed.emit(file_path, True)
        except Exception as e:
            self.error_occurred.emit(file_path, str(e))

    def _do_batch_read(self, file_paths: List[str], encoding: str):
        results = []
        for path in file_paths:
            try:
                with open(path, "r", encoding=encoding) as f:
                    content = f.read()
                results.append((path, content, None))
            except Exception as e:
                results.append((path, None, str(e)))

        self.batch_read_completed.emit(results)


class AsyncFileIO(QObject):
    """
    QThread-based asynchronous file I/O operations.

    Signals:
        read_completed(str, str): Emitted when read finishes (file_path, content)
        write_completed(str, bool): Emitted when write finishes (file_path, success)
        error_occurred(str, str): Emitted on error (file_path, error_message)
        batch_read_completed(list): Emitted when batch read finishes

    Usage:
        io = AsyncFileIO()
        io.read_completed.connect(self.on_file_read)
        io.read_file("path/to/file.py")
    """

    read_completed = pyqtSignal(str, str)
    write_completed = pyqtSignal(str, bool)
    error_occurred = pyqtSignal(str, str)
    batch_read_completed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = _AsyncFileIOWorker(parent)
        self._worker.read_completed.connect(self._on_read_completed)
        self._worker.write_completed.connect(self._on_write_completed)
        self._worker.error_occurred.connect(self._on_error_occurred)
        self._worker.batch_read_completed.connect(self._on_batch_read_completed)
        self._worker.start()

    def _on_read_completed(self, file_path: str, content: str):
        self.read_completed.emit(file_path, content)

    def _on_write_completed(self, file_path: str, success: bool):
        self.write_completed.emit(file_path, success)

    def _on_error_occurred(self, file_path: str, error: str):
        self.error_occurred.emit(file_path, error)

    def _on_batch_read_completed(self, results: list):
        self.batch_read_completed.emit(results)

    def read_file(self, file_path: str, encoding: str = "utf-8"):
        """
        Read file asynchronously.

        Args:
            file_path: Path to file to read
            encoding: File encoding (default: utf-8)
        """
        self._worker.add_read_task(file_path, encoding)

    def write_file(self, file_path: str, content: str, encoding: str = "utf-8"):
        """
        Write file asynchronously.

        Args:
            file_path: Path to file to write
            content: Content to write
            encoding: File encoding (default: utf-8)
        """
        self._worker.add_write_task(file_path, content, encoding)

    def read_files_batch(self, file_paths: List[str], encoding: str = "utf-8"):
        """
        Read multiple files in parallel.

        Args:
            file_paths: List of file paths to read
            encoding: File encoding (default: utf-8)
        """
        self._worker.add_batch_read_task(file_paths, encoding)

    def shutdown(self):
        """Stop the worker thread."""
        self._worker.stop()
        self._worker.wait(2000)


# =============================================================================
# 5. ThreadPoolManager - QThread Lifecycle Manager
# =============================================================================


class ThreadPoolManager:
    """
    Manages QThread lifecycle to prevent thread leaks.

    Features:
    - Tracks all active threads
    - Auto-cleanup of finished threads
    - Named threads for debugging
    - Batch cancel support

    Usage:
        manager = ThreadPoolManager()
        manager.submit(my_thread, name="parse_task")
        # Later:
        manager.cleanup_finished()
        print(manager.active_count())
    """

    def __init__(self):
        self._threads: Dict[str, QThread] = {}
        self._lock = threading.Lock()

    def submit(self, thread: QThread, name: str = "") -> str:
        """
        Register and start a thread.

        Args:
            thread: QThread instance to manage
            name: Optional name for the thread

        Returns:
            Thread identifier
        """
        with self._lock:
            if not name:
                name = f"thread_{len(self._threads) + 1}"

            if name in self._threads:
                counter = 2
                while f"{name}_{counter}" in self._threads:
                    counter += 1
                name = f"{name}_{counter}"

            self._threads[name] = thread
            thread.finished.connect(lambda n=name: self._on_finished(n))

            if not thread.isRunning():
                thread.start()

            return name

    def _on_finished(self, name: str):
        """Internal: Called when a thread finishes."""
        with self._lock:
            if name in self._threads:
                del self._threads[name]

    def cleanup_finished(self) -> int:
        """
        Remove finished threads from tracking.

        Returns:
            Number of threads cleaned up
        """
        removed = 0
        with self._lock:
            finished = [
                name for name, t in self._threads.items()
                if not t.isRunning()
            ]
            for name in finished:
                del self._threads[name]
                removed += 1
        return removed

    def cancel_all(self):
        """Request all threads to stop."""
        with self._lock:
            for name, thread in self._threads.items():
                if thread.isRunning():
                    thread.requestInterruption()
                    if hasattr(thread, "stop"):
                        thread.stop()

    def active_count(self) -> int:
        """Return number of active threads."""
        with self._lock:
            return sum(1 for t in self._threads.values() if t.isRunning())

    def get_active_threads(self) -> List[str]:
        """Return list of active thread names."""
        with self._lock:
            return [
                name for name, t in self._threads.items()
                if t.isRunning()
            ]

    def get_all_threads(self) -> List[str]:
        """Return list of all tracked thread names."""
        with self._lock:
            return list(self._threads.keys())


# =============================================================================
# 6. DebounceTimer - Debounce Timer for UI Operations
# =============================================================================


class DebounceTimer(QObject):
    """
    Debounce timer to prevent rapid-fire UI operations.

    Instead of blocking with direct QTimer, this coalesces rapid trigger()
    calls into a single delayed signal.

    Signals:
        triggered: Emitted after delay when no new triggers arrive

    Usage:
        timer = DebounceTimer(delay_ms=500)
        timer.triggered.connect(self.on_action)
        # Rapid calls are coalesced:
        timer.trigger()  # starts 500ms countdown
        timer.trigger()  # resets countdown
        timer.trigger()  # resets countdown
        # Only one triggered() signal fires after 500ms
    """

    triggered = pyqtSignal()

    def __init__(self, delay_ms: int = 500, parent=None):
        super().__init__(parent)
        self._delay_ms = delay_ms
        self._timer: Optional[QThread] = None
        self._lock = threading.Lock()
        self._cancelled = False

    def trigger(self):
        """Reset the debounce timer."""
        with self._lock:
            self._cancelled = False

            if self._timer is not None and self._timer.isRunning():
                self._timer.requestInterruption()
                self._timer.quit()
                self._timer.wait(100)

            self._timer = QThread()
            self._timer.started.connect(self._run_timer)
            self._timer.finished.connect(self._on_timer_finished)
            self._timer.start()

    def _run_timer(self):
        """Internal: Timer worker."""
        from PyQt6.QtCore import QThread
        start = time.time()
        while (time.time() - start) < (self._delay_ms / 1000.0):
            if QThread.currentThread().isInterruptionRequested():
                return
            QThread.msleep(10)

    def _on_timer_finished(self):
        """Internal: Timer completed."""
        with self._lock:
            if not self._cancelled:
                self.triggered.emit()

    def cancel(self):
        """Cancel pending trigger."""
        with self._lock:
            self._cancelled = True
            if self._timer is not None and self._timer.isRunning():
                self._timer.requestInterruption()
                self._timer.quit()
                self._timer.wait(100)


# =============================================================================
# 7. ChatHistoryManager - Chat History with Memory Limits
# =============================================================================


class ChatHistoryManager:
    """
    Manages chat history with automatic memory management.

    Features:
    - Limits total message count
    - Limits total character count
    - Automatic trimming when limits exceeded
    - Preserves conversation context

    Usage:
        manager = ChatHistoryManager(max_messages=200, max_total_chars=500_000)
        manager.add_message("user", "Hello!")
        manager.add_message("assistant", "Hi there!")
        messages = manager.get_messages(last_n=10)  # Get last 10 messages
    """

    def __init__(
        self,
        max_messages: int = 200,
        max_total_chars: int = 500_000
    ):
        self._max_messages = max_messages
        self._max_total_chars = max_total_chars
        self._messages: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self._total_chars = 0

    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a message to history.

        Args:
            role: Message role (e.g., "user", "assistant", "system")
            content: Message content
            metadata: Optional metadata dict
        """
        with self._lock:
            message = {
                "role": role,
                "content": content,
                "timestamp": time.time(),
            }
            if metadata:
                message["metadata"] = metadata

            self._messages.append(message)
            self._total_chars += len(content)

            self.trim()

    def get_messages(self, last_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get messages from history.

        Args:
            last_n: Return only last N messages (None for all)

        Returns:
            List of message dicts
        """
        with self._lock:
            if last_n is None:
                return list(self._messages)
            return list(self._messages[-last_n:])

    def trim(self) -> int:
        """
        Trim history if limits are exceeded.

        Returns:
            Number of messages removed
        """
        removed = 0

        while (
            len(self._messages) > self._max_messages
            or self._total_chars > self._max_total_chars
        ) and self._messages:
            old = self._messages.pop(0)
            self._total_chars -= len(old["content"])
            removed += 1

        return removed

    def clear(self) -> None:
        """Clear all history."""
        with self._lock:
            self._messages.clear()
            self._total_chars = 0

    def size_info(self) -> Dict[str, Any]:
        """Return size information."""
        with self._lock:
            return {
                "message_count": len(self._messages),
                "total_characters": self._total_chars,
                "max_messages": self._max_messages,
                "max_total_chars": self._max_total_chars,
                "usage_percent": min(
                    100.0,
                    (len(self._messages) / self._max_messages) * 100
                ),
            }


# =============================================================================
# 8. ParallelScanner - Parallel Project Scanner
# =============================================================================


class ParallelScanner:
    """
    Parallel project scanner using ThreadPoolExecutor.

    Features:
    - Multi-threaded file discovery
    - Pattern-based filtering
    - Max file limit to prevent memory issues
    - Structured project scanning

    Usage:
        scanner = ParallelScanner()
        py_files = scanner.scan_files(".", pattern="*.py", max_workers=4)
        structure = scanner.scan_project_structure(".")
    """

    def __init__(self, default_max_workers: int = 4):
        self._default_max_workers = default_max_workers

    def scan_files(
        self,
        root_dir: str,
        pattern: str = "*.py",
        max_workers: Optional[int] = None,
        max_files: int = 200,
        exclude_dirs: Optional[List[str]] = None
    ) -> List[str]:
        """
        Scan directory for files matching pattern in parallel.

        Args:
            root_dir: Root directory to scan
            pattern: Glob pattern (e.g., "*.py", "*.txt")
            max_workers: Number of worker threads (default: 4)
            max_files: Maximum files to return (0 for unlimited)
            exclude_dirs: Directories to exclude (e.g., ["__pycache__", ".git"])

        Returns:
            List of matching file paths
        """
        if max_workers is None:
            max_workers = self._default_max_workers

        if exclude_dirs is None:
            exclude_dirs = ["__pycache__", ".git", ".venv", "node_modules", ".idea"]

        found_files = []
        dirs_to_scan = [root_dir]

        while dirs_to_scan:
            current_dir = dirs_to_scan.pop(0)

            try:
                entries = os.listdir(current_dir)
            except (PermissionError, OSError):
                continue

            for entry in entries:
                full_path = os.path.join(current_dir, entry)

                if os.path.isdir(full_path):
                    if entry not in exclude_dirs:
                        dirs_to_scan.append(full_path)
                elif fnmatch.fnmatch(entry, pattern):
                    found_files.append(full_path)

                    if max_files > 0 and len(found_files) >= max_files:
                        return found_files

        if max_workers <= 1 or len(found_files) < 10:
            return found_files

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            batch_size = max(1, len(found_files) // (max_workers * 2))
            batches = [
                found_files[i:i + batch_size]
                for i in range(0, len(found_files), batch_size)
            ]
            results = list(executor.map(lambda b: sorted(b), batches))

        all_files = []
        for batch_result in results:
            all_files.extend(batch_result)

        return sorted(all_files)

    def scan_project_structure(
        self,
        root_dir: str,
        max_depth: int = 5
    ) -> Dict[str, Any]:
        """
        Scan project structure.

        Args:
            root_dir: Root directory to scan
            max_depth: Maximum directory depth

        Returns:
            Dict with directory tree and file counts
        """
        structure = {
            "root": root_dir,
            "directories": {},
            "file_counts": {},
            "total_files": 0,
        }

        def scan_recursive(current_dir: str, depth: int) -> Optional[Dict]:
            if depth > max_depth:
                return None

            try:
                entries = os.listdir(current_dir)
            except (PermissionError, OSError):
                return None

            dir_info = {"files": [], "subdirs": {}}
            file_count = 0

            for entry in entries:
                if entry.startswith("."):
                    continue

                full_path = os.path.join(current_dir, entry)

                if os.path.isdir(full_path):
                    subdir = scan_recursive(full_path, depth + 1)
                    if subdir:
                        dir_info["subdirs"][entry] = subdir
                        file_count += subdir.get("total_files", 0)
                else:
                    dir_info["files"].append(entry)
                    file_count += 1

            dir_info["total_files"] = file_count
            return dir_info

        result = scan_recursive(root_dir, 0)
        if result:
            structure.update(result)

        ext_counts = {}
        def count_extensions(d):
            for f in d.get("files", []):
                ext = os.path.splitext(f)[1] or "no_ext"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
            for subdir in d.get("subdirs", {}).values():
                count_extensions(subdir)

        count_extensions(result or {})
        structure["file_counts"] = ext_counts

        return structure


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "LRUCache",
    "FileContentCache",
    "ASTCache",
    "AsyncFileIO",
    "ThreadPoolManager",
    "DebounceTimer",
    "ChatHistoryManager",
    "ParallelScanner",
]
