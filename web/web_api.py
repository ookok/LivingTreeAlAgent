"""
Web API - FastAPI Web接口层
=========================

提供与桌面/移动端一致的REST API和WebSocket接口

架构:
- FastAPI 应用
- REST API (与客户端API一致)
- WebSocket (实时状态推送)
- 静态文件服务 (PWA)
"""

import asyncio
import json
import time
import hashlib
import base64
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available, web server will not be functional")


# ==================== 数据模型 ====================

@dataclass
class RouteTestRequest:
    """路由测试请求"""
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    body: Optional[str] = None
    timeout: int = 30


@dataclass
class RouteTestResult:
    """路由测试结果"""
    success: bool
    status_code: Optional[int]
    response_time: float  # ms
    headers: Dict[str, str]
    body: Optional[str]
    error: Optional[str] = None
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class SystemStatus:
    """系统状态"""
    online: bool
    connected_nodes: int
    active_routes: int
    cpu_usage: float
    memory_usage: float
    network_quality: str  # excellent/good/poor
    last_update: float = None

    def __post_init__(self):
        if self.last_update is None:
            self.last_update = time.time()


@dataclass
class ConfigUpdate:
    """配置更新"""
    key: str
    value: Any
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


# ==================== Web API 类 ====================

class WebAPIManager:
    """
    Web API 管理器

    封装所有Web API逻辑
    """

    def __init__(self, route_engine=None, config_store=None):
        self.route_engine = route_engine
        self.config_store = config_store
        self.active_websockets: List[WebSocket] = []
        self.system_status = SystemStatus(
            online=True,
            connected_nodes=0,
            active_routes=0,
            cpu_usage=0.0,
            memory_usage=0.0,
            network_quality="good"
        )

    async def test_route(self, request: RouteTestRequest) -> RouteTestResult:
        """测试路由 - 与客户端API完全一致"""
        start_time = time.time()

        try:
            # 复用核心引擎
            if self.route_engine:
                result = await self.route_engine.test(
                    request.url,
                    method=request.method,
                    headers=request.headers,
                    body=request.body,
                    timeout=request.timeout
                )
                return RouteTestResult(
                    success=result.get('success', False),
                    status_code=result.get('status_code'),
                    response_time=(time.time() - start_time) * 1000,
                    headers=result.get('headers', {}),
                    body=result.get('body'),
                    error=result.get('error')
                )

            # 模拟响应（无引擎时）
            return RouteTestResult(
                success=True,
                status_code=200,
                response_time=50.0,
                headers={"Content-Type": "text/html"},
                body="<h1>Web API Test</p>",
                error=None
            )

        except Exception as e:
            return RouteTestResult(
                success=False,
                status_code=None,
                response_time=(time.time() - start_time) * 1000,
                headers={},
                body=None,
                error=str(e)
            )

    async def get_system_status(self) -> SystemStatus:
        """获取系统状态"""
        # 更新状态
        if hasattr(self, '_status_monitor'):
            status = await self._status_monitor.get_status()
            self.system_status = SystemStatus(**status)
        return self.system_status

    async def update_config(self, update: ConfigUpdate) -> Dict[str, Any]:
        """更新配置"""
        if self.config_store:
            await self.config_store.set(update.key, update.value)
            return {"success": True, "key": update.key}

        return {"success": False, "error": "Config store not available"}

    async def get_config(self, key: str) -> Any:
        """获取配置"""
        if self.config_store:
            return await self.config_store.get(key)
        return None

    async def broadcast_status(self):
        """广播状态更新到所有WebSocket客户端"""
        if not self.active_websockets:
            return

        status = await self.get_system_status()
        message = json.dumps({
            "type": "status_update",
            "data": asdict(status),
            "timestamp": time.time()
        })

        disconnected = []
        for ws in self.active_websockets:
            try:
                await ws.send_text(message)
            except:
                disconnected.append(ws)

        # 清理断开的连接
        for ws in disconnected:
            self.active_websockets.remove(ws)

    async def handle_websocket(self, websocket: WebSocket):
        """处理WebSocket连接"""
        await websocket.accept()
        self.active_websockets.append(websocket)

        try:
            while True:
                # 接收客户端消息
                data = await websocket.receive_json()

                # 处理消息
                response = await self._handle_ws_message(data)
                if response:
                    await websocket.send_json(response)

        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            if websocket in self.active_websockets:
                self.active_websockets.remove(websocket)

    async def _handle_ws_message(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理WebSocket消息"""
        msg_type = data.get("type")

        if msg_type == "ping":
            return {"type": "pong", "timestamp": time.time()}

        elif msg_type == "get_status":
            status = await self.get_system_status()
            return {"type": "status", "data": asdict(status), "timestamp": time.time()}

        elif msg_type == "subscribe":
            return {"type": "subscribed", "timestamp": time.time()}

        return None


# ==================== FastAPI 应用 ====================

if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Hermes Desktop Web API",
        description="智能路由系统 Web API - 与桌面/移动端API一致",
        version="1.0.0"
    )

    # 中间件
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API管理器（需要初始化）
    api_manager: Optional[WebAPIManager] = None


    @app.on_event("startup")
    async def startup_event():
        """应用启动"""
        global api_manager
        api_manager = WebAPIManager()

        # 启动状态广播定时器
        asyncio.create_task(status_broadcaster())


    async def status_broadcaster():
        """状态广播定时器"""
        while True:
            if api_manager:
                await api_manager.broadcast_status()
            await asyncio.sleep(5)  # 每5秒广播一次


    # ==================== API 端点 ====================

    @app.get("/")
    async def root():
        """根路径 - 返回Web界面"""
        return HTMLResponse(content=get_web_index_html())


    @app.get("/api/health")
    async def health_check():
        """健康检查"""
        return {"status": "healthy", "timestamp": time.time()}


    @app.get("/api/status")
    async def get_status():
        """获取系统状态"""
        if api_manager:
            status = await api_manager.get_system_status()
            return asdict(status)
        return {"error": "API not initialized"}


    @app.post("/api/route/test")
    async def test_route(request: RouteTestRequest):
        """
        路由测试

        与桌面/移动端API完全一致
        """
        if api_manager:
            result = await api_manager.test_route(request)
            return asdict(result)
        raise HTTPException(status_code=500, detail="API not initialized")


    @app.get("/api/route/list")
    async def list_routes():
        """获取路由列表"""
        # 模拟数据
        return {
            "routes": [
                {"id": "1", "name": "GitHub加速", "pattern": "*.github.com/*", "enabled": True},
                {"id": "2", "name": "学术搜索", "pattern": "*.scholar.google.com/*", "enabled": True},
                {"id": "3", "name": "Docker镜像", "pattern": "*.docker.io/*", "enabled": False},
            ]
        }


    @app.post("/api/config/update")
    async def update_config(update: ConfigUpdate):
        """更新配置"""
        if api_manager:
            result = await api_manager.update_config(update)
            return result
        raise HTTPException(status_code=500, detail="API not initialized")


    @app.get("/api/config/{key}")
    async def get_config(key: str):
        """获取配置"""
        if api_manager:
            value = await api_manager.get_config(key)
            return {"key": key, "value": value}
        raise HTTPException(status_code=500, detail="API not initialized")


    @app.get("/api/device/info")
    async def get_device_info(request: Request):
        """获取设备信息"""
        user_agent = request.headers.get("user-agent", "")

        # 解析设备类型
        device_info = parse_user_agent(user_agent)

        return {
            "device_type": device_info["type"],
            "os": device_info["os"],
            "browser": device_info["browser"],
            "is_mobile": device_info["is_mobile"],
            "is_tablet": device_info["is_tablet"],
            "has_keyboard": device_info["has_keyboard"],
            "screen_size": device_info.get("screen_size"),
            "supports_pwa": True,
        }


    @app.websocket("/ws/status")
    async def websocket_status(websocket: WebSocket):
        """WebSocket状态推送"""
        if api_manager:
            await api_manager.handle_websocket(websocket)


    # ==================== PWA 相关 ====================

    @app.get("/manifest.json")
    async def get_manifest():
        """PWA Manifest"""
        return {
            "name": "Hermes Desktop",
            "short_name": "Hermes",
            "description": "智能路由系统 Web版",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#1e1e1e",
            "theme_color": "#007acc",
            "orientation": "any",
            "icons": [
                {
                    "src": "/icons/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png"
                },
                {
                    "src": "/icons/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png"
                },
                {
                    "src": "/icons/icon-maskable.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable"
                }
            ],
            "categories": ["productivity", "utilities"],
            "lang": "zh-CN"
        }


    @app.get("/sw.js")
    async def get_service_worker():
        """Service Worker"""
        return FileResponse(
            "web/sw.js",
            media_type="application/javascript"
        )


    # ==================== 设备检测工具函数 ====================

    def parse_user_agent(ua: str) -> Dict[str, Any]:
        """解析User-Agent获取设备信息"""
        ua = ua.lower()

        info = {
            "type": "desktop",
            "os": "unknown",
            "browser": "unknown",
            "is_mobile": False,
            "is_tablet": False,
            "has_keyboard": True,
            "screen_size": None
        }

        # 检测操作系统
        if "windows" in ua:
            info["os"] = "windows"
        elif "macintosh" in ua or "mac os" in ua:
            info["os"] = "macos"
        elif "linux" in ua:
            info["os"] = "linux"
        elif "android" in ua:
            info["os"] = "android"
            info["is_mobile"] = True
            info["has_keyboard"] = False
        elif "iphone" in ua or "ipad" in ua:
            info["os"] = "ios"
            info["is_mobile"] = True
            info["has_keyboard"] = False

        # 检测设备类型
        if "ipad" in ua:
            info["type"] = "tablet"
            info["is_tablet"] = True
            info["has_keyboard"] = False
        elif "iphone" in ua:
            info["type"] = "phone"
        elif "android" in ua and "mobile" in ua:
            info["type"] = "phone"
        elif "tablet" in ua or "tab" in ua:
            info["type"] = "tablet"
            info["is_tablet"] = True

        # 检测浏览器
        if "chrome" in ua and "edg" not in ua:
            info["browser"] = "chrome"
        elif "firefox" in ua:
            info["browser"] = "firefox"
        elif "safari" in ua:
            info["browser"] = "safari"
        elif "edg" in ua:
            info["browser"] = "edge"

        return info


# ==================== Web 界面 HTML ====================

def get_web_index_html() -> str:
    """获取Web首页HTML"""
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="description" content="Hermes Desktop - 智能路由系统 Web版">
    <meta name="theme-color" content="#1e1e1e">
    <title>Hermes Desktop - 智能路由</title>

    <!-- PWA -->
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/icons/icon-192.png">

    <style>
        /* CSS Variables */
        :root {
            --bg-primary: #1e1e1e;
            --bg-secondary: #252526;
            --bg-tertiary: #2d2d2e;
            --text-primary: #d4d4d4;
            --text-secondary: #858585;
            --primary: #007acc;
            --primary-hover: #1e90ff;
            --success: #4CAF50;
            --warning: #ff9800;
            --error: #f44336;
            --border: #3c3c3c;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Header */
        .header {
            background: var(--bg-secondary);
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-icon {
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, var(--primary), #3794ff);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
        }

        .logo-text {
            font-size: 18px;
            font-weight: 600;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            background: var(--bg-tertiary);
            border-radius: 20px;
            font-size: 12px;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* Main Content */
        .main {
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }

        /* Status Cards */
        .status-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .status-card {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid var(--border);
        }

        .status-card-label {
            color: var(--text-secondary);
            font-size: 12px;
            margin-bottom: 8px;
        }

        .status-card-value {
            font-size: 28px;
            font-weight: 600;
            color: var(--text-primary);
        }

        .status-card-value.success { color: var(--success); }
        .status-card-value.warning { color: var(--warning); }
        .status-card-value.error { color: var(--error); }

        /* Route Test Section */
        .section {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid var(--border);
        }

        .section-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .input-group {
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
        }

        .input-group input {
            flex: 1;
            padding: 12px 16px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }

        .input-group input:focus {
            border-color: var(--primary);
        }

        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-primary {
            background: var(--primary);
            color: white;
        }

        .btn-primary:hover {
            background: var(--primary-hover);
        }

        .btn-secondary {
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }

        .btn-secondary:hover {
            background: var(--border);
        }

        /* Route List */
        .route-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .route-item {
            display: flex;
            align-items: center;
            padding: 12px 16px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            gap: 12px;
        }

        .route-toggle {
            width: 44px;
            height: 24px;
            background: var(--border);
            border-radius: 12px;
            position: relative;
            cursor: pointer;
            transition: background 0.2s;
        }

        .route-toggle.active {
            background: var(--primary);
        }

        .route-toggle::after {
            content: '';
            position: absolute;
            width: 20px;
            height: 20px;
            background: white;
            border-radius: 50%;
            top: 2px;
            left: 2px;
            transition: transform 0.2s;
        }

        .route-toggle.active::after {
            transform: translateX(20px);
        }

        .route-info {
            flex: 1;
        }

        .route-name {
            font-weight: 500;
            margin-bottom: 4px;
        }

        .route-pattern {
            font-size: 12px;
            color: var(--text-secondary);
        }

        .route-status {
            font-size: 12px;
            padding: 4px 8px;
            border-radius: 4px;
            background: var(--bg-secondary);
        }

        .route-status.active {
            color: var(--success);
        }

        /* Test Result */
        .test-result {
            margin-top: 16px;
            padding: 16px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            display: none;
        }

        .test-result.show {
            display: block;
        }

        .test-result-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
        }

        .test-status {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .test-status.success { color: var(--success); }
        .test-status.error { color: var(--error); }

        /* Mobile Responsive */
        @media (max-width: 767px) {
            .header {
                padding: 12px 16px;
            }

            .logo-text {
                font-size: 16px;
            }

            .main {
                padding: 16px;
            }

            .status-cards {
                grid-template-columns: repeat(2, 1fr);
            }

            .status-card {
                padding: 16px;
            }

            .status-card-value {
                font-size: 24px;
            }

            .input-group {
                flex-direction: column;
            }

            .btn {
                width: 100%;
            }
        }

        /* Tablet Responsive */
        @media (min-width: 768px) and (max-width: 1024px) {
            .status-cards {
                grid-template-columns: repeat(3, 1fr);
            }
        }

        /* Loading */
        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid var(--text-secondary);
            border-radius: 50%;
            border-top-color: var(--primary);
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Toast */
        .toast {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 24px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.3s;
        }

        .toast.show {
            opacity: 1;
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">
            <div class="logo-icon">H</div>
            <span class="logo-text">Hermes Desktop</span>
        </div>
        <div class="status-badge">
            <div class="status-dot"></div>
            <span>在线</span>
        </div>
    </header>

    <main class="main">
        <!-- Status Cards -->
        <div class="status-cards">
            <div class="status-card">
                <div class="status-card-label">连接节点</div>
                <div class="status-card-value" id="nodes">0</div>
            </div>
            <div class="status-card">
                <div class="status-card-label">活跃路由</div>
                <div class="status-card-value success" id="routes">0</div>
            </div>
            <div class="status-card">
                <div class="status-card-label">网络质量</div>
                <div class="status-card-value" id="network">良好</div>
            </div>
            <div class="status-card">
                <div class="status-card-label">响应时间</div>
                <div class="status-card-value" id="latency">--</div>
            </div>
        </div>

        <!-- Route Test -->
        <div class="section">
            <h2 class="section-title">
                <span>路由测试</span>
            </h2>
            <div class="input-group">
                <input type="text" id="testUrl" placeholder="输入要测试的URL，如 https://github.com" value="https://github.com">
                <button class="btn btn-primary" id="testBtn" onclick="testRoute()">
                    测试
                </button>
            </div>
            <div class="test-result" id="testResult">
                <div class="test-result-header">
                    <div class="test-status" id="testStatus">
                        <span>等待测试...</span>
                    </div>
                    <div id="testTime" style="color: var(--text-secondary);">--</div>
                </div>
                <pre id="testBody" style="font-size: 12px; overflow-x: auto; white-space: pre-wrap;"></pre>
            </div>
        </div>

        <!-- Route List -->
        <div class="section">
            <h2 class="section-title">
                <span>路由规则</span>
                <button class="btn btn-secondary" onclick="loadRoutes()" style="margin-left: auto; padding: 6px 12px; font-size: 12px;">
                    刷新
                </button>
            </h2>
            <div class="route-list" id="routeList">
                <div class="route-item">
                    <div class="route-info">
                        <div class="route-name">加载中...</div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <div class="toast" id="toast"></div>

    <script>
        // API Base
        const API_BASE = '/api';

        // WebSocket
        let ws = null;

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            initWebSocket();
            loadStatus();
            loadRoutes();
        });

        // WebSocket Connection
        function initWebSocket() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${location.host}/ws/status`);

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'status_update') {
                    updateStatus(data.data);
                }
            };

            ws.onclose = () => {
                setTimeout(initWebSocket, 3000);
            };
        }

        // Load Status
        async function loadStatus() {
            try {
                const res = await fetch(`${API_BASE}/status`);
                const data = await res.json();
                updateStatus(data);
            } catch (e) {
                console.error('Failed to load status:', e);
            }
        }

        // Update Status
        function updateStatus(data) {
            document.getElementById('nodes').textContent = data.connected_nodes || 0;
            document.getElementById('routes').textContent = data.active_routes || 0;
            document.getElementById('network').textContent = data.network_quality === 'excellent' ? '优秀' :
                data.network_quality === 'good' ? '良好' : '一般';
            document.getElementById('network').className = 'status-card-value ' +
                (data.network_quality === 'excellent' ? 'success' :
                 data.network_quality === 'good' ? '' : 'warning');
        }

        // Test Route
        async function testRoute() {
            const url = document.getElementById('testUrl').value;
            const btn = document.getElementById('testBtn');
            const result = document.getElementById('testResult');

            if (!url) {
                showToast('请输入URL');
                return;
            }

            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span>';
            result.classList.add('show');
            document.getElementById('testStatus').innerHTML = '<span class="loading"></span> 正在测试...';
            document.getElementById('testTime').textContent = '';
            document.getElementById('testBody').textContent = '';

            try {
                const res = await fetch(`${API_BASE}/route/test`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, method: 'GET' })
                });

                const data = await res.json();

                document.getElementById('testTime').textContent = data.response_time.toFixed(1) + 'ms';

                if (data.success) {
                    document.getElementById('testStatus').className = 'test-status success';
                    document.getElementById('testStatus').innerHTML = '✓ 成功 (' + data.status_code + ')';
                    document.getElementById('testBody').textContent = data.body ?
                        data.body.substring(0, 500) + (data.body.length > 500 ? '...' : '') : '(无响应体)';
                } else {
                    document.getElementById('testStatus').className = 'test-status error';
                    document.getElementById('testStatus').innerHTML = '✗ 失败: ' + (data.error || '未知错误');
                    document.getElementById('testBody').textContent = '';
                }

                document.getElementById('latency').textContent = data.response_time.toFixed(0) + 'ms';

            } catch (e) {
                document.getElementById('testStatus').className = 'test-status error';
                document.getElementById('testStatus').innerHTML = '✗ 请求失败';
                showToast('测试请求失败');
            }

            btn.disabled = false;
            btn.textContent = '测试';
        }

        // Load Routes
        async function loadRoutes() {
            try {
                const res = await fetch(`${API_BASE}/route/list`);
                const data = await res.json();

                const list = document.getElementById('routeList');
                list.innerHTML = data.routes.map(route => `
                    <div class="route-item">
                        <div class="route-toggle ${route.enabled ? 'active' : ''}"
                             onclick="toggleRoute('${route.id}')"></div>
                        <div class="route-info">
                            <div class="route-name">${route.name}</div>
                            <div class="route-pattern">${route.pattern}</div>
                        </div>
                        <div class="route-status ${route.enabled ? 'active' : ''}">
                            ${route.enabled ? '启用' : '禁用'}
                        </div>
                    </div>
                `).join('');

            } catch (e) {
                console.error('Failed to load routes:', e);
            }
        }

        // Toggle Route
        async function toggleRoute(id) {
            showToast('路由切换功能开发中...');
        }

        // Toast
        function showToast(message) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }
    </script>
</body>
</html>
"""


if __name__ == "__main__" and FASTAPI_AVAILABLE:
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)