"""
RealtimeTracker - 实时追踪器

实现"实时追踪"功能：
1. 添加"关注列表"（人物/公司/话题）
2. 定期爬取最新动态（使用 DeepSearch / WebCrawler）
3. 自动更新到 KnowledgeGraph / IntelligentMemory

参考 Rowboat 的实时追踪设计。
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime, timedelta
from enum import Enum
import asyncio


class TrackType(Enum):
    """追踪类型"""
    PERSON = "person"
    COMPANY = "company"
    TOPIC = "topic"
    KEYWORD = "keyword"


class TrackStatus(Enum):
    """追踪状态"""
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


@dataclass
class TrackItem:
    """追踪项"""
    item_id: str
    name: str
    track_type: TrackType
    query: str
    status: TrackStatus = TrackStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: Optional[datetime] = None
    update_interval: int = 3600  # 默认每小时更新一次
    sources: List[str] = field(default_factory=list)
    total_updates: int = 0


@dataclass
class TrackUpdate:
    """追踪更新"""
    update_id: str
    item_id: str
    title: str
    content: str
    url: str
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    relevance: float = 0.0


class RealtimeTracker:
    """
    实时追踪器
    
    核心功能：
    1. 管理关注列表
    2. 定期爬取最新动态
    3. 自动更新到知识库
    4. 支持多种追踪类型
    """

    def __init__(self):
        self._logger = logger.bind(component="RealtimeTracker")
        self._track_items: Dict[str, TrackItem] = {}
        self._updates: Dict[str, List[TrackUpdate]] = {}
        self._running = False
        self._scheduler_task = None
        self._update_interval = 60  # 检查间隔（秒）

    async def start(self):
        """启动追踪器"""
        if self._running:
            return
        
        self._running = True
        self._logger.info("启动实时追踪器")
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop(self):
        """停止追踪器"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
        self._logger.info("停止实时追踪器")

    async def _scheduler_loop(self):
        """调度循环"""
        while self._running:
            now = datetime.now()
            
            # 检查每个追踪项是否需要更新
            for item in self._track_items.values():
                if item.status != TrackStatus.ACTIVE:
                    continue
                
                # 检查是否需要更新
                if item.last_updated is None or (now - item.last_updated).total_seconds() >= item.update_interval:
                    await self._update_track_item(item)
            
            await asyncio.sleep(self._update_interval)

    async def _update_track_item(self, item: TrackItem):
        """更新追踪项"""
        self._logger.info(f"更新追踪项: {item.name}")
        
        try:
            # 执行搜索获取最新动态
            updates = await self._search_updates(item)
            
            # 处理更新
            for update in updates:
                await self._process_update(update)
            
            # 更新追踪项状态
            item.last_updated = datetime.now()
            item.total_updates += 1
            
            self._logger.info(f"追踪项 {item.name} 更新完成，新增 {len(updates)} 条动态")
            
        except Exception as e:
            self._logger.error(f"更新追踪项失败: {item.name}, 错误: {e}")

    async def _search_updates(self, item: TrackItem) -> List[TrackUpdate]:
        """搜索最新动态"""
        updates = []
        
        # 模拟搜索结果
        search_results = await self._simulate_search(item.query)
        
        for i, result in enumerate(search_results):
            update = TrackUpdate(
                update_id=f"update_{len(self._updates) + i}",
                item_id=item.item_id,
                title=result.get("title", ""),
                content=result.get("content", ""),
                url=result.get("url", ""),
                source=result.get("source", "unknown"),
                relevance=result.get("relevance", 0.0)
            )
            updates.append(update)
        
        return updates

    async def _simulate_search(self, query: str) -> List[Dict[str, Any]]:
        """模拟搜索"""
        # 模拟搜索延迟
        await asyncio.sleep(0.5)
        
        return [
            {
                "title": f"{query} 最新动态 1",
                "content": f"关于 {query} 的最新信息...",
                "url": f"https://example.com/{query}/1",
                "source": "DeepSearch",
                "relevance": 0.95
            },
            {
                "title": f"{query} 最新动态 2",
                "content": f"{query} 的最新进展...",
                "url": f"https://example.com/{query}/2",
                "source": "WebCrawler",
                "relevance": 0.88
            }
        ]

    async def _process_update(self, update: TrackUpdate):
        """处理更新"""
        # 添加到更新列表
        if update.item_id not in self._updates:
            self._updates[update.item_id] = []
        
        # 去重：检查是否已存在相同的 URL
        exists = any(u.url == update.url for u in self._updates[update.item_id])
        if not exists:
            self._updates[update.item_id].append(update)
            
            # 限制每个追踪项的更新数量
            if len(self._updates[update.item_id]) > 100:
                self._updates[update.item_id] = self._updates[update.item_id][-50:]

        # 更新到知识库（预留接口）
        await self._update_knowledge_base(update)

    async def _update_knowledge_base(self, update: TrackUpdate):
        """更新到知识库"""
        # 预留：更新 KnowledgeGraph 和 IntelligentMemory
        self._logger.debug(f"更新知识库: {update.title}")

    def add_track_item(
        self,
        item_id: str,
        name: str,
        track_type: TrackType,
        query: str,
        update_interval: int = 3600
    ) -> TrackItem:
        """
        添加追踪项
        
        Args:
            item_id: 追踪项 ID
            name: 名称
            track_type: 追踪类型
            query: 搜索查询词
            update_interval: 更新间隔（秒）
            
        Returns:
            TrackItem
        """
        if item_id in self._track_items:
            raise ValueError(f"追踪项已存在: {item_id}")

        item = TrackItem(
            item_id=item_id,
            name=name,
            track_type=track_type,
            query=query,
            update_interval=update_interval
        )

        self._track_items[item_id] = item
        self._logger.info(f"添加追踪项: {name}")
        return item

    def remove_track_item(self, item_id: str):
        """移除追踪项"""
        if item_id in self._track_items:
            del self._track_items[item_id]
            if item_id in self._updates:
                del self._updates[item_id]
            self._logger.info(f"移除追踪项: {item_id}")

    def pause_track_item(self, item_id: str):
        """暂停追踪项"""
        item = self._track_items.get(item_id)
        if item:
            item.status = TrackStatus.PAUSED
            self._logger.info(f"暂停追踪项: {item.name}")

    def resume_track_item(self, item_id: str):
        """恢复追踪项"""
        item = self._track_items.get(item_id)
        if item:
            item.status = TrackStatus.ACTIVE
            self._logger.info(f"恢复追踪项: {item.name}")

    def get_track_item(self, item_id: str) -> Optional[TrackItem]:
        """获取追踪项"""
        return self._track_items.get(item_id)

    def list_track_items(self, track_type: Optional[TrackType] = None) -> List[TrackItem]:
        """列出追踪项"""
        items = list(self._track_items.values())
        if track_type:
            items = [i for i in items if i.track_type == track_type]
        return items

    def get_updates(self, item_id: str) -> List[TrackUpdate]:
        """获取追踪项的更新"""
        return self._updates.get(item_id, [])

    def search_updates(self, keyword: str) -> List[TrackUpdate]:
        """搜索更新"""
        all_updates = []
        for updates in self._updates.values():
            for update in updates:
                if keyword.lower() in update.title.lower() or keyword.lower() in update.content.lower():
                    all_updates.append(update)
        
        # 按相关性排序
        all_updates.sort(key=lambda x: x.relevance, reverse=True)
        return all_updates

    def get_stats(self) -> Dict[str, Any]:
        """获取追踪器统计信息"""
        active_count = sum(1 for i in self._track_items.values() if i.status == TrackStatus.ACTIVE)
        total_updates = sum(len(u) for u in self._updates.values())
        
        return {
            "total_track_items": len(self._track_items),
            "active_track_items": active_count,
            "total_updates": total_updates,
            "running": self._running
        }