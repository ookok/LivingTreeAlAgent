# CONTEXT.md — Project Background

> LivingTree AI Agent v5.5 — 数字生命体 (Digital Lifeform)
> See also: [README.md](README.md), [AGENTS.md](AGENTS.md)

---

## 1. What Is LivingTree?

LivingTree is a **full-stack AI agent platform** modeled as a digital lifeform with
biological architecture (organs, consciousness, emotions, evolution). It is not a
chatbot, not a code assistant, not a RAG framework — it is a self-evolving autonomous
system.

| Metric | Value |
|--------|-------|
| Python modules | ~700 |
| Total lines | ~230,000 |
| Top-level organs | 22 |
| Applied research papers | 19 |
| Test suite | 615 passing |

Version: **5.5** (core) / **2.5** (web tool chain)

---

## 2. Core Subsystems (14+ Domains)

| Domain | Directory | Key Modules |
|--------|-----------|-------------|
| **CLI / TUI** | `livingtree/`, `main.py` | `desktop_shell.py`, `tui/`, `livingtree/__main__.py` |
| **TreeLLM** | `livingtree/treellm/` | 28 providers from 18 bases, 4-layer election, task vector geometry, depth attention, semantic cache, connection pool |
| **Config** | `livingtree/config/` | 16-provider cross-validation, encrypted secrets vault (50 entries) |
| **DNA / Bio** | `livingtree/dna/` | 50+ modules: consciousness emergence, self-conditioning, Shesha multi-head, emotional decision |
| **Economy** | `livingtree/economy/` | Metabolism, thermodynamic budget, inverse RL, spatial rewards |
| **Knowledge** | `livingtree/knowledge/` | ContextWiki, RDF retrieval (10 shapes), reasoning reranker, AgenticRAG |
| **API** | `livingtree/api/` | FastAPI + HTMX, 90+ endpoints, 5 WebSockets |
| **Execution** | `livingtree/execution/` | Task tree SSE, habit compilation, recursive decomposition, self-healing |
| **Frontend** | `livingtree/templates/` | Tailwind CSS admin panel, living/canvas/awakening/admin/task_tree |
| **MCP** | `livingtree/mcp/` | MCP host client, tool bridges |
| **Network** | `livingtree/network/` | Scinet reinforcement, distributed consciousness, 6-layer failover, P2P swarm evolution |
| **Core** | `livingtree/core/` | Autonomous loop, VIGIL diagnostics, connection pool |
| **Reasoning** | `livingtree/reasoning/` | Task vector geometry, depth attention, chain-of-thought |
| **Capability** | `livingtree/capability/` | 94 modules: tools, skills, browser agent, document engines |

---

## 3. TreeLLM — Multi-Provider LLM Engine

**Entry point**: `livingtree/treellm/core.py` → `TreeLLM.chat()`

- **28 providers** from 18 base classes (OpenAI, Anthropic, Google, local Ollama, etc.)
- 4-layer model election (`election_bus.py`, `holistic_election.py`)
- Predictive routing with bandit learning (`bandit_router.py`, `predictive_router.py`)
- Semantic + hierarchical caching (`semantic_cache.py`, `cache_hierarchy.py`)
- Token circuit breakers and budget management (`token_circuit_breaker.py`, `reasoning_budget.py`)
- Provider round-robin with health prediction (`provider_round_robin.py`, `health_predictor.py`)

---

## 4. CapabilityBus — Unified Tool Registration

**Module**: `livingtree/treellm/capability_bus.py`

Single entry point for all capabilities (tools, skills, MCP, roles, users, LLM, VFS).
Auto-discovers and registers from existing registries.

```python
bus = get_capability_bus()
result = await bus.invoke("tool:web_search", query="AI papers")
result = await bus.invoke("skill:tabular_reason", data={...})
```

---

## 5. Web Tool Chain (v2.5)

| Tool | Purpose |
|------|---------|
| `api_search` / `api_call` | 28 REST API endpoints (weather, maps, translate) |
| `web_search` | Multi-engine search (MCP → Spark → Bing → DDG) |
| `web_fetch` | Scrapling StealthyFetcher — static HTTP GET with anti-bot |
| `browser_browse` | Playwright + LLM — JS render, type, click, ARIA extraction |
| `browser_screenshot` | Page screenshot → base64 for LLM vision |
| `browser_session_*` | Persistent browser session management (open/close/list) |

**Key**: LLM is the router. No centralized dispatcher. The LLM decides which tool to call.

---

## 6. Self-Evolution — Three-SKILL System

| Module | Purpose |
|--------|---------|
| `skill_discovery.py` | Autonomous discovery of new skills from usage patterns |
| `skill_factory.py` | Create new skills from discovered patterns |
| `skill_buckets.py` | Organize skills into domain buckets |

After security audit: **10 security fixes** applied (input sanitization, sandboxing,
permission gating, rate limiting, source verification, anti-recursion, output validation,
scope isolation, audit logging, kill switch).

---

## 7. Frontend

Tailwind CSS admin panel with 5 pages:

| Route | Page |
|-------|------|
| `/tree/living` | Lifeform interaction |
| `/tree/canvas` | Canvas visualization |
| `/tree/task` | Task decomposition tree (SSE real-time) |
| `/tree/admin` | Admin console (incl. Scinet) |
| `/tree/awakening` | Awakening animation |

---

## 8. Applied Research (19 Papers)

Key papers landed in production modules:
- **Mumford Agency** (2605.02810) → `shesha_heads.py`, `play_engine.py`
- **MemPO** (2603.00680) → `memory_policy.py`, `credit_assigner.py`
- **Task Vector Geometry** (2605.03780) → `task_vector_geometry.py`
- **VIGIL** (2512.07094) → `autonomous_core.py`, `vigil.py`
- **MemReranker** (2605.06132) → `reasoning_reranker.py`

---

## 9. Current Status — v2.5 Web Chain

- StealthyFetcher ready (anti-bot: Cloudflare, Turnstile, canvas, WebRTC)
- Skill system hardened (10 security fixes)
- Encrypted secrets vault (50 entries)
- 28 API endpoints registered
- 615 tests passing
- Python 3.13+ required
