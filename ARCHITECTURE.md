# LivingTreeAI 架构文档

> 版本：v2.1 | 更新时间：2026-04-28 | 架构师：LivingTreeAI Team

---

## 📚 核心文档索引

| 文档 | 用途 | 路径 |
|------|------|------|
| **LIVINGTREE_ARCHITECTURE_GUIDE.md** | 完整架构指南 | `docs/LIVINGTREE_ARCHITECTURE_GUIDE.md` |
| **LIVINGTREE_DEVELOPMENT_GUIDE.md** | 功能开发指南 | `docs/LIVINGTREE_DEVELOPMENT_GUIDE.md` |
| **AGENTS.md** | AI开发规范 | `AGENTS.md` |

### 快速导航

- **架构设计** → `docs/LIVINGTREE_ARCHITECTURE_GUIDE.md`
- **功能开发** → `docs/LIVINGTREE_DEVELOPMENT_GUIDE.md`
- **技术细节** → 本文档 (`ARCHITECTURE.md`)

---

## 📋 目录

1. [架构概览](#架构概览)
2. [技术栈](#技术栈)
3. [项目结构](#项目结构)
4. [核心模块](#核心模块)
5. [数据流](#数据流)
6. [设计模式](#设计模式)
7. [配置系统](#配置系统)
8. [部署架构](#部署架构)
9. [性能优化](#性能优化)
10. [安全设计](#安全设计)

---

## 架构概览

### 核心理念

LivingTreeAI 采用 **"生命之树"** 架构理念：

```
        用户意图
           │
           ▼
    ┌─────────────┐
    │  意图驱动层  │ ← 理解用户想做什么
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  智能代理层  │ ← 多Agent协作执行
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  自我进化层  │ ← 测试、诊断、修复
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  基础设施层  │ ← 配置、网络、存储
    └─────────────┘
```

### 架构特点

| 特点 | 说明 | 优势 |
|------|------|------|
| 🌱 **自我生长** | 从经验中学习，持续优化 | 系统越用越智能 |
| 🔄 **自我修复** | 自动检测并修复问题 | 减少人工维护成本 |
| 💡 **意图驱动** | 听懂用户意图，而非指令 | 降低使用门槛 |
| 🤝 **协作进化** | 多智能体协同工作 | 复杂任务分解执行 |
| 📊 **可视化** | 所有过程可视化追踪 | 易于调试和理解 |

---

## 技术栈

### 后端技术

| 技术 | 版本 | 用途 |
|------|------|------|
| **Python** | 3.11+ | 主力开发语言 |
| **PyQt6** | 6.0+ | 桌面 GUI 框架 |
| **FastAPI** | 0.104+ | 服务器 API 框架 |
| **SQLite** | 3.35+ | 本地数据库 |
| **PostgreSQL** | 14+ | 服务器数据库（可选） |

### AI/ML 技术

| 技术 | 版本 | 用途 |
|------|------|------|
| **Ollama** | 0.1.0+ | 本地 LLM 运行框架 |
| **Qwen** | 3.5:4b | 默认推理模型 |
| **LangChain** | 0.0.340+ | Agent 开发框架 |
| **ChromaDB** | 0.4.0+ | 向量数据库 |

### 前端技术

| 技术 | 版本 | 用途 |
|------|------|------|
| **PyQt6** | 6.0+ | UI 组件库 |
| **QSS** | - | 样式表（类似 CSS） |
| **Matplotlib** | 3.8+ | 图表绘制 |

---

## 项目结构

### 完整目录树

```
LivingTreeAlAgent/
├── client/                          # 客户端（可编辑安装）
│   └── src/
│       ├── main.py                  # PyQt6 入口 → HomePage
│       ├── business/                # 业务逻辑层（340+ 文件）
│       │   ├── config.py           # UnifiedConfig 兼容层
│       │   ├── nanochat_config.py  # NanochatConfig（推荐）
│       │   ├── optimal_config.py   # OptimalConfig
│       │   ├── intent_engine/      # 意图驱动引擎
│       │   ├── evolution_engine/   # 进化引擎（71 文件）
│       │   ├── hermes_agent/       # Hermes Agent 框架
│       │   ├── amphiloop/          # 双向调度系统
│       │   ├── optimization/       # PRISM 优化
│       │   ├── enterprise/         # P2P 存储 & 任务调度
│       │   ├── digital_twin/      # 数字孪生
│       │   ├── credit_economy/     # 积分系统
│       │   ├── decommerce/         # 电子商务（22 文件）
│       │   ├── living_tree_ai/     # 语音、浏览器、会议（300 文件）
│       │   ├── fusion_rag/         # 多源检索
│       │   ├── knowledge_graph/    # 知识图谱
│       │   ├── plugin_framework/   # 插件框架
│       │   ├── p2p_*/             # P2P 网络（多个模块）
│       │   ├── personal_mode/     # 个人模式
│       │   ├── ecc_*/              # Agent 本能/技能（多个模块）
│       │   ├── evolving_community/ # 进化社区
│       │   ├── intelligent_hints/  # 智能提示
│       │   ├── office_automation/  # 办公自动化
│       │   └── ...                # 其他 300+ 模块
│       ├── infrastructure/          # 基础设施层
│       │   ├── database/           # 数据库迁移（v1-v14）
│       │   ├── config/             # 配置管理
│       │   ├── network/            # 网络通信
│       │   ├── model/              # 模型管理
│       │   └── storage/            # 存储管理
│       ├── presentation/           # 表现层（200+ 文件）
│       │   ├── panels/             # 所有面板（102+ 文件）
│       │   │   ├── finance_hub_panel.py
│       │   │   ├── game_hub_panel.py
│       │   │   └── ...
│       │   ├── components/         # 可复用组件
│       │   ├── widgets/            # 自定义控件
│       │   ├── dialogs/            # 对话框
│       │   ├── modules/            # 子模块
│       │   ├── layouts/            # 布局管理
│       │   ├── resources/          # 资源文件
│       │   ├── router/             # 路由管理
│       │   └── theme/              # 主题管理
│       └── shared/                 # 共享工具
│           ├── utils/              # 工具函数
│           ├── constants/          # 常量定义
│           └── types/              # 类型定义
├── server/                         # 服务器层
│   ├── relay_server/               # FastAPI Relay（46 文件）
│   │   ├── api/                   # API 路由（9 文件）
│   │   ├── cluster/               # 集群管理
│   │   ├── database/              # 数据库操作
│   │   ├── middleware/            # 中间件
│   │   ├── services/              # 业务服务（11 文件）
│   │   ├── web/                   # Web 界面
│   │   ├── main.py                # 服务器入口
│   │   └── ...
│   ├── tracker_server.py           # P2P Tracker
│   ├── shared/                    # 共享模块
│   └── web/                       # Web 前端
├── app/                            # 独立企业应用（23 文件）
├── mobile/                         # PWA/移动端（7 文件）
│   ├── main.py
│   ├── screens/
│   ├── adaptive_layout/
│   └── pwa_integration/
├── packages/                       # 共享库
│   ├── living_tree_naming/         # 命名规范
│   └── shared/                    # 共享代码
├── config/                         # 配置文件
├── tests/                          # 测试文件（30+ 文件）
│   ├── test_provider.py            # 唯一有效测试
│   └── test_*.py                  # 其他测试（部分过期）
├── assets/                         # 静态资源
├── main.py                         # CLI 入口
├── run.bat                         # Windows 快速启动
├── pyproject.toml                  # 项目配置
├── pytest.ini                      # 测试配置
├── README.md                       # 项目说明
├── AGENTS.md                       # AI 指引文档
├── ARCHITECTURE.md                # 架构文档（本文件）
├── TODO.md                         # 待办任务清单
└── .workbuddy/                     # WorkBuddy 配置
    └── memory/                     # 工作记忆
```

---

## 核心模块

### 1. 意图驱动引擎（IntentEngine）

**路径**：`client/src/business/intent_engine/`

**功能**：
- 自然语言理解
- 意图分类
- 实体提取
- 上下文管理

**核心类**：
```python
class IntentEngine:
    def parse(self, text: str) -> Intent
    def execute(self, intent: Intent) -> Result
    def learn(self, feedback: Feedback) -> None
```

**使用示例**：
```python
from client.src.business.intent_engine import IntentEngine

engine = IntentEngine()
intent = engine.parse("帮我写一个用户登录接口，要用 FastAPI")
result = engine.execute(intent)
```

---

### 2. 进化引擎（EvolutionEngine）

**路径**：`client/src/business/evolution_engine/` (71 文件)

**功能**：
- 遗传算法优化
- NSGA-II 多目标优化
- 自适应进化策略
- 表观遗传（Lamarckian + Baldwinian）

**核心类**：
```python
class EvolutionEngine:
    def evolve(self, population: List[Individual]) -> List[Individual]
    def evaluate(self, individual: Individual) -> Fitness
    def mutate(self, individual: Individual) -> Individual
    def crossover(self, parent1: Individual, parent2: Individual) -> Individual
```

**子模块**：
- `NSGA2Engine` - 多目标优化
- `AdaptiveEvolutionEngine` - 自适应策略
- `EpigeneticEngine` - 表观遗传
- `CrossoverEngine` - 交叉遗传（7种策略）

---

### 3. 智能代理框架（HermesAgent）

**路径**：`client/src/business/hermes_agent/`

**功能**：
- 多智能体协作
- 任务分解与调度
- 知识共享
- 通信协议（A2A）

**核心类**：
```python
class HermesAgent:
    def assign_task(self, task: Task) -> None
    def collaborate(self, other_agent: HermesAgent) -> None
    def share_knowledge(self, knowledge: Knowledge) -> None
```

**子模块**：
- `agent_skills/` - Agent 技能管理（17 文件）
- `a2a_protocol/` - Agent-to-Agent 协议（10 文件）
- `task_decomposer/` - 任务分解器
- `agent_memory/` - Agent 记忆管理

---

### 4. 自我进化系统（SelfEvolution）

**路径**：`client/src/business/self_evolution.py` + `evolution_engine/`

**功能**：
- 零干扰后台自动升级
- 自我测试与诊断
- 热修复引擎
- 根因追踪

**核心组件**：
- `MirrorLauncher` - 镜像启动器（沙盒测试环境）
- `ComponentScanner` - 组件扫描器
- `ProblemDetector` - 问题检测器
- `HotFixEngine` - 热修复引擎
- `AutoTester` - 自动测试执行器
- `RootCauseTracer` - 根因追踪器
- `DeploymentManager` - 部署管理器
- `BackupManager` - 备份管理器

---

### 5. 融合RAG（FusionRAG）

**路径**：`client/src/business/fusion_rag/`

**功能**：
- 多源数据检索
- 向量检索
- 图谱检索
- 混合检索

**核心类**：
```python
class FusionRAG:
    def retrieve(self, query: str) -> List[Document]
    def index(self, documents: List[Document]) -> None
    def rerank(self, results: List[Document]) -> List[Document]
```

**三层架构**：
- L1: 向量检索（Dense Retrieval）
- L2: 图谱检索（Graph Retrieval）
- L3: 混合检索（Hybrid Retrieval）

---

### 6. 领域面板（Domain Panels）

**路径**：`client/src/presentation/panels/`

**已完成的面板**：
- `FinanceHubPanel` - 金融面板
  - Dashboard - 仪表板
  - Investment - 投资分析
  - Payment - 支付集成
  - Credit - 信用评估
  - Project - 项目管理
  - Economics - 经济指标

- `GameHubPanel` - 游戏面板
  - Library - 游戏库
  - Session - 游戏会话
  - Achievement - 成就系统
  - Stats - 统计数据

**规划中的面板**：
- `HealthHubPanel` - 健康面板
- `EducationHubPanel` - 教育面板
- `EnterpriseHubPanel` - 企业面板

---

### 7. P2P 网络（P2P Networking）

**路径**：`client/src/business/p2p_*/`

**功能**：
- 分布式存储
- 节点发现
- 数据同步
- 去中心化知识库

**核心模块**：
- `p2p_network/` - P2P 网络核心
- `p2p_storage/` - P2P 存储
- `p2p_sync/` - 数据同步
- `p2p_discovery/` - 节点发现

---

### 8. 数字孪生（Digital Twin）

**路径**：`client/src/business/digital_twin/`

**功能**：
- 数字化身
- 行为模拟
- 虚拟会议
- 虚拟云引擎

**核心类**：
```python
class DigitalTwin:
    def simulate(self, behavior: Behavior) -> Result
    def interact(self, user: User) -> Response
    def update(self, feedback: Feedback) -> None
```

---

## 数据流

### 用户请求处理流程

```
用户输入
    │
    ▼
┌─────────────────┐
│ IntentEngine    │ ← 意图识别
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ TaskDecomposer  │ ← 任务分解
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ AgentOrchestrator│ ← Agent 编排
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ HermesAgent     │ ← 任务执行
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ ResultAggregator│ ← 结果聚合
└─────────────────┘
    │
    ▼
用户输出
```

### 自我进化流程

```
系统运行
    │
    ▼
┌─────────────────┐
│ ProblemDetector │ ← 问题检测
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ RootCauseTracer │ ← 根因分析
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ HotFixEngine    │ ← 热修复
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ MirrorLauncher  │ ← 沙盒测试
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ AutoTester      │ ← 自动测试
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ DeploymentMgr   │ ← 部署/回滚
└─────────────────┘
    │
    ▼
系统更新
```

---

## 设计模式

### 1. 分层架构（Layered Architecture）

```
┌─────────────────────┐
│   Presentation Layer  │ ← PyQt6 UI
├─────────────────────┤
│   Business Layer     │ ← 业务逻辑
├─────────────────────┤
│   Infrastructure Lay │ ← 基础设施
├─────────────────────┤
│   Data Access Layer  │ ← 数据访问
└─────────────────────┘
```

### 2. 插件架构（Plugin Architecture）

```python
# 插件接口
class Plugin:
    def initialize(self) -> None
    def execute(self, context: Context) -> Result
    def shutdown(self) -> None

# 插件管理器
class PluginManager:
    def load_plugin(self, path: str) -> Plugin
    def unload_plugin(self, name: str) -> None
    def list_plugins(self) -> List[Plugin]
```

### 3. 观察者模式（Observer Pattern）

```python
# 事件总线
class EventBus:
    def subscribe(self, event: str, handler: Callable) -> None
    def unsubscribe(self, event: str, handler: Callable) -> None
    def publish(self, event: str, data: Any) -> None
```

### 4. 策略模式（Strategy Pattern）

```python
# 进化策略
class EvolutionStrategy(ABC):
    @abstractmethod
    def evolve(self, population: List[Individual]) -> List[Individual]

# 具体策略
class NSGA2Strategy(EvolutionStrategy):
    def evolve(self, population: List[Individual]) -> List[Individual]:
        # NSGA-II 算法
        pass

class AdaptiveStrategy(EvolutionStrategy):
    def evolve(self, population: List[Individual]) -> List[Individual]:
        # 自适应算法
        pass
```

---

## 配置系统

### NanochatConfig（推荐）

**路径**：`client/src/business/nanochat_config.py`

**特点**：
- Dataclass 风格
- 直接属性访问
- 类型安全
- 性能提升 10x

**使用示例**：
```python
from client.src.business.nanochat_config import config

# 直接属性访问
url = config.ollama.url
timeout = config.timeouts.default
max_retries = config.retries.default

# 配置结构
"""
NanochatConfig
├── ollama: EndpointConfig
├── timeouts: TimeoutConfig
├── retries: RetryConfig
├── delays: DelayConfig
├── agent: AgentConfig
├── llm: LLMConfig
├── api_keys: ApiKeysConfig
├── paths: PathsConfig
└── limits: LimitsConfig
"""
```

### UnifiedConfig（兼容层）

**路径**：`client/src/business/config.py`

**特点**：
- 字典风格访问
- 兼容旧代码
- 已弃用（显示警告）

**使用示例**：
```python
from client.src.business.config import UnifiedConfig

config = UnifiedConfig.get_instance()
url = config.get("endpoints.ollama.url")
```

**迁移指南**：
1. 查找所有 `from client.src.business.config import UnifiedConfig`
2. 替换为 `from client.src.business.nanochat_config import config`
3. 将 `config.get("endpoints.ollama.url")` 替换为 `config.ollama.url`
4. 测试确保功能正常

---

## 部署架构

### 桌面客户端部署

```
┌─────────────────────────────────────┐
│         用户桌面环境                  │
│  ┌─────────────────────────────┐   │
│  │    LivingTreeAI Client      │   │
│  │  ┌─────────────────────┐   │   │
│  │  │   PyQt6 GUI          │   │   │
│  │  ├─────────────────────┤   │   │
│  │  │   Business Logic    │   │   │
│  │  ├─────────────────────┤   │   │
│  │  │   Local DB (SQLite) │   │   │
│  │  └─────────────────────┘   │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │    Ollama (Local LLM)       │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

### 服务器部署

```
┌─────────────────────────────────────┐
│           Load Balancer             │
│         (Nginx/HAProxy)            │
└─────────────────┬───────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
┌───────▼────────┐  ┌───────▼────────┐
│ Relay Server 1 │  │ Relay Server 2 │
│  (FastAPI)     │  │  (FastAPI)     │
└───────┬────────┘  └───────┬────────┘
        │                   │
        └─────────┬─────────┘
                  │
        ┌─────────▼─────────┐
        │   PostgreSQL DB     │
        └────────────────────┘
```

### Docker 部署

```yaml
# docker-compose.yml
version: '3.8'
services:
  client:
    build: ./client
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data
  
  relay-server:
    build: ./server/relay_server
    ports:
      - "8000:8000"
    depends_on:
      - postgres
  
  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: livingtree
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## 性能优化

### 1. 配置系统优化

**问题**：UnifiedConfig 使用 YAML 解析 + 字典查找，性能差

**解决方案**：NanochatConfig 使用 dataclass，性能提升 10x

**对比**：
```
UnifiedConfig:
- 加载时间: ~100ms
- 访问时间: ~1ms/次
- 内存占用: ~10MB

NanochatConfig:
- 加载时间: ~10ms
- 访问时间: ~0.1ms/次
- 内存占用: ~1MB
```

### 2. 数据库优化

**索引优化**：
```sql
-- 用户表索引
CREATE INDEX idx_user_email ON users(email);
CREATE INDEX idx_user_created_at ON users(created_at);

-- 会话表索引
CREATE INDEX idx_session_user_id ON sessions(user_id);
CREATE INDEX idx_session_updated_at ON sessions(updated_at);
```

**查询优化**：
```python
# 差：N+1 查询
users = User.query.all()
for user in users:
    print(user.sessions.count())

# 好：JOIN 查询
users = User.query.options(joinedload(User.sessions)).all()
for user in users:
    print(len(user.sessions))
```

### 3. 缓存策略

**内存缓存**：
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_user_profile(user_id: int) -> dict:
    return db.query(User).filter_by(id=user_id).first()
```

**Redis 缓存**：
```python
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def get_cached(key: str, fetch_func: Callable) -> Any:
    value = redis_client.get(key)
    if value is None:
        value = fetch_func()
        redis_client.setex(key, 3600, value)
    return value
```

---

## 安全设计

### 1. 沙箱隔离

**目的**：防止恶意代码执行

**实现**：
```python
import subprocess
import resource

def run_in_sandbox(code: str) -> str:
    # 限制 CPU 时间
    resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
    
    # 限制内存
    resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
    
    # 限制文件大小
    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
    
    # 执行代码
    result = subprocess.run(['python', '-c', code], capture_output=True, timeout=5)
    return result.stdout.decode()
```

### 2. 权限控制

**RBAC（基于角色的访问控制）**：
```python
class Permission(Enum):
    READ = 'read'
    WRITE = 'write'
    EXECUTE = 'execute'
    ADMIN = 'admin'

class Role:
    def __init__(self, name: str, permissions: List[Permission]):
        self.name = name
        self.permissions = permissions

# 预定义角色
ROLES = {
    'user': Role('user', [Permission.READ, Permission.WRITE]),
    'admin': Role('admin', [Permission.READ, Permission.WRITE, Permission.EXECUTE, Permission.ADMIN]),
    'guest': Role('guest', [Permission.READ])
}
```

### 3. 数据加密

**传输加密（TLS）**：
```python
# FastAPI 配置 TLS
import uvicorn

if __name__ == '__main__':
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=8000,
        ssl_keyfile='/path/to/key.pem',
        ssl_certfile='/path/to/cert.pem'
    )
```

**存储加密（AES）**：
```python
from cryptography.fernet import Fernet

# 生成密钥
key = Fernet.generate_key()
cipher = Fernet(key)

# 加密
encrypted = cipher.encrypt(b'Sensitive data')

# 解密
decrypted = cipher.decrypt(encrypted)
```

---

## 附录

### A. 常见问题（FAQ）

**Q1: 为什么选择 PyQt6 而不是 Web 技术？**

A: PyQt6 提供更好的桌面集成、性能和离线能力。

**Q2: 为什么使用 Python 3.11+？**

A: Python 3.11 引入了更好的错误处理和性能优化。

**Q3: 如何贡献代码？**

A: 参考 `AGENTS.md` 了解项目规范，然后提交 PR。

### B. 参考资源

- [PyQt6 文档](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Ollama 文档](https://ollama.ai/docs)
- [LangChain 文档](https://python.langchain.com/docs)

### C. 更新日志

**v2.0 (2026-04-26)**
- ✅ 完成 `core/` → `client/src/business/` 迁移
- ✅ 完成 `ui/` → `client/src/presentation/` 迁移
- ✅ 引入 NanochatConfig 配置系统
- ✅ 重写 README 和架构文档

**v1.0 (2026-04-24)**
- ✅ 项目启动
- ✅ Phase 1-4 完成
- ✅ 基础功能实现

---

*最后更新：2026-04-26 | 如有问题，请提交 Issue*
