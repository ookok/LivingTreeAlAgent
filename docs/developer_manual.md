# LivingTree AI Agent - 开发手册

> 本手册面向开发者，介绍代码规范、模块使用和扩展开发指南。

---

## 目录

1. [代码规范](#1-代码规范)
2. [模块导入](#2-模块导入)
3. [核心 API](#3-核心-api)
4. [扩展开发](#4-扩展开发)
5. [测试指南](#5-测试指南)

---

## 1. 代码规范

### 1.1 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 类名 | PascalCase | `HermesAgent`, `KnowledgeGraph` |
| 函数/方法 | snake_case | `get_response`, `update_memory` |
| 常量 | UPPER_SNAKE_CASE | `MAX_TOKEN`, `OLLAMA_BASE_URL` |
| 模块文件 | snake_case | `ollama_client.py`, `session_db.py` |
| 私有成员 | `_prefix` | `_internal_method`, `_cache` |

### 1.2 Import 规范

**新代码（推荐）**：
```python
from client.src.business.hermes_agent import HermesAgent
from client.src.presentation.panels import WorkspacePanel
```

**旧代码（兼容）**：
```python
from core.hermes_agent import HermesAgent  # 仍然可用
```

### 1.3 类型标注

```python
from typing import Optional, List, Dict, Any

def process_query(
    query: str,
    context: Optional[Dict[str, Any]] = None
) -> List[str]:
    """处理查询并返回结果列表"""
    ...
```

### 1.4 文档字符串

```python
def calculate_score(metrics: Dict[str, float]) -> float:
    """
    计算综合评分。

    Args:
        metrics: 指标字典，包含 accuracy、precision、recall

    Returns:
        float: 综合评分 (0-100)

    Example:
        >>> calculate_score({"accuracy": 0.9, "precision": 0.8})
        85.0
    """
    return sum(metrics.values()) / len(metrics) * 100
```

---

## 2. 模块导入

### 2.1 核心模块导入

```python
# Hermes Agent
from core.hermes_agent import HermesAgent, OllamaClient

# 记忆管理
from core.memory_manager import MemoryManager

# 知识图谱
from core.knowledge_graph import KnowledgeGraph

# 技能进化
from core.skill_evolution import SkillEvolutionAgent

# Fusion RAG
from core.fusion_rag import DeepSearchWikiSystem
```

### 2.2 基础设施导入

```python
# 数据库
from client.src.infrastructure.database import SessionDB

# 配置
from client.src.infrastructure.config import Config

# 模型管理
from client.src.infrastructure.model import ModelManager
```

### 2.3 UI 模块导入

```python
# 面板
from client.src.presentation.panels import (
    WorkspacePanel,
    ChatPanel,
    SettingsDialog
)

# 组件
from client.src.presentation.components import Theme
```

---

## 3. 核心 API

### 3.1 HermesAgent

```python
from core.hermes_agent import HermesAgent

# 初始化
agent = HermesAgent(
    model="qwen3.5:9b",
    temperature=0.7,
    max_tokens=4096
)

# 对话
response = await agent.chat("你好，请介绍一下自己")
print(response.content)

# 流式对话
async for chunk in agent.stream_chat("写一首诗"):
    print(chunk, end="", flush=True)
```

### 3.2 OllamaClient

```python
from core.ollama_client import OllamaClient

# 初始化
client = OllamaClient(base_url="http://localhost:11434")

# 同步调用
response = client.chat([
    {"role": "user", "content": "Hello!"}
])

# 同步调用（非流式）
response = client.chat_sync([
    {"role": "user", "content": "Hello!"}
])

# 获取可用模型
models = client.list_models()
```

### 3.3 MemoryManager

```python
from core.memory_manager import MemoryManager

# 初始化
memory = MemoryManager(
    working_limit=4096,    # 工作记忆 token 限制
    short_term_limit=50,   # 短期记忆轮次
)

# 添加记忆
memory.add("user", "用户问了关于天气的问题")
memory.add("assistant", "回答了天气相关信息")

# 获取上下文
context = memory.get_context(max_tokens=2048)

# 持久化
memory.save()
```

### 3.4 KnowledgeGraph

```python
from core.knowledge_graph import KnowledgeGraph

# 初始化
kg = KnowledgeGraph()

# 添加实体
entity_id = kg.add_entity(
    name="张三",
    entity_type="PERSON",
    properties={"age": 30, "city": "北京"}
)

# 添加关系
kg.add_relation(
    from_entity="张三",
    to_entity="北京",
    relation_type="LIVES_IN"
)

# 查询
results = kg.query("张三 住在哪里")
```

### 3.5 SkillEvolutionAgent

```python
from core.skill_evolution import SkillEvolutionAgent

# 初始化
skill_agent = SkillEvolutionAgent()

# 执行任务
result = await skill_agent.execute_task(
    task_description="帮我分析这段代码",
    context={"code": "def foo(): pass"}
)

# 获取技能统计
stats = skill_agent.get_stats()
print(f"技能总数: {stats['total_skills']}")
```

---

## 4. 扩展开发

### 4.1 创建新工具

```python
# core/tools/my_tool.py
from typing import Dict, Any
from core.hermes_agent.tools import BaseTool

class MyTool(BaseTool):
    """我的自定义工具"""

    name = "my_tool"
    description = "执行特定操作的工具"
    category = "utility"

    async def execute(self, params: Dict[str, Any]) -> str:
        """执行工具逻辑"""
        action = params.get("action")

        if action == "calculate":
            return str(params["a"] + params["b"])
        elif action == "query":
            return f"查询结果: {params['keyword']}"
        else:
            return "未知操作"

# 注册工具
from core.hermes_agent import ToolRegistry
registry = ToolRegistry()
registry.register(MyTool())
```

### 4.2 创建新技能

```python
# core/skills/my_skill.py
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class Skill:
    """技能定义"""
    name: str
    description: str
    trigger_patterns: List[str]
    handler: callable
    metadata: Dict[str, Any]

async def my_skill_handler(context: Dict[str, Any]) -> str:
    """技能处理器"""
    user_input = context.get("input", "")
    # 技能逻辑
    return f"处理结果: {user_input}"

# 创建技能
my_skill = Skill(
    name="我的技能",
    description="处理特定任务的技能",
    trigger_patterns=["关键词1", "关键词2"],
    handler=my_skill_handler,
    metadata={"version": "1.0.0", "author": "开发者"}
)
```

### 4.3 创建新面板

```python
# client/src/presentation/panels/my_panel.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal

class MyPanel(QWidget):
    """自定义面板"""

    # 信号定义
    action_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("我的面板")
        layout.addWidget(title)

        # 内容...

    def update_data(self, data: dict):
        """更新面板数据"""
        pass
```

### 4.4 创建新 Agent

```python
# core/agents/my_agent.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseAgent(ABC):
    """Agent 基类"""

    @abstractmethod
    async def process(self, input: str) -> str:
        """处理输入"""
        pass

class MyAgent(BaseAgent):
    """自定义 Agent"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

    async def process(self, input: str) -> str:
        """处理输入"""
        # Agent 逻辑
        return f"处理结果: {input}"
```

---

## 5. 测试指南

### 5.1 运行测试

```bash
# 所有测试
pytest

# 单个测试文件
pytest tests/test_provider.py

# 按标记运行
pytest -m unit        # 单元测试
pytest -m integration # 集成测试
pytest -m slow        # 慢速测试
```

### 5.2 编写测试

```python
# tests/test_my_module.py
import pytest
from client.src.business.my_module import MyClass

class TestMyClass:
    """MyClass 测试"""

    def setup_method(self):
        """每个测试前执行"""
        self.instance = MyClass()

    def test_basic_function(self):
        """基础功能测试"""
        result = self.instance.process("input")
        assert result == "expected_output"

    @pytest.mark.asyncio
    async def test_async_function(self):
        """异步函数测试"""
        result = await self.instance.async_process("input")
        assert "processed" in result
```

### 5.3 Mock 使用

```python
from unittest.mock import Mock, patch

def test_with_mock():
    """使用 Mock 测试"""
    mock_client = Mock()
    mock_client.chat.return_value = "mocked response"

    with patch('my_module.OllamaClient', return_value=mock_client):
        from my_module import MyProcessor
        processor = MyProcessor()
        result = processor.process("test")
        assert result == "mocked response"
```

---

## 附录

### A. 常用配置

```python
# Ollama 配置
OLLAMA_BASE_URL = "http://www.mogoo.com.cn:8899/v1"
OLLAMA_MODEL = "qwen3.5:9b"

# 模型层级配置
MODEL_TIERS = {
    "L0": {"model": "qwen2.5:0.5b", "max_tokens": 512},
    "L1": {"model": "qwen2.5:1.5b", "max_tokens": 1024},
    "L3": {"model": "qwen3.5:4b", "max_tokens": 2048},
    "L4": {"model": "qwen3.5:9b", "max_tokens": 4096},
}
```

### B. 快捷命令

```bash
# 启动客户端
python main.py client

# 启动中继服务
python main.py relay

# 语法检查
python -m py_compile myfile.py

# 代码格式化
python -m black myfile.py
```

---

*最后更新：2026-04-24*
