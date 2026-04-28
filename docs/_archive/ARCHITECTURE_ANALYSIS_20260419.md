# Hermes Desktop 架构分析与改造方案

**生成时间**: 2026-04-19
**版本**: V2.0

---

## 一、学习成果总结

### 1.1 参考开源项目分析

| 项目 | 核心特性 | 借鉴价值 |
|------|---------|---------|
| **claude-mem** | 三层搜索工作流、Chroma向量数据库、渐进式披露 | 记忆系统Token优化 |
| **Ralph** | 外部持久化记忆、PRD驱动循环、反馈质量门禁 | Agent闭环设计 |
| **cognee** | remember/recall/forget/improve API、知识图谱+向量混合 | 记忆增强机制 |
| **LinkMind** | 多模态API路由、生产级过滤器、模型故障转移 | 企业级中间件 |
| **Disco-RAG** | 块内话语树、块间修辞图、规划蓝图 | RAG结构化增强 |
| **Nano-vLLM** | 1200行轻量实现、前缀缓存、张量并行 | 本地推理优化 |
| **Vheer** | 免费图像视频生成、多模型集成 | 多模态内容生成 |

### 1.2 上游项目更新 (hermes-agent-windows v0.9.0)

**新增功能**:
- Web UI 管理面板（对话/状态/会话/分析/日志/定时任务/技能/配置/密钥）
- 零配置启动 + Windows 兼容性修复
- CLI 命令增强 (`hermes setup/web/gateway`)
- Gateway 网关服务

---

## 二、现有架构分析

### 2.1 核心模块

```
hermes-desktop/
├── core/           # 核心业务逻辑 (130+ 模块)
│   ├── agent.py           # Hermes Agent 核心
│   ├── fusion_rag/        # 四层混合检索
│   ├── intelligent_memory/# 智能记忆系统
│   ├── smart_deploy/      # 智能部署
│   └── ui_self_check/     # UI自检
├── ui/             # PyQt6 界面 (100+ 面板)
│   ├── main_window.py     # 主窗口
│   └── *_panel/           # 功能面板
└── models/         # GGUF 模型
```

### 2.2 当前记忆系统 vs 参考项目

| 维度 | 现有 intelligent_memory | claude-mem/cognee |
|------|------------------------|-------------------|
| **存储** | SQLite | SQLite + Chroma 向量 |
| **检索** | 关键词匹配 | 语义向量搜索 |
| **API** | 手动调用 | remember/recall 自动路由 |
| **会话隔离** | 无 | 多会话/租户隔离 |
| **遗忘机制** | 无 | forget API |
| **持续学习** | 基础 | improve 反馈优化 |

---

## 三、架构改进方案

### 3.1 记忆系统增强 (借鉴 claude-mem + cognee)

**新增模块**: `core/cognee_memory/`

```python
# 核心 API 设计
class CogneeMemoryAdapter:
    """适配 cognee 记忆增强机制"""

    async def remember(self, text: str, session_id: str = None):
        """存储到知识图谱 + 向量数据库"""

    async def recall(self, query: str, session_id: str = None):
        """自动路由查询，混合向量+图搜索"""

    async def forget(self, dataset: str):
        """删除数据"""

    async def improve(self, feedback: dict):
        """持续改进优化"""
```

**改进点**:
1. 集成 Chroma 向量数据库
2. 实现三层搜索工作流（search → timeline → get_observations）
3. 添加会话隔离机制
4. 实现 forget/improve API

### 3.2 Discourse-Aware RAG (借鉴 Disco-RAG)

**新增模块**: `core/disco_rag/`

```python
class DiscourseRAG:
    """话语感知的 RAG 系统"""

    def build_intra_chunk_tree(self, chunk: str):
        """构建块内话语树"""

    def build_inter_chunk_graph(self, chunks: List[str]):
        """构建块间修辞图"""

    def generate_planning_blueprint(self, query: str, chunks: List[str]):
        """生成规划蓝图"""
```

**改进点**:
1. 文档块内层级结构建模
2. 跨段落修辞关系图
3. 结构化生成引导
4. 替代扁平拼接的 RAG

### 3.3 外部持久化 Agent 循环 (借鉴 Ralph)

**新增模块**: `core/ralph_loop/`

```python
class RalphAgentLoop:
    """外部持久化的 Agent 闭环"""

    def run_until_complete(self, prd_path: str):
        """PRD 驱动循环，直到所有任务完成"""

    def create_checkpoint(self, branch: str):
        """创建 Git 分支检查点"""

    def quality_gate(self) -> bool:
        """质量门禁（测试+类型检查）"""

    def update_progress(self, story_id: str, passes: bool):
        """更新 PRD 进度"""
```

**改进点**:
1. 每次迭代外部存储（非内存）
2. PRD 驱动的小任务拆分
3. 质量反馈循环必须存在
4. Git 分支版本控制

### 3.4 Nano-vLLM 本地推理集成

**新增模块**: `core/nano_vllm/`

```python
from nanovllm import LLM, SamplingParams

class NanoVLLMClient:
    """Nano-vLLM 本地推理客户端"""

    def __init__(self, model_path: str):
        self.llm = LLM(model_path, enforce_eager=True)

    def generate(self, prompt: str, **kwargs):
        """生成响应（API 兼容 vLLM）"""
```

**改进点**:
1. 支持 1200 行轻量 vLLM
2. 前缀缓存优化
3. 张量并行支持
4. 替代 llama-cpp 作为本地推理

### 3.5 Vheer 多模态集成

**新增模块**: `core/vheer_client/`

```python
class VheerClient:
    """Vheer AI 平台集成"""

    async def text_to_image(self, prompt: str, model: str = "flux") -> str:
        """文生图"""

    async def image_to_video(self, image_path: str) -> str:
        """图生视频"""

    async def text_to_video(self, prompt: str) -> str:
        """文生视频"""
```

**改进点**:
1. 集成免费无限制的图像生成
2. 视频生成能力
3. 多种 AI 模型选择
4. 替代需要付费的图像生成服务

### 3.6 企业级模型路由 (借鉴 LinkMind)

**新增模块**: `core/model_router/`

```python
class ModelRouter:
    """企业级多模型路由"""

    def chat(self, prompt: str, model: str = "auto"):
        """自动选择最佳模型"""

    def route_best(self, query: str) -> str:
        """best() 路由：选择最优模型"""

    def route_pass(self, query: str) -> str:
        """pass() 路由：故障转移"""

    def add_filter(self, filter_type: str, config: dict):
        """添加过滤器（敏感词/停用词/优先级）"""
```

**改进点**:
1. 多模型自动路由
2. 故障转移机制
3. 生产级过滤器
4. Token 用量统计

---

## 四、跨平台适配方案

### 4.1 功能映射表

| 桌面端功能 | 移动端 | Web端 | 技术方案 |
|-----------|--------|-------|---------|
| 聊天对话 | ✅ | ✅ | React + WebSocket |
| 技能市场 | ✅ | ✅ | Vue + REST API |
| MCP 管理 | ❌ | ✅ | Web 管理界面 |
| LAN 聊天 | ✅ | ❌ | P2P WebRTC |
| 数字分身 | ✅ | ❌ | PyQt6 QML |
| 智能部署 | ❌ | ✅ | SSH Web Terminal |
| 知识库 | ✅ | ✅ | PWA + IndexedDB |
| 积分系统 | ✅ | ✅ | 全端共享 API |
| 游戏中心 | ✅ | ❌ | WebGL Canvas |
| 设置面板 | ✅ | ✅ | 配置同步 |

### 4.2 跨平台架构

```
┌─────────────────────────────────────────────────────┐
│                    Web UI (React/Vue)                │
├─────────────────────────────────────────────────────┤
│              API Gateway (FastAPI)                   │
│  ┌──────────┬──────────┬──────────┬──────────┐      │
│  │  Chat    │  Skills  │  Model   │  Assets  │      │
│  └──────────┴──────────┴──────────┴──────────┘      │
├─────────────────────────────────────────────────────┤
│           Hermes Desktop Core (Python)               │
│  ┌──────────┬──────────┬──────────┬──────────┐      │
│  │  Agent   │  Memory  │  RAG     │  P2P     │      │
│  └──────────┴──────────┴──────────┴──────────┘      │
└─────────────────────────────────────────────────────┘
```

### 4.3 Web 版本目录结构

```
hermes-web/
├── src/
│   ├── components/       # 通用组件
│   ├── pages/           # 页面
│   │   ├── chat/        # 聊天页面
│   │   ├── skills/      # 技能市场
│   │   └── settings/    # 设置页面
│   ├── stores/          # 状态管理
│   ├── services/        # API 服务
│   └── App.tsx
├── server/              # FastAPI 后端
│   ├── api/             # API 路由
│   ├── core/            # 核心逻辑（复用 desktop）
│   └── main.py
└── package.json
```

### 4.4 移动端方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Flutter** | 原生性能、热重载 | 需要重写 UI |
| **React Native** | JS 生态、部分复用 | 性能一般 |
| **PWA** | 零重写、快速上线 | 功能受限 |
| **Tauri Mobile** | Rust 性能、代码共享 | 新兴生态 |

**推荐**: PWA 先行，Flutter 长期

---

## 五、实施计划

### Phase 1: 记忆系统增强 (1-2 周)
- [ ] 集成 Chroma 向量数据库
- [ ] 实现 cognee API 适配器
- [ ] 添加三层搜索工作流
- [ ] 实现会话隔离机制

### Phase 2: RAG 增强 (2 周)
- [ ] 实现 Discourse-Aware RAG
- [ ] 块内话语树构建
- [ ] 块间修辞图生成
- [ ] 规划蓝图条件生成

### Phase 3: 本地推理优化 (1 周)
- [ ] 集成 Nano-vLLM
- [ ] 前缀缓存优化
- [ ] 多模型支持

### Phase 4: 多模态集成 (2 周)
- [ ] Vheer API 集成
- [ ] 文生图/图生视频
- [ ] UI 集成面板

### Phase 5: Agent 闭环 (2 周)
- [ ] Ralph 风格外部记忆
- [ ] PRD 驱动任务系统
- [ ] 质量门禁机制

### Phase 6: 跨平台 (持续)
- [ ] Web 版本开发
- [ ] PWA 适配
- [ ] 移动端评估

---

## 六、技术债务清理

### 6.1 代码重复
- `core/smart_deploy/` 和 `core/ui_self_check/` 存在重复的模拟执行逻辑
- 建议：合并到 `core/shared_sandbox/`

### 6.2 空方法填充
- 部分 panel 的空方法需要实现具体逻辑
- 建议：逐个填充功能

### 6.3 测试覆盖
- 缺少单元测试和集成测试
- 建议：引入 pytest + pytest-asyncio

---

## 七、总结

通过学习借鉴以下开源项目：
- **claude-mem**: 记忆系统 Token 优化
- **cognee**: 记忆增强 API
- **Ralph**: Agent 闭环设计
- **LinkMind**: 企业级路由
- **Disco-RAG**: RAG 结构化
- **Nano-vLLM**: 轻量推理
- **Vheer**: 多模态生成

可以显著提升 Hermes Desktop 的：
1. **记忆能力**: 从简单存储到语义检索
2. **RAG 质量**: 从扁平到结构化
3. **推理性能**: 轻量级本地引擎
4. **多模态**: 免费图像视频生成
5. **Agent 闭环**: 外部持久化质量门禁

建议按 Phase 分步实施，优先完成记忆系统增强和 RAG 改进。
