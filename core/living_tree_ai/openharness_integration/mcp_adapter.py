"""
MCP 工具协议适配器

实现 Model Context Protocol (MCP) 工具调用标准
"""

import json
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


class MCPErrorCode(Enum):
    """MCP 错误码"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    TOOL_NOT_FOUND = -32001
    TOOL_EXECUTION_ERROR = -32002


@dataclass
class MCPRequest:
    """MCP 请求"""
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    method: str = ""
    params: Optional[Dict[str, Any]] = None


@dataclass
class MCPResponse:
    """MCP 响应"""
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Optional[Callable] = None


@dataclass
class MCPToolResult:
    """MCP 工具执行结果"""
    success: bool
    result: Any = None
    error: str = ""


class MCPProtocolAdapter:
    """MCP 协议适配器"""
    
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self._request_handlers: Dict[str, Callable] = {}
    
    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable
    ):
        """
        注册 MCP 工具
        
        Args:
            name: 工具名称
            description: 工具描述
            input_schema: 输入模式（JSON Schema 格式）
            handler: 处理函数
        """
        tool = MCPTool(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler
        )
        self.tools[name] = tool
        print(f"[MCP] 注册工具: {name}")
    
    def register_function_tool(
        self,
        name: str,
        func: Callable,
        description: str = ""
    ):
        """
        注册函数作为 MCP 工具
        
        Args:
            name: 工具名称
            func: 函数对象
            description: 工具描述（从函数文档字符串提取）
        """
        import inspect
        
        # 从函数提取信息
        sig = inspect.signature(func)
        func_description = description or func.__doc__ or ""
        
        # 构建输入模式
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            param_type = "string"
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == list:
                param_type = "array"
            elif param.annotation == dict:
                param_type = "object"
            
            properties[param_name] = {
                "type": param_type,
                "description": f"参数: {param_name}"
            }
            
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        input_schema = {
            "type": "object",
            "properties": properties,
            "required": required
        }
        
        async def handler(params: Dict[str, Any]) -> MCPToolResult:
            try:
                # 如果是异步函数
                if asyncio.iscoroutinefunction(func):
                    result = await func(**params)
                else:
                    result = func(**params)
                return MCPToolResult(success=True, result=result)
            except Exception as e:
                return MCPToolResult(success=False, error=str(e))
        
        self.register_tool(name, func_description, input_schema, handler)
    
    def unregister_tool(self, name: str):
        """注销工具"""
        if name in self.tools:
            del self.tools[name]
            print(f"[MCP] 注销工具: {name}")
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具列表"""
        tools = []
        for name, tool in self.tools.items():
            tools.append({
                "name": name,
                "description": tool.description,
                "inputSchema": tool.input_schema
            })
        return tools
    
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """
        处理 MCP 请求
        
        Args:
            request: MCP 请求
            
        Returns:
            MCP 响应
        """
        try:
            # 解析请求方法
            method = request.method
            
            if method == "tools/list":
                # 列出所有工具
                return MCPResponse(
                    id=request.id,
                    result={"tools": self.get_tools()}
                )
            
            elif method == "tools/call":
                # 调用工具
                return await self._handle_tool_call(request)
            
            else:
                # 未知方法
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": MCPErrorCode.METHOD_NOT_FOUND.value,
                        "message": f"方法未找到: {method}"
                    }
                )
                
        except Exception as e:
            return MCPResponse(
                id=request.id,
                error={
                    "code": MCPErrorCode.INTERNAL_ERROR.value,
                    "message": str(e)
                }
            )
    
    async def _handle_tool_call(self, request: MCPRequest) -> MCPResponse:
        """处理工具调用请求"""
        params = request.params or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name:
            return MCPResponse(
                id=request.id,
                error={
                    "code": MCPErrorCode.INVALID_PARAMS.value,
                    "message": "缺少工具名称"
                }
            )
        
        if tool_name not in self.tools:
            return MCPResponse(
                id=request.id,
                error={
                    "code": MCPErrorCode.TOOL_NOT_FOUND.value,
                    "message": f"工具未找到: {tool_name}"
                }
            )
        
        tool = self.tools[tool_name]
        
        if not tool.handler:
            return MCPResponse(
                id=request.id,
                error={
                    "code": MCPErrorCode.INTERNAL_ERROR.value,
                    "message": f"工具没有处理器: {tool_name}"
                }
            )
        
        try:
            # 执行工具
            result = await tool.handler(arguments)
            
            if result.success:
                return MCPResponse(
                    id=request.id,
                    result={
                        "content": [
                            {
                                "type": "text",
                                "text": str(result.result) if result.result is not None else ""
                            }
                        ],
                        "isError": False
                    }
                )
            else:
                return MCPResponse(
                    id=request.id,
                    result={
                        "content": [
                            {
                                "type": "text",
                                "text": f"错误: {result.error}"
                            }
                        ],
                        "isError": True
                    }
                )
                
        except Exception as e:
            return MCPResponse(
                id=request.id,
                error={
                    "code": MCPErrorCode.TOOL_EXECUTION_ERROR.value,
                    "message": f"工具执行错误: {str(e)}"
                }
            )
    
    def parse_request(self, request_data: str) -> Optional[MCPRequest]:
        """
        解析请求数据
        
        Args:
            request_data: JSON 字符串
            
        Returns:
            MCP 请求或 None
        """
        try:
            data = json.loads(request_data)
            return MCPRequest(
                jsonrpc=data.get("jsonrpc", "2.0"),
                id=data.get("id"),
                method=data.get("method", ""),
                params=data.get("params")
            )
        except json.JSONDecodeError:
            return None
    
    def create_response(self, response: MCPResponse) -> str:
        """
        创建响应数据
        
        Args:
            response: MCP 响应
            
        Returns:
            JSON 字符串
        """
        return json.dumps({
            "jsonrpc": response.jsonrpc,
            "id": response.id,
            "result": response.result,
            "error": response.error
        }, ensure_ascii=False)


class MCPClient:
    """MCP 客户端"""
    
    def __init__(self, server_url: str):
        """
        初始化 MCP 客户端
        
        Args:
            server_url: MCP 服务器 URL
        """
        self.server_url = server_url
        self.tools: List[Dict[str, Any]] = []
    
    async def connect(self):
        """连接到 MCP 服务器"""
        # 获取可用工具列表
        request = MCPRequest(
            id=1,
            method="tools/list"
        )
        
        response = await self._send_request(request)
        if response and response.result:
            self.tools = response.result.get("tools", [])
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        request = MCPRequest(
            id=1,
            method="tools/call",
            params={
                "name": name,
                "arguments": arguments
            }
        )
        
        response = await self._send_request(request)
        
        if response and response.result:
            content = response.result.get("content", [])
            if content and content[0].get("type") == "text":
                return {
                    "success": not response.result.get("isError", False),
                    "result": content[0].get("text", "")
                }
        
        if response and response.error:
            return {
                "success": False,
                "error": response.error.get("message", "未知错误")
            }
        
        return {
            "success": False,
            "error": "请求失败"
        }
    
    async def _send_request(self, request: MCPRequest) -> Optional[MCPResponse]:
        """发送请求到 MCP 服务器"""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.server_url,
                    json={
                        "jsonrpc": request.jsonrpc,
                        "id": request.id,
                        "method": request.method,
                        "params": request.params
                    }
                ) as response:
                    data = await response.json()
                    return MCPResponse(
                        jsonrpc=data.get("jsonrpc", "2.0"),
                        id=data.get("id"),
                        result=data.get("result"),
                        error=data.get("error")
                    )
        except Exception as e:
            print(f"[MCP Client] 请求失败: {e}")
            return None
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """获取工具列表"""
        return self.tools


# 全局 MCP 适配器实例
_mcp_adapter: Optional[MCPProtocolAdapter] = None


def get_mcp_adapter() -> MCPProtocolAdapter:
    """获取 MCP 适配器实例"""
    global _mcp_adapter
    if _mcp_adapter is None:
        _mcp_adapter = MCPProtocolAdapter()
    return _mcp_adapter


def register_mcp_tool(
    name: str,
    description: str,
    input_schema: Dict[str, Any],
    handler: Callable
):
    """注册 MCP 工具的便捷函数"""
    adapter = get_mcp_adapter()
    adapter.register_tool(name, description, input_schema, handler)


def register_mcp_function_tool(name: str, func: Callable, description: str = ""):
    """注册函数作为 MCP 工具的便捷函数"""
    adapter = get_mcp_adapter()
    adapter.register_function_tool(name, func, description)
