"""
ScraplingEngine - Scrapling 核心封装（修正版，基于真实 API）

基于 Scrapling 0.4.7 真实 API：
- Fetcher.configure(adaptive=True)  # 类方法，配置类本身
- f = Fetcher()                      # 创建实例
- r = f.get(url, timeout=10)        # 返回 Response
- r.status                          # HTTP 状态码（不是 status_code）
- r.find(selector)                  # 直接在 Response 上查找
- r.find_all(selector)
- r.text                            # 文本内容
- r.prettify                        # 格式化的 HTML
- r.body                            # 原始字节
- r.url, r.encoding, r.headers, r.cookies

文档：https://scrapling.readthedocs.io/
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
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
    content: str = ""               # 提取的文本内容
    html: str = ""                  # 格式化 HTML（prettify）
    raw_html: bytes = b""          # 原始 HTML 字节
    title: str = ""                # 页面标题
    status: int = 0               # HTTP 状态码
    success: bool = False
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ScraplingEngine:
    """Scrapling 引擎封装（基于真实 API）

    用法：
        # 配置（类方法，只需调用一次）
        from scrapling import Fetcher
        Fetcher.configure(adaptive=True)

        # 创建实例并使用
        engine = ScraplingEngine()
        result = await engine.extract("https://example.com")
    """

    # 类级别配置（所有实例共享）
    _configured = False

    @classmethod
    def configure_class(cls, adaptive: bool = True, **kwargs):
        """配置 Scrapling 类级别参数（只需调用一次）"""
        if not _SCRAPLING_AVAILABLE:
            logger.warning("Scrapling 未安装，无法配置")
            return
        valid_keys = {'huge_tree', 'adaptive', 'storage',
                      'keep_cdata', 'keep_comments', 'adaptive_domain'}
        filtered = {k: v for k, v in kwargs.items() if k in valid_keys}
        if adaptive:
            filtered['adaptive'] = True
        Fetcher.configure(**filtered)
        cls._configured = True
        logger.info(f"Scrapling Fetcher 类已配置: {filtered}")

    def __init__(
        self,
        timeout: int = 30,
        adaptive: bool = True,
        proxy: Optional[str] = None,
    ):
        """
        Args:
            timeout: 请求超时（秒），传给 f.get(timeout=...)
            adaptive: 是否启用自适应模式
            proxy: 代理地址，如 "http://127.0.0.1:7890"
        """
        self.timeout = timeout
        self.adaptive = adaptive
        self.proxy = proxy

        # 确保类已配置
        if adaptive and not self.__class__._configured:
            self.__class__.configure_class(adaptive=True)
            self.__class__._configured = True

    async def extract(
        self,
        url: str,
        selector: Optional[str] = None,
        output_format: str = "text",
        proxy: Optional[str] = None,
    ) -> CrawlResult:
        """提取网页内容

        Args:
            url: 目标 URL
            selector: CSS 选择器（可选，指定提取区域）
            output_format: 输出格式（"text" / "html" / "prettify"）
            proxy: 动态传入代理地址（优先级高于 self.proxy）

        Returns:
            CrawlResult: 提取结果
        """
        if not _SCRAPLING_AVAILABLE:
            logger.warning("Scrapling 未安装，使用降级方案")
            return await self._extract_fallback(url, selector)

        # 代理优先级：动态传入 > self.proxy
        effective_proxy = proxy or self.proxy

        try:
            f = Fetcher()
            # 传入代理（Scrapling 支持 proxy 参数）
            get_kwargs = {"timeout": self.timeout}
            if effective_proxy:
                get_kwargs["proxy"] = effective_proxy
            response = f.get(url, **get_kwargs)

            if response.status != 200:
                return CrawlResult(
                    url=url,
                    status=response.status,
                    success=False,
                    error=f"HTTP {response.status}",
                )

            # 提取标题
            title = ""
            title_elem = response.find("title")
            if title_elem:
                title = title_elem.text.strip()

            # 提取正文
            content, html = self._extract_content(response, selector, output_format)

            return CrawlResult(
                url=str(response.url),
                content=content,
                html=html,
                raw_html=response.body if hasattr(response, 'body') else b"",
                title=title,
                status=response.status,
                success=True,
                metadata={
                    "encoding": getattr(response, 'encoding', None),
                    "headers": dict(getattr(response, 'headers', {})),
                }
            )

        except Exception as e:
            logger.error(f"Scrapling 提取失败: {url} - {e}")
            logger.info(f"降级到内置方案: {url}")
            return await self._extract_fallback(url, selector)

    def _extract_content(
        self,
        response,
        selector: Optional[str],
        output_format: str,
    ) -> tuple:
        """从 Response 提取内容（Scrapling 0.4.7 真实 API）

        注意：response.text 可能为空，应使用 get_all_text() 获取全文。
        """
        # 如果指定了选择器，限定范围
        target = response
        if selector:
            elem = response.find(selector)
            if elem:
                target = elem

        # 提取文本：优先用 get_all_text()，再用 text
        def _get_text(obj) -> str:
            """安全获取对象文本"""
            if hasattr(obj, 'get_all_text'):
                result = obj.get_all_text()
                if result:
                    return result
            if hasattr(obj, 'text'):
                result = obj.text
                if result:
                    return result
            # 降级：拼接所有 <p> 的文本
            if hasattr(obj, 'find_all'):
                paragraphs = obj.find_all("p")
                if paragraphs:
                    texts = [p.get_all_text() if hasattr(p, 'get_all_text')
                             else p.text for p in paragraphs]
                    return "\n\n".join(t for t in texts if t and t.strip())
            return ""

        content = _get_text(target)
        html = response.prettify if hasattr(response, 'prettify') else ""

        if output_format == "text":
            return content, html

        elif output_format == "html":
            return content, html

        elif output_format == "prettify":
            return html, html

        else:
            return content, ""

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
                    status=resp.status_code,
                    success=False,
                    error=f"HTTP {resp.status_code}",
                )

            doc = lxml_html.fromstring(resp.content)

            # 提取标题
            title_elem = doc.find(".//title")
            title = title_elem.text_content().strip() if title_elem is not None else ""

            # 去掉 script/style
            for tag in doc.xpath("//script | //style"):
                tag.getparent().remove(tag)

            # 提取正文
            content = ""
            if selector:
                if selector.startswith("."):
                    cls = selector[1:]
                    elem = doc.find(f'.//*[contains(@class, "{cls}")]')
                elif selector.startswith("#"):
                    id_ = selector[1:]
                    elem = doc.find(f'.//*[@id="{id_}"]')
                else:
                    elem = doc.find(f".//{selector}")
                if elem is not None:
                    content = elem.text_content().strip()

            if not content:
                body = doc.find(".//body")
                content = body.text_content() if body is not None else doc.text_content()
                import re
                content = re.sub(r'\s+', ' ', content).strip()

            return CrawlResult(
                url=url,
                content=content,
                title=title,
                status=resp.status_code,
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
        """批量提取（并发）"""

        semaphore = asyncio.Semaphore(max_concurrent)

        async def _extract_one(url: str) -> tuple:
            async with semaphore:
                result = await self.extract(url)
                return (url, result)

        results = await asyncio.gather(
            *[_extract_one(url) for url in urls],
            return_exceptions=True
        )

        output = {}
        for item in results:
            if isinstance(item, Exception):
                logger.warning(f"批量提取异常: {item}")
                continue
            url, result = item
            output[url] = result
        return output

    def extract_sync(self, url: str, **kwargs) -> CrawlResult:
        """同步提取（便捷方法）"""
        return asyncio.run(self.extract(url, **kwargs))


# 便捷函数
async def extract_with_scrapling(url: str, **kwargs) -> str:
    """便捷函数：使用 Scrapling 提取网页内容"""
    engine = ScraplingEngine()
    result = await engine.extract(url, **kwargs)
    if result.success:
        return result.content
    else:
        raise RuntimeError(f"Scrapling 提取失败: {result.error}")
