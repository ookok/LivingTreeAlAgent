"""
智能搜索引擎
"""

import re
import asyncio
import aiohttp
from typing import List, Optional, Dict, Callable
from datetime import datetime
from .models import SearchQuery, SearchResult, SourceType


class SmartSearchEngine:
    """智能搜索引擎"""
    
    # 搜索源配置
    SEARCH_SOURCES = {
        "google": {
            "name": "Google搜索",
            "url": "https://www.google.com/search",
            "weight": 1.0,
            "need_proxy": True,
        },
        "bing": {
            "name": "Bing搜索",
            "url": "https://cn.bing.com/search",
            "weight": 0.9,
            "need_proxy": False,
        },
        "baidu": {
            "name": "百度搜索",
            "url": "https://www.baidu.com/s",
            "weight": 1.0,
            "need_proxy": False,
        },
        "sogou": {
            "name": "搜狗搜索",
            "url": "https://www.sogou.com/web",
            "weight": 0.8,
            "need_proxy": False,
        },
    }
    
    # 专业搜索源
    VERTICAL_SOURCES = {
        "github": {
            "name": "GitHub",
            "url": "https://github.com/search",
            "weight": 1.0,
            "patterns": ["github.com", "repo", "repository"],
        },
        "stackoverflow": {
            "name": "Stack Overflow",
            "url": "https://stackoverflow.com/search",
            "weight": 0.95,
            "patterns": ["stackoverflow", "question", "answer"],
        },
        "arxiv": {
            "name": "arXiv",
            "url": "https://arxiv.org/search",
            "weight": 0.9,
            "patterns": ["arxiv", "paper", "pdf"],
        },
        "zhihu": {
            "name": "知乎",
            "url": "https://www.zhihu.com/search",
            "weight": 0.85,
            "patterns": ["知乎", "zhihu"],
        },
    }
    
    # 来源类型映射
    DOMAIN_TYPE_MAP = {
        "github.com": SourceType.OFFICIAL_DOCS,
        "docs.python.org": SourceType.OFFICIAL_DOCS,
        "docs.microsoft.com": SourceType.OFFICIAL_DOCS,
        "developer.mozilla.org": SourceType.OFFICIAL_DOCS,
        "stackoverflow.com": SourceType.QNA,
        "serverfault.com": SourceType.QNA,
        "zhihu.com": SourceType.BLOG,
        "medium.com": SourceType.BLOG,
        "dev.to": SourceType.BLOG,
        "youtube.com": SourceType.VIDEO,
        "bilibili.com": SourceType.VIDEO,
        "arxiv.org": SourceType.PAPER,
        "papers.nips.cc": SourceType.PAPER,
        "arxiv.org": SourceType.PAPER,
        "twitter.com": SourceType.SOCIAL,
        "x.com": SourceType.SOCIAL,
    }
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._search_cache: Dict[str, List[SearchResult]] = {}
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    def expand_query(self, query: str) -> SearchQuery:
        """扩展查询词"""
        expanded = [query]
        
        # 英文扩展（针对技术术语）
        english_terms = {
            "机器学习": "machine learning",
            "深度学习": "deep learning",
            "人工智能": "artificial intelligence AI",
            "神经网络": "neural network",
            "大语言模型": "large language model LLM GPT",
            "自然语言处理": "NLP natural language processing",
            "计算机视觉": "computer vision CV",
        }
        
        for cn, en in english_terms.items():
            if cn in query:
                expanded.append(en)
        
        # 添加通用扩展
        extensions = ["tutorial", "guide", "documentation", "introduction"]
        for ext in extensions:
            if ext not in query.lower():
                expanded.append(f"{query} {ext}")
        
        return SearchQuery(
            original=query,
            expanded=list(set(expanded)),
        )
    
    def _detect_source_type(self, url: str) -> SourceType:
        """检测来源类型"""
        domain = re.sub(r"https?://(www\.)?", "", url.split("/")[0] if "/" in url else url)
        
        for pattern, source_type in self.DOMAIN_TYPE_MAP.items():
            if pattern in domain:
                return source_type
        
        # 基于URL模式判断
        if "stackoverflow" in url:
            return SourceType.QNA
        elif "arxiv" in url or "paper" in url:
            return SourceType.PAPER
        elif "youtube" in url or "video" in url:
            return SourceType.VIDEO
        elif any(kw in url for kw in ["blog", "medium", "article"]):
            return SourceType.BLOG
        elif any(kw in url for kw in ["docs", "documentation", "guide"]):
            return SourceType.OFFICIAL_DOCS
        
        return SourceType.UNKNOWN
    
    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """执行搜索（返回搜索结果，不含全文）"""
        search_query = self.expand_query(query)
        
        # 使用缓存
        cache_key = f"{query}:{max_results}"
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]
        
        results = []
        
        # 模拟搜索结果（实际使用时需要调用真实搜索引擎API）
        # 这里提供演示数据
        demo_results = self._generate_demo_results(query)
        results.extend(demo_results)
        
        # 去重
        seen_urls = set()
        unique_results = []
        for r in results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(r)
        
        # 限制数量
        unique_results = unique_results[:max_results]
        
        # 缓存
        self._search_cache[cache_key] = unique_results
        
        return unique_results

    async def search_and_fetch(
        self,
        query: str,
        max_results: int = 5,
        use_jina: bool = True,
        use_scrapling: bool = True,
        max_concurrent: int = 3,
    ) -> List[SearchResult]:
        """执行深度搜索：搜索 + 自动提取全文（L1→L2→L3）
        
        完整三层内容提取策略：
        L1: Jina Reader（最高质量，需代理）
        L2: Scrapling（高速+反爬，本地运行）
        L3: 内置简单提取（降级方案）
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数（建议 ≤10）
            use_jina: 是否启用 L1 Jina Reader
            use_scrapling: 是否启用 L2 Scrapling
            max_concurrent: 最大并发提取数
            
        Returns:
            List[SearchResult]: 搜索结果（包含全文内容）
        """
        # 1. 获取搜索结果
        results = await self.search(query, max_results)
        urls = [r.url for r in results if r.url]
        
        if not urls:
            return results
        
        # 2. 并发提取全文（使用完整三层策略）
        from client.src.business.web_content_extractor import ContentExtractor, ExtractionConfig
        
        config = ExtractionConfig(
            use_jina=use_jina,
            use_scrapling=use_scrapling,
            fallback_to_builtin=True,
        )
        extractor = ContentExtractor(config=config)
        
        try:
            # 批量提取
            import asyncio
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def _extract_one(url: str) -> tuple:
                async with semaphore:
                    content = await extractor.extract(url)
                    return url, content
            
            tasks = [_extract_one(url) for url in urls]
            extract_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 3. 将内容写回 SearchResult
            url_content_map = {}
            for item in extract_results:
                if isinstance(item, Exception):
                    logger.warning(f"提取异常: {item}")
                    continue
                url, content = item
                url_content_map[url] = content
            
            for result in results:
                if result.url in url_content_map:
                    content = url_content_map[result.url]
                    if content:
                        result.content = content
                        result.word_count = len(content.split())
                        
        except Exception as e:
            logger.error(f"批量提取失败: {e}")
        finally:
            await extractor.close()
        
        return results
    
    def _generate_demo_results(self, query: str) -> List[SearchResult]:
        """生成演示搜索结果"""
        # 基于查询生成合理的演示结果
        results = []
        
        # 官方文档
        results.append(SearchResult(
            url=f"https://docs.example.com/{query.replace(' ', '-')}",
            title=f"{query} - 官方文档",
            snippet=f"关于{query}的官方技术文档，包含完整的API参考和使用指南。",
            source_type=SourceType.OFFICIAL_DOCS,
            domain="docs.example.com",
            score=95,
            is_verified=True,
        ))
        
        # GitHub仓库
        results.append(SearchResult(
            url=f"https://github.com/example/{query.replace(' ', '-')}",
            title=f"example/{query.replace(' ', '-')} - GitHub",
            snippet=f"开源{query}实现，包含源代码、示例代码和详细的使用说明。",
            source_type=SourceType.OFFICIAL_DOCS,
            domain="github.com",
            score=90,
            is_verified=True,
        ))
        
        # 博客文章
        results.append(SearchResult(
            url=f"https://medium.com/@author/{query.replace(' ', '-')}",
            title=f"深入理解{query}：完整指南",
            snippet=f"一篇关于{query}的深度技术博客，涵盖了核心概念和实践应用。",
            source_type=SourceType.BLOG,
            domain="medium.com",
            score=80,
        ))
        
        # 视频教程
        results.append(SearchResult(
            url=f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}",
            title=f"{query} 视频教程合集",
            snippet=f"精选的{query}相关视频教程，从入门到精通。",
            source_type=SourceType.VIDEO,
            domain="youtube.com",
            score=75,
        ))
        
        # Stack Overflow
        results.append(SearchResult(
            url="https://stackoverflow.com/questions/tagged/example",
            title="Stack Overflow - 相关问答",
            snippet=f"开发者社区关于{query}的常见问题和解答。",
            source_type=SourceType.QNA,
            domain="stackoverflow.com",
            score=85,
        ))
        
        return results
    
    async def fetch_content(
        self,
        url: str,
        use_jina: bool = True,
        use_scrapling: bool = True,
    ) -> Optional[str]:
        """获取页面内容（完整三层策略：L1→L2→L3）
        
        Args:
            url: 目标网页 URL
            use_jina: 是否使用 L1 Jina Reader
            use_scrapling: 是否使用 L2 Scrapling
            
        Returns:
            Optional[str]: 提取的文本内容（Markdown 格式）
        """
        from client.src.business.web_content_extractor import ContentExtractor, ExtractionConfig
        
        config = ExtractionConfig(
            use_jina=use_jina,
            use_scrapling=use_scrapling,
            fallback_to_builtin=True,
        )
        extractor = ContentExtractor(config=config)
        try:
            content = await extractor.extract(url)
            if content:
                logger.info(f"内容提取成功: {url} ({len(content)} chars)")
                return content
            else:
                logger.warning(f"所有策略均未返回内容: {url}")
                return None
        finally:
            await extractor.close()
    
    def _extract_main_content(self, html: str) -> str:
        """提取页面主要内容"""
        # 移除script和style标签
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        
        # 移除注释
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', html)
        
        # 清理空白
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text[:5000]  # 限制长度
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "cache_size": len(self._search_cache),
            "sources_count": len(self.SEARCH_SOURCES) + len(self.VERTICAL_SOURCES),
        }
