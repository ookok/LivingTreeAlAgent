"""
MCP Manager — Re-export from livingtree.adapters.mcp.manager

Full migration complete. Import from new location.
"""

from livingtree.adapters.mcp.manager import (
    MCPServerManager,
    MCPClient,
    MCPDatabase,
    MCPServerInfo,
    MCPToolDef,
    MCPProtocol,
    ServerStatus,
    ServerSource,
    get_mcp_manager,
)

# Compatibility aliases for old code
MCPServer = MCPServerInfo
MCPTool = MCPToolDef
def get_mcp_server_manager(): return get_mcp_manager()

__all__ = [
    "MCPServerManager", "MCPClient", "MCPDatabase",
    "MCPServer", "MCPTool", "MCPServerInfo", "MCPToolDef",
    "MCPProtocol", "ServerStatus", "ServerSource",
    "get_mcp_manager", "get_mcp_server_manager",
]
