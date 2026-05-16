# DESIGN.md — Architecture & Design Decisions

> LivingTree AI Agent v2.5 — Web Tool Chain Architecture
> See also: [AGENTS.md](AGENTS.md) for the tool chain reference card.

---

## 1. Web Tool Chain (v2.5) — LLM as Router

```
User Input → TreeLLM.chat() →
  LLM receives tool list in system prompt
  LLM autonomously chooses which tool to call based on intent
  Result → injected into LLM context → final answer
```

**Key design decision**: No centralized tool dispatcher. The LLM itself is the router.
It sees the full available tool list in its system prompt and decides which tool(s) to
invoke based on the user's intent. This avoids the fragility of hard-coded dispatch rules
and lets the LLM reason about tool selection dynamically.

### 1.1 Eight Tools in Scope

| # | Tool | Module | Purpose |
|---|------|--------|---------|
| 1 | `api_search` | `capability_bus.py → api_map` | Discover matching REST API endpoints by keyword |
| 2 | `api_call` | `treellm/api_map.py` | Call a registered API (28 REST/JSON endpoints) |
| 3 | `web_search` | `execution/react_executor.py` | Multi-engine internet search (MCP → Spark → Bing → DDG) |
| 4 | `web_fetch` | `capability_bus.py → Scrapling Fetcher` | Static HTTP GET with TLS impersonation, stealth headers |
| 5 | `browser_browse` | `capability/browser_agent.py` | Playwright + LLM: JS render, type, click, extract |
| 6 | `browser_screenshot` | `capability/browser_agent.py` | Page screenshot → base64 for LLM visual analysis |
| 7 | `browser_session_open` | `capability/browser_agent.py` | Open persistent browser session (reuse across calls) |
| 8 | `browser_session_close` | `capability/browser_agent.py` | Close browser session |
| 9 | `browser_session_list` | `capability/browser_agent.py` | List active sessions |

### 1.2 Tool Call XML Format

The LLM emits tool invocations in a structured XML-like format understood by
`execution/react_executor.py`. Each call carries a tool name, parameters, and an
optional `think` block for reasoning trace.

### 1.3 Entry Point: `TreeLLM.chat()`

`livingtree/treellm/core.py` — `TreeLLM` is the multi-provider LLM engine (28 providers
from 18 base classes). `TreeLLM.chat()` is the single entry point for all LLM interactions,
including tool-augmented ones.

---

## 2. Scrapling Integration — Anti-Bot & JS Render

The web tool chain integrates **Scrapling** (Python stealth scraping library) for two
distinct purposes:

### 2.1 Static Fetcher (`StealthyFetcher`)

- **Module**: `livingtree/treellm/capability_bus.py`
- **Class**: `StealthyFetcher` (from `scrapling.fetchers`)
- **Purpose**: Static HTTP GET with TLS impersonation (Chromium fingerprint), stealth
  headers, and cookie persistence to bypass Cloudflare, Turnstile, canvas fingerprinting,
  and WebRTC leak detection.
- **Used by**: `web_fetch` tool

### 2.2 Dynamic Fetcher (`DynamicFetcher`)

- **Module**: `livingtree/capability/browser_agent.py`
- **Class**: `DynamicFetcher` (from `scrapling.fetchers`)
- **Purpose**: Chromium-backed JS rendering for pages that require JavaScript execution.
  Supports retries, ad blocking, resource disabling, and scroll actions.

### 2.3 Fetcher Import Pattern

All imports are **hard** — no `try/except ImportError` fallback:

```python
from scrapling.fetchers import Fetcher, DynamicFetcher, StealthyFetcher
from scrapling.parser import Selector
```

---

## 3. ARIA Tree Extraction — ~2KB vs. 30KB Raw HTML

The `browser_browse` tool extracts the **ARIA accessibility tree** instead of raw HTML
for LLM consumption:

| Approach | Size | LLM Token Cost |
|----------|------|----------------|
| Raw HTML | ~30 KB | ~7,500 tokens |
| ARIA Tree | ~2 KB | ~500 tokens |

The ARIA tree provides structured, semantic page state (roles, labels, values) with 15x
fewer tokens, making it practical to fit page context in the LLM's context window without
truncation.

**Implementation**: `livingtree/capability/browser_agent.py` — `_extract_aria_tree()` method.

Scrapling extraction toolkit (`_direct_extract`):
```
css/xpath selectors → find_by_text → find_similar → find_ancestor → find_by_regex
get_all_text → extract_first → text.clean → generate_css_selector → download links
Adaptive: auto_save + adaptive survives page structure changes
```

---

## 4. JSON Serialization — orjson 12x

All JSON input/output uses `orjson` for 12x faster serialization compared to stdlib `json`:

```python
import orjson
_json_dumps = lambda obj: orjson.dumps(obj, option=orjson.OPT_INDENT_2).decode()
_json_loads = orjson.loads
```

This is critical because tool results (especially browser screenshots and ARIA trees) are
serialized/deserialized frequently in the LLM context pipeline.

---

## 5. API Map — 28 REST Endpoints

`livingtree/treellm/api_map.py` registers 28 REST/JSON API endpoints covering:
weather, maps, translation, geocoding, IP lookup, currency conversion, and more.

The `api_search` tool queries this map by keyword and returns matching endpoint
descriptors. The `api_call` tool then executes a selected endpoint with user-provided
parameters.

---

## 6. Skill System — 10 Security Fixes Applied

The Three-SKILL system (`skill_discovery.py`, `skill_factory.py`, `skill_buckets.py`)
allows the agent to autonomously discover, create, and organize skills. After an audit,
**10 security fixes** were applied:

- Input sanitization on skill parameters
- Sandboxed execution boundaries
- Permission gating for destructive skills
- Rate limiting on skill factory
- Skill source verification
- Prevent recursive self-modification loops
- Output validation before downstream consumption
- Scope isolation between skill buckets
- Audit logging for all skill creations
- Kill switch for runaway skill execution

---

## 7. Encrypted Secrets Vault — 50 Entries

The secrets vault stores ~50 encrypted values (API keys, tokens, service credentials)
using `cryptography` (Fernet symmetric encryption). Vault is loaded at startup by the
config subsystem and never exposes raw values in logs or LLM context.

**Module**: `livingtree/config/` — vault integration.

---

## 8. All Imports Are Hard

Every package import in the codebase uses direct `import` statements. There are no
`try/except ImportError` fallback patterns. This ensures:

- Fast-fail at import time (no silent degradation)
- Clear dependency requirements
- No hidden missing-package bugs
