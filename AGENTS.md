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
| `web_fetch` | `capability_bus.py → aiohttp` | Static HTTP GET, returns cleaned text |
| `browser_browse` | `capability/browser_agent.py` | Playwright + LLM: JS render, type, click, extract (ARIA tree, ~2KB per page) |

Key: **LLM is the router**. No centralized tool dispatcher. The LLM sees available tools
and decides which to call based on the user's intent.