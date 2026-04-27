# 统一记忆系统架构文档

> **状态**: 已完成 ✅  
> **版本**: 1.0.0  
> **日期**: 2026-04-26  
> **作者**: LivingTreeAI Agent

---

## 1. 概述

### 1.1 核心理念

**不合并功能，统一接口** — 8个现有记忆模块保持独立特色，通过统一接口提供一致访问。

```
┌─────────────────────────────────────────────────────────────────────┐
│                        统一记忆系统架构                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                │
│   │智能记忆 │ │增强记忆 │ │ Cognee  │ │ GBrain  │                │
│   │         │ │         │ │   RAG   │ │         │                │
│   │  868行  │ │  750行  │ │  629行  │ │  491行  │                │
│   └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘                │
│        │           │           │           │                       │
│        └───────────┴─────┬─────┴───────────┘                       │
│                          │                                         │
│                    ┌─────▼─────┐                                   │
│                    │   IMemory │  统一接口                          │
│                    │  System   │                                   │
│                    └─────┬─────┘                                   │
│                          │                                         │
│                    ┌─────▼─────┐                                   │
│                    │   Memory  │  智能路由器                        │
│                    │   Router  │  • 类型路由                        │
│                    └─────┬─────┘  • 结果聚合                        │
│                          │         • 单例模式                       │
│                    ┌─────▼─────┐                                   │
│                    │  便捷API  │                                   │
│                    └───────────┘                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 设计原则

1. **接口统一** — 所有记忆模块实现 `IMemorySystem` 接口
2. **功能保留** — 各模块保持原有特色功能
3. **智能路由** — 根据记忆类型自动路由到合适的系统
4. **跨系统查询** — 支持跨多个记忆系统聚合查询

---

## 2. 核心组件

### 2.1 数据类型

```python
from core.unified_memory import MemoryType, MemoryPriority, MemoryItem, MemoryQuery, MemoryResult
```

| 类型 | 值 | 用途 | 示例 |
|------|-----|------|------|
| `WORKING` | working | 工作记忆（短期） | 当前对话上下文 |
| `SESSION` | session | 会话记忆 | 整个会话的信息 |
| `LONG_TERM` | long_term | 长期记忆 | 持久化知识 |
| `SEMANTIC` | semantic | 语义记忆 | 概念、定义 |
| `EPISODIC` | episodic | 情景记忆 | 事件、经历 |
| `PROCEDURAL` | procedural | 程序记忆 | 技能、错误修复 |

| 优先级 | 值 | 用途 |
|--------|-----|------|
| `LOW` | 0 | 低优先级，可清理 |
| `MEDIUM` | 1 | 普通记忆 |
| `HIGH` | 2 | 重要记忆，保留 |
| `CRITICAL` | 3 | 关键记忆，永不删除 |

### 2.2 统一接口

```python
class IMemorySystem(ABC):
    @property
    def name(self) -> str:
        """系统名称"""
        pass
    
    @property
    def description(self) -> str:
        """系统描述"""
        pass
    
    @property
    def supported_types(self) -> List[MemoryType]:
        """支持的记忆类型"""
        pass
    
    def store(self, item: MemoryItem) -> str:
        """存储记忆，返回记忆ID"""
        pass
    
    def retrieve(self, query: MemoryQuery) -> MemoryResult:
        """检索记忆"""
        pass
    
    def update(self, item_id: str, updates: Dict) -> bool:
        """更新记忆"""
        pass
    
    def delete(self, item_id: str) -> bool:
        """删除记忆"""
        pass
```

### 2.3 适配器列表

| 适配器 | 包装模块 | 支持类型 | 优先级 |
|--------|----------|----------|--------|
| `IntelligentMemoryAdapter` | `intelligent_memory.py` | SESSION, SEMANTIC, LONG_TERM | HIGH |
| `EnhancedMemoryAdapter` | `enhanced_memory/` | SESSION, LONG_TERM, EPISODIC | HIGH |
| `CogneeMemoryAdapter` | `cognee_memory/` | SEMANTIC, LONG_TERM, PROCEDURAL | HIGH |
| `GBrainMemoryAdapter` | `gbrain_memory/` | LONG_TERM, EPISODIC, SEMANTIC | MEDIUM |
| `ErrorMemoryAdapter` | `error_memory/` | PROCEDURAL | MEDIUM |
| `MemoryPalaceAdapter` | `memory_palace/` | WORKING, SESSION, LONG_TERM | MEDIUM |

### 2.4 MemoryRouter

```python
from core.unified_memory import MemoryRouter, get_memory_router

# 获取单例
router = get_memory_router()

# 查询
result = router.query(MemoryQuery(
    query="用户偏好",
    memory_types=[MemoryType.SEMANTIC],
    limit=10
))

# 存储
results = router.store(MemoryItem(
    content="用户偏好深色主题",
    memory_type=MemoryType.SEMANTIC,
    tags=["preference", "ui"]
))

# 列出系统
systems = router.list_systems()
```

---

## 3. 集成方式

### 3.1 方式一：Mixin 混入（推荐）

```python
from core.unified_memory_integration import UnifiedMemoryMixin

class MyAgent(UnifiedMemoryMixin, BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_unified_memory()
    
    def do_something(self):
        # 存储记忆
        self.unified_memory_store(
            content="执行了某操作",
            memory_type="session"
        )
        
        # 检索记忆
        results = self.unified_memory_retrieve(
            query="用户偏好",
            memory_types=["semantic"]
        )
```

### 3.2 方式二：桥接器

```python
from core.unified_memory_integration import AgentMemoryBridge

bridge = AgentMemoryBridge(agent)

# 自动同步
bridge.sync_on_init()
bridge.sync_conversation(user_msg, assistant_msg)
bridge.sync_task_result(task, result, success)
bridge.sync_error(error_msg, context)
bridge.sync_knowledge(concept, explanation)
```

### 3.3 方式三：快捷函数

```python
from core.unified_memory_integration import quick_store, quick_retrieve

# 快速存储
quick_store("用户偏好深色主题", "semantic")

# 快速检索
results = quick_retrieve("用户偏好", "semantic")
```

---

## 4. 文件结构

```
core/
├── unified_memory.py              # 核心统一接口
├── unified_memory_integration.py   # Agent 集成模块
├── intelligent_memory.py           # 智能记忆系统 (868行)
├── enhanced_memory/                # 增强记忆系统 (750行)
│   └── core.py
├── cognee_memory/                 # Cognee RAG (629行)
│   └── __init__.py
├── gbrain_memory/                 # GBrain 记忆 (491行)
│   └── models.py
├── error_memory/                  # 错误修复记忆 (669行)
│   └── error_knowledge_base.py
└── memory_palace/                 # 记忆宫殿 (437行)
    └── models.py
```

---

## 5. 测试

### 5.1 测试文件

```
tests/
└── test_unified_memory_standalone.py  # 18个测试用例
```

### 5.2 运行测试

```bash
python -m pytest tests/test_unified_memory_standalone.py -v
```

### 5.3 测试覆盖

| 测试类 | 测试数量 | 内容 |
|--------|----------|------|
| `TestMemoryTypes` | 1 | 记忆类型枚举 |
| `TestMemoryPriority` | 1 | 优先级枚举 |
| `TestMemoryItem` | 2 | 记忆项数据类 |
| `TestMemoryQuery` | 2 | 查询数据类 |
| `TestMemoryResult` | 2 | 结果数据类 |
| `TestIMemorySystem` | 2 | 接口抽象检查 |
| `TestMemoryRouter` | 8 | 路由器功能 |
| `TestIntegration` | 1 | 集成测试 |

---

## 6. 使用示例

### 6.1 存储对话

```python
from core.unified_memory import MemoryItem, MemoryType, get_memory_router

router = get_memory_router()

# 存储用户消息
router.store(MemoryItem(
    content="用户询问如何优化Python代码",
    memory_type=MemoryType.SESSION,
    tags=["user", "question", "python"],
    metadata={"intent": "咨询"}
))

# 存储知识
router.store(MemoryItem(
    content="Python性能优化：使用list comprehension替代循环",
    memory_type=MemoryType.SEMANTIC,
    tags=["knowledge", "python", "optimization"]
))
```

### 6.2 跨系统查询

```python
from core.unified_memory import MemoryQuery, MemoryType, get_memory_router

router = get_memory_router()

# 查询所有相关记忆
result = router.query(MemoryQuery(
    query="Python 优化",
    limit=20
))

print(f"找到 {result.total} 条记忆")
print(f"来源系统: {result.sources}")
print(f"按类型分布: {result.by_type}")
```

### 6.3 类型过滤

```python
# 只查询程序记忆（错误修复）
result = router.query(MemoryQuery(
    query="修复 ImportError",
    memory_types=[MemoryType.PROCEDURAL]
))
```

---

## 7. 与现有系统集成

### 7.1 现有 `MemoryManager` 兼容

现有代码无需修改，统一记忆系统作为增强层：

```python
# 原有代码保持不变
self.memory = MemoryManager()  # 原有记忆

# 新增统一记忆（可选）
self._init_unified_memory()  # 统一记忆
```

### 7.2 自动降级

如果统一记忆系统不可用，自动回退到传统记忆：

```python
if self._unified_memory_enabled:
    # 使用统一记忆
    results = self.unified_memory_retrieve(...)
else:
    # 回退到传统记忆
    results = self.memory.search(...)
```

---

## 8. 后续计划

| 阶段 | 任务 | 状态 |
|------|------|------|
| P0-B-1 | 创建统一接口 | ✅ 已完成 |
| P0-B-2 | 创建测试文件 | ✅ 已完成 |
| P0-B-3 | 集成到 Agent | ⏳ 进行中 |
| P0-B-4 | 文档完善 | ⏳ 进行中 |
| P1 | 性能优化 | 待处理 |
| P1 | 向量索引共享 | 待处理 |

---

## 9. 附录

### 9.1 配置

暂无特殊配置要求。统一记忆系统自动发现并注册所有适配器。

### 9.2 日志

日志前缀: `core.agent.unified_memory`

### 9.3 错误处理

- 导入失败: 静默回退，不影响主流程
- 查询失败: 跳过失败的系统，继续其他系统
- 存储失败: 记录日志，返回空结果

### 9.4 性能指标

| 操作 | 预期耗时 | 说明 |
|------|----------|------|
| 单系统查询 | < 100ms | 取决于具体系统 |
| 跨系统查询 | < 500ms | 并行查询所有系统 |
| 存储 | < 50ms | 同步存储到目标系统 |
