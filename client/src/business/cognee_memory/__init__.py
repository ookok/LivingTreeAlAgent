"""
Cognee 记忆增强适配器模块
遵循自我进化原则：从交互中学习记忆结构

架构指南参考: docs/LIVINGTREE_ARCHITECTURE_GUIDE.md (章节 5.3.1)
"""

from business.cognee_memory.cognee_memory_adapter import (
    CogneeMemoryAdapter,
    Memory,
    RecallResult,
)


__all__ = [
    "CogneeMemoryAdapter",
    "Memory",
    "RecallResult",
]
