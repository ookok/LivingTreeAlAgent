"""
API 服务

提供 RESTful API 接口，支持部署为服务
"""

import json
import asyncio
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import traceback


class HttpMethod(Enum):
    """HTTP 方法"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class ApiEndpoint:
    """API 端点"""
    path: str
    method: HttpMethod
    handler: Callable
    description: str = ""
    auth_required: bool = False


class ApiResponse:
    """API 响应"""
    
    def __init__(
        self,
        status_code: int = 200,
        body: Any = None,
        error: str = "",
        headers: Optional[Dict[str, str]] = None
    ):
        self.status_code = status_code
        self.body = body
        self.error = error
        self.headers = headers or {"Content-Type": "application/json"}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        if self.error:
            return {
                "success": False,
                "error": self.error
            }
        return {
            "success": True,
            "data": self.body
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class Request:
    """API 请求"""
    
    def __init__(self, method: str, path: str, headers: Dict[str, str], body: Any = None):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body


class ApiService:
    """API 服务"""
    
    def __init__(self, name: str = "API Service", version: str = "v1"):
        self.name = name
        self.version = version
        self.endpoints: Dict[str, Dict[HttpMethod, ApiEndpoint]] = {}
        self.middlewares: list = []
        self._running = False
    
    def register(
        self,
        path: str,
        method: HttpMethod = HttpMethod.GET,
        description: str = "",
        auth_required: bool = False
    ):
        """注册端点的装饰器"""
        def decorator(handler: Callable) -> Callable:
            self.add_endpoint(path, method, handler, description, auth_required)
            return handler
        return decorator
    
    def add_endpoint(
        self,
        path: str,
        method: HttpMethod,
        handler: Callable,
        description: str = "",
        auth_required: bool = False
    ):
        """添加端点"""
        if path not in self.endpoints:
            self.endpoints[path] = {}
        
        endpoint = ApiEndpoint(
            path=path,
            method=method,
            handler=handler,
            description=description,
            auth_required=auth_required
        )
        
        self.endpoints[path][method] = endpoint
        print(f"[API] 注册端点: {method.value} {path}")
    
    def add_middleware(self, middleware: Callable):
        """添加中间件"""
        self.middlewares.append(middleware)
    
    async def handle_request(self, request: Request) -> ApiResponse:
        """处理请求"""
        try:
            # 查找端点
            path = request.path
            method = HttpMethod(request.method.upper())
            
            if path not in self.endpoints:
                return ApiResponse(
                    status_code=404,
                    error=f"端点未找到: {path}"
                )
            
            if method not in self.endpoints[path]:
                return ApiResponse(
                    status_code=405,
                    error=f"方法不允许: {method.value}"
                )
            
            endpoint = self.endpoints[path][method]
            
            # 检查认证
            if endpoint.auth_required:
                auth_result = await self._check_auth(request)
                if not auth_result:
                    return ApiResponse(
                        status_code=401,
                        error="需要认证"
                    )
            
            # 执行中间件
            for middleware in self.middlewares:
                result = await middleware(request)
                if result is not None:
                    return result
            
            # 执行处理器
            if asyncio.iscoroutinefunction(endpoint.handler):
                result = await endpoint.handler(request)
            else:
                result = endpoint.handler(request)
            
            if isinstance(result, ApiResponse):
                return result
            
            return ApiResponse(body=result)
            
        except Exception as e:
            return ApiResponse(
                status_code=500,
                error=f"服务器错误: {str(e)}"
            )
    
    async def _check_auth(self, request: Request) -> bool:
        """检查认证"""
        # 简化实现
        auth_header = request.headers.get("Authorization", "")
        return bool(auth_header)
    
    async def start(self, host: str = "0.0.0.0", port: int = 8000):
        """启动服务"""
        try:
            from aiohttp import web
            
            app = web.Application()
            
            # 添加路由
            async def handle(request):
                method = request.method
                path = request.path
                
                # 解析请求体
                body = None
                if method in ["POST", "PUT", "PATCH"]:
                    try:
                        body = await request.json()
                    except:
                        body = await request.text()
                
                req = Request(
                    method=method,
                    path=path,
                    headers=dict(request.headers),
                    body=body
                )
                
                response = await self.handle_request(req)
                
                return web.json_response(
                    response.to_dict(),
                    status=response.status_code,
                    headers=response.headers
                )
            
            app.router.add_route("*", "/{path:.*}", handle)
            
            runner = web.AppRunner(app)
            await runner.setup()
            
            site = web.TCPSite(runner, host, port)
            await site.start()
            
            self._running = True
            print(f"[API] 服务已启动: http://{host}:{port}")
            print(f"[API] 服务名称: {self.name} {self.version}")
            
        except ImportError:
            print("[API] aiohttp 未安装，无法启动服务")
            print("[API] 请运行: pip install aiohttp")
    
    def list_endpoints(self) -> list:
        """列出所有端点"""
        result = []
        for path, methods in self.endpoints.items():
            for method, endpoint in methods.items():
                result.append({
                    "path": path,
                    "method": method.value,
                    "description": endpoint.description,
                    "auth_required": endpoint.auth_required
                })
        return result


# 全局 API 服务实例
_api_service: Optional[ApiService] = None


def get_api_service() -> ApiService:
    """获取 API 服务实例"""
    global _api_service
    if _api_service is None:
        _api_service = ApiService()
    return _api_service


def create_api_service(name: str = "API Service", version: str = "v1") -> ApiService:
    """创建 API 服务"""
    global _api_service
    _api_service = ApiService(name, version)
    return _api_service


# 预定义的 API 服务实例
def create_document_qa_api_service() -> ApiService:
    """创建文档问答 API 服务"""
    service = create_api_service("Document QA API", "v1")
    
    @service.register("/api/qa/ask", HttpMethod.POST, "提问")
    async def ask_question(request: Request) -> ApiResponse:
        try:
            from business.living_tree_ai.knowledge.multi_document_qa import get_collection_manager
            
            body = request.body
            question = body.get("question", "")
            collection_name = body.get("collection", "default")
            
            if not question:
                return ApiResponse(status_code=400, error="问题不能为空")
            
            manager = get_collection_manager()
            qa = manager.get_collection(collection_name)
            
            if not qa:
                return ApiResponse(status_code=404, error=f"集合不存在: {collection_name}")
            
            result = qa.query(question)
            
            if result:
                return ApiResponse(body={
                    "answer": result.answer,
                    "confidence": result.confidence,
                    "processing_time": result.processing_time,
                    "sources_count": len(result.sources)
                })
            else:
                return ApiResponse(status_code=500, error="问答执行失败")
                
        except Exception as e:
            return ApiResponse(status_code=500, error=str(e))
    
    @service.register("/api/qa/load", HttpMethod.POST, "加载文档")
    async def load_document(request: Request) -> ApiResponse:
        try:
            from business.living_tree_ai.knowledge.multi_document_qa import get_collection_manager
            
            body = request.body
            file_path = body.get("file_path", "")
            collection_name = body.get("collection", "default")
            
            if not file_path:
                return ApiResponse(status_code=400, error="文件路径不能为空")
            
            manager = get_collection_manager()
            qa = manager.get_collection(collection_name)
            
            if not qa:
                qa = manager.create_collection(collection_name)
            
            success = qa.load_document(file_path)
            
            if success:
                stats = qa.get_stats()
                return ApiResponse(body={
                    "success": True,
                    "collection": collection_name,
                    "stats": stats
                })
            else:
                return ApiResponse(status_code=500, error="加载文档失败")
                
        except Exception as e:
            return ApiResponse(status_code=500, error=str(e))
    
    @service.register("/api/qa/collections", HttpMethod.GET, "获取集合列表")
    async def list_collections(request: Request) -> ApiResponse:
        try:
            from business.living_tree_ai.knowledge.multi_document_qa import get_collection_manager
            
            manager = get_collection_manager()
            collections = manager.list_collections()
            
            return ApiResponse(body={
                "collections": collections
            })
                
        except Exception as e:
            return ApiResponse(status_code=500, error=str(e))
    
    @service.register("/api/health", HttpMethod.GET, "健康检查")
    async def health_check(request: Request) -> ApiResponse:
        return ApiResponse(body={
            "status": "healthy",
            "service": service.name,
            "version": service.version
        })
    
    return service


def create_browser_use_api_service() -> ApiService:
    """创建 browser-use API 服务"""
    service = create_api_service("Browser Use API", "v1")
    
    @service.register("/api/browser/navigate", HttpMethod.POST, "导航")
    async def navigate(request: Request) -> ApiResponse:
        try:
            from business.living_tree_ai.browser_gateway.browser_use_adapter import create_browser_use_adapter
            
            body = request.body
            url = body.get("url", "")
            
            if not url:
                return ApiResponse(status_code=400, error="URL 不能为空")
            
            adapter = create_browser_use_adapter()
            await adapter.initialize()
            
            result = await adapter.navigate(url)
            await adapter.close()
            
            return ApiResponse(body=result)
                
        except Exception as e:
            return ApiResponse(status_code=500, error=str(e))
    
    @service.register("/api/browser/execute", HttpMethod.POST, "执行任务")
    async def execute_task(request: Request) -> ApiResponse:
        try:
            from business.living_tree_ai.browser_gateway.browser_use_adapter import create_browser_use_adapter
            
            body = request.body
            task = body.get("task", "")
            
            if not task:
                return ApiResponse(status_code=400, error="任务不能为空")
            
            adapter = create_browser_use_adapter()
            await adapter.initialize()
            
            result = await adapter.execute_task(task)
            await adapter.close()
            
            return ApiResponse(body=result)
                
        except Exception as e:
            return ApiResponse(status_code=500, error=str(e))
    
    @service.register("/api/browser/search", HttpMethod.POST, "搜索")
    async def search(request: Request) -> ApiResponse:
        try:
            from business.living_tree_ai.browser_gateway.browser_use_adapter import create_browser_use_adapter
            
            body = request.body
            query = body.get("query", "")
            engine = body.get("engine", "google")
            
            if not query:
                return ApiResponse(status_code=400, error="搜索查询不能为空")
            
            adapter = create_browser_use_adapter()
            await adapter.initialize()
            
            result = await adapter.search(query, engine)
            await adapter.close()
            
            return ApiResponse(body=result)
                
        except Exception as e:
            return ApiResponse(status_code=500, error=str(e))
    
    @service.register("/api/health", HttpMethod.GET, "健康检查")
    async def health_check(request: Request) -> ApiResponse:
        return ApiResponse(body={
            "status": "healthy",
            "service": service.name,
            "version": service.version
        })
    
    return service
