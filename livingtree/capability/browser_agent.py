"""BrowserAgent — Scrapling + StealthyFetcher LLM-driven browser automation.

Core capabilities:
  1. StealthyFetcher — anti-bot (Cloudflare,Turnstile,canvas,WebRTC leak)
  2. Playwright/Chromium — JS rendering + interaction (session reuse)
  3. ARIA tree — structured page state for LLM (~2KB)
  4. Adaptive selectors — survive page structure changes
  5. orjson — 12x faster JSON output
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

import orjson
from loguru import logger
from playwright.async_api import async_playwright
from scrapling.fetchers import Fetcher, DynamicFetcher, StealthyFetcher
from scrapling.parser import Selector

_json_dumps = lambda obj: orjson.dumps(obj, option=orjson.OPT_INDENT_2).decode()
_json_loads = orjson.loads

MAX_ITERATIONS = 6
MAX_TEXT_LENGTH = 5000


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


class BrowserAgent:

    def __init__(self, llm=None):
        self._llm = llm

    async def _get_llm(self):
        if self._llm:
            return self._llm
        from livingtree.treellm.core import TreeLLM
        self._llm = get_tool_registry().get('treellm_core').from_config()
        return self._llm

    async def browse(self, url: str, task: str,
                     max_iterations: int = MAX_ITERATIONS) -> BrowseResult:
        t0 = time.time()
        result = BrowseResult(url=url)
        llm = await self._get_llm()
        if not llm:
            result.error = "No LLM available"
            return result

        browser = None
        own_browser = False
        try:
            sid = getattr(self, '_active_session', None)
            state = (getattr(self, '_session_state', {}) or {}).get(sid, {}) if sid else {}
            if state.get("page"):
                browser = state["browser"]
                page = state["page"]
            else:
                pw = await async_playwright().__aenter__()
                browser = await pw.chromium.launch(headless=True)
                ctx = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080}, locale="zh-CN",
                )
                page = await ctx.new_page()
                own_browser = True

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

            if not result.items:
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
                if browser and own_browser:
                    await browser.close()
            except Exception:
                pass

        result.elapsed_ms = (time.time() - t0) * 1000
        return result

    async def _navigate(self, page, url: str):
        DynamicFetcher.adaptive = True
        try:
            sp = StealthyFetcher.fetch(
                url, headless=True, network_idle=True, timeout=30_000,
                disable_resources=True, retries=2, block_ads=True,
                solve_cloudflare=True, hide_canvas=True, block_webrtc=True,
                page_action=self._page_action_scroll,
            )
            if sp and not self._is_blocked(sp.text or ""):
                html = sp.body.decode("utf-8", errors="replace") if isinstance(sp.body, bytes) else str(sp.body)
                await page.set_content(html, wait_until="networkidle")
                return
        except Exception:
            pass

        try:
            sp = DynamicFetcher.fetch(
                url, headless=True, network_idle=True, timeout=30_000,
                disable_resources=True, retries=2, block_ads=True,
                page_action=self._page_action_scroll,
            )
            if sp and not self._is_blocked(sp.text or ""):
                html = sp.body.decode("utf-8", errors="replace") if isinstance(sp.body, bytes) else str(sp.body)
                await page.set_content(html, wait_until="networkidle")
                return
        except Exception:
            pass

        await page.goto(url, timeout=30_000, wait_until="networkidle")
        await asyncio.sleep(2)

    @staticmethod
    def _page_action_scroll(page):
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass

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
        import re as _re
        items = []

        for sel in ["table tr", "ul li", "ol li",
                    "[class*='item']", "[class*='list']", "[class*='row']",
                    "[class*='article']", "[class*='result']", "[class*='content']",
                    "[class*='entry']", "[class*='post']",
                    ".xxgk_content", "#zoom", "#content",
                    ".article-content", ".main-content", ".entry-content"]:
            els = page.css(sel, auto_save=True)
            if len(els) >= 2:
                for el in els[:50]:
                    text = el.get_all_text(strip=True) if hasattr(el, 'get_all_text') else (el.text or "")
                    text = (text[:500] if isinstance(text, str) else "")
                    if len(text) > 20:
                        sel_gen = el.generate_css_selector if hasattr(el, 'generate_css_selector') else sel
                        items.append({"text": text, "selector": sel_gen})
                if items:
                    return items

        keywords = _re.findall(r'[\u4e00-\u9fff]{2,}|\w{3,}', task)
        for kw in keywords[:5]:
            try:
                el = page.find_by_text(kw, partial=True, first_match=True)
                if not el:
                    continue
                container = None
                if hasattr(el, 'find_ancestor'):
                    container = el.find_ancestor(
                        lambda e: e.tag in ('ul', 'ol', 'table', 'section', 'div') and
                        (getattr(e, 'css', None) and len(e.css('li, tr, [class*="item"]')) >= 2)
                    ) or el.parent
                else:
                    container = el.parent if hasattr(el, 'parent') else el
                source = container if container else el
                similar = source.find_similar() if hasattr(source, 'find_similar') else ([source] if source else [])
                for s in similar[:50]:
                    text = s.get_all_text(strip=True) if hasattr(s, 'get_all_text') else (s.text or "")
                    text = (text[:500] if isinstance(text, str) else "")
                    if text and len(text) > 15:
                        items.append({"text": text, "method": "find_similar"})
                if items:
                    return items
            except Exception:
                continue

        for pat in [r'https?://[^\s<>"\')\]},，。]{10,}', r'[\w.-]+@[\w.-]+\.\w+', r'(?:1[3-9]\d|86)?\d{7,11}']:
            try:
                matches = page.find_by_regex(_re.compile(pat), first_match=False)
                if matches:
                    for m in matches[:50]:
                        text = m.extract_first() if hasattr(m, 'extract_first') else (m.text or "")
                        text = (text[:500] if isinstance(text, str) else "")
                        if text:
                            items.append({"text": text, "pattern": pat, "method": "regex"})
                    if items:
                        return items
            except Exception:
                continue

        dl_exts = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".7z", ".ppt", ".pptx"]
        dl_links = []
        for a in page.css("a[href]"):
            href = (a.attrib.get("href", "") or "").lower()
            if any(href.endswith(e) or (f".{e.strip('.')}?" in href) for e in dl_exts):
                label = (a.text or "").strip() if hasattr(a, 'text') else ""
                label = label.clean if hasattr(label, 'clean') else label
                dl_links.append({"text": label[:200] if label else "附件", "link": a.attrib.get("href", ""), "method": "download_link"})
        if dl_links:
            return dl_links[:50]

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
            try: return _json_loads(m.group(0))
            except Exception: pass
        return {}

    # ═══ Session Management ════════════════════════════════════════

    async def session_open(self, url: str = "") -> dict:
        if not hasattr(self, '_session_state'):
            self._session_state = {}
        sid = f"ses_{int(time.time())}"
        pw = await async_playwright().__aenter__()
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}, locale="zh-CN",
        )
        page = await ctx.new_page()
        if url:
            await page.goto(url, timeout=30_000, wait_until="networkidle")
        self._session_state[sid] = {"playwright": pw, "browser": browser, "context": ctx, "page": page}
        self._active_session = sid
        return {"success": True, "session_id": sid, "url": url}

    async def session_close(self) -> dict:
        sid = getattr(self, '_active_session', None)
        if not sid or not hasattr(self, '_session_state'):
            return {"success": False, "error": "No active session"}
        state = self._session_state.pop(sid, {})
        if state.get("browser"):
            await state["browser"].close()
        self._active_session = None
        return {"success": True, "closed": sid}

    def session_list(self) -> dict:
        sessions = getattr(self, '_session_state', {})
        return {"sessions": [{"id": k, "url": v.get("page", None) and v["page"].url or ""}
                             for k, v in sessions.items()],
                "active": getattr(self, '_active_session', None)}

    # ═══ Screenshot ═════════════════════════════════════════════════

    async def screenshot(self) -> dict:
        sid = getattr(self, '_active_session', None)
        state = (getattr(self, '_session_state', {}) or {}).get(sid, {}) if sid else {}
        page = state.get("page")
        if not page:
            return {"success": False, "error": "No active browser session. Use browser_session_open first."}
        import base64
        shot = await page.screenshot(type="png", full_page=False)
        return {
            "success": True,
            "base64": base64.b64encode(shot).decode(),
            "width": page.viewport_size.get("width", 0) if page.viewport_size else 0,
            "height": page.viewport_size.get("height", 0) if page.viewport_size else 0,
        }


_agent: Optional[BrowserAgent] = None

def get_browser_agent(llm=None) -> BrowserAgent:
    global _agent
    if _agent is None or llm:
        _agent = BrowserAgent(llm)
    return _agent
