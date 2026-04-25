# CODEBUDDY.md This file provides guidance for WorkBuddy when working with code in this repository.

> 2026-04-26 | Python 3.11+ | PyQt6 | ~3400 files

## OVERVIEW

Desktop AI agent platform (Hermes) — PyQt6 GUI, clean 3-layer architecture. **Migration from legacy `core/` + `ui/` to `client/src/` is COMPLETE.**

Core capabilities: multi-agent system, P2P storage, digital twins, credit economy, e-commerce, browser automation, virtual conference, AmphiLoop bidirectional scheduling, PRISM context optimization.

## ARCHITECTURE (Big Picture)

### ✅ Migration Complete

The project has completed migration from legacy monolithic structure to clean 3-layer architecture:

- **`client/src/`**: Clean separation into `business/` (logic), `infrastructure/` (DB/config/network), `presentation/` (UI), and `shared/` (utilities). **This is where ALL code lives now.**

### Key Architectural Patterns

- **`client/src/business/`**: All business logic modules (~340+ files, organized by domain)
- **`client/src/presentation/`**: All UI components (panels/, components/, widgets/, dialogs/, modules/)
- **No legacy code**: `core/` and `ui/` directories have been completely removed
- **Import paths**: Use `from client.src.business.{domain}.{module}` or `from client.src.presentation.{subdir}.{module}`

### Module Categories (`client/src/business/` — ~340+ files)

Key modules include: `amphiloop/` (scheduling), `optimization/` (PRISM), `enterprise/` (P2P storage & task scheduling), `digital_twin/` (digital avatars), `credit_economy/` (points system), `decommerce/` (e-commerce), `living_tree_ai/` (300 files — voice, browser, meeting), `fusion_rag/` (multi-source retrieval), `knowledge_graph/`, `plugin_framework/`, `hermes_agent/`, `p2p_*` (P2P networking), `personal_mode/`, `ecc_*` (agent instincts/skills), `evolving_community/`, `intelligent_hints/`, `office_automation/`

### Module Categories (`client/src/presentation/` — ~200+ files)

- `panels/`: All UI panels (102+ files migrated from `ui/`)
- `components/`: Reusable UI components (cards, gauges, spinners, etc.)
- `widgets/`: Custom widgets
- `dialogs/`: Dialog windows
- `modules/`: Sub-modules (a2ui, connector, forum, intelligence, etc.)

### Server Layer

- `server/relay_server/` — FastAPI relay (api/, cluster/, database/)
- `server/tracker_server.py` — P2P node tracker

### Other Key Areas

- `app/` — Standalone enterprise application
- `packages/` — Shared libraries (`living_tree_naming/`, `shared/`)
- `mobile/` — PWA/mobile support (main.py, screens, adaptive_layout, pwa_integration)
- `config/` — Configuration files

## STRUCTURE

```
root/
├── client/src/              # ✅ ALL code lives here now
│   ├── main.py              # PyQt6 entry → HomePage
│   ├── business/            # Business logic (~340+ files)
│   │   ├── amphiloop/
│   │   ├── optimization/
│   │   ├── enterprise/
│   │   ├── digital_twin/
│   │   ├── credit_economy/
│   │   ├── decommerce/
│   │   ├── living_tree_ai/
│   │   ├── fusion_rag/
│   │   ├── knowledge_graph/
│   │   ├── plugin_framework/
│   │   ├── hermes_agent/
│   │   ├── p2p_*/
│   │   ├── personal_mode/
│   │   ├── ecc_*/
│   │   ├── evolving_community/
│   │   ├── intelligent_hints/
│   │   ├── office_automation/
│   │   ├── config.py           # UnifiedConfig compatibility layer
│   │   ├── nanochat_config.py # NanochatConfig (dataclass-based)
│   │   ├── optimal_config.py   # OptimalConfig
│   │   └── ...                # ~300+ more modules
│   ├── infrastructure/      # DB (v1-v14), config, network, model, storage
│   ├── presentation/        # UI (~200+ files)
│   │   ├── panels/          # All panels (102+ files)
│   │   ├── components/      # Reusable components
│   │   ├── widgets/        # Custom widgets
│   │   ├── dialogs/        # Dialog windows
│   │   ├── modules/        # Sub-modules (a2ui, connector, etc.)
│   │   └── ...
│   └── shared/              # Shared utilities
├── server/                  # Server layer
│   ├── relay_server/        # FastAPI relay (api/, cluster/, database/)
│   └── tracker_server.py   # P2P tracker
├── app/                     # Standalone enterprise app
├── mobile/                  # PWA/mobile (7 files)
├── packages/                # Shared libs (living_tree_naming/, shared/)
├── config/                  # Config files
├── main.py                  # CLI: client|relay|tracker|app|all
├── run.bat                  # Windows quick start (default: client)
├── pyproject.toml           # setuptools build, livingtree CLI
├── pytest.ini               # markers: unit, integration, slow, ui
└── tests/                   # Real tests (1 file: test_provider.py)
```

## RUN COMMANDS

### Launch

```powershell
python main.py client           # desktop client (default)
python main.py relay            # relay server
python main.py tracker          # P2P tracker
python main.py app              # enterprise app
python main.py all              # relay + tracker + client
python -m livingtree client     # via CLI entry point
```

### Install (editable, order matters)

```powershell
pip install -e ./client
pip install -e ./server/relay_server
pip install -e ./app
```

### Test

```powershell
pytest                              # all tests
pytest tests/test_provider.py       # single test file
pytest -m unit                      # unit tests only
pytest -m integration               # integration tests only
pytest -m slow --timeout 120        # slow tests
pytest -m ui                        # UI tests
pytest -v                           # verbose output
pytest --tb=short                   # short traceback (default)
```

### CLI

```powershell
# livingtree CLI (installed via pyproject.toml)
livingtree --help
```

## CONVENTIONS

- **All new code**: `client/src/business/` (logic) or `client/src/presentation/` (UI) — **NEVER** `core/` or `ui/`
- **Import**: `from client.src.business.{domain}.{module}` (business logic) or `from client.src.presentation.{subdir}.{module}` (UI)
- **Windows**: Use `;` not `&&` for command chaining
- **No lint/typecheck/formatter**: Manual quality control only
- **Database migrations**: `client/src/infrastructure/database/` (v1-v14)
- **Config**: `client/src/business/config.py` (UnifiedConfig compatibility layer) or `client/src/business/nanochat_config.py` (NanochatConfig)
- **Tests**: `tests/` directory (only 1 real test file — root `test_*.py` files are stale)

## QUICK LOOKUP

| Task                     | Go here                                 |
| ------------------------ | ---------------------------------------- |
| New business logic       | `client/src/business/`                   |
| New UI panel            | `client/src/presentation/panels/`        |
| UI components           | `client/src/presentation/components/`     |
| UI widgets             | `client/src/presentation/widgets/`       |
| DB migrations          | `client/src/infrastructure/database/`    |
| Config                | `client/src/business/config.py`          |
| Server API            | `server/relay_server/`                   |
| Mobile/PWA            | `mobile/`                                |
| P2P networking        | `client/src/business/p2p_*`             |
| Agent framework        | `client/src/business/hermes_agent/`       |
| Skill system           | `client/src/business/hermes_agent/`       |
| Knowledge graph        | `client/src/business/knowledge_graph/`    |

## ANTI-PATTERNS

- ❌ Don't write to `core/` or `ui/` — **these directories have been deleted**
- ❌ Don't use `from core.xxx` or `from ui.xxx` imports — **use `from client.src.business.xxx` or `from client.src.presentation.xxx`**
- ❌ Don't open huge `__init__.py` (99k+ lines) — read sub-files instead
- ❌ Root `test_*.py` (~80 stale files) — real tests in `tests/` (1 file)
- ❌ Install in wrong order: client → relay_server → app
- ❌ No CI/CD — no `&&` on Windows, use PowerShell `;`
- ❌ Don't assume legacy modules are dead — they've been migrated to `client/src/business/`

## CONFIGURATION SYSTEM

### NanochatConfig (New, Preferred)

```python
# Preferred: Direct attribute access
from client.src.business.nanochat_config import config

url = config.ollama.url
timeout = config.timeouts.default
max_retries = config.retries.default
```

### UnifiedConfig (Legacy Compatibility Layer)

```python
# Still works, but deprecated
from client.src.business.config import UnifiedConfig

config = UnifiedConfig.get_instance()
url = config.get("endpoints.ollama.url")
```

**Migration**: New code should use `NanochatConfig` (dataclass-based, type-safe, 10x faster).
