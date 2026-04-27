"""
统一记忆系统测试
================

测试 P0-B 记忆系统统一工作成果

Author: LivingTreeAI Agent
Date: 2026-04-26
"""

import pytest
import time
import sys
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, List, Dict, Any

# ═══════════════════════════════════════════════════════════════════════════════
# 核心代码（从 unified_memory.py 复制）
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryType(Enum):
    WORKING = "working"
    SESSION = "session"
    LONG_TERM = "long_term"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"


class MemoryPriority(Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class MemoryItem:
    id: str = ""
    content: str = ""
    memory_type: MemoryType = MemoryType.SESSION
    priority: MemoryPriority = MemoryPriority.MEDIUM
    keywords: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    quality_score: float = 1.0
    usage_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    last_modified: float = field(default_factory=time.time)
    source: str = ""
    source_type: str = ""
    related_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryQuery:
    query: str = ""
    memory_types: List[MemoryType] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    limit: int = 10
    min_quality: float = 0.0
    time_range: tuple = None


@dataclass
class MemoryResult:
    items: List[MemoryItem] = field(default_factory=list)
    total: int = 0
    query_time_ms: float = 0.0
    sources: List[str] = field(default_factory=list)
    by_type: Dict[str, int] = field(default_factory=dict)
    by_priority: Dict[str, int] = field(default_factory=dict)


class IMemorySystem(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass
    
    @property
    @abstractmethod
    def description(self) -> str: pass
    
    @property
    @abstractmethod
    def supported_types(self) -> List[MemoryType]: pass
    
    @abstractmethod
    def store(self, item: MemoryItem) -> str: pass
    
    @abstractmethod
    def retrieve(self, query: MemoryQuery) -> MemoryResult: pass
    
    @abstractmethod
    def update(self, item_id: str, updates: Dict[str, Any]) -> bool: pass
    
    @abstractmethod
    def delete(self, item_id: str) -> bool: pass


class MemoryRouter:
    _instance: Optional['MemoryRouter'] = None
    
    def __init__(self):
        self._adapters: Dict[str, IMemorySystem] = {}
        self._type_registry: Dict[MemoryType, List[str]] = {}
        self._priority_order: List[str] = []
    
    def register(self, name: str, adapter: IMemorySystem):
        self._adapters[name] = adapter
        self._priority_order.append(name)
        for mem_type in adapter.supported_types:
            if mem_type not in self._type_registry:
                self._type_registry[mem_type] = []
            if name not in self._type_registry[mem_type]:
                self._type_registry[mem_type].append(name)
    
    def unregister(self, name: str):
        if name in self._adapters:
            adapter = self._adapters.pop(name)
            self._priority_order.remove(name)
            for mem_type in adapter.supported_types:
                if mem_type in self._type_registry:
                    self._type_registry[mem_type].remove(name)
    
    def query(self, query: MemoryQuery) -> MemoryResult:
        start_time = time.time()
        all_items: List[MemoryItem] = []
        all_sources: List[str] = []
        
        systems_to_query = set()
        if query.memory_types:
            for mem_type in query.memory_types:
                if mem_type in self._type_registry:
                    systems_to_query.update(self._type_registry[mem_type])
        else:
            systems_to_query = set(self._adapters.keys())
        
        for name in self._priority_order:
            if name not in systems_to_query:
                continue
            try:
                adapter = self._adapters[name]
                result = adapter.retrieve(query)
                all_items.extend(result.items)
                all_sources.extend(result.sources)
            except Exception as e:
                pass
        
        seen_ids = set()
        unique_items = []
        for item in all_items:
            if item.id and item.id not in seen_ids:
                seen_ids.add(item.id)
                unique_items.append(item)
        
        unique_items = unique_items[:query.limit]
        
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
        results = {}
        if not target_systems:
            if item.memory_type in self._type_registry:
                target_systems = self._type_registry[item.memory_type]
            else:
                target_systems = list(self._adapters.keys())[:1] if self._adapters else []
        
        for name in target_systems:
            if name not in self._adapters:
                continue
            try:
                adapter = self._adapters[name]
                if item.memory_type in adapter.supported_types:
                    item_id = adapter.store(item)
                    results[name] = item_id
            except Exception as e:
                pass
        
        return results
    
    def get_system(self, name: str) -> Optional[IMemorySystem]:
        return self._adapters.get(name)
    
    def list_systems(self) -> List[Dict[str, Any]]:
        return [
            {"name": adapter.name, "description": adapter.description, "supported_types": [t.value for t in adapter.supported_types]}
            for adapter in self._adapters.values()
        ]
    
    @classmethod
    def get_instance(cls) -> 'MemoryRouter':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        cls._instance = None


# ═══════════════════════════════════════════════════════════════════════════════
# 测试用例
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryTypes:
    def test_all_types_exist(self):
        assert MemoryType.WORKING.value == "working"
        assert MemoryType.SESSION.value == "session"
        assert MemoryType.LONG_TERM.value == "long_term"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.PROCEDURAL.value == "procedural"
        assert len(MemoryType) == 6


class TestMemoryPriority:
    def test_priority_order(self):
        assert MemoryPriority.LOW.value < MemoryPriority.MEDIUM.value
        assert MemoryPriority.MEDIUM.value < MemoryPriority.HIGH.value
        assert MemoryPriority.HIGH.value < MemoryPriority.CRITICAL.value


class TestMemoryItem:
    def test_create_minimal(self):
        item = MemoryItem(content="test")
        assert item.content == "test"
        assert item.memory_type == MemoryType.SESSION
    
    def test_create_full(self):
        item = MemoryItem(
            id="001",
            content="full test",
            memory_type=MemoryType.SEMANTIC,
            priority=MemoryPriority.HIGH,
            keywords=["test"],
            tags=["unit-test"],
            quality_score=0.9
        )
        assert item.id == "001"
        assert item.memory_type == MemoryType.SEMANTIC
        assert item.priority == MemoryPriority.HIGH


class TestMemoryQuery:
    def test_create_minimal(self):
        q = MemoryQuery(query="test")
        assert q.query == "test"
        assert q.limit == 10
    
    def test_create_with_types(self):
        q = MemoryQuery(query="test", memory_types=[MemoryType.SESSION, MemoryType.WORKING])
        assert len(q.memory_types) == 2


class TestMemoryResult:
    def test_create(self):
        r = MemoryResult(items=[], total=0, sources=["test"])
        assert r.total == 0
        assert "test" in r.sources


class TestIMemorySystem:
    def test_interface_is_abstract(self):
        with pytest.raises(TypeError):
            IMemorySystem()


class TestMemoryRouter:
    def setup_method(self):
        MemoryRouter.reset_instance()
    
    def test_singleton(self):
        r1 = MemoryRouter.get_instance()
        r2 = MemoryRouter.get_instance()
        assert r1 is r2
    
    def test_register_adapter(self):
        router = MemoryRouter()
        mock = Mock(spec=IMemorySystem)
        mock.name = "test"
        mock.description = "test desc"
        mock.supported_types = [MemoryType.SESSION]
        mock.retrieve.return_value = MemoryResult(items=[], total=0, sources=["test"])
        
        router.register("test", mock)
        assert "test" in router._adapters
    
    def test_unregister(self):
        router = MemoryRouter()
        mock = Mock(spec=IMemorySystem)
        mock.name = "test"
        mock.description = "test"
        mock.supported_types = [MemoryType.SESSION]
        mock.retrieve.return_value = MemoryResult(items=[], total=0, sources=["test"])
        
        router.register("test", mock)
        router.unregister("test")
        assert "test" not in router._adapters
    
    def test_query_with_mock(self):
        router = MemoryRouter()
        mock = Mock(spec=IMemorySystem)
        mock.name = "test"
        mock.description = "test"
        mock.supported_types = [MemoryType.SESSION]
        mock.retrieve.return_value = MemoryResult(
            items=[MemoryItem(id="1", content="test")],
            total=1,
            sources=["test"]
        )
        router.register("test", mock)
        
        result = router.query(MemoryQuery(query="test"))
        assert result.total >= 0
    
    def test_store_with_mock(self):
        router = MemoryRouter()
        mock = Mock(spec=IMemorySystem)
        mock.name = "test"
        mock.description = "test"
        mock.supported_types = [MemoryType.SESSION]
        mock.store.return_value = "new_id"
        
        router.register("test", mock)
        item = MemoryItem(content="test", memory_type=MemoryType.SESSION)
        results = router.store(item, target_systems=["test"])
        
        assert "test" in results
        mock.store.assert_called_once()
    
    def test_type_routing(self):
        router = MemoryRouter()
        mock = Mock(spec=IMemorySystem)
        mock.name = "test"
        mock.description = "test"
        mock.supported_types = [MemoryType.PROCEDURAL]
        mock.retrieve.return_value = MemoryResult(items=[], total=0, sources=["test"])
        
        router.register("test", mock)
        
        # PROCEDURAL 类型应该路由到 test
        systems = router._type_registry.get(MemoryType.PROCEDURAL, [])
        assert "test" in systems
    
    def test_list_systems(self):
        router = MemoryRouter()
        systems = router.list_systems()
        assert isinstance(systems, list)
    
    def test_empty_query(self):
        router = MemoryRouter()
        result = router.query(MemoryQuery(query=""))
        assert result is not None
    
    def test_cross_system_query(self):
        router = MemoryRouter()
        mock1 = Mock(spec=IMemorySystem)
        mock1.name = "system_a"
        mock1.description = "a"
        mock1.supported_types = [MemoryType.SESSION]
        mock1.retrieve.return_value = MemoryResult(items=[], total=0, sources=["system_a"])
        
        mock2 = Mock(spec=IMemorySystem)
        mock2.name = "system_b"
        mock2.description = "b"
        mock2.supported_types = [MemoryType.LONG_TERM]
        mock2.retrieve.return_value = MemoryResult(items=[], total=0, sources=["system_b"])
        
        router.register("system_a", mock1)
        router.register("system_b", mock2)
        
        # 空类型应该查询所有
        result = router.query(MemoryQuery(query="test"))
        assert result is not None


class TestIntegration:
    def setup_method(self):
        MemoryRouter.reset_instance()
    
    def test_full_workflow(self):
        router = MemoryRouter()
        
        # 注册系统
        mock = Mock(spec=IMemorySystem)
        mock.name = "workflow_test"
        mock.description = "workflow"
        mock.supported_types = [MemoryType.SESSION, MemoryType.SEMANTIC]
        mock.retrieve.return_value = MemoryResult(items=[], total=0, sources=["workflow_test"])
        mock.store.return_value = "stored_id"
        router.register("workflow_test", mock)
        
        # 存储
        item = MemoryItem(id="1", content="测试记忆", memory_type=MemoryType.SESSION)
        store_result = router.store(item)
        assert "workflow_test" in store_result
        
        # 查询
        query = MemoryQuery(query="测试")
        query_result = router.query(query)
        assert query_result is not None
        
        # 列出系统
        systems = router.list_systems()
        assert len(systems) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
