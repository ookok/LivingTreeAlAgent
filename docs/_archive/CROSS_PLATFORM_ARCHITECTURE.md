# Hermes Desktop 跨平台架构设计方案

**版本**: V2.0
**更新时间**: 2026-04-19

---

## 一、架构概述

### 1.1 设计目标

| 目标 | 描述 |
|------|------|
| **桌面优先** | PyQt6 桌面端为核心，保持功能完整 |
| **Web 扩展** | FastAPI Web 层，提供 PWA 和 REST API |
| **移动适配** | Kivy/PWA 移动端，保持核心体验一致 |
| **代码复用** | 核心业务逻辑共享，最小化重复开发 |

### 1.2 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端层 (Client)                         │
├──────────────┬──────────────┬──────────────┬───────────────────┤
│  桌面端      │   Web端      │   移动端     │   嵌入式端        │
│  (PyQt6)     │   (PWA)      │   (Kivy)     │   (TUI/CLI)       │
└──────┬───────┴──────┬───────┴──────┬───────┴───────────────────┘
       │              │              │
       ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API 网关层 (API Gateway)                    │
│  ┌──────────────┬──────────────┬──────────────┬───────────────┐  │
│  │  REST API   │  WebSocket  │  GraphQL    │   SSE        │  │
│  └──────────────┴──────────────┴──────────────┴───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      核心业务层 (Core Business)                  │
│  ┌────────────┬────────────┬────────────┬────────────┬────────┐ │
│  │  Agent    │  Memory    │   RAG     │   P2P     │  etc.  │ │
│  └────────────┴────────────┴────────────┴────────────┴────────┘ │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      数据层 (Data Layer)                         │
│  ┌────────────┬────────────┬────────────┬────────────────────┐  │
│  │  SQLite   │  Vector DB │  File DB  │   Network Cache   │  │
│  └────────────┴────────────┴────────────┴────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、桌面端架构 (PyQt6)

### 2.1 目录结构

```
hermes-desktop/
├── ui/                      # PyQt6 UI 层
│   ├── main_window.py       # 主窗口 (三栏布局)
│   ├── *_panel/             # 功能面板 (100+)
│   └── components/          # 通用组件
├── core/                    # 核心业务逻辑
│   ├── agent.py             # Hermes Agent
│   ├── fusion_rag/          # 四层混合检索
│   ├── intelligent_memory/  # 智能记忆系统
│   ├── cognee_memory/      # Cognee 记忆适配器
│   ├── disco_rag/           # Discourse-Aware RAG
│   ├── nano_vllm/           # Nano-vLLM 客户端
│   └── smart_deploy/        # 智能部署系统
├── models/                  # GGUF 模型
└── main.py                  # 入口
```

### 2.2 主窗口布局

```
┌──────────────────────────────────────────────────────────────┐
│  菜单栏 (MenuBar)                                            │
├────────────┬─────────────────────────────┬───────────────────┤
│            │                             │                   │
│  侧边栏    │      主工作区              │   详情面板       │
│ (Sidebar)  │   (MainWorkspace)           │  (DetailPanel)   │
│            │                             │                   │
│ • 会话     │  ┌─────────────────────┐   │  • 属性          │
│ • 技能     │  │    Tab 区域         │   │  • 历史          │
│ • 设置     │  │                     │   │  • 操作          │
│            │  │                     │   │                   │
│            │  └─────────────────────┘   │                   │
├────────────┴─────────────────────────────┴───────────────────┤
│  状态栏 (StatusBar) - 连接状态 | 任务进度 | 快捷操作         │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、Web 端架构 (PWA + FastAPI)

### 3.1 目录结构

```
hermes-desktop/web/
├── static/                  # 静态资源
│   ├── icons/              # PWA 图标
│   ├── sw.js               # Service Worker
│   └── manifest.json        # PWA Manifest
├── src/                    # Web 源码
│   ├── components/         # React/Vue 组件
│   ├── pages/              # 页面
│   │   ├── chat/           # 聊天页面
│   │   ├── skills/         # 技能市场
│   │   ├── knowledge/      # 知识库
│   │   └── settings/       # 设置
│   ├── stores/             # 状态管理 (Pinia/Zustand)
│   ├── services/           # API 服务
│   └── App.tsx
├── server/                  # FastAPI 后端
│   ├── api/                # API 路由
│   │   ├── chat.py         # 聊天 API
│   │   ├── skills.py       # 技能 API
│   │   ├── memory.py       # 记忆 API
│   │   └── upload.py       # 上传 API
│   ├── core/               # 复用 desktop 核心
│   ├── middleware/         # 中间件
│   └── main.py
├── package.json
└── vite.config.ts
```

### 3.2 PWA 功能

| 功能 | 实现 |
|------|------|
| **离线访问** | Service Worker 缓存核心资源 |
| **安装到桌面** | Web App Manifest |
| **推送通知** | Web Push API |
| **后台同步** | Background Sync API |
| **文件系统** | File System Access API |

### 3.3 API 端点

```python
# 核心 API
GET    /api/v1/health              # 健康检查
GET    /api/v1/status              # 系统状态
POST   /api/v1/chat/completions    # 聊天完成
GET    /api/v1/memory/search       # 记忆搜索
POST   /api/v1/memory/store        # 存储记忆
GET    /api/v1/skills/list         # 技能列表
POST   /api/v1/skills/execute      # 执行技能
POST   /api/v1/upload              # 文件上传

# WebSocket
WS     /ws/v1/chat                 # 聊天 WebSocket
WS     /ws/v1/status               # 状态推送
```

---

## 四、移动端架构 (Kivy + PWA)

### 4.1 目录结构

```
hermes-desktop/mobile/
├── main.py                    # Kivy 入口
├── adaptive_layout.py         # 自适应布局
├── foldable_support.py       # 折叠屏支持
├── tablet_features.py        # 平板特性
├── screens/                  # 屏幕
│   ├── chat_screen.py        # 聊天屏幕
│   ├── skills_screen.py      # 技能屏幕
│   └── settings_screen.py    # 设置屏幕
├── widgets/                  # 移动端组件
│   ├── mobile_chat.py        # 移动端聊天
│   ├── gesture_nav.py        # 手势导航
│   └── bottom_nav.py         # 底部导航
└── utils/                    # 工具
    ├── device_detector.py    # 设备检测
    └── offline_sync.py       # 离线同步
```

### 4.2 设备适配策略

| 设备类型 | 屏幕尺寸 | 布局策略 |
|----------|----------|----------|
| **Phone** | < 600dp | 单栏、底部导航 |
| **Phablet** | 600-900dp | 双栏、侧边栏折叠 |
| **Tablet** | 900-1200dp | 三栏、侧边栏展开 |
| **Large Tablet** | > 1200dp | 桌面布局 |

### 4.3 响应式设计

```python
# 自适应网格列数
PHONE_PORTRAIT = 3
PHONE_LANDSCAPE = 5
TABLET_PORTRAIT = 5
TABLET_LANDSCAPE = 7
LARGE_TABLET = 8

# 图标大小
PHONE_ICON = 56dp
PHABLET_ICON = 64dp
TABLET_ICON = 72dp
LARGE_TABLET_ICON = 88dp
```

---

## 五、API 网关层

### 5.1 网关架构

```
                    ┌─────────────────┐
                    │   API Gateway    │
                    │   (FastAPI)      │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  REST API    │   │  WebSocket    │   │   SSE         │
│  Handler     │   │  Handler      │   │   Handler     │
└───────┬───────┘   └───────┬───────┘   └───────────────┘
        │                    │                    
        ▼                    ▼                    
┌───────────────────────────────────────────────────────┐
│                   业务逻辑层 (Business)                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
│  │ Chat    │  │ Memory  │  │ Skills  │  │  P2P    │  │
│  │ Service │  │ Service │  │ Service │  │ Service │  │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │
└───────────────────────────────────────────────────────┘
        │                    │                    
        ▼                    ▼                    
┌───────────────────────────────────────────────────────┐
│                   核心模块 (Core)                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
│  │ Agent   │  │ Cognee  │  │ Disco   │  │ Nano    │  │
│  │         │  │ Memory  │  │ RAG     │  │ vLLM    │  │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │
└───────────────────────────────────────────────────────┘
```

### 5.2 认证与授权

```python
# JWT Token 认证
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 权限级别
class PermissionLevel(Enum):
    GUEST = 0        # 只读
    USER = 1         # 基本操作
    PREMIUM = 2      # 高级功能
    ADMIN = 3        # 管理功能
```

### 5.3 限流策略

```python
# 速率限制
RATE_LIMITS = {
    "default": "100/minute",
    "chat": "60/minute",
    "upload": "10/minute",
    "search": "30/minute",
}

# 配额管理
QUOTAS = {
    "free": {"tokens": 1000, "storage": "100MB"},
    "premium": {"tokens": 10000, "storage": "1GB"},
    "enterprise": {"tokens": -1, "storage": "unlimited"},
}
```

---

## 六、跨平台功能映射

### 6.1 功能矩阵

| 功能模块 | 桌面端 | Web端 | 移动端 | 技术实现 |
|----------|--------|--------|--------|----------|
| **聊天对话** | ✅ | ✅ | ✅ | WebSocket + REST |
| **技能市场** | ✅ | ✅ | ✅ | REST API |
| **MCP 管理** | ✅ | ✅ | ❌ | SSH Tunnel |
| **LAN 聊天** | ✅ | ❌ | ✅ | P2P WebRTC |
| **数字分身** | ✅ | ❌ | ✅ | PyQt/QML |
| **智能部署** | ✅ | ✅ | ❌ | SSH + Web Terminal |
| **知识库** | ✅ | ✅ | ✅ | PWA + IndexedDB |
| **积分系统** | ✅ | ✅ | ✅ | 全端共享 API |
| **游戏中心** | ✅ | ❌ | ❌ | WebGL Canvas |
| **设置面板** | ✅ | ✅ | ✅ | 配置同步 |

### 6.2 离线能力

| 功能 | 离线支持 | 实现方式 |
|------|----------|----------|
| **聊天历史** | ✅ | IndexedDB/SQLite |
| **技能执行** | ⚠️ | 依赖网络 |
| **知识检索** | ✅ | 本地向量索引 |
| **文件访问** | ✅ | File System Access API |
| **消息推送** | ❌ | 需网络 |

---

## 七、代码复用策略

### 7.1 共享模块

```
hermes-desktop/
├── packages/                 # 公共包
│   ├── shared/              # 共享代码
│   │   ├── models/          # 数据模型
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── utils/          # 工具函数
│   │   └── constants/       # 常量定义
│   └── living_tree_naming/  # 命名系统
├── core/                    # 核心业务 (共享)
│   ├── agent.py
│   ├── memory/
│   ├── rag/
│   └── p2p/
└── relay_server/           # 中继服务
```

### 7.2 核心模块复用

```python
# 统一入口设计
class UnifiedInterface:
    """三端统一接口"""

    def chat(self, message: str) -> str:
        """聊天 - 三端一致"""
        pass

    def search_memory(self, query: str) -> List[Memory]:
        """记忆搜索 - 三端一致"""
        pass

    def execute_skill(self, skill_id: str, params: dict) -> Any:
        """技能执行 - 三端一致"""
        pass
```

---

## 八、实施计划

### Phase 1: Web API 层 (1周)
- [ ] 完善 FastAPI 网关
- [ ] 实现 REST API 端点
- [ ] 添加 WebSocket 支持
- [ ] 实现 PWA 资源

### Phase 2: Web 前端 (2周)
- [ ] React/Vue 框架搭建
- [ ] 核心组件开发
- [ ] 页面开发
- [ ] 状态管理

### Phase 3: 移动端适配 (2周)
- [ ] Kivy 自适应布局完善
- [ ] 移动端组件开发
- [ ] 离线支持
- [ ] 手势导航

### Phase 4: 跨平台测试 (1周)
- [ ] 桌面端回归测试
- [ ] Web 端兼容性测试
- [ ] 移动端适配测试
- [ ] 性能优化

---

## 九、技术选型总结

| 层级 | 技术栈 | 说明 |
|------|--------|------|
| **桌面端** | PyQt6 | 功能完整，性能优秀 |
| **Web 前端** | React + TypeScript | 生态丰富，开发效率高 |
| **移动端** | Kivy + Python | 代码复用，跨平台 |
| **后端** | FastAPI + Python | 高性能，易扩展 |
| **数据库** | SQLite + Chroma | 轻量 + 向量检索 |
| **实时通信** | WebSocket + SSE | 双通道保障 |
| **离线存储** | IndexedDB | Web 端持久化 |

---

## 十、总结

通过分层架构设计，实现：

1. **代码最大化复用**: 核心业务逻辑共享，三端一致性
2. **体验一致性**: 统一设计语言，差异化适配
3. **离线优先**: 本地优先，减少网络依赖
4. **渐进增强**: 根据设备能力提供最佳体验

**核心原则**: "桌面优先，移动适配，Web 扩展"
