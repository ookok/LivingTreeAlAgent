"""
腾讯云知识库同步引擎
Tencent Cloud Knowledge Base Sync Engine
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class SyncDirection(Enum):
    """同步方向"""
    TO_CLOUD = "to_cloud"
    FROM_CLOUD = "from_cloud"
    BIDIRECTIONAL = "bidirectional"


class ConflictStrategy(Enum):
    """冲突解决策略"""
    NEWER_WINS = "newer_wins"
    LOCAL_WINS = "local_wins"
    CLOUD_WINS = "cloud_wins"
    KEEP_BOTH = "keep_both"
    MANUAL = "manual"


@dataclass
class TencentSyncConfig:
    """腾讯云同步配置"""
    enabled: bool = False
    secret_id: str = ""
    secret_key: str = ""
    region: str = "ap-guangzhou"
    knowledge_base_id: str = ""
    
    # 同步设置
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    conflict_strategy: ConflictStrategy = ConflictStrategy.NEWER_WINS
    sync_interval: int = 300  # 秒
    
    # 选择性同步
    sync_tags: List[str] = field(default_factory=list)  # 空表示全部
    exclude_tags: List[str] = field(default_factory=list)
    
    # 加密
    encrypt_data: bool = True


@dataclass
class SyncEntry:
    """同步条目"""
    entry_id: str
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    
    # 版本信息
    local_version: int = 1
    cloud_version: int = 0
    local_updated: datetime = field(default_factory=datetime.now)
    cloud_updated: Optional[datetime] = None
    
    # 同步状态
    needs_sync: bool = False
    sync_status: str = "synced"  # synced, pending, conflict, error
    last_sync: Optional[datetime] = None
    
    # 元数据
    checksum: Optional[str] = None


@dataclass
class SyncResult:
    """同步结果"""
    success: bool
    direction: SyncDirection
    uploaded: int = 0
    downloaded: int = 0
    conflicts: int = 0
    errors: int = 0
    message: str = ""


class TencentSyncEngine:
    """
    腾讯云知识库同步引擎
    
    功能：
    - 双向增量同步
    - 冲突检测与解决
    - 选择性同步
    - 加密传输
    """
    
    def __init__(self, config: TencentSyncConfig, knowledge_base):
        self.config = config
        self.knowledge_base = knowledge_base
        
        # 存储
        self._storage_path = Path.home() / ".hermes-desktop" / "tencent_sync"
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        # 同步状态
        self._local_entries: Dict[str, SyncEntry] = {}
        self._sync_state_file = self._storage_path / "sync_state.json"
        self._load_sync_state()
        
        # 状态
        self._running = False
        self._syncing = False
        self._last_sync: Optional[datetime] = None
        
        # 锁
        self._lock = asyncio.Lock()
        
        logger.info("腾讯云同步引擎初始化完成")
    
    def _load_sync_state(self) -> None:
        """加载同步状态"""
        if self._sync_state_file.exists():
            try:
                with open(self._sync_state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for entry_data in data.get('entries', []):
                    entry = SyncEntry(
                        entry_id=entry_data['entry_id'],
                        title=entry_data['title'],
                        content=entry_data['content'],
                        tags=entry_data.get('tags', []),
                        local_version=entry_data.get('local_version', 1),
                        cloud_version=entry_data.get('cloud_version', 0),
                        local_updated=datetime.fromisoformat(entry_data['local_updated']),
                        cloud_updated=datetime.fromisoformat(entry_data['cloud_updated']) if entry_data.get('cloud_updated') else None,
                        needs_sync=entry_data.get('needs_sync', False),
                        sync_status=entry_data.get('sync_status', 'synced'),
                        last_sync=datetime.fromisoformat(entry_data['last_sync']) if entry_data.get('last_sync') else None,
                        checksum=entry_data.get('checksum')
                    )
                    self._local_entries[entry.entry_id] = entry
                
                if data.get('last_sync'):
                    self._last_sync = datetime.fromisoformat(data['last_sync'])
                
                logger.info(f"加载了 {len(self._local_entries)} 个同步条目")
                
            except Exception as e:
                logger.error(f"加载同步状态失败: {e}")
    
    def _save_sync_state(self) -> None:
        """保存同步状态"""
        try:
            data = {
                'last_sync': self._last_sync.isoformat() if self._last_sync else None,
                'entries': [
                    {
                        'entry_id': e.entry_id,
                        'title': e.title,
                        'content': e.content,
                        'tags': e.tags,
                        'local_version': e.local_version,
                        'cloud_version': e.cloud_version,
                        'local_updated': e.local_updated.isoformat(),
                        'cloud_updated': e.cloud_updated.isoformat() if e.cloud_updated else None,
                        'needs_sync': e.needs_sync,
                        'sync_status': e.sync_status,
                        'last_sync': e.last_sync.isoformat() if e.last_sync else None,
                        'checksum': e.checksum
                    }
                    for e in self._local_entries.values()
                ]
            }
            
            with open(self._sync_state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存同步状态失败: {e}")
    
    def _compute_checksum(self, content: str) -> str:
        """计算内容校验和"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    async def start(self) -> None:
        """启动同步引擎"""
        if self._running:
            return
        
        self._running = True
        
        # 启动定时同步
        asyncio.create_task(self._sync_timer())
        
        logger.info("腾讯云同步引擎已启动")
    
    async def stop(self) -> None:
        """停止同步引擎"""
        self._running = False
        self._save_sync_state()
        logger.info("腾讯云同步引擎已停止")
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    async def _sync_timer(self) -> None:
        """定时同步"""
        while self._running:
            try:
                await asyncio.sleep(self.config.sync_interval)
                
                if not self._syncing and self._running:
                    await self.sync_bidirectional()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"定时同步错误: {e}")
    
    async def add_entry(self, entry_id: str, title: str, content: str,
                       tags: Optional[List[str]] = None) -> SyncEntry:
        """
        添加同步条目
        
        Args:
            entry_id: 条目ID
            title: 标题
            content: 内容
            tags: 标签
        
        Returns:
            SyncEntry: 创建的条目
        """
        async with self._lock:
            entry = SyncEntry(
                entry_id=entry_id,
                title=title,
                content=content,
                tags=tags or [],
                needs_sync=True,
                sync_status='pending',
                checksum=self._compute_checksum(content)
            )
            
            self._local_entries[entry_id] = entry
            self._save_sync_state()
            
            return entry
    
    async def update_entry(self, entry_id: str, title: str, content: str,
                          tags: Optional[List[str]] = None) -> bool:
        """
        更新同步条目
        
        Args:
            entry_id: 条目ID
            title: 标题
            content: 内容
            tags: 标签
        
        Returns:
            bool: 是否成功
        """
        async with self._lock:
            entry = self._local_entries.get(entry_id)
            if not entry:
                return False
            
            entry.title = title
            entry.content = content
            if tags is not None:
                entry.tags = tags
            
            entry.local_version += 1
            entry.local_updated = datetime.now()
            entry.needs_sync = True
            entry.sync_status = 'pending'
            entry.checksum = self._compute_checksum(content)
            
            self._save_sync_state()
            return True
    
    async def delete_entry(self, entry_id: str) -> bool:
        """
        删除同步条目
        
        Args:
            entry_id: 条目ID
        
        Returns:
            bool: 是否成功
        """
        async with self._lock:
            if entry_id in self._local_entries:
                del self._local_entries[entry_id]
                self._save_sync_state()
                return True
            return False
    
    async def sync_to_cloud(self) -> SyncResult:
        """
        同步到云端
        
        Returns:
            SyncResult: 同步结果
        """
        if self._syncing:
            return SyncResult(False, SyncDirection.TO_CLOUD, message="同步进行中")
        
        self._syncing = True
        result = SyncResult(False, SyncDirection.TO_CLOUD)
        
        try:
            # 获取需要上传的条目
            to_upload = [e for e in self._local_entries.values()
                        if e.needs_sync and e.sync_status != 'synced']
            
            if not to_upload:
                result.success = True
                result.message = "没有需要上传的内容"
                return result
            
            # TODO: 调用腾讯云API上传
            # 这里模拟上传过程
            for entry in to_upload:
                try:
                    # 模拟API调用
                    await asyncio.sleep(0.1)
                    
                    # 更新状态
                    entry.cloud_version = entry.local_version
                    entry.cloud_updated = datetime.now()
                    entry.needs_sync = False
                    entry.sync_status = 'synced'
                    entry.last_sync = datetime.now()
                    
                    result.uploaded += 1
                    
                except Exception as e:
                    logger.error(f"上传条目失败 {entry.entry_id}: {e}")
                    entry.sync_status = 'error'
                    result.errors += 1
            
            self._last_sync = datetime.now()
            self._save_sync_state()
            
            result.success = result.errors == 0
            result.message = f"上传完成: {result.uploaded} 成功, {result.errors} 失败"
            
        finally:
            self._syncing = False
        
        return result
    
    async def sync_from_cloud(self) -> SyncResult:
        """
        从云端同步
        
        Returns:
            SyncResult: 同步结果
        """
        if self._syncing:
            return SyncResult(False, SyncDirection.FROM_CLOUD, message="同步进行中")
        
        self._syncing = True
        result = SyncResult(False, SyncDirection.FROM_CLOUD)
        
        try:
            # TODO: 调用腾讯云API获取更新
            # 这里模拟获取过程
            cloud_entries = []
            
            for entry in cloud_entries:
                local = self._local_entries.get(entry['entry_id'])
                
                if not local:
                    # 云端新增
                    new_entry = SyncEntry(
                        entry_id=entry['entry_id'],
                        title=entry['title'],
                        content=entry['content'],
                        tags=entry.get('tags', []),
                        cloud_version=entry.get('version', 1),
                        cloud_updated=datetime.now(),
                        sync_status='synced'
                    )
                    self._local_entries[new_entry.entry_id] = new_entry
                    result.downloaded += 1
                    
                else:
                    # 检查冲突
                    if entry.get('version', 0) > local.cloud_version:
                        conflict = await self._resolve_conflict(local, entry)
                        
                        if conflict == 'download':
                            local.title = entry['title']
                            local.content = entry['content']
                            local.cloud_version = entry.get('version', 1)
                            local.cloud_updated = datetime.now()
                            result.downloaded += 1
                        elif conflict == 'upload':
                            result.uploaded += 1
                        elif conflict == 'both':
                            result.downloaded += 1
                            result.conflicts += 1
            
            self._last_sync = datetime.now()
            self._save_sync_state()
            
            result.success = True
            result.message = f"下载完成: {result.downloaded} 条"
            
        finally:
            self._syncing = False
        
        return result
    
    async def _resolve_conflict(self, local: SyncEntry, 
                                cloud: Dict[str, Any]) -> str:
        """
        解决冲突
        
        Returns:
            str: 'download', 'upload', 'both', 或 'skip'
        """
        if self.config.conflict_strategy == ConflictStrategy.LOCAL_WINS:
            return 'skip'
        
        elif self.config.conflict_strategy == ConflictStrategy.CLOUD_WINS:
            return 'download'
        
        elif self.config.conflict_strategy == ConflictStrategy.NEWER_WINS:
            local_time = local.local_updated.timestamp()
            cloud_time = datetime.fromisoformat(cloud.get('updated', '')).timestamp()
            
            if cloud_time > local_time:
                return 'download'
            else:
                return 'skip'
        
        elif self.config.conflict_strategy == ConflictStrategy.KEEP_BOTH:
            # 创建冲突副本
            conflict_entry = SyncEntry(
                entry_id=f"{local.entry_id}_conflict_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                title=f"[冲突] {local.title}",
                content=local.content,
                tags=local.tags,
                sync_status='conflict'
            )
            self._local_entries[conflict_entry.entry_id] = conflict_entry
            return 'both'
        
        else:  # MANUAL
            local.sync_status = 'conflict'
            return 'skip'
    
    async def sync_bidirectional(self) -> SyncResult:
        """
        双向同步
        
        Returns:
            SyncResult: 同步结果
        """
        result = SyncResult(False, SyncDirection.BIDIRECTIONAL)
        
        # 先上传
        upload_result = await self.sync_to_cloud()
        result.uploaded = upload_result.uploaded
        result.errors = upload_result.errors
        
        # 再下载
        download_result = await self.sync_from_cloud()
        result.downloaded = download_result.downloaded
        result.conflicts = download_result.conflicts
        
        result.success = result.errors == 0
        result.message = f"双向同步完成: 上传 {result.uploaded}, 下载 {result.downloaded}, 冲突 {result.conflicts}"
        
        return result
    
    def get_pending_count(self) -> int:
        """获取待同步数量"""
        return sum(1 for e in self._local_entries.values() if e.needs_sync)
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        return {
            'running': self._running,
            'syncing': self._syncing,
            'last_sync': self._last_sync.isoformat() if self._last_sync else None,
            'total_entries': len(self._local_entries),
            'pending_count': self.get_pending_count(),
            'conflict_count': sum(1 for e in self._local_entries.values() 
                                  if e.sync_status == 'conflict'),
            'error_count': sum(1 for e in self._local_entries.values() 
                               if e.sync_status == 'error')
        }
