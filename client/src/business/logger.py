"""
Logger — Re-export from livingtree.core.observability.logger

Full migration complete. Drop-in replacement.
"""

from livingtree.core.observability.logger import (
    StructuredLogger,
    LogEntry,
    LogLevel,
)

import logging as _logging
import os
from pathlib import Path


class LoggerShim(StructuredLogger):
    """Shim to match old `business.logger` API exactly"""
    def __init__(self, name: str = "livingtree"):
        log_dir = str(Path(__file__).parent.parent.parent.parent / "logs")
        super().__init__(module=name, log_dir=log_dir)
        self._py_logger = _logging.getLogger(name)
        self._py_logger.setLevel(_logging.INFO)

    def info(self, msg, *args, **kwargs):
        self._py_logger.info(msg, *args, **kwargs)
        super().info(str(msg), input_summary=str(msg)[:100])

    def debug(self, msg, *args, **kwargs):
        self._py_logger.debug(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._py_logger.warning(msg, *args, **kwargs)
        super().warn(str(msg))

    def error(self, msg, *args, **kwargs):
        self._py_logger.error(msg, *args, **kwargs)
        super().error(str(msg))

    def critical(self, msg, *args, **kwargs):
        self._py_logger.critical(msg, *args, **kwargs)
        super().fatal(str(msg))


_logger_instances = {}


def get_logger(name: str = "livingtree") -> LoggerShim:
    if name not in _logger_instances:
        _logger_instances[name] = LoggerShim(name)
    return _logger_instances[name]


logger = get_logger("livingtree")

__all__ = ["logger", "get_logger", "LoggerShim"]
