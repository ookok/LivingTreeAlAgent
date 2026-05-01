# LivingTreeAlAgent NG - 快速启动指南

## 🚀 5 分钟快速开始

### 1. 检查环境要求

确保你已安装：
- Python 3.11+
- PyQt6 & PyQt6 WebEngine
- Ollama（可选，用于 LLM 功能）

### 2. 安装依赖

```powershell
cd f:\mhzyapp\LivingTreeAlAgent\livingtree_ng
pip install -r requirements.txt
```

### 3. （可选）启动 Ollama

如果你想使用完整的 LLM 功能：

1. 下载并安装 Ollama：https://ollama.ai/download
2. 拉取模型：
   ```powershell
   ollama pull llama3
   ```
3. 验证服务正常运行：
   ```powershell
   curl http://localhost:11434/api/tags
   ```

### 4. 启动应用

```powershell
python main.py
```

## 🎯 功能导航

### 页面概览

| 页面 | 路径 | 功能 |
|------|------|------|
| 仪表板 | / | 系统状态、会话、聊天、推理 |
| 记忆系统 | /memory | 记忆编码、记忆检索 |
| 自修复 | /healing | 触发修复、查看历史 |
| 设置 | /settings | 系统设置、配置管理 |
| 关于 | /about | 项目说明、版本信息 |

### 核心特色功能

#### 🧠 大脑启发记忆系统
- 4 种记忆类型：
  - 情景记忆 - 特定事件和经历
  - 语义记忆 - 通用知识和概念
  - 程序记忆 - 技能和过程
  - 情绪记忆 - 情绪相关经历
- 海马体编码 - 快速记忆获取
- 新皮层存储 - 长期语义存储
- 记忆巩固 - 离线记忆重放

#### 🛡️ 自修复容错系统
- 实时健康监控
- 多种修复策略
- 修复历史追踪
- 预测性故障检测

#### 📚 持续学习系统
- EWC (Elastic Weight Consolidation) 防止遗忘
- 渐进神经网络
- 元学习
- 课程学习

#### 🤔 认知推理系统
- 因果推理
- 符号推理
- 类比推理
- 反事实推理

#### 🔧 自我意识系统
- 自我模型
- 自我诊断
- 自我修复
- 自我优化

## 📂 项目结构

```
livingtree_ng/
├── main.py                      # PyQt6 + WebEngine 入口
├── requirements.txt             # Python 依赖
├── README.md                    # 详细说明
├── PROJECT_OVERVIEW.md          # 项目概览
├── QUICKSTART.md                # 本文档
├── backend/
│   ├── __init__.py
│   ├── core/                    # 核心创新系统
│   │   ├── brain_memory/        # 🧠 大脑启发记忆
│   │   │   ├── hippocampus.py   # 海马体编码
│   │   │   └── neocortex.py     # 新皮层存储
│   │   ├── self_healing/        # 🛡️ 自修复系统
│   │   │   └── healing_engine.py
│   │   ├── continual_learning/  # 📚 持续学习
│   │   │   └── manager.py
│   │   ├── cognitive_reasoning/ # 🤔 认知推理
│   │   │   └── reasoner.py
│   │   ├── self_awareness/      # 🔧 自我意识
│   │   │   └── awareness.py
│   │   └── llm/                 # 🤖 LLM 集成
│   │       ├── ollama_client.py
│   │       └── llm_manager.py
│   ├── business/                # 业务逻辑
│   │   ├── amphiloop.py         # 双向循环调度
│   │   └── ...
│   ├── infrastructure/          # 基础设施
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # 数据库
│   │   └── bridge/
│   │       └── backend_bridge.py # 前后端桥接
│   └── shared/                  # 共享组件
│       ├── event_bus.py         # 事件总线
│       └── logger.py            # 统一日志
└── frontend/
    ├── index.html               # Vue 3 入口
    └── app.js                   # Vue 应用代码
```

## 💡 使用示例

### 创建会话并聊天

1. 打开应用
2. 点击「新建会话」
3. 输入会话名称
4. 在聊天输入框发送消息
5. AI 会自动回复

### 编码记忆

1. 切换到「记忆系统」页面
2. 选择记忆类型
3. 输入记忆内容
4. 点击「编码」

### 触发修复

1. 切换到「自修复」页面
2. 输入组件名称和问题
3. 点击「请求修复」

## 🔧 常见问题

### Ollama 连接失败

**问题**: 显示「未连接」
**解决方案**:
1. 检查 Ollama 服务是否运行
2. 确认 Ollama URL 正确（默认：http://localhost:11434）
3. 检查防火墙配置

### 依赖安装问题

**问题**: PyQt6 安装失败
**解决方案**:
```powershell
pip install PyQt6 PyQt6-WebEngine PyQt6-WebChannel
```

### 数据库问题

**问题**: 数据库连接错误
**解决方案**: 首次运行会自动创建 `data` 文件夹，请确保有写入权限

## 📚 资源链接

- Vue 3 文档: https://vuejs.org/
- PyQt6 文档: https://www.riverbankcomputing.com/static/Docs/PyQt6/
- Ollama 文档: https://ollama.ai/docs/

## 🎉 祝贺你！

现在你已经拥有了一个：
- 完整的 AI 应用
- 5 大创新系统
- 优雅的界面
- 强大的功能

继续探索和开发，享受创新的乐趣！
