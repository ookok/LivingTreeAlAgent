"""
Jina AI Reader 封装

将任意 URL 转换为 LLM 友好的 Markdown 格式。
支持免费版（r.jina.ai 前缀）和 API Key 版。

免费使用：在 URL 前加 https://r.jina.ai/
付费使用：提供 API Key，享受更高速率和更长内容

文档：https://jina.ai/reader/
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 免费版基础 URL
JINA_FREE_BASE = "https://r.jina.ai/"


@dataclass
class ExtractResult:
    """内容提取结果"""
    url: str                     # 原始 URL
    content: str                  # 提取的文本内容（Markdown 格式）
    title: str = ""              # 页面标题
    description: str = ""        # 页面描述
    success: bool = True         # 是否成功
    error: str = ""             # 错误信息
    metadata: Dict[str, Any] = field(default_factory=dict)


class JinaReader:
    """Jina AI Reader 封装

    将网页内容转换为 LLM 友好的结构化文本（Markdown 格式）。

    用法：
        reader = JinaReader()  # 免费版
        reader = JinaReader(api_key="xxx")  # API Key 版

        # 异步使用（推荐）
        result = await reader.extract("https://example.com")

        # 同步使用
        result = reader.extract_sync("https://example.com")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 30,
        proxy: Optional[str] = None,
    ):
        """
        Args:
            api_key: Jina AI API Key（可选，不提供则使用免费版）
            timeout: 请求超时时间（秒）
            proxy: 代理地址，如 "http://127.0.0.1:7890"
                    也支持从项目 SmartProxyGateway 自动获取
        """
        self.api_key = api_key
        self.timeout = timeout
        self.proxy = proxy
        self._session = None  # aiohttp session（延迟创建）

    async def _get_session(self):
        """获取或创建 aiohttp session"""
        if self._session is None or self._session.closed:
            import aiohttp
            timeout_obj = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout_obj)
        return self._session

    async def close(self):
        """关闭 session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _build_url(self, url: str) -> str:
        """构建 Jina Reader 请求 URL"""
        # 如果已经是 Jina URL，直接返回
        if url.startswith("https://r.jina.ai/"):
            return url
        return f"{JINA_FREE_BASE}{url}"

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Accept": "text/markdown",  # 请求 Markdown 格式
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def extract(
        self,
        url: str,
        proxy: Optional[str] = None,
        **kwargs,
    ) -> ExtractResult:
        """异步提取网页内容

        Args:
            url: 目标网页 URL
            proxy: 动态传入代理地址（优先级高于 self.proxy）
            **kwargs: 额外参数（保留扩展）

        Returns:
            ExtractResult: 提取结果
        """
        jina_url = self._build_url(url)
        headers = self._build_headers()

        # 代理优先级：动态传入 > self.proxy
        effective_proxy = proxy or self.proxy

        try:
            session = await self._get_session()
            # 传入代理（如有）
            get_kwargs = {}
            if effective_proxy:
                get_kwargs["proxy"] = effective_proxy

            async with session.get(jina_url, headers=headers, **get_kwargs) as resp:
                if resp.status != 200:
                    return ExtractResult(
                        url=url,
                        content="",
                        success=False,
                        error=f"HTTP {resp.status}: {resp.reason}",
                    )

                # Jina Reader 返回的是干净的 Markdown 文本
                content = await resp.text()

                # 尝试从内容中提取标题（第一个 # 开头的行）
                title = ""
                description = ""
                lines = content.split("\n")[:20]  # 只看前20行
                for line in lines:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break

                return ExtractResult(
                    url=url,
                    content=content,
                    title=title,
                    description=description,
                    success=True,
                    metadata={
                        "jina_url": jina_url,
                        "status_code": resp.status,
                        "content_length": len(content),
                    }
                )

        except asyncio.TimeoutError:
            return ExtractResult(
                url=url,
                content="",
                success=False,
                error=f"请求超时（{self.timeout}秒）",
            )
        except Exception as e:
            logger.error(f"Jina Reader 提取失败: {url} - {e}")
            return ExtractResult(
                url=url,
                content="",
                success=False,
                error=str(e),
            )

    def extract_sync(self, url: str, **kwargs) -> ExtractResult:
        """同步提取网页内容（便捷方法）

        Args:
            url: 目标网页 URL

        Returns:
            ExtractResult: 提取结果
        """
        return asyncio.run(self.extract(url, **kwargs))

    async def batch_extract(
        self,
        urls: List[str],
        max_concurrent: int = 5,
    ) -> List[ExtractResult]:
        """批量提取网页内容（并发）

        Args:
            urls: URL 列表
            max_concurrent: 最大并发数

        Returns:
            List[ExtractResult]: 提取结果列表（顺序与输入一致）
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _extract_with_semaphore(url: str) -> ExtractResult:
            async with semaphore:
                return await self.extract(url)

        tasks = [_extract_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return list(results)


def extract_url(url: str, api_key: Optional[str] = None) -> str:
    """快捷函数：提取单个 URL 的内容（同步）

    Args:
        url: 目标网页 URL
        api_key: 可选 API Key

    Returns:
        str: 提取的 Markdown 文本内容
    """
    reader = JinaReader(api_key=api_key)
    result = reader.extract_sync(url)
    if result.success:
        return result.content
    else:
        raise RuntimeError(f"提取失败: {result.error}")


async def aextract_url(url: str, api_key: Optional[str] = None) -> str:
    """快捷函数：提取单个 URL 的内容（异步）

    Args:
        url: 目标网页 URL
        api_key: 可选 API Key

    Returns:
        str: 提取的 Markdown 文本内容
    """
    reader = JinaReader(api_key=api_key)
    try:
        result = await reader.extract(url)
        return result.content if result.success else ""
    finally:
        await reader.close()
