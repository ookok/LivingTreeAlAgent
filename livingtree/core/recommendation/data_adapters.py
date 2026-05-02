"""
数据适配器
将不同来源的数据转换为统一格式
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from .recall import RawItem
from .ranking import RankedItem, ContentType


@dataclass
class UnifiedItem:
    """
    统一数据格式
    所有来源的数据都转换为这个格式
    """
    id: str
    type: str                    # news/video/product
    title: str
    description: str
    url: str
    icon: str                    # 图片/emoji
    source: str                  # 来源
    publish_time: str            # 友好时间
    tags: list[str] = field(default_factory=list)
    
    # 额外信息
    extra: dict = field(default_factory=dict)
    
    @classmethod
    def from_ranked_item(cls, item: RankedItem) -> "UnifiedItem":
        """从排序项转换"""
        type_icon = {
            ContentType.NEWS: "📰",
            ContentType.VIDEO: "🎬",
            ContentType.PRODUCT: "🛒",
        }
        
        return cls(
            id=item.item_id,
            type=item.content_type.value,
            title=item.title,
            description=item.description,
            url=item.url,
            icon=item.image_url or type_icon.get(item.content_type, "📄"),
            source=item.source,
            publish_time=item.time_ago,
            tags=item.tags,
            extra={
                "score": item.score,
                "hot_score": item.hot_score,
            }
        )
    
    @classmethod
    def from_raw_item(cls, item: RawItem, content_type: str = "news") -> "UnifiedItem":
        """从原始项转换"""
        type_icon = {
            "news": "📰",
            "video": "🎬",
            "product": "🛒",
        }
        
        return cls(
            id=item.item_id,
            type=content_type,
            title=item.title,
            description=item.description,
            url=item.url,
            icon=item.image_url or type_icon.get(content_type, "📄"),
            source=item.source,
            publish_time=_format_time(item.publish_time),
            tags=item.tags,
        )


class NewsAdapter:
    """新闻数据适配器"""
    
    @staticmethod
    def adapt(raw_data: dict) -> Optional[UnifiedItem]:
        """适配新闻数据"""
        try:
            return UnifiedItem(
                id=str(raw_data.get("id", raw_data.get("news_id", ""))),
                type="news",
                title=raw_data.get("title", ""),
                description=raw_data.get("desc", raw_data.get("description", "")),
                url=raw_data.get("url", raw_data.get("link", "")),
                icon=raw_data.get("image", raw_data.get("thumbnail", "📰")),
                source=raw_data.get("source", "未知来源"),
                publish_time=raw_data.get("time", "刚刚"),
                tags=raw_data.get("tags", []),
            )
        except Exception:
            return None


class VideoAdapter:
    """视频数据适配器"""
    
    @staticmethod
    def adapt(raw_data: dict) -> Optional[UnifiedItem]:
        """适配视频数据"""
        try:
            return UnifiedItem(
                id=str(raw_data.get("id", raw_data.get("bvid", ""))),
                type="video",
                title=raw_data.get("title", ""),
                description=raw_data.get("desc", raw_data.get("description", "")),
                url=raw_data.get("url", f"https://bilibili.com/video/{raw_data.get('bvid', '')}"),
                icon=raw_data.get("pic", raw_data.get("cover", "🎬")),
                source=raw_data.get("source", raw_data.get("owner", {}).get("name", "B站")),
                publish_time=raw_data.get("ctime", "最近"),
                tags=raw_data.get("tags", []),
                extra={
                    "duration": raw_data.get("duration", ""),
                    "views": raw_data.get("stat", {}).get("view", 0),
                }
            )
        except Exception:
            return None


class ProductAdapter:
    """商品数据适配器"""
    
    @staticmethod
    def adapt(raw_data: dict) -> Optional[UnifiedItem]:
        """适配商品数据"""
        try:
            return UnifiedItem(
                id=str(raw_data.get("id", raw_data.get("item_id", ""))),
                type="product",
                title=raw_data.get("title", raw_data.get("name", "")),
                description=raw_data.get("desc", raw_data.get("description", "")),
                url=raw_data.get("url", raw_data.get("link", "")),
                icon=raw_data.get("image", raw_data.get("pic", "🛒")),
                source=raw_data.get("source", "电商"),
                publish_time=raw_data.get("update_time", "热卖中"),
                tags=raw_data.get("tags", []),
                extra={
                    "price": raw_data.get("price", ""),
                    "sales": raw_data.get("sales", ""),
                }
            )
        except Exception:
            return None


def _format_time(timestamp: float) -> str:
    """格式化时间戳"""
    import time
    now = time.time()
    diff = now - timestamp
    
    if diff < 60:
        return "刚刚"
    elif diff < 3600:
        return f"{int(diff / 60)}分钟前"
    elif diff < 86400:
        return f"{int(diff / 3600)}小时前"
    else:
        return f"{int(diff / 86400)}天前"


def adapt_items(ranked_items: list[RankedItem]) -> list[UnifiedItem]:
    """批量转换排序项为统一格式"""
    return [UnifiedItem.from_ranked_item(item) for item in ranked_items]
