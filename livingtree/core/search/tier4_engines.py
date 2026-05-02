"""
第四层：备用方案引擎

包含：本地缓存引擎、知识库引擎
特点：稳定性最高、非实时数据、适合兜底
"""

import json
import os
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import re

from .models import SearchResult, TierLevel, APIConfig


class BaseFallbackEngine:
    """备用方案引擎基类"""
    
    tier = TierLevel.TIER_4_FALLBACK
    
    def __init__(self):
        pass
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        raise NotImplementedError


class LocalCacheEngine(BaseFallbackEngine):
    """
    本地缓存引擎
    
    特点：
    - 数据来自之前的搜索请求缓存
    - 实时性依赖缓存更新时间
    - 零网络请求
    - 适合：热门查询、历史查询
    """
    
    name = "local_cache"
    
    def __init__(self, cache_dir: Optional[Path] = None, ttl_hours: int = 24):
        super().__init__()
        self.cache_dir = cache_dir or Path.home() / ".hermes-desktop" / "search_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_4_FALLBACK,
            api_url="local://cache",
            rate_limit=999999,  # 无限制
            cn_support=True,
            description="本地缓存 - 历史搜索结果",
        )
    
    def _get_cache_key(self, query: str) -> str:
        """生成缓存键"""
        return hashlib.sha256(query.encode()).hexdigest()[:16]
    
    def _is_cache_valid(self, cache_file: Path) -> bool:
        """检查缓存是否有效"""
        if not cache_file.exists():
            return False
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        return datetime.now() - mtime < self.ttl
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """从本地缓存搜索"""
        results = []
        
        # 精确匹配
        cache_key = self._get_cache_key(query)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if self._is_cache_valid(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                for item in data.get("results", [])[:num_results]:
                    result = SearchResult(
                        title=item["title"],
                        url=item["url"],
                        snippet=item["snippet"],
                        source=item["source"],
                        date=item.get("date"),
                        api_name=self.name,
                        tier=self.tier,
                    )
                    result.is_cached = True
                    result.cached_at = datetime.fromisoformat(item["cached_at"]) if item.get("cached_at") else None
                    results.append(result)
                    
                # 标记为缓存结果
                return results
                
            except Exception as e:
                print(f"[LocalCacheEngine] Load cache failed: {e}")
        
        # 模糊匹配 - 在缓存目录中搜索相似查询
        results = await self._fuzzy_search(query, num_results)
        
        return results
    
    async def _fuzzy_search(self, query: str, num_results: int) -> List[SearchResult]:
        """模糊搜索缓存"""
        results = []
        query_keywords = set(query.lower().split())
        
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # 检查查询相似度
                cached_query = data.get("query", "").lower()
                cached_keywords = set(cached_query.split())
                
                # 计算关键词重叠度
                overlap = len(query_keywords & cached_keywords)
                if overlap >= 2:  # 至少2个关键词匹配
                    for item in data.get("results", [])[:3]:
                        result = SearchResult(
                            title=item["title"],
                            url=item["url"],
                            snippet=item["snippet"],
                            source=item["source"],
                            date=item.get("date"),
                            relevance_score=overlap / max(len(query_keywords), 1),
                            api_name=self.name,
                            tier=self.tier,
                        )
                        result.is_cached = True
                        result.cached_at = datetime.fromtimestamp(cache_file.stat().st_mtime)
                        results.append(result)
                        
            except Exception:
                continue
        
        # 按相关性排序
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:num_results]
    
    def save_to_cache(self, query: str, results: List[SearchResult]) -> None:
        """保存结果到缓存"""
        cache_key = self._get_cache_key(query)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        data = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "source": r.source,
                    "date": r.date,
                    "cached_at": datetime.now().isoformat(),
                }
                for r in results
            ]
        }
        
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[LocalCacheEngine] Save cache failed: {e}")


class KnowledgeBaseEngine(BaseFallbackEngine):
    """
    本地知识库引擎
    
    特点：
    - 基于本地预构建的知识数据库
    - 支持向量相似度搜索
    - 适合：专业领域知识、常见问题
    - 数据定期更新
    """
    
    name = "knowledge_base"
    
    def __init__(self, kb_dir: Optional[Path] = None):
        super().__init__()
        self.kb_dir = kb_dir or Path.home() / ".hermes-desktop" / "knowledge_base"
        self.kb_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_4_FALLBACK,
            api_url="local://knowledge_base",
            rate_limit=999999,
            cn_support=True,
            description="本地知识库 - 领域专业知识",
        )
        
        # 预定义的领域知识
        self._init_default_kb()
    
    def _init_default_kb(self):
        """初始化默认知识库"""
        # 常见编程知识
        self.programming_kb = {
            "python": [
                ("Python官网", "https://www.python.org", "Python官方文档和教程"),
                ("Python Package Index", "https://pypi.org", "Python第三方包索引"),
                ("Real Python", "https://realpython.com", "Python教程和文章"),
            ],
            "javascript": [
                ("MDN Web Docs", "https://developer.mozilla.org", "JavaScript官方文档"),
                ("npm", "https://www.npmjs.com", "Node.js包管理器"),
            ],
            "github": [
                ("GitHub", "https://github.com", "全球最大代码托管平台"),
                ("GitHub Docs", "https://docs.github.com", "GitHub使用文档"),
            ],
        }
        
        # 常见工具知识
        self.tools_kb = {
            "docker": [
                ("Docker官网", "https://www.docker.com", "容器化平台"),
                ("Docker Hub", "https://hub.docker.com", "Docker镜像仓库"),
            ],
            "kubernetes": [
                ("Kubernetes官网", "https://kubernetes.io", "容器编排平台"),
            ],
            "git": [
                ("Git官网", "https://git-scm.com", "版本控制系统"),
            ],
        }
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """搜索本地知识库"""
        results = []
        query_lower = query.lower()
        
        # 检查编程知识
        for topic, entries in self.programming_kb.items():
            if topic in query_lower:
                for title, url, snippet in entries:
                    results.append(SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source="knowledge_base",
                        relevance_score=0.8,
                        api_name=self.name,
                        tier=self.tier,
                    ))
        
        # 检查工具知识
        for topic, entries in self.tools_kb.items():
            if topic in query_lower:
                for title, url, snippet in entries:
                    results.append(SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source="knowledge_base",
                        relevance_score=0.8,
                        api_name=self.name,
                        tier=self.tier,
                    ))
        
        # 加载用户自定义知识库
        user_results = await self._search_user_kb(query, num_results)
        results.extend(user_results)
        
        # 去重
        seen_urls = set()
        unique_results = []
        for r in results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(r)
        
        return unique_results[:num_results]
    
    async def _search_user_kb(self, query: str, num_results: int) -> List[SearchResult]:
        """搜索用户自定义知识库"""
        results = []
        
        user_kb_file = self.kb_dir / "custom_kb.json"
        if user_kb_file.exists():
            try:
                with open(user_kb_file, "r", encoding="utf-8") as f:
                    custom_kb = json.load(f)
                
                query_keywords = set(query.lower().split())
                
                for item in custom_kb:
                    title = item.get("title", "").lower()
                    content = item.get("content", "").lower()
                    
                    # 简单关键词匹配
                    if any(kw in title or kw in content for kw in query_keywords):
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            snippet=item.get("content", "")[:200],
                            source="user_knowledge_base",
                            relevance_score=0.6,
                            api_name=self.name,
                            tier=self.tier,
                        ))
                        
            except Exception as e:
                print(f"[KnowledgeBaseEngine] Load user KB failed: {e}")
        
        return results
    
    def add_to_knowledge_base(self, title: str, url: str, content: str, category: str = "custom") -> bool:
        """添加知识到本地知识库"""
        user_kb_file = self.kb_dir / "custom_kb.json"
        
        custom_kb = []
        if user_kb_file.exists():
            try:
                with open(user_kb_file, "r", encoding="utf-8") as f:
                    custom_kb = json.load(f)
            except:
                pass
        
        custom_kb.append({
            "title": title,
            "url": url,
            "content": content,
            "category": category,
            "added_at": datetime.now().isoformat(),
        })
        
        try:
            with open(user_kb_file, "w", encoding="utf-8") as f:
                json.dump(custom_kb, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[KnowledgeBaseEngine] Add to KB failed: {e}")
            return False


class SemanticsCacheEngine(BaseFallbackEngine):
    """
    语义缓存引擎
    
    特点：
    - 基于向量相似度匹配
    - 即使查询不完全相同也能返回相关结果
    - 适合：自然语言查询
    """
    
    name = "semantic_cache"
    
    def __init__(self, cache_dir: Optional[Path] = None, similarity_threshold: float = 0.7):
        super().__init__()
        self.cache_dir = cache_dir or Path.home() / ".hermes-desktop" / "semantic_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.similarity_threshold = similarity_threshold
        
        self.config = APIConfig(
            name=self.name,
            tier=TierLevel.TIER_4_FALLBACK,
            api_url="local://semantic_cache",
            rate_limit=999999,
            cn_support=True,
            description="语义缓存 - 相似查询匹配",
        )
    
    def _compute_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（简单TF-IDF）"""
        # 简化的相似度计算
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """语义搜索缓存"""
        results = []
        
        cache_file = self.cache_dir / "semantic_index.json"
        if not cache_file.exists():
            return results
        
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                index = json.load(f)
            
            for item in index:
                cached_query = item.get("query", "")
                similarity = self._compute_similarity(query, cached_query)
                
                if similarity >= self.similarity_threshold:
                    for result_data in item.get("results", [])[:3]:
                        result = SearchResult(
                            title=result_data["title"],
                            url=result_data["url"],
                            snippet=result_data["snippet"],
                            source=result_data["source"],
                            date=result_data.get("date"),
                            relevance_score=similarity,
                            api_name=self.name,
                            tier=self.tier,
                        )
                        result.is_cached = True
                        results.append(result)
                        
        except Exception as e:
            print(f"[SemanticsCacheEngine] Search failed: {e}")
        
        return results[:num_results]


__all__ = [
    "LocalCacheEngine",
    "KnowledgeBaseEngine",
    "SemanticsCacheEngine",
]
