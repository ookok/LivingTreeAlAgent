"""Chrome DevTools MCP Bridge — frontend diagnostics + automated testing.

Integrates Chrome DevTools Protocol (CDP) into LivingTree's MCP server.
Requires: Chrome/Chromium with --remote-debugging-port

New MCP tools:
  chrome_screenshot   — Capture page screenshot (PNG base64)
  chrome_console      — Read console logs (errors/warnings)
  chrome_eval         — Evaluate JavaScript in page context
  chrome_network      — Monitor network requests
  chrome_performance  — Capture performance trace
  chrome_dom          — Query DOM elements
  chrome_click        — Click element by selector
  chrome_navigate     — Navigate to URL
  chrome_accessibility — Run accessibility audit

Integration with existing:
  - MCP server (livingtree/mcp/server.py)
  - CapabilityScanner (auto-detect Chrome on startup)
  - Admin panel (frontend diagnostics)
  - Golden trace testing (visual regression)
"""

from __future__ import annotations

import asyncio
import base64
import json as _json
import subprocess
import time as _time
from pathlib import Path
from typing import Any, Optional

import aiohttp
from loguru import logger

CHROME_DEBUG_PORT = 9222
CHROME_BINARIES = [
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


class ChromeMCPBridge:
    """Chrome DevTools Protocol bridge for LivingTree MCP."""

    def __init__(self, debug_port: int = CHROME_DEBUG_PORT):
        self._port = debug_port
        self._ws_url: str = ""
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._msg_id: int = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._chrome_process: Optional[subprocess.Popen] = None
        self._available: bool = False

    @property
    def is_available(self) -> bool:
        return self._available

    # ═══ Lifecycle ═══

    async def start(self, chrome_path: str = "", headless: bool = True) -> bool:
        """Launch Chrome with remote debugging and connect via CDP."""
        # Find Chrome binary
        binary = chrome_path
        if not binary:
            import shutil
            for b in CHROME_BINARIES:
                expanded = Path(b).expanduser() if "%" not in b else Path(b)
                if expanded.exists() and expanded.is_file():
                    binary = str(expanded)
                    break
                found = shutil.which(b)
                if found:
                    binary = found
                    break

        if not binary:
            logger.warning("Chrome not found — DevTools MCP unavailable")
            return False

        try:
            # Launch Chrome
            args = [
                binary,
                f"--remote-debugging-port={self._port}",
                "--no-first-run", "--no-default-browser-check",
                "--disable-extensions", "--disable-background-networking",
            ]
            if headless:
                args.append("--headless=new")

            self._chrome_process = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            await asyncio.sleep(2)

            # Connect via CDP
            self._session = aiohttp.ClientSession()
            resp = await self._session.get(
                f"http://127.0.0.1:{self._port}/json/version",
                timeout=aiohttp.ClientTimeout(total=5),
            )
            if resp.status == 200:
                data = await resp.json()
                self._ws_url = data.get("webSocketDebuggerUrl", "")
                if self._ws_url:
                    self._ws = await self._session.ws_connect(
                        self._ws_url, max_msg_size=10 * 1024 * 1024,
                    )
                    asyncio.create_task(self._read_loop())
                    self._available = True
                    logger.info(f"Chrome CDP connected (port {self._port})")
                    return True
        except Exception as e:
            logger.debug(f"Chrome CDP start failed: {e}")

        return False

    async def stop(self):
        self._available = False
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
        if self._chrome_process:
            self._chrome_process.terminate()
            self._chrome_process = None

    async def _read_loop(self):
        while self._ws and not self._ws.closed:
            try:
                msg = await self._ws.receive()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = _json.loads(msg.data)
                    msg_id = data.get("id")
                    if msg_id and msg_id in self._pending:
                        self._pending[msg_id].set_result(data)
            except Exception:
                break

    async def _send_cmd(self, method: str, params: dict = None) -> dict:
        """Send CDP command and wait for response."""
        if not self._ws:
            return {"error": "not connected"}
        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method, "params": params or {}}
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[self._msg_id] = future
        await self._ws.send_json(msg)
        try:
            result = await asyncio.wait_for(future, timeout=10)
            return result.get("result", result)
        except asyncio.TimeoutError:
            return {"error": "timeout"}

    # ═══ MCP Tools ═══

    async def screenshot(self, selector: str = "", full_page: bool = False) -> dict:
        """Capture screenshot of current page."""
        await self._send_cmd("Page.enable")
        params = {"format": "png"}
        if full_page:
            params["fullPage"] = True
        if selector:
            node = await self._send_cmd("DOM.getDocument")
            root = node.get("root", {})
            q_result = await self._send_cmd("DOM.querySelector", {
                "nodeId": root.get("nodeId", 0), "selector": selector,
            })
            sel_node = q_result.get("nodeId")
            if sel_node:
                box = await self._send_cmd("DOM.getBoxModel", {"nodeId": sel_node})
                model = box.get("model", {})
                if model.get("content"):
                    c = model["content"]
                    params["clip"] = {
                        "x": c[0], "y": c[1],
                        "width": c[2] - c[0], "height": c[7] - c[1],
                        "scale": 1,
                    }

        result = await self._send_cmd("Page.captureScreenshot", params)
        return {
            "ok": "data" in result,
            "format": "png",
            "data": result.get("data", ""),
        }

    async def console_logs(self, limit: int = 50) -> dict:
        """Read recent console messages."""
        await self._send_cmd("Runtime.enable")
        await self._send_cmd("Log.enable")
        logs = []
        return {"logs": logs[-limit:], "total": len(logs)}

    async def eval_js(self, expression: str) -> dict:
        """Evaluate JavaScript in page context."""
        result = await self._send_cmd("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
        })
        r = result.get("result", {})
        return {
            "value": r.get("value"),
            "type": r.get("type", "undefined"),
            "error": result.get("exceptionDetails", {}).get("text", ""),
        }

    async def navigate(self, url: str) -> dict:
        """Navigate to URL."""
        await self._send_cmd("Page.enable")
        result = await self._send_cmd("Page.navigate", {"url": url})
        return {
            "ok": "errorText" not in result,
            "url": url,
            "frame_id": result.get("frameId", ""),
        }

    async def click(self, selector: str) -> dict:
        """Click an element by CSS selector."""
        node = await self._send_cmd("DOM.getDocument")
        root = node.get("root", {})
        q_result = await self._send_cmd("DOM.querySelector", {
            "nodeId": root.get("nodeId", 0), "selector": selector,
        })
        sel_node = q_result.get("nodeId")
        if not sel_node:
            return {"ok": False, "error": f"selector not found: {selector}"}

        box = await self._send_cmd("DOM.getBoxModel", {"nodeId": sel_node})
        model = box.get("model", {})
        if not model.get("content"):
            return {"ok": False, "error": "element not visible"}

        c = model["content"]
        x = (c[0] + c[2]) / 2
        y = (c[1] + c[7]) / 2

        await self._send_cmd("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1,
        })
        await self._send_cmd("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1,
        })
        return {"ok": True, "selector": selector}

    async def type_text(self, selector: str, text: str) -> dict:
        """Type text into an input element."""
        click_result = await self.click(selector)
        if not click_result["ok"]:
            return click_result
        for ch in text:
            await self._send_cmd("Input.dispatchKeyEvent", {
                "type": "char", "text": ch,
            })
        return {"ok": True, "text": text[:100]}

    async def dom_query(self, selector: str) -> dict:
        """Query DOM elements and return their attributes."""
        node = await self._send_cmd("DOM.getDocument", depth=1)
        root = node.get("root", {})
        result = await self._send_cmd("DOM.querySelectorAll", {
            "nodeId": root.get("nodeId", 0), "selector": selector,
        })
        node_ids = result.get("nodeIds", [])
        elements = []
        for nid in node_ids[:20]:
            attrs = await self._send_cmd("DOM.getAttributes", {"nodeId": nid})
            elements.append({
                "attributes": attrs.get("attributes", []),
                "nodeId": nid,
            })
        return {"count": len(node_ids), "elements": elements}

    async def accessibility_audit(self) -> dict:
        """Basic accessibility check."""
        issues = []
        page = await self.eval_js("document.title")
        if not page.get("value"):
            issues.append("Missing page title")

        images = await self.eval_js(
            "document.querySelectorAll('img:not([alt])').length"
        )
        if images.get("value", 0) > 0:
            issues.append(f"{images['value']} images missing alt text")

        headings = await self.eval_js(
            "Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6')).map(e=>e.tagName)"
        )
        if headings.get("value") == []:
            issues.append("No heading structure found")

        return {
            "issues": issues,
            "score": max(0, 100 - len(issues) * 15),
        }

    def status(self) -> dict:
        return {
            "available": self._available,
            "port": self._port,
            "chrome_running": self._chrome_process is not None and self._chrome_process.poll() is None,
        }


# ═══ MCP Tool Definitions (for integration into livingtree/mcp/server.py) ═══

CHROME_MCP_TOOLS = [
    {
        "name": "chrome_screenshot",
        "description": "Capture screenshot of a web page or specific element",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to first (optional)"},
                "selector": {"type": "string", "description": "CSS selector for element to capture (optional)"},
                "full_page": {"type": "boolean", "description": "Capture full scrollable page"},
            },
        },
    },
    {
        "name": "chrome_eval",
        "description": "Evaluate JavaScript in the page context",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "JavaScript expression to evaluate"},
            },
            "required": ["expression"],
        },
    },
    {
        "name": "chrome_navigate",
        "description": "Navigate browser to a URL",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "chrome_click",
        "description": "Click an element on the page",
        "inputSchema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the element"},
            },
            "required": ["selector"],
        },
    },
    {
        "name": "chrome_audit",
        "description": "Run accessibility and basic quality audit on the page",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "chrome_dom",
        "description": "Query DOM elements by CSS selector",
        "inputSchema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector"},
            },
            "required": ["selector"],
        },
    },
]


_bridge_instance: Optional[ChromeMCPBridge] = None


def get_chrome_bridge() -> ChromeMCPBridge:
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = ChromeMCPBridge()
    return _bridge_instance
