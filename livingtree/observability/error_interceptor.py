"""Error Interceptor — Global error capture with TUI display and file logging.

Hooks:
- sys.excepthook: all unhandled sync exceptions
- asyncio exception handler: all unhandled async exceptions  
- Signal handlers: Ctrl+C, SIGTERM

On error:
1. Writes to .livingtree/errors.log with full traceback + context
2. Shows notification in TUI (when app is running)
3. Updates footer status bar with error count
4. Keeps last 100 errors in memory for /errors command

Usage:
    from livingtree.observability.error_interceptor import install
    
    # Once at app startup:
    install()
    
    # In chat:
    /errors → list recent errors
    /errors clear → clear error history
"""

from __future__ import annotations

import asyncio
import json
import signal
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger


@dataclass
class CapturedError:
    id: int
    timestamp: str
    exception_type: str
    message: str
    traceback: str
    location: str
    thread: str
    is_async: bool = False
    severity: str = "error"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "type": self.exception_type,
            "message": self.message,
            "location": self.location,
            "traceback": self.traceback[-1000:],
            "thread": self.thread,
            "async": self.is_async,
        }

    def format_display(self) -> str:
        loc = self.location[:60]
        return (
            f"[bold #f85149]{self.exception_type}[/bold #f85149] "
            f"[dim]at {loc}[/dim]\n"
            f"  {self.message[:150]}"
        )


class ErrorInterceptor:
    """Global error capture, display, and logging."""

    ERROR_LOG = ".livingtree/errors.log"
    ERROR_JSON = ".livingtree/errors.json"
    MAX_MEMORY = 100

    def __init__(self):
        self._errors: list[CapturedError] = []
        self._counter = 0
        self._original_excepthook = sys.excepthook
        self._original_async_handler = None
        self._tui_app: Any = None
        self._installed = False

    def install(self, tui_app: Any = None) -> None:
        if self._installed:
            return

        self._tui_app = tui_app

        sys.excepthook = self._handle_sync_error
        self._hook_asyncio()

        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except (ValueError, OSError):
            pass

        self._installed = True
        logger.info("ErrorInterceptor installed (sync + async + signals)")

        if self._tui_app:
            self._tui_app._error_interceptor = self

    def uninstall(self) -> None:
        if not self._installed:
            return
        sys.excepthook = self._original_excepthook
        self._installed = False

    def capture(self, exception: Exception, context: str = "") -> CapturedError:
        return self._record(
            exception_type=type(exception).__name__,
            message=str(exception),
            tb_str=traceback.format_exc(),
            location=context or "manual_capture",
            thread="main",
        )

    def get_recent(self, count: int = 20) -> list[dict]:
        return [e.to_dict() for e in self._errors[-count:]]

    def get_stats(self) -> dict:
        types = {}
        for e in self._errors:
            types[e.exception_type] = types.get(e.exception_type, 0) + 1

        recent_60s = sum(
            1 for e in self._errors
            if time.time() - self._parse_timestamp(e.timestamp) < 60
        )

        return {
            "total_errors": len(self._errors),
            "installed": self._installed,
            "recent_60s": recent_60s,
            "top_types": dict(sorted(types.items(), key=lambda x: x[1], reverse=True)[:5]),
        }

    def clear(self) -> int:
        count = len(self._errors)
        self._errors.clear()
        self._counter = 0
        return count

    def format_for_tui(self) -> str:
        if not self._errors:
            return "[dim]No errors captured[/dim]"

        lines = [f"[bold #f85149]Errors ({len(self._errors)}):[/bold #f85149]"]
        for e in self._errors[-10:]:
            lines.append(f"  [{e.timestamp[11:19]}] {e.exception_type}: {e.message[:80]}")
        return "\n".join(lines)

    # ── Private ──

    def _handle_sync_error(self, exc_type, exc_value, exc_tb):
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        location = ""
        if exc_tb:
            frame = traceback.extract_tb(exc_tb)
            if frame:
                last = frame[-1]
                location = f"{last.filename}:{last.lineno} in {last.name}"

        self._record(
            exception_type=exc_type.__name__,
            message=str(exc_value),
            tb_str=tb_str,
            location=location,
            thread="main",
            is_async=False,
        )

        if self._tui_app and hasattr(self._tui_app, 'notify'):
            try:
                self._tui_app.notify(
                    f"{exc_type.__name__}: {str(exc_value)[:80]}",
                    severity="error",
                    timeout=8,
                )
            except Exception:
                pass

        self._original_excepthook(exc_type, exc_value, exc_tb)

    def _handle_async_error(self, loop, context):
        exception = context.get("exception")
        message = context.get("message", "")

        tb_str = ""
        if exception:
            tb_str = "".join(traceback.format_exception(
                type(exception), exception, exception.__traceback__,
            ))

        self._record(
            exception_type=type(exception).__name__ if exception else "AsyncError",
            message=message or str(exception or ""),
            tb_str=tb_str,
            location=context.get("task", "unknown"),
            thread="async",
            is_async=True,
        )

        self._original_async_handler(loop, context)

    def _handle_signal(self, signum, frame):
        sig_name = signal.Signals(signum).name
        logger.warning(f"Signal {sig_name} received, shutting down")
        self._record(
            exception_type="SignalReceived",
            message=f"Process received {sig_name}",
            tb_str=traceback.format_stack(frame),
            location="signal_handler",
            thread="signal",
            severity="warning",
        )

        if self._tui_app and hasattr(self._tui_app, 'action_quit'):
            try:
                self._tui_app.action_quit()
            except Exception:
                pass

    def _record(
        self,
        exception_type: str,
        message: str,
        tb_str: str,
        location: str,
        thread: str,
        is_async: bool = False,
        severity: str = "error",
    ) -> CapturedError:
        self._counter += 1
        ts = datetime.now(timezone.utc).isoformat()

        error = CapturedError(
            id=self._counter,
            timestamp=ts,
            exception_type=exception_type,
            message=message,
            traceback=tb_str,
            location=location,
            thread=thread,
            is_async=is_async,
            severity=severity,
        )

        self._errors.append(error)
        if len(self._errors) > self.MAX_MEMORY:
            self._errors = self._errors[-self.MAX_MEMORY:]

        self._write_log(error)
        self._write_json()

        return error

    def _write_log(self, error: CapturedError) -> None:
        try:
            path = Path(self.ERROR_LOG)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"[{error.timestamp}] {error.exception_type} ({error.severity})\n")
                f.write(f"  Location: {error.location}\n")
                f.write(f"  Thread: {error.thread} {'(async)' if error.is_async else ''}\n")
                f.write(f"  Message: {error.message}\n")
                f.write(f"  Traceback:\n{error.traceback}\n")
        except Exception:
            pass

    def _write_json(self) -> None:
        try:
            path = Path(self.ERROR_JSON)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    [e.to_dict() for e in self._errors[-100:]],
                    ensure_ascii=False, indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _hook_asyncio(self) -> None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return

        self._original_async_handler = loop.get_exception_handler()
        loop.set_exception_handler(self._handle_async_error)

    @staticmethod
    def _parse_timestamp(ts: str) -> float:
        try:
            return datetime.fromisoformat(ts).timestamp()
        except Exception:
            return 0.0


# Singleton
_interceptor: Optional[ErrorInterceptor] = None


def install(tui_app: Any = None) -> ErrorInterceptor:
    global _interceptor
    if _interceptor is None:
        _interceptor = ErrorInterceptor()
    _interceptor.install(tui_app)
    return _interceptor


def get_interceptor() -> Optional[ErrorInterceptor]:
    return _interceptor
