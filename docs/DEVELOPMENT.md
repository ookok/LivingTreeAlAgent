# LivingTree v5.0 — Development Manual

> 开发手册 · 模块组织 · 编码规范 · 调试 · 测试 · 部署

---

## 项目结构

```
LivingTreeAlAgent/
├── livingtree/           # 核心代码 (所有新代码放这里)
│   ├── api/              # FastAPI + HTMX 端点
│   │   ├── htmx_web.py   # 主要面板端点 (3100行, 50+ endpoints)
│   │   ├── routes.py     # REST + WebSocket 端点
│   │   └── server.py     # App工厂 + 中间件
│   ├── core/             # v5.0 核心模块 (18个新模块)
│   ├── network/          # v5.0 网络模块 (8个新模块)
│   ├── dna/              # 意识/生命引擎
│   ├── knowledge/        # 知识库/超图/RAG
│   ├── execution/        # 任务编排/执行
│   ├── treellm/          # LLM路由
│   ├── capability/       # 工具/技能/文档引擎
│   ├── economy/          # 经济学/ROI
│   ├── cell/             # 细胞训练
│   ├── tui/              # Textual TUI
│   ├── observability/    # 监控/评估
│   ├── config/           # 配置/密钥
│   └── templates/        # Jinja2 + HTMX 模板
├── client/web/           # 前端静态文件
│   ├── manifest.json     # PWA配置
│   ├── sw.js             # Service Worker
│   ├── js/               # JS文件
│   └── assets/           # 图标/资源
├── config/               # YAML配置 + 加密密钥
├── protos/               # Protobuf定义
├── deploy/               # Docker/K8s部署
├── tests/                # 测试
├── relay_server.py       # 中继服务器
└── build_relay_exe.py    # EXE构建脚本
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置
cp config/config.yaml.example config/config.yaml
# 编辑 config.yaml, 至少设置 deepseek_api_key

# 3. 运行
python -m livingtree server

# 4. 打开
http://localhost:8100/tree/living        # Living Canvas
http://localhost:8100/api/admin           # 管理员控制台
```

## 模块开发规范

### 新增模块模板

```python
"""Module purpose — one line summary.

Detailed description if needed.
"""

from __future__ import annotations
from typing import Optional
from loguru import logger

class MyModule:
    """Class docstring."""

    def __init__(self, hub=None):
        self._hub = hub

    @property
    def hub(self):
        return self._hub

    async def start(self):
        pass

    async def stop(self):
        pass

_instance: Optional[MyModule] = None

def get_my_module() -> MyModule:
    global _instance
    if _instance is None:
        _instance = MyModule()
    return _instance
```

### 集成到 Hub

在 `livingtree/integration/hub.py` 中:

```python
# _init_sync 中初始化:
from ..core.my_module import get_my_module
self.my_module = get_my_module()
self.my_module._hub = self

# _init_async 中启动:
await self.my_module.start()
```

### 添加 WebSocket 端点

在 `routes.py` 的 `setup_routes()` 中:

```python
@app.websocket("/ws/my-endpoint")
async def my_ws(websocket: WebSocket):
    await websocket.accept()
    # ...
```

### 添加 HTMX 面板

在 `htmx_web.py` 中:

```python
@htmx_router.get("/my/panel")
async def tree_my_panel(request: Request):
    return HTMLResponse('<div class="card">...</div>')
```

### 自适应触发

模块应自动触发, 不依赖手动调用:

```python
# 好的模式:
# 在 hub._init_async 中 await module.start()
# module.start() 内部创建 asyncio.create_task(loop)
# loop 中定时检查 + 自动响应

# 不好的模式:
# 等待用户调用 /api/trigger_my_module
```

## 编码规范

- **导入**: `from livingtree.core import X`
- **日志**: `from loguru import logger` → `logger.info()`
- **类型**: 所有公共方法带类型标注
- **单例**: `get_xxx()` 模式, 全局单例
- **异步**: 所有 I/O 操作使用 async/await
- **WebSocket**: 4个端点 `/ws`, `/ws/im`, `/ws/rtc-signal`, `/ws/reach`
- **Protobuf**: P2P消息使用二进制, 不是JSON
- **管理面板**: `data-admin="1"` 标记, 默认隐藏

## 调试

```bash
# 查看日志
tail -f .livingtree/logs/livingtree.log

# 查看API文档
http://localhost:8100/docs     # Swagger
http://localhost:8100/redoc    # ReDoc

# 查看管理面板
http://localhost:8100/api/admin

# 单步测试
python -m livingtree quick "你的问题"
```

## 测试

```bash
# 全部测试
pytest

# 单个文件
pytest tests/test_chat.py -v

# 按标记
pytest -m unit      # 单元测试
pytest -m slow      # 慢速测试

# 378 tests
```

## 构建

```bash
# 中继服务器 EXE
.venv\Scripts\python.exe build_relay_exe.py
# 输出: dist/relay_server.exe (~30MB)

# Docker
docker build -f deploy/docker/Dockerfile.relay -t livingtree-relay .
docker run -p 8899:8899 livingtree-relay

# Protobuf 编译 (修改 proto 后)
python -m grpc_tools.protoc -Iprotos --python_out=livingtree/network --grpc_python_out=livingtree/network protos/livingtree.proto
```

## 配置文件

```
config/config.yaml        # 主配置 (LLM keys, 端口, 模型)
config/secrets.enc        # Fernet加密的密钥 (不要提交到Git)
.livingtree/              # 运行时数据 (不要提交)
  model_spec.md           # AI宪法
  bonding.json            # 用户羁绊数据
  knowledge_forest.json   # 个人知识森林
  memory_tiers.json       # 分层记忆
  preferences.jsonl       # DPO偏好
  sessions/               # 会话快照
```

## 反模式

- ❌ 不要直接修改 `client/` — 新代码放 `livingtree/`
- ❌ 不要在UI中硬编码工具 — 用AI驱动发现
- ❌ 不要用JSON传P2P消息 — 用Protobuf (message_bus)
- ❌ 不要手动触发模块 — 自适应
- ❌ 不要暴露管理面板给终端用户 — ⚙ 入口
