"""
增强搜索系统 - 整合所有搜索功能
==================================

功能：
1. 智能路由 - 根据查询类型选择最优策略
2. 纠错搜索 - 错别字自动纠正
3. 持久化知识库 - ChromaDB 存储，搜索结果永不过期
4. 健康监控 - 自动选择可用引擎
5. 多源融合 - 结合本地知识库 + 联网搜索
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from core.knowledge_vector_db_persistent import (
    PersistentKnowledgeBase,
    ChineseTypoCorrector,
    TypoCorrection
)
from core.search_engine_monitor import SearchEngineMonitor, EngineStatus


class SearchSource(Enum):
    """搜索来源"""
    KNOWLEDGE_BASE = "knowledge_base"    # 本地知识库
    WEB_SEARCH = "web_search"          # 联网搜索
    CORRECTED = "corrected"            # 纠错后搜索
    FUSION = "fusion"                  # 融合结果


@dataclass
class SearchResult:
    """搜索结果"""
    content: str
    source: SearchSource
    url: Optional[str] = None
    score: float = 0.0
    correction: Optional[TypoCorrection] = None
    engine: str = ""


class EnhancedSearch:
    """
    增强搜索系统
    
    整合知识库、纠错、联网搜索的统一搜索接口
    """
    
    def __init__(self):
        # 持久化知识库
        self.kb = PersistentKnowledgeBase()
        
        # 错别字纠错
        self.typo_corrector = ChineseTypoCorrector()
        
        # 搜索引擎监控
        self.engine_monitor = SearchEngineMonitor()
        
        # HTTP 客户端
        import httpx
        self.http = httpx.AsyncClient(timeout=15.0)
        
        print("[EnhancedSearch] 初始化完成")
        print(f"[EnhancedSearch] 知识库: {self.kb.count()} 条记录")
    
    async def search(
        self,
        query: str,
        use_kb: bool = True,
        use_correction: bool = True,
        use_web: bool = True,
        top_k: int = 10
    ) -> List[SearchResult]:
        """
        增强搜索
        
        Args:
            query: 查询文本
            use_kb: 是否搜索本地知识库
            use_correction: 是否使用错别字纠错
            use_web: 是否联网搜索
            top_k: 返回结果数量
            
        Returns:
            List[SearchResult]: 搜索结果
        """
        results = []
        correction_used = None
        
        # 1. 知识库搜索（优先）
        if use_kb:
            kb_results = self._search_knowledge_base(query)
            results.extend(kb_results)
            
            # 如果知识库有结果，检查是否需要纠错后重试
            if not kb_results and use_correction:
                correction = self.typo_corrector.correct(query)
                if correction.corrections:
                    correction_used = correction
                    print(f"[EnhancedSearch] 纠错: {query} -> {correction.corrected}")
                    kb_results_corrected = self._search_knowledge_base(correction.corrected)
                    for r in kb_results_corrected:
                        r.correction = correction
                    results.extend(kb_results_corrected)
        
        # 2. 联网搜索（如果知识库无结果或结果不足）
        if use_web and len(results) < top_k:
            web_results = await self._search_web(query)
            results.extend(web_results)
            
            # 如果没有结果且有纠错，尝试纠错后的搜索
            if not web_results and use_correction and not correction_used:
                correction = self.typo_corrector.correct(query)
                if correction.corrections:
                    correction_used = correction
                    print(f"[EnhancedSearch] 纠错: {query} -> {correction.corrected}")
                    web_results_corrected = await self._search_web(correction.corrected)
                    for r in web_results_corrected:
                        r.correction = correction
                    results.extend(web_results_corrected)
        
        # 去重（按 URL）
        seen_urls = set()
        unique_results = []
        for r in results:
            if r.url and r.url in seen_urls:
                continue
            if r.url:
                seen_urls.add(r.url)
            unique_results.append(r)
        
        return unique_results[:top_k]
    
    def _search_knowledge_base(self, query: str) -> List[SearchResult]:
        """搜索本地知识库"""
        kb_results = self.kb.search(query, top_k=5)
        
        return [
            SearchResult(
                content=r["content"],
                source=SearchSource.KNOWLEDGE_BASE,
                url=r.get("url"),
                score=r.get("score", 0),
            )
            for r in kb_results
        ]
    
    async def _search_web(self, query: str) -> List[SearchResult]:
        """联网搜索"""
        # 获取可用引擎
        available = self.engine_monitor.get_available_engines()
        
        if not available:
            print("[EnhancedSearch] 无可用搜索引擎")
            return []
        
        results = []
        
        # 尝试每个可用引擎
        for engine_name, health in available[:3]:  # 最多尝试3个
            try:
                results = await self._search_with_engine(engine_name, query)
                if results:
                    print(f"[EnhancedSearch] {engine_name} 返回 {len(results)} 条结果")
                    break
            except Exception as e:
                print(f"[EnhancedSearch] {engine_name} 搜索失败: {e}")
                continue
        
        return results
    
    async def _search_with_engine(self, engine: str, query: str) -> List[SearchResult]:
        """使用指定引擎搜索"""
        import re
        
        configs = {
            "360": {
                "url": "https://www.so.com/s",
                "params": {"q": query, "pn": 1, "rn": 10},
            },
            "bing": {
                "url": "https://cn.bing.com/search",
                "params": {"q": query, "first": 0, "count": 10},
            },
            "sogou": {
                "url": "https://www.sogou.com/web",
                "params": {"query": query, "page": 1},
            },
        }
        
        if engine not in configs:
            return []
        
        config = configs[engine]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            response = await self.http.get(
                config["url"],
                params=config["params"],
                headers=headers,
                follow_redirects=True
            )
            
            if response.status_code != 200:
                return []
            
            html = response.text
            
            # 解析结果
            results = []
            
            if engine == "360":
                # 360搜索结果
                pattern = r'<h3[^>]*class="[^"]*res-title[^"]*"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
                matches = re.findall(pattern, html, re.DOTALL)
                
                for url, title_html in matches[:10]:
                    title = re.sub(r'<[^>]+>', '', title_html).strip()
                    if title and url.startswith('http'):
                        results.append(SearchResult(
                            content=title,
                            source=SearchSource.WEB_SEARCH,
                            url=url,
                            engine=engine
                        ))
            
            elif engine == "bing":
                # 必应结果
                pattern = r'<li class="b_algo"[^>]*>.*?<a href="([^"]+)"[^>]*><h2>([^<]+)</h2>'
                matches = re.findall(pattern, html, re.DOTALL)
                
                for url, title in matches[:10]:
                    title = re.sub(r'<[^>]+>', '', title).strip()
                    if title and url.startswith('http'):
                        results.append(SearchResult(
                            content=title,
                            source=SearchSource.WEB_SEARCH,
                            url=url,
                            engine=engine
                        ))
            
            elif engine == "sogou":
                # 搜狗结果
                pattern = r'<h3[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
                matches = re.findall(pattern, html, re.DOTALL)
                
                for url, title_html in matches[:10]:
                    title = re.sub(r'<[^>]+>', '', title_html).strip()
                    if title and url.startswith('http'):
                        results.append(SearchResult(
                            content=title,
                            source=SearchSource.WEB_SEARCH,
                            url=url,
                            engine=engine
                        ))
            
            return results
            
        except Exception as e:
            print(f"[EnhancedSearch] {engine} 搜索异常: {e}")
            return []
    
    def add_to_knowledge_base(
        self,
        content: str,
        query: str = "",
        source: str = "",
        url: str = ""
    ):
        """添加知识到本地知识库"""
        self.kb.add(
            content=content,
            source=source or "manual",
            query=query,
            url=url
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "knowledge_base": self.kb.get_stats(),
            "available_engines": [
                {"name": name, "response_time": health.avg_response_time}
                for name, health in self.engine_monitor.get_available_engines()
            ],
            "best_engine": self.engine_monitor.get_best_engine(),
        }


# 全局实例
_enhanced_search: Optional[EnhancedSearch] = None


def get_enhanced_search() -> EnhancedSearch:
    """获取增强搜索实例"""
    global _enhanced_search
    if _enhanced_search is None:
        _enhanced_search = EnhancedSearch()
    return _enhanced_search


if __name__ == "__main__":
    # 测试
    import sys
    
    async def test():
        search = get_enhanced_search()
        
        print("=== 增强搜索测试 ===\n")
        
        # 测试纠错
        test_queries = [
            "吉奥环鹏",
            "吉奥环朋",
            "这家公司怎么样",
        ]
        
        for q in test_queries:
            print(f"\n查询: {q}")
            print("-" * 40)
            
            correction = search.typo_corrector.correct(q)
            if correction.corrections:
                print(f"纠错: {correction.corrections}")
            
            results = await search.search(q)
            print(f"找到 {len(results)} 条结果")
            
            for i, r in enumerate(results[:3], 1):
                print(f"  {i}. [{r.source.value}] {r.content[:50]}...")
        
        # 添加吉奥环朋信息
        print("\n\n=== 添加知识到知识库 ===")
        search.add_to_knowledge_base(
            content="吉奥环朋科技（江苏）有限公司成立于2021年，注册资本5000万人民币，位于南京市雨花台区",
            query="吉奥环朋",
            source="test"
        )
        search.add_to_knowledge_base(
            content="吉奥环朋科技（扬州）有限公司成立于2021年，注册资本12250万人民币，主要业务包括新兴能源技术研发、锂电池回收",
            query="吉奥环朋",
            source="test"
        )
        
        # 再次搜索
        print("\n=== 搜索 吉奥环鹏（测试纠错）===")
        results = await search.search("吉奥环鹏")
        print(f"找到 {len(results)} 条结果")
        for i, r in enumerate(results[:3], 1):
            print(f"  {i}. {r.content[:60]}...")
            if r.correction:
                print(f"     纠错: {r.correction.corrections}")
        
        print(f"\n统计: {search.get_stats()}")
    
    asyncio.run(test())
