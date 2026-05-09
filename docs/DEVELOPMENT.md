# 生命之树 · LivingTree 开发手册

> v3.1 | 2026-05

---

## 一、环境要求

- Python 3.13+
- Git
- (可选) NVIDIA GPU + CUDA 用于本地模型推理

```bash
pip install -r requirements.txt
```

---

## 二、项目结构 (v3.0)

```
livingtree/
├── api/                    # Web服务层
│   ├── server.py           #   FastAPI应用工厂
│   ├── routes.py           #   核心路由 (chat/health/tools/ws...)
│   ├── htmx_web.py         #   HTMX超媒体路由 (Jinja2模板)
│   ├── auth.py             #   认证 (JWT · 企业微信)
│   ├── code_api.py         #   代码项目管理 (Git集成)
│   ├── audit.py            #   审计追踪 (Merkle链)
│   └── workspace.py        #   多人协作工作空间
│
├── knowledge/              # 知识层 — 10模块
│   ├── hypergraph_store.py #   N元超图存储 · 优先约束
│   ├── precedence_model.py #   转移概率学习 · Beam Search
│   ├── order_aware_reranker.py # 顺序感知RRF重排
│   ├── gravity_model.py    #   知识引力场
│   ├── lazy_index.py       #   文档章节字节偏移索引
│   ├── graph_introspector.py#  图可视化 · 影响分析
│   ├── om_weather.py       #   Open-Meteo天气客户端
│   ├── agentic_rag.py      #   短路径优先 · 熔断器
│   ├── knowledge_base.py   #   RRF融合 + 知识图谱
│   └── multidoc_fusion.py  #   跨文档时序推理
│
├── execution/              # 推理与规划 — 6模块
│   ├── gtsm_planner.py     #   GTSM统一规划器 (树/流/混合)
│   ├── unified_pipeline.py #   StarVLA乐高式流水线
│   ├── cofee_engine.py     #   CoFEE四约束认知推理
│   ├── treeflow_planner.py #   树骨架→流精化加速
│   ├── plan_validator.py   #   计划验证 (增强)
│   └── dag_executor.py     #   DAG并行执行
│
├── dna/                    # DNA/意识 — 9模块
│   ├── phenomenal_consciousness.py # 现象意识6层
│   ├── godelian_self.py    #   哥德尔自指 · 数学不可还原
│   ├── xiaoshu.py          #   小树自主生长 · 内在驱动力
│   ├── organism.py         #   12器官完整生命体
│   ├── inquiry_engine.py   #   Doctor-R1多轮问询
│   ├── research_team.py    #   4角色免费模型研究员
│   ├── emergence_detector.py # Anderson涌现检测
│   ├── predictability_engine.py # 可预测性分析
│   ├── safety.py           #   安全守卫 (增强)
│   └── life_engine.py      #   7阶段生命管道
│
├── economy/                # 经济学与优化 — 5模块
│   ├── spatial_reward.py   #   S-GRPO空间感知奖励
│   ├── tdm_reward.py       #   TDM-R1不可微奖励RL
│   ├── thermo_budget.py    #   热力学预算控制
│   ├── latent_grpo.py      #   潜在空间GRPO + 反馈对齐
│   └── economic_engine.py  #   经济引擎 (三元优化)
│
├── core/                   # 自治与基础设施 — 7模块
│   ├── synaptic_plasticity.py # 沉默突触 · LTP/LTD
│   ├── system_health.py    #   8子系统统一监控
│   ├── action_principle.py #   最小作用量变分原理
│   ├── autonomic_loop.py   #   5阶段闭合自校正
│   ├── launch.py           #   一键启动 (12阶段)
│   ├── resource_tree.py    #   统一虚拟资源树
│   └── event_bus.py        #   事件总线
│
├── treellm/                # LLM路由 — 5新增模块
│   ├── bandit_router.py    #   Thompson采样贝叶斯路由
│   ├── score_matching_router.py # 扩散化路由
│   ├── free_pool_manager.py #  10+免费模型池
│   ├── parallel_drafter.py #   DFlash并行块起草
│   ├── mtp_drafter.py      #   Gemma4 MTP多token预测
│   ├── holistic_election.py #  5维评分选举 (增强)
│   ├── core.py             #   TreeLLM主类
│   └── providers.py        #   50+Provider (SenseTime新增)
│
├── cell/                   # 细胞繁殖
│   └── dsmtree_distiller.py #  dsmTree知识蒸馏
│
├── templates/              # HTMX前端模板
│   ├── base.html           #   基础布局 + SSE心跳
│   ├── index.html          #   仪表盘主页
│   ├── chat.html           #   对话界面
│   ├── dashboard.html      #   系统监控
│   └── knowledge.html      #   知识图谱
│
├── config/                 # 配置
│   └── settings.py         #   Pydantic配置 (热加载)
│
└── infrastructure/         # 基础设施
    └── event_bus.py        #   事件总线 (pub/sub)
```

---

## 三、核心概念

### 1. 超图知识存储 (HypergraphStore)

不同于传统三元组 (s,p,o)，超边连接任意数量的实体:

```python
hg = HypergraphStore()
hg.add_hyperedge(Hyperedge(
    entities=["GB3095-2012", "SO2", "24h_avg", "150μg/m³", "Class_II"],
    relation="emission_limit",
    precedence_before=["monitoring_plan"],
    precedence_after=["standard_selection"],
))
# 5个实体的单条超边 → 高阶关系表达
```

### 2. 沉默突触 (Synaptic Plasticity)

每个知识连接都有生物突触类似的状态:

```
SILENT (30%) ──(激活)──→ ACTIVE ──(巩固)──→ MATURE (保护)
    ↑                       │
    └── PRUNED ←──(衰减)────┘
```

```python
sp = get_plasticity()
sp.strengthen("provider:sensetime")   # LTP — 成功使用
sp.weaken("provider:bad_model")       # LTD — 失败
sp.degradation_alert()                # 检测知识退化
```

### 3. 最小作用量原理 (Action Principle)

所有模块行为从单一变分原理推导:

```
δS = δ∫ (T - V) dt = 0

T (动能) = 适应代价
V (势能) = 偏离代价

Euler-Lagrange → 最优超参数自动确定
```

### 4. 统一流水线 (Pipeline Orchestrator)

4种执行模式共享一个接口:

```python
orch = get_pipeline_orchestrator()
result = await orch.run(task, context, mode="auto")
# auto → 自动选择: DAG / ReAct / BehaviorTree / GTSM
```

---

## 四、开发指南

### 添加新 Provider

需修改 5 个文件:

1. `treellm/providers.py` — 添加工厂函数
2. `config/settings.py` — 添加API key字段 + 环境变量映射
3. `treellm/holistic_election.py` — 添加能力画像
4. `treellm/free_pool_manager.py` — 添加到免费池 (如有)
5. `economy/economic_engine.py` — 添加定价

参考 `create_sensetime_provider()` 的实现。

### 添加新器官系统

1. 在 `dna/organism.py` 中创建器官类 (继承生物隐喻)
2. 实现 `report()` 方法返回 `OrganReport`
3. 在 `LivingOrganism.__init__` 中注册
4. 在 `launch.py` 的 `_init_organism()` 中初始化

### 运行测试

```bash
python -m pytest tests/ -q                     # 全部 424 测试
python -m pytest tests/ -q -k "economy"        # 按模块筛选
python -m pytest tests/ -q --cov=livingtree    # 覆盖率
```

### 启动开发服务器

```bash
python -m livingtree                           # 完整服务 (8100端口)
# HTMX前端: http://localhost:8100/tree/
# API文档:  http://localhost:8100/docs
```

---

## 五、关键设计模式

### 单例模式

所有核心模块通过 `get_*()` 函数获取全局单例:

```python
from livingtree.core.synaptic_plasticity import get_plasticity
sp = get_plasticity()  # 全局唯一
```

### 依赖注入

模块间通过 `modules` 字典传递引用，避免循环导入:

```python
modules = {"hypergraph_store": hg, "free_pool": pool}
engine = PredictabilityEngine()
engine.feed_life_engine_metrics(life_engine)
```

### 观察者模式

事件总线支持发布/订阅:

```python
from livingtree.infrastructure.event_bus import get_event_bus
bus = get_event_bus()
bus.subscribe("memory_created", handler)
bus.publish("memory_created", {"key": "value"})
```

---

## 六、配置管理

### 热加载

```python
from livingtree.config.settings import get_config_watcher
watcher = get_config_watcher()
await watcher.start()  # 自动监控config/目录变化
```

### 环境变量

```bash
export LT_SENSETIME_API_KEY="sk-xxx"
export LT_DEEPSEEK_API_KEY="sk-xxx"
```

---

## 七、性能基准

| 指标 | 值 |
|------|----|
| 测试数量 | 424 |
| 测试通过率 | 100% |
| 模块总数 | 40+ |
| 支持Provider | 50+ (含SenseTime) |
| 免费模型池 | 12种 |
| 后台守护进程 | 6个 |
| 自主生长周期 | 2-4分钟/次 |
| HTMX前端大小 | 14KB (零JS框架) |
