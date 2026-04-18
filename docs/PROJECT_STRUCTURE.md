# Hermes Desktop V2.0 - 工程化拆分后目录结构

## 顶层结构

```
hermes-desktop/
├── client/                    # 🖥️ 桌面客户端
├── server/                    # 🌐 服务端
├── app/                      # 🏢 企业模型管理 (独立应用)
├── packages/                 # 📚 公共包
├── scripts/                  # 🔧 脚本工具
├── docs/                     # 📖 文档
├── models/                   # 🤖 模型文件
├── data/                     # 💾 数据存储
├── main.py                   # 🚀 统一入口
├── run.bat                   # 🪟 Windows启动脚本
└── requirements.txt          # 📦 依赖
```

---

## 客户端结构 (client/)

```
client/
├── src/
│   ├── __init__.py
│   ├── main.py               # 客户端入口
│   │
│   ├── presentation/         # 🎨 表现层 (UI)
│   │   ├── __init__.py
│   │   ├── main_window.py   # 主窗口
│   │   ├── theme.py         # 主题样式
│   │   ├── panels/          # 功能面板
│   │   │   ├── assembler_panel.py  # 嫁接园
│   │   │   ├── metaverse_panel.py   # 舰桥
│   │   │   ├── home_page.py        # 首页
│   │   │   ├── chat_panel.py       # 聊天
│   │   │   └── settings_panel.py   # 设置
│   │   ├── components/      # 可复用组件
│   │   └── widgets/         # 独立小部件
│   │
│   ├── business/            # 📋 业务逻辑层
│   │   ├── __init__.py
│   │   ├── assembler/       # 🌱 根系装配园
│   │   │   ├── assembler_core.py
│   │   │   ├── navigator.py
│   │   │   ├── radar.py
│   │   │   ├── conflict.py
│   │   │   ├── isolation_bay/
│   │   │   ├── adapter_gen.py
│   │   │   ├── proving_grounds.py
│   │   │   └── deployment_bay.py
│   │   │
│   │   ├── fusion_rag/      # 🔍 FusionRAG检索
│   │   ├── intelligence/     # 📡 情报中心
│   │   ├── social_commerce/  # 🛒 社交电商
│   │   ├── flash_listing/   # ⚡ 闪电上架
│   │   ├── local_market/    # 🏪 本地市场
│   │   ├── mailbox/         # 📧 去中心化邮箱
│   │   ├── metaverse/       # 🚀 舰桥系统
│   │   ├── living_tree/     # 🌳 生命之树
│   │   ├── writing/        # ✍️ 写作助手
│   │   ├── task/           # 📌 任务系统
│   │   └── knowledge/      # 📚 知识管理
│   │
│   ├── infrastructure/      # ⚙️ 基础设施层
│   │   ├── __init__.py
│   │   ├── config/         # 配置管理
│   │   │   └── config.py
│   │   ├── database/       # 数据库
│   │   │   ├── __init__.py
│   │   │   └── connection.py
│   │   ├── model/          # 模型管理
│   │   │   ├── ollama_client.py
│   │   │   └── llama_cpp.py
│   │   ├── network/        # 网络通信
│   │   │   ├── relay_client.py
│   │   │   └── lan_discovery.py
│   │   └── storage/        # 存储抽象
│   │
│   └── shared/             # 🔧 共享工具
│       ├── __init__.py
│       ├── utils.py
│       ├── logging.py
│       └── exceptions.py
│
├── resources/               # 📦 资源文件
│   ├── icons/
│   ├── styles/
│   └── sounds/
│
├── tests/                  # 🧪 客户端测试
│   ├── __init__.py
│   └── test_assembler.py
│
└── requirements-client.txt
```

---

## 服务端结构 (server/)

```
server/
├── __init__.py
│
├── relay_server/           # 🔄 进化中继服务
│   ├── __init__.py
│   ├── main.py            # FastAPI入口
│   ├── api/               # API端点
│   │   ├── collect.py     # 数据收集
│   │   ├── bot.py         # Bot管理
│   │   ├── forum.py       # 论坛
│   │   ├── email.py       # 邮件
│   │   └── scheduler.py   # 调度
│   ├── models/            # 数据模型
│   │   └── schemas.py
│   ├── services/          # 业务服务
│   │   ├── email_sender.py
│   │   ├── email_tasks.py
│   │   └── safety.py
│   ├── web/              # Web界面
│   │   ├── index.html
│   │   └── dashboard.py
│   └── requirements-server.txt
│
├── tracker/               # 📊 追踪服务
│   ├── __init__.py
│   └── tracker_server.py
│
└── shared/               # 🔧 服务共享
    └── constants.py
```

---

## 企业应用结构 (app/)

```
app/
├── __init__.py
├── main.py               # GGUF管理入口
├── api/                 # API层
├── core/                # 核心逻辑
├── services/            # 服务
└── requirements-app.txt
```

---

## 公共包结构 (packages/)

```
packages/
├── shared/              # 共享代码
│   ├── __init__.py
│   ├── constants.py
│   ├── types.py
│   └── exceptions.py
│
└── living_tree_naming/  # 🌳 生命之树命名
    ├── __init__.py
    └── naming.py
```

---

## 启动方式

### Windows
```batch
run.bat              # 默认启动客户端
run.bat client       # 启动客户端
run.bat relay        # 启动中继服务器
run.bat tracker      # 启动追踪服务器
run.bat all          # 启动所有服务
```

### Linux/Mac
```bash
./scripts/run_client.sh           # 默认启动客户端
./scripts/run_client.sh client    # 启动客户端
./scripts/run_client.sh relay    # 启动中继服务器
```

### Python直接运行
```bash
python main.py client    # 启动客户端
python main.py relay     # 启动中继服务器
python main.py tracker   # 启动追踪服务器
```

---

## 模块归属表

| 模块 | 归属 | 说明 |
|------|------|------|
| assembler | client | 根系装配园 |
| fusion_rag | client | 多源融合检索 |
| intelligence | client | 情报中心 |
| social_commerce | client | 社交电商 |
| flash_listing | client | 闪电上架 |
| local_market | client | 本地市场 |
| mailbox | client | 去中心化邮箱 |
| metaverse | client | 舰桥系统 |
| living_tree | client | 生命之树 |
| relay_server | server | 中继服务 |
| tracker | server | 追踪服务 |
