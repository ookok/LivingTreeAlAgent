"""
统一记忆集成模块 (core/unified_memory_integration.py)
====================================================

将 unified_memory 集成到 Agent 系统

功能：
1. UnifiedMemoryMixin - 混入类，为 Agent 添加统一记忆能力
2. AgentMemoryBridge - Agent 与统一记忆系统的桥接
3. 自动同步 - Agent 操作时自动同步到统一记忆

Author: LivingTreeAI Agent
Date: 2026-04-26
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field
import time
import threading

# 避免循环导入
if TYPE_CHECKING:
    from core.unified_memory import MemoryRouter, MemoryItem, MemoryQuery, MemoryResult, MemoryType, MemoryPriority

# 全局路由器实例
_router_instance: Optional['MemoryRouter'] = None
_router_lock = threading.Lock()


def get_unified_memory_router() -> Optional['MemoryRouter']:
    """
    获取统一记忆路由器（延迟初始化）
    
    Returns:
        MemoryRouter 实例，如果导入失败返回 None
    """
    global _router_instance
    
    if _router_instance is not None:
        return _router_instance
    
    with _router_lock:
        if _router_instance is not None:
            return _router_instance
        
        try:
            from core.unified_memory import MemoryRouter
            _router_instance = MemoryRouter.get_instance()
            return _router_instance
        except ImportError as e:
            import logging
            logging.warning(f"无法导入 unified_memory: {e}")
            return None
        except Exception as e:
            import logging
            logging.warning(f"初始化 unified_memory 失败: {e}")
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# UnifiedMemoryMixin - Agent 混入类
# ═══════════════════════════════════════════════════════════════════════════════

class UnifiedMemoryMixin:
    """
    统一记忆混入类
    
    为 Agent 添加统一记忆能力，无需修改原有 Agent 结构。
    使用方法：
    
    ```python
    class MyAgent(UnifiedMemoryMixin, BaseAgent):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._init_unified_memory()
    ```
    """
    
    def _init_unified_memory(self):
        """初始化统一记忆系统"""
        self._unified_memory_router = get_unified_memory_router()
        self._unified_memory_enabled = self._unified_memory_router is not None
        
        if self._unified_memory_enabled:
            self._log_unified_memory_event("init", {"status": "enabled"})
        else:
            import logging
            logging.warning("统一记忆系统未启用，将回退到传统记忆")
    
    def unified_memory_store(
        self,
        content: str,
        memory_type: str = "session",
        priority: str = "medium",
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
        source: str = "agent"
    ) -> Dict[str, str]:
        """
        存储到统一记忆系统
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型 (working/session/long_term/semantic/episodic/procedural)
            priority: 优先级 (low/medium/high/critical)
            tags: 标签列表
            metadata: 额外元数据
            
        Returns:
            存储结果 {系统名: 记忆ID}
        """
        if not self._unified_memory_enabled:
            return {}
        
        try:
            from core.unified_memory import MemoryItem, MemoryType, MemoryPriority as UnifiedPriority
            
            # 转换类型
            type_map = {
                "working": MemoryType.WORKING,
                "session": MemoryType.SESSION,
                "long_term": MemoryType.LONG_TERM,
                "semantic": MemoryType.SEMANTIC,
                "episodic": MemoryType.EPISODIC,
                "procedural": MemoryType.PROCEDURAL,
            }
            unified_type = type_map.get(memory_type, MemoryType.SESSION)
            
            priority_map = {
                "low": UnifiedPriority.LOW,
                "medium": UnifiedPriority.MEDIUM,
                "high": UnifiedPriority.HIGH,
                "critical": UnifiedPriority.CRITICAL,
            }
            unified_priority = priority_map.get(priority, UnifiedPriority.MEDIUM)
            
            item = MemoryItem(
                content=content,
                memory_type=unified_type,
                priority=unified_priority,
                tags=tags or [],
                metadata=metadata or {},
                source=source
            )
            
            results = self._unified_memory_router.store(item)
            
            self._log_unified_memory_event("store", {
                "content_length": len(content),
                "type": memory_type,
                "targets": list(results.keys())
            })
            
            return results
            
        except Exception as e:
            import logging
            logging.error(f"统一记忆存储失败: {e}")
            return {}
    
    def unified_memory_retrieve(
        self,
        query: str,
        memory_types: List[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        从统一记忆系统检索
        
        Args:
            query: 查询文本
            memory_types: 要查询的记忆类型列表，空=全部
            limit: 返回数量限制
            
        Returns:
            检索结果
        """
        if not self._unified_memory_enabled:
            return {"items": [], "total": 0, "sources": []}
        
        try:
            from core.unified_memory import MemoryQuery, MemoryType
            
            # 转换类型
            type_map = {
                "working": MemoryType.WORKING,
                "session": MemoryType.SESSION,
                "long_term": MemoryType.LONG_TERM,
                "semantic": MemoryType.SEMANTIC,
                "episodic": MemoryType.EPISODIC,
                "procedural": MemoryType.PROCEDURAL,
            }
            
            unified_types = []
            if memory_types:
                unified_types = [type_map.get(t, MemoryType.SESSION) for t in memory_types]
            
            mem_query = MemoryQuery(
                query=query,
                memory_types=unified_types,
                limit=limit
            )
            
            result = self._unified_memory_router.query(mem_query)
            
            self._log_unified_memory_event("retrieve", {
                "query": query,
                "types": memory_types,
                "result_count": result.total
            })
            
            return {
                "items": [
                    {
                        "id": item.id,
                        "content": item.content,
                        "type": item.memory_type.value,
                        "quality": item.quality_score
                    }
                    for item in result.items
                ],
                "total": result.total,
                "sources": result.sources,
                "by_type": result.by_type
            }
            
        except Exception as e:
            import logging
            logging.error(f"统一记忆检索失败: {e}")
            return {"items": [], "total": 0, "sources": []}
    
    def unified_memory_search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        跨系统搜索
        
        Args:
            query: 查询文本
            limit: 返回数量
            
        Returns:
            搜索结果列表
        """
        result = self.unified_memory_retrieve(query, limit=limit)
        return result.get("items", [])
    
    def _log_unified_memory_event(self, event_type: str, data: Dict[str, Any]):
        """记录统一记忆事件"""
        try:
            import logging
            logger = logging.getLogger("core.agent.unified_memory")
            logger.debug(f"[{event_type}] {data}")
        except Exception:
            pass
    
    @property
    def unified_memory_stats(self) -> Dict[str, Any]:
        """获取统一记忆系统统计"""
        if not self._unified_memory_enabled:
            return {"enabled": False}
        
        systems = self._unified_memory_router.list_systems()
        return {
            "enabled": True,
            "system_count": len(systems),
            "systems": systems
        }


# ═══════════════════════════════════════════════════════════════════════════════
# AgentMemoryBridge - Agent 记忆桥接
# ═══════════════════════════════════════════════════════════════════════════════

class AgentMemoryBridge:
    """
    Agent 记忆桥接器
    
    将 Agent 的传统记忆操作同步到统一记忆系统。
    使用方法：
    
    ```python
    bridge = AgentMemoryBridge(agent)
    bridge.sync_on_init()      # Agent 初始化时
    bridge.sync_on_message()  # 每条消息后
    bridge.sync_on_response() # 每次响应后
    ```
    """
    
    def __init__(self, agent):
        """
        初始化桥接器
        
        Args:
            agent: Agent 实例
        """
        self.agent = agent
        self.router = get_unified_memory_router()
        self.enabled = self.router is not None
    
    def sync_on_init(self):
        """Agent 初始化时同步"""
        if not self.enabled:
            return
        
        self.agent.unified_memory_store(
            content=f"Agent {self.agent.__class__.__name__} 初始化",
            memory_type="session",
            tags=["agent", "init"]
        )
    
    def sync_conversation(self, user_message: str, assistant_response: str):
        """
        同步对话到统一记忆
        
        Args:
            user_message: 用户消息
            assistant_response: 助手响应
        """
        if not self.enabled:
            return
        
        # 存储用户意图
        self.agent.unified_memory_store(
            content=f"用户: {user_message[:200]}",
            memory_type="session",
            tags=["conversation", "user"]
        )
        
        # 存储助手响应
        self.agent.unified_memory_store(
            content=f"助手: {assistant_response[:200]}",
            memory_type="session",
            tags=["conversation", "assistant"]
        )
    
    def sync_task_result(self, task: str, result: str, success: bool):
        """
        同步任务结果到统一记忆
        
        Args:
            task: 任务描述
            result: 任务结果
            success: 是否成功
        """
        if not self.enabled:
            return
        
        self.agent.unified_memory_store(
            content=f"任务: {task[:100]}\n结果: {result[:200]}",
            memory_type="episodic",
            priority="high" if not success else "medium",
            tags=["task", "success" if success else "failed"]
        )
    
    def sync_error(self, error: str, context: str):
        """
        同步错误信息到统一记忆
        
        Args:
            error: 错误信息
            context: 错误上下文
        """
        if not self.enabled:
            return
        
        self.agent.unified_memory_store(
            content=f"错误: {error}\n上下文: {context[:200]}",
            memory_type="procedural",
            priority="high",
            tags=["error", "debug"]
        )
    
    def sync_knowledge(self, concept: str, explanation: str):
        """
        同步知识到统一记忆
        
        Args:
            concept: 概念
            explanation: 解释
        """
        if not self.enabled:
            return
        
        self.agent.unified_memory_store(
            content=f"概念: {concept}\n解释: {explanation}",
            memory_type="semantic",
            tags=["knowledge", "concept"]
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 自动同步装饰器
# ═══════════════════════════════════════════════════════════════════════════════

def auto_sync_memory(event_type: str = "action", memory_type: str = "session"):
    """
    自动同步记忆的装饰器
    
    用法：
    
    ```python
    @auto_sync_memory("task", "episodic")
    def execute_task(self, task):
        ...
    ```
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            
            # 检查是否有 unified_memory
            if hasattr(self, "unified_memory_store"):
                try:
                    self.unified_memory_store(
                        content=f"执行: {func.__name__}",
                        memory_type=memory_type,
                        tags=["auto_sync", event_type]
                    )
                except Exception:
                    pass
            
            return result
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════════════════════

def get_memory_stats() -> Dict[str, Any]:
    """获取记忆系统统计"""
    router = get_unified_memory_router()
    if router is None:
        return {"enabled": False}
    
    return {
        "enabled": True,
        "system_count": len(router._adapters),
        "systems": router.list_systems(),
        "type_registry": {
            t.value: len(systems) 
            for t, systems in router._type_registry.items()
        }
    }


def quick_store(content: str, memory_type: str = "session") -> bool:
    """
    快速存储到统一记忆
    
    用法：
    ```python
    from core.unified_memory_integration import quick_store
    quick_store("用户偏好深色主题", "semantic")
    ```
    """
    router = get_unified_memory_router()
    if router is None:
        return False
    
    try:
        from core.unified_memory import MemoryItem, MemoryType
        
        type_map = {
            "working": MemoryType.WORKING,
            "session": MemoryType.SESSION,
            "long_term": MemoryType.LONG_TERM,
            "semantic": MemoryType.SEMANTIC,
            "episodic": MemoryType.EPISODIC,
            "procedural": MemoryType.PROCEDURAL,
        }
        
        item = MemoryItem(
            content=content,
            memory_type=type_map.get(memory_type, MemoryType.SESSION)
        )
        
        results = router.store(item)
        return len(results) > 0
        
    except Exception:
        return False


def quick_retrieve(query: str, memory_type: str = None) -> List[Dict]:
    """
    快速检索统一记忆
    
    用法：
    ```python
    from core.unified_memory_integration import quick_retrieve
    results = quick_retrieve("用户偏好", "semantic")
    ```
    """
    router = get_unified_memory_router()
    if router is None:
        return []
    
    try:
        from core.unified_memory import MemoryQuery, MemoryType
        
        type_map = {
            "working": MemoryType.WORKING,
            "session": MemoryType.SESSION,
            "long_term": MemoryType.LONG_TERM,
            "semantic": MemoryType.SEMANTIC,
            "episodic": MemoryType.EPISODIC,
            "procedural": MemoryType.PROCEDURAL,
        }
        
        unified_types = []
        if memory_type:
            unified_types = [type_map.get(memory_type, MemoryType.SESSION)]
        
        mem_query = MemoryQuery(
            query=query,
            memory_types=unified_types
        )
        
        result = router.query(mem_query)
        
        return [
            {
                "content": item.content,
                "type": item.memory_type.value,
                "quality": item.quality_score
            }
            for item in result.items
        ]
        
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# 导出
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # 混入类
    "UnifiedMemoryMixin",
    
    # 桥接器
    "AgentMemoryBridge",
    
    # 装饰器
    "auto_sync_memory",
    
    # 函数
    "get_unified_memory_router",
    "get_memory_stats",
    "quick_store",
    "quick_retrieve",
]
