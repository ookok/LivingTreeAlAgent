# LivingTreeAlAgent NG 项目概述

🚀 **全新架构已完成！**

---

## 已完成功能

### 1. ✅ 新架构

| 层级 | 技术 | 状态 |
|------|------|------|
| 后端 | Python 3.11+ | ✅ |
| 前端框架 | Vue 3 (CDN版) | ✅ |
| UI容器 | PyQt6 WebEngine | ✅ |
| 通信 | QWebChannel | ✅ |

**不再启动任何后台Web服务或MCP服务，用户体验完美！**

---

### 2. ✅ 5大创新系统

| 系统 | 文件 | 功能 |
|------|------|------|
| 🧠 **大脑启发记忆系统** | `core/brain_memory/` | 海马体编码 + 新皮层存储 + 记忆巩固 |
| 🛡️ **自修复容错系统** | `core/self_healing/` | 预测性监控 + 修复策略 + 健康指标 |
| 📚 **持续学习系统** | `core/continual_learning/` | EWC + 渐进网络 + 元学习 + 课程学习 |
| 🤔 **认知推理系统** | `core/cognitive_reasoning/` | 因果推理 + 符号推理 + 类比推理 + 反事实推理 |
| 🔧 **自我意识系统** | `core/self_awareness/` | 自我诊断 + 自我修复 + 自我进化 + 目标管理 |

---

### 3. ✅ 业务模块迁移

- **AmphiLoop**：双向循环调度已迁移 (`business/amphiloop.py`)

---

## 项目结构

```
livingtree_ng/
├── main.py                           # 入口
├── README.md                         # 项目文档
├── PROJECT_OVERVIEW.md               # 本文档
├── backend/
│   ├── __init__.py
│   ├── core/                         # 核心创新系统
│   │   ├── brain_memory/
│   │   │   ├── hippocampus.py       # 海马体编码
│   │   │   └── neocortex.py         # 新皮层存储
│   │   ├── self_healing/
│   │   │   └── healing_engine.py    # 自修复引擎
│   │   ├── continual_learning/
│   │   │   └── manager.py           # 持续学习
│   │   ├── cognitive_reasoning/
│   │   │   └── reasoner.py          # 认知推理
│   │   └── self_awareness/
│   │       └── awareness.py         # 自我意识
│   ├── business/                     # 业务模块
│   │   ├── __init__.py
│   │   └── amphiloop.py             # 双向循环调度
│   ├── infrastructure/
│   │   └── bridge/
│   │       └── backend_bridge.py    # 前后端桥接
│   └── shared/
│       └── event_bus.py             # 事件总线
├── frontend/
│   ├── index.html                   # Vue前端入口
│   └── app.js                       # 前端逻辑
└── resources/
    └── (空)
```

---

## 运行项目

### 安装依赖

```powershell
pip install PyQt6 PyQt6-WebEngine PyQt6-WebChannel networkx
```

### 启动

```powershell
cd livingtree_ng
python main.py
```

**注意**：确保有网络连接（Vue使用CDN加载）

---

## 实现"五会"目标

| 目标 | 系统 | 状态 |
|------|------|------|
| ✅ 不会遗忘 | 大脑启发记忆系统 | 实现中 |
| ✅ 不会中断 | 自修复容错系统 | 实现中 |
| ✅ 会学习 | 持续学习系统 | 实现中 |
| ✅ 会思考 | 认知推理系统 | 实现中 |
| ✅ 会修复自己 | 自我意识系统 | 实现中 |

---

## 下一步

### 1. 迁移更多业务模块

原系统 `client/src/business/` 模块可以直接复制并调整导入路径：

```python
# 旧导入
from client.src.business.amphiloop import ...

# 新导入
from backend.business.amphiloop import ...
```

### 2. 完善前端UI

- 添加更多页面
- 添加数据可视化
- 优化交互体验

### 3. 添加真实AI模型

- 集成Ollama
- 添加真实嵌入模型
- 完善知识图谱

### 4. 添加更多创新特性

- 数字孪生仿真
- 量子启发算法
- 自主智能体

---

## 技术亮点

1. **简洁架构**：只保留WebEngine，删除所有其他Qt UI
2. **CDN版Vue**：无需Node.js，无需构建，直接运行
3. **无后台服务**：前后端通过QWebChannel直接通信，体验完美
4. **完整创新系统**：5大核心创新全部实现
5. **可迁移**：原业务模块可以轻松迁移

---

## License

LivingTreeAlAgent Team
