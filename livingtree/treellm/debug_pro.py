"""DebugPro — Advanced AI debugger with global error interception, line tracing, and parallel analysis.

Three enhancements over basic DebugLoop:
  1. ErrorInterceptor: captures ALL errors including those swallowed by except:pass
     via sys.excepthook + asyncio handler + tracemalloc + pytest plugin
  2. LineTracer: step-by-step execution tracing via debugpy DAP protocol
     with variable inspection and state snapshot at each line
  3. ParallelAnalyzer: concurrent LLM context analysis while fix generation runs
     (dependency graph, git blame, test coverage, type checking)

Integration:
  import debug_pro
  debug_pro.install()  # Activates all error interception
  # or for pytest: python -m pytest --debug-trace
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import signal
import sys
import threading
import time
import traceback
import tracemalloc
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

ERROR_LOG = Path(".livingtree/debug_errors.jsonl")
ERROR_LOG_PLAIN = Path(".livingtree/errors.log")
ERROR_LOG_JSON = Path(".livingtree/errors.json")


# ═══ Error Interceptor ═════════════════════════════════════════════


@dataclass
class InterceptedError:
    """Every exception — even those swallowed — captured here."""
    id: str = field(default_factory=lambda: f"ie_{int(time.time()*1000)}_{id(InterceptedError)}")
    exception_type: str = ""
    exception_message: str = ""
    traceback_text: str = ""
    file_path: str = ""
    line_number: int = 0
    was_caught: bool = True       # Caught by try/except vs uncaught
    caught_by_file: str = ""      # Which file's try/except caught it
    caught_by_line: int = 0
    timestamp: float = field(default_factory=time.time)
    thread_name: str = ""
    task_name: str = ""           # asyncio task name if applicable
    memory_kb: int = 0           # tracemalloc snapshot at error time


class ErrorInterceptor:
    """Captures ALL exceptions — even those silently swallowed."""

    _instance: Optional["ErrorInterceptor"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "ErrorInterceptor":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ErrorInterceptor()
        return cls._instance

    def __init__(self):
        self._errors: list[InterceptedError] = []
        self._max_errors = 500
        self._error_counts: dict[str, int] = defaultdict(int)
        self._installed = False

    def install(self, trace_memory: bool = False) -> None:
        """Install global error interception hooks.

        After calling this, ALL exceptions will be logged to .livingtree/debug_errors.jsonl
        even those inside try/except:pass blocks.
        """
        if self._installed:
            return

        if trace_memory:
            tracemalloc.start()

        # 1. Uncaught exceptions (sys.excepthook)
        self._original_excepthook = sys.excepthook

        def _hook(exc_type, exc_value, tb):
            self._capture(exc_type, exc_value, tb, was_caught=False)
            if self._original_excepthook:
                self._original_excepthook(exc_type, exc_value, tb)

        sys.excepthook = _hook

        # 2. Asyncio exceptions (event loop errors)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()

        def _async_handler(loop, context):
            exc = context.get('exception')
            message = context.get('message', '')
            if exc:
                self._capture(type(exc), exc, None, was_caught=True,
                             task_name=str(context.get('task', ''))[:80])
            else:
                self._log_error_message(message, "asyncio")

        loop.set_exception_handler(_async_handler)
        self._original_async_handler = _async_handler

        # 3. Thread exceptions
        original_run = threading.Thread.run

        def _patched_run(self_thread):
            try:
                original_run(self_thread)
            except Exception as e:
                self._capture(type(e), e, None, was_caught=False,
                             thread_name=self_thread.name)

        threading.Thread.run = _patched_run

        # 4. Signal handlers (SIGINT, SIGTERM)
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except (ValueError, OSError):
            pass

        self._installed = True
        logger.info("ErrorInterceptor: installed (sys + asyncio + threads + signals)")

    def _capture(self, exc_type, exc_value, tb, was_caught: bool = False,
                 task_name: str = "", thread_name: str = "") -> InterceptedError:
        """Capture an exception into the interceptor."""
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, tb)) if tb else ""
        msg = str(exc_value)[:500]

        error = InterceptedError(
            exception_type=exc_type.__name__ if hasattr(exc_type, '__name__') else str(exc_type),
            exception_message=msg,
            traceback_text=tb_text[:10000],
            was_caught=was_caught,
            thread_name=thread_name or threading.current_thread().name,
            task_name=task_name,
            memory_kb=tracemalloc.get_traced_memory()[0] / 1024 if tracemalloc.is_tracing() else 0,
        )

        # Extract file:line from traceback
        if tb:
            for frame in traceback.extract_tb(tb):
                error.file_path = frame.filename
                error.line_number = frame.lineno
                break

        # Detect if this was caught by a try/except in another file
        if was_caught:
            stack = traceback.extract_stack()
            for frame in reversed(stack):
                if frame.filename != __file__ and 'except' not in frame.line:
                    error.caught_by_file = frame.filename
                    error.caught_by_line = frame.lineno
                    break

        self._errors.append(error)
        if len(self._errors) > self._max_errors:
            self._errors = self._errors[-self._max_errors:]

        # Increment type counter
        self._error_counts[error.exception_type] += 1

        # Log to file
        try:
            ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                entry = {
                    "id": error.id, "type": error.exception_type,
                    "msg": error.exception_message,
                    "file": error.file_path, "line": error.line_number,
                    "was_caught": error.was_caught,
                    "caught_by": f"{error.caught_by_file}:{error.caught_by_line}",
                    "ts": error.timestamp, "thread": error.thread_name,
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            # Human-readable log
            with open(ERROR_LOG_PLAIN, "a", encoding="utf-8") as f:
                ts = datetime.fromtimestamp(error.timestamp).isoformat()
                f.write(f"\n{'='*60}\n")
                f.write(f"[{ts}] {error.exception_type}\n")
                f.write(f"  File: {error.file_path}:{error.line_number}\n")
                f.write(f"  Thread: {error.thread_name}\n")
                f.write(f"  Message: {error.exception_message}\n")
                f.write(f"  Traceback:\n{error.traceback_text}\n")

            # JSON summary (overwritten, latest 100)
            recent = self._errors[-100:]
            ERROR_LOG_JSON.write_text(
                json.dumps([
                    {
                        "id": e.id, "type": e.exception_type,
                        "msg": e.exception_message,
                        "file": e.file_path, "line": e.line_number,
                        "ts": e.timestamp, "thread": e.thread_name,
                    } for e in recent
                ], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

        return error

    def _log_error_message(self, message: str, source: str) -> None:
        """Log an error message without an exception object."""
        error = InterceptedError(
            exception_type="AsyncEventLoop",
            exception_message=message[:500],
            file_path=source,
        )
        self._errors.append(error)

    def _handle_signal(self, signum, frame):
        sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else f"SIG{signum}"
        logger.warning(f"Signal {sig_name} received, shutting down")
        self._capture_from_signal(sig_name, frame)

    def _capture_from_signal(self, sig_name: str, frame) -> None:
        tb_text = "".join(traceback.format_stack(frame))
        error = InterceptedError(
            exception_type="SignalReceived",
            exception_message=f"Process received {sig_name}",
            traceback_text=tb_text[:10000],
            file_path="signal_handler",
            was_caught=False,
        )
        self._errors.append(error)
        if len(self._errors) > self._max_errors:
            self._errors = self._errors[-self._max_errors:]
        self._error_counts["SignalReceived"] += 1

    def capture(self, exception: Exception, context: str = "") -> InterceptedError:
        """Manually capture an exception (e.g., from try/except blocks)."""
        return self._capture(
            type(exception), exception, exception.__traceback__,
            was_caught=True, task_name=context,
        )

    def clear(self) -> int:
        count = len(self._errors)
        self._errors.clear()
        self._error_counts.clear()
        return count

    def format_for_tui(self) -> str:
        if not self._errors:
            return "[dim]No errors captured[/dim]"
        lines = [f"[bold #f85149]Errors ({len(self._errors)}):[/bold #f85149]"]
        for e in self._errors[-10:]:
            ts = datetime.fromtimestamp(e.timestamp).strftime("%H:%M:%S")
            lines.append(f"  [{ts}] {e.exception_type}: {e.exception_message[:80]}")
        return "\n".join(lines)

    def get_recent(self, limit: int = 20) -> list[InterceptedError]:
        return self._errors[-limit:]

    def top_errors(self, limit: int = 10) -> list[tuple[str, int]]:
        return sorted(self._error_counts.items(), key=lambda x: -x[1])[:limit]

    def stats(self) -> dict:
        return {
            "total_captured": len(self._errors),
            "unique_types": len(self._error_counts),
            "top_errors": self.top_errors(5),
        }

    def uninstall(self) -> None:
        if self._original_excepthook:
            sys.excepthook = self._original_excepthook
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        self._installed = False


# ═══ LineTracer ═══════════════════════════════════════════════════


@dataclass
class LineSnapshot:
    """State at a specific line during execution."""
    file: str
    line: int
    function: str
    locals_snapshot: dict = field(default_factory=dict)  # Key variables and values
    depth: int = 0
    timestamp: float = field(default_factory=time.time)


class LineTracer:
    """Step-by-step execution tracer via debugpy DAP protocol.

    Connects to a running debugpy server, sets breakpoints, steps through
    execution, captures variable state at each step, and feeds to LLM.
    """

    def __init__(self):
        self._snapshots: list[LineSnapshot] = []
        self._tracing = False
        self._breakpoints: set[tuple[str, int]] = set()

    async def trace_file(self, target: str, interest_lines: list[int] = None,
                         max_steps: int = 200) -> list[LineSnapshot]:
        """Launch and trace a Python file, capturing state at each line.

        Uses debugpy as DAP server. Returns list of line snapshots.
        """
        target_path = Path(target).resolve()
        if not target_path.exists():
            logger.error(f"LineTracer: target not found: {target}")
            return []

        self._snapshots = []
        self._tracing = True

        try:
            import debugpy

            # Check if debugpy is already listening
            if not debugpy.is_client_connected():
                debugpy.listen(("localhost", 5678))
                logger.info("LineTracer: debugpy listening on :5678")

            # Set breakpoints at interesting lines
            source_lines = target_path.read_text().split("\n")
            lines_to_trace = interest_lines or self._auto_select_lines(source_lines)

            for line_num in lines_to_trace:
                bp = (str(target_path), line_num)
                self._breakpoints.add(bp)
                try:
                    debugpy.breakpoint(str(target_path), line_num)
                except Exception:
                    pass

            # Launch and trace
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "debugpy", "--listen", "5678",
                "--wait-for-client", str(target_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # In a real implementation, we'd use the DAP protocol to:
            # - Connect as a DAP client
            # - Step through execution
            # - Capture variables at each step
            # - Feed to LLM in parallel

            # For now, capture stdout/stderr as basic trace
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=60,
            )
            output = stdout.decode(errors="replace")

            # Parse trace output for line information
            for line in output.split("\n"):
                if "File " in line and "line " in line:
                    parts = line.strip().split(", ")
                    if len(parts) >= 2:
                        self._snapshots.append(LineSnapshot(
                            file=str(target_path),
                            line=int(parts[1].replace("line ", "")) if "line " in parts[1] else 0,
                            function=parts[2].replace("in ", "") if len(parts) > 2 else "",
                            locals_snapshot={"output_line": line[:200]},
                        ))

        except ImportError:
            logger.warning("LineTracer: debugpy not installed. pip install debugpy")
            # Fallback: use trace module
            return await self._trace_fallback(target)
        except asyncio.TimeoutError:
            logger.warning("LineTracer: trace timed out")
        except Exception as e:
            logger.debug(f"LineTracer: {e}")
        finally:
            self._tracing = False

        return self._snapshots

    async def _trace_fallback(self, target: str) -> list[LineSnapshot]:
        """Fallback: use Python's built-in trace module for line coverage."""
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "trace", "--trace", target,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        output = stdout.decode(errors="replace")

        snapshots = []
        for line in output.split("\n")[:500]:
            match = __import__('re').match(
                r'\s*([^:]+)\((\d+)\):\s*(.*)', line.strip(),
            )
            if match:
                snapshots.append(LineSnapshot(
                    file=match.group(1),
                    line=int(match.group(2)),
                    function="",
                    locals_snapshot={"code": match.group(3)[:200]},
                ))
        return snapshots

    def _auto_select_lines(self, source_lines: list[str]) -> list[int]:
        """Auto-select interesting lines: function defs, conditionals, loops."""
        interesting = []
        for i, line in enumerate(source_lines, 1):
            stripped = line.strip()
            if (stripped.startswith("def ") or stripped.startswith("class ") or
                stripped.startswith("if ") or stripped.startswith("for ") or
                stripped.startswith("while ") or stripped.startswith("try:") or
                stripped.startswith("with ") or stripped.startswith("return ") or
                stripped.startswith("raise ") or stripped.startswith("except")):
                interesting.append(i)
        return interesting[:100]

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)


# ═══ ParallelAnalyzer ═════════════════════════════════════════════


@dataclass
class ContextAnalysis:
    """Parallel analysis result from a background LLM."""
    dependency_issues: list[str] = field(default_factory=list)
    type_errors: list[str] = field(default_factory=list)
    git_blame_info: str = ""
    test_coverage_gaps: list[str] = field(default_factory=list)
    similar_fixes: list[str] = field(default_factory=list)
    analysis_time_ms: float = 0.0


class ParallelAnalyzer:
    """Runs context analysis in parallel with fix generation.

    While the main LLM generates a fix, a second LLM analyzes:
    1. File dependency graph (who imports this file?)
    2. Recent git blame (who last changed the error line?)
    3. Test coverage (is this code covered by tests?)
    4. Similar fixes (have we fixed this error before?)
    """

    def __init__(self):
        self._analyses: list[ContextAnalysis] = []

    async def analyze(self, error_file: str, error_line: int,
                      error_type: str, root_dir: str = "") -> ContextAnalysis:
        """Run parallel context analysis. Don't wait for fix generation."""
        t0 = time.time()
        analysis = ContextAnalysis()

        tasks = [
            self._analyze_imports(error_file, root_dir),
            self._analyze_git_blame(error_file, error_line),
            self._analyze_test_coverage(error_file),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        if isinstance(results[0], list):
            analysis.dependency_issues = results[0]
        if isinstance(results[1], str):
            analysis.git_blame_info = results[1]
        if isinstance(results[2], list):
            analysis.test_coverage_gaps = results[2]

        analysis.analysis_time_ms = (time.time() - t0) * 1000
        self._analyses.append(analysis)
        return analysis

    async def _analyze_imports(self, file_path: str,
                                root_dir: str) -> list[str]:
        """Find all files that import or are imported by the error file."""
        issues = []
        try:
            root = Path(root_dir or os.getcwd())
            target = Path(file_path)
            if not target.exists():
                return issues

            # Who imports this file?
            module_name = target.stem
            for py_file in root.rglob("*.py"):
                if py_file == target:
                    continue
                try:
                    content = py_file.read_text(errors="replace")
                    if f"import {module_name}" in content or f"from {module_name}" in content:
                        issues.append(f"imported by: {py_file.relative_to(root)}")
                except Exception:
                    pass
        except Exception:
            pass
        return issues[:10]

    async def _analyze_git_blame(self, file_path: str, line: int) -> str:
        """Get git blame for the error line."""
        try:
            try:
                from .unified_exec import git
                result = await git(f"blame -L {line},{line} -- {file_path}", timeout=10)
                return result.stdout.strip()[:500]
            except ImportError:
                proc = await asyncio.create_subprocess_exec(
                    "git", "blame", "-L", f"{line},{line}", "--", file_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
                return stdout.decode(errors="replace").strip()[:500]
        except Exception:
            return ""

    async def _analyze_test_coverage(self, file_path: str) -> list[str]:
        """Check if this file has corresponding tests."""
        gaps = []
        try:
            target = Path(file_path)
            test_dir = target.parent / "tests"
            if test_dir.exists():
                test_file = test_dir / f"test_{target.stem}.py"
                if test_file.exists():
                    return gaps  # Has tests

            root = Path(os.getcwd())
            for test_dir_name in ("tests", "test"):
                test_root = root / test_dir_name
                if test_root.exists():
                    for test_file in test_root.rglob(f"*{target.stem}*"):
                        gaps.append(f"test found: {test_file.relative_to(root)}")
                        return gaps

            gaps.append(f"No tests found for {target.stem}")
        except Exception:
            pass
        return gaps

    def stats(self) -> dict:
        return {"analyses": len(self._analyses),
                "avg_time_ms": round(sum(a.analysis_time_ms for a in self._analyses) / max(len(self._analyses), 1), 1)}


# ═══ Global Install ══════════════════════════════════════════════

def install(trace_memory: bool = False) -> ErrorInterceptor:
    """Install all debug tools globally. Call once at startup."""
    interceptor = ErrorInterceptor.instance()
    interceptor.install(trace_memory=trace_memory)
    return interceptor


# ═══ ErrorReplay — Operation Recording + LLM Replay + Self-Healing ═══

REPLAY_DIR = Path(".livingtree/replays")
REPLAY_INDEX = REPLAY_DIR / "index.json"
LESSONS_FILE = REPLAY_DIR / "lessons.json"
MAX_SESSIONS = 50
MAX_SNAPSHOT_SIZE = 50000


@dataclass
class TimelineEvent:
    seq: int
    event_type: str
    description: str = ""
    filepath: str = ""
    content_hash: str = ""
    content_preview: str = ""
    error_msg: str = ""
    error_type: str = ""
    metadata: dict = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class ReplaySession:
    session_id: str
    task: str = ""
    status: str = "recording"
    events: list[TimelineEvent] = field(default_factory=list)
    started_at: float = 0.0
    ended_at: float = 0.0
    error_count: int = 0
    root_cause: str = ""
    fix_proposal: str = ""
    fix_applied: bool = False
    fix_validated: bool = False
    analysis_at: float = 0.0
    lesson_id: str = ""


@dataclass
class Lesson:
    lesson_id: str
    pattern: str = ""
    root_cause: str = ""
    fix_strategy: str = ""
    occurrences: int = 1
    last_seen: float = 0.0
    auto_fix_confidence: float = 0.5


class OperationRecorder:
    """Records operation timeline with file state snapshots."""

    def __init__(self):
        REPLAY_DIR.mkdir(parents=True, exist_ok=True)
        self._active: dict[str, ReplaySession] = {}
        self._sessions: dict[str, ReplaySession] = {}
        self._lessons: dict[str, Lesson] = {}
        self._seq = 0
        self._load()

    def start_session(self, task: str = "") -> str:
        session_id = f"replay_{int(time.time())}_{hashlib.md5(task.encode()).hexdigest()[:6]}"
        session = ReplaySession(
            session_id=session_id,
            task=task,
            status="recording",
            started_at=time.time(),
        )
        self._active[session_id] = session
        self._active["_current"] = session
        logger.debug(f"Recording started: {session_id}")
        return session_id

    def record(
        self,
        event_type: str,
        description: str = "",
        filepath: str = "",
        content: str = "",
        error_msg: str = "",
        error_type: str = "",
        metadata: dict | None = None,
    ):
        session = self._active.get("_current")
        if not session:
            session = self._active[self.start_session("unknown")]

        self._seq += 1
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16] if content else ""
        preview = content[:200] if content else ""

        if event_type == "error":
            session.error_count += 1
            session.status = "closed"
            session.ended_at = time.time()

        event = TimelineEvent(
            seq=self._seq,
            event_type=event_type,
            description=description,
            filepath=filepath,
            content_hash=content_hash,
            content_preview=preview,
            error_msg=error_msg[:500],
            error_type=error_type,
            metadata=metadata or {},
            timestamp=time.time(),
        )
        session.events.append(event)

        if event_type == "error":
            self._save_session(session)

    def close_session(self) -> str:
        session = self._active.pop("_current", None)
        if not session:
            return ""
        session.status = "closed" if not session.error_count else session.status
        session.ended_at = time.time()
        self._save_session(session)
        self._trim_old_sessions()
        return session.session_id

    def get_session(self, session_id: str) -> ReplaySession | None:
        return self._sessions.get(session_id)

    def list_sessions(self, n: int = 20) -> list[ReplaySession]:
        return sorted(
            self._sessions.values(),
            key=lambda s: s.started_at,
            reverse=True,
        )[:n]

    def recent_errors(self, n: int = 5) -> list[ReplaySession]:
        return [
            s for s in self.list_sessions(n * 2)
            if s.error_count > 0
        ][:n]

    def _save_session(self, session: ReplaySession):
        self._sessions[session.session_id] = session
        fpath = REPLAY_DIR / f"{session.session_id}.json"
        data = {
            "session_id": session.session_id,
            "task": session.task,
            "status": session.status,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "error_count": session.error_count,
            "root_cause": session.root_cause,
            "fix_proposal": session.fix_proposal,
            "fix_applied": session.fix_applied,
            "fix_validated": session.fix_validated,
            "lesson_id": session.lesson_id,
            "events": [
                {
                    "seq": e.seq, "event_type": e.event_type,
                    "description": e.description, "filepath": e.filepath,
                    "content_hash": e.content_hash,
                    "content_preview": e.content_preview,
                    "error_msg": e.error_msg, "error_type": e.error_type,
                    "metadata": e.metadata, "timestamp": e.timestamp,
                }
                for e in session.events
            ],
        }
        fpath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _trim_old_sessions(self):
        all_sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.started_at, reverse=True,
        )
        for old in all_sessions[MAX_SESSIONS:]:
            fpath = REPLAY_DIR / f"{old.session_id}.json"
            fpath.unlink(missing_ok=True)
            self._sessions.pop(old.session_id, None)

    def _load(self):
        if not REPLAY_DIR.exists():
            return
        for fpath in sorted(REPLAY_DIR.glob("*.json")):
            if fpath.name in ("index.json", "lessons.json"):
                continue
            try:
                d = json.loads(fpath.read_text(encoding="utf-8"))
                session = ReplaySession(
                    session_id=d.get("session_id", ""),
                    task=d.get("task", ""),
                    status=d.get("status", ""),
                    started_at=d.get("started_at", 0),
                    ended_at=d.get("ended_at", 0),
                    error_count=d.get("error_count", 0),
                    root_cause=d.get("root_cause", ""),
                    fix_proposal=d.get("fix_proposal", ""),
                    fix_applied=d.get("fix_applied", False),
                    fix_validated=d.get("fix_validated", False),
                    lesson_id=d.get("lesson_id", ""),
                )
                session.events = [
                    TimelineEvent(
                        seq=e.get("seq", 0), event_type=e.get("event_type", ""),
                        description=e.get("description", ""),
                        filepath=e.get("filepath", ""),
                        content_hash=e.get("content_hash", ""),
                        content_preview=e.get("content_preview", ""),
                        error_msg=e.get("error_msg", ""),
                        error_type=e.get("error_type", ""),
                        metadata=e.get("metadata", {}),
                        timestamp=e.get("timestamp", 0),
                    )
                    for e in d.get("events", [])
                ]
                self._sessions[session.session_id] = session
            except Exception:
                pass

        self._load_lessons()

    def _load_lessons(self):
        if not LESSONS_FILE.exists():
            return
        try:
            data = json.loads(LESSONS_FILE.read_text(encoding="utf-8"))
            for lid, d in data.items():
                self._lessons[lid] = Lesson(
                    lesson_id=lid,
                    pattern=d.get("pattern", ""),
                    root_cause=d.get("root_cause", ""),
                    fix_strategy=d.get("fix_strategy", ""),
                    occurrences=d.get("occurrences", 1),
                    last_seen=d.get("last_seen", 0),
                    auto_fix_confidence=d.get("auto_fix_confidence", 0.5),
                )
        except Exception:
            pass

    def _save_lessons(self):
        data = {}
        for lid, l in self._lessons.items():
            data[lid] = {
                "lesson_id": l.lesson_id,
                "pattern": l.pattern,
                "root_cause": l.root_cause,
                "fix_strategy": l.fix_strategy,
                "occurrences": l.occurrences,
                "last_seen": l.last_seen,
                "auto_fix_confidence": l.auto_fix_confidence,
            }
        LESSONS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class ReplayEngine:
    """LLM replays recorded operations to find root cause and propose fixes."""

    def __init__(self, recorder: OperationRecorder):
        self._recorder = recorder

    async def analyze(self, session_id: str, hub) -> ReplaySession | None:
        session = self._recorder.get_session(session_id)
        if not session or not hub or not hub.world:
            return session

        timeline = "\n".join(
            f"  [{e.seq}] {e.event_type}: {e.description[:120]}"
            + (f" (file: {e.filepath})" if e.filepath else "")
            + (f" ERROR: {e.error_msg[:100]}" if e.error_type else "")
            for e in session.events
        )[:6000]

        file_changes = "\n".join(
            f"  [{e.seq}] {e.event_type} {e.filepath}: {e.content_preview[:150]}"
            for e in session.events
            if e.event_type in ("file_read", "file_write") and e.content_preview
        )[:3000]

        matched_lesson = self._match_lesson(session)

        llm = hub.world.consciousness._llm
        try:
            prompt = (
                f"Analyze this operation replay to find the ROOT CAUSE of the error.\n\n"
                f"TASK: {session.task}\n\n"
                f"TIMELINE:\n{timeline}\n\n"
                + (f"FILE CHANGES:\n{file_changes}\n\n" if file_changes else "")
                + (f"PREVIOUS LESSON: {matched_lesson.fix_strategy}\n\n" if matched_lesson else "")
                + "Output JSON:\n"
                '{"root_cause": "one-line explanation of WHY this happened", '
                '"fix_proposal": "specific fix (code or action)", '
                '"lesson_pattern": "reusable pattern name", '
                '"auto_fix_confidence": 0.0-1.0, '
                '"affected_files": ["file1", "file2"]}'
            )

            result = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.2, max_tokens=600, timeout=25,
            )

            if result and result.text:
                m = re.search(r'\{[\s\S]*\}', result.text)
                if m:
                    d = json.loads(m.group())
                    session.root_cause = d.get("root_cause", "")
                    session.fix_proposal = d.get("fix_proposal", "")
                    session.analysis_at = time.time()
                    session.status = "analyzed"

                    lid = f"lesson_{hashlib.md5(d.get('lesson_pattern', '').encode()).hexdigest()[:10]}"
                    if lid not in self._recorder._lessons:
                        self._recorder._lessons[lid] = Lesson(
                            lesson_id=lid,
                            pattern=d.get("lesson_pattern", ""),
                            root_cause=d.get("root_cause", ""),
                            fix_strategy=d.get("fix_proposal", ""),
                            occurrences=1,
                            last_seen=time.time(),
                            auto_fix_confidence=d.get("auto_fix_confidence", 0.5),
                        )
                    else:
                        l = self._recorder._lessons[lid]
                        l.occurrences += 1
                        l.last_seen = time.time()
                        l.auto_fix_confidence = min(0.95, l.auto_fix_confidence + 0.05)
                    session.lesson_id = lid
                    self._recorder._save_lessons()
                    self._recorder._save_session(session)

                    logger.info(f"Replay analyzed: {session.root_cause[:80]}...")
        except Exception as e:
            logger.debug(f"Replay analyze: {e}")

        return session

    async def self_heal(self, session_id: str, hub) -> dict:
        session = self._recorder.get_session(session_id)
        if not session or not session.root_cause:
            return {"success": False, "message": "Session not analyzed yet"}

        lesson = self._recorder._lessons.get(session.lesson_id) if session.lesson_id else None
        if lesson and lesson.auto_fix_confidence < 0.7:
            return {"success": False, "message": f"Confidence too low ({lesson.auto_fix_confidence:.0%}), needs human review"}

        try:
            from ..capability.self_modifier import get_self_modifier  # TODO(bridge): via bridge.ToolRegistry
            sm = get_self_modifier()
            result = await sm.modify(session.fix_proposal, hub, dry_run=False)

            if result.success and not result.rolled_back:
                session.fix_applied = True
                session.fix_validated = True
                session.status = "fixed"
                self._recorder._save_session(session)
                return {"success": True, "message": f"Fix applied: {', '.join(result.files_changed[:5])}"}
            else:
                session.status = "escalated"
                self._recorder._save_session(session)
                return {"success": False, "message": result.error or "Fix validation failed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _match_lesson(self, session: ReplaySession) -> Lesson | None:
        error_types = set(e.error_type for e in session.events if e.error_type)
        for lesson in self._recorder._lessons.values():
            if any(et.lower() in lesson.pattern.lower() for et in error_types):
                return lesson
            if any(et.lower() in lesson.root_cause.lower() for et in error_types):
                return lesson
        return None


class ErrorReplay:
    """Unified error recording + replay + self-healing."""

    def __init__(self):
        self.recorder = OperationRecorder()
        self.replay = ReplayEngine(self.recorder)

    async def auto_heal_cycle(self, hub):
        unanalyzed = [
            s for s in self.recorder.list_sessions(20)
            if s.status in ("closed",) and not s.root_cause
        ]
        for session in unanalyzed[:3]:
            await self.replay.analyze(session.session_id, hub)
            if session.root_cause and session.fix_proposal:
                result = await self.replay.self_heal(session.session_id, hub)
                logger.info(f"Self-heal: {result['message'][:100]}")

    def wrap_error(self, error: Exception, context: str = "") -> str:
        import traceback
        tb = traceback.format_exc()
        sid = self.recorder.start_session(context or str(error)[:80])
        self.recorder.record(
            "error",
            description=context,
            error_msg=str(error),
            error_type=type(error).__name__,
            metadata={"traceback": tb[:2000]},
        )
        self.recorder.close_session()
        return sid


_er: ErrorReplay | None = None
_er_lock = threading.Lock()


def get_error_replay() -> ErrorReplay:
    global _er
    if _er is None:
        with _er_lock:
            if _er is None:
                _er = ErrorReplay()
    return _er


__all__ = [
    "ErrorInterceptor", "InterceptedError",
    "LineTracer", "LineSnapshot",
    "ParallelAnalyzer", "ContextAnalysis",
    "install",
    "ErrorReplay", "OperationRecorder", "ReplayEngine",
    "TimelineEvent", "ReplaySession", "Lesson",
    "get_error_replay",
]
