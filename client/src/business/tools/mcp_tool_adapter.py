"""
MCP Tool Adapter — MCP Server 工具支持
=============================================

将 MCP (Model Context Protocol) Server 暴露的工具
适配为项目标准 BaseTool 接口，并自动注册到 ToolRegistry。

支持两种 MCP Server 连接方式：
  - stdio：启动子进程，通过 stdin/stdout 收发 JSON-RPC 2.0 消息
  - HTTP：向 MCP Server 的 HTTP 端点发送 POST 请求

快速上手
----------
>>> from client.src.business.tools.mcp_tool_adapter import MCPToolDiscoverer
>>> discoverer = MCPToolDiscoverer()
>>> discoverer.add_stdio_server("filesystem", ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"])
>>> adapters = discoverer.discover_all()
>>> len(adapters)
8
"""

import json
import logging
import subprocess
import time
from typing import Any, Dict, List, Optional

import requests

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_registry import ToolRegistry
from client.src.business.tools.tool_result import ToolResult

logger = logging.getLogger(__name__)

# ── 单个 MCP 工具的适配器 ────────────────────────────────────────────────

class MCPToolAdapter(BaseTool):
    """
    MCP 工具 → BaseTool 适配器

    每个 MCP Server 暴露的 tool 对应一个 MCPToolAdapter 实例。
    调用 execute() 时，通过 stdio 或 HTTP 将请求转发给 MCP Server。

    Examples
    --------
    >>> adapter.execute(path="/tmp/test.txt", content="hello")
    ToolResult(success=True, data="...")
    """

    def __init__(
        self,
        mcp_server_name: str,
        mcp_tool: Dict[str, Any],
        server_command: Optional[List[str]] = None,
        server_url: Optional[str] = None,
    ):
        """
        Args:
            mcp_server_name:  MCP Server 名称（用于日志 / 工具命名）
            mcp_tool:         MCP tools/list 返回的单个 tool 字典
            server_command:    stdio 模式：启动 Server 的命令
            server_url:       HTTP 模式：Server 的 URL
        """
        self._mcp_server_name = mcp_server_name
        self._mcp_tool = mcp_tool
        self._server_command = server_command
        self._server_url = server_url

        tool_name = mcp_tool.get("name", "unknown")
        self._tool_name = tool_name
        self._input_schema: Dict = mcp_tool.get("inputSchema", {})

        display_name = f"mcp_{mcp_server_name}_{tool_name}"
        description = mcp_tool.get("description", f"MCP tool: {tool_name}")

        super().__init__(name=display_name, description=description)

    # ── BaseTool 接口 ─────────────────────────────────────────────────

    def execute(self, **kwargs) -> ToolResult:
        """
        执行 MCP 工具

        MCP tools/call 的参数放在 params.arguments 里，
        返回值在 result.content[?type=text].text。
        """
        try:
            request = self._build_request("tools/call", {
                "name": self._tool_name,
                "arguments": kwargs,
            })

            raw = self._send_request(request)
            result = raw.get("result", {})

            # MCP 规范：content 是 List[{"type": "text", "text": "..."}]
            contents = result.get("content", [])
            texts = [
                item.get("text", "")
                for item in contents
                if item.get("type") == "text"
            ]
            data = "\n".join(texts) if texts else json.dumps(result, ensure_ascii=False)

            # 检查 isError
            if result.get("isError"):
                return ToolResult(success=False, error=data)

            return ToolResult(success=True, data=data, metadata={
                "mcp_server": self._mcp_server_name,
                "mcp_tool": self._tool_name,
            })

        except Exception as e:
            logger.exception(f"MCP 工具执行失败: {self.name}")
            return ToolResult(success=False, error=str(e))

    # ── 内部方法 ─────────────────────────────────────────────────────

    def _build_request(self, method: str, params: Dict) -> Dict:
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }

    def _send_request(self, request: Dict) -> Dict:
        """根据连接方式（stdio / HTTP）发送请求并解析响应。"""
        if self._server_command:
            return self._send_stdio(request)
        elif self._server_url:
            return self._send_http(request)
        else:
            raise RuntimeError("未配置 server_command 或 server_url")

    def _send_stdio(self, request: Dict) -> Dict:
        """通过 stdio 与 MCP Server 通信。"""
        proc = subprocess.Popen(
            self._server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        try:
            request_line = json.dumps(request, ensure_ascii=False) + "\n"
            proc.stdin.write(request_line)
            proc.stdin.flush()

            # 读取单行 JSON-RPC 响应（MCP Server 规范行为）
            response_line = proc.stdout.readline()
            if not response_line:
                raise RuntimeError("MCP Server 未返回响应（进程可能已退出）")

            response = json.loads(response_line)

            if "error" in response:
                raise RuntimeError(f"MCP Server 返回错误: {response['error']}")

            return response

        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def _send_http(self, request: Dict) -> Dict:
        """通过 HTTP POST 与 MCP Server 通信。"""
        resp = requests.post(
            self._server_url,
            json=request,
            timeout=30,
        )
        response = resp.json()

        if "error" in response:
            raise RuntimeError(f"MCP Server 返回错误: {response['error']}")

        return response

    # ── 工具定义（供 ToolRegistry 语义搜索用） ─────────────────────

    @property
    def input_schema(self) -> Dict:
        """返回 MCP tool 的 inputSchema，供参数校验使用。"""
        return self._input_schema


# ── MCP Server 发现器 ──────────────────────────────────────────────────

class MCPToolDiscoverer:
    """
    MCP Server 工具发现器

    管理已配置的 MCP Server，调用 tools/list 发现工具，
    自动包装为 MCPToolAdapter 并注册到 ToolRegistry。

    Examples
    --------
    >>> discoverer = MCPToolDiscoverer()
    >>> discoverer.add_stdio_server(
    ...     "filesystem",
    ...     ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    ... )
    >>> discoverer.add_http_server(
    ...     "my-mcp-server",
    ...     "http://localhost:8080/mcp"
    ... )
    >>> adapters = discoverer.discover_all()
    """

    def __init__(self):
        self._servers: Dict[str, Dict[str, Any]] = {}
        self._registry = ToolRegistry.get_instance()

    # ── 注册 MCP Server ─────────────────────────────────────────────

    def add_stdio_server(self, name: str, command: List[str]):
        """
        注册一个 stdio 类型的 MCP Server

        Args:
            name:    Server 名称（唯一标识）
            command: 启动 Server 的命令，如 ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
        """
        self._servers[name] = {
            "type": "stdio",
            "command": command,
        }
        logger.info(f"[MCP] 注册 stdio Server: {name}, 命令: {command}")

    def add_http_server(self, name: str, url: str):
        """
        注册一个 HTTP 类型的 MCP Server

        Args:
            name: Server 名称（唯一标识）
            url:  Server 的 HTTP 端点，如 "http://localhost:8080/mcp"
        """
        self._servers[name] = {
            "type": "http",
            "url": url,
        }
        logger.info(f"[MCP] 注册 HTTP Server: {name}, URL: {url}")

    # ── 发现并注册工具 ─────────────────────────────────────────────

    def discover_all(self) -> List[MCPToolAdapter]:
        """发现所有已注册 Server 的工具，并注册到 ToolRegistry。"""
        adapters: List[MCPToolAdapter] = []
        for name, config in self._servers.items():
            try:
                server_adapters = self._discover_server(name, config)
                adapters.extend(server_adapters)
            except Exception as e:
                logger.error(f"[MCP] 发现 Server {name} 失败: {e}")
        return adapters

    def _discover_server(self, name: str, config: Dict) -> List[MCPToolAdapter]:
        """发现单个 Server 的工具列表。"""
        # 发送 tools/list 请求
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
        }

        if config["type"] == "stdio":
            raw = self._stdio_call(config["command"], request)
        else:
            raw = self._http_call(config["url"], request)

        if "error" in raw:
            raise RuntimeError(f"MCP Server 错误: {raw['error']}")

        tools = raw.get("result", {}).get("tools", [])
        logger.info(f"[MCP] Server {name} 返回 {len(tools)} 个工具")

        adapters = []
        for tool in tools:
            if config["type"] == "stdio":
                adapter = MCPToolAdapter(
                    mcp_server_name=name,
                    mcp_tool=tool,
                    server_command=config["command"],
                )
            else:
                adapter = MCPToolAdapter(
                    mcp_server_name=name,
                    mcp_tool=tool,
                    server_url=config["url"],
                )

            # 注册到 ToolRegistry
            self._registry.register_tool(adapter)
            adapters.append(adapter)
            logger.info(f"[MCP] 注册工具: {adapter.name}")

        return adapters

    # ── 底层通信 ─────────────────────────────────────────────────

    def _stdio_call(self, command: List[str], request: Dict) -> Dict:
        """通过 stdio 调用 MCP Server，返回解析后的 JSON-RPC 响应。"""
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        try:
            proc.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            proc.stdin.flush()
            response_line = proc.stdout.readline()
            if not response_line:
                stderr = proc.stderr.read()
                raise RuntimeError(f"MCP Server 未返回响应: {stderr[:200]}")
            return json.loads(response_line)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def _http_call(self, url: str, request: Dict) -> Dict:
        """通过 HTTP POST 调用 MCP Server。"""
        resp = requests.post(url, json=request, timeout=30)
        return resp.json()


# ── 便捷函数 ─────────────────────────────────────────────────────────

def discover_mcp_tools(configs: Optional[Dict[str, Dict]] = None) -> List[MCPToolAdapter]:
    """
    便捷函数：发现并注册所有 MCP Server 的工具

    Args:
        configs:  Server 配置字典，格式：
                  {
                      "filesystem": {"type": "stdio", "command": ["npx", "..."]},
                      "my-server": {"type": "http", "url": "http://localhost:8080/mcp"},
                  }
                为 None 时读取项目配置。

    Returns:
        已注册的 MCPToolAdapter 列表
    """
    discoverer = MCPToolDiscoverer()

    if configs is None:
        # 从项目配置读取（~/.livingtree/mcp_servers.json）
        import pathlib
        config_path = pathlib.Path.home() / ".livingtree" / "mcp_servers.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                configs = json.load(f)
        else:
            logger.warning("[MCP] 未找到 mcp_servers.json，未发现任何 Server")
            return []

    for name, cfg in configs.items():
        if cfg["type"] == "stdio":
            discoverer.add_stdio_server(name, cfg["command"])
        else:
            discoverer.add_http_server(name, cfg["url"])

    return discoverer.discover_all()
