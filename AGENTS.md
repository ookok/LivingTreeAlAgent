# LivingTree AI Agent v2.1 — AGENTS.md

> 2026-05-06 | Python 3.14+ | Textual (Toad) | ~200 files in livingtree/

## OVERVIEW

Digital life form AI platform. **UI is Toad (Textual-based TUI)** — PyQt6 + Vue 3 are deprecated and unused. All active code lives in `livingtree/`.

Core: LifeEngine 6-stage cycle (perceive → cognize → plan → execute → reflect → evolve) with 10+ LLM providers, P2P network, self-evolving cells, knowledge base (FTS5 + vector + graph), and industrial document generation.

## ARCHITECTURE

```
livingtree/
├── main.py                  # CLI entry: tui | client | server | test | check | quick
├── __init__.py              # Lazy imports — __getattr__ pattern for deferred loading
├── __main__.py              # python -m livingtree
│
├── dna/                     # DNA — Life blueprint (32 files)
│   ├── life_engine.py       # LifeEngine: perceive → cognize → plan → execute → reflect → evolve
│   ├── living_world.py      # LivingWorld: single system-wide context container
│   ├── consciousness.py     # Consciousness: intent recognition, LLM abstraction
│   ├── dual_consciousness.py # DualModelConsciousness: flash + pro model routing
│   ├── genome.py            # Genome: digital genetics, evolution tracking
│   ├── safety.py            # SafetyGuard: sandbox, audit chain, kill switch, SSRF guard
│   ├── cache_optimizer.py   # Prefix cache tracker for LLM token reuse
│   ├── tool_repair.py       # ToolCallRepair: auto-fix broken tool calls
│   ├── thought_harvest.py   # ThoughtHarvester: extract thinking blocks
│   ├── conversation_dna.py  # ConversationDNA: session pattern tracking
│   ├── tui_orchestrator.py  # LLM → TUI routing
│   ├── unified_skill_system.py  # Skill self-learning
│   ├── life_daemon.py       # Background life cycle daemon
│   ├── self_evolving.py     # SelfEvolvingEngine
│   ├── multi_agent_debate.py # MultiAgentDebate
│   ├── predictive_world.py  # PredictiveWorldModel
│   ├── biorhythm.py         # Biorhythm cycles
│   ├── adaptive_ui.py       # Adaptive UI behavior
│   └── anticipatory.py      # Anticipatory actions
│
├── cell/                    # Cell — Trainable AI cells (9 files)
│   ├── cell_ai.py           # CellAI: trainable LLM unit
│   ├── trainer.py           # CellTrainer: LoRA training
│   ├── registry.py          # CellRegistry: discovery + registration
│   ├── mitosis.py           # Mitosis: cell splitting/specialization
│   ├── phage.py             # Phage: absorb external codebases
│   ├── regen.py             # Regen: recovery from checkpoints
│   ├── distillation.py      # Distillation: knowledge extraction
│   └── swift_trainer.py     # SwiftDrillTrainer: fast training pipeline
│
├── knowledge/               # Knowledge — KB layer (14 files)
│   ├── knowledge_base.py    # KnowledgeBase: central KB
│   ├── vector_store.py      # VectorStore: pluggable embedding backends
│   ├── knowledge_graph.py   # KnowledgeGraph: entity relationships
│   ├── document_kb.py       # DocumentKB: chunked doc storage
│   ├── intelligent_kb.py    # IntelligentKB: search + fact-check
│   ├── struct_mem.py        # StructMemory: hierarchical memory
│   ├── session_search.py    # FTS5 session search
│   ├── auto_knowledge_miner.py  # Auto knowledge mining
│   ├── learning_engine.py   # TemplateLearner, SkillDiscoverer, RoleGenerator
│   ├── provenance.py        # ProvenanceTracker: data lineage
│   └── dedup.py             # Deduplication
│
├── capability/              # Capability — Skills & engines (16+ files)
│   ├── skill_factory.py     # SkillFactory: skill creation
│   ├── tool_market.py       # ToolMarket: tool registry + marketplace
│   ├── doc_engine.py        # DocEngine: industrial report generation (EIA, emergency plans)
│   ├── code_engine.py       # CodeEngine: code generation with annotations
│   ├── code_graph.py        # CodeGraph: AST-based code relationship graph
│   ├── ast_parser.py        # ASTParser: multi-language parsing
│   ├── extraction_engine.py # ExtractionEngine: LangExtract grounded entity extraction
│   ├── pipeline_engine.py   # PipelineEngine: workflow orchestration
│   ├── multimodal_parser.py # MultimodalParser: image/table/document parsing
│   ├── skill_discovery.py   # SkillDiscoveryManager: auto-discover skills
│   ├── self_discovery.py    # SelfDiscovery: tool pattern discovery
│   ├── memory_pipeline.py   # MemoryPipeline: structured memory processing
│   ├── web_reach.py         # WebReach: smart web scraping
│   └── ddg_search.py        # DuckDuckGo search
│
├── execution/               # Execution — Task orchestration (19 files)
│   ├── task_planner.py      # TaskPlanner: task decomposition
│   ├── orchestrator.py      # Orchestrator: multi-agent coordination
│   ├── real_pipeline.py     # Real orchestrator: intent-driven pipeline
│   ├── self_healer.py       # SelfHealer: health checks + recovery
│   ├── panel_agent.py       # Panel agents: per-panel self-healing
│   ├── quality_checker.py   # MultiAgentQualityChecker
│   ├── side_git.py          # SideGit: turn-based snapshot + restore
│   ├── session_manager.py   # SessionManager: cross-session resume
│   ├── sub_agent_roles.py   # SubAgentRoles: implementer/verifier pattern
│   ├── rlm.py               # RLMRunner: fan-out parallel LLM tasks
│   ├── dag_executor.py      # DAGExecutor: dependency-aware execution
│   ├── hitl.py              # HumanInTheLoop: approval workflow
│   ├── checkpoint.py        # TaskCheckpoint: state persistence
│   ├── cost_aware.py        # CostAware: token budget management
│   ├── cron_scheduler.py    # CronScheduler: periodic jobs
│   ├── auto_skill_resolver.py  # Auto skill completion
│   ├── task_guard.py        # TaskGuard: timeout + circuit breaker
│   └── thinking_evolution.py  # ThinkingEvolution: elite pool evolution
│
├── treellm/                 # TreeLLM — LLM routing (11 files)
│   ├── core.py              # TreeLLM: multi-provider routing engine
│   ├── providers.py         # OpenAILikeProvider + provider adapters
│   ├── holistic_election.py # 5-dimension model election (cost/speed/quality/...)
│   ├── structured_enforcer.py  # JSON Schema validation
│   ├── skill_router.py      # Full-text skill routing
│   ├── model_registry.py    # ModelRegistry: auto-discover + cache
│   ├── cache_director.py    # CacheDirector: prompt cache management
│   ├── classifier.py        # Request classifier
│   ├── local_scanner.py     # Local model scanner
│   └── session_binding.py   # Session-model binding
│
├── tui/                     # TUI — Toad/Textual interface (15+ dirs)
│   ├── app.py               # LivingTreeTuiApp: extends ToadApp, 5 panels
│   ├── td/                  # Toad source (54 files) — embedded Textual framework
│   ├── screens/             # Screen implementations:
│   │   ├── boot.py          # BootScreen: progressive initialization
│   │   ├── neon_chat.py     # NeonChatScreen: main chat panel
│   │   ├── code.py          # CodeScreen: code editor
│   │   ├── docs.py          # KnowledgeScreen: KB panel
│   │   ├── tools.py         # ToolsScreen: toolbox
│   │   ├── settings.py      # Settings screen
│   │   ├── login.py         # LoginScreen: mandatory auth
│   │   └── help.py          # HelpScreen
│   ├── widgets/             # UI components: Card, StatusBar, etc.
│   ├── styles/theme.tcss    # CSS theme
│   ├── i18n.py              # i18n: zh/en translation (singleton, t("key"))
│   └── wt_bootstrap.py      # Windows Terminal bootstrapper: downloads WT if missing
│
├── network/                 # Network — P2P layer + Scinet v2.0 intelligent proxy (21 files)
│   ├── node.py              # Node: P2P node identity
│   ├── discovery.py         # Discovery: LAN peer discovery
│   ├── nat_traverse.py      # NATTraverser: NAT traversal
│   ├── reputation.py        # Reputation: trust scoring
│   ├── encrypted_channel.py # EncryptedChannel: AES messaging
│   ├── offline_mode.py      # DualMode: online/offline switching
│   ├── p2p_node.py          # P2P node lifecycle
│   ├── proxy_fetcher.py     # ProxyPool: multi-source proxies (6 sources)
│   ├── scinet_service.py    # ScinetService: local HTTP proxy (port 7890)
│   ├── scinet_engine.py     # 🆕 ScinetEngine v2.0: unified intelligent pipeline
│   ├── scinet_quic.py       # 🆕 QUIC/HTTP3 tunnel + protocol obfuscation
│   ├── scinet_bandit.py     # 🆕 Contextual Bandit RL proxy selection (LinUCB + Thompson)
│   ├── scinet_federated.py  # 🆕 Federated proxy quality learning (FedAvg + differential privacy)
│   ├── scinet_topology.py   # 🆕 GNN-inspired topology optimizer (GAT attention routing)
│   ├── scinet_cache.py      # 🆕 Semantic cache (L1 memory + L2 SQLite + delta compression)
│   ├── scinet_webtransport.py # 🆕 WebTransport browser-native tunnel (QUIC)
│   ├── domain_ip_pool.py    # DomainIPPool: 100+ pre-tested overseas IPs
│   ├── site_accelerator.py  # SiteAccelerator: FastGithub-style acceleration
│   └── collective.py        # CollectiveConsciousness: swarm intelligence
│
├── integration/             # Integration — Wiring layer (9 files)
│   ├── hub.py               # IntegrationHub: progressive boot, DI, lifecycle
│   ├── launcher.py          # Launch modes: CLIENT | SERVER | TEST | QUICK | CHECK
│   ├── self_updater.py      # Auto-update with mirror fallback
│   ├── pkg_manager.py       # Package manager: pip/conda/uv detection
│   ├── sse_server.py        # SSE agent server
│   ├── opencode_bridge.py   # OpenCode integration
│   ├── opencode_serve.py    # OpenCode serve launcher
│   └── message_gateway.py   # Multi-platform message gateway
│
├── config/                  # Config — Settings (6 files)
│   ├── settings.py          # LTAIConfig: Pydantic, YAML + env + vault
│   ├── secrets.py           # SecretVault: Fernet-encrypted API key storage
│   ├── system_config.py     # System constants
│   └── config_editor.py     # Config editor utility
│
├── core/                    # Core — Primitives (4 files)
│   ├── unified_registry.py  # UnifiedRegistry: tools/roles/KB single source
│   ├── async_disk.py        # AsyncDisk: batched async file I/O
│   ├── task_guard.py        # TaskGuard: timeout + circuit breaker
│   └── file_resolver.py     # File path resolution
│
├── api/                     # API — FastAPI server (3 files)
│   └── server.py            # FastAPI app, WebSocket support
│
├── mcp/                     # MCP — Model Context Protocol (2 files)
│   └── server.py            # MCP server implementation
│
├── lsp/                     # LSP — Language Server Protocol (2 files)
│   └── lsp_manager.py       # LSPManager: code diagnostics
│
└── observability/           # Observability (11 files)
    ├── setup.py             # setup_observability: logger + metrics + tracer
    ├── error_interceptor.py # Global error capture
    ├── system_monitor.py    # System resource monitoring
    ├── activity_feed.py     # Unified event stream
    ├── agent_eval.py        # 4-layer agent evaluation
    ├── trust_scoring.py     # Per-agent trust scoring
    └── error_replay.py      # Error recording + self-healing
```

## RUN COMMANDS

```bash
# TUI (primary interface — Textual in Windows Terminal)
python -m livingtree tui              # normal boot (with WT bootstrap)
python -m livingtree tui --direct     # skip WT bootstrap, run directly
python -m livingtree tui /path/to/workspace  # with workspace path

# CLI modes
python -m livingtree client           # interactive CLI chat
python -m livingtree server           # FastAPI on http://localhost:8100
python -m livingtree quick "message"  # single interaction
python -m livingtree check            # environment check
python -m livingtree test             # integration tests

# Update
python -m livingtree update           # check + apply updates
python -m livingtree _update_cli --check  # check only
python -m livingtree _update_cli --mirror --no-deps  # mirror, skip deps

# Via root main.py (legacy compatibility)
python main.py livingtree tui         # same as python -m livingtree tui
```

## CONFIG

**LTAIConfig** (`livingtree/config/settings.py`) — Pydantic model, loaded from:
1. Defaults (hardcoded)
2. YAML: `config/ltaiconfig.yaml` or `config/config.yaml` or `~/.livingtree/config.yaml`
3. Env vars: `LT_*` prefix (e.g., `LT_DEEPSEEK_API_KEY`, `LT_FLASH_MODEL`)
4. **Secret Vault** (`livingtree/config/secrets.py`) — Fernet-encrypted, stores API keys

```python
from livingtree.config import LTAIConfig, get_config, reload_config, config

# Direct access (Pydantic)
key = config.model.deepseek_api_key
flash = config.model.flash_model   # default: "deepseek/deepseek-v4-flash"
pro = config.model.pro_model       # default: "deepseek/deepseek-v4-pro"

# Reload
cfg = get_config(reload=True)
```

**Env overrides:**
| Variable | Maps to |
|----------|---------|
| `LT_DEEPSEEK_API_KEY` | `model.deepseek_api_key` |
| `LT_FLASH_MODEL` | `model.flash_model` |
| `LT_PRO_MODEL` | `model.pro_model` |
| `LT_NODE_NAME` | `network.node_name` |
| `LT_LAN_PORT` | `network.lan_port` |
| `LT_API_HOST` / `LT_API_PORT` | `api.host` / `api.port` |

## INTEGRATIONHUB BOOT SEQUENCE

`IntegrationHub(lazy=True)` → instant UI, heavy init deferred:

1. `__init__`: config + observability only
2. `_init_sync` (thread executor): LivingWorld, all components, wire everything
3. `_init_async`: health checks, node register, P2P, cron, model registry, daemon

**Progressive boot** in TUI: UI shows immediately, IntegrationHub created in background thread, heavy sync work runs in executor, async init follows.

```python
hub = IntegrationHub(lazy=True)  # fast
await hub.start()                 # full init
result = await hub.chat("帮我生成报告")  # main interaction
await hub.shutdown()
```

## LLM PROVIDERS (10+ supported)

Configured via `config/model/` — each provider has `base_url`, `api_key`, `flash_model`, `pro_model`:

| Provider | Default flash | Default pro |
|----------|--------------|-------------|
| DeepSeek | deepseek-v4-flash | deepseek-v4-pro |
| LongCat | LongCat-Flash-Lite | - |
| Xiaomi | mimo-v2-flash | mimo-v2.5 |
| Aliyun | qwen-turbo | qwen-max |
| Zhipu | glm-4-flash | glm-4-plus |
| SiliconFlow | Qwen2.5-7B | DeepSeek-V3 |
| MoFang (Gitee) | Qwen2.5-7B | DeepSeek-V3 |
| DMXAPI | gpt-5-mini | - |
| Spark (讯飞) | xdeepseekv3 | - |
| NVIDIA | deepseek-r1 | - |

**HolisticElection** selects model per-request based on 5 dimensions: cost, speed, quality, availability, and task complexity.

## CONVENTIONS

- **All new code** goes in `livingtree/` — never in `client/`
- **Imports**: `from livingtree.dna import LifeEngine`, `from livingtree.config import get_config`
- **Windows**: use `;` not `&&` for command chaining
- **i18n**: use `t("key")` from `livingtree/tui/i18n.py` — default lang is zh
- **Tests**: `pytest` from project root, tests in `tests/`
- **Logging**: loguru, level configured via `config.observability.log_level`

## ANTI-PATTERNS

- ❌ Don't reference `client/src/business/` or PyQt6 — they're deprecated
- ❌ Don't reference `client/src/frontend/` or Vue 3 — they're deprecated
- ❌ Don't import from `livingtree/infrastructure/config.py` — config is in `livingtree/config/settings.py`
- ❌ Don't use `from client.src.business.global_model_router` — use `livingtree/treellm/`
- ❌ Don't suppress errors with `as any` or `try/except: pass` in core logic
- ❌ Don't modify `.gitignore` patterns for `*.db` / `*.json` — they're intentional (data dir)

## TEST

```bash
pytest                              # all tests
pytest -v                           # verbose
pytest tests/test_parser.py         # single file
pytest -m unit                      # unit tests only
pytest -m livingtree                # livingtree core tests
```

Markers: `unit`, `integration`, `slow`, `ui`, `livingtree`, `provider`

## KEY FILES TO READ FOR CONTEXT

| Need | Read |
|------|------|
| System entry | `livingtree/main.py` |
| Boot + wiring | `livingtree/integration/hub.py` |
| Life cycle | `livingtree/dna/life_engine.py` |
| LLM routing | `livingtree/treellm/core.py` |
| Config system | `livingtree/config/settings.py` |
| TUI app | `livingtree/tui/app.py` |
| i18n | `livingtree/tui/i18n.py` |
