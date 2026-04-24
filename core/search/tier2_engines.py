"""
第二层：国内专业垂直免费API引擎

包含：知乎、豆瓣、高德地图、和风天气、GitHub
"""

import asyncio
import json
import re
from typing import List, Optional, Dict, Any
import httpx

from .models import SearchResult, TierLevel, APIConfig
from core.logger import get_logger
logger = get_logger('search.tier2_engines')



class BaseVerticalEngine:
    """垂直领域搜索引擎基类"""
    
    tier = TierLevel.TIER_2_CN_VERTICAL
    cn_support = True
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
        }
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        raise NotImplementedError


class ZhihuEngine(BaseVerticalEngine):
    """
    知乎搜索API
    
    无需认证（频率限制）
    适合深度分析、专业见解
    """
    
    name = "zhihu"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_2_CN_VERTICAL,
            api_url="https://www.zhihu.com/api/v4/search_v3",
            rate_limit=60,
            rate_limit_unit="minute",
            timeout=10.0,
            cn_support=True,
            description="知乎 - 专业问答社区",
            supported_types=["technical", "knowledge", "academic"],
        )
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行知乎搜索"""
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = "https://www.zhihu.com/api/v4/search_v3"
                params = {
                    "q": query,
                    "t": "general",
                    "correction": 1,
                    "offset": 0,
                    "limit": num_results,
                }
                
                headers = {
                    **self.base_headers,
                    "Referer": "https://www.zhihu.com/",
                }
                
                r = await client.get(url, params=params, headers=headers)
                r.raise_for_status()
                data = r.json()
                
                for item in data.get("data", [])[:num_results]:
                    obj = item.get("object", {})
                    if obj.get("type") == "answer":
                        question = obj.get("question", {})
                        results.append(SearchResult(
                            title=question.get("title", ""),
                            url=f"https://www.zhihu.com/question/{question.get('id', '')}",
                            snippet=obj.get("excerpt", "")[:200],
                            source="zhihu.com",
                            source_url="https://www.zhihu.com",
                            author=obj.get("author", {}).get("name", ""),
                            api_name=self.name,
                            tier=self.tier,
                        ))
                
        except Exception as e:
            logger.info(f"[ZhihuEngine] Search failed: {e}")
        
        return results


class DoubanEngine(BaseVerticalEngine):
    """
    豆瓣API
    
    无需认证（频率限制）
    适合书籍、电影、音乐信息查询
    """
    
    name = "douban"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_2_CN_VERTICAL,
            api_url="https://douban-api.itswincer.com/v2",
            rate_limit=40,
            rate_limit_unit="minute",
            timeout=10.0,
            cn_support=True,
            description="豆瓣 - 书籍电影音乐",
            supported_types=["entertainment", "knowledge"],
        )
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行豆瓣搜索"""
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"https://douban-api.itswincer.com/v2/book/search"
                params = {
                    "q": query,
                    "count": num_results,
                }
                
                r = await client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
                
                for item in data.get("books", [])[:num_results]:
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("alt", ""),
                        snippet=f"作者: {item.get('author', ['未知'])[0]} | 评分: {item.get('rating', {}).get('average', 'N/A')}",
                        source="douban.com",
                        source_url="https://www.douban.com",
                        author=item.get("author", [""])[0],
                        date=item.get("pubdate", ""),
                        api_name=self.name,
                        tier=self.tier,
                        extra_data={
                            "rating": item.get("rating", {}),
                            "publisher": item.get("publisher", ""),
                        }
                    ))
                
        except Exception as e:
            logger.info(f"[DoubanEngine] Book search failed: {e}")
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"https://douban-api.itswincer.com/v2/movie/search"
                params = {
                    "q": query,
                    "count": num_results,
                }
                
                r = await client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
                
                for item in data.get("subjects", [])[:num_results]:
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("alt", ""),
                        snippet=f"导演: {', '.join(item.get('directors', [])[:2])} | 评分: {item.get('rating', {}).get('average', 'N/A')}",
                        source="douban.com/movie",
                        source_url="https://movie.douban.com",
                        date=item.get("year", ""),
                        api_name=self.name,
                        tier=self.tier,
                        extra_data={
                            "rating": item.get("rating", {}),
                            "casts": item.get("casts", []),
                        }
                    ))
                
        except Exception as e:
            logger.info(f"[DoubanEngine] Movie search failed: {e}")
        
        return results[:num_results]


class GaodeEngine(BaseVerticalEngine):
    """
    高德地图 Web API
    
    免费额度：每日3000次
    适合地理位置、路径规划查询
    """
    
    name = "gaode"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.api_key = api_key
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_2_CN_VERTICAL,
            api_url="https://restapi.amap.com/v3",
            rate_limit=3000,
            rate_limit_unit="day",
            timeout=10.0,
            api_key=api_key,
            cn_support=True,
            description="高德地图 - 地理位置API",
            supported_types=["life"],
        )
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行高德地图搜索"""
        if not self.api_key:
            return []
        
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = "https://restapi.amap.com/v3/place/text"
                params = {
                    "key": self.api_key,
                    "keywords": query,
                    "types": "",
                    "city": "全国",
                    "offset": num_results,
                    "page": 1,
                    "extensions": "all",
                }
                
                r = await client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
                
                if data.get("status") == "1":
                    pois = data.get("pois", [])
                    for poi in pois[:num_results]:
                        location = poi.get("location", "")
                        address = poi.get("address", "")
                        
                        results.append(SearchResult(
                            title=poi.get("name", ""),
                            url=f"https://www.amap.com/detail/{poi.get('id', '')}",
                            snippet=f"{address} | 类型: {poi.get('type', '')}" if address else f"类型: {poi.get('type', '')}",
                            source="amap.com",
                            source_url="https://www.amap.com",
                            api_name=self.name,
                            tier=self.tier,
                            extra_data={
                                "location": location,
                                "tel": poi.get("tel", ""),
                                "pname": poi.get("pname", ""),
                                "cityname": poi.get("cityname", ""),
                            }
                        ))
                
        except Exception as e:
            logger.info(f"[GaodeEngine] Search failed: {e}")
        
        return results


class HefengEngine(BaseVerticalEngine):
    """
    和风天气 API
    
    免费额度：每日1000次
    适合天气、空气质量查询
    """
    
    name = "hefeng"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.api_key = api_key
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_2_CN_VERTICAL,
            api_url="https://devapi.qweather.com/v7",
            rate_limit=1000,
            rate_limit_unit="day",
            timeout=10.0,
            api_key=api_key,
            cn_support=True,
            description="和风天气 - 天气预报API",
            supported_types=["life"],
        )
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行和风天气搜索"""
        if not self.api_key:
            return []
        
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                search_url = "https://geoapi.qweather.com/v2/city/lookup"
                search_params = {
                    "key": self.api_key,
                    "location": query,
                }
                
                r = await client.get(search_url, params=search_params)
                r.raise_for_status()
                search_data = r.json()
                
                if search_data.get("code") == "200":
                    locations = search_data.get("location", [])
                    for loc in locations[:num_results]:
                        location_id = loc.get("id")
                        city_name = loc.get("name", "")
                        
                        weather_url = "https://devapi.qweather.com/v7/weather/now"
                        weather_params = {
                            "key": self.api_key,
                            "location": location_id,
                        }
                        
                        wr = await client.get(weather_url, params=weather_params)
                        weather_data = wr.json()
                        
                        weather_text = ""
                        if weather_data.get("code") == "200":
                            now = weather_data.get("now", {})
                            weather_text = f"天气: {now.get('text', '')} | 温度: {now.get('temp', '')}C | {now.get('windDir', '')}"
                        
                        results.append(SearchResult(
                            title=f"{city_name}天气预报",
                            url=f"https://www.qweather.com/weather/{loc.get('id', '')}",
                            snippet=weather_text,
                            source="qweather.com",
                            source_url="https://www.qweather.com",
                            api_name=self.name,
                            tier=self.tier,
                            extra_data={
                                "location_id": location_id,
                                "adm": loc.get("adm", ""),
                                "country": loc.get("country", ""),
                            }
                        ))
                
        except Exception as e:
            logger.info(f"[HefengEngine] Search failed: {e}")
        
        return results


class GithubEngine(BaseVerticalEngine):
    """
    GitHub API
    
    免费额度：未认证60次/小时，认证5000次/小时
    适合技术文档、开源项目搜索
    """
    
    name = "github"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.api_key = api_key
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_2_CN_VERTICAL,
            api_url="https://api.github.com/search",
            rate_limit=60,
            rate_limit_unit="hour",
            timeout=15.0,
            api_key=api_key,
            cn_support=False,
            description="GitHub - 代码项目管理",
            supported_types=["technical"],
        )
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行GitHub仓库搜索"""
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                url = "https://api.github.com/search/repositories"
                params = {
                    "q": query,
                    "sort": "stars",
                    "per_page": num_results,
                }
                
                headers = {
                    **self.base_headers,
                    "Accept": "application/vnd.github.v3+json",
                }
                
                if self.api_key:
                    headers["Authorization"] = f"token {self.api_key}"
                
                r = await client.get(url, params=params, headers=headers)
                r.raise_for_status()
                data = r.json()
                
                for item in data.get("items", [])[:num_results]:
                    results.append(SearchResult(
                        title=item.get("full_name", ""),
                        url=item.get("html_url", ""),
                        snippet=item.get("description", "") or "无描述",
                        source="github.com",
                        source_url="https://github.com",
                        author=item.get("owner", {}).get("login", ""),
                        date=item.get("created_at", "")[:10] if item.get("created_at") else None,
                        api_name=self.name,
                        tier=self.tier,
                        extra_data={
                            "stars": item.get("stargazers_count", 0),
                            "forks": item.get("forks_count", 0),
                            "language": item.get("language", ""),
                            "topics": item.get("topics", []),
                        }
                    ))
                
        except Exception as e:
            logger.info(f"[GithubEngine] Search failed: {e}")
        
        return results


__all__ = [
    "ZhihuEngine",
    "DoubanEngine",
    "GaodeEngine",
    "HefengEngine",
    "GithubEngine",
]
