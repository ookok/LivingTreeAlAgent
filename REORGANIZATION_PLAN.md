# Hermes Desktop V2.0 - 工程化拆分方案

## 现状分析

### 当前问题

```
hermes-desktop/
├── app/              # 企业级GGUF模型管理 (独立服务)
├── core/             # 554个Python文件，职责模糊
├── ui/               # 89个Python文件，UI与业务耦合
├── relay_server/     # FastAPI中继服务器 (独立运行)
├── database/         # SQLite数据库
├── server/           # tracker_server (单文件)
├── main.py           # 桌面客户端入口
└── [50+其他目录]      # 各种工具和测试
```

### 问题清单

1. **职责不清**: `core/` 和 `ui/` 混在一起，没有清晰的边界
2. **服务端混杂**: `relay_server/` 和 `server/` 是两个不同的服务端组件
3. **企业App独立**: `app/` 是另一个独立应用，但放在同一项目
4. **命名不一致**: 有的用 `metaverse_ui/`，有的用 `metaverse_ui_panel.py`
5. **根目录混乱**: 50+个测试文件和顶层文件

---

## 拆分原则

### 单一职责
- 每个包只负责一个功能领域
- 相关代码必须在一起

### 客户端-服务端分离
- **客户端**: PyQt6桌面应用，本地AI能力
- **服务端**: API服务器，远程能力聚合

### 层次清晰
```
presentation/    → UI层 (PyQt6)
business/        → 业务逻辑层
infrastructure/  → 基础设施层
```

---

## 新目录结构

```
hermes-desktop/
│
├── 📁 client/                    # 🖥️ 桌面客户端
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py               # 客户端入口
│   │   │
│   │   ├── 📁 presentation/       # 🎨 表现层 (UI)
│   │   │   ├── __init__.py
│   │   │   ├── main_window.py    # 主窗口
│   │   │   ├── theme.py          # 主题样式
│   │   │   ├── components/       # 可复用UI组件
│   │   │   │   ├── __init__.py
│   │   │   │   ├── button.py
│   │   │   │   ├── card.py
│   │   │   │   ├── dialog.py
│   │   │   │   └── toast.py
│   │   │   ├── panels/           # 功能面板
│   │   │   │   ├── __init__.py
│   │   │   │   ├── home.py       # 首页
│   │   │   │   ├── chat.py       # 聊天
│   │   │   │   ├── assembler.py  # 嫁接园
│   │   │   │   ├── market.py     # 市场
│   │   │   │   └── settings.py   # 设置
│   │   │   └── widgets/          # 独立小部件
│   │   │       ├── __init__.py
│   │   │       ├── task_progress.py
│   │   │       └── avatar.py
│   │   │
│   │   ├── 📁 business/           # 📋 业务逻辑层
│   │   │   ├── __init__.py
│   │   │   ├── assembler/        # 🌱 根系装配园
│   │   │   │   ├── __init__.py
│   │   │   │   ├── navigator.py
│   │   │   │   ├── radar.py
│   │   │   │   ├── conflict.py
│   │   │   │   ├── isolation_bay/
│   │   │   │   ├── adapter_gen.py
│   │   │   │   ├── proving_grounds.py
│   │   │   │   ├── deployment_bay.py
│   │   │   │   └── assembler_core.py
│   │   │   │
│   │   │   ├── fusion_rag/       # 🔍 FusionRAG检索
│   │   │   ├── intelligence/     # 📡 情报中心
│   │   │   ├── social_commerce/  # 🛒 社交电商
│   │   │   ├── flash_listing/    # ⚡ 闪电上架
│   │   │   ├── local_market/     # 🏪 本地市场
│   │   │   ├── mailbox/          # 📧 去中心化邮箱
│   │   │   ├── metaverse/        # 🚀 舰桥系统
│   │   │   ├── living_tree/      # 🌳 生命之树
│   │   │   │
│   │   │   ├── writing/          # ✍️ 写作助手
│   │   │   ├── task/             # 📌 任务系统
│   │   │   └── knowledge/        # 📚 知识管理
│   │   │
│   │   ├── 📁 infrastructure/    # ⚙️ 基础设施层
│   │   │   ├── __init__.py
│   │   │   ├── config/           # 配置管理
│   │   │   ├── database/         # 数据库
│   │   │   │   ├── __init__.py
│   │   │   │   ├── connection.py
│   │   │   │   ├── migrations.py
│   │   │   │   └── models.py
│   │   │   ├── model/            # 模型管理
│   │   │   │   ├── __init__.py
│   │   │   │   ├── ollama_client.py
│   │   │   │   ├── llama_cpp.py
│   │   │   │   └── model_market.py
│   │   │   ├── network/          # 网络通信
│   │   │   │   ├── __init__.py
│   │   │   │   ├── relay_client.py
│   │   │   │   ├── lan_discovery.py
│   │   │   │   └── p2p_broadcast.py
│   │   │   └── storage/          # 存储抽象
│   │   │
│   │   └── 📁 shared/            # 🔧 共享工具
│   │       ├── __init__.py
│   │       ├── utils.py
│   │       ├── logging.py
│   │       └── exceptions.py
│   │
│   ├── 📁 resources/             # 📦 资源文件
│   │   ├── icons/
│   │   ├── styles/
│   │   └── sounds/
│   │
│   ├── 📁 tests/                 # 🧪 客户端测试
│   │   ├── __init__.py
│   │   ├── test_assembler.py
│   │   ├── test_fusion_rag.py
│   │   └── test_ui.py
│   │
│   └── requirements-client.txt
│
│
├── 📁 server/                    # 🌐 服务端
│   │
│   ├── 📁 relay_server/          # 🔄 进化中继服务
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI入口
│   │   ├── api/                  # API端点
│   │   │   ├── __init__.py
│   │   │   ├── collect.py        # 数据收集
│   │   │   ├── bot.py            # Bot管理
│   │   │   ├── forum.py          # 论坛
│   │   │   ├── email.py          # 邮件
│   │   │   └── scheduler.py      # 调度
│   │   ├── models/               # 数据模型
│   │   │   ├── __init__.py
│   │   │   └── schemas.py
│   │   ├── services/             # 业务服务
│   │   │   ├── __init__.py
│   │   │   ├── email_sender.py
│   │   │   ├── email_tasks.py
│   │   │   └── safety.py
│   │   ├── web/                  # Web界面
│   │   │   ├── index.html
│   │   │   └── dashboard.py
│   │   └── requirements-server.txt
│   │
│   ├── 📁 tracker/               # 📊 追踪服务
│   │   ├── __init__.py
│   │   └── tracker_server.py
│   │
│   └── 📁 shared/                # 🔧 服务共享
│       ├── __init__.py
│       └── constants.py
│
│
├── 📁 app/                       # 🏢 企业模型管理 (独立应用)
│   ├── __init__.py
│   ├── main.py                   # GGUF管理入口
│   ├── api/                      # API层
│   ├── core/                     # 核心逻辑
│   ├── services/                 # 服务
│   └── requirements-app.txt
│
│
├── 📁 packages/                   # 📚 公共包
│   ├── shared/                   # 共享代码
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   ├── types.py
│   │   └── exceptions.py
│   │
│   └── living_tree_naming/       # 🌳 生命之树命名
│       ├── __init__.py
│       └── naming.py
│
│
├── 📁 scripts/                    # 🔧 脚本工具
│   ├── setup.sh
│   ├── run_client.sh
│   └── run_server.sh
│
├── 📁 docs/                      # 📖 文档
│
├── 📁 models/                    # 🤖 模型文件
│
├── 📁 data/                      # 💾 数据存储
│
├── main.py                       # 统一入口脚本
├── run.bat                       # Windows启动
├── requirements.txt               # 顶层依赖
├── pyproject.toml                 # 项目配置
└── README.md
```

---

## 模块分类清单

### 业务模块 (business/)

| 模块 | 说明 | 归属 |
|------|------|------|
| `assembler` | 根系装配园 | client |
| `fusion_rag` | 多源融合检索 | client |
| `intelligence` | 情报中心 | client |
| `social_commerce` | 社交电商 | client |
| `flash_listing` | 闪电上架 | client |
| `local_market` | 本地市场 | client |
| `mailbox` | 去中心化邮箱 | client |
| `metaverse` | 舰桥系统 | client |
| `living_tree` | 生命之树 | client |
| `writing` | 写作助手 | client |
| `task` | 任务系统 | client |
| `knowledge` | 知识管理 | client |

### 基础设施 (infrastructure/)

| 模块 | 说明 | 归属 |
|------|------|------|
| `config` | 配置管理 | client |
| `database` | 数据库 | client |
| `model` | 模型管理 | client |
| `network` | 网络通信 | client |
| `storage` | 存储抽象 | client |

### 服务端模块 (server/)

| 模块 | 说明 |
|------|------|
| `relay_server` | 进化中继服务 |
| `tracker` | 追踪服务 |

---

## 迁移计划

### Phase 1: 创建新结构
1. 创建顶层目录 `client/`, `server/`, `packages/`, `scripts/`
2. 创建 `__init__.py` 文件

### Phase 2: 迁移客户端
1. 移动 `core/` → `client/src/business/`
2. 移动 `ui/` → `client/src/presentation/`
3. 移动 `database/` → `client/src/infrastructure/database/`
4. 移动 `resources/`, `static/` → `client/resources/`

### Phase 3: 迁移服务端
1. 移动 `relay_server/` → `server/relay_server/`
2. 移动 `server/tracker_server.py` → `server/tracker/`

### Phase 4: 整理共享代码
1. 创建 `packages/shared/`
2. 提取通用类型定义、常量、异常

### Phase 5: 更新入口和配置
1. 重写 `main.py` 统一入口
2. 更新 `requirements.txt` 分离依赖
3. 更新 `run.bat`

### Phase 6: 更新文档
1. 更新架构文档
2. 更新用户手册
3. 更新README

---

## 依赖分离

### client/requirements-client.txt
```
PyQt6>=6.6.0
pyqtdarktheme>=2.1.0
ollama>=0.1.0
llama-cpp-python>=0.2.0
modelscope>=1.11.0
```

### server/relay_server/requirements-server.txt
```
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic>=2.0.0
apscheduler>=3.10.0
```

### requirements.txt (顶层)
```
# 客户端
-e ./client

# 服务端
-e ./server/relay_server
-e ./server/tracker
```

---

## 命名规范

### Python包命名
- 使用小写字母和下划线: `local_market`
- 避免缩写: `config` 而非 `cfg`
- 模块名反映功能: `assembler` 而非 `mod1`

### 类命名
- PascalCase: `StardockAssembler`
- 继承命名规范: `*Panel`, `*Dialog`, `*Widget`

### 常量命名
- UPPER_SNAKE_CASE: `MAX_RETRY_COUNT`
- 放在 `constants.py` 或类内部

---

## 实施检查清单

- [ ] Phase 1: 创建目录结构
- [ ] Phase 2: 迁移客户端代码
- [ ] Phase 3: 迁移服务端代码
- [ ] Phase 4: 整理共享包
- [ ] Phase 5: 更新入口和配置
- [ ] Phase 6: 更新文档
- [ ] 验证所有import路径正确
- [ ] 验证客户端可以正常启动
- [ ] 验证服务端可以正常启动
