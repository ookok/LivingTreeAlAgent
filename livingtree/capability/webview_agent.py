"""WebView + JS Injection Bridge — lightweight browser for AI Agent.

3rd browser layer between Scrapling StealthyFetcher and Playwright:

  web_fetch       → Scrapling (static, TLS impersonation, zero browser)
  browser_inject  → WebView + JS bridge (JS render, native fingerprint, CORS proxy)  ← NEW
  browser_browse  → Playwright (full Chrome, click, type, screenshot)

Architecture:
  Python (LLM) ←→ QWebChannel Bridge ←→ PyQt6 WebEngine Page
      │                                       │
      inject(code)                            execute in page context
      extract(selector)                       return text/HTML
      navigate(url)                           load page, auto-inject Page Agent
      fetch(url, options)                     CORS-bypass proxy via Python
      click(selector) / type(text)            JS-driven DOM interaction
      screenshot()                            capture visible viewport
      wait(ms)                                sleep for dynamic content

PyQt6-WebEngine = Chromium under the hood but WITHOUT navigator.webdriver flag.
On load, injects stealth patches to fix WebView fingerprint gaps.
"""

from __future__ import annotations

import base64
import json
import re
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from queue import Queue, Empty
from typing import Any, Optional

import orjson
from loguru import logger

_json_dumps = lambda obj: orjson.dumps(obj, option=orjson.OPT_INDENT_2).decode()
_json_loads = orjson.loads

MAX_TEXT = 5000
PAGE_TIMEOUT_MS = 15000

# ── Stealth JS injected on every page load ──
STEALTH_JS = r"""
(function() {
    // 1. Remove WebDriver flag (WebEngine doesn't set this, but belt-and-suspenders)
    Object.defineProperty(navigator, 'webdriver', { get: () => false });

    // 2. Fake plugins array (WebView has none by default)
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            let arr = [new Plugin('Chrome PDF Plugin'), new Plugin('Chrome PDF Viewer'),
                       new Plugin('Native Client')];
            arr.item = i => arr[i];
            arr.namedItem = n => arr.find(p => p.name === n);
            arr.refresh = () => {};
            Object.setPrototypeOf(arr, PluginArray.prototype);
            return arr;
        }
    });
    function Plugin(name) { this.name = name; this.filename = 'internal-' + name; this.length = 1; }

    // 3. Fake languages
    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US', 'en'] });

    // 4. Fake hardware concurrency
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });

    // 5. Fake device memory
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

    // 6. Override permissions query to return 'granted' for common APIs
    const _origQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = function(params) {
        if (params.name === 'notifications') return Promise.resolve({ state: 'prompt' });
        return _origQuery.call(this, params).then(r => {
            if (['geolocation', 'camera', 'microphone'].includes(params.name)) {
                return { ...r, state: 'prompt' };
            }
            return r;
        });
    };

    // 7. Canvas fingerprint noise (tiny drift to avoid exact matching)
    const _origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type) {
        const ctx = this.getContext('2d');
        if (ctx && this.width > 10 && this.height > 10) {
            ctx.fillStyle = 'rgba(0,0,0,0.001)';
            ctx.fillRect(0, 0, 1, 1);
        }
        return _origToDataURL.apply(this, arguments);
    };
})();
"""

# ── Page Agent JS (injected on page load, maintains CORS proxy bridge) ──
PAGE_AGENT_JS = r"""
(function() {
    'use strict';

    // ── ARIA / DOM extraction ──
    window.__pg_extract = function(selector) {
        try {
            if (selector) {
                let el = typeof selector === 'string' ?
                    document.querySelector(selector) : selector;
                if (!el) return JSON.stringify({ error: 'selector not found' });
                return JSON.stringify({
                    tag: el.tagName,
                    text: (el.textContent || '').trim().slice(0, 5000),
                    html: el.outerHTML.slice(0, 5000),
                    rect: el.getBoundingClientRect ? (() => {
                        let r = el.getBoundingClientRect();
                        return { x: r.x, y: r.y, w: r.width, h: r.height };
                    })() : null
                });
            }
            // Full page ARIA tree
            function walk(el, depth) {
                if (depth > 12 || !el || !el.tagName) return null;
                let info = { tag: el.tagName.toLowerCase() };
                let role = el.getAttribute('role') || el.getAttribute('aria-label') || '';
                if (role) info.role = role.slice(0, 100);
                let text = '';
                if (el.tagName === 'A' && el.href) text = el.href;
                else if (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3)
                    text = el.textContent.trim();
                if (text && text.length < 200) info.text = text;
                let children = [];
                for (let c of el.children) {
                    let childInfo = walk(c, depth + 1);
                    if (childInfo) children.push(childInfo);
                }
                if (children.length) info.children = children;
                if (!info.role && !info.text && (!info.children || !info.children.length)) {
                    let t = (el.textContent || '').trim().slice(0, 100);
                    if (t) info.text = t;
                }
                return info;
            }
            return JSON.stringify(walk(document.body, 0));
        } catch(e) { return JSON.stringify({ error: e.message }); }
    };

    // ── Click element ──
    window.__pg_click = function(selector) {
        try {
            let el = document.querySelector(selector);
            if (!el) return JSON.stringify({ error: 'not found: ' + selector });
            el.scrollIntoView({ behavior: 'instant', block: 'center' });
            el.click();
            return JSON.stringify({ ok: true, tag: el.tagName, text: (el.textContent||'').slice(0, 200) });
        } catch(e) { return JSON.stringify({ error: e.message }); }
    };

    // ── Type text into input ──
    window.__pg_type = function(selector, text) {
        try {
            let el = document.querySelector(selector);
            if (!el) return JSON.stringify({ error: 'not found: ' + selector });
            el.focus();
            el.value = text;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return JSON.stringify({ ok: true, typed: text.slice(0, 50) });
        } catch(e) { return JSON.stringify({ error: e.message }); }
    };

    // ── Scroll ──
    window.__pg_scroll = function(px) {
        try {
            window.scrollBy({ top: px, behavior: 'smooth' });
            return JSON.stringify({ ok: true, scrollY: window.scrollY });
        } catch(e) { return JSON.stringify({ error: e.message }); }
    };

    // ── Proxy fetch (bypass CORS via Python bridge) ──
    window.__pg_fetch = function(url, options) {
        return new Promise(function(resolve) {
            let id = 'pg_fetch_' + Date.now() + '_' + Math.random().toString(36).slice(2);
            window.__pg_callbacks = window.__pg_callbacks || {};
            window.__pg_callbacks[id] = resolve;
            try {
                if (window.__bridge && window.__bridge.proxyFetch) {
                    window.__bridge.proxyFetch(id, url, JSON.stringify(options || {}));
                } else {
                    resolve(JSON.stringify({ error: 'bridge not ready' }));
                }
            } catch(e) { resolve(JSON.stringify({ error: e.message })); }
        });
    };
    // Called from Python side after fetch completes
    window.__pg_fetch_callback = function(id, result) {
        if (window.__pg_callbacks && window.__pg_callbacks[id]) {
            window.__pg_callbacks[id](result);
            delete window.__pg_callbacks[id];
        }
    };
})();
"""


@dataclass
class WebViewResult:
    success: bool = False
    url: str = ""
    title: str = ""
    text: str = ""
    items: list[dict] = field(default_factory=list)
    count: int = 0
    method: str = ""
    elapsed_ms: float = 0.0
    error: str = ""

    def to_json(self) -> str:
        return _json_dumps(asdict(self))


class WebViewBridge:
    """QWebChannel bridge object exposed to JS side as window.__bridge."""

    def __init__(self, agent: "WebViewAgent"):
        self._agent = agent
        self._fetch_results: dict[str, Queue] = {}

    def proxyFetch(self, request_id: str, url: str, options_json: str):
        """JS calls this → Python executes HTTP → calls back JS."""
        threading.Thread(target=self._do_proxy_fetch,
                         args=(request_id, url, options_json), daemon=True).start()

    def _do_proxy_fetch(self, request_id: str, url: str, options_json: str):
        import urllib.request as _req
        try:
            opts = json.loads(options_json) if options_json else {}
            method = opts.get("method", "GET").upper()
            headers = opts.get("headers", {})
            body = opts.get("body", "").encode() if opts.get("body") else None
            req = _req.Request(url, data=body, headers=headers, method=method)
            resp = _req.urlopen(req, timeout=15)
            data = resp.read().decode("utf-8", errors="replace")[:10000]
            result = json.dumps({"ok": True, "status": resp.status, "body": data})
        except Exception as e:
            result = json.dumps({"ok": False, "error": str(e)})
        self._agent._page.runJavaScript(
            f"window.__pg_fetch_callback('{request_id}', {result});")

    def agentLog(self, msg: str):
        logger.debug(f"[WebView] {msg}")


class WebViewAgent:
    """Lightweight browser with JS injection bridge.

    Uses PyQt6 WebEngine (Chromium without navigator.webdriver flag).
    Singleton per process — QApplication must be single instance.
    """

    _instance: Optional["WebViewAgent"] = None
    _app: Any = None
    _app_thread: Optional[threading.Thread] = None

    def __init__(self):
        self._view: Any = None
        self._page: Any = None
        self._bridge: Optional[WebViewBridge] = None
        self._ready = threading.Event()
        self._page_loaded = threading.Event()
        self._load_result: dict = {}
        self._current_url = ""
        self._current_title = ""

    @classmethod
    def get_instance(cls) -> "WebViewAgent":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.start()
        return cls._instance

    def start(self):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer

        if WebViewAgent._app is None:
            WebViewAgent._app = QApplication.instance() or QApplication([])
        self._app = WebViewAgent._app

        if self._view is None:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
            from PyQt6.QtWebChannel import QWebChannel
            from PyQt6.QtCore import QUrl

            profile = QWebEngineProfile.defaultProfile()
            profile.setHttpUserAgent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
            profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)

            self._bridge = WebViewBridge(self)
            self._channel = QWebChannel()
            self._channel.registerObject("__bridge", self._bridge)
            # Also expose bridge methods as callable from JS
            self._view = QWebEngineView()
            self._page = self._view.page()
            self._page.setWebChannel(self._channel)
            self._page.loadFinished.connect(self._on_load_finished)
            self._view.resize(1280, 900)

            QTimer.singleShot(0, self._emit_ready)

        WebViewAgent._app_thread = threading.Thread(
            target=self._run_event_loop, daemon=True)
        WebViewAgent._app_thread.start()
        self._ready.wait(timeout=5)
        logger.info("WebViewAgent started (PyQt6 WebEngine)")

    def _run_event_loop(self):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: None)  # keep-alive
        self._app.exec()

    def _emit_ready(self):
        self._ready.set()

    def _on_load_finished(self, ok: bool):
        self._load_result = {"ok": ok, "url": self._current_url}
        self._page_loaded.set()

    def _run_on_qt(self, fn, *args):
        """Execute a callable on the Qt event loop thread and return result."""
        result_queue: Queue = Queue()

        def wrapper():
            try:
                result_queue.put(("ok", fn(*args)))
            except Exception as e:
                result_queue.put(("err", str(e)))

        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self._view, "setFocus", Qt.ConnectionType.QueuedConnection)
        # Use a timer trick to run in Qt thread
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, wrapper)

        try:
            status, val = result_queue.get(timeout=PAGE_TIMEOUT_MS / 1000 + 5)
            if status == "err":
                raise RuntimeError(val)
            return val
        except Empty:
            raise TimeoutError("Qt operation timed out")

    def _eval_js(self, js: str) -> str:
        """Execute JS in page and return result string."""
        result_queue: Queue = Queue()

        def callback(result):
            result_queue.put(result)

        self._page.runJavaScript(js, 0, callback)
        try:
            return result_queue.get(timeout=10)
        except Empty:
            return json.dumps({"error": "JS eval timeout"})

    # ═══ Public API ═══

    async def navigate(self, url: str) -> WebViewResult:
        t0 = time.monotonic()
        self._page_loaded.clear()
        self._current_url = url

        from PyQt6.QtCore import QUrl, QTimer
        QTimer.singleShot(0, lambda: self._page.load(QUrl(url)))

        if not self._page_loaded.wait(timeout=PAGE_TIMEOUT_MS / 1000):
            return WebViewResult(success=False, url=url, error="page load timeout",
                                 elapsed_ms=(time.monotonic() - t0) * 1000)

        ok = self._load_result.get("ok", False)
        if not ok:
            return WebViewResult(success=False, url=url, error="page load failed",
                                 elapsed_ms=(time.monotonic() - t0) * 1000)

        # Inject stealth + page agent
        self._page.runJavaScript(STEALTH_JS)
        self._page.runJavaScript(PAGE_AGENT_JS)

        title_js = "document.title"
        title_queue: Queue = Queue()
        self._page.runJavaScript(title_js, 0, title_queue.put)
        try:
            title = title_queue.get(timeout=3) or ""
        except Empty:
            title = ""
        self._current_title = title

        return WebViewResult(
            success=True, url=url, title=title,
            method="webview", elapsed_ms=(time.monotonic() - t0) * 1000)

    async def inject(self, js_code: str) -> str:
        """Execute arbitrary JS in page context, return result."""
        result_queue: Queue = Queue()
        self._page.runJavaScript(js_code, 0, result_queue.put)
        try:
            val = result_queue.get(timeout=10)
            return str(val) if val is not None else "null"
        except Empty:
            return json.dumps({"error": "JS execution timeout"})

    async def extract(self, selector: str = "") -> WebViewResult:
        """Extract content from page. If selector given, extract that element.
        Otherwise extract full ARIA tree."""
        t0 = time.monotonic()
        js = f"window.__pg_extract({json.dumps(selector) if selector else 'null'});"
        result_queue: Queue = Queue()
        self._page.runJavaScript(js, 0, result_queue.put)
        try:
            raw = result_queue.get(timeout=10) or "{}"
        except Empty:
            raw = "{}"

        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            data = {"text": str(raw)[:MAX_TEXT]}

        if isinstance(data, dict) and data.get("error"):
            return WebViewResult(success=False, error=data["error"],
                                 elapsed_ms=(time.monotonic() - t0) * 1000)

        return WebViewResult(
            success=True, url=self._current_url, title=self._current_title,
            text=json.dumps(data, ensure_ascii=False)[:MAX_TEXT],
            items=[data] if data else [],
            method="webview_extract",
            elapsed_ms=(time.monotonic() - t0) * 1000)

    async def click(self, selector: str) -> WebViewResult:
        t0 = time.monotonic()
        raw = await self.inject(f"window.__pg_click({json.dumps(selector)});")
        try:
            data = json.loads(raw)
            return WebViewResult(
                success=data.get("ok", False), error=data.get("error", ""),
                text=data.get("text", ""), method="webview_click",
                elapsed_ms=(time.monotonic() - t0) * 1000)
        except json.JSONDecodeError:
            return WebViewResult(success=False, error="invalid response",
                                 elapsed_ms=(time.monotonic() - t0) * 1000)

    async def type_text(self, selector: str, text: str) -> WebViewResult:
        t0 = time.monotonic()
        raw = await self.inject(
            f"window.__pg_type({json.dumps(selector)}, {json.dumps(text)});")
        try:
            data = json.loads(raw)
            return WebViewResult(
                success=data.get("ok", False), error=data.get("error", ""),
                method="webview_type", elapsed_ms=(time.monotonic() - t0) * 1000)
        except json.JSONDecodeError:
            return WebViewResult(success=False, error="invalid response",
                                 elapsed_ms=(time.monotonic() - t0) * 1000)

    async def scroll(self, px: int = 500) -> WebViewResult:
        t0 = time.monotonic()
        raw = await self.inject(f"window.__pg_scroll({px});")
        return WebViewResult(success=True, text=raw, method="webview_scroll",
                             elapsed_ms=(time.monotonic() - t0) * 1000)

    async def fetch_proxy(self, url: str, method: str = "GET",
                          headers: dict | None = None, body: str = "") -> str:
        """Proxy HTTP request through Python (bypass page CORS)."""
        import urllib.request as _req
        try:
            hdrs = headers or {}
            data = body.encode() if body and method.upper() in ("POST", "PUT", "PATCH") else None
            req = _req.Request(url, data=data, headers=hdrs, method=method.upper())
            resp = _req.urlopen(req, timeout=15)
            return resp.read().decode("utf-8", errors="replace")[:10000]
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def wait(self, ms: int = 1000) -> str:
        await asyncio_sleep(ms / 1000)
        return json.dumps({"waited_ms": ms})

    async def screenshot(self) -> str:
        """Returns base64 PNG screenshot."""
        if not self._page:
            return json.dumps({"error": "page not loaded"})
        result_queue: Queue = Queue()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._grab_screenshot(result_queue))
        try:
            b64 = result_queue.get(timeout=10)
            return json.dumps({"screenshot_base64": b64[:100], "truncated": len(b64) > 100})
        except Empty:
            return json.dumps({"error": "screenshot timeout"})

    def _grab_screenshot(self, queue: Queue):
        try:
            pixmap = self._view.grab()
            from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            pixmap.save(buf, "PNG")
            b64 = bytes(buf.data().toBase64()).decode()
            queue.put(b64)
        except Exception as e:
            queue.put(json.dumps({"error": str(e)}))

    def close(self):
        if self._view:
            self._view.close()
            self._view.deleteLater()
            self._view = None
            self._page = None
        WebViewAgent._instance = None


def asyncio_sleep(seconds: float):
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        # Already in async context, use loop directly
        import concurrent.futures
        f = concurrent.futures.Future()

        def done():
            if not f.done():
                f.set_result(None)

        loop.call_later(seconds, done)
        return f
    except RuntimeError:
        import time as _time
        _time.sleep(seconds)
        f = concurrent.futures.Future()
        f.set_result(None)
        return f


# ═══ Singleton ═══

_agent: Optional[WebViewAgent] = None


async def get_webview_agent() -> WebViewAgent:
    global _agent
    if _agent is None:
        _agent = WebViewAgent()
    return _agent


async def browser_inject(url: str, task: str = "extract main content") -> str:
    """Navigate to URL in WebView and execute task.

    The task can use special commands:
      extract [selector]  — extract DOM/ARIA from selector or full page
      click <selector>    — click element
      type <selector> <text> — type into input
      scroll <px>         — scroll page
      wait <ms>           — wait for dynamic content
      eval <js>           — arbitrary JS execution
      fetch <url>         — CORS-bypass proxy fetch

    Args: url, then task description or commands separated by newlines.
    """
    agent = await get_webview_agent()
    result = await agent.navigate(url)
    if not result.success:
        return f"WebView error: {result.error}"

    output_parts = [f"Page: {result.title} ({result.url})"]

    # Parse task into commands
    lines = task.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line or line.startswith("http"):
            continue

        if line.lower().startswith("extract"):
            sel = line[7:].strip().strip('"\'') if len(line) > 7 else ""
            r = await agent.extract(sel)
            output_parts.append(f"[extract] {r.text[:2000]}")

        elif line.lower().startswith("click"):
            sel = line[5:].strip().strip('"\'')
            r = await agent.click(sel)
            output_parts.append(f"[click {sel}] {'OK' if r.success else r.error}")

        elif line.lower().startswith("type "):
            parts = line[5:].strip().split(maxsplit=1)
            sel = parts[0].strip('"\'') if parts else ""
            txt = parts[1].strip('"\'') if len(parts) > 1 else ""
            r = await agent.type_text(sel, txt)
            output_parts.append(f"[type {sel}] {'OK' if r.success else r.error}")

        elif line.lower().startswith("scroll"):
            try:
                px = int(line[6:].strip() or 500)
            except ValueError:
                px = 500
            r = await agent.scroll(px)
            output_parts.append(f"[scroll {px}] done")

        elif line.lower().startswith("wait"):
            try:
                ms = int(line[4:].strip() or 1000)
            except ValueError:
                ms = 1000
            await agent.wait(ms)
            output_parts.append(f"[wait {ms}ms] done")

        elif line.lower().startswith("eval"):
            js = line[4:].strip()
            val = await agent.inject(js)
            output_parts.append(f"[eval] {str(val)[:1000]}")

        elif line.lower().startswith("fetch "):
            proxy_url = line[6:].strip()
            proxy_result = await agent.fetch_proxy(proxy_url)
            output_parts.append(f"[fetch {proxy_url[:60]}] {proxy_result[:500]}")

        elif line.lower().startswith("screenshot"):
            b64 = await agent.screenshot()
            output_parts.append(f"[screenshot] {b64[:200]}")

    return "\n\n".join(output_parts)


__all__ = [
    "WebViewAgent", "WebViewBridge", "WebViewResult",
    "browser_inject", "get_webview_agent",
]
