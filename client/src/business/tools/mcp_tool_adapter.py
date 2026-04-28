"""
MCPToolAdapter - MCP 工具适配器

完善 MCP 协议支持，对接外部工具。

参考 ml-intern 的 MCP 协议实现。

功能：
1. MCP 服务器发现
2. 工具描述获取
3. 工具调用
4. 错误处理和重试
5. 会话管理

遵循自我进化原则：
- 自动发现可用的 MCP 服务器
- 从使用中学习优化工具选择
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
import asyncio


@dataclass
class MCPToolInfo:
    """MCP 工具信息"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    server_url: str


@dataclass
class MCPExecutionResult:
    """MCP 执行结果"""
    success: bool
    result: Optional[Any]
    error: Optional[str]
    server_url: str
    tool_name: str


@dataclass
class MCPServerInfo:
    """MCP 服务器信息"""
    url: str
    name: str
    description: str
    tools: List[str]
    last_seen: datetime = field(default_factory=datetime.now)
    status: str = "unknown"


class MCPToolAdapter:
    """
    MCP 工具适配器
    
    完善 MCP 协议支持，对接外部工具。
    
    核心功能：
    1. MCP 服务器发现和注册
    2. 工具描述获取和缓存
    3. 工具调用和错误处理
    4. 会话管理和状态追踪
    """

    def __init__(self):
        self._logger = logger.bind(component="MCPToolAdapter")
        self._servers: Dict[str, MCPServerInfo] = {}
        self._tool_cache: Dict[str, MCPToolInfo] = {}
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._discovery_interval = 300  # 5分钟重新发现一次

    async def discover_servers(self, discovery_urls: Optional[List[str]] = None):
        """
        发现 MCP 服务器
        
        Args:
            discovery_urls: 已知的服务器 URL 列表
        """
        if discovery_urls is None:
            discovery_urls = []

        # 添加默认的本地服务器
        default_servers = [
            "http://localhost:8000",
            "http://localhost:8080",
            "http://127.0.0.1:8000"
        ]
        
        discovery_urls = list(set(discovery_urls + default_servers))

        for url in discovery_urls:
            await self._discover_server(url)

    async def _discover_server(self, url: str):
        """发现单个服务器"""
        try:
            info = await self._get_server_info(url)
            if info:
                self._servers[url] = info
                self._logger.info(f"发现 MCP 服务器: {info.name} ({url})")
                
                # 获取服务器上的工具
                await self._discover_server_tools(url)
        except Exception as e:
            self._logger.warning(f"发现服务器失败: {url}, 错误: {e}")

    async def _get_server_info(self, url: str) -> Optional[MCPServerInfo]:
        """获取服务器信息"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{url}/info", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return MCPServerInfo(
                        url=url,
                        name=data.get("name", "Unknown"),
                        description=data.get("description", ""),
                        tools=data.get("tools", []),
                        status="online"
                    )
        except:
            pass
        return None

    async def _discover_server_tools(self, server_url: str):
        """发现服务器上的工具"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{server_url}/tools", timeout=5)
                if response.status_code == 200:
                    tools = response.json().get("tools", [])
                    for tool in tools:
                        tool_info = MCPToolInfo(
                            name=tool.get("name", ""),
                            description=tool.get("description", ""),
                            input_schema=tool.get("input_schema", {}),
                            output_schema=tool.get("output_schema", {}),
                            server_url=server_url
                        )
                        self._tool_cache[f"{server_url}_{tool['name']}"] = tool_info
                        
                        self._logger.debug(f"发现工具: {tool['name']}")
        except Exception as e:
            self._logger.warning(f"发现工具失败: {server_url}, 错误: {e}")

    async def call_tool(self, tool_name: str, params: Dict[str, Any], 
                       server_url: Optional[str] = None) -> MCPExecutionResult:
        """
        调用 MCP 工具
        
        Args:
            tool_name: 工具名称
            params: 工具参数
            server_url: 服务器 URL（可选，自动选择）
            
        Returns:
            MCPExecutionResult
        """
        # 如果没有指定服务器，自动选择
        if server_url is None:
            server_url = await self._select_server(tool_name)
        
        if not server_url:
            return MCPExecutionResult(
                success=False,
                result=None,
                error=f"找不到工具 {tool_name} 的服务器",
                server_url="",
                tool_name=tool_name
            )

        try:
            return await self._execute_tool(server_url, tool_name, params)
        except Exception as e:
            return MCPExecutionResult(
                success=False,
                result=None,
                error=str(e),
                server_url=server_url,
                tool_name=tool_name
            )

    async def _select_server(self, tool_name: str) -> Optional[str]:
        """选择合适的服务器"""
        # 在缓存中查找
        for key, tool_info in self._tool_cache.items():
            if tool_info.name == tool_name:
                return tool_info.server_url
        
        # 尝试从在线服务器中查找
        for url, server in self._servers.items():
            if server.status == "online" and tool_name in server.tools:
                return url
        
        return None

    async def _execute_tool(self, server_url: str, tool_name: str, 
                           params: Dict[str, Any]) -> MCPExecutionResult:
        """执行工具"""
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{server_url}/tools/{tool_name}/execute",
                json={"params": params},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return MCPExecutionResult(
                    success=data.get("success", False),
                    result=data.get("result"),
                    error=data.get("error"),
                    server_url=server_url,
                    tool_name=tool_name
                )
            else:
                return MCPExecutionResult(
                    success=False,
                    result=None,
                    error=f"HTTP 错误: {response.status_code}",
                    server_url=server_url,
                    tool_name=tool_name
                )

    def get_tool_info(self, tool_name: str) -> Optional[MCPToolInfo]:
        """获取工具信息"""
        for key, tool_info in self._tool_cache.items():
            if tool_info.name == tool_name:
                return tool_info
        return None

    def list_tools(self) -> List[MCPToolInfo]:
        """列出所有可用的 MCP 工具"""
        return list(self._tool_cache.values())

    def list_servers(self) -> List[MCPServerInfo]:
        """列出所有发现的服务器"""
        return list(self._servers.values())

    def create_session(self, session_id: str, server_url: str):
        """创建会话"""
        self._sessions[session_id] = {
            "server_url": server_url,
            "created_at": datetime.now(),
            "calls": 0
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        return self._sessions.get(session_id)

    def close_session(self, session_id: str):
        """关闭会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]

    def refresh_cache(self):
        """刷新缓存"""
        self._tool_cache.clear()
        for url in self._servers.keys():
            asyncio.create_task(self._discover_server_tools(url))
        self._logger.info("MCP 工具缓存已刷新")

    def get_stats(self) -> Dict[str, Any]:
        """获取适配器统计信息"""
        online_servers = sum(1 for s in self._servers.values() if s.status == "online")
        
        return {
            "total_servers": len(self._servers),
            "online_servers": online_servers,
            "total_tools": len(self._tool_cache),
            "active_sessions": len(self._sessions)
        }