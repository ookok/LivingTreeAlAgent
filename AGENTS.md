## WEB TOOL CHAIN (v2.5)

```
User Input → TreeLLM.chat() →
  LLM receives tool list in system prompt:
    api_search(keyword)   — find matching REST API endpoints
    api_call(name, params) — call a registered API (28 endpoints)
    web_search(query)      — search internet (MCP→Spark→Bing→DDG)
    web_fetch(url)         — fetch static HTML page
    browser_browse(url, task) — LLM-driven JS page (Playwright)
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
  Anti-bot: DynamicFetcher with retries, block_ads, disable_resources, page_action scroll