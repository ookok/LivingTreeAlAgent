"""Structured logger using loguru with context propagation."""
from __future__ import annotations

import sys
from contextvars import ContextVar
from typing import Any

from loguru import logger


class LogContext:
    """Thread-safe context propagation for structured logging."""
    _session_id: ContextVar[str] = ContextVar("session_id", default="")
    _trace_id: ContextVar[str] = ContextVar("trace_id", default="")
    _agent_id: ContextVar[str] = ContextVar("agent_id", default="")

    @classmethod
    def set_session(cls, session_id: str) -> None:
        cls._session_id.set(session_id)

    @classmethod
    def get_session(cls) -> str:
        return cls._session_id.get()

    @classmethod
    def set_trace(cls, trace_id: str) -> None:
        cls._trace_id.set(trace_id)

    @classmethod
    def get_trace(cls) -> str:
        return cls._trace_id.get()

    @classmethod
    def set_agent(cls, agent_id: str) -> None:
        cls._agent_id.set(agent_id)

    @classmethod
    def get_agent(cls) -> str:
        return cls._agent_id.get()

    @classmethod
    def get_context(cls) -> dict[str, str]:
        ctx = {}
        sid = cls.get_session()
        tid = cls.get_trace()
        aid = cls.get_agent()
        if sid:
            ctx["session_id"] = sid
        if tid:
            ctx["trace_id"] = tid
        if aid:
            ctx["agent_id"] = aid
        return ctx


def _context_format(record: dict) -> str:
    """Custom log format with structured context."""
    ctx = LogContext.get_context()
    if ctx:
        extra = " | ".join(f"{k}={v}" for k, v in ctx.items())
        return f"<green>{{time:YYYY-MM-DD HH:mm:ss.SSS}}</green> | <level>{{level: <8}}</level> | <cyan>{{name}}</cyan>:<cyan>{{function}}</cyan>:<cyan>{{line}}</cyan> | {extra} | <level>{{message}}</level>\n"
    return "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>\n"


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
    rotation: str = "100 MB",
    retention: str = "30 days",
    json_format: bool = False,
) -> None:
    """Configure logging with structured format.

    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (None = console only)
        rotation: When to rotate log files
        retention: How long to keep rotated logs
        json_format: Whether to use JSON format for machine parsing
    """
    logger.remove()

    if json_format:
        logger.add(
            sys.stderr,
            level=level,
            format="{message}",
            serialize=True,
            colorize=False,
        )
    else:
        logger.add(
            sys.stderr,
            level=level,
            format=_context_format,
            colorize=True,
        )

    if log_file:
        logger.add(
            log_file,
            level=level,
            format=_context_format if not json_format else "{message}",
            rotation=rotation,
            retention=retention,
            serialize=json_format,
            encoding="utf-8",
        )

    logger.info(f"Logging initialized at level {level}")


def get_logger(name: str | None = None) -> Any:
    """Get a logger instance with optional module name binding."""
    if name:
        return logger.bind(name=name)
    return logger
