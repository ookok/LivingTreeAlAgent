"""
第三层：国外免费API引擎

包含：DuckDuckGo、Wikipedia、Open Library
适合：英文内容、国际资讯、百科知识
"""

import asyncio
import json
import re
from typing import List, Optional, Dict, Any
import httpx

from .models import SearchResult, TierLevel, APIConfig


class BaseGlobalEngine:
    """国外搜索引擎基类"""
    
    tier = TierLevel.TIER_3_GLOBAL
    cn_support = False
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        raise NotImplementedError


class DuckDuckGoEngine(BaseGlobalEngine):
    """
    DuckDuckGo Instant Answer API
    
    免费，无需API Key
    隐私友好，英文结果为主
    适合：通用搜索、隐私搜索
    """
    
    name = "duckduckgo"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_3_GLOBAL,
            api_url="https://api.duckduckgo.com/",
            rate_limit=100,
            rate_limit_unit="minute",
            timeout=15.0,
            cn_support=False,
            description="DuckDuckGo - 隐私友好搜索引擎",
        )
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行DuckDuckGo搜索"""
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                }
                
                r = await client.get(self.config.api_url, params=params, headers=self.base_headers)
                r.raise_for_status()
                data = r.json()
                
                # 解析Abstract（首选结果）
                if data.get("AbstractText"):
                    results.append(SearchResult(
                        title=data.get("Heading", query),
                        url=data.get("AbstractURL", ""),
                        snippet=data["AbstractText"],
                        source=data.get("AbstractSource", ""),
                        date=data.get("AbstractTimestamp", ""),
                        api_name=self.name,
                        tier=self.tier,
                    ))
                
                # 解析Related Topics
                for topic in data.get("RelatedTopics", [])[:num_results-1]:
                    if "Text" in topic and "FirstURL" in topic:
                        icon_url = topic.get("Icon", {}).get("URL", "")
                        source = icon_url.split("/")[-2] if icon_url else "duckduckgo"
                        
                        results.append(SearchResult(
                            title=topic.get("Text", "")[:200],
                            url=topic["FirstURL"],
                            snippet=topic.get("Text", ""),
                            source=source,
                            source_url="https://duckduckgo.com",
                            api_name=self.name,
                            tier=self.tier,
                        ))
                
        except Exception as e:
            print(f"[DuckDuckGoEngine] Search failed: {e}")
        
        return results[:num_results]


class WikipediaEngine(BaseGlobalEngine):
    """
    Wikipedia API
    
    免费，无需认证
    适合：百科知识、学术信息
    支持多语言
    """
    
    name = "wikipedia"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_3_GLOBAL,
            api_url="https://en.wikipedia.org/w/api.php",
            rate_limit=200,
            rate_limit_unit="minute",
            timeout=10.0,
            cn_support=True,  # 支持中文维基
            description="Wikipedia - 维基百科",
        )
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行Wikipedia搜索"""
        results = []
        
        # 尝试中文维基
        urls = [
            ("https://zh.wikipedia.org/w/api.php", "zh.wikipedia.org"),
            ("https://en.wikipedia.org/w/api.php", "en.wikipedia.org"),
        ]
        
        for api_url, source_name in urls:
            if results:
                break
                
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    params = {
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "format": "json",
                        "utf8": 1,
                        "srlimit": num_results,
                        "srprop": "snippet|timestamp",
                    }
                    
                    r = await client.get(api_url, params=params, headers=self.base_headers)
                    r.raise_for_status()
                    data = r.json()
                    
                    search_results = data.get("query", {}).get("search", [])
                    
                    for item in search_results[:num_results]:
                        page_id = item.get("pageid")
                        snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
                        
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            url=f"https://{source_name}/wiki/{item.get('title', '').replace(' ', '_')}",
                            snippet=snippet[:200],
                            source=source_name,
                            source_url=f"https://{source_name}",
                            date=item.get("timestamp", "")[:10] if item.get("timestamp") else None,
                            api_name=self.name,
                            tier=self.tier,
                            extra_data={"page_id": page_id}
                        ))
                    
            except Exception as e:
                print(f"[WikipediaEngine] Search failed ({source_name}): {e}")
                continue
        
        return results[:num_results]


class OpenLibraryEngine(BaseGlobalEngine):
    """
    Open Library API
    
    免费，无需认证
    适合：书籍元数据查询
    """
    
    name = "openlibrary"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_3_GLOBAL,
            api_url="https://openlibrary.org/search.json",
            rate_limit=100,
            rate_limit_unit="minute",
            timeout=15.0,
            cn_support=False,
            description="Open Library - 开放图书库",
        )
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行Open Library书籍搜索"""
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                params = {
                    "q": query,
                    "limit": num_results,
                    "fields": "key,title,author_name,first_publish_year,subject,cover_i,ratings_average",
                }
                
                r = await client.get(self.config.api_url, params=params, headers=self.base_headers)
                r.raise_for_status()
                data = r.json()
                
                docs = data.get("docs", [])
                
                for doc in docs[:num_results]:
                    authors = doc.get("author_name", ["Unknown"])
                    rating = doc.get("ratings_average", 0)
                    
                    results.append(SearchResult(
                        title=doc.get("title", ""),
                        url=f"https://openlibrary.org{doc.get('key', '')}",
                        snippet=f"作者: {', '.join(authors[:2])} | 首发: {doc.get('first_publish_year', 'N/A')} | 评分: {rating:.1f}",
                        source="openlibrary.org",
                        source_url="https://openlibrary.org",
                        author=authors[0] if authors else None,
                        date=str(doc.get("first_publish_year", "")) if doc.get("first_publish_year") else None,
                        api_name=self.name,
                        tier=self.tier,
                        extra_data={
                            "rating": rating,
                            "subjects": doc.get("subject", [])[:5],
                            "cover_id": doc.get("cover_i"),
                        }
                    ))
                
        except Exception as e:
            print(f"[OpenLibraryEngine] Search failed: {e}")
        
        return results


class RedditEngine(BaseGlobalEngine):
    """
    Reddit API
    
    免费，需要注册应用获取credentials
    适合：社区讨论、技术反馈
    """
    
    name = "reddit"
    
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        super().__init__()
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_3_GLOBAL,
            api_url="https://www.reddit.com/search.json",
            rate_limit=60,
            rate_limit_unit="minute",
            timeout=15.0,
            api_key=client_id,
            api_secret=client_secret,
            cn_support=False,
            description="Reddit - 社区讨论",
        )
    
    async def _get_access_token(self) -> Optional[str]:
        """获取Reddit访问令牌"""
        if not self.client_id or not self.client_secret:
            return None
            
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                auth = httpx.BasicAuth(self.client_id, self.client_secret)
                r = await client.post(
                    "https://www.reddit.com/api/v1/access_token",
                    data={"grant_type": "client_credentials"},
                    auth=auth,
                    headers={"User-Agent": "HermesDesktop/1.0"}
                )
                r.raise_for_status()
                data = r.json()
                return data.get("access_token")
        except Exception as e:
            print(f"[RedditEngine] Auth failed: {e}")
            return None
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行Reddit搜索"""
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                headers = {
                    **self.base_headers,
                    "User-Agent": "HermesDesktop/1.0",
                }
                
                # 未认证请求
                url = "https://www.reddit.com/search.json"
                params = {
                    "q": query,
                    "limit": num_results,
                    "sort": "relevance",
                }
                
                r = await client.get(url, params=params, headers=headers)
                r.raise_for_status()
                data = r.json()
                
                children = data.get("data", {}).get("children", [])
                
                for child in children[:num_results]:
                    post = child.get("data", {})
                    results.append(SearchResult(
                        title=post.get("title", ""),
                        url=f"https://www.reddit.com{post.get('permalink', '')}",
                        snippet=post.get("selftext", "")[:200] or post.get("link_flair_text", ""),
                        source=f"reddit.com/r/{post.get('subreddit', '')}",
                        source_url="https://www.reddit.com",
                        author=post.get("author", ""),
                        date=datetime.fromtimestamp(post.get("created_utc", 0)).isoformat()[:10] if post.get("created_utc") else None,
                        api_name=self.name,
                        tier=self.tier,
                        extra_data={
                            "score": post.get("score", 0),
                            "num_comments": post.get("num_comments", 0),
                            "subreddit": post.get("subreddit", ""),
                        }
                    ))
                    
        except Exception as e:
            print(f"[RedditEngine] Search failed: {e}")
        
        return results


# 辅助函数
from datetime import datetime


__all__ = [
    "DuckDuckGoEngine",
    "WikipediaEngine",
    "OpenLibraryEngine",
    "RedditEngine",
]
