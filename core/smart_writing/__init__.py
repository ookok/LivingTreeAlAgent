# -*- coding: utf-8 -*-
"""
智能写作模块 - Smart Writing Module
====================================

提供意图驱动的智能写作、代码生成、文件操作等能力。

主要组件：
- streaming_output: 流式输出（打字机效果）
- progress_visualizer: 进度可视化
- error_recovery: 错误恢复机制
- multimodal_output: 统一多模态输出管理
- pyqt6_integration: PyQt6 GUI 集成

Author: Hermes Desktop Team
"""

# =============================================================================
# Phase 4: 多模态交互模块
# =============================================================================

# 流式输出
from .streaming_output import (
    StreamingConfig,
    StreamingOutput,
    EnhancedStreamingOutput,
    typewriter_effect,
    stream_markdown,
)

# 进度可视化
from .progress_visualizer import (
    ProgressData,
    ProgressManager,
    ProgressRenderer,
    ProgressStatus,
    ProgressStyle,
    QtProgressWidget,
    TerminalRenderer,
    get_progress_manager,
    progress,
)

# 错误恢复
from .error_recovery import (
    ErrorType,
    RecoveryAction,
    RecoverableError,
    NetworkError,
    TimeoutError,
    RateLimitError,
    ValidationError,
    RetryPolicy,
    Checkpoint,
    CheckpointManager,
    CircuitBreaker,
    FallbackStrategy,
    ReturnNoneFallback,
    ReturnDefaultFallback,
    FallbackChain,
    RecoveryContext,
    RecoveryExecutor,
    get_recovery_executor,
    get_checkpoint_manager,
)

# 多模态输出管理器
from .multimodal_output import (
    OutputMode,
    OutputEvent,
    OutputEventType,
    OutputHandler,
    PyQtOutputHandler,
    ConsoleOutputHandler,
    EventBus,
    MultimodalOutputManager,
    ProgressTracker,
    get_output_manager,
    set_output_manager,
    output_stream,
    output_progress,
    output_error,
    output_complete,
)

# PyQt6 集成
from .pyqt6_integration import (
    PyQtSignalBridge,
    StreamingTextWidget,
    ProgressWidget,
    PyQt6OutputManager,
    create_output_manager,
)


# =============================================================================
# 模块版本
# =============================================================================

__version__ = "1.0.0"
__all__ = [
    # 流式输出
    "StreamingConfig",
    "StreamingOutput",
    "EnhancedStreamingOutput",
    "typewriter_effect",
    "stream_markdown",
    # 进度可视化
    "ProgressData",
    "ProgressManager",
    "ProgressRenderer",
    "ProgressStatus",
    "ProgressStyle",
    "QtProgressWidget",
    "TerminalRenderer",
    "get_progress_manager",
    "progress",
    # 错误恢复
    "ErrorType",
    "RecoveryAction",
    "RecoverableError",
    "NetworkError",
    "TimeoutError",
    "RateLimitError",
    "ValidationError",
    "RetryPolicy",
    "Checkpoint",
    "CheckpointManager",
    "CircuitBreaker",
    "FallbackStrategy",
    "ReturnNoneFallback",
    "ReturnDefaultFallback",
    "FallbackChain",
    "RecoveryContext",
    "RecoveryExecutor",
    "get_recovery_executor",
    "get_checkpoint_manager",
    # 多模态输出
    "OutputMode",
    "OutputEvent",
    "OutputEventType",
    "OutputHandler",
    "PyQtOutputHandler",
    "ConsoleOutputHandler",
    "EventBus",
    "MultimodalOutputManager",
    "ProgressTracker",
    "get_output_manager",
    "set_output_manager",
    "output_stream",
    "output_progress",
    "output_error",
    "output_complete",
    # PyQt6 集成
    "PyQtSignalBridge",
    "StreamingTextWidget",
    "ProgressWidget",
    "PyQt6OutputManager",
    "create_output_manager",
]
