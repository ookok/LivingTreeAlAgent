---
name: LivingTree
version: 1.0.0
description: Dark data-dashboard aesthetic with biophilic green accent. Command-center feel, minimal chrome, high information density.
colors:
  primary: "#6c8"
  primary-on: "#0a0a0f"
  on-primary: "#ffffff"
  bg: "#0a0a0f"
  panel: "#12121a"
  border: "#1e1e2e"
  text: "#c8c8d4"
  dim: "#667"
  warn: "#e8a030"
  err: "#e05050"
  light-bg: "#f5f5f5"
  light-text: "#333"
  light-dim: "#999"
typography:
  fontFamily: system-ui, -apple-system, "Segoe UI", sans-serif
  fontMono: "JetBrains Mono", "Fira Code", monospace
  h1: { fontFamily: inherit, fontSize: 18px, fontWeight: 700 }
  h2: { fontFamily: inherit, fontSize: 14px, fontWeight: 600 }
  body: { fontFamily: inherit, fontSize: 12px, fontWeight: 400 }
  code: { fontFamily: "JetBrains Mono", fontSize: 11px }
  label: { fontFamily: inherit, fontSize: 10px, fontWeight: 400 }
rounded:
  sm: 4px
  md: 6px
  lg: 8px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
components:
  card: { backgroundColor: "{colors.panel}", rounded: "{rounded.lg}", padding: 12px, borderColor: "{colors.border}" }
  button-primary: { backgroundColor: "{colors.primary}", textColor: "{colors.on-primary}", rounded: "{rounded.md}", padding: "8px 16px" }
  button-secondary: { backgroundColor: "{colors.panel}", textColor: "{colors.text}", rounded: "{rounded.md}", borderColor: "{colors.border}" }
  input: { backgroundColor: "{colors.panel}", textColor: "{colors.text}", rounded: "{rounded.sm}", borderColor: "{colors.border}" }
  tooltip: { backgroundColor: "{colors.panel}", textColor: "{colors.dim}", fontSize: 10px }
  status-active: { color: "{colors.primary}" }
  status-error: { color: "{colors.err}" }
  status-warning: { color: "{colors.warn}" }
---

# DESIGN.md — Architecture & Design Decisions

> LivingTree AI Agent v2.5 — Google DESIGN.md format
> Validated via `npx @google/design.md lint DESIGN.md`
> See also: [AGENTS.md](AGENTS.md) for the tool chain reference card, [CONVENTIONS.md](CONVENTIONS.md) for code conventions

---

## Overview

Dark command-center aesthetic with a biophilic green accent (`#6c8`). The UI evokes a data dashboard — high information density, minimal chrome, monospace code areas. Focus is on content, not decoration.

## Colors

Three-layer hierarchy:
- **Primary (`#6c8`)** — accent green. CTA buttons, active states, success indicators. The only saturated color.
- **Neutrals (`#0a0a0f` → `#c8c8d4`)** — bg → panel → border → text → dim. Dark slate gradient.
- **Alert colors** — warn (`#e8a030`) and err (`#e05050`) for status indicators only.

Light mode inverts the neutral scale (`#f5f5f5` bg, `#333` text).

## Layout & Spacing

Grid-based admin console with auto-fill columns (`grid-template-columns: repeat(auto-fill, minmax(200px, 1fr))`). Cards use `{spacing.md}` padding. Nav buttons use `{spacing.sm}` gaps.

## Shapes

All UI elements use `{rounded.sm}` to `{rounded.md}`. No sharp corners. Cards and panels use `{rounded.lg}`.

## Components

| Component | Token |
|-----------|-------|
| Card | `{components.card}` |
| Primary Button | `{components.button-primary}` |
| Secondary Button | `{components.button-secondary}` |
| Input/Textarea | `{components.input}` |

## Do's and Don'ts

- ✅ Use `var(--accent)` for interactive elements and primary CTA
- ✅ Use `var(--dim)` for secondary info, timestamps, metadata
- ✅ Use `var(--err)` only for destructive actions and error states
- ✅ Prefer Tailwind utility classes over custom CSS
- ❌ Don't add new color tokens without updating this file
- ❌ Don't use raw hex values in HTML — use CSS variables

---

## 1. Web Tool Chain (v2.5) — LLM as Router

```
User Input → TreeLLM.chat() →
  LLM receives tool list in system prompt
  LLM autonomously chooses which tool to call based on intent
  Result → injected into LLM context → final answer
```

| Tool | Module | Purpose |
|------|--------|---------|
| `api_search` | `capability_bus.py → api_map` | Discover matching APIs by keyword |
| `api_call` | `treellm/api_map.py` | 28 REST/JSON APIs (weather, maps, translate, etc.) |
| `web_search` | `execution/react_executor.py` | Multi-engine: Parallel MCP → SparkSearch → Bing → DDG |
| `web_fetch` | `capability_bus.py → Scrapling Fetcher` | Static HTTP GET (TLS impersonation, stealth headers) |
| `browser_browse` | `capability/browser_agent.py` | Playwright + LLM: JS render, type, click, extract (ARIA tree, ~2KB per page) |
| `browser_screenshot` | `capability/browser_agent.py` | Take page screenshot, returns base64 for LLM visual analysis |
| `browser_session_open` | `capability/browser_agent.py` | Open persistent browser session (reuse across calls) |
| `browser_session_close` | `capability/browser_agent.py` | Close browser session |
| `browser_session_list` | `capability/browser_agent.py` | List active sessions |

Key: **LLM is the router**. No centralized tool dispatcher. The LLM sees available tools
and decides which to call based on the user's intent.

Scrapling extraction toolkit (in browser_agent._direct_extract):
  css/xpath selectors → find_by_text → find_similar → find_ancestor → find_by_regex
  get_all_text → extract_first → text.clean → generate_css_selector → download links
  Adaptive: auto_save + adaptive survives page structure changes
  Anti-bot: StealthyFetcher with solve_cloudflare, hide_canvas, block_webrtc, retries, block_ads, disable_resources, page_action scroll

---

## 2. StealthyFetcher — Anti-bot Bypass

Tiered browser launch in `browser_agent._navigate()`:
  1. **StealthyFetcher** (patchright) — solve_cloudflare, hide_canvas, block_webrtc
  2. **DynamicFetcher** (Playwright) — JS render, retries=2, block_ads, disable_resources
  3. **Raw Playwright** — direct goto with stealth headers

Block detection: checks for 云防御/拦截/captcha/blocked signals.

---

## 3. ARIA Tree Extraction

Replaces raw HTML (30KB) with structured JSON (~2KB):
  - `_extract_page_state()` → {title, inputs[], clickables[], text}
  - Inputs include CSS selector, type, placeholder, visibility
  - Clickables include CSS selector and text label
  - LLM receives clean structure, decides next action

---

## 4. orjson — 12x Faster Serialization

All JSON output uses orjson (12x over stdlib json.dumps):
  - `BrowseResult.to_json()` — browser result serialization
  - `WebToolRouter` result formatting
  - LLM response parsing (`_parse_json`)

---

## 5. API Map — 28 Endpoints, 50 Secrets

- 28 REST/JSON API endpoints in `api_map.py`
- 50 encrypted secrets in `config/secrets.enc`
- Auto-loads API keys from vault on init
- Categories: weather (5), media (2), map (3), dev (3), academic (1), knowledge (1), language (1), finance (2), data (3), fun (4), news (2), network (1)

---

## 6. Skill System — 10 Security Fixes

- AST scan on LLM-generated code (reject dangerous imports/calls)
- Git clone URL whitelist (github/gitlab/gitee/bitbucket/codeberg only)
- pip install virtualenv isolation with --user fallback
- Skill body HTML sanitization (strip script/iframe/js:)
- YAML bomb protection (64KB frontmatter cap, 500-key map limit)
- Rate limiting on skill creation (20/hour per user)
- Workspace membership check before skill CRUD
- File extension validation in skill discovery
- Frontmatter line count limit (100 lines)
- Fixed SkillAdapter method reference (execute_skill → execute)

---

## 7. Hard Import Policy

All external package imports are direct (no try/except ImportError):
  - Framework deps: scrapling, playwright, orjson, aiohttp, bs4, lxml
  - Optional deps: numpy, torch, faiss, paddleocr, etc. (fail-fast with clear ModuleNotFoundError)
  - Internal module imports use try/except (legitimate for optional subsystems)
