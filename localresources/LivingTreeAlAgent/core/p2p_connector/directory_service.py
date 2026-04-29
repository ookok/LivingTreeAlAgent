"""
目录服务与ID解析

实现短ID到节点档案的解析、节点注册、状态维护
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional, Callable

from .models import NodeProfile, PeerStatus, DEFAULT_DIRECTORY_SERVERS

logger = logging.getLogger(__name__)


class DirectoryService:
    """
    目录服务
    
    功能:
    - 节点档案注册与更新
    - 短ID解析
    - 在线状态维护
    - 节点发现
    """
    
    # 状态过期时间 (秒)
    STATUS_EXPIRY = 300  # 5分钟
    
    def __init__(self, data_dir: str = "~/.hermes-desktop/connector"):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 数据库
        self.db_path = self.data_dir / "directory.db"
        self._init_db()
        
        # 目录服务器
        self.directory_servers = DEFAULT_DIRECTORY_SERVERS
        
        # 我的节点信息
        self._my_profile: Optional[NodeProfile] = None
        
        # 在线节点缓存
        self._online_cache: dict[str, NodeProfile] = {}
        self._cache_time: dict[str, float] = {}
        
        # 回调函数
        self._on_peer_online: Optional[Callable] = None
        self._on_peer_offline: Optional[Callable] = None
        self._on_profile_updated: Optional[Callable] = None
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 节点档案表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                node_id TEXT PRIMARY KEY,
                short_id TEXT UNIQUE,
                display_name TEXT,
                avatar TEXT,
                public_ip TEXT,
                public_port INTEGER,
                nat_type INTEGER,
                relay_hosts TEXT,
                public_key TEXT,
                status TEXT,
                last_seen REAL,
                capabilities TEXT,
                tags TEXT,
                bio TEXT,
                updated_at REAL
            )
        """)
        
        # 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_short_id ON profiles(short_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON profiles(status)")
        
        # 历史记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lookup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_id TEXT,
                node_id TEXT,
                timestamp REAL,
                result TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Directory database initialized: {self.db_path}")
    
    # ========== 节点档案管理 ==========
    
    def register_profile(self, profile: NodeProfile) -> bool:
        """
        注册节点档案
        
        Args:
            profile: 节点档案
            
        Returns:
            bool: 是否成功
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO profiles (
                    node_id, short_id, display_name, avatar,
                    public_ip, public_port, nat_type, relay_hosts,
                    public_key, status, last_seen, capabilities, tags, bio,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile.node_id,
                profile.short_id,
                profile.display_name,
                profile.avatar,
                profile.public_ip,
                profile.public_port,
                profile.nat_type,
                json.dumps(profile.relay_hosts),
                profile.public_key,
                profile.status.value,
                profile.last_seen,
                json.dumps(profile.capabilities),
                json.dumps(profile.tags),
                profile.bio,
                time.time()
            ))
            
            conn.commit()
            conn.close()
            
            # 更新缓存
            self._online_cache[profile.node_id] = profile
            self._cache_time[profile.node_id] = time.time()
            
            logger.debug(f"Registered profile: {profile.short_id} -> {profile.node_id[:16]}...")
            return True
            
        except Exception as e:
            logger.error(f"Register profile failed: {e}")
            return False
    
    def update_status(self, node_id: str, status: PeerStatus) -> bool:
        """
        更新节点状态
        
        Args:
            node_id: 节点ID
            status: 新状态
            
        Returns:
            bool: 是否成功
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE profiles SET status = ?, last_seen = ?
                WHERE node_id = ?
            """, (status.value, time.time(), node_id))
            
            conn.commit()
            conn.close()
            
            # 更新缓存
            if node_id in self._online_cache:
                self._online_cache[node_id].status = status
                self._online_cache[node_id].last_seen = time.time()
                
                # 触发回调
                if status == PeerStatus.ONLINE and self._on_peer_online:
                    self._on_peer_online(node_id)
                elif status == PeerStatus.OFFLINE and self._on_peer_offline:
                    self._on_peer_offline(node_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Update status failed: {e}")
            return False
    
    def get_profile(self, node_id: str) -> Optional[NodeProfile]:
        """
        获取节点档案
        
        Args:
            node_id: 节点ID
            
        Returns:
            NodeProfile or None
        """
        # 检查缓存
        if node_id in self._online_cache:
            if time.time() - self._cache_time[node_id] < self.STATUS_EXPIRY:
                return self._online_cache[node_id]
        
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM profiles WHERE node_id = ?", (node_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            profile = self._row_to_profile(row)
            
            # 更新缓存
            if profile.status == PeerStatus.ONLINE:
                self._online_cache[node_id] = profile
                self._cache_time[node_id] = time.time()
            
            return profile
        
        return None
    
    def _row_to_profile(self, row: sqlite3.Row) -> NodeProfile:
        """行转档案"""
        return NodeProfile(
            node_id=row["node_id"],
            short_id=row["short_id"] or "",
            display_name=row["display_name"] or "",
            avatar=row["avatar"],
            public_ip=row["public_ip"],
            public_port=row["public_port"],
            nat_type=row["nat_type"] or 0,
            relay_hosts=json.loads(row["relay_hosts"]) if row["relay_hosts"] else [],
            public_key=row["public_key"],
            status=PeerStatus(row["status"]) if row["status"] else PeerStatus.OFFLINE,
            last_seen=row["last_seen"] or time.time(),
            capabilities=json.loads(row["capabilities"]) if row["capabilities"] else [],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            bio=row["bio"] or ""
        )
    
    # ========== ID解析 ==========
    
    def resolve_short_id(self, short_id: str) -> Optional[NodeProfile]:
        """
        通过短ID解析节点档案
        
        Args:
            short_id: 短ID
            
        Returns:
            NodeProfile or None
        """
        # 查询数据库
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT node_id FROM profiles WHERE short_id = ?
        """, (short_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            # 记录查询历史
            self._log_lookup(short_id, row["node_id"], "local")
            
            # 获取完整档案
            return self.get_profile(row["node_id"])
        
        # 本地找不到, 尝试查询目录服务器
        return self._resolve_from_server(short_id)
    
    async def _resolve_from_server(self, short_id: str) -> Optional[NodeProfile]:
        """从目录服务器解析"""
        for server in self.directory_servers:
            try:
                host, port = server.split(":")
                profile = await self._query_server(host, int(port), short_id)
                
                if profile:
                    # 缓存到本地
                    self.register_profile(profile)
                    self._log_lookup(short_id, profile.node_id, f"server:{server}")
                    return profile
                    
            except Exception as e:
                logger.debug(f"Query server {server} failed: {e}")
        
        return None
    
    async def _query_server(self, host: str, port: int, short_id: str) -> Optional[NodeProfile]:
        """查询目录服务器"""
        try:
            import socket
            
            # 发送查询请求
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )
            
            query = json.dumps({"action": "resolve", "short_id": short_id})
            writer.write(query.encode())
            await writer.drain()
            
            # 接收响应
            response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            writer.close()
            await writer.wait_closed()
            
            data = json.loads(response.decode())
            
            if data.get("found"):
                return NodeProfile.from_dict(data["profile"])
            
        except Exception as e:
            logger.debug(f"Query server failed: {e}")
        
        return None
    
    def _log_lookup(self, short_id: str, node_id: str, source: str):
        """记录查询历史"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO lookup_history (short_id, node_id, timestamp, result)
                VALUES (?, ?, ?, ?)
            """, (short_id, node_id, time.time(), source))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"Log lookup failed: {e}")
    
    # ========== 节点发现 ==========
    
    def discover_peers(self, tags: list[str] = None, capabilities: list[str] = None,
                      limit: int = 50) -> list[NodeProfile]:
        """
        发现节点
        
        Args:
            tags: 标签过滤
            capabilities: 能力过滤
            limit: 返回数量
            
        Returns:
            list[NodeProfile]
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM profiles WHERE status = 'online'"
        params = []
        
        if tags:
            # JSON数组包含任一标签
            for tag in tags:
                query += " AND capabilities LIKE ?"
                params.append(f"%{tag}%")
        
        if capabilities:
            for cap in capabilities:
                query += " AND capabilities LIKE ?"
                params.append(f"%{cap}%")
        
        query += " ORDER BY last_seen DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_profile(row) for row in rows]
    
    def get_online_peers(self) -> list[NodeProfile]:
        """获取所有在线节点"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM profiles 
            WHERE status = 'online' AND last_seen > ?
            ORDER BY last_seen DESC
        """, (time.time() - self.STATUS_EXPIRY,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_profile(row) for row in rows]
    
    # ========== 我的节点 ==========
    
    def set_my_profile(self, profile: NodeProfile):
        """设置我的节点档案"""
        profile.status = PeerStatus.ONLINE
        profile.last_seen = time.time()
        self._my_profile = profile
        self.register_profile(profile)
    
    def get_my_profile(self) -> Optional[NodeProfile]:
        """获取我的节点档案"""
        return self._my_profile
    
    # ========== 批量操作 ==========
    
    def bulk_register(self, profiles: list[NodeProfile]) -> int:
        """
        批量注册节点
        
        Args:
            profiles: 节点档案列表
            
        Returns:
            int: 成功数量
        """
        count = 0
        for profile in profiles:
            if self.register_profile(profile):
                count += 1
        return count
    
    def cleanup_expired(self) -> int:
        """
        清理过期记录
        
        Returns:
            int: 清理数量
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        expiry = time.time() - self.STATUS_EXPIRY * 2
        
        cursor.execute("""
            UPDATE profiles SET status = 'offline'
            WHERE status = 'online' AND last_seen < ?
        """, (expiry,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Cleaned up {deleted} expired profiles")
        return deleted
    
    # ========== 回调设置 ==========
    
    def set_callbacks(self, **kwargs):
        """设置回调函数"""
        self._on_peer_online = kwargs.get("on_peer_online")
        self._on_peer_offline = kwargs.get("on_peer_offline")
        self._on_profile_updated = kwargs.get("on_profile_updated")
