## WEB TOOL CHAIN (v2.4)

```
User Input → TreeLLM.chat() →
  LLM decides if web tool needed →
    <tool_call name="web_lookup">{"url":"...","query":"..."}</tool_call>
      → CapabilityBus → WebToolRouter.lookup() →
        ├─ URL + interaction needed → browser_agent.browse(url, task)
        ├─ URL + static page        → web_fetch(url) [light_crawler]
        ├─ Matches API (score≥5)    → api_map.call(name, params)
        └─ Natural language search  → web_search(query) [Parallel MCP → SparkSearch → DDG]
  Result → injected into LLM context → final answer
```

| Tool | Module | Purpose |
|------|--------|---------|
| `api_map.call()` | `treellm/api_map.py` | 28 REST/JSON APIs (weather, maps, translate, etc.) |
| `web_fetch()` | `web_router.py → light_crawler` | Static HTTP GET, returns raw HTML |
| `browser_agent.browse()` | `capability/browser_agent.py` | LLM-driven Playwright: JS render, type, click, extract |
| `web_search()` | `web_router.py → duckduckgo_search` | General search engine |
| `WebToolRouter.lookup()` | `capability/web_router.py` | Unified entry point, auto-classify + route |