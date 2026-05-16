# CONVENTIONS.md — Code Conventions

> LivingTree AI Agent codebase standards. Python 3.13+, ~230K lines, ~700 modules.
> See also: [pyproject.toml](pyproject.toml) for tool config (ruff, mypy).

---

## 1. Imports

### 1.1 Direct imports only — no try/except ImportError

Every dependency is a hard requirement. No fallback imports:

```python
# CORRECT
import orjson
from scrapling.fetchers import StealthyFetcher
from loguru import logger

# WRONG — not used in this codebase
try:
    import orjson
except ImportError:
    import json as orjson
```

### 1.2 All imports at module level

No lazy imports inside functions. The only exception is circular-dependency avoidance
inside `_get_llm()`-style factory methods.

### 1.3 Import order

- `from __future__ import annotations` (always first)
- Standard library
- Third-party packages
- `livingtree` internal modules / livingtree.*

---

## 2. JSON Serialization — orjson Only

All JSON I/O uses `orjson` (12x faster than stdlib):

```python
import orjson
_json_dumps = lambda obj: orjson.dumps(obj, option=orjson.OPT_INDENT_2).decode()
_json_loads = orjson.loads
```

---

## 3. String Formatting

| Context | Style |
|---------|-------|
| Simple interpolation | Python f-string: `f"Hello {name}"` |
| Multi-line HTML / templates | Triple-quoted strings: `"""<div>...</div>"""` |
| Docstrings | Triple double-quotes (see Section 6) |

---

## 4. Logging — loguru

```python
from loguru import logger
logger.info("message")
logger.error("message")
```

No stdlib `logging` module used anywhere.

---

## 5. Async/await Throughout

The entire codebase is async-first:

```python
async def browse(self, url: str, task: str) -> BrowseResult:
    ...
```

Use `asyncio` for concurrency. Synchronous wrappers are rare and explicit.

---

## 6. Data Classes for Result Types

All structured return values use `@dataclass`:

```python
from dataclasses import dataclass, field

@dataclass
class BrowseResult:
    success: bool = False
    url: str = ""
    title: str = ""
    items: list[dict] = field(default_factory=list)
    count: int = 0
    method: str = ""
    elapsed_ms: float = 0.0
    iterations: int = 0
    error: str = ""

    def to_json(self) -> str:
        return _json_dumps(asdict(self))
```

---

## 7. Singleton Pattern

Global singletons use module-level `_instance` + `get_xxx()` function:

```python
_instance: Optional[CapabilityBus] = None

def get_capability_bus() -> CapabilityBus:
    global _instance
    if _instance is None:
        _instance = CapabilityBus()
    return _instance
```

No heavy DI frameworks. Simple, explicit, testable.

---

## 8. Type Hints Required

All function signatures and dataclass fields must have type annotations:

```python
from typing import Any, Optional

async def browse(self, url: str, task: str) -> BrowseResult:
    ...
```

Use `| None` syntax (Python 3.10+) rather than `Optional[X]` where possible, though
`Optional` is still common in existing code. `from __future__ import annotations` is
always present for PEP 604 support.

---

## 9. Bilingual Descriptions — Chinese + English

Module docstrings and key identifiers use dual-language descriptions:

```python
"""CapabilityBus — Unified interface for ALL digital lifeform capabilities.
能力总线 — 统一接口，用于所有数字生命体能力。
"""
```

Section separators use Unicode box-drawing characters:

```python
# ═══ Capability Category ═══════════════════════════════════════════
```

---

## 10. File Naming — snake_case

| Convention | Example |
|------------|---------|
| Python modules | `browser_agent.py`, `capability_bus.py` |
| Config / docs | `pyproject.toml`, `AGENTS.md`, `DESIGN.md` |
| Packages | `livingtree/`, `capability/`, `treellm/` |

---

## 11. Indentation — 4 Spaces

All Python files use 4-space indentation. No tabs. Enforced by ruff.

---

## 12. Line Length — 100 Characters

ruff `line-length = 100` (see pyproject.toml). Docstrings and comments may exceed
where readability benefits.

---

## 13. Lint & Format — ruff

```bash
ruff check .       # lint (E, F, W, I, N, UP, B, SIM, C4)
ruff format .      # format (double quotes, 4-space indent)
```

MyPy is configured but `disallow_untyped_defs = false` (gradually tightening).
