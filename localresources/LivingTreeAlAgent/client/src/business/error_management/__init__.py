#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Error Management Module
======================

错误管理模块，提供错误日志记录、自动诊断和修复功能。
"""

from .error_logger import (
    get_error_logger,
    ErrorLogger,
    ErrorType,
    ErrorSeverity,
    catch_and_log_errors
)

from .auto_diagnosis import (
    get_auto_diagnoser,
    AutoDiagnoser,
    FixStrategy
)

__all__ = [
    "get_error_logger",
    "ErrorLogger",
    "ErrorType",
    "ErrorSeverity",
    "catch_and_log_errors",
    "get_auto_diagnoser",
    "AutoDiagnoser",
    "FixStrategy"
]
