# LivingTreeAlAgent NG

## 项目概述

这是一个全面重构的项目，具有创新架构：

- **只使用 PyQt6 WebEngine**
- **Vue 3 前端（CDN 版）**
- **Python 后端**
- **QWebChannel 通信**
- **5 大创新系统**

## 架构

```
livingtree_ng/
├── main.py
├── backend/
│   ├── core/
│   │   ├── brain_memory/       # 大脑启发记忆
│   │   ├── self_healing/       # 自修复容错
│   │   ├── continual_learning/ # 持续学习
│   │   ├── cognitive_reasoning/ # 认知推理
│   │   ├── self_awareness/     # 自我意识
│   │   └── llm/              # LLM 集成
│   │       ├── ollama_client.py
│   │       └── llm_manager.py
│   └── infrastructure/
│       ├── config.py           # 配置系统
│       ├── database.py         # 数据库系统
│       └── bridge/
│           └── backend_bridge.py # 前后端桥接
└── frontend/
    ├── index.html
    └── app.js
```

## 快速开始

### 1. 安装依赖

```powershell
pip install -r requirements.txt
```

### 2. （可选）安装并运行 Ollama

**下载 Ollama**

Windows: https://ollama.ai/download

**拉取模型**

```powershell
ollama pull llama3
```

### 3. 运行

```powershell
python main.py
```

## 功能特性

### 5 大创新系统

| 系统 | 功能 | 目标 |
|------|------|------|
| 🧠 **大脑启发记忆** | 海马体编码 + 新皮层存储 | 不会遗忘 |
| 🛡️ **自修复容错** | 预测监控 + 修复策略 | 不会中断 |
| 📚 **持续学习** | EWC + 渐进网络 + 元学习 | 会学习 |
| 🤔 **认知推理** | 因果/符号/类比推理 | 会思考 |
| 🔧 **自我意识** | 自我诊断 + 修复 + 进化 | 会修复自己 |

### LLM 集成

- **Ollama 集成**
- **对话历史管理**
- **系统提示词**
- **配置化模型调用**

### 会话管理

- **创建/列出会话**
- **会话历史**
- **数据库持久化**

### 配置系统

- **NanochatConfig 配置**
- **保存/加载配置**
- **运行时更新配置**

### 数据库系统

- **SQLite 数据库**
- **会话/消息/知识存储**

### 日志系统

- **统一日志系统**
- **文件旋转**
- **控制台输出**

## UI 功能

| 页面 | 功能 |
|------|------|
| 仪表板 | 系统状态 + 会话列表 + 聊天 + 推理 |
| 记忆系统 | 编码/检索记忆 |
| 自修复 | 触发修复 + 查看历史 |
| 关于 | 项目信息 |

## API 功能

| 功能 | API |
|------|------|
| LLM 聊天 | `llmChat(user_message, conversation_id)` |
| LLM 模型列表 | `llmListModels()` |
| LLM 连接检查 | `llmCheckConnection()` |
| 配置管理 | `getConfig()` / `setConfig()` |
| 会话管理 | `createSession()` / `listSessions()` / `getSession()` |
| 消息发送 | `sendChatMessageFull()` |
| 知识管理 | `addKnowledge()` / `searchKnowledge()` |

## 数据目录

```
data/
├── logs/           # 日志
├── memory/         # 记忆存储
├── db.sqlite       # SQLite 数据库
└── config.json    # 配置文件
```

## 创新系统详解

### 1. 大脑启发记忆系统

- **海马体编码** - 快速记忆编码
- **新皮层存储** - 语义记忆存储
- **记忆巩固** - 记忆巩固过程

### 2. 自修复容错系统

- **健康监控** - 实时监控系统健康
- **修复策略** - 多种修复策略

### 3. 持续学习系统

- **知识保护** - 防止灾难性遗忘
- **元学习** - 学习如何学习
- **课程学习** - 从简单到复杂学习

### 4. 认知推理系统

- **因果推理** - 因果关系推理
- **符号推理** - 符号逻辑推理
- **类比推理** - 类比推理

### 5. 自我意识系统

- **自我模型** - 系统自我认知
- **自我诊断** - 自动诊断问题
- **自我修复** - 自动修复问题
- **自我进化** - 系统自我进化
