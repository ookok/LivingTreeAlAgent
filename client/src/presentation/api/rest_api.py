"""
REST API - REST API 导出模块

支持将工具/技能导出为 REST API。

遵循自我进化原则：
- 自动生成 API 文档
- 支持动态路由注册
- 从使用中学习优化 API 设计
"""

from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from loguru import logger
import asyncio

try:
    from client.src.business.tools.tool_registry import ToolRegistry
    from client.src.business.tools.base_tool import ToolResult
except ImportError:
    from tools.tool_registry import ToolRegistry
    from tools.base_tool import ToolResult


class ToolRequest(BaseModel):
    """工具调用请求"""
    tool_name: str
    params: Optional[Dict[str, Any]] = None


class ToolResponse(BaseModel):
    """工具调用响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None


class RESTAPI:
    """
    REST API 服务
    
    将工具/技能导出为 REST API。
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self._host = host
        self._port = port
        self._app = FastAPI(title="LivingTreeAI Agent API", version="1.0")
        self._registry = ToolRegistry.get_instance()
        self._logger = logger.bind(component="RESTAPI")
        self._server = None
        self._setup_routes()

    def _setup_routes(self):
        """设置 API 路由"""
        @self._app.get("/")
        async def root():
            return {"message": "LivingTreeAI Agent API", "version": "1.0"}

        @self._app.get("/api/tools")
        async def list_tools():
            """列出所有可用工具"""
            tools = self._registry.list_tools()
            return {"tools": [tool.to_dict() for tool in tools]}

        @self._app.get("/api/tools/{tool_name}")
        async def get_tool(tool_name: str):
            """获取工具详情"""
            tool = self._registry.get_tool(tool_name)
            if not tool:
                raise HTTPException(status_code=404, detail=f"工具 {tool_name} 不存在")
            return tool.to_dict()

        @self._app.post("/api/tools/{tool_name}/execute", response_model=ToolResponse)
        async def execute_tool(tool_name: str, request: ToolRequest):
            """执行工具"""
            if request.params is None:
                request.params = {}
            
            result = await self._registry.execute(tool_name, **request.params)
            
            return ToolResponse(
                success=result.success,
                data=result.data,
                error=result.error,
                message=result.message
            )

        @self._app.post("/api/tools/execute", response_model=ToolResponse)
        async def execute_tool_by_request(request: ToolRequest):
            """执行工具（通过请求体）"""
            if request.params is None:
                request.params = {}
            
            result = await self._registry.execute(request.tool_name, **request.params)
            
            return ToolResponse(
                success=result.success,
                data=result.data,
                error=result.error,
                message=result.message
            )

        @self._app.get("/api/tools/search/{query}")
        async def search_tools(query: str, top_k: int = 5):
            """搜索工具"""
            tools = self._registry.discover(query, top_k)
            return {"tools": [tool.to_dict() for tool in tools]}

        @self._app.get("/api/health")
        async def health_check():
            """健康检查"""
            return {"status": "healthy", "timestamp": len(self._registry.get_stats())}

    async def start(self):
        """启动 API 服务"""
        self._logger.info(f"启动 REST API 服务: {self._host}:{self._port}")
        
        # 在单独的线程中运行 uvicorn
        import threading
        thread = threading.Thread(
            target=uvicorn.run,
            args=(self._app,),
            kwargs={"host": self._host, "port": self._port, "log_level": "info"},
            daemon=True
        )
        thread.start()
        
        # 等待服务启动
        await asyncio.sleep(1)
        self._logger.info("REST API 服务已启动")

    async def stop(self):
        """停止 API 服务"""
        self._logger.info("停止 REST API 服务")
        # uvicorn 在 daemon 线程中运行，会随主进程退出而停止

    def get_app(self):
        """获取 FastAPI 应用实例"""
        return self._app

    def get_stats(self) -> Dict[str, Any]:
        """获取 API 统计信息"""
        return {
            "host": self._host,
            "port": self._port,
            "tools_count": len(self._registry.list_tools()),
            "status": "running" if self._server else "stopped"
        }