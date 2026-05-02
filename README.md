# LivingTree AI Agent

> 🌳 数字生命体 — 智能代理开发平台 | v1.0.0

桌面 AI 代理平台，基于 PyQt6 + FastAPI + Vue 3 混合架构。

## 架构

项目已重构为清晰的 `livingtree/` 核心包 + `client/src/` 遗留代码的混合架构。

```
livingtree/                    # 新核心 —— 所有新代码
├── core/                      # 核心引擎 (LifeEngine + 任务链)
│   ├── life_engine.py         # 中央调度器 (感知→认知→规划→执行→反思)
│   ├── model/                 # 统一模型路由 (Local/Edge/Cloud 三层)
│   ├── intent/                # 意图解析 + 多轮跟踪
│   ├── memory/                # 统一存储 (VectorDB + GraphDB + Sessions)
│   ├── planning/              # 任务规划 + CoT 分解
│   ├── skills/                # 技能匹配
│   ├── tools/                 # 工具注册与调度
│   ├── plugins/               # 插件管理
│   ├── context/               # 上下文装配与压缩
│   ├── evolution/             # 自进化引擎
│   ├── world_model/           # 世界模型 (状态预测)
│   └── observability/         # 日志/追踪/指标
├── infrastructure/            # 配置/事件总线/数据库/WebSocket/安全
├── adapters/                  # MCP/API网关/Provider适配
├── frontend_bridge/           # 前端桥接
├── server/                    # Relay + Tracker 适配器
└── main.py                    # CLI 入口
```

## 快速开始

```powershell
# 安装依赖
pip install -r requirements.txt

# 启动
python main.py client           # PyQt6 桌面客户端
python -m livingtree server     # FastAPI 服务 (http://localhost:8100)
python -m livingtree quick      # 交互式对话
python -m livingtree test       # 集成测试

# 或使用一键启动器
run.bat
```

## 测试

```powershell
python main.py test                        # CLI 测试
python -m livingtree test                  # 包测试
pytest tests/test_livingtree_core.py -v    # 核心套件 (36 tests)
pytest tests/ -v                           # 全部测试 (95 tests)
```

## 配置

```python
from livingtree.infrastructure.config import config

# Dataclass 风格访问
model = config.ollama.default_model
timeout = config.timeouts.default

# 根据任务复杂度计算最优参数
optimal = config.compute_optimal(depth=5)
```

配置文件: `config/config.yaml`

## API

启动服务器后访问 http://localhost:8100/docs 查看 Swagger 文档。

```
POST /api/chat     — 聊天
GET  /api/health   — 健康检查
GET  /api/tools    — 工具列表
GET  /api/skills   — 技能列表
GET  /api/metrics  — 运行时指标
WS   /ws           — WebSocket
```

## 项目结构

```
root/
├── livingtree/         # ✅ 新核心包
├── client/src/         # 遗留代码 (逐步迁移中)
│   ├── business/       # 业务逻辑 (~340 files)
│   ├── frontend/       # Vue 3 前端
│   └── presentation/   # PyQt6 UI
├── server/             # 遗留服务器
├── app/                # 企业应用
├── mobile/             # PWA/移动端
├── packages/           # 共享库
├── tests/              # 测试
├── docs/               # 文档
└── config/             # 配置文件
```

## 许可

MIT
