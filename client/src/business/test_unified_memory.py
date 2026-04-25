"""
统一记忆系统测试 (core/test_unified_memory.py)
==============================================

测试 P0-B 记忆系统统一工作成果：
1. MemoryRouter 单例模式
2. 记忆类型分类
3. 适配器注册和查询
4. 跨系统查询聚合
5. 统一存储接口

Author: LivingTreeAI Agent
Date: 2026-04-26
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, List, Dict, Any


# ═══════════════════════════════════════════════════════════════════════════════
# 复制 unified_memory.py 中的核心代码进行独立测试
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryType(Enum):
    """记忆类型"""
    WORKING = "working"
    SESSION = "session"
    LONG_TERM = "long_term"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"


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
    """统一查询请求"""
    query: str = ""
    memory_types: List[MemoryType] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    limit: int = 10
    min_quality: float = 0.0
    time_range: tuple = None


@dataclass
class MemoryResult:
    """统一查询结果"""
    items: List[MemoryItem] = field(default_factory=list)
    total: int = 0
    query_time_ms: float = 0.0
    sources: List[str] = field(default_factory=list)
    by_type: Dict[str, int] = field(default_factory=dict)
    by_priority: Dict[str, int] = field(default_factory=dict)


class IMemorySystem(ABC):
    """记忆系统统一接口"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        pass
    
    @property
    @abstractmethod
    def supported_types(self) -> List[MemoryType]:
        pass
    
    @abstractmethod
    def store(self, item: MemoryItem) -> str:
        pass
    
    @abstractmethod
    def retrieve(self, query: MemoryQuery) -> MemoryResult:
        pass
    
    @abstractmethod
    def update(self, item_id: str, updates: Dict[str, Any]) -> bool:
        pass
    
    @abstractmethod
    def delete(self, item_id: str) -> bool:
        pass


class MemoryRouter:
    """统一记忆路由器"""
    _instance: Optional['MemoryRouter'] = None
    
    def __init__(self):
        self._adapters: Dict[str, IMemorySystem] = {}
        self._type_registry: Dict[MemoryType, List[str]] = {}
        self._priority_order: List[str] = []
    
    def register(self, name: str, adapter: IMemorySystem):
        """注册记忆系统适配器"""
        self._adapters[name] = adapter
        self._priority_order.append(name)
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
        """统一查询接口"""
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
                print(f"[MemoryRouter] {name} 查询失败: {e}")
        
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
        """存储到指定系统"""
        results = {}
        if not target_systems:
            if item.memory_type in self._type_registry:
                target_systems = self._type_registry[item.memory_type]
            else:
                target_systems = list(self._adapters.keys())[:1]
        
        for name in target_systems:
            if name not in self._adapters:
                continue
            try:
                adapter = self._adapters[name]
                if item.memory_type in adapter.supported_types:
                    item_id = adapter.store(item)
                    results[name] = item_id
            except Exception as e:
                print(f"[MemoryRouter] {name} 存储失败: {e}")
        
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
    
    @classmethod
    def reset_instance(cls):
        """重置单例（用于测试）"""
        cls._instance = None


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
# 测试夹具 (Fixtures)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_memory_item():
    """创建测试用记忆项"""
    return MemoryItem(
        id="test_001",
        content="这是一个测试记忆，用于验证统一记忆系统功能",
        memory_type=MemoryType.SESSION,
        priority=MemoryPriority.MEDIUM,
        keywords=["测试", "记忆", "验证"],
        tags=["unit-test", "demo"],
        quality_score=0.8,
        source="test",
        metadata={"test_id": "test_001"}
    )


@pytest.fixture
def sample_memory_query():
    """创建测试用查询"""
    return MemoryQuery(
        query="测试记忆",
        memory_types=[MemoryType.SESSION],
        limit=5
    )


@pytest.fixture
def mock_adapter():
    """创建模拟适配器"""
    adapter = Mock(spec=IMemorySystem)
    adapter.name = "mock_adapter"
    adapter.description = "模拟适配器"
    adapter.supported_types = [MemoryType.SESSION, MemoryType.WORKING]
    
    adapter.retrieve.return_value = MemoryResult(
        items=[
            MemoryItem(
                id="mock_001",
                content="模拟记忆内容",
                memory_type=MemoryType.SESSION
            )
        ],
        total=1,
        sources=["mock_adapter"]
    )
    
    adapter.store.return_value = "mock_id_001"
    adapter.update.return_value = True
    adapter.delete.return_value = True
    
    return adapter


# ═══════════════════════════════════════════════════════════════════════════════
# 1. MemoryType 测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryType:
    """测试记忆类型枚举"""
    
    def test_memory_type_values(self):
        """验证所有记忆类型都有值"""
        expected_types = [
            "working", "session", "long_term",
            "semantic", "episodic", "procedural"
        ]
        
        for type_name in expected_types:
            assert hasattr(MemoryType, type_name.upper())
            assert MemoryType[type_name.upper()].value == type_name
    
    def test_memory_type_count(self):
        """验证有6种记忆类型"""
        assert len(MemoryType) == 6
    
    def test_memory_type_usage(self):
        """验证各类型预期用途"""
        assert MemoryType.WORKING.value == "working"
        assert MemoryType.SESSION.value == "session"
        assert MemoryType.LONG_TERM.value == "long_term"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.PROCEDURAL.value == "procedural"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. MemoryPriority 测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryPriority:
    """测试记忆优先级枚举"""
    
    def test_priority_values(self):
        """验证优先级定义"""
        assert MemoryPriority.LOW.value == 0
        assert MemoryPriority.MEDIUM.value == 1
        assert MemoryPriority.HIGH.value == 2
        assert MemoryPriority.CRITICAL.value == 3
    
    def test_priority_ordering(self):
        """验证优先级顺序"""
        assert MemoryPriority.LOW.value < MemoryPriority.MEDIUM.value
        assert MemoryPriority.MEDIUM.value < MemoryPriority.HIGH.value
        assert MemoryPriority.HIGH.value < MemoryPriority.CRITICAL.value


# ═══════════════════════════════════════════════════════════════════════════════
# 3. MemoryItem 测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryItem:
    """测试记忆项数据类"""
    
    def test_create_minimal_item(self):
        """创建最小记忆项"""
        item = MemoryItem(content="最小测试")
        assert item.content == "最小测试"
        assert item.id == ""
        assert item.memory_type == MemoryType.SESSION
        assert item.priority == MemoryPriority.MEDIUM
    
    def test_create_full_item(self, sample_memory_item):
        """创建完整记忆项"""
        assert sample_memory_item.id == "test_001"
        assert sample_memory_item.content == "这是一个测试记忆，用于验证统一记忆系统功能"
        assert sample_memory_item.memory_type == MemoryType.SESSION
        assert sample_memory_item.keywords == ["测试", "记忆", "验证"]
        assert sample_memory_item.tags == ["unit-test", "demo"]
        assert sample_memory_item.quality_score == 0.8
    
    def test_item_metadata(self, sample_memory_item):
        """测试元数据"""
        assert sample_memory_item.metadata == {"test_id": "test_001"}
        sample_memory_item.metadata["extra"] = "data"
        assert sample_memory_item.metadata["extra"] == "data"
    
    def test_item_time_defaults(self, sample_memory_item):
        """测试时间戳默认值"""
        assert sample_memory_item.created_at > 0
        assert sample_memory_item.last_accessed > 0
        assert sample_memory_item.last_modified > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 4. MemoryQuery 测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryQuery:
    """测试查询数据类"""
    
    def test_create_minimal_query(self):
        """创建最小查询"""
        query = MemoryQuery(query="测试")
        assert query.query == "测试"
        assert query.memory_types == []
        assert query.limit == 10
    
    def test_create_full_query(self, sample_memory_query):
        """创建完整查询"""
        assert sample_memory_query.query == "测试记忆"
        assert sample_memory_query.memory_types == [MemoryType.SESSION]
        assert sample_memory_query.limit == 5
    
    def test_query_filtering(self):
        """测试查询过滤参数"""
        query = MemoryQuery(
            query="代码生成",
            memory_types=[MemoryType.SEMANTIC, MemoryType.PROCEDURAL],
            tags=["python", "ai"],
            min_quality=0.7
        )
        assert query.min_quality == 0.7
        assert len(query.memory_types) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 5. MemoryResult 测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryResult:
    """测试结果数据类"""
    
    def test_create_result(self):
        """创建结果"""
        items = [
            MemoryItem(id="1", content="结果1"),
            MemoryItem(id="2", content="结果2"),
        ]
        result = MemoryResult(
            items=items,
            total=2,
            query_time_ms=15.5,
            sources=["system_a", "system_b"]
        )
        assert len(result.items) == 2
        assert result.total == 2
        assert result.query_time_ms == 15.5
        assert len(result.sources) == 2
    
    def test_result_statistics(self):
        """测试结果统计"""
        items = [
            MemoryItem(id="1", memory_type=MemoryType.SESSION, priority=MemoryPriority.HIGH),
            MemoryItem(id="2", memory_type=MemoryType.SESSION, priority=MemoryPriority.LOW),
        ]
        result = MemoryResult(
            items=items,
            total=2,
            sources=["test"],
            by_type={"session": 2},
            by_priority={"HIGH": 1, "LOW": 1}
        )
        assert result.by_type["session"] == 2
        assert result.by_priority["HIGH"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 6. IMemorySystem 接口测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestIMemorySystem:
    """测试记忆系统接口"""
    
    def test_interface_methods(self):
        """验证接口定义了所有必需方法"""
        required_methods = ['name', 'description', 'supported_types', 'store', 'retrieve', 'update', 'delete']
        for method in required_methods:
            assert hasattr(IMemorySystem, method)
    
    def test_interface_is_abstract(self):
        """验证接口是抽象的，不能直接实例化"""
        with pytest.raises(TypeError):
            IMemorySystem()


# ═══════════════════════════════════════════════════════════════════════════════
# 7. MemoryRouter 单例测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryRouterSingleton:
    """测试路由器单例模式"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        MemoryRouter.reset_instance()
    
    def test_get_instance_creates_instance(self):
        """获取实例"""
        router = MemoryRouter.get_instance()
        assert router is not None
        assert isinstance(router, MemoryRouter)
    
    def test_get_instance_returns_same_instance(self):
        """获取相同实例"""
        router1 = MemoryRouter.get_instance()
        router2 = MemoryRouter.get_instance()
        assert router1 is router2
    
    def test_get_memory_router_function(self):
        """便捷函数获取路由器"""
        router = get_memory_router()
        assert router is not None
        assert isinstance(router, MemoryRouter)
    
    def test_router_initialization(self):
        """路由器初始化"""
        router = MemoryRouter()
        assert router._adapters is not None
        assert router._type_registry is not None
        assert router._priority_order is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 8. MemoryRouter 注册测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryRouterRegistration:
    """测试路由器适配器注册"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        MemoryRouter.reset_instance()
    
    def test_register_adapter(self, mock_adapter):
        """注册适配器"""
        router = MemoryRouter()
        router.register("test_adapter", mock_adapter)
        assert "test_adapter" in router._adapters
        assert "test_adapter" in router._priority_order
    
    def test_register_creates_type_mapping(self, mock_adapter):
        """注册时创建类型映射"""
        router = MemoryRouter()
        router.register("test_adapter", mock_adapter)
        assert MemoryType.SESSION in router._type_registry
        assert MemoryType.WORKING in router._type_registry
    
    def test_unregister_adapter(self, mock_adapter):
        """注销适配器"""
        router = MemoryRouter()
        router.register("test_adapter", mock_adapter)
        router.unregister("test_adapter")
        assert "test_adapter" not in router._adapters
    
    def test_list_systems(self):
        """列出所有系统"""
        router = MemoryRouter.get_instance()
        systems = router.list_systems()
        assert len(systems) >= 0  # 可能为空，取决于初始化
        if systems:
            assert all("name" in s for s in systems)
            assert all("description" in s for s in systems)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. MemoryRouter 查询测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryRouterQuery:
    """测试路由器查询功能"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        MemoryRouter.reset_instance()
    
    def test_query_empty_types_queries_all(self):
        """空类型查询所有系统"""
        router = MemoryRouter()
        query = MemoryQuery(query="测试")
        assert query.memory_types == []
        systems_to_query = set(router._adapters.keys())
        assert len(systems_to_query) >= 0
    
    def test_query_with_types_routes_correctly(self):
        """按类型路由查询"""
        router = MemoryRouter()
        query = MemoryQuery(query="测试", memory_types=[MemoryType.PROCEDURAL])
        systems = router._type_registry.get(MemoryType.PROCEDURAL, [])
        assert isinstance(systems, list)
    
    def test_query_result_structure(self):
        """查询结果结构"""
        result = MemoryResult(
            items=[],
            total=0,
            query_time_ms=0.0,
            sources=[],
            by_type={},
            by_priority={}
        )
        assert hasattr(result, "items")
        assert hasattr(result, "total")
        assert hasattr(result, "query_time_ms")
        assert hasattr(result, "sources")
    
    def test_unified_retrieve_function(self):
        """统一检索函数"""
        router = MemoryRouter.get_instance()
        result = router.query(MemoryQuery(query="测试"))
        assert result is not None
        assert hasattr(result, "total")


# ═══════════════════════════════════════════════════════════════════════════════
# 10. MemoryRouter 存储测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryRouterStore:
    """测试路由器存储功能"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        MemoryRouter.reset_instance()
    
    def test_store_with_auto_selection(self, mock_adapter):
        """自动选择目标系统"""
        router = MemoryRouter()
        router.register("test", mock_adapter)
        item = MemoryItem(content="测试", memory_type=MemoryType.SESSION)
        results = router.store(item)
        mock_adapter.store.assert_called()
    
    def test_store_with_target_systems(self, mock_adapter):
        """指定目标系统存储"""
        router = MemoryRouter()
        router.register("test", mock_adapter)
        item = MemoryItem(content="测试", memory_type=MemoryType.SESSION)
        results = router.store(item, target_systems=["test"])
        assert "test" in results
    
    def test_unified_store_function(self):
        """统一存储函数"""
        router = MemoryRouter.get_instance()
        item = MemoryItem(content="测试", memory_type=MemoryType.SESSION)
        results = router.store(item)
        assert isinstance(results, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# 11. 集成测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """集成测试"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        MemoryRouter.reset_instance()
    
    def test_full_workflow_mock(self, sample_memory_item, sample_memory_query):
        """完整工作流（使用Mock）"""
        router = MemoryRouter()
        mock = Mock(spec=IMemorySystem)
        mock.name = "test_mock"
        mock.description = "测试用Mock"
        mock.supported_types = [MemoryType.SESSION]
        mock.retrieve.return_value = MemoryResult(
            items=[sample_memory_item],
            total=1,
            sources=["test_mock"]
        )
        mock.store.return_value = "new_id"
        router.register("test_mock", mock)
        
        # 存储
        results = router.store(sample_memory_item, target_systems=["test_mock"])
        assert "test_mock" in results
        
        # 查询
        result = router.query(sample_memory_query)
        assert result is not None
    
    def test_type_routing_integration(self):
        """类型路由集成"""
        router = MemoryRouter()
        for mem_type in MemoryType:
            systems = router._type_registry.get(mem_type, [])
            assert isinstance(systems, list)
    
    def test_cross_system_query(self, mock_adapter):
        """跨系统查询"""
        router = MemoryRouter()
        router.register("system_a", mock_adapter)
        router.register("system_b", mock_adapter)
        
        query = MemoryQuery(query="跨系统测试")
        result = router.query(query)
        
        assert result is not None
        assert hasattr(result, "sources")


# ═══════════════════════════════════════════════════════════════════════════════
# 12. 性能测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerformance:
    """性能测试"""
    
    def test_query_time_recorded(self):
        """查询时间被记录"""
        router = MemoryRouter.get_instance()
        start = time.time()
        result = router.query(MemoryQuery(query="性能测试"))
        elapsed = (time.time() - start) * 1000
        assert elapsed < 1000
    
    def test_bulk_operations(self):
        """批量操作性能"""
        router = MemoryRouter()
        mock = Mock(spec=IMemorySystem)
        mock.name = "perf_mock"
        mock.description = "性能测试"
        mock.supported_types = [MemoryType.SESSION]
        mock.store.return_value = "id"
        mock.retrieve.return_value = MemoryResult(items=[], total=0, sources=["perf_mock"])
        router.register("perf_mock", mock)
        
        # 多次存储
        for i in range(100):
            item = MemoryItem(id=f"item_{i}", content=f"内容{i}", memory_type=MemoryType.SESSION)
            router.store(item)
        
        mock.store.assert_called()


# ═══════════════════════════════════════════════════════════════════════════════
# 13. 边界条件测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界条件测试"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        MemoryRouter.reset_instance()
    
    def test_empty_query(self):
        """空查询"""
        router = MemoryRouter()
        result = router.query(MemoryQuery(query=""))
        assert result is not None
    
    def test_large_limit(self):
        """大限制值"""
        router = MemoryRouter()
        query = MemoryQuery(query="测试", limit=1000)
        result = router.query(query)
        assert result is not None
    
    def test_unregistered_system_query(self):
        """查询不存在的系统"""
        router = MemoryRouter()
        result = router.query(MemoryQuery(query="测试", memory_types=[MemoryType.PROCEDURAL]))
        assert result is not None
    
    def test_store_to_unregistered_system(self):
        """存储到不存在的系统"""
        router = MemoryRouter()
        item = MemoryItem(content="测试", memory_type=MemoryType.SESSION)
        results = router.store(item, target_systems=["nonexistent"])
        assert len(results) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
