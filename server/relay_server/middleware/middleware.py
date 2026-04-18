"""
API Middleware - API 中间件
========================

提供限流、请求日志、CORS 等中间件功能
"""

import time
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from collections import defaultdict
from functools import wraps

try:
    from fastapi import Request, Response, HTTPException
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


# ============ 限流器 ============

class RateLimiter:
    """
    令牌桶限流器
    
    支持:
    - 按 IP 限流
    - 按用户限流
    - 按 API Key 限流
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        requests_per_day: int = 10000,
        burst_size: int = 10,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.requests_per_day = requests_per_day
        self.burst_size = burst_size
        
        # 存储: {key: [timestamp1, timestamp2, ...]}
        self._requests: Dict[str, list] = defaultdict(list)
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def _get_key(self, request: Request) -> str:
        """获取限流 key"""
        # 优先使用用户 ID
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"
        
        # 其次使用 API Key
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")
        if api_key:
            return f"apikey:{api_key[:16]}"  # 只用前 16 位
        
        # 最后使用 IP
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    def _cleanup_old_requests(self, key: str):
        """清理过期的请求记录"""
        now = time.time()
        cutoff_minute = now - 60
        cutoff_hour = now - 3600
        cutoff_day = now - 86400
        
        self._requests[key] = [
            t for t in self._requests[key]
            if t > cutoff_day
        ]
    
    def is_allowed(self, request: Request) -> tuple[bool, Dict[str, Any]]:
        """
        检查是否允许请求
        
        Returns:
            (is_allowed, info)
        """
        key = self._get_key(request)
        now = time.time()
        
        # 清理过期记录
        self._cleanup_old_requests(key)
        
        # 获取最近的请求时间
        requests = self._requests[key]
        
        # 检查各种限制
        minute_count = sum(1 for t in requests if t > now - 60)
        hour_count = sum(1 for t in requests if t > now - 3600)
        day_count = len(requests)
        
        info = {
            "key": key,
            "minute_count": minute_count,
            "hour_count": hour_count,
            "day_count": day_count,
            "limit_minute": self.requests_per_minute,
            "limit_hour": self.requests_per_hour,
            "limit_day": self.requests_per_day,
            "reset_in": 60 - (now % 60),  # 下个分钟重置
        }
        
        # 检查限制
        if minute_count >= self.requests_per_minute:
            return False, info
        if hour_count >= self.requests_per_hour:
            return False, info
        if day_count >= self.requests_per_day:
            return False, info
        
        # 记录请求
        requests.append(now)
        
        return True, info
    
    async def check_rate_limit(self, request: Request) -> Optional[JSONResponse]:
        """
        检查限流中间件
        
        Returns:
            None 表示通过，返回 JSONResponse 表示拒绝
        """
        allowed, info = self.is_allowed(request)
        
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Try again in {info['reset_in']:.0f} seconds.",
                    "limit": info,
                },
                headers={
                    "X-RateLimit-Limit-Minute": str(self.requests_per_minute),
                    "X-RateLimit-Limit-Hour": str(self.requests_per_hour),
                    "X-RateLimit-Limit-Day": str(self.requests_per_day),
                    "X-RateLimit-Remaining-Minute": str(max(0, self.requests_per_minute - info["minute_count"])),
                    "X-RateLimit-Reset": str(int(time.time() + info["reset_in"])),
                }
            )
        
        return None


# 全局限流器
default_rate_limiter = RateLimiter()


# ============ 请求日志中间件 ============

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件
    
    记录所有请求的:
    - 请求方法、路径
    - 响应状态码
    - 处理时间
    - 客户端 IP
    """
    
    def __init__(self, app, logger=None, log_body: bool = False, log_headers: bool = False):
        super().__init__(app)
        self.logger = logger
        self.log_body = log_body
        self.log_headers = log_headers
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 记录开始时间
        start_time = time.time()
        
        # 获取请求信息
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        
        # 生成请求 ID
        request_id = request.headers.get("X-Request-ID", f"{int(start_time * 1000)}")
        
        # 构建日志
        log_data = {
            "request_id": request_id,
            "method": method,
            "path": path,
            "client_ip": client_ip,
            "user_agent": request.headers.get("user-agent", ""),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # 可选：记录请求体
        if self.log_body and method in ("POST", "PUT", "PATCH"):
            body = await request.body()
            if body:
                try:
                    log_data["body"] = json.loads(body)
                except:
                    log_data["body"] = "<binary or invalid>"
        
        # 可选：记录请求头
        if self.log_headers:
            log_data["headers"] = dict(request.headers)
        
        # 打印请求日志
        if self.logger:
            self.logger.info(f"Request: {json.dumps(log_data, ensure_ascii=False)}")
        else:
            print(f"[{log_data['timestamp']}] {method} {path} from {client_ip}")
        
        # 处理请求
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise
        finally:
            # 计算处理时间
            process_time = (time.time() - start_time) * 1000  # 毫秒
            
            # 记录响应
            response_log = {
                **log_data,
                "status_code": status_code,
                "process_time_ms": round(process_time, 2),
            }
            
            if status_code >= 400:
                if self.logger:
                    self.logger.warning(f"Response: {json.dumps(response_log, ensure_ascii=False)}")
                else:
                    print(f"[!] {method} {path} -> {status_code} ({process_time:.2f}ms)")
            
            # 添加响应头
            # response.headers["X-Request-ID"] = request_id
            # response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        
        return response


# ============ CORS 中间件 ============

class CORSMiddleware:
    """
    简单的 CORS 中间件
    
    生产环境建议使用 FastAPI 内置的 CORSMiddleware
    """
    
    def __init__(
        self,
        allow_origins: list = None,
        allow_methods: list = None,
        allow_headers: list = None,
        allow_credentials: bool = True,
        max_age: int = 600,
    ):
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        self.allow_headers = allow_headers or ["*"]
        self.allow_credentials = allow_credentials
        self.max_age = max_age
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        origin = request.headers.get("origin")
        
        # 处理预检请求
        if request.method == "OPTIONS":
            headers = {
                "Access-Control-Allow-Methods": ", ".join(self.allow_methods),
                "Access-Control-Allow-Headers": ", ".join(self.allow_headers),
                "Access-Control-Max-Age": str(self.max_age),
            }
            
            if origin and (self.allow_origins == ["*"] or origin in self.allow_origins):
                headers["Access-Control-Allow-Origin"] = origin
                if self.allow_credentials:
                    headers["Access-Control-Allow-Credentials"] = "true"
            
            return Response(headers=headers)
        
        # 处理普通请求
        response = await call_next(request)
        
        if origin and (self.allow_origins == ["*"] or origin in self.allow_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
            if self.allow_credentials:
                response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response


# ============ 错误处理中间件 ============

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    统一错误处理中间件
    """
    
    def __init__(self, app, logger=None):
        super().__init__(app)
        self.logger = logger
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except HTTPException:
            raise
        except Exception as e:
            # 记录错误
            error_info = {
                "error": type(e).__name__,
                "message": str(e),
                "path": request.url.path,
                "method": request.method,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            if self.logger:
                self.logger.error(f"Unhandled error: {json.dumps(error_info, ensure_ascii=False)}")
            else:
                print(f"[ERROR] {error_info}")
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "request_id": request.headers.get("X-Request-ID"),
                }
            )


# ============ 健康检查端点 ============

if FASTAPI_AVAILABLE:
    from fastapi import APIRouter
    
    router = APIRouter()
    
    @router.get("/health")
    async def health_check():
        """健康检查"""
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0",
        }
    
    @router.get("/health/detailed")
    async def detailed_health_check(request: Request):
        """详细健康检查"""
        # 检查数据库
        db_status = "unknown"
        try:
            from ..database import get_db_manager
            db = get_db_manager()
            with db.get_session() as session:
                session.execute("SELECT 1")
            db_status = "healthy"
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
        
        # 检查 WebSocket 连接
        ws_status = "unknown"
        try:
            from ..services.ws_service import get_ws_relay_service
            ws = get_ws_relay_service()
            stats = ws.get_stats()
            ws_status = f"healthy: {stats['total_connections']} connections"
        except Exception as e:
            ws_status = f"unhealthy: {str(e)}"
        
        return {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0",
            "components": {
                "database": db_status,
                "websocket": ws_status,
                "api": "healthy",
            }
        }
    
    @router.get("/stats")
    async def get_stats(request: Request):
        """获取服务统计"""
        from ..services.ws_service import get_ws_relay_service
        
        ws = get_ws_relay_service()
        ws_stats = ws.get_stats()
        
        return {
            "websocket": ws_stats,
            "timestamp": datetime.utcnow().isoformat(),
        }
