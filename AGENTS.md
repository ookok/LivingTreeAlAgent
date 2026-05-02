# CODEBUDDY.md This file provides guidance for WorkBuddy when working with code in this repository.

> 2026-05-02 | Python 3.11+ | PyQt6 | ~3400 files

## OVERVIEW

Desktop AI agent platform (LivingTree) — PyQt6 GUI, 3-layer clean architecture with new `livingtree/` core package.

Core capabilities: multi-agent system, P2P storage, digital twins, credit economy, e-commerce, browser automation, virtual conference, AmphiLoop bidirectional scheduling, PRISM context optimization, World Model prediction, Self-Evolution.

## ARCHITECTURE — New (livingtree/)

The project has been restructured into a clean `livingtree/` package — a **Digital Lifeform** with a TaskChain pipeline:

```
Perceive → Cognize → Plan → Execute → Reflect → Evolve
```

### Key Packages

- **`livingtree/`**: The new core package. All new backend code goes here.
  - `livingtree/core/` — Core engine (LifeEngine + cells)
    - `model/` — Unified Model Router (3-tier: Local/Edge/Cloud)
    - `intent/` — Intent Parser + multi-turn tracker
    - `memory/` — Unified MemoryStore (VectorDB + GraphDB + Sessions)
    - `planning/` — TaskPlanner + Decomposer(CoT) + Scheduler
    - `skills/` — SkillMatcher + Loader + Repository
    - `tools/` — ToolRegistry + Dispatcher + builtins
    - `plugins/` — PluginManager + Sandbox
    - `context/` — ContextAssembler + Compressor
    - `evolution/` — EvolutionEngine (Reflect→Identify→Experiment→Validate→Adopt)
    - `world_model/` — StatePredictor + OutcomeSimulator
    - `observability/` — StructuredLogger + RequestTracer + MetricsCollector
  - `livingtree/infrastructure/` — Config(LTAIConfig), EventBus, DB, WebSocket, Security
  - `livingtree/adapters/` — MCP, API Gateway, Providers (Ollama/OpenAI)
  - `livingtree/frontend_bridge/` — FrontendChannel + BridgeAPI (connect Vue frontend)
  - `livingtree/server/` — Relay + Tracker (streamlined)

### Legacy Packages (to be phased out)

- **`client/src/business/`**: Legacy business logic (~340+ files). Modules being migrated to `livingtree/core/`.
- **`client/src/presentation/`**: PyQt6 UI components. Still active for desktop GUI.
- **`client/src/frontend/`**: Vue 3 frontend (the preserved frontend). Connected via `livingtree/frontend_bridge/`.

### Server Layer

- `server/relay_server/` — FastAPI relay (legacy, migrating to `livingtree/server/relay/`)
- `server/tracker_server.py` — P2P node tracker (legacy, migrating to `livingtree/server/tracker/`)

## STRUCTURE

```
root/
├── livingtree/                    # ✅ NEW — All new backend code
│   ├── core/
│   │   ├── life_engine.py         # LifeEngine — central dispatcher
│   │   ├── model/router.py        # UnifiedModelRouter
│   │   ├── intent/parser.py       # IntentParser + IntentTracker
│   │   ├── memory/store.py        # MemoryStore (VectorDB + GraphDB + Sessions)
│   │   ├── planning/decomposer.py # TaskPlanner + CoT Decomposer
│   │   ├── skills/matcher.py      # SkillMatcher + SkillLoader
│   │   ├── tools/registry.py      # ToolRegistry + Dispatcher
│   │   ├── plugins/manager.py     # PluginManager + Sandbox
│   │   ├── context/assembler.py   # ContextAssembler + Compressor
│   │   ├── evolution/reflection.py # EvolutionEngine
│   │   ├── world_model/predictor.py # StatePredictor + Simulator
│   │   └── observability/         # Logger + Tracer + Metrics
│   ├── infrastructure/            # Config + EventBus + DB + WS + Security
│   ├── adapters/                  # MCP + API Gateway + Providers
│   ├── frontend_bridge/           # FrontendChannel + BridgeAPI
│   └── server/                    # Relay + Tracker
│
├── client/src/                    # Legacy (being phased out)
│   ├── main.py                    # PyQt6 entry
│   ├── business/                  # Legacy business logic
│   ├── frontend/                   # Vue 3 frontend (preserved)
│   └── presentation/              # PyQt6 UI components
│
├── server/                        # Legacy server (migrating)
│   └── relay_server/
├── app/                           # Standalone enterprise app
├── mobile/                        # PWA/mobile
├── config/                        # YAML config files
├── main.py                        # CLI entry: livingtree client|relay|...
├── pyproject.toml                 # setuptools build
└── tests/                         # Test files
```

## RUN COMMANDS

### Launch

```powershell
python main.py client           # desktop client (default)
python main.py relay            # relay server
python main.py tracker          # P2P tracker
python main.py app              # enterprise app

# New livingtree entry points
python -m livingtree client     # via CLI entry point
python -m livingtree server     # relay + tracker
```

### Quick Test

```powershell
# Test the new livingtree core
python -c "from livingtree.core.life_engine import LifeEngine; e = LifeEngine(); r = e.handle_request('hello'); print(r.text)"
```

### Install (editable)

```powershell
pip install -e ./client
pip install -e ./server/relay_server
```

### Test

```powershell
pytest                              # all tests
pytest tests/test_provider.py       # single test file
pytest -v                           # verbose output
```

## CONVENTIONS

- **New backend code**: `livingtree/core/` (logic), `livingtree/infrastructure/` (config/db), `livingtree/adapters/` (external)
- **Import (new)**: `from livingtree.core.model.router import UnifiedModelRouter`
- **Import (new)**: `from livingtree.infrastructure.config import get_config`
- **Import (new)**: `from livingtree.core.observability.logger import get_logger`
- **Import (legacy)**: `from client.src.business.{module}` (for code not yet migrated)
- **Windows**: Use `;` not `&&` for command chaining
- **Config**: `livingtree/infrastructure/config.py` — LTAIConfig (dataclass-based, unifies NanochatConfig + OptimalConfig + UnifiedConfig)
- **Tests**: `tests/` directory

## QUICK LOOKUP

| Task                     | Go here                                     |
| ------------------------ | -------------------------------------------- |
| New business logic       | `livingtree/core/`                           |
| Config                  | `livingtree/infrastructure/config.py`        |
| Event bus               | `livingtree/infrastructure/event_bus.py`     |
| Model routing           | `livingtree/core/model/router.py`            |
| Intent parsing          | `livingtree/core/intent/parser.py`           |
| Memory storage          | `livingtree/core/memory/store.py`            |
| Task planning           | `livingtree/core/planning/decomposer.py`     |
| Skill matching          | `livingtree/core/skills/matcher.py`          |
| Tool registry           | `livingtree/core/tools/registry.py`          |
| Plugin management       | `livingtree/core/plugins/manager.py`         |
| Context assembly        | `livingtree/core/context/assembler.py`       |
| Self-evolution          | `livingtree/core/evolution/reflection.py`    |
| World model             | `livingtree/core/world_model/predictor.py`   |
| Observability           | `livingtree/core/observability/`             |
| MCP protocol            | `livingtree/adapters/mcp/manager.py`         |
| API gateway             | `livingtree/adapters/api/gateway.py`         |
| Model providers         | `livingtree/adapters/providers/ollama.py`    |
| Frontend bridge         | `livingtree/frontend_bridge/channel.py`      |
| Database                | `livingtree/infrastructure/database.py`      |
| WebSocket               | `livingtree/infrastructure/websocket.py`     |
| Security                | `livingtree/infrastructure/security.py`      |
| Central dispatcher      | `livingtree/core/life_engine.py`             |
| Vue frontend            | `client/src/frontend/`                       |
| PyQt6 UI                | `client/src/presentation/`                   |
| Server API              | `server/relay_server/`                       |

## ANTI-PATTERNS

- ❌ Don't write new backend code to `client/src/business/` — **use `livingtree/core/`**
- ❌ Don't use `from client.src.business.global_model_router` — **use `from livingtree.core.model.router import get_model_router`**
- ❌ Don't create duplicate config systems — **use `livingtree/infrastructure/config.py` (LTAIConfig)**
- ❌ Don't open huge `__init__.py` files
- ❌ No CI/CD — no `&&` on Windows, use PowerShell `;`

## CONFIGURATION SYSTEM

### LTAIConfig (New, Unified)

```python
from livingtree.infrastructure.config import config, get_config

# Dataclass-style access
url = config.ollama.base_url
timeout = config.timeouts.default
max_retries = config.retries.default

# Compute optimal params for task complexity
optimal = config.compute_optimal(depth=5)

# Reload from YAML
config = get_config(reload=True)
```
