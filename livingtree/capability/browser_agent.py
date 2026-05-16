"""BrowserAgent — LLM-driven browser tool for interactive web search & extraction.

Architecture (LLM orchestrates, Playwright executes, Scrapling parses):
  1. Playwright fetches JS-rendered page (stealth Chromium)
  2. LLM analyzes HTML → decides action (search/click/extract/navigate)
  3. Playwright executes the action (type, click, wait)
  4. Scrapling Selector extracts structured content (when selectors known)
  5. LLM extracts final structured data from HTML
  6. Repeat until done or max iterations

No hardcoded CSS selectors. LLM reads raw HTML and decides everything.

Usage:
    agent = BrowserAgent()
    result = await agent.browse(
        url="http://esg.epmap.org/reports",
        task="Search for 格林美 ESG reports, extract titles and download links"
    )
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

MAX_ITERATIONS = 5
MAX_HTML_CHUNK = 30_000

HAS_PLAYWRIGHT = False
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    pass

HAS_SCRAPLING = False
try:
    from scrapling.parser import Selector
    HAS_SCRAPLING = True
except ImportError:
    pass


@dataclass
class BrowseResult:
    url: str = ""
    task: str = ""
    title: str = ""
    data: dict = field(default_factory=dict)
    raw_html: str = ""
    found: bool = False
    iterations: int = 0
    error: str = ""
    elapsed_ms: float = 0.0


@dataclass
class BrowseResult:
    url: str = ""
    task: str = ""
    title: str = ""
    data: dict = field(default_factory=dict)
    raw_html: str = ""
    found: bool = False
    iterations: int = 0
    error: str = ""
    elapsed_ms: float = 0.0


class BrowserAgent:
    """LLM-driven browser tool. No hardcoded selectors — LLM decides all actions."""

    def __init__(self, llm=None):
        self._llm = llm

    async def _get_llm(self):
        if self._llm:
            return self._llm
        try:
            from livingtree.treellm.core import TreeLLM
            self._llm = TreeLLM.from_config()
            return self._llm
        except Exception:
            pass
        return None

    # ═══ Public API ════════════════════════════════════════════════

    async def browse(
        self, url: str, task: str, max_iterations: int = MAX_ITERATIONS,
    ) -> BrowseResult:
        """LLM-driven browsing: navigate, search, extract — all decided by LLM."""
        t0 = time.time()
        result = BrowseResult(url=url, task=task)
        llm = await self._get_llm()

        if not llm:
            result.error = "No LLM available"
            return result
        if not HAS_PLAYWRIGHT:
            result.error = "Playwright not installed: pip install playwright && playwright install chromium"
            return result

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30_000, wait_until="networkidle")
                await asyncio.sleep(1)

                for iteration in range(max_iterations):
                    result.iterations = iteration + 1

                    # 1) Get current page state
                    html = await page.content()
                    html = html[:MAX_HTML_CHUNK]
                    result.raw_html = html
                    if not result.title:
                        result.title = await page.title()

                    # 2) LLM decides next action
                    action = await self._llm_decide(
                        llm, html, page.url, task, iteration, max_iterations
                    )
                    if not action:
                        break

                    act_type = action.get("action", "done")

                    if act_type == "done":
                        result.data = action.get("extracted", {})
                        result.found = action.get("found", bool(result.data))
                        break

                    # 3) Execute action
                    await self._exec_action(page, action)

                await browser.close()

        except Exception as e:
            result.error = str(e)[:500]
            logger.warning(f"BrowserAgent: {e}")

        result.elapsed_ms = (time.time() - t0) * 1000
        return result

    # ═══ LLM Decision ══════════════════════════════════════════════

    async def _llm_decide(self, llm, html: str, url: str, task: str,
                          iteration: int, max_iter: int) -> dict | None:
        """LLM reads the HTML and decides what to do next."""
        system = (
            "You are a web browser agent. You receive HTML page content and a task. "
            "Decide the NEXT SINGLE ACTION to complete the task. "
            "Reply with ONLY a JSON object, no markdown, no explanation."
        )

        prompt = (
            f"URL: {url}\n"
            f"Task: {task}\n"
            f"Iteration {iteration + 1} of {max_iter}\n\n"
            f"=== PAGE HTML (first {len(html)} chars) ===\n"
            f"{html}\n\n"
            f"Choose ONE action:\n\n"
            f'If you found the answer → {{"action":"done","found":true,"extracted":{{...structured data...}},"summary":"..."}}\n\n'
            f'If you need to type into an input → {{"action":"type","selector":"<CSS selector of the INPUT>","text":"<what to type>","submit":true}}\n'
            f'If you need to click something → {{"action":"click","selector":"<CSS selector>"}}\n\n'
            f"RULES:\n"
            f"- CSS selectors come from actual tag/class/id attributes in the HTML.\n"
            f"- Element UI inputs: class='el-input__inner'. Ant Design: class='ant-input'.\n"
            f"- Find the search-related input by placeholder text or class.\n"
            f"- After typing, click the search button/icon or press Enter (set submit:true).\n"
            f"- If page is empty/error/loading, return done with found=false.\n"
            f"- Extract ALL useful info into the 'extracted' field.\n"
        )

        try:
            response = await llm.chat(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1, max_tokens=2000, timeout=90,
            )
            if response and response.text:
                return self._parse_json(response.text)
        except Exception as e:
            logger.debug(f"LLM decide: {e}")
        return None

    # ═══ Action Executor ═══════════════════════════════════════════

    async def _exec_action(self, page, action: dict) -> None:
        """Execute a single action: type, click, or wait."""
        act_type = action.get("action", "")
        selector = action.get("selector", "")
        text = action.get("text", "")
        submit = action.get("submit", False)

        try:
            if act_type == "type" and selector:
                el = page.locator(selector).first
                if await el.is_visible(timeout=2000):
                    await el.click()
                    await el.fill("")
                    await el.fill(text)
                    await asyncio.sleep(0.3)
                    if submit:
                        await el.press("Enter")
                    await asyncio.sleep(2)

            elif act_type == "click" and selector:
                el = page.locator(selector).first
                if await el.is_visible(timeout=2000):
                    await el.click()
                    await asyncio.sleep(2)

        except Exception as e:
            logger.debug(f"Action {act_type} on {selector}: {e}")

    # ═══ Utilities ════════════════════════════════════════════════

    @staticmethod
    def _parse_json(text: str) -> dict:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}


# ═══ Tool Registration ════════════════════════════════════════════

_agent: Optional[BrowserAgent] = None


def get_browser_agent(llm=None) -> BrowserAgent:
    global _agent
    if _agent is None or llm:
        _agent = BrowserAgent(llm)
    return _agent


def register_browser_tool(bus=None):
    """Register browser_agent as a capability tool on the capability bus."""
    try:
        from livingtree.treellm.capability_bus import Capability, CapCategory, CapParam, get_capability_bus
        if bus is None:
            bus = get_capability_bus()
        agent = get_browser_agent()

        async def _handler(url: str = "", task: str = "", **kwargs) -> dict:
            result = await agent.browse(url=url, task=task)
            return {
                "found": result.found,
                "title": result.title,
                "data": result.data,
                "elapsed_ms": result.elapsed_ms,
                "error": result.error,
            }

        bus.register(Capability(
            id="tool:browser_agent",
            name="web_browse",
            category=CapCategory.TOOL,
            description="LLM-driven browser automation. Fetches JS-rendered pages, types search queries, clicks buttons, and extracts structured data. Use for dynamic SPA websites that require interaction.",
            params=[
                CapParam(name="url", type="string", description="Target page URL"),
                CapParam(name="task", type="string", description="What to do: search query, data to extract, etc."),
            ],
            handler=_handler,
            source="browser_agent",
            tags=["browser", "scraping", "spa", "js-render", "search"],
        ))
        logger.info("BrowserAgent registered as capability tool: web_browse")
        return True
    except Exception as e:
        logger.debug(f"BrowserAgent tool registration: {e}")
        return False
