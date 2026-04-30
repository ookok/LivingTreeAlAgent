# 🌳 LivingTreeAI Agent Platform

> **新一代 AI 智能体平台** - 构建未来的 AI 编码体验

LivingTreeAI 是一个基于 PyQt6 的桌面 AI 智能体平台，采用清晰的三层架构设计，具备多代理系统、P2P 存储、数字孪生、信用经济、电子商务、浏览器自动化、虚拟会议等核心能力。

---

## 📋 项目状态

**阶段**: **全面测试阶段** (Phase 1 Complete)

所有核心功能已开发完成，进入质量保证和集成测试阶段。

---

## ✨ 核心功能

### 🎯 多代理系统 (Multi-Agent System)
- **Hermes Agent Framework**: 灵活的智能体框架，支持多种智能体类型
- **Agent Orchestration**: 智能体协作编排引擎
- **Skill System**: 技能系统，支持技能发现、匹配和执行

### 🔄 P2P 网络 (Peer-to-Peer Networking)
- **P2P CDN**: 分布式内容分发网络
- **P2P Storage**: 去中心化存储系统
- **Node Tracker**: 节点追踪和发现

### 🤖 数字孪生 (Digital Twin)
- **Digital Avatar**: 数字化身系统
- **Virtual Conference**: 虚拟会议支持
- **Real-time Collaboration**: 实时协作能力

### 💰 信用经济 (Credit Economy)
- **Points System**: 积分和信用系统
- **Reward Mechanism**: 奖励机制
- **Economic Model**: 经济模型

### 🛒 电子商务 (E-commerce)
- **DecCommerce**: 去中心化电商模块
- **Marketplace**: 市场和交易平台
- **Smart Contracts**: 智能合约支持

### 🌐 浏览器自动化 (Browser Automation)
- **Web Automation**: 网页自动化操作
- **Browser Integration**: 浏览器深度集成
- **Web Scraping**: 智能网页抓取

### ⏰ 智能调度 (Smart Scheduling)
- **AmphiLoop**: 双向调度引擎
- **Task Planning**: 任务规划系统
- **Resource Management**: 资源管理

### 🧠 智能优化 (AI Optimization)
- **PRISM**: 上下文优化系统
- **Fusion RAG**: 多源检索增强生成
- **Knowledge Graph**: 知识图谱

---

## 🚀 快速开始

### 系统要求

- **Python**: 3.11+
- **操作系统**: Windows 10+, macOS 10.15+, Linux (Ubuntu 20.04+)
- **内存**: 建议 8GB+
- **存储**: 至少 10GB 可用空间

### 一键启动

**Windows**:
```bash
双击 run.bat
```

**Linux/Mac**:
```bash
chmod +x run.sh
./run.sh
```

### 手动安装

```bash
# 安装客户端
pip install -e ./client

# 安装服务端
pip install -e ./server/relay_server

# 启动客户端
python main.py client
```

### 启动命令

```bash
python main.py client          # 启动桌面客户端（默认）
python main.py relay           # 启动中继服务器
python main.py tracker         # 启动 P2P 追踪器
python main.py app             # 启动企业应用
python main.py check           # 环境自检
python main.py update          # 检查更新
python main.py config          # 运行配置向导
python main.py model <name>    # 确保模型已安装
```

---

## 📁 项目结构

```
LivingTreeAlAgent/
├── client/
│   └── src/
│       ├── business/          # 业务逻辑层 (~340+ 文件)
│       │   ├── hermes_agent/  # 智能体框架
│       │   ├── fusion_rag/    # 多源检索
│       │   ├── knowledge_graph/ # 知识图谱
│       │   ├── amphiloop/     # 调度引擎
│       │   ├── optimization/  # PRISM 优化
│       │   ├── enterprise/    # P2P 存储
│       │   ├── digital_twin/  # 数字孪生
│       │   ├── credit_economy/ # 信用经济
│       │   ├── decommerce/    # 电子商务
│       │   └── living_tree_ai/ # 核心 AI
│       ├── presentation/      # 表示层 (~200+ 文件)
│       │   ├── panels/        # UI 面板
│       │   ├── components/    # 可复用组件
│       │   ├── widgets/       # 自定义部件
│       │   └── dialogs/       # 对话框
│       ├── infrastructure/    # 基础设施层
│       │   ├── database/      # 数据库 (v1-v14)
│       │   ├── config/        # 配置管理
│       │   └── network/       # 网络通信
│       └── shared/            # 共享工具
├── server/                    # 服务端
│   ├── relay_server/          # FastAPI 中继
│   └── tracker_server.py      # P2P 节点追踪
├── app/                       # 企业应用
├── deploy/                    # 部署配置
│   ├── docker/                # Docker 配置
│   └── k8s/                   # Kubernetes 配置
└── scripts/                   # 辅助脚本
    ├── check.py               # 环境自检
    ├── config_wizard.py       # 配置向导
    ├── auto_update.py         # 自动更新
    ├── auto_heal.py           # 自动修复
    └── model_manager.py       # 模型管理
```

---

## 🏗️ 架构设计

### 三层架构

| 层级 | 职责 | 技术栈 |
|-----|------|-------|
| **Presentation Layer** | UI 展示和用户交互 | PyQt6 |
| **Business Layer** | 业务逻辑处理 | Python |
| **Infrastructure Layer** | 数据存储和网络 | SQLite/PostgreSQL, Redis |

### 核心模块

1. **Agent Framework**: 智能体生命周期管理
2. **Model Router**: LLM 模型路由和选择
3. **Memory System**: 长短期记忆系统
4. **Skill System**: 技能注册和执行
5. **Task Orchestrator**: 任务编排引擎
6. **Knowledge Graph**: 知识图谱管理
7. **RAG Engine**: 检索增强生成
8. **Event Bus**: 事件总线

---

## 🔧 配置

### 配置文件

配置文件位于 `config/` 目录：

- `config.yaml`: 主配置文件
- `unified.yaml`: 统一配置
- `logging.yaml`: 日志配置
- `tools_manifest.json`: 工具清单

### 使用 NanochatConfig (推荐)

```python
from client.src.business.nanochat_config import config

# 直接属性访问
url = config.ollama.url
timeout = config.timeouts.default
```

### 使用 UnifiedConfig (兼容模式)

```python
from client.src.business.config import UnifiedConfig

config = UnifiedConfig.get_instance()
url = config.get("endpoints.ollama.url")
```

---

## 🧪 测试

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
```

---

## 📦 部署

### Docker 部署

```bash
cd deploy/docker
docker-compose up -d
```

### Kubernetes 部署

```bash
kubectl apply -f deploy/k8s/deployment.yml
```

---

## 🤝 贡献

欢迎贡献代码！请遵循以下步骤：

1. Fork 仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

---

## 📞 联系方式

- **项目主页**: https://github.com/ookok/LivingTreeAlAgent
