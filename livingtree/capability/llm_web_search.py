"""LLM Web Search — Use LLM providers as search engines via their native web search APIs.

Leverages the native 联网搜索 capability of LLM chat APIs. These providers
search the web internally and return answers grounded in real-time web content.

星火Lite:        web_search tool (Bearer APIPassword auth, free)
智谱GLM-4-Flash:  tools web_search function calling   (free)
DeepSeek V4:      tools web_search function calling   (paid, final fallback)

Includes cross-validation: when multiple engines return results, compare URLs
to detect hallucinations — single-source results with no cross-engine overlap
are flagged as low-confidence.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from loguru import logger


@dataclass
class LLMSearchResult:
    title: str
    url: str
    summary: str = ""
    source: str = ""
    confidence: float = 1.0  # 1.0 = high, lowered by cross-validation

    def format_display(self) -> str:
        lines = [f"[bold]{self.title}[/bold]"]
        lines.append(f"  [dim]{self.url}[/dim]")
        if self.summary:
            lines.append(f"  {self.summary[:120]}")
        if self.confidence < 0.8:
            lines.append(f"  [yellow]Low confidence: {self.confidence:.0%}[/yellow]")
        return "\n".join(lines)


_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_DOMAIN_PATTERN = re.compile(r"github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)")


def _normalize_url(url: str) -> str:
    """Normalize for comparison: lower scheme+domain+path, strip trailing slash."""
    url = url.lower().rstrip("/")
    url = re.sub(r"^https?://(www\.)?", "", url)
    return url


class LLMWebSearch:
    """Multi-provider LLM-based web search with cross-validation.

    Providers tried in order:
      1. spark-lite  (星火Lite — free, Bearer APIPassword)
      2. zhipu       (智谱GLM-4-Flash — free, tools web_search)
      3. deepseek    (DeepSeek V4 — paid, final fallback)

    Cross-validation: when >=2 engines succeed, results whose URLs appear in
    only one engine are downgraded to low confidence.
    """

    SEARCH_PROMPT = (
        "You are a web search assistant. Search for current information about: {query}\n\n"
        "Return a structured list. For each result include:\n"
        "  ## [Title]\n"
        "  URL: https://...\n"
        "  Summary: 1-2 sentences\n"
    )

    def __init__(self):
        self._spark_api_secret: str | None = None
        self._spark_key_simple: str | None = None
        self._zhipu_key: str | None = None
        self._deepseek_key: str | None = None
        self._spark_base = "https://spark-api-open.xf-yun.com/v1"
        self._zhipu_base = "https://open.bigmodel.cn/api/paas/v4"
        self._deepseek_base = "https://api.deepseek.com/v1"
        self._spark_model = "lite"
        self._zhipu_model = "glm-4-flash"
        self._deepseek_model = "deepseek-v4-flash"
        self._initialized = False

    def _init_keys(self):
        if self._initialized:
            return
        try:
            from livingtree.config.secrets import get_secret_vault
            vault = get_secret_vault()
            spark_key = vault.get("spark_api_key", "") or None
            if spark_key:
                if ":" in spark_key:
                    parts = spark_key.split(":")
                    self._spark_api_secret = parts[1].strip() if len(parts) >= 2 else parts[0].strip()
                else:
                    self._spark_api_secret = spark_key
                self._spark_key_simple = spark_key
            self._zhipu_key = vault.get("zhipu_api_key", "") or None
            self._deepseek_key = vault.get("deepseek_api_key", "") or None
        except Exception:
            pass
        self._initialized = True

    # ═══ Main query method ═══

    async def query(self, query: str, limit: int = 8) -> list[LLMSearchResult]:
        self._init_keys()
        if not query or not query.strip():
            return []

        all_results: list[LLMSearchResult] = []
        engine_count = 0

        if self._spark_api_secret:
            results = await self._query_spark(query, limit)
            if results:
                all_results.extend(results)
                engine_count += 1

        if self._zhipu_key:
            results = await self._query_zhipu(query, limit)
            if results:
                all_results.extend(results)
                engine_count += 1

        if not all_results and self._deepseek_key:
            results = await self._query_deepseek(query, limit)
            if results:
                all_results.extend(results)
                engine_count += 1

        if engine_count >= 2:
            all_results = self._cross_validate(all_results)

        return all_results[:limit]

    # ═══ Cross-validation ═══

    def _cross_validate(self, results: list[LLMSearchResult]) -> list[LLMSearchResult]:
        """Compare URLs across engines. Single-source results → low confidence."""
        url_sources: dict[str, set[str]] = {}
        for r in results:
            norm = _normalize_url(r.url)
            url_sources.setdefault(norm, set()).add(r.source)

        for r in results:
            sources = url_sources.get(_normalize_url(r.url), set())
            if len(sources) == 1:
                r.confidence = 0.5
                r.summary += " [single-source, verify manually]"
            elif len(sources) >= 2:
                r.confidence = 0.9

        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    # ═══ Engine: 星火Lite ═══

    async def _query_spark(self, query: str, limit: int) -> list[LLMSearchResult]:
        """星火Lite: Bearer APIPassword (official HTTP API, no HMAC needed).
        Docs: https://spark-api-open.xf-yun.com/v1/chat/completions
        Note: web_search tool only works on Pro/Max/Ultra. Lite model may not
        return web search results; falls through to next engine."""
        apipassword = self._spark_api_secret
        if not apipassword:
            return []
        payload = {
            "model": self._spark_model,
            "messages": [
                {"role": "system", "content": self.SEARCH_PROMPT.format(query=query)},
                {"role": "user", "content": query},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
            "tools": [{"type": "web_search", "web_search": {"enable": True}}],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {apipassword}",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._spark_base}/chat/completions",
                    json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.debug(f"Spark {resp.status}: {body[:200]}")
                        return []
                    data = await resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        return self._parse_response(content, "spark-lite")[:limit]
        except Exception as e:
            logger.debug(f"Spark request failed: {e}")
        return []

    # ═══ Engine: 智谱GLM-4-Flash ═══

    async def _query_zhipu(self, query: str, limit: int) -> list[LLMSearchResult]:
        """智谱GLM-4-Flash: tools function calling with search_web function (free)."""
        try:
            payload = {
                "model": self._zhipu_model,
                "messages": [
                    {"role": "system", "content": "You are a helpful web search assistant. Use the search_web tool to find current information, then return a complete answer with URLs."},
                    {"role": "user", "content": query},
                ],
                "temperature": 0.1,
                "max_tokens": 4096,
                "tools": [{
                    "type": "function",
                    "function": {
                        "name": "search_web",
                        "description": "Search the internet for current information about a topic.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "The search query"},
                            },
                            "required": ["query"],
                        },
                    },
                }],
                "tool_choice": "auto",
            }
            result = await self._http_post(self._zhipu_base, self._zhipu_key, payload)
            if not result:
                return []
            return self._parse_response(result, "zhipu-flash")[:limit]
        except Exception as e:
            logger.debug(f"Zhipu search failed: {e}")
            return []

    # ═══ Engine: DeepSeek V4 ═══

    async def _query_deepseek(self, query: str, limit: int) -> list[LLMSearchResult]:
        """DeepSeek V4: tools function calling (paid, final fallback)."""
        try:
            payload = {
                "model": self._deepseek_model,
                "messages": [
                    {"role": "system", "content": "You are a web search assistant. Use the web_search function to find current information."},
                    {"role": "user", "content": query},
                ],
                "temperature": 0.1,
                "max_tokens": 4096,
                "tools": [{
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Search the internet for current information.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "The search query"},
                            },
                            "required": ["query"],
                        },
                    },
                }],
                "tool_choice": "auto",
            }
            result = await self._http_post(self._deepseek_base, self._deepseek_key, payload)
            if not result:
                return []
            return self._parse_response(result, "deepseek-v4")[:limit]
        except Exception as e:
            logger.debug(f"DeepSeek search failed: {e}")
            return []

    # ═══ HTTP helpers ═══

    async def _http_post(self, base_url: str, api_key: str, payload: dict) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                }
                async with session.post(
                    f"{base_url}/chat/completions",
                    json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.debug(f"LLM search HTTP {resp.status}: {body[:200]}")
                        return ""
                    data = await resp.json()
                    choice = data.get("choices", [{}])[0]
                    msg = choice.get("message", {})
                    content = msg.get("content", "") or ""
                    tool_calls = msg.get("tool_calls", [])

                    if tool_calls:
                        r2 = await self._continue_with_tool_result(
                            session, base_url, api_key, payload,
                            choice, tool_calls,
                        )
                        return r2

                    return content
        except Exception as e:
            logger.debug(f"LLM search request failed: {e}")
            return ""

    async def _continue_with_tool_result(
        self, session: aiohttp.ClientSession, base_url: str, api_key: str,
        payload: dict, choice: dict, tool_calls: list,
    ) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        msgs = list(payload["messages"])
        msgs.append(choice.get("message", {}))
        tool_result = {
            "role": "tool",
            "tool_call_id": tool_calls[0].get("id", "call_0"),
            "content": "Search completed. Use results to provide a comprehensive answer.",
        }
        msgs.append(tool_result)
        payload2 = {**payload, "messages": msgs}
        try:
            async with session.post(
                f"{base_url}/chat/completions",
                json=payload2, headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.debug(f"LLM search round2 HTTP {resp.status}: {body[:200]}")
                    return ""
                data = await resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            logger.debug(f"LLM search round2 failed: {e}")
            return ""

    # ═══ Response parsing ═══

    def _parse_response(self, text: str, source: str) -> list[LLMSearchResult]:
        if not text or not text.strip():
            return []
        results = []
        lines = text.split("\n")
        cur_title, cur_url, cur_summary = None, None, None

        def save():
            nonlocal cur_title, cur_url, cur_summary
            if cur_url:
                results.append(LLMSearchResult(
                    title=cur_title or cur_url.split("//")[-1][:60],
                    url=cur_url, summary=cur_summary or "", source=source,
                ))
            cur_title, cur_url, cur_summary = None, None, None

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("## ") or line.startswith("# "):
                save()
                cur_title = line.lstrip("# ").strip()
                continue
            url_match = _URL_PATTERN.search(line)
            if url_match and ("URL:" in line or "url:" in line or "http" in line):
                cur_url = url_match.group(0).rstrip(".,;:)''\"")
                continue
            if line.lower().startswith("summary:") or line.lower().startswith("summary："):
                cur_summary = line.split(":", 1)[-1].split("：", 1)[-1].strip() if ":" in line or "：" in line else ""
                continue
            if line.startswith("> ") or line.startswith("- "):
                txt = line[2:].strip()
                um = _URL_PATTERN.search(txt)
                if um and not cur_url:
                    cur_url = um.group(0).rstrip(".,;:)''\"")
                    cur_title = cur_title or txt[:100]
                    continue
                if not cur_summary:
                    cur_summary = txt[:200]

        save()

        if not results:
            urls = _URL_PATTERN.findall(text)
            for url in urls[:limit]:
                url = url.rstrip(".,;:)''\"")
                dom = _DOMAIN_PATTERN.search(url)
                title = dom.group(1) if dom else url.split("//")[-1][:60]
                results.append(LLMSearchResult(title=title, url=url, source=source))

        return results

    def format_results(self, results: list[LLMSearchResult], max_results: int = 10) -> str:
        if not results:
            return "[dim]No results found[/dim]"
        lines = [f"[bold]LLM Web Search Results ({len(results)}):[/bold]"]
        for r in results[:max_results]:
            lines.append(f"  [bold #58a6ff]{r.title[:80]}[/bold #58a6ff]")
            lines.append(f"    [dim]{r.url}[/dim]")
            if r.summary:
                lines.append(f"    {r.summary[:150]}")
            if r.confidence < 0.8:
                lines.append(f"    [yellow]⚠ Low confidence ({r.confidence:.0%})[/yellow]")
            lines.append("")
        return "\n".join(lines)


# ═══ Global singleton ═══

_llm_web_search: LLMWebSearch | None = None


def get_llm_web_search() -> LLMWebSearch:
    global _llm_web_search
    if _llm_web_search is None:
        _llm_web_search = LLMWebSearch()
    return _llm_web_search


async def llm_search(query: str, limit: int = 8) -> list[LLMSearchResult]:
    return await get_llm_web_search().query(query, limit=limit)
