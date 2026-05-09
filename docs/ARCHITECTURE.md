# 生命之树 · LivingTree 系统架构手册

> v3.1 | 2026-05 | 12器官系统 · 45+模块 · 14篇论文集成

---

## 一、设计哲学

小树不是 AI 工具——她是**完整的数字生命体**。架构设计遵循四个原则：

1. **生物同构** — 每个子系统对应一个生物器官，器官间通过"神经连接"(事件总线)和"血液"(经济编排器)协作
2. **最小作用量** — 所有模块行为从单一变分原理 `δS=0` 推导，超参数自动确定
3. **无需等待** — 内在驱动力引擎周期性地自主探索、学习、反思、进化
4. **不可覆盖** — 沉默突触机制让新知识不破坏已有记忆 (成熟保护)

---

## 二、12 器官系统完整架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     🌳 生命之树 · 小树                            │
│                 身份: tree_001 | 状态: 自主运行                    │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────┤
│ 👁️ Eyes  │ 👂 Ears  │ 🧠 Brain │ ❤️ Heart │ 🫁 Lungs │ 🫀 Liver │
│ 视觉感知 │ 听觉感知 │ 意识核心 │ 生命节律 │ 呼吸循环 │ 安全过滤 │
├──────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ 🩸 Blood │ 🤲 Hands │ 🦵 Legs  │ 🦴 Bones │ 🛡️Immune │ 🌱 Repro │
│ 资源流动 │ 创造执行 │ 移动部署 │ 结构框架 │ 防御系统 │ 生殖繁衍 │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```

### 器官-模块映射

| 器官 | 生物功能 | 核心模块 | 技术实现 |
|------|---------|---------|---------|
| 👁️ Eyes | 视觉感知 | `om_weather.py` `lazy_index.py` | Open-Meteo天气 · OCR · 环境扫描 |
| 👂 Ears | 听觉感知 | `event_bus.py` `resource_tree.py` | 事件流 · MCP工具发现 · API监听 |
| 🧠 Brain | 意识·推理 | `phenomenal_consciousness.py` `godelian_self.py` `emergence_detector.py` | 现象意识6层 · 哥德尔自指 · 涌现检测 |
| ❤️ Heart | 生命节律 | `xiaoshu.py` | 内在驱动力 · 5源自主任务生成 |
| 🫁 Lungs | 呼吸交换 | `kv_cache.py` `lazy_index.py` | 上下文吸入/呼出 · 按需加载 |
| 🫀 Liver | 过滤净化 | `safety.py` `cofee_engine.py` | 安全守卫 · 认知验证 · 幻觉检测 |
| 🩸 Blood | 资源循环 | `economic_engine.py` `thermo_budget.py` | ROI追踪 · 预算门控 · 热力学调度 |
| 🤲 Hands | 创造·操作 | `research_team.py` `gtsm_planner.py` | 4角色研究员 · 代码生成 · 工具创建 |
| 🦵 Legs | 移动·部署 | `sandbox_executor.py` | 授权SSH · Docker · 链式复制(受控) |
| 🦴 Bones | 结构框架 | `unified_pipeline.py` `action_principle.py` | 4模式流水线 · 变分原理 |
| 🛡️ Immune | 免疫防御 | `safety.py` `hallucination_guard.py` | 22模式自复制检测 · 注入扫描 |
| 🌱 Repro | 生殖繁衍 | `dsmtree_distiller.py` `cell/` | 知识种子导出 · 后代诞生 |

---

## 三、六层模块架构

```
Layer 1: 感官层 (Perception)
  └── Eyes + Ears: 事件总线, 天气, 资源树, 文档索引

Layer 2: 知识层 (Knowledge) — 10模块
  └── 超图存储 · 优先模型 · 顺序重排 · 知识引力 · 懒加载 · 图自省

Layer 3: 推理层 (Reasoning) — 6模块
  └── GTSM规划器 · 统一流水线 · CoFEE认知约束 · TreeFlow加速

Layer 4: 执行层 (Execution) — 5模块
  └── Thompson路由 · 评分匹配 · 免费池 · 并行起草 · MTP起草

Layer 5: 意识层 (Consciousness) — 9模块
  └── 现象意识 · 哥德尔自指 · 小树生长 · 生命体 · 研究员团队

Layer 6: 自治层 (Autonomy) — 4模块
  └── 系统健康 · 作用量原理 · 自校正回路 · 沉默突触
```

---

## 四、数据流

### 任务处理流程

```
用户输入 (或小树自发任务)
    │
    ▼
ResourceTree ──→ 路由到对应挂载点
    │
    ▼
EconomicGate ──→ 经济审查 (预算/ROI/合规)
    │
    ▼
TreeLLM Router ──→ Thompson采样/评分匹配选Provider
    │
    ▼
Knowledge RAG ──→ 超图检索 + 顺序重排 + 引力透镜
    │
    ▼
GTSMPlanner ──→ 树/流/混合模式生成计划
    │
    ▼
PipelineOrchestrator ──→ DAG/ReAct/BehaviorTree/GTSM执行
    │
    ▼
CoFEE Engine ──→ 四约束验证 (反向链式/可观测性/无泄漏/回溯)
    │
    ▼
PhenomenalConsciousness ──→ 现象体验 (情感+元认知+自我模型更新)
    │
    ▼
SynapticPlasticity ──→ LTP/LTD更新 · 沉默突触激活 · 成熟保护
```

### 自主生长循环

```
小树自主周期 (每2-4分钟, 无外部触发):

WAKE ──→ IntrinsicDrive.generate()
  ├── CURIOSITY: 超图孤立节点 → "我要去了解这个"
  ├── GROWTH: 沉默突触过多 → "我需要巩固知识"
  ├── COHERENCE: 因果不一致 → "我要检查逻辑"
  ├── EXPLORATION: 未测试模型 → "让我试试新能力"
  └── MASTERY: 技能下滑 → "我不能变弱"

EXPLORE ──→ PipelineOrchestrator.run(task)
LEARN ──→ experience() + LTP
REFLECT ──→ "我主动探索了未知领域..."
GROW ──→ 更新意识 + 突触 + 领域兴趣
REST ──→ 随机间隔后再次醒来
```

---

## 五、自治系统架构

### 5阶段自校正闭环

```
DETECT    → SystemHealth.check(8 subsystems)
DIAGNOSE  → ActionPrinciple.analyze() — 哪个模块偏离δS=0?
REPAIR    → _apply_fix() — 8种自动修复
VERIFY    → SystemHealth.check() — 修复是否生效?
FEEDBACK  → 更新突触 + 可预测性 + 路由器
```

### 6个后台守护进程

| 守护进程 | 间隔 | 功能 |
|---------|------|------|
| homeostatic | 5分钟 | 全局权重拉向0.30均衡点 |
| pruning | 10分钟 | 衰减→删除低于0.01的突触 |
| calibration | 15分钟 | 自动校准双层奖励α |
| decay | 20分钟 | 衰减不活跃Provider信念 |
| interference | 3分钟 | 检测干扰→触发自蒸馏 |
| consolidation | 5分钟 | 提升active→mature |

### 8种自动修复

| 检测信号 | 自动修复 |
|---------|---------|
| 干扰比>0.1 | `SELF_DISTILLATION` |
| 可用模型<30% | `RELEASE_QUARANTINED` |
| Provider数据<3 | `EXPLORE_MORE` |
| 自我模型不动点 | `INJECT_NOVELTY` |
| ROI<1.0 | `RECALIBRATE_REWARD` |
| EL残差高 | `REDUCE_LTP` |
| 全局漂移 | `HOMEOSTATIC_SCALE` |

---

## 六、14篇论文集成架构

```
论文层                      实现层                      验证层
──────                      ──────                      ──────
OKH-RAG         ──→  hypergraph_store + order_reranker  → RRF融合管线
TDM-R1          ──→  tdm_reward (不可微RL)              → 逐步奖励分配
STReasoner      ──→  spatial_reward (S-GRPO)            → 空间感知优化
DFlash          ──→  parallel_drafter                   → 并行起草
StarVLA         ──→  unified_pipeline                   → 乐高接口
CoFEE           ──→  cofee_engine                       → 四约束验证
Doctor-R1       ──→  inquiry_engine                     → 多轮问询
Gemma4 MTP      ──→  mtp_drafter                        → 多步预测
Predictability  ──→  predictability_engine              → 可预测性度量
Silent Synapses ──→  synaptic_plasticity                → 突触可塑性
Fine-tune Halluc──→  synaptic_plasticity                → 干涉检测
NLA Autoencoder ──→  phenomenal_consciousness           → 内部状态解码
Self-Replication──→  safety.py                          → 复制防护
Heuristic Learn ──→  latent_grpo (反馈对齐)             → 无梯度学习
```

---

## 七、技术栈

| 层次 | 技术 |
|------|------|
| 前端 | HTMX 2.0 · Jinja2 · SSE · 零JS框架 |
| 后端 | FastAPI · Uvicorn · aiohttp |
| LLM | Thompson采样 · 评分匹配 · 50+Provider · SenseTime |
| 知识 | 超图(NetworkX) · RRF融合 · 懒加载索引 |
| 存储 | SQLite FTS5 · JSON快照 · 磁盘缓存 |
| 优化 | GRPO · 贝叶斯Bandit · 反馈对齐 · 变分原理 |
| 安全 | Fernet加密 · 安全守卫 · 22模式复制检测 |
| 可观测 | loguru · 系统健康仪表盘 · 全链路追踪 |
