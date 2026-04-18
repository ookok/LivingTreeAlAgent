# -*- coding: utf-8 -*-
"""
Multi-Search 多源搜索聚合引擎
Intelligence Gathering - Multi-Source Search Aggregator
"""

import asyncio
import hashlib
import json
import logging
import re
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


class SearchIntent(Enum):
    """搜索意图"""
    GENERAL = "general"
    COMPETITOR = "competitor"
    PRODUCT = "product"
    NEWS = "news"
    RUMOR = "rumor"
    REVIEW = "review"


class SearchSource(Enum):
    WEB = "web"
    NEWS = "news"
    SOCIAL = "social"
    ACADEMIC = "academic"


@dataclass
class SearchResult:
    title: str = ""
    url: str = ""
    snippet: str = ""
    source: str = ""
    source_type: SearchSource = SearchSource.WEB
    published_date: Optional[str] = None
    domain: str = ""
    relevance_score: float = 0.0
    authority_score: float = 0.0
    freshness_score: float = 0.0
    is_ad: bool = False


@dataclass
class SearchQuery:
    original: str = ""
    intent: SearchIntent = SearchIntent.GENERAL
    sources: List[SearchSource] = field(default_factory=lambda: [SearchSource.WEB])
    optimized: str = ""
    variants: List[str] = field(default_factory=list)
    limit: int = 20


@dataclass
class SearchResponse:
    query: SearchQuery
    results: List[SearchResult] = field(default_factory=list)
    total_count: int = 0
    sources_used: List[str] = field(default_factory=list)
    cache_hit: bool = False
    execution_time_ms: float = 0.0


class QueryOptimizer:
    """Query优化器"""

    INTENT_PATTERNS = {
        SearchIntent.COMPETITOR: ["竞争对手", "竞品", "替代", "vs"],
        SearchIntent.PRODUCT: ["产品", "评测", "体验"],
        SearchIntent.NEWS: ["最新", "今日", "新闻", "动态"],
        SearchIntent.RUMOR: ["谣言", "辟谣", "真假", "fact check"],
        SearchIntent.REVIEW: ["评价", "口碑", "反馈", "用户"],
    }

    @classmethod
    def detect_intent(cls, query: str) -> SearchIntent:
        query_lower = query.lower()
        for intent, patterns in cls.INTENT_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in query_lower:
                    return intent
        return SearchIntent.GENERAL

    @classmethod
    def generate_variants(cls, query: str, intent: SearchIntent) -> List[str]:
        variants = [query]
        if intent == SearchIntent.COMPETITOR:
            variants.extend([f"{query} 竞品", f"{query} 竞争对手"])
        elif intent == SearchIntent.NEWS:
            variants.extend([f"{query} 最新", f"{query} 新闻"])
        elif intent == SearchIntent.REVIEW:
            variants.extend([f"{query} 评价", f"{query} 用户反馈"])
        return list(dict.fromkeys(variants))[:5]

    @classmethod
    def is_ad_result(cls, title: str, snippet: str) -> bool:
        text = f"{title} {snippet}".lower()
        ad_patterns = [r"Advertisement|Sponsored|广告", r"立刻购买|立即下载"]
        for pattern in ad_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


class MultiSourceSearcher:
    """多源搜索聚合器"""

    ENGINES = {
        "baidu": {"name": "百度", "type": SearchSource.WEB, "base_url": "https://www.baidu.com/s"},
        "bing": {"name": "Bing", "type": SearchSource.WEB, "base_url": "https://www.bing.com/search"},
        "news_baidu": {"name": "百度新闻", "type": SearchSource.NEWS, "base_url": "https://www.baidu.com/s"},
        "zhihu": {"name": "知乎", "type": SearchSource.SOCIAL, "base_url": "https://www.zhihu.com/search"},
    }

    AUTHORITY_DOMAINS = {
        "wikipedia.org": 0.9, "github.com": 0.85, "stackoverflow.com": 0.85,
        "知乎.com": 0.8, "bilibili.com": 0.75, "baidu.com": 0.6,
    }

    def __init__(self, cache_dir: str = "", cache_ttl_hours: int = 1, timeout: int = 30):
        self.cache_dir = Path(cache_dir) if cache_dir else Path("")
        self.cache_ttl = cache_ttl_hours * 3600
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._memory_cache: Dict[str, Dict] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                }
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _hash_key(self, query: str, sources: List[str]) -> str:
        key = f"{query}|{','.join(sorted(sources))}"
        return hashlib.md5(key.encode()).hexdigest()

    def _get_cache(self, query: str, sources: List[str]) -> Optional[SearchResponse]:
        key = self._hash_key(query, sources)
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if time.time() < entry["expires_at"]:
                return self._deserialize(entry["data"])
        return None

    def _set_cache(self, query: str, sources: List[str], response: SearchResponse):
        key = self._hash_key(query, sources)
        self._memory_cache[key] = {
            "data": self._serialize(response),
            "expires_at": time.time() + self.cache_ttl,
        }

    def _serialize(self, r: SearchResponse) -> Dict:
        return {
            "query": {"original": r.query.original, "intent": r.query.intent.value},
            "results": [
                {"title": x.title, "url": x.url, "snippet": x.snippet, "source": x.source,
                 "source_type": x.source_type.value, "published_date": x.published_date,
                 "domain": x.domain, "relevance_score": x.relevance_score,
                 "authority_score": x.authority_score, "freshness_score": x.freshness_score, "is_ad": x.is_ad}
                for x in r.results
            ],
            "total_count": r.total_count,
            "sources_used": r.sources_used,
            "cache_hit": r.cache_hit,
            "execution_time_ms": r.execution_time_ms,
        }

    def _deserialize(self, data: Dict) -> SearchResponse:
        q = SearchQuery(original=data["query"]["original"], intent=SearchIntent(data["query"]["intent"]))
        results = [SearchResult(**x) for x in data["results"]]
        return SearchResponse(query=q, results=results, total_count=data["total_count"],
                              sources_used=data["sources_used"], cache_hit=True, execution_time_ms=data["execution_time_ms"])

    async def search(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        use_cache: bool = True,
    ) -> SearchResponse:
        start_time = time.time()
        sources = sources or ["baidu"]

        intent = QueryOptimizer.detect_intent(query)
        sq = SearchQuery(original=query, intent=intent, optimized=query,
                         variants=QueryOptimizer.generate_variants(query, intent))

        if use_cache:
            cached = self._get_cache(query, sources)
            if cached:
                return cached

        # 并行调用多个搜索引擎
        tasks = [self._search_engine(name, sq) for name in sources if name in self.ENGINES]
        results = []
        for task_result in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(task_result, list):
                results.extend(task_result)

        results = self._deduplicate(results)
        results = self._rank(results)

        execution_time = (time.time() - start_time) * 1000
        response = SearchResponse(query=sq, results=results[:sq.limit], total_count=len(results),
                                  sources_used=sources, cache_hit=False, execution_time_ms=execution_time)

        if use_cache:
            self._set_cache(query, sources, response)

        return response

    async def _search_engine(self, engine_name: str, query: SearchQuery) -> List[SearchResult]:
        """调用单个搜索引擎"""
        try:
            engine = self.ENGINES.get(engine_name)
            if not engine:
                return []

            client = await self._get_client()
            params = {"wd" if "baidu" in engine_name else "q": query.optimized, "rn": 20}

            response = await client.get(engine["base_url"], params=params)
            if response.status_code != 200:
                return []

            return self._parse_html(response.text, engine["type"], engine["name"])

        except Exception as e:
            logger.warning(f"搜索引擎 {engine_name} 失败: {e}")
            return []

    def _parse_html(self, html: str, source_type: SearchSource, source_name: str) -> List[SearchResult]:
        """解析HTML结果 - 简化实现"""
        # 实际应使用BeautifulSoup
        # 这里返回空列表，由爬虫模块提供完整实现
        return []

    def _deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        seen: Set[str] = set()
        unique = []
        for r in results:
            if r.url and r.url not in seen:
                seen.add(r.url)
                unique.append(r)
        return unique

    def _rank(self, results: List[SearchResult]) -> List[SearchResult]:
        for r in results:
            r.authority_score = self._get_authority(r.domain)
            r.freshness_score = self._get_freshness(r.published_date)
            r.is_ad = QueryOptimizer.is_ad_result(r.title, r.snippet)
            r.relevance_score = 0.4 * r.authority_score + 0.3 * r.freshness_score + 0.3 * (0.0 if r.is_ad else 1.0)
        return sorted(results, key=lambda x: x.relevance_score, reverse=True)

    def _get_authority(self, domain: str) -> float:
        for d, score in self.AUTHORITY_DOMAINS.items():
            if d in domain:
                return score
        return 0.5

    def _get_freshness(self, date_str: Optional[str]) -> float:
        if not date_str:
            return 0.5
        text = date_str.lower()
        if "今天" in text or "today" in text:
            return 1.0
        elif "昨天" in text or "yesterday" in text:
            return 0.9
        elif "周" in text or "week" in text:
            return 0.7
        elif "月" in text or "month" in text:
            return 0.5
        return 0.3


class DeepSearchPipeline:
    """深度搜索流水线 - 竞品监控专用"""

    def __init__(self, searcher: MultiSourceSearcher):
        self.searcher = searcher

    async def search_competitor(self, competitor_name: str, keywords: Optional[List[str]] = None) -> SearchResponse:
        """搜索竞品动态"""
        keywords = keywords or ["最新", "新品", "评测", "价格"]
        queries = [f"{competitor_name} {kw}" for kw in keywords]

        responses = await asyncio.gather(*[self.searcher.search(q) for q in queries], return_exceptions=True)

        all_results = []
        for resp in responses:
            if isinstance(resp, SearchResponse):
                all_results.extend(resp.results)

        all_results = self.searcher._deduplicate(all_results)
        all_results = self.searcher._rank(all_results)

        return SearchResponse(
            query=SearchQuery(original=f"{competitor_name} 综合搜索", intent=SearchIntent.COMPETITOR),
            results=all_results[:30], total_count=len(all_results),
            sources_used=["baidu", "bing", "news_baidu"], execution_time_ms=0
        )

    async def search_product_releases(self, product_name: str) -> SearchResponse:
        """搜索近期产品发布"""
        queries = [f"{product_name} 新品发布", f"{product_name} 上市"]
        responses = await asyncio.gather(*[self.searcher.search(q) for q in queries], return_exceptions=True)

        all_results = []
        for resp in responses:
            if isinstance(resp, SearchResponse):
                all_results.extend(resp.results)

        return SearchResponse(
            query=SearchQuery(original=f"{product_name} 新品", intent=SearchIntent.NEWS),
            results=all_results[:20], total_count=len(all_results),
            sources_used=["baidu", "news_baidu"], execution_time_ms=0
        )

    async def search_sentiment(self, brand_name: str) -> SearchResponse:
        """搜索市场舆情"""
        queries = [f"{brand_name} 口碑", f"{brand_name} 评价", f"{brand_name} 投诉"]
        responses = await asyncio.gather(*[self.searcher.search(q) for q in queries], return_exceptions=True)

        all_results = []
        for resp in responses:
            if isinstance(resp, SearchResponse):
                all_results.extend(resp.results)

        all_results = self.searcher._deduplicate(all_results)
        all_results = self.searcher._rank(all_results)

        return SearchResponse(
            query=SearchQuery(original=f"{brand_name} 舆情", intent=SearchIntent.REVIEW),
            results=all_results[:20], total_count=len(all_results),
            sources_used=["baidu", "zhihu"], execution_time_ms=0
        )


__all__ = ["SearchIntent", "SearchSource", "SearchResult", "SearchQuery",
           "SearchResponse", "MultiSourceSearcher", "DeepSearchPipeline", "QueryOptimizer"]