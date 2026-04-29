"""
第一层：国内高稳定性免费API引擎

包含：百度搜索、搜狗搜索、360搜索、天行数据、聚合数据
"""

import asyncio
import json
import re
from typing import List, Optional, Dict, Any
import httpx

from .models import SearchResult, TierLevel, APIConfig, QueryType


class BaseCNEngine:
    """国内搜索引擎基类"""
    
    tier = TierLevel.TIER_1_CN_HIGH
    cn_support = True
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        raise NotImplementedError
    
    def _detect_file_type(self, url: str) -> Optional[str]:
        """检测URL中的文件类型"""
        url_lower = url.lower()
        patterns = [
            (r'\.pdf[\?#]?', 'pdf'),
            (r'\.docx?[\?#]?', 'doc'),
            (r'\.xlsx?[\?#]?', 'xlsx'),
            (r'\.pptx?[\?#]?', 'ppt'),
            (r'\.zip[\?#]?', 'zip'),
            (r'\.rar[\?#]?', 'rar'),
        ]
        for pattern, ftype in patterns:
            if re.search(pattern, url_lower):
                return ftype
        return None
    
    def _extract_date(self, text: str) -> Optional[str]:
        """从文本中提取日期"""
        patterns = [
            r'(\d{4})[年\-\/](\d{1,2})[月\-\/](\d{1,2})',
            r'(\d{1,2})[月\-\/](\d{1,2})[日]?',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None


class BaiduEngine(BaseCNEngine):
    """
    百度搜索开放平台
    
    免费额度：每日1000次
    需要API Key（可从百度搜索资源平台申请）
    """
    
    name = "baidu"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_1_CN_HIGH,
            api_url="https://api.baidu.com/json/sms/v4/SearchHandler/search",
            rate_limit=1000,
            rate_limit_unit="day",
            timeout=10.0,
            api_key=api_key,
            cn_support=True,
            description="百度搜索开放平台",
        )
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行百度搜索"""
        # 百度搜索需要使用网页抓取方式（非官方API）
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # 使用百度搜索（模拟浏览器请求）
                url = "https://www.baidu.com/s"
                params = {
                    "wd": query,
                    "rn": num_results,
                    "ie": "utf-8",
                }
                
                r = await client.get(url, params=params, headers=self.base_headers)
                r.raise_for_status()
                
                # 解析HTML（简化版）
                html = r.text
                results = self._parse_baidu_html(html, num_results)
                
        except Exception as e:
            print(f"[BaiduEngine] Search failed: {e}")
        
        return results
    
    def _parse_baidu_html(self, html: str, num_results: int) -> List[SearchResult]:
        """解析百度搜索结果HTML"""
        results = []
        
        # 提取搜索结果块
        result_pattern = r'<h3 class="t">.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?</h3>'
        matches = re.findall(result_pattern, html, re.DOTALL)
        
        # 提取摘要
        snippet_pattern = r'<span class="c-color-gray">(.*?)</span>'
        
        for url, title_html in matches[:num_results]:
            # 清理HTML标签
            title = re.sub(r'<[^>]+>', '', title_html)
            title = title.strip()
            
            if title and url.startswith('http'):
                # 查找对应的摘要
                snippet = ""
                snippet_match = re.search(rf'href="{re.escape(url)}"[^>]*>.*?<div class="c-abstract">(.*?)</div>', html, re.DOTALL)
                if snippet_match:
                    snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1))[:200]
                
                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="baidu.com",
                    source_url="https://www.baidu.com",
                    file_type=self._detect_file_type(url),
                    api_name=self.name,
                    tier=self.tier,
                ))
        
        return results


class SogouEngine(BaseCNEngine):
    """
    搜狗搜索API
    
    免费额度：每日500次
    无需认证（有限制）
    """
    
    name = "sogou"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_1_CN_HIGH,
            api_url="https://www.sogou.com/suggnew/ajajjson",
            rate_limit=500,
            rate_limit_unit="day",
            timeout=10.0,
            cn_support=True,
            description="搜狗搜索",
        )
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行搜狗搜索"""
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = "https://www.sogou.com/web"
                params = {
                    "query": query,
                    "ie": "utf-8",
                    "type": "web",
                }
                
                r = await client.get(url, params=params, headers=self.base_headers)
                r.raise_for_status()
                
                html = r.text
                results = self._parse_sogou_html(html, num_results)
                
        except Exception as e:
            print(f"[SogouEngine] Search failed: {e}")
        
        return results
    
    def _parse_sogou_html(self, html: str, num_results: int) -> List[SearchResult]:
        """解析搜狗搜索结果HTML"""
        results = []
        
        # 提取结果
        pattern = r'<h3 class="[^"]*">.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for url, title_html in matches[:num_results]:
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            
            if title and url.startswith('http'):
                # 提取摘要
                snippet = ""
                snippet_match = re.search(
                    rf'href="{re.escape(url)}"[^>]*>.*?<p class="[^"]*">(.*?)</p>',
                    html, re.DOTALL
                )
                if snippet_match:
                    snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1))[:200]
                
                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="sogou.com",
                    source_url="https://www.sogou.com",
                    file_type=self._detect_file_type(url),
                    api_name=self.name,
                    tier=self.tier,
                ))
        
        return results


class So360Engine(BaseCNEngine):
    """
    360搜索开放平台
    
    免费额度：每日300次
    需要企业认证
    """
    
    name = "so360"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_1_CN_HIGH,
            api_url="https://s.so.360.com/s",
            rate_limit=300,
            rate_limit_unit="day",
            timeout=10.0,
            cn_support=True,
            description="360搜索",
        )
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行360搜索"""
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = "https://www.so.com/s"
                params = {
                    "q": query,
                    "ie": "utf-8",
                }
                
                r = await client.get(url, params=params, headers=self.base_headers)
                r.raise_for_status()
                
                html = r.text
                results = self._parse_360_html(html, num_results)
                
        except Exception as e:
            print(f"[So360Engine] Search failed: {e}")
        
        return results
    
    def _parse_360_html(self, html: str, num_results: int) -> List[SearchResult]:
        """解析360搜索结果HTML"""
        results = []
        
        pattern = r'<h3[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for url, title_html in matches[:num_results]:
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            
            if title and url.startswith('http'):
                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet="",
                    source="so.com",
                    source_url="https://www.so.com",
                    file_type=self._detect_file_type(url),
                    api_name=self.name,
                    tier=self.tier,
                ))
        
        return results


class TiangongEngine(BaseCNEngine):
    """
    天行数据 API
    
    免费额度：每日500次（新闻、百科）
    需要API Key
    官网：https://www.tianapi.com/
    """
    
    name = "tiangong"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.api_key = api_key
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_1_CN_HIGH,
            api_url="https://apis.tianapi.com/",
            rate_limit=500,
            rate_limit_unit="day",
            timeout=10.0,
            api_key=api_key,
            cn_support=True,
            description="天行数据 - 新闻百科API",
        )
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行天行数据搜索"""
        if not self.api_key:
            return []
        
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # 使用天行数据的网络搜索接口
                url = "https://apis.tianapi.com/network/index"
                params = {
                    "key": self.api_key,
                    "word": query,
                    "num": num_results,
                }
                
                r = await client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
                
                if data.get("code") == 200:
                    newslist = data.get("result", {}).get("newslist", [])
                    for item in newslist:
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            snippet=item.get("description", "")[:200],
                            source=item.get("source", ""),
                            date=item.get("ctime", ""),
                            api_name=self.name,
                            tier=self.tier,
                        ))
                
        except Exception as e:
            print(f"[TiangongEngine] Search failed: {e}")
        
        return results


class JuhuasuanEngine(BaseCNEngine):
    """
    聚合数据 API
    
    免费额度：每日100次
    多源聚合，有广告
    官网：https://www.juhe.cn/
    """
    
    name = "juhuasuan"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.api_key = api_key
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_1_CN_HIGH,
            api_url="https://apis.juhe.cn/",
            rate_limit=100,
            rate_limit_unit="day",
            timeout=10.0,
            api_key=api_key,
            cn_support=True,
            description="聚合数据 - 综合API平台",
        )
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行聚合数据搜索"""
        if not self.api_key:
            return []
        
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # 使用聚合数据的社会搜索接口
                url = "https://apis.juhe.cn/social/search"
                params = {
                    "key": self.api_key,
                    "q": query,
                    "page": 1,
                    "page_size": num_results,
                }
                
                r = await client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
                
                if data.get("error_code") == 0:
                    result_list = data.get("result", {}).get("data", [])
                    for item in result_list:
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            snippet=item.get("summary", "")[:200],
                            source=item.get("source", ""),
                            date=item.get("date", ""),
                            api_name=self.name,
                            tier=self.tier,
                        ))
                
        except Exception as e:
            print(f"[JuhuasuanEngine] Search failed: {e}")
        
        return results


# 导出所有Tier-1引擎
__all__ = [
    "BaiduEngine",
    "SogouEngine",
    "So360Engine",
    "TiangongEngine",
    "JuhuasuanEngine",
]
