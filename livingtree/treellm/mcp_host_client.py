"""MCP Host Client — Standard MCP JSON-RPC subprocess client.

Connects to external MCP servers (Parallel Search, etc.) via subprocess stdio
using the standard MCP JSON-RPC protocol (tools/list, tools/call, initialize).

Supported launchers: npx (npm), uvx (Python), direct command.

Usage:
    client = MCPHostClient.launch("parallel-search", command="npx",
                                   args=["-y", "@parallel-web/mcp-server"])
    await client.initialize()
    result = await client.call_tool("web_search", query="AI research")
    await client.shutdown()
"""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class MCPHostTool:
    name: str
    description: str
    input_schema: dict


@dataclass
class MCPHostResult:
    success: bool
    content: Any
    tool_name: str = ""
    error: str = ""
    execution_time: float = 0.0


# Built-in MCP server registrations — add new servers here
MCP_SERVER_REGISTRY: dict[str, dict] = {
    "parallel-search": {
        "name": "Parallel Search",
        "description": "Parallel Web Systems search MCP server — web_search + web_fetch, free tier, zero API key needed",
        "command": "npx",
        "args": ["-y", "@parallel-web/mcp-server"],
        "env": None,
        "tools": ["web_search", "web_fetch"],
    },
    "filesystem": {
        "name": "Filesystem",
        "description": "Secure file system access MCP server — read/write/list files with sandboxed paths",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        "env": None,
        "tools": ["read_file", "write_file", "list_directory", "move_file", "search_files", "get_file_info"],
    },
    "sqlite": {
        "name": "SQLite",
        "description": "SQLite database MCP server — query/insert/update with parameterized queries",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite", "livingtree.db"],
        "env": None,
        "tools": ["read_query", "write_query", "create_table", "list_tables", "describe_table"],
    },
    "github": {
        "name": "GitHub",
        "description": "GitHub API MCP server — repo ops, issues, PRs, code search. Requires GITHUB_TOKEN env",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
        "tools": ["search_repositories", "get_file_contents", "create_issue", "list_pull_requests"],
    },
    "brave-search": {
        "name": "Brave Search",
        "description": "Brave Search API MCP server — web + news + local search. Requires BRAVE_API_KEY env",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
        "tools": ["web_search", "news_search", "local_search"],
    },
    "fetch": {
        "name": "Fetch",
        "description": "Web content fetching MCP server — fetch URLs as markdown/html/text",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-fetch"],
        "env": None,
        "tools": ["fetch", "fetch_markdown"],
    },
}

_SERVER_PRESETS: dict[str, dict] = dict(MCP_SERVER_REGISTRY)


def register_mcp_server(name: str, command: str, args: list[str],
                         description: str = "", tools: list[str] = None,
                         env: dict = None) -> None:
    """Register an external MCP server for auto-connection."""
    _SERVER_PRESETS[name] = {
        "name": name, "description": description or name,
        "command": command, "args": args, "env": env,
        "tools": tools or [],
    }


class MCPHostClient:
    """Standard MCP JSON-RPC client over subprocess stdio.

    Launches an external MCP server as a subprocess (npx, uvx, or direct command),
    sends JSON-RPC 2.0 requests, and reads JSON-RPC responses from stdout.

    Protocol flow:
        1. Launch subprocess
        2. Send initialize request → receive capabilities
        3. Send tools/list → discover available tools
        4. Send tools/call → invoke tool
        5. Terminate subprocess on shutdown
    """

    def __init__(self, server_id: str, command: str, args: list[str],
                 env: dict = None, startup_timeout: float = 30.0):
        self.server_id = server_id
        self.command = command
        self.args = list(args)
        self.env = env or {}
        self.startup_timeout = startup_timeout
        self._process: asyncio.subprocess.Process | None = None
        self._tools: dict[str, MCPHostTool] = {}
        self._ready = False
        self._request_id = 0
        self._total_calls = 0

    @classmethod
    def launch(cls, server_id: str, command: str = None, args: list[str] = None,
               startup_timeout: float = 30.0) -> "MCPHostClient":
        """Factory: launch from preset registry or explicit command/args.

        Args:
            server_id: Preset name (e.g. 'parallel-search') or unique ID
            command: Override command (uses preset if None)
            args: Override args (uses preset if None)
            startup_timeout: Max seconds to wait for server readiness
        """
        preset = _SERVER_PRESETS.get(server_id, {})
        cmd = command or preset.get("command", server_id)
        cli_args = args or preset.get("args", [])
        env = preset.get("env")
        return cls(server_id, cmd, cli_args, env, startup_timeout)

    @classmethod
    def presets(cls) -> dict[str, dict]:
        """Return all registered MCP server presets."""
        return dict(_SERVER_PRESETS)

    # ── Lifecycle ──────────────────────────────────────────────────

    async def initialize(self) -> bool:
        """Launch subprocess and perform MCP handshake. Returns True if ready.
        
        Uses asyncio.create_subprocess_exec with stdio pipes for MCP JSON-RPC
        protocol — unified_exec.run does not support bidirectional pipe I/O.
        """
        if self._ready:
            return True

        cmd = self._resolve_command()
        if not cmd:
            logger.warning(f"MCPHostClient [{self.server_id}]: {self.command} not found in PATH")
            return False

        env_full = {}
        env_full.update(__import__('os').environ)
        env_full.update(self.env)

        try:
            self._process = await asyncio.create_subprocess_exec(
                cmd, *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env_full,
            )
        except Exception as e:
            logger.error(f"MCPHostClient [{self.server_id}]: launch failed: {e}")
            self._process = None
            return False

        # MCP initialize handshake
        try:
            init_resp = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "livingtree-mcp-client", "version": "2.5.0"},
            })
            if init_resp:
                logger.info(f"MCPHostClient [{self.server_id}]: initialized "
                             f"(server={json.dumps(init_resp.get('serverInfo',{}), default=str)})")
            # Send initialized notification
            await self._send_notification("notifications/initialized", {})
        except Exception as e:
            logger.error(f"MCPHostClient [{self.server_id}]: init failed: {e}")
            await self.shutdown()
            return False

        # Discover tools
        try:
            tools_resp = await self._send_request("tools/list", {})
            tools = tools_resp.get("tools", []) if tools_resp else []
            for t in tools:
                self._tools[t["name"]] = MCPHostTool(
                    name=t["name"], description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                )
            logger.info(f"MCPHostClient [{self.server_id}]: {len(self._tools)} tools discovered: "
                         f"{list(self._tools.keys())}")
        except Exception as e:
            logger.error(f"MCPHostClient [{self.server_id}]: tool discovery failed: {e}")
            await self.shutdown()
            return False

        self._ready = True
        return True

    async def shutdown(self) -> None:
        """Terminate the MCP server subprocess."""
        self._ready = False
        if self._process:
            try:
                self._process.stdin.close()
            except Exception:
                pass
            try:
                self._process.kill()
                await self._process.wait()
            except Exception:
                pass
            self._process = None
        logger.info(f"MCPHostClient [{self.server_id}]: shutdown")

    # ── Tool Discovery ─────────────────────────────────────────────

    @property
    def tools(self) -> dict[str, MCPHostTool]:
        return self._tools

    @property
    def is_ready(self) -> bool:
        return self._ready and self._process is not None and self._process.returncode is None

    def get_tool(self, name: str) -> MCPHostTool | None:
        return self._tools.get(name)

    # ── Tool Invocation ────────────────────────────────────────────

    async def call_tool(self, tool_name: str, **params) -> MCPHostResult:
        """Invoke an MCP tool. Returns MCPHostResult with success/content/error."""
        t0 = time.time()
        if not self.is_ready:
            return MCPHostResult(False, None, tool_name, "MCP server not ready",
                                 time.time() - t0)

        if tool_name not in self._tools:
            return MCPHostResult(False, None, tool_name,
                                 f"Unknown tool: {tool_name} (available: {list(self._tools.keys())})",
                                 time.time() - t0)

        self._total_calls += 1
        try:
            raw = await self._send_request("tools/call", {
                "name": tool_name,
                "arguments": {k: v for k, v in params.items() if v is not None},
            })
            content = raw.get("content", []) if raw else []
            text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
            result = "\n".join(text_parts) if text_parts else json.dumps(content, ensure_ascii=False)
            return MCPHostResult(True, result, tool_name, "",
                                 (time.time() - t0) * 1000)
        except Exception as e:
            logger.error(f"MCPHostClient [{self.server_id}]: call '{tool_name}' failed: {e}")
            return MCPHostResult(False, None, tool_name, str(e),
                                 (time.time() - t0) * 1000)

    # ── Command Resolution ─────────────────────────────────────────

    def _resolve_command(self) -> str | None:
        """Resolve the subprocess command, handling Windows .ps1/.cmd quirks."""
        import os as _os
        found = shutil.which(self.command)
        if not found:
            return None
        if _os.name == "nt" and found.endswith(".ps1"):
            cmd_path = found[:-4] + ".cmd"
            if _os.path.isfile(cmd_path):
                return cmd_path
        return found

    # ── JSON-RPC Wire Protocol ─────────────────────────────────────

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _send_request(self, method: str, params: dict,
                             timeout: float = 60.0) -> dict | None:
        """Send a JSON-RPC request and return the result."""
        if not self._process or self._process.returncode is not None:
            raise RuntimeError("MCP subprocess not running")

        req_id = self._next_id()
        request = json.dumps({
            "jsonrpc": "2.0", "id": req_id,
            "method": method, "params": params,
        }, ensure_ascii=False)
        payload = (request + "\n").encode("utf-8")

        try:
            self._process.stdin.write(payload)
            await self._process.stdin.drain()
        except Exception as e:
            raise RuntimeError(f"Write failed: {e}") from e

        try:
            line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Timeout waiting for response to {method}")

        if not line:
            raise RuntimeError(f"EOF from subprocess during {method}")

        try:
            response = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as e:
            raw = line.decode("utf-8", errors="replace")
            raise RuntimeError(f"Invalid JSON response: {raw[:200]}") from e

        if "error" in response:
            err = response["error"]
            raise RuntimeError(f"MCP error [{err.get('code','?')}]: {err.get('message','?')}")

        return response.get("result")

    async def _send_notification(self, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._process or self._process.returncode is not None:
            return
        try:
            notif = json.dumps({
                "jsonrpc": "2.0", "method": method, "params": params,
            }, ensure_ascii=False)
            self._process.stdin.write((notif + "\n").encode("utf-8"))
            await self._process.stdin.drain()
        except Exception:
            pass

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "server_id": self.server_id,
            "ready": self._ready,
            "tools": list(self._tools.keys()),
            "total_calls": self._total_calls,
            "command": f"{self.command} {' '.join(self.args)}",
        }


# ═══ Singleton pool ══════════════════════════════════════════════

_hosts: dict[str, MCPHostClient] = {}


async def get_mcp_host(server_id: str, command: str = None,
                        args: list[str] = None) -> MCPHostClient | None:
    """Get or create an MCP host client (singleton per server_id).

    Returns None if the server command is not found on PATH.
    """
    if server_id in _hosts:
        host = _hosts[server_id]
        if host.is_ready:
            return host
        await host.shutdown()
        del _hosts[server_id]

    host = MCPHostClient.launch(server_id, command, args)
    if await host.initialize():
        _hosts[server_id] = host
        return host

    await host.shutdown()
    return None


async def shutdown_all_hosts() -> None:
    for host in list(_hosts.values()):
        await host.shutdown()
    _hosts.clear()


async def call_mcp_tool(server_id: str, tool_name: str, **params) -> MCPHostResult:
    """Convenience: get or create host, call tool, return result.

    Creates the host on first call, reuses for subsequent calls.
    Returns error result if server is unreachable.
    """
    host = await get_mcp_host(server_id)
    if host is None:
        return MCPHostResult(False, None, tool_name,
                              f"MCP server '{server_id}' is unavailable")

    return await host.call_tool(tool_name, **params)
