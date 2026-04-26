"""
网络搜索动作处理器
支持多种搜索引擎，集成到IntentEngine
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from .base import BaseActionHandler, ActionContext, ActionResult, ActionResultStatus

logger = logging.getLogger(__name__)


class WebSearchHandler(BaseActionHandler):
    """
    网络搜索动作处理器
    
    支持的搜索引擎：
    - DuckDuckGo（默认，无需API key）
    - Google（需要API key）
    - Bing（需要API key）
    - Baidu（中文搜索）
    """
    
    # 搜索引擎配置
    SEARCH_ENGINES = {
        "duckduckgo": {
            "name": "DuckDuckGo",
            "url": "https://api.duckduckgo.com/",
            "need_api_key": False,
        },
        "google": {
            "name": "Google",
            "url": "https://www.googleapis.com/customsearch/v1",
            "need_api_key": True,
        },
        "bing": {
            "name": "Bing",
            "url": "https://api.bing.microsoft.com/v7.0/search",
            "need_api_key": True,
        },
        "baidu": {
            "name": "Baidu",
            "url": "https://www.baidu.com/s",
            "need_api_key": False,
        },
    }
    
    def __init__(self, default_engine: str = "duckduckgo", max_results: int = 10):
        """
        初始化搜索处理器
        
        Args:
            default_engine: 默认搜索引擎
            max_results: 最大结果数
        """
        self.default_engine = default_engine
        self.max_results = max_results
        self.api_keys: Dict[str, str] = {}
        
        logger.info(f"WebSearchHandler 初始化: 默认引擎={default_engine}, 最大结果={max_results}")
    
    def set_api_key(self, engine: str, api_key: str):
        """设置API key"""
        self.api_keys[engine] = api_key
        logger.info(f"设置 {engine} API key")
    
    async def handle(self, context: ActionContext) -> ActionResult:
        """
        执行网络搜索
        
        context.kwargs 可以包含：
        - query: 搜索查询（必需）
        - engine: 搜索引擎（可选，默认使用default_engine）
        - max_results: 最大结果数（可选）
        - language: 语言（可选，如 'zh-CN', 'en-US'）
        """
        query = context.kwargs.get("query", "")
        if not query:
            return ActionResult(
                status=ActionResultStatus.FAILURE,
                error="缺少搜索查询 (query)",
            )
        
        engine = context.kwargs.get("engine", self.default_engine)
        max_results = context.kwargs.get("max_results", self.max_results)
        language = context.kwargs.get("language", "zh-CN")
        
        logger.info(f"执行网络搜索: query='{query}', engine={engine}")
        
        try:
            # 根据搜索引擎选择搜索方法
            if engine == "duckduckgo":
                results = await self._search_duckduckgo(query, max_results, language)
            elif engine == "google":
                results = await self._search_google(query, max_results, language)
            elif engine == "bing":
                results = await self._search_bing(query, max_results, language)
            elif engine == "baidu":
                results = await self._search_baidu(query, max_results)
            else:
                return ActionResult(
                    status=ActionResultStatus.FAILURE,
                    error=f"不支持的搜索引擎: {engine}",
                )
            
            # 格式化结果
            formatted_results = self._format_results(results)
            
            return ActionResult(
                status=ActionResultStatus.SUCCESS,
                data={
                    "query": query,
                    "engine": engine,
                    "results": results,
                    "formatted": formatted_results,
                    "count": len(results),
                    "timestamp": datetime.now().isoformat(),
                },
            )
        
        except Exception as e:
            logger.error(f"网络搜索失败: {e}")
            return ActionResult(
                status=ActionResultStatus.FAILURE,
                error=f"搜索失败: {str(e)}",
            )
    
    async def _search_duckduckgo(self, query: str, max_results: int, language: str) -> List[Dict]:
        """使用 DuckDuckGo 搜索"""
        try:
            import aiohttp
            
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
                "kl": language,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # 解析结果
                        results = []
                        
                        # AbstractText（摘要）
                        if data.get("AbstractText"):
                            results.append({
                                "title": data.get("Heading", ""),
                                "url": data.get("AbstractURL", ""),
                                "snippet": data.get("AbstractText", ""),
                                "source": "Abstract",
                            })
                        
                        # RelatedTopics（相关主题）
                        for topic in data.get("RelatedTopics", [])[:max_results - len(results)]:
                            if "Text" in topic and "FirstURL" in topic:
                                results.append({
                                    "title": topic.get("Text", "").split(" - ")[0],
                                    "url": topic["FirstURL"],
                                    "snippet": topic["Text"],
                                    "source": "RelatedTopic",
                                })
                        
                        return results[:max_results]
                    else:
                        logger.error(f"DuckDuckGo 搜索失败: {resp.status}")
                        return []
        
        except ImportError:
            logger.warning("aiohttp 未安装，尝试使用 requests")
            return self._search_duckduckgo_sync(query, max_results, language)
        except Exception as e:
            logger.error(f"DuckDuckGo 搜索异常: {e}")
            return []
    
    def _search_duckduckgo_sync(self, query: str, max_results: int, language: str) -> List[Dict]:
        """同步版本的 DuckDuckGo 搜索"""
        try:
            import requests
            
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
                "kl": language,
            }
            
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                
                results = []
                
                if data.get("AbstractText"):
                    results.append({
                        "title": data.get("Heading", ""),
                        "url": data.get("AbstractURL", ""),
                        "snippet": data.get("AbstractText", ""),
                        "source": "Abstract",
                    })
                
                for topic in data.get("RelatedTopics", [])[:max_results - len(results)]:
                    if "Text" in topic and "FirstURL" in topic:
                        results.append({
                            "title": topic["Text"].split(" - ")[0],
                            "url": topic["FirstURL"],
                            "snippet": topic["Text"],
                            "source": "RelatedTopic",
                        })
                
                return results[:max_results]
            else:
                return []
        
        except Exception as e:
            logger.error(f"DuckDuckGo 同步搜索异常: {e}")
            return []
    
    async def _search_google(self, query: str, max_results: int, language: str) -> List[Dict]:
        """使用 Google Custom Search API 搜索"""
        if "google" not in self.api_keys:
            logger.error("Google 搜索需要 API key")
            return []
        
        try:
            import aiohttp
            
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.api_keys["google"],
                "cx": "YOUR_SEARCH_ENGINE_ID",  # 需要用户配置
                "q": query,
                "num": min(max_results, 10),  # Google API 每次最多10条
                "lr": language,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        results = []
                        for item in data.get("items", []):
                            results.append({
                                "title": item.get("title", ""),
                                "url": item.get("link", ""),
                                "snippet": item.get("snippet", ""),
                                "source": "Google",
                            })
                        
                        return results[:max_results]
                    else:
                        logger.error(f"Google 搜索失败: {resp.status}")
                        return []
        
        except Exception as e:
            logger.error(f"Google 搜索异常: {e}")
            return []
    
    async def _search_bing(self, query: str, max_results: int, language: str) -> List[Dict]:
        """使用 Bing Search API 搜索"""
        if "bing" not in self.api_keys:
            logger.error("Bing 搜索需要 API key")
            return []
        
        try:
            import aiohttp
            
            url = "https://api.bing.microsoft.com/v7.0/search"
            headers = {"Ocp-Apim-Subscription-Key": self.api_keys["bing"]}
            params = {
                "q": query,
                "count": max_results,
                "setLang": language,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        results = []
                        for item in data.get("webPages", {}).get("value", []):
                            results.append({
                                "title": item.get("name", ""),
                                "url": item.get("url", ""),
                                "snippet": item.get("snippet", ""),
                                "source": "Bing",
                            })
                        
                        return results[:max_results]
                    else:
                        logger.error(f"Bing 搜索失败: {resp.status}")
                        return []
        
        except Exception as e:
            logger.error(f"Bing 搜索异常: {e}")
            return []
    
    async def _search_baidu(self, query: str, max_results: int) -> List[Dict]:
        """使用百度搜索（网页抓取）"""
        try:
            import aiohttp
            from bs4 import BeautifulSoup
            
            url = "https://www.baidu.com/s"
            params = {
                "wd": query,
                "rn": max_results,
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        results = []
                        for item in soup.select(".result")[:max_results]:
                            title_elem = item.select_one("h3 a")
                            snippet_elem = item.select_one(".c-abstract")
                            
                            if title_elem:
                                results.append({
                                    "title": title_elem.text,
                                    "url": title_elem.get("href", ""),
                                    "snippet": snippet_elem.text if snippet_elem else "",
                                    "source": "Baidu",
                                })
                        
                        return results
                    else:
                        logger.error(f"百度搜索失败: {resp.status}")
                        return []
        
        except ImportError:
            logger.warning("BeautifulSoup 未安装，无法使用百度搜索")
            return []
        except Exception as e:
            logger.error(f"百度搜索异常: {e}")
            return []
    
    def _format_results(self, results: List[Dict]) -> str:
        """格式化搜索结果为可读文本"""
        if not results:
            return "未找到相关结果。"
        
        lines = [f"找到 {len(results)} 条结果：\n"]
        
        for i, result in enumerate(results, 1):
            lines.append(f"{i}. {result['title']}")
            lines.append(f"   URL: {result['url']}")
            if result.get('snippet'):
                lines.append(f"   {result['snippet']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_supported_engines(self) -> List[str]:
        """获取支持的搜索引擎列表"""
        return list(self.SEARCH_ENGINES.keys())
    
    def test_connection(self, engine: str = None) -> bool:
        """测试搜索引擎连接"""
        engine = engine or self.default_engine
        
        try:
            # 简单测试：搜索 "test"
            loop = asyncio.get_event_loop()
            results = loop.run_until_complete(self._search_duckduckgo("test", 1, "en-US"))
            return len(results) > 0
        except:
            return False
