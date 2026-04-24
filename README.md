# LivingTree AI Agent

> *「根系装配园开放，每一位开发者都是嫁接者，将创新的枝条接入生命之树。」*

一个基于 PyQt6 的智能代理开发平台，集成本次会话实现的所有高级功能，包括企业级 P2P 存储、数字分身、积分经济系统和智能浏览器。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)](https://pypi.org/project/PyQt6/)

---

## 核心功能

### 🤖 智能代理架构

| 模块 | 说明 |
|------|------|
| **分层代理架构** | LLM Agent、SequentialAgent、ParallelAgent、LoopAgent 分层设计 |
| **角色管理系统** | agency-agents 风格，支持角色能力矩阵和协作工作流 |
| **共享工作空间** | OpenSpace 风格，多 Agent 共享上下文和消息总线 |
| **技能进化系统** | 技能固化、合并、分裂、遗忘完整生命周期管理 |

### 🎭 虚拟会议系统

| 模块 | 说明 |
|------|------|
| **虚拟会议** | 支持评审会、法庭、课堂等多种场景 |
| **数字分身** | 语音克隆、数字分身参加会议 |
| **实时字幕** | 流式 Whisper 实时语音识别 |
| **同声传译** | 多语言实时翻译 |
| **会议纪要** | LLM 自动生成会议纪要 |

### 🧬 AmphiLoop 引擎

| 模块 | 说明 |
|------|------|
| **双向调度** | 感知→推理→执行→反馈→调整完整闭环 |
| **检查点系统** | 执行状态快照与回滚 |
| **容错回滚** | 失败时自动回退到稳定状态 |
| **增量学习** | 从经验中持续优化 |

### ⚡ Entraly 优化

| 模块 | 说明 |
|------|------|
| **PRISM 优化器** | 4维评估体系（更新频率、使用频率、语义相似度、香农熵） |
| **0/1 背包选择** | 动态规划算法压缩上下文到最小 token 容量 |
| **实时仪表盘** | 本地监控 token 消耗和成本节省 |

### 🌟 数字分身系统

| 模块 | 说明 |
|------|------|
| **数字分身管理** | 创建、管理和升级数字分身 |
| **数字分身出租** | 允许用户出租数字分身参与其他用户的活动 |
| **活动参与** | 数字分身可以参与各种活动，如会议、游戏等 |
| **积分交易** | 出租数字分身可以获得积分，积分可以用于其他服务 |

### 💰 积分经济系统

| 模块 | 说明 |
|------|------|
| **积分管理** | 管理用户积分，包括赚取、花费、转移和交易 |
| **成就系统** | 完成任务获得成就，提升用户等级 |
| **徽章系统** | 获得特殊徽章，展示用户成就 |

### 🛒 电商系统

| 模块 | 说明 |
|------|------|
| **多种服务类型** | 实物商品、远程实景直播、AI 计算服务、数字商品 |
| **积分支付** | 支持使用积分购买商品和服务 |
| **支付流程** | 买家付款→资金冻结→服务开始→服务完成→打款卖家 |

### 🌐 AI 增强浏览器

| 模块 | 说明 |
|------|------|
| **浏览器自动化** | 支持导航、提取内容、填写表单、搜索、截图等操作 |
| **扩展系统** | 借鉴 qutebrowser 的插件系统 |
| **插件系统** | 支持插件的注册、钩子和命令 |

---

## 技术架构

> 🌳 项目采用三层架构（client/src/）

```
LivingTreeAlAgent/
├── client/src/                    # 桌面客户端
│   ├── main.py                     # 客户端入口
│   ├── presentation/              # 表现层 (UI)
│   │   ├── panels/                # 功能面板
│   │   ├── components/            # 可复用组件
│   │   └── widgets/               # 独立小部件
│   ├── business/                  # 业务逻辑层
│   │   ├── fusion_rag/            # 多源融合检索
│   │   ├── hermes_agent/          # 代理框架
│   │   ├── knowledge_graph/       # 知识图谱
│   │   └── ...                    # 其他核心模块
│   └── infrastructure/            # 基础设施层
│       ├── database/              # 数据库
│       ├── config/                # 配置管理
│       └── model/                 # 模型管理
├── core/                          # 核心引擎 (legacy)
├── server/                        # 服务端
├── docs/                          # 文档
│   ├── architecture_manual.md     # 架构手册
│   ├── developer_manual.md         # 开发手册
│   └── operation_manual.md         # 操作手册
└── main.py                        # 统一入口
```

---

## 快速开始

### 环境要求

- Python 3.11+
- PyQt6
- Windows 10+ / macOS / Ubuntu

### 安装依赖

```bash
pip install -e ./client
pip install -e ./server/relay_server
pip install -e ./app
```

### 启动应用

```bash
# 启动桌面客户端（默认）
python main.py client

# 启动中继服务器
python main.py relay

# 启动追踪服务器
python main.py tracker

# 启动所有服务
python main.py all
```

---

## 文档导航

| 文档 | 说明 |
|------|------|
| [架构手册](docs/architecture_manual.md) | 系统架构与设计模式 |
| [开发手册](docs/developer_manual.md) | 开发规范与代码示例 |
| [操作手册](docs/operation_manual.md) | 日常操作指南 |

---

## 更新日志

### 2026-04-24

- 新增 L4 层知识蒸馏模块 (`core/expert_distillation/`)
- 新增用户须知功能（架构/开发/操作手册）
- 重构 Workspace Panel，添加文档快速访问

### 2026-04-21

- 完成三层架构工程化拆分
- 新增 AmphiLoop 引擎、Entraly 优化
- 新增 Hermes Agent 技能系统
- 新增企业级 P2P 存储系统和任务调度系统
- 新增数字分身系统和积分经济系统
- 新增 AI 增强浏览器

---

## 致谢

- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) - Hermes Agent 架构参考
- [PyQt6](https://pypi.org/project/PyQt6/) - 桌面应用框架
- [Ollama](https://ollama.ai/) - 本地 LLM 运行框架

---

*LivingTree AI Agent - 让智能体自我进化* 🌟
