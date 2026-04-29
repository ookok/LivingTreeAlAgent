"""
AmphiLoop 模块

双向循环调度、状态持久化、动态终止判定、容错回滚与增量学习
"""

from .amphiloop_engine import (
    AmphiLoopEngine,
    CheckpointManager,
    Checkpoint,
    CheckpointStatus,
    RollbackManager,
    RollbackPoint,
    BidirectionalScheduler,
    ExecutionFeedback,
    DynamicTerminator,
    IncrementalLearning,
    RollbackStrategy,
    get_amphiloop_engine,
)

__all__ = [
    "AmphiLoopEngine",
    "CheckpointManager",
    "Checkpoint",
    "CheckpointStatus",
    "RollbackManager",
    "RollbackPoint",
    "BidirectionalScheduler",
    "ExecutionFeedback",
    "DynamicTerminator",
    "IncrementalLearning",
    "RollbackStrategy",
    "get_amphiloop_engine",
]
