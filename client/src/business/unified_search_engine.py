"""统一检索引擎 - 整合所有检索源"""

from typing import Optional, Dict, Any, List
from enum import Enum
import asyncio

class SearchSource(Enum):
    MEMORY = "memory"
    SKILL = "skill"
    WEB = "web"
    WIKI = "wiki"
    RAG = "rag"
    TOOL = "tool"

class UnifiedSearchEngine:
    """统一检索引擎"""
    
    def __init__(self):
        self._sources: Dict[str, Any] = {}
        self._priorities: Dict[str, float] = {
            SearchSource.MEMORY.value: 1.0,
            SearchSource.SKILL.value: 0.9,
            SearchSource.WIKI.value: 0.95,
            SearchSource.RAG.value: 0.85,
            SearchSource.WEB.value: 0.8,
            SearchSource.TOOL.value: 0.92,
        }
        self._initialized = False
    
    async def initialize(self):
        """初始化检索引擎"""
        if self._initialized:
            return
        
        from .intelligent_search_engine import IntelligentSearchEngine
        from .skill_matcher import SkillMatcher
        from .tools.tool_registry import ToolRegistry
        
        self._sources[SearchSource.WEB.value] = IntelligentSearchEngine()
        self._sources[SearchSource.SKILL.value] = SkillMatcher()
        self._sources[SearchSource.TOOL.value] = ToolRegistry.get_instance()
        
        await asyncio.gather(
            self._sources[SearchSource.WEB.value].initialize(),
            self._sources[SearchSource.SKILL.value].initialize()
        )
        
        self._initialized = True
    
    async def search(self, query: str, sources: Optional[List[SearchSource]] = None) -> List[Dict[str, Any]]:
        """统一搜索接口"""
        if not self._initialized:
            await self.initialize()
        
        if not sources:
            sources = list(SearchSource)
        
        tasks = []
        for source in sources:
            if source.value in self._sources:
                priority = self._priorities[source.value]
                tasks.append(self._search_source(source.value, query, priority))
        
        results = await asyncio.gather(*tasks)
        return self._merge_results([r for r in results if r])
    
    async def _search_source(self, source: str, query: str, priority: float):
        """搜索单个源"""
        try:
            if source == SearchSource.TOOL.value:
                return await self._search_tools(query, priority)
            
            results = await self._sources[source].search(query)
            for r in results:
                r["source"] = source
                r["priority"] = priority
            return results
        except Exception as e:
            print(f"Search failed for {source}: {e}")
            return []
    
    async def _search_tools(self, query: str, priority: float) -> List[Dict[str, Any]]:
        """搜索工具"""
        tool_registry = self._sources.get(SearchSource.TOOL.value)
        if not tool_registry:
            return []
        
        try:
            tools = tool_registry.discover(query)
            results = []
            
            for tool in tools:
                results.append({
                    "content": f"{tool.name}: {tool.description}",
                    "title": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "category": tool.category,
                    "version": tool.version,
                    "source": SearchSource.TOOL.value,
                    "priority": priority,
                    "relevance": 1.0,
                    "type": "tool",
                    "tool_name": tool.name,
                })
            
            return results
        except Exception as e:
            print(f"Tool search failed: {e}")
            return []
    
    def _merge_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并并排序结果"""
        seen = set()
        unique_results = []
        
        for r in results:
            key = f"{r.get('content', '')[:100]}"
            if key not in seen:
                seen.add(key)
                unique_results.append(r)
        
        unique_results.sort(key=lambda x: (x.get("priority", 0), x.get("relevance", 0)), reverse=True)
        
        return unique_results
    
    def add_source(self, name: str, source: Any, priority: float = 0.8):
        """添加自定义搜索源"""
        self._sources[name] = source
        self._priorities[name] = priority
    
    def remove_source(self, name: str):
        """移除搜索源"""
        self._sources.pop(name, None)
        self._priorities.pop(name, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "initialized": self._initialized,
            "sources": list(self._sources.keys()),
            "priorities": self._priorities,
        }

# 全局单例
_search_engine_instance = None

def get_unified_search_engine() -> UnifiedSearchEngine:
    """获取统一检索引擎实例"""
    global _search_engine_instance
    if _search_engine_instance is None:
        _search_engine_instance = UnifiedSearchEngine()
    return _search_engine_instance