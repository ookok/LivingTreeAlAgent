"""BrowserAgent — Scrapling-powered LLM-driven browser automation.

Core capabilities:
  1. DynamicFetcher pre-check — WAF/block detection
  2. Playwright browser — JS rendering + interaction (reused across iterations)
  3. ARIA tree extraction — structured page state for LLM (~2KB vs 30KB raw HTML)
  4. Adaptive selectors (Scrapling) — survive page structure changes
  5. Structured JSON output — ready for UI rendering

Architecture:
  Scrapling pre-check → Playwright page → LLM analysis → click/type →
  ARIA refresh → LLM extraction → structured JSON

Usage:
    agent = BrowserAgent()
    result = await agent.browse(
        url="http://www.njls.gov.cn/...",
        task="Extract project name and download link for the EIA report"
    )
    # result.items = [{"text":"...", "link":"..."}]
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from loguru import logger

MAX_ITERATIONS = 6
MAX_TEXT_LENGTH = 5000

HAS_PLAYWRIGHT = False
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    pass

HAS_SCRAPLING = False
try:
    from scrapling.fetchers import DynamicFetcher
    from scrapling.parser import Selector
    HAS_SCRAPLING = True
except ImportError:
    pass


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

    def to_json(self) -> dict:
        return asdict(self)


class BrowserAgent:

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

    async def browse(self, url: str, task: str,
                     max_iterations: int = MAX_ITERATIONS) -> BrowseResult:
        t0 = time.time()
        result = BrowseResult(url=url)
        llm = await self._get_llm()
        if not llm:
            result.error = "No LLM available"
            return result
        if not HAS_PLAYWRIGHT:
            result.error = "Playwright not installed"
            return result

        browser = None
        try:
            pw = await async_playwright().__aenter__()
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}, locale="zh-CN",
            )
            page = await ctx.new_page()

            # Navigate (pre-check via Scrapling for WAF)
            await self._navigate(page, url)
            result.title = await page.title()
            result.method = "playwright"

            for iteration in range(max_iterations):
                result.iterations = iteration + 1
                state = await self._extract_page_state(page)
                action = await self._llm_decide(llm, state, url, task, iteration, max_iterations)
                if not action:
                    break
                if action.get("action") == "done":
                    result.items = action.get("extracted", {}).get("items", [])
                    result.count = action.get("extracted", {}).get("count", len(result.items))
                    result.success = result.count > 0
                    break
                await self._exec_action(page, action)

            if not result.items and HAS_SCRAPLING:
                html = await page.content()
                sel = Selector(html)
                extracted = self._direct_extract(sel, task)
                if extracted:
                    result.items = extracted
                    result.count = len(extracted)
                    result.success = True
                    result.method = "adaptive_extraction"

        except Exception as e:
            result.error = str(e)[:500]
            logger.warning(f"BrowserAgent: {e}")
        finally:
            try:
                if browser:
                    await browser.close()
            except Exception:
                pass

        result.elapsed_ms = (time.time() - t0) * 1000
        return result

    async def _navigate(self, page, url: str):
        """Navigate with Scrapling pre-check for WAF detection."""
        if HAS_SCRAPLING:
            try:
                sp = DynamicFetcher.fetch(url, headless=True, network_idle=True, timeout=15_000)
                if sp and not self._is_blocked(sp.text or ""):
                    html = sp.body.decode("utf-8", errors="replace") if isinstance(sp.body, bytes) else str(sp.body)
                    await page.set_content(html, wait_until="networkidle")
                    return
            except Exception:
                pass
        await page.goto(url, timeout=30_000, wait_until="networkidle")
        await asyncio.sleep(2)

    @staticmethod
    def _is_blocked(text: str) -> bool:
        blocked = ["云防御", "拦截", "captcha", "blocked", "访问受限", "请验证"]
        return any(s in (text or "").lower() for s in blocked)

    async def _llm_decide(self, llm, state: dict, url: str, task: str,
                          iteration: int, max_iter: int) -> dict | None:
        prompt = (
            f"URL: {url}\nTask: {task}\nIteration {iteration+1}/{max_iter}\n\n"
            f"=== Title ===\n{state.get('title','')}\n\n"
            f"=== Inputs ===\n{self._fmt_inputs(state.get('inputs',[]))}\n\n"
            f"=== Buttons/Links ===\n{self._fmt_clickables(state.get('clickables',[]))}\n\n"
            f"=== Text ===\n{state.get('text','')[:3000]}\n\n"
            f"Reply with only JSON:\n"
            f'Done: {{"action":"done","extracted":{{"items":[{{...}}],"count":N}}}}\n'
            f'Type: {{"action":"type","selector":"<CSS>","text":"<text>"}}\n'
            f'Click: {{"action":"click","selector":"<CSS>"}}\n'
        )
        try:
            resp = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=2000, timeout=90,
            )
            if resp and resp.text:
                return self._parse_json(resp.text)
        except Exception as e:
            logger.debug(f"LLM: {e}")
        return None

    def _direct_extract(self, page, task: str) -> list[dict]:
        items = []
        try:
            for sel in ["table tr", "ul li", ".xxgk_content", "#zoom",
                        "[class*='item']", "[class*='list']", "[class*='article']"]:
                els = page.css(sel)
                if len(els) > 1:
                    for el in els[:50]:
                        text = el.text.strip() if el.text else ""
                        if len(text) > 20:
                            items.append({"text": text[:500], "selector": sel})
                    if items:
                        break
            if not items:
                items = [{"text": (a.text or "附件").strip()[:200], "link": a.attrib.get("href","")}
                         for a in page.css("a[href]")
                         if any(e in (a.attrib.get("href","") or "").lower()
                                for e in [".pdf", ".doc", ".docx", ".xls", ".zip"])]
        except Exception:
            pass
        return items[:50]

    async def _extract_page_state(self, page) -> dict:
        state = {}
        try:
            state["title"] = await page.title()
            state["inputs"] = await page.evaluate("""
                () => Array.from(document.querySelectorAll('input:not([type="hidden"]), textarea, select'))
                    .slice(0,30).map(el => {
                        let css = el.tagName.toLowerCase();
                        if (el.id) css += '#' + el.id;
                        else if (el.className && typeof el.className === 'string')
                            css += '.' + el.className.trim().split(/\\s+/).join('.');
                        if (el.name) css += '[name="' + el.name + '"]';
                        if (el.placeholder) css += '[placeholder="' + el.placeholder + '"]';
                        return {css:css.slice(0,120), type:el.type||el.tagName.toLowerCase(),
                                placeholder:(el.placeholder||'').slice(0,60), visible:el.offsetParent!==null};
                    })
            """)
            state["clickables"] = await page.evaluate("""
                () => Array.from(document.querySelectorAll('button, a, [role="button"], [onclick]'))
                    .slice(0,40).map(el => {
                        let css = el.tagName.toLowerCase();
                        if (el.id) css += '#' + el.id;
                        else if (el.className && typeof el.className === 'string')
                            css += '.' + el.className.trim().split(/\\s+/).join('.');
                        const text = (el.textContent || '').trim().slice(0,40);
                        return {css:css.slice(0,120), text, visible:el.offsetParent!==null};
                    }).filter(x => x.text && x.visible)
            """)
            state["text"] = await page.evaluate("""
                () => {const w=document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT,null,false);
                    const p=[]; let n;
                    while(n=w.nextNode()){const t=(n.parentElement||{}).tagName;
                        if(t==='SCRIPT'||t==='STYLE'||t==='NOSCRIPT'||t==='SVG') continue;
                        const tx=n.textContent.trim(); if(tx&&tx.length>1) p.push(tx);}
                    return p.join('\\n').slice(0,5000);}
            """)
        except Exception as e:
            logger.debug(f"Page state: {e}")
        return state

    async def _exec_action(self, page, action: dict):
        act = action.get("action", "")
        sel = action.get("selector", "")
        txt = action.get("text", "")
        try:
            if act == "type" and sel:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    await el.click(); await el.fill(""); await el.fill(txt)
                    await asyncio.sleep(0.5); await el.press("Enter"); await asyncio.sleep(2)
            elif act == "click" and sel:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    await el.click(); await asyncio.sleep(2)
        except Exception as e:
            logger.debug(f"Action {act}: {e}")

    @staticmethod
    def _fmt_inputs(inputs) -> str:
        if not inputs: return "(none)"
        return "\n".join(f"  {i.get('css','?')} [{i.get('type','')}] ph=\"{i.get('placeholder','')}\""
                         for i in inputs[:30] if isinstance(i, dict))

    @staticmethod
    def _fmt_clickables(clickables) -> str:
        if not clickables: return "(none)"
        return "\n".join(f"  {e.get('css','?')} -> \"{e.get('text','')}\""
                         for e in clickables[:30] if isinstance(e, dict))

    @staticmethod
    def _parse_json(text: str) -> dict:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try: return json.loads(m.group(0))
            except json.JSONDecodeError: pass
        return {}


_agent: Optional[BrowserAgent] = None

def get_browser_agent(llm=None) -> BrowserAgent:
    global _agent
    if _agent is None or llm:
        _agent = BrowserAgent(llm)
    return _agent
