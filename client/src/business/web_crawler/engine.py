"""
ScraplingEngine - Scrapling 核心封装

基于 Scrapling 框架的高性能网页内容提取引擎。
比 BeautifulSoup 快 774 倍，内置反爬绕过能力。

特性：
- 自适应解析（网站改版后自动修复选择器）
- 反爬绕过（Cloudflare、随机 UA、指纹伪装）
- 极速解析（基于 lxml + 异步）
- 支持动态页面（可选 JS 渲染）

文档：https://scrapling.readthedocs.io/
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Scrapling 可选依赖
try:
    from scrapling import Fetcher
    _SCRAPLING_AVAILABLE = True
except ImportError:
    _SCRAPLING_AVAILABLE = False
    Fetcher = None
    logger.warning("Scrapling 未安装，web_crawler 模块功能受限")


@dataclass
class CrawlResult:
    """爬取结果"""
    url: str
    content: str = ""               # 提取的文本内容（Markdown 格式）
    html: str = ""                  # 原始 HTML
    title: str = ""                # 页面标题
    status_code: int = 0          # HTTP 状态码
    success: bool = False
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ScraplingEngine:
    """Scrapling 引擎封装

    高性能网页内容提取，支持反爬绕过。
    自动降级到 requests + lxml（如果 Scrapling 不可用）。

    用法：
        engine = ScraplingEngine()
        result = await engine.extract("https://example.com")

        # 批量提取
        results = await engine.batch_extract([url1, url2])
    """

    def __init__(
        self,
        timeout: int = 30,
        use_proxies: bool = False,
        proxies: Optional[List[str]] = None,
    ):
        """
        Args:
            timeout: 请求超时（秒）
            use_proxies: 是否使用代理
            proxies: 代理列表（格式：["http://proxy1:port", ...]）
        """
        self.timeout = timeout
        self.use_proxies = use_proxies
        self.proxies = proxies or []
        self._fetcher: Optional[Fetcher] = None

    def _get_fetcher(self) -> Optional[Fetcher]:
        """获取或创建 Fetcher 实例"""
        if not _SCRAPLING_AVAILABLE:
            return None

        if self._fetcher is None:
            self._fetcher = Fetcher(
                auto_adapt=True,        # 自适应模式
                timeout=self.timeout,
            )
        return self._fetcher

    async def extract(
        self,
        url: str,
        selector: Optional[str] = None,
        output_format: str = "markdown",
    ) -> CrawlResult:
        """提取网页内容

        Args:
            url: 目标 URL
            selector: CSS 选择器（可选，指定提取区域）
            output_format: 输出格式（"markdown" / "text" / "html"）

        Returns:
            CrawlResult: 提取结果
        """
        if not _SCRAPLING_AVAILABLE:
            logger.warning("Scrapling 未安装，使用降级方案")
            return await self._extract_fallback(url, selector)

        fetcher = self._get_fetcher()
        if fetcher is None:
            return CrawlResult(url=url, success=False, error="Fetcher 初始化失败")

        try:
            # 使用 Scrapling 的 Fetcher 获取页面
            # Fetcher 是 Scrapling 的核心，比 requests + BeautifulSoup 快很多
            response = fetcher.get(
                url,
                timeout=self.timeout,
                allow_redirects=True,
            )

            if response.status_code != 200:
                return CrawlResult(
                    url=url,
                    status_code=response.status_code,
                    success=False,
                    error=f"HTTP {response.status_code}",
                )

            # 用 response.page 获取 Page 对象（Scrapling 的智能解析器）
            page = response.page

            # 提取标题
            title = ""
            title_elem = page.find("title")
            if title_elem:
                title = title_elem.text.strip()

            # 提取正文内容
            content = self._extract_content(page, selector, output_format)

            return CrawlResult(
                url=url,
                content=content,
                html=response.text[:5000],   # 限制原始 HTML 大小
                title=title,
                status_code=response.status_code,
                success=True,
                metadata={
                    "url": str(response.url),
                    "encoding": response.encoding,
                }
            )

        except Exception as e:
            logger.error(f"Scrapling 提取失败: {url} - {e}")
            # 降级到简单方案
            logger.info(f"降级到内置方案: {url}")
            return await self._extract_fallback(url, selector)

    def _extract_content(
        self,
        page: "Page",
        selector: Optional[str],
        output_format: str,
    ) -> str:
        """使用 Scrapling Page 提取内容

        Page 是 Scrapling 的智能解析器，比 BeautifulSoup 快 774 倍。
        支持自适应选择器（网站改版后自动适配）。
        """
        # 如果指定了选择器，只提取该区域
        if selector:
            elem = page.find(selector)
            if elem:
                page = elem  # 限定范围

        if output_format == "markdown":
            # 使用 Scrapling 的内置 Markdown 转换
            return page.markdown

        elif output_format == "text":
            # 纯文本
            return page.text

        elif output_format == "html":
            # HTML 片段
            return page.html

        else:
            # 默认：尝试提取文章正文
            # Scrapling 有内置的智能正文提取
            return page.markdown

    async def _extract_fallback(
        self,
        url: str,
        selector: Optional[str] = None,
    ) -> CrawlResult:
        """降级方案：使用 requests + lxml"""
        try:
            import requests
            from lxml import html as lxml_html

            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                return CrawlResult(
                    url=url,
                    status_code=resp.status_code,
                    success=False,
                    error=f"HTTP {resp.status_code}",
                )

            # 使用 lxml 解析（也比 BeautifulSoup 快很多）
            doc = lxml_html.fromstring(resp.content)
            
            # 提取标题
            title_elem = doc.find(".//title")
            title = title_elem.text_content().strip() if title_elem is not None else ""

            # 提取正文（简单策略：去掉 script/style，取 body 文本）
            for tag in doc.xpath("//script | //style"):
                tag.getparent().remove(tag)
            
            body = doc.find(".//body")
            content = body.text_content() if body is not None else doc.text_content()
            
            # 清理空白
            import re
            content = re.sub(r'\s+', ' ', content).strip()

            return CrawlResult(
                url=url,
                content=content,
                title=title,
                status_code=resp.status_code,
                success=True,
                metadata={"method": "fallback_lxml"},
            )

        except Exception as e:
            logger.error(f"降级方案也失败: {url} - {e}")
            return CrawlResult(
                url=url,
                success=False,
                error=str(e),
            )

    async def batch_extract(
        self,
        urls: List[str],
        max_concurrent: int = 5,
    ) -> Dict[str, CrawlResult]:
        """批量提取（并发）

        Args:
            urls: URL 列表
            max_concurrent: 最大并发数

        Returns:
            Dict[str, CrawlResult]: URL -> 结果的映射
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _extract_one(url: str) -> tuple:
            async with semaphore:
                result = await self.extract(url)
                return (url, result)

        results = await asyncio.gather(*[_extract_one(url) for url in urls])
        return dict(results)

    def extract_sync(self, url: str, **kwargs) -> CrawlResult:
        """同步提取（便捷方法）"""
        return asyncio.run(self.extract(url, **kwargs))


# 便捷函数

async def extract_with_scrapling(url: str, **kwargs) -> str:
    """便捷函数：使用 Scrapling 提取网页内容

    Args:
        url: 目标 URL
        **kwargs: 传递给 ScraplingEngine.extract()

    Returns:
        str: 提取的 Markdown 内容
    """
    engine = ScraplingEngine()
    result = await engine.extract(url, **kwargs)
    if result.success:
        return result.content
    else:
        raise RuntimeError(f"Scrapling 提取失败: {result.error}")
