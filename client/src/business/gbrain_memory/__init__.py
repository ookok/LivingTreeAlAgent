"""
GBrain - 个人 AI 记忆系统
Inspired by: https://github.com/garrytan/gbrain

核心设计理念：
1. Compiled Truth + Timeline - 每页记忆由两部分组成
2. MECE 分类目录 - 互斥且穷尽的分类体系
3. Human Authority - 人类永远是最终权威
4. Brain-First Lookup - 先查大脑再调用外部 API
5. 复利增长 - 每次对话都在让大脑变聪明

主要模块：
- models.py: 数据模型（BrainPage, Timeline, CompiledTruth）
- page_manager.py: 页面管理器（CRUD + Timeline 追加）
- search_engine.py: 搜索引擎（SQLite FTS5 + RRF 混合排序）
- agent_loop.py: Brain-Agent 循环（信号 → 实体检测 → READ/WRITE）
- sync.py: 同步管理（Git 仓库同步 + 导入/导出）
- ui/panel.py: PyQt6 管理面板
"""

from business.gbrain_memory.models import (
    BrainPage,
    MemoryCategory,
    TimelineEntry,
    CompiledTruth,
    EvidenceSource,
    BrainSignal,
    SignalType,
    EntityDetection,
    AgentResponse,
    MemoryQuery,
    MemorySearchResult,
    CATEGORY_STRUCTURE,
)

from business.gbrain_memory.page_manager import PageManager
from business.gbrain_memory.search_engine import SearchEngine
from business.gbrain_memory.agent_loop import BrainAgentLoop
from business.gbrain_memory.sync import SyncManager, SyncStatus, ConflictResolution

__all__ = [
    # 模型
    "BrainPage",
    "MemoryCategory",
    "TimelineEntry",
    "CompiledTruth",
    "EvidenceSource",
    "BrainSignal",
    "SignalType",
    "EntityDetection",
    "AgentResponse",
    "MemoryQuery",
    "MemorySearchResult",
    "CATEGORY_STRUCTURE",
    # 管理器
    "PageManager",
    "SearchEngine",
    "BrainAgentLoop",
    "SyncManager",
    "SyncStatus",
    "ConflictResolution",
]

# 单例
_brain_agent: BrainAgentLoop = None


def get_brain_agent() -> BrainAgentLoop:
    """获取 BrainAgent 单例"""
    global _brain_agent
    if _brain_agent is None:
        _brain_agent = BrainAgentLoop()
    return _brain_agent


def init_brain_async(callback=None):
    """异步初始化大脑"""
    import threading

    def init():
        global _brain_agent
        _brain_agent = BrainAgentLoop()
        if callback:
            callback(_brain_agent)

    thread = threading.Thread(target=init, daemon=True)
    thread.start()
    return _brain_agent
