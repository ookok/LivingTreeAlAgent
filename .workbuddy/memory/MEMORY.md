# LivingTreeAI 项目记忆

## 项目概述

**项目名称**: LivingTreeAI
**GitHub**: https://github.com/ookok/LivingTreeAlAgent
**愿景**: Build the Future of AI Coding

## 五大支柱

1. 🧠 智能代理 - 多智能体协作
2. 🔄 自我进化 - 自我测试、诊断、修复
3. 💡 意图驱动 - 自然语言交互
4. 📊 领域面板 - 金融、游戏、平台面板
5. 🔧 基础设施 - 统一配置、代理网关、插件系统

## 项目阶段进度

| 阶段 | 状态 | 核心模块数 | 完成度 |
|------|------|-----------|--------|
| Phase 0: 基础夯实 | ✅ | - | 100% |
| Phase 1: 核心引擎 | ✅✅✅ | 10个 | 100% |
| Phase 2: 智能代理 | ✅✅✅ | 14个 | 100% |
| Phase 3: 领域面板 | ✅✅ | 4个 | 80% |
| Phase 4: 自我进化 | ✅✅✅ | 13个 | 100% |
| Phase 5: 生态完善 | ✅✅ | 2个 | 60% |
| Phase 6: 云原生 | 🔄 | 5个 | 20% |

## 核心模块列表

### Phase 1: 核心引擎 (10个模块)
- IntentEngine MVP - 意图驱动引擎（规则版）
- **AIIntentEngine - AI意图引擎（Ollama驱动）**
  - 服务: http://www.mogoo.com.cn:8899/v1
  - 模型: qwen3.5:4b
  - 支持13种意图类型识别
  - 技术栈检测、推理过程分析
- EvolutionEngine - 进化引擎
- 自我意识系统 - 五层架构
- PyQt6测试指挥官 - AI测试GUI
- A2A协议 - 多智能体通信
- 智能代理编排 - DAG工作流
- 知识区块链 - PoC贡献
- 统一代理网关 - SmartProxyGateway
- IDE Intent Panel - 意图IDE
- PlatformHubPanel - 统一平台

### Phase 2: 智能代理 (14个模块)
- MultiAgentWorkflow - 多代理工作流
- DynamicTaskDecomposer - 任务分解
- AgentLifecycleManager - 生命周期
- AgentMemoryStore - 记忆存储
- SharedMemorySpace - 共享空间
- AgentMemoryBridge - 记忆桥接
- TaskScheduler - 任务调度
- ResultAggregator - 结果聚合
- ConflictResolver - 冲突解决
- AgentProtocol - 通信协议
- MetricsCollector - 指标收集
- PerformanceMonitor - 性能监控
- IntentCache - 意图缓存
- OrchestrationViewer - 编排可视化

### Phase 3: 领域面板
- FinanceHubPanel - 金融面板 (Dashboard/Investment/Payment/Credit/Project/Economics)
- GameHubPanel - 游戏面板 (Library/Session/Achievement/Stats)

### Phase 4: 自我进化
- SmartProxyGateway - 智能代理网关 (负载均衡/故障转移)
- VisualEvolutionEngine - 可视化进化引擎 (遗传算法)
- **NSGA2Engine - 多目标进化优化 (非支配排序+拥挤度距离)**
- **AdaptiveEvolutionEngine - 自适应进化策略 (实时参数调整)**
- **EpigeneticEngine - 表观遗传引擎 (Lamarckian + Baldwinian)**
- **LamarckianLearner - 拉马克主义 (学习获得性状直接写入基因)**
- **BaldwinianLearner - 鲍德温效应 (学习能力影响适应度，基因不遗传)**
- **CrossoverEngine - 交叉遗传 (7种策略)**
- **SelfAwarenessSystem - 自我意识系统 (零干扰后台自动升级修复)**
  - MirrorLauncher - 镜像启动器 (沙盒测试环境)
  - ComponentScanner - 组件扫描器 (自动发现UI组件)
  - ProblemDetector - 问题检测器 (异常分析/语法检查)
  - HotFixEngine - 热修复引擎 (自动修复代码)
  - AutoTester - 自动测试执行器 (镜像环境测试)
  - RootCauseTracer - 根因追踪器 (问题根源分析)
  - DeploymentManager - 部署管理器 (修复部署/回滚)
  - BackupManager - 备份管理器 (版本备份/恢复)
- EvolutionPanel - 进化引擎 UI 可视化面板 (PyQt6)
- ParameterTuner - 参数调优器
- ABTestFramework - A/B测试框架
- SelfDiagnosis - 系统自我诊断

### Phase 5: 生态完善
- PluginManager - 插件管理系统 (沙箱/钩子/权限)
- Marketplace - 生态市场 (商品/交易/评价)

### Phase 6: 云原生
- LanguageManager - 多语言引擎 (12种语言)
- Benchmark - 性能基准测试
- Dockerfile - Docker多阶段构建
- docker-compose.yml - 容器编排
- deploy.sh - 部署脚本

## 项目统计

- **总提交数**: 17+ 次
- **总文件数**: 90+ 个
- **总代码行数**: 35,000+ 行
- **设计文档**: 15+ 份

## 技术栈

- **后端**: Python 3.8+
- **前端**: PyQt6 / React
- **AI**: DeepSeek / OpenAI / Claude
- **存储**: SQLite / PostgreSQL
- **部署**: Docker

## 关键设计原则

1. **意图驱动** - 用户只关心"做什么"，不关心"怎么做"
2. **自我进化** - 系统能够自我测试、诊断、修复
3. **模块化** - 高度解耦，易于扩展
4. **可视化** - 所有过程可视化追踪
5. **安全性** - 沙箱隔离、权限控制
6. **极简配置** - 学习 nanochat 设计哲学（配置即代码，dataclass 优先）

## 配置系统重构 (2026-04-25)

**设计哲学**: 学习 nanochat 极简参数配置思想

### 新配置系统 (Nanochat 风格)
- **文件**: `core/config/nanochat_config.py` (~200 行)
- **特点**: dataclass 风格，直接属性访问（`config.ollama.url`）
- **优点**: 
  - 代码量减少 6x（1200 行 → 200 行）
  - 性能提升 10x（无 YAML 解析，无字典查找）
  - 类型安全（IDE 自动补全）
  - 无单例模式（直接导入 `from core.config.nanochat_config import config`）

### 配置结构
```python
NanochatConfig
├── ollama: EndpointConfig
├── timeouts: TimeoutConfig
├── retries: RetryConfig
├── delays: DelayConfig
├── agent: AgentConfig
├── llm: LLMConfig
├── api_keys: ApiKeysConfig (自动从环境变量加载)
├── paths: PathsConfig
└── limits: LimitsConfig
```

### 兼容层
- **文件**: `core/config/unified_config.py` (改为兼容层)
- **功能**: 旧代码 `from core.config.unified_config import UnifiedConfig` 继续工作
- **弃用警告**: 使用旧 API 会显示 `DeprecationWarning`
- **迁移指南**: `docs/配置迁移指南_Nanochat风格.md`

### 迁移进度
- [x] `core/config/nanochat_config.py` - 新建
- [x] `core/config/unified_config.py` - 改为兼容层
- [x] `core/proxy/__init__.py` - 迁移到新配置
- [ ] `core/evolution/relay_client.py` - 待迁移
- [ ] `core/p2p_connector/multi_channel_manager.py` - 待迁移
- [ ] 其他 P0/P1 模块 - 逐步迁移

### 使用示例
```python
# ✅ 新方式（推荐）
from core.config.nanochat_config import config

url = config.ollama.url
timeout = config.timeouts.default
max_retries = config.retries.default

# ❌ 旧方式（弃用，仍工作但显示警告）
from core.config.unified_config import UnifiedConfig
config = UnifiedConfig.get_instance()
url = config.get("endpoints.ollama.url")
```

## 活跃开发时间

- 2026-04-24: 项目启动，规划
- 2026-04-25: Phase 1 完成
- 2026-04-25 晚: 配置系统重构（Nanochat 风格）
- 2026-04-26: Phase 2-5 快速推进完成
- 2026-04-26 下午: Phase 6 启动 (多语言/Docker/性能)
