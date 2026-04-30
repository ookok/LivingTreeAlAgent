"""
MCP Server 管理器
支持 MCP Server 订阅、发布、状态监听
"""

import json
import time
import asyncio
import threading
import sqlite3
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
import httpx
import uuid


class MCPProtocol(Enum):
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


class ServerStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    CONNECTING = "connecting"


class ServerSource(Enum):
    LOCAL = "local"
    REMOTE = "remote"
    MARKET = "market"


@dataclass
class MCPServer:
    """MCP Server 信息"""
    id: str
    name: str
    description: str = ""
    url: str = ""
    protocol: str = "sse"
    status: str = "offline"
    source: str = "local"
    capabilities: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_connected: float = 0.0
    last_error: str = ""
    auto_connect: bool = False


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)


class MCPDatabase:
    """MCP 数据库管理"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS mcp_servers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                url TEXT DEFAULT '',
                protocol TEXT DEFAULT 'sse',
                status TEXT DEFAULT 'offline',
                source TEXT DEFAULT 'local',
                capabilities TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                created_at REAL DEFAULT 0,
                updated_at REAL DEFAULT 0,
                last_connected REAL DEFAULT 0,
                last_error TEXT DEFAULT '',
                auto_connect INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS mcp_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                user_id TEXT DEFAULT 'default',
                status TEXT DEFAULT 'inactive',
                last_error TEXT DEFAULT '',
                FOREIGN KEY (server_id) REFERENCES mcp_servers(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_servers_status ON mcp_servers(status);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_server ON mcp_subscriptions(server_id);
        """)
        conn.close()

    def add_server(self, server: MCPServer) -> bool:
        """添加服务器"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                INSERT OR REPLACE INTO mcp_servers 
                (id, name, description, url, protocol, status, source, 
                 capabilities, tags, created_at, updated_at, last_connected, last_error, auto_connect)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                server.id, server.name, server.description, server.url,
                server.protocol, server.status, server.source,
                json.dumps(server.capabilities), json.dumps(server.tags),
                server.created_at, server.updated_at, server.last_connected,
                server.last_error, 1 if server.auto_connect else 0
            ))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_server(self, server_id: str) -> Optional[MCPServer]:
        """获取服务器"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT * FROM mcp_servers WHERE id=?", (server_id,)
            ).fetchone()
            if row:
                return self._row_to_server(row)
            return None
        finally:
            conn.close()

    def list_servers(self, source: str = None) -> List[MCPServer]:
        """列出服务器"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            if source:
                rows = conn.execute(
                    "SELECT * FROM mcp_servers WHERE source=?", (source,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM mcp_servers").fetchall()
            return [self._row_to_server(row) for row in rows]
        finally:
            conn.close()

    def update_status(self, server_id: str, status: str, error: str = ""):
        """更新状态"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "UPDATE mcp_servers SET status=?, last_error=?, updated_at=?, last_connected=? WHERE id=?",
                (status, error, time.time(), time.time() if status == "online" else 0, server_id)
            )
            conn.commit()
        finally:
            conn.close()

    def delete_server(self, server_id: str):
        """删除服务器"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("DELETE FROM mcp_servers WHERE id=?", (server_id,))
            conn.commit()
        finally:
            conn.close()

    def _row_to_server(self, row: sqlite3.Row) -> MCPServer:
        """行转对象"""
        return MCPServer(
            id=row[0], name=row[1], description=row[2], url=row[3],
            protocol=row[4], status=row[5], source=row[6],
            capabilities=json.loads(row[7] or "[]"),
            tags=json.loads(row[8] or "[]"),
            created_at=row[9], updated_at=row[10],
            last_connected=row[11], last_error=row[12],
            auto_connect=bool(row[13])
        )


class MCPClient:
    """MCP 客户端 - 订阅远程 MCP Server"""

    def __init__(self, server: MCPServer):
        self.server = server
        self._connected = False
        self._tools: List[MCPTool] = []
        self._lock = threading.Lock()

    async def connect(self) -> bool:
        """连接到 MCP Server"""
        if self.server.protocol == MCPProtocol.SSE.value:
            return await self._connect_sse()
        elif self.server.protocol == MCPProtocol.HTTP.value:
            return await self._connect_http()
        return False

    async def _connect_sse(self) -> bool:
        """SSE 连接"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                async with client.stream("GET", f"{self.server.url}/sse") as response:
                    self._connected = True
                    self.server.status = ServerStatus.ONLINE.value
                    # 解析 tools
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            data = line[5:].strip()
                            if data.startswith("{"):
                                self._parse_tool_response(json.loads(data))
                    return True
        except Exception as e:
            self.server.last_error = str(e)
            self.server.status = ServerStatus.ERROR.value
            return False

    async def _connect_http(self) -> bool:
        """HTTP 连接"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{self.server.url}/tools")
                if response.status_code == 200:
                    self._parse_tool_response(response.json())
                    self._connected = True
                    self.server.status = ServerStatus.ONLINE.value
                    return True
        except Exception as e:
            self.server.last_error = str(e)
            self.server.status = ServerStatus.ERROR.value
            return False

    def _parse_tool_response(self, data: dict):
        """解析工具响应"""
        tools = data.get("tools", [])
        with self._lock:
            self._tools = [
                MCPTool(
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {})
                ) for t in tools
            ]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具"""
        if not self._connected:
            return {"error": "Not connected"}

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.server.url}/call",
                    json={"tool": tool_name, "arguments": arguments}
                )
                if response.status_code == 200:
                    return response.json()
                return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def disconnect(self):
        """断开连接"""
        self._connected = False

    @property
    def tools(self) -> List[MCPTool]:
        with self._lock:
            return self._tools.copy()


class MCPServerManager:
    """
    MCP Server 管理器
    
    功能：
    - 添加/删除 MCP Server
    - 连接/断开
    - 状态监听
    - 工具调用
    """

    def __init__(self, db_path: str | Path = None):
        if db_path is None:
            from business.config import get_config_dir
            db_path = get_config_dir() / "mcp.db"
        self.db = MCPDatabase(db_path)
        self._clients: Dict[str, MCPClient] = {}
        self._status_listeners: List[Callable[[str, str, str], None]] = []
        self._monitor_thread: threading.Thread | None = None
        self._stop_monitor = threading.Event()

    def add_server(
        self, name: str, url: str, protocol: str = "sse",
        description: str = "", tags: List[str] = None,
        source: str = "remote", auto_connect: bool = False
    ) -> MCPServer:
        """添加 MCP Server"""
        server = MCPServer(
            id=str(uuid.uuid4()),
            name=name, url=url, protocol=protocol,
            description=description, tags=tags or [],
            source=source, auto_connect=auto_connect
        )
        self.db.add_server(server)
        return server

    def remove_server(self, server_id: str):
        """移除服务器"""
        if server_id in self._clients:
            self._clients[server_id].disconnect()
            del self._clients[server_id]
        self.db.delete_server(server_id)

    def list_servers(self, source: str = None) -> List[MCPServer]:
        """列出所有服务器"""
        return self.db.list_servers(source)

    def get_server(self, server_id: str) -> Optional[MCPServer]:
        """获取服务器"""
        return self.db.get_server(server_id)

    async def connect(self, server_id: str) -> bool:
        """连接服务器"""
        server = self.db.get_server(server_id)
        if not server:
            return False

        server.status = ServerStatus.CONNECTING.value
        self.db.update_status(server_id, server.status)

        client = MCPClient(server)
        success = await client.connect()

        if success:
            self._clients[server_id] = client
            self.db.update_status(server_id, ServerStatus.ONLINE.value)
            self._notify_status(server_id, "online", "")
        else:
            self.db.update_status(server_id, ServerStatus.ERROR.value, server.last_error)
            self._notify_status(server_id, "error", server.last_error)

        return success

    def disconnect(self, server_id: str):
        """断开连接"""
        if server_id in self._clients:
            self._clients[server_id].disconnect()
            del self._clients[server_id]
            self.db.update_status(server_id, ServerStatus.OFFLINE.value)
            self._notify_status(server_id, "offline", "")

    async def call_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具"""
        if server_id not in self._clients:
            # 尝试连接
            if not await self.connect(server_id):
                return {"error": "Failed to connect"}
        
        client = self._clients.get(server_id)
        if not client:
            return {"error": "Client not available"}
        
        return await client.call_tool(tool_name, arguments)

    def get_tools(self, server_id: str) -> List[MCPTool]:
        """获取服务器提供的工具"""
        client = self._clients.get(server_id)
        if client:
            return client.tools
        return []

    def on_status_change(self, callback: Callable[[str, str, str], None]):
        """注册状态变化监听"""
        self._status_listeners.append(callback)

    def _notify_status(self, server_id: str, status: str, error: str):
        """通知状态变化"""
        for listener in self._status_listeners:
            try:
                listener(server_id, status, error)
            except Exception:
                pass

    def start_monitoring(self, interval: int = 30):
        """启动状态监控"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, args=(interval,), daemon=True
        )
        self._monitor_thread.start()

    def stop_monitoring(self):
        """停止监控"""
        self._stop_monitor.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

    def _monitor_loop(self, interval: int):
        """监控循环"""
        while not self._stop_monitor.wait(interval):
            for server in self.db.list_servers():
                if server.auto_connect and server.status != ServerStatus.ONLINE.value:
                    # 自动重连
                    asyncio.run(self.connect(server.id))

    def publish_as_server(self, name: str, port: int = 8765) -> "PublishedMCPServer":
        """将本机发布为 MCP Server"""
        return PublishedMCPServer(name, port)

    def discover_market(self, query: str = "") -> List[MCPServer]:
        """从市场发现服务器"""
        # TODO: 实现从远程市场发现
        return []


class PublishedMCPServer:
    """发布的 MCP Server"""

    def __init__(self, name: str, port: int):
        self.name = name
        self.port = port
        self._running = False
        self._server = None
        self._tools: Dict[str, Callable] = {}

    def register_tool(self, name: str, description: str, handler: Callable, schema: dict = None):
        """注册工具"""
        self._tools[name] = handler

    async def start(self):
        """启动服务"""
        # TODO: 实现 HTTP/SSE 服务器
        self._running = True

    def stop(self):
        """停止服务"""
        self._running = False


# 单例
_mcp_manager: Optional[MCPServerManager] = None


def get_mcp_manager() -> MCPServerManager:
    """获取 MCP 管理器单例"""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPServerManager()
    return _mcp_manager
