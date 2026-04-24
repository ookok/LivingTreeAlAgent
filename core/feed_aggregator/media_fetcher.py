# media_fetcher.py — 媒体增强抓取层
# 优先提取首图/视频封面，缩略图懒加载

import re
import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from .models import FeedItem, FeedSource, MediaType, FeedType


class MediaFetcher:
    """
    媒体增强抓取器

    功能：
    1. 从多个来源抓取内容
    2. 优先提取缩略图/封面
    3. 提取视频嵌入 URL
    4. 内容安全初筛
    """

    def __init__(self, data_dir: Optional[Path] = None, max_workers: int = 4):
        self.data_dir = data_dir or Path.home() / ".hermes-desktop" / "feed_aggregator"
        self.cache_dir = self.data_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # 来源处理器
        self._handlers = {
            FeedSource.WEIBO: self._fetch_weibo,
            FeedSource.ZHIHU: self._fetch_zhihu,
            FeedSource.REDDIT: self._fetch_reddit,
            FeedSource.GITHUB: self._fetch_github,
            FeedSource.NEWS: self._fetch_news,
            FeedSource.FORUM: self._fetch_forum,
            FeedSource.CUSTOM: self._fetch_custom,
        }

    # ============================================================
    # 主入口
    # ============================================================

    async def fetch_all(
        self,
        sources: List[FeedSource],
        max_per_source: int = 20,
    ) -> List[FeedItem]:
        """
        从多个来源抓取内容

        Args:
            sources: 来源列表
            max_per_source: 每来源最大条数

        Returns:
            List[FeedItem]: 抓取的内容列表
        """
        tasks = []
        for source in sources:
            if source in self._handlers:
                tasks.append(self._fetch_source(source, max_per_source))

        results = await self._gather_with_limit(tasks)
        return results

    async def fetch_source(
        self,
        source: FeedSource,
        max_items: int = 20,
    ) -> List[FeedItem]:
        """从单个来源抓取"""
        return await self._fetch_source(source, max_items)

    async def _fetch_source(
        self,
        source: FeedSource,
        max_items: int,
    ) -> List[FeedItem]:
        """内部抓取方法"""
        handler = self._handlers.get(source)
        if not handler:
            return []

        try:
            items = await handler(max_items)
            # 媒体增强
            items = await self._enhance_media(items)
            return items
        except Exception as e:
            logger.info(f"[MediaFetcher] Fetch {source.value} failed: {e}")
            return []

    async def _gather_with_limit(self, tasks, limit: int = 10):
        """并发执行任务（限制并发数）"""
        import asyncio
        semaphore = asyncio.Semaphore(limit)

        async def bounded(t):
            async with semaphore:
                return await t

        return await asyncio.gather(*[bounded(t) for t in tasks], return_exceptions=True)

    # ============================================================
    # 媒体增强
    # ============================================================

    async def _enhance_media(self, items: List[FeedItem]) -> List[FeedItem]:
        """增强每个条目的媒体信息"""
        for item in items:
            # 提取缩略图
            if not item.thumbnail_url:
                item.thumbnail_url = self._extract_thumbnail(item)

            # 确定媒体类型
            if item.video_embed:
                item.media_type = MediaType.VIDEO
            elif item.thumbnail_url:
                item.media_type = MediaType.IMAGE
            else:
                item.media_type = MediaType.NONE

        return items

    def _extract_thumbnail(self, item: FeedItem) -> str:
        """
        从内容中提取缩略图

        策略：
        1. 微博: pic_url 字段
        2. 论坛/Markdown: 首张图片
        3. 新闻: og:image 或头图
        """
        extra = item.extra_data

        # 微博 pic_url
        if item.source == FeedSource.WEIBO:
            pic_url = extra.get("pic_url") or extra.get("thumbnail")
            if pic_url:
                return self._to_thumbnail_url(pic_url)

        # 知乎图片
        if item.source == FeedSource.ZHIHU:
            image_url = extra.get("thumbnail") or extra.get("cover")
            if image_url:
                return self._to_thumbnail_url(image_url)

        # Reddit 图片
        if item.source == FeedSource.REDDIT:
            url = extra.get("url") or extra.get("preview", {}).get("images", [{}])[0].get("source", {}).get("url")
            if url:
                return self._to_thumbnail_url(url)

        # GitHub README 图片
        if item.source == FeedSource.GITHUB:
            avatar = extra.get("owner", {}).get("avatar_url")
            if avatar:
                return avatar

        # 从 summary/description 中提取图片
        text = f"{item.title} {item.summary}"
        img_matches = re.findall(r'!\[.*?\]\((.*?)\)|<img.*?src=["\'](.*?)["\']', text)
        if img_matches and img_matches[0]:
            url = img_matches[0][0] or img_matches[0][1]
            if url and not url.startswith('data:'):
                return self._to_thumbnail_url(url)

        # 从 URL 推断图片 (新闻网站)
        if item.source == FeedSource.NEWS:
            og_image = extra.get("og_image")
            if og_image:
                return self._to_thumbnail_url(og_image)

        return ""

    def _to_thumbnail_url(self, url: str) -> str:
        """
        转换为缩略图 URL

        策略：
        1. 微博: 替换为 wap640 尺寸
        2. 知乎: 替换为 xl 尺寸
        3. 其他: 添加尺寸参数或使用原图
        """
        if not url:
            return ""

        # 微博缩略图转换
        if "sinaimg.cn" in url:
            # 替换为中等尺寸
            return re.sub(r'/[\w]+\.jpg', '/wap640.jpg', url)

        # 知乎缩略图
        if "zhimg.com" in url:
            # 已经是 CDN 图片，保持原样
            return url

        # GitHub 头像
        if "github.com" in url and "/avatars/" in url:
            return url

        return url

    # ============================================================
    # 来源处理器（骨架实现）
    # ============================================================

    async def _fetch_weibo(self, max_items: int) -> List[FeedItem]:
        """
        抓取微博

        注意：需要微博 Cookie 或 SDK
        骨架实现
        """
        # 骨架代码 - 实际需要微博 API
        return []

    async def _fetch_zhihu(self, max_items: int) -> List[FeedItem]:
        """
        抓取知乎

        注意：需要登录态或知乎 SDK
        骨架实现
        """
        return []

    async def _fetch_reddit(self, max_items: int) -> List[FeedItem]:
        """抓取 Reddit 热门"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = "https://www.reddit.com/r/programming/hot.json?limit=50"
                async with session.get(url, headers={"User-Agent": "LivingTreeAI/1.0"}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = []
                        for post in data.get("data", {}).get("children", [])[:max_items]:
                            p = post["data"]
                            items.append(FeedItem(
                                id=f"reddit_{p['id']}",
                                title=p.get("title", ""),
                                summary=p.get("selftext", "")[:200],
                                source=FeedSource.REDDIT,
                                url=p.get("url", ""),
                                thumbnail_url=p.get("thumbnail", ""),
                                author=p.get("author", ""),
                                likes=p.get("score", 0),
                                comments=p.get("num_comments", 0),
                                tags=["reddit", "programming"],
                                published_at=datetime.fromtimestamp(p.get("created_utc", 0)),
                                extra_data=p,
                            ))
                        return items
        except Exception as e:
            logger.info(f"[MediaFetcher] Reddit fetch failed: {e}")
        return []

    async def _fetch_github(self, max_items: int) -> List[FeedItem]:
        """抓取 GitHub Trending"""
        try:
            import aiohttp
from core.logger import get_logger
logger = get_logger('feed_aggregator.media_fetcher')

            async with aiohttp.ClientSession() as session:
                url = "https://api.github.com/search/repositories?q=stars:>1000+pushed:>2024-01-01&sort=stars&per_page=50"
                async with session.get(url, headers={"User-Agent": "LivingTreeAI/1.0"}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = []
                        for repo in data.get("items", [])[:max_items]:
                            items.append(FeedItem(
                                id=f"github_{repo['id']}",
                                title=repo.get("full_name", ""),
                                summary=repo.get("description", "") or "",
                                source=FeedSource.GITHUB,
                                url=repo.get("html_url", ""),
                                thumbnail_url=repo.get("owner", {}).get("avatar_url", ""),
                                author=repo.get("owner", {}).get("login", ""),
                                likes=repo.get("stargazers_count", 0),
                                tags=["github", "trending"],
                                published_at=datetime.fromisoformat(repo.get("pushed_at", "").replace("Z", "")),
                                feed_type=FeedType.TECH,
                                extra_data=repo,
                            ))
                        return items
        except Exception as e:
            logger.info(f"[MediaFetcher] GitHub fetch failed: {e}")
        return []

    async def _fetch_news(self, max_items: int) -> List[FeedItem]:
        """抓取新闻 (RSS 风格)"""
        # 可接入 RSS 源或新闻 API
        return []

    async def _fetch_forum(self, max_items: int) -> List[FeedItem]:
        """抓取论坛"""
        return []

    async def _fetch_custom(self, max_items: int) -> List[FeedItem]:
        """自定义来源"""
        return []

    # ============================================================
    # 缓存
    # ============================================================

    def _cache_key(self, source: FeedSource) -> str:
        return f"{source.value}_{datetime.now().strftime('%Y%m%d%H')}.json"

    async def get_cached(self, source: FeedSource) -> List[FeedItem]:
        """获取缓存"""
        cache_file = self.cache_dir / self._cache_key(source)
        if not cache_file.exists():
            return []

        try:
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)
                return [self._dict_to_item(d) for d in data]
        except:
            return []

    async def save_cache(self, source: FeedSource, items: List[FeedItem]):
        """保存缓存"""
        cache_file = self.cache_dir / self._cache_key(source)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump([self._item_to_dict(i) for i in items], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.info(f"[MediaFetcher] Cache save failed: {e}")

    def _item_to_dict(self, item: FeedItem) -> Dict:
        return {
            "id": item.id,
            "title": item.title,
            "summary": item.summary,
            "source": item.source.value,
            "url": item.url,
            "thumbnail_url": item.thumbnail_url,
            "video_embed": item.video_embed,
            "media_type": item.media_type.value,
            "author": item.author,
            "tags": item.tags,
            "likes": item.likes,
            "comments": item.comments,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "extra_data": item.extra_data,
        }

    def _dict_to_item(self, d: Dict) -> FeedItem:
        return FeedItem(
            id=d["id"],
            title=d["title"],
            summary=d["summary"],
            source=FeedSource(d["source"]),
            url=d["url"],
            thumbnail_url=d.get("thumbnail_url", ""),
            video_embed=d.get("video_embed", ""),
            media_type=MediaType(d.get("media_type", "none")),
            author=d.get("author", ""),
            tags=d.get("tags", []),
            likes=d.get("likes", 0),
            comments=d.get("comments", 0),
            published_at=datetime.fromisoformat(d["published_at"]) if d.get("published_at") else None,
            extra_data=d.get("extra_data", {}),
        )


# 全局单例
_media_fetcher: Optional[MediaFetcher] = None


def get_media_fetcher() -> MediaFetcher:
    global _media_fetcher
    if _media_fetcher is None:
        _media_fetcher = MediaFetcher()
    return _media_fetcher
