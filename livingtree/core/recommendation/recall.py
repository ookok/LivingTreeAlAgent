"""
召回引擎
负责从多数据源拉取候选内容
"""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Optional
from enum import Enum

import aiohttp

from .user_profile import UserProfile


class DataSource(Enum):
    """数据源枚举"""
    NEWS_HOT = "news_hot"           # 新闻热榜
    NEWS_TECH = "news_tech"         # 科技新闻
    NEWS_FINANCE = "news_finance"   # 财经新闻
    VIDEO_HOT = "video_hot"         # 视频热榜
    VIDEO_BILIBILI = "video_bilibili"  # B站视频
    PRODUCT_HOT = "product_hot"     # 商品热榜
    PRODUCT_TAOBAO = "product_taobao"   # 淘宝商品


@dataclass
class RawItem:
    """原始数据项"""
    source: str
    item_id: str
    title: str
    description: str = ""
    url: str = ""
    image_url: str = ""
    tags: list[str] = None
    hot_score: float = 0.0
    publish_time: float = 0.0
    raw_data: dict = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.raw_data is None:
            self.raw_data = {}


class RecallEngine:
    """
    召回引擎
    从多个数据源并行拉取内容
    """
    
    def __init__(self, profile_manager, config: dict = None):
        self.profile_manager = profile_manager
        self.config = config or {}
        
        # 数据源配置
        self.sources = {
            DataSource.NEWS_HOT: {
                "enabled": True,
                "weight": 0.3,
                "url": "https://api.vvhan.com/api/hotlist/j berita",  # 示例API
            },
            DataSource.NEWS_TECH: {
                "enabled": True,
                "weight": 0.3,
                "url": "https://api.vvhan.com/api/hotlist/jishisa",
            },
            DataSource.VIDEO_HOT: {
                "enabled": True,
                "weight": 0.2,
                "url": "",
            },
            DataSource.PRODUCT_HOT: {
                "enabled": True,
                "weight": 0.2,
                "url": "",
            },
        }
        
        # 缓存
        self._cache: dict[str, tuple[list[RawItem], float]] = {}
        self.cache_ttl = 300  # 5分钟缓存
    
    def _get_cache(self, source: DataSource) -> Optional[list[RawItem]]:
        """获取缓存数据"""
        key = source.value
        if key in self._cache:
            items, timestamp = self._cache[key]
            if time.time() - timestamp < self.cache_ttl:
                return items
        return None
    
    def _set_cache(self, source: DataSource, items: list[RawItem]):
        """设置缓存"""
        self._cache[source.value] = (items, time.time())
    
    async def recall_all(self, user_profile: UserProfile, limit_per_source: int = 20) -> list[RawItem]:
        """
        召回所有数据源的内容
        """
        profile = self.profile_manager.get_profile()
        tasks = []
        
        # 根据用户画像决定启用哪些数据源
        enabled_sources = self._get_enabled_sources(profile)
        
        for source in enabled_sources:
            tasks.append(self._recall_source(source, limit_per_source))
        
        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 合并结果
        all_items = []
        for result in results:
            if isinstance(result, list):
                all_items.extend(result)
        
        return all_items
    
    def _get_enabled_sources(self, profile: UserProfile) -> list[DataSource]:
        """根据用户画像启用数据源"""
        enabled = []
        
        if profile.is_cold_start:
            # 冷启动：启用热榜
            enabled = [DataSource.NEWS_HOT, DataSource.VIDEO_HOT, DataSource.PRODUCT_HOT]
        else:
            # 有画像：启用所有
            enabled = list(self.sources.keys())
        
        return [s for s in enabled if self.sources.get(s, {}).get("enabled", True)]
    
    async def _recall_source(self, source: DataSource, limit: int) -> list[RawItem]:
        """从单个数据源召回"""
        # 先检查缓存
        cached = self._get_cache(source)
        if cached:
            return cached[:limit]
        
        try:
            if source == DataSource.NEWS_HOT:
                return await self._fetch_news_hot(limit)
            elif source == DataSource.NEWS_TECH:
                return await self._fetch_tech_news(limit)
            elif source == DataSource.VIDEO_HOT:
                return await self._fetch_video_hot(limit)
            elif source == DataSource.PRODUCT_HOT:
                return await self._fetch_product_hot(limit)
            else:
                return []
        except Exception as e:
            print(f"[RecallEngine] {source.value} fetch error: {e}")
            return []
    
    async def _fetch_news_hot(self, limit: int) -> list[RawItem]:
        """获取新闻热榜"""
        # 使用示例API，实际应替换为真实API
        items = []
        
        # 模拟数据（实际应调用API）
        mock_news = [
            {"id": "n001", "title": "AI技术再获突破，大模型能力持续提升", "desc": "最新研究表明，大语言模型在多模态任务上取得显著进展...", "source": "科技日报"},
            {"id": "n002", "title": "量子计算商用加速，多家企业布局", "desc": "量子计算领域传来好消息，多家科技巨头宣布量子计算商用计划...", "source": "财经周刊"},
            {"id": "n003", "title": "新能源汽车销量再创新高", "desc": "最新数据显示，新能源汽车市场持续火爆，销量同比增长...", "source": "汽车之家"},
            {"id": "n004", "title": "数字经济成为增长新引擎", "desc": "数字经济蓬勃发展，成为推动经济增长的重要力量...", "source": "经济观察"},
            {"id": "n005", "title": "智能家居市场迎来爆发期", "desc": "智能家居产品快速普及，智能音箱、智能门锁等成为家庭标配...", "source": "智能家居"},
        ]
        
        for news in mock_news[:limit]:
            items.append(RawItem(
                source="news_hot",
                item_id=news["id"],
                title=news["title"],
                description=news.get("desc", ""),
                url=f"https://news.example.com/{news['id']}",
                tags=["新闻", news.get("source", "综合")],
                hot_score=0.8,
                publish_time=time.time() - 3600
            ))
        
        self._set_cache(DataSource.NEWS_HOT, items)
        return items
    
    async def _fetch_tech_news(self, limit: int) -> list[RawItem]:
        """获取科技新闻"""
        items = []
        
        mock_tech = [
            {"id": "t001", "title": "OpenAI发布新一代GPT模型", "desc": "GPT-5在推理能力和多模态理解上有重大突破...", "source": "AI科技"},
            {"id": "t002", "title": "苹果MR头显正式发售", "desc": "苹果Vision Pro正式上市，开启空间计算时代...", "source": "科技前沿"},
            {"id": "t003", "title": "特斯拉全自动驾驶获批", "desc": "特斯拉FSD在多个国家获监管批准...", "source": "汽车科技"},
            {"id": "t004", "title": "谷歌AI助手全面升级", "desc": "Google Assistant接入Gemini模型，能力大幅提升...", "source": "AI科技"},
        ]
        
        for tech in mock_tech[:limit]:
            items.append(RawItem(
                source="news_tech",
                item_id=tech["id"],
                title=tech["title"],
                description=tech.get("desc", ""),
                url=f"https://tech.example.com/{tech['id']}",
                tags=["科技", tech.get("source", "科技")],
                hot_score=0.75,
                publish_time=time.time() - 7200
            ))
        
        self._set_cache(DataSource.NEWS_TECH, items)
        return items
    
    async def _fetch_video_hot(self, limit: int) -> list[RawItem]:
        """获取视频热榜"""
        items = []
        
        mock_videos = [
            {"id": "v001", "title": "AI画师创作教程：从入门到精通", "desc": "Midjourney、Stable Diffusion实战技巧...", "image": "🎨", "source": "B站"},
            {"id": "v002", "title": "程序员必看：代码优化技巧", "desc": "提升代码性能的10个实用技巧...", "image": "💻", "source": "B站"},
            {"id": "v003", "title": "智能家居改造全过程记录", "desc": "打造全屋智能的完整方案...", "image": "🏠", "source": "抖音"},
        ]
        
        for video in mock_videos[:limit]:
            items.append(RawItem(
                source="video_hot",
                item_id=video["id"],
                title=video["title"],
                description=video.get("desc", ""),
                url=f"https://bilibili.com/video/{video['id']}",
                image_url=video.get("image", ""),
                tags=["视频", video.get("source", "视频")],
                hot_score=0.7,
                publish_time=time.time() - 10800
            ))
        
        self._set_cache(DataSource.VIDEO_HOT, items)
        return items
    
    async def _fetch_product_hot(self, limit: int) -> list[RawItem]:
        """获取商品热榜"""
        items = []
        
        mock_products = [
            {"id": "p001", "title": "小米14 Pro 智能手机", "desc": "骁龙8 Gen3处理器，徕卡影像...", "price": "4999元", "source": "小米"},
            {"id": "p002", "title": "Apple Watch S9", "desc": "全新S9芯片，血氧心率监测...", "price": "2999元", "source": "Apple"},
            {"id": "p003", "title": "Switch OLED 游戏机", "desc": "7寸OLED屏幕Joy-Con全新配色...", "price": "2599元", "source": "Nintendo"},
        ]
        
        for product in mock_products[:limit]:
            items.append(RawItem(
                source="product_hot",
                item_id=product["id"],
                title=product["title"],
                description=f"{product.get('desc', '')} | {product.get('price', '')}",
                url=f"https://jd.com/product/{product['id']}",
                tags=["商品", product.get("source", "商品")],
                hot_score=0.6,
                publish_time=time.time() - 86400
            ))
        
        self._set_cache(DataSource.PRODUCT_HOT, items)
        return items
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()


# 便捷函数
_recall_engine: Optional[RecallEngine] = None


def get_recall_engine(profile_manager) -> RecallEngine:
    """获取全局召回引擎"""
    global _recall_engine
    if _recall_engine is None:
        _recall_engine = RecallEngine(profile_manager)
    return _recall_engine
