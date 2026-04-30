"""
统一记忆系统接口 (Unified Memory Interface)
============================================

核心理念：
- 不合并功能，而是统一接口
- 各模块保持特色，接口统一
- 支持跨系统查询

设计原则：
1. IMemorySystem 统一接口
2. MemoryRouter 智能路由
3. 共享向量存储层
4. 跨系统查询能力

Author: LivingTreeAI Agent
Date: 2026-04-25
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
import time


class MemoryType(Enum):
    """记忆类型"""
    WORKING = "working"        # 工作记忆（短期）
    SESSION = "session"        # 会话记忆
    LONG_TERM = "long_term"   # 长期记忆
    SEMANTIC = "semantic"     # 语义记忆（知识图谱）
    EPISODIC = "episodic"     # 情景记忆（事件）
    PROCEDURAL = "procedural"   # 程序记忆（技能/错误修复）


class MemoryPriority(Enum):
    """记忆优先级"""
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class MemoryItem:
    """统一记忆项"""
    id: str = ""
    content: str = ""
    memory_type: MemoryType = MemoryType.SESSION
    priority: MemoryPriority = MemoryPriority.MEDIUM
    
    # 元数据
    keywords: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    # 质量评估
    quality_score: float = 1.0
    usage_count: int = 0
    
    # 时间戳
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    last_modified: float = field(default_factory=time.time)
    
    # 来源追踪
    source: str = ""
    source_type: str = ""
    
    # 关联
    related_ids: List[str] = field(default_factory=list)
    
    # 扩展
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryQuery:
    """统一查询请求"""
    query: str = ""
    memory_types: List[MemoryType] = field(default_factory=list)  # 空=全部
    tags: List[str] = field(default_factory=list)  # 空=全部
    keywords: List[str] = field(default_factory=list)  # 空=全部
    
    # 数量限制
    limit: int = 10
    
    # 质量过滤
    min_quality: float = 0.0
    
    # 时间范围
    time_range: tuple = None  # (start, end)


@dataclass
class MemoryResult:
    """统一查询结果"""
    items: List[MemoryItem] = field(default_factory=list)
    total: int = 0
    query_time_ms: float = 0.0
    sources: List[str] = field(default_factory=list)  # 结果来源模块
    
    # 统计
    by_type: Dict[str, int] = field(default_factory=dict)
    by_priority: Dict[str, int] = field(default_factory=dict)


class IMemorySystem(ABC):
    """
    记忆系统统一接口
    
    所有记忆模块都应实现此接口
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """系统名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """系统描述"""
        pass
    
    @property
    @abstractmethod
    def supported_types(self) -> List[MemoryType]:
        """支持的记忆类型"""
        pass
    
    @abstractmethod
    def store(self, item: MemoryItem) -> str:
        """
        存储记忆
        
        Args:
            item: 记忆项
            
        Returns:
            记忆ID
        """
        pass
    
    @abstractmethod
    def retrieve(self, query: MemoryQuery) -> MemoryResult:
        """
        检索记忆
        
        Args:
            query: 查询条件
            
        Returns:
            查询结果
        """
        pass
    
    @abstractmethod
    def update(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新记忆
        
        Args:
            item_id: 记忆ID
            updates: 更新内容
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def delete(self, item_id: str) -> bool:
        """
        删除记忆
        
        Args:
            item_id: 记忆ID
            
        Returns:
            是否成功
        """
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "name": self.name,
            "supported_types": [t.value for t in self.supported_types],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 适配器：包装现有记忆模块
# ═══════════════════════════════════════════════════════════════════════════════

class IntelligentMemoryAdapter(IMemorySystem):
    """
    intelligent_memory.py 适配器
    
    包装现有智能记忆系统
    """
    
    def __init__(self):
        from business.intelligent_memory import get_memory_system
        self._system = get_memory_system()
        self._type_map = {
            MemoryType.SESSION: "qa",
            MemoryType.SEMANTIC: "fact",
            MemoryType.LONG_TERM: "entity",
        }
    
    @property
    def name(self) -> str:
        return "intelligent_memory"
    
    @property
    def description(self) -> str:
        return "智能记忆系统 - 语义缓存、事实锚点、上下文示例"
    
    @property
    def supported_types(self) -> List[MemoryType]:
        return [MemoryType.SESSION, MemoryType.SEMANTIC, MemoryType.LONG_TERM]
    
    def store(self, item: MemoryItem) -> str:
        """存储到智能记忆系统"""
        # 记录问答交互
        if item.metadata.get("question"):
            qa_id = self._system.record_interaction(
                question=item.metadata["question"],
                answer=item.content,
                metadata={"tags": item.tags}
            )
            return qa_id or item.id
        
        # 存储实体
        if item.entities:
            from business.intelligent_memory import Entity
            for entity_name in item.entities[:5]:
                entity = Entity(
                    name=entity_name,
                    entity_type=item.metadata.get("entity_type", ""),
                    description=item.content[:200]
                )
                self._system.db.save_entity(entity)
        
        # 存储事实
        if item.memory_type == MemoryType.SEMANTIC:
            self._system.db.save_qa_pair(
                self._system.db.save_qa_pair  # 复用
            )
        
        return item.id
    
    def retrieve(self, query: MemoryQuery) -> MemoryResult:
        """从智能记忆系统检索"""
        # 获取上下文
        context = self._system.retrieve_context(query.query)
        
        items = []
        for ex in context.get("fewshot_examples", []):
            items.append(MemoryItem(
                id=f"qa_{hash(ex['question'])}",
                content=f"Q: {ex['question']}\nA: {ex['answer']}",
                memory_type=MemoryType.SESSION,
                quality_score=ex.get("quality", 0.5)
            ))
        
        return MemoryResult(
            items=items,
            total=len(items),
            sources=[self.name]
        )
    
    def update(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆"""
        if "quality_delta" in updates:
            self._system.update_quality_feedback(item_id, updates["quality_delta"])
            return True
        return False
    
    def delete(self, item_id: str) -> bool:
        """删除记忆（标记删除）"""
        # 智能记忆系统不直接支持删除，降低优先级
        self.update(item_id, {"quality_delta": -0.5})
        return True


class EnhancedMemoryAdapter(IMemorySystem):
    """
    enhanced_memory/ 适配器
    
    包装增强记忆系统
    """
    
    def __init__(self):
        from business.enhanced_memory import get_enhanced_memory_system
        self._system = get_enhanced_memory_system()
    
    @property
    def name(self) -> str:
        return "enhanced_memory"
    
    @property
    def description(self) -> str:
        return "增强记忆系统 - 语义搜索、记忆压缩、渐进检索"
    
    @property
    def supported_types(self) -> List[MemoryType]:
        return [MemoryType.SESSION, MemoryType.LONG_TERM, MemoryType.EPISODIC]
    
    def store(self, item: MemoryItem) -> str:
        """存储到增强记忆系统"""
        return self._system.add_memory(
            content=item.content,
            tags=item.tags
        )
    
    def retrieve(self, query: MemoryQuery) -> MemoryResult:
        """从增强记忆系统检索"""
        items = self._system.search_memory(
            query=query.query,
            limit=query.limit,
            use_semantic=True
        )
        
        return MemoryResult(
            items=[
                MemoryItem(
                    id=i.id,
                    content=i.content,
                    memory_type=MemoryType.SESSION,
                    quality_score=i.value_level / 3.0,
                    created_at=i.created_at
                )
                for i in items
            ],
            total=len(items),
            sources=[self.name]
        )
    
    def update(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆"""
        # 增强记忆系统需要完整重建
        return False
    
    def delete(self, item_id: str) -> bool:
        """删除记忆"""
        return False


class CogneeMemoryAdapter(IMemorySystem):
    """
    cognee_memory/ 适配器
    
    包装Cognee RAG记忆系统
    """
    
    def __init__(self):
        from business.cognee_memory import get_cognee_memory
        import asyncio
        self._system = get_cognee_memory()
        self._loop = asyncio.new_event_loop()
    
    @property
    def name(self) -> str:
        return "cognee_memory"
    
    @property
    def description(self) -> str:
        return "Cognee RAG - 完整知识图谱、多模态摄入"
    
    @property
    def supported_types(self) -> List[MemoryType]:
        return [MemoryType.SEMANTIC, MemoryType.LONG_TERM, MemoryType.PROCEDURAL]
    
    def store(self, item: MemoryItem) -> str:
        """存储到Cognee记忆系统"""
        from business.cognee_memory import MemoryType as CogneeType
        
        cognee_type = {
            MemoryType.SEMANTIC: CogneeType.PERMANENT,
            MemoryType.SESSION: CogneeType.SESSION,
            MemoryType.WORKING: CogneeType.WORKING,
        }.get(item.memory_type, CogneeType.PERMANENT)
        
        return self._system.remember(
            content=item.content,
            memory_type=cognee_type,
            metadata=item.metadata
        )
    
    def retrieve(self, query: MemoryQuery) -> MemoryResult:
        """从Cognee记忆系统检索"""
        results = self._system.recall(
            query=query.query,
            limit=query.limit
        )
        
        return MemoryResult(
            items=[
                MemoryItem(
                    id=r.get("id", ""),
                    content=r.get("content", ""),
                    memory_type=MemoryType.SEMANTIC,
                    quality_score=r.get("quality", 0.5)
                )
                for r in results
            ],
            total=len(results),
            sources=[self.name]
        )
    
    def update(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆"""
        return False
    
    def delete(self, item_id: str) -> bool:
        """删除记忆"""
        self._system.forget(memory_id=item_id)
        return True


class GBrainMemoryAdapter(IMemorySystem):
    """
    gbrain_memory/ 适配器
    
    包装GBrain记忆系统（Timeline机制）
    """
    
    def __init__(self):
        from business.gbrain_memory import get_brain_agent, PageManager
        self._agent = get_brain_agent()
        self._manager = PageManager()
    
    @property
    def name(self) -> str:
        return "gbrain_memory"
    
    @property
    def description(self) -> str:
        return "GBrain - Timeline证据链、MECE分类"
    
    @property
    def supported_types(self) -> List[MemoryType]:
        return [MemoryType.LONG_TERM, MemoryType.EPISODIC, MemoryType.SEMANTIC]
    
    def store(self, item: MemoryItem) -> str:
        """存储到GBrain系统"""
        from business.gbrain_memory.models import MemoryCategory, EvidenceSource
        
        # 转换分类
        category_map = {
            MemoryType.SEMANTIC: MemoryCategory.CONCEPTS,
            MemoryType.EPISODIC: MemoryCategory.CONVERSATIONS,
            MemoryType.LONG_TERM: MemoryCategory.PROJECTS,
        }
        category = category_map.get(item.memory_type, MemoryCategory.UNCLASSIFIED)
        
        # 创建页面
        page = self._manager.create_page(
            title=item.keywords[0] if item.keywords else "记忆项",
            category=category,
            content=item.content,
            source=item.source or "unified_memory",
            tags=item.tags
        )
        
        return page.id
    
    def retrieve(self, query: MemoryQuery) -> MemoryResult:
        """从GBrain系统检索"""
        from business.gbrain_memory.models import MemoryQuery as GBrainQuery
        
        gb_query = MemoryQuery(
            keywords=query.keywords or [query.query],
            limit=query.limit
        )
        
        pages = self._manager.search_pages(
            keywords=gb_query.keywords,
            limit=gb_query.limit
        )
        
        return MemoryResult(
            items=[
                MemoryItem(
                    id=p.id,
                    content=p.compiled_truth.summary or "\n".join([e.content for e in p.timeline[-3:]]),
                    memory_type=MemoryType.LONG_TERM,
                    tags=p.tags,
                    created_at=p.created_at
                )
                for p in pages
            ],
            total=len(pages),
            sources=[self.name]
        )
    
    def update(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆"""
        # GBrain的Timeline是Append-only，只能添加新条目
        if "content" in updates:
            self._manager.append_timeline(
                page_id=item_id,
                content=updates["content"],
                source="unified_memory"
            )
            return True
        return False
    
    def delete(self, item_id: str) -> bool:
        """删除记忆"""
        self._manager.delete_page(item_id)
        return True


class ErrorMemoryAdapter(IMemorySystem):
    """
    error_memory/ 适配器
    
    包装错误修复记忆系统
    """
    
    def __init__(self):
        from business.error_memory import get_error_system
        self._system = get_error_system()
    
    @property
    def name(self) -> str:
        return "error_memory"
    
    @property
    def description(self) -> str:
        return "错误修复记忆 - 模式学习、方案模板"
    
    @property
    def supported_types(self) -> List[MemoryType]:
        return [MemoryType.PROCEDURAL]
    
    def store(self, item: MemoryItem) -> str:
        """存储到错误记忆系统"""
        # 通过快速修复接口
        from business.error_memory import quick_learn
        
        if item.metadata.get("error"):
            quick_learn(item.metadata["error"], item.metadata)
        
        return item.id
    
    def retrieve(self, query: MemoryQuery) -> MemoryResult:
        """从错误记忆系统检索"""
        from business.error_memory import quick_fix_from_message
        
        # 查询错误解决方案
        solution = quick_fix_from_message(query.query, {})
        
        items = []
        if solution.get("success"):
            items.append(MemoryItem(
                id=solution.get("matched_pattern", {}).get("pattern_id", ""),
                content=str(solution),
                memory_type=MemoryType.PROCEDURAL,
                quality_score=solution.get("matched_pattern", {}).get("confidence", 0.5)
            ))
        
        return MemoryResult(
            items=items,
            total=len(items),
            sources=[self.name]
        )
    
    def update(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆"""
        return False
    
    def delete(self, item_id: str) -> bool:
        """删除记忆"""
        return False


class MemoryPalaceAdapter(IMemorySystem):
    """
    memory_palace/ 适配器
    
    包装记忆宫殿系统（Loci记忆术）
    """
    
    def __init__(self):
        from business.memory_palace import get_memory_palace, MemoryLevel
        self._system = get_memory_palace()
        self._level_map = {
            MemoryType.WORKING: MemoryLevel.DRAWER,
            MemoryType.SESSION: MemoryLevel.ROOM,
            MemoryType.LONG_TERM: MemoryLevel.HALL,
        }
    
    @property
    def name(self) -> str:
        return "memory_palace"
    
    @property
    def description(self) -> str:
        return "记忆宫殿 - Loci记忆术、空间化分层"
    
    @property
    def supported_types(self) -> List[MemoryType]:
        return [MemoryType.WORKING, MemoryType.SESSION, MemoryType.LONG_TERM]
    
    def store(self, item: MemoryItem) -> str:
        """存储到记忆宫殿"""
        from business.memory_palace import MemoryLevel
        
        level = self._level_map.get(item.memory_type, MemoryLevel.ROOM)
        
        entry = self._system.store_entry(
            level=level,
            parent_id=item.metadata.get("parent_id", ""),
            title=item.keywords[0] if item.keywords else "记忆",
            content=item.content,
            metadata=item.metadata
        )
        
        return entry.id
    
    def retrieve(self, query: MemoryQuery) -> MemoryResult:
        """从记忆宫殿检索"""
        entries = self._system.search(
            query=query.query,
            limit=query.limit
        )
        
        return MemoryResult(
            items=[
                MemoryItem(
                    id=e.id,
                    content=e.content,
                    memory_type=MemoryType.LONG_TERM,
                    created_at=e.created_at.timestamp() if hasattr(e.created_at, 'timestamp') else e.created_at
                )
                for e in entries
            ],
            total=len(entries),
            sources=[self.name]
        )
    
    def update(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆"""
        return False
    
    def delete(self, item_id: str) -> bool:
        """删除记忆"""
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 统一记忆路由器
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryRouter:
    """
    统一记忆路由器
    
    功能：
    1. 管理多个记忆系统适配器
    2. 智能路由查询到合适的系统
    3. 聚合多系统查询结果
    4. 提供统一查询接口
    """
    
    _instance: Optional['MemoryRouter'] = None
    
    def __init__(self):
        self._adapters: Dict[str, IMemorySystem] = {}
        self._type_registry: Dict[MemoryType, List[str]] = {}  # 类型 -> 适配器
        self._priority_order: List[str] = []  # 适配器优先级
        
        # 注册默认适配器
        self._register_default_adapters()
    
    def _register_default_adapters(self):
        """注册默认适配器"""
        adapters = [
            ("intelligent", IntelligentMemoryAdapter()),
            ("enhanced", EnhancedMemoryAdapter()),
            ("cognee", CogneeMemoryAdapter()),
            ("gbrain", GBrainMemoryAdapter()),
            ("error", ErrorMemoryAdapter()),
            ("palace", MemoryPalaceAdapter()),
        ]
        
        for name, adapter in adapters:
            self.register(name, adapter)
    
    def register(self, name: str, adapter: IMemorySystem):
        """注册记忆系统适配器"""
        self._adapters[name] = adapter
        self._priority_order.append(name)
        
        # 注册类型映射
        for mem_type in adapter.supported_types:
            if mem_type not in self._type_registry:
                self._type_registry[mem_type] = []
            if name not in self._type_registry[mem_type]:
                self._type_registry[mem_type].append(name)
    
    def unregister(self, name: str):
        """注销记忆系统"""
        if name in self._adapters:
            adapter = self._adapters.pop(name)
            self._priority_order.remove(name)
            
            for mem_type in adapter.supported_types:
                if mem_type in self._type_registry:
                    self._type_registry[mem_type].remove(name)
    
    def query(self, query: MemoryQuery) -> MemoryResult:
        """
        统一查询接口
        
        自动路由到合适的记忆系统并聚合结果
        """
        import time
        start_time = time.time()
        
        all_items: List[MemoryItem] = []
        all_sources: List[str] = []
        
        # 确定要查询的系统
        systems_to_query = set()
        
        if query.memory_types:
            # 指定了类型，只查询支持该类型的系统
            for mem_type in query.memory_types:
                if mem_type in self._type_registry:
                    systems_to_query.update(self._type_registry[mem_type])
        else:
            # 未指定类型，查询所有系统
            systems_to_query = set(self._adapters.keys())
        
        # 按优先级查询
        for name in self._priority_order:
            if name not in systems_to_query:
                continue
            
            try:
                adapter = self._adapters[name]
                result = adapter.retrieve(query)
                
                all_items.extend(result.items)
                all_sources.extend(result.sources)
                
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"[MemoryRouter] {name} 查询失败: {e}")
        
        # 去重（按ID）
        seen_ids = set()
        unique_items = []
        for item in all_items:
            if item.id and item.id not in seen_ids:
                seen_ids.add(item.id)
                unique_items.append(item)
        
        # 限制数量
        unique_items = unique_items[:query.limit]
        
        # 统计
        by_type: Dict[str, int] = {}
        by_priority: Dict[str, int] = {}
        for item in unique_items:
            type_key = item.memory_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1
            priority_key = item.priority.name
            by_priority[priority_key] = by_priority.get(priority_key, 0) + 1
        
        return MemoryResult(
            items=unique_items,
            total=len(unique_items),
            query_time_ms=(time.time() - start_time) * 1000,
            sources=list(set(all_sources)),
            by_type=by_type,
            by_priority=by_priority
        )
    
    def store(self, item: MemoryItem, target_systems: List[str] = None) -> Dict[str, str]:
        """
        存储到指定系统
        
        Args:
            item: 记忆项
            target_systems: 目标系统列表，空=根据类型自动选择
            
        Returns:
            {系统名: 记忆ID}
        """
        results = {}
        
        # 确定目标系统
        if not target_systems:
            if item.memory_type in self._type_registry:
                target_systems = self._type_registry[item.memory_type]
            else:
                target_systems = list(self._adapters.keys())[:1]  # 默认第一个
        
        for name in target_systems:
            if name not in self._adapters:
                continue
            
            try:
                adapter = self._adapters[name]
                if item.memory_type in adapter.supported_types:
                    item_id = adapter.store(item)
                    results[name] = item_id
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"[MemoryRouter] {name} 存储失败: {e}")
        
        return results
    
    def get_system(self, name: str) -> Optional[IMemorySystem]:
        """获取指定系统"""
        return self._adapters.get(name)
    
    def list_systems(self) -> List[Dict[str, Any]]:
        """列出所有已注册系统"""
        return [
            {
                "name": adapter.name,
                "description": adapter.description,
                "supported_types": [t.value for t in adapter.supported_types],
            }
            for adapter in self._adapters.values()
        ]
    
    @classmethod
    def get_instance(cls) -> 'MemoryRouter':
        """获取单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# ═══════════════════════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════════════════════

def get_memory_router() -> MemoryRouter:
    """获取统一记忆路由器"""
    return MemoryRouter.get_instance()


def unified_store(item: MemoryItem) -> Dict[str, str]:
    """统一存储接口"""
    return get_memory_router().store(item)


def unified_retrieve(query: MemoryQuery) -> MemoryResult:
    """统一检索接口"""
    return get_memory_router().query(query)


# ═══════════════════════════════════════════════════════════════════════════════
# 导出
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # 类型定义
    "MemoryType",
    "MemoryPriority",
    "MemoryItem",
    "MemoryQuery",
    "MemoryResult",
    
    # 接口
    "IMemorySystem",
    
    # 适配器
    "IntelligentMemoryAdapter",
    "EnhancedMemoryAdapter",
    "CogneeMemoryAdapter",
    "GBrainMemoryAdapter",
    "ErrorMemoryAdapter",
    "MemoryPalaceAdapter",
    
    # 路由器
    "MemoryRouter",
    "get_memory_router",
    
    # 便捷函数
    "unified_store",
    "unified_retrieve",
]
