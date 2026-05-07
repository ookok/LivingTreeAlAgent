# LivingTree 全项目架构审计与重构计划

> 生成日期: 2026-05-07 | 项目版本: v2.1.0

---

## 项目规模

| 维度 | 数据 |
|------|------|
| Python 文件 | 501 (不含 vendored Textual) |
| 子模块数 | 20+ |
| 最大文件 | hub.py 1583行, life_engine.py 1650行, struct_mem.py 1406行 |
| 新增模块 (2026-05) | 10 新建 + 7 扩展 |
| LLM Provider | 13 注册 + models.dev 50+ |

---

## 架构评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 模块化 | ⭐⭐⭐⭐ | 分层清晰 (dna/knowledge/execution/treellm) |
| 内聚性 | ⭐⭐⭐ | 部分 layer 间交叉导入多 |
| 冗余度 | ⭐⭐ | 多对重复逻辑 |
| 可测试性 | ⭐⭐ | 缺少 pytest 单元测试 |
| 文档 | ⭐⭐⭐ | README 已更新，缺少 API doc |

---

## 冗余发现 (13 项)

### 高优先级

1. orchestrator.py (150行) — 外立面，被 real_pipeline.py 取代 → 删除
2. self_evolving.py (288行) vs self_evolving_rules.py (779行) → 合并为 dna/evolution.py
3. knowledge_base.py (832行) vs intelligent_kb.py (473行) — 检索功能重叠 → 合并入口
4. hallucination_guard.py (272行) vs retrieval_validator.py (226行) → 合并为 quality_guard.py
5. content_quality.py (294行) vs quality_scorer.py (233行) vs quality_checker.py (484行) → 保留 quality_checker
6. context_glossary.py (416行) vs onto_bridge.py (251行) → 合并为 entity_bridge.py

### 中优先级

7. life_engine.py 1650行 — 超大类 → 拆分经济门控/计划验证
8. struct_mem.py 1406行 — 最大文件 → 拆为 3 文件
9. dna/ 40 文件 — 薄模块过多 → 归档 anticipatory/adaptive_ui/biorhythm
10. hub.py 1583行 — 初始化庞大 → 拆分模型注册/能力注册

### 低优先级

11. knowledge/ 34 文件 — 归档 format_discovery(76)/gap_detector(50)/knowledge_graph(83)
12. 无 pytest 测试框架 → 新建 tests/
13. styles/ 目录未确认使用状态

---

## 增强机会 (5 项)

E1: Qwen thinking 模式支持
E2: models.dev 启动同步 (已部分完成)
E3: cost_aware 全量 models.dev 同步
E4: Agentic RAG HITL 人机协同
E5: 端到端性能基准

---

## 创新建议 (3 项)

I1: 自适应经济调度器 (时段/紧急度/ROI 动态切换策略)
I2: 跨会话知识蒸馏 (models.dev → TreeLLM 路由权重更新)
I3: Gradual Agent 渐进智能 (简单→Agentic→多Agent)

---

## 执行计划

### Phase 1 — 清理冗余 (P0) ✅ 已修正
- [x] ~~删除 orchestrator.py~~ → **取消**: hub.py 主动实例化使用（agent注册/状态/健康检查），非外立面
- [x] ~~合并 content_quality/quality_scorer/quality_checker~~ → **取消**: 三者在不同层（knowledge vs execution），服务不同目的
- [x] 标记 knowledge/ 轻量模块 deprecated: format_discovery.py, gap_detector.py, knowledge_graph.py
- [x] 移除 execution/__init__.py 未使用的重复导出
- [x] 低优先级: knowledge/ 轻量模块 (format_discovery 76行, gap_detector 50行, knowledge_graph 83行) — 虽小但有独立用途，保留但标记为候选合并

## 修正说明

Phase 1 初步分析过于激进。经实际引用扫描发现：
- **orchestrator.py**: hub.py 主动实例化 `Orchestrator(max_agents=...)`，用于 agent 注册、状态查询、健康检查。与 real_pipeline.py 的 RealOrchestrator 是互补关系（registry vs execution），非冗余。
- **content_quality.py** (knowledge/) vs **quality_scorer.py** (execution/) vs **quality_checker.py** (execution/): 分属不同层，服务不同目的（内容质量 vs 输出评分 vs 多Agent校验），不可合并。

### Phase 2 — 模块合并 (P1)
- [ ] 合并 self_evolving.py + self_evolving_rules.py → dna/evolution.py
- [ ] 合并 hallucination_guard + retrieval_validator → quality_guard.py
- [ ] 合并 context_glossary + onto_bridge → entity_bridge.py
- [ ] 归档 anticipatory/adaptive_ui/biorhythm → personality.py

### Phase 3 — 拆分大文件 (P1)
- [ ] life_engine.py 经济门控提取到 economy/
- [ ] struct_mem.py 拆为 3 文件
- [ ] hub.py 模型初始化提取到 treellm/bootstrap.py

### Phase 4 — 增强 (P2)
- [ ] E1: Qwen thinking 支持
- [ ] E2: models.dev 启动同步
- [ ] E3: cost_aware 全量同步
- [ ] E4: Agentic RAG HITL 模式

### Phase 5 — 创新 (P2)
- [ ] I1: 自适应经济调度器
- [ ] I2: 跨会话知识蒸馏
- [ ] I3: Gradual Agent 渐进智能
