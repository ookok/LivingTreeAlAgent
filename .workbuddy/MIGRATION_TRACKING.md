# LivingTree 模块迁移跟踪

> 从 `client/src/business/` 到 `livingtree/` 包的迁移进度。
> 最后更新：2026-05-02

## 总体进度

| 阶段 | 状态 | 进度 |
|------|------|------|
| 核心引擎框架 (11 子系统) | ✅ 完成 | 100% |
| 基础设施层 | ✅ 完成 | 90% |
| 适配器层 | 🔄 进行中 | 70% |
| 前端桥接 | ✅ 完成 | 70% |
| **业务模块迁移** | 🔄 进行中 | ~40% |

---

## 已完成迁移

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

## 待迁移 (按优先级)

### P1 — 高优先级

| 源路径 | 目标路径 | 说明 |
|--------|----------|------|
| `llm_wiki/knowledge_graph_integrator_v3.py` (1089行) | `knowledge/wiki/kg_integrator.py` | V3 实体链接+图推理 (V4依赖) |
| `llm_wiki/knowledge_graph_integrator_v4.py` (588行) | `knowledge/wiki/kg_integrator_v4.py` | V4 EvoRAG 集成版 |
| `llm_wiki/integration.py` (1124行) | `knowledge/wiki/integration.py` | FusionRAG 全量集成 |
| `p2p_broadcast/` (~6 文件) | `network/p2p/` | P2P 广播 |
| `p2p_connector/` (~3 文件) | `network/connector/` | P2P 连接器 |
| `p2p_knowledge/` (~4 文件) | `network/knowledge/` | P2P 知识共享 |
| `relay_chain/` (~8 文件) | `consensus/` | 区块链式中继共识 |
| `provider/*` (driver架构) | `adapters/providers/drivers/` | hard_load/local_service/cloud |

### P2 — 中优先级

| 源路径 | 目标路径 | 说明 |
|--------|----------|------|
| `fusion_rag/` (~8 文件) | `knowledge/rag/` | 融合 RAG 引擎 |
| `search/` (~9 文件) | `search/` | 分层搜索引擎 |
| `decommerce/` (~4 文件) | `ecommerce/` | 去中心化电商 |
| `local_market/` (~11 文件) | `market/` | 本地市场 |
| `credit_economy/` (~3 文件) | `economy/` | 信用经济 |
| `provider/` (driver 架构) | `adapters/providers/drivers/` | driver 模式实现 |

### P3 — 低优先级

| 源路径 | 目标路径 | 说明 |
|--------|----------|------|
| `dou_di_zhu/` (~3 文件) | `games/` | 斗地主 AI |
| `git_nexus/` (~3 文件) | `integrations/` | Git 分析 |
| `github_store/` (~4 文件) | `integrations/` | GitHub 存储 |
| `self_upgrade/` (~3 文件) | `maintenance/` | 自升级系统 |

---

## 文件统计

| 类别 | 文件数 | 已迁移 | 待迁移 |
|------|--------|--------|--------|
| knowledge/wiki | 13 | 5 | 8 |
| providers | 40+ | 34 配置 | 6 driver 实现 |
| network (p2p) | 13 | 0 | 13 |
| consensus (relay_chain) | 8 | 0 | 8 |
| 其他业务模块 | 200+ | 0 | 200+ |

---

## 约定

- 新代码使用 `from loguru import logger`
- 使用 `livingtree.core.knowledge.wiki.xxx` 格式导入
- numpy 作为可选依赖 (try/except ImportError)
- 保持与 legacy 代码的 API 兼容性
