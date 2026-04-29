"""
分层搜索集成模块

将免费网络搜索API分层策略与现有搜索工具集成
提供统一的搜索接口
"""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime

# 尝试导入分层搜索模块
try:
    from core.search import (
        SearchScheduler,
        TierRouter,
        TierLevel,
        QueryType,
    )
    TIERED_SEARCH_AVAILABLE = True
except ImportError:
    TIERED_SEARCH_AVAILABLE = False


class TieredSearchAdapter:
    """
    分层搜索适配器
    
    将分层搜索结果转换为现有SearchResult格式
    """
    
    def __init__(self):
        self.scheduler: Optional[SearchScheduler] = None
        self._initialized = False
    
    async def initialize(self):
        """初始化分层搜索调度器"""
        if not TIERED_SEARCH_AVAILABLE:
            print("[TieredSearchAdapter] 分层搜索模块不可用")
            return
        
        if self._initialized:
            return
        
        try:
            self.scheduler = SearchScheduler()
            self._initialized = True
            print("[TieredSearchAdapter] 分层搜索已初始化")
        except Exception as e:
            print(f"[TieredSearchAdapter] 初始化失败: {e}")
    
    async def search(
        self, 
        query: str, 
        num_results: int = 10,
        max_tier: int = 3,
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        执行分层搜索
        
        Args:
            query: 搜索查询
            num_results: 结果数量
            max_tier: 最大层级 (1-4)
            use_cache: 是否使用缓存
            
        Returns:
            搜索结果字典
        """
        if not self._initialized:
            await self.initialize()
        
        if not self.scheduler:
            return None
        
        # 转换层级
        tier_map = {
            1: TierLevel.TIER_1_CN_HIGH,
            2: TierLevel.TIER_2_CN_VERTICAL,
            3: TierLevel.TIER_3_GLOBAL,
            4: TierLevel.TIER_4_FALLBACK,
        }
        max_tier_level = tier_map.get(max_tier, TierLevel.TIER_3_GLOBAL)
        
        try:
            result = await self.scheduler.search(
                query=query,
                num_results=num_results,
                max_tier=max_tier_level,
                use_cache=use_cache,
                timeout=15.0
            )
            
            # 转换为字典格式
            return {
                "query": query,
                "results": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                        "source": r.source,
                        "date": r.date,
                        "api_name": r.api_name,
                        "tier": r.tier.value,
                        "quality_score": r.quality_score,
                        "relevance_score": r.relevance_score,
                    }
                    for r in result.results
                ],
                "stats": {
                    "total_results": len(result.results),
                    "unique_urls": result.unique_urls,
                    "avg_quality": result.avg_quality_score,
                    "avg_relevance": result.avg_relevance_score,
                    "sources": result.sources_used,
                    "tier_distribution": {
                        k.value: v for k, v in result.tier_distribution.items()
                    },
                    "cached": result.cached,
                },
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as e:
            print(f"[TieredSearchAdapter] 搜索失败: {e}")
            return None
    
    async def batch_search(
        self, 
        queries: List[str], 
        num_results: int = 10,
        max_tier: int = 3
    ) -> List[Optional[Dict[str, Any]]]:
        """
        批量搜索
        
        Args:
            queries: 查询列表
            num_results: 每个查询的结果数量
            max_tier: 最大层级
            
        Returns:
            结果列表
        """
        tasks = [
            self.search(q, num_results, max_tier)
            for q in queries
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [
            r if not isinstance(r, Exception) else None
            for r in results
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.scheduler:
            return {"error": "未初始化"}
        
        return self.scheduler.get_stats()
    
    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        if not self.scheduler:
            return {"error": "未初始化"}
        
        return self.scheduler.get_health_report()
    
    def clear_cache(self):
        """清空缓存"""
        if self.scheduler:
            self.scheduler.clear_cache()
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return TIERED_SEARCH_AVAILABLE and self._initialized


# 全局实例
_tiered_adapter: Optional[TieredSearchAdapter] = None


def get_tiered_adapter() -> TieredSearchAdapter:
    """获取全局分层搜索适配器"""
    global _tiered_adapter
    if _tiered_adapter is None:
        _tiered_adapter = TieredSearchAdapter()
    return _tiered_adapter


async def tiered_search(
    query: str,
    num_results: int = 10,
    max_tier: int = 3,
    use_cache: bool = True
) -> Optional[Dict[str, Any]]:
    """
    快捷搜索函数
    
    Args:
        query: 搜索查询
        num_results: 结果数量
        max_tier: 最大层级 (1=国内高速, 2=垂直专业, 3=全球免费, 4=备用)
        use_cache: 是否使用缓存
        
    Returns:
        搜索结果字典
    """
    adapter = get_tiered_adapter()
    await adapter.initialize()
    
    return await adapter.search(
        query=query,
        num_results=num_results,
        max_tier=max_tier,
        use_cache=use_cache
    )


__all__ = [
    "TieredSearchAdapter",
    "get_tiered_adapter",
    "tiered_search",
]
