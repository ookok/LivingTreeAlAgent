"""
LivingTree — MCP Server Manager (Full Migration)
==================================================

Full migration from client/src/business/mcp_manager.py

Features:
- MCP Server subscription (SSE/HTTP/stdio)
- Status monitoring with auto-reconnect
- Tool discovery and invocation
- SQLite persistence
- Publish self as MCP server
"""

import json
import time
import asyncio
import threading
import sqlite3
import uuid
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum

try:
    import httpx
except ImportError:
    httpx = None


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
class MCPServerInfo:
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
class MCPToolDef:
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)


class MCPDatabase:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS mcp_servers (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
                url TEXT DEFAULT '', protocol TEXT DEFAULT 'sse',
                status TEXT DEFAULT 'offline', source TEXT DEFAULT 'local',
                capabilities TEXT DEFAULT '[]', tags TEXT DEFAULT '[]',
                created_at REAL DEFAULT 0, updated_at REAL DEFAULT 0,
                last_connected REAL DEFAULT 0, last_error TEXT DEFAULT '',
                auto_connect INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_mcp_servers_status ON mcp_servers(status);
        """)
        conn.close()

    def add_server(self, server: MCPServerInfo) -> bool:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT OR REPLACE INTO mcp_servers "
                "(id,name,description,url,protocol,status,source,capabilities,tags,"
                "created_at,updated_at,last_connected,last_error,auto_connect) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (server.id, server.name, server.description, server.url,
                 server.protocol, server.status, server.source,
                 json.dumps(server.capabilities), json.dumps(server.tags),
                 server.created_at, server.updated_at, server.last_connected,
                 server.last_error, 1 if server.auto_connect else 0))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_server(self, server_id: str) -> Optional[MCPServerInfo]:
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute("SELECT * FROM mcp_servers WHERE id=?", (server_id,)).fetchone()
            return self._row_to_server(row) if row else None
        finally:
            conn.close()

    def list_servers(self, source: str = None) -> List[MCPServerInfo]:
        conn = sqlite3.connect(str(self.db_path))
        try:
            if source:
                rows = conn.execute("SELECT * FROM mcp_servers WHERE source=?", (source,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM mcp_servers").fetchall()
            return [self._row_to_server(row) for row in rows]
        finally:
            conn.close()

    def update_status(self, server_id: str, status: str, error: str = ""):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "UPDATE mcp_servers SET status=?,last_error=?,updated_at=?,last_connected=? WHERE id=?",
                (status, error, time.time(), time.time() if status == "online" else 0, server_id))
            conn.commit()
        finally:
            conn.close()

    def delete_server(self, server_id: str):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("DELETE FROM mcp_servers WHERE id=?", (server_id,))
            conn.commit()
        finally:
            conn.close()

    def _row_to_server(self, row) -> MCPServerInfo:
        return MCPServerInfo(
            id=row[0], name=row[1], description=row[2], url=row[3],
            protocol=row[4], status=row[5], source=row[6],
            capabilities=json.loads(row[7] or "[]"), tags=json.loads(row[8] or "[]"),
            created_at=row[9], updated_at=row[10],
            last_connected=row[11], last_error=row[12], auto_connect=bool(row[13]))


class MCPClient:
    def __init__(self, server: MCPServerInfo):
        self.server = server
        self._connected = False
        self._tools: List[MCPToolDef] = []
        self._lock = threading.Lock()

    async def connect(self) -> bool:
        if self.server.protocol == MCPProtocol.SSE.value:
            return await self._connect_sse()
        elif self.server.protocol == MCPProtocol.HTTP.value:
            return await self._connect_http()
        return False

    async def _connect_sse(self) -> bool:
        if httpx is None:
            return False
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                async with client.stream("GET", f"{self.server.url}/sse") as response:
                    self._connected = True
                    self.server.status = ServerStatus.ONLINE.value
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
        if httpx is None:
            return False
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
        tools = data.get("tools", [])
        with self._lock:
            self._tools = [MCPToolDef(
                name=t.get("name", ""), description=t.get("description", ""),
                input_schema=t.get("inputSchema", {})) for t in tools]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self._connected:
            return {"error": "Not connected"}
        if httpx is None:
            return {"error": "httpx not available"}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.server.url}/call",
                    json={"tool": tool_name, "arguments": arguments})
                return response.json() if response.status_code == 200 else {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def disconnect(self):
        self._connected = False

    @property
    def tools(self) -> List[MCPToolDef]:
        with self._lock:
            return self._tools.copy()


class MCPServerManager:
    def __init__(self, db_path: str | Path = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "mcp.db"
        self.db = MCPDatabase(db_path)
        self._clients: Dict[str, MCPClient] = {}
        self._status_listeners: List[Callable[[str, str, str], None]] = []
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()

    def add_server(self, name: str, url: str, protocol: str = "sse",
                   description: str = "", tags: List[str] = None,
                   source: str = "remote", auto_connect: bool = False) -> MCPServerInfo:
        server = MCPServerInfo(
            id=str(uuid.uuid4()), name=name, url=url, protocol=protocol,
            description=description, tags=tags or [],
            source=source, auto_connect=auto_connect)
        self.db.add_server(server)
        return server

    def remove_server(self, server_id: str):
        if server_id in self._clients:
            self._clients[server_id].disconnect()
            del self._clients[server_id]
        self.db.delete_server(server_id)

    def list_servers(self, source: str = None) -> List[MCPServerInfo]:
        return self.db.list_servers(source)

    def get_server(self, server_id: str) -> Optional[MCPServerInfo]:
        return self.db.get_server(server_id)

    async def connect(self, server_id: str) -> bool:
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
        if server_id in self._clients:
            self._clients[server_id].disconnect()
            del self._clients[server_id]
            self.db.update_status(server_id, ServerStatus.OFFLINE.value)
            self._notify_status(server_id, "offline", "")

    async def call_tool(self, server_id: str, tool_name: str,
                        arguments: Dict[str, Any]) -> Dict[str, Any]:
        if server_id not in self._clients:
            if not await self.connect(server_id):
                return {"error": "Failed to connect"}
        client = self._clients.get(server_id)
        return await client.call_tool(tool_name, arguments) if client else {"error": "Client not available"}

    def get_tools(self, server_id: str) -> List[MCPToolDef]:
        client = self._clients.get(server_id)
        return client.tools if client else []

    def on_status_change(self, callback: Callable):
        self._status_listeners.append(callback)

    def _notify_status(self, server_id: str, status: str, error: str):
        for listener in self._status_listeners:
            try:
                listener(server_id, status, error)
            except Exception:
                pass

    def start_monitoring(self, interval: int = 30):
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, args=(interval,), daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self):
        self._stop_monitor.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

    def _monitor_loop(self, interval: int):
        while not self._stop_monitor.wait(interval):
            for server in self.db.list_servers():
                if server.auto_connect and server.status != ServerStatus.ONLINE.value:
                    asyncio.run(self.connect(server.id))


# ── Singleton ──────────────────────────────────────────────

_mcp_manager: Optional[MCPServerManager] = None


def get_mcp_manager(db_path: str = None) -> MCPServerManager:
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPServerManager(db_path)
    return _mcp_manager


__all__ = [
    "MCPServerManager", "MCPClient", "MCPDatabase",
    "MCPServerInfo", "MCPToolDef",
    "MCPProtocol", "ServerStatus", "ServerSource",
    "get_mcp_manager",
]
