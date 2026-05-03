# 系统架构手册

## 1. 顶层架构

```
LivingWorld (统一上下文)
    │
    ├── LifeEngine (6阶段管线)
    │   ├── perceive  → DualModelConsciousness.stream_of_thought()
    │   ├── cognize   → KnowledgeBase.search() + chain_of_thought()
    │   ├── plan      → TaskPlanner.decompose_task()
    │   ├── execute   → Orchestrator + HITL + CostAware + Checkpoint
    │   ├── reflect   → 成功率计算 + 质量报告汇总
    │   └── evolve    → 精英保留 + 交叉变异 + 细胞进化
    │
    ├── DualModelConsciousness (LiteLLM路由)
    │   ├── flash: deepseek/deepseek-v4-flash (t=0.3)
    │   └── pro:   deepseek/deepseek-v4-pro  (t=0.7, thinking)
    │
    ├── SafetyGuard (16层安全)
    │   ├── MerkleAuditChain (SHA-256链式审计)
    │   ├── PathGuard (路径穿越防护)
    │   ├── SSRFGuard (内网/元数据阻断)
    │   └── PromptInjectionScanner (9种攻击模式)
    │
    └── Subsystems
        ├── Cell: CellAI, Distillation, Mitosis, Phage, Regen, SwiftDrillTrainer
        ├── Knowledge: Bi-temporal KB, VectorStore, KnowledgeGraph
        ├── Capability: ToolMarket(30 tools), DocEngine, CodeEngine, ASTParser, CodeGraph
        ├── Execution: TaskPlanner, Orchestrator, HITL, Checkpoint, CostAware, QualityChecker
        ├── Network: P2P Node, Discovery, NATTraverser, EncryptedChannel, Reputation
        └── TUI: Chat/Code/Docs/Settings screens + TaskTree + CommandPalette
```

## 2. LifeEngine 管线详解

### 2.1 perceive (感知)
- `DualModelConsciousness.stream_of_thought()` 流式分析输入
- `MaterialCollector.collect_from_web()` 外部资料收集
- `SafetyGuard.scan_prompt()` 提示注入扫描

### 2.2 cognize (认知)
- `chain_of_thought()` 深度推理理解意图
- `KnowledgeBase.search()` bi-temporal知识检索
- `_context_budget()` 根据复杂度动态分配知识注入量
- `self_questioning()` 识别知识空白

### 2.3 plan (规划)
- `TaskPlanner.decompose_task()` 5领域模板匹配
- `hypothesis_generation()` 多假设生成
- `Checkpoint.resume()` 检测断点续传

### 2.4 execute (执行)
- `CostAware.can_use()` 预算检查 → 超85%自动降级
- `HITL.request_approval()` needs_approval步骤暂停等人类决策
- `Orchestrator.assign_task()` 17Agent多智能体调度
- `QualityChecker.check()` 7阶段质量验证
- `Checkpoint.save()` 每步自动保存

### 2.5 reflect (反思)
- 成功率计算
- 错误归因
- 质量报告汇总

### 2.6 evolve (进化)
- **精英保留**: >=80%成功率的会话存入elite_registry
- **交叉变异**: 3+精英会话自动合成新策略
- **细胞进化**: 失败时触发cell.evolve()
- **基因突变**: mutation_history记录
- **自愈**: SelfHealer.run_all_checks()

## 3. 数据流

### 3.1 知识管道
```
Raw Ledger (SQLiteBackend)
    → Views (VectorStore.search + GapDetector)
    → Policy (Genome.expressed_genes)
    → Commit (merge_knowledge)
    → Provenance (MerkleAuditChain + Document.source/author/revision)
```

### 3.2 Bi-temporal 时序
```
Document.valid_from / valid_to     ← 真实世界有效性窗口
Document.created_at / updated_at   ← 系统记录时间

search(as_of=datetime(2023,6,15))  → 时间点回溯
search_current()                   → 仅当前有效
history()                          → 全部含已失效
at_time(point)                     → "当时的KB快照"
```

### 3.3 成本追踪
```
TokenUsage → CostAware.record()
    → BudgetStatus.usage_pct
    → >=85% 自动 degrade(): pro→flash
    → <85% 自动 restore(): flash→pro
    → API: /api/cost/status
```

## 4. 安全架构

### 4.1 Merkle 审计链
```
entry_n.hash = SHA256(entry_n.data + entry_{n-1}.hash)
verify() → 全链验证 → 篡改即断裂
export_proof(index) → 包含证明
```

### 4.2 防护矩阵

| 防护层 | 实现 | 检测模式 |
|--------|------|---------|
| 路径穿越 | PathGuard | ../检测 + 工作区沙箱 |
| SSRF | SSRFGuard | 私有IP段 + 云元数据端点黑名单 |
| 提示注入 | PromptInjectionScanner | 9种攻击模式正则 |
| 密钥保护 | ZeroizingSecret | 字节数组 + __del__自动清零 |
| 代码安全 | SandboxedExecutor | 子进程隔离 + 超时 |

## 5. 扩展点

- **新LLM提供商**: 修改 `config.ltaiconfig.yaml` 中的 model 字段 (`provider/model` 格式)
- **新工具**: 在 `capability/tool_market.py` 中添加 handler + ALL_TOOLS 条目
- **新报告模板**: 在 `capability/doc_engine.py` 的 `INDUSTRIAL_TEMPLATES` 中添加
- **新Agent角色**: 在 `integration/hub.py` 的 `_register_agents()` 中添加
- **新TaskPlanner模板**: 在 `execution/task_planner.py` 的 `DOMAIN_TEMPLATES` 中添加
