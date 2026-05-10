"""Chrome Dual-Mode Bridge — npx MCP (preferred) or Python CDP (fallback).

Dual-mode architecture:
  Mode 1 (preferred): npx/node available → npm MCP (autoConnect, full Puppeteer)
  Mode 2 (fallback):   npx unavailable   → Python CDP (chrome --remote-debugging-port=9222)
  Mode 3 (none):       both unavailable  → panel shows setup instructions

All 5 existing endpoints (screenshot, eval, navigate, audit, dom) remain unchanged.
New endpoints: POST /api/chrome/start, POST /api/chrome/stop
"""

from __future__ import annotations

import asyncio
import json as _json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from loguru import logger


_NODE_SCRIPT = Path(__file__).resolve().parent / "chrome_mcp_node.mjs"


class _NpxMCPClient:
    """Communicates with the Node.js MCP server via JSON-RPC over stdio."""

    def __init__(self, script_path: str = ""):
        self._script = script_path or str(_NODE_SCRIPT)
        self._proc: Optional[subprocess.Popen] = None
        self._ready = False
        self._msg_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._reader_tasks: list[asyncio.Task] = []
        self._lock = asyncio.Lock()

    @staticmethod
    def detect_node() -> Optional[str]:
        node = shutil.which("node")
        if node:
            return node
        for p in [
            r"C:\Program Files\nodejs\node.exe",
            r"C:\Program Files (x86)\nodejs\node.exe",
            "/usr/local/bin/node",
            "/usr/bin/node",
        ]:
            if Path(p).is_file():
                return p
        return None

    @staticmethod
    def detect_npx() -> Optional[str]:
        npx = shutil.which("npx")
        if npx:
            return npx
        for p in [
            r"C:\Program Files\nodejs\npx.cmd",
            r"C:\Program Files (x86)\nodejs\npx.cmd",
        ]:
            if Path(p).is_file():
                return p
        return None

    @property
    def ready(self) -> bool:
        return self._ready

    async def start(self, headless: bool = True) -> dict:
        node = self.detect_node()
        if not node:
            return {"ok": False, "error": "node not found", "mode": "npx_mcp"}

        if not Path(self._script).is_file():
            return {"ok": False, "error": f"script not found: {self._script}", "mode": "npx_mcp"}

        try:
            self._proc = subprocess.Popen(
                [node, self._script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            self._reader_tasks.append(asyncio.create_task(self._stdout_reader()))
            self._reader_tasks.append(asyncio.create_task(self._stderr_reader()))
            await asyncio.sleep(0.5)

            result = await self._call("initialize", {"headless": headless}, timeout=30)
            self._ready = result.get("ok", False)
            if self._ready:
                logger.info(f"Chrome npx MCP mode active (node={node})")
            return {"ok": self._ready, "mode": "npx_mcp", "detail": result}
        except Exception as e:
            logger.warning(f"npx MCP start failed: {e}")
            await self.stop()
            return {"ok": False, "error": str(e), "mode": "npx_mcp"}

    async def stop(self):
        self._ready = False
        for task in self._reader_tasks:
            task.cancel()
        self._reader_tasks.clear()
        for fut in self._pending.values():
            if not fut.done():
                fut.set_result({"error": "process stopped"})
        self._pending.clear()
        if self._proc:
            try:
                self._proc.stdin.write(_json.dumps({"jsonrpc": "2.0", "method": "close", "id": 999, "params": {}}) + "\n")
                self._proc.stdin.flush()
            except Exception:
                pass
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

    async def _stderr_reader(self):
        while self._proc and self._proc.stderr:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, self._proc.stderr.readline)
                if not line:
                    break
                line = line.strip()
                if line:
                    logger.debug(f"[npx-mcp] {line}")
            except Exception:
                break

    async def _call(self, method: str, params: dict = None, timeout: int = 15) -> dict:
        if not self._proc or self._proc.poll() is not None:
            return {"error": "process not running"}
        async with self._lock:
            self._msg_id += 1
            msg = {"jsonrpc": "2.0", "id": self._msg_id, "method": method, "params": params or {}}
            future: asyncio.Future = asyncio.get_event_loop().create_future()
            self._pending[self._msg_id] = future
            try:
                self._proc.stdin.write(_json.dumps(msg) + "\n")
                self._proc.stdin.flush()
            except Exception as e:
                return {"error": f"write failed: {e}"}
            try:
                raw = await asyncio.wait_for(future, timeout=timeout)
                return raw
            except asyncio.TimeoutError:
                return {"error": "timeout"}

    async def _stdout_reader(self):
        while self._proc and self._proc.stdout:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, self._proc.stdout.readline)
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                resp = _json.loads(line)
                mid = resp.get("id")
                if mid and mid in self._pending:
                    fut = self._pending.pop(mid)
                    if not fut.done():
                        if "error" in resp:
                            fut.set_result({"error": resp["error"].get("message", str(resp["error"]))})
                        else:
                            result = resp.get("result", {})
                            content = result.get("content", [])
                            if content and isinstance(content, list) and len(content) > 0:
                                text = content[0].get("text", "")
                                try:
                                    fut.set_result(_json.loads(text))
                                except (_json.JSONDecodeError, TypeError):
                                    fut.set_result({"ok": True, "data": text} if isinstance(text, str) else result)
                            else:
                                fut.set_result(result)
            except Exception:
                break


class ChromeDualBridge:
    """Dual-mode Chrome bridge: prefers npx MCP, falls back to Python CDP.

    All 5 existing API methods remain compatible regardless of active mode.
    """

    def __init__(self):
        self._mode: str = "none"             # "npx_mcp", "python_cdp", "none"
        self._mode_label: str = "未检测"       # "npm MCP", "Python CDP", "不可用"
        self._npx_client: Optional[_NpxMCPClient] = None
        self._cdp_bridge = None               # ChromeMCPBridge (lazy)
        self._probed = False
        self._instructions: dict[str, str] = {}
        self._npx_available: bool = False
        self._node_path: str = ""
        self._npx_path: str = ""
        self._headless: bool = True

    # ═══ Probe & Mode Selection ═══

    async def probe(self) -> dict:
        """Detect available modes and determine best option."""
        if self._probed:
            return self.status()

        self._node_path = _NpxMCPClient.detect_node() or ""
        self._npx_path = _NpxMCPClient.detect_npx() or ""
        self._npx_available = bool(self._node_path)

        self._instructions = {}

        if self._npx_available:
            self._mode = "npx_mcp"
            self._mode_label = "npm MCP (Puppeteer)"
            self._instructions["npx_mcp"] = f"node={self._node_path}"
        else:
            self._mode = "python_cdp"
            self._mode_label = "Python CDP"
            self._instructions["python_cdp"] = "chrome --remote-debugging-port=9222"
            if not shutil.which("chrome") and not shutil.which("google-chrome"):
                chrome_found = False
                for b in [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                ]:
                    if Path(b).is_file():
                        chrome_found = True
                        break
                if not chrome_found:
                    self._mode = "none"
                    self._mode_label = "不可用"
                    self._instructions["setup"] = "请安装 Node.js (含 npx) 或 Google Chrome 浏览器"
                    self._instructions["npx_setup"] = "安装 Node.js: https://nodejs.org (推荐, 获得自动连接)"
                    self._instructions["cdp_setup"] = "或安装 Chrome 并以调试模式启动: chrome --remote-debugging-port=9222"

        self._probed = True
        logger.info(f"ChromeDualBridge: mode={self._mode} ({self._mode_label})")
        return self.status()

    # ═══ Lifecycle ═══

    async def start(self, headless: bool = None) -> dict:
        """Start Chrome in the best available mode."""
        if not self._probed:
            await self.probe()

        if headless is not None:
            self._headless = headless

        if self._mode == "npx_mcp":
            self._npx_client = _NpxMCPClient()
            result = await self._npx_client.start(headless=self._headless)
            return result

        elif self._mode == "python_cdp":
            from .chrome_mcp import get_chrome_bridge
            self._cdp_bridge = get_chrome_bridge()
            ok = await self._cdp_bridge.start(headless=self._headless)
            return {"ok": ok, "mode": "python_cdp", "detail": self._cdp_bridge.status()}

        else:
            return {"ok": False, "mode": "none", "error": "No Chrome mode available"}

    async def stop(self) -> dict:
        """Stop Chrome in the active mode."""
        if self._npx_client:
            await self._npx_client.stop()
            self._npx_client = None

        if self._cdp_bridge:
            await self._cdp_bridge.stop()

        return {"ok": True, "mode": self._mode}

    @property
    def is_available(self) -> bool:
        if self._mode == "npx_mcp":
            return self._npx_client is not None and self._npx_client.ready
        elif self._mode == "python_cdp":
            return self._cdp_bridge is not None and self._cdp_bridge.is_available
        return False

    def status(self) -> dict:
        """Return current mode, availability, and setup instructions."""
        info: dict[str, Any] = {
            "available": self.is_available,
            "mode": self._mode,
            "mode_label": self._mode_label,
            "npx_available": self._npx_available,
            "node_path": self._node_path,
            "npx_path": self._npx_path,
        }
        if self._mode == "npx_mcp" and self._npx_client:
            info["detail"] = "npm MCP (Puppeteer — autoConnect)"
        elif self._mode == "python_cdp" and self._cdp_bridge:
            info["detail"] = self._cdp_bridge.status()
        elif self._mode == "python_cdp":
            info["detail"] = "Python CDP — 需要手动启动: chrome --remote-debugging-port=9222"
        info["instructions"] = self._instructions
        return info

    # ═══ Unified API (delegates to active mode) ═══

    async def _ensure_cdp(self):
        if self._cdp_bridge is None:
            from .chrome_mcp import get_chrome_bridge
            self._cdp_bridge = get_chrome_bridge()

    async def screenshot(self, selector: str = "", full_page: bool = False) -> dict:
        if self._mode == "npx_mcp" and self._npx_client and self._npx_client.ready:
            params = {}
            if selector:
                params["selector"] = selector
            if full_page:
                params["full_page"] = True
            return await self._npx_client._call("screenshot", params)
        await self._ensure_cdp()
        return await self._cdp_bridge.screenshot(selector=selector, full_page=full_page)

    async def eval_js(self, expression: str) -> dict:
        if self._mode == "npx_mcp" and self._npx_client and self._npx_client.ready:
            return await self._npx_client._call("evaluate", {"expression": expression})
        await self._ensure_cdp()
        return await self._cdp_bridge.eval_js(expression)

    async def navigate(self, url: str) -> dict:
        if self._mode == "npx_mcp" and self._npx_client and self._npx_client.ready:
            return await self._npx_client._call("navigate", {"url": url})
        await self._ensure_cdp()
        return await self._cdp_bridge.navigate(url)

    async def accessibility_audit(self) -> dict:
        if self._mode == "npx_mcp" and self._npx_client and self._npx_client.ready:
            return await self._npx_client._call("accessibility_audit", {})
        await self._ensure_cdp()
        return await self._cdp_bridge.accessibility_audit()

    async def dom_query(self, selector: str) -> dict:
        if self._mode == "npx_mcp" and self._npx_client and self._npx_client.ready:
            return await self._npx_client._call("dom_query", {"selector": selector})
        await self._ensure_cdp()
        return await self._cdp_bridge.dom_query(selector)


_dual_instance: Optional[ChromeDualBridge] = None


def get_chrome_dual() -> ChromeDualBridge:
    global _dual_instance
    if _dual_instance is None:
        _dual_instance = ChromeDualBridge()
    return _dual_instance
