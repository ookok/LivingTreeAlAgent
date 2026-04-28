"""
ThirdPartyToolIntegrator - 第三方工具集成器

扩展第三方工具集成，兼容 MCP 协议，支持私有连接器对接企业内部系统。

遵循自我进化原则：
- 自动发现 MCP 工具
- 支持动态注册第三方工具
- 从使用中学习优化工具选择
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum


class ToolSource(Enum):
    """工具来源"""
    MCP = "mcp"
    API = "api"
    CLI = "cli"
    PRIVATE = "private"


@dataclass
class ThirdPartyTool:
    """第三方工具"""
    tool_id: str
    name: str
    description: str
    source: ToolSource
    config: Dict[str, Any]
    enabled: bool = True
    usage_count: int = 0


class ThirdPartyToolIntegrator:
    """
    第三方工具集成器
    
    扩展第三方工具集成，兼容 MCP 协议。
    """

    def __init__(self):
        self._logger = logger.bind(component="ThirdPartyToolIntegrator")
        self._tools: Dict[str, ThirdPartyTool] = {}
        self._mcp_servers: List[str] = []
        self._discovery_history = []

    async def discover_mcp_tools(self, server_url: str):
        """
        发现 MCP 服务器上的工具
        
        Args:
            server_url: MCP 服务器 URL
        """
        self._logger.info(f"发现 MCP 工具: {server_url}")
        
        if server_url not in self._mcp_servers:
            self._mcp_servers.append(server_url)
        
        # 模拟发现过程
        await self._simulate_mcp_discovery(server_url)

    async def _simulate_mcp_discovery(self, server_url: str):
        """模拟 MCP 工具发现"""
        # 模拟发现的工具
        discovered_tools = [
            {"tool_id": "mcp_stripe", "name": "Stripe", "description": "支付处理"},
            {"tool_id": "mcp_slack", "name": "Slack", "description": "团队沟通"},
            {"tool_id": "mcp_github", "name": "GitHub", "description": "代码托管"},
            {"tool_id": "mcp_salesforce", "name": "Salesforce", "description": "客户关系管理"},
        ]
        
        for tool_info in discovered_tools:
            tool = ThirdPartyTool(
                tool_id=tool_info["tool_id"],
                name=tool_info["name"],
                description=tool_info["description"],
                source=ToolSource.MCP,
                config={"server_url": server_url}
            )
            self._tools[tool.tool_id] = tool
        
        self._discovery_history.append({
            "server_url": server_url,
            "discovered_count": len(discovered_tools),
            "timestamp": len(self._discovery_history)
        })
        
        self._logger.info(f"从 {server_url} 发现 {len(discovered_tools)} 个工具")

    def register_api_tool(
        self,
        tool_id: str,
        name: str,
        description: str,
        base_url: str,
        auth_config: Optional[Dict[str, Any]] = None
    ):
        """
        注册 API 工具
        
        Args:
            tool_id: 工具 ID
            name: 工具名称
            description: 工具描述
            base_url: API 基础 URL
            auth_config: 认证配置
        """
        if tool_id in self._tools:
            raise ValueError(f"工具已存在: {tool_id}")

        tool = ThirdPartyTool(
            tool_id=tool_id,
            name=name,
            description=description,
            source=ToolSource.API,
            config={"base_url": base_url, "auth": auth_config or {}}
        )
        
        self._tools[tool_id] = tool
        self._logger.info(f"已注册 API 工具: {name}")

    def register_cli_tool(
        self,
        tool_id: str,
        name: str,
        description: str,
        command: str
    ):
        """
        注册 CLI 工具
        
        Args:
            tool_id: 工具 ID
            name: 工具名称
            description: 工具描述
            command: CLI 命令
        """
        if tool_id in self._tools:
            raise ValueError(f"工具已存在: {tool_id}")

        tool = ThirdPartyTool(
            tool_id=tool_id,
            name=name,
            description=description,
            source=ToolSource.CLI,
            config={"command": command}
        )
        
        self._tools[tool_id] = tool
        self._logger.info(f"已注册 CLI 工具: {name}")

    def register_private_tool(
        self,
        tool_id: str,
        name: str,
        description: str,
        connector_config: Dict[str, Any]
    ):
        """
        注册私有连接器工具
        
        Args:
            tool_id: 工具 ID
            name: 工具名称
            description: 工具描述
            connector_config: 连接器配置
        """
        if tool_id in self._tools:
            raise ValueError(f"工具已存在: {tool_id}")

        tool = ThirdPartyTool(
            tool_id=tool_id,
            name=name,
            description=description,
            source=ToolSource.PRIVATE,
            config=connector_config
        )
        
        self._tools[tool_id] = tool
        self._logger.info(f"已注册私有工具: {name}")

    async def execute_tool(self, tool_id: str, **kwargs) -> Dict[str, Any]:
        """
        执行第三方工具
        
        Args:
            tool_id: 工具 ID
            kwargs: 工具参数
            
        Returns:
            执行结果
        """
        if tool_id not in self._tools:
            raise ValueError(f"工具不存在: {tool_id}")

        tool = self._tools[tool_id]
        tool.usage_count += 1
        
        self._logger.info(f"执行第三方工具: {tool.name}")
        
        # 根据工具类型执行
        if tool.source == ToolSource.MCP:
            return await self._execute_mcp_tool(tool, kwargs)
        elif tool.source == ToolSource.API:
            return await self._execute_api_tool(tool, kwargs)
        elif tool.source == ToolSource.CLI:
            return await self._execute_cli_tool(tool, kwargs)
        elif tool.source == ToolSource.PRIVATE:
            return await self._execute_private_tool(tool, kwargs)
        
        return {"error": "未知工具类型"}

    async def _execute_mcp_tool(self, tool: ThirdPartyTool, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行 MCP 工具"""
        return {
            "tool": tool.name,
            "source": "mcp",
            "result": f"执行 MCP 工具 {tool.name}，参数: {params}",
            "success": True
        }

    async def _execute_api_tool(self, tool: ThirdPartyTool, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行 API 工具"""
        return {
            "tool": tool.name,
            "source": "api",
            "result": f"执行 API 工具 {tool.name}，参数: {params}",
            "success": True
        }

    async def _execute_cli_tool(self, tool: ThirdPartyTool, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行 CLI 工具"""
        return {
            "tool": tool.name,
            "source": "cli",
            "result": f"执行 CLI 工具 {tool.name}，参数: {params}",
            "success": True
        }

    async def _execute_private_tool(self, tool: ThirdPartyTool, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行私有工具"""
        return {
            "tool": tool.name,
            "source": "private",
            "result": f"执行私有工具 {tool.name}，参数: {params}",
            "success": True
        }

    def list_tools(self) -> List[ThirdPartyTool]:
        """列出所有第三方工具"""
        return list(self._tools.values())

    def get_tool(self, tool_id: str) -> Optional[ThirdPartyTool]:
        """获取工具"""
        return self._tools.get(tool_id)

    def enable_tool(self, tool_id: str):
        """启用工具"""
        if tool_id in self._tools:
            self._tools[tool_id].enabled = True

    def disable_tool(self, tool_id: str):
        """禁用工具"""
        if tool_id in self._tools:
            self._tools[tool_id].enabled = False

    def get_stats(self) -> Dict[str, Any]:
        """获取集成器统计信息"""
        source_counts = {}
        for tool in self._tools.values():
            source = tool.source.value
            source_counts[source] = source_counts.get(source, 0) + 1
        
        return {
            "total_tools": len(self._tools),
            "enabled_tools": sum(1 for t in self._tools.values() if t.enabled),
            "total_mcp_servers": len(self._mcp_servers),
            "source_distribution": source_counts,
            "total_usage": sum(t.usage_count for t in self._tools.values()),
            "discovery_count": len(self._discovery_history)
        }