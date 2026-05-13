"""
MCP Manager — Re-export from livingtree.mcp
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MCPServerInfo:
    name: str = ""
    status: str = "stopped"
    tools: list = field(default_factory=list)


@dataclass
class MCPToolDef:
    name: str = ""
    description: str = ""
    inputSchema: dict = field(default_factory=dict)


class MCPClient:
    """Stub MCP client."""
    def list_tools(self): return []
    def call_tool(self, name, params): return {}


class MCPDatabase:
    """Stub MCP database."""
    pass


class MCPServerManager:
    """Stub MCP server manager."""
    def start(self): return True
    def stop(self): return True
    def status(self): return {"servers": []}


class MCPProtocol:
    JSONRPC = "jsonrpc"
    SSE = "sse"


class ServerStatus:
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class ServerSource:
    LOCAL = "local"
    REMOTE = "remote"
    EMBEDDED = "embedded"


def get_mcp_manager():
    return MCPServerManager()


# Compatibility aliases
MCPServer = MCPServerInfo
MCPTool = MCPToolDef


def get_mcp_server_manager():
    return get_mcp_manager()


__all__ = [
    "MCPServerManager", "MCPClient", "MCPDatabase",
    "MCPServer", "MCPTool", "MCPServerInfo", "MCPToolDef",
    "MCPProtocol", "ServerStatus", "ServerSource",
    "get_mcp_manager", "get_mcp_server_manager",
]
