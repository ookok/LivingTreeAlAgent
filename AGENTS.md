# CODEBUDDY.md This file provides guidance for WorkBuddy when working with code in this repository.

> 2026-04-22 | Python 3.11+ | PyQt6 | ~3400 files

## OVERVIEW

Desktop AI agent platform (Hermes) — PyQt6 GUI, layered architecture. Two parallel codebases: new `client/src/` (3-layer migration) and legacy `core/` + `ui/`. Both still actively used during migration.

Core capabilities: multi-agent system, P2P storage, digital twins, credit economy, e-commerce, browser automation, virtual conference, AmphiLoop bidirectional scheduling, PRISM context optimization.

## ARCHITECTURE (Big Picture)

### Dual Codebase Strategy
The project is in active migration from a legacy monolithic structure to a clean 3-layer architecture:

- **New codebase** (`client/src/`): Clean separation into `business/` (logic), `infrastructure/` (DB/config/network), `presentation/` (UI), and `shared/` (utilities). This is where all new code belongs.
- **Legacy codebase** (`core/` + `ui/`): ~300+ modules in a flat structure, still actively used and referenced. Do not delete — both import paths coexist during migration.

### Key Architectural Patterns
- **Big `__init__.py` monoliths**: Some legacy modules (e.g., `personal_mode`, `universal_asset_ecosystem`) use `__init__.py` as entry point (99k+ lines). Read sub-files instead.
- **Legacy `core/__init__.py` exports**: `HermesAgent`, `OllamaClient`, `SessionDB`, `MemoryManager`, `ToolRegistry` — still actively imported by existing code.
- **Import paths**: Both `from core.xxx` and `from client.src.business.xxx` work. Prefer new path for new code.

### Module Categories (Legacy `core/` — ~243 dirs)
Key modules include: `amphiloop/` (scheduling), `optimization/` (PRISM), `enterprise/` (P2P storage & task scheduling), `digital_twin/` (digital avatars), `credit_economy/` (points system), `decommerce/` (e-commerce), `living_tree_ai/` (300 files — voice, browser, meeting), `fusion_rag/` (multi-source retrieval), `knowledge_graph/`, `plugin_framework/`, `hermes_agent/`, `p2p_*` (P2P networking), `personal_mode/`, `ecc_*` (agent instincts/skills), `evolving_community/`, `intelligent_hints/`, `office_automation/`

### Module Categories (New `client/src/business/` — ~340 files)
Mirrors legacy structure — all legacy modules have been ported here. New code goes here.

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
├── client/src/              # ✅ New code (3-layer migration target)
│   ├── main.py              # PyQt6 entry → HomePage
│   ├── business/            # Business logic (~340 files, mirrors core/)
│   ├── infrastructure/      # DB (v1-v14), config, network, model, storage
│   ├── presentation/        # UI (panels/ 186 files, components/, widgets/)
│   └── shared/              # Shared utilities
├── core/                    # ⚠️ Legacy (~243 dirs, still actively used)
│   ├── living_tree_ai/      # 300 files — voice, browser, meeting, etc.
│   ├── amphiloop/           # Bidirectional scheduling engine
│   ├── optimization/        # PRISM optimizer, Shannon entropy
│   ├── enterprise/          # P2P storage & task scheduling (11 files)
│   ├── digital_twin/        # Digital avatar system
│   ├── credit_economy/      # Points/credits system
│   ├── decommerce/          # E-commerce (22 files)
│   ├── fusion_rag/          # Multi-source retrieval (28 files)
│   ├── knowledge_graph/     # Knowledge graph (16 files)
│   ├── plugin_framework/    # Plugin system (16 files)
│   ├── hermes_agent/        # Agent framework
│   ├── p2p_*/               # P2P networking modules
│   ├── ecc_*/               # Agent instincts/skills
│   ├── evolving_community/  # Community system (15 files)
│   ├── personal_mode/       # Personal mode (99k+ line __init__.py)
│   └── ...                  # ~200 more modules
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

- **New code**: `client/src/business/` (never `core/`), `client/src/presentation/` (never `ui/`)
- **Import**: `from client.src.business.{domain}.{module}` (new) — `from core.xxx` still works but deprecated
- **Windows**: Use `;` not `&&` for command chaining
- **No lint/typecheck/formatter**: Manual quality control only
- **Database migrations**: `client/src/infrastructure/database/` (v1-v14)
- **Config**: `config/` directory
- **Tests**: `tests/` directory (only 1 real test file — root `test_*.py` files are stale)
- **Big `__init__.py`**: Avoid — read sub-files instead. Some legacy modules use it as monolith entry.

## QUICK LOOKUP

| Task | Go here |
|------|--|
| New business logic | `client/src/business/` |
| New UI panel | `client/src/presentation/panels/` |
| UI components | `client/src/presentation/components/` or `widgets/` |
| DB migrations | `client/src/infrastructure/database/` (v1-v14) |
| Legacy business | `core/` (~243 modules) |
| Model store | `core/model_hub/`, `core/model_store/` |
| Server API | `server/relay_server/` |
| Config | `config/` |
| Mobile/PWA | `mobile/` |
| P2P networking | `core/p2p_*` or `client/src/business/p2p_*` |
| Agent framework | `core/hermes_agent/` or `client/src/business/hermes_agent/` |
| Skill system | `core/hermes_agent/` or `client/src/business/hermes_agent/` |
| Knowledge graph | `core/knowledge_graph/` or `client/src/business/knowledge_graph/` |

## ANTI-PATTERNS

- ❌ Don't write to `core/` or `ui/` — both are legacy. Use `client/src/`
- ❌ Don't open huge `__init__.py` (99k+ lines) — read sub-files instead
- ❌ Root `test_*.py` (~80 stale files) — real tests in `tests/` (1 file)
- ❌ Install in wrong order: client → relay_server → app
- ❌ Both import paths coexist (`from core.xxx` still works) — don't assume old imports are dead
- ❌ No CI/CD — no `&&` on Windows, use PowerShell `;`
- ❌ Don't assume legacy modules are dead — they're still actively imported
- ❌ Don't open `core/__init__.py` — it exports key symbols still in use
