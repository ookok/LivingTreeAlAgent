# TASKS.md — Pending Tasks

> LivingTree AI Agent — actionable task list as of v2.5 web chain.
> See also: [DESIGN.md](DESIGN.md), [CONTEXT.md](CONTEXT.md)

---

## 1. Install Missing Dependencies

Several optional dependencies are not yet installed:

```bash
# Vector DB (faiss-cpu needed for knowledge/semantic search)
pip install faiss-cpu

# GIS / Spatial
pip install shapely fiona networkx

# Visualization
pip install graphviz

# Desktop
pip install webview

# Document
pip install weasyprint ezdxf

# OCR
pip install pytesseract paddleocr easyocr

# LSP
pip install tree-sitter tree-sitter-python tree-sitter-javascript tree-sitter-typescript tree-sitter-go tree-sitter-rust

# Full install (all optional deps)
pip install -e ".[all]"
```

**Priority**: faiss-cpu and shapely are highest (core knowledge + GIS functionality).
The remainder can be installed as-needed.

---

## 2. End-to-End Test: 溧水地区 锂电池 环评报告

Full pipeline test combining all web tools:

1. `web_search("溧水地区 锂电池 环评报告")` — multi-engine search
2. `web_fetch` — collect candidate pages
3. `browser_browse` — JS-render dynamic gov/industry portals
4. `api_search` + `api_call` — supplement with public data APIs
5. LLM synthesizes into structured EIA report

**Goal**: Validate the full web tool chain end-to-end with a real-world Chinese
environmental impact assessment query.

**Command**:
```bash
python -m pytest tests/test_e2e.py -k "e2e_web_chain" -v
```

---

## 3. Patchright Browser Download

Scrapling's `StealthyFetcher` requires a patched Chromium for full anti-bot capability
(bypass Cloudflare Turnstile, canvas fingerprinting, WebRTC leak):

```bash
patchright install chromium
```

Without this, `StealthyFetcher` falls back to standard Playwright Chromium which has
detectable automation markers.

---

## 4. Frontend: Spider Crawl Dashboard Live Test

The admin panel (`/tree/admin`) should display live crawl status from the web tool chain:

- [ ] Show active `browser_session_list` sessions
- [ ] Display crawl queue with `light_crawler.py` progress
- [ ] Render `browser_screenshot` thumbnails in dashboard
- [ ] WebSocket push for real-time crawl updates

**Module**: `livingtree/templates/` (HTMX + Tailwind CSS)
**API**: `livingtree/api/` (FastAPI endpoints)

---

## 5. CodeGraph Rebuild

`livingtree/capability/code_graph.py` — the codebase knowledge graph needs a fresh scan:

```bash
livingtree improve --scan
```

This rebuilds the AST-based dependency graph and semantic index used by:
- `semantic_code_search.py`
- `code_analyzer.py`
- `code_reviewer.py`
- `sast_scanner.py`

---

## 6. Package as Executable

Build standalone Windows `.exe` with PyInstaller:

```bash
livingtree build
```

This invokes `build_relay_exe.py` with the spec in `build_relay/` to produce a
self-contained executable for distribution on Windows Server 2008+.

**Prerequisites**: All optional dependencies installed (Section 1), `patchright`
chromium bundled (Section 3).

---

## 7. Quick Status Check

```bash
# Test suite
python -m pytest tests/ -q

# Lint
ruff check .

# Type check
mypy livingtree/

# Verify web tool chain imports
python -c "from scrapling.fetchers import StealthyFetcher, DynamicFetcher; print('OK')"
python -c "from livingtree.capability.browser_agent import BrowserAgent; print('OK')"
python -c "from livingtree.treellm.capability_bus import get_capability_bus; print('OK')"
```
