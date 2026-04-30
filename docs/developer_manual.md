# 📖 LivingTreeAI 开发手册

> **版本**: v1.0.0  
> **状态**: 全面测试阶段  
> **最后更新**: 2026-04-30

---

## 📋 目录

1. [开发环境搭建](#1-开发环境搭建)
2. [项目结构详解](#2-项目结构详解)
3. [核心模块开发指南](#3-核心模块开发指南)
4. [智能体开发](#4-智能体开发)
5. [技能开发](#5-技能开发)
6. [UI 组件开发](#6-ui-组件开发)
7. [测试与调试](#7-测试与调试)
8. [代码规范](#8-代码规范)
9. [发布流程](#9-发布流程)

---

## 1. 开发环境搭建

### 1.1 系统要求

| 依赖 | 版本 | 说明 |
|-----|------|------|
| Python | 3.11+ | 开发语言 |
| PyQt6 | 6.6+ | UI 框架 |
| Ollama | 0.1.40+ | 本地 LLM 运行时 |
| PostgreSQL | 15+ | 数据库 (生产环境) |
| Redis | 7+ | 缓存 |

### 1.2 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/ookok/LivingTreeAlAgent.git
cd LivingTreeAlAgent

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. 安装依赖（顺序重要）
pip install -e ./client
pip install -e ./server/relay_server
pip install -e ./app

# 4. 安装开发依赖
pip install pytest pytest-cov pytest-asyncio pytest-qt
pip install pylint flake8 mypy

# 5. 安装 Ollama（可选，用于本地模型）
# 访问 https://ollama.com/download 下载安装
```

### 1.3 环境变量

| 变量 | 说明 | 默认值 |
|-----|------|-------|
| `LIVINGTREE_ENV` | 运行环境 | production |
| `OLLAMA_URL` | Ollama 服务地址 | http://localhost:11434 |
| `DB_TYPE` | 数据库类型 | sqlite |
| `DB_PATH` | SQLite 数据库路径 | ./data/livingtree.db |
| `REDIS_URL` | Redis 地址 | redis://localhost:6379/0 |
| `SECRET_KEY` | 加密密钥 | 随机生成 |

### 1.4 一键启动

**开发模式**:
```bash
# Windows
run.bat

# Linux/Mac
./run.sh
```

**手动启动**:
```bash
# 启动客户端
python main.py client

# 启动中继服务器
python main.py relay

# 启动 P2P 追踪器
python main.py tracker
```

---

## 2. 项目结构详解

### 2.1 整体结构

```
LivingTreeAlAgent/
├── client/                    # 客户端应用
│   └── src/
│       ├── business/          # 业务逻辑层 (~340+ 文件)
│       ├── presentation/      # 表示层 (~200+ 文件)
│       ├── infrastructure/    # 基础设施层
│       └── shared/            # 共享工具
├── server/                    # 服务端
│   ├── relay_server/          # FastAPI 中继服务器
│   └── tracker_server.py      # P2P 节点追踪器
├── app/                       # 企业应用
├── deploy/                    # 部署配置
├── tests/                     # 测试用例
└── scripts/                   # 辅助脚本
```

### 2.2 业务层结构

| 模块 | 职责 | 说明 |
|-----|------|------|
| `hermes_agent/` | 智能体框架 | 智能体生命周期管理 |
| `fusion_rag/` | 多源检索 | RAG 检索增强生成 |
| `knowledge_graph/` | 知识图谱 | 实体关系管理 |
| `amphiloop/` | 调度引擎 | 任务调度 |
| `optimization/` | PRISM | 上下文优化 |
| `enterprise/` | P2P 存储 | 分布式存储 |
| `digital_twin/` | 数字孪生 | 虚拟形象 |
| `credit_economy/` | 信用经济 | 积分系统 |
| `decommerce/` | 电子商务 | 交易市场 |

### 2.3 表示层结构

| 模块 | 职责 | 说明 |
|-----|------|------|
| `panels/` | 主面板 | 聊天、IDE、技能等面板 |
| `components/` | 可复用组件 | 卡片、按钮、输入框 |
| `widgets/` | 自定义部件 | 自定义 Qt 控件 |
| `dialogs/` | 对话框 | 模态对话框 |
| `modules/` | 功能模块 | 设置、连接器等 |

---

## 3. 核心模块开发指南

### 3.1 配置系统

**NanochatConfig（推荐）**:
```python
from client.src.business.nanochat_config import config

# 直接属性访问
url = config.ollama.url
timeout = config.timeouts.default
max_retries = config.retries.default
```

**UnifiedConfig（兼容模式）**:
```python
from client.src.business.config import UnifiedConfig

config = UnifiedConfig.get_instance()
url = config.get("endpoints.ollama.url")
```

**添加新配置项**:
```python
# 在 client/src/business/nanochat_config.py 中添加
@dataclass
class OllamaConfig:
    url: str = "http://localhost:11434"
    default_model: str = "llama3"
    timeout: int = 60
```

### 3.2 事件总线

**发布事件**:
```python
from client.src.business.shared.event_bus import event_bus

event_bus.publish({
    "type": "task_completed",
    "payload": {
        "task_id": "abc123",
        "status": "completed",
        "result": "success"
    }
})
```

**订阅事件**:
```python
def handle_task_completed(event):
    print(f"Task {event['payload']['task_id']} completed")

event_bus.subscribe("task_completed", handle_task_completed)
```

### 3.3 日志系统

**使用 logger**:
```python
from client.src.business.logger import logger

logger.info("应用启动")
logger.warning("内存使用率过高")
logger.error("连接失败", exc_info=True)
logger.debug("调试信息")
```

**日志配置**:
配置文件位于 `config/logging.yaml`，支持多级别输出、文件轮转等。

---

## 4. 智能体开发

### 4.1 创建智能体

**基础智能体**:
```python
from client.src.business.hermes_agent.base_agent import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_id="my_agent", config={})
        self.name = "My Agent"
    
    async def execute(self, task):
        # 执行任务逻辑
        result = await self._process_task(task)
        return result
    
    async def _process_task(self, task):
        # 任务处理逻辑
        return {"status": "completed", "data": "result"}
```

**注册智能体**:
```python
from client.src.business.agent_registry import AgentRegistry

registry = AgentRegistry()
registry.register(MyAgent)
```

### 4.2 智能体生命周期

```python
class BaseAgent:
    async def on_start(self):
        """启动时调用"""
        pass
    
    async def on_stop(self):
        """停止时调用"""
        pass
    
    async def on_pause(self):
        """暂停时调用"""
        pass
    
    async def on_resume(self):
        """恢复时调用"""
        pass
```

### 4.3 智能体通信

**发送消息**:
```python
from client.src.business.agent_hub import AgentHub

hub = AgentHub()
await hub.send_message(
    from_agent_id="agent1",
    to_agent_id="agent2",
    message={"type": "request", "data": "hello"}
)
```

**接收消息**:
```python
async def handle_message(self, message):
    if message["type"] == "request":
        response = await self.process_request(message)
        await self.send_response(message["from_agent_id"], response)
```

---

## 5. 技能开发

### 5.1 创建技能

```python
from client.src.business.tools.base_tool import BaseTool

class MySkill(BaseTool):
    name = "my_skill"
    description = "我的自定义技能"
    parameters = [
        {"name": "input", "type": "string", "required": True, "description": "输入数据"}
    ]
    
    async def execute(self, **kwargs):
        input_data = kwargs.get("input")
        # 执行技能逻辑
        return {"result": f"处理完成: {input_data}"}
```

### 5.2 注册技能

```python
from client.src.business.skill_manager import SkillManager

skill_manager = SkillManager()
skill_manager.register(MySkill)
```

### 5.3 技能元数据

```python
class MySkill(BaseTool):
    # 技能分类
    category = "工具"
    
    # 技能标签
    tags = ["工具", "处理"]
    
    # 技能版本
    version = "1.0.0"
    
    # 技能作者
    author = "LivingTreeAI Team"
    
    # 技能图标
    icon = "🔧"
```

### 5.4 技能发现与匹配

```python
# 发现相关技能
skills = skill_manager.discover("文档处理")

# 匹配最优技能
skill = skill_manager.match(intent="总结文档")

# 执行技能
result = await skill.execute(input="需要总结的文档内容")
```

---

## 6. UI 组件开发

### 6.1 创建面板

```python
from client.src.presentation.panels.base_panel import BasePanel
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class MyPanel(BasePanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        label = QLabel("我的面板")
        layout.addWidget(label)
        self.setLayout(layout)
    
    def on_show(self):
        """面板显示时调用"""
        pass
    
    def on_hide(self):
        """面板隐藏时调用"""
        pass
```

### 6.2 创建组件

```python
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton

class ActionButton(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout()
        self.button = QPushButton(self.text)
        self.button.clicked.connect(self.on_click)
        layout.addWidget(self.button)
        self.setLayout(layout)
    
    def on_click(self):
        """按钮点击事件"""
        self.clicked.emit()
```

### 6.3 使用资源

```python
# 加载图标
from PyQt6.QtGui import QIcon

icon = QIcon("resources/icons/my_icon.png")

# 加载样式
with open("resources/styles/style.qss", "r") as f:
    style = f.read()
self.setStyleSheet(style)
```

---

## 7. 测试与调试

### 7.1 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest -m unit

# 运行集成测试
pytest -m integration

# 运行 UI 测试
pytest -m ui

# 运行指定测试文件
pytest tests/test_provider.py -v

# 生成覆盖率报告
pytest --cov=client/src --cov-report=html
```

### 7.2 测试结构

```
tests/
├── test_provider.py          # 核心功能测试
├── test_agent_framework.py   # 智能体框架测试
├── test_skill_integration.py # 技能集成测试
├── test_memory_enhancements.py # 记忆系统测试
└── test_auto_integration.py  # 自动集成测试
```

### 7.3 调试技巧

**使用 pdb**:
```python
import pdb
pdb.set_trace()  # 设置断点
```

**使用 PyQt 调试**:
```python
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)
app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar)

# 启用 Qt 调试模式
QApplication.setApplicationName("LivingTreeAI - Debug")
```

**日志调试**:
```python
logger.debug(f"变量值: {variable}")
logger.debug(f"函数调用: {func.__name__}")
```

---

## 8. 代码规范

### 8.1 Python 规范

**命名规则**:
- 类名: `PascalCase`
- 函数/方法名: `snake_case`
- 变量名: `snake_case`
- 常量: `UPPER_SNAKE_CASE`

**代码风格**:
- 行长度: 最大 120 字符
- 缩进: 4 空格
- 空行: 函数/类之间空两行

**导入顺序**:
1. 标准库导入
2. 第三方库导入
3. 项目内部导入

```python
# 标准库
import os
import sys

# 第三方库
from PyQt6.QtWidgets import QWidget
import requests

# 项目内部
from client.src.business.config import UnifiedConfig
```

### 8.2 文档规范

**函数文档**:
```python
def process_task(task_id: str, params: dict) -> dict:
    """处理任务
    
    Args:
        task_id: 任务ID
        params: 任务参数
    
    Returns:
        处理结果字典
    
    Raises:
        ValueError: 任务ID无效时
    """
    pass
```

**类文档**:
```python
class TaskProcessor:
    """任务处理器
    
    负责处理和执行各种任务类型。
    
    Attributes:
        task_queue: 任务队列
        max_workers: 最大工作线程数
    """
    pass
```

### 8.3 类型提示

```python
from typing import Optional, List, Dict, Any

def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """获取用户信息"""
    pass

def process_tasks(tasks: List[dict]) -> bool:
    """处理任务列表"""
    pass
```

---

## 9. 发布流程

### 9.1 版本管理

**版本命名**: `v{major}.{minor}.{patch}`

- **Major**: 重大变更，不兼容升级
- **Minor**: 新增功能，向后兼容
- **Patch**: Bug 修复，向后兼容

### 9.2 构建流程

```bash
# 检查代码质量
pylint client/src/
flake8 client/src/

# 运行测试
pytest

# 构建 Docker 镜像
cd deploy/docker
docker-compose build

# 推送镜像
docker push ghcr.io/ookok/livingtreeai:latest
```

### 9.3 部署流程

**Docker Compose**:
```bash
cd deploy/docker
docker-compose up -d
```

**Kubernetes**:
```bash
kubectl apply -f deploy/k8s/deployment.yml
kubectl apply -f deploy/k8s/service.yml
kubectl apply -f deploy/k8s/ingress.yml
```

### 9.4 更新流程

```bash
# 拉取更新
git pull

# 安装依赖
pip install -e ./client -e ./server/relay_server

# 重启服务
docker-compose restart
```

---

## 📚 参考资源

| 资源 | 链接 |
|-----|------|
| PyQt6 文档 | https://doc.qt.io/qtforpython/ |
| FastAPI 文档 | https://fastapi.tiangolo.com/ |
| Ollama API | https://github.com/ollama/ollama/blob/main/docs/api.md |
| 项目 Wiki | https://github.com/ookok/LivingTreeAlAgent/wiki |

---

## 🤝 贡献指南

1. Fork 仓库
2. 创建特性分支 (`git checkout -b feature/feature-name`)
3. 编写代码和测试
4. 提交更改 (`git commit -m 'Add feature'`)
5. 推送到分支 (`git push origin feature/feature-name`)
6. 创建 Pull Request

---

**文档版本**: v1.0.0  
**最后更新**: 2026-04-30  
**维护团队**: LivingTreeAI Team