"""
链接快照服务 - Link Preview Service
实现 Telegram 风格的 og:title/og:image 预览

功能:
1. 异步抓取网页 OpenGraph 元数据
2. 生成预览卡片 (缩略图 + 标题 + 域名)
3. 缓存机制避免重复抓取
"""

import re
import asyncio
import hashlib
import time
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import html
import urllib.parse

try:
    import aiohttp
except ImportError:
    aiohttp = None

from .models import LinkPreview


@dataclass
class LinkPreviewCache:
    """链接预览缓存"""
    url: str
    preview: LinkPreview
    fetched_at: float
    expires_at: float  # 过期时间


class LinkPreviewService:
    """
    链接预览服务

    参考 Telegram 的链接预览实现:
    1. 用户发送 URL
    2. 后台自动抓取 og:title, og:description, og:image
    3. 生成预览卡片
    4. 用户点击卡片跳转浏览器
    """

    def __init__(self, cache_ttl: int = 3600):
        """
        Args:
            cache_ttl: 缓存有效期 (秒), 默认 1 小时
        """
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, LinkPreviewCache] = {}
        self._fetching: Dict[str, asyncio.Event] = {}  # 防止重复抓取
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> Optional[aiohttp.ClientSession]:
        """获取或创建 HTTP Session"""
        if aiohttp is None:
            return None
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def _get_cache_key(self, url: str) -> str:
        """获取缓存 key"""
        return hashlib.md5(url.encode()).hexdigest()

    def _is_cache_valid(self, cache: LinkPreviewCache) -> bool:
        """检查缓存是否有效"""
        return time.time() < cache.expires_at

    async def fetch_preview(self, url: str) -> Optional[LinkPreview]:
        """
        获取链接预览

        Args:
            url: 目标 URL

        Returns:
            LinkPreview 对象, 失败返回 None
        """
        # 检查缓存
        cache_key = self._get_cache_key(url)
        if cache_key in self._cache:
            cache = self._cache[cache_key]
            if self._is_cache_valid(cache):
                return cache.preview

        # 防止重复抓取
        if url in self._fetching:
            await self._fetching[url].wait()
            cached = self._cache.get(cache_key)
            return cached.preview if cached else None

        # 创建抓取事件
        event = asyncio.Event()
        self._fetching[url] = event

        try:
            preview = await self._fetch(url)
            if preview:
                # 存入缓存
                self._cache[cache_key] = LinkPreviewCache(
                    url=url,
                    preview=preview,
                    fetched_at=time.time(),
                    expires_at=time.time() + self.cache_ttl
                )
            return preview
        finally:
            event.set()
            self._fetching.pop(url, None)

    async def _fetch(self, url: str) -> Optional[LinkPreview]:
        """实际抓取网页"""
        if aiohttp is None:
            return self._sync_fetch(url)

        session = await self._get_session()
        if not session:
            return self._sync_fetch(url)

        try:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    return None

                content_type = resp.headers.get("Content-Type", "")
                if "text/html" not in content_type:
                    # 非 HTML 内容, 只获取基本信息
                    return LinkPreview(
                        url=url,
                        loaded=True,
                        mime_type=content_type
                    )

                html_content = await resp.text()
                return self._parse_html(url, html_content)

        except Exception as e:
            print(f"[LinkPreview] Fetch error: {e}")
            return None

    def _sync_fetch(self, url: str) -> Optional[LinkPreview]:
        """同步抓取 (备选方案)"""
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=10) as resp:
                if resp.status != 200:
                    return None
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" not in content_type:
                    return LinkPreview(url=url, loaded=True, mime_type=content_type)
                html_content = resp.read().decode("utf-8", errors="ignore")
                return self._parse_html(url, html_content)
        except Exception as e:
            print(f"[LinkPreview] Sync fetch error: {e}")
            return None

    def _parse_html(self, url: str, html: str) -> LinkPreview:
        """解析 HTML 获取 OpenGraph 元数据"""
        preview = LinkPreview(url=url, loaded=True)

        # 解析 og:title
        og_title = self._extract_meta(html, "og:title")
        if not og_title:
            og_title = self._extract_meta(html, "twitter:title")
        if not og_title:
            og_title = self._extract_title(html)

        # 解析 og:description
        og_desc = self._extract_meta(html, "og:description")
        if not og_desc:
            og_desc = self._extract_meta(html, "twitter:description")
        if not og_desc:
            og_desc = self._extract_meta(html, "description")

        # 解析 og:image
        og_image = self._extract_meta(html, "og:image")
        if not og_image:
            og_image = self._extract_meta(html, "twitter:image")

        # 解析 og:site_name
        og_site_name = self._extract_meta(html, "og:site_name")

        # 解析网站图标
        favicon = self._extract_favicon(html, url)

        # 组装 URL (处理相对路径)
        if og_image:
            og_image = self._resolve_url(url, og_image)

        preview.title = html.unescape(og_title or "")
        preview.description = html.unescape(og_desc or "")[:200]  # 限制长度
        preview.image_url = og_image
        preview.site_name = html.unescape(og_site_name or self._get_domain(url))
        preview.favicon = favicon

        return preview

    def _extract_meta(self, html: str, property: str) -> Optional[str]:
        """提取 meta 标签内容"""
        # og: 属性
        pattern = rf'<meta[^>]*(?:property|name)=["\']{re.escape(property)}["\'][^>]*content=["\']([^"\']*)["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # 反向顺序
        pattern = rf'<meta[^>]*content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']{re.escape(property)}["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        return None

    def _extract_title(self, html: str) -> Optional[str]:
        """提取 <title> 标签"""
        match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _extract_favicon(self, html: str, base_url: str) -> str:
        """提取网站图标"""
        # 尝试 og:image 式的图标
        favicon = self._extract_meta(html, "og:image")
        if favicon:
            return self._resolve_url(base_url, favicon)

        # 尝试 link 标签
        patterns = [
            r'<link[^>]*rel=["\'](?:shortcut )?icon["\'][^>]*href=["\']([^"\']*)["\']',
            r'<link[^>]*href=["\']([^"\']*)["\'][^>]*rel=["\'](?:shortcut )?icon["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return self._resolve_url(base_url, match.group(1))

        # 默认 /favicon.ico
        parsed = urllib.parse.urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"

    def _get_domain(self, url: str) -> str:
        """获取域名"""
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.replace("www.", "")

    def _resolve_url(self, base: str, relative: str) -> str:
        """解析相对路径为绝对路径"""
        if not relative:
            return ""
        if relative.startswith(("http://", "https://")):
            return relative
        if relative.startswith("//"):
            parsed = urllib.parse.urlparse(base)
            return f"{parsed.scheme}:{relative}"
        parsed = urllib.parse.urlparse(base)
        if relative.startswith("/"):
            return f"{parsed.scheme}://{parsed.netloc}{relative}"
        else:
            return f"{parsed.scheme}://{parsed.netloc}/{relative}"

    def extract_urls(self, text: str) -> list:
        """从文本中提取 URL"""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        return re.findall(url_pattern, text)

    async def fetch_previews(self, urls: list) -> Dict[str, LinkPreview]:
        """批量获取预览"""
        results = {}
        tasks = [self.fetch_preview(url) for url in urls]
        previews = await asyncio.gather(*tasks, return_exceptions=True)
        for url, preview in zip(urls, previews):
            if isinstance(preview, LinkPreview):
                results[url] = preview
        return results

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()

    def cleanup_expired(self):
        """清理过期缓存"""
        now = time.time()
        expired = [k for k, v in self._cache.items() if now >= v.expires_at]
        for k in expired:
            del self._cache[k]

    async def close(self):
        """关闭服务"""
        if self._session and not self._session.closed:
            await self._session.close()
        self._executor.shutdown(wait=False)


# 单例
_link_preview_service: Optional[LinkPreviewService] = None


def get_link_preview_service() -> LinkPreviewService:
    """获取链接预览服务单例"""
    global _link_preview_service
    if _link_preview_service is None:
        _link_preview_service = LinkPreviewService()
    return _link_preview_service
