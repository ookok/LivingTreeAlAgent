"""
知识库同步引擎

实现分布式知识库的增量同步、冲突检测与解决
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .models import (
    KnowledgeItem, SyncOperation, SyncConflict, SyncStatus,
    SyncState, Message, CHUNK_SIZE
)

logger = logging.getLogger(__name__)


class KnowledgeDatabase:
    """知识库本地数据库"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # 创建表
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_items (
                item_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                content TEXT,
                content_type TEXT DEFAULT 'text',
                tags TEXT,
                created_at REAL,
                updated_at REAL,
                version INTEGER DEFAULT 1,
                checksum TEXT,
                size INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0,
                synced INTEGER DEFAULT 0
            );
            
            CREATE INDEX IF NOT EXISTS idx_user_id ON knowledge_items(user_id);
            CREATE INDEX IF NOT EXISTS idx_updated ON knowledge_items(updated_at);
            
            CREATE TABLE IF NOT EXISTS sync_operations (
                op_id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                op_type TEXT NOT NULL,
                timestamp REAL,
                version INTEGER,
                checksum TEXT,
                payload TEXT,
                source_node TEXT,
                applied INTEGER DEFAULT 0
            );
            
            CREATE INDEX IF NOT EXISTS idx_item_ops ON sync_operations(item_id, timestamp);
            
            CREATE TABLE IF NOT EXISTS sync_state (
                user_id TEXT PRIMARY KEY,
                last_sync REAL,
                status INTEGER,
                pending_ops INTEGER DEFAULT 0,
                synced_items INTEGER DEFAULT 0,
                conflicts INTEGER DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                created_at REAL,
                retries INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()
    
    def close(self):
        """关闭数据库"""
        if self.conn:
            self.conn.close()
    
    # 知识库操作
    def save_item(self, item: KnowledgeItem) -> bool:
        """保存知识条目"""
        try:
            self.conn.execute("""
                INSERT OR REPLACE INTO knowledge_items 
                (item_id, user_id, title, content, content_type, tags, 
                 created_at, updated_at, version, checksum, size, is_deleted, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                item.item_id, item.user_id, item.title, item.content,
                item.content_type, json.dumps(item.tags), item.created_at,
                item.updated_at, item.version, item.checksum, item.size, 
                1 if item.is_deleted else 0
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Save item failed: {e}")
            return False
    
    def get_item(self, item_id: str) -> Optional[KnowledgeItem]:
        """获取知识条目"""
        row = self.conn.execute(
            "SELECT * FROM knowledge_items WHERE item_id = ?", (item_id,)
        ).fetchone()
        
        if not row:
            return None
        
        return self._row_to_item(row)
    
    def get_items_by_user(self, user_id: str, include_deleted: bool = False) -> list[KnowledgeItem]:
        """获取用户的所有条目"""
        query = "SELECT * FROM knowledge_items WHERE user_id = ?"
        if not include_deleted:
            query += " AND is_deleted = 0"
        
        rows = self.conn.execute(query, (user_id,)).fetchall()
        return [self._row_to_item(r) for r in rows]
    
    def delete_item(self, item_id: str):
        """标记删除条目"""
        self.conn.execute(
            "UPDATE knowledge_items SET is_deleted = 1, updated_at = ?, synced = 0 WHERE item_id = ?",
            (time.time(), item_id)
        )
        self.conn.commit()
    
    def get_unsynced_items(self, user_id: str) -> list[KnowledgeItem]:
        """获取未同步的条目"""
        rows = self.conn.execute(
            "SELECT * FROM knowledge_items WHERE user_id = ? AND synced = 0",
            (user_id,)
        ).fetchall()
        return [self._row_to_item(r) for r in rows]
    
    def mark_synced(self, item_ids: list[str]):
        """标记已同步"""
        placeholders = ','.join(['?'] * len(item_ids))
        self.conn.execute(
            f"UPDATE knowledge_items SET synced = 1 WHERE item_id IN ({placeholders})",
            item_ids
        )
        self.conn.commit()
    
    def _row_to_item(self, row: sqlite3.Row) -> KnowledgeItem:
        """行转知识条目"""
        return KnowledgeItem(
            item_id=row['item_id'],
            user_id=row['user_id'],
            title=row['title'] or '',
            content=row['content'] or '',
            content_type=row['content_type'] or 'text',
            tags=json.loads(row['tags'] or '[]'),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            version=row['version'],
            checksum=row['checksum'],
            size=row['size'],
            is_deleted=bool(row['is_deleted'])
        )
    
    # 同步操作
    def save_operation(self, op: SyncOperation) -> bool:
        """保存同步操作"""
        try:
            self.conn.execute("""
                INSERT OR REPLACE INTO sync_operations 
                (op_id, item_id, user_id, op_type, timestamp, version, checksum, payload, source_node, applied)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                op.op_id, op.item_id, op.user_id, op.op_type,
                op.timestamp, op.version, op.checksum,
                json.dumps(op.payload) if op.payload else None, op.source_node
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Save operation failed: {e}")
            return False
    
    def get_operations_since(self, timestamp: float, user_id: str) -> list[SyncOperation]:
        """获取指定时间后的操作"""
        rows = self.conn.execute("""
            SELECT * FROM sync_operations 
            WHERE timestamp > ? AND user_id = ?
            ORDER BY timestamp
        """, (timestamp, user_id)).fetchall()
        
        return [self._row_to_op(r) for r in rows]
    
    def mark_operation_applied(self, op_id: str):
        """标记操作已应用"""
        self.conn.execute(
            "UPDATE sync_operations SET applied = 1 WHERE op_id = ?",
            (op_id,)
        )
        self.conn.commit()
    
    def _row_to_op(self, row: sqlite3.Row) -> SyncOperation:
        """行转同步操作"""
        return SyncOperation(
            op_id=row['op_id'],
            item_id=row['item_id'],
            user_id=row['user_id'],
            op_type=row['op_type'],
            timestamp=row['timestamp'],
            version=row['version'],
            checksum=row['checksum'],
            payload=json.loads(row['payload']) if row['payload'] else None,
            source_node=row['source_node']
        )
    
    # 同步状态
    def get_sync_state(self, user_id: str) -> Optional[SyncState]:
        """获取同步状态"""
        row = self.conn.execute(
            "SELECT * FROM sync_state WHERE user_id = ?", (user_id,)
        ).fetchone()
        
        if not row:
            return None
        
        return SyncState(
            user_id=row['user_id'],
            last_sync=row['last_sync'],
            status=SyncStatus(row['status']),
            pending_ops=row['pending_ops'],
            synced_items=row['synced_items'],
            conflicts=row['conflicts']
        )
    
    def update_sync_state(self, state: SyncState):
        """更新同步状态"""
        self.conn.execute("""
            INSERT OR REPLACE INTO sync_state 
            (user_id, last_sync, status, pending_ops, synced_items, conflicts)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            state.user_id, state.last_sync, state.status.value,
            state.pending_ops, state.synced_items, state.conflicts
        ))
        self.conn.commit()


class KnowledgeSync:
    """知识库同步引擎"""
    
    def __init__(
        self,
        user_id: str,
        db_path: str,
        chunk_size: int = CHUNK_SIZE
    ):
        self.user_id = user_id
        self.db = KnowledgeDatabase(db_path)
        self.chunk_size = chunk_size
        
        # 同步状态
        self.state = self.db.get_sync_state(user_id) or SyncState(user_id=user_id)
        self.running = False
        self._sync_task: Optional[asyncio.Task] = None
        
        # 冲突解决
        self.conflict_resolver = ConflictResolver()
        
        # P2P消息处理
        self._pending_sync: dict[str, asyncio.Future] = {}
    
    async def start(self):
        """启动同步引擎"""
        self.running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info(f"Knowledge sync engine started for user {self.user_id}")
    
    async def stop(self):
        """停止同步引擎"""
        self.running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        self.db.close()
        logger.info(f"Knowledge sync engine stopped for user {self.user_id}")
    
    async def _sync_loop(self):
        """同步循环"""
        while self.running:
            try:
                await asyncio.sleep(30)  # 每30秒同步一次
                await self._perform_sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
    
    async def _perform_sync(self):
        """执行同步"""
        self.state.status = SyncStatus.SYNCING
        
        try:
            # 1. 收集本地未同步的操作
            unsynced = self.db.get_unsynced_items(self.user_id)
            pending_ops = []
            
            for item in unsynced:
                op = SyncOperation(
                    item_id=item.item_id,
                    user_id=self.user_id,
                    op_type="delete" if item.is_deleted else ("create" if item.version == 1 else "update"),
                    version=item.version,
                    checksum=item.compute_checksum()
                )
                self.db.save_operation(op)
                pending_ops.append(op)
            
            self.state.pending_ops = len(pending_ops)
            
            # 2. 获取远程操作
            remote_ops = await self._fetch_remote_operations()
            
            # 3. 合并和冲突检测
            merged_ops = self._merge_operations(pending_ops, remote_ops)
            
            # 4. 应用远程操作
            conflicts = await self._apply_remote_operations(merged_ops)
            
            # 5. 广播本地操作
            await self._broadcast_local_operations(pending_ops)
            
            # 6. 更新状态
            self.state.last_sync = time.time()
            self.state.status = SyncStatus.COMPLETED if not conflicts else SyncStatus.CONFLICT
            self.state.conflicts = len(conflicts)
            self.state.synced_items = len(pending_ops)
            self.db.update_sync_state(self.state)
            
            logger.info(f"Sync completed: {len(pending_ops)} items, {len(conflicts)} conflicts")
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            self.state.status = SyncStatus.FAILED
            self.state.error_message = str(e)
            self.db.update_sync_state(self.state)
    
    async def _fetch_remote_operations(self) -> list[SyncOperation]:
        """从远程获取操作（需要P2P网络支持）"""
        # 这里需要调用P2P网络获取其他节点的更新
        # 返回空列表表示没有远程操作
        return []
    
    def _merge_operations(
        self,
        local_ops: list[SyncOperation],
        remote_ops: list[SyncOperation]
    ) -> list[SyncOperation]:
        """合并本地和远程操作"""
        all_ops = local_ops + remote_ops
        
        # 按时间戳排序
        all_ops.sort(key=lambda x: x.timestamp)
        
        # 去重：保留每个item_id的最新操作
        latest_ops = {}
        for op in all_ops:
            if op.item_id not in latest_ops or op.timestamp > latest_ops[op.item_id].timestamp:
                latest_ops[op.item_id] = op
        
        return list(latest_ops.values())
    
    async def _apply_remote_operations(
        self,
        operations: list[SyncOperation]
    ) -> list[SyncConflict]:
        """应用远程操作"""
        conflicts = []
        
        for op in operations:
            if op.source_node == self.user_id:
                continue  # 跳过自己的操作
            
            local_item = self.db.get_item(op.item_id)
            
            if op.op_type == "delete":
                if local_item and not local_item.is_deleted:
                    self.db.delete_item(op.item_id)
            
            elif op.op_type == "create" or op.op_type == "update":
                if local_item:
                    # 检测冲突
                    if local_item.checksum != op.checksum and local_item.updated_at > op.timestamp - 1:
                        conflict = SyncConflict(
                            item_id=op.item_id,
                            local_version=local_item,
                            remote_version=self._op_to_item(op),
                            conflict_type="content"
                        )
                        conflicts.append(conflict)
                        continue
                
                # 应用远程更新
                item = self._op_to_item(op)
                self.db.save_item(item)
        
        return conflicts
    
    async def _broadcast_local_operations(self, operations: list[SyncOperation]):
        """广播本地操作到P2P网络"""
        for op in operations:
            msg = Message(
                msg_type="sync_operation",
                source_id=self.user_id,
                payload=op.to_dict()
            )
            # 实际需要发送到P2P网络
            logger.debug(f"Broadcasting operation: {op.op_id}")
    
    def _op_to_item(self, op: SyncOperation) -> KnowledgeItem:
        """操作转知识条目"""
        payload = op.payload or {}
        return KnowledgeItem(
            item_id=op.item_id,
            user_id=op.user_id,
            title=payload.get("title", ""),
            content=payload.get("content", ""),
            content_type=payload.get("content_type", "text"),
            tags=payload.get("tags", []),
            updated_at=op.timestamp,
            version=op.version,
            checksum=op.checksum
        )
    
    # 公共API
    async def add_item(self, item: KnowledgeItem) -> bool:
        """添加知识条目"""
        item.user_id = self.user_id
        item.compute_checksum()
        
        if self.db.save_item(item):
            # 创建同步操作
            op = SyncOperation(
                item_id=item.item_id,
                user_id=self.user_id,
                op_type="create",
                version=item.version,
                checksum=item.checksum,
                payload=item.to_dict()
            )
            self.db.save_operation(op)
            return True
        
        return False
    
    async def update_item(self, item: KnowledgeItem) -> bool:
        """更新知识条目"""
        item.user_id = self.user_id
        item.version += 1
        item.updated_at = time.time()
        item.compute_checksum()
        
        if self.db.save_item(item):
            op = SyncOperation(
                item_id=item.item_id,
                user_id=self.user_id,
                op_type="update",
                version=item.version,
                checksum=item.checksum,
                payload=item.to_dict()
            )
            self.db.save_operation(op)
            return True
        
        return False
    
    async def delete_item(self, item_id: str) -> bool:
        """删除知识条目"""
        self.db.delete_item(item_id)
        
        op = SyncOperation(
            item_id=item_id,
            user_id=self.user_id,
            op_type="delete"
        )
        self.db.save_operation(op)
        return True
    
    def get_items(self, include_deleted: bool = False) -> list[KnowledgeItem]:
        """获取所有知识条目"""
        return self.db.get_items_by_user(self.user_id, include_deleted)
    
    def get_item(self, item_id: str) -> Optional[KnowledgeItem]:
        """获取单个条目"""
        return self.db.get_item(item_id)
    
    async def force_sync(self):
        """强制同步"""
        await self._perform_sync()
    
    def get_status(self) -> SyncState:
        """获取同步状态"""
        return self.state
    
    async def resolve_conflict(self, item_id: str, resolution: str) -> bool:
        """解决冲突"""
        # resolution: "keep_local", "keep_remote", "merge"
        # 这里简化处理，实际需要更复杂的合并逻辑
        return True


class ConflictResolver:
    """冲突解决器"""
    
    def resolve_text_conflict(self, local: str, remote: str, strategy: str = "merge") -> str:
        """
        解决文本冲突
        strategy: keep_local, keep_remote, merge, latest
        """
        if strategy == "keep_local":
            return local
        elif strategy == "keep_remote":
            return remote
        elif strategy == "latest":
            return remote if len(remote) > len(local) else local
        else:  # merge
            # 简单的行级别合并
            local_lines = set(local.splitlines())
            remote_lines = set(remote.splitlines())
            merged = local_lines | remote_lines
            return "\n".join(sorted(merged))
    
    def resolve_delete_conflict(self, local_deleted: bool, remote_deleted: bool) -> bool:
        """解决删除冲突：两边都删了就是删了"""
        return local_deleted and remote_deleted


class SelectiveSync:
    """选择性同步"""
    
    def __init__(self):
        self.include_patterns: list[str] = []  # 包含模式
        self.exclude_patterns: list[str] = []  # 排除模式
        self.file_type_filters: list[str] = []  # 文件类型过滤
    
    def should_sync(self, item: KnowledgeItem) -> bool:
        """判断是否应该同步"""
        # 检查排除模式
        for pattern in self.exclude_patterns:
            if pattern in item.title or pattern in item.content:
                return False
        
        # 检查包含模式
        if self.include_patterns:
            for pattern in self.include_patterns:
                if pattern in item.title or pattern in item.content:
                    return True
            return False
        
        # 检查文件类型
        if self.file_type_filters and item.content_type == "file":
            return item.file_path and any(
                item.file_path.endswith(ext) for ext in self.file_type_filters
            )
        
        return True
    
    def set_include_patterns(self, patterns: list[str]):
        """设置包含模式"""
        self.include_patterns = patterns
    
    def set_exclude_patterns(self, patterns: list[str]):
        """设置排除模式"""
        self.exclude_patterns = patterns
