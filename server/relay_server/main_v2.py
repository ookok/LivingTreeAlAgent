"""
Relay Server V2 - 完整版中继服务器
================================

整合所有模块的完整中继服务器

特性:
- SQLAlchemy 数据库 + SQLite
- JWT 认证
- WebSocket 中继
- API 限流
- 请求日志
- CORS 支持
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

# 添加项目根目录到路径
_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_root))

from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# ==================== 配置 ====================

def get_data_dir() -> Path:
    """获取数据目录"""
    return Path(os.environ.get(
        "HERMES_RELAY_DATA",
        str(Path.home() / ".hermes-desktop" / "relay_server")
    ))

DATA_DIR = get_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 初始化数据库
DB_DIR = DATA_DIR / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)

# ==================== 日志 ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ==================== 初始化模块 ====================

def init_modules():
    """初始化所有模块"""
    logger.info("初始化数据库...")
    from .database import init_sqlite_tables
    init_sqlite_tables()
    
    logger.info("初始化认证服务...")
    from .services import get_auth_service
    get_auth_service()
    
    logger.info("初始化 WebSocket 中继服务...")
    from .services import get_ws_relay_service
    get_ws_relay_service()
    
    logger.info("模块初始化完成")

# ==================== FastAPI 应用 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info("Hermes Relay Server V2 启动中...")
    logger.info(f"数据目录: {DATA_DIR}")
    
    # 初始化模块
    init_modules()
    
    yield
    
    logger.info("Hermes Relay Server V2 关闭中...")

app = FastAPI(
    title="Hermes Relay Server V2",
    description="完整版中继服务器 - 数据库 + 认证 + WebSocket + 限流",
    version="2.0.0",
    lifespan=lifespan,
)

# ==================== 中间件 ====================

# 限流
from .middleware import default_rate_limiter

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """限流中间件"""
    # 跳过健康检查和静态文件
    if request.url.path in ("/", "/api/health", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)
    
    # 检查限流
    response = await default_rate_limiter.check_rate_limit(request)
    if response:
        return response
    
    return await call_next(request)

# 请求日志
from .middleware import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)

# 错误处理
from .middleware import ErrorHandlingMiddleware
app.add_middleware(ErrorHandlingMiddleware)

# CORS
from starlette.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== API 路由 ====================

# 导入 API 路由
from .api.v1 import auth_router
from .api import auth_router as legacy_auth_router

# 注册路由
app.include_router(auth_router, prefix="/api/v1")

# 博客和论坛 API
from .services.blog_forum_api import router as blogforum_router
app.include_router(blogforum_router)

# 企业许可证 API
from .api.v1.enterprise_license import router as enterprise_license_router
app.include_router(enterprise_license_router)

# 用户认证与节点注册 API
from .api.v1.user_auth import router as user_auth_router
app.include_router(user_auth_router)

# 统一支付网关 API
from .api.v1.payment import router as payment_router
app.include_router(payment_router)

# 积分充值与VIP系统 API
from .api.v1.credit import router as credit_router
app.include_router(credit_router)

# 管理员通知与积分同步 API
from .api.v1.notification import router as notification_router
app.include_router(notification_router)

# 序列号管理后台 API
from .api.v1.serial_admin import router as serial_admin_router
app.include_router(serial_admin_router)

# ==================== 核心 API ====================

@app.get("/")
async def root():
    """服务信息"""
    return {
        "service": "Hermes Relay Server V2",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    from .services import get_ws_relay_service
    
    ws = get_ws_relay_service()
    stats = ws.get_stats()
    
    return {
        "status": "healthy",
        "timestamp": int(time.time()),
        "relay_mode": True,
        "connections": stats["total_connections"],
        "channels": stats["total_channels"],
    }


@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    from .services import get_ws_relay_service
    
    ws = get_ws_relay_service()
    return {
        "websocket": ws.get_stats(),
        "timestamp": int(time.time()),
    }


# ==================== WebSocket 端点 ====================

@app.websocket("/ws/{channel}")
async def websocket_chat(websocket: WebSocket, channel: str):
    """
    WebSocket 聊天端点
    
    连接后可以发送消息:
    - {"type": "chat", "content": "消息内容"}
    - {"type": "ping"}
    - {"type": "join", "channel": "频道名"}
    - {"type": "direct", "to": "connection_id", "content": "消息"}
    """
    from .services import websocket_endpoint, get_ws_relay_service
    
    # 获取 token（可选）
    token = websocket.query_params.get("token")
    
    await websocket_endpoint(websocket, channel, token)


@app.websocket("/ws")
async def websocket_default(websocket: WebSocket):
    """默认 WebSocket 端点（默认频道）"""
    await websocket_chat(websocket, "default")


# ==================== 配置同步 API（保留原有功能）===================

class ConfigSyncPushRequest(BaseModel):
    """推送配置到服务器"""
    user_token: str
    config_key: str
    config_data: Dict[str, Any]
    client_id: str
    platform: str = "unknown"
    version: str = "2.0.0"


@app.post("/api/config/sync")
async def sync_config_push(request: ConfigSyncPushRequest):
    """推送配置到服务器"""
    from .database import sqlite_session
    from datetime import datetime
    
    with sqlite_session() as conn:
        cursor = conn.cursor()
        
        # 查找或创建配置
        cursor.execute(
            "SELECT id FROM user_configs WHERE user_id = ? AND config_key = ?",
            (request.user_token[:16], request.config_key)
        )
        row = cursor.fetchone()
        
        now = int(time.time())
        
        if row:
            cursor.execute("""
                UPDATE user_configs 
                SET config_data = ?, client_id = ?, platform = ?, version = ?, updated_at = ?
                WHERE user_id = ? AND config_key = ?
            """, (
                json.dumps(request.config_data),
                request.client_id,
                request.platform,
                request.version,
                now,
                request.user_token[:16],
                request.config_key
            ))
        else:
            cursor.execute("""
                INSERT INTO user_configs 
                (user_id, config_key, config_data, client_id, platform, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.user_token[:16],
                request.config_key,
                json.dumps(request.config_data),
                request.client_id,
                request.platform,
                request.version,
                now,
                now
            ))
        
        return {
            "success": True,
            "config_key": request.config_key,
            "server_timestamp": now,
        }


@app.get("/api/config/sync")
async def sync_config_pull(user_token: str, config_key: Optional[str] = None):
    """从服务器拉取配置"""
    from .database import sqlite_session
    
    with sqlite_session() as conn:
        cursor = conn.cursor()
        
        if config_key:
            cursor.execute(
                "SELECT config_data, updated_at FROM user_configs WHERE user_id = ? AND config_key = ?",
                (user_token[:16], config_key)
            )
            row = cursor.fetchone()
            
            if row:
                return {
                    "success": True,
                    "config_key": config_key,
                    "config_data": json.loads(row[0]),
                    "updated_at": row[1],
                    "server_timestamp": int(time.time()),
                }
            else:
                return {
                    "success": False,
                    "error": "Config key not found",
                }
        else:
            cursor.execute(
                "SELECT config_key, config_data, updated_at FROM user_configs WHERE user_id = ?",
                (user_token[:16],)
            )
            rows = cursor.fetchall()
            
            configs = {}
            for row in rows:
                configs[row[0]] = {
                    "data": json.loads(row[1]),
                    "updated_at": row[2]
                }
            
            return {
                "success": True,
                "configs": configs,
                "server_timestamp": int(time.time()),
            }


# ==================== 统计 API（保留原有功能）===================

@app.get("/api/stats/overview")
async def get_overview_stats():
    """全局统计概览"""
    from .database import sqlite_session
    
    with sqlite_session() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT client_id) FROM relay_stats")
        row = cursor.fetchone()
        
        cursor.execute("SELECT SUM(total_patches) FROM relay_stats")
        row2 = cursor.fetchone()
        
        return {
            "total_reports": row[0] or 0,
            "total_clients": row[1] or 0,
            "total_patches": row2[0] or 0,
            "generated_at": int(time.time()),
        }


# ==================== 启动 ====================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8766,
        log_level="info",
    )
