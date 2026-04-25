# -*- coding: utf-8 -*-
"""
同步客户端 - Sync Client
========================

功能：
1. WebSocket 长连接管理
2. 增量数据同步
3. 离线队列管理
4. 状态回调通知

Author: Hermes Desktop Team
"""

from __future__ import annotations
import asyncio
import json
import logging
import threading
import queue
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from .data_types import (
    SyncData, SyncRecord, SyncStatus, SyncDataType,
    SyncConflict, SyncStatistics, ConflictStrategy
)

logger = logging.getLogger(__name__)


def _get_default_sync_config() -> Dict[str, Any]:
    """从统一配置获取默认值"""
    try:
        from core.config.unified_config import get_config
        return get_config().get_sync_config()
    except Exception:
        return {}


def _get_default_cloud_sync_config() -> Dict[str, Any]:
    """从统一配置获取云同步默认值"""
    try:
        from core.config.unified_config import get_config
        config = get_config()
        return {
            "url": config.get("endpoints.cloud_sync.url", "ws://localhost:8765/sync"),
            "timeout": config.get("endpoints.cloud_sync.timeout", 30),
        }
    except Exception:
        return {"url": "ws://localhost:8765/sync", "timeout": 30}


# 获取默认值
_default_config = _get_default_sync_config()
_default_cloud = _get_default_cloud_sync_config()


@dataclass
class SyncConfig:
    """同步配置"""
    server_url: str = field(default_factory=lambda: _default_cloud.get("url", "ws://localhost:8765/sync"))
    user_id: str = ""
    device_id: str = ""
    api_key: str = ""
    auto_sync: bool = True
    sync_interval: int = field(default_factory=lambda: _default_config.get("interval", 30))  # 秒
    batch_size: int = field(default_factory=lambda: _default_config.get("batch_size", 100))
    timeout: int = field(default_factory=lambda: _default_config.get("timeout", 30))
    retry_count: int = field(default_factory=lambda: _default_config.get("retry_count", 3))
    retry_delay: int = field(default_factory=lambda: _default_config.get("retry_delay", 5))


class SyncClient:
    """
    同步客户端
    
    管理本地数据与云端服务器的同步
    """
    
    def __init__(self, config: Optional[SyncConfig] = None):
        self.config = config or SyncConfig()
        self._running = False
        self._ws = None
        self._lock = threading.Lock()
        self._pending_queue: queue.Queue = queue.Queue()
        self._callbacks: Dict[str, List[Callable]] = {
            'on_sync': [],
            'on_conflict': [],
            'on_error': [],
            'on_status_change': [],
        }
        self._statistics = SyncStatistics()
        self._sync_thread: Optional[threading.Thread] = None
        self._local_db: Dict[str, SyncRecord] = {}  # 本地缓存
        self._pending_local: Dict[str, SyncRecord] = {}  # 待同步本地变更
        
    # ── 事件回调 ──────────────────────────────────────────────────────────────
    
    def on_sync(self, callback: Callable[[SyncStatistics], None]):
        """同步完成回调"""
        self._callbacks['on_sync'].append(callback)
    
    def on_conflict(self, callback: Callable[[SyncConflict], Any]):
        """冲突发现回调"""
        self._callbacks['on_conflict'].append(callback)
    
    def on_error(self, callback: Callable[[Exception], None]):
        """错误回调"""
        self._callbacks['on_error'].append(callback)
    
    def on_status_change(self, callback: Callable[[SyncStatus, str], None]):
        """状态变化回调"""
        self._callbacks['on_status_change'].append(callback)
    
    def _emit(self, event: str, *args):
        """触发事件"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    # ── 连接管理 ──────────────────────────────────────────────────────────────
    
    async def connect(self) -> bool:
        """连接服务器"""
        try:
            import websockets
            
            headers = {}
            if self.config.api_key:
                headers['Authorization'] = f"Bearer {self.config.api_key}"
            
            self._ws = await websockets.connect(
                self.config.server_url,
                extra_headers=headers,
                ping_timeout=self.config.timeout
            )
            
            # 发送认证
            await self._send({
                "type": "auth",
                "user_id": self.config.user_id,
                "device_id": self.config.device_id
            })
            
            logger.info(f"Connected to sync server: {self.config.server_url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self._emit('on_error', e)
            return False
    
    async def disconnect(self):
        """断开连接"""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("Disconnected from sync server")
    
    async def _send(self, data: Dict[str, Any]):
        """发送消息"""
        if self._ws:
            await self._ws.send(json.dumps(data, ensure_ascii=False))
    
    async def _recv(self) -> Optional[Dict[str, Any]]:
        """接收消息"""
        if self._ws:
            try:
                msg = await asyncio.wait_for(
                    self._ws.recv(),
                    timeout=self.config.timeout
                )
                return json.loads(msg)
            except asyncio.TimeoutError:
                return None
        return None
    
    # ── 同步操作 ──────────────────────────────────────────────────────────────
    
    def add_pending(self, record: SyncRecord):
        """添加待同步记录"""
        with self._lock:
            record.status = SyncStatus.PENDING
            record.updated_at = datetime.now()
            record.compute_checksum()
            self._pending_local[record.id] = record
            self._pending_queue.put(record)
    
    async def sync_now(self) -> SyncStatistics:
        """立即同步"""
        start_time = datetime.now()
        
        try:
            self._emit('on_status_change', SyncStatus.SYNCING, "Starting sync...")
            
            # 获取待同步记录
            pending = list(self._pending_local.values())
            
            if not pending:
                logger.info("No pending records to sync")
                self._statistics.last_sync_at = datetime.now()
                return self._statistics
            
            # 分批同步
            for i in range(0, len(pending), self.config.batch_size):
                batch = pending[i:i + self.config.batch_size]
                await self._sync_batch(batch)
            
            # 获取远程更新
            await self._fetch_remote_updates()
            
            self._statistics.last_sync_at = datetime.now()
            self._emit('on_sync', self._statistics)
            
        except Exception as e:
            logger.error(f"Sync error: {e}")
            self._statistics.total_failed += 1
            self._emit('on_error', e)
        
        finally:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self._statistics.sync_duration_ms = duration
        
        return self._statistics
    
    async def _sync_batch(self, records: List[SyncRecord]):
        """同步一批记录"""
        # 发送同步请求
        await self._send({
            "type": "sync_batch",
            "records": [r.to_dict() for r in records]
        })
        
        # 等待响应
        response = await self._recv()
        
        if response and response.get('type') == 'sync_response':
            for result in response.get('results', []):
                record_id = result['id']
                status = result['status']
                
                if record_id in self._pending_local:
                    local_record = self._pending_local[record_id]
                    
                    if status == 'synced':
                        local_record.status = SyncStatus.SYNCED
                        local_record.synced_at = datetime.now()
                        self._statistics.total_synced += 1
                    elif status == 'conflict':
                        local_record.status = SyncStatus.CONFLICT
                        local_record.conflict_data = result.get('remote_data')
                        self._statistics.total_conflicts += 1
                        
                        # 触发冲突回调
                        conflict = SyncConflict(
                            record_id=record_id,
                            local_data=local_record.content,
                            remote_data=result.get('remote_data', {}),
                            local_version=local_record.version,
                            remote_version=result.get('version', 1),
                            local_updated_at=local_record.updated_at,
                            remote_updated_at=datetime.fromisoformat(
                                result.get('updated_at', datetime.now().isoformat())
                            )
                        )
                        self._emit('on_conflict', conflict)
                    elif status == 'failed':
                        local_record.status = SyncStatus.FAILED
                        self._statistics.total_failed += 1
    
    async def _fetch_remote_updates(self):
        """获取远程更新"""
        await self._send({
            "type": "fetch_updates",
            "last_sync": self._statistics.last_sync_at.isoformat() if self._statistics.last_sync_at else None
        })
        
        response = await self._recv()
        
        if response and response.get('type') == 'updates':
            for record_data in response.get('records', []):
                record = SyncRecord.from_dict(record_data)
                
                # 检查本地是否已有
                if record.id in self._pending_local:
                    local = self._pending_local[record.id]
                    if local.updated_at > record.updated_at:
                        # 本地更新，跳过
                        continue
                
                # 更新本地
                self._local_db[record.id] = record
                logger.debug(f"Fetched remote update: {record.id}")
    
    # ── 冲突解决 ──────────────────────────────────────────────────────────────
    
    async def resolve_conflict(
        self,
        record_id: str,
        strategy: ConflictStrategy,
        user_choice: Optional[Dict] = None
    ):
        """解决冲突"""
        if record_id not in self._local_db:
            return
        
        record = self._local_db[record_id]
        
        if strategy == ConflictStrategy.LAST_WRITE_WINS:
            # 比较时间戳
            if record.conflict_data:
                local_time = record.updated_at
                remote_time = datetime.fromisoformat(
                    record.conflict_data.get('updated_at', datetime.now().isoformat())
                )
                
                if remote_time > local_time:
                    # 使用远程
                    record.content = record.conflict_data.get('content', {})
                # 否则保持本地
        
        elif strategy == ConflictStrategy.MERGE:
            # 合并策略（简单实现）
            if record.conflict_data:
                local_content = record.content
                remote_content = record.conflict_data.get('content', {})
                record.content = {**local_content, **remote_content}
        
        elif strategy == ConflictStrategy.USER_CHOICE and user_choice:
            record.content = user_choice
        
        # 重新同步
        record.status = SyncStatus.PENDING
        record.version += 1
        self.add_pending(record)
        await self.sync_now()
    
    # ── 后台同步 ──────────────────────────────────────────────────────────────
    
    def start_background_sync(self):
        """启动后台同步"""
        if self._running:
            return
        
        self._running = True
        self._sync_thread = threading.Thread(
            target=self._background_sync_loop,
            daemon=True
        )
        self._sync_thread.start()
        logger.info("Background sync started")
    
    def stop_background_sync(self):
        """停止后台同步"""
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
        logger.info("Background sync stopped")
    
    def _background_sync_loop(self):
        """后台同步循环"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self._running:
            try:
                loop.run_until_complete(self.connect())
                
                while self._running:
                    loop.run_until_complete(self.sync_now())
                    loop.run_until_complete(asyncio.sleep(self.config.sync_interval))
                    
            except Exception as e:
                logger.error(f"Background sync error: {e}")
                loop.run_until_complete(asyncio.sleep(self.config.retry_delay))
            
            finally:
                try:
                    loop.run_until_complete(self.disconnect())
                except:
                    pass
    
    # ── 状态查询 ──────────────────────────────────────────────────────────────
    
    def get_statistics(self) -> SyncStatistics:
        """获取同步统计"""
        return self._statistics
    
    def get_pending_count(self) -> int:
        """获取待同步数量"""
        with self._lock:
            return len(self._pending_local)
    
    def get_local_record(self, record_id: str) -> Optional[SyncRecord]:
        """获取本地记录"""
        return self._local_db.get(record_id)
    
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._ws is not None


# ── 全局实例 ──────────────────────────────────────────────────────────────────

_sync_client: Optional[SyncClient] = None
_config: Optional[SyncConfig] = None


def get_sync_client(config: Optional[SyncConfig] = None) -> SyncClient:
    """获取同步客户端单例"""
    global _sync_client, _config
    
    if _sync_client is None or config is not None:
        _config = config or SyncConfig()
        _sync_client = SyncClient(_config)
    
    return _sync_client


def init_sync_client(
    server_url: str,
    user_id: str,
    device_id: str,
    api_key: str = ""
) -> SyncClient:
    """初始化同步客户端"""
    config = SyncConfig(
        server_url=server_url,
        user_id=user_id,
        device_id=device_id,
        api_key=api_key
    )
    return get_sync_client(config)
