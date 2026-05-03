# LivingTree 模块迁移跟踪

> 从 `client/src/business/` 到 `livingtree/` 包的迁移进度。
> 最后更新：2026-05-03

## 总体进度

| 阶段 | 状态 | 进度 |
|------|------|------|
| 核心引擎框架 (11 子系统) | ✅ 完成 | 100% |
| 基础设施层 | ✅ 完成 | 90% |
| 适配器层 | ✅ 完成 | 70% |
| 前端桥接 | ✅ 完成 | 70% |
| **业务模块迁移** | 🔄 进行中 | ~70% |

---

## 已完成迁移

### P1 — 高优先级 ✅ 100%

| 源路径 | 目标路径 | 状态 | 说明 |
|--------|----------|------|------|
| `llm_wiki/knowledge_graph_integrator_v3.py` | `knowledge/wiki/kg_integrator.py` | ✅ | V3 实体链接+图推理 |
| `llm_wiki/knowledge_graph_integrator_v4.py` | `knowledge/wiki/kg_integrator_v4.py` | ✅ | V4 EvoRAG 集成版 |
| `llm_wiki/integration.py` | `knowledge/wiki/integration.py` | ✅ | FusionRAG 全量集成 |
| `p2p_broadcast/` (~6 文件) | `network/p2p/` | ✅ | P2P 广播 |
| `p2p_connector/` (~3 文件) | `network/connector/` | ✅ | P2P 连接器 |
| `p2p_knowledge/` (~4 文件) | `network/knowledge/` | ✅ | P2P 知识共享 |
| `relay_chain/` (~8 文件) | `consensus/` | ✅ | 区块链式中继共识 |
| `provider/*` (driver架构) | `adapters/providers/drivers/` | ✅ | hard_load/local_service/cloud |

### P2 — 中优先级 ✅ 100%

| 源路径 | 目标路径 | 状态 | 说明 |
|--------|----------|------|------|
| `fusion_rag/` (~8 文件) | `knowledge/rag/` | ✅ | 融合 RAG 引擎：统一 RAGResult、RAGPipeline 5 策略 |
| `search/` (~9 文件) | `search/` | ✅ | 16 引擎分层搜索 + TierRouter |
| `decommerce/` (~4 文件) | `ecommerce/models/` | ✅ | 统一 Order/Listing/Node/Reputation 模型 |
| `local_market/` (~11 文件) | `ecommerce/models/` | ✅ | 合并入统一 ecommerce 模型 |
| `flash_listing/` | `ecommerce/models/` | ✅ | 合并入统一 ecommerce 模型 |
| `social_commerce/` | `ecommerce/models/` | ✅ | 合并入统一 ecommerce 模型 |
| `credit_economy/` (~3 文件) | `economy/` | ✅ | CreditRegistry 单例 + 4 预设插件 |
| - | `ecommerce/managers/` | ✅ | OrderManager(CRDT) + ReputationManager(BFS) |

### P3 — 低优先级 ✅ 100%

| 源路径 | 目标路径 | 状态 | 说明 |
|--------|----------|------|------|
| `dou_di_zhu/` (~3 文件) | `games/` | ✅ | 斗地主 AI：修复 undefined cards bug，优化组合生成 |
| `git_nexus/` (~5 文件) | `integrations/git_nexus.py` | ✅ | Git 分析+AST 解析+搜索+质量：修复 3 bug |
| `github_store/` (~6 文件) | `integrations/github_store.py` | ✅ | GitHub 应用商店：修复 2 bug，统一资产检测 |
| `self_upgrade/` (~9 文件) | `maintenance/` | ✅ | 自我升级系统：修复 4 bug，依赖注入解耦 |
| `enhanced_model_router.py` (1 文件) | `model/enhanced_router.py` | ✅ | 增强路由器：合并 ModelCapability 枚举；pipeline_orchestrator + router_adapter 已更新引用 |

### 核心引擎 (livingtree/core/)

| 源路径 | 目标路径 | 状态 | 说明 |
|--------|----------|------|------|
| `llm_wiki/models.py` | `knowledge/wiki/models.py` | ✅ | DocumentChunk, PaperMetadata |
| `llm_wiki/parsers.py` | `knowledge/wiki/parsers.py` | ✅ | LLMDocumentParser, PaperParser, CodeExtractor |
| `llm_wiki/feedback_manager.py` | `knowledge/wiki/feedback_manager.py` | ✅ | EvoRAG 反馈管理系统 |
| `llm_wiki/kg_self_evolver.py` | `knowledge/wiki/kg_self_evolver.py` | ✅ | 知识图谱自进化引擎 |
| `llm_wiki/hybrid_retriever.py` | `knowledge/wiki/hybrid_retriever.py` | ✅ | 混合优先级检索器 |

### 适配器层 (livingtree/adapters/)

| 源路径 | 目标路径 | 状态 | 说明 |
|--------|----------|------|------|
| `providers/provider_registry.py` | `providers/provider_catalog.py` | ✅ | 34 预配置提供商 (本地/云端/国内/企业) |
| `providers/base_provider.py` | `providers/ollama.py` (已存在) | ✅ | ProviderBase 基类 |
| - | `providers/deepseek.py` (已存在) | ✅ | DeepSeek Provider |

---

## 迁移统计

### 代码缩减

| 模块 | 旧文件数 | 旧 LOC | 新文件数 | 新 LOC | 缩减率 |
|------|---------|--------|---------|--------|--------|
| ecommerce (P2) | ~25 | ~30,000 | 8 | ~2,500 | ~92% |
| fusion_rag (P2) | ~8 | ~8,000 | 2 | ~500 | ~94% |
| search (P2) | ~9 | ~5,000 | 1 | ~800 | ~84% |
| economy (P2) | ~3 | ~2,000 | 1 | ~350 | ~83% |
| dou_di_zhu (P3) | ~3 | ~1,100 | 1 | ~500 | ~55% |
| git_nexus (P3) | 5 | ~1,700 | 1 | ~850 | ~50% |
| github_store (P3) | 6 | ~1,800 | 1 | ~900 | ~50% |
| self_upgrade (P3) | 9 | ~3,600 | 1 | ~1,100 | ~70% |
| enhanced_router (P3) | 1 | ~577 | 1 | ~420 | ~27% |
| **合计** | ~69 | ~53,800 | 17 | ~7,920 | ~85% |

### Bug 修复

| 模块 | Bug | 影响 |
|------|-----|------|
| dou_di_zhu | `cards` 变量未定义 | compare() 运行时崩溃 |
| dou_di_zhu | O(2^n) 组合扫描 | 性能指数爆炸 |
| dou_di_zhu | 3 玩家硬编码 | 无法扩展 |
| git_nexus | ClassDef AST 重复处理 | 弹栈永远为真 |
| git_nexus | 质量分析器 file_path 硬编码 | 所有分析结果路径错误 |
| git_nexus | `source` 变量未定义 (recommend_code) | 代码推荐运行时崩溃 |
| github_store | `AssetType.ASSET` 拼写错误 | APK 检测失败 |
| github_store | 资产检测逻辑重复 | 维护时需两处同步修改 |
| self_upgrade | 硬编码 legacy `business.config` | 无法独立运行 |
| self_upgrade | `check_safety()` 循环导入风险 | 模块加载时可能崩溃 |
| self_upgrade | `system_brain` 硬编码 legacy 依赖 | 无法独立运行 |
| self_upgrade | SQL 直接字符串 verdict | 类型不安全 |

---

## 文件统计

| 类别 | 文件数 | 已迁移 | 待迁移 |
|------|--------|--------|--------|
| knowledge/wiki | 13 | 13 | 0 |
| providers | 40+ | 34 | 6 |
| network (p2p) | 13 | 13 | 0 |
| consensus (relay_chain) | 8 | 8 | 0 |
| ecommerce | 25+ | 25+ | 0 |
| search | 9 | 9 | 0 |
| economy | 3 | 3 | 0 |
| games | 3 | 3 | 0 |
| integrations | 11 | 11 | 0 |
| maintenance | 9 | 9 | 0 |
| model (enhanced_router) | 1 | 1 | 0 |
| 其他业务模块 | ~99 | 0 | ~99 |

---

## 约定

- 新代码使用 `from loguru import logger`
- 使用 `livingtree.core.knowledge.wiki.xxx` 格式导入
- numpy 作为可选依赖 (try/except ImportError)
- 保持与 legacy 代码的 API 兼容性（通过 shim）
- 迁移=梳理架构+合并增强，不照抄代码
