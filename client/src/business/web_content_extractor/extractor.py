"""
统一内容提取接口

提供多层降级策略：
1. Jina Reader（最高质量，需代理）
2. Scrapling（高速+反爬，本地运行）
3. 内置简单提取（备选）
"""

import asyncio
import logging
import re
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass, field

from .jina_reader import JinaReader, ExtractResult

logger = logging.getLogger(__name__)

# Scrapling 可选依赖
try:
    from scrapling import Fetcher
    _SCRAPLING_AVAILABLE = True
except ImportError:
    _SCRAPLING_AVAILABLE = False
    logger.warning("Scrapling 未安装，L2 策略不可用")


@dataclass
class ExtractionConfig:
    """提取配置

    三层提取策略：
    L1: Jina Reader（最高质量，需代理）
    L2: Scrapling（高速+反爬，本地运行）
    L3: 内置简单提取（降级方案）
    """
    use_jina: bool = True              # L1: 是否使用 Jina Reader
    jina_api_key: Optional[str] = None  # Jina API Key
    jina_timeout: int = 30           # Jina 请求超时
    proxy: Optional[str] = None        # 手动指定代理地址（优先级最高）
    proxy_auto: bool = True           # 是否自动从项目代理池获取代理
    use_scrapling: bool = True        # L2: 是否使用 Scrapling
    scrapling_timeout: int = 30      # Scrapling 请求超时
    fallback_to_builtin: bool = True  # L3: 是否降级到内置提取
    max_content_length: int = 50000   # 最大内容长度（字符）
    remove_boilerplate: bool = True   # 是否移除样板内容

    def get_proxy(self) -> Optional[str]:
        """获取代理地址（自动 + 手动）

        优先级：
        1. 手动指定 proxy
        2. 自动从代理池获取（proxy_auto=True）
        3. None（不使用代理）

        注意：如果 proxy_auto=True 但代理池为空，返回 None，
        此时 Jina Reader 可能无法访问 r.jina.ai（国内网络）。
        """
        # 1. 手动指定优先
        if self.proxy:
            logger.debug(f"使用手动指定代理: {self.proxy}")
            return self.proxy

        # 2. 自动从代理池获取
        if self.proxy_auto:
            try:
                from business.proxy_search.proxy_pool import get_proxy_pool
                pooled = get_proxy_pool().get_proxy()
                if pooled:
                    addr = pooled.proxy.full_address
                    logger.info(f"从代理池获取代理: {addr}")
                    return addr
                else:
                    logger.warning(
                        "代理池为空！Jina Reader 可能无法访问 r.jina.ai（国内网络）。"
                        "请检查代理源配置，或手动指定 proxy。"
                    )
            except Exception as e:
                logger.warning(f"从代理池获取代理失败: {e}")

        # 3. 无代理
        return None


class ContentExtractor:
    """统一内容提取器

    支持多种提取策略，自动降级。

    用法：
        extractor = ContentExtractor()
        content = await extractor.extract("https://example.com")

        # 或者指定策略
        content = await extractor.extract_with_jina("https://example.com")
        content = await extractor.extract_builtin("https://example.com")
    """

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
        self._jina_reader: Optional[JinaReader] = None
        self._scrapling_engine: Optional[Any] = None  # ScraplingEngine

    def _get_jina_reader(self) -> JinaReader:
        """获取或创建 JinaReader 实例"""
        if self._jina_reader is None:
            self._jina_reader = JinaReader(
                api_key=self.config.jina_api_key,
                timeout=self.config.jina_timeout,
                proxy=self.config.proxy,
            )
        return self._jina_reader

    def _get_scrapling_engine(self):
        """获取或创建 ScraplingEngine 实例"""
        if self._scrapling_engine is None:
            try:
                from business.web_crawler.engine import ScraplingEngine
                self._scrapling_engine = ScraplingEngine(
                    timeout=self.config.scrapling_timeout,
                    proxy=self.config.proxy,
                )
            except ImportError:
                self._scrapling_engine = None
                logger.warning("ScraplingEngine 导入失败，L2 策略不可用")
        return self._scrapling_engine

    async def close(self):
        """关闭资源"""
        if self._jina_reader:
            await self._jina_reader.close()
        if self._scrapling_engine:
            # ScraplingEngine doesn't have close(), but clean up anyway
            self._scrapling_engine = None

    async def extract(self, url: str) -> str:
        """提取网页内容（自动选择策略）

        三层策略：
        L1: Jina Reader（最高质量，需代理）
        L2: Scrapling（高速+反爬，本地运行）
        L3: 内置提取（降级方案）

        Args:
            url: 目标网页 URL

        Returns:
            str: 提取的文本内容（Markdown 或纯文本）
        """
        # 动态获取代理（从配置：手动 > 自动代理池 > None）
        proxy = self.config.get_proxy()

        # L1: Jina Reader
        if self.config.use_jina:
            try:
                result = await self._get_jina_reader().extract(url, proxy=proxy)
                if result.success and result.content:
                    content = result.content
                    if self.config.max_content_length > 0:
                        content = content[:self.config.max_content_length]
                    logger.info(f"L1 Jina Reader 提取成功: {url} ({len(content)} chars)")
                    return content
                else:
                    logger.warning(f"L1 Jina Reader 提取失败: {url} - {result.error}")
            except Exception as e:
                logger.warning(f"L1 Jina Reader 异常: {url} - {e}")

        # L2: Scrapling
        if self.config.use_scrapling and _SCRAPLING_AVAILABLE:
            try:
                engine = self._get_scrapling_engine()
                if engine:
                    from business.web_crawler.engine import CrawlResult
                    result: CrawlResult = await engine.extract(url, proxy=proxy)
                    if result.success and result.content:
                        content = result.content
                        if self.config.max_content_length > 0:
                            content = content[:self.config.max_content_length]
                        logger.info(f"L2 Scrapling 提取成功: {url} ({len(content)} chars)")
                        return content
                    else:
                        logger.warning(f"L2 Scrapling 提取失败: {url} - {result.error}")
            except Exception as e:
                logger.warning(f"L2 Scrapling 异常: {url} - {e}")

        # L3: 内置提取（降级）
        if self.config.fallback_to_builtin:
            logger.info(f"L3 降级到内置提取: {url}")
            return await self.extract_builtin(url)

        return ""

    async def extract_with_jina(self, url: str, proxy: Optional[str] = None) -> str:
        """使用 Jina Reader 提取（不降级）

        Args:
            url: 目标网页 URL
            proxy: 动态传入代理（可选，覆盖配置）

        Returns:
            str: Markdown 格式内容
        """
        # 自动获取代理（如果未手动指定）
        if proxy is None:
            proxy = self.config.get_proxy()

        result = await self._get_jina_reader().extract(url, proxy=proxy)
        if result.success:
            return result.content
        else:
            raise RuntimeError(f"Jina Reader 提取失败: {result.error}")

    async def extract_with_scrapling(self, url: str, proxy: Optional[str] = None) -> str:
        """使用 Scrapling 提取（不降级）

        Args:
            url: 目标网页 URL
            proxy: 动态传入代理（可选，覆盖配置）

        Returns:
            str: Markdown 格式内容
        """
        if not _SCRAPLING_AVAILABLE:
            raise RuntimeError("Scrapling 未安装，请先运行: pip install scrapling")

        # 自动获取代理（如果未手动指定）
        if proxy is None:
            proxy = self.config.get_proxy()

        engine = self._get_scrapling_engine()
        if engine is None:
            raise RuntimeError("ScraplingEngine 初始化失败")

        from business.web_crawler.engine import CrawlResult
        result: CrawlResult = await engine.extract(url, proxy=proxy)
        if result.success:
            return result.content
        else:
            raise RuntimeError(f"Scrapling 提取失败: {result.error}")

    async def extract_builtin(self, url: str) -> str:
        """使用内置方法提取（无需外部 API）

        这是一个简单的降级方案，使用 aiohttp 获取 HTML 后简单清洗。
        质量不如 Jina Reader，但不依赖外部服务。

        Args:
            url: 目标网页 URL

        Returns:
            str: 提取的纯文本内容
        """
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.warning(f"内置提取 HTTP {resp.status}: {url}")
                        return ""
                    html = await resp.text(encoding="utf-8", errors="ignore")
                    return self._simple_extract(html)

        except Exception as e:
            logger.error(f"内置提取失败: {url} - {e}")
            return ""

    def _simple_extract(self, html: str) -> str:
        """简单内容提取（内置降级方案）

        移除 HTML 标签、script、style，保留纯文本。
        这是 Jina Reader 不可用时的备选方案。

        Args:
            html: 原始 HTML 字符串

        Returns:
            str: 提取的纯文本
        """
        # 移除 script 和 style 标签及其内容
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # 移除 HTML 注释
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

        # 将 <br>、<p>、<div> 等块级标签替换为换行
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</(p|div|h[1-6]|li|tr)>', '\n', html, flags=re.IGNORECASE)

        # 移除所有剩余的 HTML 标签
        text = re.sub(r'<[^>]+>', '', html)

        # 解码 HTML 实体
        text = text.replace("&nbsp;", " ")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&amp;", "&")
        text = text.replace("&quot;", "\"")
        text = text.replace("&#39;", "'")

        # 清理多余空白
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if line:
                lines.append(line)

        result = "\n".join(lines)

        # 限制长度
        if self.config.max_content_length > 0:
            result = result[:self.config.max_content_length]

        return result


# 便捷函数

_default_extractor: Optional[ContentExtractor] = None


def get_extractor(config: Optional[ExtractionConfig] = None) -> ContentExtractor:
    """获取全局提取器实例"""
    global _default_extractor
    if _default_extractor is None:
        _default_extractor = ContentExtractor(config)
    return _default_extractor


async def extract_content(url: str, use_jina: bool = True) -> str:
    """便捷函数：提取网页内容

    Args:
        url: 目标网页 URL
        use_jina: 是否使用 Jina Reader

    Returns:
        str: 提取的文本内容
    """
    config = ExtractionConfig(use_jina=use_jina)
    extractor = ContentExtractor(config)
    try:
        return await extractor.extract(url)
    finally:
        await extractor.close()


async def batch_extract(
    urls: List[str],
    use_jina: bool = True,
    max_concurrent: int = 5,
) -> Dict[str, str]:
    """便捷函数：批量提取网页内容

    Args:
        urls: URL 列表
        use_jina: 是否使用 Jina Reader
        max_concurrent: 最大并发数

    Returns:
        Dict[str, str]: URL -> 内容 的映射
    """
    config = ExtractionConfig(use_jina=use_jina)
    extractor = ContentExtractor(config)

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _extract_one(url: str) -> tuple:
        async with semaphore:
            content = await extractor.extract(url)
            return (url, content)

    try:
        results = await asyncio.gather(*[_extract_one(url) for url in urls])
        return dict(results)
    finally:
        await extractor.close()
